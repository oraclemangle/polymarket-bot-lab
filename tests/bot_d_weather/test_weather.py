"""Tests for Bot D weather pipeline — discovery, strategy, one-bet-per-event."""
from __future__ import annotations

import time
from decimal import Decimal

import httpx
from freezegun import freeze_time

from bots.bot_d_weather import weather_fetcher
from bots.bot_d_weather.config import (
    CITIES,
    SETTLEMENT_SPECS,
    apply_settlement_value,
    resolve_city,
    settlement_value_for_rounding,
)
from bots.bot_d_weather.discovery import WeatherMarket, fetch_weather_markets, parse_weather_question
from bots.bot_d_weather.strategy import (
    apply_one_bet_per_event,
    apply_wave_regime_sizing,
    empirical_bucket_probability,
    evaluate_weather_market,
    range_probability,
)
from bots.bot_d_weather.weather_fetcher import ForecastResult
from core.db import Event, get_session_factory


def _fc(city="NYC", date="2026-04-16", mean_high=75.0, std_high=3.0,
        mean_low=55.0, std_low=3.0, member_highs=(), member_lows=(),
        metar_max=None, metar_min=None, nws_high=None, nws_low=None) -> ForecastResult:
    return ForecastResult(
        city=city, date=date, mean_high_f=mean_high, std_high_f=std_high,
        mean_low_f=mean_low, std_low_f=std_low, ensemble_count=31, source="ensemble",
        member_highs_f=tuple(member_highs), member_lows_f=tuple(member_lows),
        metar_max_so_far_f=metar_max, metar_min_so_far_f=metar_min,
        nws_high_f=nws_high, nws_low_f=nws_low,
    )


def _mkt(city="NYC", date="2026-04-16", temp_type="high", direction="between",
         lo=74.0, hi=76.0, yes_price=0.3, gamma_id="g1") -> WeatherMarket:
    return WeatherMarket(
        gamma_id=gamma_id, slug="s", question="q", city=city, date=date,
        temp_type=temp_type, direction=direction,
        range_low_f=lo, range_high_f=hi, unit="F",
        yes_token_id="y", no_token_id="n",
        yes_price=Decimal(str(yes_price)), volume_24h_usd=Decimal("1000"),
    )


def _reset_weather_cache() -> None:
    with weather_fetcher._FORECAST_CACHE_LOCK:
        weather_fetcher._FORECAST_CACHE.clear()
        weather_fetcher._NOAA_NBM_TEXT_CACHE.clear()
        weather_fetcher._GRIBSTREAM_CACHE.clear()
        weather_fetcher._OPEN_METEO_COOLDOWN_UNTIL = 0.0


# --- Forecast fetcher ---------------------------------------------------------

def test_open_meteo_429_sets_retry_after_cooldown():
    _reset_weather_cache()
    request = httpx.Request("GET", "https://api.open-meteo.com/v1/forecast")
    response = httpx.Response(429, headers={"Retry-After": "17"}, request=request)
    exc = httpx.HTTPStatusError("rate limited", request=request, response=response)

    assert weather_fetcher._mark_open_meteo_429(exc, city_key="NYC", source="test")
    assert weather_fetcher._open_meteo_cooldown_remaining() > 15


def test_open_meteo_429_without_retry_after_uses_long_default(monkeypatch):
    _reset_weather_cache()
    monkeypatch.delenv("BOT_D_OPEN_METEO_RETRY_AFTER_SEC", raising=False)
    request = httpx.Request("GET", "https://api.open-meteo.com/v1/forecast")
    response = httpx.Response(429, request=request)
    exc = httpx.HTTPStatusError("rate limited", request=request, response=response)

    assert weather_fetcher._mark_open_meteo_429(exc, city_key="NYC", source="test")
    assert weather_fetcher._open_meteo_cooldown_remaining() > 1700


def test_get_forecasts_uses_cache_during_open_meteo_cooldown(monkeypatch):
    _reset_weather_cache()
    monkeypatch.setenv("BOT_D_FORECAST_REQUEST_PAUSE_SEC", "0")
    calls = []

    def fake_fetch_ensemble(city_key, dates, *, client=None):
        calls.append((city_key, tuple(dates)))
        return {
            dates[0]: _fc(
                city=city_key,
                date=dates[0],
                mean_high=72.0,
                mean_low=54.0,
            )
        }

    monkeypatch.setattr(weather_fetcher, "fetch_ensemble", fake_fetch_ensemble)
    first = weather_fetcher.get_forecasts(
        cities=["NYC"],
        days_ahead=1,
        include_metar=False,
        include_nws=False,
    )

    def fail_fetch_ensemble(city_key, dates, *, client=None):
        raise AssertionError("fetch_ensemble should not run during cached cooldown")

    monkeypatch.setattr(weather_fetcher, "fetch_ensemble", fail_fetch_ensemble)
    weather_fetcher._OPEN_METEO_COOLDOWN_UNTIL = time.time() + 60
    second = weather_fetcher.get_forecasts(
        cities=["NYC"],
        days_ahead=1,
        include_metar=False,
        include_nws=False,
    )

    assert len(calls) == 1
    first_fc = next(iter(first["NYC"].values()))
    second_fc = next(iter(second["NYC"].values()))
    assert second_fc.mean_high_f == first_fc.mean_high_f == 72.0


