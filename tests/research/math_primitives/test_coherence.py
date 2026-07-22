"""Tests for the coherence / basket-arb primitives."""
from __future__ import annotations

import pytest

from scripts.research.math_primitives.coherence import (
    detect_basket_arb,
    detect_linked_time_bucket_violation,
    detect_threshold_ladder_violations,
    expected_profit_per_dollar_per_day,
)


def test_basket_arb_buy_when_sum_asks_below_one():
    legs = [
        {"market_id": "A", "best_bid": 0.30, "best_ask": 0.35, "top_bid_size": 100, "top_ask_size": 100},
        {"market_id": "B", "best_bid": 0.45, "best_ask": 0.50, "top_bid_size": 100, "top_ask_size": 100},
    ]
    # sum_asks = 0.85 → gross BUY edge = 0.15. Fees small, well above threshold.
    violation = detect_basket_arb(legs=legs, fee_rate=0.072, min_edge=0.005)
    assert violation is not None
    assert violation.kind == "BUY_BASKET"
    assert violation.gross_edge == pytest.approx(0.15)
    assert violation.fillable_size == 100.0
    assert violation.expected_profit_usd > 0


def test_basket_arb_sell_when_sum_bids_above_one():
    legs = [
        {"market_id": "A", "best_bid": 0.65, "best_ask": 0.70, "top_bid_size": 50, "top_ask_size": 50},
        {"market_id": "B", "best_bid": 0.55, "best_ask": 0.60, "top_bid_size": 50, "top_ask_size": 50},
    ]
    # sum_bids = 1.20 → SELL edge = 0.20 (gross). Fees small.
    violation = detect_basket_arb(legs=legs, fee_rate=0.072, min_edge=0.005)
    assert violation is not None
    assert violation.kind == "SELL_BASKET"
    assert violation.gross_edge == pytest.approx(0.20)
    assert violation.fillable_size == 50.0


def test_basket_arb_returns_none_when_no_edge():
    legs = [
        {"market_id": "A", "best_bid": 0.45, "best_ask": 0.50, "top_bid_size": 100, "top_ask_size": 100},
        {"market_id": "B", "best_bid": 0.45, "best_ask": 0.50, "top_bid_size": 100, "top_ask_size": 100},
    ]
    # sum_asks = 1.00, sum_bids = 0.90 → no edge
    violation = detect_basket_arb(legs=legs, fee_rate=0.072, min_edge=0.005)
    assert violation is None


def test_basket_arb_fees_can_eliminate_thin_edge():
    legs = [
        {"market_id": "A", "best_bid": 0.49, "best_ask": 0.498, "top_bid_size": 100, "top_ask_size": 100},
        {"market_id": "B", "best_bid": 0.49, "best_ask": 0.498, "top_bid_size": 100, "top_ask_size": 100},
    ]
    # gross BUY edge = 0.004 — below min_edge after fees
    violation = detect_basket_arb(legs=legs, fee_rate=0.072, min_edge=0.005)
    assert violation is None


def test_basket_arb_requires_two_legs():
    legs = [
        {"market_id": "A", "best_bid": 0.30, "best_ask": 0.35, "top_bid_size": 100, "top_ask_size": 100},
    ]
    assert detect_basket_arb(legs=legs, fee_rate=0.072) is None


def test_threshold_ladder_no_violations_in_monotone_sequence():
    rungs = [
        {"threshold": 60, "p_at_or_above": 0.95},
        {"threshold": 65, "p_at_or_above": 0.80},
        {"threshold": 70, "p_at_or_above": 0.50},
        {"threshold": 75, "p_at_or_above": 0.20},
    ]
    violations = detect_threshold_ladder_violations(rungs)
    assert violations == []


def test_threshold_ladder_detects_violation():
    rungs = [
        {"threshold": 60, "p_at_or_above": 0.50},
        {"threshold": 65, "p_at_or_above": 0.70},  # higher threshold but higher prob — inversion
        {"threshold": 70, "p_at_or_above": 0.30},
    ]
    violations = detect_threshold_ladder_violations(rungs)
    # Pair (0, 1): p_j=0.70 > p_i=0.50 → violation
    # Pair (0, 2): p_j=0.30 ≤ p_i=0.50 → ok
    # Pair (1, 2): p_j=0.30 ≤ p_i=0.70 → ok
    assert len(violations) == 1
    assert violations[0]["i"] == 0 and violations[0]["j"] == 1
    assert violations[0]["magnitude"] == pytest.approx(0.20)


def test_linked_time_bucket_no_violation_under_real_correlation():
    # 5m x 3 sub-windows each with p=0.5 for "Up"
    # Independence bound: 1 - 0.5^3 = 0.875
    # Real Brownian correlation should make parent ≥ 0.875
    sub = [0.5, 0.5, 0.5]
    parent_realistic = 0.85  # close to bound, within tolerance 0.05
    result = detect_linked_time_bucket_violation(
        sub, parent_realistic, tolerance=0.05
    )
    # Gap = 0.875 - 0.85 = 0.025 ≤ 0.05 → no violation
    assert result is None


def test_linked_time_bucket_detects_below_bound():
    sub = [0.5, 0.5, 0.5]
    parent_low = 0.50  # well below independence bound
    result = detect_linked_time_bucket_violation(
        sub, parent_low, tolerance=0.05
    )
    assert result is not None
    assert result["kind"] == "parent_below_independence_bound"
    assert result["gap"] == pytest.approx(0.875 - 0.50)


def test_linked_time_bucket_empty_subs():
    assert detect_linked_time_bucket_violation([], 0.5) is None


def test_expected_profit_per_dollar_per_day():
    # $5 profit on $100 capital locked for 5 days = $0.01/$/day
    result = expected_profit_per_dollar_per_day(
        expected_profit_usd=5.0,
        capital_required_usd=100.0,
        settlement_lag_days=5.0,
    )
    assert result == pytest.approx(0.01)


def test_expected_profit_zero_capital():
    assert (
        expected_profit_per_dollar_per_day(
            expected_profit_usd=10.0,
            capital_required_usd=0.0,
            settlement_lag_days=1.0,
        )
        == 0.0
    )


def test_expected_profit_zero_lag_returns_inf_for_positive():
    val = expected_profit_per_dollar_per_day(
        expected_profit_usd=5.0,
        capital_required_usd=100.0,
        settlement_lag_days=0.0,
    )
    assert val == float("inf")
