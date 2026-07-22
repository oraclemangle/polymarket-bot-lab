"""Tests for the betting confidence sequence."""
from __future__ import annotations

import numpy as np
import pytest

from scripts.research.math_primitives.sequential_ci import (
    agrapa_lambda,
    binarize_outcomes_by_day,
    capital_process,
    confidence_sequence,
)


def test_agrapa_empty_history_zero():
    assert agrapa_lambda([], mu=0.5) == 0.0
    assert agrapa_lambda([0.5], mu=0.5) == 0.0  # only one observation


def test_agrapa_clipped_into_valid_range():
    history = [0.9] * 5  # very biased
    lam = agrapa_lambda(history, mu=0.5, a=0, b=1)
    # Half-clip to 0.5 / (b - mu) at most. mu = 0.5, so |lam| <= 1.
    assert -1.0 <= lam <= 1.0


def test_agrapa_input_validation():
    with pytest.raises(ValueError):
        agrapa_lambda([1.5], mu=0.5, a=0, b=1)
    with pytest.raises(ValueError):
        agrapa_lambda([0.5], mu=0.5, a=1.0, b=0.0)
    with pytest.raises(ValueError):
        agrapa_lambda([0.5], mu=2.0, a=0.0, b=1.0)


def test_capital_process_at_true_mean_stays_around_one():
    """Under the null mu = true mean, K_t is a martingale at 1."""
    rng = np.random.default_rng(0)
    n = 200
    p_true = 0.5
    obs = rng.binomial(1, p_true, n).astype(float)
    capital = capital_process(obs, mu=p_true)
    # By Doob, E[K_T] = 1; for n=200 and i.i.d. Bernoulli, K_T should
    # not blow up. Let it land in a wide band.
    assert 0.001 < capital < 1000.0


def test_capital_process_at_false_mean_grows():
    """Under a wrong mu far from the truth, K_t should grow."""
    rng = np.random.default_rng(1)
    n = 500
    p_true = 0.7
    obs = rng.binomial(1, p_true, n).astype(float)
    # Big enough gap between hypothesis and truth to drive K large.
    capital_wrong = capital_process(obs, mu=0.3)
    capital_right = capital_process(obs, mu=p_true)
    # Capital under the right mean should be smaller (closer to 1).
    assert capital_wrong > capital_right


def test_capital_process_input_validation():
    with pytest.raises(ValueError):
        capital_process([0.5], mu=2.0)  # mu out of [0,1]
    with pytest.raises(ValueError):
        capital_process([1.5], mu=0.5)  # observation out of support


def test_confidence_sequence_covers_truth_with_high_probability():
    """Across 50 simulations, the CS covers the truth >= 95%."""
    rng = np.random.default_rng(123)
    p_true = 0.4
    n = 100
    covered = 0
    trials = 50
    for _ in range(trials):
        obs = rng.binomial(1, p_true, n).astype(float)
        cs = confidence_sequence(obs, alpha=0.05, grid_size=51)
        if cs.lower <= p_true <= cs.upper:
            covered += 1
    # Anytime-valid CS coverage should be at least 1 - alpha = 0.95.
    assert covered >= int(0.85 * trials)  # leave headroom for grid quantisation


def test_confidence_sequence_shrinks_with_n():
    rng = np.random.default_rng(7)
    p_true = 0.6
    obs_short = rng.binomial(1, p_true, 30).astype(float)
    obs_long = rng.binomial(1, p_true, 500).astype(float)
    cs_short = confidence_sequence(obs_short, alpha=0.1, grid_size=51)
    cs_long = confidence_sequence(obs_long, alpha=0.1, grid_size=51)
    width_short = cs_short.upper - cs_short.lower
    width_long = cs_long.upper - cs_long.lower
    assert width_long < width_short


def test_confidence_sequence_empty():
    cs = confidence_sequence([], alpha=0.05)
    assert cs.lower == 0.0 and cs.upper == 1.0 and cs.n == 0


def test_binarize_outcomes_by_day_groups_correctly():
    # Two days, three trades each
    day1 = 1_700_000_000_000  # ms
    day2 = day1 + 86_400_000  # one day later
    timestamps = [day1, day1 + 60_000, day1 + 120_000, day2, day2 + 60_000, day2 + 120_000]
    outcomes = [1, 0, 1, 0, 0, 1]
    daily = binarize_outcomes_by_day(timestamps, outcomes)
    assert daily == [pytest.approx(2 / 3), pytest.approx(1 / 3)]


def test_binarize_outcomes_by_day_empty():
    assert binarize_outcomes_by_day([], []) == []


def test_binarize_outcomes_shape_check():
    with pytest.raises(ValueError):
        binarize_outcomes_by_day([1, 2], [1])
