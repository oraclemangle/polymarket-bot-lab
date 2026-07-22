"""Bot A thresholds and caps.  Single source of truth.

Derived defaults from specs/bot-a-spec.md §"Risk controls" and §"Market selection filters".
Most values are env-overridable via BOT_A_* env vars, but the category set
and question blacklist are deliberately code-level (require review to change).
"""

from __future__ import annotations

import os
from decimal import Decimal

BOT_ID = "bot_a"

# --- Market selection filters ---
TARGET_CATEGORIES: frozenset[str] = frozenset(
    {"geopolitics", "politics", "finance", "economics"}
)

# Fade the far tail: only when YES is priced at or below this.
MAX_YES_ENTRY_PRICE: Decimal = Decimal("0.05")

# Ensure exit optionality if thesis breaks.
MIN_24H_VOLUME_USD: Decimal = Decimal("5000")

# Window to resolution: short enough to compound, long enough to avoid event variance.
# 14 is the aggressive end of "fade the tail" — below this, pricing is news-driven
# and the structural longshot bias weakens. Env-overridable.
MIN_DAYS_TO_RESOLUTION: int = int(os.environ.get("BOT_A_MIN_DAYS_TO_RESOLUTION", "21"))
MAX_DAYS_TO_RESOLUTION: int = int(os.environ.get("BOT_A_MAX_DAYS_TO_RESOLUTION", "180"))

# Depth at NO-ask within 2¢ of mid — ensures fill at touch without slippage.
MIN_NO_ASK_DEPTH_USD: Decimal = Decimal("500")
DEPTH_WIDTH_CENTS: Decimal = Decimal("0.02")

# Manual blacklist — seed list; curate as Bot A surfaces questionable markets.
# Phrases matched case-insensitively against `question`.
QUESTION_BLACKLIST: tuple[str, ...] = (
    "assassinat",
    "killed by",
    "dies by",
    "murder",
    "suicide",
    "nuclear strike",
    "chemical attack",
    "biological attack",
)

# --- Sizing ---
ENTRY_SIZE_USD: Decimal = Decimal(os.environ.get("BOT_A_ENTRY_SIZE_USD", "30"))
BANKROLL_FRACTION_CAP: Decimal = Decimal(os.environ.get("BOT_A_BANKROLL_FRACTION_CAP", "0.05"))
BOOK_DEPTH_FRACTION_CAP: Decimal = Decimal(os.environ.get("BOT_A_BOOK_DEPTH_FRACTION_CAP", "0.05"))

# Polymarket CLOB enforces a 5-share minimum per order. Orders below this
# are rejected with HTTP 400 "Size lower than the minimum: 5".
MIN_ORDER_SHARES: Decimal = Decimal("5")

# --- Risk controls ---
# Exposure cap defaults to BANKROLL × 1.0 so the operator-facing
# BOT_A_BANKROLL_GBP variable IS the cap by default. Pre-Session-14 the
# cap defaulted to a hardcoded $1000 with no link to bankroll, which let
# Bot A spend up to $1000 even when bankroll was set to ~$200 — the bug
# that caused the Session 14 emergency. Operators who want a wider cap
# than bankroll can still override BOT_A_EXPOSURE_CAP_USD explicitly.
def _default_exposure_cap_usd() -> Decimal:
    explicit = os.environ.get("BOT_A_EXPOSURE_CAP_USD")
    if explicit:
        return Decimal(explicit)
    bankroll_gbp = os.environ.get("BOT_A_BANKROLL_GBP")
    if bankroll_gbp:
        gbp_usd = Decimal(os.environ.get("DEFAULT_GBP_USD_RATE", "1.35"))
        return Decimal(bankroll_gbp) * gbp_usd
    return Decimal("1000")  # legacy fallback when neither env var is set


AGGREGATE_EXPOSURE_CAP_USD: Decimal = _default_exposure_cap_usd()
DISPUTE_STREAK_HALT_COUNT: int = 3

# --- Exit thresholds ---
# Phase 3 audit 2026-04-17 (GLM-5.1 Q7 / Gemini / Codex): two-level abnormal
# exit. The hard stop stays at 0.25 (5× entry), but we add a re-evaluate
# trigger at 0.15 (3× entry) that exits if same-day volume has doubled since
# entry (genuine news-driven repricing). Env-overridable so operator can
# revert to the single-level behavior by setting REEVAL = 0.25.
ABNORMAL_EXIT_YES_PRICE: Decimal = Decimal(
    os.environ.get("BOT_A_ABNORMAL_EXIT_YES_PRICE", "0.25")
)
REEVAL_EXIT_YES_PRICE: Decimal = Decimal(
    os.environ.get("BOT_A_REEVAL_EXIT_YES_PRICE", "0.15")
)
# Volume-doubling multiplier for re-evaluate trigger. If 24h volume at
# re-eval time >= (volume_at_entry * this), exit at the re-eval price.
REEVAL_VOLUME_DOUBLE_MULT: Decimal = Decimal(
    os.environ.get("BOT_A_REEVAL_VOLUME_DOUBLE_MULT", "2.0")
)

# --- Liveness ---
BOOK_STALE_SECONDS: int = 300  # 5 min per spec
SCRAPER_STALE_MINUTES: int = 30

# Cancel resting BUYs older than this so the tail-price window we priced into
# doesn't drift while we sit idle. The next tick rebuilds and reposts.
# Phase 3 audit: reduced from 6h to 2h. A 6-hour stale NO bid sitting on a
# fast-moving tail-probability market could be swept by a news-aggregator bot
# after the market has already repriced. Env-overridable.
REPOST_STALE_HOURS: int = int(os.environ.get("BOT_A_REPOST_STALE_HOURS", "2"))


def bankroll_usd(bot_a_bankroll_gbp: Decimal, gbp_to_usd: Decimal) -> Decimal:
    """Convert GBP bankroll to USD for per-market sizing math."""
    return bot_a_bankroll_gbp * gbp_to_usd


# --- Exec-policy integration (ADR-031) ---
#
# MVP wiring: toxicity-block-on-placement only. Ladder stepping is deliberately
# disabled for Bot A because tail-fade edge requires price patience — stepping
# a 5c NO-buy toward 10c kills the strategy. The existing `cancel_stale_orders`
# helper already handles age-based cancellation at a Bot-A-appropriate cadence
# (REPOST_STALE_HOURS, default 2h).
#
# Default EXEC_POLICY_ENABLED=false. Operator flips it on the bot host to begin the
# 7-day paper measurement period per ADR-031 rollout sequence. The flow source
# used when enabled is `bots/bot_a/flow_source.py::build_flow_window`, currently
# a zero-flow stub (toxicity always = 0, should_place always allows). Real flow
# source is a follow-up task documented in flow_source.py.
EXEC_POLICY_ENABLED: bool = os.environ.get("BOT_A_EXEC_POLICY_ENABLED", "false").lower() in ("1", "true", "yes")
EXEC_POLICY_TOXICITY_PLACE_BLOCK: float = float(
    os.environ.get("BOT_A_EXEC_TOX_PLACE_BLOCK", "0.80")
)
EXEC_POLICY_TOXICITY_FREEZE: float = float(
    os.environ.get("BOT_A_EXEC_TOX_FREEZE", "0.70")
)
EXEC_POLICY_FLOW_LOOKBACK_S: int = int(
    os.environ.get("BOT_A_EXEC_FLOW_LOOKBACK_S", "60")
)
