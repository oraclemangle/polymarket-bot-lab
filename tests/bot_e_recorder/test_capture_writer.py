"""Tests for the recorder writer loop + handlers (no real network)."""
from __future__ import annotations

import asyncio
import json
import time as time_mod
from contextlib import suppress
from pathlib import Path

import pytest

from bots.bot_e_recorder.capture import (
    RecorderState,
    _drain_queues,
    _enqueue_bulk,
    _enqueue_priority,
    _flush_batch,
    _make_cex_handler,
    _make_pm_handler,
    _subscription_id,
    _WriteTask,
    discovery_loop,
)
from bots.bot_e_recorder.market_discovery import CryptoMarket
from bots.bot_e_recorder.schema import init_db
from core.cex_ws import CexTrade
from core.polymarket_ws import WSSEvent


class TestHandlers:
    @pytest.mark.asyncio
    async def test_pm_handler_enqueues_typed_row(self):
        state = RecorderState(Path("/tmp/unused.db"))
        handler = _make_pm_handler(state)
        ev = WSSEvent(
            event_type="book",
            payload={"asset_id": "tok1", "bids": [["0.4", "10"]]},
            received_at_ms=1000,
            subscription_id="sub1",
        )
        await handler(ev)
        assert state.write_queue.qsize() == 1
        task = await state.write_queue.get()
        assert task.kind == "pm_event"
        assert task.row["event_type"] == "book"
        assert task.row["asset_id"] == "tok1"
        assert task.row["subscription_id"] == "sub1"
        # payload_json must be valid JSON
        decoded = json.loads(task.row["payload_json"])
        assert decoded["asset_id"] == "tok1"

    @pytest.mark.asyncio
    async def test_pm_handler_tracks_last_seen(self):
        state = RecorderState(Path("/tmp/unused.db"))
        handler = _make_pm_handler(state)
        ev = WSSEvent("book", {}, 12345, "sub1")
        await handler(ev)
        assert state.last_pm_by_sub_ms["sub1"] == 12345

    @pytest.mark.asyncio
    async def test_cex_handler_enqueues_typed_row(self):
        state = RecorderState(Path("/tmp/unused.db"))
        handler = _make_cex_handler(state)
        t = CexTrade(
            symbol="BTCUSDT", price=68000.0, size=0.01,
            trade_time_ms=999, received_at_ms=1000,
            is_buyer_maker=True,
        )
        await handler(t)
        assert state.last_cex_ms == 1000
        task = await state.write_queue.get()
        assert task.kind == "cex_trade"
        assert task.row["symbol"] == "BTCUSDT"
        assert task.row["is_buyer_maker"] == 1

    @pytest.mark.asyncio
    async def test_pm_handler_drops_instead_of_blocking_when_bulk_queue_full(self):
        state = RecorderState(Path("/tmp/unused.db"))
        state.write_queue = asyncio.Queue(maxsize=1)
        state.write_queue.put_nowait(_WriteTask(kind="pm_event", row={}))
        handler = _make_pm_handler(state)
        ev = WSSEvent(
            event_type="book",
            payload={"asset_id": "tok1"},
            received_at_ms=1000,
            subscription_id="sub1",
        )

        await asyncio.wait_for(handler(ev), timeout=0.1)

        assert state.write_queue.qsize() == 1
        assert state.dropped_counts["pm_event"] == 1
        assert state.last_pm_by_sub_ms["sub1"] == 1000

    def test_priority_queue_still_accepts_when_bulk_queue_full(self):
        state = RecorderState(Path("/tmp/unused.db"))
        state.write_queue = asyncio.Queue(maxsize=1)
        state.priority_write_queue = asyncio.Queue(maxsize=1)
        state.write_queue.put_nowait(_WriteTask(kind="pm_event", row={}))

        ok = _enqueue_priority(
            state,
            _WriteTask(kind="heartbeat", row={"source": "process"}),
        )

        assert ok is True
        assert state.priority_write_queue.qsize() == 1
        assert state.dropped_counts == {}

    def test_drain_queues_prioritises_liveness_rows(self):
        state = RecorderState(Path("/tmp/unused.db"))
        _enqueue_bulk(state, _WriteTask(kind="pm_event", row={"n": 1}))
        _enqueue_priority(state, _WriteTask(kind="heartbeat", row={"n": 2}))

        batch: list[_WriteTask] = []
        drained = _drain_queues(state, batch, limit=2)

        assert drained == 2
        assert [task.kind for task in batch] == ["heartbeat", "pm_event"]


