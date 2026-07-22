"""Bot A daemon — scheduled tick loop.

Invoked by `python -m bots.bot_a` (systemd unit calls this).

Loop:
  1. Sleep until next tick (default 5 min).
  2. Load preflight flag from DB (so `preflight_check.py --commit` unblocks live).
  3. Refresh markets + books via shared ingestion modules.
  4. Run `lifecycle.tick()`.
  5. Snapshot daily PnL at UTC midnight boundary.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from datetime import UTC, datetime
from decimal import Decimal

from bots.bot_a.config import (
    BOT_ID,
    MAX_YES_ENTRY_PRICE,
    MIN_24H_VOLUME_USD,
    REPOST_STALE_HOURS,
    TARGET_CATEGORIES,
)
from bots.bot_a.executor import BotAExecutor
from bots.bot_a.lifecycle import tick
from core.clob_v2 import ClobWrapperV2 as ClobWrapper
from core.config import get_settings
from core.ingest import BookSnapshotter, Scraper, build_mark_prices, latest_yes_price_fn
from core.keystore import Keystore, KeystoreError
from core.portfolio import Portfolio, get_usd_to_gbp_rate

log = logging.getLogger("bot_a")

TICK_INTERVAL_SECONDS = int(os.environ.get("BOT_A_TICK_INTERVAL", "300"))
_running = True


def _handle_signal(signum, _):
    global _running
    log.info("bot_a.daemon.signal", extra={"signum": signum})
    _running = False


def _load_keystore_if_live() -> Keystore | None:
    s = get_settings()
    if not s.is_live():
        return None
    try:
        return Keystore.load(s.polymarket_keystore_path, s.polymarket_passphrase_path)
    except KeystoreError as e:
        log.error("bot_a.daemon.keystore_fail", extra={"error": str(e)})
        raise


def main() -> int:
    logging.basicConfig(
        level=get_settings().polymarket_log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Session 17m (2026-04-18) — ADR-033 archival guard. Default ARCHIVED.
    # Bot A walk-forward (docs/bot-a-walkforward-wangzj-2026-04-18.md)
    # showed -$13,614 PnL on 12,521 trades despite 93.7% hit rate. The bot
    # is kept in tree so restoration is a single revert; this guard
    # prevents accidental systemd re-enable from placing orders.
    archived = os.environ.get("BOT_A_ARCHIVED", "true").lower() in ("true", "1", "yes", "on")
    if archived:
        log.warning(
            "bot_a.daemon.archived — ADR-033 active. Set BOT_A_ARCHIVED=false "
            "AND re-run the walk-forward with positive net PnL before starting."
        )
        return 0

    settings = get_settings()
    log.info("bot_a.daemon.start", extra={"env": settings.polymarket_env.value})

    ks = _load_keystore_if_live()
    try:
        clob = ClobWrapper(keystore=ks)
        preflight_ok = clob.load_preflight_from_db()
        log.info("bot_a.daemon.preflight", extra={"ok": preflight_ok})

        executor = BotAExecutor(clob=clob)
        portfolio = Portfolio()
        last_snapshot_date = None

        while _running:
            gbp_to_usd = Decimal("1") / get_usd_to_gbp_rate()
            bankroll_gbp = settings.bot_a_bankroll_gbp
            bankroll_usd = bankroll_gbp * gbp_to_usd

            # Keep shared infra warm — cheap refresh.
            try:
                Scraper().run_once(max_pages=20)
                # Narrow the book-snapshot set to markets that could plausibly
                # pass Bot A's yes-price filter (with headroom to catch
                # markets that may drop into range). Without this the
                # snapshotter iterates all ~10k active tokens per tick.
                snapshotter = BookSnapshotter()
                targets = snapshotter.tokens_for_bot_a(
                    max_yes_price=MAX_YES_ENTRY_PRICE * Decimal("3"),
                    min_volume_usd=MIN_24H_VOLUME_USD,
                    categories=TARGET_CATEGORIES,
                )
                snapshotter.run_once(token_ids=targets)
            except Exception as e:
                log.warning("bot_a.daemon.ingest_fail", extra={"error": str(e)})

            # Volume map: derived from markets ingested; placeholder until
            # the scraper stores volume_24h. For now filters rely on the
            # enriched payload; Bot A skips when volume is 0.
            try:
                stale = executor.cancel_stale_orders(REPOST_STALE_HOURS)
                if stale:
                    log.info("bot_a.daemon.stale_cancelled", extra={"count": stale})
            except Exception as e:
                log.warning("bot_a.daemon.stale_cancel_fail", extra={"error": str(e)})

            # Reconcile fills BEFORE tick so exposure caps use fresh truth.
            try:
                if settings.is_live():
                    portfolio.reconcile_live_fills(clob, BOT_ID)
                else:
                    portfolio.simulate_paper_fills(BOT_ID)
            except Exception as e:
                log.warning("bot_a.daemon.reconcile_fail", extra={"error": str(e)})

            result = tick(
                executor,
                bankroll_usd=bankroll_usd,
                volume_map={},
                current_yes_price_fn=latest_yes_price_fn(),
            )
            log.info(
                "bot_a.daemon.tick", extra={
                    "placed": result.entries_placed,
                    "skipped": result.entries_skipped,
                    "exits": result.exits_placed,
                }
            )

            today = datetime.now(UTC).date()
            if last_snapshot_date != today:
                try:
                    portfolio.snapshot_daily(
                        BOT_ID,
                        bankroll_usd,
                        mark_prices=build_mark_prices(BOT_ID),
                        on_date=today,
                    )
                    last_snapshot_date = today
                except Exception as e:
                    log.warning("bot_a.daemon.snapshot_fail", extra={"error": str(e)})

            for _ in range(TICK_INTERVAL_SECONDS):
                if not _running:
                    break
                time.sleep(1)
    finally:
        if ks is not None:
            ks.close()
    log.info("bot_a.daemon.stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
