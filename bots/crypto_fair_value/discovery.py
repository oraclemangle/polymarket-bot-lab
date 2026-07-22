"""Recorder-backed discovery/state reads for crypto fair-value paper bots."""
from __future__ import annotations

import bisect
import json
import logging
import re
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from bots.crypto_fair_value.config import CryptoFairValueConfig
from bots.crypto_fair_value.model import (
    BookSide,
    BookState,
    CexState,
    MarketMeta,
    realized_vol_tick,
)

log = logging.getLogger(__name__)

SYMBOL_TO_CEX = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}


def connect_recorder(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=2.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-65536")
    except Exception:
        pass
    return conn


def _parse_end(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _clock_to_minutes(hour: int, minute: int, ampm: str) -> int:
    hour = hour % 12
    if ampm == "PM":
        hour += 12
    return hour * 60 + minute


def _parse_range_minutes(question: str) -> int | None:
    match = re.search(
        r"(\d{1,2})(?::(\d{2}))?([AP]M)-(\d{1,2})(?::(\d{2}))?([AP]M) ET",
        question,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    sh, sm, sap, eh, em, eap = match.groups()
    start_min = _clock_to_minutes(int(sh), int(sm or 0), sap.upper())
    end_min = _clock_to_minutes(int(eh), int(em or 0), eap.upper())
    if end_min <= start_min:
        end_min += 24 * 60
    duration = end_min - start_min
    return duration if duration in (5, 15) else None


def _symbol_from_question(question: str) -> str:
    q = question.upper()
    if "BITCOIN" in q or " BTC " in f" {q} ":
        return "BTC"
    if "ETHEREUM" in q or " ETH " in f" {q} ":
        return "ETH"
    if "SOLANA" in q or " SOL " in f" {q} ":
        return "SOL"
    return "unknown"


def active_markets(
    conn: sqlite3.Connection,
    *,
    config: CryptoFairValueConfig,
    now_ms: int,
) -> list[MarketMeta]:
    max_window_ms = max(config.max_seconds_to_close_5m, config.max_seconds_to_close_15m) * 1000
    now_iso = datetime.fromtimestamp(now_ms / 1000, tz=UTC).isoformat()
    future_iso = datetime.fromtimestamp((now_ms + max_window_ms) / 1000, tz=UTC).isoformat()
    rows = conn.execute(
        """
        SELECT condition_id, question, end_date_iso, yes_token_id, no_token_id,
               symbol, duration_minutes
        FROM markets
        WHERE end_date_iso IS NOT NULL
          AND end_date_iso >= ?
          AND end_date_iso <= ?
        GROUP BY condition_id HAVING scan_at_ms = MAX(scan_at_ms)
        ORDER BY end_date_iso
        """,
        (now_iso, future_iso),
    ).fetchall()
    out: list[MarketMeta] = []
    for row in rows:
        question = str(row["question"] or "")
        symbol = str(row["symbol"] or "").upper() or _symbol_from_question(question)
        if symbol not in config.symbols:
            continue
        end_dt = _parse_end(str(row["end_date_iso"] or ""))
        if end_dt is None:
            continue
        duration = int(row["duration_minutes"] or 0) or (_parse_range_minutes(question) or 0)
        if duration not in config.durations:
            continue
        max_close = (
            config.max_seconds_to_close_5m
            if duration == 5
            else config.max_seconds_to_close_15m
        )
        seconds_left = end_dt.timestamp() - now_ms / 1000
        if seconds_left < config.min_seconds_to_close or seconds_left > max_close:
            continue
        yes_token = str(row["yes_token_id"] or "")
        no_token = str(row["no_token_id"] or "")
        if not yes_token or not no_token:
            continue
        out.append(
            MarketMeta(
                condition_id=str(row["condition_id"]),
                question=question,
                end_ms=int(end_dt.timestamp() * 1000),
                start_ms=int(end_dt.timestamp() * 1000) - duration * 60_000,
                symbol=symbol,
                duration_minutes=duration,
                yes_token_id=yes_token,
                no_token_id=no_token,
            )
        )
    return out


def _row_payload(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    try:
        parsed = json.loads(row["payload_json"] or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _book_side_from_payload(token_id: str, payload: dict[str, Any], ts_ms: int) -> BookSide | None:
    bids = payload.get("bids") or []
    asks = payload.get("asks") or []
    bid_levels: list[tuple[Decimal, Decimal]] = []
    ask_levels: list[tuple[Decimal, Decimal]] = []
    for level in bids:
        try:
            price = Decimal(str(level.get("price")))
            size = Decimal(str(level.get("size") or "0"))
        except Exception:
            continue
        if price > 0 and size > 0:
            bid_levels.append((price, size))
    for level in asks:
        try:
            price = Decimal(str(level.get("price")))
            size = Decimal(str(level.get("size") or "0"))
        except Exception:
            continue
        if price > 0 and size > 0:
            ask_levels.append((price, size))
    if not bid_levels or not ask_levels:
        return None
    best_bid = max(price for price, _size in bid_levels)
    best_ask, top_size = min(ask_levels, key=lambda item: item[0])
    if best_bid >= best_ask:
        return None
    return BookSide(
        token_id=token_id,
        best_bid=best_bid,
        best_ask=best_ask,
        top_ask_size=top_size,
        ts_ms=ts_ms,
    )


def latest_book_state(
    conn: sqlite3.Connection,
    meta: MarketMeta,
    *,
    now_ms: int,
    max_age_sec: float,
) -> BookState | None:
    cutoff = now_ms - int(max_age_sec * 1000)

    def read_side(token_id: str) -> BookSide | None:
        row = conn.execute(
            """
            SELECT payload_json, received_at_ms
            FROM pm_events
            WHERE asset_id = ?
              AND event_type = 'book'
              AND received_at_ms >= ?
              AND received_at_ms <= ?
            ORDER BY received_at_ms DESC
            LIMIT 1
            """,
            (token_id, cutoff, now_ms),
        ).fetchone()
        if row is None:
            return None
        return _book_side_from_payload(token_id, _row_payload(row), int(row["received_at_ms"]))

    yes = read_side(meta.yes_token_id)
    no = read_side(meta.no_token_id)
    if yes is None or no is None:
        return None
    return BookState(yes=yes, no=no)


def _cex_rows(
    conn: sqlite3.Connection,
    symbol: str,
    *,
    start_ms: int,
    end_ms: int,
) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT received_at_ms, price
            FROM cex_trades
            WHERE symbol = ?
              AND received_at_ms >= ?
              AND received_at_ms <= ?
            ORDER BY received_at_ms
            """,
            (symbol, start_ms, end_ms),
        )
    )


def _price_at_or_before(conn: sqlite3.Connection, symbol: str, ts_ms: int) -> tuple[float, int] | None:
    row = conn.execute(
        """
        SELECT price, received_at_ms
        FROM cex_trades
        WHERE symbol = ?
          AND received_at_ms <= ?
        ORDER BY received_at_ms DESC
        LIMIT 1
        """,
        (symbol, ts_ms),
    ).fetchone()
    if row is None:
        return None
    return float(row["price"]), int(row["received_at_ms"])


def cex_state(
    conn: sqlite3.Connection,
    meta: MarketMeta,
    *,
    now_ms: int,
    max_age_sec: float,
) -> CexState | None:
    cex_symbol = SYMBOL_TO_CEX[meta.symbol]
    start = _price_at_or_before(conn, cex_symbol, meta.start_ms)
    current = _price_at_or_before(conn, cex_symbol, now_ms)
    prev_60 = _price_at_or_before(conn, cex_symbol, now_ms - 60_000)
    if start is None or current is None or prev_60 is None:
        return None
    current_price, current_ts = current
    if current_ts < now_ms - int(max_age_sec * 1000):
        return None
    start_price, _start_ts = start
    prev_price, _prev_ts = prev_60
    if start_price <= 0 or current_price <= 0 or prev_price <= 0:
        return None

    # Sample roughly 60 prices over the prior 10 minutes, matching the
    # validation harness's conservative remaining-vol scaling.
    samples: list[float] = []
    sample_start = now_ms - 600_000
    sample_step = 10_000
    rows = _cex_rows(conn, cex_symbol, start_ms=sample_start - sample_step, end_ms=now_ms)
    ts_list = [int(r["received_at_ms"]) for r in rows]
    price_list = [float(r["price"]) for r in rows]
    t = sample_start
    while t <= now_ms:
        idx = bisect.bisect_right(ts_list, t) - 1
        if idx >= 0:
            samples.append(price_list[idx])
        t += sample_step

    return CexState(
        symbol=cex_symbol,
        start_price=start_price,
        current_price=current_price,
        current_ts_ms=current_ts,
        realized_vol_tick=realized_vol_tick(samples),
        move_60s=current_price / prev_price - 1.0,
    )