class TestFlushBatch:
    def test_empty_batch_noop(self, tmp_path: Path):
        conn = init_db(tmp_path / "rec.db")
        try:
            _flush_batch(conn, [])
            n = conn.execute("SELECT COUNT(*) FROM pm_events").fetchone()[0]
            assert n == 0
        finally:
            conn.close()

    def test_flush_mixed_batch(self, tmp_path: Path):
        conn = init_db(tmp_path / "rec.db")
        try:
            batch = [
                _WriteTask(kind="pm_event", row={
                    "received_at_ms": 1, "subscription_id": "s",
                    "event_type": "book", "asset_id": "t", "condition_id": "c",
                    "payload_json": "{}",
                }),
                _WriteTask(kind="cex_trade", row={
                    "received_at_ms": 1, "trade_time_ms": 1, "symbol": "BTCUSDT",
                    "price": 68000.0, "size": 0.01, "is_buyer_maker": 1,
                }),
                _WriteTask(kind="market", row={
                    "scan_at_ms": 1, "condition_id": "c", "question": "q",
                    "end_date_iso": "2026-04-17T00:00:00+00:00",
                    "yes_token_id": "yt", "no_token_id": "nt",
                    "volume_24h_usd": 100.0, "yes_price": 0.5,
                    "category": "crypto", "raw_json": "{}",
                }),
                _WriteTask(kind="heartbeat", row={
                    "emitted_at_ms": 1, "source": "pm",
                    "subscription_id": "s", "last_message_age_sec": 0.1,
                    "metadata_json": None,
                }),
            ]
            _flush_batch(conn, batch)
            assert conn.execute("SELECT COUNT(*) FROM pm_events").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM cex_trades").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM markets").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM heartbeats").fetchone()[0] == 1
        finally:
            conn.close()

    def test_flush_does_not_raise_on_bad_row(self, tmp_path: Path, caplog):
        """Per ADR-022: a bad write must not bring down capture."""
        conn = init_db(tmp_path / "rec.db")
        try:
            bad_batch = [
                _WriteTask(kind="pm_event", row={
                    # Missing required payload_json; SQLite will reject (NOT NULL)
                    "received_at_ms": 1, "subscription_id": "s",
                    "event_type": "book", "asset_id": None, "condition_id": None,
                }),
            ]
            # Should not raise
            _flush_batch(conn, bad_batch)
        finally:
            conn.close()


class TestSubscriptionId:
    def test_stable_format(self):
        from datetime import UTC, datetime
        from decimal import Decimal
        m = CryptoMarket(
            condition_id="c1", question="Up or down on BTC...",
            symbol="BTC",
            end_date=datetime(2026, 4, 17, 15, 15, tzinfo=UTC),
            yes_token_id="yt", no_token_id="nt",
            yes_price=Decimal("0.5"), volume_24h_usd=Decimal("100"),
            duration_minutes=15,
            raw={},
        )
        assert _subscription_id(m) == "btc-15m-20260417T1515"

    def test_duration_prevents_5m_15m_collision(self):
        from dataclasses import replace
        from datetime import UTC, datetime
        from decimal import Decimal

        base = CryptoMarket(
            condition_id="c1", question="Up or down on BTC...",
            symbol="BTC",
            end_date=datetime(2026, 4, 17, 15, 15, tzinfo=UTC),
            yes_token_id="yt", no_token_id="nt",
            yes_price=Decimal("0.5"), volume_24h_usd=Decimal("100"),
            duration_minutes=15,
            raw={},
        )

        assert _subscription_id(replace(base, duration_minutes=5)) != _subscription_id(base)


