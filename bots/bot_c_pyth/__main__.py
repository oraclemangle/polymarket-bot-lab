"""Bot C entrypoint — Pyth ingest + analysis daemon.

Usage:
  python -m bots.bot_c_pyth [--mode {ingest,analysis,both}]
                            [--endpoint both|pro|hermes]
                            [--symbols GOLD,AAPL,...] [--db-path PATH]
                            [--scan-interval-s 60] [--edge-threshold 0.10]

Modes:
  ingest    — Pyth WS ingest only (raw ticks + OHLC bars)
  analysis  — Gamma scan + edge calc against existing Pyth data (no trading)
  both      — run ingest AND analysis concurrently (default)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

# Register Pyth models with SQLAlchemy Base on import.
from core import pyth_models  # noqa: F401
from core.db import init_db
from core.pyth_ingest import run_ingest

from bots.bot_c_pyth.analyst import (
    DEFAULT_EDGE_THRESHOLD,
    DEFAULT_SCAN_INTERVAL_S,
    run_analysis_loop,
)
from bots.bot_c_pyth.config import load_config


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="bots.bot_c_pyth")
    p.add_argument("--mode", choices=["ingest", "analysis", "both"], default="both")
    p.add_argument("--endpoint", choices=["both", "pro", "hermes"], default=None)
    p.add_argument("--symbols", default=None,
                   help="comma-separated symbols; default = all active feeds")
    p.add_argument("--db-path", default=None,
                   help="override SQLite path; default data/bot_c_pyth.db")
    p.add_argument("--scan-interval-s", type=float, default=DEFAULT_SCAN_INTERVAL_S)
    p.add_argument("--edge-threshold", type=float, default=DEFAULT_EDGE_THRESHOLD)
    p.add_argument("--log-level", default="INFO")
    p.add_argument(
        "--enable-executor",
        action="store_true",
        default=False,
        help="Enable the CLOB executor. Paper vs live follows POLYMARKET_ENV.",
    )
    # Deprecated alias, kept so the installed systemd unit's ExecStart still works:
    p.add_argument("--ingest-only", action="store_true", default=False,
                   help="(deprecated) equivalent to --mode ingest")
    return p.parse_args(argv)


async def _main_async(args: argparse.Namespace) -> int:
    if args.ingest_only:
        args.mode = "ingest"

    cfg = load_config(
        endpoint=args.endpoint,
        symbols=args.symbols,
        db_path=args.db_path,
    )
    logging.info(
        "bot_c: mode=%s db=%s endpoint=%s include_pro=%s include_hermes=%s feeds=%d",
        args.mode, cfg.db_path, cfg.endpoint, cfg.include_pro, cfg.include_hermes,
        len(cfg.feeds),
    )

    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = init_db(cfg.db_path)
    from sqlalchemy.orm import sessionmaker
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    # Optional executor — paper/live decided by Bot-C-scoped BOT_C_ENV
    # (cfg.trading_mode) rather than the global POLYMARKET_ENV, so Bot C
    # can paper-trade while Bot A/B are live. ClobWrapper.paper_override
    # forces paper routing regardless of global settings.
    executor = None
    if args.enable_executor and args.mode in ("analysis", "both"):
        from core.clob_v2 import ClobWrapperV2 as ClobWrapper
        from core.config import get_settings
        from core.db import init_db as init_main_db
        from bots.bot_c_pyth.executor import BotCExecutor

        settings = get_settings()
        # Initialise the main (shared) DB so orders/positions tables exist.
        init_main_db()

        bot_c_live = cfg.trading_mode == "live"
        keystore = None
        if bot_c_live:
            # Live Bot C requires real signing; inherit the shared keystore.
            from core.keystore import Keystore
            keystore = Keystore.load_from_settings(settings)

        # paper_override=True when Bot C paper, ensuring we short-circuit
        # to _paper_fill even if POLYMARKET_ENV=live globally.
        clob = ClobWrapper(keystore=keystore, paper_override=not bot_c_live)

        if bot_c_live:
            # Need preflight to be verified for live signing.
            clob.load_preflight_from_db()

        executor = BotCExecutor(clob=clob)
        logging.info(
            "bot_c: executor enabled (bot_c_env=%s, global_polymarket_env=%s)",
            "LIVE" if bot_c_live else "PAPER",
            "LIVE" if settings.is_live() else "PAPER",
        )

    tasks: list[asyncio.Task] = []
    if args.mode in ("ingest", "both"):
        tasks.append(asyncio.create_task(
            run_ingest(
                session_factory=session_factory,
                token=cfg.pyth_token,
                feeds=cfg.feeds,
                include_pro=cfg.include_pro,
                include_hermes=cfg.include_hermes,
            ),
            name="ingest",
        ))
    if args.mode in ("analysis", "both"):
        # SECURITY_AUDIT.md H-2: pick the bar table that matches the active
        # endpoint. "both" prefers Pro (matches pre-fix behaviour); pure
        # Hermes runs read from PythBarHermes.
        from core.pyth_models import PythBarHermes, PythBarPro
        if cfg.endpoint == "hermes":
            bar_model = PythBarHermes
        else:
            bar_model = PythBarPro
        tasks.append(asyncio.create_task(
            run_analysis_loop(
                session_factory=session_factory,
                scan_interval_s=args.scan_interval_s,
                edge_threshold=args.edge_threshold,
                executor=executor,
                bar_model=bar_model,
            ),
            name="analyst",
        ))

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logging.info("bot_c: cancelled, shutting down")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Session 17m (2026-04-18) — ADR-034 archival guard. Default ARCHIVED.
    # Evidence: docs/bot-c-thesis.md §8-9. Pyth Pro ingest silently broken
    # since 2026-04-15 17:37 (HTTP 502 server rejects, never recovered);
    # market universe only 3-10 parseable candidates per scan which caps
    # trade cadence below Phase-1 viability. Flip BOT_C_ARCHIVED=false
    # after a new thesis + evidence of market-universe depth.
    import os as _os
    if _os.environ.get("BOT_C_ARCHIVED", "true").lower() in ("true", "1", "yes", "on"):
        logging.warning(
            "bot_c.daemon.archived — ADR-034 active. Pyth ingest broken + "
            "thin market universe. Set BOT_C_ARCHIVED=false + re-write thesis "
            "per docs/bot-c-thesis.md §9 before starting."
        )
        return 0
    try:
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        logging.info("bot_c: interrupted by user")
        return 130


if __name__ == "__main__":
    sys.exit(main())
