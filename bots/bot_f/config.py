"""Bot F configuration — Hunter thresholds and Mirror/Trigger settings.

Thresholds are BACKTEST STARTING POINTS, not live defaults. Live values
come from the 2-week measurement phase + backtest calibration.

Per operator feedback in CLAUDE.md: safety controls should be tunable,
not hard walls. Every threshold is env-overridable.
"""

from __future__ import annotations

import os
from decimal import Decimal

BOT_ID = "bot_f"

# --- Data sources (public Polymarket APIs, no auth required) ---
LB_API_URL = os.environ.get("BOT_F_LB_API_URL", "https://lb-api.polymarket.com")
DATA_API_URL = os.environ.get("BOT_F_DATA_API_URL", "https://data-api.polymarket.com")
GAMMA_API_URL = os.environ.get("BOT_F_GAMMA_API_URL", "https://gamma-api.polymarket.com")

# --- Hunter thresholds ---
# Backtest starting points (not live defaults).
HUNTER_MIN_TRADES = int(os.environ.get("BOT_F_HUNTER_MIN_TRADES", "100"))
HUNTER_MIN_WIN_RATE = float(os.environ.get("BOT_F_HUNTER_MIN_WIN_RATE", "0.62"))
HUNTER_MIN_PROFIT_FACTOR = float(os.environ.get("BOT_F_HUNTER_MIN_PROFIT_FACTOR", "1.8"))
HUNTER_LOOKBACK_DAYS = int(os.environ.get("BOT_F_HUNTER_LOOKBACK_DAYS", "90"))
HUNTER_TOP_N = int(os.environ.get("BOT_F_HUNTER_TOP_N", "40"))

# How many wallets to pull from the leaderboard before filtering.
HUNTER_LEADERBOARD_SAMPLE = int(os.environ.get("BOT_F_HUNTER_LEADERBOARD_SAMPLE", "200"))

# How many trades to fetch per wallet (for metric computation).
HUNTER_TRADES_PER_WALLET = int(os.environ.get("BOT_F_HUNTER_TRADES_PER_WALLET", "500"))

# Recent-edge check: trailing-30d P&L ≥ 80% of trailing 6-month median monthly P&L.
# Kills wallets whose edge is compressing out (Grok/Codex blind-spot #1).
HUNTER_RECENT_EDGE_RATIO = float(os.environ.get("BOT_F_HUNTER_RECENT_EDGE_RATIO", "0.80"))

# Grok addition: sharper 7d-vs-30d P&L ratio — 7d P&L must be ≥ 50% of 30d P&L / 4
# (i.e. the latest week is pulling at least its proportional share of the month).
HUNTER_7D_MIN_SHARE = float(os.environ.get("BOT_F_HUNTER_7D_MIN_SHARE", "0.50"))

# Crowd-edge category deprioritization: skip categories where the top-50-wallet
# rolling-30d ROI has dropped >40% vs 6-month median. Kills saturated categories.
HUNTER_CROWD_EDGE_DROP_PCT = float(os.environ.get("BOT_F_HUNTER_CROWD_EDGE_DROP_PCT", "0.40"))

# Bot F must not overlap Bot B's LLM-thesis category. Starting blacklist:
HUNTER_CATEGORY_BLACKLIST: frozenset[str] = frozenset(
    os.environ.get(
        "BOT_F_CATEGORY_BLACKLIST",
        "geopolitics,politics",
    ).lower().split(",")
)

# --- Mirror settings (Phase 1, not live yet) ---
MIRROR_DEDUP_WINDOW_S = int(os.environ.get("BOT_F_MIRROR_DEDUP_S", "60"))
MIRROR_SIGNAL_MAX_AGE_S = int(os.environ.get("BOT_F_MIRROR_SIGNAL_MAX_AGE_S", "90"))

# --- Trigger settings (Phase 2, conditional) ---
TRIGGER_MAX_BANKROLL_FRACTION = float(
    os.environ.get("BOT_F_TRIGGER_MAX_BANKROLL_FRACTION", "0.03")
)
TRIGGER_MAX_POSITIONS_PER_MARKET = int(
    os.environ.get("BOT_F_TRIGGER_MAX_POS_PER_MARKET", "2")
)
TRIGGER_MAX_SPREAD_CENTS = int(
    os.environ.get("BOT_F_TRIGGER_MAX_SPREAD_CENTS", "4")
)
TRIGGER_MIN_TTR_HOURS = int(os.environ.get("BOT_F_TRIGGER_MIN_TTR_HOURS", "6"))
TRIGGER_WHALE_POSITION_CAP_FRACTION = float(
    os.environ.get("BOT_F_TRIGGER_WHALE_POS_CAP", "0.25")
)

# Portfolio notional cap across ALL mirrored positions (Grok blind-spot #5).
TRIGGER_PORTFOLIO_NOTIONAL_CAP = Decimal(
    os.environ.get("BOT_F_TRIGGER_PORTFOLIO_CAP", "0.20")
)  # 20% of bankroll across all open mirrored positions

# Paper bankroll (Phase 0 + 1 are read-only; this is only used if Phase 2 launches).
BOT_F_BANKROLL_USD = Decimal(os.environ.get("BOT_F_BANKROLL_USD", "500"))