def test_get_forecasts_uses_nws_bypass_during_open_meteo_cooldown(monkeypatch):
    _reset_weather_cache()
    monkeypatch.setenv("BOT_D_FORECAST_REQUEST_PAUSE_SEC", "0")
    monkeypatch.setenv("BOT_D_NOAA_NBM_ENABLED", "false")

    def blocked_fetch_ensemble(city_key, dates, *, client=None):
        weather_fetcher._OPEN_METEO_COOLDOWN_UNTIL = time.time() + 60
        return {}

    def fail_fetch_standard(city_key, dates, *, client=None):
        raise AssertionError("Open-Meteo standard fallback must stay bypassed")

    def fake_fetch_nws_forecast(city_key, dates, *, client=None):
        return {dates[0]: (81.0, 66.0)}

    monkeypatch.setattr(weather_fetcher, "fetch_ensemble", blocked_fetch_ensemble)
    monkeypatch.setattr(weather_fetcher, "fetch_standard", fail_fetch_standard)
    monkeypatch.setattr(weather_fetcher, "fetch_nws_forecast", fake_fetch_nws_forecast)

    forecasts = weather_fetcher.get_forecasts(
        cities=["NYC"],
        days_ahead=1,
        include_metar=False,
        include_nws=True,
    )

    fc = forecasts["NYC"][next(iter(forecasts["NYC"]))]
    assert fc.source == "nws_fallback"
    assert fc.mean_high_f == 81.0
    assert fc.mean_low_f == 66.0
    assert fc.member_highs_f == (81.0,)
    assert fc.nws_high_f == 81.0
    assert fc.nws_low_f == 66.0


def test_nbm_text_parser_maps_forecast_hours_to_valid_times():
    block = """
 KATL   NBM V5.0 NBS GUIDANCE    5/05/2026  1700 UTC
 UTC  21 00 03 06
 FHR  04 07 10 13
 TMP  80 75 68 66
 TSD   2  2  2  3
"""

    run_time, series = weather_fetcher._parse_nbm_block_timeseries(block)

    assert run_time is not None
    assert run_time.isoformat() == "2026-05-05T17:00:00+00:00"
    assert [(dt.isoformat(), temp, std) for dt, temp, std in series] == [
        ("2026-05-05T21:00:00+00:00", 80.0, 2.0),
        ("2026-05-06T00:00:00+00:00", 75.0, 2.0),
        ("2026-05-06T03:00:00+00:00", 68.0, 2.0),
        ("2026-05-06T06:00:00+00:00", 66.0, 3.0),
    ]


def test_fetch_noaa_nbm_forecast_builds_station_forecast(monkeypatch):
    _reset_weather_cache()
    nbh = """
 KATL   NBM V5.0 NBH GUIDANCE    5/05/2026  1700 UTC
 UTC  18 19 20 21 22 23 00 01
 TMP  77 79 80 81 80 78 75 72
 TSD   1  1  2  2  2  2  2  3
"""
    nbs = """
 KATL   NBM V5.0 NBS GUIDANCE    5/05/2026  1700 UTC
 UTC  21 00 03 06 09 12 15 18
 FHR  04 07 10 13 16 19 22 25
 TMP  81 75 68 66 64 65 72 78
 TSD   2  2  2  3  3  2  2  4
"""

    def fake_latest(product, *, client=None, max_lookback_hours=8):
        text = nbh if product == "NBH" else nbs
        return weather_fetcher.datetime(2026, 5, 5, 17, tzinfo=weather_fetcher.UTC), "mock", text

    monkeypatch.setattr(weather_fetcher, "_latest_nbm_text_product", fake_latest)

    forecasts = weather_fetcher.fetch_noaa_nbm_forecast("Atlanta", ["2026-05-05", "2026-05-06"])

    assert forecasts["2026-05-05"].source == "noaa_nbm"
    assert forecasts["2026-05-05"].mean_high_f == 81.0
    assert forecasts["2026-05-06"].mean_high_f == 78.0
    assert forecasts["2026-05-06"].mean_low_f == 64.0
    assert forecasts["2026-05-06"].std_high_f >= 1.0


