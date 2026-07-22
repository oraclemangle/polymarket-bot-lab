"""Bot E — executor.

Receives `ObiSignal` objects, applies risk filters (halts, caps, stale-feed,
time-to-resolution window, maker price sanity), computes position size, and
either places a maker-only limit order (live/paper) or logs it (dry-run).

Schema additions per ADR-022 / Codex C-S4: every trade/order carries
a three-tier tag:
- `strategy_signal` (primary): "obi_yes" | "obi_no" | "manual_override"
- `reason_code` (secondary, five-question enum): stored in existing column
  where possible; falls back to "liquidity_weak" for OBI since imbalance is
  fundamentally a liquidity-weakness signal
- `reason_detail` (tertiary, free text): optional

Halts wired (v96/Grok/Codex union):
- consecutive-loss halt (5 in 10 min)
- trailing-loss halt (12 of last 20)
- daily-loss kill (-18%)
- global-drawdown kill (-35%)
- stale-feed halt (>500 ms)
- feed-divergence halt (>100 bps between sources)

In v1 only stale-feed + consecutive-loss are active; others are scaffolded
and can be enabled from config without code changes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from bots.bot_e_btc_scalp.signal import ObiSignal
from bots.bot_e_btc_scalp.sizer import OpenPosition, size_maker_entry

log = logging.getLogger(__name__)

BOT_ID = "bot_e"

# --- Primary tag enum (strategy_signal column) ---
TAG_OBI_YES = "obi_yes"
TAG_OBI_NO = "obi_no"
TAG_MANUAL = "manual_override"

# --- Secondary tag enum (reason_code column, five-question framing) ---
REASON_LIQUIDITY_WEAK = "liquidity_weak"


@dataclass
class EntryDecision:
    """Outcome of `try_enter`."""
    accepted: bool
    reason: str                         # human-readable rejection or "placed"
    strategy_signal: str | None = None  # primary tag
    reason_code: str | None = None      # secondary tag (five-question enum)
    reason_detail: str | None = None    # tertiary free text
    order_id: str | None = None
    limit_price: Decimal | None = None
    notional_usd: Decimal | None = None
    shares: Decimal | None = None


@dataclass
class TraderState:
    """In-process state tracking halts, recent results, and open positions.

    NOT persisted to DB here; assumption is the executor is instantiated once
    per `run_loop` cycle by __main__ and reads persistent state from core.db
    as needed.
    """
    recent_outcomes: list[bool] = field(default_factory=list)  # True = win
    consecutive_losses: int = 0
    consecutive_loss_streak_started_ms: int = 0
    open_positions: list[OpenPosition] = field(default_factory=list)
    last_stale_feed_ms: int = 0


def _opposite_side(side: str) -> str:
    return "BUY_NO" if side == "BUY_YES" else "BUY_YES"


def _compute_maker_limit(
    *,
    signal_side: str,
    yes_price: Decimal | None,
    no_price: Decimal | None,
    maker_offset: Decimal,
    order_style_override: str | None = None,  # deprecated; retained for call-site compat
) -> Decimal | None:
    """Compute maker-only limit price for entry.

    BUY_YES: yes_price - offset
    BUY_NO:  no_price - offset

    Return None if we don't have price data.

    NOTE (2026-04-17 audit fix, P0 from all three reviewers): the earlier
    `order_style_override="taker"` path has been REMOVED. That path bid
    above the bid-derived mid rather than crossing the real touch, so it
    was neither a faithful taker model nor a maker model — it produced
    paper fills that could not be reproduced live and systematically biased
    calibration. See `docs/audit/bots-a-d-e-audit-responses/` Q20/Q23.

    `order_style_override` is kept in the signature so legacy call sites
    don't raise; any non-"maker" value is ignored with a warning.
    """
    if order_style_override is not None and order_style_override != "maker":
        log.warning(
            "bot_e.order_style_override=%s IGNORED — maker-only enforced (audit 2026-04-17)",
            order_style_override,
        )
    if signal_side == "BUY_YES":
        if yes_price is None or yes_price <= 0:
            return None
        limit = (yes_price - maker_offset).quantize(Decimal("0.001"))
    else:
        if no_price is None or no_price <= 0:
            return None
        limit = (no_price - maker_offset).quantize(Decimal("0.001"))
    return max(Decimal("0.001"), min(Decimal("0.99"), limit))


def try_enter(
    signal: ObiSignal,
    state: TraderState,
    *,
    bankroll_usd: Decimal,
    fixed_trade_usd: Decimal,
    per_trade_cap_frac: Decimal,
    crypto_bucket_cap_frac: Decimal,
    aggregate_cap_frac: Decimal,
    maker_offset: Decimal,
    maker_only: bool,
    stale_feed_ms: float,
    consecutive_loss_halt_n: int,
    is_halted: bool,
    dry_run: bool,
    last_feed_age_ms: int,
    symbol: str,
    minutes_to_resolution: float,
    entry_window_min_sec: float,
    entry_window_max_sec: float,
    order_style: str = "maker",
    # Audit 2026-04-17 (Q21) — correlation-adjusted crypto bucket cap.
    crypto_correlation_adj: bool = False,
    crypto_avg_correlation: Decimal = Decimal("0"),
) -> EntryDecision:
    """Full pre-trade chain: halts → freshness → timing → sizing → place.

    Returns `EntryDecision` indicating what happened. Actual CLOB placement
    is done in `_place_maker_order` below (extracted so tests can run without
    a live ClobWrapper).
    """
    # --- Halts ---
    if is_halted:
        return EntryDecision(accepted=False, reason="halted")

    if state.consecutive_losses >= consecutive_loss_halt_n:
        return EntryDecision(accepted=False, reason="consecutive_loss_halt")

    # --- Per-market dedup (Session 17f audit 2026-04-17).
    # Without this, OBI staying above threshold for N scan iterations
    # results in N duplicate orders on the same market. Observed 2026-04-17
    # 10:35 UTC: 12 paper fills on cid 0xa52c... in 50s as the bot
    # re-fired every 5s. Calibration samples are NOT independent under
    # that pattern (same outcome recorded 12 times).
    # Matches Bot A/B/D `has_existing_position` guard.
    if any(
        p.subscription_id == signal.subscription_id for p in state.open_positions
    ):
        return EntryDecision(accepted=False, reason="position_exists")

    # --- Feed freshness ---
    if last_feed_age_ms > stale_feed_ms:
        return EntryDecision(accepted=False, reason=f"stale_feed:{last_feed_age_ms}ms")

    # --- Time-to-resolution window ---
    t_sec = minutes_to_resolution * 60
    if t_sec < entry_window_min_sec:
        return EntryDecision(accepted=False, reason=f"past_entry_window:{t_sec:.0f}s")
    if t_sec > entry_window_max_sec:
        return EntryDecision(accepted=False, reason=f"pre_entry_window:{t_sec:.0f}s")

    # --- Maker-only guard ---
    # v1 live should always be maker-only. Paper mode may explicitly opt
    # into taker via order_style="taker" so paper trades actually fill.
    if not maker_only and order_style != "taker":
        log.warning("bot_e.maker_only_disabled env=? would become taker")
        return EntryDecision(accepted=False, reason="maker_only_required")

    limit = _compute_maker_limit(
        order_style_override=order_style,
        signal_side=signal.side,
        yes_price=signal.yes_price,
        no_price=signal.no_price,
        maker_offset=maker_offset,
    )
    if limit is None:
        return EntryDecision(accepted=False, reason="no_price_for_maker_limit")

    # --- Size ---
    sizing = size_maker_entry(
        signal_side=signal.side,
        limit_price=limit,
        bankroll_usd=bankroll_usd,
        fixed_trade_usd=fixed_trade_usd,
        per_trade_cap_frac=per_trade_cap_frac,
        crypto_bucket_cap_frac=crypto_bucket_cap_frac,
        aggregate_cap_frac=aggregate_cap_frac,
        open_positions=state.open_positions,
        symbol=symbol,
        is_crypto=True,
        crypto_correlation_adj=crypto_correlation_adj,
        crypto_avg_correlation=crypto_avg_correlation,
    )
    if not sizing.can_enter:
        return EntryDecision(accepted=False, reason=sizing.reason,
                             limit_price=limit,
                             notional_usd=sizing.proposed_notional,
                             shares=sizing.proposed_shares)

    tag_primary = TAG_OBI_YES if signal.side == "BUY_YES" else TAG_OBI_NO
    reason_detail = (
        f"obi={signal.obi:+.3f} win={signal.window_sec:.0f}s "
        f"n_trades={signal.n_trades} vol={signal.total_volume}"
    )

    if dry_run:
        log.info(
            "bot_e.dry_run side=%s limit=%s shares=%s notional=%s obi=%.3f",
            signal.side, limit, sizing.proposed_shares,
            sizing.proposed_notional, signal.obi,
        )
        return EntryDecision(
            accepted=True, reason="dry_run",
            strategy_signal=tag_primary,
            reason_code=REASON_LIQUIDITY_WEAK,
            reason_detail=reason_detail,
            limit_price=limit,
            notional_usd=sizing.proposed_notional,
            shares=sizing.proposed_shares,
        )

    # Live/paper placement deferred to caller (integration with ClobWrapper
    # happens in __main__.py — executor stays framework-free for testability).
    return EntryDecision(
        accepted=True, reason="placed",
        strategy_signal=tag_primary,
        reason_code=REASON_LIQUIDITY_WEAK,
        reason_detail=reason_detail,
        limit_price=limit,
        notional_usd=sizing.proposed_notional,
        shares=sizing.proposed_shares,
    )


def record_outcome(
    state: TraderState,
    *,
    win: bool,
    now_ms: int,
) -> None:
    """Update halt state after a trade resolves."""
    state.recent_outcomes.append(win)
    if not win:
        state.consecutive_losses += 1
        if state.consecutive_loss_streak_started_ms == 0:
            state.consecutive_loss_streak_started_ms = now_ms
    else:
        state.consecutive_losses = 0
        state.consecutive_loss_streak_started_ms = 0
    # Trim tail — last N outcomes only
    if len(state.recent_outcomes) > 100:
        state.recent_outcomes = state.recent_outcomes[-100:]


def should_halt_trailing(
    state: TraderState,
    *,
    trailing_n: int,
    trailing_window: int,
) -> bool:
    """True if >= `trailing_n` of last `trailing_window` outcomes are losses."""
    recent = state.recent_outcomes[-trailing_window:]
    if len(recent) < trailing_window:
        return False
    losses = sum(1 for w in recent if not w)
    return losses >= trailing_n
