"""Tiny live-maker executor for crypto fair-value candidates.

This is intentionally separate from the paper/shadow runner. The existing
``bots.crypto_fair_value`` package stays paper-only; this module is the
approval-gated live path for the probability-gap and Brownian FV maker
experiments.
"""
from __future__ import annotations

import argparse
import logging
import os
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from bots.crypto_fair_value.config import CryptoFairValueConfig, load_config
from bots.crypto_fair_value.discovery import (
    active_markets,
    cex_state,
    connect_recorder,
    latest_book_state,
)
from bots.crypto_fair_value.model import (
    MarketMeta,
    Signal,
    brownian_fair_value_signal,
    probability_gap_signal,
)
from core.clob_v2 import ClobWrapperV2, OrderResponse, OrderType, Side
from core.db import (
    Event,
    HaltFlag,
    Order,
    Position,
    get_session_factory,
    init_db,
    upsert_market_minimal,
)
from core.emergency_halt import is_emergency_halted
from core.fleet import check_fleet_exposure
from core.portfolio import Portfolio

log = logging.getLogger("crypto_fv_live_maker")

LIVE_BOT_IDS = {
    "probability_gap": "crypto_probability_gap_live_maker",
    "brownian_fair_value": "crypto_brownian_fv_live_maker",
}
DEFAULT_CAPS = {
    "probability_gap": {
        "daily_gross_cap_usd": "250",
        "open_exposure_cap_usd": "100",
        "max_concurrent_positions": "20",
    },
    "brownian_fair_value": {
        "daily_gross_cap_usd": "300",
        "open_exposure_cap_usd": "120",
        "max_concurrent_positions": "24",
    },
}