def test_fetch_gribstream_nbm_forecast_builds_station_forecast(tmp_db, monkeypatch):
    _reset_weather_cache()
    monkeypatch.setenv("BOT_D_GRIBSTREAM_ENABLED", "true")
    monkeypatch.setenv("GRIBSTREAM_API_TOKEN", "test-token")
    csv_text = "\n".join([
        "forecasted_at,forecasted_time,lat,lon,name,temp",
        "2026-05-05T12:00:00Z,2026-05-05T18:00:00Z,33.64,-84.43,KATL,300.15",
        "2026-05-05T12:00:00Z,2026-05-05T21:00:00Z,33.64,-84.43,KATL,302.15",
        "2026-05-05T18:00:00Z,2026-05-06T09:00:00Z,33.64,-84.43,KATL,291.15",
        "2026-05-05T18:00:00Z,2026-05-06T18:00:00Z,33.64,-84.43,KATL,299.15",
    ])

    class FakeClient:
        def __init__(self):
            self.payload = None
            self.headers = None

        def post(self, url, *, json=None, headers=None):
            self.url = url
            self.payload = json
            self.headers = headers
            return httpx.Response(
                200,
                text=csv_text,
                request=httpx.Request("POST", url),
            )

    client = FakeClient()

    forecasts = weather_fetcher.fetch_gribstream_nbm_forecast(
        "Atlanta",
        ["2026-05-05", "2026-05-06"],
        client=client,  # type: ignore[arg-type]
    )

    assert forecasts["2026-05-05"].source == "gribstream_nbm"
    assert round(forecasts["2026-05-05"].mean_high_f, 1) == 84.2
    assert round(forecasts["2026-05-06"].mean_low_f, 1) == 64.4
    assert client.payload["coordinates"][0]["name"] == "KATL"
    assert client.headers["Authorization"] == "Bearer test-token"
    with get_session_factory()() as session:
        event = session.query(Event).filter_by(event_type="bot_d.gribstream_call").one()
    assert event.payload["status"] == "ok"
    assert event.payload["city"] == "Atlanta"
    assert event.payload["response_rows"] == 4
    assert event.payload["results_count"] == 2
    assert "test-token" not in str(event.payload)


def test_fetch_gribstream_nbm_forecast_records_cache_hit(tmp_db, monkeypatch):
    _reset_weather_cache()
    monkeypatch.setenv("BOT_D_GRIBSTREAM_ENABLED", "true")
    monkeypatch.setenv("GRIBSTREAM_API_TOKEN", "test-token")
    csv_text = "\n".join([
        "forecasted_at,forecasted_time,lat,lon,name,temp",
        "2026-05-05T12:00:00Z,2026-05-05T18:00:00Z,33.64,-84.43,KATL,300.15",
    ])

    class FakeClient:
        calls = 0

        def post(self, url, *, json=None, headers=None):
            self.calls += 1
            return httpx.Response(
                200,
                text=csv_text,
                request=httpx.Request("POST", url),
            )

    client = FakeClient()
    first = weather_fetcher.fetch_gribstream_nbm_forecast(
        "Atlanta",
        ["2026-05-05"],
        client=client,  # type: ignore[arg-type]
    )
    second = weather_fetcher.fetch_gribstream_nbm_forecast(
        "Atlanta",
        ["2026-05-05"],
        client=client,  # type: ignore[arg-type]
    )

    assert first
    assert second
    assert client.calls == 1
    with get_session_factory()() as session:
        statuses = [
            row.payload["status"]
            for row in session.query(Event)
            .filter_by(event_type="bot_d.gribstream_call")
            .order_by(Event.id)
            .all()
        ]
    assert statuses == ["ok", "cache_hit"]


def test_get_forecasts_prefers_noaa_then_adds_gribstream_when_needed(monkeypatch):
    _reset_weather_cache()
    monkeypatch.setenv("BOT_D_FORECAST_REQUEST_PAUSE_SEC", "0")
    monkeypatch.setenv("BOT_D_GRIBSTREAM_ENABLED", "true")
    monkeypatch.setenv("GRIBSTREAM_API_TOKEN", "test-token")
    calls = []

    def blocked_fetch_ensemble(city_key, dates, *, client=None):
        weather_fetcher._OPEN_METEO_COOLDOWN_UNTIL = time.time() + 60
        return {}

    def fake_fetch_gribstream(city_key, dates, *, client=None):
        calls.append(("gribstream", city_key))
        return {
            dates[0]: ForecastResult(
                city=city_key,
                date=dates[0],
                mean_high_f=82.0,
                std_high_f=3.0,
                mean_low_f=65.0,
                std_low_f=3.0,
                ensemble_count=1,
                source="gribstream_nbm",
                member_highs_f=(82.0,),
                member_lows_f=(65.0,),
            )
        }

    def fake_fetch_noaa(city_key, dates, *, client=None):
        calls.append(("nbm", city_key))
        return {
            dates[0]: ForecastResult(
                city=city_key,
                date=dates[0],
                mean_high_f=83.0,
                std_high_f=2.0,
                mean_low_f=66.0,
                std_low_f=2.0,
                ensemble_count=1,
                source="noaa_nbm",
                member_highs_f=(83.0,),
                member_lows_f=(66.0,),
            )
        }

    def fake_fetch_nws_forecast(city_key, dates, *, client=None):
        calls.append(("nws", city_key))
        return {dates[0]: (81.0, 66.0)}

    monkeypatch.setattr(weather_fetcher, "fetch_ensemble", blocked_fetch_ensemble)
    monkeypatch.setattr(weather_fetcher, "fetch_gribstream_nbm_forecast", fake_fetch_gribstream)
    monkeypatch.setattr(weather_fetcher, "fetch_noaa_nbm_forecast", fake_fetch_noaa)
    monkeypatch.setattr(weather_fetcher, "fetch_nws_forecast", fake_fetch_nws_forecast)

    forecasts = weather_fetcher.get_forecasts(
        cities=["NYC"],
        days_ahead=1,
        include_metar=False,
        include_nws=True,
    )

    fc = forecasts["NYC"][next(iter(forecasts["NYC"]))]
    assert fc.source == "noaa_nbm"
    assert fc.nws_high_f == 81.0
    assert dict(fc.api_highs_f) == {"gribstream_nbm": 82.0, "noaa_nbm": 83.0}
    assert calls == [("nbm", "NYC"), ("gribstream", "NYC"), ("nws", "NYC")]


