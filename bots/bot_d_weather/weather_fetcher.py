"""Multi-model weather fetcher via Open-Meteo + NWS + METAR.

Three data layers, each free and no-API-key:
  1. Open-Meteo multi-model ensemble (GFS 31 + ECMWF 51 = 82 members)
  2. NOAA NBM station text guidance (US resolving-station forecast bypass)
  3. NWS gridpoint hourly forecast (US cities only — second-opinion filter)
  4. METAR airport observations (US cities — real-time calibration for <24h)

Fallback: single-model Open-Meteo forecast with city RMSE as sigma.
"""
from __future__ import annotations

import csv
import io
import logging
import os
import re
import statistics
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from bots.bot_d_weather.config import (
    CITIES,
    OPEN_METEO_ENSEMBLE_URL,
    OPEN_METEO_FORECAST_URL,
    forecast_coordinates,
    observation_station,
)

log = logging.getLogger(__name__)

_ForecastCacheKey = tuple[str, tuple[str, ...], bool, bool]
_FORECAST_CACHE: dict[_ForecastCacheKey, tuple[float, dict[str, ForecastResult]]] = {}
_FORECAST_CACHE_LOCK = threading.Lock()
_OPEN_METEO_COOLDOWN_UNTIL = 0.0
_NOAA_NBM_TEXT_CACHE: dict[str, tuple[float, datetime, str, str]] = {}
_GRIBSTREAM_CACHE: dict[tuple[str, tuple[str, ...], str], tuple[float, dict[str, ForecastResult]]] = {}


def _forecast_cache_ttl_seconds() -> float:
    return float(os.environ.get("BOT_D_FORECAST_CACHE_TTL_SEC", "900"))


def _forecast_request_pause_seconds() -> float:
    return float(os.environ.get("BOT_D_FORECAST_REQUEST_PAUSE_SEC", "0.25"))


def _noaa_nbm_enabled() -> bool:
    return os.environ.get("BOT_D_NOAA_NBM_ENABLED", "true").strip().lower() == "true"


def _noaa_nbm_cache_ttl_seconds() -> float:
    return float(os.environ.get("BOT_D_NOAA_NBM_CACHE_TTL_SEC", "3600"))


def _gribstream_enabled() -> bool:
    return os.environ.get("BOT_D_GRIBSTREAM_ENABLED", "false").strip().lower() == "true"


def _gribstream_model() -> str:
    return os.environ.get("BOT_D_GRIBSTREAM_MODEL", "nbm").strip().lower() or "nbm"


def _gribstream_cache_ttl_seconds() -> float:
    return float(os.environ.get("BOT_D_GRIBSTREAM_CACHE_TTL_SEC", "3600"))


def _gribstream_timeout_seconds() -> float:
    return float(os.environ.get("BOT_D_GRIBSTREAM_TIMEOUT_SEC", "20"))


def _gribstream_token() -> str | None:
    token = os.environ.get("GRIBSTREAM_API_TOKEN", "").strip()
    return token or None


def _gribstream_audit_enabled() -> bool:
    return os.environ.get("BOT_D_GRIBSTREAM_AUDIT_ENABLED", "true").strip().lower() == "true"


