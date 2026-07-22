"""Discrete-time hazard models + survival + spike-to-threshold.

Formula source: ``docs/reports/math-formula-roadmap-split-2026-05-08.md``
§6.3. References:

- Allison 1982, "Discrete-Time Methods for the Analysis of Event
  Histories", Sociological Methodology 13:61-98, DOI 10.2307/270718.
- King & Zeng 2001, "Logistic Regression in Rare Events Data",
  Political Analysis 9(2):137-163, DOI 10.1093/oxfordjournals.pan.a004868.

Logistic regression is fit via Newton-Raphson on the IRLS update.
For very rare events (positive class < 5%) the King-Zeng prior bias
correction is applied; otherwise the uncorrected MLE is returned.
"""
# ruff: noqa: N803, N806, B007
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class HazardLogit:
    """Fitted discrete-time hazard logistic regression.

    Attributes:
        coef: coefficient vector (intercept first, then features)
        feature_names: names of the columns in the design matrix
          *without* the intercept; ``coef[0]`` is the intercept.
        n_iter: number of Newton-Raphson iterations
        converged: True if change in log-likelihood was below tolerance
        rare_event_corrected: True if King-Zeng correction was applied
        n_observations: total panel rows
        n_events: number of rows with outcome == 1
    """

    coef: np.ndarray
    feature_names: list[str]
    n_iter: int
    converged: bool
    rare_event_corrected: bool
    n_observations: int
    n_events: int


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -50.0, 50.0)))


