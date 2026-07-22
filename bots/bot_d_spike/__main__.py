"""Entrypoint for Bot D-Spike paper lane and capped live probe."""

from __future__ import annotations

import argparse
import logging
import time
from datetime import UTC, datetime

from bots.bot_d_spike import config as cfg
from bots.bot_d_spike.discovery import find_eligible_candidates
from bots.bot_d_spike.executor import SpikeExecutor
from bots.bot_d_spike.strategy import decide_entry
from core.clob_v2 import ClobWrapperV2
from core.config import get_settings
from core.db import init_db
from core.keystore import Keystore

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bot D-Spike paper runner")
    parser.add_argument("--dry-run", action="store_true", help="scan and log decisions without DB writes")
    parser.add_argument("--once", action="store_true", help="run one scan and exit")
    parser.add_argument("--scan-interval-s", type=float, default=cfg.SCAN_INTERVAL_S)
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--gamma-limit", type=int, default=500)
    return parser


def _build_clob(settings) -> ClobWrapperV2:
    live = settings.is_live() and not cfg.PAPER_ONLY
    if live:
        if not cfg.LIVE_APPROVED_AT:
            raise SystemExit("Bot D-Spike live mode requires BOT_D_SPIKE_LIVE_APPROVED_AT")
        keystore = Keystore.load(settings.polymarket_keystore_path, settings.polymarket_passphrase_path)
        clob = ClobWrapperV2(keystore=keystore, paper_override=False)
        clob.load_preflight_from_db()
        return clob
    return ClobWrapperV2(keystore=None, paper_override=True)


def scan_once(*, dry_run: bool, gamma_limit: int) -> int:
    settings = get_settings()
    if settings.is_live() and cfg.PAPER_ONLY:
        log.warning("bot_d_spike.live_global_env_seen forced_paper_override=true")

    clob = _build_clob(settings)
    candidates = find_eligible_candidates(clob=clob, limit=gamma_limit)
    log.info("bot_d_spike.scan eligible=%d dry_run=%s", len(candidates), dry_run)
    if dry_run:
        for candidate in candidates:
            decision = decide_entry(candidate)
            log.info(
                "bot_d_spike.dry_candidate enter=%s reason=%s city=%s bucket=%s ask=%s bid=%s ttr_h=%s",
                decision.enter,
                decision.reason,
                candidate.city,
                candidate.market.bucket,
                candidate.best_ask,
                candidate.best_bid,
                candidate.hours_to_resolution,
            )
        return 0

    executor = SpikeExecutor(clob)
    placed = 0
    for candidate in candidates:
        result = executor.try_enter(decide_entry(candidate))
        if result.placed:
            placed += 1
        log.info(
            "bot_d_spike.entry_result placed=%s reason=%s condition_id=%s order_id=%s fills=%d",
            result.placed,
            result.reason,
            result.condition_id,
            result.order_id,
            result.fills_simulated,
        )
        if executor.todays_entries() >= cfg.MAX_DAILY_ENTRIES:
            break
    if executor._effective_paper():
        settled = executor.reconcile_resolutions()
        log.info("bot_d_spike.scan_done placed=%d settled=%d mode=paper", placed, settled)
    else:
        settled = executor.reconcile_live_fills()
        log.info("bot_d_spike.scan_done placed=%d reconciled=%d mode=live", placed, settled)
    return placed


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    init_db()
    last_resolve_ts = 0.0
    while True:
        scan_once(dry_run=args.dry_run, gamma_limit=args.gamma_limit)
        if args.dry_run or args.once:
            return
        now_ts = time.time()
        if now_ts - last_resolve_ts >= cfg.PAPER_RESOLVE_INTERVAL_S:
            try:
                settings = get_settings()
                executor = SpikeExecutor(_build_clob(settings))
                settled = (
                    executor.reconcile_resolutions()
                    if executor._effective_paper()
                    else executor.reconcile_live_fills()
                )
                log.info("bot_d_spike.periodic_reconcile count=%d at=%s", settled, datetime.now(UTC).isoformat())
            except Exception as exc:
                log.warning("bot_d_spike.periodic_resolve_failed err=%s", exc)
            last_resolve_ts = now_ts
        time.sleep(args.scan_interval_s)


if __name__ == "__main__":
    main()
