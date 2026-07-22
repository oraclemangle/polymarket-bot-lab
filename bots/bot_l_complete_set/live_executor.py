"""Bot L Complete-Set BUY/MERGE live-probe executor.

This module is deliberately conservative. It can place BUY orders only when
the approved bundle cap satisfies the exchange's 5-share minimum and the
bundle stays inside daily/open exposure caps.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, time
from decimal import Decimal
from pathlib import Path

from core.clob_v2 import ClobWrapperV2, OrderResponse, OrderType, Side
from core.db import Event, Order, get_session_factory, upsert_market_minimal
from core.portfolio import Portfolio

BOT_ID = "bot_l_complete_set"
MIN_CLOB_SHARES = Decimal("5")


@dataclass(frozen=True)
class CompleteSetSignal:
    signal_id: int
    condition_id: str
    question: str | None
    yes_token_id: str
    no_token_id: str
    yes_price: Decimal
    no_price: Decimal
    simulated_cost_usd: Decimal
    detected_at_ms: int


@dataclass(frozen=True)
class CompleteSetResult:
    placed: bool
    reason: str
    signal_id: int | None = None
    yes_order_id: str | None = None
    no_order_id: str | None = None
    shares: Decimal | None = None
    gross_cost_usd: Decimal | None = None


def _signal_already_attempted(signal_id: int) -> bool:
    sf = get_session_factory()
    with sf() as session:
        return session.query(Event.id).filter(
            Event.bot_id == BOT_ID,
            Event.event_type.in_(
                (
                    "bot_l.complete_set.bundle_attempt",
                    "bot_l.complete_set.bundle_incomplete",
                )
            ),
            Event.payload["signal_id"].as_integer() == int(signal_id),
        ).first() is not None


def daily_gross_used_usd() -> Decimal:
    sf = get_session_factory()
    day_start = datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)
    total = Decimal("0")
    with sf() as session:
        rows = session.query(Order.price, Order.size).filter(
            Order.bot_id == BOT_ID,
            Order.side == "BUY",
            Order.placed_at >= day_start,
            Order.status.in_(("OPEN", "FILLED", "PARTIAL", "SUBMITTING")),
        )
        for price, size in rows:
            if price is not None and size is not None:
                total += Decimal(str(price)) * Decimal(str(size))
    return total.quantize(Decimal("0.0001"))


def open_order_exposure_usd() -> Decimal:
    sf = get_session_factory()
    total = Decimal("0")
    with sf() as session:
        rows = session.query(Order.price, Order.size).filter(
            Order.bot_id == BOT_ID,
            Order.side == "BUY",
            Order.status.in_(("OPEN", "PARTIAL", "SUBMITTING")),
        )
        for price, size in rows:
            if price is not None and size is not None:
                total += Decimal(str(price)) * Decimal(str(size))
    return total.quantize(Decimal("0.0001"))


def current_open_exposure_usd() -> Decimal:
    portfolio_exposure = Decimal(str(Portfolio().get_total_exposure(BOT_ID) or 0))
    return (portfolio_exposure + open_order_exposure_usd()).quantize(Decimal("0.0001"))


def latest_executable_signal(
    paper_db_path: Path,
    *,
    max_signal_age_ms: int | None = None,
) -> CompleteSetSignal | None:
    con = sqlite3.connect(str(paper_db_path))
    con.row_factory = sqlite3.Row
    try:
        cutoff_ms = None
        if max_signal_age_ms is not None:
            cutoff_ms = int(datetime.now(UTC).timestamp() * 1000) - int(max_signal_age_ms)
        row = con.execute(
            """
            SELECT id, condition_id, question, yes_token_id, no_token_id,
                   yes_price, no_price, simulated_cost_usd, detected_at_ms
            FROM bot_l_complete_set_signals
            WHERE signal_type='BUY_COMPLETE_SET'
              AND executable=1
              AND reason='passes_haircut'
              AND (? IS NULL OR detected_at_ms >= ?)
            ORDER BY detected_at_ms DESC, id DESC
            LIMIT 1
            """,
            (cutoff_ms, cutoff_ms),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        return None
    return CompleteSetSignal(
        signal_id=int(row["id"]),
        condition_id=str(row["condition_id"]),
        question=row["question"],
        yes_token_id=str(row["yes_token_id"]),
        no_token_id=str(row["no_token_id"]),
        yes_price=Decimal(str(row["yes_price"])),
        no_price=Decimal(str(row["no_price"])),
        simulated_cost_usd=Decimal(str(row["simulated_cost_usd"])),
        detected_at_ms=int(row["detected_at_ms"]),
    )


def place_buy_bundle(
    clob: ClobWrapperV2,
    signal: CompleteSetSignal,
    *,
    max_bundle_usd: Decimal = Decimal("1"),
    daily_gross_used_usd: Decimal = Decimal("0"),
    daily_gross_cap_usd: Decimal = Decimal("10"),
    open_exposure_usd: Decimal = Decimal("0"),
    open_exposure_cap_usd: Decimal = Decimal("20"),
    dry_run: bool = False,
) -> CompleteSetResult:
    if _signal_already_attempted(signal.signal_id):
        return CompleteSetResult(False, "dedupe", signal_id=signal.signal_id)

    gross_price = signal.yes_price + signal.no_price
    if gross_price <= 0:
        return CompleteSetResult(False, "bad_price", signal_id=signal.signal_id)
    target_gross_usd = max_bundle_usd.quantize(Decimal("0.0001"))
    if target_gross_usd <= 0:
        return CompleteSetResult(False, "bundle_cap", signal_id=signal.signal_id)
    shares = (target_gross_usd / gross_price).quantize(Decimal("0.0001"))
    gross_cost = (shares * gross_price).quantize(Decimal("0.0001"))
    if gross_cost > max_bundle_usd:
        return CompleteSetResult(False, "bundle_cap", signal_id=signal.signal_id)
    if shares < MIN_CLOB_SHARES:
        return CompleteSetResult(
            False,
            "below_exchange_min_shares",
            signal_id=signal.signal_id,
            shares=shares,
            gross_cost_usd=gross_cost,
        )
    if daily_gross_used_usd + gross_cost > daily_gross_cap_usd:
        return CompleteSetResult(False, "daily_gross_cap", signal_id=signal.signal_id)
    if open_exposure_usd + gross_cost > open_exposure_cap_usd:
        return CompleteSetResult(False, "open_exposure_cap", signal_id=signal.signal_id)
    if dry_run:
        return CompleteSetResult(
            False,
            "dry_run",
            signal_id=signal.signal_id,
            shares=shares,
            gross_cost_usd=gross_cost,
        )

    try:
        clob.get_book(signal.yes_token_id)
        clob.get_book(signal.no_token_id)
    except Exception as exc:
        return CompleteSetResult(False, f"live_book_unavailable:{type(exc).__name__}", signal_id=signal.signal_id)

    try:
        yes_resp = clob.place_limit(
            token_id=signal.yes_token_id,
            price=signal.yes_price.quantize(Decimal("0.001")),
            size=shares,
            side=Side.BUY,
            order_type=OrderType.GTC,
        )
    except Exception as exc:
        return CompleteSetResult(False, f"yes_place_failed:{type(exc).__name__}", signal_id=signal.signal_id)
    if not yes_resp.order_id:
        return CompleteSetResult(False, f"yes_rejected:{yes_resp.status}", signal_id=signal.signal_id)

    try:
        no_resp = clob.place_limit(
            token_id=signal.no_token_id,
            price=signal.no_price.quantize(Decimal("0.001")),
            size=shares,
            side=Side.BUY,
            order_type=OrderType.GTC,
        )
    except Exception as exc:
        no_resp = OrderResponse(order_id="", status=f"place_failed:{type(exc).__name__}", raw={})
    if not no_resp.order_id:
        cancel_ok = False
        try:
            cancel_ok = clob.cancel_order(yes_resp.order_id)
        except Exception:
            cancel_ok = False
        _persist_incomplete_bundle(
            signal,
            yes_order_id=yes_resp.order_id,
            yes_status="CANCELLED" if cancel_ok else "OPEN",
            no_status=str(no_resp.status or "NO_ORDER_ID"),
            shares=shares,
            gross_cost=gross_cost,
            yes_price=signal.yes_price,
        )
        return CompleteSetResult(
            False,
            f"no_rejected:{no_resp.status}",
            signal_id=signal.signal_id,
            yes_order_id=yes_resp.order_id,
        )

    sf = get_session_factory()
    now = datetime.now(UTC)
    with sf() as session:
        upsert_market_minimal(
            session,
            condition_id=signal.condition_id,
            category="crypto",
            question=signal.question,
            yes_token_id=signal.yes_token_id,
            no_token_id=signal.no_token_id,
        )
        for order_id, token_id, price in (
            (yes_resp.order_id, signal.yes_token_id, signal.yes_price),
            (no_resp.order_id, signal.no_token_id, signal.no_price),
        ):
            session.add(
                Order(
                    order_id=order_id,
                    bot_id=BOT_ID,
                    condition_id=signal.condition_id,
                    token_id=token_id,
                    side="BUY",
                    price=price.quantize(Decimal("0.001")),
                    size=shares,
                    status="OPEN",
                    order_type="GTC",
                    placed_at=now,
                )
            )
        session.add(
            Event(
                bot_id=BOT_ID,
                event_type="bot_l.complete_set.bundle_attempt",
                severity="info",
                message=f"BUY_COMPLETE_SET signal={signal.signal_id} shares={shares}",
                payload={
                    "signal_id": signal.signal_id,
                    "condition_id": signal.condition_id,
                    "yes_order_id": yes_resp.order_id,
                    "no_order_id": no_resp.order_id,
                    "shares": str(shares),
                    "gross_cost_usd": str(gross_cost),
                },
            )
        )
        session.commit()

    return CompleteSetResult(
        True,
        "placed",
        signal_id=signal.signal_id,
        yes_order_id=yes_resp.order_id,
        no_order_id=no_resp.order_id,
        shares=shares,
        gross_cost_usd=gross_cost,
    )


def _persist_incomplete_bundle(
    signal: CompleteSetSignal,
    *,
    yes_order_id: str,
    yes_status: str,
    no_status: str,
    shares: Decimal,
    gross_cost: Decimal,
    yes_price: Decimal,
) -> None:
    sf = get_session_factory()
    now = datetime.now(UTC)
    with sf() as session:
        upsert_market_minimal(
            session,
            condition_id=signal.condition_id,
            category="crypto",
            question=signal.question,
            yes_token_id=signal.yes_token_id,
            no_token_id=signal.no_token_id,
        )
        session.merge(
            Order(
                order_id=yes_order_id,
                bot_id=BOT_ID,
                condition_id=signal.condition_id,
                token_id=signal.yes_token_id,
                side="BUY",
                price=yes_price.quantize(Decimal("0.001")),
                size=shares,
                status=yes_status,
                order_type="GTC",
                placed_at=now,
            )
        )
        session.add(
            Event(
                bot_id=BOT_ID,
                event_type="bot_l.complete_set.bundle_incomplete",
                severity="kill" if yes_status != "CANCELLED" else "warn",
                message=f"BUY_COMPLETE_SET incomplete signal={signal.signal_id}",
                payload={
                    "signal_id": signal.signal_id,
                    "condition_id": signal.condition_id,
                    "yes_order_id": yes_order_id,
                    "yes_status": yes_status,
                    "no_status": no_status,
                    "shares": str(shares),
                    "gross_cost_usd": str(gross_cost),
                },
            )
        )
        session.commit()


def reconcile_live(clob: ClobWrapperV2) -> int:
    return int(Portfolio().reconcile_live_fills(clob, BOT_ID, require_known_order=True) or 0)
