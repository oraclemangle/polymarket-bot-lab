"""Analysis loop: periodic scan of Polymarket → evaluate edge vs Pyth → persist decisions."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy.orm import sessionmaker

from bots.bot_c_pyth.discovery import ParsedMarket, fetch_candidate_markets
from bots.bot_c_pyth.strategy import EdgeDecision, get_spot_and_vol, evaluate_market
from core.pyth_feeds import feed_by_symbol
from core.pyth_models import BotCDecision

# Forward reference to avoid circular import in executor.py.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bots.bot_c_pyth.executor import BotCExecutor

log = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL_S = 60.0
# F-08/09: align analyst thresholds with executor so we don't evaluate
# markets the executor will reject. These are the OUTER filters; the
# executor has its own BOT_C_MIN_EDGE_FOR_ORDER and
# BOT_C_MAX_HOURS_TO_RESOLUTION from env. The analyst should be at
# least as permissive as the executor, but not 9x wider.
#
# Session 24 (2026-04-23): made env-configurable so Hermes-basic tuning
# doesn't require redeploy. Systemd unit passes --edge-threshold via
# argparse default; env wins if present.
DEFAULT_EDGE_THRESHOLD = float(os.getenv("BOT_C_ANALYST_EDGE_THRESHOLD", "0.10"))
MIN_VOLUME_USD = Decimal("100")  # keep looser than executor's $500 — we want to LOG near-misses
MAX_HOURS_TO_RESOLUTION = 24 * 90  # keep wide — executor's env-override tightens at entry time


def _persist(session_factory: sessionmaker, decisions: list[EdgeDecision]) -> int:
    with session_factory() as s:
        for d in decisions:
            m = d.market
            s.add(BotCDecision(
                decided_at=d.decided_at,
                gamma_id=m.gamma_id,
                slug=m.slug,
                question=m.question,
                symbol=m.symbol,
                direction=m.direction,
                strike_low=m.strike_low,
                strike_high=m.strike_high,
                resolution_date=m.resolution_date,
                spot_price=d.spot_price,
                annualised_vol=Decimal(str(d.annualised_vol)),
                hours_to_resolution=Decimal(str(d.hours_to_resolution)),
                model_p_yes=Decimal(str(round(d.model_p_yes, 6))),
                market_p_yes=Decimal(str(round(d.market_p_yes, 6))),
                edge=Decimal(str(round(d.net_edge, 6))),
                side=d.side,
                reason=d.reason,
                yes_token_id=m.yes_token_id,
                no_token_id=m.no_token_id,
                volume_24h_usd=m.volume_24h_usd,
            ))
        s.commit()
    return len(decisions)


def _eligible(market: ParsedMarket) -> tuple[bool, str]:
    if market.yes_price is None:
        return False, "no_yes_price"
    if market.volume_24h_usd is not None and market.volume_24h_usd < MIN_VOLUME_USD:
        return False, f"volume<{MIN_VOLUME_USD}"
    dt = (market.resolution_date - datetime.now(UTC)).total_seconds() / 3600.0
    if dt > MAX_HOURS_TO_RESOLUTION:
        return False, f"horizon>{MAX_HOURS_TO_RESOLUTION}h"
    if dt <= 0:
        return False, "expired"
    return True, "ok"


def run_scan(
    session_factory: sessionmaker,
    *,
    edge_threshold: float = DEFAULT_EDGE_THRESHOLD,
    http_client: httpx.Client | None = None,
    executor: "BotCExecutor | None" = None,
    bar_model=None,
) -> tuple[int, int, int, int]:
    """Single scan pass: fetch, evaluate, persist, (optionally) place orders.

    Returns (scanned, evaluated, persisted, orders_placed).

    bar_model: which Pyth table to read spot/vol from. Defaults to PythBarPro
    for back-compat. Pass PythBarHermes when running against the Hermes
    endpoint (SECURITY_AUDIT.md H-2).
    """
    if bar_model is None:
        from core.pyth_models import PythBarPro
        bar_model = PythBarPro
    markets = fetch_candidate_markets(http_client=http_client, limit=500)
    decisions: list[EdgeDecision] = []
    for m in markets:
        ok, why = _eligible(m)
        if not ok:
            log.debug("skip %s/%s: %s", m.symbol, m.slug, why)
            continue
        feed = feed_by_symbol(m.symbol)
        if feed is None or feed.id is None:
            log.debug("skip %s/%s: no pyth feed", m.symbol, m.slug)
            continue
        spot, sigma = get_spot_and_vol(
            session_factory, feed.id, category=feed.category, bar_model=bar_model,
        )
        if spot is None or sigma is None:
            log.debug("skip %s: no spot/vol yet (warming)", m.symbol)
            continue
        dec = evaluate_market(m, spot, sigma, edge_threshold=edge_threshold)
        decisions.append(dec)
        if dec.side != "SKIP":
            log.info(
                "EDGE %s %s spot=%s strike=%s/%s hrs=%.1f model=%.3f mkt=%.3f edge=%+.3f → %s",
                m.symbol, m.slug, spot, m.strike_low, m.strike_high,
                dec.hours_to_resolution, dec.model_p_yes, dec.market_p_yes,
                dec.edge, dec.side,
            )
    persisted = _persist(session_factory, decisions)
    non_skip = sum(1 for d in decisions if d.side != "SKIP")
    orders_placed = 0
    orders_cancelled = 0
    positions_exited = 0
    if executor is not None:
        try:
            entries = executor.try_enter_all(decisions)
            orders_placed = sum(1 for e in entries if e.placed)
            for e in entries:
                if not e.placed:
                    log.info("bot_c.entry.not_placed reason=%s", e.reason)
        except Exception as exc:
            log.warning("executor entry failed: %s", exc)
        # Fix 5: review open orders for edge collapse.
        try:
            orders_cancelled = executor.review_open_orders(decisions)
        except Exception as exc:
            log.warning("executor review failed: %s", exc)
        try:
            positions_exited = executor.review_open_positions(decisions)
        except Exception as exc:
            log.warning("executor position review failed: %s", exc)
    log.info(
        "scan done: candidates=%d evaluated=%d persisted=%d non_skip=%d "
        "orders_placed=%d orders_cancelled=%d positions_exited=%d",
        len(markets), len(decisions), persisted, non_skip,
        orders_placed, orders_cancelled, positions_exited,
    )
    return len(markets), len(decisions), persisted, orders_placed


async def run_analysis_loop(
    session_factory: sessionmaker,
    *,
    scan_interval_s: float = DEFAULT_SCAN_INTERVAL_S,
    edge_threshold: float = DEFAULT_EDGE_THRESHOLD,
    stop_event: asyncio.Event | None = None,
    executor: "BotCExecutor | None" = None,
    bar_model=None,
) -> None:
    """Forever loop: scan every scan_interval_s. Cancellable via stop_event or cancel()."""
    from datetime import date

    from core.portfolio import Portfolio

    BOT_C_INITIAL_USD = Decimal(os.environ.get("BOT_C_INITIAL_USD", "0"))
    portfolio = Portfolio()
    last_snapshot_date: date | None = None

    client = httpx.Client(timeout=15.0, headers={"User-Agent": "bot-c/0.1"})
    try:
        while stop_event is None or not stop_event.is_set():
            # Audit fix #1: reconcile fills BEFORE scan so exposure caps use fresh truth.
            if executor is not None:
                try:
                    from core.config import get_settings
                    if get_settings().is_live() and not executor.clob.paper_override:
                        portfolio.reconcile_live_fills(executor.clob, "bot_c")
                    else:
                        portfolio.simulate_paper_fills("bot_c")
                except Exception as exc:
                    log.warning("bot_c.reconcile.fail: %s", exc)

            try:
                await asyncio.to_thread(
                    run_scan,
                    session_factory,
                    edge_threshold=edge_threshold,
                    http_client=client,
                    executor=executor,
                    bar_model=bar_model,
                )
            except Exception as exc:
                log.warning("scan failed: %s", exc)

            # Daily PnL snapshot — same pattern as Bot A/B.
            # Audit fix #6: pass mark_prices for unrealised PnL visibility.
            today = datetime.now(UTC).date()
            if last_snapshot_date != today:
                try:
                    mark_prices: dict[str, Decimal] = {}
                    try:
                        from core.ingest import build_mark_prices
                        mark_prices = build_mark_prices("bot_c")
                    except Exception:
                        pass
                    portfolio.snapshot_daily(
                        "bot_c",
                        BOT_C_INITIAL_USD,
                        mark_prices=mark_prices,
                        on_date=today,
                    )
                    last_snapshot_date = today
                    log.info("bot_c.snapshot.done", extra={"date": today.isoformat()})
                except Exception as exc:
                    log.warning("bot_c.snapshot.fail", extra={"error": str(exc)})

            try:
                await asyncio.sleep(scan_interval_s)
            except asyncio.CancelledError:
                raise
    finally:
        client.close()
