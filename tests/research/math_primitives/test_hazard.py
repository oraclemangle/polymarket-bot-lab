"""Tests for the discrete hazard primitives."""
# ruff: noqa: N806
from __future__ import annotations

import numpy as np
import pytest

from scripts.research.math_primitives.hazard import (
    bootstrap_roi_ci_by_day,
    discrete_hazard_logit_fit,
    eventual_event_probability,
    predict_hazard,
    spike_to_threshold_probability,
    survival_from_hazards,
    top_k_pnl_concentration,
)


def test_logit_fit_recovers_known_coefficients():
    """Generate y from known logit; check β recovery within tolerance."""
    rng = np.random.default_rng(42)
    n = 5000
    X = rng.normal(0, 1, (n, 2))
    true_intercept = -1.0
    true_beta = np.array([1.5, -0.5])
    eta = true_intercept + X @ true_beta
    p = 1.0 / (1.0 + np.exp(-eta))
    y = rng.binomial(1, p).astype(float)
    fit = discrete_hazard_logit_fit(X, y, feature_names=["a", "b"])
    # Intercept first, then features
    assert fit.coef[0] == pytest.approx(true_intercept, abs=0.15)
    assert fit.coef[1] == pytest.approx(true_beta[0], abs=0.15)
    assert fit.coef[2] == pytest.approx(true_beta[1], abs=0.15)
    assert fit.converged
    assert not fit.rare_event_corrected  # 27% event rate, not rare


def test_logit_fit_rare_event_correction_fires():
    rng = np.random.default_rng(0)
    n = 2000
    X = rng.normal(0, 1, (n, 1))
    # Force ~2% event rate
    eta = -4.0 + 0.5 * X[:, 0]
    p = 1.0 / (1.0 + np.exp(-eta))
    y = rng.binomial(1, p).astype(float)
    fit = discrete_hazard_logit_fit(X, y, feature_names=["x"])
    assert fit.n_events / n < 0.05
    assert fit.rare_event_corrected


def test_logit_fit_input_validation():
    with pytest.raises(ValueError):
        discrete_hazard_logit_fit(np.array([1, 2, 3]), np.array([1, 0, 1]))
    with pytest.raises(ValueError):
        discrete_hazard_logit_fit(
            np.array([[1.0], [2.0]]), np.array([1, 2])  # not binary
        )
    with pytest.raises(ValueError):
        discrete_hazard_logit_fit(
            np.array([[1.0], [2.0]]),
            np.array([0, 1]),
            feature_names=["a", "b"],  # length mismatch
        )


def test_predict_hazard_matches_fit_at_training_points():
    rng = np.random.default_rng(7)
    n = 1000
    X = rng.normal(0, 1, (n, 2))
    eta = -0.5 + X @ np.array([0.3, -0.2])
    p_true = 1.0 / (1.0 + np.exp(-eta))
    y = rng.binomial(1, p_true).astype(float)
    fit = discrete_hazard_logit_fit(X, y)
    preds = predict_hazard(fit, X)
    # Predictions should correlate with truth
    corr = np.corrcoef(preds, p_true)[0, 1]
    assert corr > 0.95


def test_survival_and_eventual():
    h = [0.1, 0.2, 0.3]
    surv = survival_from_hazards(h)
    expected = 0.9 * 0.8 * 0.7
    assert surv == pytest.approx(expected)
    assert eventual_event_probability(h) == pytest.approx(1.0 - expected)


def test_survival_empty():
    assert survival_from_hazards([]) == 1.0
    assert eventual_event_probability([]) == 0.0


def test_survival_input_validation():
    with pytest.raises(ValueError):
        survival_from_hazards([0.1, 1.5])
    with pytest.raises(ValueError):
        survival_from_hazards([-0.1, 0.5])


def test_spike_to_threshold():
    # Path that touches 0.10
    assert spike_to_threshold_probability([0.04, 0.07, 0.11, 0.05], 0.10) == 1
    # Path that does not
    assert spike_to_threshold_probability([0.04, 0.05, 0.06], 0.10) == 0


def test_top_k_concentration():
    pnls = [10.0, 5.0, 2.0, 1.0, 1.0, 1.0]  # total 20
    conc = top_k_pnl_concentration(pnls, k_values=(1, 2, 5))
    assert conc[1] == pytest.approx(0.5)  # 10/20
    assert conc[2] == pytest.approx(0.75)  # 15/20
    assert conc[5] == pytest.approx(19.0 / 20.0)


def test_top_k_concentration_zero_total():
    pnls = [-1.0, -2.0, 1.0, 2.0]  # total 0
    conc = top_k_pnl_concentration(pnls)
    assert all(v == 0.0 for v in conc.values())


def test_bootstrap_roi_ci_basic():
    daily_roi = [0.1, 0.05, 0.0, 0.15, -0.05, 0.08, 0.02]
    lo, hi = bootstrap_roi_ci_by_day(daily_roi, n_resamples=1000, alpha=0.1)
    assert lo < np.mean(daily_roi) < hi


def test_bootstrap_roi_ci_empty():
    lo, hi = bootstrap_roi_ci_by_day([], n_resamples=100)
    assert lo == 0.0 and hi == 0.0