def _record_gribstream_call(
    *,
    city_key: str,
    dates: list[str],
    model: str,
    status: str,
    from_cache: bool = False,
    http_status: int | None = None,
    response_rows: int | None = None,
    results_count: int | None = None,
    response_bytes: int | None = None,
    duration_ms: float | None = None,
    error_type: str | None = None,
) -> None:
    """Best-effort GribStream usage telemetry. Never logs tokens or headers."""
    if not _gribstream_audit_enabled():
        return
    try:
        from bots.bot_d_weather.config import BOT_D_BOT_ID
        from core.db import Event, get_session_factory

        payload = {
            "provider": "gribstream",
            "model": model,
            "city": city_key,
            "dates": list(dates),
            "status": status,
            "from_cache": bool(from_cache),
            "http_status": http_status,
            "response_rows": response_rows,
            "results_count": results_count,
            "response_bytes": response_bytes,
            "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
            "error_type": error_type,
            "credit_charge_expected": not from_cache and status == "ok",
        }
        with get_session_factory()() as session:
            session.add(
                Event(
                    bot_id=BOT_D_BOT_ID,
                    event_type="bot_d.gribstream_call",
                    severity="info" if status in {"ok", "cache_hit", "disabled"} else "warn",
                    message=(
                        f"gribstream {model} {city_key} status={status} "
                        f"rows={response_rows} results={results_count}"
                    )[:500],
                    payload=payload,
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
    except Exception as exc:
        log.debug("gribstream audit write failed for %s: %s", city_key, exc)


def _open_meteo_retry_after_default_seconds() -> float:
    return float(os.environ.get("BOT_D_OPEN_METEO_RETRY_AFTER_SEC", "1800"))


def _open_meteo_cooldown_remaining() -> float:
    with _FORECAST_CACHE_LOCK:
        return max(0.0, _OPEN_METEO_COOLDOWN_UNTIL - time.time())


def _open_meteo_cooldown_active() -> bool:
    return _open_meteo_cooldown_remaining() > 0


def _retry_after_seconds(response: httpx.Response) -> float:
    raw = response.headers.get("Retry-After")
    if raw:
        with suppress(ValueError):
            return max(1.0, float(raw))
        with suppress(Exception):
            parsed = parsedate_to_datetime(raw)
            return max(1.0, (parsed - datetime.now(parsed.tzinfo or UTC)).total_seconds())
    return _open_meteo_retry_after_default_seconds()


def _mark_open_meteo_429(exc: Exception, *, city_key: str, source: str) -> bool:
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code != 429:
        return False
    delay = _retry_after_seconds(exc.response)
    global _OPEN_METEO_COOLDOWN_UNTIL
    with _FORECAST_CACHE_LOCK:
        _OPEN_METEO_COOLDOWN_UNTIL = max(_OPEN_METEO_COOLDOWN_UNTIL, time.time() + delay)
    log.warning(
        "open-meteo rate limited for %s via %s; cooling down for %.0fs",
        city_key,
        source,
        delay,
    )
    return True


def _forecast_cache_get(
    key: _ForecastCacheKey,
) -> dict[str, ForecastResult] | None:
    with _FORECAST_CACHE_LOCK:
        cached = _FORECAST_CACHE.get(key)
        if cached is None:
            return None
        cached_at, forecasts = cached
        if time.time() - cached_at > _forecast_cache_ttl_seconds():
            _FORECAST_CACHE.pop(key, None)
            return None
        return dict(forecasts)


def _forecast_cache_put(
    key: _ForecastCacheKey,
    forecasts: dict[str, ForecastResult],
) -> None:
    with _FORECAST_CACHE_LOCK:
        _FORECAST_CACHE[key] = (time.time(), dict(forecasts))


def _forecast_cache_usable_during_open_meteo_cooldown(
    forecasts: dict[str, ForecastResult],
) -> bool:
    """Avoid extending single-source NWS fallback blocks when NBM is available."""
    if not _noaa_nbm_enabled():
        return True
    return any(fc.source != "nws_fallback" for fc in forecasts.values())

# ICAO airport codes for METAR observation stations. These should match
# the stations Polymarket uses for resolution (typically Weather Underground
# → NWS METAR). Only US cities have reliable free METAR via api.weather.gov.
CITY_ICAO: dict[str, str] = {
    city: station
    for city in CITIES
    if (station := observation_station(city)) is not None
}

# NWS gridpoint coordinates for forecast.weather.gov (office/x,y).
# Only US cities. These are approximate; the NWS API redirects to exact gridpoints.
# If a city isn't listed, NWS second-opinion is skipped for that city.
NWS_GRIDPOINTS: dict[str, str] = {
    "NYC": "OKX/33,37",
    "Chicago": "LOT/76,73",
    "Dallas": "FWD/79,108",
    "Atlanta": "FFC/52,89",
    "Miami": "MFL/75,53",
    "Houston": "HGX/65,97",
    "Austin": "EWX/156,91",
    "LA": "LOX/154,44",
    "Seattle": "SEW/124,67",
    "SF": "MTR/85,105",
    "Denver": "BOU/62,60",
}


def _c_to_f(celsius: float) -> float:
    return celsius * 9.0 / 5.0 + 32.0


@dataclass(frozen=True)
class ForecastResult:
    city: str
    date: str
    mean_high_f: float
    std_high_f: float
    mean_low_f: float
    std_low_f: float
    ensemble_count: int
    source: str  # "multi_model" | "ensemble" | "standard" | "gribstream_nbm" | "noaa_nbm" | "nws_fallback"
    fetched_at: datetime | None = None
    model_timestamp: str | None = None
    # Raw daily highs/lows per ensemble member, used for empirical bucket odds.
    member_highs_f: tuple[float, ...] = field(default_factory=tuple)
    member_lows_f: tuple[float, ...] = field(default_factory=tuple)
    # Upgrade 3: METAR current observation (None if unavailable or not relevant).
    metar_temp_f: float | None = None
    metar_age_minutes: float | None = None
    metar_max_so_far_f: float | None = None
    metar_min_so_far_f: float | None = None
    # Upgrade 5: NWS gridpoint forecast high/low (None if unavailable).
    nws_high_f: float | None = None
    nws_low_f: float | None = None
    # Independent model/API panel excluding NWS. Used to tell whether NWS is
    # a genuine veto or the outlier against station-targeted model sources.
    api_highs_f: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    api_lows_f: tuple[tuple[str, float], ...] = field(default_factory=tuple)


def _target_dates(city_key: str, days_ahead: int = 3) -> list[str]:
    cfg = CITIES[city_key]
    today = datetime.now(ZoneInfo(cfg.timezone)).date()
    return [(today + timedelta(days=i)).isoformat() for i in range(days_ahead)]


# --- Upgrade 1: Multi-model ensemble -----------------------------------------

def fetch_ensemble(
    city_key: str,
    dates: list[str],
    *,
    client: httpx.Client | None = None,
) -> dict[str, ForecastResult]:
    """Fetch GFS + ECMWF ensemble (82 total members) from Open-Meteo.

    Upgrade 1: requests both `gfs_seamless` and `ecmwf_ifs025` in one call.
    All members are pooled into a single mega-ensemble. The sigma naturally
    widens when the two models disagree, which is exactly when uncertainty
    is highest.
    """
    cfg = CITIES[city_key]
    lat, lon = forecast_coordinates(city_key)
    owns = client is None
    c = client or httpx.Client(timeout=30.0, headers={"User-Agent": "bot-d-weather/0.2"})
    fetched_at = datetime.now(UTC)
    if _open_meteo_cooldown_active():
        log.info(
            "open-meteo ensemble skipped for %s during cooldown (%.0fs remaining)",
            city_key,
            _open_meteo_cooldown_remaining(),
        )
        if owns:
            c.close()
        return {}
    try:
        resp = c.get(OPEN_METEO_ENSEMBLE_URL, params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m",
            "forecast_days": len(dates) + 1,
            "timezone": cfg.timezone,
            "models": "gfs_seamless,ecmwf_ifs025",  # Upgrade 1: multi-model
        })
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        if _mark_open_meteo_429(exc, city_key=city_key, source="ensemble_multi_model"):
            return {}
        log.warning("multi-model fetch failed for %s, trying GFS-only: %s", city_key, exc)
        # Fallback to GFS-only if multi-model request fails.
        try:
            resp = c.get(OPEN_METEO_ENSEMBLE_URL, params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m",
                "forecast_days": len(dates) + 1,
                "timezone": cfg.timezone,
            })
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc2:
            if _mark_open_meteo_429(exc2, city_key=city_key, source="ensemble_gfs"):
                return {}
            log.warning("GFS-only also failed for %s: %s", city_key, exc2)
            return {}
    finally:
        if owns:
            c.close()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    # Collect ALL temperature keys — both GFS and ECMWF members.
    model_keys = [k for k in hourly if "temperature_2m" in k]
    if not model_keys:
        log.warning("no ensemble temperature data for %s", city_key)
        return {}

    # Count models for source label.
    has_gfs = any("gefs" in k or (k == "temperature_2m") for k in model_keys)
    has_ecmwf = any("ecmwf" in k for k in model_keys)
    source = "multi_model" if (has_gfs and has_ecmwf) else "ensemble"

    date_set = set(dates)
    model_daily: dict[str, dict[str, list[float]]] = {
        mk: {d: [] for d in dates} for mk in model_keys
    }
    for mk in model_keys:
        temps = hourly[mk]
        for i, t_str in enumerate(times):
            if i >= len(temps) or temps[i] is None:
                continue
            date_part = t_str[:10]
            if date_part in date_set:
                model_daily[mk][date_part].append(_c_to_f(temps[i]))

    results: dict[str, ForecastResult] = {}
    for date_str in dates:
        highs: list[float] = []
        lows: list[float] = []
        for mk in model_keys:
            hourly_temps = model_daily[mk][date_str]
            if hourly_temps:
                highs.append(max(hourly_temps))
                lows.append(min(hourly_temps))
        if not highs:
            continue
        results[date_str] = ForecastResult(
            city=city_key,
            date=date_str,
            mean_high_f=statistics.fmean(highs),
            std_high_f=statistics.stdev(highs) if len(highs) > 1 else cfg.rmse_f,
            mean_low_f=statistics.fmean(lows),
            std_low_f=statistics.stdev(lows) if len(lows) > 1 else cfg.rmse_f,
            ensemble_count=len(highs),
            source=source,
            fetched_at=fetched_at,
            model_timestamp=str(data.get("model_run") or data.get("model_run_at") or "") or None,
            member_highs_f=tuple(highs),
            member_lows_f=tuple(lows),
        )
    return results


