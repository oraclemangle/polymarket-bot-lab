"""Entrypoint for Bot K — Sports Taker (market-open) paper lane."""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from bots.bot_k_sports_taker import config as cfg
from bots.bot_k_sports_taker.executor import run_once
from core.db import init_db

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Bot K — Sports Taker paper lane")
    p.add_argument("--recorder-db", type=Path, default=cfg.DEFAULT_RECORDER_DB)
    p.add_argument("--once", action="store_true", help="run one scan and exit")
    p.add_argument("--poll-interval-s", type=float, default=cfg.POLL_INTERVAL_S)
    p.add_argument("--log-level", default="INFO")
    return p


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not cfg.PAPER_ONLY:
        raise SystemExit("Bot K live mode is forbidden without a new ADR")

    init_db()

    if args.once:
        result = run_once(recorder_db=args.recorder_db)
        log.info("bot_k.once_done scanned=%d recorded=%d", result["scanned"], result["recorded"])
        return

    log.info("bot_k.start poll_interval=%.1fs", args.poll_interval_s)
    while True:
        try:
            result = run_once(recorder_db=args.recorder_db)
            if result.get("recorded", 0) > 0:
                log.info(
                    "bot_k.poll scanned=%d recorded=%d",
                    result["scanned"],
                    result["recorded"],
                )
        except Exception:
            log.exception("bot_k.poll_error")
        time.sleep(args.poll_interval_s)


if __name__ == "__main__":
    raise SystemExit(main())
