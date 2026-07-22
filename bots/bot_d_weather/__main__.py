"""Bot D entrypoint — weather temperature-bucket trading daemon.

Usage:
  python -m bots.bot_d_weather [--enable-executor] [--log-level INFO]
                               [--scan-interval-s 300]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx

from bots.bot_d_weather.audit import (
    log_discovery_health,
    log_entry_attempt_snapshot,
    log_forecast_entry_snapshot,
    log_nws_vetoes,
    log_scan_summary,
)
from bots.bot_d_weather.config import (
    BOT_D_BOT_ID,
    BOT_D_EDGE_THRESHOLD,
    BOT_D_EMPIRICAL_DISAGREE_THRESHOLD,
    BOT_D_ENV,
    BOT_D_MAX_LOCKUP_HOURS,
    BOT_D_MIN_ENTRY_HOURS_TO_END,
    BOT_D_NWS_VETO_MIN_THRESHOLD_F,
    BOT_D_REQUIRE_KNOWN_END_DATE,
    BOT_D_REQUIRE_VERIFIED_SETTLEMENT,
    BOT_D_SCAN_INTERVAL_S,
    BOT_D_SOURCE_SNAPSHOT_ENABLED,
    SETTLEMENT_SPECS,
)
from bots.bot_d_weather.discovery import WeatherMarket, fetch_weather_markets
from bots.bot_d_weather.source_monitor import (
    record_completed_forecast_resolutions,
    record_source_snapshots,
)
from bots.bot_d_weather.strategy import (
    WeatherEdgeDecision,
    apply_one_bet_per_event,
    apply_wave_regime_sizing,
    evaluate_weather_market,
)
from bots.bot_d_weather.weather_fetcher import get_forecasts

if TYPE_CHECKING:
    from bots.bot_d_weather.executor import BotDExecutor

log = logging.getLogger(__name__)


def _skip_reason_bucket(reason: str) -> str:
    if reason.startswith("net_edge"):
        return "below_threshold"
    if reason.startswith("observed_"):
        return "observed_constraint"
    if reason.startswith("nws_disagrees"):
        return "nws_disagrees"
    if reason.startswith("ensemble_shape_disagrees"):
        return "ensemble_shape_disagrees"
    return reason.split(" ", 1)[0].split(";", 1)[0] or "unknown"


def _nws_shadow_reason_values(reason: str) -> tuple[float, float] | None:
    import re

    m = re.search(
        r"mean=([\-\d.]+)\s+vs\s+nws=([\-\d.]+),\s+threshold=([\-\d.]+)",
        reason,
    )
    if not m:
        return None
    try:
        mean_f = float(m.group(1))
        nws_f = float(m.group(2))
        return abs(mean_f - nws_f), float(m.group(3))
    except ValueError:
        return None


def _nws_shadow_tradeable(decisions: list[WeatherEdgeDecision], *, floor_f: float | None) -> int:
    """Count candidates that would reach the wave-gated entry list under a looser NWS floor."""
    shadow: list[WeatherEdgeDecision] = []
    for d in decisions:
        if d.side != "SKIP":
            shadow.append(d)
            continue
        if not d.reason.startswith("nws_disagrees"):
            continue
        if abs(d.net_edge) < BOT_D_EDGE_THRESHOLD:
            continue
        if (
            d.probability_disagreement is not None
            and d.probability_disagreement > BOT_D_EMPIRICAL_DISAGREE_THRESHOLD
        ):
            continue
        vals = _nws_shadow_reason_values(d.reason)
        if vals is None:
            continue
        nws_diff, _current_threshold = vals
        if floor_f is not None:
            bucket_width = 1.0
            if d.market.range_low_f is not None and d.market.range_high_f is not None:
                bucket_width = max(1.0, d.market.range_high_f - d.market.range_low_f)
            if nws_diff > max(float(floor_f), bucket_width * 0.5):
                continue
        side = "BUY_YES" if d.net_edge > 0 else "BUY_NO"
        shadow.append(replace(d, side=side, reason=f"nws_shadow_{side.lower()}"))
    return len(apply_wave_regime_sizing(apply_one_bet_per_event(shadow)))


def _nws_shadow_clears_edge(d: WeatherEdgeDecision, *, floor_f: float | None) -> bool:
    if d.side != "SKIP" or not d.reason.startswith("nws_disagrees"):
        return False
    if abs(d.net_edge) < BOT_D_EDGE_THRESHOLD:
        return False
    if (
        d.probability_disagreement is not None
        and d.probability_disagreement > BOT_D_EMPIRICAL_DISAGREE_THRESHOLD
    ):
        return False
    vals = _nws_shadow_reason_values(d.reason)
    if vals is None:
        return False
    nws_diff, _current_threshold = vals
    if floor_f is None:
        return True
    bucket_width = 1.0
    if d.market.range_low_f is not None and d.market.range_high_f is not None:
        bucket_width = max(1.0, d.market.range_high_f - d.market.range_low_f)
    return nws_diff <= max(float(floor_f), bucket_width * 0.5)


def _nws_shadow_payload(decisions: list[WeatherEdgeDecision]) -> dict[str, int | float]:
    vetoed = [d for d in decisions if d.side == "SKIP" and d.reason.startswith("nws_disagrees")]
    return {
        "current_floor_f": float(BOT_D_NWS_VETO_MIN_THRESHOLD_F),
        "vetoed": len(vetoed),
        "would_clear_edge_floor_3f": sum(
            1 for d in decisions if _nws_shadow_clears_edge(d, floor_f=3.0)
        ),
        "would_clear_edge_floor_4f": sum(
            1 for d in decisions if _nws_shadow_clears_edge(d, floor_f=4.0)
        ),
        "would_clear_edge_nws_off": sum(
            1 for d in decisions if _nws_shadow_clears_edge(d, floor_f=None)
        ),
        "would_tradeable_floor_3f": _nws_shadow_tradeable(decisions, floor_f=3.0),
        "would_tradeable_floor_4f": _nws_shadow_tradeable(decisions, floor_f=4.0),
        "would_tradeable_nws_off": _nws_shadow_tradeable(decisions, floor_f=None),
    }


def _scan_summary_payload(
    *,
    raw_markets: int,
    kept_markets: int,
    decisions: list[WeatherEdgeDecision],
    missing_forecasts: int,
    per_event: list[WeatherEdgeDecision],
    tradeable: list[WeatherEdgeDecision],
) -> dict[str, object]:
    non_skip = [d for d in decisions if d.side != "SKIP"]
    skipped = [d for d in decisions if d.side == "SKIP"]
    source_counts = Counter(
        str(d.forecast_source or "unknown")
        for d in decisions
    )
    skip_reasons = Counter(_skip_reason_bucket(d.reason) for d in skipped)
    top_abs = max((d.net_edge for d in decisions), key=abs, default=0.0)
    top_pos = max((d.net_edge for d in decisions), default=0.0)
    top_neg = min((d.net_edge for d in decisions), default=0.0)
    wave_count = sum(1 for d in tradeable if d.regime == "wave")
    isolated_count = sum(1 for d in tradeable if d.regime == "isolated")
    return {
        "raw_markets": raw_markets,
        "kept_markets": kept_markets,
        "evaluated": len(decisions),
        "missing_forecasts": missing_forecasts,
        "non_skip": len(non_skip),
        "after_one_bet_per_event": len(per_event),
        "tradeable": len(tradeable),
        "wave": wave_count,
        "isolated": isolated_count,
        "forecast_sources": dict(sorted(source_counts.items())),
        "skip_reasons": dict(sorted(skip_reasons.items())),
        "nws_shadow": _nws_shadow_payload(decisions),
        "top_abs_net_edge": round(float(top_abs), 6),
        "top_positive_net_edge": round(float(top_pos), 6),
        "top_negative_net_edge": round(float(top_neg), 6),
    }


def _executor_is_paper(executor: object | None) -> bool:
    if executor is None:
        return False
    clob = getattr(executor, "clob", None)
    effective_paper = getattr(clob, "_effective_paper", None)
    if callable(effective_paper):
        try:
            return bool(effective_paper())
        except Exception:
            pass
    paper_override = getattr(clob, "paper_override", None)
    if isinstance(paper_override, bool):
        from core.config import get_settings
        return paper_override or not get_settings().is_live()
    from core.config import get_settings
    return not get_settings().is_live()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="bots.bot_d_weather")
    p.add_argument("--enable-executor", action="store_true", default=False)
    p.add_argument("--scan-interval-s", type=float, default=BOT_D_SCAN_INTERVAL_S)
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def run_scan(
    *,
    http_client: httpx.Client | None = None,
    executor: BotDExecutor | None = None,
) -> tuple[int, int, int]:
    """One scan cycle: fetch forecasts → discover markets → evaluate edges → trade.

    Returns (markets_found, edges_found, orders_placed).
    """
    # 1. Discover temperature markets on Polymarket.
    markets = fetch_weather_markets(client=http_client)
    raw_market_count = len(markets)
    markets = _paper_candidate_markets(markets)
    if raw_market_count != len(markets):
        log.info(
            "bot_d.paper_candidate_filter kept=%d dropped=%d raw=%d",
            len(markets),
            raw_market_count - len(markets),
            raw_market_count,
        )
    if not markets:
        log.info("no temperature markets found on Polymarket")
        payload = {
            "raw_markets": raw_market_count,
            "kept_markets": 0,
            "reason": "zero_temperature_markets",
            "bot_d_env": BOT_D_ENV,
            "require_verified_settlement": BOT_D_REQUIRE_VERIFIED_SETTLEMENT,
            "require_known_end_date": BOT_D_REQUIRE_KNOWN_END_DATE,
            "min_entry_hours_to_end": BOT_D_MIN_ENTRY_HOURS_TO_END,
            "max_lockup_hours": BOT_D_MAX_LOCKUP_HOURS,
            "checked_at": datetime.now(UTC).isoformat(),
        }
        try:
            from core.db import get_session_factory as _sf
            log_discovery_health(_sf(), payload)
        except Exception as exc:
            log.warning("bot_d.audit.discovery_health_failed: %s", exc)
        return 0, 0, 0

    # 1b. Source telemetry: record the latest settlement-station state and
    # market price before any entry logic runs. This is read-only and
    # best-effort; failures must never block scans or trades.
    if BOT_D_SOURCE_SNAPSHOT_ENABLED:
        try:
            from core.db import get_session_factory as _sf
            written = record_source_snapshots(
                _sf(),
                markets,
                bot_id=BOT_D_BOT_ID,
                client=http_client,
            )
            if written:
                log.info("bot_d.source_snapshot.logged count=%d", written)
            labelled = record_completed_forecast_resolutions(
                _sf(),
                bot_id=BOT_D_BOT_ID,
                client=http_client,
            )
            if labelled:
                log.info("bot_d.forecast_resolution.logged count=%d", labelled)
        except Exception as exc:
            log.debug("bot_d.source_snapshot.failed: %s", exc)

    # 2. Determine which cities we need forecasts for.
    cities_needed = list({m.city for m in markets})
    target_dates_by_city: dict[str, list[str]] = {}
    for m in markets:
        target_dates_by_city.setdefault(m.city, []).append(m.date)
    log.info("fetching forecasts for %d cities: %s", len(cities_needed), cities_needed)
    forecasts = get_forecasts(
        cities=cities_needed,
        client=http_client,
        target_dates_by_city=target_dates_by_city,
    )

    # 3. Evaluate edges.
    all_decisions: list[WeatherEdgeDecision] = []
    missing_forecasts = 0
    for m in markets:
        city_fc = forecasts.get(m.city, {})
        fc = city_fc.get(m.date)
        if fc is None:
            missing_forecasts += 1
            log.debug("no forecast for %s %s, skipping", m.city, m.date)
            continue
        dec = evaluate_weather_market(m, fc)
        all_decisions.append(dec)
        if dec.side != "SKIP":
            log.info(
                "EDGE %s %s %s %s %s→%s gfs=%.3f mkt=%.3f net=%+.3f → %s",
                m.city, m.date, m.temp_type, m.direction,
                m.range_low_f, m.range_high_f,
                dec.gfs_probability, dec.market_probability,
                dec.net_edge, dec.side,
            )

    # 3b. Audit log: NWS vetoes (K2.6 follow-up 2026-04-21). Every skipped
    # "nws_disagrees" decision goes into the events table so offline
    # analysis can measure whether the NWS filter adds edge or filters
    # out winners. Best-effort — never block the scan on a log failure.
    try:
        from core.db import get_session_factory as _sf
        log_nws_vetoes(_sf(), all_decisions)
    except Exception as exc:
        log.warning("bot_d.audit.nws_log_failed: %s", exc)

    # 4. One-bet-per-event + wave-regime sizing.
    per_event = apply_one_bet_per_event(all_decisions)
    tradeable = apply_wave_regime_sizing(per_event)
    summary = _scan_summary_payload(
        raw_markets=raw_market_count,
        kept_markets=len(markets),
        decisions=all_decisions,
        missing_forecasts=missing_forecasts,
        per_event=per_event,
        tradeable=tradeable,
    )
    log.info(
        "scan: %d markets, %d evaluated, %d non-skip, %d after one-bet-per-event, "
        "wave=%d isolated=%d",
        len(markets), len(all_decisions),
        summary["non_skip"],
        len(per_event),
        summary["wave"],
        summary["isolated"],
    )
    log.info(
        "bot_d.scan_summary %s",
        json.dumps(summary, sort_keys=True, separators=(",", ":")),
    )
    try:
        from core.db import get_session_factory as _sf
        log_scan_summary(_sf(), summary)
    except Exception as exc:
        log.warning("bot_d.audit.scan_summary_failed: %s", exc)

    # 5. Execute new entries.
    orders_placed = 0
    if executor is not None:
        if tradeable:
            try:
                entries = executor.try_enter_all(tradeable)
                orders_placed = sum(1 for e in entries if e.placed)
                # Forecast-entry snapshot for each placed trade (K2.6
                # follow-up 2026-04-21): enables later AR(1) bias fit by
                # capturing forecast state at the moment of entry.
                try:
                    from core.db import get_session_factory as _sf
                    for e in entries:
                        dec = next(
                            (d for d in tradeable if d.market.gamma_id == e.condition_id),
                            None,
                        )
                        if dec is not None:
                            try:
                                log_entry_attempt_snapshot(
                                    _sf(), dec,
                                    placed=e.placed,
                                    reason=e.reason,
                                    order_id=e.order_id,
                                    size_usd=e.size_usd,
                                    size_shares=e.size_shares,
                                    limit_price=e.limit_price,
                                    depth_usd=e.depth_usd,
                                    required_depth_usd=e.required_depth_usd,
                                )
                            except Exception as exc:
                                log.debug("bot_d.audit.entry_attempt_failed: %s", exc)
                        if not e.placed:
                            log.info("bot_d.entry.not_placed reason=%s", e.reason)
                            continue
                        if dec is not None:
                            log_forecast_entry_snapshot(
                                _sf(), dec,
                                order_id=e.order_id,
                                size_usd=e.size_usd,
                                limit_price=e.limit_price,
                                depth_usd=e.depth_usd,
                                required_depth_usd=e.required_depth_usd,
                            )
                except Exception as exc:
                    log.warning("bot_d.audit.forecast_entry_log_failed: %s", exc)
            except Exception as exc:
                log.warning("executor entry failed: %s", exc)
        # 6. Review open orders for edge collapse after GFS update.
        try:
            executor.review_open_orders(all_decisions)
        except Exception as exc:
            log.warning("executor review failed: %s", exc)

        # 7. Review FILLED positions for edge collapse — K2.6 audit fix
        # 2026-04-21. Previously Bot D had no bot-driven exit path; filled
        # positions were held blindly to resolution, locking the book in
        # the face of 6h GFS updates flipping edge direction.
        try:
            positions_exited = executor.review_open_positions(all_decisions)
            if positions_exited:
                log.info("bot_d.positions_exited=%d", positions_exited)
        except Exception as exc:
            log.warning("executor position review failed: %s", exc)

    return len(markets), len(tradeable), orders_placed


def _paper_candidate_markets(markets: list[WeatherMarket]) -> list[WeatherMarket]:
    """Keep only markets shaped like a future tiny-live Bot D candidate."""
    out: list[WeatherMarket] = []
    now = datetime.now(UTC)
    for market in markets:
        if BOT_D_REQUIRE_VERIFIED_SETTLEMENT:
            spec = SETTLEMENT_SPECS.get(market.city)
            if spec is None or not spec.verified:
                continue
        if BOT_D_REQUIRE_KNOWN_END_DATE and market.end_date is None:
            continue
        if market.end_date is not None:
            end_date = market.end_date
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=UTC)
            hours_to_end = (end_date - now).total_seconds() / 3600
            if hours_to_end <= 0:
                continue
            if BOT_D_MIN_ENTRY_HOURS_TO_END > 0 and hours_to_end < BOT_D_MIN_ENTRY_HOURS_TO_END:
                continue
            if BOT_D_MAX_LOCKUP_HOURS > 0 and hours_to_end > BOT_D_MAX_LOCKUP_HOURS:
                continue
        out.append(market)
    return out


async def run_loop(args: argparse.Namespace) -> None:
    """Main scan loop. Runs every scan_interval_s seconds."""
    executor = None
    if args.enable_executor:
        from bots.bot_d_weather.executor import BotDExecutor
        from core.clob_v2 import ClobWrapperV2 as ClobWrapper
        from core.config import get_settings
        from core.db import init_db

        init_db()
        bot_d_live = BOT_D_ENV == "live"
        keystore = None
        if bot_d_live:
            from core.keystore import Keystore
            keystore = Keystore.load_from_settings(get_settings())
        clob = ClobWrapper(keystore=keystore, paper_override=not bot_d_live)
        if bot_d_live:
            clob.load_preflight_from_db()
        executor = BotDExecutor(clob=clob)
        log.info(
            "bot_d: executor enabled (bot_id=%s bot_d_env=%s)",
            BOT_D_BOT_ID,
            "LIVE" if bot_d_live else "PAPER",
        )

    # Audit fix #1 + #7: reconciliation + daily snapshot path.
    from datetime import date
    from decimal import Decimal

    from core.portfolio import Portfolio
    portfolio = Portfolio()
    # K2.6 audit 2026-04-21 (bug #6H): previously defaulted to "0" silently,
    # which made daily P&L snapshots compute against a $0 baseline — any
    # non-zero realised P&L got reported as infinite %. Now require the
    # operator to set BOT_D_INITIAL_USD explicitly, or fall through to
    # BOT_D_BANKROLL_USD as the sensible baseline for paper reporting.
    _initial_env = os.environ.get("BOT_D_INITIAL_USD")
    if _initial_env is None or _initial_env.strip() == "":
        from bots.bot_d_weather.config import BOT_D_BANKROLL_USD
        bot_d_initial_usd = BOT_D_BANKROLL_USD
        log.warning(
            "bot_d.config.missing_initial_usd — BOT_D_INITIAL_USD unset, "
            "using BOT_D_BANKROLL_USD=%s as baseline for daily P&L snapshots. "
            "Set BOT_D_INITIAL_USD explicitly to silence this warning.",
            BOT_D_BANKROLL_USD,
        )
    else:
        bot_d_initial_usd = Decimal(_initial_env)
        if bot_d_initial_usd <= 0:
            raise RuntimeError(
                f"BOT_D_INITIAL_USD must be > 0 (got {bot_d_initial_usd}). "
                "This value is the baseline for daily P&L — a zero or "
                "negative baseline produces meaningless return metrics."
            )
    last_snapshot_date: date | None = None
    # Paper-resolution reconciliation: hourly is cheap (Gamma is public,
    # one request per OPEN position). Session 17r-ext: Bot D had 17/22 OPEN
    # positions past end_date because paper mode never calls on_redeem.
    last_paper_resolve_ts: float = 0.0
    paper_resolve_interval_s: float = float(
        os.environ.get("BOT_D_PAPER_RESOLVE_INTERVAL_S", "3600")
    )
    # Live wallet-position reconciliation: 2026-05-14 fix for the same
    # parity drift on the LIVE side. Dashboard showed 22 OPEN positions /
    # $100.35 exposure while the wallet held only 5 (~$30.80). The
    # CLOB on_fill / on_redeem path misses some sells/redeems; this
    # cheap hourly check against Polymarket's public /positions endpoint
    # closes the gap without touching wallet funds or CLOB orders.
    last_wallet_resolve_ts: float = 0.0
    wallet_resolve_interval_s: float = float(
        os.environ.get("BOT_D_WALLET_RESOLVE_INTERVAL_S", "3600")
    )

    client = httpx.Client(timeout=30.0, headers={"User-Agent": "bot-d-weather/0.1"})
    try:
        while True:
            # Reconcile fills before scan (audit fix #1).
            if executor is not None:
                try:
                    from core.config import get_settings
                    if get_settings().is_live() and not executor.clob.paper_override:
                        portfolio.reconcile_live_fills(
                            executor.clob,
                            BOT_D_BOT_ID,
                            require_known_order=True,
                        )
                    else:
                        portfolio.simulate_paper_fills(BOT_D_BOT_ID)
                except Exception as exc:
                    log.warning("bot_d.reconcile.fail: %s", exc)

            # Paper-resolution reconciliation (hourly). Closes OPEN positions
            # whose markets have resolved on Gamma — paper mode has no
            # on-chain on_redeem path so these would otherwise stay OPEN
            # forever. See ADR-035.
            now_ts = time.time()
            if _executor_is_paper(executor) and now_ts - last_paper_resolve_ts >= paper_resolve_interval_s:
                try:
                    settled = await asyncio.to_thread(
                        portfolio.reconcile_paper_resolutions, BOT_D_BOT_ID
                    )
                    if settled:
                        log.info("bot_d.paper_resolve.settled count=%d", settled)
                    last_paper_resolve_ts = now_ts
                except Exception as exc:
                    log.warning("bot_d.paper_resolve.fail: %s", exc)

            # Live wallet-position reconciliation (hourly, live mode only).
            # Closes locally-OPEN rows that the wallet no longer holds —
            # detected by comparing Position(status='OPEN') token_ids
            # against the wallet's current /positions response. Safety:
            # no orders, no cancels, no redemptions, no key access. On
            # Data API failure: log + leave local rows unchanged.
            if (
                bot_d_live
                and not _executor_is_paper(executor)
                and keystore is not None
                and now_ts - last_wallet_resolve_ts >= wallet_resolve_interval_s
            ):
                try:
                    result = await asyncio.to_thread(
                        portfolio.reconcile_live_positions_against_wallet,
                        BOT_D_BOT_ID,
                        keystore.address,
                    )
                    if not result.get("ok"):
                        log.warning(
                            "bot_d.wallet_resolve.degraded reason=%s checked=%d",
                            result.get("reason"),
                            result.get("checked", 0),
                        )
                    elif result.get("closed_count"):
                        log.info(
                            "bot_d.wallet_resolve.closed_stale count=%d kept=%d "
                            "(wallet=%s)",
                            result["closed_count"],
                            result["kept_open"],
                            keystore.address[:10] + "…",
                        )
                    last_wallet_resolve_ts = now_ts
                except Exception as exc:
                    log.warning("bot_d.wallet_resolve.fail: %s", exc)

            try:
                mkts, edges, orders = await asyncio.to_thread(
                    run_scan, http_client=client, executor=executor,
                )
                log.info("cycle done: markets=%d edges=%d orders=%d", mkts, edges, orders)
            except Exception as exc:
                log.warning("scan cycle failed: %s", exc)

            # Daily PnL snapshot (audit fix #7).
            today = datetime.now(UTC).date()
            if last_snapshot_date != today:
                try:
                    mark_prices: dict[str, Decimal] = {}
                    try:
                        from core.ingest import build_mark_prices
                        mark_prices = build_mark_prices(BOT_D_BOT_ID)
                    except Exception:
                        pass
                    portfolio.snapshot_daily(
                        BOT_D_BOT_ID, bot_d_initial_usd,
                        mark_prices=mark_prices, on_date=today,
                    )
                    last_snapshot_date = today
                    log.info("bot_d.snapshot.done date=%s", today.isoformat())
                except Exception as exc:
                    log.warning("bot_d.snapshot.fail: %s", exc)

            await asyncio.sleep(args.scan_interval_s)
    except asyncio.CancelledError:
        log.info("bot_d: cancelled")
    finally:
        client.close()


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("bot_d starting: scan_interval=%ss executor=%s bot_d_env=%s",
             args.scan_interval_s, args.enable_executor, BOT_D_ENV)
    try:
        asyncio.run(run_loop(args))
    except KeyboardInterrupt:
        log.info("bot_d: interrupted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
