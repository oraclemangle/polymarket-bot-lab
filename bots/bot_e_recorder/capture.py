"""Crypto recorder — main async capture loop.

Orchestrates:
1. Periodic market discovery (every 60s) — finds the currently-live crypto
   Up/Down markets.
2. Polymarket WSS subscriptions — one per (symbol, condition_id). Events are
   serialised and written to `pm_events`.
3. CEX (Binance) WSS — BTC/ETH/SOL @trade, written to `cex_trades`.
4. Heartbeat emission — every N seconds across all active subscriptions.

All writes go through an async queue + a single writer task so that SQLite
stays single-writer (WAL mode handles concurrent readers).

No order placement. No trading logic. Zero.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from bots.bot_e_recorder.config import (
    BOT_E_CEX_SYMBOLS,
    BOT_E_HEARTBEAT_INTERVAL_SEC,
    BOT_E_MARKET_SCAN_INTERVAL_SEC,
    BOT_E_MAX_MINUTES_TO_RES,
    BOT_E_MIN_VOLUME_USD,
    BOT_E_RECORDER_DB_PATH,
)
from bots.bot_e_recorder.market_discovery import CryptoMarket, fetch_live_crypto_markets
from bots.bot_e_recorder.schema import init_db
from core.cex_ws import BinanceWSSClient, CexTrade
from core.polymarket_ws import PolymarketWSSClient, WSSEvent
from core.sd_notify import notify_status, notify_watchdog

log = logging.getLogger(__name__)

BULK_QUEUE_MAXSIZE = 200_000
PRIORITY_QUEUE_MAXSIZE = 10_000
WRITER_BATCH_SIZE = 5_000
WRITER_DRAIN_CHUNK_SIZE = 10_000
WRITER_FLUSH_INTERVAL_SEC = 0.5
WRITER_METRICS_INTERVAL_SEC = 30.0
QUEUE_WARN_FRACTION = 0.70
DROP_LOG_INTERVAL_SEC = 15.0
WATCHDOG_PING_INTERVAL_SEC = 30.0
WRITER_STALL_ABORT_SEC = 90.0
BOOT_GRACE_SEC = 60.0
SUBSCRIPTION_END_GRACE_SEC = 90.0


@dataclass
class _WriteTask:
    """One write request on the DB queue."""
    kind: str                  # "pm_event" | "cex_trade" | "market" | "heartbeat"
    row: dict[str, Any]


class RecorderState:
    """In-process state; tracks active subscriptions and writer pipeline."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        # Session 41 / OQ-056 (2026-04-28): bumped 50_000 → 200_000 after
        # the V2 cutover storm pushed sustained event rate from ~70/sec to
        # ~3,000/sec at peak. The previous 50k cap saturated within
        # minutes during burst hours even with synchronous=OFF (which
        # already raised the writer drain rate ~5-10x). 200k slots x
        # ~70 bytes per _WriteTask ≈ 15 MB additional memory budget; host
        # 105 has 6.2 GB free, so the trade is trivially favourable.
        # Hardware audited 2026-04-28: 22% host CPU + 11 GB host RAM
        # available — the bottleneck was queue cap, not hardware.
        self.write_queue: asyncio.Queue[_WriteTask] = asyncio.Queue(maxsize=BULK_QUEUE_MAXSIZE)
        # Session 42 / OQ-056 (2026-04-29): keep liveness/control-plane writes
        # separate from the bulk raw-event tape. V2 bursts filled the 200k bulk
        # queue and froze discovery/heartbeat paths. A small priority queue lets
        # heartbeats and discovery status continue while PM/CEX tape overload is
        # dropped and measured.
        self.priority_write_queue: asyncio.Queue[_WriteTask] = asyncio.Queue(
            maxsize=PRIORITY_QUEUE_MAXSIZE
        )
        self.enqueued_counts: Counter[str] = Counter()
        self.dropped_counts: Counter[str] = Counter()
        self.flushed_counts: Counter[str] = Counter()
        self.last_drop_log_ts: dict[str, float] = {}
        self.last_writer_metrics_ts: float = 0.0
        self.pm_clients: dict[str, PolymarketWSSClient] = {}   # subscription_id -> client
        self.pm_tasks: dict[str, asyncio.Task] = {}             # subscription_id -> task
        self.pm_end_dates: dict[str, datetime] = {}             # subscription_id -> Gamma end_date
        self.cex_client: BinanceWSSClient | None = None
        self.cex_task: asyncio.Task | None = None
        self.last_pm_by_sub_ms: dict[str, int] = {}
        self.last_cex_ms: int = 0
        # Session 17s 2026-04-19: wall-clock of last successful _flush_batch.
        # Read by watchdog_ping_loop to detect silent writer wedges; if
        # stale > 120s, the recorder self-aborts for systemd restart.
        self.last_flush_ts: float = 0.0
        self._closed = False

    async def close(self) -> None:
        self._closed = True


