"""Async capture loop for the Bot H Maker V2 recorder.

Subscribes to the Polymarket CLOB WSS for politics + sports + awards +
crypto markets in the 1c-50c price band (per `config.RECORDER_FILTER`)
and persists every event to `data/maker_recorder.db`.

Compared to `bots/bot_e_recorder/capture.py`, this loop is simpler:

- Single async queue, single writer task.
- One INSERT per event (volume here is much lower than crypto's ~3000/s
  V2 burst rate; we expect <50/s sustained for politics+sports).
- Periodic batched commit via `WRITER_FLUSH_INTERVAL_SEC`.

If volume turns out higher than expected, the writer can be upgraded to
the bot_e_recorder priority/control-plane queue pattern. For Phase 1 the
simpler loop is sufficient.

No order placement. No quote generation. Strictly read-only WSS recorder.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from bots.bot_h_maker_v2.config import (
    GAMMA_SCAN_INTERVAL_SEC,
    HEARTBEAT_INTERVAL_SEC,
    MAX_TOKENS_SUBSCRIBED,
    RECORDER_DB_PATH,
    WRITER_FLUSH_INTERVAL_SEC,
)
from bots.bot_h_maker_v2.discovery import MakerMarket, fetch_recorder_markets
from bots.bot_h_maker_v2.schema import init_db
from core.polymarket_ws import PolymarketWSSClient, WSSEvent

log = logging.getLogger(__name__)

QUEUE_MAXSIZE = 50_000
SUBSCRIPTION_REFRESH_BACKOFF_SEC = 60.0


@dataclass
class WriteTask:
    kind: str  # "pm_event" | "market" | "heartbeat"
    row: dict[str, Any]


class RecorderState:
    """In-process state for the recorder. Tracks the subscription set,
    the writer queue, and the per-token → condition_id index used to
    enrich incoming WSS events."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[WriteTask] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        # token_id -> condition_id mapping. Populated by discovery on
        # every gamma scan. WSS event handler uses this to enrich
        # `condition_id` on each event row.
        self.token_to_condition: dict[str, str] = {}
        # condition_id -> MakerMarket, kept for analysis-time joins.
        self.markets: dict[str, MakerMarket] = {}
        # Active subscription tasks keyed by subscription_id.
        self.subscriptions: dict[str, asyncio.Task] = {}
        # Per-subscription event counts (debug visibility).
        self.event_counts: Counter[str] = Counter()


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


async def writer_loop(state: RecorderState) -> None:
    """Single-writer task drains the queue into SQLite."""
    conn = init_db(RECORDER_DB_PATH)
    log.info("bot_h_maker_v2.writer.started db=%s", RECORDER_DB_PATH)
    last_flush = time.monotonic()
    pending = 0
    try:
        while True:
            try:
                task = await asyncio.wait_for(state.queue.get(), timeout=WRITER_FLUSH_INTERVAL_SEC)
            except asyncio.TimeoutError:
                if pending:
                    conn.commit()
                    pending = 0
                    last_flush = time.monotonic()
                continue
            try:
                _execute_task(conn, task)
                pending += 1
            except Exception as exc:
                log.warning("bot_h_maker_v2.writer.task_failed kind=%s err=%s", task.kind, exc)
            now = time.monotonic()
            if pending >= 200 or now - last_flush >= WRITER_FLUSH_INTERVAL_SEC:
                conn.commit()
                pending = 0
                last_flush = now
    except asyncio.CancelledError:
        with suppress(Exception):
            conn.commit()
        log.info("bot_h_maker_v2.writer.cancelled")
        raise
    finally:
        with suppress(Exception):
            conn.close()


