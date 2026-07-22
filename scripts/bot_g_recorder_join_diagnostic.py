#!/usr/bin/env python3
"""Read-only Bot G order-to-recorder book diagnostic.

For each Bot G order, joins nearby crypto-recorder events around placed_at and
reports observed bid/ask/depth versus submitted limit and actual fill price.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.bot_g_crypto_replay_grid import connect_ro, parse_dt, table_exists

DEFAULT_MAIN_DB = Path("data/main.db")
DEFAULT_RECORDER_DB = Path("data/bot_e_recorder.db")


def dt_to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def payload(raw: object) -> dict[str, Any]:
    try:
        parsed = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _num(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_snapshot(event_type: str, raw: object, token_id: str) -> dict[str, float | None]:
    data = payload(raw)
    if event_type == "price_change":
        for change in data.get("price_changes") or []:
            if not isinstance(change, dict) or str(change.get("asset_id") or "") != token_id:
                continue
            return {
                "observed_bid": _num(change.get("best_bid")),
                "observed_ask": _num(change.get("best_ask")),
                "ask_size": _num(change.get("size")) if str(change.get("side") or "").upper() == "SELL" else None,
            }
    if event_type == "best_bid_ask":
        if str(data.get("asset_id") or data.get("assetId") or "") not in {"", token_id}:
            return {"observed_bid": None, "observed_ask": None, "ask_size": None}
        return {
            "observed_bid": _num(data.get("best_bid") or data.get("bid")),
            "observed_ask": _num(data.get("best_ask") or data.get("ask")),
            "ask_size": _num(data.get("ask_size") or data.get("askSize")),
        }
    if event_type == "book":
        if str(data.get("asset_id") or data.get("assetId") or "") not in {"", token_id}:
            return {"observed_bid": None, "observed_ask": None, "ask_size": None}
        bids = data.get("bids") or []
        asks = data.get("asks") or []
        bid_prices = [_num((row or {}).get("price") if isinstance(row, dict) else row[0]) for row in bids if row]
        ask_rows = [row for row in asks if row]
        asks_parsed = []
        for row in ask_rows:
            if isinstance(row, dict):
                price = _num(row.get("price"))
                size = _num(row.get("size") or row.get("amount"))
            else:
                price = _num(row[0])
                size = _num(row[1] if len(row) > 1 else None)
            if price is not None:
                asks_parsed.append((price, size))
        best_ask = min((price for price, _size in asks_parsed), default=None)
        ask_size = next((size for price, size in asks_parsed if price == best_ask), None)
        return {
            "observed_bid": max((p for p in bid_prices if p is not None), default=None),
            "observed_ask": best_ask,
            "ask_size": ask_size,
        }
    return {"observed_bid": None, "observed_ask": None, "ask_size": None}


def nearest_snapshot(
    recorder: sqlite3.Connection,
    *,
    token_id: str,
    placed_at: datetime,
    before_ms: int,
    after_ms: int,
) -> dict[str, Any]:
    if not table_exists(recorder, "pm_events"):
        return {}
    start_ms = dt_to_ms(placed_at) - before_ms
    end_ms = dt_to_ms(placed_at) + after_ms
    rows = recorder.execute(
        """
        SELECT received_at_ms, event_type, payload_json
        FROM pm_events
        WHERE asset_id = ?
          AND received_at_ms BETWEEN ? AND ?
          AND event_type IN ('best_bid_ask', 'price_change', 'book')
        ORDER BY ABS(received_at_ms - ?), received_at_ms DESC
        LIMIT 25
        """,
        (token_id, start_ms, end_ms, dt_to_ms(placed_at)),
    )
    for row in rows:
        snap = extract_snapshot(str(row["event_type"] or ""), row["payload_json"], token_id)
        if snap.get("observed_bid") is not None or snap.get("observed_ask") is not None:
            return {
                "recorder_event_ms": int(row["received_at_ms"]),
                "recorder_event_type": row["event_type"],
                **snap,
            }
    return {}


def fill_price_by_order(main: sqlite3.Connection, *, bot_ids: tuple[str, ...], cutoff: datetime) -> dict[str, float]:
    if not table_exists(main, "trades"):
        return {}
    placeholders = ",".join("?" for _ in bot_ids)
    rows = main.execute(
        f"""
        SELECT order_id, price
        FROM trades
        WHERE bot_id IN ({placeholders})
          AND side LIKE 'BUY%'
          AND filled_at >= ?
        ORDER BY filled_at
        """,
        (*bot_ids, cutoff.strftime("%Y-%m-%d %H:%M:%S")),
    )
    out = {}
    for row in rows:
        order_id = str(row["order_id"] or "")
        if order_id and order_id not in out:
            out[order_id] = float(row["price"] or 0)
    return out


def build_rows(
    main: sqlite3.Connection,
    recorder: sqlite3.Connection,
    *,
    bot_ids: tuple[str, ...],
    cutoff: datetime,
    before_ms: int,
    after_ms: int,
) -> list[dict[str, Any]]:
    if not table_exists(main, "orders"):
        return []
    placeholders = ",".join("?" for _ in bot_ids)
    fills = fill_price_by_order(main, bot_ids=bot_ids, cutoff=cutoff)
    rows = []
    for order in main.execute(
        f"""
        SELECT order_id, bot_id, placed_at, token_id, price, status
        FROM orders
        WHERE bot_id IN ({placeholders})
          AND placed_at >= ?
        ORDER BY placed_at
        """,
        (*bot_ids, cutoff.strftime("%Y-%m-%d %H:%M:%S")),
    ):
        placed_at = parse_dt(order["placed_at"])
        token_id = str(order["token_id"] or "")
        snap = (
            nearest_snapshot(
                recorder,
                token_id=token_id,
                placed_at=placed_at,
                before_ms=before_ms,
                after_ms=after_ms,
            )
            if placed_at and token_id
            else {}
        )
        limit = float(order["price"] or 0)
        fill = fills.get(str(order["order_id"] or ""))
        observed_ask = snap.get("observed_ask")
        observed_bid = snap.get("observed_bid")
        rows.append(
            {
                "order_id": order["order_id"],
                "bot_id": order["bot_id"],
                "placed_at": order["placed_at"],
                "token_id": token_id,
                "submitted_limit": limit,
                "fill_price": fill,
                "observed_ask": observed_ask,
                "observed_bid": observed_bid,
                "ask_size": snap.get("ask_size"),
                "spread_cents": (
                    round((float(observed_ask) - float(observed_bid)) * 100, 4)
                    if observed_ask is not None and observed_bid is not None
                    else None
                ),
                "price_improvement_cents": (
                    round((limit - fill) * 100, 4) if fill is not None else None
                ),
                "recorder_event_ms": snap.get("recorder_event_ms"),
                "recorder_event_type": snap.get("recorder_event_type"),
                "status": order["status"],
            }
        )
    return rows


def improvement_bucket(value: object) -> str:
    if value is None:
        return "no_fill"
    v = float(value)
    if v <= 0:
        return "no_improvement"
    if v < 0.5:
        return "<0.5c"
    if v < 1:
        return "0.5c-1c"
    if v < 2:
        return "1c-2c"
    if v < 4:
        return "2c-4c"
    return ">4c"


def render_markdown(rows: list[dict[str, Any]]) -> str:
    live = [row for row in rows if row["bot_id"] == "bot_g_prime_live"]
    buckets: dict[str, int] = {}
    for row in live:
        bucket = improvement_bucket(row.get("price_improvement_cents"))
        buckets[bucket] = buckets.get(bucket, 0) + 1
    lines = [
        "# Bot G Recorder Join Diagnostic",
        "",
        "Read-only diagnostic joining orders to nearby recorder book events.",
        "",
        "## Live Price Improvement",
        "",
        "| bucket | orders |",
        "|---|---:|",
    ]
    for bucket in ("no_fill", "no_improvement", "<0.5c", "0.5c-1c", "1c-2c", "2c-4c", ">4c"):
        lines.append(f"| {bucket} | {buckets.get(bucket, 0)} |")
    lines.extend([
        "",
        "## Recent Rows",
        "",
        "| bot | placed | limit | fill | ask | bid | spread c | improvement c | status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ])
    for row in rows[-25:]:
        fill_text = "" if row["fill_price"] is None else f"{row['fill_price']:.4f}"
        ask_text = "" if row["observed_ask"] is None else f"{row['observed_ask']:.4f}"
        bid_text = "" if row["observed_bid"] is None else f"{row['observed_bid']:.4f}"
        spread_text = "" if row["spread_cents"] is None else str(row["spread_cents"])
        improvement_text = (
            ""
            if row["price_improvement_cents"] is None
            else str(row["price_improvement_cents"])
        )
        lines.append(
            f"| {row['bot_id']} | {row['placed_at']} | {row['submitted_limit']:.4f} | "
            f"{fill_text} | {ask_text} | {bid_text} | {spread_text} | "
            f"{improvement_text} | "
            f"{row['status']} |"
        )
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "order_id", "bot_id", "placed_at", "token_id", "submitted_limit",
        "fill_price", "observed_ask", "observed_bid", "ask_size",
        "spread_cents", "price_improvement_cents", "recorder_event_ms",
        "recorder_event_type", "status",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Join Bot G orders to recorder snapshots.")
    parser.add_argument("--db", type=Path, default=DEFAULT_MAIN_DB)
    parser.add_argument("--recorder-db", type=Path, default=DEFAULT_RECORDER_DB)
    parser.add_argument("--lookback-hours", type=float, default=72.0)
    parser.add_argument("--bot-id", action="append", dest="bot_ids")
    parser.add_argument("--before-ms", type=int, default=5000)
    parser.add_argument("--after-ms", type=int, default=1000)
    parser.add_argument("--out-csv", "--output-csv", dest="output_csv", type=Path)
    parser.add_argument("--out-md", "--output-md", dest="output_md", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bot_ids = tuple(args.bot_ids or ["bot_g_prime_live", "bot_g_prime"])
    cutoff = datetime.now(UTC) - timedelta(hours=args.lookback_hours)
    main_con = connect_ro(args.db)
    recorder_con = connect_ro(args.recorder_db)
    try:
        rows = build_rows(
            main_con,
            recorder_con,
            bot_ids=bot_ids,
            cutoff=cutoff,
            before_ms=args.before_ms,
            after_ms=args.after_ms,
        )
    finally:
        main_con.close()
        recorder_con.close()
    markdown = render_markdown(rows)
    if args.output_csv:
        write_csv(args.output_csv, rows)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown)
    if not args.output_md:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