def _record_enqueue(state: RecorderState, kind: str) -> None:
    state.enqueued_counts[kind] += 1


def _record_drop(
    state: RecorderState,
    kind: str,
    *,
    queue_name: str,
    qsize: int,
    maxsize: int,
) -> None:
    state.dropped_counts[kind] += 1
    now = time.time()
    key = f"{queue_name}:{kind}"
    last = state.last_drop_log_ts.get(key, 0.0)
    if now - last >= DROP_LOG_INTERVAL_SEC:
        state.last_drop_log_ts[key] = now
        log.warning(
            "recorder.write_queue_drop queue=%s kind=%s qsize=%d maxsize=%d "
            "dropped_kind=%d",
            queue_name,
            kind,
            qsize,
            maxsize,
            state.dropped_counts[kind],
        )


def _enqueue_bulk(state: RecorderState, task: _WriteTask) -> bool:
    """Best-effort enqueue for high-volume raw tape.

    Under V2 cutover load, blocking producers on the bulk queue wedged the
    recorder while still failing to preserve all rows. Drop-on-full keeps the
    event loop and subscription reconciliation alive and makes loss explicit.
    """
    try:
        state.write_queue.put_nowait(task)
    except asyncio.QueueFull:
        _record_drop(
            state,
            task.kind,
            queue_name="bulk",
            qsize=state.write_queue.qsize(),
            maxsize=state.write_queue.maxsize,
        )
        return False
    _record_enqueue(state, task.kind)
    return True


def _enqueue_priority(state: RecorderState, task: _WriteTask) -> bool:
    """Best-effort enqueue for liveness/control-plane rows."""
    try:
        state.priority_write_queue.put_nowait(task)
    except asyncio.QueueFull:
        _record_drop(
            state,
            task.kind,
            queue_name="priority",
            qsize=state.priority_write_queue.qsize(),
            maxsize=state.priority_write_queue.maxsize,
        )
        return False
    _record_enqueue(state, task.kind)
    return True


def _queues_empty(state: RecorderState) -> bool:
    return state.priority_write_queue.empty() and state.write_queue.empty()


def _drain_queues(state: RecorderState, batch: list[_WriteTask], limit: int) -> int:
    drained = 0
    while drained < limit:
        try:
            batch.append(state.priority_write_queue.get_nowait())
        except asyncio.QueueEmpty:
            break
        drained += 1
    while drained < limit:
        try:
            batch.append(state.write_queue.get_nowait())
        except asyncio.QueueEmpty:
            break
        drained += 1
    return drained