def test_get_forecasts_skips_gribstream_when_open_meteo_and_noaa_are_available(monkeypatch):
    _reset_weather_cache()
    monkeypatch.setenv("BOT_D_FORECAST_REQUEST_PAUSE_SEC", "0")
    monkeypatch.setenv("BOT_D_GRIBSTREAM_ENABLED", "true")
    calls = []

    def fake_fetch_ensemble(city_key, dates, *, client=None):
        calls.append(("ensemble", city_key, tuple(dates)))
        return {
            dates[0]: ForecastResult(
                city=city_key,
                date=dates[0],
                mean_high_f=82.0,
                std_high_f=3.0,
                mean_low_f=65.0,
                std_low_f=3.0,
                ensemble_count=31,
                source="multi_model",
                member_highs_f=(82.0,),
                member_lows_f=(65.0,),
            )
        }

    def fail_fetch_gribstream(*args, **kwargs):
        raise AssertionError("GribStream should not run when Open-Meteo + NOAA are available")

    def fake_fetch_noaa(city_key, dates, *, client=None):
        calls.append(("nbm", city_key, tuple(dates)))
        return {
            dates[0]: ForecastResult(
                city=city_key,
                date=dates[0],
                mean_high_f=83.0,
                std_high_f=2.0,
                mean_low_f=66.0,
                std_low_f=2.0,
                ensemble_count=1,
                source="noaa_nbm",
                member_highs_f=(83.0,),
                member_lows_f=(66.0,),
            )
        }

    monkeypatch.setattr(weather_fetcher, "fetch_ensemble", fake_fetch_ensemble)
    monkeypatch.setattr(weather_fetcher, "fetch_gribstream_nbm_forecast", fail_fetch_gribstream)
    monkeypatch.setattr(weather_fetcher, "fetch_noaa_nbm_forecast", fake_fetch_noaa)
    monkeypatch.setattr(weather_fetcher, "fetch_nws_forecast", lambda *a, **k: {})

    forecasts = weather_fetcher.get_forecasts(
        cities=["NYC"],
        days_ahead=3,
        include_metar=False,
        include_nws=True,
        target_dates_by_city={"NYC": ["2026-05-06"]},
    )

    fc = forecasts["NYC"]["2026-05-06"]
    assert fc.source == "multi_model"
    assert dict(fc.api_highs_f) == {"multi_model": 82.0, "noaa_nbm": 83.0}
    assert calls == [
        ("ensemble", "NYC", ("2026-05-06",)),
        ("nbm", "NYC", ("2026-05-06",)),
    ]


def test_get_forecasts_uses_noaa_nbm_before_nws_fallback(monkeypatch):
    _reset_weather_cache()
    monkeypatch.setenv("BOT_D_FORECAST_REQUEST_PAUSE_SEC", "0")
    monkeypatch.setenv("BOT_D_GRIBSTREAM_ENABLED", "false")
    calls = []

    def blocked_fetch_ensemble(city_key, dates, *, client=None):
        weather_fetcher._OPEN_METEO_COOLDOWN_UNTIL = time.time() + 60
        return {}

    def fake_fetch_noaa_nbm(city_key, dates, *, client=None):
        calls.append(("nbm", city_key))
        return {
            dates[0]: _fc(
                city=city_key,
                date=dates[0],
                mean_high=82.0,
                mean_low=65.0,
            ).__class__(
                city=city_key,
                date=dates[0],
                mean_high_f=82.0,
                std_high_f=2.0,
                mean_low_f=65.0,
                std_low_f=2.0,
                ensemble_count=1,
                source="noaa_nbm",
                member_highs_f=(82.0,),
                member_lows_f=(65.0,),
            )
        }

    def fake_fetch_nws_forecast(city_key, dates, *, client=None):
        calls.append(("nws", city_key))
        return {dates[0]: (81.0, 66.0)}

    monkeypatch.setattr(weather_fetcher, "fetch_ensemble", blocked_fetch_ensemble)
    monkeypatch.setattr(weather_fetcher, "fetch_noaa_nbm_forecast", fake_fetch_noaa_nbm)
    monkeypatch.setattr(weather_fetcher, "fetch_nws_forecast", fake_fetch_nws_forecast)

    forecasts = weather_fetcher.get_forecasts(
        cities=["NYC"],
        days_ahead=1,
        include_metar=False,
        include_nws=True,
    )

    fc = forecasts["NYC"][next(iter(forecasts["NYC"]))]
    assert fc.source == "noaa_nbm"
    assert fc.mean_high_f == 82.0
    assert fc.nws_high_f == 81.0
    assert dict(fc.api_highs_f) == {"noaa_nbm": 82.0}
    assert calls == [("nbm", "NYC"), ("nws", "NYC")]


