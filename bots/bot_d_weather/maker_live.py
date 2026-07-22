"""Bot D maker live probe.

Separate live-maker lane for Weather Fade. This service reuses Bot D's
forecast/fair-value model but places only non-crossing BUY quotes under a
separate bot id. It is intentionally isolated from ``bot_d_live_probe`` so
maker fills, P&L, caps, and cancels can be audited independently.
"""
from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from time import sleep

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from bots.bot_d_weather.config import (
    BOT_D_EDGE_THRESHOLD,
    BOT_D_MAX_LOCKUP_HOURS,
    BOT_D_REQUIRE_KNOWN_END_DATE,
    BOT_D_REQUIRE_VERIFIED_SETTLEMENT,
    SETTLEMENT_SPECS,
)
from bots.bot_d_weather.discovery import WeatherMarket, fetch_weather_markets
from bots.bot_d_weather.executor import MIN_POLYMARKET_SHARES, BotDExecutor
from bots.bot_d_weather.strategy import (
    WeatherEdgeDecision,
    apply_one_bet_per_event,
    apply_wave_regime_sizing,
    evaluate_weather_market,
)
from bots.bot_d_weather.weather_fetcher import get_forecasts
from core.clob import OrderBook, OrderResponse, OrderType, Side
from core.db import Event, HaltFlag, Order, Position, get_session_factory, init_db
from core.emergency_halt import is_emergency_halted
from core.fleet import check_fleet_exposure
from core.portfolio import Portfolio

log = logging.getLogger(__name__)

