"""Discovery for Bot D-Spike-Short weather candidates.

Re-uses parsing helpers from `bots.bot_d_spike.discovery` (pattern matchers,
gamma fetch, market normalization) — those have no TTR or bot_id coupling
and are stable across both lanes. Only the candidate filtering (which
applies the cfg-specific TTR window) is local to this module so the short
lane can diverge cleanly later if needed.

`SpikeCandidate` and `SpikeMarket` dataclasses are re-exported from
bot_d_spike.discovery so both lanes use compatible types and the dashboard
can join on `condition_id` without a translation layer.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

import requests

from bots.bot_d_spike.discovery import (
    SpikeCandidate,
    SpikeMarket,
    fetch_spike_markets,
    hours_to_resolution,
    parse_spike_weather_question,
)
from bots.bot_d_spike_short import config as cfg
from core.clob import OrderBook

log = logging.getLogger(__name__)

__all__ = [
    "SpikeCandidate",
    "SpikeMarket",
    "candidate_from_market",
    "fetch_spike_markets",
    "find_eligible_candidates",
    "hours_to_resolution",
    "in_ttr_window",
    "parse_spike_weather_question",
]


def in_ttr_window(end_date: datetime, now: datetime | None = None) -> bool:
    hours = hours_to_resolution(end_date, now)
    return cfg.TTR_MIN_HOURS <= hours < cfg.TTR_MAX_HOURS


def _top_depth_at_ask(book: OrderBook, best_ask: Decimal) -> Decimal:
    return sum((size for price, size in book.asks if price == best_ask), Decimal("0"))


def candidate_from_market(
    market: SpikeMarket,
    *,
    clob: object,
    now: datetime | None = None,
) -> SpikeCandidate | None:
    city_meta = cfg.CITY_WHITELIST.get(market.city)
    if city_meta is None or market.city in cfg.CITY_BLACKLIST:
        return None
    hours = hours_to_resolution(market.end_date, now)
    if not (cfg.TTR_MIN_HOURS <= hours < cfg.TTR_MAX_HOURS):
        return None
    book = clob.get_book(market.yes_token_id)
    best_ask = book.best_ask()
    best_bid = book.best_bid()
    if best_ask is None or best_bid is None:
        return None
    spread = best_ask - best_bid
    depth = _top_depth_at_ask(book, best_ask)
    if not (cfg.ENTRY_PRICE_MIN <= best_ask <= cfg.ENTRY_PRICE_MAX):
        return None
    if spread > cfg.MAX_SPREAD_USD:
        return None
    if depth < cfg.MIN_DEPTH_AT_ASK_SHARES:
        return None
    return SpikeCandidate(
        market=market,
        yes_token_id=market.yes_token_id,
        best_ask=best_ask,
        best_bid=best_bid,
        spread=spread,
        depth_at_ask_shares=depth,
        hours_to_resolution=hours,
        city=market.city,
        city_tier=int(city_meta["tier"]),
    )


def find_eligible_candidates(
    *,
    clob: object,
    client: requests.Session | None = None,
    now: datetime | None = None,
    limit: int = 500,
) -> list[SpikeCandidate]:
    candidates: list[SpikeCandidate] = []
    for market in fetch_spike_markets(client=client, limit=limit):
        try:
            candidate = candidate_from_market(market, clob=clob, now=now)
        except Exception as exc:
            log.info(
                "bot_d_spike_short.discovery.book_skip condition_id=%s err=%s",
                market.condition_id,
                type(exc).__name__,
            )
            continue
        if candidate is not None:
            candidates.append(candidate)
    candidates.sort(key=lambda c: (c.market.end_date, c.best_ask, c.city))
    return candidates