def test_get_forecasts_tolerates_nws_bypass_none(monkeypatch):
    _reset_weather_cache()
    monkeypatch.setenv("BOT_D_FORECAST_REQUEST_PAUSE_SEC", "0")
    monkeypatch.setenv("BOT_D_NOAA_NBM_ENABLED", "false")

    def blocked_fetch_ensemble(city_key, dates, *, client=None):
        weather_fetcher._OPEN_METEO_COOLDOWN_UNTIL = time.time() + 60
        return {}

    monkeypatch.setattr(weather_fetcher, "fetch_ensemble", blocked_fetch_ensemble)
    monkeypatch.setattr(weather_fetcher, "fetch_nws_forecast", lambda *a, **k: None)

    forecasts = weather_fetcher.get_forecasts(
        cities=["NYC"],
        days_ahead=1,
        include_metar=False,
        include_nws=True,
    )

    assert forecasts == {}


def test_scan_summary_payload_buckets_skip_reasons():
    from bots.bot_d_weather import __main__ as bot_d_main

    skipped = evaluate_weather_market(
        _mkt(lo=74.0, hi=76.0, yes_price=0.25),
        _fc(mean_high=75.0, std_high=3.0),
    )
    edge = evaluate_weather_market(
        _mkt(lo=74.0, hi=76.0, yes_price=0.05),
        _fc(mean_high=75.0, std_high=2.0),
    )

    payload = bot_d_main._scan_summary_payload(
        raw_markets=3,
        kept_markets=2,
        decisions=[skipped, edge],
        missing_forecasts=1,
        per_event=[edge],
        tradeable=[],
    )

    assert payload["raw_markets"] == 3
    assert payload["kept_markets"] == 2
    assert payload["evaluated"] == 2
    assert payload["missing_forecasts"] == 1
    assert payload["non_skip"] == 1
    assert payload["skip_reasons"]["below_threshold"] == 1
    assert payload["forecast_sources"]["ensemble"] == 2
    assert payload["nws_shadow"]["vetoed"] == 0
    assert payload["top_positive_net_edge"] > 0


def test_scan_summary_payload_counts_looser_nws_shadow(monkeypatch):
    from bots.bot_d_weather import __main__ as bot_d_main
    from bots.bot_d_weather import config as bot_d_cfg

    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_VETO_OVERRIDE_ENABLED", False)

    vetoed = evaluate_weather_market(
        _mkt(lo=73.0, hi=77.0, yes_price=0.05),
        _fc(mean_high=75.0, std_high=3.0, nws_high=72.4),
    )

    payload = bot_d_main._scan_summary_payload(
        raw_markets=1,
        kept_markets=1,
        decisions=[vetoed],
        missing_forecasts=0,
        per_event=[],
        tradeable=[],
    )

    assert payload["skip_reasons"]["nws_disagrees"] == 1
    assert payload["nws_shadow"]["vetoed"] == 1
    assert payload["nws_shadow"]["would_clear_edge_floor_3f"] == 1
    assert payload["nws_shadow"]["would_clear_edge_nws_off"] == 1


# --- City resolution ----------------------------------------------------------

def test_resolve_nyc():
    assert resolve_city("New York City") == "NYC"
    assert resolve_city("nyc") == "NYC"


def test_resolve_tokyo():
    assert resolve_city("Tokyo") == "Tokyo"


def test_resolve_unknown():
    assert resolve_city("Narnia") is None


def test_all_cities_have_aliases():
    for key, cfg in CITIES.items():
        assert len(cfg.aliases) > 0, f"{key} has no aliases"


def test_verified_settlement_specs_use_airport_stations():
    assert SETTLEMENT_SPECS["NYC"].station == "KLGA"
    assert SETTLEMENT_SPECS["Dallas"].station == "KDAL"
    assert SETTLEMENT_SPECS["Dallas"].forecast_lat == CITIES["Dallas"].lat
    assert SETTLEMENT_SPECS["Dallas"].forecast_lon == CITIES["Dallas"].lon


def test_settlement_rounding_half_up_fahrenheit():
    assert apply_settlement_value("Dallas", 72.49) == 72.0
    assert apply_settlement_value("Dallas", 72.50) == 73.0


def test_settlement_rounding_happens_in_native_celsius():
    # Tokyo settles in whole Celsius; 19.5 C should round to 20 C, then
    # compare in Bot D's normalized Fahrenheit bucket space.
    assert round(apply_settlement_value("Tokyo", 67.1), 1) == 68.0


def test_settlement_rounding_counterfactual_helper_supports_floor():
    assert settlement_value_for_rounding("Dallas", 72.99, "nearest_int") == 73.0
    assert settlement_value_for_rounding("Dallas", 72.99, "floor") == 72.0
    # 22.9 C should floor to 22 C, then convert back to Fahrenheit.
    assert round(settlement_value_for_rounding("Tokyo", 73.22, "floor"), 1) == 71.6


