"""Entrypoint for Bot H Maker V2 — Phase 1 recorder mode (paper-only)."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging

from bots.bot_h_maker_v2.capture import run_recorder
from bots.bot_h_maker_v2.config import PAPER_ONLY


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Bot H Maker V2 — Phase 1 recorder")
    p.add_argument("--log-level", default="INFO")
    return p


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not PAPER_ONLY:
        raise SystemExit(
            "Bot H Maker V2 live mode is forbidden without a new ADR after Phase 2 validation"
        )
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_recorder())


if __name__ == "__main__":
    main()
