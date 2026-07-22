#!/usr/bin/env python3
"""Read-only Bot G crypto recorder replay grid.

This report compares actual Bot G paper/live entries against the shared crypto
recorder tape. It is intentionally analysis-only: no order placement, no wallet
calls, and no live setting changes.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.bot_g_feature_analysis import fetch_trades, fifo_match

DEFAULT_MAIN_DB = Path("data/main.db")
DEFAULT_RECORDER_DB = Path("data/bot_e_recorder.db")

SYMBOL_NEEDLES = {
    "BTC": ("BTC", "BITCOIN"),
    "ETH": ("ETH", "ETHEREUM"),
    "SOL": ("SOL", "SOLANA"),
    "XRP": ("XRP", "RIPPLE"),
    "DOGE": ("DOGE", "DOGECOIN"),
}


@dataclass(frozen=True)
class MarketMeta:
    condition_id: str
    question: str
    end_date: datetime | None
    yes_token_id: str | None
    no_token_id: str | None
    symbol: str
    duration_minutes: int | None


def connect_ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def parse_dt(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def iso_sql(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def payload_dict(raw: object) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in con.execute(f"PRAGMA table_info({table})")}


def symbol_from_question(question: object) -> str:
    q = str(question or "").upper()
    for symbol, needles in SYMBOL_NEEDLES.items():
        if any(needle in q for needle in needles):
            return symbol
    return "unknown"


def price_bucket(price: object) -> str:
    try:
        p = float(price)
    except (TypeError, ValueError):
        return "unknown"
    if p < 0.01:
        return "<1c"
    if p < 0.03:
        return "1c-3c"
    if p < 0.035:
        return "3c-3.5c"
    if p <= 0.055:
        return "3.5c-5.5c"
    if p <= 0.08:
        return "5.5c-8c"
    return ">8c"


def lead_bucket(seconds: object) -> str:
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return "unknown"
    if s < 0:
        return "after_close"
    if s < 30:
        return "<30s"
    if s < 45:
        return "30s-45s"
    if s < 60:
        return "45s-60s"
    if s < 90:
        return "60s-90s"
    return ">=90s"


def theory_band_for_lead(bucket: str) -> str:
    return {
        "45s-60s": "5c-8c theory lane",
        "30s-45s": "3c-5c theory lane",
        "<30s": "1c-3c theory lane",
    }.get(bucket, "outside theory lanes")


def cheap_price_from_yes(yes_price: object) -> float | None:
    try:
        p = float(yes_price)
    except (TypeError, ValueError):
        return None
    if not 0 <= p <= 1:
        return None
    return min(p, 1.0 - p)


def load_entry_payloads(
    con: sqlite3.Connection,
    *,
    bot_ids: tuple[str, ...],
    cutoff: datetime,
) -> dict[str, dict[str, Any]]:
    if not bot_ids or not table_exists(con, "events"):
        return {}
    placeholders = ",".join("?" for _ in bot_ids)
    out: dict[str, dict[str, Any]] = {}
    for row in con.execute(
        f"""
        SELECT bot_id, created_at, payload
        FROM events
        WHERE bot_id IN ({placeholders})
          AND event_type = 'bot_g.entry_placed'
          AND created_at >= ?
          AND payload IS NOT NULL
        ORDER BY created_at
        """,
        (*bot_ids, iso_sql(cutoff)),
    ):
        payload = payload_dict(row["payload"])
        order_id = str(payload.get("order_id") or "")
        if not order_id:
            continue
        payload["_bot_id"] = row["bot_id"]
        payload["_created_at"] = row["created_at"]
        out[order_id] = payload
    return out


def load_market_meta(
    recorder: sqlite3.Connection,
    condition_ids: set[str],
) -> dict[str, MarketMeta]:
    if not condition_ids or not table_exists(recorder, "markets"):
        return {}
    cols = table_columns(recorder, "markets")
    symbol_expr = "symbol" if "symbol" in cols else "NULL AS symbol"
    duration_expr = (
        "duration_minutes" if "duration_minutes" in cols else "NULL AS duration_minutes"
    )
    placeholders = ",".join("?" for _ in condition_ids)
    rows = recorder.execute(
        f"""
        SELECT condition_id, question, end_date_iso, yes_token_id, no_token_id,
               {symbol_expr}, {duration_expr}
        FROM markets
        WHERE id IN (
            SELECT MAX(id)
            FROM markets
            WHERE condition_id IN ({placeholders})
            GROUP BY condition_id
        )
        """,
        tuple(sorted(condition_ids)),
    ).fetchall()
    out: dict[str, MarketMeta] = {}
    for row in rows:
        question = str(row["question"] or "")
        symbol = str(row["symbol"] or "").upper() or symbol_from_question(question)
        duration = row["duration_minutes"]
        out[str(row["condition_id"])] = MarketMeta(
            condition_id=str(row["condition_id"]),
            question=question,
            end_date=parse_dt(row["end_date_iso"]),
            yes_token_id=str(row["yes_token_id"]) if row["yes_token_id"] else None,
            no_token_id=str(row["no_token_id"]) if row["no_token_id"] else None,
            symbol=symbol,
            duration_minutes=int(duration) if duration is not None else None,
        )
    return out


def load_trades_by_order(
    con: sqlite3.Connection,
    *,
    bot_ids: tuple[str, ...],
    cutoff: datetime,
) -> dict[str, dict[str, Any]]:
    if not bot_ids or not table_exists(con, "trades"):
        return {}
    placeholders = ",".join("?" for _ in bot_ids)
    out: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "buy_notional": 0.0,
            "buy_size": 0.0,
            "settle_notional": 0.0,
            "settle_size": 0.0,
            "fills": 0,
            "settlements": 0,
        }
    )
    for row in con.execute(
        f"""
        SELECT order_id, side, price, size, filled_at
        FROM trades
        WHERE bot_id IN ({placeholders})
          AND filled_at >= ?
        ORDER BY filled_at
        """,
        (*bot_ids, iso_sql(cutoff)),
    ):
        order_id = str(row["order_id"] or "")
        if not order_id:
            continue
        side = str(row["side"] or "").upper()
        price = float(row["price"] or 0)
        size = float(row["size"] or 0)
        if side.startswith("BUY"):
            out[order_id]["buy_notional"] += price * size
            out[order_id]["buy_size"] += size
            out[order_id]["fills"] += 1
        elif side.startswith("SELL"):
            out[order_id]["settle_notional"] += price * size
            out[order_id]["settle_size"] += size
            out[order_id]["settlements"] += 1
    return dict(out)


def load_closed_by_order(
    con: sqlite3.Connection,
    *,
    bot_ids: tuple[str, ...],
    cutoff: datetime,
    entry_payloads: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    trades = [
        trade
        for trade in fetch_trades(con, bot_ids=bot_ids)
        if (filled_at := parse_dt(trade.get("filled_at"))) is not None
        and filled_at >= cutoff
    ]
    closed_rows = fifo_match(trades, entry_events=entry_payloads, con=con)
    out: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "closed": 0,
            "wins": 0,
            "buy_notional": 0.0,
            "settle_notional": 0.0,
            "pnl_usd": 0.0,
        }
    )
    for row in closed_rows:
        order_id = str(row.get("order_id") or "")
        if not order_id:
            continue
        size = float(row.get("size") or 0)
        buy_price = float(row.get("buy_price") or 0)
        pnl = float(row.get("pnl_usd") or 0)
        out[order_id]["closed"] += 1
        out[order_id]["wins"] += 1 if row.get("win") else 0
        out[order_id]["buy_notional"] += buy_price * size
        out[order_id]["settle_notional"] += (buy_price * size) + pnl
        out[order_id]["pnl_usd"] += pnl
    return dict(out)


def load_bot_orders(
    main: sqlite3.Connection,
    recorder: sqlite3.Connection,
    *,
    bot_ids: tuple[str, ...],
    cutoff: datetime,
) -> list[dict[str, Any]]:
    if not table_exists(main, "orders"):
        return []
    placeholders = ",".join("?" for _ in bot_ids)
    order_rows = main.execute(
        f"""
        SELECT bot_id, order_id, condition_id, token_id, price, size, status, placed_at
        FROM orders
        WHERE bot_id IN ({placeholders})
          AND placed_at >= ?
        ORDER BY placed_at
        """,
        (*bot_ids, iso_sql(cutoff)),
    ).fetchall()
    payloads = load_entry_payloads(main, bot_ids=bot_ids, cutoff=cutoff)
    condition_ids = {str(row["condition_id"]) for row in order_rows if row["condition_id"]}
    meta = load_market_meta(recorder, condition_ids)
    trades = load_trades_by_order(main, bot_ids=bot_ids, cutoff=cutoff)
    closed_by_order = load_closed_by_order(
        main,
        bot_ids=bot_ids,
        cutoff=cutoff,
        entry_payloads=payloads,
    )

    out: list[dict[str, Any]] = []
    for row in order_rows:
        order_id = str(row["order_id"] or "")
        payload = payloads.get(order_id, {})
        condition_id = str(row["condition_id"] or "")
        market = meta.get(condition_id)
        placed_at = parse_dt(row["placed_at"])
        lead_seconds = payload.get("fresh_t_to_res_sec")
        if lead_seconds is None and market and market.end_date and placed_at:
            lead_seconds = (market.end_date - placed_at).total_seconds()
        observed_price = (
            payload.get("observed_ask_price")
            or payload.get("ask_price")
            or payload.get("limit_price")
            or row["price"]
        )
        trade = trades.get(order_id, {})
        closed_info = closed_by_order.get(order_id, {})
        status = str(row["status"] or "")
        fills = int(trade.get("fills") or 0)
        if fills:
            outcome = "filled"
        elif status == "EXCHANGE_CLOSED":
            outcome = "no_fill"
        elif status.upper() in {"OPEN", "PARTIAL", "LIVE"}:
            outcome = "open"
        else:
            outcome = "unfilled_or_pending"
        closed_count = int(closed_info.get("closed") or 0)
        closed = closed_count > 0
        pnl = float(closed_info.get("pnl_usd") or 0)
        symbol = market.symbol if market else symbol_from_question(payload.get("question"))
        out.append(
            {
                "bot_id": row["bot_id"],
                "order_id": order_id,
                "condition_id": condition_id,
                "token_id": row["token_id"],
                "placed_at": row["placed_at"],
                "status": status,
                "limit_price": float(row["price"] or 0),
                "size": float(row["size"] or 0),
                "observed_price": float(observed_price or 0),
                "price_bucket": price_bucket(observed_price),
                "lead_seconds": lead_seconds,
                "lead_bucket": lead_bucket(lead_seconds),
                "theory_lane": theory_band_for_lead(lead_bucket(lead_seconds)),
                "symbol": symbol,
                "side_token": str(payload.get("side_token") or "UNKNOWN"),
                "execution_mode": str(payload.get("execution_mode") or ""),
                "duration_minutes": market.duration_minutes if market else None,
                "question": market.question if market else "",
                "outcome": outcome,
                "filled": fills > 0,
                "closed": closed,
                "win": int(closed_info.get("wins") or 0) > 0,
                "buy_notional": round(
                    float(closed_info.get("buy_notional") or trade.get("buy_notional") or 0),
                    6,
                ),
                "settle_notional": round(float(closed_info.get("settle_notional") or 0), 6),
                "pnl_usd": round(pnl, 6) if closed else 0.0,
            }
        )
    return out


def trim_roi(rows: list[dict[str, Any]], remove_wins: int) -> float | None:
    closed = [row for row in rows if row.get("closed")]
    if remove_wins:
        winners = sorted(
            [row for row in closed if float(row.get("pnl_usd") or 0) > 0],
            key=lambda row: float(row.get("pnl_usd") or 0),
            reverse=True,
        )
        remove_ids = {id(row) for row in winners[:remove_wins]}
        closed = [row for row in closed if id(row) not in remove_ids]
    cost = sum(float(row.get("buy_notional") or 0) for row in closed)
    pnl = sum(float(row.get("pnl_usd") or 0) for row in closed)
    return round(pnl / cost * 100, 2) if cost else None


def summarise_entry_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    placed = len(rows)
    filled = sum(1 for row in rows if row.get("filled"))
    closed = [row for row in rows if row.get("closed")]
    no_fill = sum(1 for row in rows if row.get("outcome") == "no_fill")
    open_count = sum(1 for row in rows if row.get("outcome") == "open")
    cost = sum(float(row.get("buy_notional") or 0) for row in closed)
    pnl = sum(float(row.get("pnl_usd") or 0) for row in closed)
    return {
        "placed": placed,
        "filled": filled,
        "closed": len(closed),
        "wins": sum(1 for row in closed if row.get("win")),
        "no_fill": no_fill,
        "open": open_count,
        "cost_usd": round(cost, 4),
        "pnl_usd": round(pnl, 4),
        "roi_pct": round(pnl / cost * 100, 2) if cost else None,
        "ex_largest_win_roi_pct": trim_roi(rows, 1),
        "ex_largest_two_roi_pct": trim_roi(rows, 2),
        "fill_rate_pct": round(filled / placed * 100, 2) if placed else None,
    }


def group_entries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = sorted(
        {
            (
                str(row.get("bot_id") or "unknown"),
                str(row.get("lead_bucket") or "unknown"),
                str(row.get("price_bucket") or "unknown"),
                str(row.get("symbol") or "unknown"),
                str(row.get("duration_minutes") or "unknown"),
            )
            for row in rows
        }
    )
    out: dict[str, Any] = {}
    for bot_id, lead, price, symbol, duration in keys:
        group_rows = [
            row
            for row in rows
            if str(row.get("bot_id") or "unknown") == bot_id
            and str(row.get("lead_bucket") or "unknown") == lead
            and str(row.get("price_bucket") or "unknown") == price
            and str(row.get("symbol") or "unknown") == symbol
            and str(row.get("duration_minutes") or "unknown") == duration
        ]
        out[f"{bot_id}|{lead}|{price}|{symbol}|{duration}"] = {
            "bot_id": bot_id,
            "lead_bucket": lead,
            "theory_lane": theory_band_for_lead(lead),
            "price_bucket": price,
            "symbol": symbol,
            "duration_minutes": duration,
            **summarise_entry_rows(group_rows),
        }
    return out


def group_by_lead_price(rows: list[dict[str, Any]], bot_id: str) -> dict[str, Any]:
    filtered = [row for row in rows if row.get("bot_id") == bot_id]
    keys = sorted(
        {
            (str(row.get("lead_bucket") or "unknown"), str(row.get("price_bucket") or "unknown"))
            for row in filtered
        }
    )
    out: dict[str, Any] = {}
    for lead, price in keys:
        group_rows = [
            row
            for row in filtered
            if str(row.get("lead_bucket") or "unknown") == lead
            and str(row.get("price_bucket") or "unknown") == price
        ]
        out[f"{lead}|{price}"] = {
            "lead_bucket": lead,
            "theory_lane": theory_band_for_lead(lead),
            "price_bucket": price,
            **summarise_entry_rows(group_rows),
        }
    return out


def recorder_snapshot_grid(
    recorder: sqlite3.Connection,
    *,
    cutoff: datetime,
    max_lead_seconds: int,
) -> dict[str, Any]:
    if not table_exists(recorder, "markets"):
        return {}
    cols = table_columns(recorder, "markets")
    symbol_expr = "symbol" if "symbol" in cols else "NULL AS symbol"
    duration_expr = (
        "duration_minutes" if "duration_minutes" in cols else "NULL AS duration_minutes"
    )
    cutoff_ms = int(cutoff.timestamp() * 1000)
    rows = recorder.execute(
        f"""
        SELECT scan_at_ms, condition_id, question, end_date_iso, {symbol_expr}, {duration_expr},
               yes_price, volume_24h_usd
        FROM markets
        WHERE scan_at_ms >= ?
          AND yes_price IS NOT NULL
          AND end_date_iso IS NOT NULL
        ORDER BY scan_at_ms
        """,
        (cutoff_ms,),
    )
    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        scan_dt = datetime.fromtimestamp(int(row["scan_at_ms"]) / 1000, tz=UTC)
        end_dt = parse_dt(row["end_date_iso"])
        if not end_dt:
            continue
        lead = (end_dt - scan_dt).total_seconds()
        if lead < 0 or lead > max_lead_seconds:
            continue
        cheap = cheap_price_from_yes(row["yes_price"])
        if cheap is None:
            continue
        symbol = str(row["symbol"] or "").upper() or symbol_from_question(row["question"])
        duration = str(row["duration_minutes"] or "unknown")
        lead_label = lead_bucket(lead)
        price_label = price_bucket(cheap)
        key = (lead_label, price_label, symbol, duration)
        if key not in groups:
            groups[key] = {
                "lead_bucket": lead_label,
                "theory_lane": theory_band_for_lead(lead_label),
                "price_bucket": price_label,
                "symbol": symbol,
                "duration_minutes": duration,
                "snapshots": 0,
                "unique_markets": set(),
                "avg_volume_24h_usd_sum": 0.0,
                "avg_volume_24h_usd_n": 0,
            }
        group = groups[key]
        group["snapshots"] += 1
        group["unique_markets"].add(str(row["condition_id"]))
        if row["volume_24h_usd"] is not None:
            group["avg_volume_24h_usd_sum"] += float(row["volume_24h_usd"] or 0)
            group["avg_volume_24h_usd_n"] += 1
    out: dict[str, Any] = {}
    for key, group in sorted(groups.items()):
        n = int(group.pop("avg_volume_24h_usd_n"))
        total = float(group.pop("avg_volume_24h_usd_sum"))
        markets = group.pop("unique_markets")
        group["unique_markets"] = len(markets)
        group["avg_volume_24h_usd"] = round(total / n, 2) if n else None
        out["|".join(key)] = group
    return out


def build_report(
    main: sqlite3.Connection,
    recorder: sqlite3.Connection,
    *,
    cutoff: datetime,
    bot_ids: tuple[str, ...],
    max_recorder_lead_seconds: int,
) -> dict[str, Any]:
    entries = load_bot_orders(main, recorder, bot_ids=bot_ids, cutoff=cutoff)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "cutoff": cutoff.isoformat(),
        "bot_ids": bot_ids,
        "overall_by_bot": {
            bot_id: summarise_entry_rows([row for row in entries if row["bot_id"] == bot_id])
            for bot_id in bot_ids
        },
        "actual_entry_grid": group_entries(entries),
        "lead_price_grid_by_bot": {
            bot_id: group_by_lead_price(entries, bot_id) for bot_id in bot_ids
        },
        "recorder_snapshot_grid": recorder_snapshot_grid(
            recorder,
            cutoff=cutoff,
            max_lead_seconds=max_recorder_lead_seconds,
        ),
        "recent_entries": entries[-25:],
    }


def pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.1f}%"


def money(value: object) -> str:
    return f"${float(value or 0):+.2f}"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Bot G Crypto Recorder Replay Grid",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Window start: `{report['cutoff']}`",
        "",
        "## Interpretation",
        "",
        "This is read-only analysis. Actual Bot G rows come from orders/trades; "
        "recorder rows show observed market availability, not guaranteed fills.",
        "",
        "Theory lanes under review:",
        "",
        "- `45s-60s`: test whether wider `5c-8c` entries behave better.",
        "- `30s-45s`: test whether `3c-5c` is the stronger late-middle lane.",
        "- `<30s`: test whether `1c-3c` is only sensible very close to close.",
        "",
        "## Overall By Bot",
        "",
        "| bot | placed | filled | closed | wins | no-fill | open | P&L | ROI | ex-win ROI | ex-two ROI | fill rate |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bot_id, row in report["overall_by_bot"].items():
        lines.append(
            f"| {bot_id} | {row['placed']} | {row['filled']} | {row['closed']} | "
            f"{row['wins']} | {row['no_fill']} | {row['open']} | "
            f"{money(row['pnl_usd'])} | {pct(row['roi_pct'])} | "
            f"{pct(row['ex_largest_win_roi_pct'])} | "
            f"{pct(row['ex_largest_two_roi_pct'])} | {pct(row['fill_rate_pct'])} |"
        )

    for bot_id, grid in report["lead_price_grid_by_bot"].items():
        lines.extend([
            "",
            f"## {bot_id} Lead x Price Grid",
            "",
            "| lead | theory lane | price | placed | filled | closed | wins | P&L | ROI | ex-two ROI | fill rate |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        if not grid:
            lines.append("| no rows | | | 0 | 0 | 0 | 0 | $0.00 | n/a | n/a | n/a |")
        for row in grid.values():
            lines.append(
                f"| {row['lead_bucket']} | {row['theory_lane']} | {row['price_bucket']} | "
                f"{row['placed']} | {row['filled']} | {row['closed']} | {row['wins']} | "
                f"{money(row['pnl_usd'])} | {pct(row['roi_pct'])} | "
                f"{pct(row['ex_largest_two_roi_pct'])} | {pct(row['fill_rate_pct'])} |"
            )

    lines.extend([
        "",
        "## Actual Entry Grid With Symbol And Window",
        "",
        "| bot | lead | price | symbol | window | placed | filled | closed | wins | P&L | ROI | ex-two ROI |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    if not report["actual_entry_grid"]:
        lines.append("| no rows | | | | | 0 | 0 | 0 | 0 | $0.00 | n/a | n/a |")
    for row in report["actual_entry_grid"].values():
        lines.append(
            f"| {row['bot_id']} | {row['lead_bucket']} | {row['price_bucket']} | "
            f"{row['symbol']} | {row['duration_minutes']} | {row['placed']} | "
            f"{row['filled']} | {row['closed']} | {row['wins']} | "
            f"{money(row['pnl_usd'])} | {pct(row['roi_pct'])} | "
            f"{pct(row['ex_largest_two_roi_pct'])} |"
        )

    lines.extend([
        "",
        "## Recorder Availability Grid",
        "",
        "Recorder availability counts cheap-side market snapshots near close. "
        "These are opportunities to investigate, not proof that Bot G would fill.",
        "",
        "| lead | theory lane | cheap price | symbol | window | snapshots | markets | avg 24h vol |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ])
    if not report["recorder_snapshot_grid"]:
        lines.append("| no rows | | | | | 0 | 0 | n/a |")
    for row in report["recorder_snapshot_grid"].values():
        avg_vol = row["avg_volume_24h_usd"]
        avg_text = "n/a" if avg_vol is None else f"${avg_vol:.0f}"
        lines.append(
            f"| {row['lead_bucket']} | {row['theory_lane']} | {row['price_bucket']} | "
            f"{row['symbol']} | {row['duration_minutes']} | {row['snapshots']} | "
            f"{row['unique_markets']} | {avg_text} |"
        )

    lines.extend([
        "",
        "## Recent Entries",
        "",
        "| bot | placed | symbol | window | lead | price | outcome | status | P&L |",
        "|---|---|---|---:|---:|---|---|---|---:|",
    ])
    if not report["recent_entries"]:
        lines.append("| no rows | | | | | | | | |")
    for row in report["recent_entries"]:
        lines.append(
            f"| {row['bot_id']} | {row['placed_at']} | {row['symbol']} | "
            f"{row['duration_minutes'] or 'unknown'} | {row['lead_bucket']} | "
            f"{row['price_bucket']} | {row['outcome']} | {row['status']} | "
            f"{money(row['pnl_usd'])} |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Bot G crypto recorder replay grid.")
    parser.add_argument("--main-db", type=Path, default=DEFAULT_MAIN_DB)
    parser.add_argument("--recorder-db", type=Path, default=DEFAULT_RECORDER_DB)
    parser.add_argument("--lookback-hours", type=float, default=48.0)
    parser.add_argument(
        "--bot-id",
        action="append",
        dest="bot_ids",
        default=None,
        help="Bot id to include. Repeatable. Defaults to live + paper shadow.",
    )
    parser.add_argument("--max-recorder-lead-seconds", type=int, default=120)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bot_ids = tuple(args.bot_ids or ["bot_g_prime_live", "bot_g_prime"])
    cutoff = datetime.now(UTC) - timedelta(hours=args.lookback_hours)
    main_con = connect_ro(args.main_db)
    recorder_con = connect_ro(args.recorder_db)
    try:
        report = build_report(
            main_con,
            recorder_con,
            cutoff=cutoff,
            bot_ids=bot_ids,
            max_recorder_lead_seconds=args.max_recorder_lead_seconds,
        )
    finally:
        main_con.close()
        recorder_con.close()
    markdown = render_markdown(report)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True))
    if not args.output_md:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
