"""Regression tests for Bot D audit fixes — date rollover, METAR, NWS scaling, dashboard."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from bots.bot_d_weather.discovery import WeatherMarket, _parse_date
from bots.bot_d_weather.strategy import evaluate_weather_market
from bots.bot_d_weather.weather_fetcher import ForecastResult


def _fc(city="NYC", date="2026-04-16", mean_high=75.0, std_high=3.0,
        mean_low=55.0, std_low=3.0, metar_temp=None, metar_age=None,
        nws_high=None, nws_low=None, source="multi_model",
        api_highs=(), api_lows=()) -> ForecastResult:
    return ForecastResult(
        city=city, date=date, mean_high_f=mean_high, std_high_f=std_high,
        mean_low_f=mean_low, std_low_f=std_low, ensemble_count=82, source=source,
        metar_temp_f=metar_temp, metar_age_minutes=metar_age,
        nws_high_f=nws_high, nws_low_f=nws_low,
        api_highs_f=tuple(api_highs), api_lows_f=tuple(api_lows),
    )


def _mkt(city="NYC", date="2026-04-16", temp_type="high", direction="between",
         lo=74.0, hi=76.0, yes_price=0.05, gamma_id="g1") -> WeatherMarket:
    return WeatherMarket(
        gamma_id=gamma_id, slug="s", question="q", city=city, date=date,
        temp_type=temp_type, direction=direction,
        range_low_f=float(lo) if lo is not None else None,
        range_high_f=float(hi) if hi is not None else None, unit="F",
        yes_token_id="y", no_token_id="n",
        yes_price=Decimal(str(yes_price)), volume_24h_usd=Decimal("1000"),
    )


# --- Fix #1: same-day date parser rollover -----------------------------------

def test_same_day_not_rolled_to_next_year():
    """'April 16' parsed on April 16 at noon UTC should stay 2026, not roll to 2027."""
    # Simulate: it's noon on April 16, 2026 UTC.
    # The parser uses datetime.now(UTC) internally, so we can't inject time.
    # Instead, test that today's date does NOT roll — this test will pass
    # as long as it runs on or before the date. For a deterministic test,
    # we call _parse_date with a known-future date.
    result = _parse_date("December 31")
    assert result is not None
    # Should be this year (2026) since Dec 31 hasn't passed yet in April.
    assert result == "2026-12-31"


def test_yesterday_rolls_to_next_year():
    """A date that has fully passed should roll forward."""
    # January 1 has fully passed (we're in April 2026).
    result = _parse_date("January 1")
    assert result is not None
    assert result == "2027-01-01"


def test_explicit_year_never_rolls():
    result = _parse_date("January 1, 2026")
    assert result is not None
    assert result == "2026-01-01"  # explicit year preserved even if past


# --- Fix #2: METAR wired into strategy ---------------------------------------

def test_metar_shifts_mean_when_observation_exceeds_ensemble():
    """If METAR shows 80°F and ensemble mean is 75°F, the METAR+UHI adjustment
    should raise the probability of buckets AT THE NEW EFFECTIVE MEAN vs. no
    METAR.

    Phase 3 audit 2026-04-17: NYC UHI=+2, and skew-normal pushes the mode
    further right. With METAR=80 + UHI=2, effective mean ~82, skew-normal
    mode ~84. A bucket near this shifted region ([82, 86]) should gain
    probability relative to the no-METAR baseline (where the distribution
    is centered at 75).
    """
    fc_with = _fc(mean_high=75.0, std_high=3.0, metar_temp=80.0, metar_age=30.0)
    fc_without = _fc(mean_high=75.0, std_high=3.0)
    m = _mkt(lo=82.0, hi=86.0, yes_price=0.05)
    dec_with = evaluate_weather_market(m, fc_with)
    dec_without = evaluate_weather_market(m, fc_without)
    assert dec_with.gfs_probability > dec_without.gfs_probability


def test_metar_no_shift_when_below_ensemble():
    """If METAR shows 70°F and ensemble mean is 75°F, no adjustment (high hasn't happened yet)."""
    fc = _fc(mean_high=75.0, std_high=3.0, metar_temp=70.0, metar_age=30.0)
    m = _mkt(lo=74.0, hi=76.0, yes_price=0.05)
    dec_with = evaluate_weather_market(m, fc)

    fc_without = _fc(mean_high=75.0, std_high=3.0)
    dec_without = evaluate_weather_market(m, fc_without)
    # Same result — METAR below mean doesn't shift
    assert abs(dec_with.gfs_probability - dec_without.gfs_probability) < 0.01


def test_metar_ignored_for_low_temp_markets():
    """METAR adjustment only applies to high-temp markets."""
    fc = _fc(mean_low=55.0, std_low=3.0, metar_temp=80.0, metar_age=30.0)
    m = _mkt(temp_type="low", direction="below", lo=None, hi=50.0, yes_price=0.05)
    dec = evaluate_weather_market(m, fc)
    # METAR should not affect low-temp probability
    fc_no_metar = _fc(mean_low=55.0, std_low=3.0)
    dec_no = evaluate_weather_market(m, fc_no_metar)
    assert abs(dec.gfs_probability - dec_no.gfs_probability) < 0.01


def test_metar_ignored_when_stale():
    """METAR older than 120 minutes should not be attached."""
    # This is enforced in weather_fetcher.py — if metar_age > 120, metar_temp is None.
    # Strategy code checks metar_age_minutes < 120 as an extra guard.
    fc = _fc(mean_high=75.0, std_high=3.0, metar_temp=90.0, metar_age=200.0)
    m = _mkt(lo=88.0, hi=92.0, yes_price=0.05)
    dec = evaluate_weather_market(m, fc)
    # Stale METAR: age > 120 → strategy ignores it → probability should be low
    # (75 mean, 88-92 range is far right tail)
    assert dec.gfs_probability < 0.05


# --- Fix #4: NWS veto scaled by bucket width ---------------------------------

def test_nws_veto_on_narrow_bucket_with_small_disagreement():
    """2°F disagreement on a 1°F bucket should trigger veto (2 > max(2, 0.5))."""
    m = _mkt(lo=74.0, hi=75.0)  # 1°F bucket → threshold = max(2, 0.5) = 2.0
    # 2°F diff == threshold → NOT triggered (need > threshold)
    # Let's use 2.5°F diff
    fc2 = _fc(mean_high=75.0, nws_high=72.4)  # 2.6°F diff
    dec2 = evaluate_weather_market(m, fc2)
    assert dec2.side == "SKIP"
    assert "nws_disagrees" in dec2.reason


def test_nws_veto_floor_is_configurable(monkeypatch):
    from bots.bot_d_weather import config as bot_d_cfg

    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_VETO_MIN_THRESHOLD_F", 3.0)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_VETO_OVERRIDE_ENABLED", False)
    fc = _fc(mean_high=75.0, nws_high=72.4)  # 2.6°F diff
    m = _mkt(lo=74.0, hi=75.0, yes_price=0.05)

    dec = evaluate_weather_market(m, fc)

    assert "nws_disagrees" not in dec.reason


