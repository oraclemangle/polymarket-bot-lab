"""Bot A — order placement / cancellation layer.

Thin shim that:
  1. Refuses to act if the bot is halted (HaltFlag).
  2. Respects per-market "no existing position" invariant.
  3. Delegates to `core/clob.py` for actual submission.
  4. Records the Order row for audit.

Entry helper: `try_enter(candidate, bankroll_usd, depth_usd)`
Exit helpers: `try_cut_loss(position)`, `try_redeem(position, usdc_received)`
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select

from bots.bot_a.config import (
    ABNORMAL_EXIT_YES_PRICE,
    REEVAL_EXIT_YES_PRICE,
    REEVAL_VOLUME_DOUBLE_MULT,
    AGGREGATE_EXPOSURE_CAP_USD,
    BOT_ID,
    EXEC_POLICY_ENABLED,
    EXEC_POLICY_FLOW_LOOKBACK_S,
    EXEC_POLICY_TOXICITY_FREEZE,
    EXEC_POLICY_TOXICITY_PLACE_BLOCK,
    MIN_ORDER_SHARES,
)
from bots.bot_a.filters import Candidate
from bots.bot_a.flow_source import build_flow_window
from bots.bot_a.sizer import shares_from_notional, size_position
from core.clob_v2 import ClobWrapperV2 as ClobWrapper, OrderType, Side
from core.db import HaltFlag, Order, Position, get_session_factory
from core.exec_policy import LadderPolicy, should_place
from core.portfolio import Portfolio

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


@dataclass
class EntryDecision:
    placed: bool
    order_id: str | None = None
    reason: str | None = None
    size_usd: Decimal | None = None


class BotAExecutor:
    def __init__(
        self,
        clob: ClobWrapper,
        portfolio: Portfolio | None = None,
        session_factory=None,
        exec_policy: LadderPolicy | None = None,
        flow_source=None,
    ):
        self.clob = clob
        self.portfolio = portfolio or Portfolio()
        self._sessions = session_factory or get_session_factory()
        # Exec-policy integration (ADR-031). Default None => behaviour unchanged.
        # When EXEC_POLICY_ENABLED is set and no explicit policy is passed,
        # construct one from config; test code passes exec_policy=LadderPolicy()
        # directly to exercise the gate without touching env.
        self.exec_policy = exec_policy if exec_policy is not None else (
            LadderPolicy(
                toxicity_place_block_threshold=EXEC_POLICY_TOXICITY_PLACE_BLOCK,
                toxicity_freeze_threshold=EXEC_POLICY_TOXICITY_FREEZE,
            ) if EXEC_POLICY_ENABLED else None
        )
        self._flow_source = flow_source or build_flow_window

    def _log_shadow_signal(self, candidate, rejection_reason: str) -> None:
        """Log what we WOULD have traded to an Event row.

        Session 17 (2026-04-16): preserves signal data even when the bot
        is halted or otherwise blocked, so operators can evaluate whether
        the edge still works while live trading is paused. Read via
        SELECT * FROM events WHERE event_type='bot_a.shadow.signal'.
        """
        try:
            from core.db import Event
            with self._sessions() as s:
                s.add(Event(
                    bot_id=BOT_ID,
                    event_type="bot_a.shadow.signal",
                    severity="info",
                    message=f"would-have-traded: blocked={rejection_reason}",
                    payload={
                        "condition_id": candidate.condition_id,
                        "yes_price": str(candidate.best_yes_ask),
                        "blocked_by": rejection_reason,
                    },
                ))
                s.commit()
        except Exception as e:
            log.debug("bot_a.shadow_signal_log_failed err=%s", e)

    def is_halted(self) -> bool:
        with self._sessions() as s:
            flag = s.get(HaltFlag, BOT_ID)
            return bool(flag and flag.halted)

    def has_existing_position(self, condition_id: str) -> bool:
        with self._sessions() as s:
            existing = s.scalars(
                select(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.condition_id == condition_id,
                    Position.status == "OPEN",
                )
            ).first()
            return existing is not None

    def has_open_order(self, condition_id: str) -> bool:
        with self._sessions() as s:
            existing = s.scalars(
                select(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.condition_id == condition_id,
                    Order.status.in_(("OPEN", "PARTIAL", "PAPER_OPEN", "live")),
                )
            ).first()
            return existing is not None

    def aggregate_exposure_usd(self) -> Decimal:
        # Cap must include pending open orders; otherwise a flurry of entries
        # before any fills reconcile sails through even a tight cap.
        return self.portfolio.get_total_exposure(BOT_ID)

    def try_enter(
        self,
        candidate: Candidate,
        bankroll_usd: Decimal,
        depth_usd: Decimal | None = None,
    ) -> EntryDecision:
        if self.is_halted():
            # Session 17 (2026-04-16): minimum viable paper-shadow.
            # When halted (manual halt, drawdown kill, bankroll exhausted),
            # log what we WOULD have traded so operators can evaluate
            # whether the edge still works while the bot is paused.
            # Full paper-shadow daemon (separate process, paper fills,
            # shadow P&L tracking) is deferred — this is the first-order
            # data-preservation primitive.
            self._log_shadow_signal(candidate, "halted")
            return EntryDecision(placed=False, reason="halted")
        # Emergency repo-wide halt (Phase 3, audit 2026-04-17 M-2).
        from core.emergency_halt import is_emergency_halted
        if is_emergency_halted():
            self._log_shadow_signal(candidate, "emergency_halt")
            return EntryDecision(placed=False, reason="emergency_halt")
        if self.has_existing_position(candidate.condition_id):
            return EntryDecision(placed=False, reason="position_exists")
        if self.has_open_order(candidate.condition_id):
            return EntryDecision(placed=False, reason="order_exists")
        if candidate.no_token_id is None:
            return EntryDecision(placed=False, reason="no_no_token")

        depth = depth_usd if depth_usd is not None else candidate.no_ask_depth_within_2c_usd
        notional = size_position(bankroll_usd, depth)
        if notional <= Decimal("0"):
            return EntryDecision(placed=False, reason="zero_size")

        # Aggregate cap check.
        if self.aggregate_exposure_usd() + notional > AGGREGATE_EXPOSURE_CAP_USD:
            return EntryDecision(placed=False, reason="aggregate_cap")

        # Fleet cap check (audit 2026-04-17, atomic pre-trade).
        # Blocks any trade that would push cross-bot exposure above the
        # deployable fraction of the fleet wallet.
        from core.fleet import check_fleet_exposure
        fleet_check = check_fleet_exposure("bot_a", notional)
        if not fleet_check.ok:
            return EntryDecision(placed=False, reason="fleet_cap_breach")

        # Exec-policy toxicity gate (ADR-031). Only runs when a policy is wired.
        # Bot A fades tail markets where aggressive flow against our NO_BUY side
        # (= aggressive SELL on the NO token, i.e. dumpers hitting our bid) is
        # an adverse-selection signal. The shadow_signal log captures blocked
        # markets for the 7-day paper-measurement comparison. If the flow
        # source itself fails, default to allowing the trade — exec-policy
        # must never block trading on its own infrastructure failure.
        if self.exec_policy is not None:
            try:
                flow = self._flow_source(
                    market_id=candidate.condition_id,
                    lookback_s=EXEC_POLICY_FLOW_LOOKBACK_S,
                )
                ok, reason = should_place(self.exec_policy, "NO_BUY", flow)
                if not ok:
                    self._log_shadow_signal(candidate, f"exec_policy:{reason}")
                    return EntryDecision(placed=False, reason=f"exec_policy:{reason}")
            except Exception as e:  # pragma: no cover
                log.warning("bot_a.exec_policy.unavailable err=%s", e)

        # Limit price: (1 − best_yes_ask). Canonical NO price equivalent.
        limit_price = (Decimal("1") - candidate.best_yes_ask).quantize(Decimal("0.01"))
        # Safety: NO-side price should be > 0.9 given YES ≤ 0.05.
        if limit_price < Decimal("0.90"):
            return EntryDecision(placed=False, reason="implied_no_price_too_low")

        size_shares = shares_from_notional(notional, limit_price)
        if size_shares < MIN_ORDER_SHARES:
            return EntryDecision(placed=False, reason="below_min_size", size_usd=notional)

        try:
            resp = self.clob.place_limit(
                token_id=candidate.no_token_id,
                price=limit_price,
                size=size_shares,
                side=Side.BUY,
                order_type=OrderType.GTC,
            )
        except Exception as e:
            log.warning("bot_a.entry.place_failed", extra={"condition_id": candidate.condition_id, "error": str(e)[:300]})
            return EntryDecision(placed=False, reason=f"place_failed: {type(e).__name__}", size_usd=notional)

        # Record.
        with self._sessions() as s:
            s.add(
                Order(
                    order_id=resp.order_id,
                    bot_id=BOT_ID,
                    condition_id=candidate.condition_id,
                    token_id=candidate.no_token_id,
                    side="BUY",
                    price=limit_price,
                    size=size_shares,
                    status=resp.status or "OPEN",
                    order_type="GTC",
                )
            )
            # A-2: entry-time slippage/fill-quality instrumentation.
            # Captures what we INTENDED at placement; a fill-time pair
            # (bot_a.fill.quality) will be emitted by reconcile_live_fills
            # once OQ-030 lands, letting us compute realised slippage =
            # actual_fill_price - requested_limit_price over resolved trades.
            # These events are the execution-quality dataset Bot A's
            # expected-edge math currently assumes away.
            try:
                from core.db import Event
                s.add(Event(
                    bot_id=BOT_ID,
                    event_type="bot_a.entry.quality",
                    severity="info",
                    message="entry placed (requested params)",
                    payload={
                        "order_id": resp.order_id,
                        "condition_id": candidate.condition_id,
                        "requested_limit_price": str(limit_price),
                        "requested_size_shares": str(size_shares),
                        "requested_notional_usd": str(notional),
                        "best_yes_ask_at_request": str(candidate.best_yes_ask),
                        "no_ask_depth_within_2c_usd": str(
                            candidate.no_ask_depth_within_2c_usd
                        ),
                        "volume_24h_usd": str(candidate.volume_24h_usd),
                    },
                ))
            except Exception as e:  # pragma: no cover — instrumentation must never block a trade
                log.debug("bot_a.entry_quality_log_failed err=%s", e)
            s.commit()
        log.info(
            "bot_a.entry.placed",
            extra={
                "order_id": resp.order_id,
                "condition_id": candidate.condition_id,
                "size_shares": str(size_shares),
                "limit_price": str(limit_price),
                "notional_usd": str(notional),
            },
        )
        return EntryDecision(
            placed=True, order_id=resp.order_id, size_usd=notional
        )

    def should_cut_loss(
        self,
        current_yes_price: Decimal,
        entry_volume_usd: Decimal | None = None,
        current_volume_usd: Decimal | None = None,
    ) -> bool:
        """Two-level abnormal-exit decision (Phase 3 audit 2026-04-17).

        Hard exit at `ABNORMAL_EXIT_YES_PRICE` (default 0.25) unconditional.
        Re-evaluate trigger at `REEVAL_EXIT_YES_PRICE` (default 0.15):
        exit only if 24h volume has doubled since entry — a signal that
        the repricing is driven by genuine news flow, not thin-liquidity
        noise. When entry/current volume aren't available (e.g. historical
        positions pre-dating this field), fall back to hard-exit-only
        behavior.
        """
        if current_yes_price >= ABNORMAL_EXIT_YES_PRICE:
            return True
        if current_yes_price < REEVAL_EXIT_YES_PRICE:
            return False
        # In the re-eval band [REEVAL, ABNORMAL). Require volume-doubling.
        if entry_volume_usd is None or current_volume_usd is None:
            return False
        if entry_volume_usd <= 0:
            return False
        return current_volume_usd >= entry_volume_usd * REEVAL_VOLUME_DOUBLE_MULT

    def try_cut_loss(self, position: Position, best_yes_price: Decimal) -> bool:
        """If `best_yes_price >= ABNORMAL_EXIT_YES_PRICE`, submit a SELL at
        (1 − best_yes_price − safety_buffer) to exit at or near market.

        Returns True if an exit order was submitted.
        """
        if not self.should_cut_loss(best_yes_price):
            return False
        if position.size <= Decimal("0"):
            return False
        # NO price = 1 - YES price; give up 1¢ to ensure fill.
        exit_price = (Decimal("1") - best_yes_price - Decimal("0.01")).quantize(
            Decimal("0.01")
        )
        resp = self.clob.place_limit(
            token_id=position.token_id,
            price=exit_price,
            size=position.size,
            side=Side.SELL,
            order_type=OrderType.GTC,
        )
        with self._sessions() as s:
            s.add(
                Order(
                    order_id=resp.order_id,
                    bot_id=BOT_ID,
                    condition_id=position.condition_id,
                    token_id=position.token_id,
                    side="SELL",
                    price=exit_price,
                    size=position.size,
                    status=resp.status or "OPEN",
                    order_type="GTC",
                )
            )
            s.commit()
        log.info(
            "bot_a.exit.cut_loss",
            extra={
                "order_id": resp.order_id,
                "condition_id": position.condition_id,
                "best_yes_price": str(best_yes_price),
            },
        )
        return True

    def cancel_stale_orders(self, older_than_hours: int) -> int:
        """Cancel any resting BUY that has sat past `older_than_hours`.

        Bot A's longshot edge relies on getting inside the spread; when the
        tail price drifts away, a stale order is not participating and just
        occupies our exposure cap. Cancelling frees capital for fresher
        candidates on the next tick.
        """
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)
        with self._sessions() as s:
            stale = list(
                s.scalars(
                    select(Order).where(
                        Order.bot_id == BOT_ID,
                        Order.side == "BUY",
                        Order.status.in_(("OPEN", "PARTIAL", "PAPER_OPEN", "live")),
                        Order.placed_at < cutoff,
                    )
                )
            )
        count = 0
        for o in stale:
            try:
                if self.clob.cancel_order(o.order_id):
                    count += 1
                    with self._sessions() as s:
                        db_o = s.get(Order, o.order_id)
                        if db_o is not None:
                            db_o.status = "CANCELLED"
                            s.commit()
            except Exception as e:
                log.warning(
                    "bot_a.stale_cancel.failed",
                    extra={"order_id": o.order_id, "error": str(e)},
                )
        return count

    def cancel_all(self) -> int:
        """Cancel every open order for Bot A. Used by watchdog kill-switch.

        Kill-switch latency matters: issue a single bulk cancel first,
        then walk the DB to update local status and catch orders placed
        between the query and the bulk call.
        """
        try:
            bulk_n = self.clob.cancel_all()
            log.info("bot_a.cancel_all.bulk", extra={"cancelled": bulk_n})
        except Exception as e:
            log.warning(
                "bot_a.cancel_all.bulk_failed",
                extra={"error": f"{type(e).__name__}: {e}"[:300]},
            )
        with self._sessions() as s:
            open_orders = list(
                s.scalars(
                    select(Order).where(
                        Order.bot_id == BOT_ID,
                        Order.status.in_(("OPEN", "PARTIAL", "PAPER_OPEN", "live")),
                    )
                )
            )
        count = 0
        for o in open_orders:
            try:
                if self.clob.cancel_order(o.order_id):
                    count += 1
                    with self._sessions() as s:
                        db_o = s.get(Order, o.order_id)
                        if db_o is not None:
                            db_o.status = "CANCELLED"
                            s.commit()
            except Exception as e:
                log.warning(
                    "bot_a.cancel.failed", extra={"order_id": o.order_id, "error": str(e)}
                )
        return count
