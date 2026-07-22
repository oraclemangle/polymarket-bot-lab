"""Bayesian Model Averaging via Expectation-Maximisation.

Formula source: ``docs/reports/math-formula-roadmap-split-2026-05-08.md``
§6.2. References:

- Raftery, Gneiting, Balabdaoui & Polakowski 2005, "Using Bayesian
  Model Averaging to Calibrate Forecast Ensembles", Monthly Weather
  Review 133(5), DOI 10.1175/MWR2906.1.
- Aihaiti et al. 2022, "BMA-based 2 m temperature post-processing",
  Frontiers in Earth Science, DOI 10.3389/feart.2022.960156.

Each forecast source ``k`` provides a Gaussian kernel
``N(forecast_k + bias_k, sigma_k^2)``. The BMA mixture is

    p_BMA(T) = sum_k w_k * N(T; forecast_k + bias_k, sigma_k^2)

with ``sum_k w_k = 1, w_k >= 0``. Weights, biases, and per-source
variances are fit by EM on a training set of (forecasts, observed)
pairs.
"""
# ruff: noqa: N806, B007
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BMAFit:
    """Fitted BMA model.

    Attributes:
        weights: w_k, summing to 1
        biases: bias_k for each source
        sigmas: sigma_k for each source
        source_names: list of source labels (same order as forecasts cols)
        n_iter: EM iterations performed
        converged: whether EM converged before max_iter
        n_observations: training set size
    """

    weights: np.ndarray
    biases: np.ndarray
    sigmas: np.ndarray
    source_names: list[str]
    n_iter: int
    converged: bool
    n_observations: int


def _normal_pdf(x: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    sigma_safe = np.clip(sigma, 1e-6, None)
    z = (x - mu) / sigma_safe
    return np.exp(-0.5 * z * z) / (sigma_safe * math.sqrt(2.0 * math.pi))


def fit_bma_em(
    forecasts: np.ndarray,
    observed: np.ndarray,
    source_names: Sequence[str],
    *,
    max_iter: int = 200,
    tol: float = 1e-4,
) -> BMAFit:
    """Fit BMA via EM.

    ``forecasts`` is shape (n, K): each row is one observation, each
    column is one source's deterministic forecast. ``observed`` is
    shape (n,). EM updates per §6.2:

        E-step:  z_kn = w_k * p_k(T_n) / sum_j w_j * p_j(T_n)
        M-step:  w_k        = (1/N) sum_n z_kn
                 bias_k     = sum_n z_kn (T_n - f_kn) / sum_n z_kn
                 sigma_k^2  = sum_n z_kn (T_n - f_kn - bias_k)^2 / sum_n z_kn
    """
    F = np.asarray(forecasts, dtype=float)
    y = np.asarray(observed, dtype=float)
    if F.ndim != 2:
        raise ValueError("forecasts must be 2D (n_obs, K)")
    if y.ndim != 1 or y.shape[0] != F.shape[0]:
        raise ValueError("observed length mismatch")
    n, K = F.shape
    if len(source_names) != K:
        raise ValueError("source_names length must equal forecast columns")
    if n < K + 1:
        raise ValueError("need more observations than sources")

    # Initialise: equal weights, OLS-residual biases, residual sigmas
    w = np.ones(K) / K
    bias = np.array([float(np.mean(y - F[:, k])) for k in range(K)])
    sigma = np.array(
        [float(max(np.std(y - F[:, k] - bias[k]), 1e-3)) for k in range(K)]
    )

    converged = False
    for it in range(max_iter):
        # E-step: responsibilities (n, K)
        Y_col = y.reshape(-1, 1)
        mu_kn = F + bias.reshape(1, -1)  # broadcast
        sigma_kn = np.broadcast_to(sigma.reshape(1, -1), (n, K))
        pdf_kn = _normal_pdf(Y_col, mu_kn, sigma_kn)
        weighted = pdf_kn * w.reshape(1, -1)
        denom = np.sum(weighted, axis=1, keepdims=True)
        # Avoid 0/0: if denom is tiny, fall back to uniform
        safe_denom = np.where(denom < 1e-30, 1e-30, denom)
        z = weighted / safe_denom
        # M-step
        Z_k = np.sum(z, axis=0)  # (K,)
        Z_k_safe = np.where(Z_k < 1e-30, 1e-30, Z_k)
        w_new = Z_k / n
        bias_new = np.array(
            [float(np.sum(z[:, k] * (y - F[:, k])) / Z_k_safe[k]) for k in range(K)]
        )
        sigma_sq_new = np.array(
            [
                float(
                    np.sum(z[:, k] * (y - F[:, k] - bias_new[k]) ** 2)
                    / Z_k_safe[k]
                )
                for k in range(K)
            ]
        )
        sigma_new = np.sqrt(np.clip(sigma_sq_new, 1e-6, None))
        # Convergence check
        if (
            np.max(np.abs(w_new - w)) < tol
            and np.max(np.abs(bias_new - bias)) < tol
            and np.max(np.abs(sigma_new - sigma)) < tol
        ):
            w, bias, sigma = w_new, bias_new, sigma_new
            converged = True
            break
        w, bias, sigma = w_new, bias_new, sigma_new

    return BMAFit(
        weights=w,
        biases=bias,
        sigmas=sigma,
        source_names=list(source_names),
        n_iter=it + 1,
        converged=converged,
        n_observations=n,
    )


def predict_bma(
    fit: BMAFit, forecasts: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return (mixture_mean, mixture_sd) for each forecast row.

    Mixture mean: ``mu_BMA = sum_k w_k (f_k + bias_k)``.
    Mixture variance: ``sigma_BMA^2 = sum_k w_k [sigma_k^2 + (mu_k - mu_BMA)^2]``.
    """
    F = np.asarray(forecasts, dtype=float)
    if F.ndim == 1:
        F = F.reshape(1, -1)
    if F.shape[1] != fit.weights.shape[0]:
        raise ValueError(
            f"forecasts has {F.shape[1]} cols, model expects {fit.weights.shape[0]}"
        )
    mu_k = F + fit.biases.reshape(1, -1)  # (n, K)
    mixture_mean = mu_k @ fit.weights
    mixture_var = (
        (fit.sigmas ** 2 + (mu_k - mixture_mean.reshape(-1, 1)) ** 2)
        @ fit.weights
    )
    return mixture_mean, np.sqrt(np.clip(mixture_var, 1e-12, None))


def bucket_probability_bma(
    fit: BMAFit, forecasts: np.ndarray, low: float, high: float
) -> np.ndarray:
    """``P(low <= T <= high)`` under the BMA mixture, per row."""
    F = np.asarray(forecasts, dtype=float)
    if F.ndim == 1:
        F = F.reshape(1, -1)
    n = F.shape[0]
    K = fit.weights.shape[0]
    out = np.zeros(n)
    for k in range(K):
        mu_k = F[:, k] + fit.biases[k]
        sigma_k = max(fit.sigmas[k], 1e-6)
        z_hi = (high - mu_k) / sigma_k
        z_lo = (low - mu_k) / sigma_k
        # vectorised normal CDF
        Phi_hi = 0.5 * (1.0 + np.vectorize(math.erf)(z_hi / math.sqrt(2.0)))
        Phi_lo = 0.5 * (1.0 + np.vectorize(math.erf)(z_lo / math.sqrt(2.0)))
        out += fit.weights[k] * (Phi_hi - Phi_lo)
    return np.clip(out, 0.0, 1.0)
