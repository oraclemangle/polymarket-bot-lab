"""Tests for bot_e_btc_scalp/__main__.py — live loop wiring.

Covers:
1. High-OBI signal triggers an order placement.
2. DB halt flag prevents order placement.
3. Regime-chop blocks placement (no order placed).
4. Fixed-$30 size is used despite Kelly recommendation differing.
5. Paper-collection mode starts without GO-file (ADR-022.1).
6. Low-OBI signal below threshold produces no order.
"""
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import bots.bot_e_btc_scalp.__main__ as main_mod
from bots.bot_e_btc_scalp.signal import ObiSignal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(obi: float = 0.5, side: str = "BUY_YES") -> ObiSignal:
    return ObiSignal(
        subscription_id="btc-test-cid",
        side=side,
        obi=obi,
        abs_obi=abs(obi),
        window_sec=120,
        n_trades=10,
        total_volume=Decimal("500"),
        yes_price=Decimal("0.55"),
        no_price=Decimal("0.45"),
        ts_ms=int(time.time() * 1000),
    )


def _make_book(midpoint: float = 0.55):
    """Return a mock OrderBook with fixed midpoint."""
    book = MagicMock()
    book.best_bid.return_value = Decimal(str(midpoint - 0.01))
    book.best_ask.return_value = Decimal(str(midpoint + 0.01))
    book.midpoint.return_value = Decimal(str(midpoint))
    book.timestamp = time.time()
    return book


def _make_market(cid: str = "btc-test-cid", minutes_to_res: float = 7.0):
    """Return a mock CryptoMarket within the entry window (t-5 to t-10 min)."""
    m = MagicMock()
    m.condition_id = cid
    m.symbol = "BTC"
    m.question = "Will BTC go up or down in 15 min?"
    m.yes_token_id = "yes-token-123"
    m.no_token_id = "no-token-456"
    m.yes_price = Decimal("0.55")
    m.minutes_to_resolution.return_value = minutes_to_res
    return m


def _make_clob(order_status: str = "PAPER_OPEN", order_id: str = "paper-abc123"):
    """Return a mock ClobWrapper."""
    clob = MagicMock()
    resp = MagicMock()
    resp.order_id = order_id
    resp.status = order_status
    clob.place_limit.return_value = resp
    clob.get_book.return_value = _make_book(0.55)
    return clob


def _base_patches(clob, markets, signal_val=None, chop=False, halted=False):
    """Return a list of patch context managers for the common run() path."""
    patches = [
        patch.object(main_mod, "_is_db_halted", return_value=halted),
        patch.object(main_mod, "_persist_order", return_value="paper-abc001"),
        patch.object(main_mod, "ClobWrapper", return_value=clob),
        patch.object(main_mod, "init_db"),
        patch.object(main_mod, "fetch_live_crypto_markets", return_value=markets),
        patch.object(main_mod, "should_skip_due_to_chop", return_value=chop),
        patch.object(main_mod, "_cex_cvd_gate_ok", return_value=(True, "test")),
        patch.object(main_mod, "_depth_gate_ok", return_value=(True, "test")),
        patch.object(main_mod, "_persist_book_snapshot"),
        patch.object(main_mod, "_emit_bot_e_event"),
        patch.object(main_mod, "_emit_scan_summary"),
    ]
    if signal_val is not None:
        patches.append(patch.object(main_mod, "maybe_fire", return_value=signal_val))
    return patches


async def _run_one_iter(patches_list):
    """Run the main loop for a short time then cancel."""
    with _nested(*patches_list):
        task = asyncio.create_task(main_mod.run(is_live=False))
        await asyncio.sleep(0.75)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class _nested:
    """Context manager that enters multiple context managers in sequence."""
    def __init__(self, *cms):
        self._cms = cms
        self._entered = []

    def __enter__(self):
        for cm in self._cms:
            self._entered.append(cm.__enter__())
        return self._entered

    def __exit__(self, *exc):
        for cm in reversed(self._cms):
            cm.__exit__(*exc)


# ---------------------------------------------------------------------------
# Test 1: High-OBI signal triggers order placement
# ---------------------------------------------------------------------------

