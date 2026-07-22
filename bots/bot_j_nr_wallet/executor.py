"""Executor for Bot J — Near-Resolution Wallet paper lane.

Polls wallet_tag_forward.db for qualifying BUY trades from the 7-wallet
cohort in sports/esports markets at 30-70c, then records paper entries in
the main bot DB (orders, trades, positions).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select

from bots.bot_j_nr_wallet import config as cfg
from core.db import Order, Position, Trade, get_session_factory, upsert_market_minimal
from core.fees import fee_for_fill

log = logging.getLogger(__name__)


def _is_sports(question: str | None) -> bool:
    if not question:
        return False
    q = question.lower()
    has_kw = any(kw in q for kw in cfg.SPORTS_KEYWORDS)
    if not has_kw:
        return False
    # Require "game" or "map" to co-occur with an esports keyword
    if "game" in q or "map" in q:
        esports_kws = {"lol", "cs:", "counter-strike", "esports", "bo3", "bo5", "league of legends", "valorant", "vct"}
        if not any(ek in q for ek in esports_kws):
            return False
    return True


def _connect_observer(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _log_wallet_signal(wallet: str, condition_id: str, price: Decimal, side: str) -> None:
    """Emit a structured wallet-quality log line for downstream aggregation.

    Format: wallet=0xABC… condition=0xDEF… price=0.42 side=YES
    Dashboard / audit scripts can grep `bot_j.wallet_signal` for per-wallet
    hit-rate and P&L tracking.
    """
    log.info(
        "bot_j.wallet_signal wallet=%s condition=%s price=%.4f side=%s",
        wallet,
        condition_id,
        float(price),
        side,
    )


def _paper_order_id(trade: dict[str, Any]) -> str:
    return f"bot_j_{trade['wallet'][:10]}_{trade['timestamp_s']}"


def _qualifying_trades(
    con: sqlite3.Connection,
    *,
    after_ingested_at: str | None = None,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = "t.taker_direction = ? AND t.price >= ? AND t.price <= ?"
    params.extend([cfg.DIRECTION, cfg.MIN_PRICE, cfg.MAX_PRICE])
    if after_ingested_at:
        where += " AND t.ingested_at > ?"
        params.append(after_ingested_at)

    wallets = ",".join("?" * len(cfg.WALLET_COHORT))
    rows = con.execute(
        f"""
        SELECT
            t.wallet, t.asset_id, t.timestamp_s, t.price,
            t.token_amount, t.condition_id, t.market_id,
            t.outcome, t.outcome_index, t.usd_amount, t.ingested_at,
            m.question, m.end_date_iso
        FROM observed_trades t
        LEFT JOIN observed_markets m ON t.condition_id = m.condition_id
        WHERE t.wallet IN ({wallets})
          AND {where}
        ORDER BY t.ingested_at ASC
        """,
        list(cfg.WALLET_COHORT) + params,
    ).fetchall()

    out = []
    for r in rows:
        if not _is_sports(r["question"]):
            continue
        out.append({
            "wallet": r["wallet"],
            "asset_id": r["asset_id"],
            "timestamp_s": r["timestamp_s"],
            "price": float(r["price"]),
            "token_amount": float(r["token_amount"]),
            "condition_id": r["condition_id"],
            "market_id": r["market_id"],
            "outcome": r["outcome"],
            "outcome_index": r["outcome_index"],
            "usd_amount": float(r["usd_amount"] or 0),
            "ingested_at": r["ingested_at"],
            "question": r["question"] or "",
            "end_date_iso": r["end_date_iso"],
        })
    return out


def _has_open_or_recent(
    condition_id: str,
    cooldown_seconds: int = cfg.COOLDOWN_S,
) -> bool:
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


def _paper_order_exists(order_id: str) -> bool:
    sf = get_session_factory()
    with sf() as session:
        return session.scalars(
            select(Order.order_id).where(Order.order_id == order_id)
        ).first() is not None


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


def _token_side(outcome: str | None, outcome_index: int | None) -> str | None:
    if outcome_index is not None:
        return "YES" if outcome_index == 0 else "NO"
    label = str(outcome or "").strip().lower()
    if label in {"yes", "y"}:
        return "YES"
    if label in {"no", "n"}:
        return "NO"
    log.warning("bot_j.unknown_token_side outcome=%r — skipping", outcome)
    return None


def _record_paper_entry(trade: dict[str, Any]) -> bool:
    condition_id = trade["condition_id"]
    order_id = _paper_order_id(trade)
    if _paper_order_exists(order_id):
        log.debug("bot_j.skip duplicate order_id=%s", order_id)
        return False

    if _has_open_or_recent(condition_id):
        log.debug("bot_j.skip cooldown condition_id=%s", condition_id)
        return False

    if _daily_entry_count() >= cfg.MAX_DAILY_ENTRIES:
        log.warning("bot_j.daily_cap_reached max=%d", cfg.MAX_DAILY_ENTRIES)
        return False

    if _open_position_count() >= cfg.MAX_CONCURRENT_POSITIONS:
        log.warning("bot_j.concurrent_cap_reached max=%d", cfg.MAX_CONCURRENT_POSITIONS)
        return False

    price = Decimal(str(trade["price"]))
    stake = Decimal(str(cfg.STAKE_USD))
    size = (stake / price).quantize(Decimal("0.00000001"))
    fee = fee_for_fill(price, size, "sports", is_maker=False).gross_fee
    side = _token_side(trade["outcome"], trade.get("outcome_index"))
    if side is None:
        log.warning("bot_j.skip unknown side condition_id=%s", condition_id)
        return False
    token_id = trade["asset_id"]
    now = datetime.now(UTC)

    sf = get_session_factory()
    with sf() as session:
        upsert_market_minimal(
            session,
            condition_id=condition_id,
            category="sports",
            question=trade["question"],
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
                usd_gbp_rate=Decimal(cfg.USD_GBP_RATE),
                gbp_notional=(stake * Decimal("0.79")).quantize(Decimal("0.00000001")),
            )
        )
        session.add(
            Position(
                bot_id=cfg.BOT_ID,
                condition_id=condition_id,
                token_id=token_id,
                side=side,
                size=size,
                avg_price=price,
                cost_basis_usd=(price * size + fee).quantize(Decimal("0.00000001")),
                status="OPEN",
                opened_at=now,
            )
        )
        session.commit()

    log.info(
        "bot_j.paper_entry wallet=%s price=%.4f size=%s side=%s condition=%s question=%.60s",
        trade["wallet"],
        float(price),
        str(size),
        side,
        condition_id,
        trade["question"],
    )
    _log_wallet_signal(trade["wallet"], condition_id, price, side)
    return True


def run_once(*, observer_db: Path | None = None) -> dict[str, Any]:
    db_path = observer_db or cfg.DEFAULT_OBSERVER_DB
    con = _connect_observer(db_path)
    try:
        trades = _qualifying_trades(con)
    finally:
        con.close()

    if not trades:
        log.info("bot_j.no_qualifying_trades")
        return {"scanned": 0, "recorded": 0}

    log.info("bot_j.qualifying_trades n=%d", len(trades))
    recorded = 0
    for trade in trades:
        if _record_paper_entry(trade):
            recorded += 1

    return {"scanned": len(trades), "recorded": recorded}