BOT_ID = os.getenv("BOT_D_MAKER_ID_OVERRIDE", "bot_d_maker_live_probe")


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: str = "false") -> bool:
    return _env(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_decimal(name: str, default: str) -> Decimal:
    return Decimal(_env(name, default))


def _env_int(name: str, default: str) -> int:
    return int(_env(name, default))


@dataclass(frozen=True)
class MakerConfig:
    wallet_usd: Decimal = field(default_factory=lambda: _env_decimal("BOT_D_MAKER_LIVE_WALLET_USD", "200"))
    min_notional_usd: Decimal = field(default_factory=lambda: _env_decimal("BOT_D_MAKER_MIN_NOTIONAL_USD", "5"))
    max_order_usd: Decimal = field(default_factory=lambda: _env_decimal("BOT_D_MAKER_MAX_ORDER_USD", "10"))
    max_daily_gross_usd: Decimal = field(
        default_factory=lambda: _env_decimal("BOT_D_MAKER_MAX_DAILY_GROSS_USD", "100")
    )
    max_open_exposure_usd: Decimal = field(
        default_factory=lambda: _env_decimal("BOT_D_MAKER_MAX_OPEN_EXPOSURE_USD", "100")
    )
    max_concurrent: int = field(default_factory=lambda: _env_int("BOT_D_MAKER_MAX_CONCURRENT_POSITIONS", "20"))
    max_quote_age_sec: int = field(default_factory=lambda: _env_int("BOT_D_MAKER_MAX_QUOTE_AGE_SEC", "180"))
    max_forecast_age_sec: int = field(default_factory=lambda: _env_int("BOT_D_MAKER_MAX_FORECAST_AGE_SEC", "1800"))
    min_maker_edge: Decimal = field(default_factory=lambda: _env_decimal("BOT_D_MAKER_MIN_EDGE", "0.025"))
    quote_discount: Decimal = field(default_factory=lambda: _env_decimal("BOT_D_MAKER_QUOTE_DISCOUNT", "0.015"))
    assumed_tick: Decimal = field(default_factory=lambda: _env_decimal("BOT_D_MAKER_ASSUMED_TICK", "0.001"))
    max_lockup_hours: float = field(
        default_factory=lambda: float(_env("BOT_D_MAKER_MAX_LOCKUP_HOURS", str(BOT_D_MAX_LOCKUP_HOURS)))
    )
    min_entry_hours_to_end: float = field(
        default_factory=lambda: float(_env("BOT_D_MAKER_MIN_ENTRY_HOURS_TO_END", "3"))
    )
    late_yes_hours_to_end: float = field(
        default_factory=lambda: float(_env("BOT_D_MAKER_LATE_YES_HOURS_TO_END", "6"))
    )
    late_yes_max_notional_usd: Decimal = field(
        default_factory=lambda: _env_decimal("BOT_D_MAKER_LATE_YES_MAX_NOTIONAL_USD", "2")
    )
    cheap_yes_price: Decimal = field(default_factory=lambda: _env_decimal("BOT_D_MAKER_CHEAP_YES_PRICE", "0.05"))
    cheap_yes_max_notional_usd: Decimal = field(
        default_factory=lambda: _env_decimal("BOT_D_MAKER_CHEAP_YES_MAX_NOTIONAL_USD", "2")
    )
    live_authorized: bool = field(default_factory=lambda: _env_bool("BOT_D_MAKER_LIVE_AUTHORIZED"))
    approved_at: str = field(default_factory=lambda: _env("BOT_D_MAKER_LIVE_APPROVED_AT", "").strip())


@dataclass(frozen=True)
class MakerQuote:
    decision: WeatherEdgeDecision
    token_id: str
    side: Side
    fair_price: Decimal
    quote_price: Decimal
    shares: Decimal
    notional_usd: Decimal
    best_bid: Decimal | None
    best_ask: Decimal | None
    hours_to_end: float | None = None
    min_notional_usd: Decimal | None = None
    max_notional_usd: Decimal | None = None
    reason: str = "maker_quote"


OPEN_ORDER_STATUSES = {"OPEN", "PARTIAL", "MATCHED", "live"}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _q_price(value: Decimal) -> Decimal:
    return max(Decimal("0.001"), min(Decimal("0.999"), value)).quantize(Decimal("0.001"))


def _ceil_shares(notional: Decimal, price: Decimal) -> Decimal:
    if price <= 0:
        return MIN_POLYMARKET_SHARES
    return (notional / price).quantize(Decimal("1"), rounding=ROUND_CEILING)


def _floor_shares(notional: Decimal, price: Decimal) -> Decimal:
    if price <= 0:
        return MIN_POLYMARKET_SHARES
    return (notional / price).quantize(Decimal("1"), rounding=ROUND_FLOOR)


def _candidate_markets(markets: list[WeatherMarket], cfg: MakerConfig) -> list[WeatherMarket]:
    out: list[WeatherMarket] = []
    now = _utc_now()
    for market in markets:
        if BOT_D_REQUIRE_VERIFIED_SETTLEMENT:
            spec = SETTLEMENT_SPECS.get(market.city)
            if spec is None or not spec.verified:
                continue
        if BOT_D_REQUIRE_KNOWN_END_DATE and market.end_date is None:
            continue
        if market.end_date is not None:
            end = market.end_date if market.end_date.tzinfo else market.end_date.replace(tzinfo=UTC)
            hours_to_end = (end - now).total_seconds() / 3600
            if hours_to_end <= 0:
                continue
            if cfg.min_entry_hours_to_end > 0 and hours_to_end < cfg.min_entry_hours_to_end:
                continue
            if cfg.max_lockup_hours > 0 and hours_to_end > cfg.max_lockup_hours:
                continue
        out.append(market)
    return out


def _hours_to_end(market: WeatherMarket) -> float | None:
    if market.end_date is None:
        return None
    end = market.end_date if market.end_date.tzinfo else market.end_date.replace(tzinfo=UTC)
    return (end - _utc_now()).total_seconds() / 3600


def _best_bid_ask(book: OrderBook) -> tuple[Decimal | None, Decimal | None]:
    bids = [Decimal(str(p)) for p, _ in (book.bids or [])]
    asks = [Decimal(str(p)) for p, _ in (book.asks or [])]
    return (max(bids) if bids else None, min(asks) if asks else None)


def _side_token_and_fair(decision: WeatherEdgeDecision) -> tuple[str, Side, Decimal]:
    if decision.side == "BUY_YES":
        return decision.market.yes_token_id, Side.BUY, Decimal(str(decision.gfs_probability))
    if decision.side == "BUY_NO":
        return decision.market.no_token_id, Side.BUY, Decimal("1") - Decimal(str(decision.gfs_probability))
    raise ValueError(f"not buyable: {decision.side}")


def _notional_bounds(
    price: Decimal,
    cfg: MakerConfig,
    *,
    decision: WeatherEdgeDecision,
    hours_to_end: float | None,
) -> tuple[Decimal, Decimal]:
    min_notional = cfg.min_notional_usd
    max_notional = cfg.max_order_usd
    if decision.side == "BUY_YES":
        if price < cfg.cheap_yes_price:
            max_notional = min(max_notional, cfg.cheap_yes_max_notional_usd)
            min_notional = min(min_notional, max_notional)
        if (
            hours_to_end is not None
            and cfg.late_yes_hours_to_end > 0
            and hours_to_end < cfg.late_yes_hours_to_end
        ):
            max_notional = min(max_notional, cfg.late_yes_max_notional_usd)
            min_notional = min(min_notional, max_notional)
    return min_notional, max_notional


def _target_shares(
    price: Decimal,
    cfg: MakerConfig,
    *,
    min_notional_usd: Decimal | None = None,
    max_order_usd: Decimal | None = None,
) -> Decimal:
    """Price-aware maker sizing.

    The operator-approved packet says "$5 min notional" and "5-10 shares
    depending on cost". For cheap prices these conflict. We treat the dollar
    packet as the hard risk/evidence unit and use 5-10 shares only when that
    still reaches the minimum notional.
    """
    if price <= 0:
        return MIN_POLYMARKET_SHARES
    if price < Decimal("0.20"):
        base = Decimal("10")
    elif price < Decimal("0.60"):
        base = Decimal("8")
    else:
        base = Decimal("5")
    min_notional = min_notional_usd if min_notional_usd is not None else cfg.min_notional_usd
    max_notional = max_order_usd if max_order_usd is not None else cfg.max_order_usd
    min_shares = max(MIN_POLYMARKET_SHARES, _ceil_shares(min_notional, price))
    max_shares = max(MIN_POLYMARKET_SHARES, _floor_shares(max_notional, price))
    target = max(base, min_shares)
    return min(target, max_shares).quantize(Decimal("0.01"))


class BotDMakerLive:
    def __init__(self, *, clob, session_factory: sessionmaker | None = None, cfg: MakerConfig | None = None):
        self.clob = clob
        self.session_factory = session_factory or get_session_factory()
        self.cfg = cfg or MakerConfig()
        self.portfolio = Portfolio(session_factory=self.session_factory)

    def _emit(self, event_type: str, message: str, *, severity: str = "info", payload: dict | None = None) -> None:
        with self.session_factory() as s:
            s.add(Event(
                bot_id=BOT_ID,
                event_type=event_type,
                severity=severity,
                message=message,
                payload=payload or {},
            ))
            s.commit()

    def _paper_or_unauthorized_reason(self) -> str | None:
        if os.environ.get("POLYMARKET_ENV", "").lower() != "live":
            return "polymarket_env_not_live"
        if os.environ.get("BOT_D_MAKER_ENV", "").lower() != "live":
            return "maker_env_not_live"
        if not self.cfg.live_authorized:
            return "maker_live_not_authorized"
        if not self.cfg.approved_at:
            return "maker_live_missing_approved_at"
        if BOT_ID != "bot_d_maker_live_probe":
            return "maker_requires_separate_bot_id"
        effective_paper = getattr(self.clob, "_effective_paper", None)
        if callable(effective_paper) and effective_paper():
            return "clob_effective_paper"
        return None

    def halt_reason(self) -> str | None:
        if is_emergency_halted():
            return "emergency_halt"
        with self.session_factory() as s:
            flag = s.scalars(select(HaltFlag).where(HaltFlag.bot_id == BOT_ID)).first()
            if flag is not None and flag.halted:
                return "bot_halt"
        return None

    def count_open(self) -> int:
        with self.session_factory() as s:
            positions = s.scalars(
                select(Position.condition_id).where(
                    Position.bot_id == BOT_ID,
                    Position.status == "OPEN",
                )
            ).all()
            orders = s.scalars(
                select(Order.condition_id).where(
                    Order.bot_id == BOT_ID,
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            ).all()
        return len(set(positions) | set(orders))

    def open_exposure(self) -> Decimal:
        with self.session_factory() as s:
            pos = s.execute(
                select(func.coalesce(func.sum(Position.cost_basis_usd), 0)).where(
                    Position.bot_id == BOT_ID,
                    Position.status == "OPEN",
                )
            ).scalar() or Decimal("0")
            resting = s.execute(
                select(func.coalesce(func.sum(Order.price * Order.size), 0)).where(
                    Order.bot_id == BOT_ID,
                    Order.side == "BUY",
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            ).scalar() or Decimal("0")
        return Decimal(str(pos)) + Decimal(str(resting))

    def daily_gross(self) -> Decimal:
        day_start = _utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        with self.session_factory() as s:
            total = s.execute(
                select(func.coalesce(func.sum(Order.price * Order.size), 0)).where(
                    Order.bot_id == BOT_ID,
                    Order.placed_at >= day_start,
                    Order.side.in_(("BUY", "SELL")),
                )
            ).scalar() or Decimal("0")
        return Decimal(str(total))

    def has_open_order_or_position(self, condition_id: str) -> bool:
        with self.session_factory() as s:
            order = s.scalars(
                select(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.condition_id == condition_id,
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            ).first()
            if order is not None:
                return True
            pos = s.scalars(
                select(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.condition_id == condition_id,
                    Position.status == "OPEN",
                )
            ).first()
        return pos is not None

    def _sync_open_orders(self) -> int:
        try:
            exchange_ids = {o.order_id for o in self.clob.get_user_orders() if o.order_id}
        except Exception as exc:
            log.warning("bot_d_maker.order_sync.failed: %s", exc)
            return 0
        now = _utc_now()
        updated = 0
        with self.session_factory() as s:
            orders = list(s.scalars(
                select(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            ))
            for order in orders:
                if order.order_id in exchange_ids:
                    continue
                order.status = "CANCELLED"
                order.last_updated = now
                updated += 1
            if updated:
                s.add(Event(
                    bot_id=BOT_ID,
                    event_type="bot_d_maker.order_sync",
                    severity="info",
                    message=f"synced {updated} non-open maker orders",
                    payload={"updated": updated, "exchange_open_orders": len(exchange_ids)},
                ))
                s.commit()
        return updated

    def cancel_stale_quotes(self) -> int:
        now = _utc_now()
        cancelled = 0
        with self.session_factory() as s:
            orders = list(s.scalars(
                select(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.side == "BUY",
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            ))
        for order in orders:
            placed = order.placed_at if order.placed_at.tzinfo else order.placed_at.replace(tzinfo=UTC)
            age = (now - placed).total_seconds()
            if age < self.cfg.max_quote_age_sec:
                continue
            try:
                ok = bool(self.clob.cancel_order(order.order_id))
            except Exception as exc:
                self._emit(
                    "bot_d_maker.cancel_failed",
                    f"maker cancel failed order={order.order_id}",
                    severity="warn",
                    payload={"order_id": order.order_id, "age_seconds": age, "error": str(exc)[:200]},
                )
                continue
            with self.session_factory() as s:
                db_order = s.get(Order, order.order_id)
                if db_order is not None:
                    db_order.status = "CANCELLED" if ok else db_order.status
                    db_order.last_updated = now
                s.add(Event(
                    bot_id=BOT_ID,
                    event_type="bot_d_maker.quote_cancelled",
                    severity="info",
                    message=f"cancelled stale maker quote {order.order_id}",
                    payload={"order_id": order.order_id, "age_seconds": age, "ok": ok},
                ))
                s.commit()
            cancelled += 1 if ok else 0
        return cancelled

    def quote_for_decision(self, decision: WeatherEdgeDecision) -> MakerQuote | str:
        halted = self.halt_reason()
        if halted is not None:
            return halted
        if decision.side == "SKIP":
            return "skip"
        if decision.forecast_source == "nws_fallback":
            return "nws_fallback_entry_blocked"
        hours_to_end = _hours_to_end(decision.market)
        if decision.market.end_date is None and BOT_D_REQUIRE_KNOWN_END_DATE:
            return "missing_end_date"
        if hours_to_end is not None:
            if hours_to_end <= 0:
                return "market_ended"
            if self.cfg.min_entry_hours_to_end > 0 and hours_to_end < self.cfg.min_entry_hours_to_end:
                return "too_close_to_end"
            if self.cfg.max_lockup_hours > 0 and hours_to_end > self.cfg.max_lockup_hours:
                return "lockup_too_long"
        if decision.forecast_fetched_at is None:
            return "missing_forecast_fetched_at"
        fetched = (
            decision.forecast_fetched_at
            if decision.forecast_fetched_at.tzinfo
            else decision.forecast_fetched_at.replace(tzinfo=UTC)
        )
        age = (_utc_now() - fetched).total_seconds()
        if age > self.cfg.max_forecast_age_sec:
            return "stale_forecast"
        if BotDExecutor._numeric_blocker(decision) is not None:
            return "invalid_numeric"
        if self.has_open_order_or_position(decision.market.gamma_id):
            return "dedupe"
        if self.count_open() >= self.cfg.max_concurrent:
            return "max_concurrent"

        token_id, side, fair = _side_token_and_fair(decision)
        if fair <= 0 or fair >= 1:
            return "bad_fair"
        try:
            book = self.clob.get_book(token_id)
        except Exception as exc:
            return f"book_fetch_failed:{type(exc).__name__}"
        best_bid, best_ask = _best_bid_ask(book)
        if best_ask is None:
            return "no_best_ask"

        tick = self.cfg.assumed_tick
        get_tick = getattr(self.clob, "get_tick_size", None)
        if callable(get_tick):
            try:
                tick = Decimal(str(get_tick(token_id)))
            except Exception:
                tick = self.cfg.assumed_tick

        raw_quote = fair - self.cfg.quote_discount
        quote = raw_quote
        if best_bid is not None:
            quote = max(quote, best_bid + tick)
        quote = min(quote, best_ask - tick)
        quote = _q_price(quote)
        if quote >= best_ask:
            return "crossed_book_rejected"
        if quote <= 0:
            return "bad_quote"
        if fair - quote < self.cfg.min_maker_edge:
            return "maker_edge_too_small"

        expensive_no = BotDExecutor._expensive_no_guard_reason(decision, limit_price=quote)
        if expensive_no is not None:
            return expensive_no
        no_inside = BotDExecutor._buy_no_bucket_contradiction_reason(decision)
        if no_inside is not None:
            return no_inside
        premium = BotDExecutor._no_premium_hard_skip_reason(decision, limit_price=quote)
        if premium is not None:
            return premium

        min_notional, max_notional = _notional_bounds(
            quote,
            self.cfg,
            decision=decision,
            hours_to_end=hours_to_end,
        )
        shares = _target_shares(
            quote,
            self.cfg,
            min_notional_usd=min_notional,
            max_order_usd=max_notional,
        )
        notional = (shares * quote).quantize(Decimal("0.01"))
        if notional < min_notional:
            return "maker_below_min_notional"
        if notional > max_notional:
            return "maker_order_cap"
        if self.open_exposure() + notional > self.cfg.max_open_exposure_usd:
            return "maker_open_exposure_cap"
        if self.daily_gross() + notional > self.cfg.max_daily_gross_usd:
            return "maker_daily_gross_cap"
        if self.open_exposure() + notional > self.cfg.wallet_usd:
            return "maker_wallet_cap"
        fleet = check_fleet_exposure(BOT_ID, notional)
        if not fleet.ok:
            return fleet.reason

        return MakerQuote(
            decision=decision,
            token_id=token_id,
            side=side,
            fair_price=fair.quantize(Decimal("0.001")),
            quote_price=quote,
            shares=shares,
            notional_usd=notional,
            best_bid=best_bid,
            best_ask=best_ask,
            hours_to_end=hours_to_end,
            min_notional_usd=min_notional,
            max_notional_usd=max_notional,
        )

    def place_quote(self, quote: MakerQuote) -> OrderResponse:
        blocker = self._paper_or_unauthorized_reason()
        if blocker is not None:
            raise RuntimeError(blocker)
        response = self.clob.place_limit(
            quote.token_id,
            quote.quote_price,
            quote.shares,
            quote.side,
            OrderType.GTC,
        )
        if not response.order_id:
            raise RuntimeError(f"maker_empty_order_id:{response.status}")
        now = _utc_now()
        with self.session_factory() as s:
            s.add(Order(
                order_id=response.order_id,
                bot_id=BOT_ID,
                condition_id=quote.decision.market.gamma_id,
                token_id=quote.token_id,
                side=quote.side.value,
                price=quote.quote_price,
                size=quote.shares,
                status=response.status or "live",
                order_type="GTC",
                placed_at=now,
                last_updated=now,
            ))
            s.add(Event(
                bot_id=BOT_ID,
                event_type="bot_d_maker.quote_placed",
                severity="info",
                message=f"maker quote placed {response.order_id}",
                payload={
                    "order_id": response.order_id,
                    "condition_id": quote.decision.market.gamma_id,
                    "city": quote.decision.market.city,
                    "date": quote.decision.market.date,
                    "side": quote.decision.side,
                    "token_id": quote.token_id,
                    "fair_price": str(quote.fair_price),
                    "quote_price": str(quote.quote_price),
                    "shares": str(quote.shares),
                    "notional_usd": str(quote.notional_usd),
                    "hours_to_end": quote.hours_to_end,
                    "min_notional_usd": str(quote.min_notional_usd)
                    if quote.min_notional_usd is not None
                    else None,
                    "max_notional_usd": str(quote.max_notional_usd)
                    if quote.max_notional_usd is not None
                    else None,
                    "best_bid": str(quote.best_bid) if quote.best_bid is not None else None,
                    "best_ask": str(quote.best_ask) if quote.best_ask is not None else None,
                    "net_edge": quote.decision.net_edge,
                    "forecast_source": quote.decision.forecast_source,
                },
            ))
            s.commit()
        return response

    def scan_once(self) -> tuple[int, int, int]:
        self._sync_open_orders()
        fills = self.portfolio.reconcile_live_fills(
            self.clob,
            BOT_ID,
            require_known_order=True,
        )
        if fills:
            log.info("bot_d_maker.fills_reconciled=%d", fills)
        self.cancel_stale_quotes()
        halted = self.halt_reason()
        if halted is not None:
            self._emit(
                "bot_d_maker.scan_summary",
                f"maker scan halted: {halted}",
                severity="warn",
                payload={
                    "halt_reason": halted,
                    "tradeable": 0,
                    "placed": 0,
                    "open_exposure_usd": str(self.open_exposure()),
                    "daily_gross_usd": str(self.daily_gross()),
                },
            )
            return 0, 0, 0

        markets = fetch_weather_markets()
        raw = len(markets)
        markets = _candidate_markets(markets, self.cfg)
        if not markets:
            self._emit(
                "bot_d_maker.scan_summary",
                "maker scan no eligible markets",
                payload={"raw_markets": raw, "kept_markets": 0, "tradeable": 0, "placed": 0},
            )
            return raw, 0, 0

        target_dates_by_city: dict[str, list[str]] = {}
        for m in markets:
            target_dates_by_city.setdefault(m.city, []).append(m.date)
        forecasts = get_forecasts(
            cities=list(target_dates_by_city),
            target_dates_by_city=target_dates_by_city,
        )
        decisions: list[WeatherEdgeDecision] = []
        missing = 0
        for market in markets:
            forecast = forecasts.get(market.city, {}).get(market.date)
            if forecast is None:
                missing += 1
                continue
            decisions.append(evaluate_weather_market(market, forecast, edge_threshold=BOT_D_EDGE_THRESHOLD))
        tradeable = apply_wave_regime_sizing(apply_one_bet_per_event(decisions))
        placed = 0
        skipped: dict[str, int] = {}
        for decision in tradeable:
            quote_or_reason = self.quote_for_decision(decision)
            if isinstance(quote_or_reason, str):
                skipped[quote_or_reason] = skipped.get(quote_or_reason, 0) + 1
                continue
            try:
                self.place_quote(quote_or_reason)
                placed += 1
            except Exception as exc:
                reason = f"place_failed:{type(exc).__name__}"
                skipped[reason] = skipped.get(reason, 0) + 1
                self._emit(
                    "bot_d_maker.quote_failed",
                    reason,
                    severity="warn",
                    payload={"error": str(exc)[:200], "condition_id": quote_or_reason.decision.market.gamma_id},
                )
        self._emit(
            "bot_d_maker.scan_summary",
            "maker scan complete",
            payload={
                "raw_markets": raw,
                "kept_markets": len(markets),
                "evaluated": len(decisions),
                "missing_forecasts": missing,
                "tradeable": len(tradeable),
                "placed": placed,
                "skipped": skipped,
                "open_exposure_usd": str(self.open_exposure()),
                "daily_gross_usd": str(self.daily_gross()),
            },
        )
        return raw, len(tradeable), placed


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="bots.bot_d_weather.maker_live")
    p.add_argument("--scan-interval-s", type=float, default=float(_env("BOT_D_MAKER_SCAN_INTERVAL_S", "300")))
    p.add_argument("--log-level", default="INFO")
    p.add_argument("--once", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    init_db()

    from core.clob_v2 import ClobWrapperV2
    from core.config import get_settings
    from core.keystore import Keystore

    if os.environ.get("POLYMARKET_ENV", "").lower() != "live":
        raise RuntimeError("Bot D maker live requires POLYMARKET_ENV=live")
    if os.environ.get("BOT_D_MAKER_ENV", "").lower() != "live":
        raise RuntimeError("Bot D maker live requires BOT_D_MAKER_ENV=live")

    keystore = Keystore.load_from_settings(get_settings())
    clob = ClobWrapperV2(keystore=keystore, paper_override=False)
    clob.load_preflight_from_db()
    runner = BotDMakerLive(clob=clob)
    log.info("bot_d_maker starting bot_id=%s scan_interval=%s", BOT_ID, args.scan_interval_s)
    while True:
        try:
            raw, tradeable, placed = runner.scan_once()
            log.info("bot_d_maker.cycle raw=%d tradeable=%d placed=%d", raw, tradeable, placed)
        except Exception as exc:
            log.exception("bot_d_maker.cycle_failed: %s", exc)
        if args.once:
            break
        sleep(args.scan_interval_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
