"""Notify daemon — long-polls Telegram for /status and /unhalt.

Handles unhalt by delegating to a shared Watchdog instance.
"""

from __future__ import annotations

import logging
import signal
import time
from decimal import Decimal

from bots.bot_a.executor import BotAExecutor

# Bot B excluded from public export; see docs/bot-b-reference.md
from core.clob_v2 import ClobWrapperV2 as ClobWrapper
from core.config import get_settings
from core.notify import Listener, default_client
from core.portfolio import Portfolio, get_usd_to_gbp_rate
from core.watchdog import Watchdog, WatchdogConfig

log = logging.getLogger("notify_daemon")

_running = True


def _handle_signal(signum, _):
    global _running
    _running = False


def main() -> int:
    logging.basicConfig(
        level=get_settings().polymarket_log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    settings = get_settings()
    gbp_to_usd = Decimal("1") / get_usd_to_gbp_rate()

    # SECURITY_AUDIT.md M-1: in live mode, ClobWrapper needs a keystore to
    # sign cancellation requests. Without it, /unhalt commands from Telegram
    # would clear the halt flag but fail to actually cancel orders on the
    # CLOB — exposure remains.
    keystore = None
    if settings.is_live():
        try:
            from core.keystore import Keystore
            keystore = Keystore.load_from_settings(settings)
            # Codex A-16: mask full wallet in logs by default. Emit a
            # prefix/suffix so the operator can still cross-reference
            # without leaking the full address into systemd journal.
            _addr = keystore.address
            log.info(
                "notify_daemon.keystore_loaded address=%s…%s",
                _addr[:6], _addr[-4:],
            )
        except Exception as e:
            log.error(
                "notify_daemon.keystore_failed: %s — cancellation will not "
                "work in live mode until keystore is available",
                e,
            )

    clob = ClobWrapper(keystore=keystore)
    if settings.is_live() and keystore is not None:
        clob.load_preflight_from_db()
    exec_a = BotAExecutor(clob=clob)

    def dispatch_cancel(bot_id: str) -> int:
        if bot_id == "bot_a":
            return exec_a.cancel_all()
        return 0

    def unhalt(bot_id: str, reason: str) -> bool:
        cfg = WatchdogConfig(
            bot_b_initial_usd=settings.bot_b_bankroll_gbp * gbp_to_usd,
        )
        watchdog = Watchdog(cfg, portfolio=Portfolio(), cancel_all=dispatch_cancel)
        return watchdog.unhalt(bot_id, reason)

    listener = Listener(client=default_client(), unhalt_handler=unhalt)
    log.info("notify.daemon.start")

    while _running:
        try:
            listener.poll_once(timeout=25)
        except Exception as e:
            log.warning("notify.daemon.poll_fail", extra={"error": str(e)})
            time.sleep(5)
    log.info("notify.daemon.stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
