"""Bot Longshot Fade (G) — env-var config.

See ADR-036 for thesis + backtest evidence backing these defaults.
"""
from __future__ import annotations

import os
from decimal import Decimal

BOT_ID = os.environ.get("BOT_G_ID_OVERRIDE", "bot_g")


def _env_decimal(key: str, default: str) -> Decimal:
    return Decimal(os.environ.get(key, default))


def _env_float(key: str, default: str) -> float:
    return float(os.environ.get(key, default))


def _env_int(key: str, default: str) -> int:
    return int(os.environ.get(key, default))


def _env_bool(key: str, default: str) -> bool:
    return os.environ.get(key, default).lower() in ("true", "1", "yes", "on")


# --- Execution mode ----------------------------------------------------------

# Paper-only in v0 — operator must explicitly flip this to go live.
BOT_G_ENV = os.environ.get("BOT_G_ENV", "paper")
BOT_G_DRY_RUN = _env_bool("BOT_G_DRY_RUN", "true")
BOT_G_ARCHIVED = _env_bool("BOT_G_ARCHIVED", "false")


# --- Bankroll + sizing -------------------------------------------------------

BOT_G_BANKROLL_USD = _env_decimal("BOT_G_BANKROLL_USD", "500")
# Fixed per-trade notional. Cheap tokens → high shares → high upside but
# low $ risk.
#
# Grok round-3 2026-04-20 fractional Kelly analysis:
#   Full Kelly f* = (p·b - q) / b where b≈99 (100x gross on 1¢), p≈0.08,
#   q=0.92 → f* ≈ 0.07 (7% of bankroll). Use 1/8 to 1/10 Kelly = ~0.7-0.9%
#   of bankroll = ~$3.50-$4.50 per trade on $500 bankroll.
# $5 is slightly above 1/8 Kelly; acceptable for paper, keep for now.
BOT_G_FIXED_TRADE_USD = _env_decimal("BOT_G_FIXED_TRADE_USD", "5")


# --- Entry gate --------------------------------------------------------------

# Three-mode operation:
#   * Prime mode   (t=30s, 4-8c, CEX-confirmed): current candidate.
#   * Jackpot mode (t=60s, no gap filter): asymmetric payoff, 8-14% WR,
#     1 dominant winner drives P&L, high variance.
#   * Scalp mode   (t=30s, no gap filter): 20.9% WR, smaller per-win
#     payouts, lower variance.
# Orders from each mode carry a distinct tag suffix
# in their tag field so post-hoc attribution is clean.
BOT_G_PRIME_MODE_ENABLED = _env_bool("BOT_G_PRIME_MODE_ENABLED", "false")
BOT_G_JACKPOT_MODE_ENABLED = _env_bool("BOT_G_JACKPOT_MODE_ENABLED", "true")
BOT_G_SCALP_MODE_ENABLED = _env_bool("BOT_G_SCALP_MODE_ENABLED", "true")

BOT_G_PRIME_ENTRY_SECONDS = _env_int("BOT_G_PRIME_ENTRY_SECONDS", "30")
BOT_G_JACKPOT_ENTRY_SECONDS = _env_int("BOT_G_JACKPOT_ENTRY_SECONDS", "60")
BOT_G_SCALP_ENTRY_SECONDS = _env_int("BOT_G_SCALP_ENTRY_SECONDS", "30")
# Final pre-submit freshness guard. The scan loop can spend time on book,
# filter, and CLOB checks after it first computes t-to-resolution; this floor
# prevents stale scan time from sending orders into/after the close.
BOT_G_MIN_ENTRY_LEAD_SECONDS = _env_int("BOT_G_MIN_ENTRY_LEAD_SECONDS", "5")

# Legacy alias — used by _try_enter_market for the default mode (jackpot).
BOT_G_ENTRY_SECONDS_BEFORE_RES = _env_int(
    "BOT_G_ENTRY_SECONDS_BEFORE_RES", str(BOT_G_JACKPOT_ENTRY_SECONDS),
)

