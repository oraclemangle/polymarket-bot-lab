"""Tests for bot_e_btc_scalp/regime.py — choppiness + bps-normalised trend."""
from __future__ import annotations

import pytest

from bots.bot_e_btc_scalp.regime import (
    choppiness_ratio,
    classify,
    dir_bps,
    should_skip_due_to_chop,
)


class TestChoppinessRatio:
    def test_pure_trend_zero_chop(self):
        closes = [100, 101, 102, 103, 104]
        assert choppiness_ratio(closes) == 0.0

    def test_pure_chop_one(self):
        closes = [100, 101, 100, 101, 100]  # alternating
        assert choppiness_ratio(closes) == 1.0

    def test_mixed(self):
        closes = [100, 101, 102, 101, 102]  # 3 ups, 1 down, 1 up
        # signs: +, +, -, + → reversals = 2 (between signs[1]->signs[2] and signs[2]->signs[3])
        # (len(signs)-1) = 3 intervals
        # ratio = 2/3
        assert abs(choppiness_ratio(closes) - 2/3) < 1e-9

    def test_requires_3_closes(self):
        with pytest.raises(ValueError):
            choppiness_ratio([100, 101])


class TestDirBps:
    def test_10pct_up_at_btc_scale(self):
        closes = [85000, 93500]
        # (93500 - 85000) / 93500 * 10000 ≈ 909.1 bps
        assert abs(dir_bps(closes) - 909.09) < 0.1

    def test_small_move(self):
        closes = [85000, 85042.5]  # $42.50 move
        # 42.5 / 85042.5 * 10000 ≈ 5 bps
        assert abs(dir_bps(closes) - 5.0) < 0.1

    def test_negative_down(self):
        closes = [100, 99]
        assert dir_bps(closes) == pytest.approx(-101.01, rel=1e-3)

    def test_single_close_zero(self):
        assert dir_bps([100]) == 0.0

    def test_zero_end_safe(self):
        # Defensive: avoid div by zero
        assert dir_bps([100, 0]) == 0.0


class TestClassify:
    def test_trending(self):
        closes = [100, 101, 102, 103, 104]  # monotonic up
        s = classify(closes, choppiness_max=0.65, trend_min_bps=50)
        assert s.regime == "trending"
        assert s.choppiness == 0.0

    def test_choppy(self):
        closes = [100, 101, 100, 101, 100]
        s = classify(closes, choppiness_max=0.65, trend_min_bps=50)
        assert s.regime == "choppy"

    def test_unknown_when_insufficient(self):
        s = classify([100, 101], choppiness_max=0.65, trend_min_bps=50)
        assert s.regime == "unknown"

    def test_unknown_when_below_trend_min(self):
        # Smooth sequence but tiny move
        closes = [100.00, 100.01, 100.02, 100.03, 100.04]
        s = classify(closes, choppiness_max=0.65, trend_min_bps=50)
        assert s.regime == "unknown"

    def test_trending_requires_both_low_chop_and_sufficient_move(self):
        # Low chop but move is only 4 bps — trend_min_bps=50 → unknown
        closes = [100.00, 100.01, 100.02, 100.03, 100.04]
        s = classify(closes, choppiness_max=0.65, trend_min_bps=50)
        assert s.regime == "unknown"


class TestShouldSkipDueToChop:
    def test_trending_passes(self):
        closes = [100, 101, 102, 103, 104]
        assert should_skip_due_to_chop(closes, choppiness_max=0.65) is False

    def test_choppy_skips(self):
        closes = [100, 101, 100, 101, 100]
        assert should_skip_due_to_chop(closes, choppiness_max=0.65) is True

    def test_insufficient_does_not_block(self):
        """Per spec: don't halt trading for lack of data."""
        closes = [100, 101]
        assert should_skip_due_to_chop(closes, choppiness_max=0.65) is False
