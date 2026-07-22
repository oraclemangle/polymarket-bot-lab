"""Tests for the NGR / EMOS primitive."""
# ruff: noqa: N806
from __future__ import annotations

import numpy as np
import pytest

from scripts.research.math_primitives.ngr import (
    bucket_probability_normal,
    fit_ngr,
    predict_ngr,
)


def test_ngr_recovers_known_mean_coefficients():
    """If observations are noisy linear in features, OLS recovers β."""
    rng = np.random.default_rng(42)
    n = 1000
    X_mean = rng.normal(0, 1, (n, 2))
    true_intercept = 50.0
    true_beta = np.array([2.0, -1.5])
    noise = rng.normal(0, 0.5, n)
    y = true_intercept + X_mean @ true_beta + noise
    X_var = np.zeros((n, 1))  # constant variance, no features
    fit = fit_ngr(
        mean_features=X_mean,
        mean_feature_names=["a", "b"],
        variance_features=X_var,
        variance_feature_names=["c"],
        observed=y,
    )
    assert fit.mean_coef[0] == pytest.approx(true_intercept, abs=0.1)
    assert fit.mean_coef[1] == pytest.approx(true_beta[0], abs=0.1)
    assert fit.mean_coef[2] == pytest.approx(true_beta[1], abs=0.1)


def test_ngr_heteroscedastic_variance_responds_to_features():
    """Larger variance feature leads to larger sigma estimate."""
    rng = np.random.default_rng(0)
    n = 1500
    X_mean = np.zeros((n, 1))
    # Half the data has larger noise
    var_feat = np.concatenate([np.zeros(n // 2), np.ones(n - n // 2)]).reshape(-1, 1)
    sigmas_true = np.where(var_feat[:, 0] > 0.5, 2.0, 0.5)
    y = rng.normal(0, sigmas_true)
    fit = fit_ngr(
        mean_features=X_mean,
        mean_feature_names=["x"],
        variance_features=var_feat,
        variance_feature_names=["v"],
        observed=y,
    )
    # Predict for var_feat=0 vs var_feat=1
    _, sigma_low = predict_ngr(
        fit,
        mean_features=np.array([[0.0]]),
        variance_features=np.array([[0.0]]),
    )
    _, sigma_high = predict_ngr(
        fit,
        mean_features=np.array([[0.0]]),
        variance_features=np.array([[1.0]]),
    )
    assert sigma_high[0] > sigma_low[0]


def test_predict_ngr_shape():
    n = 100
    X_mean = np.zeros((n, 1))
    X_var = np.zeros((n, 1))
    y = np.zeros(n) + 1.0
    fit = fit_ngr(
        mean_features=X_mean,
        mean_feature_names=["a"],
        variance_features=X_var,
        variance_feature_names=["b"],
        observed=y,
    )
    mu, sigma = predict_ngr(
        fit,
        mean_features=np.zeros((5, 1)),
        variance_features=np.zeros((5, 1)),
    )
    assert mu.shape == (5,)
    assert sigma.shape == (5,)


def test_bucket_probability_normal_full_range_is_one():
    p = bucket_probability_normal(mu=0.0, sigma=1.0, low=-100.0, high=100.0)
    assert p == pytest.approx(1.0, abs=1e-6)


def test_bucket_probability_normal_symmetric_about_mean():
    # P(-1 <= X <= 1) under N(0, 1) ≈ 0.6827
    p = bucket_probability_normal(mu=0.0, sigma=1.0, low=-1.0, high=1.0)
    assert p == pytest.approx(0.6827, abs=1e-3)


def test_bucket_probability_normal_zero_for_inverted():
    p = bucket_probability_normal(mu=0.0, sigma=1.0, low=2.0, high=-2.0)
    # high < low => CDF(high) - CDF(low) is negative; clipped to 0
    assert p == 0.0


def test_ngr_input_validation():
    with pytest.raises(ValueError):
        fit_ngr(
            mean_features=np.zeros((10, 1)),
            mean_feature_names=["a"],
            variance_features=np.zeros((5, 1)),
            variance_feature_names=["b"],
            observed=np.zeros(10),
        )
    with pytest.raises(ValueError):
        fit_ngr(
            mean_features=np.zeros((10, 1)),
            mean_feature_names=["a"],
            variance_features=np.zeros((10, 1)),
            variance_feature_names=["b"],
            observed=np.zeros(5),
        )