def discrete_hazard_logit_fit(
    X: np.ndarray,
    y: np.ndarray,
    *,
    feature_names: Sequence[str] | None = None,
    max_iter: int = 100,
    tol: float = 1e-7,
    rare_event_threshold: float = 0.05,
) -> HazardLogit:
    """Fit ``logit(h_t) = X @ beta`` via IRLS.

    ``X`` should be a (n, p) design matrix WITHOUT an intercept
    column (an intercept is prepended automatically). Each row is one
    candidate-bucket panel observation; ``y[i] = 1`` if the event
    fired in that bucket, ``0`` otherwise.

    If event rate < ``rare_event_threshold``, a King-Zeng prior bias
    correction is applied. The correction shifts the fitted
    coefficients toward zero by the leading-order analytical term
    from King-Zeng eq. (5).
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    if X.ndim != 2:
        raise ValueError("X must be 2D")
    if y.ndim != 1 or y.shape[0] != X.shape[0]:
        raise ValueError("y must be 1D with the same length as X rows")
    if not np.all(np.isin(y, (0.0, 1.0))):
        raise ValueError("y must be binary 0/1")
    n, p = X.shape
    # Add intercept column.
    X_int = np.column_stack([np.ones(n), X])
    p_full = p + 1
    if feature_names is None:
        feature_names = [f"x{i}" for i in range(p)]
    if len(feature_names) != p:
        raise ValueError("feature_names length mismatch")

    beta = np.zeros(p_full)
    converged = False
    prev_loglik = -np.inf
    for iteration in range(max_iter):
        eta = X_int @ beta
        mu = _sigmoid(eta)
        # Avoid 0/1 mu causing 0 weight rows
        mu_safe = np.clip(mu, 1e-12, 1.0 - 1e-12)
        W = mu_safe * (1.0 - mu_safe)
        # Newton step: beta_new = beta + (X' W X)^-1 X' (y - mu)
        XtW = X_int.T * W
        H = XtW @ X_int
        grad = X_int.T @ (y - mu)
        try:
            step = np.linalg.solve(H + 1e-10 * np.eye(p_full), grad)
        except np.linalg.LinAlgError:
            break
        beta = beta + step
        # Log-likelihood
        loglik = float(
            np.sum(y * np.log(mu_safe) + (1.0 - y) * np.log(1.0 - mu_safe))
        )
        if abs(loglik - prev_loglik) < tol:
            converged = True
            break
        prev_loglik = loglik
    n_iter = iteration + 1

    n_events = int(np.sum(y))
    event_rate = n_events / n
    rare_event_corrected = False
    if event_rate < rare_event_threshold and event_rate > 0:
        # King-Zeng eq. (5): bias = (X'WX)^-1 X' W xi where xi has
        # i-th component 0.5 * Q_ii * ((1+w_1) mu_i - w_1) and
        # Q = X (X'WX)^-1 X'. Here w_1 = 1 (no case-control sampling).
        eta = X_int @ beta
        mu = _sigmoid(eta)
        mu_safe = np.clip(mu, 1e-12, 1.0 - 1e-12)
        W = mu_safe * (1.0 - mu_safe)
        XtWX = (X_int.T * W) @ X_int
        try:
            XtWX_inv = np.linalg.inv(XtWX + 1e-10 * np.eye(p_full))
            Q_diag = np.einsum(
                "ij,jk,ik->i", X_int, XtWX_inv, X_int
            )
            xi = 0.5 * Q_diag * (2.0 * mu_safe - 1.0)
            bias = XtWX_inv @ (X_int.T * W) @ xi
            beta = beta - bias
            rare_event_corrected = True
        except np.linalg.LinAlgError:
            pass

    return HazardLogit(
        coef=beta,
        feature_names=list(feature_names),
        n_iter=n_iter,
        converged=converged,
        rare_event_corrected=rare_event_corrected,
        n_observations=n,
        n_events=n_events,
    )


def predict_hazard(model: HazardLogit, X: np.ndarray) -> np.ndarray:
    """Predict hazard ``h_t = P(event in bucket | covariates)``."""
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X.reshape(1, -1)
    if X.shape[1] != len(model.feature_names):
        raise ValueError(
            f"X has {X.shape[1]} cols, model expects {len(model.feature_names)}"
        )
    X_int = np.column_stack([np.ones(X.shape[0]), X])
    return _sigmoid(X_int @ model.coef)


def survival_from_hazards(hazards: Sequence[float]) -> float:
    """``S(T) = product_{t=1}^T (1 - h_t)``.

    The probability that no event has fired by the end of the
    sequence.
    """
    arr = np.asarray(hazards, dtype=float)
    if arr.size == 0:
        return 1.0
    if np.any((arr < 0.0) | (arr > 1.0)):
        raise ValueError("hazards must lie in [0, 1]")
    return float(np.prod(1.0 - arr))


def eventual_event_probability(hazards: Sequence[float]) -> float:
    """``P(eventual event) = 1 - S(T_close)``."""
    return 1.0 - survival_from_hazards(hazards)


def spike_to_threshold_probability(
    best_bid_path: Sequence[float], threshold: float
) -> int:
    """Return ``1`` if the path ever reaches the threshold else ``0``.

    For computing ``P(spike_X | covariates)`` from observed paths.
    Caller aggregates the binary indicator across many paths.
    """
    arr = np.asarray(best_bid_path, dtype=float)
    return int(np.any(arr >= threshold))


def top_k_pnl_concentration(
    pnls: Sequence[float], k_values: Sequence[int] = (1, 2, 5)
) -> dict[int, float]:
    """``concentration_k = sum_{i=1}^k pnl_i / sum pnl_i`` (sorted desc).

    Reports the share of total positive P&L coming from the top
    k outcomes. Flag ``concentration_2 >= 0.80`` per §6.3.
    """
    arr = np.asarray(pnls, dtype=float)
    if arr.size == 0:
        return {k: 0.0 for k in k_values}
    sorted_desc = np.sort(arr)[::-1]
    total = float(np.sum(arr))
    if total <= 0:
        return {k: 0.0 for k in k_values}
    out: dict[int, float] = {}
    for k in k_values:
        if k <= 0:
            out[k] = 0.0
            continue
        out[k] = float(np.sum(sorted_desc[:k])) / total
    return out


def bootstrap_roi_ci_by_day(
    daily_roi: Sequence[float],
    *,
    n_resamples: int = 10_000,
    alpha: float = 0.05,
    rng: np.random.Generator | None = None,
) -> tuple[float, float]:
    """Trading-day-level bootstrap CI for ROI.

    Resamples *trading days* with replacement (not individual trades)
    to respect the daily clustering of P&L.
    """
    arr = np.asarray(daily_roi, dtype=float)
    if arr.size == 0:
        return (0.0, 0.0)
    if rng is None:
        rng = np.random.default_rng(seed=42)
    means = np.empty(n_resamples)
    n = arr.size
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        means[i] = float(np.mean(arr[idx]))
    lo = float(np.quantile(means, alpha / 2))
    hi = float(np.quantile(means, 1.0 - alpha / 2))
    return (lo, hi)