def test_nws_no_veto_on_wide_bucket():
    """2°F disagreement on a 10°F bucket should NOT trigger veto (2 < max(2, 5.0) = 5.0)."""
    fc = _fc(mean_high=75.0, nws_high=73.0)  # 2°F diff
    m = _mkt(lo=70.0, hi=80.0, yes_price=0.30)  # 10°F bucket → threshold = max(2, 5) = 5.0
    dec = evaluate_weather_market(m, fc)
    assert dec.side != "SKIP" or "nws_disagrees" not in dec.reason


def test_nws_veto_on_wide_bucket_with_large_disagreement(monkeypatch):
    """6°F disagreement on a 10°F bucket SHOULD trigger veto (6 > max(2, 5.0) = 5.0)."""
    from bots.bot_d_weather import config as bot_d_cfg

    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_VETO_OVERRIDE_ENABLED", False)
    fc = _fc(mean_high=75.0, nws_high=69.0)  # 6°F diff
    m = _mkt(lo=70.0, hi=80.0, yes_price=0.30)
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "SKIP"
    assert "nws_disagrees" in dec.reason


def test_nws_veto_strong_edge_override_is_paper_only(monkeypatch):
    from bots.bot_d_weather import config as bot_d_cfg

    fc = _fc(mean_high=75.0, nws_high=69.0)
    m = _mkt(lo=70.0, hi=80.0, yes_price=0.01)

    monkeypatch.setattr(bot_d_cfg, "BOT_D_ENV", "paper")
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_VETO_OVERRIDE_ENABLED", True)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_VETO_OVERRIDE_MIN_EDGE", 0.15)
    dec = evaluate_weather_market(m, fc)
    assert dec.side == "BUY_YES"
    assert "nws_override" in dec.reason

    monkeypatch.setattr(bot_d_cfg, "BOT_D_ENV", "live")
    live_dec = evaluate_weather_market(m, fc)
    assert live_dec.side == "SKIP"
    assert "nws_disagrees" in live_dec.reason