# --- Upgrade 3: METAR real-time observations ----------------------------------

def _parse_awc_report_time(record: dict[str, Any]) -> datetime | None:
    raw = record.get("reportTime") or record.get("receiptTime")
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _fetch_aviationweather_metars(
    city_key: str,
    *,
    hours: int,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Fetch recent METAR/SPECI records from AviationWeather for a city."""
    icao = CITY_ICAO.get(city_key)
    if not icao:
        return []
    owns = client is None
    c = client or httpx.Client(timeout=10.0, headers={"User-Agent": "bot-d-weather/0.3"})
    try:
        resp = c.get(
            "https://aviationweather.gov/api/data/metar",
            params={"ids": icao, "format": "json", "hours": hours},
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else []
    except Exception as exc:
        log.debug("aviationweather metar fetch failed for %s (%s): %s", city_key, icao, exc)
        return []
    finally:
        if owns:
            c.close()


def fetch_metar(city_key: str, *, client: httpx.Client | None = None) -> tuple[float | None, float | None]:
    """Fetch latest METAR observation for a US city.

    Returns (temp_fahrenheit, age_minutes) or (None, None) if unavailable.
    Uses AviationWeather's METAR endpoint, which matches airport-station
    settlement anchors better than generic city forecasts.
    """
    icao = CITY_ICAO.get(city_key)
    if not icao:
        return None, None
    records = _fetch_aviationweather_metars(city_key, hours=3, client=client)
    if not records:
        return None, None
    latest = max(records, key=lambda r: _parse_awc_report_time(r) or datetime.min.replace(tzinfo=UTC))
    temp_c = latest.get("temp")
    if temp_c is None:
        return None, None
    age_min = None
    obs_time = _parse_awc_report_time(latest)
    if obs_time is not None:
        age_min = (datetime.now(obs_time.tzinfo) - obs_time).total_seconds() / 60.0
    return _c_to_f(float(temp_c)), age_min


def fetch_metar_extrema(
    city_key: str,
    target_date: str,
    *,
    client: httpx.Client | None = None,
) -> tuple[float | None, float | None]:
    """Return same-local-day METAR max/min so far for the settlement station."""
    if city_key not in CITIES:
        return None, None
    cfg = CITIES[city_key]
    records = _fetch_aviationweather_metars(city_key, hours=36, client=client)
    temps_f: list[float] = []
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    tz = ZoneInfo(cfg.timezone)
    for record in records:
        temp_c = record.get("temp")
        report_time = _parse_awc_report_time(record)
        if temp_c is None or report_time is None:
            continue
        if report_time.astimezone(tz).date() != target:
            continue
        temps_f.append(_c_to_f(float(temp_c)))
    if not temps_f:
        return None, None
    return max(temps_f), min(temps_f)


# --- GribStream NBM provider -------------------------------------------------

def _target_date_utc_window(city_key: str, dates: list[str]) -> tuple[datetime, datetime]:
    cfg = CITIES[city_key]
    tz = ZoneInfo(cfg.timezone)
    local_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]
    start_local = datetime.combine(min(local_dates), datetime.min.time(), tzinfo=tz)
    end_local = datetime.combine(max(local_dates) + timedelta(days=1), datetime.min.time(), tzinfo=tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def _parse_gribstream_time(value: str) -> datetime | None:
    if not value:
        return None
    with suppress(Exception):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _gribstream_temp_to_f(value: str) -> float | None:
    if value == "":
        return None
    with suppress(ValueError):
        temp = float(value)
        # GribStream's GRIB TMP selector returns Kelvin for GFS/NBM examples.
        if temp > 170.0:
            return (temp - 273.15) * 9.0 / 5.0 + 32.0
        return temp
    return None


def fetch_gribstream_nbm_forecast(
    city_key: str,
    dates: list[str],
    *,
    client: httpx.Client | None = None,
) -> dict[str, ForecastResult]:
    """Fetch GribStream NBM 2m temperature for the resolving station.

    GribStream is an optional paid shortcut over the same NOAA model family.
    It is used before direct NOAA text when Open-Meteo is unavailable, but it
    never replaces the NWS second-opinion guard and never stores the API token.
    """
    if not _gribstream_enabled():
        return {}
    model = _gribstream_model()
    token = _gribstream_token()
    if not token:
        log.info("gribstream disabled for %s: missing GRIBSTREAM_API_TOKEN", city_key)
        _record_gribstream_call(
            city_key=city_key,
            dates=dates,
            model=model,
            status="missing_token",
            results_count=0,
        )
        return {}
    station = observation_station(city_key)
    if not station or city_key not in CITIES:
        _record_gribstream_call(
            city_key=city_key,
            dates=dates,
            model=model,
            status="unsupported_city",
            results_count=0,
        )
        return {}
    cache_key = (city_key, tuple(dates), model)
    cached = _GRIBSTREAM_CACHE.get(cache_key)
    if cached is not None:
        cached_at, forecasts = cached
        if time.time() - cached_at <= _gribstream_cache_ttl_seconds():
            _record_gribstream_call(
                city_key=city_key,
                dates=dates,
                model=model,
                status="cache_hit",
                from_cache=True,
                results_count=len(forecasts),
            )
            return dict(forecasts)

    cfg = CITIES[city_key]
    tz = ZoneInfo(cfg.timezone)
    lat, lon = forecast_coordinates(city_key)
    from_time, until_time = _target_date_utc_window(city_key, dates)
    fetched_at = datetime.now(UTC)
    payload = {
        "fromTime": from_time.isoformat().replace("+00:00", "Z"),
        "untilTime": until_time.isoformat().replace("+00:00", "Z"),
        "coordinates": [{"lat": lat, "lon": lon, "name": station}],
        "variables": [
            {"name": "TMP", "level": "2 m above ground", "info": "", "alias": "temp"}
        ],
    }
    owns = client is None
    c = client or httpx.Client(
        timeout=_gribstream_timeout_seconds(),
        headers={"User-Agent": "bot-d-weather/0.5"},
    )
    start = time.perf_counter()
    response_text = ""
    http_status: int | None = None
    try:
        resp = c.post(
            f"https://gribstream.com/api/v2/{model}/timeseries",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "text/csv",
            },
        )
        http_status = resp.status_code
        resp.raise_for_status()
        response_text = resp.text
    except Exception as exc:
        log.warning("gribstream %s fetch failed for %s: %s", model, city_key, exc)
        if isinstance(exc, httpx.HTTPStatusError):
            http_status = exc.response.status_code
        _record_gribstream_call(
            city_key=city_key,
            dates=dates,
            model=model,
            status="error",
            http_status=http_status,
            results_count=0,
            duration_ms=(time.perf_counter() - start) * 1000.0,
            error_type=type(exc).__name__,
        )
        return {}
    finally:
        if owns:
            c.close()

    by_date: dict[str, list[float]] = {d: [] for d in dates}
    model_runs: set[str] = set()
    response_rows = 0
    reader = csv.DictReader(io.StringIO(response_text))
    for row in reader:
        response_rows += 1
        valid_at = _parse_gribstream_time(row.get("forecasted_time", ""))
        if valid_at is None:
            continue
        date_str = valid_at.astimezone(tz).date().isoformat()
        if date_str not in by_date:
            continue
        temp_f = _gribstream_temp_to_f(row.get("temp", ""))
        if temp_f is None:
            continue
        by_date[date_str].append(temp_f)
        model_run = row.get("forecasted_at")
        if model_run:
            model_runs.add(model_run)

    results: dict[str, ForecastResult] = {}
    source = f"gribstream_{model}"
    for date_str, temps in by_date.items():
        if not temps:
            continue
        high_f = max(temps)
        low_f = min(temps)
        results[date_str] = ForecastResult(
            city=city_key,
            date=date_str,
            mean_high_f=high_f,
            std_high_f=cfg.rmse_f,
            mean_low_f=low_f,
            std_low_f=cfg.rmse_f,
            ensemble_count=1,
            source=source,
            fetched_at=fetched_at,
            model_timestamp=";".join(sorted(model_runs)) if model_runs else None,
            member_highs_f=(high_f,),
            member_lows_f=(low_f,),
        )
    if results:
        _GRIBSTREAM_CACHE[cache_key] = (time.time(), dict(results))
        log.info("gribstream %s forecast built for %s station=%s dates=%d", model, city_key, station, len(results))
    _record_gribstream_call(
        city_key=city_key,
        dates=dates,
        model=model,
        status="ok" if results else "empty",
        http_status=http_status,
        response_rows=response_rows,
        results_count=len(results),
        response_bytes=len(response_text.encode("utf-8")),
        duration_ms=(time.perf_counter() - start) * 1000.0,
    )
    return results


# --- NOAA NBM station text bypass --------------------------------------------

def _nbm_product_filename(product: str, cycle_hour: int) -> str:
    code = product.lower()
    return f"blend_{code}tx.t{cycle_hour:02d}z"


def _nbm_product_url(product: str, run_time: datetime) -> str:
    cycle = run_time.hour
    return (
        "https://noaa-nbm-grib2-pds.s3.amazonaws.com/"
        f"blend.{run_time:%Y%m%d}/{cycle:02d}/text/"
        f"{_nbm_product_filename(product, cycle)}"
    )


def _latest_nbm_text_product(
    product: str,
    *,
    client: httpx.Client | None = None,
    max_lookback_hours: int = 8,
) -> tuple[datetime, str, str] | None:
    """Fetch the latest available NBM text product from NOAA's public S3 bucket."""
    product = product.upper()
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    cached = _NOAA_NBM_TEXT_CACHE.get(product)
    if cached is not None:
        cached_at, run_time, url, text = cached
        if time.time() - cached_at <= _noaa_nbm_cache_ttl_seconds():
            return run_time, url, text

    owns = client is None
    c = client or httpx.Client(timeout=60.0, headers={"User-Agent": "bot-d-weather/0.4"})
    try:
        for hours_back in range(max_lookback_hours + 1):
            run_time = now - timedelta(hours=hours_back)
            url = _nbm_product_url(product, run_time)
            try:
                resp = c.get(url, timeout=60.0)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                text = resp.text
                if not text.strip():
                    continue
                _NOAA_NBM_TEXT_CACHE[product] = (time.time(), run_time, url, text)
                log.info("noaa-nbm %s loaded run=%s bytes=%d", product, run_time.isoformat(), len(text))
                return run_time, url, text
            except Exception as exc:
                log.debug("noaa-nbm %s fetch failed url=%s err=%s", product, url, exc)
                continue
    finally:
        if owns:
            c.close()
    return None


def _extract_nbm_station_block(text: str, station: str) -> str | None:
    station = station.upper()
    match = re.search(rf"(?m)^\s{re.escape(station)}\s+NBM\b", text)
    if not match:
        return None
    start = match.start()
    next_match = re.search(r"(?m)^\s[A-Z0-9]{3,6}\s+NBM\b", text[match.end():])
    end = match.end() + next_match.start() if next_match else len(text)
    return text[start:end].strip("\n")


def _parse_nbm_run_time(block: str) -> datetime | None:
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{2})(\d{2})\s+UTC", block)
    if not match:
        return None
    month, day, year, hour, minute = (int(part) for part in match.groups())
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def _nbm_row_values(block: str, row_name: str) -> list[str]:
    for line in block.splitlines():
        if line[:4].strip().upper() == row_name.upper():
            return line[4:].split()
    return []


