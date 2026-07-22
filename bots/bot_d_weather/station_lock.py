"""Bot D Station Lock — late station-certainty lane.

Classifies exact station-day observations to identify markets where the
bucket outcome is already certain before Polymarket has fully repriced.

Entry point: python -m bots.bot_d_weather.station_lock

Hard constraints:
- Paper by default. Live mode requires BOT_D_STATION_LOCK_PAPER_ONLY=false
  and BOT_D_STATION_LOCK_LIVE_APPROVED_AT.
- Never touches bot_d_live_probe parameters, caps, sizing, or wallet env.
- Bot id is always "bot_d_station_lock" (separate paper ledger).
"""

import logging
import math
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from bots.bot_d_weather.config import (
    BOT_D_REQUIRE_KNOWN_END_DATE,
    BOT_D_REQUIRE_VERIFIED_SETTLEMENT,
    CITIES,
    SETTLEMENT_SPECS,
)
from bots.bot_d_weather.discovery import WeatherMarket, fetch_weather_markets
from bots.bot_d_weather.source_monitor import (
    StationDaySnapshot,
    fetch_station_day_snapshot,
)
from core.clob_v2 import ClobWrapperV2, OrderType, Side
from core.db import Event, Order, get_session_factory, upsert_market_minimal
from core.keystore import Keystore
from core.portfolio import Portfolio
from core.tiny_live_probe import TinyLiveProbeSpec

log = logging.getLogger(__name__)

BOT_ID = "bot_d_station_lock"

# ── Config ────────────────────────────────────────────────────────────────────


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


