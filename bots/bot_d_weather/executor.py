"""Bot D executor — Kelly-sized orders from WeatherEdgeDecisions.

Same pattern as Bot C but with Kelly sizing (fractional Kelly at 15%,
matching little-rocky's proven config) and weather-specific parameters.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy import select as sa_select
from sqlalchemy.orm import sessionmaker

from bots.bot_d_weather.config import (
    BOT_D_ALLOW_NWS_FALLBACK_ENTRY,
    BOT_D_BANKROLL_USD,
    BOT_D_BLOCK_BUY_NO_MEAN_INSIDE_BUCKET,
    BOT_D_BOT_ID,
    BOT_D_DEPTH_GATE_ENABLED,
    BOT_D_ENTRY_HALT,
    BOT_D_EXIT_STALE_MIN,
    BOT_D_EXPENSIVE_NO_GUARD_ENABLED,
    BOT_D_EXPENSIVE_NO_GUARD_MIN_PRICE,
    BOT_D_EXPENSIVE_NO_MAX_API_GAP_F,
    BOT_D_EXPENSIVE_NO_MIN_API_AGREEMENT,
    BOT_D_EXPENSIVE_NO_MIN_DISTANCE_F,
    BOT_D_EXPENSIVE_NO_MIN_DISTANCE_STD_MULT,
    BOT_D_EXPENSIVE_NO_TIER_C_MIN_EDGE,
    BOT_D_KELLY_FRACTION,
    BOT_D_LIMIT_OFFSET,
    BOT_D_LIVE_APPROVED_AT,
    BOT_D_LIVE_AUTHORIZED,
    BOT_D_LIVE_EXIT_LIMIT_OFFSET,
    BOT_D_LIVE_FIXED_SHARES,
    BOT_D_LIVE_MAX_CONCURRENT_POSITIONS,
    BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD,
    BOT_D_LIVE_MAX_DYNAMIC_SHARES,
    BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD,
    BOT_D_LIVE_MAX_ORDER_USD,
    BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD,
    BOT_D_LIVE_NO_PREMIUM_HARD_SKIP,
    BOT_D_LIVE_NO_SHARES_HIGH,
    BOT_D_LIVE_NO_SHARES_MID,
    BOT_D_LIVE_NO_SHARES_VERY_HIGH,
    BOT_D_LIVE_PROBE_MODE,
    BOT_D_LIVE_SIZING_MODE,
    BOT_D_MAX_CONCURRENT_POSITIONS,
    BOT_D_MAX_LOCKUP_HOURS,
    BOT_D_MIN_ENTRY_DEPTH_USD,
    BOT_D_MIN_ENTRY_HOURS_TO_END,
    BOT_D_MIN_VOLUME_24H_USD,
    BOT_D_PAPER_EXIT_SLIPPAGE_BPS,
    BOT_D_PER_TRADE_USD,
    BOT_D_POSITION_AUTO_SELL_ENABLED,
    BOT_D_POSITION_PRICE_ONLY_STOP_ENABLED,
    BOT_D_POSITION_RAW_WARN_DISTANCE_F,
    BOT_D_POSITION_STOP_LOSS_PCT,
    BOT_D_POSITION_VALIDATION_ENABLED,
    BOT_D_REQUIRE_KNOWN_END_DATE,
    BOT_D_REQUIRE_VERIFIED_SETTLEMENT,
    BOT_D_TAIL_CAP_END,
    BOT_D_TAIL_CAP_FLOOR,
    BOT_D_TAIL_CAP_START,
    BOT_D_TAKE_PROFIT_ENABLED,
    BOT_D_TAKE_PROFIT_LIMIT_OFFSET,
    BOT_D_TAKE_PROFIT_MIN_BID,
    BOT_D_TAKE_PROFIT_MIN_HOURS_TO_END,
    SETTLEMENT_SPECS,
)
from bots.bot_d_weather.labels import setup_tier
from bots.bot_d_weather.strategy import WeatherEdgeDecision
from core.clob import OrderBook
from core.clob_v2 import ClobWrapperV2 as ClobWrapper
from core.clob_v2 import OrderType, Side
from core.config import get_settings
from core.db import (
    Book,
    Event,
    HaltFlag,
    Order,
    Position,
    Trade,
    get_session_factory,
    upsert_market_minimal,
)
from core.fees import taker_fee_per_share
from core.portfolio import Portfolio

log = logging.getLogger(__name__)
BOT_ID = BOT_D_BOT_ID
MIN_POLYMARKET_SHARES = Decimal("5")
EXCHANGE_MARKETABLE_BUY_MIN_NOTIONAL_USD = Decimal("1.00")
OPEN_ORDER_STATUSES = ("OPEN", "PARTIAL", "PAPER_OPEN", "live", "MATCHED")


def _tail_scaled_cap(p_market: float, base_cap: Decimal) -> Decimal:
    """Shrink the per-trade cap on tail markets (Session 17l, 2026-04-21).

    Bot D's first $1,405 of realised paper profit came almost entirely
    from one 2.8¢ Lagos weather market resolving YES — $50 stake returned
    $1,785 (+$1,735 in a single trade). The base per-trade cap limits
    STAKE, but not the resulting MAX PAYOFF which scales with 1/p_market.

    This helper tightens the cap further on tail markets:
        p_market >= end    ->  base_cap                  (no reduction)
        p_market <= start  ->  base_cap * floor
        start < p < end    ->  linear interp

    Defaults are floor=0.60, start=0.05, end=0.20, so a 2.8¢ market with
    base_cap $50 sizes at $30. This keeps tail risk bounded while no longer
    suppressing the 2-5¢ subtype to 30% of normal size.
    """
    p = Decimal(str(p_market))
    floor = BOT_D_TAIL_CAP_FLOOR
    start = BOT_D_TAIL_CAP_START
    end = BOT_D_TAIL_CAP_END
    # Guard against misconfiguration that would make the interp degenerate
    # or negative-slope; fall back to fullsize.
    if end <= start:
        return base_cap
    if p >= end:
        return base_cap
    if p <= start:
        return (base_cap * floor).quantize(Decimal("0.01"))
    factor = floor + (p - start) * (Decimal("1.00") - floor) / (end - start)
    return (base_cap * factor).quantize(Decimal("0.01"))


def _kelly_size(
    p_model: float, p_market: float,
    bankroll: Decimal, kelly_fraction: float,
    max_per_trade: Decimal,
) -> Decimal:
    """Fractional Kelly for binary outcome. Capped by per-trade max.

    Refuses to size when bankroll is non-positive or less than the per-trade
    floor (prevents division-by-zero downstream and catches misconfigured
    env vars like BOT_D_BANKROLL_USD=0).

    Per-trade cap is further scaled down on tail markets by
    ``_tail_scaled_cap`` to limit single-market payoff concentration.
    """
    if bankroll <= Decimal("0") or bankroll < Decimal("10"):
        log.warning(
            "bot_d.kelly.bad_bankroll",
            extra={"bankroll": str(bankroll), "reason": "bankroll_too_low"},
        )
        return Decimal("0")
    if p_market <= 0.01 or p_market >= 0.99 or p_model <= 0:
        return Decimal("0")
    b = (1.0 - p_market) / p_market  # net odds
    q = 1.0 - p_model
    f_star = (p_model * b - q) / b if b > 0 else 0.0
    f_frac = max(0.0, f_star) * kelly_fraction
    size = Decimal(str(f_frac)) * bankroll
    effective_cap = _tail_scaled_cap(p_market, max_per_trade)
    if effective_cap < max_per_trade:
        log.info(
            "bot_d.tail_cap_applied p_market=%s base_cap=%s effective_cap=%s factor=%s",
            p_market,
            max_per_trade,
            effective_cap,
            (effective_cap / max_per_trade).quantize(Decimal("0.0001")),
        )
    size = min(size, effective_cap)
    return max(Decimal("0"), size.quantize(Decimal("0.01")))


def _round_share_size(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_UP)


def _ceil_min_notional_shares(price: Decimal) -> Decimal:
    return _ceil_notional_shares(price, BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD)


def _ceil_notional_shares(price: Decimal, notional_usd: Decimal) -> Decimal:
    if price <= 0 or notional_usd <= 0:
        return MIN_POLYMARKET_SHARES
    return _round_share_size(notional_usd / price)


def _finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


@dataclass
class DEntryDecision:
    placed: bool
    reason: str
    order_id: str | None = None
    condition_id: str | None = None
    token_id: str | None = None
    limit_price: Decimal | None = None
    size_shares: Decimal | None = None
    size_usd: Decimal | None = None
    depth_usd: Decimal | None = None
    required_depth_usd: Decimal | None = None


@dataclass(frozen=True)
class DPositionValidation:
    position_id: int | None
    condition_id: str
    action: str
    reason: str
    token_id: str
    side: str
    size: Decimal
    avg_price: Decimal | None
    best_bid: Decimal | None
    best_ask: Decimal | None
    mark_value_usd: Decimal | None
    cost_basis_usd: Decimal | None
    mtm_pnl_usd: Decimal | None
    mtm_loss_pct: Decimal | None
    hours_to_end: float | None
    edge_for_side: float | None
    bucket_state: str | None
    station_metric_f: float | None
    distance_to_bucket_f: float | None
    has_pending_exit_order: bool
    auto_sell_enabled: bool


class BotDExecutor:
    def __init__(
        self,
        clob: ClobWrapper,
        main_session_factory: sessionmaker | None = None,
    ) -> None:
        self.clob = clob
        self._sessions = main_session_factory or get_session_factory()

    def is_halted(self) -> bool:
        with self._sessions() as s:
            flag = s.scalar(select(HaltFlag).where(HaltFlag.bot_id == BOT_ID))
        return bool(flag and flag.halted)

    def has_open_order(self, condition_id: str) -> bool:
        with self._sessions() as s:
            n = s.scalar(
                select(func.count()).select_from(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.condition_id == condition_id,
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            )
        return (n or 0) > 0

    def has_position(self, condition_id: str) -> bool:
        with self._sessions() as s:
            n = s.scalar(
                select(func.count()).select_from(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.condition_id == condition_id,
                    Position.status == "OPEN",
                )
            )
        return (n or 0) > 0

    def _is_paper_mode(self) -> bool:
        effective_paper = getattr(self.clob, "_effective_paper", None)
        if callable(effective_paper):
            try:
                return bool(effective_paper())
            except Exception:
                pass
        paper_override = getattr(self.clob, "paper_override", None)
        if isinstance(paper_override, bool):
            return paper_override or not get_settings().is_live()
        return not get_settings().is_live()

    def _open_position_for_condition(self, condition_id: str) -> Position | None:
        with self._sessions() as s:
            return s.execute(
                sa_select(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.condition_id == condition_id,
                    Position.status == "OPEN",
                )
            ).scalars().first()

    def _has_pending_exit_order(self, token_id: str) -> bool:
        with self._sessions() as s:
            n = s.scalar(
                select(func.count()).select_from(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.token_id == token_id,
                    Order.side == "SELL",
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            )
        return (n or 0) > 0

    def _live_readiness_blocker(self) -> str | None:
        """Return a live-entry blocker when this process would hit real CLOB."""
        if self._is_paper_mode():
            return None
        if not BOT_D_LIVE_AUTHORIZED:
            return "live_not_authorized"
        if BOT_D_LIVE_PROBE_MODE == "plumbing":
            if BOT_ID != "bot_d_live_probe":
                return "live_probe_requires_separate_bot_id"
            if not BOT_D_LIVE_APPROVED_AT:
                return "live_probe_missing_approved_at"
            since = datetime.now(UTC) - timedelta(minutes=60)
            with self._sessions() as s:
                recent_skew_fallback = s.scalar(
                    select(func.count()).select_from(Event).where(
                        Event.bot_id == BOT_ID,
                        Event.event_type == "bot_d.skewnorm_fallback",
                        Event.created_at >= since,
                    )
                )
            if recent_skew_fallback:
                return "skewnorm_fallback_recent"
            return None
        try:
            from scripts.bot_d_readiness_report import build_report
            report = build_report(get_settings().polymarket_db_path)
        except Exception as exc:
            log.error("bot_d.live_readiness_check_failed err=%s", exc)
            return "live_readiness_unavailable"
        readiness = report.get("readiness") or {}
        if not readiness.get("live_ready"):
            blockers = readiness.get("blockers") or []
            suffix = ",".join(str(b) for b in blockers[:5]) or "report_not_ready"
            return f"live_readiness_blocked:{suffix}"
        return None

    def _emit_exit_event(
        self,
        *,
        event_type: str,
        severity: str,
        message: str,
        payload: dict,
    ) -> None:
        with self._sessions() as s:
            s.add(Event(
                bot_id=BOT_ID,
                event_type=event_type,
                severity=severity,
                message=message,
                payload=payload,
            ))
            s.commit()

    @staticmethod
    def _book_depth_usd(book: OrderBook, limit_price: Decimal) -> Decimal:
        """Return executable BUY notional available at or below limit."""
        depth = Decimal("0")
        for price, size in book.asks:
            if price <= limit_price:
                depth += price * size
        return depth.quantize(Decimal("0.0001"))

    def _capture_book_snapshot(
        self,
        token_id: str,
        *,
        order_id: str | None = None,
        book: OrderBook | None = None,
    ) -> OrderBook | None:
        """Best-effort book capture so Bot D paper fills are measurable."""
        try:
            if book is None:
                book = self.clob.get_book(token_id)
            return book
        except Exception as exc:
            log.debug(
                "bot_d.book_fetch_failed token=%s order=%s err=%s",
                token_id[:12],
                order_id,
                exc,
            )
            return None
        finally:
            if book is not None:
                try:
                    snapshot_at = datetime.fromtimestamp(float(book.timestamp), tz=UTC)

                    def rows(levels):
                        return [[str(price), str(size)] for price, size in levels]

                    with self._sessions() as s:
                        s.add(Book(
                            token_id=book.token_id,
                            snapshot_at=snapshot_at,
                            bids=rows(book.bids),
                            asks=rows(book.asks),
                        ))
                        s.commit()
                    log.debug("bot_d.book_snapshot token=%s order=%s", token_id[:12], order_id)
                except Exception as exc:
                    log.debug(
                        "bot_d.book_snapshot_persist_failed token=%s order=%s err=%s",
                        token_id[:12],
                        order_id,
                        exc,
                    )

    @staticmethod
    def _best_bid(book: OrderBook | None) -> Decimal | None:
        if book is None or not book.bids:
            return None
        return max(price for price, _size in book.bids)

    @staticmethod
    def _best_ask(book: OrderBook | None) -> Decimal | None:
        if book is None or not book.asks:
            return None
        return min(price for price, _size in book.asks)

    @staticmethod
    def _clamp_price(price: Decimal) -> Decimal:
        return max(Decimal("0.001"), min(Decimal("0.999"), price))

    def _exit_book_and_bid(self, token_id: str) -> tuple[OrderBook | None, Decimal | None]:
        book = self._capture_book_snapshot(token_id)
        return book, self._best_bid(book)

    def _paper_exit_fill_price(
        self,
        *,
        token_id: str,
        fallback_exit_px: Decimal,
    ) -> Decimal:
        _book, best_bid = self._exit_book_and_bid(token_id)
        px = best_bid if best_bid is not None else fallback_exit_px
        if BOT_D_PAPER_EXIT_SLIPPAGE_BPS > 0:
            haircut = Decimal("1") - (BOT_D_PAPER_EXIT_SLIPPAGE_BPS / Decimal("10000"))
            px *= haircut
        return self._clamp_price(px).quantize(Decimal("0.001"))

    def _live_exit_limit_price(
        self,
        *,
        token_id: str,
        fallback_exit_px: Decimal,
        offset: Decimal | None = None,
    ) -> Decimal:
        _book, best_bid = self._exit_book_and_bid(token_id)
        basis = best_bid if best_bid is not None else fallback_exit_px
        live_offset = BOT_D_LIVE_EXIT_LIMIT_OFFSET if offset is None else offset
        return self._clamp_price(basis - live_offset).quantize(
            Decimal("0.001")
        )

    def _exit_position(
        self,
        *,
        pos: Position,
        dec: WeatherEdgeDecision | None,
        exit_px: Decimal,
        reason: str,
        source: str,
        now: datetime,
    ) -> bool:
        """Paper closes locally; live submits a real SELL and waits for fill."""
        if self._is_paper_mode():
            fill_px = self._paper_exit_fill_price(
                token_id=pos.token_id,
                fallback_exit_px=exit_px,
            )
            fee_usd = (taker_fee_per_share(fill_px, "weather") * pos.size).quantize(
                Decimal("0.00000001")
            )
            Portfolio(self._sessions).on_fill(
                bot_id=BOT_ID,
                trade_id=f"bot_d-{source}-exit-{pos.id}-{int(now.timestamp())}",
                order_id=None,
                condition_id=pos.condition_id,
                token_id=pos.token_id,
                side="SELL",
                price=fill_px,
                size=pos.size,
                fee_usd=fee_usd,
                filled_at=now,
            )
            log.info(
                "bot_d.position_exit.paper_closed pos_id=%s cid=%s size=%s "
                "exit_px=%s fee_usd=%s reason=%s",
                pos.id, pos.condition_id, pos.size, fill_px, fee_usd, reason,
            )
            return True

        if self._has_pending_exit_order(pos.token_id):
            log.info(
                "bot_d.position_exit.live_pending_exists pos_id=%s token=%s reason=%s",
                pos.id, pos.token_id, reason,
            )
            return False

        if pos.size < MIN_POLYMARKET_SHARES:
            self._emit_exit_event(
                event_type="bot_d.live_exit.blocked_below_min_size",
                severity="warn",
                message=f"live exit blocked below min size pos={pos.id}",
                payload={
                    "position_id": pos.id,
                    "condition_id": pos.condition_id,
                    "token_id": pos.token_id,
                    "size": str(pos.size),
                    "exit_px": str(exit_px),
                    "reason": reason,
                },
            )
            return False

        limit = self._live_exit_limit_price(
            token_id=pos.token_id,
            fallback_exit_px=exit_px,
            offset=(
                BOT_D_TAKE_PROFIT_LIMIT_OFFSET
                if source == "take_profit"
                else BOT_D_LIVE_EXIT_LIMIT_OFFSET
            ),
        )
        try:
            resp = self.clob.place_limit(
                token_id=pos.token_id,
                price=limit,
                size=pos.size,
                side=Side.SELL,
                order_type=OrderType.GTC,
            )
        except Exception as exc:
            log.warning(
                "bot_d.position_exit.live_order_failed pos_id=%s cid=%s: %s",
                pos.id, pos.condition_id, exc,
            )
            self._emit_exit_event(
                event_type="bot_d.live_exit.order_failed",
                severity="warn",
                message=f"live exit order failed pos={pos.id}",
                payload={
                    "position_id": pos.id,
                    "condition_id": pos.condition_id,
                    "token_id": pos.token_id,
                    "size": str(pos.size),
                    "limit": str(limit),
                    "reason": reason,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            return False

        if not resp.order_id or resp.status == "SKIPPED_MIN_SIZE":
            self._emit_exit_event(
                event_type="bot_d.live_exit.order_skipped",
                severity="warn",
                message=f"live exit order skipped pos={pos.id} status={resp.status}",
                payload={
                    "position_id": pos.id,
                    "condition_id": pos.condition_id,
                    "token_id": pos.token_id,
                    "size": str(pos.size),
                    "limit": str(limit),
                    "reason": reason,
                    "status": resp.status,
                    "raw": resp.raw,
                },
            )
            return False

        with self._sessions() as s:
            s.add(Order(
                order_id=resp.order_id,
                bot_id=BOT_ID,
                condition_id=pos.condition_id,
                token_id=pos.token_id,
                side="SELL",
                price=limit,
                size=pos.size,
                status=resp.status or "OPEN",
                order_type="GTC",
            ))
            s.add(Event(
                bot_id=BOT_ID,
                event_type="bot_d.live_exit.order_placed",
                severity="warn",
                message=f"live exit SELL placed pos={pos.id} order={resp.order_id}",
                payload={
                    "position_id": pos.id,
                    "condition_id": pos.condition_id,
                    "token_id": pos.token_id,
                    "size": str(pos.size),
                    "limit": str(limit),
                    "exit_px": str(exit_px),
                    "reason": reason,
                    "source": source,
                    "status": resp.status,
                },
            ))
            s.commit()
        log.warning(
            "bot_d.position_exit.live_sell_placed pos_id=%s order=%s cid=%s size=%s limit=%s reason=%s",
            pos.id, resp.order_id, pos.condition_id, pos.size, limit, reason,
        )
        return True

    def _take_profit_exit_reason(
        self,
        *,
        pos: Position,
        dec: WeatherEdgeDecision | None,
        now: datetime,
    ) -> tuple[str, Decimal] | None:
        """Return (reason, best_bid) when an open position should be banked."""
        if not BOT_D_TAKE_PROFIT_ENABLED:
            return None
        if (
            BOT_D_TAKE_PROFIT_MIN_HOURS_TO_END > 0
            and dec is not None
            and dec.market.end_date is not None
        ):
            end_date = dec.market.end_date
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=UTC)
            hours_to_end = (end_date - now).total_seconds() / 3600
            if hours_to_end < BOT_D_TAKE_PROFIT_MIN_HOURS_TO_END:
                return None
        _book, best_bid = self._exit_book_and_bid(pos.token_id)
        if best_bid is None or best_bid < BOT_D_TAKE_PROFIT_MIN_BID:
            return None
        return (
            f"take_profit bid={best_bid}>={BOT_D_TAKE_PROFIT_MIN_BID}",
            best_bid,
        )

    def _latest_source_snapshot_payload(self, condition_id: str) -> dict | None:
        with self._sessions() as s:
            events = list(
                s.execute(
                    sa_select(Event).where(
                        Event.bot_id == BOT_ID,
                        Event.event_type == "bot_d.source_snapshot",
                    ).order_by(Event.created_at.desc()).limit(1000)
                ).scalars().all()
            )
        for event in events:
            payload = event.payload if isinstance(event.payload, dict) else {}
            if str(payload.get("condition_id") or "") == condition_id:
                return payload
        return None

    @staticmethod
    def _hours_to_end_from(dec: WeatherEdgeDecision | None, source_payload: dict | None, now: datetime) -> float | None:
        end_date: datetime | None = None
        if dec is not None and getattr(dec.market, "end_date", None) is not None:
            end_date = dec.market.end_date
        elif source_payload and source_payload.get("end_date"):
            try:
                end_date = datetime.fromisoformat(str(source_payload["end_date"]).replace("Z", "+00:00"))
            except ValueError:
                end_date = None
        if end_date is None:
            return None
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=UTC)
        return round((end_date - now).total_seconds() / 3600, 3)

    @staticmethod
    def _edge_for_position_side(pos: Position, dec: WeatherEdgeDecision | None) -> float | None:
        if dec is None:
            return None
        pos_is_yes = pos.token_id == dec.market.yes_token_id or str(pos.side).upper() == "YES"
        return float(dec.net_edge) if pos_is_yes else -float(dec.net_edge)

    @staticmethod
    def _raw_position_signal(pos: Position, source_payload: dict | None) -> tuple[str | None, str | None]:
        if not source_payload:
            return None, None
        state = str(source_payload.get("bucket_state") or "")
        if not state:
            return None, None
        pos_side = str(pos.side or "").upper()
        distance = source_payload.get("distance_to_bucket_f")
        try:
            distance_f = float(distance) if distance is not None else None
        except (TypeError, ValueError):
            distance_f = None

        if pos_side == "NO":
            if state in {"locked_yes", "already_yes"}:
                return "SELL_NOW", f"raw_station_against_no:{state}"
            if state == "pending" and distance_f == 0.0:
                return "SELL_RECOMMENDED", "raw_station_inside_yes_bucket_against_no"
            if state == "pending" and distance_f is not None and distance_f <= BOT_D_POSITION_RAW_WARN_DISTANCE_F:
                return "WATCH", f"raw_station_near_yes_bucket distance_f={distance_f:.3f}"
        else:
            if state in {"locked_no", "already_no"}:
                return "SELL_NOW", f"raw_station_against_yes:{state}"
        return None, None

    @staticmethod
    def _ranked_action(current: str, candidate: str) -> str:
        ranks = {"HOLD": 0, "WATCH": 1, "SELL_RECOMMENDED": 2, "SELL_NOW": 3}
        return candidate if ranks.get(candidate, 0) > ranks.get(current, 0) else current

    def validate_open_position(
        self,
        pos: Position,
        *,
        dec: WeatherEdgeDecision | None,
        now: datetime,
    ) -> DPositionValidation:
        book = self._capture_book_snapshot(pos.token_id)
        best_bid = self._best_bid(book)
        best_ask = self._best_ask(book)
        cost_basis = Decimal(str(pos.cost_basis_usd or 0))
        size = Decimal(str(pos.size or 0))
        avg_price = Decimal(str(pos.avg_price)) if pos.avg_price is not None else None
        mark_value = (best_bid * size).quantize(Decimal("0.0001")) if best_bid is not None else None
        mtm_pnl = (mark_value - cost_basis).quantize(Decimal("0.0001")) if mark_value is not None else None
        mtm_loss_pct = None
        if mtm_pnl is not None and cost_basis > 0 and mtm_pnl < 0:
            mtm_loss_pct = ((-mtm_pnl) / cost_basis).quantize(Decimal("0.0001"))

        source_payload = self._latest_source_snapshot_payload(pos.condition_id)
        edge_for_side = self._edge_for_position_side(pos, dec)
        hours_to_end = self._hours_to_end_from(dec, source_payload, now)
        raw_action, raw_reason = self._raw_position_signal(pos, source_payload)
        has_pending_exit = self._has_pending_exit_order(pos.token_id)

        action = "HOLD"
        reasons: list[str] = []
        if edge_for_side is not None:
            if edge_for_side < 0:
                action = self._ranked_action(action, "SELL_NOW")
                reasons.append(f"edge_flipped edge={edge_for_side:+.3f}")
            elif abs(edge_for_side) < 0.02:
                action = self._ranked_action(action, "SELL_RECOMMENDED")
                reasons.append(f"edge_decayed edge={edge_for_side:+.3f}")
        if raw_action is not None:
            action = self._ranked_action(action, raw_action)
            if raw_reason:
                reasons.append(raw_reason)
        if mtm_loss_pct is not None and mtm_loss_pct >= BOT_D_POSITION_STOP_LOSS_PCT:
            if raw_action in {"SELL_NOW", "SELL_RECOMMENDED"} or (edge_for_side is not None and edge_for_side < 0):
                action = self._ranked_action(action, "SELL_RECOMMENDED")
                reasons.append(f"stop_loss_with_invalidating_data loss_pct={mtm_loss_pct}")
            elif BOT_D_POSITION_PRICE_ONLY_STOP_ENABLED:
                action = self._ranked_action(action, "SELL_RECOMMENDED")
                reasons.append(f"price_only_stop_loss loss_pct={mtm_loss_pct}")
            else:
                action = self._ranked_action(action, "WATCH")
                reasons.append(f"stop_loss_watch_needs_data loss_pct={mtm_loss_pct}")
        if has_pending_exit:
            reasons.append("pending_exit_order_exists")

        source_payload = source_payload or {}
        return DPositionValidation(
            position_id=pos.id,
            condition_id=pos.condition_id,
            action=action,
            reason="; ".join(reasons) if reasons else "no_exit_signal",
            token_id=pos.token_id,
            side=str(pos.side or ""),
            size=size,
            avg_price=avg_price,
            best_bid=best_bid,
            best_ask=best_ask,
            mark_value_usd=mark_value,
            cost_basis_usd=cost_basis,
            mtm_pnl_usd=mtm_pnl,
            mtm_loss_pct=mtm_loss_pct,
            hours_to_end=hours_to_end,
            edge_for_side=edge_for_side,
            bucket_state=str(source_payload.get("bucket_state") or "") or None,
            station_metric_f=(
                float(source_payload["station_metric_f"])
                if source_payload.get("station_metric_f") is not None
                else None
            ),
            distance_to_bucket_f=(
                float(source_payload["distance_to_bucket_f"])
                if source_payload.get("distance_to_bucket_f") is not None
                else None
            ),
            has_pending_exit_order=has_pending_exit,
            auto_sell_enabled=BOT_D_POSITION_AUTO_SELL_ENABLED,
        )

    def _emit_position_validation(self, validation: DPositionValidation) -> None:
        payload = {
            "position_id": validation.position_id,
            "condition_id": validation.condition_id,
            "action": validation.action,
            "reason": validation.reason,
            "token_id": validation.token_id,
            "side": validation.side,
            "size": str(validation.size),
            "avg_price": str(validation.avg_price) if validation.avg_price is not None else None,
            "best_bid": str(validation.best_bid) if validation.best_bid is not None else None,
            "best_ask": str(validation.best_ask) if validation.best_ask is not None else None,
            "mark_value_usd": str(validation.mark_value_usd) if validation.mark_value_usd is not None else None,
            "cost_basis_usd": str(validation.cost_basis_usd) if validation.cost_basis_usd is not None else None,
            "mtm_pnl_usd": str(validation.mtm_pnl_usd) if validation.mtm_pnl_usd is not None else None,
            "mtm_loss_pct": str(validation.mtm_loss_pct) if validation.mtm_loss_pct is not None else None,
            "hours_to_end": validation.hours_to_end,
            "edge_for_side": validation.edge_for_side,
            "bucket_state": validation.bucket_state,
            "station_metric_f": validation.station_metric_f,
            "distance_to_bucket_f": validation.distance_to_bucket_f,
            "has_pending_exit_order": validation.has_pending_exit_order,
            "auto_sell_enabled": validation.auto_sell_enabled,
        }
        severity = "warn" if validation.action in {"SELL_RECOMMENDED", "SELL_NOW"} else "info"
        self._emit_exit_event(
            event_type="bot_d.position_validation",
            severity=severity,
            message=f"Bot D position validation {validation.action} pos={validation.position_id}",
            payload=payload,
        )

    def count_open(self) -> int:
        """Count open positions + pending orders (concurrency cap input).

        U-06 (audit 2026-04-18): after removing the Position dual-write at
        placement, count_open must also count orders that haven't yet filled
        — otherwise a placed-but-not-filled order lets the next iteration
        treat the slot as empty and re-enter. A condition_id can appear in
        EITHER Position (filled) OR Order (pending), never both for the same
        fill lifecycle; we union the distinct condition_ids across the two
        sources and return the count.
        """
        with self._sessions() as s:
            position_cids = set(s.scalars(
                select(Position.condition_id).where(
                    Position.bot_id == BOT_ID,
                    Position.status == "OPEN",
                )
            ).all())
            order_cids = set(s.scalars(
                select(Order.condition_id).where(
                    Order.bot_id == BOT_ID,
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            ).all())
        return len(position_cids | order_cids)

    def aggregate_exposure(self) -> Decimal:
        """Canonical cap input: open position cost basis + open-order notional.

        Uses Portfolio.get_total_exposure which correctly sums both sides:
          - open Position rows (filled orders that became positions)
          - open Order rows (OPEN/PARTIAL/PAPER_OPEN/live/MATCHED states)

        Prior version only counted orders in OPEN/PAPER_OPEN status, so
        once an order filled or CLOB set it to "live", it dropped out of
        the exposure cap and the bot kept adding more.
        """
        return Portfolio(self._sessions).get_total_exposure(BOT_ID)

    def _live_daily_gross_notional(self) -> Decimal:
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        with self._sessions() as s:
            rows = s.execute(
                sa_select(Order.price, Order.size).where(
                    Order.bot_id == BOT_ID,
                    Order.side.in_(("BUY", "SELL")),
                    Order.placed_at >= start,
                )
            ).all()
        total = sum(
            (Decimal(str(price or 0)) * Decimal(str(size or 0)) for price, size in rows),
            Decimal("0"),
        )
        return total.quantize(Decimal("0.0001"))

    def _sync_live_open_order_statuses(self) -> int:
        """Drop stale local open-order rows when CLOB says they are not open.

        CLOB fill reconciliation is trade-driven. If an order fills in multiple
        chunks or disappears from the book without a new trade, a local
        `live`/`PARTIAL` row can keep counting against Bot D's exposure cap.
        The exchange open-order list is the source of truth for resting orders.
        """
        if self._is_paper_mode():
            return 0
        try:
            exchange_open_ids = {
                o.order_id for o in (self.clob.get_user_orders() or []) if o.order_id
            }
        except Exception as exc:
            log.warning("bot_d.live_order_sync.fetch_failed: %s", exc)
            return 0

        now = datetime.now(UTC)
        updated = 0
        with self._sessions() as s:
            local_open = list(
                s.scalars(
                    sa_select(Order).where(
                        Order.bot_id == BOT_ID,
                        Order.side == "BUY",
                        Order.status.in_(OPEN_ORDER_STATUSES),
                    )
                )
            )
            for order in local_open:
                if order.order_id in exchange_open_ids:
                    continue
                filled = (
                    s.execute(
                        sa_select(func.coalesce(func.sum(Trade.size), 0)).where(
                            Trade.bot_id == BOT_ID,
                            Trade.order_id == order.order_id,
                        )
                    ).scalar()
                    or Decimal("0")
                )
                filled_dec = Decimal(str(filled))
                order_size = Decimal(str(order.size or 0))
                order.status = (
                    "FILLED"
                    if order_size > 0 and filled_dec >= order_size - Decimal("0.00000001")
                    else "CANCELLED"
                )
                order.last_updated = now
                updated += 1
            if updated:
                s.add(Event(
                    bot_id=BOT_ID,
                    event_type="bot_d.live_order_sync",
                    severity="info",
                    message=f"synced {updated} stale local live order statuses",
                    payload={
                        "updated": updated,
                        "exchange_open_orders": len(exchange_open_ids),
                    },
                ))
                s.commit()
        if updated:
            log.info("bot_d.live_order_sync updated=%d exchange_open=%d", updated, len(exchange_open_ids))
        return updated

    def _live_cap_blocker(self, intended_usd: Decimal) -> str | None:
        if self._is_paper_mode():
            return None
        if (
            Decimal("0") < BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD
            and intended_usd < BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD
        ):
            return "live_below_min_notional"
        if intended_usd > BOT_D_LIVE_MAX_ORDER_USD:
            return "live_order_notional_cap"
        if self.aggregate_exposure() + intended_usd > BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD:
            return "live_open_exposure_cap"
        if self._live_daily_gross_notional() + intended_usd > BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD:
            return "live_daily_gross_cap"
        return None

    @staticmethod
    def _live_setup_tier(decision: WeatherEdgeDecision) -> str:
        spec = SETTLEMENT_SPECS.get(decision.market.city)
        payload = {
            "_event_type": "bot_d.forecast_entry",
            "net_edge": decision.net_edge,
            "forecast_source": decision.forecast_source,
            "settlement_verified": bool(spec and spec.verified),
        }
        try:
            tier, _ = setup_tier(payload)
        except Exception as exc:
            log.debug("bot_d.live_sizing.tier_failed err=%s", exc)
            return "unknown"
        return tier

    @staticmethod
    def _numeric_blocker(decision: WeatherEdgeDecision) -> str | None:
        checks: dict[str, object] = {
            "gfs_probability": decision.gfs_probability,
            "market_probability": decision.market_probability,
            "gross_edge": decision.gross_edge,
            "net_edge": decision.net_edge,
            "edge": decision.edge,
            "forecast_mean_f": decision.forecast_mean_f,
            "forecast_std_f": decision.forecast_std_f,
        }
        if decision.market.yes_price is not None:
            checks["market_yes_price"] = decision.market.yes_price
        if getattr(decision, "api_agreement_max_gap_f", None) is not None:
            checks["api_agreement_max_gap_f"] = decision.api_agreement_max_gap_f
        if getattr(decision, "size_multiplier", None) is not None:
            checks["size_multiplier"] = decision.size_multiplier

        for name, value in checks.items():
            if not _finite_number(value):
                return f"invalid_numeric:{name}"
        if float(decision.forecast_std_f) <= 0:
            return "invalid_numeric:forecast_std_f"
        if not 0.0 <= float(decision.gfs_probability) <= 1.0:
            return "invalid_numeric:gfs_probability"
        if not 0.0 <= float(decision.market_probability) <= 1.0:
            return "invalid_numeric:market_probability"
        if decision.market.yes_price is not None and not Decimal("0") < Decimal(str(decision.market.yes_price)) < Decimal("1"):
            return "invalid_numeric:market_yes_price"
        return None

    def _live_size_shares(
        self,
        decision: WeatherEdgeDecision,
        *,
        limit_price: Decimal,
    ) -> Decimal:
        if BOT_D_LIVE_SIZING_MODE != "evidence_gated":
            return BOT_D_LIVE_FIXED_SHARES.quantize(Decimal("0.01"))

        city = decision.market.city
        source = (decision.forecast_source or "unknown").lower()
        tier = self._live_setup_tier(decision)
        scaled = (
            tier == "B"
            and source in {"noaa_nbm", "multi_model"}
            and city not in {"Seattle", "Denver"}
        )
        cheap_yes_collection = (
            decision.side == "BUY_YES"
            and limit_price < Decimal("0.10")
            and source in {"noaa_nbm", "multi_model"}
            and int(getattr(decision, "api_agreement_count", 0) or 0) >= 2
        )

        fixed_shares = (
            BOT_D_LIVE_FIXED_SHARES
            if BOT_D_LIVE_FIXED_SHARES > 0
            else MIN_POLYMARKET_SHARES
        )

        # ADR-160 premium-tier NO sizing ladder. BUY_NO entries shrink as the
        # limit price climbs because loss-on-miss is the full stake. The base
        # `<0.60` tier reuses `BOT_D_LIVE_FIXED_SHARES`; the `>=0.95` hard
        # skip is enforced earlier in `try_enter` via
        # `_no_premium_hard_skip_reason`. The exchange-side
        # `MIN_POLYMARKET_SHARES` floor still applies via the final clamp.
        no_ladder = (
            decision.side == "BUY_NO" and BOT_D_LIVE_SIZING_MODE == "evidence_gated"
        )

        if cheap_yes_collection:
            target = Decimal("20")
        elif no_ladder:
            if limit_price < Decimal("0.60"):
                target = fixed_shares
            elif limit_price < Decimal("0.75"):
                target = BOT_D_LIVE_NO_SHARES_MID
            elif limit_price < Decimal("0.85"):
                target = BOT_D_LIVE_NO_SHARES_HIGH
            else:
                target = BOT_D_LIVE_NO_SHARES_VERY_HIGH
        elif not scaled:
            target = fixed_shares
        elif limit_price < Decimal("0.10"):
            target = Decimal("30")
        elif limit_price < Decimal("0.20"):
            target = Decimal("20")
        elif limit_price < Decimal("0.50"):
            target = fixed_shares
        else:
            target = Decimal("10")

        if scaled and limit_price < Decimal("0.20"):
            target = max(target, _ceil_min_notional_shares(limit_price))
        if cheap_yes_collection:
            target = max(target, _ceil_notional_shares(limit_price, Decimal("1.00")))

        target = min(target, BOT_D_LIVE_MAX_DYNAMIC_SHARES)
        target = max(target, MIN_POLYMARKET_SHARES)
        return target.quantize(Decimal("0.01"))

    @staticmethod
    def _distance_from_bucket_f(decision: WeatherEdgeDecision) -> float:
        market = decision.market
        mean = float(decision.forecast_mean_f)
        low = market.range_low_f
        high = market.range_high_f
        if low is not None and high is not None:
            if low <= mean <= high:
                return 0.0
            if mean < low:
                return float(low - mean)
            return float(mean - high)
        if low is not None:
            return abs(mean - float(low))
        if high is not None:
            return abs(mean - float(high))
        return 0.0

    @staticmethod
    def _buy_no_bucket_contradiction_reason(decision: WeatherEdgeDecision) -> str | None:
        if not BOT_D_BLOCK_BUY_NO_MEAN_INSIDE_BUCKET:
            return None
        if decision.side != "BUY_NO":
            return None
        market = decision.market
        if market.range_low_f is None or market.range_high_f is None:
            return None
        mean = float(decision.forecast_mean_f)
        if float(market.range_low_f) <= mean <= float(market.range_high_f):
            return "buy_no_mean_inside_yes_bucket"
        return None

    @staticmethod
    def _expensive_no_guard_reason(
        decision: WeatherEdgeDecision,
        *,
        limit_price: Decimal,
    ) -> str | None:
        if not BOT_D_EXPENSIVE_NO_GUARD_ENABLED:
            return None
        if decision.side != "BUY_NO":
            return None
        if limit_price < BOT_D_EXPENSIVE_NO_GUARD_MIN_PRICE:
            return None

        agreement_count = int(getattr(decision, "api_agreement_count", 0) or 0)
        agreement_gap = getattr(decision, "api_agreement_max_gap_f", None)
        if (
            agreement_count < BOT_D_EXPENSIVE_NO_MIN_API_AGREEMENT
            or agreement_gap is None
            or float(agreement_gap) > BOT_D_EXPENSIVE_NO_MAX_API_GAP_F
        ):
            return "expensive_no_guard:source_agreement"

        distance_f = BotDExecutor._distance_from_bucket_f(decision)
        required_distance_f = max(
            BOT_D_EXPENSIVE_NO_MIN_DISTANCE_F,
            float(decision.forecast_std_f) * BOT_D_EXPENSIVE_NO_MIN_DISTANCE_STD_MULT,
        )
        if distance_f < required_distance_f:
            return "expensive_no_guard:distance"
        tier = BotDExecutor._live_setup_tier(decision)
        abs_edge = abs(Decimal(str(decision.net_edge)))
        if tier == "C" and abs_edge < BOT_D_EXPENSIVE_NO_TIER_C_MIN_EDGE:
            return "expensive_no_guard:tier_c_edge"
        return None

    @staticmethod
    def _no_premium_hard_skip_reason(
        decision: WeatherEdgeDecision,
        *,
        limit_price: Decimal,
    ) -> str | None:
        """ADR-160 hard skip on `BUY_NO` entries priced at or above the
        premium hard-skip threshold (default `0.95`). Payoff ceiling at this
        band is below `5c` per share while the loss-on-miss is the full
        stake, so the asymmetric tail is structurally not worth taking."""
        if decision.side != "BUY_NO":
            return None
        if limit_price >= BOT_D_LIVE_NO_PREMIUM_HARD_SKIP:
            return "no_premium_hard_skip"
        return None

    def try_enter(self, decision: WeatherEdgeDecision) -> DEntryDecision:
        if decision.side == "SKIP":
            return DEntryDecision(False, "skip")
        if BOT_D_ENTRY_HALT:
            return DEntryDecision(False, "entry_halt")
        if self.is_halted():
            return DEntryDecision(False, "halted")
        # Emergency repo-wide halt (Phase 3, audit 2026-04-17 M-2).
        from core.emergency_halt import is_emergency_halted
        if is_emergency_halted():
            return DEntryDecision(False, "emergency_halt")
        live_blocker = self._live_readiness_blocker()
        if live_blocker is not None:
            return DEntryDecision(False, live_blocker)
        if (
            decision.forecast_source == "nws_fallback"
            and (not self._is_paper_mode() or not BOT_D_ALLOW_NWS_FALLBACK_ENTRY)
        ):
            return DEntryDecision(False, "nws_fallback_entry_blocked")

        market = decision.market
        numeric_blocker = self._numeric_blocker(decision)
        if numeric_blocker is not None:
            return DEntryDecision(False, numeric_blocker, condition_id=market.gamma_id)
        gid = market.gamma_id
        if not gid:
            return DEntryDecision(False, "no_gamma_id")
        if BOT_D_REQUIRE_VERIFIED_SETTLEMENT:
            spec = SETTLEMENT_SPECS.get(market.city)
            if spec is None or not spec.verified:
                return DEntryDecision(False, "unverified_settlement")
        if BOT_D_REQUIRE_KNOWN_END_DATE and market.end_date is None:
            return DEntryDecision(False, "missing_end_date")
        if market.end_date is not None:
            end_date = market.end_date
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=UTC)
            hours_to_end = (end_date - datetime.now(UTC)).total_seconds() / 3600
            if hours_to_end <= 0:
                return DEntryDecision(False, "market_ended")
            if BOT_D_MIN_ENTRY_HOURS_TO_END > 0 and hours_to_end < BOT_D_MIN_ENTRY_HOURS_TO_END:
                return DEntryDecision(False, "too_close_to_end")
            if BOT_D_MAX_LOCKUP_HOURS > 0 and hours_to_end > BOT_D_MAX_LOCKUP_HOURS:
                return DEntryDecision(False, "lockup_too_long")
        if self.has_open_order(gid) or self.has_position(gid):
            return DEntryDecision(False, "dedupe")
        max_concurrent = (
            BOT_D_LIVE_MAX_CONCURRENT_POSITIONS
            if not self._is_paper_mode()
            else BOT_D_MAX_CONCURRENT_POSITIONS
        )
        if self.count_open() >= max_concurrent:
            return DEntryDecision(False, "max_concurrent")

        # Volume filter
        if market.volume_24h_usd is not None and market.volume_24h_usd < BOT_D_MIN_VOLUME_24H_USD:
            return DEntryDecision(False, "volume_too_low")

        # Kelly sizing
        market_p = float(market.yes_price) if market.yes_price else 0.5
        if decision.side == "BUY_YES":
            p_model = decision.gfs_probability
            token_id = market.yes_token_id
            mid = Decimal(str(market_p))
        else:
            p_model = 1.0 - decision.gfs_probability
            token_id = market.no_token_id
            mid = Decimal("1") - Decimal(str(market_p))

        size_usd = _kelly_size(p_model, float(mid), BOT_D_BANKROLL_USD,
                               BOT_D_KELLY_FRACTION, BOT_D_PER_TRADE_USD)
        if size_usd <= Decimal("0"):
            return DEntryDecision(False, "kelly_zero")

        size_multiplier = Decimal(str(getattr(decision, "size_multiplier", Decimal("1.00"))))
        if size_multiplier <= 0:
            return DEntryDecision(False, "size_multiplier_zero",
                                  size_usd=size_usd, limit_price=mid,
                                  token_id=token_id)
        if size_multiplier != Decimal("1.00"):
            raw_size = size_usd
            size_usd = (size_usd * size_multiplier).quantize(Decimal("0.01"))
            log.info(
                "bot_d.wave_size_applied gamma_id=%s regime=%s wave_count=%s "
                "factor=%s raw_size=%s size=%s",
                gid,
                getattr(decision, "regime", "unclassified"),
                getattr(decision, "wave_count", 1),
                size_multiplier,
                raw_size,
                size_usd,
            )
            if size_usd <= Decimal("0"):
                return DEntryDecision(False, "size_multiplier_zero",
                                      size_usd=size_usd, limit_price=mid,
                                      token_id=token_id)

        limit = (mid + BOT_D_LIMIT_OFFSET).quantize(Decimal("0.001"))
        limit = max(Decimal("0.001"), min(Decimal("0.99"), limit))
        if limit <= 0:
            return DEntryDecision(False, "bad_price")
        buy_no_bucket_blocker = self._buy_no_bucket_contradiction_reason(decision)
        if buy_no_bucket_blocker is not None:
            return DEntryDecision(
                False,
                buy_no_bucket_blocker,
                token_id=token_id,
                limit_price=limit,
                size_usd=size_usd,
            )
        expensive_no_blocker = self._expensive_no_guard_reason(
            decision,
            limit_price=limit,
        )
        if expensive_no_blocker is not None:
            return DEntryDecision(
                False,
                expensive_no_blocker,
                token_id=token_id,
                limit_price=limit,
                size_usd=size_usd,
            )
        premium_skip_blocker = self._no_premium_hard_skip_reason(
            decision,
            limit_price=limit,
        )
        if premium_skip_blocker is not None:
            return DEntryDecision(
                False,
                premium_skip_blocker,
                token_id=token_id,
                limit_price=limit,
                size_usd=size_usd,
            )

        if (
            not self._is_paper_mode()
            and (BOT_D_LIVE_FIXED_SHARES > 0 or BOT_D_LIVE_SIZING_MODE == "evidence_gated")
        ):
            size_shares = self._live_size_shares(decision, limit_price=limit)
            size_usd = (size_shares * limit).quantize(Decimal("0.01"))
        else:
            size_shares = (size_usd / limit).quantize(Decimal("0.01"))
        if size_shares < MIN_POLYMARKET_SHARES:
            return DEntryDecision(False, "below_min_size",
                                  limit_price=limit, size_shares=size_shares, size_usd=size_usd)

        # Aggregate bankroll cap (K2.6 audit 2026-04-21, bug #1):
        # Check is sized-aware — a tail-scaled $15 bet only consumes $15 of
        # headroom, not the raw $50 per-trade cap. Previous ordering used
        # BOT_D_PER_TRADE_USD before Kelly, which artificially choked
        # throughput when many tail-scaled positions were open.
        if self.aggregate_exposure() + size_usd > BOT_D_BANKROLL_USD:
            return DEntryDecision(False, "bankroll_cap",
                                  size_usd=size_usd, limit_price=limit,
                                  token_id=token_id)
        live_cap_blocker = self._live_cap_blocker(size_usd)
        if live_cap_blocker is not None:
            return DEntryDecision(
                False, live_cap_blocker,
                token_id=token_id, limit_price=limit,
                size_shares=size_shares, size_usd=size_usd,
            )
        if not self._is_paper_mode() and size_usd < EXCHANGE_MARKETABLE_BUY_MIN_NOTIONAL_USD:
            return DEntryDecision(
                False,
                "live_below_exchange_min_notional",
                token_id=token_id,
                limit_price=limit,
                size_shares=size_shares,
                size_usd=size_usd,
            )

        # U-01 (audit 2026-04-18): cross-bot fleet cap. Bot A/B/E call this
        # pre-trade; Bot D was the gap. Intended notional = size_usd (not
        # BOT_D_PER_TRADE_USD because Kelly already scaled it).
        from core.fleet import check_fleet_exposure
        fleet_check = check_fleet_exposure(BOT_ID, size_usd)
        if not fleet_check.ok:
            log.info(
                "bot_d.fleet_cap_breach gamma_id=%s intended=%s current=%s cap=%s",
                gid, fleet_check.intended_usd,
                fleet_check.current_total_usd, fleet_check.deployable_cap_usd,
            )
            return DEntryDecision(
                False, "fleet_cap_breach",
                token_id=token_id, limit_price=limit,
                size_shares=size_shares, size_usd=size_usd,
            )

        entry_book: OrderBook | None = None
        depth_usd: Decimal | None = None
        required_depth_usd: Decimal | None = None
        if BOT_D_DEPTH_GATE_ENABLED and Decimal("0") < BOT_D_MIN_ENTRY_DEPTH_USD:
            try:
                entry_book = self.clob.get_book(token_id)
            except Exception as exc:
                log.info(
                    "bot_d.depth_skip gamma_id=%s token=%s reason=book_unavailable err=%s",
                    gid,
                    token_id[:12],
                    type(exc).__name__,
                )
                return DEntryDecision(
                    False,
                    f"depth_unavailable:{type(exc).__name__}",
                    token_id=token_id,
                    limit_price=limit,
                    size_shares=size_shares,
                    size_usd=size_usd,
                )
            self._capture_book_snapshot(token_id, order_id=None, book=entry_book)
            depth_usd = self._book_depth_usd(entry_book, limit)
            required_depth_usd = max(BOT_D_MIN_ENTRY_DEPTH_USD, size_usd)
            if depth_usd < required_depth_usd:
                log.info(
                    "bot_d.depth_skip gamma_id=%s city=%s side=%s limit=%s "
                    "size_usd=%s depth_usd=%s required_depth_usd=%s",
                    gid,
                    market.city,
                    decision.side,
                    limit,
                    size_usd,
                    depth_usd,
                    required_depth_usd,
                )
                return DEntryDecision(
                    False,
                    "depth_too_low",
                    token_id=token_id,
                    limit_price=limit,
                    size_shares=size_shares,
                    size_usd=size_usd,
                    depth_usd=depth_usd,
                    required_depth_usd=required_depth_usd,
                )

        try:
            resp = self.clob.place_limit(
                token_id=token_id, price=limit,
                size=size_shares, side=Side.BUY, order_type=OrderType.GTC,
            )
        except Exception as exc:
            log.warning("bot_d.entry.place_failed gamma_id=%s: %s", gid, exc)
            return DEntryDecision(False, f"place_failed:{type(exc).__name__}",
                                  token_id=token_id, limit_price=limit,
                                  size_shares=size_shares, size_usd=size_usd)

        if not resp.order_id or resp.status == "SKIPPED_MIN_SIZE":
            return DEntryDecision(False, f"skipped:{resp.status}",
                                  limit_price=limit, size_shares=size_shares, size_usd=size_usd)

        # F-03: create Position row alongside Order so bankroll/concurrency caps bind.
        with self._sessions() as s:
            # ADR-021: dual-write a minimal Market row so analytics that join
            # orders->markets succeed for Bot D. The main ingest does not
            # currently capture weather markets (condition_id space mismatch +
            # category filter). Best-effort: any failure here must not block
            # the trade from being recorded.
            try:
                upsert_market_minimal(
                    s,
                    condition_id=gid,
                    category="weather",
                    question=market.question,
                    yes_token_id=market.yes_token_id,
                    no_token_id=market.no_token_id,
                    end_date=market.end_date,
                    yes_price=market.yes_price,
                    volume_24h_usd=market.volume_24h_usd,
                )
            except Exception as exc:
                # ADR-021 + Grok review S6 / Codex C-S5: never block a trade
                # on a dual-write failure, but upgrade to ERROR level and
                # count failures so silent analytics rot is surfaced.
                # The _market_upsert_fail_count running tally is zeroed by
                # a successful upsert; a Telegram alert at >1% failure rate
                # is a scheduled follow-up (not built here).
                log.error(
                    "bot_d.entry.market_upsert_failed gamma_id=%s: %s",
                    gid, exc,
                )
            s.add(Order(
                order_id=resp.order_id, bot_id=BOT_ID, condition_id=gid,
                token_id=token_id, side="BUY", price=limit,
                size=size_shares, status=resp.status or "OPEN", order_type="GTC",
            ))
            # U-06 (audit 2026-04-18): prior code also wrote a Position row
            # here. That caused Portfolio._apply_to_position to find the
            # OPEN Position at fill time and add the filled size to it
            # again — exposure doubled on every successful fill. Position
            # lifecycle is now owned exclusively by the Portfolio layer;
            # `count_open` was widened to count pending Orders so the
            # concurrency cap still binds between placement and fill.
            s.commit()

        self._capture_book_snapshot(token_id, order_id=resp.order_id, book=entry_book)
        log.info(
            "bot_d.entry.placed order_id=%s city=%s date=%s %s %s→%s "
            "edge=%+.3f kelly=$%s limit=%s shares=%s depth_usd=%s regime=%s "
            "wave_count=%s mode=%s",
            resp.order_id, market.city, market.date,
            market.temp_type, market.direction,
            f"{market.range_low_f}-{market.range_high_f}",
            decision.net_edge, size_usd, limit, size_shares,
            depth_usd if depth_usd is not None else "n/a",
            getattr(decision, "regime", "unclassified"),
            getattr(decision, "wave_count", 1),
            "PAPER" if self._is_paper_mode() else "LIVE",
        )
        return DEntryDecision(
            True, "placed", order_id=resp.order_id, token_id=token_id,
            limit_price=limit, size_shares=size_shares, size_usd=size_usd,
            depth_usd=depth_usd, required_depth_usd=required_depth_usd,
        )

    def try_enter_all(self, decisions: list[WeatherEdgeDecision]) -> list[DEntryDecision]:
        """Rank by |edge| descending, attempt each."""
        actionable = [d for d in decisions if d.side in ("BUY_YES", "BUY_NO")]
        actionable.sort(key=lambda d: abs(d.net_edge), reverse=True)
        out: list[DEntryDecision] = []
        for d in actionable:
            res = self.try_enter(d)
            if res.condition_id is None:
                res.condition_id = d.market.gamma_id
            out.append(res)
        return out

    def review_open_orders(
        self,
        decisions: list[WeatherEdgeDecision],
        edge_collapse_threshold: float = 0.03,
    ) -> int:
        """Cancel open orders whose edge has collapsed or flipped after a GFS update.

        Weather markets update every ~6h as new GFS runs come in. If the
        latest forecast shifts and the edge evaporates (|net_edge| < 0.03) or
        flips direction (we bought YES but now model says BUY_NO), cancel.
        In paper mode, also close any corresponding Position row. In live
        mode, place a real SELL order and leave the Position open until fill
        reconciliation closes it.

        Returns number of orders cancelled.
        """
        self._sync_live_open_order_statuses()
        with self._sessions() as s:
            open_orders = list(
                s.execute(
                    sa_select(Order).where(
                        Order.bot_id == BOT_ID,
                        Order.side == "BUY",
                        Order.status.in_(OPEN_ORDER_STATUSES),
                    )
                ).scalars().all()
            )

        dec_by_gid: dict[str, WeatherEdgeDecision] = {}
        for d in decisions:
            dec_by_gid[d.market.gamma_id] = d

        cancelled = self._review_stale_exit_orders(now=datetime.now(UTC))
        if not open_orders:
            return cancelled
        for order in open_orders:
            gid = order.condition_id
            dec = dec_by_gid.get(gid)
            if dec is None:
                continue
            original_side = "YES" if order.token_id == dec.market.yes_token_id else "NO"
            edge_for_side = dec.net_edge if original_side == "YES" else -dec.net_edge

            should_cancel = False
            reason = ""
            if abs(dec.net_edge) < edge_collapse_threshold:
                should_cancel = True
                reason = f"edge_collapsed |{dec.net_edge:.3f}|<{edge_collapse_threshold}"
            elif edge_for_side < 0:
                should_cancel = True
                reason = f"edge_flipped side={original_side} edge={edge_for_side:.3f}"

            if should_cancel:
                try:
                    self.clob.cancel_order(order.order_id)
                except Exception as exc:
                    log.warning("bot_d.exit.cancel_failed order=%s: %s", order.order_id, exc)
                    continue
                with self._sessions() as s:
                    o = s.get(Order, order.order_id)
                    if o:
                        o.status = "CANCELLED"
                    s.commit()
                pos = self._open_position_for_condition(gid)
                if pos and pos.size and pos.size > 0:
                    mkt_yes = (
                        Decimal(str(dec.market.yes_price))
                        if dec.market.yes_price is not None
                        else Decimal("0")
                    )
                    pos_is_yes = (pos.token_id == dec.market.yes_token_id)
                    exit_px = mkt_yes if pos_is_yes else (Decimal("1") - mkt_yes)
                    exit_px = max(Decimal("0"), min(Decimal("1"), exit_px))
                    self._exit_position(
                        pos=pos,
                        dec=dec,
                        exit_px=exit_px,
                        reason=reason,
                        source=f"edge-{order.order_id}",
                        now=datetime.now(UTC),
                    )
                log.info("bot_d.exit.cancelled order=%s city=%s reason=%s",
                         order.order_id, dec.market.city, reason)
                cancelled += 1
        return cancelled

    def _review_stale_exit_orders(self, *, now: datetime) -> int:
        if self._is_paper_mode() or BOT_D_EXIT_STALE_MIN <= 0:
            return 0
        cutoff = now.replace(tzinfo=None) if now.tzinfo else now
        stale_seconds = BOT_D_EXIT_STALE_MIN * 60
        with self._sessions() as s:
            sell_orders = list(
                s.execute(
                    sa_select(Order).where(
                        Order.bot_id == BOT_ID,
                        Order.side == "SELL",
                        Order.status.in_(OPEN_ORDER_STATUSES),
                    )
                ).scalars().all()
            )
        cancelled = 0
        for order in sell_orders:
            placed = order.placed_at
            if placed is None:
                age_seconds = stale_seconds + 1
            else:
                placed_cmp = placed.replace(tzinfo=None) if placed.tzinfo else placed
                age_seconds = (cutoff - placed_cmp).total_seconds()
            if age_seconds < stale_seconds:
                continue
            try:
                self.clob.cancel_order(order.order_id)
            except Exception as exc:
                log.warning("bot_d.live_exit.stale_cancel_failed order=%s: %s", order.order_id, exc)
                continue
            with self._sessions() as s:
                o = s.get(Order, order.order_id)
                if o:
                    o.status = "CANCELLED"
                s.add(Event(
                    bot_id=BOT_ID,
                    event_type="bot_d.live_exit.stale",
                    severity="warn",
                    message=f"stale live exit order cancelled order={order.order_id}",
                    payload={
                        "order_id": order.order_id,
                        "condition_id": order.condition_id,
                        "token_id": order.token_id,
                        "age_seconds": round(age_seconds, 1),
                        "max_age_seconds": stale_seconds,
                    },
                ))
                s.commit()
            cancelled += 1
        return cancelled

    def review_open_positions(
        self,
        decisions: list[WeatherEdgeDecision],
        edge_floor: float = 0.02,
    ) -> int:
        """Exit filled positions whose edge has collapsed or flipped.

        K2.6 audit 2026-04-21 (bug #4 — "fatal flaw"): Bot D previously had
        NO bot-driven exit path. Filled positions were held blindly to
        market resolution, exposing the book to:
          * Edge decay across 6h GFS cycles (hold -EV tickets for hours).
          * Failure to capture favourable price moves (no take-profit).
          * Inability to liquidate during thesis-breaking events.
          * No escape hatch if a model bug is discovered mid-hold.

        This method mirrors `review_open_orders` but targets the Position
        table (i.e. *filled* orders):

        For each OPEN Position with a matching WeatherEdgeDecision in
        ``decisions``:
          * Compute the edge on the position's outcome side (YES or NO).
          * If |edge_for_side| < edge_floor OR edge_for_side < 0:
              paper mode: write a synthetic SELL Trade at the current
              market mid price via Portfolio.on_fill.
              live mode: place a real CLOB SELL order and keep the
              Position open until fill reconciliation closes it.

        Price used: the current book mid for the position's side
        (``market.yes_price`` for YES, ``1 - yes_price`` for NO). Callers
        should only call this AFTER strategy has produced fresh
        decisions against the current forecast.

        Returns the count of exit actions taken this call.
        """
        with self._sessions() as s:
            open_positions = list(
                s.execute(
                    sa_select(Position).where(
                        Position.bot_id == BOT_ID,
                        Position.status == "OPEN",
                    )
                ).scalars().all()
            )
        if not open_positions:
            return 0

        dec_by_gid: dict[str, WeatherEdgeDecision] = {}
        for d in decisions:
            if d.market.gamma_id:
                dec_by_gid[d.market.gamma_id] = d

        exited = 0
        now = datetime.now(UTC)

        for pos in open_positions:
            dec = dec_by_gid.get(pos.condition_id)
            validation: DPositionValidation | None = None
            if BOT_D_POSITION_VALIDATION_ENABLED:
                try:
                    validation = self.validate_open_position(pos, dec=dec, now=now)
                    self._emit_position_validation(validation)
                except Exception as exc:
                    log.warning(
                        "bot_d.position_validation.failed pos_id=%s cid=%s err=%s",
                        pos.id,
                        pos.condition_id,
                        exc,
                    )
                if (
                    validation is not None
                    and BOT_D_POSITION_AUTO_SELL_ENABLED
                    and validation.action == "SELL_NOW"
                    and not validation.has_pending_exit_order
                    and validation.best_bid is not None
                    and self._exit_position(
                        pos=pos,
                        dec=dec,
                        exit_px=validation.best_bid,
                        reason=f"position_validation:{validation.reason}",
                        source="position_validation",
                        now=now,
                    )
                ):
                    log.warning(
                        "bot_d.position_validation.auto_sell pos_id=%s cid=%s "
                        "side=%s best_bid=%s reason=%s paper=%s",
                        pos.id,
                        pos.condition_id,
                        pos.side,
                        validation.best_bid,
                        validation.reason,
                        self._is_paper_mode(),
                    )
                    exited += 1
                    continue
            take_profit = self._take_profit_exit_reason(pos=pos, dec=dec, now=now)
            if take_profit is not None:
                reason, best_bid = take_profit
                if self._exit_position(
                    pos=pos,
                    dec=dec,
                    exit_px=best_bid,
                    reason=reason,
                    source="take_profit",
                    now=now,
                ):
                    self._emit_exit_event(
                        event_type="bot_d.take_profit_exit",
                        severity="info",
                        message=f"take-profit exit triggered pos={pos.id}",
                        payload={
                            "position_id": pos.id,
                            "condition_id": pos.condition_id,
                            "token_id": pos.token_id,
                            "size": str(pos.size),
                            "best_bid": str(best_bid),
                            "threshold": str(BOT_D_TAKE_PROFIT_MIN_BID),
                            "reason": reason,
                            "paper": self._is_paper_mode(),
                            "has_fresh_decision": dec is not None,
                        },
                    )
                    log.info(
                        "bot_d.take_profit_exit pos_id=%s cid=%s side=%s "
                        "size=%s best_bid=%s threshold=%s paper=%s fresh_decision=%s",
                        pos.id, pos.condition_id, pos.side,
                        pos.size, best_bid, BOT_D_TAKE_PROFIT_MIN_BID,
                        self._is_paper_mode(), dec is not None,
                    )
                    exited += 1
                continue
            if dec is None:
                # No fresh decision for this market — either the market
                # fell out of the scan window, resolved, or the forecast
                # pipeline skipped it. Don't force edge exits on no-signal,
                # but the take-profit check above is still allowed because it
                # only depends on executable bid.
                continue

            pos_is_yes = (pos.token_id == dec.market.yes_token_id)
            # Net edge is defined for the YES side by convention in
            # WeatherEdgeDecision; flip sign for NO positions.
            edge_for_side = dec.net_edge if pos_is_yes else -dec.net_edge

            should_exit = False
            reason = ""
            if abs(edge_for_side) < edge_floor:
                should_exit = True
                reason = f"edge_decayed |{edge_for_side:+.3f}|<{edge_floor}"
            elif edge_for_side < 0:
                should_exit = True
                reason = f"edge_flipped side={'YES' if pos_is_yes else 'NO'} edge={edge_for_side:+.3f}"

            if not should_exit:
                continue

            mkt_yes = (
                Decimal(str(dec.market.yes_price))
                if dec.market.yes_price is not None
                else Decimal("0.5")
            )
            exit_px = mkt_yes if pos_is_yes else (Decimal("1") - mkt_yes)
            exit_px = max(Decimal("0"), min(Decimal("1"), exit_px))

            if self._exit_position(
                pos=pos,
                dec=dec,
                exit_px=exit_px,
                reason=reason,
                source="pos",
                now=now,
            ):
                log.info(
                    "bot_d.position_exit.action pos_id=%s city=%s side=%s "
                    "size=%s exit_px=%s reason=%s paper=%s",
                    pos.id, dec.market.city,
                    "YES" if pos_is_yes else "NO",
                    pos.size, exit_px, reason, self._is_paper_mode(),
                )
                exited += 1
        return exited
