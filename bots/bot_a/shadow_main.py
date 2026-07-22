"""Bot A Shadow daemon — paper-mode twin of the live Bot A.

Always runs paper fills (ClobWrapper(paper_override=True)).  Ignores the live
bot_a HaltFlag; uses its own halt_flags row keyed by 'bot_a_shadow'.

Purpose: keep evaluating Bot A signals and simulating fills while live is
paused/halted so the operator can answer "would this edge still work?"

Usage:
    python -m bots.bot_a.shadow_main [--help]
    systemd: polymarket-bot-a-shadow.service

Env:
    BOT_A_SHADOW_INITIAL_USD  — shadow bankroll (default $125)
    BOT_A_TICK_INTERVAL       — seconds between ticks (default 300, shared with live)
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from bots.bot_a.candidates import build_candidates
from bots.bot_a.config import (
    AGGREGATE_EXPOSURE_CAP_USD,
    MAX_YES_ENTRY_PRICE,
    MIN_24H_VOLUME_USD,
    MIN_ORDER_SHARES,
    REPOST_STALE_HOURS,
    TARGET_CATEGORIES,
)
from bots.bot_a.filters import Candidate, qualifies
from bots.bot_a.sizer import shares_from_notional, size_position
from core.clob_v2 import ClobWrapperV2 as ClobWrapper, OrderType, Side
from core.db import HaltFlag, Order, get_session_factory
from core.ingest import BookSnapshotter, Scraper, build_mark_prices, latest_yes_price_fn
from core.portfolio import Portfolio

BOT_ID = "bot_a_shadow"
TICK_INTERVAL = int(os.environ.get("BOT_A_TICK_INTERVAL", "300"))
INITIAL_USD = Decimal(os.environ.get("BOT_A_SHADOW_INITIAL_USD", "125"))

log = logging.getLogger(BOT_ID)
_running = True


def _handle_signal(signum, _):
    global _running
    log.info("%s.signal", BOT_ID, extra={"signum": signum})
    _running = False


def _is_halted() -> bool:
    with get_session_factory()() as s:
        flag = s.get(HaltFlag, BOT_ID)
        return bool(flag and flag.halted)


def _has_open(sessions, condition_id: str) -> bool:
    with sessions() as s:
        return bool(
            s.scalars(
                select(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.condition_id == condition_id,
                    Order.status.in_(("OPEN", "PARTIAL", "PAPER_OPEN")),
                )
            ).first()
        )


def _exposure_usd(portfolio: Portfolio) -> Decimal:
    return portfolio.get_total_exposure(BOT_ID)


def _tick(clob: ClobWrapper, portfolio: Portfolio, sessions) -> dict:
    placed = skipped = 0
    if _is_halted():
        log.info("%s.tick.halted", BOT_ID)
        return {"placed": 0, "skipped": 0}

    cands = build_candidates(volume_map={})
    for cand in cands:
        if not qualifies(cand):
            skipped += 1
            continue
        if _has_open(sessions, cand.condition_id):
            skipped += 1
            continue
        if cand.no_token_id is None:
            skipped += 1
            continue

        notional = size_position(INITIAL_USD, cand.no_ask_depth_within_2c_usd)
        if notional <= Decimal("0"):
            skipped += 1
            continue
        if _exposure_usd(portfolio) + notional > AGGREGATE_EXPOSURE_CAP_USD:
            skipped += 1
            continue

        limit_price = (Decimal("1") - cand.best_yes_ask).quantize(Decimal("0.01"))
        if limit_price < Decimal("0.90"):
            skipped += 1
            continue

        size_shares = shares_from_notional(notional, limit_price)
        if size_shares < MIN_ORDER_SHARES:
            skipped += 1
            continue

        resp = clob.place_limit(
            token_id=cand.no_token_id,
            price=limit_price,
            size=size_shares,
            side=Side.BUY,
            order_type=OrderType.GTC,
        )
        with sessions() as s:
            s.add(Order(
                order_id=resp.order_id,
                bot_id=BOT_ID,
                condition_id=cand.condition_id,
                token_id=cand.no_token_id,
                side="BUY",
                price=limit_price,
                size=size_shares,
                status=resp.status or "PAPER_OPEN",
                order_type="GTC",
            ))
            s.commit()
        log.info("%s.entry.placed", BOT_ID, extra={"order_id": resp.order_id, "condition_id": cand.condition_id})
        placed += 1

    return {"placed": placed, "skipped": skipped}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="bots.bot_a.shadow_main")
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Session 17m (2026-04-18) — ADR-033 archival guard. Same env flag as
    # the live Bot A daemon: shadow follows live's archival state so paper
    # compute doesn't burn on a known-negative-EV strategy.
    archived = os.environ.get("BOT_A_ARCHIVED", "true").lower() in ("true", "1", "yes", "on")
    if archived:
        log.warning(
            "bot_a_shadow.archived — ADR-033 active. Shadow mirrors live "
            "Bot A archival state. Set BOT_A_ARCHIVED=false to re-enable both."
        )
        return 0

    log.info("%s.start", BOT_ID, extra={"initial_usd": str(INITIAL_USD)})

    clob = ClobWrapper(keystore=None, paper_override=True)
    portfolio = Portfolio()
    sessions = get_session_factory()
    last_snapshot_date = None
    # Session 17s 2026-04-20: hourly paper-resolution reconciliation (ADR-035).
    last_paper_resolve_ts: float = 0.0
    paper_resolve_interval_s: float = float(
        os.environ.get("BOT_A_SHADOW_PAPER_RESOLVE_INTERVAL_S", "3600")
    )

    while _running:
        try:
            Scraper().run_once(max_pages=20)
            snapshotter = BookSnapshotter()
            targets = snapshotter.tokens_for_bot_a(
                max_yes_price=MAX_YES_ENTRY_PRICE * Decimal("3"),
                min_volume_usd=MIN_24H_VOLUME_USD,
                categories=TARGET_CATEGORIES,
            )
            snapshotter.run_once(token_ids=targets)
        except Exception as e:
            log.warning("%s.ingest_fail", BOT_ID, extra={"error": str(e)})

        try:
            portfolio.simulate_paper_fills(BOT_ID)
        except Exception as e:
            log.warning("%s.reconcile_fail", BOT_ID, extra={"error": str(e)})

        # Paper-resolution reconciliation (hourly, ADR-035).
        now_ts = time.time()
        if (now_ts - last_paper_resolve_ts) >= paper_resolve_interval_s:
            try:
                settled = portfolio.reconcile_paper_resolutions(BOT_ID)
                if settled:
                    log.info("%s.paper_resolve.settled count=%d", BOT_ID, settled)
                last_paper_resolve_ts = now_ts
            except Exception as e:
                log.warning("%s.paper_resolve.fail", BOT_ID, extra={"error": str(e)})

        try:
            result = _tick(clob, portfolio, sessions)
            log.info("%s.tick", BOT_ID, extra=result)
        except Exception as e:
            log.warning("%s.tick_fail", BOT_ID, extra={"error": str(e)})

        today = datetime.now(UTC).date()
        if last_snapshot_date != today:
            try:
                portfolio.snapshot_daily(
                    BOT_ID,
                    INITIAL_USD,
                    mark_prices=build_mark_prices(BOT_ID),
                    on_date=today,
                )
                last_snapshot_date = today
            except Exception as e:
                log.warning("%s.snapshot_fail", BOT_ID, extra={"error": str(e)})

        for _ in range(TICK_INTERVAL):
            if not _running:
                break
            time.sleep(1)

    log.info("%s.stop", BOT_ID)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