STATION_LOCK_MIN_EDGE = float(_env("BOT_D_STATION_LOCK_MIN_EDGE", "0.08"))
STATION_LOCK_MAX_PRICE = float(_env("BOT_D_STATION_LOCK_MAX_PRICE", "0.92"))
STATION_LOCK_MIN_PRICE = float(_env("BOT_D_STATION_LOCK_MIN_PRICE", "0.02"))
STATION_LOCK_MAX_STATION_AGE_SEC = int(_env("BOT_D_STATION_LOCK_MAX_STATION_AGE_SEC", "1800"))
STATION_LOCK_MIN_HOURS_AFTER_LOCAL_START = float(
    _env("BOT_D_STATION_LOCK_MIN_HOURS_AFTER_LOCAL_START", "2")
)
STATION_LOCK_ALLOW_SOFT = _env("BOT_D_STATION_LOCK_ALLOW_SOFT", "false").strip().lower() == "true"
STATION_LOCK_PAPER_ONLY = _env("BOT_D_STATION_LOCK_PAPER_ONLY", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
STATION_LOCK_LIVE_APPROVED_AT = _env("BOT_D_STATION_LOCK_LIVE_APPROVED_AT", "").strip()
STATION_LOCK_PAPER_TRADE_USD = Decimal(_env("BOT_D_STATION_LOCK_PAPER_TRADE_USD", "5"))
STATION_LOCK_MAX_DAILY_GROSS_USD = Decimal(_env("BOT_D_STATION_LOCK_MAX_DAILY_GROSS_USD", "20"))
STATION_LOCK_MAX_OPEN_EXPOSURE_USD = Decimal(_env("BOT_D_STATION_LOCK_MAX_OPEN_EXPOSURE_USD", "25"))
STATION_LOCK_MAX_CONCURRENT_POSITIONS = int(_env("BOT_D_STATION_LOCK_MAX_CONCURRENT_POSITIONS", "5"))
STATION_LOCK_SCAN_INTERVAL_S = float(_env("BOT_D_STATION_LOCK_SCAN_INTERVAL_S", "300"))
STATION_LOCK_LIVE_PROBE_SPEC = TinyLiveProbeSpec(
    lane_id="bot_d_station_lock",
    display_name="Bot D Station Lock Tiny Live Probe",
    bot_id=BOT_ID,
    market_scope="Hard station-lock daily weather markets only; soft confidence remains excluded.",
    allowed_actions=("BUY_YES", "BUY_NO"),
    max_order_usd=Decimal("5"),
    daily_gross_cap_usd=Decimal("20"),
    open_exposure_cap_usd=Decimal("25"),
    max_concurrent_positions=5,
    kill_switches=(
        "any classifier/settlement mismatch",
        "2 hard-lock losses",
        "realised P&L <= -$10",
        "stale station data",
        "any live order/reconcile anomaly",
    ),
    rollback_plan=(
        "Stop and disable the live-probe service.",
        "Leave the paper Station Lock service running for evidence collection.",
        "Cancel unresolved live orders only through the existing approved emergency path.",
        "Record the kill event in CHANGELOG, MEMORY, and OQ-112 before any restart.",
    ),
    approval_question=(
        "the operator, approve enabling Bot D Station Lock as a tiny live probe with hard-lock-only "
        "entries, max order $5, daily gross $20, open exposure $25, max 5 concurrent "
        "positions, and the listed kill switches?"
    ),
    live_service_name="polymarket-bot-d-station-lock-live-probe.service",
    notes=("Current runtime remains paper-only until a later ADR and explicit the operator approval.",),
)

# ── Live guard ────────────────────────────────────────────────────────────────


def _live_mode_requested() -> bool:
    bot_d_env = _env("BOT_D_ENV", "paper").strip().lower()
    poly_env = _env("POLYMARKET_ENV", "paper").strip().lower()
    return bot_d_env == "live" or poly_env == "live"


def _effective_paper() -> bool:
    return STATION_LOCK_PAPER_ONLY or not _live_mode_requested()


def _assert_live_allowed() -> None:
    if _live_mode_requested() and STATION_LOCK_PAPER_ONLY:
        raise RuntimeError(
            "StationLock lane is paper-only unless BOT_D_STATION_LOCK_PAPER_ONLY=false"
        )
    if _live_mode_requested() and not STATION_LOCK_LIVE_APPROVED_AT:
        raise RuntimeError("StationLock live mode requires BOT_D_STATION_LOCK_LIVE_APPROVED_AT")


def _assert_paper_only() -> None:
    """Backward-compatible guard name used by older tests and reports."""
    _assert_live_allowed()


def _build_clob() -> ClobWrapperV2:
    if _effective_paper():
        return ClobWrapperV2(keystore=None, paper_override=True)
    from core.config import get_settings

    settings = get_settings()
    keystore = Keystore.load(settings.polymarket_keystore_path, settings.polymarket_passphrase_path)
    clob = ClobWrapperV2(keystore=keystore, paper_override=False)
    clob.load_preflight_from_db()
    return clob


# ── Classifier ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StationLockState:
    """Output of classify_station_lock.

    state: one of unknown, pending, already_yes, already_no,
           locked_yes, locked_no.
    certain_side: BUY_YES / BUY_NO / None
    confidence: hard (unambiguous certainty), soft (in-progress / pending),
                unsafe (rounding disagreement or missing/bad data).
    nearest_int_state: classification using nearest-integer rounding.
    floor_state: classification using floor/truncation rounding.
    rounding_disagreement: True when the two policies give different states.
    """

    state: str
    certain_side: str | None
    confidence: str
    reason: str
    station_metric_f: float | None
    station_metric_native: float | None
    source_age_seconds: int | None
    nearest_int_state: str
    floor_state: str
    rounding_disagreement: bool
    rounding_policy_used: str = "nearest_int"


def _nearest_int_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def _f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def _classify_one(
    temp_type: str,
    direction: str,
    lo: float | None,
    hi: float | None,
    metric: float,
    local_day_complete: bool,
) -> str:
    """Classify bucket state for a single rounded metric.

    All arguments are in the same unit (F or C depending on caller context).
    """
    if temp_type == "high":
        if direction in ("between", "exact"):
            if hi is not None and metric > hi:
                return "already_no"
            if local_day_complete:
                lo_ok = lo is None or metric >= lo
                hi_ok = hi is None or metric <= hi
                return "locked_yes" if (lo_ok and hi_ok) else "locked_no"
            return "pending"
        elif direction == "below":
            if hi is not None and metric > hi:
                return "already_no"
            if local_day_complete:
                return "locked_yes" if (hi is None or metric <= hi) else "locked_no"
            return "pending"
        elif direction in ("above", "higher"):
            if lo is not None and metric >= lo:
                return "already_yes"
            if local_day_complete:
                return "locked_no"
            return "pending"
    else:  # low temp
        if direction in ("between", "exact"):
            if lo is not None and metric < lo:
                return "already_no"
            if local_day_complete:
                lo_ok = lo is None or metric >= lo
                hi_ok = hi is None or metric <= hi
                return "locked_yes" if (lo_ok and hi_ok) else "locked_no"
            return "pending"
        elif direction == "below":
            if hi is not None and metric <= hi:
                return "already_yes"
            if local_day_complete:
                return "locked_no"
            return "pending"
        elif direction in ("above", "higher"):
            if lo is not None and metric < lo:
                return "already_no"
            if local_day_complete:
                return "locked_yes" if (lo is None or metric >= lo) else "locked_no"
            return "pending"
    return "unknown"


_CERTAIN_STATES = frozenset({"already_yes", "already_no", "locked_yes", "locked_no"})


def _certain_side(state: str) -> str | None:
    if state in ("already_yes", "locked_yes"):
        return "BUY_YES"
    if state in ("already_no", "locked_no"):
        return "BUY_NO"
    return None


def classify_station_lock(
    market: WeatherMarket,
    snapshot: StationDaySnapshot,
    *,
    now: datetime | None = None,
    data_source: str = "aviationweather_metar",
    wu_station_seen: str | None = None,
) -> StationLockState:
    """Pure classifier: StationLockState from a market + station snapshot.

    Computes two rounding counterfactuals (nearest_int, floor) and flags
    disagreement as confidence='unsafe'. Classification runs in the market's
    native unit so Celsius markets round in Celsius before bucket comparison.

    WU station mutation guard fires only when data_source='wunderground'.
    """
    _now = now or datetime.now(UTC)
    spec = SETTLEMENT_SPECS.get(market.city)
    unit = spec.unit if spec else (market.unit or "F")

    # WU station mutation guard
    if data_source == "wunderground":
        expected_station = spec.station if spec else None
        if wu_station_seen is None:
            return StationLockState(
                state="unknown",
                certain_side=None,
                confidence="unsafe",
                reason="wu_station_unknown",
                station_metric_f=None,
                station_metric_native=None,
                source_age_seconds=None,
                nearest_int_state="unknown",
                floor_state="unknown",
                rounding_disagreement=False,
            )
        if expected_station is not None and wu_station_seen != expected_station:
            return StationLockState(
                state="unknown",
                certain_side=None,
                confidence="unsafe",
                reason=(
                    f"wu_station_mutation:"
                    f"expected={expected_station},seen={wu_station_seen}"
                ),
                station_metric_f=None,
                station_metric_native=None,
                source_age_seconds=None,
                nearest_int_state="unknown",
                floor_state="unknown",
                rounding_disagreement=False,
            )

    raw_f = snapshot.raw_max_f if market.temp_type == "high" else snapshot.raw_min_f
    metric_at = (
        snapshot.raw_max_observed_at
        if market.temp_type == "high"
        else snapshot.raw_min_observed_at
    )

    if raw_f is None:
        return StationLockState(
            state="unknown",
            certain_side=None,
            confidence="unsafe",
            reason="no_station_data",
            station_metric_f=None,
            station_metric_native=None,
            source_age_seconds=None,
            nearest_int_state="unknown",
            floor_state="unknown",
            rounding_disagreement=False,
        )

    # Bucket bounds in F (WeatherMarket always stores F).
    lo_f = float(market.range_low_f) if market.range_low_f is not None else None
    hi_f = float(market.range_high_f) if market.range_high_f is not None else None
    complete = snapshot.local_day_complete

    if unit == "C":
        # Classify in Celsius: round station in C, compare against C bounds.
        # Celsius markets have integer C bucket bounds stored as exact F equivalents
        # so the reverse conversion is lossless for integer values.
        raw_native = _f_to_c(raw_f)
        lo = _f_to_c(lo_f) if lo_f is not None else None
        hi = _f_to_c(hi_f) if hi_f is not None else None
        nearest_metric = float(_nearest_int_half_up(raw_native))
        floor_metric = float(math.floor(raw_native))
        station_metric_f = _c_to_f(nearest_metric)
        station_metric_native = nearest_metric
    else:
        raw_native = raw_f
        lo = lo_f
        hi = hi_f
        nearest_metric = float(_nearest_int_half_up(raw_f))
        floor_metric = float(math.floor(raw_f))
        station_metric_f = nearest_metric
        station_metric_native = nearest_metric

    nearest_state = _classify_one(
        market.temp_type, market.direction, lo, hi, nearest_metric, complete
    )
    floor_state_val = _classify_one(
        market.temp_type, market.direction, lo, hi, floor_metric, complete
    )

    rounding_disagreement = nearest_state != floor_state_val

    if rounding_disagreement:
        state = "pending"
        confidence = "unsafe"
        reason = (
            f"rounding_disagreement:nearest_int={nearest_state},floor={floor_state_val}"
        )
        side = None
    elif nearest_state in _CERTAIN_STATES:
        state = nearest_state
        confidence = "hard"
        reason = f"hard_certainty:{state}"
        side = _certain_side(state)
    else:
        state = nearest_state
        confidence = "soft"
        reason = f"classified:{state}"
        side = _certain_side(state)

    source_age: int | None = None
    if metric_at is not None:
        source_age = int((_now - metric_at).total_seconds())

    return StationLockState(
        state=state,
        certain_side=side,
        confidence=confidence,
        reason=reason,
        station_metric_f=station_metric_f,
        station_metric_native=station_metric_native,
        source_age_seconds=source_age,
        nearest_int_state=nearest_state,
        floor_state=floor_state_val,
        rounding_disagreement=rounding_disagreement,
    )


# ── Entry gate ────────────────────────────────────────────────────────────────


def _skip_reason(
    market: WeatherMarket,
    lock: StationLockState,
    yes_price: float,
    *,
    now: datetime,
    open_exposure_usd: Decimal,
) -> str | None:
    """Return a skip reason code or None if entry is allowed."""
    spec = SETTLEMENT_SPECS.get(market.city)
    if BOT_D_REQUIRE_VERIFIED_SETTLEMENT and (spec is None or not spec.verified):
        return "unverified_settlement"
    if spec is None:
        return "no_settlement_spec"
    if BOT_D_REQUIRE_KNOWN_END_DATE and market.end_date is None:
        return "missing_end_date"
    if lock.confidence == "unsafe":
        return f"unsafe_confidence:{lock.reason}"
    if lock.certain_side is None:
        return "no_certain_side"
    if lock.confidence == "soft" and not STATION_LOCK_ALLOW_SOFT:
        return "soft_confidence_not_allowed"
    if lock.source_age_seconds is not None and lock.source_age_seconds > STATION_LOCK_MAX_STATION_AGE_SEC:
        return f"station_too_stale:{lock.source_age_seconds}s"
    if open_exposure_usd >= STATION_LOCK_LIVE_PROBE_SPEC.open_exposure_cap_usd:
        return "open_exposure_cap"
    local_hours = _hours_after_local_start(market, now)
    if local_hours is not None and local_hours < STATION_LOCK_MIN_HOURS_AFTER_LOCAL_START:
        return f"too_early_local_day:{local_hours:.2f}h"
    price = yes_price if lock.certain_side == "BUY_YES" else 1.0 - yes_price
    if price < STATION_LOCK_MIN_PRICE or price > STATION_LOCK_MAX_PRICE:
        return f"price_out_of_range:{price:.3f}"
    edge = 1.0 - price - 0.02  # 2% fee/slippage buffer
    if edge < STATION_LOCK_MIN_EDGE:
        return f"edge_too_small:{edge:.3f}"
    if open_exposure_usd + STATION_LOCK_PAPER_TRADE_USD > STATION_LOCK_MAX_OPEN_EXPOSURE_USD:
        return "open_exposure_cap"
    return None


# ── Audit events ──────────────────────────────────────────────────────────────


def _emit_event(
    session_factory: Any,
    event_type: str,
    message: str,
    payload: dict[str, Any],
) -> None:
    with session_factory() as session:
        session.add(
            Event(
                bot_id=BOT_ID,
                event_type=event_type,
                severity="info",
                message=message,
                payload=payload,
            )
        )
        session.commit()


def _entry_exists(session_factory: Any, condition_id: str) -> bool:
    """Return True if we already have a paper entry for this condition."""
    from sqlalchemy import select as sa_select

    with session_factory() as session:
        return session.execute(
            sa_select(Event.id)
            .where(
                Event.bot_id == BOT_ID,
                Event.event_type == "bot_d.station_lock.entry_attempt",
                Event.payload["condition_id"].as_string() == condition_id,
            )
            .limit(1)
        ).scalar_one_or_none() is not None


def _daily_gross_usd(session_factory: Any, *, today: str) -> Decimal:
    """Sum paper trade USD entered on the current UTC day."""
    from sqlalchemy import select as sa_select

    start = datetime.fromisoformat(f"{today}T00:00:00+00:00")
    with session_factory() as session:
        rows = session.execute(
            sa_select(Event.payload)
            .where(
                Event.bot_id == BOT_ID,
                Event.event_type == "bot_d.station_lock.entry_attempt",
            )
        ).scalars().all()
        live_orders = session.execute(
            sa_select(Order.price, Order.size).where(
                Order.bot_id == BOT_ID,
                Order.side == "BUY",
                Order.placed_at >= start,
            )
        ).all()
    total = Decimal("0")
    for payload in rows:
        p = payload if isinstance(payload, dict) else {}
        entry_day = str(p.get("entry_date") or str(p.get("entry_time") or "")[:10])
        if entry_day == today:
            total += Decimal(str(p.get("trade_usd", p.get("paper_trade_usd", "0")) or "0"))
    for price, size in live_orders:
        total += Decimal(str(price or 0)) * Decimal(str(size or 0))
    return total


def _open_exposure_usd(session_factory: Any) -> Decimal:
    """Sum unresolved paper fill cost for the station-lock lane."""
    from sqlalchemy import select as sa_select

    with session_factory() as session:
        fills = session.execute(
            sa_select(Event.payload).where(
                Event.bot_id == BOT_ID,
                Event.event_type == "bot_d.station_lock.paper_fill",
            )
        ).scalars().all()
        resolved = session.execute(
            sa_select(Event.payload).where(
                Event.bot_id == BOT_ID,
                Event.event_type == "bot_d.station_lock.resolution",
            )
        ).scalars().all()

    resolved_cids = {
        p.get("condition_id")
        for p in resolved
        if isinstance(p, dict) and p.get("condition_id")
    }
    total = Portfolio(session_factory).get_total_exposure(BOT_ID)
    with session_factory() as session:
        open_orders = session.execute(
            sa_select(Order.price, Order.size).where(
                Order.bot_id == BOT_ID,
                Order.side == "BUY",
                Order.status.in_(("OPEN", "PARTIAL", "live", "PAPER_OPEN")),
            )
        ).all()
    for price, size in open_orders:
        total += Decimal(str(price or 0)) * Decimal(str(size or 0))
    for payload in fills:
        p = payload if isinstance(payload, dict) else {}
        cid = p.get("condition_id")
        if cid and cid not in resolved_cids:
            total += Decimal(str(p.get("paper_trade_usd", "0") or "0"))
    return total


def _open_position_count(session_factory: Any) -> int:
    """Count unresolved station-lock fills by condition."""
    from sqlalchemy import select as sa_select

    with session_factory() as session:
        fills = session.execute(
            sa_select(Event.payload).where(
                Event.bot_id == BOT_ID,
                Event.event_type == "bot_d.station_lock.paper_fill",
            )
        ).scalars().all()
        resolved = session.execute(
            sa_select(Event.payload).where(
                Event.bot_id == BOT_ID,
                Event.event_type == "bot_d.station_lock.resolution",
            )
        ).scalars().all()

    resolved_cids = {
        p.get("condition_id")
        for p in resolved
        if isinstance(p, dict) and p.get("condition_id")
    }
    open_cids = {
        p.get("condition_id")
        for p in fills
        if isinstance(p, dict) and p.get("condition_id") and p.get("condition_id") not in resolved_cids
    }
    return len(open_cids)


def _hours_after_local_start(market: WeatherMarket, now: datetime) -> float | None:
    cfg = CITIES.get(market.city)
    if cfg is None:
        return None
    try:
        tz = ZoneInfo(cfg.timezone)
        local_now = now.astimezone(tz)
        market_date = datetime.strptime(market.date, "%Y-%m-%d").date()
        local_start = datetime.combine(market_date, datetime.min.time(), tzinfo=tz)
        return (local_now - local_start).total_seconds() / 3600
    except Exception:
        return None


def _market_from_payload(payload: dict[str, Any]) -> WeatherMarket:
    return WeatherMarket(
        gamma_id=str(payload["condition_id"]),
        slug=str(payload.get("slug") or payload["condition_id"]),
        question=str(payload.get("question") or ""),
        city=str(payload["city"]),
        date=str(payload["date"]),
        temp_type=str(payload["temp_type"]),
        direction=str(payload["direction"]),
        range_low_f=payload.get("bucket_low_f"),
        range_high_f=payload.get("bucket_high_f"),
        unit=str(payload.get("unit") or "F"),
        yes_token_id=str(payload.get("yes_token_id") or ""),
        no_token_id=str(payload.get("no_token_id") or ""),
        yes_price=Decimal(str(payload.get("market_probability") or "0.5")),
        volume_24h_usd=Decimal("0"),
        end_date=None,
    )


def _native_bucket_bounds(market: WeatherMarket, spec: Any) -> tuple[float | None, float | None]:
    unit = spec.unit if spec else (market.unit or "F")
    low = float(market.range_low_f) if market.range_low_f is not None else None
    high = float(market.range_high_f) if market.range_high_f is not None else None
    if unit == "C":
        low = _f_to_c(low) if low is not None else None
        high = _f_to_c(high) if high is not None else None
    return low, high


def _record_resolutions(
    session_factory: Any,
    *,
    client: httpx.Client | None,
    now: datetime,
) -> int:
    """Append resolution events for completed unresolved station-lock fills."""
    from sqlalchemy import select as sa_select

    with session_factory() as session:
        fills = session.execute(
            sa_select(Event.payload).where(
                Event.bot_id == BOT_ID,
                Event.event_type == "bot_d.station_lock.paper_fill",
            )
        ).scalars().all()
        resolved = session.execute(
            sa_select(Event.payload).where(
                Event.bot_id == BOT_ID,
                Event.event_type == "bot_d.station_lock.resolution",
            )
        ).scalars().all()

    resolved_cids = {
        p.get("condition_id")
        for p in resolved
        if isinstance(p, dict) and p.get("condition_id")
    }
    written = 0
    for payload in fills:
        p = payload if isinstance(payload, dict) else {}
        cid = p.get("condition_id")
        if not cid or cid in resolved_cids:
            continue
        try:
            market = _market_from_payload(p)
            snapshot = fetch_station_day_snapshot(market.city, market.date, client=client, now=now)
        except Exception as exc:
            log.debug("bot_d.station_lock.resolution_fetch_failed cid=%s err=%s", cid, exc)
            continue
        if not snapshot.local_day_complete:
            continue
        lock = classify_station_lock(
            market,
            snapshot,
            now=now,
            data_source="aviationweather_metar",
            wu_station_seen=None,
        )
        if lock.certain_side is None or lock.confidence == "unsafe":
            continue
        entry_side = str(p.get("certain_side"))
        resolved_correct = lock.certain_side == entry_side
        paper_usd = Decimal(str(p.get("paper_trade_usd", "0") or "0"))
        price = Decimal(str(p.get("certain_side_price", "0") or "0"))
        shares = Decimal(str(p.get("paper_shares", "0") or "0"))
        payout = shares if resolved_correct else Decimal("0")
        pnl = payout - paper_usd
        _emit_event(
            session_factory,
            "bot_d.station_lock.resolution",
            f"RESOLUTION cid={cid} correct={resolved_correct}",
            {
                **p,
                "resolved_at": now.isoformat(),
                "resolved_state": lock.state,
                "resolved_side": lock.certain_side,
                "resolved_correct": resolved_correct,
                "resolution_confidence": lock.confidence,
                "resolution_reason": lock.reason,
                "resolution_station_metric_f": lock.station_metric_f,
                "resolution_station_metric_native": lock.station_metric_native,
                "paper_payout_usd": str(payout.quantize(Decimal("0.0001"))),
                "paper_realised_pnl_usd": str(pnl.quantize(Decimal("0.0001"))),
                "paper_entry_price": str(price),
            },
        )
        written += 1
    return written


# ── Scan ─────────────────────────────────────────────────────────────────────


def run_station_lock_scan(
    *,
    session_factory: Any = None,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    clob: ClobWrapperV2 | None = None,
) -> dict[str, int]:
    """Run one station-lock scan pass. Returns counts dict."""
    _assert_live_allowed()

    sf = session_factory or get_session_factory()
    _now = now or datetime.now(UTC)
    today = _now.strftime("%Y-%m-%d")

    counts: dict[str, int] = {
        "markets_scanned": 0,
        "candidates": 0,
        "entries": 0,
        "skips": 0,
        "fills": 0,
        "resolutions": 0,
    }

    counts["resolutions"] = _record_resolutions(sf, client=client, now=_now)

    try:
        markets = fetch_weather_markets(client=client)
    except Exception as exc:
        log.error("bot_d.station_lock.discovery_failed err=%s", exc)
        return counts

    counts["markets_scanned"] = len(markets)

    daily_gross = _daily_gross_usd(sf, today=today)
    open_exposure = _open_exposure_usd(sf)

    for market in markets:
        try:
            daily_gross, open_exposure = _process_market(
                market,
                sf=sf,
                client=client,
                now=_now,
                today=today,
                daily_gross=daily_gross,
                open_exposure=open_exposure,
                counts=counts,
                clob=clob,
            )
        except Exception as exc:
            log.error(
                "bot_d.station_lock.market_error gamma_id=%s err=%s",
                market.gamma_id,
                exc,
            )

    log.info(
        "bot_d.station_lock.scan_done scanned=%d candidates=%d entries=%d skips=%d",
        counts["markets_scanned"],
        counts["candidates"],
        counts["entries"],
        counts["skips"],
    )
    return counts


def _process_market(
    market: WeatherMarket,
    *,
    sf: Any,
    client: httpx.Client | None,
    now: datetime,
    today: str,
    daily_gross: Decimal,
    open_exposure: Decimal,
    counts: dict[str, int],
    clob: ClobWrapperV2 | None = None,
) -> tuple[Decimal, Decimal]:
    spec = SETTLEMENT_SPECS.get(market.city)
    if spec is None:
        _emit_event(
            sf,
            "bot_d.station_lock.skip",
            f"no_settlement_spec city={market.city}",
            {
                "bot_id": BOT_ID,
                "condition_id": market.gamma_id,
                "city": market.city,
                "date": market.date,
                "skip_reason_code": "no_settlement_spec",
            },
        )
        counts["skips"] += 1
        return daily_gross, open_exposure

    try:
        snapshot = fetch_station_day_snapshot(market.city, market.date, client=client, now=now)
    except Exception as exc:
        log.warning(
            "bot_d.station_lock.snapshot_failed city=%s date=%s err=%s",
            market.city,
            market.date,
            exc,
        )
        counts["skips"] += 1
        return daily_gross, open_exposure

    lock = classify_station_lock(
        market,
        snapshot,
        now=now,
        data_source="aviationweather_metar",
        wu_station_seen=None,
    )
    yes_price = float(market.yes_price) if market.yes_price else 0.5

    if lock.certain_side == "BUY_YES":
        entry_price = yes_price
    elif lock.certain_side == "BUY_NO":
        entry_price = 1.0 - yes_price
    else:
        entry_price = None

    native_low, native_high = _native_bucket_bounds(market, spec)
    expected_station = spec.station

    candidate_payload: dict[str, Any] = {
        "bot_id": BOT_ID,
        "city": market.city,
        "station": snapshot.station,
        "date": market.date,
        "temp_type": market.temp_type,
        "direction": market.direction,
        "bucket_low_f": float(market.range_low_f) if market.range_low_f is not None else None,
        "bucket_high_f": float(market.range_high_f) if market.range_high_f is not None else None,
        "bucket_low_native": native_low,
        "bucket_high_native": native_high,
        "unit": market.unit,
        "question": market.question,
        "slug": market.slug,
        "yes_token_id": market.yes_token_id,
        "no_token_id": market.no_token_id,
        "state": lock.state,
        "certain_side": lock.certain_side,
        "confidence": lock.confidence,
        "reason": lock.reason,
        "station_metric_native": lock.station_metric_native,
        "station_metric_f": lock.station_metric_f,
        "latest_observed_at": (
            snapshot.raw_max_observed_at.isoformat()
            if market.temp_type == "high" and snapshot.raw_max_observed_at
            else snapshot.raw_min_observed_at.isoformat()
            if market.temp_type == "low" and snapshot.raw_min_observed_at
            else None
        ),
        "source_age_seconds": lock.source_age_seconds,
        "source": "aviationweather_metar",
        "settlement_source": snapshot.source,
        "wu_station_expected": expected_station,
        "wu_station_seen": None,
        "rounding_policy_used": lock.rounding_policy_used,
        "nearest_int_state": lock.nearest_int_state,
        "floor_state": lock.floor_state,
        "rounding_disagreement": lock.rounding_disagreement,
        "market_probability": yes_price,
        "certain_side_price": entry_price,
        "edge_after_buffer": round(1.0 - entry_price - 0.02, 4) if entry_price is not None else None,
        "condition_id": market.gamma_id,
        "skip_reason_code": None,
    }

    _emit_event(
        sf,
        "bot_d.station_lock.candidate",
        f"city={market.city} state={lock.state} confidence={lock.confidence}",
        candidate_payload,
    )
    counts["candidates"] += 1

    skip = _skip_reason(
        market,
        lock,
        yes_price,
        now=now,
        open_exposure_usd=open_exposure,
    )
    if skip:
        _emit_event(
            sf,
            "bot_d.station_lock.skip",
            f"city={market.city} skip={skip}",
            {**candidate_payload, "skip_reason_code": skip},
        )
        counts["skips"] += 1
        return daily_gross, open_exposure

    if _entry_exists(sf, market.gamma_id):
        counts["skips"] += 1
        return daily_gross, open_exposure

    if _open_position_count(sf) >= STATION_LOCK_MAX_CONCURRENT_POSITIONS:
        _emit_event(
            sf,
            "bot_d.station_lock.skip",
            f"city={market.city} skip=max_concurrent_positions",
            {**candidate_payload, "skip_reason_code": "max_concurrent_positions"},
        )
        counts["skips"] += 1
        return daily_gross, open_exposure

    if daily_gross + STATION_LOCK_PAPER_TRADE_USD > STATION_LOCK_MAX_DAILY_GROSS_USD:
        _emit_event(
            sf,
            "bot_d.station_lock.skip",
            f"city={market.city} skip=daily_gross_cap",
            {**candidate_payload, "skip_reason_code": "daily_gross_cap"},
        )
        counts["skips"] += 1
        return daily_gross, open_exposure

    paper_shares = (
        STATION_LOCK_PAPER_TRADE_USD / Decimal(str(entry_price))
        if entry_price and entry_price > 0
        else Decimal("0")
    ).quantize(Decimal("0.0001"))
    entry_payload = {
        **candidate_payload,
        "paper_trade_usd": str(STATION_LOCK_PAPER_TRADE_USD),
        "trade_usd": str(STATION_LOCK_PAPER_TRADE_USD),
        "paper_shares": str(paper_shares),
        "entry_time": now.isoformat(),
        "entry_date": today,
        "execution_mode": "paper" if _effective_paper() else "live",
    }
    token_id = market.yes_token_id if lock.certain_side == "BUY_YES" else market.no_token_id
    price = Decimal(str(entry_price)).quantize(Decimal("0.001"))
    if _effective_paper():
        _emit_event(
            sf,
            "bot_d.station_lock.entry_attempt",
            f"PAPER_ENTRY city={market.city} side={lock.certain_side} price={entry_price:.3f}",
            entry_payload,
        )
        _emit_event(
            sf,
            "bot_d.station_lock.paper_fill",
            f"PAPER_FILL city={market.city} side={lock.certain_side} price={entry_price:.3f}",
            entry_payload,
        )
    else:
        if clob is None:
            raise RuntimeError("StationLock live mode requires CLOB client")
        resp = clob.place_limit(
            token_id=token_id,
            price=price,
            size=paper_shares,
            side=Side.BUY,
            order_type=OrderType.GTC,
        )
        if not resp.order_id:
            _emit_event(
                sf,
                "bot_d.station_lock.live_order_rejected",
                f"LIVE_REJECT city={market.city} side={lock.certain_side} status={resp.status}",
                {**entry_payload, "order_status": resp.status},
            )
            counts["skips"] += 1
            return daily_gross, open_exposure
        with sf() as session:
            upsert_market_minimal(
                session,
                condition_id=market.gamma_id,
                category="weather",
                question=market.question,
                yes_token_id=market.yes_token_id,
                no_token_id=market.no_token_id,
                end_date=market.end_date,
                yes_price=market.yes_price,
                volume_24h_usd=market.volume_24h_usd,
            )
            session.add(
                Order(
                    order_id=resp.order_id,
                    bot_id=BOT_ID,
                    condition_id=market.gamma_id,
                    token_id=token_id,
                    side="BUY",
                    price=price,
                    size=paper_shares,
                    status=resp.status or "OPEN",
                    order_type="GTC",
                )
            )
            session.add(
                Event(
                    bot_id=BOT_ID,
                    event_type="bot_d.station_lock.entry_attempt",
                    severity="info",
                    message=f"LIVE_ENTRY city={market.city} side={lock.certain_side} price={entry_price:.3f}",
                    payload={**entry_payload, "order_id": resp.order_id},
                )
            )
            session.commit()
    daily_gross += STATION_LOCK_PAPER_TRADE_USD
    open_exposure += STATION_LOCK_PAPER_TRADE_USD
    counts["entries"] += 1
    if _effective_paper():
        counts["fills"] += 1
    log.info(
        "bot_d.station_lock.%s_entry city=%s side=%s price=%.3f state=%s",
        "paper" if _effective_paper() else "live",
        market.city,
        lock.certain_side,
        entry_price,
        lock.state,
    )
    return daily_gross, open_exposure


# ── Loop ─────────────────────────────────────────────────────────────────────


def run_loop() -> None:
    """Continuous scan loop. Terminates on KeyboardInterrupt."""
    _assert_live_allowed()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    clob = _build_clob()
    log.info(
        "bot_d.station_lock.start bot_id=%s interval_s=%s mode=%s",
        BOT_ID,
        STATION_LOCK_SCAN_INTERVAL_S,
        "paper" if _effective_paper() else "live",
    )
    with httpx.Client(timeout=30) as client:
        while True:
            try:
                if not _effective_paper():
                    Portfolio().reconcile_live_fills(clob, BOT_ID, require_known_order=True)
                run_station_lock_scan(client=client, clob=clob)
            except Exception as exc:
                log.error("bot_d.station_lock.scan_error err=%s", exc)
            time.sleep(STATION_LOCK_SCAN_INTERVAL_S)


def main() -> int:
    _assert_live_allowed()
    run_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