async def _wait_for_next_writes(
    state: RecorderState,
    timeout: float,
) -> list[_WriteTask]:
    if timeout <= 0:
        return []
    priority_get = asyncio.create_task(state.priority_write_queue.get())
    bulk_get = asyncio.create_task(state.write_queue.get())
    done, pending = await asyncio.wait(
        {priority_get, bulk_get},
        timeout=timeout,
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    return [task.result() for task in done]


def _maybe_log_writer_metrics(state: RecorderState, *, force: bool = False) -> None:
    now = time.time()
    if not force and (now - state.last_writer_metrics_ts) < WRITER_METRICS_INTERVAL_SEC:
        return
    state.last_writer_metrics_ts = now
    bulk_qsize = state.write_queue.qsize()
    priority_qsize = state.priority_write_queue.qsize()
    bulk_warn = bulk_qsize >= int(state.write_queue.maxsize * QUEUE_WARN_FRACTION)
    log_fn = log.warning if bulk_warn or priority_qsize else log.info
    log_fn(
        "recorder.writer_metrics bulk_qsize=%d bulk_max=%d priority_qsize=%d "
        "priority_max=%d enqueued=%s flushed=%s dropped=%s",
        bulk_qsize,
        state.write_queue.maxsize,
        priority_qsize,
        state.priority_write_queue.maxsize,
        dict(state.enqueued_counts),
        dict(state.flushed_counts),
        dict(state.dropped_counts),
    )


# ---------------------------------------------------------------------------
# Event handlers (WSS → write queue)
# ---------------------------------------------------------------------------


async def _close_subscription(state: RecorderState, sub_id: str) -> None:
    """Detach a subscription cleanly: cancel its WSS task, close its
    client, and drop ALL per-sub state from RecorderState.

    Session 39 / OQ-056 (2026-04-26): the previous inline close block
    popped ``pm_tasks`` and ``pm_clients`` but left
    ``last_pm_by_sub_ms`` populated. Across market rotations this
    accumulated entries for every sub the recorder had ever seen,
    inflating the heartbeat fan-out and the ``pm_subs=N`` status
    counter. Observed drift: 11 entries after 1h39m uptime versus
    ~3 actually live subs. Centralising the close path here makes
    the property "all per-sub state is removed" testable.
    """
    task = state.pm_tasks.pop(sub_id, None)
    client = state.pm_clients.pop(sub_id, None)
    if client is not None:
        await client.close()
    if task is not None:
        task.cancel()
    state.last_pm_by_sub_ms.pop(sub_id, None)
    state.pm_end_dates.pop(sub_id, None)


def _make_pm_handler(state: RecorderState):
    async def on_pm(ev: WSSEvent) -> None:
        state.last_pm_by_sub_ms[ev.subscription_id] = ev.received_at_ms
        # Extract commonly-queried fields out of payload for indexing
        asset_id = ev.payload.get("asset_id") or ev.payload.get("market")
        condition_id = ev.payload.get("condition_id") or ev.payload.get("conditionId")
        row = {
            "received_at_ms": ev.received_at_ms,
            "subscription_id": ev.subscription_id,
            "event_type": ev.event_type,
            "asset_id": str(asset_id) if asset_id else None,
            "condition_id": str(condition_id) if condition_id else None,
            "payload_json": json.dumps(ev.payload, default=str),
        }
        _enqueue_bulk(state, _WriteTask(kind="pm_event", row=row))
    return on_pm


def _make_cex_handler(state: RecorderState):
    async def on_cex(t: CexTrade) -> None:
        state.last_cex_ms = t.received_at_ms
        row = {
            "received_at_ms": t.received_at_ms,
            "trade_time_ms": t.trade_time_ms,
            "symbol": t.symbol,
            "price": t.price,
            "size": t.size,
            "is_buyer_maker": 1 if t.is_buyer_maker else 0,
        }
        _enqueue_bulk(state, _WriteTask(kind="cex_trade", row=row))
    return on_cex


# ---------------------------------------------------------------------------
# Main loops
# ---------------------------------------------------------------------------


async def discovery_loop(state: RecorderState) -> None:
    """Every N seconds, refresh the list of live 15-min crypto markets and
    reconcile WSS subscriptions.

    - Markets we're already subscribed to: leave alone.
    - Markets newly matching the filter: open a new PolymarketWSSClient.
    - Markets that have resolved / dropped below volume: cancel their task.

    U-07 (audit 2026-04-18): `fetch_live_crypto_markets` is a synchronous
    HTTP call. Running it inline on the event loop blocked every other
    task — including `heartbeat_loop`'s `notify_watchdog()` — for the
    duration of the request. Under network stress this produced the
    9h40m zombie hang observed 2026-04-17 00:38 UTC. Offload to a worker
    thread so only the asyncio loop blocks on `await`, never on httpx.
    """
    loop_interval = BOT_E_MARKET_SCAN_INTERVAL_SEC
    while not state._closed:
        try:
            now_ms = int(time.time() * 1000)
            markets = await asyncio.to_thread(
                fetch_live_crypto_markets,
                max_minutes_to_res=BOT_E_MAX_MINUTES_TO_RES,
                min_volume_usd=BOT_E_MIN_VOLUME_USD,
            )
            market_rows = []
            live_sub_ids = set()
            live_end_dates: dict[str, datetime] = {}
            for m in markets:
                sub_id = _subscription_id(m)
                live_sub_ids.add(sub_id)
                live_end_dates[sub_id] = m.end_date

                market_rows.append(_WriteTask(kind="market", row={
                    "scan_at_ms": now_ms,
                    "condition_id": m.condition_id,
                    "question": m.question,
                    "end_date_iso": m.end_date.isoformat(),
                    "yes_token_id": m.yes_token_id,
                    "no_token_id": m.no_token_id,
                    "symbol": m.symbol,
                    "duration_minutes": m.duration_minutes,
                    "volume_24h_usd": float(m.volume_24h_usd) if m.volume_24h_usd else None,
                    "yes_price": float(m.yes_price) if m.yes_price else None,
                    "category": "crypto",
                    "raw_json": json.dumps(m.raw, default=str),
                }))

            # Cancel subscriptions for markets no longer in the live set before
            # any best-effort DB writes. A full raw-event queue must not freeze
            # subscription reconciliation. Gamma can drop 5m crypto markets from
            # active discovery before their advertised endDate, so retain known
            # subscriptions until endDate + grace to keep Bot G's final-minute
            # quote feed alive.
            now_dt = datetime.fromtimestamp(now_ms / 1000, tz=UTC)
            for sub_id in list(state.pm_tasks.keys()):
                if sub_id in live_sub_ids:
                    state.pm_end_dates[sub_id] = live_end_dates[sub_id]
                    continue
                end_date = state.pm_end_dates.get(sub_id)
                if end_date is not None:
                    if end_date.tzinfo is None:
                        end_date = end_date.replace(tzinfo=UTC)
                    close_after = end_date + timedelta(seconds=SUBSCRIPTION_END_GRACE_SEC)
                    if now_dt <= close_after:
                        continue
                await _close_subscription(state, sub_id)
                log.info("recorder.sub_closed sub_id=%s", sub_id)

            for m in markets:
                sub_id = _subscription_id(m)
                if sub_id in state.pm_tasks:
                    continue  # already subscribed

                client = PolymarketWSSClient(
                    asset_ids=[m.yes_token_id, m.no_token_id],
                    on_event=_make_pm_handler(state),
                    subscription_id=sub_id,
                )
                task = asyncio.create_task(client.run(), name=f"pm-{sub_id}")
                state.pm_clients[sub_id] = client
                state.pm_tasks[sub_id] = task
                state.pm_end_dates[sub_id] = m.end_date
                log.info("recorder.sub_opened sub_id=%s sym=%s end=%s",
                         sub_id, m.symbol, m.end_date.isoformat())

            # Session 24 (2026-04-23) OQ-046: subscription-audit log so
            # coverage gaps are visible in journald. If n_markets > 0 but
            # n_subscriptions == 0 (or vice-versa), the discovery + WSS
            # pipeline has diverged and this line surfaces it immediately.
            log.info(
                "recorder.subscription_audit n_markets=%d n_subscriptions=%d active_subs=%s",
                len(markets), len(state.pm_tasks),
                sorted(state.pm_tasks.keys()),
            )
            for task in market_rows:
                _enqueue_bulk(state, task)
            # Emit discovery heartbeat
            _enqueue_priority(state, _WriteTask(kind="heartbeat", row={
                "emitted_at_ms": now_ms,
                "source": "discovery",
                "subscription_id": None,
                "last_message_age_sec": None,
                "metadata_json": json.dumps({
                    "n_markets": len(markets),
                    "n_subscriptions": len(state.pm_tasks),
                    "active_subs": sorted(state.pm_tasks.keys()),
                }),
            }))
        except Exception as exc:
            log.error("recorder.discovery_error: %s", exc, exc_info=True)

        try:
            await asyncio.sleep(loop_interval)
        except asyncio.CancelledError:
            raise


async def watchdog_ping_loop(state: RecorderState) -> None:
    """Independent systemd watchdog pinger + writer-stall self-abort.

    Session 17s 2026-04-19: two-part fix for the recorder's invisible
    crash pattern.

    Part 1 (systemd watchdog decouple): the Session 17q fix pinged
    ``notify_watchdog`` at the top of each ``heartbeat_loop`` iteration,
    but the subsequent ``write_queue.put`` calls in that same iteration
    can block when the 50k-slot queue fills (CEX at ~32 rows/sec fills
    it in ~26 min if writes stall). Once blocked, the loop never
    iterates again → systemd SIGABRT at WatchdogSec=180s → crash loop
    every 12-16 min. This task only fires ``WATCHDOG=1`` and sleeps, so
    queue pressure cannot stop it.

    Part 2 (writer-stall self-abort, 2026-04-19 22:12 observation): with
    Part 1 alone, the recorder can sit alive-to-systemd but with writer
    silently dead — observed 7-13 min intervals where heartbeats stopped
    flowing to SQLite despite event_loop running, discovery/httpx calls
    succeeding, and no logged errors. The external watchdog daemon sees
    stale pm_events/heartbeats and halts bot_e; systemd sees happy
    pings and does nothing. To close this gap: periodically check that
    the writer has ACTUALLY flushed something recent via
    ``state.last_flush_ts``. If it's been > 120s since the last flush,
    call os.abort() — systemd restarts us per ``Restart=always``.
    """
    # WatchdogSec=180 on the systemd unit — ping every 30 to leave 6x margin
    # and catch stalls on the next tick rather than up to 60s late.
    # If writer_loop hasn't flushed in this long, the recorder is a zombie.
    # Session 17s 2026-04-20 01:53 UTC: dropped from 120 → 90 so we beat the
    # external watchdog (core/watchdog.py hb_threshold_sec=120 + ~60s check
    # cadence = external may fire at 120-180s). Aborting at 90s lets systemd
    # restart before the external watchdog halts bot_e → avoids the halt
    # race that caused 4 overnight halts 00:00-01:23 UTC.
    # Grace period on boot — writer hasn't had time to flush yet.
    start_ts = time.time()
    while not state._closed:
        notify_watchdog()
        # Writer-stall check: only enforced after the boot grace period.
        if (time.time() - start_ts) > BOOT_GRACE_SEC:
            last_flush = getattr(state, "last_flush_ts", 0.0) or 0.0
            stall_sec = time.time() - last_flush if last_flush else float("inf")
            if stall_sec > WRITER_STALL_ABORT_SEC:
                log.error(
                    "recorder.writer_stall_abort last_flush_age=%.0fs threshold=%ds — "
                    "writer wedged; dumping stacks then aborting for systemd restart",
                    stall_sec, int(WRITER_STALL_ABORT_SEC),
                )
                # Session 17s 2026-04-20: dump Python stacks via py-spy
                # before we abort. First occurrence under this diagnostic
                # path will tell us WHERE the writer thread is wedged —
                # the put_nowait heartbeat fix eliminated queue pressure as
                # a cause (no heartbeat_dropped warnings in the 4 overnight
                # aborts), so the stall is somewhere in _flush_batch,
                # asyncio.to_thread, or the SQLite layer. Stack dump goes
                # to journald via stderr — read with:
                #   journalctl -u polymarket-bot-e-recorder.service | grep -A 60 py_spy
                try:
                    pid = os.getpid()
                    # py-spy was installed via pip into the same venv as this
                    # interpreter; sys.executable is <venv>/bin/python, so
                    # py-spy sits at <venv>/bin/py-spy. Fall back to PATH
                    # lookup if that file is missing (e.g. dev workstation).
                    venv_pyspy = os.path.join(
                        os.path.dirname(sys.executable), "py-spy"
                    )
                    pyspy_bin = venv_pyspy if os.path.exists(venv_pyspy) else "py-spy"
                    cmd = [pyspy_bin, "dump", "--pid", str(pid)]
                    result = await asyncio.to_thread(
                        subprocess.run,
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    log.error(
                        "recorder.writer_stall_abort.py_spy_dump bin=%s rc=%s\nSTDOUT:\n%s\nSTDERR:\n%s",
                        pyspy_bin, result.returncode, result.stdout, result.stderr,
                    )
                except Exception as exc:
                    log.error("recorder.writer_stall_abort.py_spy_failed err=%s", exc)
                # Give journald a moment to flush the log lines before abort.
                await asyncio.sleep(1.0)
                os.abort()
        try:
            await asyncio.sleep(WATCHDOG_PING_INTERVAL_SEC)
        except asyncio.CancelledError:
            raise


async def heartbeat_loop(state: RecorderState) -> None:
    """Every N seconds, emit a liveness row for each source.

    Per Grok S5: detect silent WSS stalls by the absence of heartbeats,
    not just the absence of market events (a genuinely quiet market
    produces no events even on a healthy connection).

    Session 17f audit 2026-04-17: also pings systemd's watchdog via
    sd_notify. If this loop stops running (e.g. async deadlock, the
    00:38 UTC zombie incident), systemd will SIGKILL the process after
    WatchdogSec and restart per `Restart=always`.
    """
    while not state._closed:
        now_ms = int(time.time() * 1000)

        # Session 17q 2026-04-19: ping systemd watchdog FIRST, before any
        # queue operations. Root cause of the 17:34 UTC hang: writer_loop
        # stalled on a slow SQLite flush → write_queue filled → heartbeat
        # coroutine blocked on `await state.write_queue.put(...)` →
        # notify_watchdog() never fired → systemd WatchdogSec=180 triggered
        # SIGABRT. This was the queue-backpressure variant of Gemini 3.1
        # Pro F-003 (previously adjudicated "theoretical") manifesting in
        # production. By pinging systemd FIRST, the asyncio-loop-alive
        # signal is decoupled from queue pressure: if the queue is full
        # for a minute or two, systemd still sees us alive. If the loop
        # itself is frozen, the ping stops and systemd kills us correctly.
        notify_watchdog()

        # Session 17s 2026-04-19: heartbeats MUST NOT block on a full
        # write_queue. Prior code awaited put(); when a burst of PM
        # price_change events saturated the 50k-slot queue, heartbeats
        # stopped landing in SQLite → external watchdog (hb_threshold
        # =120s) halted bot_e → recorder appeared "zombie" despite
        # systemd watchdog-ping still firing (commit b18b09c).
        # Fix: put_nowait + drop-on-full + log a warn. Heartbeats are
        # ~100 bytes each; losing a few under overload is strictly
        # better than the signal going silent for minutes.
        # One heartbeat per active PM subscription
        for sub_id, last_ms in list(state.last_pm_by_sub_ms.items()):
            age_sec = (now_ms - last_ms) / 1000.0 if last_ms else None
            _enqueue_priority(state, _WriteTask(kind="heartbeat", row={
                "emitted_at_ms": now_ms,
                "source": "pm",
                "subscription_id": sub_id,
                "last_message_age_sec": age_sec,
                "metadata_json": None,
            }))
        # One heartbeat for CEX
        if state.cex_client is not None:
            age_sec = (now_ms - state.last_cex_ms) / 1000.0 if state.last_cex_ms else None
            _enqueue_priority(state, _WriteTask(kind="heartbeat", row={
                "emitted_at_ms": now_ms,
                "source": "cex",
                "subscription_id": ",".join(BOT_E_CEX_SYMBOLS),
                "last_message_age_sec": age_sec,
                "metadata_json": None,
            }))

        # Session 17p 2026-04-19: unconditional process-liveness heartbeat.
        # Previous loop only emitted rows per-subscription, so during sub
        # churn (e.g. discovery cycle replaces 3 subs atomically at
        # 16:14:24 UTC on 2026-04-19) the state.last_pm_by_sub_ms dict
        # was temporarily empty → no heartbeats emitted → watchdog hit
        # its 120s hb_threshold → spurious halt. Now emit one "process"
        # heartbeat every tick regardless of subscription state.
        _enqueue_priority(state, _WriteTask(kind="heartbeat", row={
            "emitted_at_ms": now_ms,
            "source": "process",
            "subscription_id": None,
            "last_message_age_sec": None,
            "metadata_json": None,
        }))
        n_pm = len(state.last_pm_by_sub_ms)
        last_cex_age = (now_ms - state.last_cex_ms) / 1000.0 if state.last_cex_ms else None
        notify_status(
            f"pm_subs={n_pm} cex_last_age_s="
            + (f"{last_cex_age:.0f}" if last_cex_age is not None else "?")
        )
        try:
            await asyncio.sleep(BOT_E_HEARTBEAT_INTERVAL_SEC)
        except asyncio.CancelledError:
            raise


async def writer_loop(state: RecorderState) -> None:
    """Pull rows off the queue and write to SQLite in batches.

    SQLite prefers batched writes to amortise fsync. We flush on either
    batch-size OR time (whichever first) to keep latency bounded.

    U-07 (audit 2026-04-18): `_flush_batch` is a synchronous SQLite call.
    Running it inline on the event loop froze every other coroutine for
    the duration of the fsync — in particular, `heartbeat_loop` could
    not ping systemd's watchdog, which was the proximate cause of the
    9h40m zombie hang on 2026-04-17 00:38 UTC. We now offload each flush
    to a worker thread via `asyncio.to_thread` and emit `notify_watchdog`
    after each successful flush, so the systemd liveness signal is tied
    to real forward progress rather than just "the heartbeat coroutine
    is still getting cpu time".
    """
    conn = state.conn
    assert conn is not None
    batch: list[_WriteTask] = []
    last_flush = time.time()

    async def _flush_and_heartbeat(b: list[_WriteTask]) -> None:
        """Flush in a worker thread; ping watchdog on success."""
        if not b:
            return
        flush_counts = Counter(t.kind for t in b)
        started = time.monotonic()
        try:
            await asyncio.to_thread(_flush_batch, conn, b)
        except Exception as exc:
            log.error("recorder.writer_flush_failed err=%s", exc)
            return
        duration_ms = (time.monotonic() - started) * 1000.0
        state.flushed_counts.update(flush_counts)
        # Session 17s 2026-04-19: stamp the wall-clock on success so
        # watchdog_ping_loop can detect a silent writer wedge.
        state.last_flush_ts = time.time()
        if duration_ms > 500:
            log.warning(
                "recorder.writer_flush_slow rows=%d duration_ms=%.0f counts=%s "
                "bulk_qsize=%d priority_qsize=%d",
                len(b),
                duration_ms,
                dict(flush_counts),
                state.write_queue.qsize(),
                state.priority_write_queue.qsize(),
            )
        try:
            from core.sd_notify import notify_watchdog
            notify_watchdog()
        except Exception:
            pass

    # Session 39 / OQ-055 follow-up (2026-04-26): tick state.last_flush_ts
    # on every iteration — even when the queue is empty and no flush
    # actually fires. The stall-abort guard was conflating "writer is
    # wedged inside _flush_batch" with "writer hasn't had data to flush".
    # A 06:33:38 UTC abort showed all worker threads idle (not in
    # _flush_batch), proving the writer was alive but quiet. A real
    # SQLite/threadpool wedge still blocks the loop body for >90s and
    # triggers the abort correctly, because the tick only happens at the
    # TOP of each iteration — if the body hangs, no tick.
    while not state._closed or not _queues_empty(state):
        state.last_flush_ts = time.time()
        try:
            _drain_queues(
                state,
                batch,
                max(0, WRITER_DRAIN_CHUNK_SIZE - len(batch)),
            )
            if not batch:
                batch.extend(
                    await _wait_for_next_writes(
                        state,
                        timeout=WRITER_FLUSH_INTERVAL_SEC,
                    )
                )
                _drain_queues(
                    state,
                    batch,
                    max(0, WRITER_DRAIN_CHUNK_SIZE - len(batch)),
                )
        except TimeoutError:
            pass
        except asyncio.CancelledError:
            # Drain whatever we have and exit cleanly
            while not _queues_empty(state):
                _drain_queues(state, batch, WRITER_DRAIN_CHUNK_SIZE)
                if len(batch) >= WRITER_BATCH_SIZE:
                    await _flush_and_heartbeat(batch)
                    batch = []
            await _flush_and_heartbeat(batch)
            raise

        now = time.time()
        if (
            len(batch) >= WRITER_BATCH_SIZE
            or (batch and (now - last_flush) >= WRITER_FLUSH_INTERVAL_SEC)
        ):
            await _flush_and_heartbeat(batch)
            batch = []
            last_flush = now
        _maybe_log_writer_metrics(state)


def _flush_batch(conn: sqlite3.Connection, batch: list[_WriteTask]) -> None:
    """Single transaction insert of a batch, partitioned by table."""
    if not batch:
        return
    pm, cex, mk, hb = [], [], [], []
    for t in batch:
        if t.kind == "pm_event":
            pm.append(t.row)
        elif t.kind == "cex_trade":
            cex.append(t.row)
        elif t.kind == "market":
            mk.append(t.row)
        elif t.kind == "heartbeat":
            hb.append(t.row)
    try:
        with conn:
            if pm:
                conn.executemany(
                    "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, "
                    "asset_id, condition_id, payload_json) VALUES "
                    "(:received_at_ms, :subscription_id, :event_type, :asset_id, "
                    ":condition_id, :payload_json)",
                    pm,
                )
            if cex:
                conn.executemany(
                    "INSERT INTO cex_trades (received_at_ms, trade_time_ms, symbol, "
                    "price, size, is_buyer_maker) VALUES "
                    "(:received_at_ms, :trade_time_ms, :symbol, :price, :size, :is_buyer_maker)",
                    cex,
                )
            if mk:
                for row in mk:
                    row.setdefault("symbol", None)
                    row.setdefault("duration_minutes", None)
                conn.executemany(
                    "INSERT INTO markets (scan_at_ms, condition_id, question, end_date_iso, "
                    "yes_token_id, no_token_id, symbol, duration_minutes, "
                    "volume_24h_usd, yes_price, category, raw_json) "
                    "VALUES (:scan_at_ms, :condition_id, :question, :end_date_iso, "
                    ":yes_token_id, :no_token_id, :symbol, :duration_minutes, "
                    ":volume_24h_usd, :yes_price, :category, :raw_json)",
                    mk,
                )
            if hb:
                conn.executemany(
                    "INSERT INTO heartbeats (emitted_at_ms, source, subscription_id, "
                    "last_message_age_sec, metadata_json) VALUES "
                    "(:emitted_at_ms, :source, :subscription_id, :last_message_age_sec, :metadata_json)",
                    hb,
                )
    except sqlite3.Error as exc:
        log.error(
            "recorder.sqlite_write_failed n_pm=%d n_cex=%d n_mk=%d n_hb=%d error=%s",
            len(pm), len(cex), len(mk), len(hb), exc,
        )
        # Don't re-raise; keep the loop alive so capture continues.


def _subscription_id(m: CryptoMarket) -> str:
    """Stable per-market subscription id. Includes the UTC end-time so
    distinct 15-min windows get distinct subscription ids even if the same
    token_ids were recycled (they aren't, but belt and braces). Include
    duration because 5m and 15m crypto windows can resolve at the same minute
    for the same symbol with different token ids."""
    duration = f"{m.duration_minutes or 'unk'}m"
    return f"{m.symbol.lower()}-{duration}-{m.end_date.strftime('%Y%m%dT%H%M')}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_capture() -> None:
    """Top-level capture loop. Blocks forever; Ctrl-C or SIGTERM to stop."""
    log.info("recorder.startup db=%s symbols=%s",
             BOT_E_RECORDER_DB_PATH, BOT_E_CEX_SYMBOLS)

    conn = init_db(BOT_E_RECORDER_DB_PATH)
    state = RecorderState(BOT_E_RECORDER_DB_PATH)
    state.conn = conn

    # CEX subscriber — always on, one connection for all configured symbols
    cex = BinanceWSSClient(symbols=BOT_E_CEX_SYMBOLS, on_trade=_make_cex_handler(state))
    state.cex_client = cex
    cex_task = asyncio.create_task(cex.run(), name="cex-ws")
    state.cex_task = cex_task

    # Session 17s 2026-04-21: root-cause fix for the recurring "all producers
    # silent, writer sits at wait_for" stall. Previously gather() re-raised
    # the first exception and cancelled the others, so ANY task's transient
    # crash took the whole recorder down. With NRestarts=23 hitting systemd's
    # StartLimitBurst and a 1h44m silent window, layered defenses weren't
    # enough. Fix: wrap each task in a supervisor that catches all exceptions,
    # logs them, and auto-restarts the task. Use return_exceptions=True so
    # one crash doesn't cascade.
    async def _supervised(coro_factory, name: str) -> None:
        backoff = 1.0
        while not state._closed:
            try:
                await coro_factory()
                log.info("recorder.supervised_task_returned name=%s", name)
                if state._closed:
                    return
                # Unexpected clean return — backoff before restart.
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error(
                    "recorder.supervised_task_crash name=%s err=%s — restarting in %.1fs",
                    name, exc, backoff, exc_info=True,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    writer_task = asyncio.create_task(
        _supervised(lambda: writer_loop(state), "writer"), name="writer")
    discovery_task = asyncio.create_task(
        _supervised(lambda: discovery_loop(state), "discovery"), name="discovery")
    heartbeat_task = asyncio.create_task(
        _supervised(lambda: heartbeat_loop(state), "heartbeat"), name="heartbeat")
    watchdog_task = asyncio.create_task(
        _supervised(lambda: watchdog_ping_loop(state), "watchdog-ping"), name="watchdog-ping")
    # Note: cex_task is BinanceWSSClient.run() — it has its own reconnect
    # loop already. Wrapping here too for defense-in-depth.
    cex_supervised_task = asyncio.create_task(
        _supervised(lambda: cex.run(), "cex-ws"), name="cex-ws-supervised")
    # Keep original cex_task ref for finally-block cleanup, replace with
    # the supervised version for gather.
    cex_task.cancel()
    cex_task = cex_supervised_task
    state.cex_task = cex_task

    try:
        # return_exceptions=True so one task failing doesn't cancel others.
        # Supervisor above should catch everything, but belt-and-braces.
        results = await asyncio.gather(
            cex_task, writer_task, discovery_task, heartbeat_task, watchdog_task,
            return_exceptions=True,
        )
        for name, result in zip(
            ["cex", "writer", "discovery", "heartbeat", "watchdog"], results,
            strict=False,
        ):
            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                log.error("recorder.gather_task_error name=%s err=%s", name, result)
    except asyncio.CancelledError:
        log.info("recorder.shutdown_requested")
    finally:
        await state.close()
        for sub_id, task in list(state.pm_tasks.items()):
            client = state.pm_clients.get(sub_id)
            if client is not None:
                await client.close()
            task.cancel()
        cex_task.cancel()
        writer_task.cancel()
        discovery_task.cancel()
        heartbeat_task.cancel()
        watchdog_task.cancel()
        # Drain remaining writes
        with suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(writer_task, timeout=5.0)
        if state.conn:
            state.conn.close()
        log.info("recorder.stopped")
