"""Configuration for Bot D-Spike-Short (Strategy E2 short-TTR weather variant).

All strategy constants come from the WANGZJ V2 re-validation Test C
(2026-05-08): `<6h x weather x cheap-YES x city whitelist` slice.
Empirical evidence: n=40,496 trades, +36.1% as-is ROI, +11.1% top-5 robust.
This lane is paper-only; live deployment requires a new ADR per ADR-133.

City whitelist, blacklist, alias map, price band, depth/spread floors are
identical to `bots/bot_d_spike/config.py`. The TTR window is `[0, 6)` hours
and the bot_id is distinct so attribution stays clean.
"""

from __future__ import annotations

import os
from decimal import Decimal

BOT_D_SPIKE_SHORT_BOT_ID = os.getenv("BOT_D_SPIKE_SHORT_BOT_ID", "bot_d_spike_short")

PAPER_ONLY = True
ENTRY_HALT = os.getenv("BOT_D_SPIKE_SHORT_ENTRY_HALT", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

ENTRY_PRICE_MIN = Decimal(os.getenv("BOT_D_SPIKE_SHORT_ENTRY_PRICE_MIN", "0.01"))
ENTRY_PRICE_MAX = Decimal(os.getenv("BOT_D_SPIKE_SHORT_ENTRY_PRICE_MAX", "0.15"))

TTR_MIN_HOURS = Decimal(os.getenv("BOT_D_SPIKE_SHORT_TTR_MIN_HOURS", "0"))
TTR_MAX_HOURS = Decimal(os.getenv("BOT_D_SPIKE_SHORT_TTR_MAX_HOURS", "6"))

PER_POSITION_SIZE_USD = Decimal(os.getenv("BOT_D_SPIKE_SHORT_POSITION_SIZE_USD", "2"))
MAX_CONCURRENT_POSITIONS = int(os.getenv("BOT_D_SPIKE_SHORT_MAX_OPEN", "50"))
MAX_DEPLOYED_USD = Decimal(os.getenv("BOT_D_SPIKE_SHORT_MAX_DEPLOYED_USD", "200"))
MAX_DAILY_ENTRIES = int(os.getenv("BOT_D_SPIKE_SHORT_MAX_DAILY_ENTRIES", "30"))

MIN_DEPTH_AT_ASK_SHARES = Decimal(os.getenv("BOT_D_SPIKE_SHORT_MIN_DEPTH_SHARES", "25"))
MAX_SPREAD_USD = Decimal(os.getenv("BOT_D_SPIKE_SHORT_MAX_SPREAD_USD", "0.03"))
SCAN_INTERVAL_S = float(os.getenv("BOT_D_SPIKE_SHORT_SCAN_INTERVAL_S", "60"))
PAPER_RESOLVE_INTERVAL_S = float(os.getenv("BOT_D_SPIKE_SHORT_PAPER_RESOLVE_INTERVAL_S", "1800"))

DAILY_REPORT_JSON = os.getenv(
    "BOT_D_SPIKE_SHORT_DAILY_REPORT_JSON",
    "data/reports/bot_d_spike_short/latest.json",
)
DAILY_REPORT_MD = os.getenv(
    "BOT_D_SPIKE_SHORT_DAILY_REPORT_MD",
    "data/reports/bot_d_spike_short/latest.md",
)

CITY_WHITELIST: dict[str, dict[str, float | int]] = {
    "Hong Kong": {"tier": 1, "edge_pp": 7.26, "ev_per_dollar": 2.51},
    "Shenzhen": {"tier": 1, "edge_pp": 9.79, "ev_per_dollar": 1.77},
    "Wellington": {"tier": 1, "edge_pp": 4.68, "ev_per_dollar": 1.13},
    "Tokyo": {"tier": 1, "edge_pp": 4.34, "ev_per_dollar": 1.06},
    "Ankara": {"tier": 2, "edge_pp": 2.86, "ev_per_dollar": 0.77},
    "New York": {"tier": 2, "edge_pp": 2.29, "ev_per_dollar": 0.65},
    "Madrid": {"tier": 2, "edge_pp": 1.87, "ev_per_dollar": 0.51},
    "Shanghai": {"tier": 2, "edge_pp": 1.45, "ev_per_dollar": 0.38},
    "Lucknow": {"tier": 3, "edge_pp": 0.65, "ev_per_dollar": 0.29},
    "Seoul": {"tier": 3, "edge_pp": 0.59, "ev_per_dollar": 0.13},
    "Tel Aviv": {"tier": 3, "edge_pp": 0.31, "ev_per_dollar": 0.09},
    "London": {"tier": 3, "edge_pp": 0.28, "ev_per_dollar": 0.08},
}

CITY_BLACKLIST = {
    "Beijing",
    "Munich",
    "Paris",
    "Toronto",
    "Singapore",
    "Atlanta",
    "Dallas",
    "Miami",
    "Seattle",
}

CITY_ALIASES: dict[str, str] = {
    "hong kong": "Hong Kong",
    "hk": "Hong Kong",
    "shenzhen": "Shenzhen",
    "wellington": "Wellington",
    "tokyo": "Tokyo",
    "ankara": "Ankara",
    "new york": "New York",
    "new york city": "New York",
    "nyc": "New York",
    "manhattan": "New York",
    "madrid": "Madrid",
    "shanghai": "Shanghai",
    "lucknow": "Lucknow",
    "seoul": "Seoul",
    "tel aviv": "Tel Aviv",
    "tel-aviv": "Tel Aviv",
    "london": "London",
    "beijing": "Beijing",
    "munich": "Munich",
    "paris": "Paris",
    "toronto": "Toronto",
    "singapore": "Singapore",
    "atlanta": "Atlanta",
    "dallas": "Dallas",
    "miami": "Miami",
    "seattle": "Seattle",
}


def normalize_city(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = " ".join(raw.strip().lower().replace(",", " ").split())
    return CITY_ALIASES.get(key)
