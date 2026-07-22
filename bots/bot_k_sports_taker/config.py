"""Config for Bot K — Sports Taker (market-open) paper lane.

Polls the Bot H recorder DB (`data/maker_recorder.db`) for sports markets
with initial YES price in the 10-20c band, finds the first best_bid_ask tick
within N minutes of discovery, and records a paper YES buy at ask + 1 tick.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Recorder DB (read-only, the bot container shared)
# ---------------------------------------------------------------------------
DEFAULT_RECORDER_DB = REPO_ROOT / "data" / "maker_recorder.db"

# ---------------------------------------------------------------------------
# Market filters
# ---------------------------------------------------------------------------
CATEGORY = "sports"
MIN_PRICE = 0.10
MAX_PRICE = 0.20
LOOKBACK_MIN = 5  # first tick must occur within 5 min of discovery
TICK_SIZE = 0.01
MAX_TIME_TO_RESOLUTION_HOURS = 168.0

# ---------------------------------------------------------------------------
# Paper sizing
# ---------------------------------------------------------------------------
STAKE_USD = 5.0  # fixed notional per paper entry
MAX_CONCURRENT_POSITIONS = 20
MAX_DAILY_ENTRIES = 10

# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------
POLL_INTERVAL_S = 60.0
COOLDOWN_S = 300  # 5 min: do not re-enter the same condition after a paper fill

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------
PAPER_ONLY = True
BOT_ID = "bot_k_sports_taker"
