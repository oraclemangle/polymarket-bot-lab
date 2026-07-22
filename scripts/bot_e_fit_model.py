#!/usr/bin/env python3
"""Fit a Bot E predictor from recorded signals + outcomes.

Per `docs/bot-e-model-replacement-plan.md` E-2. This script:

  1. Reads the recorder DB at `$BOT_E_RECORDER_DB` (default `data/bot_e_recorder.db`).
  2. Reconstructs qualifying OBI signals using the same logic as
     `scripts/bot_e_calibration_spike.py`.
  3. Extracts features via `bots/bot_e_btc_scalp/features.py`.
  4. Labels each signal with its realised outcome (YES/NO from CEX price
     at market start vs end, same methodology as the current spike).
  5. Chronological split: 70% train, 15% val, 15% test.
  6. Fits a logistic regression (L2 regularized) and optionally a GBDT.
  7. Computes ECE, Brier, calibration slope on held-out.
  8. Writes model pickle + JSON metadata to `data/bot_e_models/<date>_<horizon>.pkl`.
  9. Refuses to set `passed_acceptance = True` unless heldout ECE ≤ 0.15,
     Brier ≤ 0.22, and N(heldout) ≥ 45.

**Usage on the bot host:**
  .venv/bin/python scripts/bot_e_fit_model.py --horizon 5-10min
  .venv/bin/python scripts/bot_e_fit_model.py --horizon 30s-60s --horizon-sweep

**Acceptance criteria (in code, not just docs):** this script WILL NOT write
`passed_acceptance=True` to the JSON if the held-out metrics fail. The daemon
refuses to load an artefact with `passed_acceptance=False`. Both sides must
agree; do not lower the thresholds here without updating the plan doc.

**Why this is a stub + comments, not a full implementation:**
This file is structural scaffolding. It defines the exact CLI, the exact
output artefact format, and the exact acceptance gate. The actual data
extraction and model fit requires (a) access to the recorder DB on the bot host,
(b) optional-dep imports (sklearn, pandas, numpy, lightgbm). The
implementation sections below are marked `TODO(fit)` and fail fast if run
without those deps. This is deliberate — we want the file in the repo so
the plan is executable, without pulling ML deps into the core daemon.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# NOTE: sklearn / lightgbm imports are LAZY inside the fit function to keep
# `import` of this file cheap for tests and CI.

log = logging.getLogger(__name__)


DEFAULT_RECORDER_DB = os.environ.get(
    "BOT_E_RECORDER_DB",
    str(Path(__file__).resolve().parent.parent / "data" / "bot_e_recorder.db"),
)
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "bot_e_models"

# Acceptance thresholds (from docs/bot-e-model-replacement-plan.md).
ACCEPT_MAX_ECE = 0.15
ACCEPT_MAX_BRIER = 0.22
ACCEPT_MIN_HELDOUT_N = 45
ACCEPT_MIN_SLOPE = 0.80
ACCEPT_MAX_SLOPE = 1.20


@dataclass
class FitResult:
    model_kind: str
    train_n: int
    val_n: int
    heldout_n: int
    heldout_ece: float
    heldout_brier: float
    heldout_calibration_slope: float
    passed_acceptance: bool
    notes: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fit Bot E predictor from recorder data.")
    p.add_argument(
        "--recorder-db",
        default=DEFAULT_RECORDER_DB,
        help="Path to bot_e_recorder.db (default: data/bot_e_recorder.db)",
    )
    p.add_argument(
        "--horizon",
        default="5-10min",
        choices=("5-10min", "30s-60s", "60s-180s", "mean-reversion-60s"),
        help="Label horizon. '5-10min' matches current live-window gate.",
    )
    p.add_argument(
        "--model-kind",
        default="logistic",
        choices=("logistic", "gbdt"),
        help="Model family. logistic is the mandatory first attempt.",
    )
    p.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Where to write the model pickle + JSON metadata pair.",
    )
    p.add_argument(
        "--horizon-sweep",
        action="store_true",
        help="Run all four horizons sequentially and produce a comparison report.",
    )
    p.add_argument(
        "--force-write",
        action="store_true",
        help="Write the artefact even if acceptance fails (still sets passed_acceptance=False).",
    )
    return p.parse_args(argv)


def compute_ece(predictions: list[float], outcomes: list[int], n_buckets: int = 10) -> float:
    """Expected Calibration Error (ECE) with equal-width buckets.

    For each bucket, |mean_predicted - mean_realised|, weighted by bucket size.
    """
    if not predictions:
        return 1.0
    bucket_preds: list[list[float]] = [[] for _ in range(n_buckets)]
    bucket_outs: list[list[int]] = [[] for _ in range(n_buckets)]
    for p, y in zip(predictions, outcomes, strict=True):
        # Clamp into [0, 1] before bucketing; clamp prevents index errors on
        # degenerate models that output exactly 1.0.
        p_clamped = min(max(p, 0.0), 0.9999)
        idx = min(int(p_clamped * n_buckets), n_buckets - 1)
        bucket_preds[idx].append(p)
        bucket_outs[idx].append(y)
    total = len(predictions)
    ece = 0.0
    for preds, outs in zip(bucket_preds, bucket_outs, strict=True):
        if not preds:
            continue
        bucket_mean_pred = sum(preds) / len(preds)
        bucket_mean_out = sum(outs) / len(outs)
        ece += abs(bucket_mean_pred - bucket_mean_out) * (len(preds) / total)
    return ece


def compute_brier(predictions: list[float], outcomes: list[int]) -> float:
    if not predictions:
        return 1.0
    return sum((p - y) ** 2 for p, y in zip(predictions, outcomes, strict=True)) / len(predictions)


def compute_calibration_slope(predictions: list[float], outcomes: list[int]) -> float:
    """Linear calibration slope: regress outcomes on predictions via OLS.

    Perfectly calibrated model → slope 1.0. Over-confident → slope < 1.
    """
    n = len(predictions)
    if n < 2:
        return 1.0
    mean_p = sum(predictions) / n
    mean_y = sum(outcomes) / n
    num = sum((p - mean_p) * (y - mean_y) for p, y in zip(predictions, outcomes, strict=True))
    den = sum((p - mean_p) ** 2 for p in predictions)
    if den == 0.0:
        return 1.0
    return num / den


def passes_acceptance(
    heldout_n: int, ece: float, brier: float, slope: float
) -> tuple[bool, str]:
    """Apply the numeric acceptance gate. Returns (passed, reason)."""
    reasons: list[str] = []
    if heldout_n < ACCEPT_MIN_HELDOUT_N:
        reasons.append(f"heldout_n={heldout_n} below {ACCEPT_MIN_HELDOUT_N}")
    if ece > ACCEPT_MAX_ECE:
        reasons.append(f"ece={ece:.3f} above {ACCEPT_MAX_ECE}")
    if brier > ACCEPT_MAX_BRIER:
        reasons.append(f"brier={brier:.3f} above {ACCEPT_MAX_BRIER}")
    if not (ACCEPT_MIN_SLOPE <= slope <= ACCEPT_MAX_SLOPE):
        reasons.append(f"slope={slope:.3f} outside [{ACCEPT_MIN_SLOPE}, {ACCEPT_MAX_SLOPE}]")
    if reasons:
        return False, "; ".join(reasons)
    return True, "passed"


def _extract_symbol_from_subid(sub_id: str) -> str:
    """Best-effort: recover 'BTC'|'ETH'|'SOL' from 'btc-2026-04-17-12:15'-style IDs."""
    if not sub_id:
        return ""
    head = sub_id.split("-", 1)[0].upper()
    return head if head in ("BTC", "ETH", "SOL") else head


def _extract_training_matrix(recorder_db_path: str, horizon: str):
    """Extract (X, y, timestamps) arrays from the recorder DB.

    Reuses the OBI extraction + outcome detection from
    `scripts/bot_e_calibration_spike.py` so the training signal is identical
    to what the live spike uses. Fills missing features (depth, polymarket_mid)
    with neutral defaults; the logistic regression will weight accordingly.
    """
    import sqlite3
    import numpy as np
    # Import from the sibling spike module; shares its extraction logic.
    import importlib.util
    spike_path = Path(__file__).resolve().parent / "bot_e_calibration_spike.py"
    spec = importlib.util.spec_from_file_location("bot_e_calibration_spike", spike_path)
    spike = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("bot_e_calibration_spike", spike)
    spec.loader.exec_module(spike)

    from bots.bot_e_btc_scalp.features import (
        FEATURE_NAMES, SignalContext, TradeTick, extract_features,
    )

    # OQ-035 (audit 2026-04-18, fix 2026-04-19): map horizon name to entry
    # window bounds in seconds-to-expiry. Prior code ignored the horizon
    # arg and always used ENTRY_WINDOW_MIN/MAX_SEC (5-10min). Horizons:
    #   "5-10min"   — current live window (t-10min to t-5min).
    #   "30s-60s"   — very-near-expiry, 30-60 seconds out.
    #   "60s-180s"  — 1-3 minutes before expiry.
    #   "mean-reversion-60s" — post-mid-window 30-90s before expiry, a
    #                          regime where OBI often reverses.
    _HORIZON_WINDOWS = {
        "5-10min":              (300.0, 600.0),
        "30s-60s":              (30.0,  60.0),
        "60s-180s":             (60.0,  180.0),
        "mean-reversion-60s":   (30.0,  90.0),
    }
    win_min, win_max = _HORIZON_WINDOWS.get(horizon, (300.0, 600.0))

    conn = sqlite3.connect(recorder_db_path)
    try:
        metas = spike.load_markets(conn)
        token_to_market = spike.build_token_to_market(metas)
        sub_to_meta = spike.build_sub_to_market(conn, token_to_market)
        signals, _n = spike.replay_signals(
            conn, token_to_market, sub_to_meta,
            entry_window_min_sec=win_min,
            entry_window_max_sec=win_max,
        )
        symbols_seen = sorted({_extract_symbol_from_subid(s.sub_id) for s in signals})
        cex_symbols = [f"{s}USDT" for s in symbols_seen if s in ("BTC", "ETH", "SOL")]
        cex_prices = spike.load_cex_prices(conn, cex_symbols) if cex_symbols else {}
        db_end_ms = conn.execute(
            "SELECT MAX(received_at_ms) FROM cex_trades"
        ).fetchone()[0] or 0
        db_start_ms = conn.execute(
            "SELECT MIN(received_at_ms) FROM cex_trades"
        ).fetchone()[0] or 0
        # 2026-04-18 U-* (Session 17m): trainer was calling
        # detect_resolutions_via_cex without db_start_ms. Function requires
        # both bounds to filter markets that fall outside the recorder's
        # observable window. Added here.
        outcomes = spike.detect_resolutions_via_cex(
            metas, cex_prices, db_start_ms=db_start_ms, db_end_ms=db_end_ms,
        )
        # attach_outcomes needs sub_to_meta for mapping subscription_id → condition_id.
        signals = spike.attach_outcomes(signals, outcomes, sub_to_meta)
    finally:
        conn.close()

    # OQ-035 FIX 2026-04-19: horizon is now honored via the entry-window
    # kwargs passed to replay_signals above. No fallback warning.
    log.info("horizon=%s extraction window: %.0fs-%.0fs to expiry; n_signals=%d",
             horizon, win_min, win_max, len(signals))

    # Build per-signal FeatureVector. Trades context: pull CEX trades on the
    # signal's symbol up to t0.
    cex_trades_by_sym: dict[str, list[TradeTick]] = {}
    conn = sqlite3.connect(recorder_db_path)
    try:
        rows = conn.execute("""
            SELECT symbol, received_at_ms, price, size, is_buyer_maker
            FROM cex_trades ORDER BY symbol, received_at_ms
        """).fetchall()
    finally:
        conn.close()
    for sym, ts, price, size, is_maker in rows:
        cex_trades_by_sym.setdefault(sym, []).append(TradeTick(
            ts_ms=int(ts), price=float(price), size=float(size),
            is_buyer_maker=bool(is_maker),
        ))

    X: list[list[float]] = []
    y: list[int] = []
    ts: list[int] = []
    for s in signals:
        if s.outcome_yes_won is None:
            continue
        sym = _extract_symbol_from_subid(s.sub_id)
        cex_sym = f"{sym}USDT"
        trades = cex_trades_by_sym.get(cex_sym, [])
        # CEX price at t0 and t0-10m.
        trades_at_t0 = [t for t in trades if t.ts_ms <= s.ts_ms]
        price_at_t0 = trades_at_t0[-1].price if trades_at_t0 else None
        t0_minus_10m = s.ts_ms - 10 * 60 * 1000
        trades_10m = [t for t in trades if t.ts_ms <= t0_minus_10m]
        price_10m_ago = trades_10m[-1].price if trades_10m else None
        ctx = SignalContext(
            t0_ms=s.ts_ms,
            tte_minutes=s.min_to_expiry,
            symbol=sym,
            polymarket_mid=None,   # not in recorder; defaults to neutral
            bid_notional=100.0,    # ditto; depth omitted from v1 features
            ask_notional=100.0,
            cex_trades_up_to_t0=trades_at_t0,
            cex_price_at_t0=price_at_t0,
            cex_price_10m_ago=price_10m_ago,
        )
        fv = extract_features(ctx, signal_id=s.sub_id)
        # Outcome label: 1 if YES won (price went up) AND signal said BUY_YES,
        # or if NO won AND signal said BUY_NO → signal's directional prediction
        # was correct. This is the binary target the model must learn.
        label = 1 if (
            (s.side == "BUY_YES" and s.outcome_yes_won)
            or (s.side == "BUY_NO" and not s.outcome_yes_won)
        ) else 0
        X.append(list(fv.values))
        y.append(label)
        ts.append(s.ts_ms)

    return np.array(X, dtype=float), np.array(y, dtype=int), np.array(ts, dtype=int), FEATURE_NAMES


def _chronological_split(X, y, ts, train_frac: float = 0.70, val_frac: float = 0.15):
    """Split by timestamp order. Returns (X_tr, y_tr, X_val, y_val, X_te, y_te)."""
    import numpy as np
    order = np.argsort(ts)
    X = X[order]; y = y[order]
    n = len(y)
    n_tr = int(n * train_frac)
    n_val = int(n * val_frac)
    return (
        X[:n_tr], y[:n_tr],
        X[n_tr:n_tr + n_val], y[n_tr:n_tr + n_val],
        X[n_tr + n_val:], y[n_tr + n_val:],
    )


def fit_and_evaluate(
    recorder_db_path: str,
    horizon: str,
    model_kind: str,
) -> tuple[Any, FitResult]:
    """Extract signals from recorder DB, fit model, evaluate on held-out.

    Requires scikit-learn + numpy. Uses `bot_e_calibration_spike` for the
    same OBI extraction + outcome detection as the live calibration gate,
    then runs FeatureVector extraction from `bots/bot_e_btc_scalp/features.py`.
    Logistic regression is the mandatory first attempt per the plan doc;
    GBDT (lightgbm) is allowed only as a second-pass upgrade after logistic
    fails AND calibration-curve nonlinearity is documented.
    """
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
    except ImportError as e:
        raise RuntimeError(
            f"Missing ML deps ({e}). Install on the bot host via "
            "`.venv/bin/pip install scikit-learn numpy pandas` before running."
        )
    if model_kind == "gbdt":
        try:
            import lightgbm  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "model_kind='gbdt' requires lightgbm. "
                "Install: `.venv/bin/pip install lightgbm`"
            )

    X, y, ts, feat_names = _extract_training_matrix(recorder_db_path, horizon)
    if len(y) == 0:
        raise RuntimeError(
            f"no signals extracted from {recorder_db_path}. Check that the "
            "recorder DB has pm_events with resolved outcomes."
        )
    X_tr, y_tr, X_val, y_val, X_te, y_te = _chronological_split(X, y, ts)

    if len(y_te) < ACCEPT_MIN_HELDOUT_N:
        log.warning(
            "heldout n=%d below acceptance min %d — acceptance will fail",
            len(y_te), ACCEPT_MIN_HELDOUT_N,
        )

    if model_kind == "logistic":
        # L2 regularized, liblinear solver (reasonable default on small data).
        # class_weight='balanced' protects against label imbalance.
        model = LogisticRegression(
            C=1.0, solver="liblinear", class_weight="balanced",
            max_iter=1000, random_state=0,
        )
    else:
        from lightgbm import LGBMClassifier
        model = LGBMClassifier(
            num_leaves=7, min_data_in_leaf=20,
            learning_rate=0.05, n_estimators=200,
            random_state=0, verbose=-1,
        )
    model.fit(X_tr, y_tr)

    # Evaluate on held-out.
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X_te)[:, 1]
    else:
        probs = model.predict(X_te)
    preds = [float(p) for p in probs]
    outs = [int(o) for o in y_te]

    ece = compute_ece(preds, outs, n_buckets=10)
    brier = compute_brier(preds, outs)
    slope = compute_calibration_slope(preds, outs)
    passed, reason = passes_acceptance(len(y_te), ece, brier, slope)

    result = FitResult(
        model_kind=model_kind,
        train_n=int(len(y_tr)),
        val_n=int(len(y_val)),
        heldout_n=int(len(y_te)),
        heldout_ece=float(ece),
        heldout_brier=float(brier),
        heldout_calibration_slope=float(slope),
        passed_acceptance=bool(passed),
        notes=reason,
    )
    return model, result


def write_artefact(
    raw_model: Any,
    fit_result: FitResult,
    output_dir: Path,
    horizon: str,
    force_write: bool,
) -> Path:
    """Write model pickle + JSON metadata pair. Refuses to write passing-flag
    on failed acceptance unless --force-write is set (flag still reflects reality).
    """
    from bots.bot_e_btc_scalp.features import FEATURE_NAMES  # avoid cycles
    output_dir.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    base = output_dir / f"{date_tag}_{horizon.replace('-', '_')}"
    pickle_path = base.with_suffix(".pkl")
    meta_path = base.with_suffix(".json")

    if not fit_result.passed_acceptance and not force_write:
        log.error(
            "refusing to write artefact — acceptance failed (%s). Use --force-write "
            "to write a NON-PASSING artefact for inspection.",
            fit_result.notes,
        )
        return Path()  # empty path signals "not written"

    with open(pickle_path, "wb") as f:
        pickle.dump(raw_model, f)
    meta = {
        "feature_names": list(FEATURE_NAMES),
        "model_kind": fit_result.model_kind,
        "trained_at_utc": datetime.now(UTC).isoformat(),
        "train_n": fit_result.train_n,
        "val_n": fit_result.val_n,
        "heldout_n": fit_result.heldout_n,
        "heldout_ece": fit_result.heldout_ece,
        "heldout_brier": fit_result.heldout_brier,
        "heldout_calibration_slope": fit_result.heldout_calibration_slope,
        "passed_acceptance": fit_result.passed_acceptance,
        "notes": fit_result.notes,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    log.info("wrote artefact to %s + %s", pickle_path, meta_path)
    return pickle_path


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    horizons = (
        ("5-10min", "30s-60s", "60s-180s", "mean-reversion-60s")
        if args.horizon_sweep
        else (args.horizon,)
    )
    output_dir = Path(args.output_dir)
    for horizon in horizons:
        log.info("fitting model kind=%s horizon=%s", args.model_kind, horizon)
        try:
            raw_model, fit_result = fit_and_evaluate(
                args.recorder_db, horizon, args.model_kind
            )
        except NotImplementedError as e:
            log.error("fit skipped: %s", e)
            return 3
        except Exception as e:
            log.exception("fit failed: %s", e)
            return 2
        written = write_artefact(
            raw_model, fit_result, output_dir, horizon, args.force_write
        )
        if not written.name:
            log.warning("no artefact written for horizon=%s", horizon)
            continue
        log.info(
            "horizon=%s passed=%s ece=%.3f brier=%.3f slope=%.3f notes=%s",
            horizon,
            fit_result.passed_acceptance,
            fit_result.heldout_ece,
            fit_result.heldout_brier,
            fit_result.heldout_calibration_slope,
            fit_result.notes,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