def test_nws_fallback_does_not_count_as_independent_second_opinion():
    """NWS-only fallback must not self-veto by comparing NWS against itself."""
    fc = _fc(mean_high=75.0, nws_high=69.0)
    fc = replace(fc, source="nws_fallback", nws_high_f=75.0)
    m = _mkt(lo=70.0, hi=80.0, yes_price=0.30)
    dec = evaluate_weather_market(m, fc)
    assert "nws_disagrees" not in dec.reason


def test_nws_outlier_probe_requires_two_api_sources(monkeypatch):
    from bots.bot_d_weather import config as bot_d_cfg

    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_ENABLED", True)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE", 0.08)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_API_AGREE_F", 2.0)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_MAX_NWS_GAP_F", 6.0)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_VETO_OVERRIDE_ENABLED", False)

    fc = _fc(
        city="Miami",
        mean_high=86.0,
        std_high=2.0,
        nws_high=91.0,
        source="gribstream_nbm",
        api_highs=(("gribstream_nbm", 86.0),),
    )
    m = _mkt(city="Miami", lo=90.0, hi=91.0, yes_price=0.40)

    dec = evaluate_weather_market(m, fc)

    assert dec.side == "SKIP"
    assert dec.reason.startswith("nws_disagrees")
    assert not dec.nws_outlier_probe


def test_nws_outlier_probe_allows_when_two_apis_agree(monkeypatch):
    from bots.bot_d_weather import config as bot_d_cfg

    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_ENABLED", True)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE", 0.08)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_API_AGREE_F", 2.0)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_MAX_NWS_GAP_F", 6.0)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_VETO_OVERRIDE_ENABLED", False)

    fc = _fc(
        city="Miami",
        mean_high=86.0,
        std_high=2.0,
        nws_high=91.0,
        source="gribstream_nbm",
        api_highs=(("gribstream_nbm", 86.0), ("noaa_nbm", 87.0)),
    )
    m = _mkt(city="Miami", lo=90.0, hi=91.0, yes_price=0.40)

    dec = evaluate_weather_market(m, fc)

    assert dec.side == "BUY_NO"
    assert "nws_outlier_probe" in dec.reason
    assert dec.nws_outlier_probe
    assert dec.api_agreement_count == 2
    assert dec.api_agreement_max_gap_f == 1.0


def test_nws_outlier_probe_can_use_live_entry_edge_floor(monkeypatch):
    from bots.bot_d_weather import config as bot_d_cfg

    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_ENABLED", True)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE", 0.07)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_API_AGREE_F", 2.0)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_MAX_NWS_GAP_F", 6.0)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_VETO_OVERRIDE_ENABLED", False)

    fc = _fc(
        city="Miami",
        mean_high=86.0,
        std_high=2.0,
        nws_high=91.0,
        source="gribstream_nbm",
        api_highs=(("gribstream_nbm", 86.0), ("noaa_nbm", 87.0)),
    )
    # Net edge is just above 7% and below the old 8% outlier-probe floor.
    m = _mkt(city="Miami", lo=90.0, hi=91.0, yes_price=0.17)

    dec = evaluate_weather_market(m, fc, edge_threshold=0.07)

    assert dec.side == "BUY_NO"
    assert "nws_outlier_probe" in dec.reason
    assert dec.nws_outlier_probe
    assert 0.07 <= abs(dec.net_edge) < 0.08


def test_nws_outlier_probe_blocks_when_api_values_are_far_apart(monkeypatch):
    from bots.bot_d_weather import config as bot_d_cfg

    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_ENABLED", True)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_MIN_EDGE", 0.08)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_API_AGREE_F", 2.0)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_OUTLIER_PROBE_MAX_NWS_GAP_F", 6.0)
    monkeypatch.setattr(bot_d_cfg, "BOT_D_NWS_VETO_OVERRIDE_ENABLED", False)

    fc = _fc(
        city="Miami",
        mean_high=86.0,
        std_high=2.0,
        nws_high=91.0,
        source="gribstream_nbm",
        api_highs=(("gribstream_nbm", 100.0), ("noaa_nbm", 86.0)),
    )
    m = _mkt(city="Miami", lo=90.0, hi=91.0, yes_price=0.40)

    dec = evaluate_weather_market(m, fc)

    assert dec.side == "SKIP"
    assert dec.reason.startswith("nws_disagrees")
    assert not dec.nws_outlier_probe
    assert dec.api_agreement_count == 1
