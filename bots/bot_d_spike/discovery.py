"""Discovery for Bot D-Spike weather candidates."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import requests

from bots.bot_d_spike import config as cfg
from core.clob import OrderBook

log = logging.getLogger(__name__)

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"


@dataclass(frozen=True)
class SpikeMarket:
    gamma_id: str
    condition_id: str
    slug: str
    question: str
    city: str
    date: str
    temp_type: str
    direction: str
    bucket: str
    yes_token_id: str
    no_token_id: str
    end_date: datetime
    yes_price_hint: Decimal | None
    volume_24h_usd: Decimal | None


@dataclass(frozen=True)
class SpikeCandidate:
    market: SpikeMarket
    yes_token_id: str
    best_ask: Decimal
    best_bid: Decimal
    spread: Decimal
    depth_at_ask_shares: Decimal
    hours_to_resolution: Decimal
    city: str
    city_tier: int


_PAT_BETWEEN = re.compile(
    r"Will the (highest|lowest) temperature in (.+?) be between (-?\d+)-(-?\d+)°([FC])\s+on\s+(.+?)\?",
    re.IGNORECASE,
)
_PAT_OR_BOUND = re.compile(
    r"Will the (highest|lowest) temperature in (.+?) be (-?\d+)°([FC])\s+or\s+(below|above)\s+on\s+(.+?)\?",
    re.IGNORECASE,
)
_PAT_EXACT = re.compile(
    r"Will the (highest|lowest) temperature in (.+?) be (?:exactly\s+)?(-?\d+)°([FC])\s+on\s+(.+?)\?",
    re.IGNORECASE,
)


def parse_spike_weather_question(question: str) -> dict[str, str] | None:
    """Parse Polymarket daily temperature bucket questions for Strategy E."""
    for kind, pat in (("between", _PAT_BETWEEN), ("bound", _PAT_OR_BOUND), ("exact", _PAT_EXACT)):
        m = pat.search(question)
        if not m:
            continue
        if kind == "between":
            temp_type_raw, city_raw, lo, hi, unit, date_raw = m.groups()
            direction = "between"
            bucket = f"{lo}-{hi}{unit.upper()}"
        elif kind == "bound":
            temp_type_raw, city_raw, value, unit, direction_raw, date_raw = m.groups()
            direction = direction_raw.lower()
            bucket = f"{value}{unit.upper()}_or_{direction}"
        else:
            temp_type_raw, city_raw, value, unit, date_raw = m.groups()
            direction = "exact"
            bucket = f"{value}{unit.upper()}"
        city = cfg.normalize_city(city_raw)
        if city is None:
            return None
        return {
            "city": city,
            "date": date_raw.strip(),
            "temp_type": "high" if temp_type_raw.lower() == "highest" else "low",
            "direction": direction,
            "bucket": bucket,
        }
    return None


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _json_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _extract_tokens(market: dict[str, Any]) -> tuple[str, str] | None:
    tokens = _json_list(market.get("clobTokenIds"))
    outcomes = _json_list(market.get("outcomes"))
    if len(tokens) != 2 or len(outcomes) != 2:
        return None
    yes_idx = next((i for i, outcome in enumerate(outcomes) if str(outcome).lower() == "yes"), None)
    no_idx = next((i for i, outcome in enumerate(outcomes) if str(outcome).lower() == "no"), None)
    if yes_idx is None or no_idx is None:
        return None
    return str(tokens[yes_idx]), str(tokens[no_idx])


def _extract_yes_price(market: dict[str, Any]) -> Decimal | None:
    prices = _json_list(market.get("outcomePrices"))
    outcomes = _json_list(market.get("outcomes"))
    if len(prices) == 2 and len(outcomes) == 2:
        yes_idx = next((i for i, outcome in enumerate(outcomes) if str(outcome).lower() == "yes"), None)
        if yes_idx is not None:
            return _decimal(prices[yes_idx])
    return _decimal(market.get("lastTradePrice"))


def _parse_end_date(raw: object) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _fetch_gamma_page(
    client: requests.Session,
    *,
    limit: int = 500,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, str] = {
        "active": "true",
        "closed": "false",
        "limit": str(limit),
        "order": "volume",
        "ascending": "false",
    }
    if tag:
        params["tag_slug"] = tag
    try:
        resp = client.get(GAMMA_MARKETS_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        log.warning(
            "bot_d_spike.discovery.gamma_fetch_failed tag=%s err=%s",
            tag or "all",
            type(exc).__name__,
        )
        return []
    return data if isinstance(data, list) else []


def fetch_spike_markets(
    *,
    client: requests.Session | None = None,
    limit: int = 500,
) -> list[SpikeMarket]:
    """Fetch active weather markets parseable by the Strategy E parser."""
    owns = client is None
    c = client or requests.Session()
    c.headers.update({"User-Agent": "bot-d-spike/0.1"})
    try:
        raw_markets: list[dict[str, Any]] = []
        raw_markets.extend(_fetch_gamma_page(c, limit=limit))
        for tag in ("daily-temperature", "temperature", "weather"):
            try:
                tagged = _fetch_gamma_page(c, limit=300, tag=tag)
            except Exception:
                continue
            raw_markets.extend(tagged)
    finally:
        if owns:
            c.close()

    seen: set[str] = set()
    out: list[SpikeMarket] = []
    for raw in raw_markets:
        gamma_id = str(raw.get("id") or "")
        condition_id = str(raw.get("conditionId") or gamma_id)
        dedup = gamma_id or condition_id
        if not dedup or dedup in seen:
            continue
        seen.add(dedup)
        question = str(raw.get("question") or "")
        parsed = parse_spike_weather_question(question)
        if parsed is None:
            continue
        tokens = _extract_tokens(raw)
        end_date = _parse_end_date(raw.get("endDate"))
        if tokens is None or end_date is None:
            continue
        yes_token, no_token = tokens
        out.append(
            SpikeMarket(
                gamma_id=gamma_id or condition_id,
                condition_id=condition_id,
                slug=str(raw.get("slug") or ""),
                question=question,
                city=parsed["city"],
                date=parsed["date"],
                temp_type=parsed["temp_type"],
                direction=parsed["direction"],
                bucket=parsed["bucket"],
                yes_token_id=yes_token,
                no_token_id=no_token,
                end_date=end_date,
                yes_price_hint=_extract_yes_price(raw),
                volume_24h_usd=_decimal(raw.get("volume24hr")),
            )
        )
    log.info("bot_d_spike.discovery.markets raw=%d parsed=%d", len(raw_markets), len(out))
    return out


def hours_to_resolution(end_date: datetime, now: datetime | None = None) -> Decimal:
    now = now or datetime.now(UTC)
    end = end_date if end_date.tzinfo is not None else end_date.replace(tzinfo=UTC)
    return Decimal(str((end - now).total_seconds() / 3600)).quantize(Decimal("0.0001"))


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
                "bot_d_spike.discovery.book_skip condition_id=%s err=%s",
                market.condition_id,
                type(exc).__name__,
            )
            continue
        if candidate is not None:
            candidates.append(candidate)
    candidates.sort(key=lambda c: (c.market.end_date, c.best_ask, c.city))
    return candidates
