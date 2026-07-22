#!/usr/bin/env python3
"""Bot E fill-conditioned replay dataset.

Read-only diagnostic that reconstructs Bot E OBI signals from the recorder DB,
then emits one denominator row per signal with simulated maker-fill, adverse
movement, depth coverage, and outcome labels when bounded future data exists.

This script is intentionally conservative:
- input SQLite DBs are opened with ``mode=ro`` URI connections;
- the CLI requires ``--lookback-hours`` or explicit ``--since-ms`` and
  ``--until-ms`` bounds;
- no Bot E runtime config, orders, services, or production state are mutated.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.bot_e_calibration_spike import (  # noqa: E402
    OBI_WINDOW_SEC,
    MarketMeta,
    SignalObs,
    attach_outcomes,
    build_sub_to_market,
    build_token_to_market,
    detect_resolutions_via_cex,
    load_cex_prices,
    replay_signals,
)

DEFAULT_RECORDER_DB = REPO_ROOT / "data" / "bot_e_recorder.db"
ADVERSE_HORIZONS_SEC = (30, 60, 300)
DEFAULT_FILL_TIMEOUT_SEC = 60.0

CSV_COLUMNS = (
    "row_type",
    "order_id",
    "order_status",
    "placed_at_ms",
    "last_updated_ms",
    "signal_id",
    "subscription_id",
    "condition_id",
    "t0_ms",
    "t0_iso",
    "side",
    "asset_id",
    "signal_price",
    "maker_limit",
    "filled",
    "fill_ts_ms",
    "fill_delay_sec",
    "fill_price",
    "fill_source",
    "book_covered",
    "book_snapshot_count",
    "depth_notional",
    "depth_source",
    "adverse_30s_price",
    "adverse_30s_delta",
    "adverse_30s_moved_against",
    "adverse_60s_price",
    "adverse_60s_delta",
    "adverse_60s_moved_against",
    "adverse_300s_price",
    "adverse_300s_delta",
    "adverse_300s_moved_against",
    "outcome_label",
    "signal_won",
    "outcome_source",
    "notes",
)


@dataclass(frozen=True)
class FillObs:
    ts_ms: int
    price: float
    source: str


@dataclass(frozen=True)
class DepthObs:
    covered: bool
    snapshot_count: int
    notional: float | None
    source: str


@dataclass
class ReplayRow:
    row_type: str
    order_id: str | None
    order_status: str | None
    placed_at_ms: int | None
    last_updated_ms: int | None
    signal_id: str
    subscription_id: str
    condition_id: str | None
    t0_ms: int
    t0_iso: str
    side: str
    asset_id: str | None
    signal_price: float | None
    maker_limit: float | None
    filled: bool
    fill_ts_ms: int | None
    fill_delay_sec: float | None
    fill_price: float | None
    fill_source: str
    book_covered: bool
    book_snapshot_count: int
    depth_notional: float | None
    depth_source: str
    adverse_30s_price: float | None
    adverse_30s_delta: float | None
    adverse_30s_moved_against: bool | None
    adverse_60s_price: float | None
    adverse_60s_delta: float | None
    adverse_60s_moved_against: bool | None
    adverse_300s_price: float | None
    adverse_300s_delta: float | None
    adverse_300s_moved_against: bool | None
    outcome_label: str | None
    signal_won: bool | None
    outcome_source: str
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ms_to_iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).isoformat()


def _sqlite_dt_from_ms(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


def _parse_db_dt(value: str) -> int:
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.astimezone(UTC).timestamp() * 1000)


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _has_columns(conn: sqlite3.Connection, table: str, required: set[str]) -> bool:
    return required.issubset(_table_columns(conn, table))


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _payload_price(raw_json: str | None) -> float | None:
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    price = _safe_float(payload.get("price"))
    return price if price is not None and price > 0 else None


def _event_prices_by_asset(
    conn: sqlite3.Connection,
    *,
    since_ms: int | None,
    until_ms: int | None,
) -> dict[str, list[tuple[int, float]]]:
    where = ["event_type = 'last_trade_price'", "asset_id IS NOT NULL"]
    params: list[int] = []
    if since_ms is not None:
        where.append("received_at_ms >= ?")
        params.append(since_ms)
    if until_ms is not None:
        where.append("received_at_ms <= ?")
        params.append(until_ms)
    rows = conn.execute(
        """
        SELECT received_at_ms, asset_id, payload_json
        FROM pm_events
        WHERE """
        + " AND ".join(where)
        + """
        ORDER BY received_at_ms
        """,
        params,
    )
    by_asset: dict[str, list[tuple[int, float]]] = {}
    for row in rows:
        price = _payload_price(row["payload_json"])
        if price is None:
            continue
        by_asset.setdefault(str(row["asset_id"]), []).append((int(row["received_at_ms"]), price))
    return by_asset


def _load_markets_bounded(
    conn: sqlite3.Connection,
    *,
    since_ms: int,
    until_ms: int,
) -> dict[str, MarketMeta]:
    """Load latest market metadata available inside the replay evidence window.

    We intentionally avoid `load_markets()`, which selects the latest row from
    the entire DB and can leak post-window metadata into a bounded replay.
    """
    touched_conditions: set[str] = set()
    touched_assets: set[str] = set()
    rows = conn.execute(
        """
        SELECT DISTINCT condition_id, asset_id
        FROM pm_events
        WHERE received_at_ms >= ?
          AND received_at_ms <= ?
          AND (condition_id IS NOT NULL OR asset_id IS NOT NULL)
        """,
        (since_ms, until_ms),
    )
    for row in rows:
        if row["condition_id"]:
            touched_conditions.add(str(row["condition_id"]))
        if row["asset_id"]:
            touched_assets.add(str(row["asset_id"]))

    if not touched_conditions and not touched_assets:
        return {}

    filters: list[str] = ["scan_at_ms <= ?"]
    params: list[object] = [until_ms]
    touched_filter_parts: list[str] = []
    if touched_conditions:
        placeholders = ", ".join("?" for _ in touched_conditions)
        touched_filter_parts.append(f"condition_id IN ({placeholders})")
        params.extend(sorted(touched_conditions))
    if touched_assets:
        placeholders = ", ".join("?" for _ in touched_assets)
        touched_filter_parts.append(
            f"(yes_token_id IN ({placeholders}) OR no_token_id IN ({placeholders}))"
        )
        ordered_assets = sorted(touched_assets)
        params.extend(ordered_assets)
        params.extend(ordered_assets)
    filters.append("(" + " OR ".join(touched_filter_parts) + ")")

    where_sql = " AND ".join(filters)
    query = f"""
        SELECT m.condition_id, m.question, m.yes_token_id, m.no_token_id,
               m.end_date_iso
        FROM markets m
        INNER JOIN (
            SELECT condition_id, MAX(scan_at_ms) AS latest
            FROM markets
            WHERE {where_sql}
            GROUP BY condition_id
        ) latest ON m.condition_id = latest.condition_id
                 AND m.scan_at_ms = latest.latest
    """
    metas: dict[str, MarketMeta] = {}
    for row in conn.execute(query, params):
        meta = MarketMeta(
            condition_id=str(row["condition_id"]),
            question=str(row["question"]),
            end_date_iso=str(row["end_date_iso"] or ""),
            yes_token_id=str(row["yes_token_id"]) if row["yes_token_id"] else None,
            no_token_id=str(row["no_token_id"]) if row["no_token_id"] else None,
        )
        meta._parse()
        metas[meta.condition_id] = meta
    return metas


def _first_simulated_fill(
    sig: SignalObs,
    by_asset: dict[str, list[tuple[int, float]]],
    *,
    fill_timeout_sec: float,
    until_ms: int | None,
) -> FillObs | None:
    if sig.asset_id_at_signal is None or sig.maker_limit is None:
        return None
    deadline = sig.ts_ms + int(fill_timeout_sec * 1000)
    if until_ms is not None:
        deadline = min(deadline, until_ms)
    for ts_ms, price in by_asset.get(str(sig.asset_id_at_signal), []):
        if ts_ms < sig.ts_ms:
            continue
        if ts_ms > deadline:
            break
        if price <= sig.maker_limit:
            return FillObs(ts_ms=ts_ms, price=price, source="recorder_last_trade")
    return None


def _actual_main_fill(
    conn: sqlite3.Connection | None,
    sig: SignalObs,
    meta: MarketMeta | None,
    *,
    fill_timeout_sec: float,
    until_ms: int | None,
) -> FillObs | None:
    if conn is None or meta is None or sig.asset_id_at_signal is None:
        return None
    if not (_table_exists(conn, "orders") and _table_exists(conn, "trades")):
        return None
    required_order_cols = {"order_id", "bot_id"}
    required_trade_cols = {
        "filled_at",
        "price",
        "order_id",
        "bot_id",
        "condition_id",
        "token_id",
        "side",
    }
    if not _has_columns(conn, "orders", required_order_cols) or not _has_columns(
        conn, "trades", required_trade_cols
    ):
        return None
    deadline = sig.ts_ms + int(fill_timeout_sec * 1000)
    if until_ms is not None:
        deadline = min(deadline, until_ms)
    row = conn.execute(
        """
        SELECT t.filled_at, t.price
        FROM trades t
        JOIN orders o ON o.order_id = t.order_id
        WHERE t.bot_id = 'bot_e'
          AND o.bot_id = 'bot_e'
          AND t.condition_id = ?
          AND t.token_id = ?
          AND t.side IN ('BUY', 'BUY_YES', 'BUY_NO')
          AND t.filled_at >= ?
          AND t.filled_at <= ?
        ORDER BY t.filled_at
        LIMIT 1
        """,
        (
            meta.condition_id,
            sig.asset_id_at_signal,
            _sqlite_dt_from_ms(sig.ts_ms),
            _sqlite_dt_from_ms(deadline),
        ),
    ).fetchone()
    if row is None:
        return None
    price = _safe_float(row["price"])
    if price is None:
        return None
    return FillObs(ts_ms=_parse_db_dt(str(row["filled_at"])), price=price, source="main_trades")


def _price_at_or_after(
    stream: list[tuple[int, float]],
    target_ms: int,
    *,
    until_ms: int | None,
) -> float | None:
    if until_ms is not None and target_ms > until_ms:
        return None
    for ts_ms, price in stream:
        if ts_ms >= target_ms:
            if until_ms is not None and ts_ms > until_ms:
                return None
            return price
    return None


def _parse_levels(raw: object) -> list[tuple[Decimal, Decimal]]:
    levels: list[tuple[Decimal, Decimal]] = []
    if not isinstance(raw, list):
        return levels
    for item in raw:
        try:
            if isinstance(item, dict):
                price_raw = item.get("price")
                size_raw = item.get("size")
            else:
                price_raw = item[0]
                size_raw = item[1]
            price = Decimal(str(price_raw))
            size = Decimal(str(size_raw))
        except (IndexError, InvalidOperation, TypeError, ValueError):
            continue
        if price >= 0 and size > 0:
            levels.append((price, size))
    return levels


def _depth_notional_from_book(raw_json: str | None, *, maker_limit: float | None) -> float | None:
    if raw_json is None or maker_limit is None:
        return None
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    asks = _parse_levels(payload.get("asks"))
    if not asks:
        return None
    limit = Decimal(str(maker_limit))
    notional = sum(price * size for price, size in asks if price <= limit)
    return float(notional)


def _recorder_depth(
    conn: sqlite3.Connection,
    sig: SignalObs,
    *,
    fill: FillObs | None,
    fill_timeout_sec: float,
    until_ms: int | None,
) -> DepthObs:
    if sig.asset_id_at_signal is None:
        return DepthObs(False, 0, None, "")
    end_ms = fill.ts_ms if fill is not None else sig.ts_ms + int(fill_timeout_sec * 1000)
    if until_ms is not None:
        end_ms = min(end_ms, until_ms)
    count_row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM pm_events
        WHERE event_type = 'book'
          AND asset_id = ?
          AND received_at_ms >= ?
          AND received_at_ms <= ?
        """,
        (sig.asset_id_at_signal, sig.ts_ms, end_ms),
    ).fetchone()
    snapshot_count = int(count_row["n"]) if count_row is not None else 0
    row = conn.execute(
        """
        SELECT payload_json
        FROM pm_events
        WHERE event_type = 'book'
          AND asset_id = ?
          AND received_at_ms >= ?
          AND received_at_ms <= ?
        ORDER BY received_at_ms DESC
        LIMIT 1
        """,
        (sig.asset_id_at_signal, sig.ts_ms, end_ms),
    ).fetchone()
    notional = _depth_notional_from_book(row["payload_json"], maker_limit=sig.maker_limit) if row else None
    return DepthObs(snapshot_count > 0, snapshot_count, notional, "recorder_book" if row else "")


