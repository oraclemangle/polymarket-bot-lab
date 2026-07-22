"""Configuration for Bot D-Spike.

All strategy constants come from the WANGZJ weather calibration report and
ADR-123/ADR-125. Live mode is limited to the ADR-164/ADR-170 tiny probe caps.
"""

from __future__ import annotations

import os
from decimal import Decimal

from core.tiny_live_probe import TinyLiveProbeSpec

BOT_D_SPIKE_BOT_ID = os.getenv("BOT_D_SPIKE_BOT_ID", "bot_d_spike")

PAPER_ONLY = os.getenv("BOT_D_SPIKE_PAPER_ONLY", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
LIVE_APPROVED_AT = os.getenv("BOT_D_SPIKE_LIVE_APPROVED_AT", "").strip()
ENTRY_HALT = os.getenv("BOT_D_SPIKE_ENTRY_HALT", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

ENTRY_PRICE_MIN = Decimal(os.getenv("BOT_D_SPIKE_ENTRY_PRICE_MIN", "0.01"))
ENTRY_PRICE_MAX = Decimal(os.getenv("BOT_D_SPIKE_ENTRY_PRICE_MAX", "0.15"))

TTR_MIN_HOURS = Decimal(os.getenv("BOT_D_SPIKE_TTR_MIN_HOURS", "6"))
TTR_MAX_HOURS = Decimal(os.getenv("BOT_D_SPIKE_TTR_MAX_HOURS", "12"))

PER_POSITION_SIZE_USD = Decimal(os.getenv("BOT_D_SPIKE_POSITION_SIZE_USD", "2"))
MAX_CONCURRENT_POSITIONS = int(os.getenv("BOT_D_SPIKE_MAX_OPEN", "10"))
MAX_DEPLOYED_USD = Decimal(os.getenv("BOT_D_SPIKE_MAX_DEPLOYED_USD", "20"))
MAX_DAILY_GROSS_USD = Decimal(os.getenv("BOT_D_SPIKE_MAX_DAILY_GROSS_USD", "10"))
MAX_DAILY_ENTRIES = int(os.getenv("BOT_D_SPIKE_MAX_DAILY_ENTRIES", "5"))

MIN_DEPTH_AT_ASK_SHARES = Decimal(os.getenv("BOT_D_SPIKE_MIN_DEPTH_SHARES", "25"))
MAX_SPREAD_USD = Decimal(os.getenv("BOT_D_SPIKE_MAX_SPREAD_USD", "0.03"))
SCAN_INTERVAL_S = float(os.getenv("BOT_D_SPIKE_SCAN_INTERVAL_S", "60"))
PAPER_RESOLVE_INTERVAL_S = float(os.getenv("BOT_D_SPIKE_PAPER_RESOLVE_INTERVAL_S", "3600"))

DAILY_REPORT_JSON = os.getenv(
    "BOT_D_SPIKE_DAILY_REPORT_JSON",
    "data/reports/bot_d_spike/latest.json",
)
DAILY_REPORT_MD = os.getenv(
    "BOT_D_SPIKE_DAILY_REPORT_MD",
    "data/reports/bot_d_spike/latest.md",
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

LIVE_PROBE_SPEC = TinyLiveProbeSpec(
    lane_id="bot_d_spike",
    display_name="Bot D-Spike 6-12h Tiny Live Probe",
    bot_id=BOT_D_SPIKE_BOT_ID,
    market_scope="6-12h TTR daily weather cheap-YES lane; positive-EV city whitelist only.",
    allowed_actions=("BUY_YES",),
    max_order_usd=Decimal("2"),
    daily_gross_cap_usd=Decimal("10"),
    open_exposure_cap_usd=Decimal("20"),
    max_concurrent_positions=10,
    kill_switches=(
        "any rule violation",
        "5 consecutive resolved losses",
        "realised P&L <= -$8",
        "CLOB/auth/reconcile fault",
        "overlap with other Bot D live exposure",
    ),
    rollback_plan=(
        "Stop and disable the Bot D-Spike live-probe service.",
        "Keep the VPS paper Spike service available for comparison.",
        "Cancel unresolved live orders only through the approved emergency path.",
        "Record the kill event in CHANGELOG, MEMORY, and the Bot D-Spike open question.",
    ),
    approval_question=(
        "the operator, approve enabling Bot D-Spike 6-12h as a tiny live probe with whitelist-only "
        "1c-15c BUY_YES entries, max order $2, daily gross $10, open exposure $20, "
        "max 10 concurrent positions, and the listed kill switches?"
    ),
    live_service_name="polymarket-bot-d-spike-live-probe-vps.service",
    notes=("Current runner still forces paper_override=True; this spec is readiness-only.",),
)


def normalize_city(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = " ".join(raw.strip().lower().replace(",", " ").split())
    return CITY_ALIASES.get(key)