# Maximum limit price we're willing to pay. ≤2¢ is the backtest-validated
# edge; widening pulls in more trades but dilutes the asymmetric-payoff
# thesis.
BOT_G_MAX_ENTRY_PRICE = _env_decimal("BOT_G_MAX_ENTRY_PRICE", "0.02")

# Optional lower bound. Prime uses this to avoid the observed 1-3c toxic band;
# legacy modes leave it at zero and preserve the old "anything <= ceiling"
# behavior.
BOT_G_MIN_ENTRY_PRICE = _env_decimal("BOT_G_MIN_ENTRY_PRICE", "0")

# Live-only fill-transfer helper: raise the submitted limit by N ticks after a
# candidate passes the normal entry band, capped by BOT_G_MAX_ENTRY_PRICE.
BOT_G_ENTRY_TICK_SIZE = _env_decimal("BOT_G_ENTRY_TICK_SIZE", "0.01")
BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS = _env_int(
    "BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS",
    "0",
)
BOT_G_EXECUTION_STYLE = os.environ.get("BOT_G_EXECUTION_STYLE", "taker").strip().lower()
BOT_G_MAKER_CANCEL_LEAD_SECONDS = _env_int("BOT_G_MAKER_CANCEL_LEAD_SECONDS", "5")

# Prime confirmation: only buy the cheap side if CEX spot is already moving
# toward that outcome in the last N seconds. For Up/Down markets, YES means
# "underlying up" and NO means "underlying down".
BOT_G_PRIME_REQUIRE_CEX_CONFIRM = _env_bool("BOT_G_PRIME_REQUIRE_CEX_CONFIRM", "true")
BOT_G_PRIME_CEX_WINDOW_SEC = _env_int("BOT_G_PRIME_CEX_WINDOW_SEC", "45")
BOT_G_PRIME_MIN_CEX_MOVE_BPS = _env_decimal("BOT_G_PRIME_MIN_CEX_MOVE_BPS", "1.5")

# Causal book-depletion telemetry. Default is observation-only; turn the
# hard gate on only after the recorder data proves it lifts WR without
# starving sample size.
BOT_G_PRIME_REQUIRE_DEPLETION = _env_bool("BOT_G_PRIME_REQUIRE_DEPLETION", "false")
BOT_G_PRIME_MAX_DEPLETION_RATIO = _env_decimal("BOT_G_PRIME_MAX_DEPLETION_RATIO", "0.75")

# Symbol universe for this Bot G process. Recorder can capture a wider
# universe than live trading; keep live explicitly narrowed in systemd.
BOT_G_ALLOWED_SYMBOLS = frozenset(
    s.strip().upper()
    for s in os.environ.get("BOT_G_ALLOWED_SYMBOLS", "BTC,ETH,SOL").split(",")
    if s.strip()
)

# Minimum share size the book must offer at our price level for us to
# enter. Sub-threshold depth = fill risk for us OR market-maker just about
# to pull. 20 shares x 2¢ entry = $0.40 minimum book support.
BOT_G_MIN_BOOK_SIZE = _env_decimal("BOT_G_MIN_BOOK_SIZE", "20")

# Spread-purity filter (Grok round-5 recommendation, 2026-04-21):
# Only enter when the OTHER side of the book is near-certainty (≥ this
# threshold). The original thesis is "the losing side is mispriced cheap
# WHILE the other side is near-certain". If YES=3¢ and NO=4¢, neither is
# the obvious loser — it's a balanced-uncertainty market, not a mispriced
# tail. Expected effect: 30-50% fewer fills but cleaner thesis purity.
#
# Operationalized as: max(yes_ask, no_ask) >= BOT_G_MIN_COUNTERPARTY_PRICE.
# Set to 0.0 to disable the filter (accept any book shape).
#
# Session 28 tactical fix: derive the default from the configured cheap-side
# ceiling. When BOT_G_MAX_ENTRY_PRICE was widened to 0.08, the old hard-coded
# 0.90 floor self-cancelled 0.08/0.88 books. Keep at least an 85c purity floor
# while allowing a 4c book-shape cushion for binary asks that do not sum to
# exactly 1.00.
_default_counterparty_price = max(
    Decimal("0.85"),
    Decimal("1") - BOT_G_MAX_ENTRY_PRICE - Decimal("0.04"),
)
BOT_G_MIN_COUNTERPARTY_PRICE = _env_decimal(
    "BOT_G_MIN_COUNTERPARTY_PRICE",
    str(_default_counterparty_price),
)


