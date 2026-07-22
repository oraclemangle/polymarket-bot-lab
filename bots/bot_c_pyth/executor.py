"""Bot C executor — fixed-size GTC limit orders from EdgeDecisions.

Runs in paper or live mode depending on POLYMARKET_ENV (via core.config.
get_settings().is_live()). Paper mode routes through ClobWrapper._paper_fill
which returns a synthetic order id; live mode signs via py-clob-client.

No Kelly; simple fixed-notional sizing. Dedupe on gamma_id → condition_id.
Hard caps on max concurrent positions + aggregate exposure.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from bots.bot_c_pyth.strategy import EdgeDecision
from core.clob_v2 import ClobWrapperV2 as ClobWrapper, OrderType, Side
from core.config import get_settings
from core.db import HaltFlag, Order, Position, get_session_factory

log = logging.getLogger(__name__)

BOT_ID = "bot_c"


def _env_decimal(name: str, default: str) -> Decimal:
    raw = os.getenv(name, default)
    try:
        return Decimal(raw)
    except Exception:
        return Decimal(default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Fixed per-trade notional. Conservative; tuned per operator.
BOT_C_PER_TRADE_USD = _env_decimal("BOT_C_PER_TRADE_USD", "10")
BOT_C_BANKROLL_USD = _env_decimal("BOT_C_BANKROLL_USD", "50")
BOT_C_MAX_CONCURRENT_POSITIONS = _env_int("BOT_C_MAX_CONCURRENT_POSITIONS", 3)
# Stricter than analysis threshold — only trade clear edges.
BOT_C_MIN_EDGE_FOR_ORDER = _env_decimal("BOT_C_MIN_EDGE_FOR_ORDER", "0.15")
# Never tie up capital longer than a week.
BOT_C_MAX_HOURS_TO_RESOLUTION = _env_int("BOT_C_MAX_HOURS_TO_RESOLUTION", 24 * 7)
# Only trade when the market has meaningful retail participation.
BOT_C_MIN_VOLUME_24H_USD = _env_decimal("BOT_C_MIN_VOLUME_24H_USD", "500")
# Fix 6: post at mid (offset 0) to avoid adverse selection. The prior +0.01
# gave away edge to fill-seekers. If fills become too slow, bump to 0.005.
BOT_C_LIMIT_OFFSET = _env_decimal("BOT_C_LIMIT_OFFSET", "0.00")
# Session 30 audit: tunables for review_open_positions synthetic-exit path.
# Watchlist "kill if forced exits > 25% of trailing 20 fills" needs floor to
# be adjustable without a code deploy. Slippage models the half-spread a real
# SELL would eat vs the posted market mid.
BOT_C_EXIT_EDGE_FLOOR = _env_decimal("BOT_C_EXIT_EDGE_FLOOR", "0.02")
BOT_C_EXIT_SLIPPAGE = _env_decimal("BOT_C_EXIT_SLIPPAGE", "0.02")
MIN_POLYMARKET_SHARES = Decimal("5")  # CLOB rejects orders below this


@dataclass
class CEntryDecision:
    placed: bool
    reason: str
    order_id: str | None = None
    token_id: str | None = None
    limit_price: Decimal | None = None
    size_shares: Decimal | None = None
    size_usd: Decimal | None = None


class BotCExecutor:
    """Fixed-size executor for Bot C paper/live trading."""

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

    def has_existing_position(self, condition_id: str) -> bool:
        with self._sessions() as s:
            n = s.scalar(
                select(func.count()).select_from(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.condition_id == condition_id,
                    Position.status == "OPEN",
                )
            )
        return (n or 0) > 0

    def has_open_order(self, condition_id: str) -> bool:
        with self._sessions() as s:
            n = s.scalar(
                select(func.count()).select_from(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.condition_id == condition_id,
                    # Codex fleet review A-17 (2026-04-22): include
                    # PARTIAL / PAPER_PARTIAL and Polymarket's "live"
                    # resting-order status. Previously only OPEN /
                    # PAPER_OPEN were treated as "already have an
                    # order" so partial-fill + live statuses slipped
                    # through and Bot C could double-enter a market.
                    # F-04: MATCHED = filled, not "open" → excluded.
                    Order.status.in_((
                        "OPEN", "PAPER_OPEN",
                        "PARTIAL", "PAPER_PARTIAL",
                        "live",
                    )),
                )
            )
        return (n or 0) > 0

    def count_open_positions(self) -> int:
        with self._sessions() as s:
            n = s.scalar(
                select(func.count()).select_from(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.status == "OPEN",
                )
            )
        return int(n or 0)

    def aggregate_exposure_usd(self) -> Decimal:
        """Canonical cap input: open position cost basis + open-order notional.

        Previously only counted Position rows — missed pending orders that
        hadn't filled yet, so the bot could accumulate 2x intended exposure.
        Delegates to Portfolio.get_total_exposure for consistency across bots.
        """
        from core.portfolio import Portfolio
        return Portfolio(self._sessions).get_total_exposure(BOT_ID)

    def _choose_token_and_limit(
        self, decision: EdgeDecision
    ) -> tuple[str | None, Decimal | None]:
        """Return (token_id, limit_price) for the side we're buying."""
        market = decision.market
        if decision.side == "BUY_YES":
            token_id = market.yes_token_id
            mid = Decimal(str(decision.market_p_yes))
        elif decision.side == "BUY_NO":
            token_id = market.no_token_id
            # NO price = 1 - YES price on a binary outcome.
            mid = Decimal("1") - Decimal(str(decision.market_p_yes))
        else:
            return None, None
        # Post inside the market on the side we're buying (slightly above the
        # apparent mid to get filled; stays safely below true fair value of ~1).
        limit = (mid + BOT_C_LIMIT_OFFSET).quantize(Decimal("0.001"))
        # Clamp to a sane range.
        if limit <= Decimal("0"):
            limit = Decimal("0.001")
        if limit >= Decimal("0.99"):
            limit = Decimal("0.99")
        return token_id, limit

    def try_enter(self, decision: EdgeDecision) -> CEntryDecision:
        """Attempt to enter a position for one EdgeDecision. Idempotent."""
        if decision.side == "SKIP":
            return CEntryDecision(False, "skip_decision")
        if self.is_halted():
            return CEntryDecision(False, "halted")

        # U-11 (audit 2026-04-18): repo-wide emergency halt check. Bot A,
        # Bot B, Bot D, Bot E all have this at the top of try_enter;
        # Bot C was the gap.
        from core.emergency_halt import is_emergency_halted
        if is_emergency_halted():
            return CEntryDecision(False, "emergency_halt")

        market = decision.market
        gid = market.gamma_id
        if not gid:
            return CEntryDecision(False, "no_gamma_id")

        # Edge threshold (stricter than analysis).
        if abs(Decimal(str(decision.edge))) < BOT_C_MIN_EDGE_FOR_ORDER:
            return CEntryDecision(False, "edge_below_order_threshold")

        # Horizon cap.
        if decision.hours_to_resolution > float(BOT_C_MAX_HOURS_TO_RESOLUTION):
            return CEntryDecision(False, "horizon_too_long")

        # Volume filter.
        if (
            market.volume_24h_usd is not None
            and market.volume_24h_usd < BOT_C_MIN_VOLUME_24H_USD
        ):
            return CEntryDecision(False, "volume_too_low")

        # Dedupe.
        if self.has_existing_position(gid):
            return CEntryDecision(False, "position_exists")
        if self.has_open_order(gid):
            return CEntryDecision(False, "order_exists")

        # Concurrency cap.
        if self.count_open_positions() >= BOT_C_MAX_CONCURRENT_POSITIONS:
            return CEntryDecision(False, "max_concurrent")

        # Aggregate bankroll cap.
        new_exposure = self.aggregate_exposure_usd() + BOT_C_PER_TRADE_USD
        if new_exposure > BOT_C_BANKROLL_USD:
            return CEntryDecision(False, "bankroll_cap")

        token_id, limit_price = self._choose_token_and_limit(decision)
        if not token_id or limit_price is None:
            return CEntryDecision(False, "no_actionable_token")

        # size_shares = notional / price; Polymarket CLOB needs >= 5 shares.
        if limit_price <= 0:
            return CEntryDecision(False, "bad_limit_price")
        size_shares = (BOT_C_PER_TRADE_USD / limit_price).quantize(Decimal("0.01"))
        if size_shares < MIN_POLYMARKET_SHARES:
            return CEntryDecision(
                False, "below_min_size",
                limit_price=limit_price, size_shares=size_shares,
                size_usd=BOT_C_PER_TRADE_USD,
            )

        # U-01 (audit 2026-04-18): cross-bot fleet cap. Bot A/B/E call this
        # pre-trade; Bot C was the gap. Block the trade if the 80% deployable
        # cap would be breached after adding this order's notional.
        from core.fleet import check_fleet_exposure
        fleet_check = check_fleet_exposure(BOT_ID, BOT_C_PER_TRADE_USD)
        if not fleet_check.ok:
            log.info(
                "bot_c.fleet_cap_breach gamma_id=%s intended=%s current=%s cap=%s",
                gid, fleet_check.intended_usd,
                fleet_check.current_total_usd, fleet_check.deployable_cap_usd,
            )
            return CEntryDecision(
                False, "fleet_cap_breach",
                token_id=token_id, limit_price=limit_price,
                size_shares=size_shares, size_usd=BOT_C_PER_TRADE_USD,
            )

        try:
            resp = self.clob.place_limit(
                token_id=token_id,
                price=limit_price,
                size=size_shares,
                side=Side.BUY,
                order_type=OrderType.GTC,
            )
        except Exception as exc:
            log.warning(
                "bot_c.entry.place_failed",
                extra={
                    "gamma_id": gid,
                    "symbol": market.symbol,
                    "token_id": token_id,
                    "limit_price": str(limit_price),
                    "size_shares": str(size_shares),
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                },
            )
            return CEntryDecision(
                False, f"place_failed:{type(exc).__name__}",
                token_id=token_id, limit_price=limit_price,
                size_shares=size_shares, size_usd=BOT_C_PER_TRADE_USD,
            )

        if not resp.order_id or resp.status == "SKIPPED_MIN_SIZE":
            log.info(
                "bot_c.entry.skipped",
                extra={"gamma_id": gid, "status": resp.status, "order_id": resp.order_id},
            )
            return CEntryDecision(
                False, f"skipped:{resp.status}",
                token_id=token_id, limit_price=limit_price,
                size_shares=size_shares, size_usd=BOT_C_PER_TRADE_USD,
            )

        # Record the order AND create a Position row so that bankroll/concurrency
        # caps are binding. (Audit F-03: without Position rows, the caps were dead
        # code — they query Position table which was always empty for bot_c.)
        with self._sessions() as s:
            s.add(
                Order(
                    order_id=resp.order_id,
                    bot_id=BOT_ID,
                    condition_id=gid,
                    token_id=token_id,
                    side="BUY",
                    price=limit_price,
                    size=size_shares,
                    status=resp.status or "OPEN",
                    order_type="GTC",
                )
            )
            # SECURITY_AUDIT.md C-2: do NOT add a Position row here. The
            # Portfolio.on_fill reconciler is the canonical owner of Position
            # state — it creates the row on first fill and updates it on
            # subsequent fills. Adding here would double-count the moment
            # reconciliation runs (it's not wired today, but the latent bug
            # would activate immediately if anyone wires reconcile_live_fills
            # into Bot C's daemon, matching the Bot A/B pattern).
            s.commit()

        log.info(
            "bot_c.entry.placed",
            extra={
                "order_id": resp.order_id,
                "gamma_id": gid,
                "symbol": market.symbol,
                "side": decision.side,
                "limit_price": str(limit_price),
                "size_shares": str(size_shares),
                "size_usd": str(BOT_C_PER_TRADE_USD),
                "edge": f"{decision.edge:+.3f}",
                "mode": "paper" if self.clob.paper_override else (
                    "live" if get_settings().is_live() else "paper"
                ),
            },
        )
        return CEntryDecision(
            True, "placed",
            order_id=resp.order_id,
            token_id=token_id,
            limit_price=limit_price,
            size_shares=size_shares,
            size_usd=BOT_C_PER_TRADE_USD,
        )

    def try_enter_all(self, decisions: list[EdgeDecision]) -> list[CEntryDecision]:
        """Rank by |edge| descending, attempt in order until a cap blocks further entries."""
        actionable = [d for d in decisions if d.side in ("BUY_YES", "BUY_NO")]
        actionable.sort(key=lambda d: abs(d.edge), reverse=True)
        out: list[CEntryDecision] = []
        for d in actionable:
            out.append(self.try_enter(d))
        return out

    # --- Fix 5: edge-collapse exit / stale-order review -----------------------

    def review_open_orders(
        self, decisions: list[EdgeDecision], edge_collapse_threshold: float = 0.03,
    ) -> int:
        """Cancel open orders whose edge has collapsed or flipped.

        For each open Bot C order, find a matching decision (by gamma_id).
        If the re-evaluated net edge is within ±collapse_threshold or has
        flipped sign (we bought YES but now model says BUY_NO), cancel.

        Returns number of orders cancelled.
        """
        from sqlalchemy import select

        with self._sessions() as s:
            open_orders = list(
                s.execute(
                    select(Order).where(
                        Order.bot_id == BOT_ID,
                        # F-04: do NOT include MATCHED — those are filled orders.
                        # Cancelling a filled order is a CLOB no-op but corrupts
                        # our local status tracking (loses the fill record).
                        Order.status.in_(("OPEN", "PAPER_OPEN")),
                    )
                ).scalars().all()
            )
        if not open_orders:
            return 0

        # Build a lookup from gamma_id → latest decision.
        dec_by_gid: dict[str, EdgeDecision] = {}
        for d in decisions:
            dec_by_gid[d.market.gamma_id] = d

        cancelled = 0
        for order in open_orders:
            gid = order.condition_id
            dec = dec_by_gid.get(gid)
            if dec is None:
                # Market not in current scan (possibly closed/expired). Skip for now.
                continue
            original_side = "YES" if order.token_id == dec.market.yes_token_id else "NO"
            edge_for_original_side = dec.net_edge if original_side == "YES" else -dec.net_edge

            should_cancel = False
            reason = ""
            if abs(dec.net_edge) < edge_collapse_threshold:
                should_cancel = True
                reason = f"edge_collapsed |{dec.net_edge:.3f}|<{edge_collapse_threshold}"
            elif edge_for_original_side < 0:
                should_cancel = True
                reason = f"edge_flipped side={original_side} edge={edge_for_original_side:.3f}"

            if should_cancel:
                try:
                    self.clob.cancel_order(order.order_id)
                except Exception as exc:
                    log.warning("bot_c.exit.cancel_failed order_id=%s: %s", order.order_id, exc)
                    continue
                with self._sessions() as s:
                    o = s.get(Order, order.order_id)
                    if o:
                        o.status = "CANCELLED"
                    # Audit fix #2: close the matching Position to prevent phantom
                    # exposure. Without this, bankroll/concurrency caps see a
                    # permanent ghost position from the cancelled order.
                    pos = s.execute(
                        select(Position).where(
                            Position.bot_id == BOT_ID,
                            Position.condition_id == gid,
                            Position.status == "OPEN",
                        )
                    ).scalars().first()
                    if pos:
                        pos.status = "CLOSED"
                    s.commit()
                log.info(
                    "bot_c.exit.cancelled order_id=%s gamma_id=%s reason=%s",
                    order.order_id, gid, reason,
                )
                cancelled += 1

        return cancelled

    def review_open_positions(
        self,
        decisions: list[EdgeDecision],
        edge_floor: Decimal | float | None = None,
    ) -> int:
        """Exit filled positions whose refreshed edge collapsed or flipped.

        ``review_open_orders`` protects resting orders. This method protects
        already-filled positions, which otherwise hold to resolution even when
        the repricing signal is gone.

        Paper-only path. Live mode raises because the exit writes a synthetic
        SELL directly to the portfolio without touching the CLOB; if bot_c
        is ever flipped to live, a real SELL-order submission must be wired
        in before this method can be trusted.
        """
        if not self.clob.paper_override:
            raise RuntimeError(
                "bot_c.review_open_positions is paper-only; live SELL path "
                "not implemented. Refusing to write synthetic exits that "
                "would leave on-chain positions orphaned."
            )

        from core.portfolio import Portfolio

        floor = (
            Decimal(str(edge_floor))
            if edge_floor is not None
            else BOT_C_EXIT_EDGE_FLOOR
        )
        slippage = BOT_C_EXIT_SLIPPAGE

        with self._sessions() as s:
            open_positions = list(
                s.execute(
                    select(Position).where(
                        Position.bot_id == BOT_ID,
                        Position.status == "OPEN",
                    )
                ).scalars().all()
            )
        if not open_positions:
            return 0

        dec_by_gid: dict[str, EdgeDecision] = {}
        for d in decisions:
            if d.market.gamma_id:
                dec_by_gid[d.market.gamma_id] = d

        exited = 0
        portfolio = Portfolio(self._sessions)
        now = datetime.now(UTC)
        for pos in open_positions:
            dec = dec_by_gid.get(pos.condition_id)
            if dec is None:
                continue

            pos_is_yes = pos.token_id == dec.market.yes_token_id
            edge_for_side = (
                Decimal(str(dec.net_edge))
                if pos_is_yes
                else -Decimal(str(dec.net_edge))
            )

            should_exit = False
            reason = ""
            if abs(edge_for_side) < floor:
                should_exit = True
                reason = f"edge_decayed |{edge_for_side:+.3f}|<{floor}"
            elif edge_for_side < 0:
                should_exit = True
                reason = (
                    f"edge_flipped side={'YES' if pos_is_yes else 'NO'} "
                    f"edge={edge_for_side:+.3f}"
                )

            if not should_exit:
                continue

            # Discount posted mid by slippage to model the half-spread a
            # real SELL would pay. Paper P&L now tracks what a realistic
            # exit would have fetched, not the model-view mid.
            mkt_yes = Decimal(str(dec.market_p_yes))
            mid_for_side = mkt_yes if pos_is_yes else (Decimal("1") - mkt_yes)
            exit_px = mid_for_side - slippage
            exit_px = max(Decimal("0"), min(Decimal("1"), exit_px))
            try:
                portfolio.on_fill(
                    bot_id=BOT_ID,
                    trade_id=f"bot_c-pos-exit-{pos.id}-{int(now.timestamp())}",
                    order_id=None,
                    condition_id=pos.condition_id,
                    token_id=pos.token_id,
                    side="SELL",
                    price=exit_px,
                    size=pos.size,
                    fee_usd=Decimal("0"),
                    filled_at=now,
                )
            except Exception as exc:
                log.warning(
                    "bot_c.position_exit.failed pos_id=%s gamma_id=%s: %s",
                    pos.id, pos.condition_id, exc,
                )
                continue

            log.info(
                "bot_c.position_exit.closed pos_id=%s gamma_id=%s side=%s "
                "size=%s exit_px=%s reason=%s",
                pos.id, pos.condition_id, "YES" if pos_is_yes else "NO",
                pos.size, exit_px, reason,
            )
            exited += 1
        return exited
