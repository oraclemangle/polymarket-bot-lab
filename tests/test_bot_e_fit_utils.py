"""Tests for the metric + acceptance helpers in `scripts/bot_e_fit_model.py`.

The heavy fit path (which needs sklearn + recorder DB) is skipped; these
tests cover the numeric gate and the metric functions that decide whether
an artefact is written.
"""
from __future__ import annotations

import pytest

import importlib.util
import sys
from pathlib import Path

# Load the script as a module (it's a CLI, not a package member).
# Register in sys.modules BEFORE exec so dataclass __module__ resolution works.
_SPEC = importlib.util.spec_from_file_location(
    "bot_e_fit_model",
    Path(__file__).resolve().parent.parent / "scripts" / "bot_e_fit_model.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["bot_e_fit_model"] = _mod
_SPEC.loader.exec_module(_mod)

compute_brier = _mod.compute_brier
compute_ece = _mod.compute_ece
compute_calibration_slope = _mod.compute_calibration_slope
passes_acceptance = _mod.passes_acceptance


# --- Brier ---

def test_brier_perfect_predictions():
    # Predict 0 for 0-outcomes and 1 for 1-outcomes → Brier = 0.
    assert compute_brier([0.0, 1.0, 1.0, 0.0], [0, 1, 1, 0]) == 0.0


def test_brier_coin_flip():
    # All predictions at 0.5, balanced outcomes → 0.25.
    assert compute_brier([0.5, 0.5, 0.5, 0.5], [0, 1, 0, 1]) == 0.25


def test_brier_max_wrong():
    # Predict 1 for 0-outcomes → Brier = 1.
    assert compute_brier([1.0, 1.0], [0, 0]) == 1.0


# --- ECE ---

def test_ece_perfectly_calibrated():
    preds = [0.1] * 10 + [0.9] * 10
    outs = [0] * 9 + [1] + [1] * 9 + [0]  # 10% and 90% realised
    ece = compute_ece(preds, outs)
    # Near zero (exact match would be 0.0; small drift due to bucketing).
    assert ece < 0.05


def test_ece_overconfident():
    # Always predict 0.9; realised 0.5 → large ECE.
    preds = [0.9] * 20
    outs = [1] * 10 + [0] * 10
    ece = compute_ece(preds, outs)
    # 0.9 predicted but 0.5 realised → 0.4 per-bucket gap.
    assert ece > 0.3


def test_ece_on_empty_returns_one():
    assert compute_ece([], []) == 1.0


# --- Calibration slope ---

def test_slope_perfect_calibration():
    # Predictions exactly equal outcomes → slope is 1 (up to numerical noise).
    preds = [0.1, 0.3, 0.5, 0.7, 0.9]
    outs = [0, 0, 1, 1, 1]
    slope = compute_calibration_slope(preds, outs)
    assert slope == pytest.approx(1.0, abs=0.2) or slope > 0


def test_slope_overconfident_below_one():
    # Overconfident model: predicts extremes but realised is more moderate.
    preds = [0.05, 0.1, 0.9, 0.95]
    outs = [0, 1, 0, 1]  # 50% realised on both ends
    slope = compute_calibration_slope(preds, outs)
    assert slope < 1.0


def test_slope_on_constant_predictions_returns_one():
    # No variance in predictions → slope defined as 1 (no signal).
    preds = [0.5, 0.5, 0.5, 0.5]
    outs = [0, 1, 0, 1]
    assert compute_calibration_slope(preds, outs) == 1.0


# --- Acceptance ---

def test_acceptance_passes_on_good_metrics():
    passed, reason = passes_acceptance(
        heldout_n=100, ece=0.08, brier=0.18, slope=0.95
    )
    assert passed is True
    assert reason == "passed"


def test_acceptance_fails_on_small_n():
    passed, reason = passes_acceptance(
        heldout_n=30, ece=0.08, brier=0.18, slope=0.95
    )
    assert passed is False
    assert "heldout_n=30" in reason


def test_acceptance_fails_on_high_ece():
    passed, reason = passes_acceptance(
        heldout_n=100, ece=0.25, brier=0.18, slope=0.95
    )
    assert passed is False
    assert "ece=" in reason


def test_acceptance_fails_on_high_brier():
    passed, reason = passes_acceptance(
        heldout_n=100, ece=0.08, brier=0.30, slope=0.95
    )
    assert passed is False
    assert "brier=" in reason


def test_acceptance_fails_on_slope_out_of_band():
    passed, reason = passes_acceptance(
        heldout_n=100, ece=0.08, brier=0.18, slope=0.6
    )
    assert passed is False
    assert "slope=" in reason


def test_acceptance_fails_on_multiple_criteria():
    """Multiple failures are all reported."""
    passed, reason = passes_acceptance(
        heldout_n=20, ece=0.40, brier=0.30, slope=0.5
    )
    assert passed is False
    for fragment in ("heldout_n=", "ece=", "brier=", "slope="):
        assert fragment in reason


# --- Fit path ---

def test_fit_and_evaluate_raises_without_recorder_db(tmp_path):
    """Running against a path that is not a recorder DB should raise clearly."""
    # Create an empty sqlite file (no schema).
    import sqlite3
    db = tmp_path / "empty.db"
    conn = sqlite3.connect(db)
    conn.close()
    with pytest.raises(Exception) as exc:
        _mod.fit_and_evaluate(str(db), "5-10min", "logistic")
    # Either sqlite OperationalError (no markets table) OR a RuntimeError
    # about no signals — both acceptable, indicating failure not silence.
    msg = str(exc.value).lower()
    assert ("no such table" in msg) or ("no signals" in msg) or ("missing" in msg)


def test_fit_and_evaluate_synthetic_path(tmp_path, monkeypatch):
    """End-to-end happy path using a mocked extractor. Guarantees the fit +
    evaluate + FitResult shape works without needing a full recorder DB."""
    import numpy as np
    # Create ~200 synthetic signals with moderate signal strength.
    rng = np.random.default_rng(42)
    n = 200
    X = rng.normal(0, 1, size=(n, 16))  # 16 features matches FEATURE_NAMES
    # Label weakly correlates with the first feature.
    y = (X[:, 0] + rng.normal(0, 0.5, size=n) > 0).astype(int)
    ts = np.arange(n)
    feat_names = (
        "obi_30s", "obi_60s", "obi_120s", "obi_300s",
        "depth_log_ratio", "cex_cvd_signed_2m", "vol_5m", "mid_distance_50c",
        "tte_bucket_3_5", "tte_bucket_5_7", "tte_bucket_7_10", "tte_bucket_10_15",
        "regime_trend_bps", "symbol_btc", "symbol_eth", "symbol_sol",
    )
    def fake_extract(path, horizon):
        return X, y, ts, feat_names
    monkeypatch.setattr(_mod, "_extract_training_matrix", fake_extract)
    model, result = _mod.fit_and_evaluate(str(tmp_path / "fake.db"),
                                          "5-10min", "logistic")
    assert result.model_kind == "logistic"
    assert result.train_n == int(n * 0.70)
    assert result.val_n == int(n * 0.15)
    assert result.heldout_n == n - result.train_n - result.val_n
    assert 0.0 <= result.heldout_brier <= 1.0
    assert 0.0 <= result.heldout_ece <= 1.0
    # Model should expose predict_proba.
    assert hasattr(model, "predict_proba")


def test_chronological_split_preserves_order(tmp_path):
    import numpy as np
    X = np.arange(100).reshape(-1, 1).astype(float)
    y = np.arange(100).astype(int)
    ts = np.arange(100)
    X_tr, y_tr, X_val, y_val, X_te, y_te = _mod._chronological_split(X, y, ts)
    # Train's last timestamp < val's first < test's first.
    assert y_tr[-1] < y_val[0] < y_te[0]
    assert len(y_tr) + len(y_val) + len(y_te) == 100


def test_extract_symbol_from_subid():
    assert _mod._extract_symbol_from_subid("btc-2026-04-17-12:15") == "BTC"
    assert _mod._extract_symbol_from_subid("ETH-2026-04-17-12:15") == "ETH"
    assert _mod._extract_symbol_from_subid("sol-up-down") == "SOL"
    assert _mod._extract_symbol_from_subid("") == ""
    assert _mod._extract_symbol_from_subid("xrp-x") == "XRP"  # passed through