def _main_depth(
    conn: sqlite3.Connection | None,
    sig: SignalObs,
    *,
    fill: FillObs | None,
) -> DepthObs | None:
    if conn is None or sig.asset_id_at_signal is None or not _table_exists(conn, "books"):
        return None
    book_cols = _table_columns(conn, "books")
    if not {"token_id", "snapshot_at", "asks"}.issubset(book_cols):
        return None
    end_ms = fill.ts_ms if fill is not None else sig.ts_ms
    row = conn.execute(
        """
        SELECT asks
        FROM books
        WHERE token_id = ?
          AND snapshot_at >= ?
          AND snapshot_at <= ?
        ORDER BY snapshot_at DESC
        LIMIT 1
        """,
        (sig.asset_id_at_signal, _sqlite_dt_from_ms(sig.ts_ms), _sqlite_dt_from_ms(end_ms)),
    ).fetchone()
    if row is None:
        return None
    try:
        asks = json.loads(row["asks"])
    except (TypeError, json.JSONDecodeError):
        return None
    notional = _depth_notional_from_book(json.dumps({"asks": asks}), maker_limit=sig.maker_limit)
    return DepthObs(True, 1, notional, "main_books")


def _best_depth(
    recorder_conn: sqlite3.Connection,
    main_conn: sqlite3.Connection | None,
    sig: SignalObs,
    *,
    fill: FillObs | None,
    fill_timeout_sec: float,
    until_ms: int | None,
) -> DepthObs:
    main = _main_depth(main_conn, sig, fill=fill)
    if main is not None:
        return main
    return _recorder_depth(
        recorder_conn,
        sig,
        fill=fill,
        fill_timeout_sec=fill_timeout_sec,
        until_ms=until_ms,
    )


