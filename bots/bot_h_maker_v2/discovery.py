"""Market discovery for the Bot H Maker V2 recorder.

Fetches active politics + sports + awards + crypto markets from the
Polymarket Gamma API, filters to the recorder scope (price 1c-50c,
volume >= $1000, valid binary YES/NO), and returns a list of
`MakerMarket` dataclasses ready to be subscribed via the WSS.

The recorder filter is intentionally wider than the active quote scope
defined in `config.py:ACTIVE_QUOTE_CELLS`. The wider data is what makes
counterfactual cell-mix analysis possible later.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import requests

from bots.bot_h_maker_v2.config import (
    RECORDER_CATEGORIES,
    RECORDER_GAMMA_TAGS,
    RECORDER_PRICE_MAX,
    RECORDER_PRICE_MIN,
    RECORDER_VOLUME_FLOOR_USD,
    question_to_category,
)

log = logging.getLogger(__name__)

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"


@dataclass(frozen=True)
class MakerMarket:
    condition_id: str
    yes_token_id: str
    no_token_id: str
    category: str
    question: str
    end_date: datetime | None
    initial_yes_price: Decimal | None
    volume_24h_usd: Decimal | None


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
    yes_idx = next((i for i, o in enumerate(outcomes) if str(o).lower() == "yes"), None)
    no_idx = next((i for i, o in enumerate(outcomes) if str(o).lower() == "no"), None)
    if yes_idx is None or no_idx is None:
        return None
    return str(tokens[yes_idx]), str(tokens[no_idx])


def _extract_yes_price(market: dict[str, Any]) -> Decimal | None:
    prices = _json_list(market.get("outcomePrices"))
    outcomes = _json_list(market.get("outcomes"))
    if len(prices) == 2 and len(outcomes) == 2:
        yes_idx = next((i for i, o in enumerate(outcomes) if str(o).lower() == "yes"), None)
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
    limit: int,
    tag: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, str] = {
        "active": "true",
        "closed": "false",
        "limit": str(limit),
        "order": "volume24hr",
        "ascending": "false",
    }
    if tag:
        params["tag_slug"] = tag
    resp = client.get(GAMMA_MARKETS_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def _market_in_filter(
    *,
    category: str,
    yes_price: Decimal | None,
    volume_24h_usd: Decimal | None,
) -> bool:
    if category not in RECORDER_CATEGORIES:
        return False
    if yes_price is None:
        return False
    if not (RECORDER_PRICE_MIN <= yes_price <= RECORDER_PRICE_MAX):
        return False
    if volume_24h_usd is None or volume_24h_usd < RECORDER_VOLUME_FLOOR_USD:
        return False
    return True


def fetch_recorder_markets(
    *,
    client: requests.Session | None = None,
    page_limit: int = 500,
) -> list[MakerMarket]:
    """Pull every politics/sports/awards/crypto market in the recorder
    filter. De-dupes across the default page and the configured tag pages."""
    owns = client is None
    c = client or requests.Session()
    c.headers.update({"User-Agent": "bot-h-maker-v2/0.1"})
    raw_markets: list[dict[str, Any]] = []
    try:
        raw_markets.extend(_fetch_gamma_page(c, limit=page_limit))
        for tag in RECORDER_GAMMA_TAGS:
            try:
                tagged = _fetch_gamma_page(c, limit=300, tag=tag)
            except Exception as exc:
                log.info("bot_h_maker_v2.gamma_tag_skip tag=%s err=%s", tag, type(exc).__name__)
                continue
            raw_markets.extend(tagged)
    finally:
        if owns:
            c.close()

    seen: set[str] = set()
    out: list[MakerMarket] = []
    for raw in raw_markets:
        gamma_id = str(raw.get("id") or "")
        condition_id = str(raw.get("conditionId") or gamma_id)
        dedup = condition_id or gamma_id
        if not dedup or dedup in seen:
            continue
        seen.add(dedup)
        question = str(raw.get("question") or "")
        category = question_to_category(question)
        yes_price = _extract_yes_price(raw)
        volume = _decimal(raw.get("volume24hr"))
        if not _market_in_filter(
            category=category,
            yes_price=yes_price,
            volume_24h_usd=volume,
        ):
            continue
        tokens = _extract_tokens(raw)
        if tokens is None:
            continue
        yes_token, no_token = tokens
        out.append(
            MakerMarket(
                condition_id=condition_id,
                yes_token_id=yes_token,
                no_token_id=no_token,
                category=category,
                question=question,
                end_date=_parse_end_date(raw.get("endDate")),
                initial_yes_price=yes_price,
                volume_24h_usd=volume,
            )
        )
    log.info(
        "bot_h_maker_v2.discovery raw=%d kept=%d categories=%s",
        len(raw_markets),
        len(out),
        {m.category for m in out},
    )
    return out