# --- Risk caps ---------------------------------------------------------------

# Max open positions across all markets. Bot G enters once per market in
# the final 60s; caps limit blast radius on a single market burst.
BOT_G_MAX_CONCURRENT_POSITIONS = _env_int("BOT_G_MAX_CONCURRENT_POSITIONS", "10")

# Max new positions per day. At 3 symbols x ~12 cohorts/hour = 864/day
# possible; cap keeps per-day $ risk bounded.
BOT_G_MAX_DAILY_ENTRIES = _env_int("BOT_G_MAX_DAILY_ENTRIES", "100")

# Tiny-live caps. These are used only when the effective CLOB path is live,
# so paper collection remains governed by the paper caps above.
BOT_G_LIVE_MAX_CONCURRENT_POSITIONS = _env_int("BOT_G_LIVE_MAX_CONCURRENT_POSITIONS", "10")
BOT_G_LIVE_MAX_DAILY_ENTRIES = _env_int("BOT_G_LIVE_MAX_DAILY_ENTRIES", "20")
BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD = _env_decimal(
    "BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD",
    "100",
)
BOT_G_LIVE_WALLET_USD = _env_decimal("BOT_G_LIVE_WALLET_USD", "200")
BOT_G_LIVE_APPROVED_AT = os.environ.get("BOT_G_LIVE_APPROVED_AT", "")

# Stop entering when realised P&L on the rolling 100-trade window
# drops below this ROI threshold. Edge-gone kill switch.
BOT_G_MIN_ROLLING_ROI_PCT = _env_decimal("BOT_G_MIN_ROLLING_ROI_PCT", "100")
BOT_G_ROLLING_WINDOW_TRADES = _env_int("BOT_G_ROLLING_WINDOW_TRADES", "100")


# --- Loop cadence ------------------------------------------------------------

# Scan every N seconds. Tight enough to catch the 60s → 0s entry window
# (target ~30s for reliability).
BOT_G_SCAN_INTERVAL_S = _env_float("BOT_G_SCAN_INTERVAL_S", "10")

# Runtime-state heartbeat cadence. The startup event proves initial mode, but
# remote dashboards/audits need a fresh timestamp while long-running VPS
# services stay up for days.
BOT_G_RUNTIME_STATE_HEARTBEAT_INTERVAL_S = _env_float(
    "BOT_G_RUNTIME_STATE_HEARTBEAT_INTERVAL_S",
    "300",
)

# Paper-resolution reconcile cadence.
BOT_G_PAPER_RESOLVE_INTERVAL_S = _env_float("BOT_G_PAPER_RESOLVE_INTERVAL_S", "3600")

# Paper-only exit experiment. This proves the "buy cheap near close, sell if
# it spikes before resolution" idea without touching live CLOB paths.
BOT_G_PAPER_TAKE_PROFIT_ENABLED = _env_bool("BOT_G_PAPER_TAKE_PROFIT_ENABLED", "false")
BOT_G_PAPER_TAKE_PROFIT_PRICE = _env_decimal("BOT_G_PAPER_TAKE_PROFIT_PRICE", "0.70")
BOT_G_PAPER_TAKE_PROFIT_START_SECONDS = _env_int("BOT_G_PAPER_TAKE_PROFIT_START_SECONDS", "25")
BOT_G_PAPER_TAKE_PROFIT_END_SECONDS = _env_int("BOT_G_PAPER_TAKE_PROFIT_END_SECONDS", "8")

