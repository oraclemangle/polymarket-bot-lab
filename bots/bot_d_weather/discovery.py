"""Polymarket temperature-market discovery via Gamma API.

Parses question patterns like:
  "Will the highest temperature in New York City be between 86-87°F on April 17?"
  "Will the highest temperature in Houston be 79°F or below on April 17?"
  "Will the highest temperature in Tokyo be 19°C on April 16?"
  "Will the lowest temperature in London be 6°C or below on April 15?"
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from bots.bot_d_weather.config import CITIES, SETTLEMENT_SPECS, resolve_city

log = logging.getLogger(__name__)

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
GAMMA_EVENTS_SLUG_URL = "https://gamma-api.polymarket.com/events/slug"

EVENT_CITY_SLUGS: dict[str, str] = {
    "NYC": "nyc",
    "Chicago": "chicago",
    "Dallas": "dallas",
    "Atlanta": "atlanta",
    "Miami": "miami",
    "Houston": "houston",
    "Austin": "austin",
    "LA": "los-angeles",
    "Seattle": "seattle",
    "SF": "san-francisco",
    "Denver": "denver",
    "London": "london",
    "Tokyo": "tokyo",
    "Seoul": "seoul",
    "Shanghai": "shanghai",
    "Beijing": "beijing",
    "Buenos Aires": "buenos-aires",
    "Helsinki": "helsinki",
    "Milan": "milan",
    "Kuala Lumpur": "kuala-lumpur",
    "Sydney": "sydney",
    "Lagos": "lagos",
    "Manila": "manila",
    "Hong Kong": "hong-kong",
    "Lucknow": "lucknow",
    "Tel Aviv": "tel-aviv",
    "Toronto": "toronto",
    "Madrid": "madrid",
    "Paris": "paris",
    "Moscow": "moscow",
    "Istanbul": "istanbul",
    "Cape Town": "cape-town",
    "Jakarta": "jakarta",
    "Qingdao": "qingdao",
    "Shenzhen": "shenzhen",
    "Taipei": "taipei",
    "Wuhan": "wuhan",
    "Guangzhou": "guangzhou",
    "Karachi": "karachi",
    "Panama City": "panama-city",
    "Ankara": "ankara",
}


@dataclass(frozen=True)
class WeatherMarket:
    gamma_id: str
    slug: str
    question: str
    city: str           # resolved city key (e.g. "NYC", "Tokyo")
    date: str           # ISO date YYYY-MM-DD
    temp_type: str      # "high" | "low"
    direction: str      # "between" | "above" | "below" | "exact"
    range_low_f: float | None   # lower bound (°F), None for "below"
    range_high_f: float | None  # upper bound (°F), None for "above"
    unit: str           # "F" | "C"
    yes_token_id: str
    no_token_id: str
    yes_price: Decimal | None
    volume_24h_usd: Decimal | None
    end_date: datetime | None = None  # Gamma-reported resolution time (UTC)


def _c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


# --- Question parsing ---------------------------------------------------------

# Pattern 1: "between X-Y°F" or "between X-Y°C"
_PAT_BETWEEN = re.compile(
    r"Will the (highest|lowest) temperature in (.+?) be between (\d+)-(\d+)°([FC])\s+on\s+(.+?)\?",
    re.IGNORECASE,
)

# Pattern 2: "X°F or below" / "X°F or above" / "X°C or below" / "X°C or above"
_PAT_OR_BOUND = re.compile(
    r"Will the (highest|lowest) temperature in (.+?) be (\d+)°([FC])\s+or\s+(below|above)\s+on\s+(.+?)\?",
    re.IGNORECASE,
)

# Pattern 3: exact "X°C" or "X°F" (single bucket, no "or below/above")
_PAT_EXACT = re.compile(
    r"Will the (highest|lowest) temperature in (.+?) be (\d+)°([FC])\s+on\s+(.+?)\?",
    re.IGNORECASE,
)


def _parse_date(date_text: str, city_tz: str | None = None) -> str | None:
    """Parse 'April 17' or 'April 17, 2026' to ISO date.

    K2.6 audit 2026-04-21 (bug #4): EOD boundary must be in the **city's**
    local timezone, not UTC. Tokyo markets resolve on JST (UTC+9); at
    15:00 UTC on April 20 the Tokyo day has already ended, but UTC-EOD
    would still think April 20 is "today". Pass ``city_tz`` (e.g.
    ``"Asia/Tokyo"``) from ``parse_weather_question`` after city
    resolution; fall back to UTC if None (preserves original behaviour
    for callers that don't yet thread the timezone).
    """
    date_text = date_text.strip().rstrip("?").strip()
    now = datetime.now(UTC)
    if city_tz:
        try:
            # zoneinfo is stdlib since 3.9; no extra dep.
            from zoneinfo import ZoneInfo  # type: ignore[import-not-found]
            tz = ZoneInfo(city_tz)
        except Exception:
            tz = UTC  # type: ignore[assignment]
    else:
        tz = UTC  # type: ignore[assignment]

    for fmt in ("%B %d, %Y", "%B %d %Y", "%B %d"):
        try:
            dt = datetime.strptime(date_text, fmt)
            year = dt.year if dt.year > 1900 else now.year
            candidate_eod = datetime(
                year, dt.month, dt.day, 23, 59, 59, tzinfo=tz
            )
            # Roll forward only if yearless AND the entire day has passed
            # in the city's local timezone.
            if candidate_eod < now and dt.year <= 1900:
                year += 1
            return datetime(year, dt.month, dt.day).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_weather_question(question: str) -> dict[str, Any] | None:
    """Parse a temperature market question. Returns a dict or None."""

    # Between X-Y°F/C
    m = _PAT_BETWEEN.search(question)
    if m:
        temp_type_raw, city_raw, lo, hi, unit, date_raw = m.groups()
        city = resolve_city(city_raw)
        if city is None:
            log.warning("bot_d.discovery.unknown_city city=%r question=%r", city_raw[:40], question[:120])
            return None
        date = _parse_date(date_raw, CITIES[city].timezone)
        if not date:
            return None
        lo_f = float(lo)
        hi_f = float(hi)
        if unit.upper() == "C":
            lo_f = _c_to_f(lo_f)
            hi_f = _c_to_f(hi_f)
        return {
            "city": city,
            "date": date,
            "temp_type": "high" if "high" in temp_type_raw.lower() else "low",
            "direction": "between",
            "range_low_f": lo_f,
            "range_high_f": hi_f,
            "unit": unit.upper(),
        }

    # X°F/C or below/above
    m = _PAT_OR_BOUND.search(question)
    if m:
        temp_type_raw, city_raw, val, unit, bound, date_raw = m.groups()
        city = resolve_city(city_raw)
        if city is None:
            log.warning("bot_d.discovery.unknown_city city=%r question=%r", city_raw[:40], question[:120])
            return None
        date = _parse_date(date_raw, CITIES[city].timezone)
        if not date:
            return None
        val_f = float(val)
        if unit.upper() == "C":
            val_f = _c_to_f(val_f)
        direction = bound.lower()
        return {
            "city": city,
            "date": date,
            "temp_type": "high" if "high" in temp_type_raw.lower() else "low",
            "direction": direction,
            "range_low_f": val_f if direction == "above" else None,
            "range_high_f": val_f if direction == "below" else None,
            "unit": unit.upper(),
        }

    # Exact X°F/C (single Celsius bucket = ±0.5°C; single Fahrenheit = exact)
    m = _PAT_EXACT.search(question)
    if m:
        # Phase 3 audit 2026-04-17 (Gemini): blacklist thin-liquidity exact
        # buckets. Config flag allows re-enabling if operator needs them.
        from bots.bot_d_weather.config import BOT_D_BLACKLIST_EXACT_TEMP
        if BOT_D_BLACKLIST_EXACT_TEMP:
            return None
        temp_type_raw, city_raw, val, unit, date_raw = m.groups()
        city = resolve_city(city_raw)
        if city is None:
            log.warning("bot_d.discovery.unknown_city city=%r question=%r", city_raw[:40], question[:120])
            return None
        date = _parse_date(date_raw, CITIES[city].timezone)
        if not date:
            return None
        val_f = float(val)
        if unit.upper() == "C":
            # Celsius bucket: exactly X°C means [X, X+1) → [X_f, (X+1)_f)
            lo_f = _c_to_f(val_f)
            hi_f = _c_to_f(val_f + 1.0)
        else:
            # Fahrenheit exact: treat as [X, X+1)
            lo_f = val_f
            hi_f = val_f + 1.0
        return {
            "city": city,
            "date": date,
            "temp_type": "high" if "high" in temp_type_raw.lower() else "low",
            "direction": "between",
            "range_low_f": lo_f,
            "range_high_f": hi_f,
            "unit": unit.upper(),
        }

    return None


# --- Gamma API fetch ----------------------------------------------------------

def _extract_tokens(market: dict[str, Any]) -> tuple[str, str] | None:
    ids = market.get("clobTokenIds") or []
    outcomes = market.get("outcomes") or []
    if isinstance(ids, str):
        try:
            ids = json.loads(ids)
        except Exception:
            return None
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            return None
    if len(ids) != 2 or len(outcomes) != 2:
        return None
    yes_idx = next((i for i, o in enumerate(outcomes) if str(o).lower() == "yes"), None)
    no_idx = next((i for i, o in enumerate(outcomes) if str(o).lower() == "no"), None)
    if yes_idx is None or no_idx is None:
        return None
    return str(ids[yes_idx]), str(ids[no_idx])


def _extract_yes_price(market: dict[str, Any]) -> Decimal | None:
    raw = market.get("outcomePrices")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if isinstance(raw, list) and len(raw) == 2:
        outcomes = market.get("outcomes")
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except Exception:
                return None
        if isinstance(outcomes, list) and len(outcomes) == 2:
            yes_idx = next((i for i, o in enumerate(outcomes) if str(o).lower() == "yes"), None)
            if yes_idx is not None:
                try:
                    return Decimal(str(raw[yes_idx]))
                except Exception:
                    return None
    ltp = market.get("lastTradePrice")
    if ltp is not None:
        try:
            return Decimal(str(ltp))
        except Exception:
            return None
    return None


def _fetch_gamma_page(
    client: httpx.Client, *, limit: int = 500, tag: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch one page from Gamma API, optionally filtered by tag."""
    params: dict[str, str] = {
        "active": "true",
        "closed": "false",
        "limit": str(limit),
        "order": "volume",
        "ascending": "false",
    }
    if tag:
        params["tag_slug"] = tag
    resp = client.get(GAMMA_MARKETS_URL, params=params)
    resp.raise_for_status()
    return resp.json()


def _market_accepts_orders(market: dict[str, Any]) -> bool:
    """Return True when Gamma's market payload still exposes a live CLOB book.

    Polymarket started hiding daily-temperature events from the active/tag
    market feed while the child markets still had `acceptingOrders=true`.
    This guard lets the event-slug fallback include those markets without
    resurrecting genuinely closed/non-orderbook rows.
    """
    if market.get("acceptingOrders") is False:
        return False
    if market.get("enableOrderBook") is False:
        return False
    return True


def _slug_date(dt: datetime) -> str:
    return f"{dt.strftime('%B').lower()}-{dt.day}-{dt.year}"


def _candidate_event_slugs(days_ahead: int = 2) -> list[str]:
    """Generate current daily-temperature event slugs for known city/date lanes."""
    slugs: list[str] = []
    seen: set[str] = set()
    now_utc = datetime.now(UTC)
    live_verified_cities = {
        city for city, spec in SETTLEMENT_SPECS.items() if spec.verified
    }
    for city, cfg in CITIES.items():
        if city not in live_verified_cities:
            continue
        city_slug = EVENT_CITY_SLUGS.get(city)
        if not city_slug:
            continue
        try:
            from zoneinfo import ZoneInfo  # type: ignore[import-not-found]
            now_local = now_utc.astimezone(ZoneInfo(cfg.timezone))
        except Exception:
            now_local = now_utc
        for offset in range(days_ahead + 1):
            date_slug = _slug_date(now_local + timedelta(days=offset))
            for temp_type in ("highest", "lowest"):
                slug = f"{temp_type}-temperature-in-{city_slug}-on-{date_slug}"
                if slug not in seen:
                    seen.add(slug)
                    slugs.append(slug)
    return slugs


def _fetch_gamma_event_markets(client: httpx.Client, slug: str) -> list[dict[str, Any]]:
    resp = client.get(f"{GAMMA_EVENTS_SLUG_URL}/{slug}")
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    event = resp.json()
    markets = event.get("markets") or []
    if not isinstance(markets, list):
        return []
    return [m for m in markets if isinstance(m, dict) and _market_accepts_orders(m)]


def _fetch_event_slug_markets(client: httpx.Client) -> list[dict[str, Any]]:
    markets: list[dict[str, Any]] = []
    for slug in _candidate_event_slugs():
        try:
            markets.extend(_fetch_gamma_event_markets(client, slug))
        except Exception as exc:
            log.debug("gamma: event slug fallback failed slug=%s err=%s", slug, exc)
    return markets


def fetch_weather_markets(
    *,
    client: httpx.Client | None = None,
    limit: int = 500,
) -> list[WeatherMarket]:
    """Fetch active temperature markets from Gamma.

    H-02 fix: queries BOTH the general top-500-by-volume AND a dedicated
    tag-filtered search for 'daily-temperature' (the current Polymarket tag
    slug). This ensures weather markets aren't lost if their volume drops
    below the top-500 threshold. Dedupes by gamma_id.
    """
    owns = client is None
    c = client or httpx.Client(timeout=15.0, headers={"User-Agent": "bot-d/0.1"})
    try:
        # Two-pass fetch: general (catches high-volume weather markets already
        # in the top 500) + tag-specific (catches all temperature markets
        # regardless of volume rank).
        general = _fetch_gamma_page(c, limit=limit)
        # Try multiple tag slugs — Polymarket has historically renamed these.
        tagged: list[dict[str, Any]] = []
        for tag in ("daily-temperature", "temperature", "weather"):
            try:
                tagged = _fetch_gamma_page(c, limit=200, tag=tag)
                if tagged:
                    log.debug("gamma: tag '%s' returned %d markets", tag, len(tagged))
                    break
            except Exception:
                continue
        # Merge + dedupe by id/conditionId.
        seen_ids: set[str] = set()
        markets: list[dict[str, Any]] = []
        for m in general + tagged:
            mid = str(m.get("id") or m.get("conditionId") or "")
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                markets.append(m)
        if not any(parse_weather_question(m.get("question") or "") for m in markets):
            fallback = _fetch_event_slug_markets(c)
            for m in fallback:
                mid = str(m.get("id") or m.get("conditionId") or "")
                if mid and mid not in seen_ids:
                    seen_ids.add(mid)
                    markets.append(m)
            if fallback:
                log.info("gamma: event-slug fallback returned %d markets", len(fallback))
    finally:
        if owns:
            c.close()

    out: list[WeatherMarket] = []
    for m in markets:
        q = m.get("question") or ""
        parsed = parse_weather_question(q)
        if not parsed:
            continue
        toks = _extract_tokens(m)
        if not toks:
            continue
        yes_tok, no_tok = toks
        yes_price = _extract_yes_price(m)
        vol = m.get("volume24hr")
        try:
            vol_dec = Decimal(str(vol)) if vol is not None else None
        except Exception:
            vol_dec = None
        end_date_raw = m.get("endDate")
        end_date_dt: datetime | None = None
        if end_date_raw:
            try:
                # Gamma returns ISO 8601 like "2026-04-17T12:00:00Z"
                end_date_dt = datetime.fromisoformat(
                    str(end_date_raw).replace("Z", "+00:00")
                )
            except Exception:
                end_date_dt = None
        out.append(WeatherMarket(
            gamma_id=str(m.get("id") or m.get("conditionId") or ""),
            slug=str(m.get("slug") or ""),
            question=q,
            city=parsed["city"],
            date=parsed["date"],
            temp_type=parsed["temp_type"],
            direction=parsed["direction"],
            range_low_f=parsed["range_low_f"],
            range_high_f=parsed["range_high_f"],
            unit=parsed["unit"],
            yes_token_id=yes_tok,
            no_token_id=no_tok,
            yes_price=yes_price,
            volume_24h_usd=vol_dec,
            end_date=end_date_dt,
        ))
    log.info("gamma: %d markets scanned, %d temperature candidates", len(markets), len(out))
    return out
