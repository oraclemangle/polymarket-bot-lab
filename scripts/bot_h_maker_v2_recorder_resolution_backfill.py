"""CLI entry point for the Bot H Maker V2 recorder resolution backfill.

Wraps `bots.bot_h_maker_v2.resolution_backfill.run_backfill` for systemd
oneshot use. Read-only against Polymarket Gamma; writes only to
`data/maker_recorder.db`.

Usage:

    python -m scripts.bot_h_maker_v2_recorder_resolution_backfill \
        --max-markets 500 \
        --recheck-throttle-hours 4 \
        --rate-limit-sec 0.5 \
        --log-level INFO
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from bots.bot_h_maker_v2.resolution_backfill import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_RATE_LIMIT_SEC,
    DEFAULT_RECHECK_THROTTLE_SEC,
    run_backfill,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "maker_recorder.db"


def _handle_signal(_signum: int, _frame: object) -> None:
    logging.getLogger(__name__).info("backfill.signal_received exiting")
    sys.exit(0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(
            os.environ.get(
                "BOT_H_MAKER_V2_RECORDER_DB_PATH",
                str(DEFAULT_DB_PATH),
            )
        ),
    )
    parser.add_argument("--max-markets", type=int, default=500)
    parser.add_argument("--recheck-throttle-hours", type=float, default=DEFAULT_RECHECK_THROTTLE_SEC / 3600)
    parser.add_argument("--rate-limit-sec", type=float, default=DEFAULT_RATE_LIMIT_SEC)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    if not args.db_path.exists():
        logging.warning(
            "backfill.db_missing path=%s — recorder hasn't deployed; nothing to do",
            args.db_path,
        )
        return 0

    stats = run_backfill(
        db_path=args.db_path,
        max_markets=args.max_markets,
        recheck_throttle_sec=int(args.recheck_throttle_hours * 3600),
        chunk_size=args.chunk_size,
        rate_limit_sec=args.rate_limit_sec,
    )
    if stats.api_errors and stats.queried == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