# Event-only live/paper shadow for the same TP formula. This never sends a
# SELL order; it records whether an open position would have crossed the
# take-profit threshold, so the live ledger can be audited before an exit ADR.
BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_ENABLED = _env_bool(
    "BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_ENABLED",
    "false",
)
BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_PRICE = _env_decimal(
    "BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_PRICE",
    str(BOT_G_PAPER_TAKE_PROFIT_PRICE),
)
BOT_G_TAKE_PROFIT_SHADOW_START_SECONDS = _env_int(
    "BOT_G_TAKE_PROFIT_SHADOW_START_SECONDS",
    str(BOT_G_PAPER_TAKE_PROFIT_START_SECONDS),
)
BOT_G_TAKE_PROFIT_SHADOW_END_SECONDS = _env_int(
    "BOT_G_TAKE_PROFIT_SHADOW_END_SECONDS",
    str(BOT_G_PAPER_TAKE_PROFIT_END_SECONDS),
)


# --- Recorder DB (read-only) -------------------------------------------------

# Bot G queries the recorder for (a) active market discovery and (b) the
# freshest best_bid_ask per token. Recorder already writes this for Bot E
# — we piggyback.
BOT_G_RECORDER_DB_PATH = os.environ.get(
    "BOT_G_RECORDER_DB_PATH",
    os.environ.get(
        "BOT_E_RECORDER_DB_PATH",
        "data/bot_e_recorder.db",
    ),
)
# Recorder market discovery can stop refreshing a 5m market several minutes
# before expiry once subscriptions are already open. Keep this above one
# discovery cycle so Bot G can still enter its 45-60s window, while excluding
# old rows from already-rotated market sets.
BOT_G_MARKET_ROW_MAX_AGE_SECONDS = _env_int("BOT_G_MARKET_ROW_MAX_AGE_SECONDS", "360")


