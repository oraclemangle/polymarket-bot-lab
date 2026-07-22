#!/usr/bin/env python3
"""CLI: run Bot D backtest against data/backtest.db using Open-Meteo historical ensemble forecasts."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.backtest_bot_d import run_bot_d_backtest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge-threshold", type=float, default=None,
                    help="override BOT_D_EDGE_THRESHOLD")
    ap.add_argument("--entry-size-usd", type=float, default=10.0)
    ap.add_argument("--decision-hours-before", type=float, default=24.0)
    ap.add_argument("--max-markets", type=int, default=300,
                    help="cap on markets evaluated (respect API rate limits)")
    ap.add_argument("--no-one-bet-per-event", action="store_true",
                    help="disable Bot D's one-bet-per-city/date/temp filter")
    ap.add_argument("--wave-filter", action="store_true",
                    help="annotate/select trades by same-day same-side wave regime")
    ap.add_argument("--wave-min-markets", type=int, default=3,
                    help="minimum same-day same-side events for wave regime")
    ap.add_argument("--isolated-size-factor", type=float, default=0.50,
                    help="size factor for isolated trades when --wave-filter is enabled")
    ap.add_argument("--require-wave", action="store_true",
                    help="drop isolated trades entirely when --wave-filter is enabled")
    ap.add_argument("--show-trades", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    db = Path(args.db_path) if args.db_path else None
    result = run_bot_d_backtest(
        edge_threshold=args.edge_threshold,
        entry_size_usd=args.entry_size_usd,
        decision_hours_before=args.decision_hours_before,
        db_path=db,
        max_markets=args.max_markets,
        one_bet_per_event=not args.no_one_bet_per_event,
        wave_filter=args.wave_filter,
        wave_min_markets=args.wave_min_markets,
        isolated_size_factor=args.isolated_size_factor,
        require_wave=args.require_wave,
    )
    summary = result.summary()

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    print("=" * 64)
    print("  BOT D BACKTEST — Open-Meteo ensemble vs resolved weather markets")
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
                f"    {dt}  {t.city:<12} {t.temp_type:<4} "
                f"{mark}${abs(t.pnl_usd):>6.2f}  mkt={t.market_prob:.3f} "
                f"model={t.model_prob:.3f} edge={t.net_edge:+.3f}  q={q}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