def _parse_nbm_block_timeseries(
    block: str,
) -> tuple[datetime | None, list[tuple[datetime, float, float | None]]]:
    run_time = _parse_nbm_run_time(block)
    if run_time is None:
        return None, []
    tmp_vals = _nbm_row_values(block, "TMP")
    if not tmp_vals:
        return run_time, []
    tsd_vals = _nbm_row_values(block, "TSD")
    fhr_vals = _nbm_row_values(block, "FHR")
    utc_vals = _nbm_row_values(block, "UTC")

    valid_times: list[datetime] = []
    if fhr_vals:
        for val in fhr_vals[: len(tmp_vals)]:
            try:
                valid_times.append(run_time + timedelta(hours=int(val)))
            except ValueError:
                break
    elif utc_vals:
        current_date = run_time.date()
        previous_hour: int | None = None
        for val in utc_vals[: len(tmp_vals)]:
            try:
                hour = int(val)
            except ValueError:
                break
            if previous_hour is None:
                if hour < run_time.hour:
                    current_date = current_date + timedelta(days=1)
            elif hour < previous_hour:
                current_date = current_date + timedelta(days=1)
            valid_times.append(datetime.combine(current_date, datetime.min.time(), tzinfo=UTC).replace(hour=hour))
            previous_hour = hour
    if not valid_times:
        return run_time, []

    out: list[tuple[datetime, float, float | None]] = []
    for i, valid_at in enumerate(valid_times[: len(tmp_vals)]):
        try:
            temp_f = float(tmp_vals[i])
        except (TypeError, ValueError):
            continue
        std_f: float | None = None
        if i < len(tsd_vals):
            try:
                std_f = float(tsd_vals[i])
            except (TypeError, ValueError):
                std_f = None
        out.append((valid_at, temp_f, std_f))
    return run_time, out


