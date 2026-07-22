"""Executor for Bot K — Sports Taker (market-open) paper lane.

Polls maker_recorder.db for new sports markets in the 10-20c band,
finds the first best_bid_ask tick within the lookback window, and records
paper entries in the main bot DB (orders, trades, positions).
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

from bots.bot_k_sports_taker import config as cfg
from core.db import Order, Position, Trade, get_session_factory, upsert_market_minimal
from core.fees import fee_for_fill

log = logging.getLogger(__name__)


def _connect_recorder(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _has_column(con: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row["name"] == column for row in con.execute(f"PRAGMA table_info({table})"))


def _to_epoch_ms(value: object) -> int | None:
    if value is None:
        return None
    try:
        raw = int(value)
    except (TypeError, ValueError):
        return None
    return raw if raw > 10_000_000_000 else raw * 1000


def _find_new_markets(con: sqlite3.Connection, *, after_discovered_at_ms: int = 0) -> list[dict[str, Any]]:
    has_end_date_ts = _has_column(con, "markets", "end_date_ts")
    end_date_select = ", end_date_ts" if has_end_date_ts else ""
    rows = con.execute(
        f"""
        SELECT condition_id, category, question, initial_yes_price, discovered_at_ms
               {end_date_select}
        FROM markets
        WHERE category = ?
          AND initial_yes_price >= ?
          AND initial_yes_price <= ?
          AND discovered_at_ms > ?
        ORDER BY discovered_at_ms ASC
        """,
        (cfg.CATEGORY, cfg.MIN_PRICE, cfg.MAX_PRICE, after_discovered_at_ms),
    ).fetchall()
    out = []
    for r in rows:
        discovered_at_ms = int(r["discovered_at_ms"]) if r["discovered_at_ms"] is not None else 0
        end_date_ms = _to_epoch_ms(r["end_date_ts"]) if has_end_date_ts else None
        if end_date_ms is not None:
            ttr_hours = (end_date_ms - discovered_at_ms) / 3_600_000
            if ttr_hours <= 0 or ttr_hours > cfg.MAX_TIME_TO_RESOLUTION_HOURS:
                continue
        out.append({
            "condition_id": str(r["condition_id"]),
            "category": str(r["category"]),
            "question": str(r["question"]),
            "initial_yes_price": float(r["initial_yes_price"]) if r["initial_yes_price"] is not None else 0.0,
            "discovered_at_ms": discovered_at_ms,
            "end_date_ms": end_date_ms,
        })
    return out


def _load_first_ticks(con: sqlite3.Connection, markets: list[dict[str, Any]], lookback_min: int) -> dict[str, dict[str, Any]]:
    if not markets:
        return {}
    cids = [m["condition_id"] for m in markets]
    placeholders = ",".join("?" * len(cids))
    rows = con.execute(
        f"""
        SELECT condition_id, received_at_ms, payload_json
        FROM pm_events
        WHERE event_type = 'best_bid_ask'
          AND condition_id IN ({placeholders})
        ORDER BY condition_id, received_at_ms
        """,
        tuple(cids),
    ).fetchall()

    by_cid: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for r in rows:
        try:
            payload = json.loads(r["payload_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        by_cid[str(r["condition_id"])].append((int(r["received_at_ms"]), payload))

    out: dict[str, dict[str, Any]] = {}
    for m in markets:
        series = by_cid.get(m["condition_id"], [])
        cutoff_ms = m["discovered_at_ms"] + lookback_min * 60 * 1000
        for ts, payload in series:
            if ts > cutoff_ms:
                break
            try:
                bid = float(payload.get("best_bid", payload.get("bid", 0)))
                ask = float(payload.get("best_ask", payload.get("ask", 0)))
            except (TypeError, ValueError):
                continue
            if bid <= 0 or ask <= 0 or ask <= bid:
                continue
            entry_price = min(ask + cfg.TICK_SIZE, 0.99)
            out[m["condition_id"]] = {
                "timestamp_ms": ts,
                "bid": bid,
                "ask": ask,
                "entry_price": entry_price,
            }
            break
    return out


def _already_entered(condition_id: str) -> bool:
    sf = get_session_factory()
    with sf() as session:
        return session.scalars(
            select(Order.order_id).where(
                Order.bot_id == cfg.BOT_ID,
                Order.condition_id == condition_id,
            )
        ).first() is not None


def _has_open_or_recent(condition_id: str, cooldown_seconds: int = cfg.COOLDOWN_S) -> bool:
    sf = get_session_factory()
    with sf() as session:
        open_pos = session.scalars(
            select(Position.id).where(
                Position.bot_id == cfg.BOT_ID,
                Position.condition_id == condition_id,
                Position.status == "OPEN",
            )
        ).first()
        if open_pos is not None:
            return True
        recent_order = session.scalars(
            select(Order.placed_at).where(
                Order.bot_id == cfg.BOT_ID,
                Order.condition_id == condition_id,
            ).order_by(Order.placed_at.desc())
        ).first()
        if recent_order is not None:
            age = (datetime.now(UTC) - recent_order).total_seconds()
            if age < cooldown_seconds:
                return True
    return False


def _daily_entry_count() -> int:
    sf = get_session_factory()
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    with sf() as session:
        return session.query(Order).filter(
            Order.bot_id == cfg.BOT_ID,
            Order.placed_at >= today,
        ).count()


def _open_position_count() -> int:
    sf = get_session_factory()
    with sf() as session:
        return session.query(Position).filter(
            Position.bot_id == cfg.BOT_ID,
            Position.status == "OPEN",
        ).count()


def _record_paper_entry(market: dict[str, Any], tick: dict[str, Any]) -> bool:
    condition_id = market["condition_id"]
    if _has_open_or_recent(condition_id):
        log.debug("bot_k.skip cooldown condition_id=%s", condition_id)
        return False

    if _daily_entry_count() >= cfg.MAX_DAILY_ENTRIES:
        log.warning("bot_k.daily_cap_reached max=%d", cfg.MAX_DAILY_ENTRIES)
        return False

    if _open_position_count() >= cfg.MAX_CONCURRENT_POSITIONS:
        log.warning("bot_k.concurrent_cap_reached max=%d", cfg.MAX_CONCURRENT_POSITIONS)
        return False

    price = Decimal(str(tick["entry_price"]))
    stake = Decimal(str(cfg.STAKE_USD))
    size = (stake / price).quantize(Decimal("0.00000001"))
    fee = fee_for_fill(price, size, "sports", is_maker=False).gross_fee
    now = datetime.now(UTC)
    order_id = f"bot_k_{condition_id[:16]}_{int(now.timestamp())}"
    token_id = f"{condition_id}-YES"

    sf = get_session_factory()
    with sf() as session:
        upsert_market_minimal(
            session,
            condition_id=condition_id,
            category="sports",
            question=market["question"],
            end_date=None,
        )
        session.add(
            Order(
                order_id=order_id,
                bot_id=cfg.BOT_ID,
                condition_id=condition_id,
                token_id=token_id,
                side="BUY",
                price=price,
                size=size,
                status="FILLED",
                placed_at=now,
                last_updated=now,
            )
        )
        session.add(
            Trade(
                trade_id=order_id,
                bot_id=cfg.BOT_ID,
                order_id=order_id,
                condition_id=condition_id,
                token_id=token_id,
                side="BUY",
                price=price,
                size=size,
                fee_usd=fee,
                filled_at=now,
                usd_gbp_rate=Decimal("0.79"),
                gbp_notional=(stake * Decimal("0.79")).quantize(Decimal("0.00000001")),
            )
        )
        session.add(
            Position(
                bot_id=cfg.BOT_ID,
                condition_id=condition_id,
                token_id=token_id,
                side="YES",
                size=size,
                avg_price=price,
                cost_basis_usd=(price * size + fee).quantize(Decimal("0.00000001")),
                status="OPEN",
                opened_at=now,
            )
        )
        session.commit()

    log.info(
        "bot_k.paper_entry price=%.4f size=%s condition=%s question=%.60s",
        float(price),
        str(size),
        condition_id,
        market["question"],
    )
    return True


def run_once(*, recorder_db: Path | None = None) -> dict[str, Any]:
    db_path = recorder_db or cfg.DEFAULT_RECORDER_DB
    if not db_path.exists():
        log.error("bot_k.recorder_db_not_found path=%s", db_path)
        return {"scanned": 0, "recorded": 0, "error": "db_not_found"}

    con = _connect_recorder(db_path)
    try:
        markets = _find_new_markets(con)
        if not markets:
            log.debug("bot_k.no_new_markets")
            return {"scanned": 0, "recorded": 0}

        ticks = _load_first_ticks(con, markets, cfg.LOOKBACK_MIN)
    finally:
        con.close()

    recorded = 0
    for m in markets:
        tick = ticks.get(m["condition_id"])
        if tick is None:
            log.debug("bot_k.no_tick condition_id=%s", m["condition_id"])
            continue
        if _already_entered(m["condition_id"]):
            log.debug("bot_k.already_entered condition_id=%s", m["condition_id"])
            continue
        if _record_paper_entry(m, tick):
            recorded += 1

    return {"scanned": len(markets), "recorded": recorded}
