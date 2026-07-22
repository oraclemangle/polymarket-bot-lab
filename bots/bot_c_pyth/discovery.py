"""Polymarket Gamma market discovery + question parsing for traditional-asset markets."""
from __future__ import annotations

import calendar
import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

log = logging.getLogger(__name__)

GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"

SYMBOL_ALIASES: dict[str, str] = {
    "aapl": "AAPL", "apple": "AAPL",
    "tsla": "TSLA", "tesla": "TSLA",
    "nvda": "NVDA", "nvidia": "NVDA",
    "coin": "COIN", "coinbase": "COIN",
    "pltr": "PLTR", "palantir": "PLTR",
    "spy": "SPY", "qqq": "QQQ", "ewy": "EWY",
    "gold": "GOLD", "gc": "GOLD", "xau": "GOLD",
    "silver": "SILVER", "si": "SILVER", "xag": "SILVER",
    "wti": "WTI", "crude oil": "WTI", "cl": "WTI", "crude": "WTI",
    "natural gas": "NATGAS", "natgas": "NATGAS",
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH",
    "solana": "SOL", "sol": "SOL",
}


@dataclass(frozen=True)
class ParsedMarket:
    gamma_id: str
    slug: str
    question: str
    symbol: str
    direction: str  # 'above' | 'below' | 'between'
    strike_low: Decimal | None
    strike_high: Decimal | None
    resolution_date: datetime
    yes_token_id: str
    no_token_id: str
    yes_price: Decimal | None
    volume_24h_usd: Decimal | None
    # Fix 1: "terminal" = price at resolution; "barrier" = touches at any point.
    question_kind: str = "terminal"


_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(
        r"^Will\s+.+?\(([A-Z]{1,5})\)\s+hit\s+\((HIGH|LOW)\)\s+\$([\d,]+\.?\d*)\s+"
        r"Week of\s+([A-Za-z]+\s+\d{1,2}(?:\s+\d{4})?)\b",
        re.IGNORECASE), "weekly_hit"),
    (re.compile(
        r"^Will\s+.+?\(([A-Z]{1,5})\)\s+finish\s+week of\s+"
        r"([A-Za-z]+\s+\d{1,2}(?:\s+\d{4})?)\s+(above|below)\s+\$([\d,]+\.?\d*)",
        re.IGNORECASE), "weekly_finish"),
    (re.compile(
        r"^Will\s+.+?\(([A-Z]{1,5})\)\s+settle\s+(over|under)\s+\$([\d,]+\.?\d*)\s+"
        r"on the final trading day of\s+([A-Za-z]+\s+\d{4})",
        re.IGNORECASE), "month_settle"),
    (re.compile(
        r"^Will\s+.+?\(([A-Z]{1,5})\)\s+hit\s+\((HIGH|LOW)\)\s+\$([\d,]+\.?\d*)\s+"
        r"by end of\s+([A-Za-z]+)(?:\s+(\d{4}))?",
        re.IGNORECASE), "eom_hit"),
    (re.compile(
        r"^Will the price of\s+(\w+)\s+be between\s+\$([\d,]+\.?\d*)\s+and\s+\$([\d,]+\.?\d*)\s+in\s+"
        r"([A-Za-z]+)(?:\s+(\d{4}))?",
        re.IGNORECASE), "crypto_between_month"),
    (re.compile(
        r"^Will the price of\s+(\w+)\s+be between\s+\$([\d,]+\.?\d*)\s+and\s+\$([\d,]+\.?\d*)\s+on\s+"
        r"([A-Za-z]+\s+\d{1,2}(?:\s+\d{4})?)",
        re.IGNORECASE), "crypto_between_date"),
]


def _money(s: str) -> Decimal:
    return Decimal(s.replace(",", "").strip())


def _parse_dmy(token: str, default_year: int, *, now: datetime | None = None) -> datetime:
    """Parse a human-written date. Fix 7: when year is missing, pick the NEXT
    occurrence (current year if still in the future, else next year)."""
    token = token.strip()
    now = now or datetime.now(UTC)
    for fmt in ("%B %d %Y", "%B %d, %Y", "%B %d"):
        try:
            dt = datetime.strptime(token, fmt)
            year = dt.year if dt.year > 1900 else default_year
            candidate = datetime(year, dt.month, dt.day, 23, 59, 59, tzinfo=UTC)
            # Fix 7: if the resolved date is in the past, roll forward one year.
            if candidate < now and dt.year <= 1900:
                candidate = datetime(year + 1, dt.month, dt.day, 23, 59, 59, tzinfo=UTC)
            return candidate
        except ValueError:
            continue
    for fmt in ("%B %Y", "%B"):
        try:
            dt = datetime.strptime(token, fmt)
            year = dt.year if dt.year > 1900 else default_year
            last = calendar.monthrange(year, dt.month)[1]
            candidate = datetime(year, dt.month, last, 23, 59, 59, tzinfo=UTC)
            if candidate < now and dt.year <= 1900:
                year += 1
                last = calendar.monthrange(year, dt.month)[1]
                candidate = datetime(year, dt.month, last, 23, 59, 59, tzinfo=UTC)
            return candidate
        except ValueError:
            continue
    raise ValueError(f"unparseable date token: {token!r}")


def _resolve_symbol(raw: str) -> str | None:
    return SYMBOL_ALIASES.get(raw.lower().strip())