def fetch_noaa_nbm_forecast(
    city_key: str,
    dates: list[str],
    *,
    client: httpx.Client | None = None,
) -> dict[str, ForecastResult]:
    """Fetch NOAA NBM station text guidance for Bot D's resolving airport.

    This gives Bot D a transparent NOAA model fallback when Open-Meteo is
    rate-limited. It is still not a full ensemble, so live keeps the NWS
    second-opinion guard and empirical ensemble-shape veto remains inactive.
    """
    station = observation_station(city_key)
    if not station or city_key not in CITIES:
        return {}
    cfg = CITIES[city_key]
    tz = ZoneInfo(cfg.timezone)
    target_dates = set(dates)
    by_date: dict[str, dict[str, list[float]]] = {
        d: {"temps": [], "stds": []} for d in dates
    }
    model_runs: list[str] = []
    for product in ("NBH", "NBS"):
        fetched = _latest_nbm_text_product(product, client=client)
        if fetched is None:
            continue
        run_time, _url, text = fetched
        block = _extract_nbm_station_block(text, station)
        if block is None:
            log.debug("noaa-nbm %s station block missing for %s", product, station)
            continue
        parsed_run_time, series = _parse_nbm_block_timeseries(block)
        model_runs.append((parsed_run_time or run_time).isoformat())
        for valid_at, temp_f, std_f in series:
            date_str = valid_at.astimezone(tz).date().isoformat()
            if date_str not in target_dates:
                continue
            by_date[date_str]["temps"].append(temp_f)
            if std_f is not None:
                by_date[date_str]["stds"].append(std_f)

    fetched_at = datetime.now(UTC)
    results: dict[str, ForecastResult] = {}
    for date_str, rows in by_date.items():
        temps = rows["temps"]
        if not temps:
            continue
        stds = rows["stds"]
        std_f = statistics.fmean(stds) if stds else cfg.rmse_f
        std_f = max(1.0, min(float(std_f), cfg.rmse_f * 1.5))
        high_f = max(temps)
        low_f = min(temps)
        results[date_str] = ForecastResult(
            city=city_key,
            date=date_str,
            mean_high_f=high_f,
            std_high_f=std_f,
            mean_low_f=low_f,
            std_low_f=std_f,
            ensemble_count=1,
            source="noaa_nbm",
            fetched_at=fetched_at,
            model_timestamp=";".join(model_runs) if model_runs else None,
            member_highs_f=(high_f,),
            member_lows_f=(low_f,),
        )
    if results:
        log.info("noaa-nbm forecast built for %s station=%s dates=%d", city_key, station, len(results))
    return results