class TestCloseSubscription:
    """Session 39 / OQ-056 regression: closing a subscription must drop
    EVERY per-sub entry from RecorderState. Previously
    last_pm_by_sub_ms was left populated, leaking across market
    rotations and inflating heartbeat fan-out."""

    @pytest.mark.asyncio
    async def test_pops_all_per_sub_state(self):
        from datetime import UTC, datetime

        from bots.bot_e_recorder.capture import _close_subscription

        state = RecorderState(Path("/tmp/unused.db"))
        # Populate every per-sub field for two subs.
        for sid in ("btc-2026", "eth-2026"):
            state.last_pm_by_sub_ms[sid] = 999_000_000_000
            state.pm_end_dates[sid] = datetime.now(UTC)

        # No real WSS task or client — ``_close_subscription`` must
        # tolerate their absence (already removed elsewhere).
        await _close_subscription(state, "btc-2026")

        assert "btc-2026" not in state.last_pm_by_sub_ms
        assert "btc-2026" not in state.pm_end_dates
        assert "eth-2026" in state.last_pm_by_sub_ms  # other sub untouched
        assert "btc-2026" not in state.pm_tasks
        assert "btc-2026" not in state.pm_clients

    @pytest.mark.asyncio
    async def test_idempotent(self):
        """Calling close on an already-closed sub is a no-op, not an
        error. Important because the discovery loop iterates over a
        list copy and another path could have popped first."""
        from bots.bot_e_recorder.capture import _close_subscription

        state = RecorderState(Path("/tmp/unused.db"))
        await _close_subscription(state, "missing")
        await _close_subscription(state, "missing")
        assert state.last_pm_by_sub_ms == {}

    @pytest.mark.asyncio
    async def test_calls_client_close_when_present(self):
        from bots.bot_e_recorder.capture import _close_subscription

        state = RecorderState(Path("/tmp/unused.db"))
        state.last_pm_by_sub_ms["btc-2026"] = 1
        closed = {"called": False}

        class FakeClient:
            async def close(self):
                closed["called"] = True

        class FakeTask:
            def __init__(self):
                self.cancelled = False
            def cancel(self):
                self.cancelled = True

        fake_client = FakeClient()
        fake_task = FakeTask()
        state.pm_clients["btc-2026"] = fake_client
        state.pm_tasks["btc-2026"] = fake_task

        await _close_subscription(state, "btc-2026")
        assert closed["called"] is True
        assert fake_task.cancelled is True
        assert "btc-2026" not in state.last_pm_by_sub_ms
        assert "btc-2026" not in state.pm_end_dates


class TestDiscoveryBackpressure:
    @pytest.mark.asyncio
    async def test_reconciles_subscriptions_even_when_bulk_queue_is_full(
        self, monkeypatch
    ):
        state = RecorderState(Path("/tmp/unused.db"))
        state.write_queue = asyncio.Queue(maxsize=1)
        state.write_queue.put_nowait(_WriteTask(kind="pm_event", row={}))
        closed = {"called": False}

        class FakeClient:
            async def close(self):
                closed["called"] = True

        class FakeTask:
            def cancel(self):
                pass

        state.pm_clients["old-sub"] = FakeClient()
        state.pm_tasks["old-sub"] = FakeTask()
        state.last_pm_by_sub_ms["old-sub"] = 1

        monkeypatch.setattr(
            "bots.bot_e_recorder.capture.fetch_live_crypto_markets",
            lambda **kwargs: [],
        )

        task = asyncio.create_task(discovery_loop(state))
        try:
            for _ in range(20):
                if closed["called"] and "old-sub" not in state.pm_tasks:
                    break
                await asyncio.sleep(0.05)
            assert closed["called"] is True
            assert "old-sub" not in state.pm_tasks
            assert "old-sub" not in state.last_pm_by_sub_ms
            assert state.priority_write_queue.qsize() == 1
        finally:
            state._closed = True
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    @pytest.mark.asyncio
    async def test_retains_subscription_until_end_grace_when_gamma_drops_it(
        self, monkeypatch
    ):
        from datetime import UTC, datetime, timedelta

        state = RecorderState(Path("/tmp/unused.db"))

        class FakeClient:
            async def close(self):
                raise AssertionError("subscription should be retained before end grace")

        class FakeTask:
            def cancel(self):
                raise AssertionError("subscription should be retained before end grace")

        sub_id = "btc-5m-20260515T2250"
        state.pm_clients[sub_id] = FakeClient()
        state.pm_tasks[sub_id] = FakeTask()
        state.last_pm_by_sub_ms[sub_id] = 1
        state.pm_end_dates[sub_id] = datetime.now(UTC) + timedelta(seconds=45)

        monkeypatch.setattr(
            "bots.bot_e_recorder.capture.fetch_live_crypto_markets",
            lambda **kwargs: [],
        )

        task = asyncio.create_task(discovery_loop(state))
        try:
            await asyncio.sleep(0.05)
            assert sub_id in state.pm_tasks
            assert sub_id in state.pm_clients
            assert sub_id in state.pm_end_dates
        finally:
            state._closed = True
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


