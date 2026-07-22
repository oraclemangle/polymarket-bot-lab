#!/usr/bin/env python3
"""CLI: run Bot C backtest against data/backtest.db using Pyth historical prices."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.backtest_bot_c import run_bot_c_backtest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge-threshold", type=float, default=0.10)
    ap.add_argument("--entry-size-usd", type=float, default=10.0)
    ap.add_argument("--decision-hours-before", type=float, default=24.0)
    ap.add_argument("--vol-lookback-days", type=int, default=30)
    ap.add_argument("--max-markets", type=int, default=500,
                    help="cap on markets evaluated (respect API rate limits)")
    ap.add_argument("--show-trades", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    db = Path(args.db_path) if args.db_path else None
    result = run_bot_c_backtest(
        edge_threshold=args.edge_threshold,
        entry_size_usd=args.entry_size_usd,
        decision_hours_before=args.decision_hours_before,
        vol_lookback_days=args.vol_lookback_days,
        db_path=db,
        max_markets=args.max_markets,
    )
    summary = result.summary()

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print("=" * 64)
    print("  BOT C BACKTEST — Pyth GBM vs resolved Polymarket markets")
    print("=" * 64)
    for k, v in summary.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")
    if args.show_trades and result.trades:
        print("\n  Sample trades:")
        for t in sorted(result.trades, key=lambda x: x.entry_ts)[: args.show_trades]:
            dt = datetime.fromtimestamp(t.entry_ts, tz=timezone.utc).strftime("%Y-%m-%d")
            mark = "+" if t.pnl_usd > 0 else "-"
            q = t.question[:48]
            print(
                f"    {dt}  {t.symbol:<6} {t.direction:<7} "
                f"{mark}${abs(t.pnl_usd):>6.2f}  mkt={t.market_prob:.3f} "
                f"model={t.model_prob:.3f} edge={t.net_edge:+.3f}  q={q}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