def validate() -> list[str]:
    errors: list[str] = []
    if BOT_G_FIXED_TRADE_USD <= 0:
        errors.append("BOT_G_FIXED_TRADE_USD must be positive")
    if BOT_G_MAX_ENTRY_PRICE <= 0 or Decimal("0.20") < BOT_G_MAX_ENTRY_PRICE:
        errors.append(
            "BOT_G_MAX_ENTRY_PRICE must be in (0, 0.20]; thesis requires "
            "tail-priced tokens, not 50-50 markets"
        )
    if BOT_G_MIN_ENTRY_PRICE < 0:
        errors.append("BOT_G_MIN_ENTRY_PRICE must be non-negative")
    if BOT_G_MIN_ENTRY_PRICE > BOT_G_MAX_ENTRY_PRICE:
        errors.append("BOT_G_MIN_ENTRY_PRICE must be <= BOT_G_MAX_ENTRY_PRICE")
    if BOT_G_ENTRY_TICK_SIZE <= 0:
        errors.append("BOT_G_ENTRY_TICK_SIZE must be positive")
    if BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS < 0:
        errors.append("BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS must be non-negative")
    if BOT_G_EXECUTION_STYLE not in {"taker", "maker"}:
        errors.append("BOT_G_EXECUTION_STYLE must be taker or maker")
    if BOT_G_MAKER_CANCEL_LEAD_SECONDS < 0:
        errors.append("BOT_G_MAKER_CANCEL_LEAD_SECONDS must be non-negative")
    if BOT_G_MIN_ENTRY_LEAD_SECONDS < 0:
        errors.append("BOT_G_MIN_ENTRY_LEAD_SECONDS must be non-negative")
    if BOT_G_MARKET_ROW_MAX_AGE_SECONDS <= 0:
        errors.append("BOT_G_MARKET_ROW_MAX_AGE_SECONDS must be positive")
    if not BOT_G_ALLOWED_SYMBOLS:
        errors.append("BOT_G_ALLOWED_SYMBOLS must not be empty")
    if BOT_ID == "bot_g_prime_live":
        legacy_live_band = (
            Decimal("0.035") <= BOT_G_MIN_ENTRY_PRICE
            and Decimal("0.055") >= BOT_G_MAX_ENTRY_PRICE
            and BOT_G_PRIME_ENTRY_SECONDS <= 60
            and BOT_G_ENTRY_SECONDS_BEFORE_RES <= 60
            and frozenset({"BTC", "ETH", "SOL"}) >= BOT_G_ALLOWED_SYMBOLS
            and Decimal("1") >= BOT_G_FIXED_TRADE_USD
        )
        high_tail_live_band = (
            Decimal("0.06") <= BOT_G_MIN_ENTRY_PRICE
            and Decimal("0.08") >= BOT_G_MAX_ENTRY_PRICE
            and BOT_G_PRIME_ENTRY_SECONDS <= 45
            and BOT_G_ENTRY_SECONDS_BEFORE_RES <= 45
            and frozenset({"ETH", "SOL"}) >= BOT_G_ALLOWED_SYMBOLS
            and Decimal("1") >= BOT_G_FIXED_TRADE_USD
        )
        if not (legacy_live_band or high_tail_live_band):
            if Decimal("0.035") > BOT_G_MIN_ENTRY_PRICE:
                errors.append("bot_g_prime_live requires BOT_G_MIN_ENTRY_PRICE >= 0.035")
            if Decimal("0.055") < BOT_G_MAX_ENTRY_PRICE and not high_tail_live_band:
                errors.append("bot_g_prime_live requires BOT_G_MAX_ENTRY_PRICE <= 0.055")
            errors.append(
                "bot_g_prime_live requires either legacy 3.5c-5.5c guard "
                "or ADR-149 high-tail guard: 6c-8c, <=45s, ETH/SOL only, <=$1"
            )
    if BOT_G_ENTRY_SECONDS_BEFORE_RES <= 0:
        errors.append("BOT_G_ENTRY_SECONDS_BEFORE_RES must be positive")
    if BOT_G_RUNTIME_STATE_HEARTBEAT_INTERVAL_S <= 0:
        errors.append("BOT_G_RUNTIME_STATE_HEARTBEAT_INTERVAL_S must be positive")
    if BOT_G_FIXED_TRADE_USD > BOT_G_BANKROLL_USD:
        errors.append("BOT_G_FIXED_TRADE_USD exceeds BOT_G_BANKROLL_USD")
    if BOT_G_LIVE_MAX_CONCURRENT_POSITIONS <= 0:
        errors.append("BOT_G_LIVE_MAX_CONCURRENT_POSITIONS must be positive")
    if BOT_G_LIVE_MAX_DAILY_ENTRIES <= 0:
        errors.append("BOT_G_LIVE_MAX_DAILY_ENTRIES must be positive")
    if BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD <= 0:
        errors.append("BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD must be positive")
    if BOT_G_LIVE_WALLET_USD <= 0:
        errors.append("BOT_G_LIVE_WALLET_USD must be positive")
    if BOT_G_FIXED_TRADE_USD > BOT_G_LIVE_WALLET_USD:
        errors.append("BOT_G_FIXED_TRADE_USD exceeds BOT_G_LIVE_WALLET_USD")
    if BOT_G_PAPER_TAKE_PROFIT_PRICE <= 0 or BOT_G_PAPER_TAKE_PROFIT_PRICE > 1:
        errors.append("BOT_G_PAPER_TAKE_PROFIT_PRICE must be in (0, 1]")
    if BOT_G_PAPER_TAKE_PROFIT_START_SECONDS < BOT_G_PAPER_TAKE_PROFIT_END_SECONDS:
        errors.append(
            "BOT_G_PAPER_TAKE_PROFIT_START_SECONDS must be >= "
            "BOT_G_PAPER_TAKE_PROFIT_END_SECONDS"
        )
    if BOT_G_PAPER_TAKE_PROFIT_END_SECONDS < 0:
        errors.append("BOT_G_PAPER_TAKE_PROFIT_END_SECONDS must be non-negative")
    if (
        BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_PRICE <= 0
        or BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_PRICE > 1
    ):
        errors.append("BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_PRICE must be in (0, 1]")
    if BOT_G_TAKE_PROFIT_SHADOW_START_SECONDS < BOT_G_TAKE_PROFIT_SHADOW_END_SECONDS:
        errors.append(
            "BOT_G_TAKE_PROFIT_SHADOW_START_SECONDS must be >= "
            "BOT_G_TAKE_PROFIT_SHADOW_END_SECONDS"
        )
    if BOT_G_TAKE_PROFIT_SHADOW_END_SECONDS < 0:
        errors.append("BOT_G_TAKE_PROFIT_SHADOW_END_SECONDS must be non-negative")
    return errors
