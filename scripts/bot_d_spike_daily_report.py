"""Daily report for Bot D-Spike paper lane."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

BOT_ID = "bot_d_spike"


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _safe_json(raw: object) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _realised_pnl(con: sqlite3.Connection, *, since: str | None = None) -> dict[str, Any]:
    params: list[object] = [BOT_ID]
    where = "bot_id=?"
    if since is not None:
        where += " AND filled_at >= ?"
        params.append(since)
    rows = con.execute(
        f"""
        SELECT condition_id, token_id, side, price, size, fee_usd, filled_at
        FROM trades
        WHERE {where}
        ORDER BY filled_at, trade_id
        """,
        params,
    ).fetchall()
    buys = 0
    sells = 0
    cost = 0.0
    proceeds = 0.0
    wins = 0
    closed = 0
    by_token: dict[str, dict[str, float]] = {}
    for row in rows:
        token = str(row["token_id"])
        item = by_token.setdefault(token, {"buy_size": 0.0, "sell_size": 0.0, "cost": 0.0, "proceeds": 0.0})
        size = float(row["size"] or 0)
        price = float(row["price"] or 0)
        side = str(row["side"] or "")
        if side.startswith("BUY"):
            buys += 1
            notional = price * size + float(row["fee_usd"] or 0)
            cost += notional
            item["buy_size"] += size
            item["cost"] += notional
        elif side.startswith("SELL"):
            sells += 1
            notional = price * size - float(row["fee_usd"] or 0)
            proceeds += notional
            item["sell_size"] += size
            item["proceeds"] += notional
    for item in by_token.values():
        if item["buy_size"] > 0 and item["sell_size"] >= item["buy_size"] - 1e-8:
            closed += 1
            if item["proceeds"] > item["cost"]:
                wins += 1
    pnl = proceeds - cost
    return {
        "buy_fills": buys,
        "sell_fills": sells,
        "closed_positions": closed,
        "wins": wins,
        "hit_rate_pct": (wins / closed * 100.0) if closed else None,
        "cost_usd": round(cost, 6),
        "proceeds_usd": round(proceeds, 6),
        "realised_pnl_usd": round(pnl, 6),
        "roi_pct": (pnl / cost * 100.0) if cost else None,
    }


def build_report(db_path: Path, *, deployed_at: datetime | None = None) -> dict[str, Any]:
    now = datetime.now(UTC)
    deployed_at = deployed_at or datetime(2026, 5, 7, tzinfo=UTC)
    week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    con = _connect(db_path)
    try:
        order_row = con.execute(
            """
            SELECT
              COUNT(*) AS total_orders,
              SUM(CASE WHEN placed_at >= ? THEN 1 ELSE 0 END) AS today_orders,
              SUM(CASE WHEN status IN ('OPEN','PARTIAL','PAPER_OPEN','MATCHED','live') THEN 1 ELSE 0 END) AS open_orders,
              SUM(CASE WHEN side='BUY' THEN COALESCE(price,0) * COALESCE(size,0) ELSE 0 END) AS buy_notional
            FROM orders
            WHERE bot_id=?
            """,
            (today_start, BOT_ID),
        ).fetchone()
        pos_row = con.execute(
            """
            SELECT
              COUNT(*) AS open_positions,
              COALESCE(SUM(cost_basis_usd), 0) AS open_cost_basis
            FROM positions
            WHERE bot_id=? AND status='OPEN'
            """,
            (BOT_ID,),
        ).fetchone()
        events = []
        city_counts: dict[str, int] = {}
        for row in con.execute(
            """
            SELECT event_type, payload, created_at
            FROM events
            WHERE bot_id=?
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (BOT_ID,),
        ):
            payload = _safe_json(row["payload"])
            city = payload.get("city")
            if city:
                city_counts[str(city)] = city_counts.get(str(city), 0) + 1
            events.append(
                {
                    "event_type": row["event_type"],
                    "created_at": row["created_at"],
                    "city": city,
                    "bucket": payload.get("bucket"),
                    "ask": payload.get("best_ask"),
                    "ttr_h": payload.get("hours_to_resolution"),
                }
            )
        cumulative = _realised_pnl(con)
        weekly = _realised_pnl(con, since=week_start)
    finally:
        con.close()
    closed = int(cumulative["closed_positions"])
    days_elapsed = max(0, (now.date() - deployed_at.date()).days)
    return {
        "generated_at": now.isoformat(),
        "bot_id": BOT_ID,
        "db_path": str(db_path),
        "orders": {
            "total": int(order_row["total_orders"] or 0),
            "today": int(order_row["today_orders"] or 0),
            "open": int(order_row["open_orders"] or 0),
            "buy_notional_usd": round(float(order_row["buy_notional"] or 0), 6),
        },
        "positions": {
            "open": int(pos_row["open_positions"] or 0),
            "open_cost_basis_usd": round(float(pos_row["open_cost_basis"] or 0), 6),
        },
        "pnl": {
            "cumulative": cumulative,
            "weekly": weekly,
        },
        "city_entry_events_recent": city_counts,
        "recent_events": events[:10],
        "kill_gate_distance": {
            "closed_positions": closed,
            "closed_remaining_to_200": max(0, 200 - closed),
            "days_elapsed": days_elapsed,
            "days_remaining_to_90": max(0, 90 - days_elapsed),
            "roi_archive_threshold_pct": 5.0,
            "hit_rate_diagnostic_baseline_pct": 3.6,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    cumulative = report["pnl"]["cumulative"]
    weekly = report["pnl"]["weekly"]
    roi = cumulative["roi_pct"]
    hit = cumulative["hit_rate_pct"]
    lines = [
        "# Bot D-Spike Daily Report",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- Orders today: `{report['orders']['today']}`",
        f"- Open positions: `{report['positions']['open']}`",
        f"- Open cost basis: `${report['positions']['open_cost_basis_usd']:.2f}`",
        f"- Closed positions: `{cumulative['closed_positions']}`",
        f"- Wins: `{cumulative['wins']}`",
        f"- Hit rate: `{hit:.2f}%`" if hit is not None else "- Hit rate: `n/a`",
        f"- Realised P&L: `${cumulative['realised_pnl_usd']:.2f}`",
        f"- ROI: `{roi:.2f}%`" if roi is not None else "- ROI: `n/a`",
        "",
        "## Last 7 Days",
        "",
        f"- Closed positions: `{weekly['closed_positions']}`",
        f"- Wins: `{weekly['wins']}`",
        f"- Realised P&L: `${weekly['realised_pnl_usd']:.2f}`",
        "",
        "## Kill Gate Distance",
        "",
        f"- Closed remaining to 200: `{report['kill_gate_distance']['closed_remaining_to_200']}`",
        f"- Days remaining to 90: `{report['kill_gate_distance']['days_remaining_to_90']}`",
    ]
    if report["recent_events"]:
        lines.extend(["", "## Recent Entries", "", "| created | city | bucket | ask | TTR h |", "|---|---|---|---:|---:|"])
        for event in report["recent_events"]:
            lines.append(
                f"| {event.get('created_at') or ''} | {event.get('city') or ''} | "
                f"{event.get('bucket') or ''} | {event.get('ask') or ''} | {event.get('ttr_h') or ''} |"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/main.db"))
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.db)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    args.out_md.write_text(render_markdown(report))


if __name__ == "__main__":
    main()
