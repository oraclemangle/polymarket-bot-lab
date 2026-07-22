#!/usr/bin/env python3
"""Backfill resolved Polymarket markets + CLOB price history into data/backtest.db.

Sources (all free, no API key required):
  - Gamma API /markets?closed=true   — resolved markets catalog
  - CLOB    /prices-history           — per-token time series

Usage:
    python scripts/backfill_history.py --days 90 --categories politics,geopolitics,finance,economics
    python scripts/backfill_history.py --days 30  # default categories
    python scripts/backfill_history.py --markets-only  # skip price history

Design:
  - Idempotent: existing condition_ids are upserted, existing (token, ts)
    price points are skipped.
  - Slow and steady: rate-limited to ~10 req/sec to be polite.
  - Writes to data/backtest.db (configurable via BACKTEST_DB_PATH).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterator

import httpx
from sqlalchemy import select

# Make repo root importable when run as a script.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.backtest_db import (  # noqa: E402
    DEFAULT_BACKTEST_DB,
    PriceHistory,
    ResolvedMarket,
    get_backtest_session_factory,
)


GAMMA_URL = "https://gamma-api.polymarket.com/markets"
CLOB_PRICES_URL = "https://clob.polymarket.com/prices-history"

DEFAULT_CATEGORIES = {
    "geopolitics",
    "politics",
    "finance",
    "economics",
    "crypto",
    "weather",
    "sports",
}

log = logging.getLogger("backfill")


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    # Polymarket uses both "Z" suffix and offset formats.
    s = s.rstrip("Z")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_json_field(value: object) -> list | None:
    """Gamma returns JSON-encoded strings for outcomes/outcomePrices/clobTokenIds."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def fetch_resolved_markets_page(
    client: httpx.Client,
    offset: int,
    limit: int,
    end_after: datetime | None,
) -> list[dict]:
    params: dict[str, object] = {
        "closed": "true",
        "limit": limit,
        "offset": offset,
        "order": "endDate",
        "ascending": "false",  # newest first — lets us stop early
    }
    r = client.get(GAMMA_URL, params=params)
    r.raise_for_status()
    data = r.json() or []
    if not isinstance(data, list):
        return []
    if end_after is None:
        return data
    out: list[dict] = []
    for m in data:
        ed = _parse_iso(m.get("endDate") or m.get("closedTime"))
        if ed is None or ed >= end_after:
            out.append(m)
    return out


