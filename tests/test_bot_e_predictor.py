"""Tests for E-2: Bot E Predictor (model artefact loader + guards).

Covers:
- Refuses to load a model whose calibration report says it failed acceptance.
- Refuses to load a model with mismatched feature names.
- predict() on unloaded model raises.
- predict() on loaded model clips to (0.001, 0.999).
- Works with both sklearn-style (predict_proba) and lightgbm-style (predict).

Does NOT exercise sklearn itself — model_kind / raw_model are injected to
keep the test suite fast and dependency-light.
"""
from __future__ import annotations

import json
import pickle
from pathlib import Path

import pytest

from bots.bot_e_btc_scalp.features import FEATURE_NAMES, FeatureVector
from bots.bot_e_btc_scalp.model import (
    ModelArtefact,
    Predictor,
    PredictorNotReady,
)


def _make_artefact(
    tmp_path: Path,
    *,
    raw_model,
    passed: bool = True,
    heldout_ece: float = 0.10,
    heldout_brier: float = 0.20,
    feature_names: tuple[str, ...] = None,
) -> Path:
    """Write a model pickle + JSON metadata pair. Return path to pickle."""
    model_path = tmp_path / "model.pkl"
    meta_path = tmp_path / "model.json"
    with open(model_path, "wb") as f:
        pickle.dump(raw_model, f)
    meta = {
        "feature_names": list(feature_names or FEATURE_NAMES),
        "model_kind": "logistic",
        "trained_at_utc": "2026-04-17T00:00:00+00:00",
        "train_n": 300,
        "val_n": 50,
        "heldout_n": 50,
        "heldout_ece": heldout_ece,
        "heldout_brier": heldout_brier,
        "heldout_calibration_slope": 0.95,
        "passed_acceptance": passed,
        "notes": "test artefact",
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f)
    return model_path


class _FakeSklearn:
    """Mimics sklearn classifier: predict_proba returns (N, 2) probabilities."""
    def __init__(self, p_up: float):
        self._p = p_up
    def predict_proba(self, X):
        return [[1.0 - self._p, self._p] for _ in X]


class _FakeLGBM:
    """Mimics lightgbm: predict returns (N,) probabilities."""
    def __init__(self, p_up: float):
        self._p = p_up
    def predict(self, X):
        return [self._p for _ in X]


def test_predictor_unloaded_raises():
    p = Predictor()
    assert not p.is_ready()
    fv = FeatureVector(values=(0.0,) * len(FEATURE_NAMES))
    with pytest.raises(PredictorNotReady, match="no model loaded"):
        p.predict(fv)


def test_predictor_refuses_failed_acceptance(tmp_path):
    path = _make_artefact(tmp_path, raw_model=_FakeSklearn(0.6), passed=False)
    with pytest.raises(PredictorNotReady, match="acceptance criteria"):
        Predictor.load_from_disk(path)


def test_predictor_refuses_feature_mismatch(tmp_path):
    bad_features = ("wrong", "feature", "names")
    path = _make_artefact(
        tmp_path, raw_model=_FakeSklearn(0.6), passed=True, feature_names=bad_features
    )
    with pytest.raises(PredictorNotReady, match="feature-name mismatch"):
        Predictor.load_from_disk(path)


def test_predictor_missing_artefact_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Predictor.load_from_disk(tmp_path / "nonexistent.pkl")


def test_predict_sklearn_style(tmp_path):
    path = _make_artefact(tmp_path, raw_model=_FakeSklearn(0.65))
    p = Predictor.load_from_disk(path)
    assert p.is_ready()
    fv = FeatureVector(values=(0.0,) * len(FEATURE_NAMES))
    out = p.predict(fv)
    assert 0.001 <= out <= 0.999
    assert out == pytest.approx(0.65)


def test_predict_lightgbm_style(tmp_path):
    path = _make_artefact(tmp_path, raw_model=_FakeLGBM(0.42))
    p = Predictor.load_from_disk(path)
    fv = FeatureVector(values=(0.0,) * len(FEATURE_NAMES))
    assert p.predict(fv) == pytest.approx(0.42)


def test_predict_clips_extreme_output(tmp_path):
    # Model that returns 1.0 (certainty) should be clipped to 0.999.
    hi = tmp_path / "hi"
    hi.mkdir()
    path = _make_artefact(hi, raw_model=_FakeSklearn(1.0))
    p = Predictor.load_from_disk(path)
    fv = FeatureVector(values=(0.0,) * len(FEATURE_NAMES))
    assert p.predict(fv) == pytest.approx(0.999)
    # And 0.0 clipped to 0.001.
    lo = tmp_path / "lo"
    lo.mkdir()
    path2 = _make_artefact(lo, raw_model=_FakeSklearn(0.0))
    p2 = Predictor.load_from_disk(path2)
    assert p2.predict(fv) == pytest.approx(0.001)


def test_predict_rejects_wrong_feature_length(tmp_path):
    path = _make_artefact(tmp_path, raw_model=_FakeSklearn(0.5))
    p = Predictor.load_from_disk(path)
    short = FeatureVector(values=(0.0, 0.0, 0.0))  # too short
    with pytest.raises(ValueError, match="feature vector length"):
        p.predict(short)
