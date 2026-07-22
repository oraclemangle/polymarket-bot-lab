from __future__ import annotations

import json

import pytest

from scripts.research.markov_state_replay import (
    bot_g_micro_state,
    estimate_transition_matrix,
    expected_value_by_next_state,
    forecast_next,
    multi_step_transition,
    run_json_state_replay,
    stationary_distribution,
    walk_forward_forecasts,
)


def test_estimate_transition_matrix_counts_and_row_normalises():
    estimate = estimate_transition_matrix(
        ["bull", "bull", "bear", "bull", "sideways", "sideways"],
        states=("bull", "bear", "sideways"),
        min_row_count=1,
        min_cell_count=1,
    )

    assert estimate.counts == [
        [1, 1, 1],
        [1, 0, 0],
        [0, 0, 1],
    ]
    assert estimate.matrix[0] == pytest.approx([1 / 3, 1 / 3, 1 / 3])
    assert estimate.matrix[1] == pytest.approx([1.0, 0.0, 0.0])
    assert estimate.matrix[2] == pytest.approx([0.0, 0.0, 1.0])


def test_alpha_smoothing_prevents_fake_certainty():
    estimate = estimate_transition_matrix(
        ["bull", "bear"],
        states=("bull", "bear", "sideways"),
        alpha=1.0,
        min_row_count=30,
        min_cell_count=20,
    )

    assert estimate.matrix[0] == pytest.approx([0.25, 0.5, 0.25])
    assert set(estimate.sparse_rows) == {"bull", "bear", "sideways"}
    assert estimate.sparse_cells


def test_multi_step_transition_uses_matrix_power():
    matrix = [
        [0.8, 0.2],
        [0.1, 0.9],
    ]

    result = multi_step_transition(matrix, 2)
    assert result[0] == pytest.approx([0.66, 0.34])
    assert result[1] == pytest.approx([0.17, 0.83])


def test_stationary_distribution_solves_left_eigenvector():
    matrix = [
        [0.8, 0.2],
        [0.1, 0.9],
    ]

    assert stationary_distribution(matrix) == pytest.approx([1 / 3, 2 / 3])


def test_forecast_next_returns_state_probabilities():
    estimate = estimate_transition_matrix(
        ["bull", "bull", "bear", "bear", "bull"],
        states=("bull", "bear"),
        min_row_count=1,
        min_cell_count=1,
    )

    assert forecast_next(estimate, current_state="bull") == pytest.approx({
        "bull": 0.5,
        "bear": 0.5,
    })


def test_walk_forward_uses_only_history_before_current_index():
    forecasts = walk_forward_forecasts(
        ["a", "a", "b", "b", "b"],
        lookback=3,
        states=("a", "b"),
        alpha=0.0,
        min_row_count=1,
        min_cell_count=1,
    )

    assert len(forecasts) == 2
    assert forecasts[0].index == 3
    assert forecasts[0].current_state == "b"
    assert forecasts[0].next_state == "b"
    # History at index 3 is ["a", "a", "b"], so b has no outgoing row yet.
    assert forecasts[0].probabilities == {"a": 0.0, "b": 0.0}


def test_expected_value_by_next_state_multiplies_probabilities():
    ev = expected_value_by_next_state(
        {"win": 0.2, "loss": 0.8},
        {"win": 9.0, "loss": -1.0},
    )

    assert ev == pytest.approx(1.0)


def test_bot_g_micro_state_encodes_key_regime_fields():
    state = bot_g_micro_state({
        "price_point_bucket": "6c-7c",
        "cex_tag": "aligned",
        "volatility_regime": "medium",
        "session_bucket": "us_overlap",
    })

    assert state == "price=6c-7c|cex=aligned|vol=medium|session=us_overlap"


def test_run_json_state_replay_accepts_bot_g_style_rows(tmp_path):
    path = tmp_path / "rows.json"
    path.write_text(json.dumps({
        "rows": [
            {"price_point_bucket": "6c-7c", "cex_tag": "aligned",
             "volatility_regime": "low", "session_bucket": "us_overlap"},
            {"price_point_bucket": "6c-7c", "cex_tag": "aligned",
             "volatility_regime": "low", "session_bucket": "us_overlap"},
            {"price_point_bucket": "7c-8c", "cex_tag": "against",
             "volatility_regime": "high", "session_bucket": "late_us"},
        ]
    }))

    report = run_json_state_replay(path=path, state_fields=None, lookback=2, alpha=1.0)

    assert report["n_rows"] == 3
    assert report["n_states"] == 2
    assert report["walk_forward_count"] == 1
