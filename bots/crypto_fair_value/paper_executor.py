"""Paper-only execution for crypto fair-value signals."""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from bots.crypto_fair_value.config import CryptoFairValueConfig
from bots.crypto_fair_value.model import MarketMeta, Signal
from core.db import Event, Order, Position, get_session_factory, upsert_market_minimal
from core.fees import fee_for_fill
from core.portfolio import Portfolio

FILL_TRACKS: tuple[tuple[str, Decimal], ...] = (
    ("paper_taker_top", Decimal("0")),
    ("paper_taker_stressed_1c", Decimal("0.01")),
    ("paper_taker_stressed_2c", Decimal("0.02")),
)
MAIN_TRACK = "paper_taker_stressed_1c"
MAKER_FILL_TRACKS: tuple[str, ...] = ("paper_maker_bid",)
MAKER_MAIN_TRACK = "paper_maker_bid"


def has_open_position(bot_id: str, condition_id: str) -> bool:
    sf = get_session_factory()
    with sf() as session:
        return session.scalars(
            select(Position).where(
                Position.bot_id == bot_id,
                Position.condition_id == condition_id,
                Position.status == "OPEN",
            )
        ).first() is not None


def has_recorded_entry(bot_id: str, condition_id: str) -> bool:
    """True once this paper bot has already claimed a market condition."""
    sf = get_session_factory()
    with sf() as session:
        existing_order = session.scalars(
            select(Order.order_id).where(
                Order.bot_id == bot_id,
                Order.condition_id == condition_id,
            )
        ).first()
        if existing_order is not None:
            return True
        return session.scalars(
            select(Position.id).where(
                Position.bot_id == bot_id,
                Position.condition_id == condition_id,
            )
        ).first() is not None


def _order_id(bot_id: str, signal: Signal, track: str) -> str:
    raw = f"{bot_id}|{signal.condition_id}|{track}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"cfv-{digest}"


def _maker_bid_price(signal: Signal) -> Decimal:
    return max(Decimal("0.01"), signal.ask_price - signal.effective_spread)


def _track_fill(
    signal: Signal,
    track: str,
    stress: Decimal,
    stake_usd: Decimal,
    *,
    execution_style: str,
) -> dict:
    price = (
        _maker_bid_price(signal)
        if execution_style == "maker"
        else signal.ask_price + stress
    )
    if price <= 0 or price >= Decimal("1"):
        return {
            "fill_track": track,
            "filled": False,
            "reason": "stressed_price_out_of_bounds",
            "entry_price": str(price),
            "execution_style": execution_style,
        }
    size = (stake_usd / price).quantize(Decimal("0.00000001"))
    fee = (
        Decimal("0")
        if execution_style == "maker"
        else fee_for_fill(price, size, "crypto", is_maker=False).gross_fee
    )
    return {
        "fill_track": track,
        "filled": True,
        "execution_style": execution_style,
        "entry_price": str(price.quantize(Decimal("0.00000001"))),
        "size": str(size),
        "fee_usd": str(fee.quantize(Decimal("0.00000001"))),
        "stake_usd": str(stake_usd),
    }


def _signal_payload(signal: Signal) -> dict:
    return {
        "strategy": signal.strategy,
        "condition_id": signal.condition_id,
        "symbol": signal.symbol,
        "duration_minutes": signal.duration_minutes,
        "side": signal.side,
        "token_id": signal.token_id,
        "ask_price": str(signal.ask_price),
        "model_probability_up": signal.model_probability_up,
        "model_edge": str(signal.model_edge),
        "pm_mid_up": str(signal.pm_mid_up),
        "effective_spread": str(signal.effective_spread),
        "top_depth_usd": str(signal.top_depth_usd),
        "seconds_left": signal.seconds_left,
        "decision_ms": signal.decision_ms,
        "cex_move_60s": signal.cex_move_60s,
    }


def execute_signal(
    *,
    config: CryptoFairValueConfig,
    meta: MarketMeta,
    signal: Signal,
    portfolio: Portfolio | None = None,
) -> bool:
    """Record a paper signal and fill the 1c stressed track in portfolio tables."""
    if has_recorded_entry(config.bot_id, signal.condition_id):
        return False

    if config.execution_style == "maker":
        track_fills = [
            _track_fill(
                signal,
                track,
                Decimal("0"),
                config.stake_usd,
                execution_style=config.execution_style,
            )
            for track in MAKER_FILL_TRACKS
        ]
        main_track = MAKER_MAIN_TRACK
    else:
        track_fills = [
            _track_fill(
                signal,
                track,
                stress,
                config.stake_usd,
                execution_style=config.execution_style,
            )
            for track, stress in FILL_TRACKS
        ]
        main_track = MAIN_TRACK
    main_fill = next(fill for fill in track_fills if fill["fill_track"] == main_track)
    now = datetime.fromtimestamp(signal.decision_ms / 1000, tz=UTC)
    order_id = _order_id(config.bot_id, signal, main_track)

    sf = get_session_factory()
    with sf() as session:
        upsert_market_minimal(
            session,
            condition_id=meta.condition_id,
            category="crypto",
            question=meta.question,
            yes_token_id=meta.yes_token_id,
            no_token_id=meta.no_token_id,
            end_date=datetime.fromtimestamp(meta.end_ms / 1000, tz=UTC),
        )
        session.add(
            Event(
                bot_id=config.bot_id,
                event_type="crypto_fair_value.signal",
                severity="info",
                message=(
                    f"{config.strategy} {signal.side} signal "
                    f"edge={signal.model_edge} ask={signal.ask_price}"
                ),
                payload={
                    **_signal_payload(signal),
                    "question": meta.question,
                    "main_fill_track": main_track,
                    "fill_tracks": track_fills,
                    "strategy": config.strategy,
                    "side": signal.side,
                    "lead_bucket": signal.lead_bucket,
                    "probability_bucket": signal.probability_bucket,
                    "ask_bucket": signal.ask_bucket,
                    "decision_iso": now.isoformat(),
                    "execution_style": config.execution_style,
                },
                created_at=now,
            )
        )
        if main_fill["filled"]:
            session.add(
                Order(
                    order_id=order_id,
                    bot_id=config.bot_id,
                    condition_id=signal.condition_id,
                    token_id=signal.token_id,
                    side="BUY",
                    price=Decimal(str(main_fill["entry_price"])),
                    size=Decimal(str(main_fill["size"])),
                    status="PAPER_OPEN",
                    order_type=(
                        "PAPER_MAKER_BID"
                        if config.execution_style == "maker"
                        else "PAPER_TAKER_STRESSED_1C"
                    ),
                    placed_at=now,
                )
            )
        session.commit()

    if not main_fill["filled"]:
        return False

    pfo = portfolio or Portfolio()
    pfo.on_fill(
        bot_id=config.bot_id,
        trade_id=f"paper-fill-{order_id}",
        order_id=order_id,
        condition_id=signal.condition_id,
        token_id=signal.token_id,
        side="BUY",
        price=Decimal(str(main_fill["entry_price"])),
        size=Decimal(str(main_fill["size"])),
        fee_usd=Decimal(str(main_fill["fee_usd"])),
        filled_at=now,
    )
    with sf() as session:
        order = session.get(Order, order_id)
        if order is not None:
            order.status = "FILLED"
            session.commit()
    return True
