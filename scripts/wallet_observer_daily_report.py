#!/usr/bin/env python3
"""Daily report for the wallet observer.

Reads the wallet_observer SQLite DB and produces:
- Markdown summary of fills observed in the last 24h / 7d
- Per-tier breakdown (Tier A vs Tier B activity)
- Per-wallet leaderboard (most-active observed wallets)
- Side distribution (BUY vs SELL frequency)
- Liveness check (last fill timestamp, run history)

Read-only against `data/wallet_observer.db`. Outputs to MD + JSON.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bots.wallet_observer import config as cfg


def fmt_dt(ts: int | None) -> str:
    if ts is None or ts == 0:
        return "n/a"
    return datetime.fromtimestamp(int(ts), UTC).isoformat()


def render(con: sqlite3.Connection) -> tuple[str, dict]:
    now = int(datetime.now(UTC).timestamp())
    since_24h = now - 86400
    since_7d = now - 7 * 86400

    def scalar(sql, args=()):
        cur = con.execute(sql, args)
        row = cur.fetchone()
        return row[0] if row else None

    total_fills = scalar("SELECT COUNT(*) FROM wallet_observed_fills") or 0
    fills_24h = scalar(
        "SELECT COUNT(*) FROM wallet_observed_fills WHERE block_ts >= ?", (since_24h,)
    ) or 0
    fills_7d = scalar(
        "SELECT COUNT(*) FROM wallet_observed_fills WHERE block_ts >= ?", (since_7d,)
    ) or 0
    distinct_wallets_24h = scalar(
        "SELECT COUNT(DISTINCT observed_address) FROM wallet_observed_fills WHERE block_ts >= ?",
        (since_24h,),
    ) or 0
    last_fill_ts = scalar("SELECT MAX(NULLIF(block_ts, 0)) FROM wallet_observed_fills")
    first_fill_ts = scalar("SELECT MIN(NULLIF(block_ts, 0)) FROM wallet_observed_fills")

    # Per-tier breakdown
    tier_24h = con.execute(
        """
        SELECT tier, COUNT(*) n_fills,
               COUNT(DISTINCT observed_address) n_wallets,
               SUM(CASE WHEN side='BUY' THEN 1 ELSE 0 END) n_buys,
               SUM(CASE WHEN side='SELL' THEN 1 ELSE 0 END) n_sells
        FROM wallet_observed_fills
        WHERE block_ts >= ? GROUP BY tier ORDER BY n_fills DESC
        """, (since_24h,),
    ).fetchall()

    # Top wallets last 24h
    top_24h = con.execute(
        """
        SELECT observed_address, user_name, tier, COUNT(*) n_fills,
               AVG(price) avg_price,
               SUM(CASE WHEN side='BUY' THEN 1 ELSE 0 END) n_buys,
               SUM(CASE WHEN side='SELL' THEN 1 ELSE 0 END) n_sells
        FROM wallet_observed_fills WHERE block_ts >= ?
        GROUP BY observed_address ORDER BY n_fills DESC LIMIT 25
        """, (since_24h,),
    ).fetchall()

    # Side distribution last 24h
    side_24h = con.execute(
        """
        SELECT side, COUNT(*) n,
               AVG(price) avg_price,
               SUM(CAST(maker_amount_filled AS REAL)) sum_maker,
               SUM(CAST(taker_amount_filled AS REAL)) sum_taker
        FROM wallet_observed_fills WHERE block_ts >= ?
        GROUP BY side ORDER BY n DESC
        """, (since_24h,),
    ).fetchall()

    # Run history
    runs = con.execute(
        """
        SELECT run_id, started_at, stopped_at, n_fills, n_polls, last_block
        FROM observer_runs ORDER BY run_id DESC LIMIT 5
        """
    ).fetchall()

    # State
    state = con.execute(
        "SELECT exchange, last_block, last_updated FROM collector_state"
    ).fetchall()

    # ---------- MD render ----------
    lines = []
    lines.append("# Wallet Observer Daily Report")
    lines.append("")
    lines.append(f"Generated: `{datetime.now(UTC).isoformat()}`")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("|---|---:|")
    lines.append(f"| Total fills observed (all time) | `{total_fills:,}` |")
    lines.append(f"| Fills in last 24h | `{fills_24h:,}` |")
    lines.append(f"| Fills in last 7d | `{fills_7d:,}` |")
    lines.append(f"| Distinct wallets active 24h | `{distinct_wallets_24h}/245` |")
    lines.append(f"| First fill recorded | `{fmt_dt(first_fill_ts)}` |")
    lines.append(f"| Last fill recorded | `{fmt_dt(last_fill_ts)}` |")
    lines.append("")

    lines.append("## Per-tier activity (last 24h)")
    lines.append("")
    lines.append("| tier | fills | distinct wallets | BUYs | SELLs |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in tier_24h:
        lines.append(f"| `{r[0]}` | {r[1]} | {r[2]} | {r[3]} | {r[4]} |")
    lines.append("")

    lines.append("## Top 25 most active observed wallets (last 24h)")
    lines.append("")
    lines.append("| wallet | user | tier | fills | avg_price | BUYs | SELLs |")
    lines.append("|---|---|---|---:|---:|---:|---:|")
    for r in top_24h:
        addr, user, tier, n_fills, avg_price, n_buys, n_sells = r
        avg_price_s = f"${avg_price:.3f}" if avg_price is not None else "n/a"
        lines.append(
            f"| `{addr[:14]}…` | {user or '(unnamed)'} | {tier[:1]} | "
            f"{n_fills} | {avg_price_s} | {n_buys} | {n_sells} |"
        )
    lines.append("")

    lines.append("## Side distribution (last 24h)")
    lines.append("")
    lines.append("| side | count | avg_price |")
    lines.append("|---|---:|---:|")
    for r in side_24h:
        side, n, avg_price, _, _ = r
        avg_price_s = f"${avg_price:.3f}" if avg_price is not None else "n/a"
        lines.append(f"| `{side or 'unknown'}` | {n} | {avg_price_s} |")
    lines.append("")

    lines.append("## Collector state")
    lines.append("")
    lines.append("| exchange | last_block | last_updated |")
    lines.append("|---|---:|---|")
    for r in state:
        lines.append(f"| `{r[0]}` | {r[1]:,} | {fmt_dt(r[2])} |")
    lines.append("")

    lines.append("## Recent service runs")
    lines.append("")
    lines.append("| run_id | started | stopped | fills | polls | last_block |")
    lines.append("|---:|---|---|---:|---:|---:|")
    for r in runs:
        run_id, started, stopped, n_fills, n_polls, last_block = r
        lines.append(
            f"| {run_id} | {fmt_dt(started)} | {fmt_dt(stopped)} | "
            f"{n_fills} | {n_polls} | {last_block} |"
        )
    lines.append("")

    lines.append("## Health")
    lines.append("")
    if last_fill_ts is None:
        lines.append("- ⚠ no fills recorded yet")
    else:
        age = now - int(last_fill_ts)
        if age < 600:
            lines.append(f"- ✓ last fill {age}s ago — collector is fresh")
        elif age < 3600:
            lines.append(f"- ⚠ last fill {age // 60}min ago — investigate")
        else:
            lines.append(f"- ❌ last fill {age // 60}min ago — likely stalled")
    lines.append("")

    md = "\n".join(lines) + "\n"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "headline": {
            "total_fills": total_fills,
            "fills_24h": fills_24h,
            "fills_7d": fills_7d,
            "distinct_wallets_24h": distinct_wallets_24h,
            "last_fill_ts": last_fill_ts,
            "first_fill_ts": first_fill_ts,
        },
        "tier_24h": [
            dict(zip(["tier", "n_fills", "n_wallets", "n_buys", "n_sells"], r))
            for r in tier_24h
        ],
        "top_wallets_24h": [
            dict(zip(
                ["wallet", "user_name", "tier", "n_fills",
                 "avg_price", "n_buys", "n_sells"], r))
            for r in top_24h
        ],
        "side_distribution_24h": [
            dict(zip(["side", "n", "avg_price"], r[:3])) for r in side_24h
        ],
        "collector_state": [
            dict(zip(["exchange", "last_block", "last_updated"], r))
            for r in state
        ],
        "runs": [
            dict(zip(
                ["run_id", "started_at", "stopped_at",
                 "n_fills", "n_polls", "last_block"], r))
            for r in runs
        ],
    }
    return md, payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(cfg.WALLET_OBSERVER_DB))
    parser.add_argument(
        "--out-md",
        default=str(Path(cfg.WALLET_OBSERVER_DB).parent / "reports" / "wallet_observer" / "latest.md"),
    )
    parser.add_argument(
        "--out-json",
        default=str(Path(cfg.WALLET_OBSERVER_DB).parent / "reports" / "wallet_observer" / "latest.json"),
    )
    args = parser.parse_args()

    con = sqlite3.connect(args.db, timeout=10)
    md, payload = render(con)
    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md)
    out_json.write_text(json.dumps(payload, indent=2, default=str))
    print(f"wrote {out_md}")
    print(f"wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