# --- Upgrade 5: NWS gridpoint second opinion ----------------------------------

def fetch_nws_forecast(
    city_key: str,
    dates: list[str],
    *,
    client: httpx.Client | None = None,
) -> dict[str, tuple[float | None, float | None]]:
    """Fetch NWS hourly gridpoint forecast and extract daily high/low.

    Returns {date: (high_f, low_f)} for dates in scope. US cities only.
    This is the NWS's own model output — independent of Open-Meteo's GFS.
    When NWS and our ensemble agree, confidence is high. When they diverge
    by >1.5°F on the target bucket, that's a signal to be cautious.
    """
    gridpoint = NWS_GRIDPOINTS.get(city_key)
    if not gridpoint:
        return {}
    owns = client is None
    c = client or httpx.Client(timeout=15.0, headers={
        "User-Agent": "bot-d-weather/0.2",
        "Accept": "application/geo+json",
    })
    try:
        resp = c.get(f"https://api.weather.gov/gridpoints/{gridpoint}/forecast/hourly")
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.debug("nws forecast failed for %s (%s): %s", city_key, gridpoint, exc)
        return {}
    finally:
        if owns:
            c.close()

    # Parse hourly periods into daily high/low.
    date_set = set(dates)
    daily_temps: dict[str, list[float]] = {d: [] for d in dates}
    for period in data.get("properties", {}).get("periods", []):
        start = period.get("startTime", "")
        date_part = start[:10]
        if date_part not in date_set:
            continue
        temp = period.get("temperature")
        unit = period.get("temperatureUnit", "F")
        if temp is None:
            continue
        temp_f = float(temp) if unit == "F" else _c_to_f(float(temp))
        daily_temps[date_part].append(temp_f)

    out: dict[str, tuple[float | None, float | None]] = {}
    for d, temps in daily_temps.items():
        if temps:
            out[d] = (max(temps), min(temps))
    return out


def _forecasts_from_nws(
    city_key: str,
    dates: list[str],
    nws_data: dict[str, tuple[float | None, float | None]],
) -> dict[str, ForecastResult]:
    """Convert NWS gridpoint high/low into a baseline forecast.

    This is a provider-bypass path for Open-Meteo outages/rate limits. It uses
    the same RMSE guardrail as the single-model fallback because NWS is a point
    forecast, not an ensemble distribution.
    """
    cfg = CITIES[city_key]
    fetched_at = datetime.now(UTC)
    results: dict[str, ForecastResult] = {}
    for date_str in dates:
        high_f, low_f = nws_data.get(date_str, (None, None))
        if high_f is None:
            continue
        low = low_f if low_f is not None else high_f - 15.0
        results[date_str] = ForecastResult(
            city=city_key,
            date=date_str,
            mean_high_f=high_f,
            std_high_f=cfg.rmse_f,
            mean_low_f=low,
            std_low_f=cfg.rmse_f,
            ensemble_count=1,
            source="nws_fallback",
            fetched_at=fetched_at,
            model_timestamp=None,
            member_highs_f=(high_f,),
            member_lows_f=(low,),
        )
    return results


def _source_api_panel(fc: ForecastResult) -> tuple[
    tuple[tuple[str, float], ...],
    tuple[tuple[str, float], ...],
]:
    if fc.source == "nws_fallback":
        return (), ()
    return (
        ((fc.source, float(fc.mean_high_f)),),
        ((fc.source, float(fc.mean_low_f)),),
    )


def _merge_api_panel(
    primary: dict[str, ForecastResult],
    *comparisons: dict[str, ForecastResult],
) -> dict[str, ForecastResult]:
    """Attach per-date non-NWS model temperatures from all fetched APIs."""
    out: dict[str, ForecastResult] = {}
    for date_str, fc in primary.items():
        highs: dict[str, float] = dict(fc.api_highs_f)
        lows: dict[str, float] = dict(fc.api_lows_f)
        source_highs, source_lows = _source_api_panel(fc)
        highs.update(source_highs)
        lows.update(source_lows)
        for comp in comparisons:
            other = comp.get(date_str)
            if other is None:
                continue
            source_highs, source_lows = _source_api_panel(other)
            highs.update(source_highs)
            lows.update(source_lows)
        out[date_str] = replace(
            fc,
            api_highs_f=tuple(sorted(highs.items())),
            api_lows_f=tuple(sorted(lows.items())),
        )
    return out