def _outcome_label(outcome_yes_won: bool | None) -> str | None:
    if outcome_yes_won is None:
        return None
    return "YES" if outcome_yes_won else "NO"


def _signal_won(sig: SignalObs) -> bool | None:
    if sig.outcome_yes_won is None:
        return None
    return bool(sig.outcome_yes_won) if sig.side == "BUY_YES" else not bool(sig.outcome_yes_won)


def _adverse_values(
    *,
    asset_id: str | None,
    fill: FillObs | None,
    by_asset: dict[str, list[tuple[int, float]]],
    until_ms: int | None,
) -> dict[int, tuple[float | None, float | None, bool | None]]:
    stream = by_asset.get(str(asset_id), []) if asset_id else []
    values: dict[int, tuple[float | None, float | None, bool | None]] = {}
    for horizon_sec in ADVERSE_HORIZONS_SEC:
        price: float | None = None
        delta: float | None = None
        moved: bool | None = None
        if fill is not None:
            target_ms = fill.ts_ms + horizon_sec * 1000
            price = _price_at_or_after(stream, target_ms, until_ms=until_ms)
            if price is not None:
                delta = round(price - fill.price, 8)
                moved = delta < 0
        values[horizon_sec] = (price, delta, moved)
    return values


def _build_replay_row(
    sig: SignalObs,
    *,
    meta: MarketMeta | None,
    fill: FillObs | None,
    depth: DepthObs,
    by_asset: dict[str, list[tuple[int, float]]],
    until_ms: int | None,
) -> ReplayRow:
    adverse_values = _adverse_values(
        asset_id=sig.asset_id_at_signal,
        fill=fill,
        by_asset=by_asset,
        until_ms=until_ms,
    )

    notes: list[str] = []
    if sig.maker_limit is None:
        notes.append("no_maker_limit")
    if fill is None:
        notes.append("no_crossing_trade_within_timeout")
    if sig.outcome_yes_won is None:
        notes.append("outcome_unavailable_in_window")
    if fill is not None and any(v[0] is None for v in adverse_values.values()):
        notes.append("some_adverse_horizons_unavailable")

    return ReplayRow(
        row_type="replay_signal",
        order_id=None,
        order_status=None,
        placed_at_ms=None,
        last_updated_ms=None,
        signal_id=f"{sig.sub_id}:{sig.ts_ms}",
        subscription_id=sig.sub_id,
        condition_id=meta.condition_id if meta else None,
        t0_ms=sig.ts_ms,
        t0_iso=_ms_to_iso(sig.ts_ms),
        side=sig.side,
        asset_id=sig.asset_id_at_signal,
        signal_price=sig.signal_price,
        maker_limit=sig.maker_limit,
        filled=fill is not None,
        fill_ts_ms=fill.ts_ms if fill else None,
        fill_delay_sec=round((fill.ts_ms - sig.ts_ms) / 1000, 3) if fill else None,
        fill_price=fill.price if fill else None,
        fill_source=fill.source if fill else "",
        book_covered=depth.covered,
        book_snapshot_count=depth.snapshot_count,
        depth_notional=depth.notional,
        depth_source=depth.source,
        adverse_30s_price=adverse_values[30][0],
        adverse_30s_delta=adverse_values[30][1],
        adverse_30s_moved_against=adverse_values[30][2],
        adverse_60s_price=adverse_values[60][0],
        adverse_60s_delta=adverse_values[60][1],
        adverse_60s_moved_against=adverse_values[60][2],
        adverse_300s_price=adverse_values[300][0],
        adverse_300s_delta=adverse_values[300][1],
        adverse_300s_moved_against=adverse_values[300][2],
        outcome_label=_outcome_label(sig.outcome_yes_won),
        signal_won=_signal_won(sig),
        outcome_source="cex_start_end" if sig.outcome_yes_won is not None else "",
        notes=";".join(notes),
    )