def test_high_obi_triggers_order():
    """A strong OBI signal (above threshold) in a trending market places an order."""
    call_count = []

    fake_clob = _make_clob()
    original = fake_clob.place_limit

    def capture(*args, **kwargs):
        call_count.append(1)
        return original(*args, **kwargs)

    fake_clob.place_limit = capture

    async def go():
        patches = _base_patches(
            clob=fake_clob,
            markets=[_make_market()],
            signal_val=_make_signal(obi=0.6),
            chop=False,
            halted=False,
        )
        await _run_one_iter(patches)

    asyncio.run(go())
    assert len(call_count) >= 1, "Expected at least one order placement for high-OBI signal"


# ---------------------------------------------------------------------------
# Test 2: Halt flag prevents order placement
# ---------------------------------------------------------------------------

def test_halt_flag_prevents_order():
    """When DB halt flag is active, no order is placed."""
    placed = []
    fake_clob = _make_clob()
    fake_clob.place_limit.side_effect = lambda *a, **k: placed.append(1)

    async def go():
        patches = _base_patches(
            clob=fake_clob,
            markets=[_make_market()],
            signal_val=_make_signal(obi=0.9),
            chop=False,
            halted=True,  # <-- halted
        )
        await _run_one_iter(patches)

    asyncio.run(go())
    assert len(placed) == 0, "Halted bot must not place orders"


# ---------------------------------------------------------------------------
# Test 3: Regime chop blocks placement
# ---------------------------------------------------------------------------

def test_regime_chop_blocks_order():
    """When should_skip_due_to_chop returns True, no order is placed."""
    placed = []
    fake_clob = _make_clob()
    fake_clob.place_limit.side_effect = lambda *a, **k: placed.append(1)

    async def go():
        patches = _base_patches(
            clob=fake_clob,
            markets=[_make_market()],
            signal_val=_make_signal(obi=0.9),
            chop=True,  # <-- choppy regime
            halted=False,
        )
        await _run_one_iter(patches)

    asyncio.run(go())
    assert len(placed) == 0, "Choppy regime must block order placement"


# ---------------------------------------------------------------------------
# Test 4: Fixed $30 size is used despite Kelly recommendation differing
# ---------------------------------------------------------------------------

def test_fixed_30_used_before_threshold():
    """For the first 200 paper trades, effective_fixed must equal PAPER_FIXED_TRADE_USD ($30)."""
    effective_sizes = []

    def mock_try_enter(signal, state, **kw):
        effective_sizes.append(kw["fixed_trade_usd"])
        # Return rejected so we don't need a real clob placement
        from bots.bot_e_btc_scalp.executor import EntryDecision
        return EntryDecision(accepted=False, reason="test_intercept")

    fake_clob = _make_clob()

    async def go():
        patches = _base_patches(
            clob=fake_clob,
            markets=[_make_market()],
            signal_val=_make_signal(obi=0.9),
            chop=False,
            halted=False,
        )
        patches.append(patch.object(main_mod, "try_enter", side_effect=mock_try_enter))
        await _run_one_iter(patches)

    asyncio.run(go())
    assert len(effective_sizes) >= 1, "try_enter should have been called at least once"
    # Audit 2026-04-17: constants moved to config.BOT_E_PAPER_FIXED_USD.
    from bots.bot_e_btc_scalp import config as _cfg
    for sz in effective_sizes:
        assert sz == _cfg.BOT_E_PAPER_FIXED_USD, (
            f"Expected fixed_trade_usd={_cfg.BOT_E_PAPER_FIXED_USD}, got {sz}"
        )


# ---------------------------------------------------------------------------
# Test 5: Paper-collection mode starts without GO-file (ADR-022.1)
# ---------------------------------------------------------------------------

def test_paper_mode_starts_without_go_file(tmp_path, caplog):
    """Paper mode (no --live) proceeds without calibration GO-file per ADR-022.1."""
    import logging

    go_file = tmp_path / "bot_e_calibration.json"
    assert not go_file.exists()

    fake_clob = _make_clob()

    async def go():
        with patch.object(main_mod, "CALIBRATION_GO_FILE", go_file):
            patches = _base_patches(
                clob=fake_clob,
                markets=[],  # no markets → loop sleeps immediately
                halted=False,
            )
            with caplog.at_level(logging.WARNING, logger="bot_e"):
                await _run_one_iter(patches)

    asyncio.run(go())

    warning_msgs = [r.message for r in caplog.records]
    assert any(
        "PAPER_COLLECTION_MODE" in m or "ADR-022.1" in m
        for m in warning_msgs
    ), f"Expected ADR-022.1 paper-collection-mode warning. Got: {warning_msgs}"