def test_paper_candidate_filter_keeps_verified_daily_only(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from bots.bot_d_weather import __main__ as bot_d_main

    monkeypatch.setattr(bot_d_main, "BOT_D_REQUIRE_VERIFIED_SETTLEMENT", True)
    monkeypatch.setattr(bot_d_main, "BOT_D_REQUIRE_KNOWN_END_DATE", True)
    monkeypatch.setattr(bot_d_main, "BOT_D_MAX_LOCKUP_HOURS", 48.0)
    monkeypatch.setattr(bot_d_main, "BOT_D_MIN_ENTRY_HOURS_TO_END", 2.0)

    soon = datetime.now(UTC) + timedelta(hours=24)
    late = datetime.now(UTC) + timedelta(hours=72)
    ended_at = datetime.now(UTC) - timedelta(minutes=1)
    too_soon = datetime.now(UTC) + timedelta(minutes=30)
    keep = _mkt(city="NYC", gamma_id="keep", yes_price=0.20)
    keep = WeatherMarket(**{**keep.__dict__, "end_date": soon})
    unverified = _mkt(city="Houston", gamma_id="unverified", yes_price=0.20)
    unverified = WeatherMarket(**{**unverified.__dict__, "end_date": soon})
    weekly = _mkt(city="NYC", gamma_id="weekly", yes_price=0.20)
    weekly = WeatherMarket(**{**weekly.__dict__, "end_date": late})
    ended = _mkt(city="NYC", gamma_id="ended", yes_price=0.20)
    ended = WeatherMarket(**{**ended.__dict__, "end_date": ended_at})
    nearly_ended = _mkt(city="NYC", gamma_id="nearly-ended", yes_price=0.20)
    nearly_ended = WeatherMarket(**{**nearly_ended.__dict__, "end_date": too_soon})
    missing_end = _mkt(city="NYC", gamma_id="missing-end", yes_price=0.20)

    result = bot_d_main._paper_candidate_markets([
        keep,
        unverified,
        weekly,
        ended,
        nearly_ended,
        missing_end,
    ])

    assert [m.gamma_id for m in result] == ["keep"]


# --- Question parsing ---------------------------------------------------------

@freeze_time("2026-04-15 12:00:00", tz_offset=0)
def test_parse_between_fahrenheit():
    # Freeze clock to 2026-04-15 so "April 17" resolves to 2026-04-17 rather
    # than rolling forward to 2027. The production roll-forward logic is
    # correct (see bots/bot_d_weather/discovery.py::_parse_date); it just
    # needs a frozen `now` for deterministic assertion.
    r = parse_weather_question(
        "Will the highest temperature in New York City be between 86-87°F on April 17?"
    )
    assert r is not None
    assert r["city"] == "NYC"
    assert r["direction"] == "between"
    assert r["range_low_f"] == 86.0
    assert r["range_high_f"] == 87.0
    assert r["temp_type"] == "high"
    assert r["date"] == "2026-04-17"


def test_parse_or_below():
    r = parse_weather_question(
        "Will the highest temperature in Houston be 79°F or below on April 17?"
    )
    assert r is not None
    assert r["city"] == "Houston"
    assert r["direction"] == "below"
    assert r["range_high_f"] == 79.0
    assert r["range_low_f"] is None


def test_parse_celsius_exact(monkeypatch):
    """Exact-temp markets are blacklisted by default (Phase 3). Disable the
    flag to exercise the parser."""
    from bots.bot_d_weather import config as bot_d_cfg
    monkeypatch.setattr(bot_d_cfg, "BOT_D_BLACKLIST_EXACT_TEMP", False)
    r = parse_weather_question(
        "Will the highest temperature in Tokyo be 19°C on April 16?"
    )
    assert r is not None
    assert r["city"] == "Tokyo"
    assert r["direction"] == "between"
    # 19°C = 66.2°F, 20°C = 68.0°F
    assert abs(r["range_low_f"] - 66.2) < 0.1
    assert abs(r["range_high_f"] - 68.0) < 0.1


def test_parse_celsius_exact_blacklisted_by_default():
    """Phase 3 audit 2026-04-17: blacklist on by default."""
    r = parse_weather_question(
        "Will the highest temperature in Tokyo be 19°C on April 16?"
    )
    assert r is None


def test_parse_lowest_temperature():
    r = parse_weather_question(
        "Will the lowest temperature in London be 6°C or below on April 15?"
    )
    assert r is not None
    assert r["city"] == "London"
    assert r["temp_type"] == "low"
    assert r["direction"] == "below"


def test_parse_unrelated_returns_none():
    assert parse_weather_question("Will Trump win 2028?") is None
    assert parse_weather_question("Will BTC be above $100k?") is None


@freeze_time("2026-05-19 10:00:00", tz_offset=0)
def test_fetch_weather_markets_event_slug_fallback_finds_hidden_daily_temperature():
    """Daily-temperature events can be hidden from Gamma's active/tag feeds.

    The child markets may still have acceptingOrders=true, so discovery falls
    back to known event slugs and parses those child market rows.
    """

    class Resp:
        def __init__(self, status_code: int, payload):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError(f"unexpected status {self.status_code}")

        def json(self):
            return self._payload

    class Client:
        def get(self, url, params=None):
            if "events/slug/highest-temperature-in-nyc-on-may-20-2026" in url:
                return Resp(200, {
                    "markets": [{
                        "id": "m1",
                        "conditionId": "c1",
                        "question": "Will the highest temperature in New York City be between 86-87°F on May 20?",
                        "slug": "highest-temperature-in-nyc-on-may-20-2026-86-87f",
                        "acceptingOrders": True,
                        "enableOrderBook": True,
                        "outcomes": '["Yes", "No"]',
                        "outcomePrices": '["0.2", "0.8"]',
                        "clobTokenIds": '["yes-token", "no-token"]',
                        "endDate": "2026-05-20T12:00:00Z",
                    }]
                })
            if "events/slug/" in url:
                return Resp(404, {})
            return Resp(200, [{
                "id": "non-weather",
                "question": "Will Amanda Anisimova win Wimbledon?",
                "outcomes": '["Yes", "No"]',
                "outcomePrices": '["0.2", "0.8"]',
                "clobTokenIds": '["x", "y"]',
            }])

    markets = fetch_weather_markets(client=Client(), limit=1)

    assert len(markets) == 1
    assert markets[0].gamma_id == "m1"
    assert markets[0].city == "NYC"
    assert markets[0].date == "2026-05-20"
    assert markets[0].yes_token_id == "yes-token"


def test_run_scan_logs_discovery_health_when_no_markets(monkeypatch):
    from bots.bot_d_weather import __main__ as bot_d_main

    calls = []
    monkeypatch.setattr(bot_d_main, "fetch_weather_markets", lambda client=None: [])
    monkeypatch.setattr(bot_d_main, "log_discovery_health", lambda sf, payload: calls.append(payload))
    monkeypatch.setattr("core.db.get_session_factory", lambda: object())

    assert bot_d_main.run_scan() == (0, 0, 0)

    assert len(calls) == 1
    assert calls[0]["reason"] == "zero_temperature_markets"
    assert calls[0]["raw_markets"] == 0
    assert calls[0]["kept_markets"] == 0


# --- Probability function -----------------------------------------------------

def test_range_probability_symmetric():
    """Mean=75, std=3: P(74 ≤ X ≤ 76) should be ~26%."""
    p = range_probability(75.0, 3.0, 74.0, 76.0)
    assert 0.20 < p < 0.35


def test_range_probability_above():
    """P(X ≥ 70) for N(75,3) should be ~95%."""
    p = range_probability(75.0, 3.0, 70.0, None)
    assert p > 0.90


def test_range_probability_below():
    """P(X ≤ 80) for N(75,3) should be ~95%."""
    p = range_probability(75.0, 3.0, None, 80.0)
    assert p > 0.90


def test_range_probability_far_otm():
    """P(90 ≤ X ≤ 91) for N(75,3) should be near 0."""
    p = range_probability(75.0, 3.0, 90.0, 91.0)
    assert p < 0.01


def test_empirical_bucket_probability_counts_rounded_members():
    p = empirical_bucket_probability(
        "Dallas",
        (74.4, 74.6, 75.2, 80.0),
        74.0,
        75.0,
    )
    assert p == 0.75


# --- Edge evaluation ----------------------------------------------------------

def test_evaluate_buy_yes_when_model_higher():
    m = _mkt(lo=74.0, hi=76.0, yes_price=0.05)  # market says 5%
    fc = _fc(mean_high=75.0, std_high=2.0)  # model says ~26%
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "BUY_YES"
    assert dec.net_edge > 0.08


def test_evaluate_buy_no_when_model_much_lower():
    m = _mkt(lo=90.0, hi=91.0, yes_price=0.20)  # market says 20%
    fc = _fc(mean_high=75.0, std_high=3.0)  # model says <1%
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "BUY_NO"
    assert dec.net_edge < -0.08


def test_evaluate_skip_when_edge_small():
    m = _mkt(lo=74.0, hi=76.0, yes_price=0.25)  # near model estimate
    fc = _fc(mean_high=75.0, std_high=3.0)
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "SKIP"


def test_evaluate_uses_low_temp_when_type_low():
    m = _mkt(temp_type="low", direction="below", lo=None, hi=40.0, yes_price=0.30)
    fc = _fc(mean_low=55.0, std_low=2.0)  # P(X≤40) is tiny; market says 30% → BUY_NO
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "BUY_NO"


def test_evaluate_skips_when_empirical_members_disagree_with_cdf():
    m = _mkt(lo=74.0, hi=76.0, yes_price=0.05)
    fc = _fc(mean_high=75.0, std_high=2.0, member_highs=(90.0,) * 31)
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "SKIP"
    assert "ensemble_shape_disagrees" in dec.reason
    assert dec.empirical_probability == 0.0
    assert dec.probability_disagreement is not None
    assert dec.probability_disagreement > 0.10


def test_single_member_fallback_does_not_trigger_empirical_shape_veto():
    m = _mkt(lo=74.0, hi=76.0, yes_price=0.05)
    fc = _fc(mean_high=75.0, std_high=2.0, member_highs=(90.0,))
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "BUY_YES"
    assert dec.empirical_probability is None
    assert dec.probability_disagreement is None


def test_observed_high_so_far_does_not_hard_zero_bounded_bucket():
    m = _mkt(lo=74.0, hi=76.0, yes_price=0.45)
    fc = _fc(mean_high=75.0, std_high=2.0, metar_max=80.0)
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "SKIP"
    assert 0.001 < dec.gfs_probability < 0.999
    assert dec.settlement_constraint is None
    assert "observed_high_exceeds_bucket" not in dec.reason
    assert "buy_no_mean_inside_yes_bucket" in dec.reason


def test_buy_no_skips_when_forecast_mean_inside_yes_bucket():
    m = _mkt(lo=60.0, hi=61.0, yes_price=0.45)
    fc = _fc(mean_high=60.0, std_high=3.3)
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "SKIP"
    assert "buy_no_mean_inside_yes_bucket" in dec.reason


def test_observed_high_so_far_marks_above_threshold_true():
    m = _mkt(direction="above", lo=80.0, hi=None, yes_price=0.30)
    fc = _fc(mean_high=75.0, std_high=2.0, metar_max=80.0)
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "BUY_YES"
    assert dec.gfs_probability == 0.999
    assert dec.settlement_constraint is not None
    assert "observed_high_reached_threshold" in dec.reason


# --- One-bet-per-event --------------------------------------------------------

def test_one_bet_per_event_keeps_highest_edge():
    d1 = evaluate_weather_market(_mkt(lo=74, hi=76, yes_price=0.05, gamma_id="g1"),
                                 _fc(mean_high=75))
    d2 = evaluate_weather_market(_mkt(lo=70, hi=72, yes_price=0.01, gamma_id="g2"),
                                 _fc(mean_high=75))
    # Both are NYC 2026-04-16 high. Only the one with bigger |edge| survives.
    result = apply_one_bet_per_event([d1, d2])
    assert len(result) == 1


def test_one_bet_per_event_different_cities_both_survive():
    d1 = evaluate_weather_market(
        _mkt(city="NYC", lo=74, hi=76, yes_price=0.05, gamma_id="g1"),
        _fc(city="NYC", mean_high=75),
    )
    d2 = evaluate_weather_market(
        _mkt(city="Tokyo", lo=18*9/5+32, hi=19*9/5+32, yes_price=0.05, gamma_id="g2"),
        _fc(city="Tokyo", mean_high=18*9/5+32),
    )
    result = apply_one_bet_per_event([d1, d2])
    assert len(result) == 2


def test_one_bet_per_event_skip_excluded():
    d1 = evaluate_weather_market(_mkt(lo=74, hi=76, yes_price=0.25, gamma_id="g1"),
                                 _fc(mean_high=75))
    # This one will be SKIP (edge too small)
    result = apply_one_bet_per_event([d1])
    assert len(result) == 0


def test_wave_regime_sizing_marks_cluster_full_size():
    decisions = [
        _dec for _dec in (
            evaluate_weather_market(
                _mkt(city=city, date="2026-04-16", lo=90, hi=91, yes_price=0.20, gamma_id=gid),
                _fc(city=city, mean_high=75),
            )
            for city, gid in (("NYC", "g1"), ("Chicago", "g2"), ("Dallas", "g3"))
        )
    ]
    result = apply_wave_regime_sizing(
        decisions,
        enabled=True,
        min_markets=3,
        isolated_size_factor=Decimal("0.50"),
        wave_size_factor=Decimal("1.00"),
    )
    assert len(result) == 3
    assert {d.regime for d in result} == {"wave"}
    assert {d.wave_count for d in result} == {3}
    assert {d.size_multiplier for d in result} == {Decimal("1.00")}


def test_wave_regime_sizing_reduces_isolated_not_filters():
    d = evaluate_weather_market(
        _mkt(city="NYC", date="2026-04-16", lo=90, hi=91, yes_price=0.20, gamma_id="solo"),
        _fc(city="NYC", mean_high=75),
    )
    result = apply_wave_regime_sizing(
        [d],
        enabled=True,
        min_markets=3,
        isolated_size_factor=Decimal("0.50"),
        require_wave=False,
    )
    assert len(result) == 1
    assert result[0].regime == "isolated"
    assert result[0].wave_count == 1
    assert result[0].size_multiplier == Decimal("0.50")


def test_wave_regime_sizing_can_require_wave():
    d = evaluate_weather_market(
        _mkt(city="NYC", date="2026-04-16", lo=90, hi=91, yes_price=0.20, gamma_id="solo"),
        _fc(city="NYC", mean_high=75),
    )
    result = apply_wave_regime_sizing(
        [d],
        enabled=True,
        min_markets=3,
        require_wave=True,
    )
    assert result == []