class TestWriterAliveTick:
    """Session 39 / OQ-055 follow-up: writer_loop must update
    state.last_flush_ts on every iteration, even when the queue is empty.
    Otherwise the watchdog_ping_loop fires writer_stall_abort whenever
    market activity dies below the heartbeat cadence — a false positive,
    since the writer is alive and just has nothing to flush.

    These tests exercise the writer_loop directly to verify the tick
    fires on quiet ticks and not only on successful flushes."""

    @pytest.mark.asyncio
    async def test_tick_updates_last_flush_ts_when_queue_is_empty(
        self, tmp_path: Path
    ):
        """Run writer_loop for a few iterations against an empty queue
        and assert state.last_flush_ts moves forward. Pre-fix this would
        have stayed at 0.0 indefinitely (false stall)."""
        from bots.bot_e_recorder.capture import writer_loop

        db_path = tmp_path / "rec.db"
        conn = init_db(db_path)
        state = RecorderState(db_path)
        state.conn = conn

        before = time_mod.time()
        # Run writer_loop in the background, then close after enough
        # iterations to give the alive-tick a few chances to fire.
        task = asyncio.create_task(writer_loop(state))

        # FLUSH_INTERVAL is 2.0s and the loop body iterates at least once
        # per FLUSH_INTERVAL. 0.3s is enough for several iterations
        # (timeout shrinks as last_flush ages).
        await asyncio.sleep(0.3)
        state._closed = True
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except TimeoutError:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        after = time_mod.time()
        assert state.last_flush_ts > 0.0, "tick never fired"
        # Tick should be within the wall-clock window the loop ran.
        assert before <= state.last_flush_ts <= after, (
            f"tick {state.last_flush_ts} outside window [{before}, {after}]"
        )
        conn.close()

    @pytest.mark.asyncio
    async def test_tick_continues_to_advance(self, tmp_path: Path):
        """Two snapshots of state.last_flush_ts must show forward
        progress across multiple loop iterations — proving the loop
        body keeps iterating even with no queue activity. Pre-fix this
        would advance only when a real flush happened (i.e. never, with
        an empty queue), so within ~95s the writer_stall_abort guard
        would false-positive."""
        from bots.bot_e_recorder.capture import writer_loop

        db_path = tmp_path / "rec.db"
        conn = init_db(db_path)
        state = RecorderState(db_path)
        state.conn = conn

        task = asyncio.create_task(writer_loop(state))
        # First iteration ticks immediately on entry, then awaits the
        # 2.0s FLUSH_INTERVAL timeout. Sleep > FLUSH_INTERVAL so the
        # second iteration starts and ticks again.
        await asyncio.sleep(0.05)
        snapshot_1 = state.last_flush_ts
        await asyncio.sleep(2.3)
        snapshot_2 = state.last_flush_ts

        state._closed = True
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except TimeoutError:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        assert snapshot_2 > snapshot_1, (
            f"writer_loop tick stalled: {snapshot_1} -> {snapshot_2}"
        )
        # Should have advanced by >= 2 seconds (one FLUSH_INTERVAL).
        assert snapshot_2 - snapshot_1 >= 1.5, (
            f"tick advanced only {snapshot_2 - snapshot_1:.2f}s; "
            f"expected >= 1.5s after a FLUSH_INTERVAL pass"
        )
        conn.close()
