"""Tests for the BMA / EM primitive."""
from __future__ import annotations

import numpy as np
import pytest

from scripts.research.math_primitives.bma import (
    bucket_probability_bma,
    fit_bma_em,
    predict_bma,
)


def test_bma_with_one_strong_source_concentrates_weight():
    """If one source is much better, EM puts most weight on it."""
    rng = np.random.default_rng(42)
    n = 1000
    truth = rng.normal(0, 1, n)
    # Source A: nearly perfect
    src_a = truth + rng.normal(0, 0.1, n)
    # Source B: very noisy
    src_b = rng.normal(0, 5, n)
    forecasts = np.column_stack([src_a, src_b])
    fit = fit_bma_em(forecasts, truth, source_names=["a", "b"])
    assert fit.weights[0] > 0.8
    assert fit.weights[1] < 0.2
    # Sum of weights = 1
    assert sum(fit.weights) == pytest.approx(1.0)


def test_bma_recovers_per_source_bias():
    rng = np.random.default_rng(0)
    n = 1000
    truth = rng.normal(0, 1, n)
    # Source A is biased high by 2
    src_a = truth + 2.0 + rng.normal(0, 0.5, n)
    forecasts = src_a.reshape(-1, 1)
    fit = fit_bma_em(forecasts, truth, source_names=["a"])
    assert fit.biases[0] == pytest.approx(-2.0, abs=0.2)
    # With one source, weight = 1
    assert fit.weights[0] == pytest.approx(1.0)


def test_bma_predict_returns_calibrated_mean():
    rng = np.random.default_rng(7)
    n = 500
    truth = rng.normal(0, 1, n)
    src_a = truth + rng.normal(0, 0.3, n)
    src_b = truth + rng.normal(0, 0.3, n)
    forecasts = np.column_stack([src_a, src_b])
    fit = fit_bma_em(forecasts, truth, source_names=["a", "b"])
    mean_pred, sigma_pred = predict_bma(fit, forecasts)
    # Mean predictions should track truth
    corr = np.corrcoef(mean_pred, truth)[0, 1]
    assert corr > 0.9
    # Sigma should be positive
    assert np.all(sigma_pred > 0)


def test_bma_bucket_probability_in_range():
    rng = np.random.default_rng(3)
    n = 200
    truth = rng.normal(60, 5, n)  # temperatures around 60 F
    src_a = truth + rng.normal(0, 1, n)
    src_b = truth + rng.normal(0, 2, n)
    forecasts = np.column_stack([src_a, src_b])
    fit = fit_bma_em(forecasts, truth, source_names=["a", "b"])
    # Probability of [55, 65] for a forecast row near 60
    p = bucket_probability_bma(fit, np.array([[60.0, 60.0]]), low=55.0, high=65.0)
    assert 0 <= float(p[0]) <= 1.0
    assert float(p[0]) > 0.5  # most mass should be in the bucket


def test_bma_input_validation():
    with pytest.raises(ValueError):
        fit_bma_em(
            np.array([[1.0]]),  # only 1 obs, K=1, n=1 < K+1
            np.array([0.0]),
            source_names=["a"],
        )
    with pytest.raises(ValueError):
        fit_bma_em(
            np.array([[1.0, 2.0], [3.0, 4.0]]),
            np.array([0.0, 0.0]),
            source_names=["a"],  # length mismatch
        )
    with pytest.raises(ValueError):
        fit_bma_em(np.array([1, 2, 3]), np.array([1, 2, 3]), source_names=["a"])


def test_bma_converges_in_reasonable_iterations():
    rng = np.random.default_rng(5)
    n = 500
    truth = rng.normal(0, 1, n)
    src_a = truth + rng.normal(0, 1, n)
    src_b = truth + rng.normal(0, 1, n)
    src_c = truth + rng.normal(0, 1, n)
    forecasts = np.column_stack([src_a, src_b, src_c])
    fit = fit_bma_em(forecasts, truth, source_names=["a", "b", "c"], max_iter=200)
    # Convergence in well-conditioned problem should be quick
    assert fit.converged
    assert fit.n_iter < 100
