#!/usr/bin/env python3
"""CLI: run Bot F Hunter against live Polymarket leaderboards + data-api.

Usage:
    python scripts/bot_f_hunter.py --max-wallets 50 --log-level INFO
    python scripts/bot_f_hunter.py --json  # machine-readable output
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bots.bot_f.discovery import run_hunter  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-wallets", type=int, default=None,
                    help="cap on wallets scanned (respect data-api rate limits)")
    ap.add_argument("--leaderboard-sample", type=int, default=200)
    ap.add_argument("--trades-per-wallet", type=int, default=500)
    ap.add_argument("--top-n", type=int, default=40)
    ap.add_argument("--log-level", default="INFO")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db-path", default=None)
    ap.add_argument(
        "--no-filter", action="store_true",
        help="skip filter rejections — useful for Phase-0 calibration runs",
    )
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    result = run_hunter(
        leaderboard_sample=args.leaderboard_sample,
        trades_per_wallet=args.trades_per_wallet,
        top_n=args.top_n,
        db_path=Path(args.db_path) if args.db_path else None,
        max_wallets=args.max_wallets,
        apply_filters=not args.no_filter,
    )
    summary = result.summary()

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
        return 0

    print("=" * 68)
    print(f"  BOT F HUNTER — {summary['run_id']}")
    print("=" * 68)
    print(f"  scanned:  {summary['wallets_scanned']}")
    print(f"  passed:   {summary['wallets_passed_filters']}")
    print(f"  top N:    {len(summary['top_N'])}")

    if summary['top_N']:
        print("\n  Ranking (top 20 shown):")
        print(
            f"    {'#':<3} {'wallet':<14} {'name':<18} {'trades':>6} "
            f"{'roi%':>6} {'P&L':>10} {'notional':>12}  top cats"
        )
        for row in summary['top_N'][:20]:
            name = (row['pseudonym'] or '-')[:16]
            pnl = row['realised_pnl']
            notional = row.get('total_notional', 0) or 1
            eff_roi = 100 * pnl / max(notional, 1)
            cats = ",".join(row['top_categories'][:2])[:30]
            print(
                f"    {row['rank']:<3} {row['wallet']:<14} {name:<18} "
                f"{row['trades']:>6} {eff_roi:>5.1f}% ${pnl:>8,.0f} "
                f"${notional:>10,.0f}  {cats}"
            )
    else:
        print("\n  No wallets passed filters. Try relaxing thresholds or expanding sample.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
