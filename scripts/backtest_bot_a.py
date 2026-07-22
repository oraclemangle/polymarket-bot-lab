#!/usr/bin/env python3
"""CLI: run Bot A backtest against data/backtest.db. Prints a text report."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.backtest_bot_a import run_bot_a_backtest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90, help="lookback window ending now")
    ap.add_argument("--min-volume", type=float, default=500.0)
    ap.add_argument("--show-trades", type=int, default=10, help="how many sample trades to print")
    ap.add_argument("--json", action="store_true", help="output JSON only")
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    db_path = Path(args.db_path) if args.db_path else None

    result = run_bot_a_backtest(
        start=start, end=end, min_volume_usd=args.min_volume, db_path=db_path
    )
    summary = result.summary()
    summary["window_days"] = args.days

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print("=" * 64)
    print(f"  BOT A BACKTEST — last {args.days} days")
    print("=" * 64)
    for k, v in summary.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")
    if args.show_trades and result.trades:
        print("\n  Sample trades (chronological):")
        trades = sorted(result.trades, key=lambda t: t.entry_ts)
        for t in trades[: args.show_trades]:
            dt = datetime.fromtimestamp(t.entry_ts, tz=timezone.utc).strftime("%Y-%m-%d")
            mark = "+" if t.pnl_usd > 0 else "-"
            q = t.question[:48]
            print(
                f"    {dt}  {mark}${abs(t.pnl_usd):>6.2f}  "
                f"yes={t.entry_yes_price:.3f} shares={t.size_shares:>6.1f}  "
                f"exit={t.exit_reason:<18} q={q}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
