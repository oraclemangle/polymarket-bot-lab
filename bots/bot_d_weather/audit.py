"""Bot D audit logging — NWS vetoes and forecast-entry snapshots.

Session 17l follow-up (2026-04-21): K2.6 audit flagged two blind spots.

1. **NWS vetoes are invisible.** The strategy filter skips markets where
   NWS disagrees with our ensemble by more than the bucket-width-scaled
   threshold, but there's no record of what was skipped, so we can't
   evaluate whether the filter adds edge or destroys it. Fix: write an
   Event row for every NWS veto. Offline analysis can later join these
   against market resolutions to measure filter value.

2. **No forecast residuals for AR(1) bias correction.** GFS/ECMWF
   forecast errors are autoregressive: if today's Chicago forecast ran
   3°F too warm, tomorrow's probably runs ~2°F too warm. Bot D
   currently models error as white noise. Before we can implement a
   rolling bias correction, we need per-entry forecast snapshots so
   that post-resolution analysis can compute the actual residual.
   Fix: write an Event row with the forecast mean/std/bucket on every
   successful entry.

Both events go into the ``events`` table with ``bot_id='bot_d'``. They
are ``severity='info'`` and do not trigger watchdog alerts. Schema:

    event_type          payload keys
    -------------------- ---------------------------------------------------
    bot_d.nws_veto       city, date, temp_type, bucket_low_f, bucket_high_f,
                         forecast_mean_f, forecast_std_f, nws_temp_f,
                         nws_disagreement_f, veto_threshold_f, net_edge,
                         gfs_probability, market_probability
    bot_d.forecast_entry city, date, temp_type, bucket_low_f, bucket_high_f,
                         forecast_mean_f, forecast_std_f, ensemble_count,
                         side, net_edge, gfs_probability, market_probability,
                         order_id, size_usd, limit_price
    bot_d.scan_summary   raw_markets, kept_markets, evaluated, missing_forecasts,
                         non_skip, after_one_bet_per_event, tradeable,
                         skip_reasons, forecast_sources, top edges
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import sessionmaker

from bots.bot_d_weather.config import (
    BOT_D_BOT_ID,
    BOT_D_PAPER_EPOCH_ID,
    BOT_D_PAPER_EPOCH_START,
    SETTLEMENT_SPECS,
)
from bots.bot_d_weather.labels import enrich_payload
from bots.bot_d_weather.strategy import WeatherEdgeDecision
from core.db import Event

log = logging.getLogger(__name__)

BOT_ID = BOT_D_BOT_ID


def _common_payload(dec: WeatherEdgeDecision) -> dict[str, Any]:
    m = dec.market
    spec = SETTLEMENT_SPECS.get(m.city)
    payload = {
        "city": m.city,
        "date": m.date,
        "temp_type": m.temp_type,
        "bucket_low_f": m.range_low_f,
        "bucket_high_f": m.range_high_f,
        "settlement_station": spec.station if spec else None,
        "observation_station": (spec.obs_station or spec.station) if spec else None,
        "settlement_source": spec.source if spec else None,
        "settlement_rounding": spec.rounding if spec else "nearest_int",
        "settlement_unit": spec.unit if spec else "F",
        "settlement_verified": bool(spec.verified) if spec else False,
        "forecast_mean_f": dec.forecast_mean_f,
        "forecast_std_f": dec.forecast_std_f,
        "forecast_source": getattr(dec, "forecast_source", None),
        "forecast_model_timestamp": getattr(dec, "forecast_model_timestamp", None),
        "forecast_fetched_at": (
            getattr(dec, "forecast_fetched_at", None).isoformat()
            if getattr(dec, "forecast_fetched_at", None) is not None
            else None
        ),
        "api_highs_f": list(getattr(dec, "api_highs_f", ()) or ()),
        "api_lows_f": list(getattr(dec, "api_lows_f", ()) or ()),
        "nws_gap_f": getattr(dec, "nws_gap_f", None),
        "api_agreement_count": getattr(dec, "api_agreement_count", 0),
        "api_agreement_max_gap_f": getattr(dec, "api_agreement_max_gap_f", None),
        "nws_outlier_probe": bool(getattr(dec, "nws_outlier_probe", False)),
        "ensemble_count": dec.ensemble_count,
        "net_edge": dec.net_edge,
        "gfs_probability": dec.gfs_probability,
        "market_probability": dec.market_probability,
        "condition_id": m.gamma_id,
        "yes_token_id": m.yes_token_id,
        "no_token_id": m.no_token_id,
        "regime": getattr(dec, "regime", "unclassified"),
        "wave_key": getattr(dec, "wave_key", None),
        "wave_count": getattr(dec, "wave_count", 1),
        "paper_epoch_id": BOT_D_PAPER_EPOCH_ID,
        "paper_epoch_start": BOT_D_PAPER_EPOCH_START,
    }
    try:
        payload.update(enrich_payload(payload, reason=getattr(dec, "reason", None)))
    except Exception as exc:
        log.debug("bot_d.audit.label_enrich_failed err=%s", exc)
    return payload


def _parse_nws_reason(reason: str) -> dict[str, float | None]:
    """Pull the numeric context out of ``reason`` strings that look like:
        'nws_disagrees (mean=72.3 vs nws=68.1, threshold=2.5)'
    """
    import re
    out: dict[str, float | None] = {
        "nws_temp_f": None,
        "nws_disagreement_f": None,
        "veto_threshold_f": None,
    }
    m = re.search(r"mean=([\-\d.]+)\s+vs\s+nws=([\-\d.]+),\s+threshold=([\-\d.]+)", reason)
    if m:
        try:
            mean_f = float(m.group(1))
            nws_f = float(m.group(2))
            thr = float(m.group(3))
            out["nws_temp_f"] = nws_f
            out["nws_disagreement_f"] = abs(mean_f - nws_f)
            out["veto_threshold_f"] = thr
        except ValueError:
            pass
    return out


def log_nws_vetoes(
    session_factory: sessionmaker,
    decisions: list[WeatherEdgeDecision],
) -> int:
    """Write one Event row per SKIP decision whose reason is 'nws_disagrees'."""
    vetoed = [d for d in decisions if d.side == "SKIP" and d.reason.startswith("nws_disagrees")]
    if not vetoed:
        return 0

    with session_factory() as s:
        for d in vetoed:
            payload = _common_payload(d)
            payload["_event_type"] = "bot_d.nws_veto"
            payload.update(_parse_nws_reason(d.reason))
            try:
                payload.update(enrich_payload(payload, reason=d.reason))
            except Exception as exc:
                log.debug("bot_d.audit.veto_label_enrich_failed err=%s", exc)
            s.add(
                Event(
                    bot_id=BOT_ID,
                    event_type="bot_d.nws_veto",
                    severity="info",
                    message=d.reason[:500],
                    payload=payload,
                )
            )
        s.commit()

    log.info("bot_d.nws_veto.logged count=%d", len(vetoed))
    return len(vetoed)


def log_forecast_entry_snapshot(
    session_factory: sessionmaker,
    decision: WeatherEdgeDecision,
    *,
    order_id: str | None,
    size_usd: Any = None,
    limit_price: Any = None,
    depth_usd: Any = None,
    required_depth_usd: Any = None,
) -> None:
    """Write an Event row capturing the forecast state at trade entry.

    Called from the executor loop after a successful ``try_enter``.
    Stored as ``bot_d.forecast_entry`` in the events table.
    """
    payload = _common_payload(decision)
    payload["_event_type"] = "bot_d.forecast_entry"
    payload["side"] = decision.side
    payload["order_id"] = order_id
    payload["size_usd"] = str(size_usd) if size_usd is not None else None
    payload["limit_price"] = str(limit_price) if limit_price is not None else None
    payload["depth_usd"] = str(depth_usd) if depth_usd is not None else None
    payload["required_depth_usd"] = str(required_depth_usd) if required_depth_usd is not None else None
    try:
        payload.update(enrich_payload(payload, reason=decision.reason))
    except Exception as exc:
        log.debug("bot_d.audit.entry_label_enrich_failed err=%s", exc)

    with session_factory() as s:
        s.add(
            Event(
                bot_id=BOT_ID,
                event_type="bot_d.forecast_entry",
                severity="info",
                message=(
                    f"{decision.market.city} {decision.market.date} "
                    f"{decision.market.temp_type} "
                    f"bucket={decision.market.range_low_f}-{decision.market.range_high_f} "
                    f"fc={decision.forecast_mean_f:.1f}±{decision.forecast_std_f:.1f} "
                    f"{decision.side} edge={decision.net_edge:+.3f}"
                )[:500],
                payload=payload,
            )
        )
        s.commit()


def log_entry_attempt_snapshot(
    session_factory: sessionmaker,
    decision: WeatherEdgeDecision,
    *,
    placed: bool,
    reason: str,
    order_id: str | None = None,
    size_usd: Any = None,
    limit_price: Any = None,
    size_shares: Any = None,
    depth_usd: Any = None,
    required_depth_usd: Any = None,
) -> None:
    """Write a non-blocking snapshot for executor accepted/rejected attempts."""
    payload = _common_payload(decision)
    payload["_event_type"] = "bot_d.entry_attempt"
    payload["side"] = decision.side
    payload["placed"] = bool(placed)
    payload["entry_attempt_reason"] = reason
    payload["order_id"] = order_id
    payload["size_usd"] = str(size_usd) if size_usd is not None else None
    payload["size_shares"] = str(size_shares) if size_shares is not None else None
    payload["limit_price"] = str(limit_price) if limit_price is not None else None
    payload["depth_usd"] = str(depth_usd) if depth_usd is not None else None
    payload["required_depth_usd"] = str(required_depth_usd) if required_depth_usd is not None else None
    try:
        payload.update(enrich_payload(payload, reason=reason))
    except Exception as exc:
        log.debug("bot_d.audit.entry_attempt_label_enrich_failed err=%s", exc)

    with session_factory() as s:
        s.add(
            Event(
                bot_id=BOT_ID,
                event_type="bot_d.entry_attempt",
                severity="info",
                message=(
                    f"{decision.market.city} {decision.market.date} "
                    f"{decision.side} placed={placed} reason={reason}"
                )[:500],
                payload=payload,
            )
        )
        s.commit()


def log_scan_summary(
    session_factory: sessionmaker,
    payload: dict[str, Any],
) -> None:
    """Write one compact Event row describing a Bot D scan outcome."""
    message = (
        "evaluated={evaluated} non_skip={non_skip} tradeable={tradeable} "
        "top_abs={top_abs_net_edge:+.3f} top_pos={top_positive_net_edge:+.3f}"
    ).format(
        evaluated=int(payload.get("evaluated") or 0),
        non_skip=int(payload.get("non_skip") or 0),
        tradeable=int(payload.get("tradeable") or 0),
        top_abs_net_edge=float(payload.get("top_abs_net_edge") or 0.0),
        top_positive_net_edge=float(payload.get("top_positive_net_edge") or 0.0),
    )
    with session_factory() as s:
        s.add(
            Event(
                bot_id=BOT_ID,
                event_type="bot_d.scan_summary",
                severity="info",
                message=message[:500],
                payload=payload,
            )
        )
        s.commit()


def log_discovery_health(
    session_factory: sessionmaker,
    payload: dict[str, Any],
) -> None:
    """Write a durable warning when discovery produces no usable markets.

    Service liveness is not enough for Bot D: the process can be healthy while
    Gamma/API contract drift means it sees zero markets. This event gives the
    dashboard and daily reports a DB-level signal to surface.
    """
    raw_markets = int(payload.get("raw_markets") or 0)
    kept_markets = int(payload.get("kept_markets") or 0)
    severity = "warn" if raw_markets == 0 or kept_markets == 0 else "info"
    with session_factory() as s:
        s.add(
            Event(
                bot_id=BOT_ID,
                event_type="bot_d.discovery_health",
                severity=severity,
                message=(
                    f"discovery raw={raw_markets} kept={kept_markets} "
                    f"reason={payload.get('reason') or 'unknown'}"
                )[:500],
                payload=payload,
            )
        )
        s.commit()
