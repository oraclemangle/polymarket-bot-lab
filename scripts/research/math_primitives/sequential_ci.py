"""Anytime-valid betting confidence sequence for bounded means.

Formula source: ``docs/reports/math-formula-roadmap-split-2026-05-08.md``
§6.5. Reference:

- Waudby-Smith & Ramdas 2024, "Estimating means of bounded random
  variables by betting", JRSS-B 86(1):1-27, DOI 10.1093/jrsssb/qkad104.

The confidence sequence is constructed from a non-negative martingale
``K_t(mu)`` indexed by the candidate mean ``mu``. By Ville's
inequality, ``CS_t = {mu : K_t(mu) < 1/alpha}`` is a uniformly valid
``(1 - alpha)`` confidence interval — optional stopping is allowed.

This module is the actual martingale + grid search; the grid search
is the standard practical approach because the martingale is convex
in ``mu`` and the boundary can be located numerically.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


def agrapa_lambda(
    history: Sequence[float],
    mu: float,
    *,
    a: float = 0.0,
    b: float = 1.0,
    eps: float = 1e-4,
) -> float:
    """Adaptive betting fraction (aGRAPA, Waudby-Smith-Ramdas §3.4).

    At step ``t``, given history ``X_1, ..., X_{t-1}`` clipped to
    ``[a, b]``:

        lambda_t = clip( (xbar_{t-1} - mu) / sigma_hat^2_{t-1},
                         lambda_min, lambda_max )

    The bounds keep the capital process non-negative for any observation
    in ``[a, b]`` under the candidate mean ``mu``.

    Empty / single-observation history returns ``0`` (no bet yet).
    """
    if b <= a:
        raise ValueError(f"need b > a, got a={a}, b={b}")
    if mu < a or mu > b:
        raise ValueError(f"mu={mu} outside support [a, b]=[{a}, {b}]")
    if not history:
        return 0.0
    arr = np.asarray(history, dtype=float)
    if np.any((arr < a) | (arr > b)):
        raise ValueError("history contains values outside [a, b]")
    if arr.size < 2:
        return 0.0
    xbar = float(np.mean(arr))
    var = float(np.var(arr, ddof=1)) if arr.size > 1 else 1.0
    var = max(var, eps)
    lam_min = -1.0 / max(b - mu, 1e-12)
    lam_max = 1.0 / max(mu - a, 1e-12)
    raw = (xbar - mu) / var
    return float(np.clip(raw, 0.5 * lam_min, 0.5 * lam_max))


def capital_process(
    observations: Sequence[float],
    mu: float,
    *,
    a: float = 0.0,
    b: float = 1.0,
) -> float:
    """Compute K_t(mu) for the betting CS.

    K_t(mu) = product_{i=1}^t [ 1 + lambda_i(mu) * (X_i - mu) ]

    where ``lambda_i`` is chosen by aGRAPA on the prefix history.
    Returns the capital process value after consuming all
    observations.
    """
    if b <= a:
        raise ValueError("need b > a")
    if mu < a or mu > b:
        raise ValueError(f"mu={mu} outside support [a, b]=[{a}, {b}]")
    arr = np.asarray(observations, dtype=float)
    if np.any((arr < a) | (arr > b)):
        raise ValueError("observations contain values outside [a, b]")
    capital = 1.0
    for i, x in enumerate(arr):
        history = arr[:i].tolist()
        lam = agrapa_lambda(history, mu=mu, a=a, b=b)
        capital *= 1.0 + lam * (x - mu)
        if capital <= 0.0:
            # Numerical safeguard: martingale never goes <= 0 in
            # theory but FP can drive it to a tiny positive number;
            # if it does cross, return 0 so the CS treats this as
            # "definitely not consistent with mu".
            return 0.0
    return capital


@dataclass
class BettingConfidenceSequence:
    """Anytime-valid (1 - alpha) confidence interval for the mean.

    Attributes:
        lower: lower bound of the confidence sequence
        upper: upper bound of the confidence sequence
        n: number of observations
        alpha: significance level (0.05 for 95% CI)
        support_lo: lower bound of the support [a, b]
        support_hi: upper bound of the support [a, b]
    """

    lower: float
    upper: float
    n: int
    alpha: float
    support_lo: float
    support_hi: float


def confidence_sequence(
    observations: Sequence[float],
    *,
    alpha: float = 0.05,
    a: float = 0.0,
    b: float = 1.0,
    grid_size: int = 401,
) -> BettingConfidenceSequence:
    """Compute the betting CS at the requested level.

    ``observations`` must lie in ``[a, b]``. The CS is the set of
    candidate means ``mu`` whose capital process is below ``1/alpha``.

    Returns the lower and upper bounds; if every grid point is
    outside the CS, returns ``(a, b)`` (the trivial CS).
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0, 1)")
    if b <= a:
        raise ValueError("need b > a")
    arr = np.asarray(observations, dtype=float)
    if arr.size == 0:
        return BettingConfidenceSequence(
            lower=a, upper=b, n=0, alpha=alpha, support_lo=a, support_hi=b
        )
    grid = np.linspace(a, b, grid_size)
    threshold = 1.0 / alpha
    in_cs = []
    for mu in grid:
        capital = capital_process(arr, float(mu), a=a, b=b)
        in_cs.append(threshold > capital)
    in_cs_arr = np.asarray(in_cs)
    if not np.any(in_cs_arr):
        return BettingConfidenceSequence(
            lower=a, upper=b, n=arr.size, alpha=alpha, support_lo=a, support_hi=b
        )
    inside = grid[in_cs_arr]
    return BettingConfidenceSequence(
        lower=float(inside.min()),
        upper=float(inside.max()),
        n=arr.size,
        alpha=alpha,
        support_lo=a,
        support_hi=b,
    )


def binarize_outcomes_by_day(
    timestamps_ms: Sequence[int], outcomes: Sequence[int]
) -> list[float]:
    """Collapse per-trade outcomes into one observation per UTC day.

    The daily observation is the day's hit-rate (mean of binary
    outcomes within that UTC day). Daily P&L autocorrelation breaks
    the i.i.d. assumption that betting CS needs at the per-trade
    level; daily binning is the standard mitigation.

    Days are derived from ``timestamps_ms`` (Unix milliseconds, UTC).
    Returns a list of daily means in chronological order.
    """
    ts_arr = np.asarray(timestamps_ms, dtype=np.int64)
    y_arr = np.asarray(outcomes, dtype=float)
    if ts_arr.shape != y_arr.shape:
        raise ValueError("timestamps and outcomes shape mismatch")
    if ts_arr.size == 0:
        return []
    days = ts_arr // 86_400_000  # ms per UTC day
    unique_days = np.unique(days)
    out: list[float] = []
    for d in unique_days:
        mask = days == d
        out.append(float(np.mean(y_arr[mask])))
    return out
