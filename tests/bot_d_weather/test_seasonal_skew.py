"""Bot D Phase 2 audit fixes: seasonal RMSE + skew-normal CDF."""
from __future__ import annotations

import importlib
from decimal import Decimal

import pytest

from bots.bot_d_weather import config as bot_d_config
from bots.bot_d_weather.config import (
    CITIES,
    effective_rmse_f,
    seasonal_rmse_multiplier,
)


class TestSeasonalRmseMultiplier:
    def test_summer_is_below_one_northern(self):
        for m in (6, 7, 8):
            assert seasonal_rmse_multiplier(m, southern_hemisphere=False) < 1.0

    def test_winter_is_above_one_northern(self):
        for m in (12, 1, 2):
            assert seasonal_rmse_multiplier(m, southern_hemisphere=False) > 1.0

    def test_southern_hemisphere_flipped(self):
        # Jan in S hemisphere = summer → multiplier < 1
        assert seasonal_rmse_multiplier(1, southern_hemisphere=True) < 1.0
        # Jul in S hemisphere = winter → multiplier > 1
        assert seasonal_rmse_multiplier(7, southern_hemisphere=True) > 1.0

    def test_invalid_month_returns_unit(self):
        assert seasonal_rmse_multiplier(0) == 1.0
        assert seasonal_rmse_multiplier(13) == 1.0


class TestEffectiveRmse:
    def test_seasonal_disabled_returns_baseline(self, monkeypatch):
        monkeypatch.setattr(bot_d_config, "BOT_D_RMSE_SEASONAL", False)
        nyc = CITIES["NYC"]
        for m in range(1, 13):
            assert effective_rmse_f(nyc, m) == nyc.rmse_f

    def test_seasonal_enabled_winter_above_summer(self, monkeypatch):
        monkeypatch.setattr(bot_d_config, "BOT_D_RMSE_SEASONAL", True)
        nyc = CITIES["NYC"]
        winter = effective_rmse_f(nyc, 1)
        summer = effective_rmse_f(nyc, 7)
        assert winter > nyc.rmse_f > summer

    def test_southern_hemisphere_city(self, monkeypatch):
        monkeypatch.setattr(bot_d_config, "BOT_D_RMSE_SEASONAL", True)
        sydney = CITIES["Sydney"]
        assert sydney.southern_hemisphere is True
        # January = Sydney summer → below baseline
        assert effective_rmse_f(sydney, 1) < sydney.rmse_f
        # July = Sydney winter → above baseline
        assert effective_rmse_f(sydney, 7) > sydney.rmse_f


class TestSkewNormalProbability:
    def test_skew_disabled_matches_gaussian(self, monkeypatch):
        monkeypatch.setattr(bot_d_config, "BOT_D_USE_SKEW_NORMAL", False)
        from bots.bot_d_weather.strategy import (
            _range_probability_with_shape,
            range_probability,
        )
        gauss = range_probability(mean=70.0, std=3.0, low=68.0, high=72.0)
        shape = _range_probability_with_shape(
            mean=70.0, std=3.0, low=68.0, high=72.0, temp_type="high",
        )
        assert abs(gauss - shape) < 1e-9

    def test_skew_high_shifts_upper_tail_up(self, monkeypatch):
        monkeypatch.setattr(bot_d_config, "BOT_D_USE_SKEW_NORMAL", True)
        monkeypatch.setattr(bot_d_config, "BOT_D_SKEW_HIGH", 3.0)
        from bots.bot_d_weather.strategy import (
            _range_probability_with_shape,
            range_probability,
        )
        # Upper-tail bucket (above the mean) should be MORE likely under
        # positive skew than under Gaussian.
        gauss = range_probability(mean=70.0, std=3.0, low=73.0, high=None)
        skew = _range_probability_with_shape(
            mean=70.0, std=3.0, low=73.0, high=None, temp_type="high",
        )
        assert skew > gauss

    def test_skew_low_shifts_lower_tail_down(self, monkeypatch):
        monkeypatch.setattr(bot_d_config, "BOT_D_USE_SKEW_NORMAL", True)
        monkeypatch.setattr(bot_d_config, "BOT_D_SKEW_LOW", -3.0)
        from bots.bot_d_weather.strategy import (
            _range_probability_with_shape,
            range_probability,
        )
        # Lower-tail bucket with negative skew: P(X <= mean-3) > Gaussian.
        gauss = range_probability(mean=40.0, std=3.0, low=None, high=37.0)
        skew = _range_probability_with_shape(
            mean=40.0, std=3.0, low=None, high=37.0, temp_type="low",
        )
        assert skew > gauss
