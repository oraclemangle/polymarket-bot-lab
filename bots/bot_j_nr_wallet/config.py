"""Config for Bot J — Near-Resolution Wallet paper lane.

Reads wallet_tag_forward.db (observer) and records paper entries when
top-7 wallets buy sports/esports tokens at 30-70c implied.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Observer DB (read-only, the bot container shared)
# ---------------------------------------------------------------------------
DEFAULT_OBSERVER_DB = REPO_ROOT / "data" / "wallet_tag_forward.db"

# ---------------------------------------------------------------------------
# Wallet cohort (ADR-151, 7-wallet PASS)
# ---------------------------------------------------------------------------
WALLET_COHORT: frozenset[str] = frozenset(
    [
        "0xF00D0000000000000000000000000000000000d8",
        "0xF00D0000000000000000000000000000000000d9",
        "0xF00D0000000000000000000000000000000000da",
        "0xF00D0000000000000000000000000000000000db",
        "0xF00D0000000000000000000000000000000000dc",
        "0xF00D0000000000000000000000000000000000dd",
        "0xF00D0000000000000000000000000000000000de",
    ]
)

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
MIN_PRICE = 0.30
MAX_PRICE = 0.70
DIRECTION = "BUY"

SPORTS_KEYWORDS: frozenset[str] = frozenset(
    [
        # esports (must co-occur with an esports keyword for "game"/"map")
        "lol",
        "cs:",
        "counter-strike",
        "esports",
        "bo3",
        "bo5",
        "league of legends",
        # soccer / football
        "soccer",
        "football",
        "fc ",
        "win on",
        "vs.",
        # other sports
        "nfl",
        "nba",
        "baseball",
        "tennis",
        "golf",
        "hockey",
        "ufc",
        "boxing",
        "mma",
    ]
)

# ---------------------------------------------------------------------------
# Paper sizing
# ---------------------------------------------------------------------------
STAKE_USD = 10.0  # fixed notional per paper entry
MAX_CONCURRENT_POSITIONS = 20
MAX_DAILY_ENTRIES = 20

# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
POLL_INTERVAL_S = 60.0
COOLDOWN_S = 300  # 5 min: do not re-enter the same condition after a paper fill

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------
PAPER_ONLY = True
BOT_ID = "bot_j_nr_wallet"

# ---------------------------------------------------------------------------
# FX rate (paper-only, updated manually)
# ---------------------------------------------------------------------------
USD_GBP_RATE = "0.79"