def _main_order_fill(conn: sqlite3.Connection, order_id: str) -> FillObs | None:
    if not _has_columns(conn, "trades", {"filled_at", "price", "order_id", "bot_id"}):
        return None
    row = conn.execute(
        """
        SELECT filled_at, price
        FROM trades
        WHERE bot_id = 'bot_e'
          AND order_id = ?
        ORDER BY filled_at
        LIMIT 1
        """,
        (order_id,),
    ).fetchone()
    if row is None:
        return None
    price = _safe_float(row["price"])
    if price is None:
        return None
    return FillObs(ts_ms=_parse_db_dt(str(row["filled_at"])), price=price, source="main_order_trade")


def _main_book_depth_for_order(
    conn: sqlite3.Connection,
    *,
    token_id: str,
    placed_at_ms: int,
    end_ms: int,
    maker_limit: float | None,
) -> DepthObs:
    if not _has_columns(conn, "books", {"token_id", "snapshot_at", "asks"}):
        return DepthObs(False, 0, None, "")
    count_row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM books
        WHERE token_id = ?
          AND snapshot_at >= ?
          AND snapshot_at <= ?
        """,
        (token_id, _sqlite_dt_from_ms(placed_at_ms), _sqlite_dt_from_ms(end_ms)),
    ).fetchone()
    snapshot_count = int(count_row["n"]) if count_row is not None else 0
    row = conn.execute(
        """
        SELECT asks
        FROM books
        WHERE token_id = ?
          AND snapshot_at >= ?
          AND snapshot_at <= ?
        ORDER BY snapshot_at DESC
        LIMIT 1
        """,
        (token_id, _sqlite_dt_from_ms(placed_at_ms), _sqlite_dt_from_ms(end_ms)),
    ).fetchone()
    if row is None:
        return DepthObs(snapshot_count > 0, snapshot_count, None, "main_books" if snapshot_count else "")
    try:
        asks = json.loads(row["asks"])
    except (TypeError, json.JSONDecodeError):
        return DepthObs(snapshot_count > 0, snapshot_count, None, "main_books")
    notional = _depth_notional_from_book(json.dumps({"asks": asks}), maker_limit=maker_limit)
    return DepthObs(snapshot_count > 0, snapshot_count, notional, "main_books")


def _main_order_rows(
    conn: sqlite3.Connection | None,
    *,
    by_asset: dict[str, list[tuple[int, float]]],
    since_ms: int,
    until_ms: int,
) -> list[ReplayRow]:
    required_order_cols = {
        "order_id",
        "bot_id",
        "condition_id",
        "token_id",
        "side",
        "price",
        "status",
        "placed_at",
        "last_updated",
    }
    if conn is None or not _has_columns(conn, "orders", required_order_cols):
        return []

    out: list[ReplayRow] = []
    rows = conn.execute(
        """
        SELECT order_id, condition_id, token_id, side, price, status,
               placed_at, last_updated
        FROM orders
        WHERE bot_id = 'bot_e'
          AND placed_at >= ?
          AND placed_at <= ?
        ORDER BY placed_at
        """,
        (_sqlite_dt_from_ms(since_ms), _sqlite_dt_from_ms(until_ms)),
    )
    for row in rows:
        order_id = str(row["order_id"])
        token_id = str(row["token_id"])
        placed_at_ms = _parse_db_dt(str(row["placed_at"]))
        last_updated_ms = _parse_db_dt(str(row["last_updated"])) if row["last_updated"] else None
        price = _safe_float(row["price"])
        fill = _main_order_fill(conn, order_id)
        if fill is not None and fill.ts_ms > until_ms:
            fill = None
        end_ms = min(fill.ts_ms if fill else (last_updated_ms or until_ms), until_ms)
        depth = _main_book_depth_for_order(
            conn,
            token_id=token_id,
            placed_at_ms=placed_at_ms,
            end_ms=end_ms,
            maker_limit=price,
        )
        adverse_values = _adverse_values(
            asset_id=token_id,
            fill=fill,
            by_asset=by_asset,
            until_ms=until_ms,
        )
        status = str(row["status"])
        notes = ["actual_main_order_denominator"]
        if fill is None:
            notes.append("no_trade_row_in_window")
        if status.upper() in {"CANCELLED", "EXCHANGE_CLOSED"}:
            notes.append("cancel_or_closed_order")
        out.append(
            ReplayRow(
                row_type="main_order",
                order_id=order_id,
                order_status=status,
                placed_at_ms=placed_at_ms,
                last_updated_ms=last_updated_ms,
                signal_id="",
                subscription_id="",
                condition_id=str(row["condition_id"]),
                t0_ms=placed_at_ms,
                t0_iso=_ms_to_iso(placed_at_ms),
                side=str(row["side"]),
                asset_id=token_id,
                signal_price=price,
                maker_limit=price,
                filled=fill is not None,
                fill_ts_ms=fill.ts_ms if fill else None,
                fill_delay_sec=round((fill.ts_ms - placed_at_ms) / 1000, 3) if fill else None,
                fill_price=fill.price if fill else None,
                fill_source=fill.source if fill else "",
                book_covered=depth.covered,
                book_snapshot_count=depth.snapshot_count,
                depth_notional=depth.notional,
                depth_source=depth.source,
                adverse_30s_price=adverse_values[30][0],
                adverse_30s_delta=adverse_values[30][1],
                adverse_30s_moved_against=adverse_values[30][2],
                adverse_60s_price=adverse_values[60][0],
                adverse_60s_delta=adverse_values[60][1],
                adverse_60s_moved_against=adverse_values[60][2],
                adverse_300s_price=adverse_values[300][0],
                adverse_300s_delta=adverse_values[300][1],
                adverse_300s_moved_against=adverse_values[300][2],
                outcome_label=None,
                signal_won=None,
                outcome_source="",
                notes=";".join(notes),
            )
        )
    return out


def run_replay(
    recorder_db: Path,
    *,
    main_db: Path | None = None,
    since_ms: int,
    until_ms: int,
    fill_timeout_sec: float = DEFAULT_FILL_TIMEOUT_SEC,
) -> dict[str, Any]:
    recorder_conn = _connect_ro(recorder_db)
    main_conn = _connect_ro(main_db) if main_db is not None else None
    try:
        warmup_since_ms = max(0, since_ms - int(OBI_WINDOW_SEC * 1000))
        metas = _load_markets_bounded(
            recorder_conn,
            since_ms=warmup_since_ms,
            until_ms=until_ms,
        )
        token_to_market = build_token_to_market(metas)
        sub_to_meta = build_sub_to_market(
            recorder_conn,
            token_to_market,
            since_ms=warmup_since_ms,
            until_ms=until_ms,
        )
        signals, n_events = replay_signals(
            recorder_conn,
            token_to_market,
            sub_to_meta,
            since_ms=warmup_since_ms,
            until_ms=until_ms,
        )
        signals = [sig for sig in signals if sig.ts_ms >= since_ms]

        cex_symbols = sorted({m.cex_symbol for m in metas.values() if m.cex_symbol})
        cex_prices = load_cex_prices(
            recorder_conn,
            cex_symbols,
            since_ms=since_ms,
            until_ms=until_ms,
        )
        outcomes = detect_resolutions_via_cex(metas, cex_prices, since_ms, until_ms)
        attach_outcomes(signals, outcomes, sub_to_meta)

        by_asset = _event_prices_by_asset(
            recorder_conn,
            since_ms=since_ms,
            until_ms=until_ms,
        )
        signal_rows: list[ReplayRow] = []
        for sig in signals:
            meta = sub_to_meta.get(sig.sub_id)
            actual_fill = _actual_main_fill(
                main_conn,
                sig,
                meta,
                fill_timeout_sec=fill_timeout_sec,
                until_ms=until_ms,
            )
            fill = actual_fill or _first_simulated_fill(
                sig,
                by_asset,
                fill_timeout_sec=fill_timeout_sec,
                until_ms=until_ms,
            )
            depth = _best_depth(
                recorder_conn,
                main_conn,
                sig,
                fill=fill,
                fill_timeout_sec=fill_timeout_sec,
                until_ms=until_ms,
            )
            signal_rows.append(
                _build_replay_row(
                    sig,
                    meta=meta,
                    fill=fill,
                    depth=depth,
                    by_asset=by_asset,
                    until_ms=until_ms,
                )
            )
        main_order_rows = _main_order_rows(
            main_conn,
            by_asset=by_asset,
            since_ms=since_ms,
            until_ms=until_ms,
        )
        rows = signal_rows + main_order_rows

        filled = sum(1 for row in rows if row.filled)
        outcome_labelled = sum(1 for row in rows if row.outcome_label is not None)
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "recorder_db": str(recorder_db),
            "main_db": str(main_db) if main_db else None,
            "since_ms": since_ms,
            "until_ms": until_ms,
            "fill_timeout_sec": fill_timeout_sec,
            "summary": {
                "pm_events_processed": n_events,
                "rows": len(rows),
                "signals": len(signal_rows),
                "main_orders": len(main_order_rows),
                "filled": filled,
                "not_filled": len(rows) - filled,
                "fill_rate": round(filled / len(rows), 4) if rows else 0.0,
                "outcome_labelled": outcome_labelled,
            },
            "rows": [row.to_dict() for row in rows],
        }
    finally:
        recorder_conn.close()
        if main_conn is not None:
            main_conn.close()


def write_csv(report: dict[str, Any], out_path: Path) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = report["rows"]
    with out_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in CSV_COLUMNS})
    return len(rows)


def write_json(report: dict[str, Any], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def _resolve_bounds(args: argparse.Namespace) -> tuple[int, int]:
    if args.lookback_hours is not None:
        if args.lookback_hours <= 0:
            raise SystemExit("--lookback-hours must be positive")
        until_ms = args.until_ms or int(time.time() * 1000)
        since_ms = until_ms - int(args.lookback_hours * 60 * 60 * 1000)
        return since_ms, until_ms
    if args.since_ms is None or args.until_ms is None:
        raise SystemExit("provide --lookback-hours or both --since-ms and --until-ms")
    if args.until_ms < args.since_ms:
        raise SystemExit("--until-ms must be >= --since-ms")
    return args.since_ms, args.until_ms


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--recorder-db", type=Path, default=DEFAULT_RECORDER_DB)
    parser.add_argument("--main-db", type=Path, default=None)
    parser.add_argument("--since-ms", type=int, default=None)
    parser.add_argument("--until-ms", type=int, default=None)
    parser.add_argument("--lookback-hours", type=float, default=None)
    parser.add_argument("--fill-timeout-sec", type=float, default=DEFAULT_FILL_TIMEOUT_SEC)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    since_ms, until_ms = _resolve_bounds(args)
    if not args.recorder_db.exists():
        print(f"recorder DB not found: {args.recorder_db}", file=sys.stderr)
        return 2
    if args.main_db is not None and not args.main_db.exists():
        print(f"main DB not found: {args.main_db}", file=sys.stderr)
        return 2
    report = run_replay(
        args.recorder_db,
        main_db=args.main_db,
        since_ms=since_ms,
        until_ms=until_ms,
        fill_timeout_sec=args.fill_timeout_sec,
    )
    if args.output_csv is not None:
        n = write_csv(report, args.output_csv)
        print(f"wrote {n} rows to {args.output_csv}")
    if args.output_json is not None:
        write_json(report, args.output_json)
        print(f"wrote {args.output_json}")
    if args.output_csv is None and args.output_json is None:
        print(json.dumps({"summary": report["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