# ---------------------------------------------------------------------------
# Test 6: Low-OBI signal (maybe_fire returns None) produces no order
# ---------------------------------------------------------------------------

def test_low_obi_no_order():
    """When maybe_fire returns None (sub-threshold), no order is placed."""
    placed = []
    fake_clob = _make_clob()
    fake_clob.place_limit.side_effect = lambda *a, **k: placed.append(1)

    async def go():
        patches = _base_patches(
            clob=fake_clob,
            markets=[_make_market()],
            signal_val=None,  # <-- no signal
            chop=False,
            halted=False,
        )
        await _run_one_iter(patches)

    asyncio.run(go())
    assert len(placed) == 0, "Sub-threshold OBI must not trigger order placement"


def test_scan_summary_persists_aggregated_counts():
    """OQ-048 telemetry writes one DB-visible counter row per scan."""
    with patch.object(main_mod, "_emit_bot_e_event") as emit:
        main_mod._emit_scan_summary(
            markets_seen=3,
            counts={"signal_none": 2, "cex_cvd_skip": 1},
            elapsed_sec=1.2345,
        )

    emit.assert_called_once()
    event_type, message, payload = emit.call_args.args
    assert event_type == "bot_e.scan_summary"
    assert "markets=3" in message
    assert payload["markets_seen"] == 3
    assert payload["counts"] == {"cex_cvd_skip": 1, "signal_none": 2}


def test_persist_book_snapshot_writes_token_book(tmp_db):
    from sqlalchemy import select

    from core.clob import OrderBook
    from core.db import Book, get_session_factory

    book = OrderBook(
        token_id="token-book",
        bids=[(Decimal("0.49"), Decimal("10"))],
        asks=[(Decimal("0.51"), Decimal("12"))],
        timestamp=datetime.now(UTC).timestamp(),
    )

    main_mod._persist_book_snapshot(book)

    with get_session_factory()() as s:
        row = s.scalars(select(Book).where(Book.token_id == "token-book")).one()
        assert row.bids == [["0.49", "10"]]
        assert row.asks == [["0.51", "12"]]


def test_counter_reason_strips_dynamic_suffix():
    assert main_mod._counter_reason("pre_entry_window:1726s") == "pre_entry_window"
    assert main_mod._counter_reason("cex_cvd_disagrees(cvd=-10 side=BUY_YES)") == (
        "cex_cvd_disagrees"
    )


def test_emit_new_fill_events_uses_existing_event_cursor(tmp_db):
    """Restarting the trader must not duplicate historical bot_e.fill rows."""
    from sqlalchemy import select

    from core.db import Event, Order, Trade, get_session_factory

    main_mod._emitted_fill_trade_ids.clear()
    with get_session_factory()() as s:
        s.add(Order(
            order_id="paper-1",
            bot_id="bot_e",
            condition_id="cid-1",
            token_id="token-1",
            side="BUY_YES",
            price=Decimal("0.42"),
            size=Decimal("10"),
            status="PAPER_OPEN",
            order_type="GTC",
        ))
        s.add(Trade(
            trade_id="trade-1",
            bot_id="bot_e",
            order_id="paper-1",
            condition_id="cid-1",
            token_id="token-1",
            side="BUY",
            price=Decimal("0.42"),
            size=Decimal("10"),
            fee_usd=Decimal("0"),
            filled_at=datetime.now(UTC),
            usd_gbp_rate=Decimal("0.8"),
            gbp_notional=Decimal("3.36"),
        ))
        s.add(Event(
            bot_id="bot_e",
            event_type="bot_e.fill",
            severity="info",
            message="fill trade-1",
            payload={"trade_id": "trade-1"},
        ))
        s.commit()

    tracker = MagicMock()
    emitted = main_mod._emit_new_fill_events_and_track(tracker)

    assert emitted == 0
    tracker.register.assert_not_called()
    with get_session_factory()() as s:
        events = list(s.scalars(select(Event).where(Event.event_type == "bot_e.fill")))
    assert len(events) == 1
