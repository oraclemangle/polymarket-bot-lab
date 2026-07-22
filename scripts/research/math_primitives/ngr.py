"""Non-homogeneous Gaussian Regression (EMOS) for ensemble post-processing.

Formula source: ``docs/reports/math-formula-roadmap-split-2026-05-08.md``
§6.1. References:

- Gneiting, Raftery, Westveld & Goldman 2005, "Calibrated Probabilistic
  Forecasting Using Ensemble Model Output Statistics and Minimum CRPS
  Estimation", Monthly Weather Review 133(5), DOI 10.1175/MWR2904.1.
- Jobst, Möller & Gross 2024, "Time-series-aware EMOS for daily
  station temperature", arXiv:2402.00555.

The mean is fit by ordinary least squares against verified observed
station temperature. The variance is fit by minimising negative
log-likelihood under the assumed heteroscedastic Gaussian, after
fixing the mean.
"""
# ruff: noqa: N803, N806, B007
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class NGRFit:
    """Fitted NGR model.

    Attributes:
        mean_coef: OLS coefficients for the mean (intercept first)
        mean_features: feature names (without intercept)
        var_coef: coefficients for log-variance regression
          (intercept first); variance = exp(var_coef @ var_features)
        var_features: feature names for variance (without intercept)
        n_observations: number of training points
        train_rmse: RMSE on training data
        train_crps: mean CRPS on training data (lower is better)
    """

    mean_coef: np.ndarray
    mean_features: list[str]
    var_coef: np.ndarray
    var_features: list[str]
    n_observations: int
    train_rmse: float
    train_crps: float


def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    n, _ = X.shape
    X_int = np.column_stack([np.ones(n), X])
    beta, *_ = np.linalg.lstsq(X_int, y, rcond=None)
    return beta


def _crps_normal(y: float, mu: float, sigma: float) -> float:
    """CRPS for a Normal forecast at observation y.

    Closed form: sigma * (z (2 Phi(z) - 1) + 2 phi(z) - 1/sqrt(pi))
    where z = (y - mu) / sigma.
    """
    if sigma <= 0:
        sigma = 1e-6
    z = (y - mu) / sigma
    phi = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    Phi = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return sigma * (z * (2.0 * Phi - 1.0) + 2.0 * phi - 1.0 / math.sqrt(math.pi))


def fit_ngr(
    *,
    mean_features: np.ndarray,
    mean_feature_names: Sequence[str],
    variance_features: np.ndarray,
    variance_feature_names: Sequence[str],
    observed: np.ndarray,
    var_max_iter: int = 200,
    var_tol: float = 1e-6,
) -> NGRFit:
    """Fit an NGR model.

    The mean is fit by OLS against ``observed``. The log-variance is
    then fit by gradient descent on the negative log-likelihood
    (Adam-free minimal implementation; sufficient for the small
    feature counts we use). Variance features should typically be
    nonnegative things like ``ensemble_dispersion^2``,
    ``lead_time``, ``recent_station_error_rmse^2``.
    """
    X_mean = np.asarray(mean_features, dtype=float)
    X_var = np.asarray(variance_features, dtype=float)
    y = np.asarray(observed, dtype=float)
    if X_mean.shape[0] != y.shape[0]:
        raise ValueError("mean_features rows != observed length")
    if X_var.shape[0] != y.shape[0]:
        raise ValueError("variance_features rows != observed length")
    n = y.shape[0]

    mean_coef = _ols(X_mean, y)
    X_mean_int = np.column_stack([np.ones(n), X_mean])
    mu = X_mean_int @ mean_coef
    residuals = y - mu

    # Fit log-variance: log(sigma^2_i) = X_var_int @ var_coef
    p_var = X_var.shape[1] + 1
    X_var_int = np.column_stack([np.ones(n), X_var])
    var_coef = np.zeros(p_var)
    # Initialise intercept from OLS residual variance
    var_coef[0] = math.log(max(float(np.var(residuals)), 1e-6))

    lr = 0.05
    for it in range(var_max_iter):
        log_var = X_var_int @ var_coef
        log_var = np.clip(log_var, -20.0, 20.0)
        var = np.exp(log_var)
        # Negative log-likelihood gradient wrt var_coef:
        #   d/dlog_var [0.5 * (log_var + r^2 / var)] = 0.5 - 0.5 r^2 / var
        # gradient on coef = X_var_int.T @ (0.5 - 0.5 r^2 / var)
        nll_grad = X_var_int.T @ (0.5 - 0.5 * (residuals ** 2) / var) / n
        new_var_coef = var_coef - lr * nll_grad
        if np.max(np.abs(new_var_coef - var_coef)) < var_tol:
            var_coef = new_var_coef
            break
        var_coef = new_var_coef

    # Final stats
    log_var = np.clip(X_var_int @ var_coef, -20.0, 20.0)
    sigma = np.sqrt(np.exp(log_var))
    rmse = float(np.sqrt(np.mean(residuals ** 2)))
    crps_vals = [
        _crps_normal(float(y[i]), float(mu[i]), float(sigma[i])) for i in range(n)
    ]
    train_crps = float(np.mean(crps_vals))

    return NGRFit(
        mean_coef=mean_coef,
        mean_features=list(mean_feature_names),
        var_coef=var_coef,
        var_features=list(variance_feature_names),
        n_observations=n,
        train_rmse=rmse,
        train_crps=train_crps,
    )


def predict_ngr(
    fit: NGRFit,
    *,
    mean_features: np.ndarray,
    variance_features: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (mu, sigma) for each prediction row."""
    X_mean = np.asarray(mean_features, dtype=float)
    X_var = np.asarray(variance_features, dtype=float)
    if X_mean.ndim == 1:
        X_mean = X_mean.reshape(1, -1)
    if X_var.ndim == 1:
        X_var = X_var.reshape(1, -1)
    n = X_mean.shape[0]
    X_mean_int = np.column_stack([np.ones(n), X_mean])
    X_var_int = np.column_stack([np.ones(n), X_var])
    mu = X_mean_int @ fit.mean_coef
    log_var = np.clip(X_var_int @ fit.var_coef, -20.0, 20.0)
    sigma = np.sqrt(np.exp(log_var))
    return mu, sigma


def bucket_probability_normal(
    mu: float, sigma: float, low: float, high: float
) -> float:
    """``P(low <= T <= high)`` under N(mu, sigma^2)."""
    if sigma <= 0:
        sigma = 1e-6
    z_hi = (high - mu) / sigma
    z_lo = (low - mu) / sigma
    Phi_hi = 0.5 * (1.0 + math.erf(z_hi / math.sqrt(2.0)))
    Phi_lo = 0.5 * (1.0 + math.erf(z_lo / math.sqrt(2.0)))
    return float(max(0.0, Phi_hi - Phi_lo))