def _execute_task(conn: sqlite3.Connection, task: WriteTask) -> None:
    if task.kind == "pm_event":
        r = task.row
        conn.execute(
            """
            INSERT INTO pm_events
              (received_at_ms, subscription_id, event_type, asset_id, condition_id, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                r["received_at_ms"],
                r["subscription_id"],
                r["event_type"],
                r.get("asset_id"),
                r.get("condition_id"),
                r["payload_json"],
            ),
        )
    elif task.kind == "market":
        r = task.row
        conn.execute(
            """
            INSERT INTO markets
              (condition_id, yes_token_id, no_token_id, category, question,
               end_date_ts, discovered_at_ms, last_seen_at_ms,
               initial_yes_price, volume_24h_usd, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(condition_id) DO UPDATE SET
              last_seen_at_ms=excluded.last_seen_at_ms,
              volume_24h_usd=excluded.volume_24h_usd,
              status='ACTIVE'
            """,
            (
                r["condition_id"],
                r["yes_token_id"],
                r["no_token_id"],
                r["category"],
                r["question"],
                r.get("end_date_ts"),
                r["discovered_at_ms"],
                r["last_seen_at_ms"],
                r.get("initial_yes_price"),
                r.get("volume_24h_usd"),
                r.get("status", "ACTIVE"),
            ),
        )
    elif task.kind == "heartbeat":
        r = task.row
        conn.execute(
            """
            INSERT INTO heartbeats
              (received_at_ms, subscription_id, asset_id_count, note)
            VALUES (?, ?, ?, ?)
            """,
            (
                r["received_at_ms"],
                r["subscription_id"],
                r["asset_id_count"],
                r.get("note"),
            ),
        )
    else:  # pragma: no cover
        log.warning("bot_h_maker_v2.writer.unknown_kind=%s", task.kind)


# ---------------------------------------------------------------------------
# WSS event handler
# ---------------------------------------------------------------------------


def _extract_event_keys(payload: dict) -> tuple[str | None, str | None]:
    """Resolve (asset_id, condition_id) from a Polymarket WSS payload.

    Handles the three observed payload shapes:

    1. ``book`` / ``last_trade_price`` / ``best_bid_ask``: top-level
       ``asset_id`` (decimal token) and ``market`` (hex condition_id).

    2. ``price_change``: top-level ``market`` (hex condition_id) and a
       ``price_changes`` array with per-token deltas. The event covers
       multiple tokens at once, so we report the FIRST asset_id from
       price_changes[0]["asset_id"] and the shared condition_id.

    3. ``new_market``: top-level ``condition_id`` plus ``clob_token_ids``
       array. We pick the first token id and the condition id directly.

    Returns (asset_id, condition_id). Either may be None for events whose
    payload does not include them (e.g. heartbeat, reconnect).
    """
    asset_id: str | None = None
    condition_id: str | None = None
    # Prefer explicit condition_id (new_market events have it directly).
    cid = payload.get("condition_id")
    if cid:
        condition_id = str(cid)
    # `market` field on book / price_change is the condition_id in 0x hex.
    if condition_id is None:
        market = payload.get("market")
        if market:
            condition_id = str(market)
    # asset_id lives at top-level on book / last_trade_price / best_bid_ask.
    aid = payload.get("asset_id") or payload.get("assetId") or payload.get("token_id")
    if aid:
        asset_id = str(aid)
    # price_change events: pick the first per-token entry.
    if asset_id is None:
        changes = payload.get("price_changes")
        if isinstance(changes, list) and changes:
            first = changes[0]
            if isinstance(first, dict):
                pc_aid = first.get("asset_id") or first.get("assetId")
                if pc_aid:
                    asset_id = str(pc_aid)
    # new_market events: pick the first clob token id.
    if asset_id is None:
        token_ids = payload.get("clob_token_ids") or payload.get("assets_ids")
        if isinstance(token_ids, list) and token_ids:
            asset_id = str(token_ids[0])
    return asset_id, condition_id


# Event types that are ALWAYS persisted regardless of subscription state.
# `new_market` is the forward-discovery feed (used to spot upcoming markets).
# `reconnect` / `disconnect` / `heartbeat` are operational metadata. Dropping
# any of these would lose information that does not scale with market count.
ALWAYS_KEEP_EVENT_TYPES = frozenset(
    {"new_market", "reconnect", "disconnect", "heartbeat"}
)


def _make_pm_handler(state: RecorderState):
    """Build a per-subscription event handler bound to RecorderState.

    Per ADR-134 (Session 256 amendment): events for non-subscribed
    markets are dropped at write time to control disk-budget growth.
    The Polymarket WSS broadcasts `book` / `price_change` /
    `last_trade_price` / `best_bid_ask` events for many markets we did
    NOT request. Pre-filter empirically: ~95% of inbound volume is
    broadcast about non-subscribed markets. Filtering at write time
    cuts disk growth proportionally without losing any data we
    actually use for analysis (the wide-recorder requirement covers
    only markets in our gamma filter, which all live in
    state.token_to_condition).

    `new_market` events bypass the filter so we keep the
    forward-discovery feed; they're cheap and let analysis identify
    markets that came online after the last gamma scan.
    """

    async def on_pm(event: WSSEvent) -> None:
        payload = event.payload if isinstance(event.payload, dict) else {}
        asset_id, payload_condition_id = _extract_event_keys(payload)
        # Resolve condition_id with two-tier lookup:
        #   1. token_to_condition map populated by discovery (decimal tokens)
        #   2. raw `market`/`condition_id` field from the payload (hex)
        # The two-tier resolution stays even after the broadcast filter
        # because subscribed events sometimes arrive with hex
        # condition_id but no asset_id (e.g. price_change events whose
        # price_changes[] array we may want to fully expand later).
        from_token_map = (
            state.token_to_condition.get(asset_id) if asset_id else None
        )
        resolved_condition_id = from_token_map or payload_condition_id

        # Write-time filter for broadcast events on non-subscribed markets.
        # `state.token_to_condition` is the canonical "subscribed?" check —
        # it's populated by `discovery_loop` for every market in our gamma
        # filter and replaced wholesale on every refresh.
        if event.event_type not in ALWAYS_KEEP_EVENT_TYPES:
            if from_token_map is None:
                state.event_counts[f"_dropped_{event.event_type}"] += 1
                return

        row = {
            "received_at_ms": event.received_at_ms,
            "subscription_id": event.subscription_id,
            "event_type": event.event_type,
            "asset_id": asset_id,
            "condition_id": resolved_condition_id,
            "payload_json": json.dumps(payload, separators=(",", ":")),
        }
        try:
            state.queue.put_nowait(WriteTask(kind="pm_event", row=row))
            state.event_counts[event.event_type] += 1
        except asyncio.QueueFull:
            log.warning(
                "bot_h_maker_v2.queue_full dropping_event type=%s sub=%s",
                event.event_type,
                event.subscription_id,
            )

    return on_pm


# ---------------------------------------------------------------------------
# Subscription manager
# ---------------------------------------------------------------------------


def _select_tokens_to_subscribe(markets: list[MakerMarket]) -> list[MakerMarket]:
    """Apply MAX_TOKENS_SUBSCRIBED cap. Each market = 2 tokens. Prefer
    higher-volume markets when over-cap."""
    max_markets = MAX_TOKENS_SUBSCRIBED // 2
    if len(markets) <= max_markets:
        return markets
    log.info(
        "bot_h_maker_v2.subscription_cap markets=%d cap=%d sorting_by_volume",
        len(markets),
        max_markets,
    )
    sorted_by_vol = sorted(
        markets,
        key=lambda m: (m.volume_24h_usd or 0),
        reverse=True,
    )
    return sorted_by_vol[:max_markets]


async def _subscription_runner(
    state: RecorderState,
    subscription_id: str,
    asset_ids: list[str],
) -> None:
    """One async runner per subscription_id. Wraps the WSS client."""
    handler = _make_pm_handler(state)
    client = PolymarketWSSClient(
        asset_ids=asset_ids,
        on_event=handler,
        subscription_id=subscription_id,
    )
    log.info(
        "bot_h_maker_v2.subscription.start id=%s tokens=%d",
        subscription_id,
        len(asset_ids),
    )
    try:
        await client.run()
    except asyncio.CancelledError:
        await client.close()
        raise


async def discovery_loop(state: RecorderState) -> None:
    """Periodically refresh the market set from Gamma, update the
    subscription manager, and persist `markets` rows."""
    subscription_id = "bot_h_maker_v2/all"
    while True:
        try:
            markets = fetch_recorder_markets()
        except Exception as exc:
            log.warning("bot_h_maker_v2.discovery_failed err=%s", exc)
            await asyncio.sleep(SUBSCRIPTION_REFRESH_BACKOFF_SEC)
            continue
        chosen = _select_tokens_to_subscribe(markets)
        token_to_cond: dict[str, str] = {}
        now_ms = int(time.time() * 1000)
        for m in chosen:
            token_to_cond[m.yes_token_id] = m.condition_id
            token_to_cond[m.no_token_id] = m.condition_id
            state.markets[m.condition_id] = m
            state.queue.put_nowait(
                WriteTask(
                    kind="market",
                    row={
                        "condition_id": m.condition_id,
                        "yes_token_id": m.yes_token_id,
                        "no_token_id": m.no_token_id,
                        "category": m.category,
                        "question": m.question,
                        "end_date_ts": int(m.end_date.timestamp())
                        if m.end_date
                        else None,
                        "discovered_at_ms": now_ms,
                        "last_seen_at_ms": now_ms,
                        "initial_yes_price": float(m.initial_yes_price)
                        if m.initial_yes_price is not None
                        else None,
                        "volume_24h_usd": float(m.volume_24h_usd)
                        if m.volume_24h_usd is not None
                        else None,
                        "status": "ACTIVE",
                    },
                )
            )
        state.token_to_condition = token_to_cond

        # Resubscribe with the new token set (single subscription channel
        # for all tokens — Polymarket WSS supports multi-asset_ids in one
        # subscribe message; see core/polymarket_ws.py docstring).
        asset_ids = list(token_to_cond.keys())
        existing = state.subscriptions.get(subscription_id)
        if existing is not None:
            existing.cancel()
            with suppress(asyncio.CancelledError):
                await existing
            del state.subscriptions[subscription_id]
        if asset_ids:
            task = asyncio.create_task(
                _subscription_runner(state, subscription_id, asset_ids),
                name=f"bot_h_maker_v2.{subscription_id}",
            )
            state.subscriptions[subscription_id] = task

        await asyncio.sleep(GAMMA_SCAN_INTERVAL_SEC)


async def heartbeat_loop(state: RecorderState) -> None:
    """Emit a heartbeat row every HEARTBEAT_INTERVAL_SEC so the audit
    script can detect silent stalls."""
    while True:
        try:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
            now_ms = int(time.time() * 1000)
            counts_summary = ",".join(
                f"{k}={v}" for k, v in sorted(state.event_counts.items())
            ) or "none"
            state.queue.put_nowait(
                WriteTask(
                    kind="heartbeat",
                    row={
                        "received_at_ms": now_ms,
                        "subscription_id": "bot_h_maker_v2/all",
                        "asset_id_count": len(state.token_to_condition),
                        "note": f"events={counts_summary} qsize={state.queue.qsize()}",
                    },
                )
            )
        except asyncio.QueueFull:
            log.warning("bot_h_maker_v2.heartbeat.queue_full skipping")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("bot_h_maker_v2.heartbeat.error %s", exc)


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------


async def run_recorder() -> None:
    """Main entrypoint: spawn writer, discovery, and heartbeat loops."""
    state = RecorderState()
    writer_task = asyncio.create_task(writer_loop(state), name="bot_h_maker_v2.writer")
    discovery_task = asyncio.create_task(
        discovery_loop(state), name="bot_h_maker_v2.discovery"
    )
    heartbeat_task = asyncio.create_task(
        heartbeat_loop(state), name="bot_h_maker_v2.heartbeat"
    )
    log.info(
        "bot_h_maker_v2.recorder.started gamma_scan_interval_s=%.0f heartbeat_interval_s=%.0f",
        GAMMA_SCAN_INTERVAL_SEC,
        HEARTBEAT_INTERVAL_SEC,
    )
    try:
        await asyncio.gather(writer_task, discovery_task, heartbeat_task)
    except asyncio.CancelledError:
        log.info("bot_h_maker_v2.recorder.cancelled shutting_down")
        for task in (writer_task, discovery_task, heartbeat_task, *state.subscriptions.values()):
            task.cancel()
        with suppress(BaseException):
            await asyncio.gather(
                writer_task,
                discovery_task,
                heartbeat_task,
                *state.subscriptions.values(),
                return_exceptions=True,
            )
        raise
