"""Tests for core/fees.py — Polymarket 2026 parabolic fee curve.

Updated 2026-04-17 after three-LLM audit (Gemini/GLM-5.1/Codex) confirmed
the shape is parabolic per Polymarket docs. See
`docs/audit/bots-a-d-e-audit-responses/` for the P0 justification.

Updated 2026-04-22 after Codex fleet review Section A #7 identified the
double-price bug: Polymarket fee is `size * baseRate * p * (1-p)`, not
`notional * baseRate * p * (1-p)`. The legacy function `taker_fee_rate`
returns the same value as before but is now interpreted as "USDC per
share", not "fraction of notional". Dollar-fee assertions have been
doubled (p=0.5) to match the corrected formula.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from core.fees import (
    TAKER_FEE_RATE_BY_CATEGORY,
    fee_for_fill,
    maker_rebate_rate,
    round_trip_cost_rate,
    taker_fee_rate,
)


def _peak(category: str) -> Decimal:
    """Expected peak fee at p=0.5 = feeRate * 0.25."""
    return TAKER_FEE_RATE_BY_CATEGORY[category] * Decimal("0.25")


class TestTakerFeeRate:
    def test_peak_at_50c_crypto(self):
        # At exactly 0.5: rate = feeRate * 0.25 = 0.072 * 0.25 = 0.018
        assert taker_fee_rate(0.5, "crypto") == _peak("crypto")

    def test_peak_at_50c_sports(self):
        assert taker_fee_rate(0.5, "sports") == _peak("sports")

    def test_peak_at_50c_weather(self):
        # weather feeRate 0.05 -> peak 0.0125
        assert taker_fee_rate(0.5, "weather") == Decimal("0.012500")

    def test_peak_at_50c_economics_fixed(self):
        # Was 0.0150 under triangular; corrected to 0.0125 per audit.
        assert taker_fee_rate(0.5, "economics") == Decimal("0.012500")

    def test_peak_at_50c_mentions_fixed(self):
        # Was 0.0156 under triangular; corrected to 0.0100 per audit.
        assert taker_fee_rate(0.5, "mentions") == Decimal("0.010000")

    def test_zero_at_boundary_prices(self):
        assert taker_fee_rate(0.0, "crypto") == Decimal("0")
        assert taker_fee_rate(1.0, "crypto") == Decimal("0")

    def test_parabolic_symmetric(self):
        for p in [Decimal("0.05"), Decimal("0.2"), Decimal("0.4")]:
            assert taker_fee_rate(p, "crypto") == taker_fee_rate(Decimal("1") - p, "crypto")

    def test_parabolic_shape_at_5c_crypto(self):
        # p=0.05 -> 0.072 * 0.05 * 0.95 = 0.00342
        got = taker_fee_rate(Decimal("0.05"), "crypto")
        assert got == Decimal("0.072") * Decimal("0.05") * Decimal("0.95")

    def test_parabolic_shape_at_25c_weather(self):
        # p=0.25 -> 0.05 * 0.25 * 0.75 = 0.009375
        got = taker_fee_rate(Decimal("0.25"), "weather")
        assert got == Decimal("0.009375")

    def test_geopolitics_zero(self):
        for p in [0.01, 0.25, 0.5, 0.75, 0.99]:
            assert taker_fee_rate(p, "geopolitics") == Decimal("0")

    def test_unknown_category_zero(self):
        assert taker_fee_rate(0.5, "nonexistent") == Decimal("0")

    def test_case_insensitive_category(self):
        assert taker_fee_rate(0.5, "CRYPTO") == taker_fee_rate(0.5, "crypto")


class TestMakerRebate:
    def test_default_is_zero_for_ev(self):
        # Audit: rebates are discretionary pool distributions, not guaranteed
        # per-fill revenue. EV math must treat as zero by default.
        for category in ["crypto", "weather", "politics"]:
            for price in [0.05, 0.3, 0.5, 0.7, 0.95]:
                assert maker_rebate_rate(price, category) == Decimal("0")

    def test_nominal_crypto_20pct(self):
        for price in [0.05, 0.3, 0.5, 0.95]:
            expected = taker_fee_rate(price, "crypto") * Decimal("0.20")
            assert maker_rebate_rate(price, "crypto", include_in_ev=True) == expected

    def test_nominal_non_crypto_25pct(self):
        for category in ["weather", "politics", "sports"]:
            for price in [0.05, 0.5, 0.95]:
                expected = taker_fee_rate(price, category) * Decimal("0.25")
                assert maker_rebate_rate(price, category, include_in_ev=True) == expected

    def test_rebate_always_nonneg(self):
        for category in ["crypto", "geopolitics"]:
            for price in [0.0, 0.01, 0.5, 0.99, 1.0]:
                assert maker_rebate_rate(price, category, include_in_ev=True) >= 0


class TestFeeForFill:
    def test_taker_fee_positive(self):
        # size 100 * per-share fee 0.018 = 1.80 USDC (Polymarket
        # formula: C * feeRate * p * (1-p)).
        fb = fee_for_fill(0.5, 100, "crypto", is_maker=False)
        assert fb.gross_fee == Decimal("1.8000")
        assert fb.is_maker_rebate is False

    def test_maker_rebate_accounting_uses_nominal(self):
        # Accounting path still records nominal rebate (for dashboard/P&L).
        # size 100 * 0.018 * 0.20 (crypto) = 0.36
        fb = fee_for_fill(0.5, 100, "crypto", is_maker=True)
        assert fb.gross_fee == Decimal("-0.3600000")
        assert fb.is_maker_rebate is True

    def test_maker_rebate_non_crypto_25pct(self):
        # weather per-share 0.0125; size 100 * 0.0125 * 0.25 = 0.3125
        fb = fee_for_fill(0.5, 100, "weather", is_maker=True)
        assert fb.gross_fee == Decimal("-0.3125000")

    def test_zero_for_geopolitics(self):
        fb_taker = fee_for_fill(0.5, 100, "geopolitics", is_maker=False)
        fb_maker = fee_for_fill(0.5, 100, "geopolitics", is_maker=True)
        assert fb_taker.gross_fee == Decimal("0")
        assert fb_maker.gross_fee == Decimal("0")


class TestRoundTripCost:
    def test_taker_round_trip_at_50c_crypto(self):
        # Per-share fee 0.018 USDC on both legs; normalized by entry_p 0.5.
        # cost = (0.018 + 0.018) / 0.5 = 0.072.
        cost = round_trip_cost_rate(
            0.5, 0.5, "crypto",
            entry_is_maker=False, exit_is_maker=False,
        )
        assert cost == Decimal("0.072")

    def test_maker_round_trip_is_zero_by_default(self):
        # EV-safe default: maker legs contribute zero to round-trip cost.
        cost = round_trip_cost_rate(
            0.5, 0.5, "crypto",
            entry_is_maker=True, exit_is_maker=True,
        )
        assert cost == Decimal("0")

    def test_maker_round_trip_with_rebate_negative(self):
        # Both rebates at 0.5 crypto: per-share = 0.018 * 0.20 = 0.0036.
        # cost = -(0.0036 + 0.0036) / 0.5 = -0.0144.
        cost = round_trip_cost_rate(
            0.5, 0.5, "crypto",
            entry_is_maker=True, exit_is_maker=True,
            include_maker_rebate=True,
        )
        assert cost == Decimal("-0.0144")

    def test_geopolitics_zero_cost(self):
        cost = round_trip_cost_rate(
            0.5, 0.6, "geopolitics",
            entry_is_maker=False, exit_is_maker=False,
        )
        assert cost == Decimal("0")

    def test_mixed_maker_taker_ev_default(self):
        # Maker entry contributes 0 (EV default); taker exit contributes
        # per-share fee at exit price, normalized by entry price.
        cost = round_trip_cost_rate(
            0.4, 0.6, "crypto",
            entry_is_maker=True, exit_is_maker=False,
        )
        taker_per_share_06 = taker_fee_rate(Decimal("0.6"), "crypto")
        expected = taker_per_share_06 / Decimal("0.4")
        assert cost == expected
