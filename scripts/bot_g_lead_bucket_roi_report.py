#!/usr/bin/env python3
"""Read-only Bot G lead-bucket ROI report.

Groups Bot G orders by execution mode, fresh lead bucket, submitted-limit
bucket, symbol, and side token. It does not place orders or mutate the DB.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.bot_g_crypto_replay_grid import (
    connect_ro,
    load_bot_orders,
    price_bucket as broad_price_bucket,
)

DEFAULT_MAIN_DB = Path("data/main.db")
DEFAULT_RECORDER_DB = Path("data/bot_e_recorder.db")
DEFAULT_BOT_IDS = (
    "bot_g_prime_live",
    "bot_g_prime",
    "bot_g_prime_shadow",
    "bot_g_prime_high_tail",
    "bot_g_prime_late_cheap",
    "bot_g_prime_take_profit",
)


def limit_price_bucket(price: object) -> str:
    try:
        p = float(price)
    except (TypeError, ValueError):
        return "unknown"
    if p < 0.01:
        return "<1c"
    if p < 0.025:
        return "1c-2.5c"
    if p < 0.035:
        return "2.5c-3.5c"
    if p < 0.045:
        return "3.5c-4.5c"
    if p < 0.055:
        return "4.5c-5.5c"
    if p < 0.065:
        return "5.5c-6.5c"
    if p <= 0.08:
        return "6.5c-8c"
    return ">8c"


def report_lead_bucket(seconds: object) -> str:
    try:
        lead = float(seconds)
    except (TypeError, ValueError):
        return "unknown"
    if lead < 0:
        return "after_close"
    if lead < 30:
        return "<30s"
    if lead < 45:
        return "30s-45s"
    if lead < 60:
        return "45s-60s"
    return ">=60s"


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    phat = wins / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return ((centre - margin) / denom, (centre + margin) / denom)


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


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n_orders = len(rows)
    n_fills = sum(1 for row in rows if row.get("filled"))
    resolved = [row for row in rows if row.get("closed")]
    won = sum(1 for row in resolved if row.get("win"))
    lost = len(resolved) - won
    cost = sum(float(row.get("buy_notional") or 0) for row in resolved)
    pnl = sum(float(row.get("pnl_usd") or 0) for row in resolved)
    ci_lo, ci_hi = wilson_interval(won, len(resolved))
    return {
        "n_orders": n_orders,
        "n_fills": n_fills,
        "fill_rate_pct": round(n_fills / n_orders * 100, 2) if n_orders else None,
        "n_resolved": len(resolved),
        "won": won,
        "lost": lost,
        "cost_basis_usd": round(cost, 4),
        "realized_pnl_usd": round(pnl, 4),
        "roi_pct": round(pnl / cost * 100, 2) if cost else None,
        "roi_ex_largest_pct": trim_roi(rows, 1),
        "roi_ex_largest_two_pct": trim_roi(rows, 2),
        "win_rate_pct": round(won / len(resolved) * 100, 2) if resolved else None,
        "wilson_ci_lo_pct": round(ci_lo * 100, 2) if ci_lo is not None else None,
        "wilson_ci_hi_pct": round(ci_hi * 100, 2) if ci_hi is not None else None,
    }


def enriched_rows(
    main: sqlite3.Connection,
    recorder: sqlite3.Connection,
    *,
    bot_ids: tuple[str, ...],
    cutoff: datetime,
) -> list[dict[str, Any]]:
    rows = load_bot_orders(main, recorder, bot_ids=bot_ids, cutoff=cutoff)
    for row in rows:
        status = str(row.get("status") or "").upper()
        bot_id = str(row.get("bot_id") or "")
        row["execution_mode"] = str(row.get("execution_mode") or "") or (
            "paper"
            if status.startswith("PAPER") or bot_id != "bot_g_prime_live"
            else "live"
        )
        row["lead_bucket"] = report_lead_bucket(row.get("lead_seconds"))
        row["price_bucket"] = limit_price_bucket(row.get("limit_price"))
        row["broad_price_bucket"] = broad_price_bucket(row.get("limit_price"))
        row["side_token"] = str(row.get("side_token") or "UNKNOWN")
    return rows


def build_report(
    main: sqlite3.Connection,
    recorder: sqlite3.Connection,
    *,
    cutoff: datetime,
    bot_ids: tuple[str, ...],
) -> dict[str, Any]:
    rows = enriched_rows(main, recorder, bot_ids=bot_ids, cutoff=cutoff)
    groups: dict[str, dict[str, Any]] = {}
    keys = sorted(
        {
            (
                str(row.get("execution_mode") or "unknown"),
                str(row.get("lead_bucket") or "unknown"),
                str(row.get("price_bucket") or "unknown"),
                str(row.get("symbol") or "unknown"),
                str(row.get("side_token") or "unknown"),
                str(row.get("bot_id") or "unknown"),
            )
            for row in rows
        }
    )
    for execution_mode, lead, price, symbol, side, bot_id in keys:
        group_rows = [
            row
            for row in rows
            if str(row.get("execution_mode") or "unknown") == execution_mode
            and str(row.get("lead_bucket") or "unknown") == lead
            and str(row.get("price_bucket") or "unknown") == price
            and str(row.get("symbol") or "unknown") == symbol
            and str(row.get("side_token") or "unknown") == side
            and str(row.get("bot_id") or "unknown") == bot_id
        ]
        groups["|".join((execution_mode, lead, price, symbol, side, bot_id))] = {
            "execution_mode": execution_mode,
            "lead_bucket": lead,
            "price_bucket": price,
            "symbol": symbol,
            "side_token": side,
            "bot_id": bot_id,
            **summarise(group_rows),
        }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "cutoff": cutoff.isoformat(),
        "bot_ids": list(bot_ids),
        "overall": {bot_id: summarise([row for row in rows if row["bot_id"] == bot_id]) for bot_id in bot_ids},
        "groups": groups,
    }


def pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.1f}%"


def money(value: object) -> str:
    return f"${float(value or 0):+.2f}"


def render_markdown(report: dict[str, Any], *, top_n: int = 80) -> str:
    lines = [
        "# Bot G Lead-Bucket ROI Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Window start: `{report['cutoff']}`",
        "",
        "## Overall",
        "",
        "| bot | orders | fills | resolved | won | lost | P&L | ROI | ex-win | ex-two | win rate | Wilson 95% |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for bot_id, row in report["overall"].items():
        lines.append(
            f"| {bot_id} | {row['n_orders']} | {row['n_fills']} | {row['n_resolved']} | "
            f"{row['won']} | {row['lost']} | {money(row['realized_pnl_usd'])} | "
            f"{pct(row['roi_pct'])} | {pct(row['roi_ex_largest_pct'])} | "
            f"{pct(row['roi_ex_largest_two_pct'])} | {pct(row['win_rate_pct'])} | "
            f"{pct(row['wilson_ci_lo_pct'])}-{pct(row['wilson_ci_hi_pct'])} |"
        )
    rows = sorted(
        report["groups"].values(),
        key=lambda row: (row["execution_mode"], row["bot_id"], row["lead_bucket"], row["price_bucket"], row["symbol"]),
    )[:top_n]
    lines.extend([
        "",
        "## Splits",
        "",
        "| mode | bot | lead | price | symbol | side | orders | fills | resolved | won | P&L | ROI | ex-two | Wilson 95% |",
        "|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    if not rows:
        lines.append("| no rows | | | | | | 0 | 0 | 0 | 0 | $0.00 | n/a | n/a | n/a |")
    for row in rows:
        lines.append(
            f"| {row['execution_mode']} | {row['bot_id']} | {row['lead_bucket']} | "
            f"{row['price_bucket']} | {row['symbol']} | {row['side_token']} | "
            f"{row['n_orders']} | {row['n_fills']} | {row['n_resolved']} | {row['won']} | "
            f"{money(row['realized_pnl_usd'])} | {pct(row['roi_pct'])} | "
            f"{pct(row['roi_ex_largest_two_pct'])} | "
            f"{pct(row['wilson_ci_lo_pct'])}-{pct(row['wilson_ci_hi_pct'])} |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Bot G lead-bucket ROI report.")
    parser.add_argument("--db", type=Path, default=DEFAULT_MAIN_DB)
    parser.add_argument("--recorder-db", type=Path, default=DEFAULT_RECORDER_DB)
    parser.add_argument("--lookback-hours", type=float, default=72.0)
    parser.add_argument("--bot-id", action="append", dest="bot_ids")
    parser.add_argument("--out-json", "--output-json", dest="output_json", type=Path)
    parser.add_argument("--out-md", "--output-md", dest="output_md", type=Path)
    parser.add_argument("--top-n", type=int, default=80)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bot_ids = tuple(args.bot_ids or DEFAULT_BOT_IDS)
    cutoff = datetime.now(UTC) - timedelta(hours=args.lookback_hours)
    main_con = connect_ro(args.db)
    recorder_con = connect_ro(args.recorder_db)
    try:
        report = build_report(main_con, recorder_con, cutoff=cutoff, bot_ids=bot_ids)
    finally:
        main_con.close()
        recorder_con.close()
    markdown = render_markdown(report, top_n=args.top_n)
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
