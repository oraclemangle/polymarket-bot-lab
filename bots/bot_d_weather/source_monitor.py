"""Settlement-source telemetry for Bot D weather markets.

This module is read-only telemetry. It records what the settlement station
has already printed, what the market was pricing at the same moment, and
whether the bucket is already locked or impossible from station observations.
It must never decide entries directly.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import sessionmaker

from bots.bot_d_weather.config import (
    BOT_D_FINAL_SOURCE_CACHE_TTL_SEC,
    BOT_D_FINAL_SOURCE_POLL_ENABLED,
    BOT_D_TOMORROW_CACHE_TTL_SEC,
    BOT_D_TOMORROW_SHADOW_ENABLED,
    BOT_D_TOMORROW_TIMEOUT_SEC,
    BOT_D_WEATHERCOM_API_KEY,
    CITIES,
    SETTLEMENT_SPECS,
    TOMORROW_API_KEY,
    TOMORROW_FORECAST_URL,
    apply_settlement_value,
    settlement_value_for_rounding,
)
from bots.bot_d_weather.discovery import WeatherMarket
from bots.bot_d_weather.weather_fetcher import (
    _fetch_aviationweather_metars,
    _parse_awc_report_time,
)
from core.db import Event

log = logging.getLogger(__name__)
httpx_log = logging.getLogger("httpx")

WEATHERCOM_CURRENT_URL = "https://api.weather.com/v3/wx/observations/current"
WEATHERCOM_KEY_BOOTSTRAP_URL = (
    "https://www.wunderground.com/history/daily/us/ny/new-york-city/KLGA"
)
_WEATHERCOM_KEY_CACHE: str | None = None
_FINAL_SOURCE_CACHE: dict[tuple[str, str], tuple[datetime, "FinalSourceSnapshot"]] = {}
_TOMORROW_CACHE: dict[tuple[str, str], tuple[datetime, "TomorrowShadowSnapshot"]] = {}


@dataclass(frozen=True)
class StationDaySnapshot:
    city: str
    date: str
    station: str | None
    source: str | None
    fetched_at: datetime
    local_day_complete: bool
    latest_temp_f: float | None
    latest_settlement_temp_f: float | None
    latest_observed_at: datetime | None
    raw_max_f: float | None
    raw_max_settlement_f: float | None
    raw_max_observed_at: datetime | None
    raw_min_f: float | None
    raw_min_settlement_f: float | None
    raw_min_observed_at: datetime | None
    sample_count: int


@dataclass(frozen=True)
class FinalSourceSnapshot:
    city: str
    date: str
    station: str | None
    source: str | None
    fetched_at: datetime
    status: str
    valid_time: datetime | None
    temperature_f: float | None
    temperature_max_24h_f: float | None
    temperature_max_since_7am_f: float | None
    temperature_min_24h_f: float | None
    source_url: str | None
    error: str | None = None


@dataclass(frozen=True)
class TomorrowShadowSnapshot:
    city: str
    date: str
    fetched_at: datetime
    status: str
    high_f: float | None
    low_f: float | None
    first_time: datetime | None
    last_time: datetime | None
    source_url: str | None
    error: str | None = None


def _iso(dt: datetime | None) -> str | None:
    return dt.astimezone(UTC).isoformat() if dt is not None else None


def _to_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _local_day_complete(city: str, date_str: str, now: datetime) -> bool:
    cfg = CITIES[city]
    tz = ZoneInfo(cfg.timezone)
    local_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    local_end = datetime.combine(local_date, time(23, 59, 59), tzinfo=tz)
    return now.astimezone(tz) >= local_end


def _is_city_local_today(city: str, date_str: str, now: datetime) -> bool:
    if city not in CITIES:
        return False
    cfg = CITIES[city]
    tz = ZoneInfo(cfg.timezone)
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    return now.astimezone(tz).date() == target


def _parse_weathercom_time(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC)
    except (TypeError, ValueError, OSError):
        pass
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)


def _weathercom_api_key(client: httpx.Client) -> str | None:
    global _WEATHERCOM_KEY_CACHE
    if BOT_D_WEATHERCOM_API_KEY:
        return BOT_D_WEATHERCOM_API_KEY
    if _WEATHERCOM_KEY_CACHE:
        return _WEATHERCOM_KEY_CACHE
    try:
        resp = client.get(
            WEATHERCOM_KEY_BOOTSTRAP_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        log.debug("bot_d.weathercom_key.fetch_failed err=%s", exc)
        return None
    match = re.search(r"apiKey=([A-Za-z0-9]{32})", resp.text)
    if not match:
        return None
    _WEATHERCOM_KEY_CACHE = match.group(1)
    return _WEATHERCOM_KEY_CACHE


def _weathercom_current_get(client: httpx.Client, station: str, api_key: str) -> httpx.Response:
    """Call Weather.com without letting httpx INFO logs print the URL API key."""
    old_level = httpx_log.level
    httpx_log.setLevel(logging.WARNING)
    try:
        return client.get(
            WEATHERCOM_CURRENT_URL,
            params={
                "apiKey": api_key,
                "language": "en-US",
                "units": "e",
                "format": "json",
                "icaoCode": station,
            },
            timeout=15.0,
        )
    finally:
        httpx_log.setLevel(old_level)


def _empty_final_source(
    city: str,
    date_str: str,
    *,
    station: str | None,
    source: str | None,
    fetched_at: datetime,
    status: str,
    error: str | None = None,
) -> FinalSourceSnapshot:
    return FinalSourceSnapshot(
        city=city,
        date=date_str,
        station=station,
        source=source,
        fetched_at=fetched_at,
        status=status,
        valid_time=None,
        temperature_f=None,
        temperature_max_24h_f=None,
        temperature_max_since_7am_f=None,
        temperature_min_24h_f=None,
        source_url=None,
        error=error,
    )


def _empty_tomorrow_shadow(
    city: str,
    date_str: str,
    *,
    fetched_at: datetime,
    status: str,
    error: str | None = None,
) -> TomorrowShadowSnapshot:
    return TomorrowShadowSnapshot(
        city=city,
        date=date_str,
        fetched_at=fetched_at,
        status=status,
        high_f=None,
        low_f=None,
        first_time=None,
        last_time=None,
        source_url=None,
        error=error,
    )


def fetch_tomorrow_shadow_snapshot(
    city: str,
    date_str: str,
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> TomorrowShadowSnapshot:
    """Fetch Tomorrow.io hourly temperature as shadow-only forecast evidence.

    This function is intentionally disconnected from Bot D entry decisions.
    It writes source evidence for later realised-settlement comparison only.
    """
    fetched_at = now or datetime.now(UTC)
    if not BOT_D_TOMORROW_SHADOW_ENABLED:
        return _empty_tomorrow_shadow(city, date_str, fetched_at=fetched_at, status="disabled")
    if not TOMORROW_API_KEY:
        return _empty_tomorrow_shadow(city, date_str, fetched_at=fetched_at, status="missing_key")
    if city not in CITIES:
        return _empty_tomorrow_shadow(city, date_str, fetched_at=fetched_at, status="unknown_city")

    cache_key = (city, date_str)
    cached = _TOMORROW_CACHE.get(cache_key)
    if cached is not None:
        cached_at, cached_snapshot = cached
        if (fetched_at - cached_at).total_seconds() <= BOT_D_TOMORROW_CACHE_TTL_SEC:
            return cached_snapshot

    lat = SETTLEMENT_SPECS.get(city).forecast_lat if SETTLEMENT_SPECS.get(city) else CITIES[city].lat
    lon = SETTLEMENT_SPECS.get(city).forecast_lon if SETTLEMENT_SPECS.get(city) else CITIES[city].lon
    cfg = CITIES[city]
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    owns = client is None
    c = client or httpx.Client(timeout=BOT_D_TOMORROW_TIMEOUT_SEC, headers={"User-Agent": "bot-d/0.1"})
    try:
        try:
            resp = c.get(
                TOMORROW_FORECAST_URL,
                params={
                    "location": f"{lat},{lon}",
                    "apikey": TOMORROW_API_KEY,
                    "timesteps": "1h",
                    "units": "imperial",
                    "fields": "temperature",
                },
                timeout=BOT_D_TOMORROW_TIMEOUT_SEC,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            snapshot = _empty_tomorrow_shadow(
                city,
                date_str,
                fetched_at=fetched_at,
                status="fetch_failed",
                error=str(exc)[:300],
            )
            _TOMORROW_CACHE[cache_key] = (fetched_at, snapshot)
            return snapshot
    finally:
        if owns:
            c.close()

    hourly = (data.get("timelines") or {}).get("hourly") or []
    tz = ZoneInfo(cfg.timezone)
    values: list[tuple[datetime, float]] = []
    for row in hourly:
        if not isinstance(row, dict):
            continue
        values_dict = row.get("values") if isinstance(row.get("values"), dict) else {}
        temp = _to_float(values_dict.get("temperature"))
        if temp is None:
            continue
        valid = _parse_weathercom_time(row.get("time"))
        if valid is None or valid.astimezone(tz).date() != target_date:
            continue
        values.append((valid, temp))

    if not values:
        snapshot = _empty_tomorrow_shadow(
            city,
            date_str,
            fetched_at=fetched_at,
            status="no_target_hours",
        )
    else:
        times = [v[0] for v in values]
        temps = [v[1] for v in values]
        snapshot = TomorrowShadowSnapshot(
            city=city,
            date=date_str,
            fetched_at=fetched_at,
            status="ok",
            high_f=round(max(temps), 3),
            low_f=round(min(temps), 3),
            first_time=min(times),
            last_time=max(times),
            source_url=f"{TOMORROW_FORECAST_URL}?location={lat},{lon}&timesteps=1h&units=imperial&fields=temperature",
            error=None,
        )
    _TOMORROW_CACHE[cache_key] = (fetched_at, snapshot)
    return snapshot


def fetch_final_source_snapshot(
    city: str,
    date_str: str,
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> FinalSourceSnapshot:
    """Fetch market-visible WU/Weather.com current station extrema.

    This is not the finalized WU history table. It is the current WU-backed
    station feed Polymarket users can see before finalization, useful for
    measuring whether METAR has led the market-visible source.
    """
    fetched_at = now or datetime.now(UTC)
    spec = SETTLEMENT_SPECS.get(city)
    station = (spec.obs_station or spec.station) if spec else None
    source = spec.source if spec else None
    if not BOT_D_FINAL_SOURCE_POLL_ENABLED:
        return _empty_final_source(
            city,
            date_str,
            station=station,
            source=source,
            fetched_at=fetched_at,
            status="disabled",
        )
    if source != "wunderground" or not station:
        return _empty_final_source(
            city,
            date_str,
            station=station,
            source=source,
            fetched_at=fetched_at,
            status="unsupported_source",
        )
    if not _is_city_local_today(city, date_str, fetched_at):
        return _empty_final_source(
            city,
            date_str,
            station=station,
            source=source,
            fetched_at=fetched_at,
            status="not_current_local_day",
        )

    cache_key = (station, date_str)
    cached = _FINAL_SOURCE_CACHE.get(cache_key)
    if cached is not None:
        cached_at, cached_snapshot = cached
        if (fetched_at - cached_at).total_seconds() <= BOT_D_FINAL_SOURCE_CACHE_TTL_SEC:
            return cached_snapshot

    owns = client is None
    c = client or httpx.Client(timeout=15.0, headers={"User-Agent": "bot-d/0.1"})
    try:
        api_key = _weathercom_api_key(c)
        if not api_key:
            snapshot = _empty_final_source(
                city,
                date_str,
                station=station,
                source=source,
                fetched_at=fetched_at,
                status="missing_weathercom_api_key",
            )
        else:
            try:
                resp = _weathercom_current_get(c, station, api_key)
                resp.raise_for_status()
                data = resp.json()
                snapshot = FinalSourceSnapshot(
                    city=city,
                    date=date_str,
                    station=station,
                    source=source,
                    fetched_at=fetched_at,
                    status="ok",
                    valid_time=_parse_weathercom_time(data.get("validTimeUtc")),
                    temperature_f=_to_float(data.get("temperature")),
                    temperature_max_24h_f=_to_float(data.get("temperatureMax24Hour")),
                    temperature_max_since_7am_f=_to_float(data.get("temperatureMaxSince7Am")),
                    temperature_min_24h_f=_to_float(data.get("temperatureMin24Hour")),
                    source_url=f"{WEATHERCOM_CURRENT_URL}?icaoCode={station}",
                    error=None,
                )
            except Exception as exc:
                snapshot = _empty_final_source(
                    city,
                    date_str,
                    station=station,
                    source=source,
                    fetched_at=fetched_at,
                    status="fetch_failed",
                    error=str(exc)[:300],
                )
    finally:
        if owns:
            c.close()
    _FINAL_SOURCE_CACHE[cache_key] = (fetched_at, snapshot)
    return snapshot


def fetch_station_day_snapshot(
    city: str,
    date_str: str,
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> StationDaySnapshot:
    """Fetch same-local-day station observations for one Bot D city/date."""
    fetched_at = now or datetime.now(UTC)
    spec = SETTLEMENT_SPECS.get(city)
    station = (spec.obs_station or spec.station) if spec else None
    source = spec.source if spec else None
    complete = _local_day_complete(city, date_str, fetched_at) if city in CITIES else False
    if city not in CITIES or station is None:
        return StationDaySnapshot(
            city=city,
            date=date_str,
            station=station,
            source=source,
            fetched_at=fetched_at,
            local_day_complete=complete,
            latest_temp_f=None,
            latest_settlement_temp_f=None,
            latest_observed_at=None,
            raw_max_f=None,
            raw_max_settlement_f=None,
            raw_max_observed_at=None,
            raw_min_f=None,
            raw_min_settlement_f=None,
            raw_min_observed_at=None,
            sample_count=0,
        )

    cfg = CITIES[city]
    tz = ZoneInfo(cfg.timezone)
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    rows: list[tuple[datetime, float, float]] = []
    for record in _fetch_aviationweather_metars(city, hours=36, client=client):
        temp_c = record.get("temp")
        observed_at = _parse_awc_report_time(record)
        if temp_c is None or observed_at is None:
            continue
        observed_at = observed_at.astimezone(UTC)
        if observed_at.astimezone(tz).date() != target:
            continue
        raw_f = float(temp_c) * 9.0 / 5.0 + 32.0
        rows.append((observed_at, raw_f, apply_settlement_value(city, raw_f)))

    if not rows:
        return StationDaySnapshot(
            city=city,
            date=date_str,
            station=station,
            source=source,
            fetched_at=fetched_at,
            local_day_complete=complete,
            latest_temp_f=None,
            latest_settlement_temp_f=None,
            latest_observed_at=None,
            raw_max_f=None,
            raw_max_settlement_f=None,
            raw_max_observed_at=None,
            raw_min_f=None,
            raw_min_settlement_f=None,
            raw_min_observed_at=None,
            sample_count=0,
        )

    latest = max(rows, key=lambda row: row[0])
    max_row = max(rows, key=lambda row: row[2])
    min_row = min(rows, key=lambda row: row[2])
    return StationDaySnapshot(
        city=city,
        date=date_str,
        station=station,
        source=source,
        fetched_at=fetched_at,
        local_day_complete=complete,
        latest_temp_f=round(latest[1], 3),
        latest_settlement_temp_f=round(latest[2], 3),
        latest_observed_at=latest[0],
        raw_max_f=round(max_row[1], 3),
        raw_max_settlement_f=round(max_row[2], 3),
        raw_max_observed_at=max_row[0],
        raw_min_f=round(min_row[1], 3),
        raw_min_settlement_f=round(min_row[2], 3),
        raw_min_observed_at=min_row[0],
        sample_count=len(rows),
    )


def classify_bucket_state(
    market: WeatherMarket,
    snapshot: StationDaySnapshot,
) -> dict[str, Any]:
    """Return late-stage bucket state for a market from station observations."""
    low = _to_float(market.range_low_f)
    high = _to_float(market.range_high_f)
    complete = bool(snapshot.local_day_complete)
    metric = (
        snapshot.raw_max_settlement_f
        if market.temp_type == "high"
        else snapshot.raw_min_settlement_f
    )
    metric_at = (
        snapshot.raw_max_observed_at
        if market.temp_type == "high"
        else snapshot.raw_min_observed_at
    )
    if metric is None:
        return {
            "bucket_state": "no_station_data",
            "bucket_locked": False,
            "bucket_impossible": False,
            "station_metric_f": None,
            "station_metric_observed_at": None,
            "lock_age_seconds": None,
            "distance_to_bucket_f": None,
        }

    in_bucket = True
    if low is not None and metric < low:
        in_bucket = False
    if high is not None and metric > high:
        in_bucket = False

    already_yes = False
    already_no = False
    if market.temp_type == "high":
        if market.direction == "above" and low is not None and metric >= low:
            already_yes = True
        elif high is not None and metric > high and market.direction in {
            "between",
            "exact",
            "below",
        }:
            already_no = True
    else:
        if market.direction == "below" and high is not None and metric <= high:
            already_yes = True
        elif low is not None and metric < low and market.direction in {
            "between",
            "exact",
            "above",
        }:
            already_no = True

    if complete and in_bucket:
        state = "locked_yes"
    elif complete and not in_bucket:
        state = "locked_no"
    elif already_yes:
        state = "already_yes"
    elif already_no:
        state = "already_no"
    else:
        state = "pending"

    if in_bucket:
        distance = 0.0
    else:
        edges = [v for v in (low, high) if v is not None]
        distance = min(abs(metric - edge) for edge in edges) if edges else None
    lock_age = (
        (snapshot.fetched_at - metric_at).total_seconds()
        if metric_at is not None and state in {"locked_yes", "locked_no", "already_yes", "already_no"}
        else None
    )
    return {
        "bucket_state": state,
        "bucket_locked": state in {"locked_yes", "already_yes"},
        "bucket_impossible": state in {"locked_no", "already_no"},
        "station_metric_f": metric,
        "station_metric_observed_at": _iso(metric_at),
        "lock_age_seconds": round(lock_age, 1) if lock_age is not None else None,
        "distance_to_bucket_f": round(distance, 3) if distance is not None else None,
    }


def _round_temp_for_audit(city: str, value: float | None, rounding: str) -> float | None:
    if value is None:
        return None
    return round(settlement_value_for_rounding(city, value, rounding), 3)


def _rounding_counterfactuals(
    market: WeatherMarket,
    snapshot: StationDaySnapshot,
    configured_rounding: str,
) -> dict[str, Any]:
    """Return audit-only bucket labels under alternate settlement rounding.

    These fields are for evidence collection only. Entry and exit decisions
    continue to use the configured `SettlementSpec.rounding` path.
    """
    out: dict[str, Any] = {}
    for rounding in ("nearest_int", "floor"):
        rounded_snapshot = replace(
            snapshot,
            latest_settlement_temp_f=_round_temp_for_audit(
                snapshot.city,
                snapshot.latest_temp_f,
                rounding,
            ),
            raw_max_settlement_f=_round_temp_for_audit(
                snapshot.city,
                snapshot.raw_max_f,
                rounding,
            ),
            raw_min_settlement_f=_round_temp_for_audit(
                snapshot.city,
                snapshot.raw_min_f,
                rounding,
            ),
        )
        state = classify_bucket_state(market, rounded_snapshot)
        observed = state.get("station_metric_f") if rounded_snapshot.local_day_complete else None
        out[rounding] = {
            "latest_settlement_temp_f": rounded_snapshot.latest_settlement_temp_f,
            "raw_max_settlement_f": rounded_snapshot.raw_max_settlement_f,
            "raw_min_settlement_f": rounded_snapshot.raw_min_settlement_f,
            "bucket_state": state.get("bucket_state"),
            "station_metric_f": state.get("station_metric_f"),
            "yes_resolved": (
                state.get("bucket_state") == "locked_yes"
                if observed is not None
                else None
            ),
            "configured": rounding == configured_rounding,
        }
    if "nearest_int" in out and "floor" in out:
        out["nearest_vs_floor_disagree"] = (
            out["nearest_int"].get("bucket_state") != out["floor"].get("bucket_state")
            or out["nearest_int"].get("yes_resolved") != out["floor"].get("yes_resolved")
        )
    return out


def _final_source_payload(
    market: WeatherMarket,
    snapshot: StationDaySnapshot,
    final_source: FinalSourceSnapshot | None,
) -> dict[str, Any]:
    if final_source is None:
        return {
            "final_source_snapshot": None,
            "source_visible_timestamp": None,
            "source_lag_seconds": None,
            "source_lag_basis": None,
            "source_station_status": None,
        }
    data = asdict(final_source)
    data["fetched_at"] = _iso(final_source.fetched_at)
    data["valid_time"] = _iso(final_source.valid_time)
    if market.temp_type == "high":
        source_metric = (
            final_source.temperature_max_24h_f
            if final_source.temperature_max_24h_f is not None
            else final_source.temperature_max_since_7am_f
        )
        source_field = (
            "temperatureMax24Hour"
            if final_source.temperature_max_24h_f is not None
            else "temperatureMaxSince7Am"
        )
        station_metric = snapshot.raw_max_settlement_f
        station_metric_at = snapshot.raw_max_observed_at
    else:
        source_metric = final_source.temperature_min_24h_f
        source_field = "temperatureMin24Hour"
        station_metric = snapshot.raw_min_settlement_f
        station_metric_at = snapshot.raw_min_observed_at
    source_matches = (
        source_metric is not None
        and station_metric is not None
        and abs(float(source_metric) - float(station_metric)) <= 0.1
    )
    lag = (
        (final_source.valid_time - station_metric_at).total_seconds()
        if source_matches and final_source.valid_time is not None and station_metric_at is not None
        else None
    )
    return {
        "final_source_snapshot": data,
        "source_station_status": final_source.status,
        "source_value_f": round(float(source_metric), 3) if source_metric is not None else None,
        "source_value_field": source_field if source_metric is not None else None,
        "source_matches_station_metric": source_matches,
        "source_visible_timestamp": _iso(final_source.valid_time) if source_matches else None,
        "source_lag_seconds": round(lag, 1) if lag is not None else None,
        "source_lag_basis": (
            "weathercom_current_rolling_24h_matches_station_metric"
            if lag is not None
            else "weathercom_current_rolling_24h_no_match"
        ),
    }


def _tomorrow_shadow_payload(
    market: WeatherMarket,
    snapshot: StationDaySnapshot,
    tomorrow: TomorrowShadowSnapshot | None,
) -> dict[str, Any]:
    if tomorrow is None:
        return {
            "tomorrow_io_snapshot": None,
            "tomorrow_io_value_f": None,
            "tomorrow_io_gap_to_station_f": None,
        }
    data = asdict(tomorrow)
    data["fetched_at"] = _iso(tomorrow.fetched_at)
    data["first_time"] = _iso(tomorrow.first_time)
    data["last_time"] = _iso(tomorrow.last_time)
    forecast_value = tomorrow.high_f if market.temp_type == "high" else tomorrow.low_f
    station_value = snapshot.raw_max_settlement_f if market.temp_type == "high" else snapshot.raw_min_settlement_f
    gap = (
        round(float(forecast_value) - float(station_value), 3)
        if forecast_value is not None and station_value is not None
        else None
    )
    return {
        "tomorrow_io_snapshot": data,
        "tomorrow_io_value_f": forecast_value,
        "tomorrow_io_gap_to_station_f": gap,
    }


def _snapshot_payload(
    market: WeatherMarket,
    snapshot: StationDaySnapshot,
    final_source: FinalSourceSnapshot | None = None,
    tomorrow_shadow: TomorrowShadowSnapshot | None = None,
) -> dict[str, Any]:
    data = asdict(snapshot)
    for key in (
        "fetched_at",
        "latest_observed_at",
        "raw_max_observed_at",
        "raw_min_observed_at",
    ):
        data[key] = _iso(data.get(key))
    spec = SETTLEMENT_SPECS.get(market.city)
    payload: dict[str, Any] = {
        "condition_id": market.gamma_id,
        "question": market.question,
        "slug": market.slug,
        "city": market.city,
        "date": market.date,
        "temp_type": market.temp_type,
        "direction": market.direction,
        "bucket_low_f": market.range_low_f,
        "bucket_high_f": market.range_high_f,
        "unit": market.unit,
        "yes_token_id": market.yes_token_id,
        "no_token_id": market.no_token_id,
        "market_yes_price": str(market.yes_price) if market.yes_price is not None else None,
        "market_no_price": (
            str((Decimal("1") - market.yes_price).quantize(Decimal("0.000001")))
            if market.yes_price is not None
            else None
        ),
        "volume_24h_usd": (
            str(market.volume_24h_usd) if market.volume_24h_usd is not None else None
        ),
        "end_date": market.end_date.astimezone(UTC).isoformat() if market.end_date else None,
        "settlement_station": spec.station if spec else snapshot.station,
        "observation_station": (spec.obs_station or spec.station) if spec else snapshot.station,
        "settlement_source": spec.source if spec else snapshot.source,
        "settlement_rounding": spec.rounding if spec else "nearest_int",
        "settlement_unit": spec.unit if spec else "F",
        "settlement_verified": bool(spec.verified) if spec else False,
        "source_snapshot": data,
    }
    bucket_state = classify_bucket_state(market, snapshot)
    payload.update(bucket_state)
    observed = bucket_state.get("station_metric_f") if snapshot.local_day_complete else None
    payload["observed_temperature_f"] = observed
    payload["observed_temperature_observed_at"] = (
        bucket_state.get("station_metric_observed_at") if observed is not None else None
    )
    payload["observed_temperature_complete"] = bool(observed is not None)
    payload["yes_resolved"] = (
        bucket_state.get("bucket_state") == "locked_yes"
        if observed is not None
        else None
    )
    latest_at = snapshot.latest_observed_at
    payload["raw_station_age_seconds"] = (
        round((snapshot.fetched_at - latest_at).total_seconds(), 1)
        if latest_at is not None
        else None
    )
    payload.update(_final_source_payload(market, snapshot, final_source))
    payload.update(_tomorrow_shadow_payload(market, snapshot, tomorrow_shadow))
    try:
        payload["settlement_rounding_counterfactuals"] = _rounding_counterfactuals(
            market,
            snapshot,
            str(payload.get("settlement_rounding") or "nearest_int"),
        )
    except Exception as exc:
        log.debug(
            "bot_d.rounding_counterfactual.failed city=%s date=%s err=%s",
            market.city,
            market.date,
            exc,
        )
    return payload


def _resolution_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    observed = payload.get("observed_temperature_f")
    if observed is None:
        return None
    out = dict(payload)
    out["_event_type"] = "bot_d.forecast_resolution"
    out["settlement_label_source"] = "station_observation"
    out["resolution_source_event_type"] = "bot_d.source_snapshot"
    return out


def _market_from_source_payload(payload: dict[str, Any]) -> WeatherMarket | None:
    condition_id = str(payload.get("condition_id") or "")
    city = str(payload.get("city") or "")
    date = str(payload.get("date") or "")
    temp_type = str(payload.get("temp_type") or "")
    direction = str(payload.get("direction") or "")
    if not condition_id or not city or not date or temp_type not in {"high", "low"}:
        return None
    try:
        yes_price = (
            Decimal(str(payload["market_yes_price"]))
            if payload.get("market_yes_price") is not None
            else None
        )
    except Exception:
        yes_price = None
    try:
        volume = (
            Decimal(str(payload["volume_24h_usd"]))
            if payload.get("volume_24h_usd") is not None
            else None
        )
    except Exception:
        volume = None
    end_date = None
    if payload.get("end_date"):
        try:
            end_date = datetime.fromisoformat(str(payload["end_date"]).replace("Z", "+00:00"))
        except ValueError:
            end_date = None
    return WeatherMarket(
        gamma_id=condition_id,
        slug=str(payload.get("slug") or ""),
        question=str(payload.get("question") or ""),
        city=city,
        date=date,
        temp_type=temp_type,
        direction=direction,
        range_low_f=_to_float(payload.get("bucket_low_f")),
        range_high_f=_to_float(payload.get("bucket_high_f")),
        unit=str(payload.get("unit") or "F"),
        yes_token_id=str(payload.get("yes_token_id") or ""),
        no_token_id=str(payload.get("no_token_id") or ""),
        yes_price=yes_price,
        volume_24h_usd=volume,
        end_date=end_date,
    )


def record_completed_forecast_resolutions(
    session_factory: sessionmaker,
    *,
    bot_id: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    lookback_days: int = 7,
    source_limit: int = 10000,
) -> int:
    """Backfill one forecast-resolution label for completed source snapshots.

    Active Gamma discovery often stops returning a daily weather market before
    the station's local day is complete. This pass reuses recent
    `bot_d.source_snapshot` payloads as the market template, re-fetches the
    completed station day, and writes one append-only label per condition id.
    """
    fetched_at = now or datetime.now(UTC)
    cutoff = fetched_at - timedelta(days=lookback_days)
    with session_factory() as session:
        existing = {
            str((event.payload or {}).get("condition_id") or "")
            for event in session.query(Event)
            .filter(
                Event.bot_id == bot_id,
                Event.event_type == "bot_d.forecast_resolution",
            )
            .all()
        }
        source_events = (
            session.query(Event)
            .filter(
                Event.bot_id == bot_id,
                Event.event_type == "bot_d.source_snapshot",
                Event.created_at >= cutoff,
            )
            .order_by(Event.created_at.desc())
            .limit(source_limit)
            .all()
        )

    candidates: dict[str, WeatherMarket] = {}
    for event in source_events:
        payload = event.payload or {}
        if not isinstance(payload, dict):
            continue
        cid = str(payload.get("condition_id") or "")
        if not cid or cid in existing or cid in candidates:
            continue
        city = str(payload.get("city") or "")
        date_str = str(payload.get("date") or "")
        if city not in CITIES or not date_str:
            continue
        if not _local_day_complete(city, date_str, fetched_at):
            continue
        market = _market_from_source_payload(payload)
        if market is not None:
            candidates[cid] = market

    if not candidates:
        return 0

    snapshots: dict[tuple[str, str], StationDaySnapshot] = {}
    final_sources: dict[tuple[str, str], FinalSourceSnapshot] = {}
    resolution_payloads: list[dict[str, Any]] = []
    for market in candidates.values():
        key = (market.city, market.date)
        snapshot = snapshots.get(key)
        if snapshot is None:
            try:
                snapshot = fetch_station_day_snapshot(
                    market.city,
                    market.date,
                    client=client,
                    now=fetched_at,
                )
            except Exception as exc:
                log.debug(
                    "bot_d.forecast_resolution.fetch_failed city=%s date=%s err=%s",
                    market.city,
                    market.date,
                    exc,
                )
                continue
            snapshots[key] = snapshot
        final_source = final_sources.get(key)
        if final_source is None:
            try:
                final_source = fetch_final_source_snapshot(
                    market.city,
                    market.date,
                    client=client,
                    now=fetched_at,
                )
            except Exception as exc:
                log.debug(
                    "bot_d.forecast_resolution.final_source_failed city=%s date=%s err=%s",
                    market.city,
                    market.date,
                    exc,
                )
                final_source = None
            if final_source is not None:
                final_sources[key] = final_source
        resolution = _resolution_payload(_snapshot_payload(market, snapshot, final_source))
        if resolution is not None:
            resolution_payloads.append(resolution)

    if not resolution_payloads:
        return 0

    with session_factory() as session:
        written = 0
        existing = {
            str((event.payload or {}).get("condition_id") or "")
            for event in session.query(Event)
            .filter(
                Event.bot_id == bot_id,
                Event.event_type == "bot_d.forecast_resolution",
            )
            .all()
        }
        for payload in resolution_payloads:
            cid = str(payload.get("condition_id") or "")
            if not cid or cid in existing:
                continue
            session.add(
                Event(
                    bot_id=bot_id,
                    event_type="bot_d.forecast_resolution",
                    severity="info",
                    message=(
                        f"{payload.get('city')} {payload.get('date')} "
                        f"{payload.get('temp_type')} observed="
                        f"{payload.get('observed_temperature_f')} "
                        f"state={payload.get('bucket_state')}"
                    )[:500],
                    payload=payload,
                    created_at=fetched_at,
                )
            )
            existing.add(cid)
            written += 1
        session.commit()
    return written


def record_source_snapshots(
    session_factory: sessionmaker,
    markets: list[WeatherMarket],
    *,
    bot_id: str,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> int:
    """Record one `bot_d.source_snapshot` Event per market.

    Best-effort only. Any failure logs and returns the snapshots successfully
    written so far.
    """
    if not markets:
        return 0
    fetched_at = now or datetime.now(UTC)
    snapshots: dict[tuple[str, str], StationDaySnapshot] = {}
    final_sources: dict[tuple[str, str], FinalSourceSnapshot] = {}
    tomorrow_sources: dict[tuple[str, str], TomorrowShadowSnapshot] = {}
    events: list[Event] = []
    resolution_payloads: list[dict[str, Any]] = []
    for market in markets:
        key = (market.city, market.date)
        snapshot = snapshots.get(key)
        if snapshot is None:
            try:
                snapshot = fetch_station_day_snapshot(
                    market.city,
                    market.date,
                    client=client,
                    now=fetched_at,
                )
            except Exception as exc:
                log.debug(
                    "bot_d.source_snapshot.fetch_failed city=%s date=%s err=%s",
                    market.city,
                    market.date,
                    exc,
                )
                continue
            snapshots[key] = snapshot
        final_source = final_sources.get(key)
        if final_source is None:
            try:
                final_source = fetch_final_source_snapshot(
                    market.city,
                    market.date,
                    client=client,
                    now=fetched_at,
                )
            except Exception as exc:
                log.debug(
                    "bot_d.source_snapshot.final_source_failed city=%s date=%s err=%s",
                    market.city,
                    market.date,
                    exc,
                )
                final_source = None
            if final_source is not None:
                final_sources[key] = final_source
        tomorrow_shadow = tomorrow_sources.get(key)
        if tomorrow_shadow is None:
            try:
                tomorrow_shadow = fetch_tomorrow_shadow_snapshot(
                    market.city,
                    market.date,
                    client=client,
                    now=fetched_at,
                )
            except Exception as exc:
                log.debug(
                    "bot_d.source_snapshot.tomorrow_failed city=%s date=%s err=%s",
                    market.city,
                    market.date,
                    exc,
                )
                tomorrow_shadow = None
            if tomorrow_shadow is not None:
                tomorrow_sources[key] = tomorrow_shadow
        payload = _snapshot_payload(market, snapshot, final_source, tomorrow_shadow)
        events.append(
            Event(
                bot_id=bot_id,
                event_type="bot_d.source_snapshot",
                severity="info",
                message=(
                    f"{market.city} {market.date} {market.temp_type} "
                    f"{market.direction} state={payload.get('bucket_state')}"
                )[:500],
                payload=payload,
                created_at=fetched_at,
            )
        )
        resolution = _resolution_payload(payload)
        if resolution is not None:
            resolution_payloads.append(resolution)
    if not events:
        return 0
    with session_factory() as session:
        session.add_all(events)
        if resolution_payloads:
            existing = {
                str((event.payload or {}).get("condition_id") or "")
                for event in session.query(Event)
                .filter(
                    Event.bot_id == bot_id,
                    Event.event_type == "bot_d.forecast_resolution",
                )
                .all()
            }
            for payload in resolution_payloads:
                cid = str(payload.get("condition_id") or "")
                if not cid or cid in existing:
                    continue
                session.add(
                    Event(
                        bot_id=bot_id,
                        event_type="bot_d.forecast_resolution",
                        severity="info",
                        message=(
                            f"{payload.get('city')} {payload.get('date')} "
                            f"{payload.get('temp_type')} observed="
                            f"{payload.get('observed_temperature_f')} "
                            f"state={payload.get('bucket_state')}"
                        )[:500],
                        payload=payload,
                        created_at=fetched_at,
                    )
                )
                existing.add(cid)
        session.commit()
    return len(events)
