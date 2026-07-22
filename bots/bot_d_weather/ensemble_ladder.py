"""Bot D Ensemble Ladder paper lane.

Paper-only research lane for the weather-basket idea described in the
2026-05-16 operator review: use station-exact ICON/GFS/ECMWF forecasts to
buy a small basket of adjacent YES temperature buckets for one city/date/event.

This module intentionally does not import the CLOB client and never writes
Order, Trade, or Position rows. It records candidate baskets as Event rows so
the lane can be audited before any live proposal.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.orm import sessionmaker

from bots.bot_d_weather.config import CITIES, SETTLEMENT_SPECS, forecast_coordinates
from bots.bot_d_weather.discovery import WeatherMarket, fetch_weather_markets
from core.db import Event, get_session_factory, init_db

log = logging.getLogger(__name__)

BOT_ID = os.getenv("BOT_D_ENSEMBLE_LADDER_BOT_ID", "bot_d_ensemble_ladder")
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MODEL_NAMES = ("icon", "gfs", "ecmwf")
MODEL_PARAM = os.getenv(
    "BOT_D_ENSEMBLE_LADDER_MODELS",
    "icon_seamless,gfs_seamless,ecmwf_ifs025",
)

WIN_MIN_H = float(os.getenv("BOT_D_ENSEMBLE_LADDER_WIN_MIN_H", "18"))
WIN_MAX_H = float(os.getenv("BOT_D_ENSEMBLE_LADDER_WIN_MAX_H", "30"))
PAIR_AGREE_C = float(os.getenv("BOT_D_ENSEMBLE_LADDER_PAIR_AGREE_C", "1.0"))
MAX_SPREAD_C = float(os.getenv("BOT_D_ENSEMBLE_LADDER_MAX_SPREAD_C", "3.0"))
MIN_LEG_PRICE = Decimal(os.getenv("BOT_D_ENSEMBLE_LADDER_MIN_LEG_PRICE", "0.01"))
MAX_LEG_PRICE = Decimal(os.getenv("BOT_D_ENSEMBLE_LADDER_MAX_LEG_PRICE", "0.45"))
MAX_BASKET_PRICE = Decimal(os.getenv("BOT_D_ENSEMBLE_LADDER_MAX_BASKET_PRICE", "0.95"))
STAKE_PER_LEG_USD = Decimal(os.getenv("BOT_D_ENSEMBLE_LADDER_STAKE_PER_LEG_USD", "2"))
SCAN_INTERVAL_S = float(os.getenv("BOT_D_ENSEMBLE_LADDER_SCAN_INTERVAL_S", "600"))
REQUIRE_VERIFIED_SETTLEMENT = os.getenv(
    "BOT_D_ENSEMBLE_LADDER_REQUIRE_VERIFIED_SETTLEMENT", "true"
).lower() not in {"0", "false", "no"}
REQUIRE_KNOWN_END_DATE = os.getenv(
    "BOT_D_ENSEMBLE_LADDER_REQUIRE_KNOWN_END_DATE", "true"
).lower() not in {"0", "false", "no"}
SHADOW_BIAS_CORRECTION = os.getenv(
    "BOT_D_ENSEMBLE_LADDER_SHADOW_BIAS_CORRECTION", "true"
).lower() in {"1", "true", "yes"}


def _c_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def _f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _assert_paper_only() -> None:
    if os.getenv("POLYMARKET_ENV", "paper").lower() == "live":
        raise RuntimeError("bot_d_ensemble_ladder is paper-only: POLYMARKET_ENV=live")
    if os.getenv("BOT_D_ENV", "paper").lower() == "live":
        raise RuntimeError("bot_d_ensemble_ladder is paper-only: BOT_D_ENV=live")


@dataclass(frozen=True)
class ThreeModelForecast:
    city: str
    date: str
    model_highs_c: dict[str, float]
    model_lows_c: dict[str, float]
    fetched_at: datetime
    model_timestamp: str | None = None
    bias_correction_param_sent: bool = False

    def model_values_native(self, market: WeatherMarket) -> dict[str, float]:
        source = self.model_highs_c if market.temp_type == "high" else self.model_lows_c
        if market.unit == "C":
            return dict(source)
        return {name: _c_to_f(value) for name, value in source.items()}


@dataclass(frozen=True)
class LadderLeg:
    market: WeatherMarket
    yes_price: Decimal
    bucket_low_native: float
    bucket_high_native: float
    midpoint_native: float


@dataclass(frozen=True)
class LadderPlan:
    event_key: str
    city: str
    date: str
    temp_type: str
    unit: str
    center_native: float
    outlier_model: str | None
    outlier_native: float | None
    closest_pair: tuple[str, str]
    closest_pair_gap_c: float
    model_spread_c: float
    model_values_native: dict[str, float]
    legs: tuple[LadderLeg, ...]
    total_price: Decimal
    stake_per_leg_usd: Decimal
    reason: str


def _event_key(city: str, date: str, temp_type: str) -> str:
    return f"{city}|{date}|{temp_type}"


def _hours_to_end(market: WeatherMarket, *, now: datetime | None = None) -> float | None:
    if market.end_date is None:
        return None
    end = market.end_date if market.end_date.tzinfo else market.end_date.replace(tzinfo=UTC)
    return (end - (now or _utc_now())).total_seconds() / 3600


def _bounded_bucket_native(market: WeatherMarket) -> tuple[float, float] | None:
    if market.direction != "between":
        return None
    if market.range_low_f is None or market.range_high_f is None:
        return None
    if market.unit == "C":
        return _f_to_c(market.range_low_f), _f_to_c(market.range_high_f)
    return market.range_low_f, market.range_high_f


def _leg_from_market(market: WeatherMarket) -> LadderLeg | None:
    bounds = _bounded_bucket_native(market)
    if bounds is None or market.yes_price is None:
        return None
    low, high = bounds
    return LadderLeg(
        market=market,
        yes_price=Decimal(str(market.yes_price)),
        bucket_low_native=low,
        bucket_high_native=high,
        midpoint_native=(low + high) / 2.0,
    )


def candidate_markets(markets: list[WeatherMarket], *, now: datetime | None = None) -> list[WeatherMarket]:
    """Filter to paper-ladder candidates without touching live policy."""
    out: list[WeatherMarket] = []
    ref = now or _utc_now()
    for market in markets:
        if REQUIRE_VERIFIED_SETTLEMENT:
            spec = SETTLEMENT_SPECS.get(market.city)
            if spec is None or not spec.verified or not spec.station:
                continue
        if REQUIRE_KNOWN_END_DATE and market.end_date is None:
            continue
        hours = _hours_to_end(market, now=ref)
        if hours is None:
            continue
        if hours <= 0 or hours < WIN_MIN_H or hours > WIN_MAX_H:
            continue
        if _bounded_bucket_native(market) is None:
            continue
        if market.yes_price is None:
            continue
        out.append(market)
    return out


def _forecast_key(raw_key: str) -> str | None:
    key = raw_key.lower()
    if "icon" in key:
        return "icon"
    if "gfs" in key:
        return "gfs"
    if "ecmwf" in key:
        return "ecmwf"
    return None


def fetch_three_model_forecasts(
    city: str,
    dates: list[str],
    *,
    client: httpx.Client | None = None,
) -> dict[str, ThreeModelForecast]:
    """Fetch deterministic ICON/GFS/ECMWF temperatures for one station city."""
    if not dates:
        return {}
    cfg = CITIES[city]
    lat, lon = forecast_coordinates(city)
    owns = client is None
    c = client or httpx.Client(timeout=30.0, headers={"User-Agent": "bot-d-ensemble-ladder/0.1"})
    fetched_at = _utc_now()
    params: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m",
        "temperature_unit": "celsius",
        "timezone": cfg.timezone,
        "models": MODEL_PARAM,
        "start_date": min(dates),
        "end_date": max(dates),
    }
    if SHADOW_BIAS_CORRECTION:
        # Open-Meteo currently accepts this parameter, but it is treated as
        # shadow metadata until official documentation confirms its effect.
        params["bias_correction"] = "true"
    try:
        resp = c.get(FORECAST_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("ensemble_ladder.forecast_failed city=%s error=%s", city, exc)
        return {}
    finally:
        if owns:
            c.close()

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    date_set = set(dates)
    by_model_date: dict[str, dict[str, list[float]]] = {
        model: {date: [] for date in dates} for model in MODEL_NAMES
    }
    for key, values in hourly.items():
        if not str(key).startswith("temperature_2m"):
            continue
        model = _forecast_key(str(key))
        if model is None or not isinstance(values, list):
            continue
        for i, ts in enumerate(times):
            if i >= len(values) or values[i] is None:
                continue
            date = str(ts)[:10]
            if date in date_set:
                try:
                    by_model_date[model][date].append(float(values[i]))
                except (TypeError, ValueError):
                    continue

    out: dict[str, ThreeModelForecast] = {}
    for date in dates:
        highs: dict[str, float] = {}
        lows: dict[str, float] = {}
        for model in MODEL_NAMES:
            vals = by_model_date[model][date]
            if vals:
                highs[model] = max(vals)
                lows[model] = min(vals)
        if set(MODEL_NAMES).issubset(highs) and set(MODEL_NAMES).issubset(lows):
            out[date] = ThreeModelForecast(
                city=city,
                date=date,
                model_highs_c=highs,
                model_lows_c=lows,
                fetched_at=fetched_at,
                model_timestamp=str(data.get("model_run") or data.get("model_run_at") or "") or None,
                bias_correction_param_sent=SHADOW_BIAS_CORRECTION,
            )
    return out


def _closest_pair(values_c: dict[str, float]) -> tuple[tuple[str, str], float]:
    pairs = [
        (("icon", "gfs"), abs(values_c["icon"] - values_c["gfs"])),
        (("icon", "ecmwf"), abs(values_c["icon"] - values_c["ecmwf"])),
        (("gfs", "ecmwf"), abs(values_c["gfs"] - values_c["ecmwf"])),
    ]
    return min(pairs, key=lambda item: item[1])


def _find_center_leg(legs: list[LadderLeg], center: float) -> LadderLeg | None:
    if not legs:
        return None
    containing = [
        leg
        for leg in legs
        if leg.bucket_low_native <= center <= leg.bucket_high_native
    ]
    if containing:
        return min(containing, key=lambda leg: abs(leg.midpoint_native - center))
    return min(legs, key=lambda leg: abs(leg.midpoint_native - center))


def _adjacent_leg(
    legs: list[LadderLeg],
    current: LadderLeg,
    direction: str,
) -> LadderLeg | None:
    ordered = sorted(legs, key=lambda leg: leg.midpoint_native)
    try:
        idx = next(i for i, leg in enumerate(ordered) if leg.market.gamma_id == current.market.gamma_id)
    except StopIteration:
        return None
    next_idx = idx + 1 if direction == "above" else idx - 1
    if 0 <= next_idx < len(ordered):
        return ordered[next_idx]
    return None


def build_ladder_plan(
    markets: list[WeatherMarket],
    forecast: ThreeModelForecast,
) -> tuple[LadderPlan | None, str]:
    """Build a 2-3 leg YES basket for one city/date/temp event."""
    if not markets:
        return None, "empty_event"
    market0 = markets[0]
    values_c = forecast.model_highs_c if market0.temp_type == "high" else forecast.model_lows_c
    if not set(MODEL_NAMES).issubset(values_c):
        return None, "missing_three_model_panel"
    spread_c = max(values_c.values()) - min(values_c.values())
    if spread_c > MAX_SPREAD_C:
        return None, "model_spread_too_wide"

    pair, pair_gap_c = _closest_pair(values_c)
    values_native = forecast.model_values_native(market0)
    if pair_gap_c <= PAIR_AGREE_C:
        center_native = (values_native[pair[0]] + values_native[pair[1]]) / 2.0
        outlier_model = next(model for model in MODEL_NAMES if model not in pair)
        outlier_native = values_native[outlier_model]
        reason = "closest_pair_consensus"
    else:
        center_native = sum(values_native.values()) / len(values_native)
        outlier_model = None
        outlier_native = None
        reason = "three_model_average"

    legs = [leg for market in markets if (leg := _leg_from_market(market)) is not None]
    legs = sorted(legs, key=lambda leg: leg.midpoint_native)
    center_leg = _find_center_leg(legs, center_native)
    if center_leg is None:
        return None, "no_center_bin"
    above_1 = _adjacent_leg(legs, center_leg, "above")
    below_1 = _adjacent_leg(legs, center_leg, "below")
    above_2 = _adjacent_leg(legs, above_1, "above") if above_1 is not None else None

    if outlier_native is not None and outlier_native > center_native:
        planned = [center_leg, above_1, above_2]
    else:
        planned = [center_leg, above_1, below_1]
    clean: list[LadderLeg] = []
    seen: set[str] = set()
    for leg in planned:
        if leg is None or leg.market.gamma_id in seen:
            continue
        seen.add(leg.market.gamma_id)
        clean.append(leg)
    if len(clean) < 2:
        return None, "not_enough_adjacent_bins"

    prices = [leg.yes_price for leg in clean]
    if any(price < MIN_LEG_PRICE for price in prices):
        return None, "leg_price_too_low"
    if any(price > MAX_LEG_PRICE for price in prices):
        return None, "leg_price_too_high"
    total = sum(prices, Decimal("0"))
    if total > MAX_BASKET_PRICE:
        return None, "basket_price_too_high"

    return LadderPlan(
        event_key=_event_key(market0.city, market0.date, market0.temp_type),
        city=market0.city,
        date=market0.date,
        temp_type=market0.temp_type,
        unit=market0.unit,
        center_native=center_native,
        outlier_model=outlier_model,
        outlier_native=outlier_native,
        closest_pair=pair,
        closest_pair_gap_c=pair_gap_c,
        model_spread_c=spread_c,
        model_values_native=values_native,
        legs=tuple(clean),
        total_price=total,
        stake_per_leg_usd=STAKE_PER_LEG_USD,
        reason=reason,
    ), "planned"


def _event_exists(session, event_key: str) -> bool:
    rows = session.query(Event.payload).filter(
        Event.bot_id == BOT_ID,
        Event.event_type == "bot_d_ensemble_ladder.plan",
    ).all()
    for (payload,) in rows:
        if isinstance(payload, dict) and payload.get("event_key") == event_key:
            return True
    return False


def _plan_payload(plan: LadderPlan) -> dict[str, Any]:
    return {
        "event_key": plan.event_key,
        "city": plan.city,
        "date": plan.date,
        "temp_type": plan.temp_type,
        "unit": plan.unit,
        "center_native": round(plan.center_native, 4),
        "outlier_model": plan.outlier_model,
        "outlier_native": round(plan.outlier_native, 4) if plan.outlier_native is not None else None,
        "closest_pair": list(plan.closest_pair),
        "closest_pair_gap_c": round(plan.closest_pair_gap_c, 4),
        "model_spread_c": round(plan.model_spread_c, 4),
        "model_values_native": {k: round(v, 4) for k, v in plan.model_values_native.items()},
        "total_yes_price": str(plan.total_price),
        "stake_per_leg_usd": str(plan.stake_per_leg_usd),
        "planned_stake_usd": str(plan.stake_per_leg_usd * Decimal(len(plan.legs))),
        "max_payout_usd": str(plan.stake_per_leg_usd / max((leg.yes_price for leg in plan.legs), default=Decimal("1"))),
        "reason": plan.reason,
        "legs": [
            {
                "condition_id": leg.market.gamma_id,
                "slug": leg.market.slug,
                "question": leg.market.question,
                "yes_token_id": leg.market.yes_token_id,
                "yes_price": str(leg.yes_price),
                "stake_usd": str(plan.stake_per_leg_usd),
                "bucket_low_native": round(leg.bucket_low_native, 4),
                "bucket_high_native": round(leg.bucket_high_native, 4),
                "midpoint_native": round(leg.midpoint_native, 4),
            }
            for leg in plan.legs
        ],
    }


def record_plan(session_factory: sessionmaker, plan: LadderPlan) -> bool:
    with session_factory() as session:
        if _event_exists(session, plan.event_key):
            return False
        session.add(Event(
            bot_id=BOT_ID,
            event_type="bot_d_ensemble_ladder.plan",
            severity="info",
            message=f"{plan.city} {plan.date} {plan.temp_type} ensemble ladder paper basket",
            payload=_plan_payload(plan),
        ))
        session.commit()
        return True


def record_scan_summary(session_factory: sessionmaker, payload: dict[str, Any]) -> None:
    with session_factory() as session:
        session.add(Event(
            bot_id=BOT_ID,
            event_type="bot_d_ensemble_ladder.scan_summary",
            severity="info",
            message="Bot D ensemble ladder paper scan summary",
            payload=payload,
        ))
        session.commit()


def run_once(
    *,
    http_client: httpx.Client | None = None,
    session_factory: sessionmaker | None = None,
    markets: list[WeatherMarket] | None = None,
    forecasts: dict[tuple[str, str], ThreeModelForecast] | None = None,
) -> dict[str, Any]:
    """Run one paper-only scan and return a summary payload."""
    _assert_paper_only()
    sf = session_factory or get_session_factory()
    raw_markets = markets if markets is not None else fetch_weather_markets(client=http_client)
    candidates = candidate_markets(raw_markets)
    dates_by_city: dict[str, set[str]] = defaultdict(set)
    for market in candidates:
        dates_by_city[market.city].add(market.date)

    forecast_map: dict[tuple[str, str], ThreeModelForecast] = dict(forecasts or {})
    if forecasts is None:
        for city, dates in dates_by_city.items():
            fetched = fetch_three_model_forecasts(city, sorted(dates), client=http_client)
            for date, forecast in fetched.items():
                forecast_map[(city, date)] = forecast

    groups: dict[tuple[str, str, str], list[WeatherMarket]] = defaultdict(list)
    for market in candidates:
        groups[(market.city, market.date, market.temp_type)].append(market)

    skip_reasons: Counter[str] = Counter()
    plans = 0
    recorded = 0
    duplicate = 0
    for (city, date, _temp_type), group in groups.items():
        forecast = forecast_map.get((city, date))
        if forecast is None:
            skip_reasons["missing_forecast"] += 1
            continue
        plan, reason = build_ladder_plan(group, forecast)
        if plan is None:
            skip_reasons[reason] += 1
            continue
        plans += 1
        if record_plan(sf, plan):
            recorded += 1
        else:
            duplicate += 1

    summary = {
        "raw_markets": len(raw_markets),
        "candidate_markets": len(candidates),
        "event_groups": len(groups),
        "plans": plans,
        "recorded_plans": recorded,
        "duplicate_plans": duplicate,
        "skip_reasons": dict(sorted(skip_reasons.items())),
        "window_hours": {"min": WIN_MIN_H, "max": WIN_MAX_H},
        "filters": {
            "pair_agree_c": PAIR_AGREE_C,
            "max_spread_c": MAX_SPREAD_C,
            "min_leg_price": str(MIN_LEG_PRICE),
            "max_leg_price": str(MAX_LEG_PRICE),
            "max_basket_price": str(MAX_BASKET_PRICE),
            "stake_per_leg_usd": str(STAKE_PER_LEG_USD),
            "require_verified_settlement": REQUIRE_VERIFIED_SETTLEMENT,
            "shadow_bias_correction_param_sent": SHADOW_BIAS_CORRECTION,
        },
    }
    record_scan_summary(sf, summary)
    return summary


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bots.bot_d_weather.ensemble_ladder")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    parser.add_argument("--scan-interval-s", type=float, default=SCAN_INTERVAL_S)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _assert_paper_only()
    init_db()
    log.info("bot_d_ensemble_ladder: paper runner started bot_id=%s", BOT_ID)
    if args.once:
        summary = run_once()
        log.info("bot_d_ensemble_ladder.summary %s", summary)
        return 0
    while True:
        try:
            summary = run_once()
            log.info("bot_d_ensemble_ladder.summary %s", summary)
        except Exception as exc:
            log.exception("bot_d_ensemble_ladder.scan_failed: %s", exc)
        time.sleep(max(5.0, float(args.scan_interval_s)))


if __name__ == "__main__":
    raise SystemExit(main())
