"""Strictly proper scoring rules and Murphy decomposition.

Formula source: ``docs/reports/math-formula-roadmap-split-2026-05-08.md``
§6.4. References:

- Brier 1950, "Verification of Forecasts Expressed in Terms of
  Probability", Monthly Weather Review 78(1), DOI
  10.1175/1520-0493(1950)078<0001:VOFEIT>2.0.CO;2.
- Murphy 1973, "A New Vector Partition of the Probability Score",
  J. Appl. Meteor. 12(4), DOI
  10.1175/1520-0450(1973)012<0595:ANVPOT>2.0.CO;2.
- Gneiting & Raftery 2007, "Strictly Proper Scoring Rules,
  Prediction, and Estimation", JASA 102(477), DOI
  10.1198/016214506000001437.
- DeGroot & Fienberg 1983, "The Comparison and Evaluation of
  Forecasters", The Statistician 32(1), DOI 10.2307/2987588.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


def _arrays(p: Sequence[float], y: Sequence[int]) -> tuple[np.ndarray, np.ndarray]:
    p_arr = np.asarray(p, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    if p_arr.shape != y_arr.shape:
        raise ValueError(
            f"p and y shape mismatch: p={p_arr.shape}, y={y_arr.shape}"
        )
    if p_arr.size == 0:
        raise ValueError("empty input")
    if np.any((p_arr < 0) | (p_arr > 1)):
        raise ValueError("predicted probabilities must lie in [0, 1]")
    if not np.all(np.isin(y_arr, (0.0, 1.0))):
        raise ValueError("outcomes must be 0 or 1")
    return p_arr, y_arr


def brier_score(p: Sequence[float], y: Sequence[int]) -> float:
    """Mean Brier score, ``(p - y)^2`` averaged. Lower is better.

    Strictly proper. Range [0, 1]. Naive baseline (predicting the
    base rate) gives ``base_rate * (1 - base_rate)``.
    """
    p_arr, y_arr = _arrays(p, y)
    return float(np.mean((p_arr - y_arr) ** 2))


def log_loss(
    p: Sequence[float], y: Sequence[int], *, eps: float = 1e-15
) -> float:
    """Mean log loss (cross-entropy). Lower is better.

    Strictly proper. Range [0, +inf). Predictions are clipped to
    ``[eps, 1-eps]`` to avoid undefined ``log(0)`` when a forecast
    confidently misses.
    """
    p_arr, y_arr = _arrays(p, y)
    p_clipped = np.clip(p_arr, eps, 1.0 - eps)
    return float(
        -np.mean(y_arr * np.log(p_clipped) + (1.0 - y_arr) * np.log(1.0 - p_clipped))
    )


def spherical_score(p: Sequence[float], y: Sequence[int]) -> float:
    """Mean spherical score. Higher is better.

    ``S(p, y) = (y * p + (1 - y) * (1 - p)) / sqrt(p^2 + (1 - p)^2)``.

    Strictly proper. Range [0, 1]. Insensitive to the same kinds of
    miscalibration as Brier but penalises overconfidence less harshly
    than log loss.
    """
    p_arr, y_arr = _arrays(p, y)
    denom = np.sqrt(p_arr ** 2 + (1.0 - p_arr) ** 2)
    numer = y_arr * p_arr + (1.0 - y_arr) * (1.0 - p_arr)
    return float(np.mean(numer / denom))


@dataclass(frozen=True)
class MurphyDecomposition:
    """Murphy 1973 partition of the Brier score.

    ``brier == reliability - resolution + uncertainty`` exactly,
    up to floating-point error. Lower reliability is better.
    Higher resolution is better. Uncertainty depends only on the
    base rate.
    """

    brier: float
    reliability: float
    resolution: float
    uncertainty: float
    n_bins: int
    n_observations: int


def murphy_decomposition(
    p: Sequence[float], y: Sequence[int], *, n_bins: int = 10
) -> MurphyDecomposition:
    """Decompose Brier into reliability + resolution + uncertainty.

    The partition follows Murphy 1973: predictions are grouped into
    ``n_bins`` calibration bins of equal width on [0, 1]. Empty bins
    contribute zero to reliability and resolution.
    """
    if n_bins < 2:
        raise ValueError("n_bins must be at least 2")
    p_arr, y_arr = _arrays(p, y)
    n_total = p_arr.size

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.searchsorted(edges, p_arr, side="right") - 1, 0, n_bins - 1)

    overall_mean_y = float(np.mean(y_arr))
    reliability = 0.0
    resolution = 0.0
    for k in range(n_bins):
        mask = bin_idx == k
        n_k = int(np.sum(mask))
        if n_k == 0:
            continue
        p_bar_k = float(np.mean(p_arr[mask]))
        y_bar_k = float(np.mean(y_arr[mask]))
        reliability += n_k * (p_bar_k - y_bar_k) ** 2
        resolution += n_k * (y_bar_k - overall_mean_y) ** 2
    reliability /= n_total
    resolution /= n_total

    uncertainty = overall_mean_y * (1.0 - overall_mean_y)
    brier = brier_score(p, y)

    return MurphyDecomposition(
        brier=brier,
        reliability=reliability,
        resolution=resolution,
        uncertainty=uncertainty,
        n_bins=n_bins,
        n_observations=n_total,
    )


def reliability_curve(
    p: Sequence[float], y: Sequence[int], *, n_bins: int = 10
) -> list[dict[str, float]]:
    """Per-bin reliability data for plotting/calibration tables.

    Returns a list of ``{bin_lo, bin_hi, n, mean_predicted, mean_observed}``
    rows; empty bins are omitted.
    """
    p_arr, y_arr = _arrays(p, y)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.searchsorted(edges, p_arr, side="right") - 1, 0, n_bins - 1)
    out: list[dict[str, float]] = []
    for k in range(n_bins):
        mask = bin_idx == k
        n_k = int(np.sum(mask))
        if n_k == 0:
            continue
        out.append(
            {
                "bin_lo": float(edges[k]),
                "bin_hi": float(edges[k + 1]),
                "n": n_k,
                "mean_predicted": float(np.mean(p_arr[mask])),
                "mean_observed": float(np.mean(y_arr[mask])),
            }
        )
    return out


def sharpness(p: Sequence[float]) -> float:
    """Predictive sharpness = mean predictive variance.

    For binary forecasts: ``mean p (1 - p)``. Lower is sharper.
    Sharpness should be evaluated *subject to* calibration
    (Gneiting-Balabdaoui-Raftery 2007).
    """
    p_arr = np.asarray(p, dtype=float)
    if p_arr.size == 0:
        raise ValueError("empty input")
    return float(np.mean(p_arr * (1.0 - p_arr)))
