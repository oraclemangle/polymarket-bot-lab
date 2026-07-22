"""Bot E trader — configuration with startup validation.

All values env-overridable. Defaults reflect v1 scope per ADR-022:
- Fixed $2/trade (NOT Kelly until 300+ paper trades per Codex C-S3)
- Binary regime gate (no tuning in v1)
- Maker-only entries
- OBI threshold TBD from Phase 0d calibration (starting value 0.20)

Validation at startup — bot refuses to run on invalid config.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_decimal(name: str, default: str) -> Decimal:
    return Decimal(_env(name, default))


def _env_float(name: str, default: str) -> float:
    return float(_env(name, default))


def _env_int(name: str, default: str) -> int:
    return int(_env(name, default))


# ============================================================================
# MODE
# ============================================================================
BOT_E_ENV = _env("BOT_E_ENV", "paper").lower()  # "paper" | "live"
BOT_E_DRY_RUN = _env("BOT_E_DRY_RUN", "true").lower() == "true"

# ============================================================================
# CAPITAL + SIZING (Codex C-S3: fixed notional, not Kelly, until calibrated)
# ============================================================================
BOT_E_BANKROLL_USD = _env_decimal("BOT_E_BANKROLL_USD", "100")
# v1: flat $2/trade; Kelly stays off until calibration.
BOT_E_FIXED_TRADE_USD = _env_decimal("BOT_E_FIXED_TRADE_USD", "2")
BOT_E_KELLY_FRACTION = _env_decimal("BOT_E_KELLY_FRACTION", "0")

# Crypto-bucket correlation cap (Grok S3): all BTC+ETH+SOL positions combined
# cannot exceed this fraction of bankroll.
# Audit 2026-04-17 (GLM-5.1 Q21 / Codex Q21 P1): tightened from 0.15 to 0.10.
# BTC/ETH/SOL have 0.7-0.9 correlation in 15-min windows; a 15% per-asset
# cap with 30% aggregate allowed ~45% effective exposure.
BOT_E_CRYPTO_BUCKET_CAP_FRAC = _env_decimal("BOT_E_CRYPTO_BUCKET_CAP_FRAC", "0.10")

# Aggregate overall exposure cap. Tightened from 0.30 to 0.25 per audit.
BOT_E_AGGREGATE_EXPOSURE_CAP_FRAC = _env_decimal(
    "BOT_E_AGGREGATE_EXPOSURE_CAP_FRAC", "0.25",
)

# Correlation-adjusted effective-exposure check. When enabled, the crypto
# bucket cap is evaluated against `sum(positions) x sqrt(1 + avg_correlation)`
# rather than raw sum. Conservative default (0.8 correlation) means three
# positions at 3% each appear as ~12% effective, breaching the 10% cap.
BOT_E_CRYPTO_CORRELATION_ADJ = (
    _env("BOT_E_CRYPTO_CORRELATION_ADJ", "true").strip().lower() == "true"
)
BOT_E_CRYPTO_AVG_CORRELATION = _env_decimal("BOT_E_CRYPTO_AVG_CORRELATION", "0.80")

# Per-trade cap as fraction of bankroll (safety net above fixed $).
BOT_E_PER_TRADE_CAP_FRAC = _env_decimal("BOT_E_PER_TRADE_CAP_FRAC", "0.025")

# ADR-037 (2026-04-22) — tuning knobs added after 69-trade drill-down.
# One 68-share outlier at entry $0.44 resolving to $0 lost $30: 17% of all
# losses from a single fill. Cap kills the tail at ~1.5x median trade size.
BOT_E_MAX_SHARES_PER_POSITION = _env_decimal("BOT_E_MAX_SHARES_PER_POSITION", "15")

# [0.0, 0.4) entry bucket had 1 win in 4 trades (25% WR). [0.4, 0.6) had
# 34 of 61 (56% WR) with +$15.47 net. Filter cuts low-SNR noise at the edge.
BOT_E_MIN_ENTRY_PRICE = _env_decimal("BOT_E_MIN_ENTRY_PRICE", "0.40")

# ============================================================================
# SIGNAL (OBI) — thresholds provisional until Phase 0d calibration
# ============================================================================
# Rolling OBI window (seconds). v96 default 120s.
BOT_E_OBI_WINDOW_SEC = _env_float("BOT_E_OBI_WINDOW_SEC", "120")
# abs(imbalance) threshold for entry candidate. 0.20 = v96; validate in Phase 0d.
BOT_E_OBI_THRESHOLD = _env_decimal("BOT_E_OBI_THRESHOLD", "0.20")
# EWMA decay half-life (seconds). 0 = rectangular window (original).
# Audit 2026-04-17 (GLM-5.1 Q15 P1): rectangular weights a 119s-old trade
# equally with a 1s-old one; EWMA with a 30s half-life weights the last
# 60s ~75%. Change from 0 → 30 is a free calibration upgrade.
BOT_E_OBI_DECAY_HALF_LIFE_SEC = _env_float("BOT_E_OBI_DECAY_HALF_LIFE_SEC", "30")
# Minimum trade count in the rolling window before we trust the imbalance.
BOT_E_OBI_MIN_TRADES = _env_int("BOT_E_OBI_MIN_TRADES", "2")
# Minimum total volume (USDC) in the window.
BOT_E_OBI_MIN_VOLUME_USD = _env_decimal("BOT_E_OBI_MIN_VOLUME_USD", "1")

# ============================================================================
# REGIME (Grok G3 + Codex C-R1): binary hard-gate in v1, bps-normalised
# ============================================================================
# Choppiness ratio: skip entries if reversals/transitions > this.
BOT_E_REGIME_CHOPPINESS_MAX = _env_float("BOT_E_REGIME_CHOPPINESS_MAX", "0.65")
# Minimum 10-min BTC move (basis points of current price) to consider "trending".
# Below this we treat as sideways and defer to OBI without regime bonus.
BOT_E_REGIME_TREND_MIN_BPS = _env_float("BOT_E_REGIME_TREND_MIN_BPS", "50")

# ============================================================================
# ENTRY/EXIT TIMING
# ============================================================================
# Paper-mode entry window (wide, for data collection).
BOT_E_ENTRY_WINDOW_MIN_SEC = _env_float("BOT_E_ENTRY_WINDOW_MIN_SEC", "180")    # t-3min
BOT_E_ENTRY_WINDOW_MAX_SEC = _env_float("BOT_E_ENTRY_WINDOW_MAX_SEC", "900")    # t-15min
# Live-mode entry window (narrow — audit 2026-04-17 Q18, GLM-5.1/Codex P1).
# Reviewers converged on 5-10 min as the live trading band: t-15m has low
# predictive power for 15m-ahead resolution; t-3m has minimal liquidity
# left. Live trading uses these tighter values, paper keeps the wider
# window so calibration captures signal decay at the window edges.
BOT_E_LIVE_ENTRY_WINDOW_MIN_SEC = _env_float("BOT_E_LIVE_ENTRY_WINDOW_MIN_SEC", "300")    # t-5min
BOT_E_LIVE_ENTRY_WINDOW_MAX_SEC = _env_float("BOT_E_LIVE_ENTRY_WINDOW_MAX_SEC", "600")    # t-10min
BOT_E_DISCOVERY_MAX_MIN = _env_float("BOT_E_DISCOVERY_MAX_MIN", "60")
# Skip if signal is this stale (ms since last WSS event).
BOT_E_STALE_FEED_MS = _env_float("BOT_E_STALE_FEED_MS", "500")

# ============================================================================
# MAKER-ONLY EXECUTION (required by 2026 fees — ADR-022 verification G1)
# ============================================================================
BOT_E_MAKER_ONLY = _env("BOT_E_MAKER_ONLY", "true").lower() == "true"
# Limit price offset from current best bid/ask (in $ per share). Paper now
# defaults to 0.000 after the 2026-04-30 cancel autopsy setup: 0.001 produced
# live order flow but no current-epoch fills. Live remains maker-only; do not
# cross the touch without a new ADR.
_BOT_E_MAKER_OFFSET_DEFAULT = "0.001" if BOT_E_ENV == "live" else "0.000"
BOT_E_MAKER_OFFSET = _env_decimal("BOT_E_MAKER_OFFSET", _BOT_E_MAKER_OFFSET_DEFAULT)
# Cancel an unfilled limit after this many seconds (we missed the window).
# Session 17 (2026-04-16): raised from 60s → 300s. Session 51 follow-up
# (2026-04-30): raised paper default from 300s → 600s because current-epoch
# orders were flowing but TTL-cancelling before producing fills.
_BOT_E_ORDER_TTL_SEC_DEFAULT = "300" if BOT_E_ENV == "live" else "600"
BOT_E_ORDER_TTL_SEC = _env_float("BOT_E_ORDER_TTL_SEC", _BOT_E_ORDER_TTL_SEC_DEFAULT)

# Order style: maker-only, enforced. Audit 2026-04-17 removed the paper-mode
# "taker" override because it bid above the bid-derived mid rather than
# crossing the real touch — neither a faithful taker nor a maker model, so
# paper calibration data could not be reproduced live. See
# `docs/audit/bots-a-d-e-audit-responses/` Q20/Q23. Env is retained for
# observability only; any non-"maker" value is ignored with a warning.
BOT_E_ORDER_STYLE = _env("BOT_E_ORDER_STYLE", "maker")

# Paper-mode calibration gating (audit 2026-04-17, Codex P0).
# Replaces the hardcoded PAPER_FIXED_TRADE_USD=$30 / 200-trade constants
# in __main__.py. Counter is now DB-backed (counts fills, not placed orders)
# and persists across restarts.
BOT_E_PAPER_FIXED_USD = _env_decimal("BOT_E_PAPER_FIXED_USD", "30")
BOT_E_PAPER_TRADE_THRESHOLD = _env_int("BOT_E_PAPER_TRADE_THRESHOLD", "200")
# Minimum lower-bound of 95% CI on observed edge before switching from
# fixed sizing to Kelly-fractional. 0 disables CI gating (pure count).
BOT_E_PAPER_EDGE_MIN_LB = _env_decimal("BOT_E_PAPER_EDGE_MIN_LB", "0")

# Bot E separate hot wallet — audit 2026-04-17 Codex AF-2 / U-08 2026-04-18.
#
# Live-mode Bot E MUST use a keystore file AND passphrase file that are both
# distinct from the shared (Bot A/B) ones. Previous code compared
# `BOT_E_KEYSTORE_PATH` against the shared PASSPHRASE path and then only
# overrode the passphrase — the keystore file itself stayed shared. U-08
# fixes this by introducing a separate env var for each and comparing each
# against its corresponding shared counterpart.
#
# BOT_E_KEYSTORE_PATH: absolute path to Bot E's age-encrypted keystore.
# BOT_E_PASSPHRASE_PATH: absolute path to Bot E's passphrase (tmpfs).
#
# Both are empty by default; paper mode ignores them (no keystore loaded).
BOT_E_KEYSTORE_PATH = _env("BOT_E_KEYSTORE_PATH", "")
BOT_E_PASSPHRASE_PATH = _env("BOT_E_PASSPHRASE_PATH", "")

# ============================================================================
# RISK CONTROLS
# ============================================================================
# Daily loss kill — halts trading for the calendar day.
BOT_E_DAILY_LOSS_KILL_FRAC = _env_decimal("BOT_E_DAILY_LOSS_KILL_FRAC", "0.18")
# Global drawdown kill — requires manual unhalt.
BOT_E_GLOBAL_DRAWDOWN_KILL_FRAC = _env_decimal("BOT_E_GLOBAL_DRAWDOWN_KILL_FRAC", "0.35")
# Consecutive-loss halt (v96/Entry 001): N losses in M seconds → cooldown.
BOT_E_CONSECUTIVE_LOSS_HALT_N = _env_int("BOT_E_CONSECUTIVE_LOSS_HALT_N", "5")
BOT_E_CONSECUTIVE_LOSS_WINDOW_SEC = _env_float("BOT_E_CONSECUTIVE_LOSS_WINDOW_SEC", "600")
BOT_E_CONSECUTIVE_LOSS_COOLDOWN_SEC = _env_float("BOT_E_CONSECUTIVE_LOSS_COOLDOWN_SEC", "900")
# Trailing-loss halt (Entry 006): N-of-M recent trades losses → halt.
BOT_E_TRAILING_LOSS_N = _env_int("BOT_E_TRAILING_LOSS_N", "12")
BOT_E_TRAILING_LOSS_WINDOW = _env_int("BOT_E_TRAILING_LOSS_WINDOW", "20")
# Feed-divergence halt (Codex C-S5): if two price sources diverge > N bps.
BOT_E_FEED_DIVERGENCE_MAX_BPS = _env_float("BOT_E_FEED_DIVERGENCE_MAX_BPS", "100")

# Phase 4 audit 2026-04-17: adverse-selection halt thresholds.
# Halts when >=ADVERSE_HALT_THRESHOLD of last ADVERSE_WINDOW_N fills moved
# against us within 30s. 60% / 20 matches the adversarial audit recommendation.
BOT_E_ADVERSE_WINDOW_N = _env_int("BOT_E_ADVERSE_WINDOW_N", "20")
BOT_E_ADVERSE_HALT_THRESHOLD = _env_decimal("BOT_E_ADVERSE_HALT_THRESHOLD", "0.60")

# Phase 5 Item 2 audit 2026-04-17: signed CEX CVD confirmation gate.
# Before emitting an OBI signal, check that cumulative signed volume on
# the equivalent CEX pair (BTC/ETH/SOL-USDT on Binance) agrees with the
# OBI direction. If CEX CVD direction disagrees, skip the signal — the
# Polymarket flow is likely trailing stale CEX movement.
BOT_E_CEX_CVD_GATE = _env("BOT_E_CEX_CVD_GATE", "true").strip().lower() == "true"
BOT_E_CEX_CVD_WINDOW_SEC = _env_float("BOT_E_CEX_CVD_WINDOW_SEC", "60")
# Minimum notional CVD magnitude to consider the CEX signal "informative".
# Below this, treat the CVD as insufficient (pass-through, not blocked).
BOT_E_CEX_CVD_MIN_USD = _env_decimal("BOT_E_CEX_CVD_MIN_USD", "1000")

# Phase 5 Item 3 audit 2026-04-17: depth-at-best gate. Skip signals when
# best-bid/ask depth on the target side is below threshold — a signal
# entering a thin book is likely to suffer adverse selection regardless
# of OBI direction.
BOT_E_DEPTH_GATE = _env("BOT_E_DEPTH_GATE", "true").strip().lower() == "true"
BOT_E_DEPTH_MIN_USD = _env_decimal("BOT_E_DEPTH_MIN_USD", "500")
# Price offset from best bid/ask (in $ per share) to consider "at best".
# 0.005 = 5bps either side; aggregate depth within that band.
BOT_E_DEPTH_BAND_WIDTH = _env_decimal("BOT_E_DEPTH_BAND_WIDTH", "0.005")

# ============================================================================
# GENERAL
# ============================================================================
BOT_E_SCAN_INTERVAL_SEC = _env_float("BOT_E_SCAN_INTERVAL_SEC", "5")
BOT_E_LOG_LEVEL = _env("BOT_E_LOG_LEVEL", "INFO")
# Separate hot wallet per spec (ADR-022): do NOT share with Bot A/B.
BOT_E_HOT_WALLET_MAX_USD = _env_decimal("BOT_E_HOT_WALLET_MAX_USD", "100")


@dataclass(frozen=True)
class ConfigSummary:
    """Snapshot of active config for startup logs."""
    env: str
    dry_run: bool
    bankroll: Decimal
    fixed_trade: Decimal
    obi_threshold: Decimal
    regime_choppiness_max: float
    regime_trend_min_bps: float
    maker_only: bool


def summary() -> ConfigSummary:
    return ConfigSummary(
        env=BOT_E_ENV,
        dry_run=BOT_E_DRY_RUN,
        bankroll=BOT_E_BANKROLL_USD,
        fixed_trade=BOT_E_FIXED_TRADE_USD,
        obi_threshold=BOT_E_OBI_THRESHOLD,
        regime_choppiness_max=BOT_E_REGIME_CHOPPINESS_MAX,
        regime_trend_min_bps=BOT_E_REGIME_TREND_MIN_BPS,
        maker_only=BOT_E_MAKER_ONLY,
    )


def validate() -> list[str]:
    """Return list of validation errors. Empty list == ok.

    Per Grok S5 / v96 pattern: bot refuses to start on invalid config.
    ~20 checks across risk caps, signal params, infra sanity.
    """
    errors: list[str] = []

    # --- Mode ---
    if BOT_E_ENV not in ("paper", "live"):
        errors.append(f"BOT_E_ENV must be 'paper' or 'live', got {BOT_E_ENV!r}")

    # --- Capital ---
    if BOT_E_BANKROLL_USD <= 0:
        errors.append("BOT_E_BANKROLL_USD must be positive")
    if BOT_E_FIXED_TRADE_USD <= 0:
        errors.append("BOT_E_FIXED_TRADE_USD must be positive")
    if BOT_E_FIXED_TRADE_USD > BOT_E_BANKROLL_USD * BOT_E_PER_TRADE_CAP_FRAC:
        errors.append(
            f"BOT_E_FIXED_TRADE_USD ({BOT_E_FIXED_TRADE_USD}) exceeds "
            f"per-trade cap ({BOT_E_BANKROLL_USD * BOT_E_PER_TRADE_CAP_FRAC})"
        )
    if not (Decimal("0") <= BOT_E_KELLY_FRACTION <= Decimal("1")):
        errors.append("BOT_E_KELLY_FRACTION must be in [0, 1]")
    if not (Decimal("0") < BOT_E_CRYPTO_BUCKET_CAP_FRAC <= Decimal("1")):
        errors.append("BOT_E_CRYPTO_BUCKET_CAP_FRAC must be in (0, 1]")
    if BOT_E_AGGREGATE_EXPOSURE_CAP_FRAC < BOT_E_CRYPTO_BUCKET_CAP_FRAC:
        errors.append("AGGREGATE_EXPOSURE_CAP_FRAC must be >= CRYPTO_BUCKET_CAP_FRAC")

    # --- Signal ---
    if BOT_E_OBI_WINDOW_SEC <= 0:
        errors.append("BOT_E_OBI_WINDOW_SEC must be positive")
    if not (Decimal("0") < BOT_E_OBI_THRESHOLD <= Decimal("1")):
        errors.append("BOT_E_OBI_THRESHOLD must be in (0, 1]")
    if BOT_E_OBI_MIN_TRADES < 1:
        errors.append("BOT_E_OBI_MIN_TRADES must be >= 1")

    # --- Regime ---
    if not (0 < BOT_E_REGIME_CHOPPINESS_MAX <= 1):
        errors.append("BOT_E_REGIME_CHOPPINESS_MAX must be in (0, 1]")
    if BOT_E_REGIME_TREND_MIN_BPS < 0:
        errors.append("BOT_E_REGIME_TREND_MIN_BPS must be non-negative")

    # --- Timing ---
    if BOT_E_ENTRY_WINDOW_MIN_SEC >= BOT_E_ENTRY_WINDOW_MAX_SEC:
        errors.append(
            "ENTRY_WINDOW_MIN_SEC must be < MAX_SEC "
            f"(got {BOT_E_ENTRY_WINDOW_MIN_SEC} / {BOT_E_ENTRY_WINDOW_MAX_SEC})"
        )
    if BOT_E_STALE_FEED_MS <= 0:
        errors.append("BOT_E_STALE_FEED_MS must be positive")

    # --- Execution ---
    if BOT_E_MAKER_OFFSET < 0:
        errors.append("BOT_E_MAKER_OFFSET must be non-negative")
    if BOT_E_ORDER_TTL_SEC <= 0:
        errors.append("BOT_E_ORDER_TTL_SEC must be positive")

    # --- Risk ---
    if not (Decimal("0") < BOT_E_DAILY_LOSS_KILL_FRAC < Decimal("1")):
        errors.append("BOT_E_DAILY_LOSS_KILL_FRAC must be in (0, 1)")
    if BOT_E_GLOBAL_DRAWDOWN_KILL_FRAC <= BOT_E_DAILY_LOSS_KILL_FRAC:
        errors.append("GLOBAL_DRAWDOWN_KILL_FRAC must be > DAILY_LOSS_KILL_FRAC")
    if BOT_E_CONSECUTIVE_LOSS_HALT_N < 1:
        errors.append("BOT_E_CONSECUTIVE_LOSS_HALT_N must be >= 1")
    if BOT_E_TRAILING_LOSS_N > BOT_E_TRAILING_LOSS_WINDOW:
        errors.append("BOT_E_TRAILING_LOSS_N cannot exceed BOT_E_TRAILING_LOSS_WINDOW")

    # --- Infra sanity ---
    if BOT_E_ENV == "live" and BOT_E_HOT_WALLET_MAX_USD <= 0:
        errors.append("BOT_E_HOT_WALLET_MAX_USD must be positive in live mode")
    if BOT_E_ENV == "live" and BOT_E_DRY_RUN:
        errors.append(
            "Refusing to start: BOT_E_ENV=live AND BOT_E_DRY_RUN=true "
            "(contradictory — set DRY_RUN=false to trade for real)"
        )

    return errors
