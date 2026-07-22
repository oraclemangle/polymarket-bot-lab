"""CLI entry point for the shared crypto recorder.

Usage:
    python -m bots.bot_e_recorder

Runs the capture loop indefinitely. Stop with Ctrl-C (SIGINT) or SIGTERM.

All configuration via env vars (see `config.py`). Refuses to start if
`config.validate()` returns any errors.

ZERO ORDER PLACEMENT. This module is read-only w.r.t. Polymarket.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys

from bots.bot_e_recorder import config
from bots.bot_e_recorder.capture import run_capture
from core.sd_notify import notify_ready, notify_stopping

log = logging.getLogger(__name__)


def main() -> int:
    errors = config.validate()
    if errors:
        for e in errors:
            sys.stderr.write(f"config error: {e}\n")
        return 2

    logging.basicConfig(
        level=getattr(logging, config.BOT_E_LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Session 17f audit 2026-04-17: signal readiness to systemd once the
    # event loop is starting. The heartbeat_loop pings WATCHDOG=1 thereafter.
    notify_ready()

    loop = asyncio.new_event_loop()
    main_task = loop.create_task(run_capture())

    def _stop(*_args):
        log.info("recorder.signal_received stopping")
        main_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass  # Windows / unsupported

    try:
        loop.run_until_complete(main_task)
    except asyncio.CancelledError:
        pass
    finally:
        notify_stopping()
        loop.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