OPEN_ORDER_STATUSES = {"OPEN", "PARTIAL", "MATCHED", "live"}
MIN_CLOB_SHARES = Decimal("5")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_bool(name: str, default: str = "false") -> bool:
    return _env(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_decimal(name: str, default: str) -> Decimal:
    return Decimal(_env(name, default))


def _env_int(name: str, default: str) -> int:
    return int(_env(name, default))


def _prefix(strategy: str) -> str:
    return "CRYPTO_PROB_GAP_LIVE" if strategy == "probability_gap" else "CRYPTO_BROWNIAN_FV_LIVE"


def _q_price(value: Decimal) -> Decimal:
    return max(Decimal("0.001"), min(Decimal("0.999"), value)).quantize(Decimal("0.001"))


def _ceil_shares(notional: Decimal, price: Decimal) -> Decimal:
    if price <= 0:
        return MIN_CLOB_SHARES
    return max(MIN_CLOB_SHARES, (notional / price).quantize(Decimal("1"), rounding=ROUND_CEILING))


@dataclass(frozen=True)
class LiveMakerConfig:
    strategy: str
    bot_id: str
    live_authorized: bool
    approved_at: str
    max_order_usd: Decimal = Decimal("5")
    daily_gross_cap_usd: Decimal = Decimal("25")
    open_exposure_cap_usd: Decimal = Decimal("25")
    max_concurrent_positions: int = 5
    max_quote_age_sec: int = 90
    quote_discount: Decimal = Decimal("0.001")
    min_maker_edge: Decimal = Decimal("0.025")
    scan_interval_s: float = 5.0


@dataclass(frozen=True)
class LiveMakerQuote:
    meta: MarketMeta
    signal: Signal
    quote_price: Decimal
    shares: Decimal
    notional_usd: Decimal
    best_bid: Decimal | None
    best_ask: Decimal
    fair_price: Decimal


def load_live_config(strategy: str) -> LiveMakerConfig:
    strategy = strategy.strip().lower()
    if strategy not in LIVE_BOT_IDS:
        raise ValueError(f"unknown live FV strategy: {strategy}")
    prefix = _prefix(strategy)
    defaults = DEFAULT_CAPS[strategy]
    return LiveMakerConfig(
        strategy=strategy,
        bot_id=_env(f"{prefix}_BOT_ID", LIVE_BOT_IDS[strategy]),
        live_authorized=_env_bool(f"{prefix}_AUTHORIZED")
        or _env_bool("CRYPTO_FV_LIVE_AUTHORIZED"),
        approved_at=(
            _env(f"{prefix}_APPROVED_AT").strip()
            or _env("CRYPTO_FV_LIVE_APPROVED_AT").strip()
        ),
        max_order_usd=_env_decimal(f"{prefix}_MAX_ORDER_USD", "5"),
        daily_gross_cap_usd=_env_decimal(
            f"{prefix}_DAILY_GROSS_CAP_USD",
            defaults["daily_gross_cap_usd"],
        ),
        open_exposure_cap_usd=_env_decimal(
            f"{prefix}_OPEN_EXPOSURE_CAP_USD",
            defaults["open_exposure_cap_usd"],
        ),
        max_concurrent_positions=_env_int(
            f"{prefix}_MAX_CONCURRENT_POSITIONS",
            defaults["max_concurrent_positions"],
        ),
        max_quote_age_sec=_env_int(f"{prefix}_MAX_QUOTE_AGE_SEC", "90"),
        quote_discount=_env_decimal(f"{prefix}_QUOTE_DISCOUNT", "0.001"),
        min_maker_edge=_env_decimal(f"{prefix}_MIN_MAKER_EDGE", "0.025"),
        scan_interval_s=float(_env(f"{prefix}_SCAN_INTERVAL_S", "5")),
    )


def _load_signal_config(strategy: str) -> CryptoFairValueConfig:
    # Reuse the paper runner's discovery/model thresholds, but force maker
    # semantics by env in the systemd unit. This function does not call
    # validate(), because validate() is the paper-only guard for the existing
    # shadow service.
    config = load_config(strategy)
    return config


def startup_authorization_blocker(live_config: LiveMakerConfig) -> str | None:
    """Return why a live process must not open wallet/client paths yet."""
    if os.environ.get("POLYMARKET_ENV", "").lower() != "live":
        return "polymarket_env_not_live"
    if os.environ.get(_prefix(live_config.strategy) + "_ENV", "").lower() != "live":
        return "strategy_live_env_not_live"
    if not live_config.live_authorized:
        return "live_not_authorized"
    if not live_config.approved_at:
        return "missing_approved_at"
    if live_config.bot_id != LIVE_BOT_IDS[live_config.strategy]:
        return "unexpected_live_bot_id"
    return None


class CryptoFVLiveMaker:
    def __init__(
        self,
        *,
        clob: ClobWrapperV2,
        signal_config: CryptoFairValueConfig,
        live_config: LiveMakerConfig,
        session_factory: sessionmaker | None = None,
    ) -> None:
        self.clob = clob
        self.signal_config = signal_config
        self.live_config = live_config
        self.session_factory = session_factory or get_session_factory()
        self.portfolio = Portfolio(session_factory=self.session_factory)

    def _emit(self, event_type: str, message: str, *, severity: str = "info", payload: dict | None = None) -> None:
        with self.session_factory() as session:
            session.add(
                Event(
                    bot_id=self.live_config.bot_id,
                    event_type=event_type,
                    severity=severity,
                    message=message,
                    payload=payload or {},
                )
            )
            session.commit()

    def authorization_blocker(self) -> str | None:
        blocker = startup_authorization_blocker(self.live_config)
        if blocker is not None:
            return blocker
        effective_paper = getattr(self.clob, "_effective_paper", None)
        if callable(effective_paper) and effective_paper():
            return "clob_effective_paper"
        return None

    def halt_reason(self) -> str | None:
        if is_emergency_halted():
            return "emergency_halt"
        with self.session_factory() as session:
            flag = session.scalars(
                select(HaltFlag).where(HaltFlag.bot_id == self.live_config.bot_id)
            ).first()
        if flag is not None and flag.halted:
            return "bot_halt"
        return None

    def open_count(self) -> int:
        with self.session_factory() as session:
            positions = session.scalars(
                select(Position.condition_id).where(
                    Position.bot_id == self.live_config.bot_id,
                    Position.status == "OPEN",
                )
            ).all()
            orders = session.scalars(
                select(Order.condition_id).where(
                    Order.bot_id == self.live_config.bot_id,
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            ).all()
        return len(set(positions) | set(orders))

    def open_exposure_usd(self) -> Decimal:
        with self.session_factory() as session:
            positions = session.execute(
                select(func.coalesce(func.sum(Position.cost_basis_usd), 0)).where(
                    Position.bot_id == self.live_config.bot_id,
                    Position.status == "OPEN",
                )
            ).scalar() or Decimal("0")
            orders = session.execute(
                select(func.coalesce(func.sum(Order.price * Order.size), 0)).where(
                    Order.bot_id == self.live_config.bot_id,
                    Order.side == "BUY",
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            ).scalar() or Decimal("0")
        return Decimal(str(positions)) + Decimal(str(orders))

    def daily_gross_usd(self) -> Decimal:
        day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        with self.session_factory() as session:
            total = session.execute(
                select(func.coalesce(func.sum(Order.price * Order.size), 0)).where(
                    Order.bot_id == self.live_config.bot_id,
                    Order.placed_at >= day_start,
                    Order.side == "BUY",
                )
            ).scalar() or Decimal("0")
        return Decimal(str(total))

    def has_open_order_or_position(self, condition_id: str) -> bool:
        with self.session_factory() as session:
            order = session.scalars(
                select(Order.order_id).where(
                    Order.bot_id == self.live_config.bot_id,
                    Order.condition_id == condition_id,
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            ).first()
            if order is not None:
                return True
            position = session.scalars(
                select(Position.id).where(
                    Position.bot_id == self.live_config.bot_id,
                    Position.condition_id == condition_id,
                    Position.status == "OPEN",
                )
            ).first()
        return position is not None

    def _sync_open_orders(self) -> int:
        try:
            exchange_ids = {order.order_id for order in self.clob.get_user_orders() if order.order_id}
        except Exception as exc:
            log.warning("crypto_fv_live_maker.order_sync_failed err=%s", exc)
            return 0
        now = datetime.now(UTC)
        updated = 0
        with self.session_factory() as session:
            orders = list(
                session.scalars(
                    select(Order).where(
                        Order.bot_id == self.live_config.bot_id,
                        Order.status.in_(OPEN_ORDER_STATUSES),
                    )
                )
            )
            for order in orders:
                if order.order_id in exchange_ids:
                    continue
                order.status = "CANCELLED"
                order.last_updated = now
                updated += 1
            if updated:
                session.add(
                    Event(
                        bot_id=self.live_config.bot_id,
                        event_type="crypto_fv_live_maker.order_sync",
                        severity="info",
                        message=f"synced {updated} non-open maker orders",
                        payload={"updated": updated, "exchange_open_orders": len(exchange_ids)},
                    )
                )
                session.commit()
        return updated

    def cancel_stale_quotes(self) -> int:
        now = datetime.now(UTC)
        with self.session_factory() as session:
            orders = list(
                session.scalars(
                    select(Order).where(
                        Order.bot_id == self.live_config.bot_id,
                        Order.side == "BUY",
                        Order.status.in_(OPEN_ORDER_STATUSES),
                    )
                )
            )
        cancelled = 0
        for order in orders:
            placed = order.placed_at if order.placed_at.tzinfo else order.placed_at.replace(tzinfo=UTC)
            age = (now - placed).total_seconds()
            if age < self.live_config.max_quote_age_sec:
                continue
            try:
                ok = bool(self.clob.cancel_order(order.order_id))
            except Exception as exc:
                self._emit(
                    "crypto_fv_live_maker.cancel_failed",
                    f"cancel failed {order.order_id}",
                    severity="warn",
                    payload={"order_id": order.order_id, "age_seconds": age, "error": str(exc)[:200]},
                )
                continue
            with self.session_factory() as session:
                db_order = session.get(Order, order.order_id)
                if db_order is not None and ok:
                    db_order.status = "CANCELLED"
                    db_order.last_updated = now
                session.add(
                    Event(
                        bot_id=self.live_config.bot_id,
                        event_type="crypto_fv_live_maker.quote_cancelled",
                        severity="info",
                        message=f"cancelled stale quote {order.order_id}",
                        payload={"order_id": order.order_id, "age_seconds": age, "ok": ok},
                    )
                )
                session.commit()
            cancelled += 1 if ok else 0
        return cancelled

    def quote_for_signal(self, meta: MarketMeta, signal: Signal) -> LiveMakerQuote | str:
        halted = self.halt_reason()
        if halted is not None:
            return halted
        if self.has_open_order_or_position(signal.condition_id):
            return "dedupe"
        if self.open_count() >= self.live_config.max_concurrent_positions:
            return "max_concurrent_positions"

        try:
            book = self.clob.get_book(signal.token_id)
        except Exception as exc:
            return f"book_fetch_failed:{type(exc).__name__}"
        bids = [Decimal(str(price)) for price, _size in (book.bids or [])]
        asks = [Decimal(str(price)) for price, _size in (book.asks or [])]
        best_bid = max(bids) if bids else None
        best_ask = min(asks) if asks else None
        if best_ask is None:
            return "no_best_ask"

        fair = (
            Decimal(str(signal.model_probability_up))
            if signal.side == "UP"
            else Decimal(str(1.0 - signal.model_probability_up))
        )
        if fair <= 0 or fair >= 1:
            return "bad_fair"
        try:
            tick = Decimal(str(self.clob.get_tick_size(signal.token_id)))
        except Exception:
            tick = Decimal("0.001")

        quote = fair - self.live_config.quote_discount
        if best_bid is not None:
            quote = max(quote, best_bid)
        quote = min(quote, best_ask - tick)
        quote = _q_price(quote)
        if quote >= best_ask:
            return "crossed_book_rejected"
        if fair - quote < self.live_config.min_maker_edge:
            return "maker_edge_too_small"

        shares = _ceil_shares(self.live_config.max_order_usd, quote)
        notional = (shares * quote).quantize(Decimal("0.01"))
        if notional > self.live_config.max_order_usd:
            shares = max(MIN_CLOB_SHARES, shares - Decimal("1"))
            notional = (shares * quote).quantize(Decimal("0.01"))
        if shares < MIN_CLOB_SHARES:
            return "below_exchange_min_shares"
        if notional <= 0 or notional > self.live_config.max_order_usd:
            return "max_order_cap"
        if self.daily_gross_usd() + notional > self.live_config.daily_gross_cap_usd:
            return "daily_gross_cap"
        if self.open_exposure_usd() + notional > self.live_config.open_exposure_cap_usd:
            return "open_exposure_cap"
        fleet = check_fleet_exposure(self.live_config.bot_id, notional)
        if not fleet.ok:
            return fleet.reason

        return LiveMakerQuote(
            meta=meta,
            signal=signal,
            quote_price=quote,
            shares=shares,
            notional_usd=notional,
            best_bid=best_bid,
            best_ask=best_ask,
            fair_price=fair.quantize(Decimal("0.001")),
        )

    def place_quote(self, quote: LiveMakerQuote) -> OrderResponse:
        blocker = self.authorization_blocker()
        if blocker is not None:
            raise RuntimeError(blocker)
        response = self.clob.place_limit(
            token_id=quote.signal.token_id,
            price=quote.quote_price,
            size=quote.shares,
            side=Side.BUY,
            order_type=OrderType.GTC,
            post_only=True,
        )
        if not response.order_id:
            raise RuntimeError(f"empty_order_id:{response.status}")
        now = datetime.now(UTC)
        with self.session_factory() as session:
            upsert_market_minimal(
                session,
                condition_id=quote.meta.condition_id,
                category="crypto",
                question=quote.meta.question,
                yes_token_id=quote.meta.yes_token_id,
                no_token_id=quote.meta.no_token_id,
                end_date=datetime.fromtimestamp(quote.meta.end_ms / 1000, tz=UTC),
            )
            session.add(
                Order(
                    order_id=response.order_id,
                    bot_id=self.live_config.bot_id,
                    condition_id=quote.signal.condition_id,
                    token_id=quote.signal.token_id,
                    side="BUY",
                    price=quote.quote_price,
                    size=quote.shares,
                    status=response.status or "live",
                    order_type="GTC",
                    placed_at=now,
                    last_updated=now,
                )
            )
            session.add(
                Event(
                    bot_id=self.live_config.bot_id,
                    event_type="crypto_fv_live_maker.quote_placed",
                    severity="info",
                    message=f"FV maker quote placed {response.order_id}",
                    payload={
                        "order_id": response.order_id,
                        "strategy": self.live_config.strategy,
                        "condition_id": quote.signal.condition_id,
                        "symbol": quote.signal.symbol,
                        "duration_minutes": quote.signal.duration_minutes,
                        "side": quote.signal.side,
                        "token_id": quote.signal.token_id,
                        "fair_price": str(quote.fair_price),
                        "quote_price": str(quote.quote_price),
                        "shares": str(quote.shares),
                        "notional_usd": str(quote.notional_usd),
                        "best_bid": str(quote.best_bid) if quote.best_bid is not None else None,
                        "best_ask": str(quote.best_ask),
                        "model_edge": str(quote.signal.model_edge),
                        "seconds_left": quote.signal.seconds_left,
                        "lead_bucket": quote.signal.lead_bucket,
                    },
                )
            )
            session.commit()
        return response

    def _signal_for_market(self, meta: MarketMeta, book, cex, now_ms: int) -> Signal | None:
        cfg = self.signal_config
        if cfg.strategy == "probability_gap":
            return probability_gap_signal(
                meta=meta,
                book=book,
                cex=cex,
                decision_ms=now_ms,
                min_edge=cfg.min_edge,
                min_price=cfg.min_price,
                max_price=cfg.max_price,
            )
        if now_ms < meta.start_ms + 30_000:
            return None
        if abs(cex.move_60s) > cfg.brownian_max_abs_move_60s:
            return None
        return brownian_fair_value_signal(
            meta=meta,
            book=book,
            cex=cex,
            decision_ms=now_ms,
            min_model_mid_gap=cfg.min_model_mid_gap,
            min_entry_edge=cfg.min_entry_edge,
            min_price=cfg.min_price,
            max_price=cfg.max_price,
        )

    def scan_once(self, *, dry_run: bool = False) -> Counter[str]:
        counts: Counter[str] = Counter()
        blocker = self.authorization_blocker()
        if blocker is not None and not dry_run:
            counts[f"blocked_{blocker}"] += 1
            self._emit("crypto_fv_live_maker.scan_summary", f"blocked: {blocker}", severity="warn", payload=dict(counts))
            return counts

        self._sync_open_orders()
        fills = self.portfolio.reconcile_live_fills(self.clob, self.live_config.bot_id, require_known_order=True)
        if fills:
            counts["fills_reconciled"] = fills
        self.cancel_stale_quotes()

        conn = connect_recorder(self.signal_config.recorder_db_path)
        if conn is None:
            counts["recorder_db_missing"] += 1
            return counts
        now_ms = int(time.time() * 1000)
        try:
            markets = active_markets(conn, config=self.signal_config, now_ms=now_ms)
            counts["markets_seen"] = len(markets)
            for meta in markets:
                counts["markets_evaluated"] += 1
                if self.has_open_order_or_position(meta.condition_id):
                    counts["duplicate_open_position"] += 1
                    continue
                book = latest_book_state(conn, meta, now_ms=now_ms, max_age_sec=self.signal_config.max_book_age_sec)
                if book is None:
                    counts["missing_book"] += 1
                    continue
                state = cex_state(conn, meta, now_ms=now_ms, max_age_sec=self.signal_config.max_cex_age_sec)
                if state is None:
                    counts["stale_or_missing_cex"] += 1
                    continue
                if book.effective_spread > self.signal_config.max_spread:
                    counts["spread_skip"] += 1
                    continue
                if abs(state.move_60s) > self.signal_config.chaos_max_abs_move_60s:
                    counts["chaos_skip"] += 1
                    continue
                signal = self._signal_for_market(meta, book, state, now_ms)
                if signal is None:
                    counts["no_signal"] += 1
                    continue
                if signal.top_depth_usd < self.signal_config.min_top_depth_usd:
                    counts["depth_skip"] += 1
                    continue
                quote = self.quote_for_signal(meta, signal)
                if isinstance(quote, str):
                    counts[f"quote_skip_{quote}"] += 1
                    continue
                if dry_run:
                    counts["dry_run_quotes"] += 1
                    continue
                try:
                    self.place_quote(quote)
                    counts["quotes_placed"] += 1
                except Exception as exc:
                    counts[f"place_failed_{type(exc).__name__}"] += 1
                    log.warning("crypto_fv_live_maker.place_failed err=%s", exc)
        finally:
            conn.close()
        self._emit("crypto_fv_live_maker.scan_summary", "FV maker scan complete", payload=dict(counts))
        return counts


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="bots.crypto_fair_value.live_maker")
    p.add_argument("--strategy", choices=tuple(LIVE_BOT_IDS), required=True)
    p.add_argument("--once", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def _build_clob(*, dry_run: bool) -> ClobWrapperV2:
    if dry_run:
        return ClobWrapperV2(keystore=None, paper_override=True)
    from core.config import get_settings
    from core.keystore import Keystore

    settings = get_settings()
    keystore = Keystore.load_from_settings(settings)
    clob = ClobWrapperV2(keystore=keystore, paper_override=False)
    clob.load_preflight_from_db()
    return clob


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    init_db()
    signal_config = _load_signal_config(args.strategy)
    live_config = load_live_config(args.strategy)
    if not args.dry_run:
        blocker = startup_authorization_blocker(live_config)
        if blocker is not None:
            log.error("crypto_fv_live_maker.startup_blocked bot_id=%s reason=%s", live_config.bot_id, blocker)
            return 2
    clob = _build_clob(dry_run=args.dry_run)
    runner = CryptoFVLiveMaker(clob=clob, signal_config=signal_config, live_config=live_config)
    while True:
        counts = runner.scan_once(dry_run=args.dry_run)
        log.info("crypto_fv_live_maker.scan bot_id=%s counts=%s", live_config.bot_id, dict(counts))
        if args.once:
            return 0
        time.sleep(live_config.scan_interval_s)


if __name__ == "__main__":
    raise SystemExit(main())
