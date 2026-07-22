"""Discover currently-live crypto Up/Down markets on Polymarket.

Queries Gamma API for active markets, filters to ones whose question matches
the crypto pattern (BTC/ETH/SOL/XRP/DOGE Up/Down ending in the near future),
then returns enough metadata for the WSS subscriber to open a subscription
on the YES and NO token IDs.

This runs on a loop (default 60s) so that as crypto windows roll forward,
new markets come into the subscription pool automatically.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

log = logging.getLogger(__name__)

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
GAMMA_MARKET_SLUG_URL = "https://gamma-api.polymarket.com/markets/slug/{slug}"

# Pattern: "Up or down on BTC for the period ending Apr 17, 2026 3:15 PM EST?"
# We keep this broad — the Gamma question phrasing has varied historically.
# Match presence of one of the target symbols AND one of the signal phrases.
_SYMBOL_PATTERNS = {
    "BTC": re.compile(r"\bBTC|bitcoin\b", re.IGNORECASE),
    "ETH": re.compile(r"\bETH|ethereum\b", re.IGNORECASE),
    "SOL": re.compile(r"\bSOL|solana\b", re.IGNORECASE),
    "XRP": re.compile(r"\bXRP|ripple\b", re.IGNORECASE),
    "DOGE": re.compile(r"\bDOGE|dogecoin\b", re.IGNORECASE),
}
_UPDOWN_PATTERN = re.compile(
    r"up\s+or\s+down|go(?:ing)?\s+up|go(?:ing)?\s+down|above|below|higher|lower",
    re.IGNORECASE,
)
_QUESTION_RANGE_PATTERN = re.compile(
    r"(?P<h1>\d{1,2}):(?P<m1>\d{2})\s*(?P<ap1>AM|PM)?\s*-\s*"
    r"(?P<h2>\d{1,2}):(?P<m2>\d{2})\s*(?P<ap2>AM|PM)",
    re.IGNORECASE,
)
_MINUTE_LABEL_PATTERN = re.compile(r"\b(?P<minutes>5|15)\s*min(?:ute)?s?\b", re.IGNORECASE)
_SLUG_SYMBOLS = ("btc", "eth", "sol")
_SLUG_DURATIONS_MIN = (5, 15)


@dataclass(frozen=True)
class CryptoMarket:
    """Minimal metadata needed to subscribe to a crypto Up/Down market."""
    condition_id: str
    question: str
    symbol: str                  # "BTC" | "ETH" | "SOL" | "XRP" | "DOGE"
    end_date: datetime           # Gamma-reported resolution time (UTC)
    yes_token_id: str
    no_token_id: str
    yes_price: Decimal | None
    volume_24h_usd: Decimal | None
    duration_minutes: int | None
    raw: dict[str, Any]

    def minutes_to_resolution(self, now: datetime | None = None) -> float:
        now = now or datetime.now(UTC)
        return (self.end_date - now).total_seconds() / 60.0


def _extract_tokens(m: dict[str, Any]) -> tuple[str, str] | None:
    """Return (yes_token_id, no_token_id). Gamma stores them as a JSON-encoded
    list in 'clobTokenIds' or as an 'outcomes'/'clobTokenIds' pair.

    Returns None if the market isn't tradable (missing ids).
    """
    import json as _json
    ids = m.get("clobTokenIds")
    if isinstance(ids, str):
        try:
            ids = _json.loads(ids)
        except Exception:
            return None
    if not isinstance(ids, list) or len(ids) < 2:
        return None
    # Gamma convention: outcome order matches token order.
    # For Up/Down markets, first token is typically "Up" (YES of "Up or down").
    return str(ids[0]), str(ids[1])


def _parse_end_date(raw: dict[str, Any]) -> datetime | None:
    """Return UTC datetime for Gamma endDate field."""
    end = raw.get("endDate") or raw.get("end_date")
    if not end:
        return None
    try:
        return datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except Exception:
        return None


def _extract_yes_price(m: dict[str, Any]) -> Decimal | None:
    """Pull YES price from Gamma's outcomes/outcomePrices."""
    import json as _json
    prices = m.get("outcomePrices")
    if isinstance(prices, str):
        try:
            prices = _json.loads(prices)
        except Exception:
            return None
    if isinstance(prices, list) and len(prices) >= 1:
        try:
            return Decimal(str(prices[0]))
        except Exception:
            return None
    return None


