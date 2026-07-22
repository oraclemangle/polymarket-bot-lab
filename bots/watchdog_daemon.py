"""Watchdog daemon — runs core.watchdog.Watchdog every minute.

When a bot's kill-switch fires, `cancel_all` on that bot is dispatched via
the appropriate executor; on any non-OK check, a Telegram alert is sent.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from collections.abc import Mapping
from decimal import Decimal

# Bot B excluded from public export; see docs/bot-b-reference.md
from core.clob_v2 import ClobWrapperV2 as ClobWrapper
from core.config import get_settings
from core.keystore import Keystore, KeystoreError
from core.notify import default_client
from core.portfolio import Portfolio, get_usd_to_gbp_rate
from core.watchdog import (
    LOCAL_WATCHDOG_EXCLUDED_BOTS,
    Watchdog,
    WatchdogConfig,
)

log = logging.getLogger("watchdog")

TICK_INTERVAL_SECONDS = 60
_running = True


def _env_keys_for_bot(bot_id: str) -> tuple[str, ...]:
    """Return env vars that declare a bot's trading mode.

    Some deployed services use variant-specific ids (`bot_f_mirror`,
    `bot_g_prime`) while their mode env is shared at the
    strategy family level. Keep this mapping explicit so watchdog cancel
    routing cannot silently fall back to global POLYMARKET_ENV.
    """
    if bot_id == "bot_f_mirror":
        return ("BOT_F_MIRROR_ENV", "BOT_F_ENV")
    if bot_id == "bot_d_live_probe":
        return ("BOT_D_LIVE_PROBE_ENV",)
    if bot_id == "bot_d_maker_live_probe":
        return ("BOT_D_MAKER_ENV",)
    if bot_id == "bot_g_prime_live":
        return ("BOT_G_PRIME_LIVE_ENV",)
    if bot_id == "bot_g_prime":
        return ("BOT_G_PRIME_ENV",)
    if bot_id == "crypto_probability_gap_live_maker":
        return ("CRYPTO_PROB_GAP_LIVE_ENV",)
    if bot_id == "crypto_brownian_fv_live_maker":
        return ("CRYPTO_BROWNIAN_FV_LIVE_ENV",)
    if bot_id in ("bot_g", "bot_g_jackpot", "bot_g_scalp"):
        return ("BOT_G_ENV",)
    if bot_id.startswith("bot_"):
        short = bot_id[len("bot_"):].split("_")[0].upper()
        return (f"BOT_{short}_ENV",)
    return (f"{bot_id.upper()}_ENV",)


def _bot_env_is_paper(
    bot_id: str,
    *,
    environ: Mapping[str, str] | None = None,
    global_live: bool | None = None,
) -> bool:
    env = os.environ if environ is None else environ
    for key in _env_keys_for_bot(bot_id):
        raw = env.get(key, "").strip().lower()
        if raw:
            return raw == "paper"

    # If the watchdog lacks a per-service env var, fall back to the canonical
    # registry. This is safer than treating global POLYMARKET_ENV=live as
    # proof that every paper service should receive live cancel traffic.
    try:
        from core.bot_registry import meta
        bot_meta = meta(bot_id)
        if bot_meta is not None:
            return bot_meta.status != "live"
    except Exception:
        pass

    live = get_settings().is_live() if global_live is None else global_live
    return not live


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
    portfolio = Portfolio()
    notify_client = default_client()

    # Codex A-3 / GLM A7 (2026-04-22): derive per-bot cancel wrapper
    # coverage from the canonical registry, so adding a new bot
    # (bot_g, bot_f_mirror) doesn't leave it without cancel coverage.
    # Excludes bot_b (has its own executor) and archived bots.
    from core.bot_registry import REGISTRY as _REG
    _cancel_coverage = tuple(
        b.bot_id for b in _REG
        if b.bot_id != "bot_b"
        and b.status not in ("archived", "shadow", "sensor")
        and b.bot_id not in LOCAL_WATCHDOG_EXCLUDED_BOTS
    )

    live_cancel_ids = tuple(
        bid for bid in ("bot_b", *_cancel_coverage)
        if bid not in LOCAL_WATCHDOG_EXCLUDED_BOTS
    )
    live_cancel_needed = any(not _bot_env_is_paper(bid) for bid in live_cancel_ids)
    ks: Keystore | None = None
    if settings.is_live() and live_cancel_needed:
        try:
            ks = Keystore.load(settings.polymarket_keystore_path, settings.polymarket_passphrase_path)
        except KeystoreError as e:
            log.error("watchdog.keystore_fail", extra={"error": str(e)})
            return 2

    def _clob_for_bot(bid: str) -> ClobWrapper:
        paper = _bot_env_is_paper(bid)
        # Paper-mode wrappers don't need a keystore; force keystore=None so a
        # missing hot wallet doesn't break paper cancel_all.
        wrapper = ClobWrapper(
            keystore=None if paper else ks,
            paper_override=paper,
        )
        if not paper:
            wrapper.load_preflight_from_db()
        log.info(
            "watchdog.per_bot_clob bot_id=%s paper=%s",
            bid, paper,
        )
        return wrapper

    # Bot B excluded from public export; see docs/bot-b-reference.md
    exec_b = None

    clob_by_bot: dict[str, ClobWrapper] = {}
    for bid in _cancel_coverage:
        clob_by_bot[bid] = _clob_for_bot(bid)
    # Shadow bots are paper-by-definition.
    for bid in ("bot_a_shadow", "bot_b_shadow"):
        clob_by_bot[bid] = ClobWrapper(keystore=None, paper_override=True)

    def dispatch_cancel(bot_id: str) -> int:
        if bot_id == "bot_a":
            # ADR-033 (2026-04-18): Bot A archived. No live orders exist.
            import os as _os
            if _os.environ.get("BOT_A_ARCHIVED", "true").lower() in ("true", "1", "yes", "on"):
                log.info("watchdog.cancel_skip.bot_a_archived")
                return 0
            log.warning("watchdog.cancel_bot_a_live_without_exec_archived")
            return 0
        if bot_id == "bot_b":
            if exec_b is None:
                log.warning("watchdog.cancel_bot_b_not_in_local_scope")
                return 0
            return exec_b.cancel_all()
        # U-03: route through the per-bot wrapper.
        wrapper = clob_by_bot.get(bot_id)
        if wrapper is None:
            log.warning("watchdog.cancel_no_wrapper.%s", bot_id)
            return 0
        try:
            return wrapper.cancel_all()
        except Exception as e:
            log.warning("watchdog.cancel_fail.%s: %s", bot_id, e)
            return 0

    def notify(sev: str, msg: str) -> None:
        try:
            notify_client.send(sev, f"[watchdog] {msg}")
        except Exception as e:
            log.warning("watchdog.notify_fail", extra={"error": str(e)})

    # Construct the Watchdog once, outside the loop, so `_last_alert_at`
    # dedupe state survives between ticks. Re-resolving FX every tick would
    # overwrite the alert memory and defeat the 30-minute throttle.
    gbp_to_usd = Decimal("1") / get_usd_to_gbp_rate()
    cfg = WatchdogConfig(
        bot_b_initial_usd=settings.bot_b_bankroll_gbp * gbp_to_usd,
    )
    watchdog = Watchdog(
        cfg,
        portfolio=portfolio,
        cancel_all=dispatch_cancel,
        notify=notify,
    )

    # Audit C9: aggregate caps sanity check. The watchdog's aggregate
    # drawdown kill operates on the total USD exposure; each bot has its
    # own per-bot cap. If the per-bot caps sum higher than the aggregate
    # cap, the aggregate cap fires before the per-bot caps have bitten —
    # a silent misconfiguration. Log loudly at startup.
    # Bot B excluded from public export; its per-bot cap check was removed
    # with it. See docs/bot-b-reference.md.

    try:
        while _running:
            # Refresh FX-derived initial USD values on each tick without
            # rebuilding the Watchdog (so dedupe memory persists).
            try:
                gbp_to_usd = Decimal("1") / get_usd_to_gbp_rate()
                watchdog.cfg.bot_b_initial_usd = settings.bot_b_bankroll_gbp * gbp_to_usd
            except Exception as e:
                log.warning("watchdog.fx_refresh_fail", extra={"error": str(e)})
            watchdog.run_once()
            for _ in range(TICK_INTERVAL_SECONDS):
                if not _running:
                    break
                time.sleep(1)
    finally:
        if ks is not None:
            ks.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
