"""Pure Strategy E entry decision."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from bots.bot_d_spike import config as cfg
from bots.bot_d_spike.discovery import SpikeCandidate


@dataclass(frozen=True)
class EntryDecision:
    candidate: SpikeCandidate
    enter: bool
    reason: str
    size_usd: Decimal | None = None


def decide_entry(candidate: SpikeCandidate) -> EntryDecision:
    if cfg.ENTRY_HALT:
        return EntryDecision(candidate, False, "entry_halt")
    if candidate.city in cfg.CITY_BLACKLIST:
        return EntryDecision(candidate, False, "city_blacklisted")
    if candidate.city not in cfg.CITY_WHITELIST:
        return EntryDecision(candidate, False, "city_not_whitelisted")
    if not (cfg.ENTRY_PRICE_MIN <= candidate.best_ask <= cfg.ENTRY_PRICE_MAX):
        return EntryDecision(candidate, False, "price_outside_band")
    if not (cfg.TTR_MIN_HOURS <= candidate.hours_to_resolution < cfg.TTR_MAX_HOURS):
        return EntryDecision(candidate, False, "ttr_outside_window")
    if candidate.spread > cfg.MAX_SPREAD_USD:
        return EntryDecision(candidate, False, "spread_too_wide")
    if candidate.depth_at_ask_shares < cfg.MIN_DEPTH_AT_ASK_SHARES:
        return EntryDecision(candidate, False, "ask_depth_too_low")
    return EntryDecision(candidate, True, "all_gates_passed", cfg.PER_POSITION_SIZE_USD)