def _classify_symbol(question: str) -> str | None:
    """Return crypto symbol if question names one, else None."""
    for sym, pat in _SYMBOL_PATTERNS.items():
        if pat.search(question):
            return sym
    return None


def _infer_duration_minutes(question: str) -> int | None:
    """Infer 5m vs 15m from common Polymarket crypto question text."""
    label = _MINUTE_LABEL_PATTERN.search(question)
    if label:
        try:
            return int(label.group("minutes"))
        except ValueError:
            return None
    match = _QUESTION_RANGE_PATTERN.search(question)
    if not match:
        return None

    def to_minutes(hour_s: str, minute_s: str, ampm: str | None) -> int:
        hour = int(hour_s)
        minute = int(minute_s)
        if ampm:
            ap = ampm.upper()
            if ap == "PM" and hour != 12:
                hour += 12
            elif ap == "AM" and hour == 12:
                hour = 0
        return hour * 60 + minute

    ap1 = match.group("ap1") or match.group("ap2")
    start = to_minutes(match.group("h1"), match.group("m1"), ap1)
    end = to_minutes(match.group("h2"), match.group("m2"), match.group("ap2"))
    if end < start:
        end += 24 * 60
    duration = end - start
    return duration if duration in (5, 15) else None


def _is_crypto_updown(question: str) -> bool:
    """Is this a crypto Up/Down market we care about?"""
    if not _UPDOWN_PATTERN.search(question):
        return False
    return _classify_symbol(question) is not None