def parse_question(question: str, *, now: datetime | None = None) -> dict[str, Any] | None:
    """Parse a Polymarket question into a normalised dict, or None if unmatched."""
    now = now or datetime.now(UTC)
    default_year = now.year
    for pat, handler in _PATTERNS:
        m = pat.search(question)
        if not m:
            continue
        try:
            if handler == "weekly_hit":
                ticker, side, strike, date_tok = m.groups()
                sym = _resolve_symbol(ticker)
                if not sym:
                    return None
                return {
                    "symbol": sym,
                    "direction": "above" if side.upper() == "HIGH" else "below",
                    "strike_low": _money(strike),
                    "strike_high": None,
                    "resolution_date": _parse_dmy(date_tok, default_year, now=now),
                    "question_kind": "barrier",
                }
            if handler == "weekly_finish":
                ticker, date_tok, side, strike = m.groups()
                sym = _resolve_symbol(ticker)
                if not sym:
                    return None
                return {
                    "symbol": sym,
                    "direction": side.lower(),
                    "strike_low": _money(strike),
                    "strike_high": None,
                    "resolution_date": _parse_dmy(date_tok, default_year, now=now),
                    "question_kind": "terminal",
                }
            if handler == "month_settle":
                ticker, side, strike, date_tok = m.groups()
                sym = _resolve_symbol(ticker)
                if not sym:
                    return None
                return {
                    "symbol": sym,
                    "direction": "above" if side.lower() == "over" else "below",
                    "strike_low": _money(strike),
                    "strike_high": None,
                    "resolution_date": _parse_dmy(date_tok, default_year, now=now),
                    "question_kind": "terminal",
                }
            if handler == "eom_hit":
                ticker, side, strike, month, year = m.groups()
                sym = _resolve_symbol(ticker)
                if not sym:
                    return None
                # Fix 7: pass month-only when year absent so _parse_dmy can rollover.
                date_tok = f"{month} {year}" if year else month
                return {
                    "symbol": sym,
                    "direction": "above" if side.upper() == "HIGH" else "below",
                    "strike_low": _money(strike),
                    "strike_high": None,
                    "resolution_date": _parse_dmy(date_tok, default_year, now=now),
                    "question_kind": "barrier",
                }
            if handler == "crypto_between_month":
                name, lo, hi, month, year = m.groups()
                sym = _resolve_symbol(name)
                if not sym:
                    return None
                date_tok = f"{month} {year}" if year else month
                return {
                    "symbol": sym,
                    "direction": "between",
                    "strike_low": _money(lo),
                    "strike_high": _money(hi),
                    "resolution_date": _parse_dmy(date_tok, default_year, now=now),
                    "question_kind": "terminal",
                }
            if handler == "crypto_between_date":
                name, lo, hi, date_tok = m.groups()
                sym = _resolve_symbol(name)
                if not sym:
                    return None
                return {
                    "symbol": sym,
                    "direction": "between",
                    "strike_low": _money(lo),
                    "strike_high": _money(hi),
                    "resolution_date": _parse_dmy(date_tok, default_year, now=now),
                    "question_kind": "terminal",
                }
        except Exception as exc:
            log.debug("parse_question: handler=%s failed on %r: %s", handler, question, exc)
            return None
    return None


def _extract_yes_no_tokens(market: dict[str, Any]) -> tuple[str, str] | None:
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
            raw = None
    if isinstance(raw, list) and len(raw) == 2:
        outcomes = market.get("outcomes")
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except Exception:
                outcomes = None
        if isinstance(outcomes, list) and len(outcomes) == 2:
            yes_idx = next((i for i, o in enumerate(outcomes) if str(o).lower() == "yes"), None)
            if yes_idx is not None:
                try:
                    return Decimal(str(raw[yes_idx]))
                except Exception:
                    return None
    # fallback: lastTradePrice
    ltp = market.get("lastTradePrice")
    if ltp is not None:
        try:
            return Decimal(str(ltp))
        except Exception:
            return None
    return None


def fetch_candidate_markets(
    *,
    http_client: httpx.Client | None = None,
    limit: int = 500,
) -> list[ParsedMarket]:
    """Fetch active Gamma markets and return those matching a traditional-asset pattern."""
    owns_client = http_client is None
    client = http_client or httpx.Client(timeout=15.0, headers={"User-Agent": "bot-c/0.1"})
    try:
        resp = client.get(GAMMA_MARKETS_URL, params={
            "active": "true",
            "closed": "false",
            "limit": str(limit),
            "order": "volume",
            "ascending": "false",
        })
        resp.raise_for_status()
        markets = resp.json()
    finally:
        if owns_client:
            client.close()

    out: list[ParsedMarket] = []
    now = datetime.now(UTC)
    for m in markets:
        q = m.get("question") or ""
        parsed = parse_question(q, now=now)
        if not parsed:
            continue
        toks = _extract_yes_no_tokens(m)
        if not toks:
            continue
        yes_tok, no_tok = toks
        end_date_raw = m.get("endDate")
        if end_date_raw:
            try:
                parsed["resolution_date"] = datetime.fromisoformat(
                    end_date_raw.replace("Z", "+00:00")
                )
            except Exception:
                pass
        yes_price = _extract_yes_price(m)
        vol24 = m.get("volume24hr")
        try:
            vol_dec = Decimal(str(vol24)) if vol24 is not None else None
        except Exception:
            vol_dec = None
        out.append(ParsedMarket(
            gamma_id=str(m.get("id") or m.get("conditionId") or ""),
            slug=str(m.get("slug") or ""),
            question=q,
            symbol=parsed["symbol"],
            direction=parsed["direction"],
            strike_low=parsed["strike_low"],
            strike_high=parsed["strike_high"],
            resolution_date=parsed["resolution_date"],
            yes_token_id=yes_tok,
            no_token_id=no_tok,
            yes_price=yes_price,
            volume_24h_usd=vol_dec,
            question_kind=parsed.get("question_kind", "terminal"),
        ))
    log.info("gamma: %d markets scanned, %d parsed traditional-asset candidates",
             len(markets), len(out))
    return out