# --- Standard fallback --------------------------------------------------------

def fetch_standard(
    city_key: str,
    dates: list[str],
    *,
    client: httpx.Client | None = None,
) -> dict[str, ForecastResult]:
    """Fallback: single-model forecast. Uses city RMSE as estimated std."""
    cfg = CITIES[city_key]
    lat, lon = forecast_coordinates(city_key)
    owns = client is None
    c = client or httpx.Client(timeout=30.0, headers={"User-Agent": "bot-d-weather/0.2"})
    fetched_at = datetime.now(UTC)
    if _open_meteo_cooldown_active():
        log.info(
            "open-meteo standard skipped for %s during cooldown (%.0fs remaining)",
            city_key,
            _open_meteo_cooldown_remaining(),
        )
        if owns:
            c.close()
        return {}
    try:
        resp = c.get(OPEN_METEO_FORECAST_URL, params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min",
            "forecast_days": len(dates) + 1,
            "timezone": cfg.timezone,
        })
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        if _mark_open_meteo_429(exc, city_key=city_key, source="standard"):
            return {}
        log.warning("standard fetch failed for %s: %s", city_key, exc)
        return {}
    finally:
        if owns:
            c.close()

    daily = data.get("daily", {})
    daily_times = daily.get("time", [])
    daily_highs = daily.get("temperature_2m_max", [])
    daily_lows = daily.get("temperature_2m_min", [])
    date_set = set(dates)
    results: dict[str, ForecastResult] = {}
    for i, d in enumerate(daily_times):
        if d not in date_set:
            continue
        high_c = daily_highs[i] if i < len(daily_highs) else None
        low_c = daily_lows[i] if i < len(daily_lows) else None
        if high_c is None:
            continue
        results[d] = ForecastResult(
            city=city_key, date=d,
            mean_high_f=_c_to_f(high_c), std_high_f=cfg.rmse_f,
            mean_low_f=_c_to_f(low_c) if low_c is not None else _c_to_f(high_c) - 15,
            std_low_f=cfg.rmse_f, ensemble_count=1, source="standard",
            fetched_at=fetched_at,
            model_timestamp=str(data.get("model_run") or data.get("model_run_at") or "") or None,
            member_highs_f=(_c_to_f(high_c),),
            member_lows_f=(
                _c_to_f(low_c) if low_c is not None else _c_to_f(high_c) - 15,
            ),
        )
    return results


# --- Orchestrator -------------------------------------------------------------

