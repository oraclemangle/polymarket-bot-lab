"""Tests for _tail_scaled_cap — Session 17l Bot D sizing fix.

The tail-scaled cap addresses single-market payoff concentration on
low-priced markets. See bots/bot_d_weather/executor.py:_tail_scaled_cap
for rationale.
"""

from decimal import Decimal

import pytest

from bots.bot_d_weather.executor import _kelly_size, _tail_scaled_cap


BASE = Decimal("50.00")


class TestTailScaledCap:
    def test_no_reduction_above_twenty_percent(self):
        for p in (0.20, 0.25, 0.50, 0.80, 0.95):
            assert _tail_scaled_cap(p, BASE) == BASE

    def test_floor_at_five_percent_or_below(self):
        for p in (0.05, 0.028, 0.01, 0.005):
            assert _tail_scaled_cap(p, BASE) == Decimal("30.00")

    def test_linear_midpoint(self):
        # At p=0.125, the midpoint between 0.05 and 0.20, factor should
        # be the midpoint between 0.60 and 1.00 = 0.80, giving $40.00.
        assert _tail_scaled_cap(0.125, BASE) == Decimal("40.00")

    def test_strictly_monotonic_in_p(self):
        caps = [_tail_scaled_cap(p, BASE) for p in (0.05, 0.10, 0.15, 0.20)]
        assert caps == sorted(caps)

    def test_proportional_to_base_cap(self):
        c1 = _tail_scaled_cap(0.028, Decimal("100"))
        c2 = _tail_scaled_cap(0.028, Decimal("50"))
        assert c1 == 2 * c2


class TestKellySizingWithTailScaling:
    """End-to-end: _kelly_size now applies the tail-scaled cap."""

    def test_lagos_scenario_before_and_after(self):
        """Reproduce the Lagos +$1,735 single-trade scenario.

        Previous tail guard: size capped at $15 (0.30 * base_cap).
        Session 27 tactical guard: size capped at $30 (0.60 * base_cap).
        """
        size = _kelly_size(
            p_model=0.50, p_market=0.028,
            bankroll=Decimal("5000"),
            kelly_fraction=0.15,
            max_per_trade=Decimal("50"),
        )
        assert size == Decimal("30.00")

    def test_mid_price_market_unaffected(self):
        """At p=0.50, there's no tail scaling — classic Kelly + cap applies."""
        size = _kelly_size(
            p_model=0.60, p_market=0.50,
            bankroll=Decimal("5000"),
            kelly_fraction=0.15,
            max_per_trade=Decimal("50"),
        )
        # Kelly f* = (0.60*1 - 0.40)/1 = 0.20; f_frac = 0.20 * 0.15 = 0.03
        # raw size = 0.03 * 5000 = $150 -> capped at $50
        assert size == Decimal("50.00")

    def test_tail_cap_is_binding_even_if_kelly_low(self):
        """Even when Kelly says stake less than the tail cap, the regular
        (non-scaled) logic passes through — the min clamps correctly.
        """
        size = _kelly_size(
            p_model=0.05, p_market=0.028,  # only marginally above market
            bankroll=Decimal("5000"),
            kelly_fraction=0.15,
            max_per_trade=Decimal("50"),
        )
        # p_model * b - q where b = (1 - 0.028)/0.028 = 34.71, p_model=0.05
        # = 0.05 * 34.71 - 0.95 = 1.7355 - 0.95 = 0.7855
        # f* = 0.7855 / 34.71 = 0.0226; f_frac = 0.0226 * 0.15 = 0.0034
        # raw = 0.0034 * 5000 = $17.00 -> cap is $30, so Kelly binds
        assert size == Decimal("16.98")

    def test_near_twenty_percent_tail_cap_almost_full(self):
        """At p just under 0.20, effective cap is almost the full base."""
        size = _kelly_size(
            p_model=0.50, p_market=0.19,
            bankroll=Decimal("5000"),
            kelly_fraction=0.15,
            max_per_trade=Decimal("50"),
        )
        # Tail cap at p=0.19 = 50 * (0.60 + 0.14*0.40/0.15) = 50 * 0.9733...
        # = $48.67
        assert size == Decimal("48.67")

    def test_three_cent_weather_tail_keeps_majority_size(self):
        assert _tail_scaled_cap(0.03, BASE) == Decimal("30.00")
