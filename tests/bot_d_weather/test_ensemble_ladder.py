from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from bots.bot_d_weather import ensemble_ladder as ladder
from bots.bot_d_weather.discovery import WeatherMarket
from core.db import Event, Order, get_session_factory


def _mkt(
    *,
    gamma_id: str,
    city: str = "NYC",
    date: str = "2026-05-20",
    temp_type: str = "high",
    low: float = 70.0,
    high: float = 71.0,
    unit: str = "F",
    price: str = "0.10",
    end_hours: float = 24.0,
) -> WeatherMarket:
    return WeatherMarket(
        gamma_id=gamma_id,
        slug=f"slug-{gamma_id}",
        question=f"market {gamma_id}",
        city=city,
        date=date,
        temp_type=temp_type,
        direction="between",
        range_low_f=low,
        range_high_f=high,
        unit=unit,
        yes_token_id=f"yes-{gamma_id}",
        no_token_id=f"no-{gamma_id}",
        yes_price=Decimal(price),
        volume_24h_usd=Decimal("1000"),
        end_date=datetime.now(UTC) + timedelta(hours=end_hours),
    )


def _fc(
    *,
    city: str = "NYC",
    date: str = "2026-05-20",
    highs: dict[str, float] | None = None,
    lows: dict[str, float] | None = None,
) -> ladder.ThreeModelForecast:
    return ladder.ThreeModelForecast(
        city=city,
        date=date,
        model_highs_c=highs or {"icon": 21.0, "gfs": 20.0, "ecmwf": 20.2},
        model_lows_c=lows or {"icon": 14.0, "gfs": 13.5, "ecmwf": 13.7},
        fetched_at=datetime.now(UTC),
    )


def test_module_has_no_live_clob_path():
    source = inspect.getsource(ladder)
    assert "ClobWrapper" not in source
    assert "py_clob" not in source
    assert "Order(" not in source
    assert "Trade(" not in source
    assert "Position(" not in source


def test_assert_paper_only_blocks_live_env(monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    with pytest.raises(RuntimeError):
        ladder._assert_paper_only()


def test_candidate_filter_requires_verified_station_and_window():
    now = datetime.now(UTC)
    good = _mkt(gamma_id="good", end_hours=24)
    too_late = _mkt(gamma_id="late", end_hours=10)
    unverified = _mkt(gamma_id="hk", city="Hong Kong", low=22, high=23, unit="C", end_hours=24)

    kept = ladder.candidate_markets([good, too_late, unverified], now=now)

    assert [m.gamma_id for m in kept] == ["good"]


def test_three_bin_plan_uses_outlier_above_to_take_two_upper_bins():
    markets = [
        _mkt(gamma_id="68", low=68, high=69, price="0.02"),
        _mkt(gamma_id="70", low=70, high=71, price="0.05"),
        _mkt(gamma_id="72", low=72, high=73, price="0.28"),
        _mkt(gamma_id="74", low=74, high=75, price="0.21"),
    ]
    forecast = _fc(highs={"icon": 23.3, "gfs": 21.0, "ecmwf": 21.1})

    plan, reason = ladder.build_ladder_plan(markets, forecast)

    assert reason == "planned"
    assert plan is not None
    assert plan.closest_pair == ("gfs", "ecmwf")
    assert plan.outlier_model == "icon"
    assert [leg.market.gamma_id for leg in plan.legs] == ["70", "72", "74"]


def test_center_in_fahrenheit_gap_falls_back_to_nearest_midpoint():
    markets = [
        _mkt(gamma_id="56", low=56, high=57, price="0.08"),
        _mkt(gamma_id="58", low=58, high=59, price="0.12"),
        _mkt(gamma_id="60", low=60, high=61, price="0.18"),
    ]
    # 14.0C is 57.2F, in the gap between the 56-57 and 58-59 buckets.
    forecast = _fc(highs={"icon": 14.0, "gfs": 14.0, "ecmwf": 14.0})

    plan, reason = ladder.build_ladder_plan(markets, forecast)

    assert reason == "planned"
    assert plan is not None
    assert plan.legs[0].market.gamma_id == "56"


def test_celsius_market_uses_native_celsius_bounds():
    markets = [
        _mkt(gamma_id="20", city="London", unit="C", low=68.0, high=69.8, price="0.10"),
        _mkt(gamma_id="21", city="London", unit="C", low=69.8, high=71.6, price="0.20"),
        _mkt(gamma_id="22", city="London", unit="C", low=71.6, high=73.4, price="0.20"),
    ]
    forecast = _fc(city="London", highs={"icon": 21.1, "gfs": 21.0, "ecmwf": 20.9})

    plan, reason = ladder.build_ladder_plan(markets, forecast)

    assert reason == "planned"
    assert plan is not None
    assert plan.unit == "C"
    assert 20.9 <= plan.center_native <= 21.1
    assert any(leg.bucket_low_native == pytest.approx(20.0) for leg in plan.legs)


def test_spread_too_wide_skips_event():
    markets = [
        _mkt(gamma_id="70", low=70, high=71, price="0.05"),
        _mkt(gamma_id="72", low=72, high=73, price="0.05"),
    ]
    forecast = _fc(highs={"icon": 26.0, "gfs": 20.0, "ecmwf": 21.0})

    plan, reason = ladder.build_ladder_plan(markets, forecast)

    assert plan is None
    assert reason == "model_spread_too_wide"


def test_price_filters_reject_overpriced_leg():
    markets = [
        _mkt(gamma_id="70", low=70, high=71, price="0.46"),
        _mkt(gamma_id="72", low=72, high=73, price="0.05"),
    ]
    forecast = _fc(highs={"icon": 21.0, "gfs": 21.0, "ecmwf": 21.0})

    plan, reason = ladder.build_ladder_plan(markets, forecast)

    assert plan is None
    assert reason == "leg_price_too_high"


def test_run_once_records_event_rows_only(tmp_db, monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    session_factory = get_session_factory()
    markets = [
        _mkt(gamma_id="70", low=70, high=71, price="0.05"),
        _mkt(gamma_id="72", low=72, high=73, price="0.20"),
        _mkt(gamma_id="74", low=74, high=75, price="0.10"),
        _mkt(gamma_id="76", low=76, high=77, price="0.10"),
    ]
    forecasts = {
        ("NYC", "2026-05-20"): _fc(highs={"icon": 22.0, "gfs": 22.0, "ecmwf": 22.1})
    }

    summary = ladder.run_once(
        session_factory=session_factory,
        markets=markets,
        forecasts=forecasts,
    )
    duplicate_summary = ladder.run_once(
        session_factory=session_factory,
        markets=markets,
        forecasts=forecasts,
    )

    with session_factory() as session:
        plans = session.query(Event).filter(Event.event_type == "bot_d_ensemble_ladder.plan").all()
        orders = session.query(Order).all()

    assert summary["recorded_plans"] == 1
    assert duplicate_summary["duplicate_plans"] == 1
    assert len(plans) == 1
    assert plans[0].bot_id == "bot_d_ensemble_ladder"
    assert plans[0].payload["planned_stake_usd"] == "6"
    assert orders == []
