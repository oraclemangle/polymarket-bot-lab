"""Configuration for Bot H Maker V2 (paper-only per ADR-134).

Two filter scopes:

- **ACTIVE_QUOTE_CELLS** (Phase 2): cells where the future quote engine
  will post quotes. Strictly limited per ADR-134 to politics 0-10c and
  sports 10-20c — the only cells that survived the outlier-robustness
  probe (worst-combo excl-top-5 ROI > +20%).

- **RECORDER_FILTER**: cells captured by the WSS recorder. Wider than the
  active quote scope so the operator can re-run the maker-flow simulator
  with real forward data and test counterfactual cell mixes. Includes
  every politics + sports + awards + crypto market with YES price in the
  0c-50c range; weather is excluded because builder-code rebate is 0
  there (no maker upside) and Strategy E2 is already covering that
  category at the taker side.

The recorder runs Phase 1; the quote engine ships in Phase 2 after
operator review of recorder output.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

BOT_H_MAKER_V2_BOT_ID = os.getenv("BOT_H_MAKER_V2_BOT_ID", "bot_h_maker_v2")
PAPER_ONLY = True

# Disk path for the dedicated recorder DB. Separate from the main trading
# DB so high-volume writes don't slow main-DB queries and the recorder DB
# can be rsynced off the host independently for analysis.
RECORDER_DB_PATH = Path(
    os.getenv(
        "BOT_H_MAKER_V2_RECORDER_DB_PATH",
        "./data/maker_recorder.db",
    )
).resolve()

# Subscription / scan timing
GAMMA_SCAN_INTERVAL_SEC = float(os.getenv("BOT_H_MAKER_V2_GAMMA_SCAN_INTERVAL_SEC", "300"))
HEARTBEAT_INTERVAL_SEC = float(os.getenv("BOT_H_MAKER_V2_HEARTBEAT_INTERVAL_SEC", "30"))
WRITER_FLUSH_INTERVAL_SEC = float(os.getenv("BOT_H_MAKER_V2_WRITER_FLUSH_INTERVAL_SEC", "1.0"))

# Hard cap on simultaneous WSS subscription tokens. Politics + sports
# markets surge during election windows; this cap prevents runaway WSS
# resource use. Each market = 2 token IDs (YES + NO), so 600 tokens =
# 300 markets. If exceeded, the discovery prefers higher-volume markets.
MAX_TOKENS_SUBSCRIBED = int(os.getenv("BOT_H_MAKER_V2_MAX_TOKENS_SUBSCRIBED", "600"))

# Recorder coverage filter: which markets end up subscribed by the WSS.
# Wide on purpose so analysis can reach beyond the active quote cells.
RECORDER_CATEGORIES: tuple[str, ...] = (
    "politics",
    "sports",
    "awards",
    "crypto",
)
RECORDER_PRICE_MIN = Decimal(os.getenv("BOT_H_MAKER_V2_RECORDER_PRICE_MIN", "0.01"))
RECORDER_PRICE_MAX = Decimal(os.getenv("BOT_H_MAKER_V2_RECORDER_PRICE_MAX", "0.50"))
RECORDER_VOLUME_FLOOR_USD = Decimal(
    os.getenv("BOT_H_MAKER_V2_RECORDER_VOLUME_FLOOR_USD", "1000")
)

# Tags used in the Polymarket Gamma API to fan out market discovery
# beyond the default page. Empty list = single default page only.
RECORDER_GAMMA_TAGS: tuple[str, ...] = (
    "politics",
    "elections",
    "sports",
    "nba",
    "nfl",
    "mlb",
    "soccer",
    "world-cup",
    "fifa",
    "awards",
    "oscars",
    "grammys",
    "crypto",
    "bitcoin",
    "ethereum",
)


@dataclass(frozen=True)
class CellFilter:
    """One (category, price_band) cell. Used for both active quote
    selection (Phase 2) and per-cell counterfactual filtering at analysis
    time (Phase 1+)."""

    category: str
    price_min: Decimal  # inclusive
    price_max: Decimal  # exclusive
    label: str

    def contains(self, category: str, price: Decimal) -> bool:
        return (
            category == self.category
            and self.price_min <= price < self.price_max
        )


# Phase 2 active-quote scope. ADR-134 restricts the quote engine to these
# cells only. Anything else captured by the recorder is for analysis,
# not for quotes.
ACTIVE_QUOTE_CELLS: tuple[CellFilter, ...] = (
    CellFilter(
        category="politics",
        price_min=Decimal("0.00"),
        price_max=Decimal("0.10"),
        label="politics_0_10c",
    ),
    CellFilter(
        category="sports",
        price_min=Decimal("0.10"),
        price_max=Decimal("0.20"),
        label="sports_10_20c",
    ),
)


def question_to_category(question: str) -> str:
    """Heuristic category classifier mirroring the maker-flow simulator's
    `m_v2.category` SQL CASE expression."""
    q = (question or "").lower()
    if "temperature" in q:
        return "weather"
    if any(k in q for k in ("bitcoin", "btc", "ethereum", "eth", "solana", "sol ")):
        return "crypto"
    if any(k in q for k in ("election", "primary", "president")):
        return "politics"
    if any(k in q for k in ("champion", "nba", "nfl", "mlb", "world cup", "premier league")):
        return "sports"
    if any(k in q for k in ("oscar", "nobel", "grammy")):
        return "awards"
    return "_other"


def is_active_quote_cell(category: str, price: Decimal) -> bool:
    """True if the (category, price) is in an active-quote cell per
    ADR-134 — i.e. Phase 2 will post a quote here. Phase 1 recorder
    captures wider scope; this helper is for the future quote engine."""
    return any(cell.contains(category, price) for cell in ACTIVE_QUOTE_CELLS)
