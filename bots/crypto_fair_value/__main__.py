"""Run a crypto fair-value paper bot.

Usage:
    python -m bots.crypto_fair_value --strategy probability_gap
    python -m bots.crypto_fair_value --strategy brownian_fair_value
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal as signal_mod
import time
from collections import Counter
from datetime import UTC, datetime

from bots.crypto_fair_value.config import load_config, validate
from bots.crypto_fair_value.discovery import (
    active_markets,
    cex_state,
    connect_recorder,
    latest_book_state,
)
from bots.crypto_fair_value.model import (
    brownian_fair_value_signal,
    probability_gap_signal,
)
from bots.crypto_fair_value.paper_executor import execute_signal, has_open_position
from core.db import Event, get_session_factory
from core.portfolio import Portfolio

log = logging.getLogger("crypto_fair_value")
_running = True


def _handle_signal(signum, _frame) -> None:
    global _running
    log.info("crypto_fair_value.signal_received signum=%s stopping", signum)
    _running = False


def _record_scan_summary(bot_id: str, counts: Counter[str]) -> None:
    sf = get_session_factory()
    with sf() as session:
        session.add(
            Event(
                bot_id=bot_id,
                event_type="crypto_fair_value.scan_summary",
                severity="info",
                message=(
                    "crypto fair-value scan: "
                    + ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
                ),
                payload=dict(counts),
            )
        )
        session.commit()


def scan_once(config) -> Counter[str]:
    counts: Counter[str] = Counter()
    conn = connect_recorder(config.recorder_db_path)
    if conn is None:
        counts["recorder_db_missing"] += 1
        _record_scan_summary(config.bot_id, counts)
        return counts

    now_ms = int(time.time() * 1000)
    try:
        markets = active_markets(conn, config=config, now_ms=now_ms)
        counts["markets_seen"] = len(markets)
        for meta in markets:
            counts["markets_evaluated"] += 1
            if has_open_position(config.bot_id, meta.condition_id):
                counts["duplicate_open_position"] += 1
                continue
            book = latest_book_state(
                conn,
                meta,
                now_ms=now_ms,
                max_age_sec=config.max_book_age_sec,
            )
            if book is None:
                counts["missing_book"] += 1
                continue
            state = cex_state(
                conn,
                meta,
                now_ms=now_ms,
                max_age_sec=config.max_cex_age_sec,
            )
            if state is None:
                counts["stale_or_missing_cex"] += 1
                continue
            if book.effective_spread > config.max_spread:
                counts["spread_skip"] += 1
                continue
            if abs(state.move_60s) > config.chaos_max_abs_move_60s:
                counts["chaos_skip"] += 1
                continue

            if config.strategy == "probability_gap":
                sig = probability_gap_signal(
                    meta=meta,
                    book=book,
                    cex=state,
                    decision_ms=now_ms,
                    min_edge=config.min_edge,
                    min_price=config.min_price,
                    max_price=config.max_price,
                )
            else:
                if now_ms < meta.start_ms + 30_000:
                    counts["brownian_opening_window_skip"] += 1
                    continue
                if abs(state.move_60s) > config.brownian_max_abs_move_60s:
                    counts["brownian_move_skip"] += 1
                    continue
                sig = brownian_fair_value_signal(
                    meta=meta,
                    book=book,
                    cex=state,
                    decision_ms=now_ms,
                    min_model_mid_gap=config.min_model_mid_gap,
                    min_entry_edge=config.min_entry_edge,
                    min_price=config.min_price,
                    max_price=config.max_price,
                )
            if sig is None:
                counts["no_signal"] += 1
                continue
            if sig.top_depth_usd < config.min_top_depth_usd:
                counts["depth_skip"] += 1
                continue
            if execute_signal(config=config, meta=meta, signal=sig):
                counts["signals_filled"] += 1
            else:
                counts["signals_not_filled"] += 1
    finally:
        conn.close()

    _record_scan_summary(config.bot_id, counts)
    return counts


async def run_loop(config, *, once: bool = False) -> None:
    pfo = Portfolio()
    last_resolve_ts = 0.0
    while _running:
        if not config.enabled:
            log.info("crypto_fair_value.disabled bot_id=%s", config.bot_id)
            return
        now_ts = time.time()
        if now_ts - last_resolve_ts >= config.paper_resolve_interval_s:
            try:
                settled = await asyncio.to_thread(
                    pfo.reconcile_paper_resolutions, config.bot_id
                )
                if settled:
                    log.info(
                        "crypto_fair_value.paper_resolve.settled bot_id=%s count=%d",
                        config.bot_id,
                        settled,
                    )
                last_resolve_ts = now_ts
            except Exception as exc:
                log.warning("crypto_fair_value.paper_resolve.failed err=%s", exc)
        counts = await asyncio.to_thread(scan_once, config)
        log.info("crypto_fair_value.scan bot_id=%s counts=%s", config.bot_id, dict(counts))
        if once:
            return
        await asyncio.sleep(config.scan_interval_s)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--strategy",
        choices=("probability_gap", "brownian_fair_value"),
        required=True,
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = load_config(args.strategy)
    errors = validate(config)
    if errors:
        for error in errors:
            log.error("crypto_fair_value.config_error %s", error)
        return 2
    log.info(
        "crypto_fair_value.runtime bot_id=%s strategy=%s dry_run=%s generated_at=%s",
        config.bot_id,
        config.strategy,
        config.dry_run,
        datetime.now(UTC).isoformat(),
    )
    signal_mod.signal(signal_mod.SIGINT, _handle_signal)
    signal_mod.signal(signal_mod.SIGTERM, _handle_signal)
    asyncio.run(run_loop(config, once=args.once))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
