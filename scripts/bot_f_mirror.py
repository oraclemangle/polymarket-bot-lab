#!/usr/bin/env python3
"""CLI: run Bot F Mirror daemon — read-only whale signal logger.

Usage:
    # Standard daemon mode (runs forever, polls every 7s):
    python scripts/bot_f_mirror.py

    # Short calibration run (e.g. 5 cycles then exit):
    python scripts/bot_f_mirror.py --max-cycles 5 --interval 3

    # Summary of captured signals:
    python scripts/bot_f_mirror.py --summary
    python scripts/bot_f_mirror.py --summary --since-hours 24
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

from bots.bot_f.db import get_bot_f_session_factory  # noqa: E402
from bots.bot_f.signal import mirror_summary, run_mirror  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=7, help="seconds between poll cycles")
    ap.add_argument("--top-n", type=int, default=40, help="top-N wallets from latest Hunter run")
    ap.add_argument("--trades-per-poll", type=int, default=20)
    ap.add_argument("--max-cycles", type=int, default=None,
                    help="exit after N cycles (useful for calibration)")
    ap.add_argument("--summary", action="store_true", help="print aggregate signal stats and exit")
    ap.add_argument("--since-hours", type=int, default=None)
    ap.add_argument("--log-level", default="INFO")
    ap.add_argument("--db-path", default=None)
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db = Path(args.db_path) if args.db_path else None

    if args.summary:
        sf = get_bot_f_session_factory(db)
        stats = mirror_summary(sf, since_hours=args.since_hours)
        print(json.dumps(stats, indent=2))
        return 0

    stats = run_mirror(
        poll_interval_s=args.interval,
        top_n=args.top_n,
        trades_per_poll=args.trades_per_poll,
        db_path=db,
        max_cycles=args.max_cycles,
    )
    print(
        f"\ndone — cycles={stats.cycles} new_signals={stats.new_signals} "
        f"polls={stats.polls} dupes={stats.duplicate_skips} errors={stats.errors}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
