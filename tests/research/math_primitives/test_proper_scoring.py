"""Tests for the proper-scoring primitives."""
from __future__ import annotations

import math

import numpy as np
import pytest

from scripts.research.math_primitives.proper_scoring import (
    brier_score,
    log_loss,
    murphy_decomposition,
    reliability_curve,
    sharpness,
    spherical_score,
)


def test_brier_perfect_forecast_is_zero():
    p = [1.0, 0.0, 1.0, 0.0]
    y = [1, 0, 1, 0]
    assert brier_score(p, y) == 0.0


def test_brier_constant_half_is_quarter():
    p = [0.5, 0.5, 0.5, 0.5]
    y = [1, 0, 1, 0]
    assert brier_score(p, y) == pytest.approx(0.25)


def test_log_loss_perfect_clipped():
    # With clipping at eps=1e-15, the asymptotic infinite log-loss is
    # bounded. Perfect forecast still gives a finite small value.
    p = [1.0, 0.0]
    y = [1, 0]
    val = log_loss(p, y)
    assert 0 <= val < 1e-13


def test_log_loss_known_value():
    # log_loss(0.7, 1) = -log(0.7); log_loss(0.4, 0) = -log(0.6)
    p = [0.7, 0.4]
    y = [1, 0]
    expected = -(math.log(0.7) + math.log(0.6)) / 2
    assert log_loss(p, y) == pytest.approx(expected)


def test_spherical_score_perfect_is_one():
    p = [1.0, 0.0, 1.0]
    y = [1, 0, 1]
    assert spherical_score(p, y) == pytest.approx(1.0)


def test_spherical_score_uniform_is_inv_sqrt2():
    p = [0.5, 0.5, 0.5, 0.5]
    y = [1, 0, 1, 0]
    # For p=0.5, score = 0.5 / sqrt(0.5) = 1/sqrt(2)
    assert spherical_score(p, y) == pytest.approx(1.0 / math.sqrt(2.0))


def test_brier_input_validation():
    with pytest.raises(ValueError):
        brier_score([1.5], [1])
    with pytest.raises(ValueError):
        brier_score([0.5], [2])
    with pytest.raises(ValueError):
        brier_score([], [])
    with pytest.raises(ValueError):
        brier_score([0.5, 0.5], [1])


def test_murphy_decomposition_partition_holds_exactly_with_discrete_p():
    """Brier == reliability - resolution + uncertainty when each bin
    has a single discrete prediction value (Murphy 1973 conditions)."""
    # Use 3 discrete prediction values, n_bins large enough that each
    # value falls in its own bin.
    p_discrete = [0.1, 0.5, 0.9] * 200
    rng = np.random.default_rng(7)
    y = [int(rng.random() < pi) for pi in p_discrete]
    decomp = murphy_decomposition(p_discrete, y, n_bins=10)
    rebuilt = decomp.reliability - decomp.resolution + decomp.uncertainty
    assert decomp.brier == pytest.approx(rebuilt, abs=1e-10)


def test_murphy_decomposition_partition_within_within_bin_residual():
    """For continuous-prediction binned decomposition, the gap between
    Brier and (reliability - resolution + uncertainty) equals the
    within-bin variance of predictions, which is small but non-zero."""
    rng = np.random.default_rng(42)
    p = rng.uniform(0, 1, 1000)
    y = (rng.uniform(0, 1, 1000) < p).astype(int)
    decomp = murphy_decomposition(p, y, n_bins=10)
    rebuilt = decomp.reliability - decomp.resolution + decomp.uncertainty
    # Within-bin spread for n_bins=10 on uniform [0,1] is bounded by
    # (1/(2*n_bins))^2 = 0.0025; loose bound 0.005 is comfortable.
    assert abs(decomp.brier - rebuilt) < 0.005


def test_murphy_decomposition_calibrated_forecast():
    """Calibrated forecast: low reliability."""
    rng = np.random.default_rng(0)
    p = rng.uniform(0.1, 0.9, 5000)
    y = (rng.uniform(0, 1, 5000) < p).astype(int)
    decomp = murphy_decomposition(p, y, n_bins=10)
    # Reliability should be small because outcomes are drawn from p.
    assert decomp.reliability < 0.01


def test_murphy_decomposition_constant_forecast_zero_resolution():
    """If we always predict the base rate, resolution is zero."""
    n = 1000
    base_rate = 0.3
    p = [base_rate] * n
    rng = np.random.default_rng(7)
    y = (rng.uniform(0, 1, n) < base_rate).astype(int).tolist()
    decomp = murphy_decomposition(p, y, n_bins=10)
    # All predictions in one bin, mean predicted = base rate, mean
    # observed = base rate empirically, so resolution = 0 by construction.
    assert decomp.resolution == 0.0


def test_reliability_curve_skip_empty_bins():
    p = [0.05, 0.05, 0.95, 0.95]
    y = [0, 0, 1, 1]
    curve = reliability_curve(p, y, n_bins=10)
    # Only the first and last bins are populated.
    assert len(curve) == 2


def test_sharpness_extremes():
    # All confident predictions => low sharpness number (sharper)
    p_sharp = [0.01, 0.99, 0.02, 0.98]
    s_sharp = sharpness(p_sharp)
    p_dull = [0.5, 0.5, 0.5, 0.5]
    s_dull = sharpness(p_dull)
    assert s_sharp < s_dull
    assert s_dull == pytest.approx(0.25)