def _slug_candidates(now: datetime, max_minutes_to_res: float) -> list[str]:
    """Return near-term deterministic crypto Up/Down slugs.

    Gamma's broad active-market pages can omit short-lived crypto markets even
    when direct slug lookup works. Keep this fallback bounded to the near-term
    windows the paper bots need, rather than crawling the full active catalog.
    """
    horizon_s = int(min(max_minutes_to_res, 20.0) * 60)
    now_s = int(now.timestamp())
    slugs: list[str] = []
    for duration in _SLUG_DURATIONS_MIN:
        step_s = duration * 60
        end_s = ((now_s // step_s) + 1) * step_s
        while end_s <= now_s + horizon_s:
            for symbol in _SLUG_SYMBOLS:
                slugs.append(f"{symbol}-updown-{duration}m-{end_s}")
            end_s += step_s
    return slugs


def fetch_live_crypto_markets(
    *,
    max_minutes_to_res: float = 20.0,
    min_volume_usd: float = 50.0,
    tags: list[str] | None = None,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> list[CryptoMarket]:
    """Pull currently-live 15-min crypto Up/Down markets from Gamma.

    Filters:
    - Active AND not closed
    - Question matches crypto Up/Down pattern
    - Resolution within `max_minutes_to_res` minutes (skip if too far out — no
      liquidity; skip if already resolved)
    - 24h volume >= `min_volume_usd`
    """
    now = now or datetime.now(UTC)
    max_end = now + timedelta(minutes=max_minutes_to_res)

    owns = client is None
    c = client or httpx.Client(timeout=15.0)
    out: list[CryptoMarket] = []
    try:
        # Gamma: sort by liquidity DESC — this is what actually surfaces the
        # Session 24 (2026-04-23): fetch BOTH liquidity- AND volume-ordered
        # pages, merged, deduped. Rationale: observed 18:30 UTC the top-1000
        # liquidity-ordered results contained exactly ONE crypto Up/Down
        # market in a 120-min window (Polymarket's top-liquidity set is
        # dominated by non-crypto election markets). The volume-ordered
        # top-500 surfaced 4 separate crypto Up/Down markets the recorder
        # was totally blind to. Using both orderings guarantees we catch
        # both "bookish" (high-liquidity, high-spread) and "traderly"
        # (high-flow, above-strike) market styles.
        markets_raw: list[dict] = []
        seen_ids: set[str] = set()
        for order in ("liquidity", "volume"):
            for offset in (0, 500):
                params = {
                    "active": "true",
                    "closed": "false",
                    "limit": 500,
                    "offset": offset,
                    "order": order,
                    "ascending": "false",
                }
                r = c.get(GAMMA_MARKETS_URL, params=params)
                r.raise_for_status()
                page = r.json()
                if not isinstance(page, list):
                    log.warning(
                        "market_discovery.bad_response order=%s offset=%s type=%s",
                        order, offset, type(page).__name__,
                    )
                    continue
                for m in page:
                    if not isinstance(m, dict):
                        continue
                    mid = str(m.get("conditionId") or m.get("id") or "")
                    if mid and mid in seen_ids:
                        continue
                    if mid:
                        seen_ids.add(mid)
                    markets_raw.append(m)
                if len(page) < 500:
                    break
        for slug in _slug_candidates(now, max_minutes_to_res):
            try:
                r = c.get(GAMMA_MARKET_SLUG_URL.format(slug=slug))
                if r.status_code == 404:
                    continue
                r.raise_for_status()
            except httpx.HTTPError as exc:
                log.warning("market_discovery.slug_lookup_failed slug=%s err=%s", slug, exc)
                continue
            m = r.json()
            if not isinstance(m, dict):
                continue
            mid = str(m.get("conditionId") or m.get("id") or "")
            if mid and mid in seen_ids:
                continue
            if mid:
                seen_ids.add(mid)
            markets_raw.append(m)

        for m in markets_raw:
            if not isinstance(m, dict):
                continue
            q = m.get("question") or ""
            if not _is_crypto_updown(q):
                continue
            end_dt = _parse_end_date(m)
            if end_dt is None:
                continue
            if end_dt <= now or end_dt > max_end:
                continue
            # volume24hr is often None on brand-new 5-min markets before any
            # trades print. Treat None as "unknown" and let the subscription
            # proceed; the min_volume_usd floor only filters markets that
            # explicitly report a number below the floor.
            vol_raw = m.get("volume24hr")
            if vol_raw is not None:
                try:
                    vol_usd = float(vol_raw)
                    if vol_usd < min_volume_usd:
                        continue
                except (TypeError, ValueError):
                    pass
            toks = _extract_tokens(m)
            if not toks:
                continue
            yes_tok, no_tok = toks
            sym = _classify_symbol(q)
            if sym is None:
                continue
            # Use vol_raw parsed above. The previous `vol` reference was a
            # NameError bug — vol was never defined; the parsing block uses
            # vol_raw → vol_usd, so vol_raw is the right source for the
            # Decimal conversion. (Audit fix 2026-04-16.)
            try:
                vol_dec = Decimal(str(vol_raw)) if vol_raw is not None else None
            except Exception:
                vol_dec = None
            out.append(CryptoMarket(
                condition_id=str(m.get("conditionId") or m.get("id") or ""),
                question=q,
                symbol=sym,
                end_date=end_dt,
                yes_token_id=yes_tok,
                no_token_id=no_tok,
                yes_price=_extract_yes_price(m),
                volume_24h_usd=vol_dec,
                duration_minutes=_infer_duration_minutes(q),
                raw=m,
            ))
    finally:
        if owns:
            c.close()

    log.info(
        "market_discovery: %d markets matching crypto Up/Down within %.1fmin",
        len(out), max_minutes_to_res,
    )
    return out
