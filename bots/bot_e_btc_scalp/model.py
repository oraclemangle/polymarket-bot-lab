"""Bot E replacement predictor — loads a fit model and predicts p(up | features).

Per `docs/bot-e-model-replacement-plan.md` E-2, this module replaces the
linear proxy `predicted_wr = 0.5 + |OBI|/2` with a fit model. It is
import-safe: no sklearn/lightgbm loaded unless `Predictor.load_from_disk`
is called. Live production path uses this module to score features from
`bots/bot_e_btc_scalp/features.py`.

**Calibration gate:** the companion fit scripts (`scripts/bot_e_fit_model.py`)
refuse to write a model artefact that doesn't meet held-out acceptance
(ECE ≤ 0.15, Brier ≤ 0.22, N(held-out) ≥ 45). A loaded model always has
a calibration report alongside it.

**Fallback:** if no model artefact is available, `Predictor.predict` raises.
The live daemon must guard with `if predictor.is_ready()` before calling.
Do NOT silently fall back to the linear proxy — that defeats the reason
for the replacement.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from bots.bot_e_btc_scalp.features import FEATURE_NAMES, FeatureVector

log = logging.getLogger(__name__)


@dataclass
class ModelArtefact:
    """Serialized model + calibration metadata.

    The binary model (sklearn pipeline / lightgbm booster) lives in a
    pickle alongside this JSON metadata file.
    """
    feature_names: tuple[str, ...]
    model_kind: str  # "logistic" | "gbdt"
    trained_at_utc: str
    train_n: int
    val_n: int
    heldout_n: int
    heldout_ece: float
    heldout_brier: float
    heldout_calibration_slope: float
    passed_acceptance: bool
    notes: str = ""


class PredictorNotReady(RuntimeError):
    """Raised by predict() when no model is loaded."""


@dataclass
class Predictor:
    """Stateful wrapper: load once, predict many.

    In tests, pass `raw_model` and `artefact` directly; in production, use
    `load_from_disk`.
    """
    raw_model: Any = None
    artefact: ModelArtefact | None = None

    @classmethod
    def load_from_disk(cls, model_path: str | os.PathLike) -> "Predictor":
        """Load a pickle + JSON pair. Refuses to load models that failed acceptance."""
        # Import pickle / sklearn lazily; trader daemon shouldn't pay for them
        # if this function never runs.
        import pickle as _pickle
        p = Path(model_path)
        meta_path = p.with_suffix(".json")
        if not p.exists() or not meta_path.exists():
            raise FileNotFoundError(
                f"predictor artefact incomplete: expected {p} + {meta_path}"
            )
        with open(meta_path, "r") as fh:
            meta_raw = json.load(fh)
        artefact = ModelArtefact(
            feature_names=tuple(meta_raw["feature_names"]),
            model_kind=meta_raw["model_kind"],
            trained_at_utc=meta_raw["trained_at_utc"],
            train_n=meta_raw["train_n"],
            val_n=meta_raw["val_n"],
            heldout_n=meta_raw["heldout_n"],
            heldout_ece=meta_raw["heldout_ece"],
            heldout_brier=meta_raw["heldout_brier"],
            heldout_calibration_slope=meta_raw["heldout_calibration_slope"],
            passed_acceptance=bool(meta_raw.get("passed_acceptance", False)),
            notes=meta_raw.get("notes", ""),
        )
        if not artefact.passed_acceptance:
            raise PredictorNotReady(
                f"refusing to load model at {p}: heldout ECE={artefact.heldout_ece} "
                f"Brier={artefact.heldout_brier} slope={artefact.heldout_calibration_slope} "
                f"did not pass acceptance criteria."
            )
        if artefact.feature_names != FEATURE_NAMES:
            raise PredictorNotReady(
                "feature-name mismatch between artefact and current code. "
                f"artefact: {artefact.feature_names!r} code: {FEATURE_NAMES!r}. "
                "Refit the model after changing feature engineering."
            )
        with open(p, "rb") as fh:
            raw = _pickle.load(fh)
        return cls(raw_model=raw, artefact=artefact)

    def is_ready(self) -> bool:
        return self.raw_model is not None and self.artefact is not None

    def predict(self, features: FeatureVector) -> float:
        """Return p(up) in (0, 1) for one feature vector."""
        if not self.is_ready():
            raise PredictorNotReady("no model loaded; refusing linear-proxy fallback")
        if len(features.values) != len(FEATURE_NAMES):
            raise ValueError(
                f"feature vector length {len(features.values)} != "
                f"expected {len(FEATURE_NAMES)}"
            )
        # Duck-typed call: sklearn pipelines and lightgbm boosters both
        # expose predict_proba or predict with a suitable signature.
        if hasattr(self.raw_model, "predict_proba"):
            # sklearn-style: returns shape (1, 2); p(up) = proba[0][1].
            proba = self.raw_model.predict_proba([list(features.values)])
            p_up = float(proba[0][1])
        elif hasattr(self.raw_model, "predict"):
            # lightgbm booster or similar: predict returns p(up) directly.
            pred = self.raw_model.predict([list(features.values)])
            p_up = float(pred[0])
        else:
            raise PredictorNotReady(
                f"model object {type(self.raw_model).__name__} exposes neither "
                "predict nor predict_proba"
            )
        # Clip to a safe range to avoid downstream math singularities;
        # matches the p_market clip in Bot B's sizer.
        return max(0.001, min(0.999, p_up))