def iter_resolved_markets(
    client: httpx.Client,
    days: int,
    categories: set[str] | None,
    page_size: int = 500,
    max_pages: int = 100,
) -> Iterator[dict]:
    """Paginate backwards from the newest resolved market until we hit `days` ago.

    Uses `closedTime` (actual resolution) as the cutoff — not `endDate`,
    which on modern Polymarket is often a placeholder (e.g. 2028-01-01).
    Order param is `closedTime desc`; when a page has no closedTime within
    our window AND at least one older market, stop early.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    offset = 0
    older_count = 0
    for page in range(max_pages):
        params: dict[str, object] = {
            "closed": "true",
            "limit": page_size,
            "offset": offset,
            "order": "closedTime",
            "ascending": "false",
        }
        r = client.get(GAMMA_URL, params=params)
        r.raise_for_status()
        batch = r.json() or []
        if not batch:
            break
        kept = 0
        page_older = 0
        for m in batch:
            ct = _parse_iso(m.get("closedTime"))
            ed = _parse_iso(m.get("endDate"))
            resolved_at = ct or ed  # prefer closedTime
            if resolved_at is not None and resolved_at < cutoff:
                page_older += 1
                continue
            if categories is not None:
                # Modern Polymarket may not set `category` at all; treat None
                # as "unknown" and pass through (backtest filters by volume).
                cat = (m.get("category") or "").strip().lower()
                if cat and cat not in categories:
                    continue
            yield m
            kept += 1
        older_count += page_older
        log.info(
            "gamma.page %d kept=%d page_size=%d older_on_page=%d cutoff=%s",
            page, kept, len(batch), page_older, cutoff.date().isoformat(),
        )
        # Stop when the entire page is older than cutoff (since we're sorted
        # closedTime desc, every subsequent page will also be older).
        if page_older == len(batch) and len(batch) > 0:
            break
        offset += page_size
        time.sleep(0.1)


def upsert_resolved_market(sf, m: dict) -> str | None:
    cid = m.get("conditionId") or ""
    if not cid:
        return None
    outcomes = _parse_json_field(m.get("outcomes"))
    prices = _parse_json_field(m.get("outcomePrices"))
    token_ids = _parse_json_field(m.get("clobTokenIds"))
    yes_token = None
    no_token = None
    yes_price = None
    no_price = None
    if token_ids and len(token_ids) >= 2:
        yes_token, no_token = str(token_ids[0]), str(token_ids[1])
    if prices and len(prices) >= 2:
        try:
            yes_price = Decimal(str(prices[0]))
            no_price = Decimal(str(prices[1]))
        except Exception:
            pass

    with sf() as s:
        existing = s.get(ResolvedMarket, cid)
        row = existing or ResolvedMarket(condition_id=cid)
        row.question = str(m.get("question") or "")[:500]
        row.category = (m.get("category") or None)
        row.end_date = _parse_iso(m.get("endDate"))
        row.closed_time = _parse_iso(m.get("closedTime"))
        row.outcome_yes_price = yes_price
        row.outcome_no_price = no_price
        row.yes_token_id = yes_token
        row.no_token_id = no_token
        row.is_neg_risk = int(bool(m.get("negRisk")))
        try:
            row.volume_usd = Decimal(str(m.get("volumeNum") or 0))
        except Exception:
            row.volume_usd = Decimal("0")
        row.fetched_at = datetime.now(timezone.utc)
        if existing is None:
            s.add(row)
        s.commit()
    return cid


def fetch_price_history(
    client: httpx.Client,
    token_id: str,
    fidelity_minutes: int = 60,
) -> list[dict]:
    """Returns list of {t: unix_seconds, p: price_float} for this token."""
    params = {"market": token_id, "interval": "max", "fidelity": fidelity_minutes}
    try:
        r = client.get(CLOB_PRICES_URL, params=params, timeout=15.0)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.warning("prices-history.failed token=%s err=%s", token_id[:20], e)
        return []
    history = data.get("history") if isinstance(data, dict) else None
    return history if isinstance(history, list) else []


def insert_price_history(sf, token_id: str, history: list[dict]) -> int:
    """Insert new price points; skip duplicates on (token_id, ts)."""
    if not history:
        return 0
    count = 0
    with sf() as s:
        existing_ts = {
            r[0] for r in s.execute(
                select(PriceHistory.ts).where(PriceHistory.token_id == token_id)
            )
        }
        for point in history:
            try:
                ts = int(point["t"])
                px = float(point["p"])
            except (KeyError, ValueError, TypeError):
                continue
            if ts in existing_ts:
                continue
            s.add(PriceHistory(token_id=token_id, ts=ts, price=px))
            count += 1
        s.commit()
    return count


def _should_fetch_prices(
    m: dict, min_volume: float, exclude_patterns: tuple[str, ...]
) -> bool:
    try:
        vol = float(m.get("volumeNum") or 0)
    except (TypeError, ValueError):
        return False
    if vol < min_volume:
        return False
    q = (m.get("question") or "").lower()
    if any(p in q for p in exclude_patterns):
        return False
    return True


def backfill(
    days: int,
    categories: set[str] | None,
    price_history: bool,
    fidelity_minutes: int,
    db_path: Path,
    min_volume_for_prices: float = 5000.0,
    exclude_patterns: tuple[str, ...] = (),
) -> dict:
    sf = get_backtest_session_factory(db_path)
    stats = {
        "markets": 0, "price_points": 0, "tokens_fetched": 0,
        "tokens_failed": 0, "prices_skipped_filter": 0,
    }

    with httpx.Client(timeout=20.0, headers={"User-Agent": "longshot-backfill/0.1"}) as client:
        for m in iter_resolved_markets(client, days=days, categories=categories):
            cid = upsert_resolved_market(sf, m)
            if cid is None:
                continue
            stats["markets"] += 1

            if not price_history:
                continue

            if not _should_fetch_prices(m, min_volume_for_prices, exclude_patterns):
                stats["prices_skipped_filter"] += 1
                continue

            token_ids = _parse_json_field(m.get("clobTokenIds")) or []
            for tid in token_ids[:2]:  # just yes + no
                time.sleep(0.1)  # polite: ~10/sec
                hist = fetch_price_history(client, str(tid), fidelity_minutes)
                if not hist:
                    stats["tokens_failed"] += 1
                    continue
                n = insert_price_history(sf, str(tid), hist)
                stats["price_points"] += n
                stats["tokens_fetched"] += 1

            if stats["tokens_fetched"] and stats["tokens_fetched"] % 50 == 0:
                log.info(
                    "progress markets=%d price_points=%d tokens=%d failed=%d skipped=%d",
                    stats["markets"], stats["price_points"],
                    stats["tokens_fetched"], stats["tokens_failed"],
                    stats["prices_skipped_filter"],
                )
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90, help="lookback window")
    ap.add_argument(
        "--categories", default=",".join(sorted(DEFAULT_CATEGORIES)),
        help="comma-separated, or 'all' for no filter",
    )
    ap.add_argument("--markets-only", action="store_true", help="skip price history fetch")
    ap.add_argument("--fidelity-minutes", type=int, default=60, help="price history bucket")
    ap.add_argument("--db-path", default=str(DEFAULT_BACKTEST_DB))
    ap.add_argument("--log-level", default="INFO")
    ap.add_argument(
        "--min-volume-for-prices", type=float, default=5000.0,
        help="only fetch price history for markets with volume >= this USD (default $5000)",
    )
    ap.add_argument(
        "--exclude-patterns", default="Spread:,Up or Down,-vs-,Goals Over,Goals Under",
        help="comma-separated question substrings to skip (sports spreads, HFT crypto, etc.)",
    )
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cats = None
    if args.categories and args.categories.lower() != "all":
        cats = {c.strip().lower() for c in args.categories.split(",") if c.strip()}

    exclude_patterns = tuple(
        p.strip().lower() for p in (args.exclude_patterns or "").split(",") if p.strip()
    )
    stats = backfill(
        days=args.days,
        categories=cats,
        price_history=not args.markets_only,
        fidelity_minutes=args.fidelity_minutes,
        db_path=Path(args.db_path),
        min_volume_for_prices=args.min_volume_for_prices,
        exclude_patterns=exclude_patterns,
    )
    log.info("DONE %s", stats)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