def get_forecasts(
    cities: list[str] | None = None,
    days_ahead: int = 3,
    *,
    client: httpx.Client | None = None,
    include_metar: bool = True,
    include_nws: bool = True,
    target_dates_by_city: dict[str, list[str]] | None = None,
) -> dict[str, dict[str, ForecastResult]]:
    """Fetch forecasts for all cities with all three data layers.

    Layer 1: Open-Meteo multi-model ensemble (GFS + ECMWF, 82 members)
    Layer 2: NWS gridpoint forecast (US only — second opinion)
    Layer 3: METAR airport observations (US only — real-time for <24h)

    Returns {city_key: {date: ForecastResult}}.
    """
    if cities is None:
        cities = list(CITIES.keys())
    owns = client is None
    c = client or httpx.Client(
        timeout=30.0,
        headers={"User-Agent": "bot-d-weather/0.2"},
        limits=httpx.Limits(max_connections=5),
    )
    out: dict[str, dict[str, ForecastResult]] = {}
    try:
        for city_key in cities:
            if city_key not in CITIES:
                continue
            dates = (
                sorted(set(target_dates_by_city.get(city_key, [])))
                if target_dates_by_city is not None
                else []
            )
            if not dates:
                dates = _target_dates(city_key, days_ahead)
            cache_key = (city_key, tuple(dates), include_metar, include_nws)
            cached = _forecast_cache_get(cache_key)
            if (
                cached is not None
                and _open_meteo_cooldown_active()
                and _forecast_cache_usable_during_open_meteo_cooldown(cached)
            ):
                out[city_key] = cached
                log.info(
                    "%s: using cached forecast during open-meteo cooldown (%.0fs remaining)",
                    city_key,
                    _open_meteo_cooldown_remaining(),
                )
                continue

            # Layer 1: multi-model ensemble.
            forecasts = fetch_ensemble(city_key, dates, client=c)
            if not forecasts:
                if (
                    _open_meteo_cooldown_active()
                    and cached is not None
                    and _forecast_cache_usable_during_open_meteo_cooldown(cached)
                ):
                    out[city_key] = cached
                    log.info("%s: using cached forecast after open-meteo 429", city_key)
                    continue
                if not _open_meteo_cooldown_active():
                    log.info("%s: ensemble unavailable, falling back to standard", city_key)
                    forecasts = fetch_standard(city_key, dates, client=c)
            gribstream_attempted = False
            noaa_nbm_attempted = False
            # Layer 2: NOAA NBM station text is the free model-source bypass
            # for Open-Meteo rate limits. Try it before paid GribStream so the
            # free source carries ordinary NWS-agreed entries.
            if not forecasts and include_nws and _noaa_nbm_enabled():
                noaa_nbm_attempted = True
                try:
                    forecasts = fetch_noaa_nbm_forecast(city_key, dates, client=c) or {}
                except Exception as exc:
                    log.warning("%s: NOAA NBM fallback fetch failed: %s", city_key, exc)
                    forecasts = {}
            # Layer 3: paid GribStream NBM is the scarce station-targeted
            # shortcut. It fills the gap when Open-Meteo and direct NOAA are
            # unavailable; otherwise it is used only if we still need a second
            # non-NWS model for the outlier probe.
            if not forecasts and include_nws and _gribstream_enabled():
                gribstream_attempted = True
                try:
                    forecasts = fetch_gribstream_nbm_forecast(city_key, dates, client=c) or {}
                except Exception as exc:
                    log.warning("%s: GribStream NBM fallback fetch failed: %s", city_key, exc)
                    forecasts = {}
            comparison_forecasts: list[dict[str, ForecastResult]] = []
            if forecasts and include_nws:
                primary_source = next(iter(forecasts.values())).source
                if (
                    _noaa_nbm_enabled()
                    and not noaa_nbm_attempted
                    and primary_source != "noaa_nbm"
                ):
                    noaa_nbm_attempted = True
                    try:
                        comp = fetch_noaa_nbm_forecast(city_key, dates, client=c) or {}
                    except Exception as exc:
                        log.info("%s: NOAA NBM comparison fetch failed: %s", city_key, exc)
                        comp = {}
                    if comp:
                        comparison_forecasts.append(comp)
                api_source_count = 1 + sum(1 for comp in comparison_forecasts if comp)
                if (
                    api_source_count < 2
                    and _gribstream_enabled()
                    and not gribstream_attempted
                    and not primary_source.startswith("gribstream_")
                ):
                    gribstream_attempted = True
                    try:
                        comp = fetch_gribstream_nbm_forecast(city_key, dates, client=c) or {}
                    except Exception as exc:
                        log.info("%s: GribStream NBM comparison fetch failed: %s", city_key, exc)
                        comp = {}
                    if comp:
                        comparison_forecasts.append(comp)
                forecasts = _merge_api_panel(forecasts, *comparison_forecasts)
            # Layer 4 can also act as an Open-Meteo bypass. Without this,
            # one provider 429 leaves all US weather markets unevaluated, but
            # live entries still block this single-source `nws_fallback` path.
            nws_data: dict[str, tuple[float | None, float | None]] = {}
            if not forecasts and include_nws:
                try:
                    nws_data = fetch_nws_forecast(city_key, dates, client=c) or {}
                except Exception as exc:
                    log.warning("%s: NWS fallback fetch failed: %s", city_key, exc)
                    nws_data = {}
                forecasts = _forecasts_from_nws(city_key, dates, nws_data)
                if forecasts:
                    log.warning(
                        "%s: using NWS forecast fallback after open-meteo unavailable",
                        city_key,
                    )
            if not forecasts:
                if cached is not None:
                    out[city_key] = cached
                    log.warning("%s: all forecast methods failed; using cached forecast", city_key)
                    continue
                log.warning("%s: all forecast methods failed", city_key)
                continue

            # Layer 2: NWS second opinion (US cities only, best-effort).
            if include_nws and not nws_data:
                with suppress(Exception):
                    nws_data = fetch_nws_forecast(city_key, dates, client=c) or {}

            # Layer 3: METAR current observation (US cities, best-effort).
            metar_temp: float | None = None
            metar_age: float | None = None
            metar_max_so_far: float | None = None
            metar_min_so_far: float | None = None
            if include_metar:
                with suppress(Exception):
                    metar_temp, metar_age = fetch_metar(city_key, client=c)
                    today_str = _target_dates(city_key, 1)[0]
                    metar_max_so_far, metar_min_so_far = fetch_metar_extrema(
                        city_key, today_str, client=c
                    )

            # Enrich each ForecastResult with NWS + METAR data.
            enriched: dict[str, ForecastResult] = {}
            for d, fc in forecasts.items():
                nws_high, nws_low = nws_data.get(d, (None, None))
                # Only attach METAR to today's date and if observation is fresh (<120 min).
                today_str = _target_dates(city_key, 1)[0]
                m_temp = metar_temp if d == today_str and metar_age is not None and metar_age < 120 else None
                m_age = metar_age if m_temp is not None else None
                enriched[d] = ForecastResult(
                    city=fc.city, date=fc.date,
                    mean_high_f=fc.mean_high_f, std_high_f=fc.std_high_f,
                    mean_low_f=fc.mean_low_f, std_low_f=fc.std_low_f,
                    ensemble_count=fc.ensemble_count, source=fc.source,
                    fetched_at=fc.fetched_at,
                    model_timestamp=fc.model_timestamp,
                    member_highs_f=fc.member_highs_f,
                    member_lows_f=fc.member_lows_f,
                    metar_temp_f=m_temp, metar_age_minutes=m_age,
                    metar_max_so_far_f=(
                        metar_max_so_far if d == today_str else None
                    ),
                    metar_min_so_far_f=(
                        metar_min_so_far if d == today_str else None
                    ),
                    nws_high_f=nws_high, nws_low_f=nws_low,
                    api_highs_f=fc.api_highs_f,
                    api_lows_f=fc.api_lows_f,
                )
            out[city_key] = enriched
            _forecast_cache_put(cache_key, enriched)
            log.debug(
                "%s: %d date(s) (source=%s, members=%d, nws=%d, metar=%s)",
                city_key, len(enriched),
                next(iter(enriched.values())).source,
                next(iter(enriched.values())).ensemble_count,
                len(nws_data),
                "yes" if metar_temp is not None else "no",
            )
            pause_seconds = _forecast_request_pause_seconds()
            if pause_seconds > 0:
                time.sleep(pause_seconds)
    finally:
        if owns:
            c.close()
    return out
