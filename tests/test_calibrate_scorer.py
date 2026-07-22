"""Tests for scripts/calibrate_scorer.py.

Covers the metric computations + cache + report rendering. Actual LLM calls
are mocked via the `call_fn` injection path (same pattern as local_scorer tests).
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "calibrate_scorer",
    Path(__file__).resolve().parent.parent / "scripts" / "calibrate_scorer.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["calibrate_scorer"] = _mod
_SPEC.loader.exec_module(_mod)


# --- Brier ---

def test_brier_perfect_predictions():
    rows = [
        _mod.ScoredRow("m1", "q1", "test", p_yes=0.99, realised=1, pick="YES"),
        _mod.ScoredRow("m2", "q2", "test", p_yes=0.01, realised=0, pick="NO"),
    ]
    assert _mod.compute_brier(rows) < 0.001


def test_brier_excludes_skip():
    """SKIP rows must not contribute to Brier."""
    rows = [
        _mod.ScoredRow("m1", "q", "test", p_yes=0.5, realised=-1, pick="SKIP"),
        _mod.ScoredRow("m2", "q", "test", p_yes=0.0, realised=1, pick="YES"),  # 100% wrong
    ]
    # Only the one usable row counts → Brier = 1.0
    assert _mod.compute_brier(rows) == 1.0


def test_brier_empty_returns_one():
    assert _mod.compute_brier([]) == 1.0


# --- Decile calibration ---

def test_decile_bucketing_basic():
    """Three rows → three different buckets."""
    rows = [
        _mod.ScoredRow("m1", "q", "test", p_yes=0.05, realised=0, pick="NO"),
        _mod.ScoredRow("m2", "q", "test", p_yes=0.55, realised=1, pick="YES"),
        _mod.ScoredRow("m3", "q", "test", p_yes=0.95, realised=1, pick="YES"),
    ]
    deciles, ece = _mod.compute_decile_calibration(rows)
    # Bucket 0 (0.0-0.1), Bucket 5 (0.5-0.6), Bucket 9 (0.9-1.0) all have n=1.
    assert deciles[0]["n"] == 1
    assert deciles[5]["n"] == 1
    assert deciles[9]["n"] == 1
    # Others should have n=0.
    for i in (1, 2, 3, 4, 6, 7, 8):
        assert deciles[i]["n"] == 0


def test_decile_ece_on_well_calibrated():
    """Well-calibrated: 5 preds at 0.8, 4 realise YES → per-bucket gap = 0.0."""
    rows = []
    for i in range(5):
        rows.append(_mod.ScoredRow(
            f"m{i}", "q", "test", p_yes=0.8, realised=(1 if i < 4 else 0), pick="YES"
        ))
    deciles, ece = _mod.compute_decile_calibration(rows)
    assert ece == pytest.approx(0.0, abs=0.01)


def test_decile_ece_on_overconfident():
    """Predict 0.95 but only 0.5 realise YES → gap 0.45."""
    rows = [
        _mod.ScoredRow(f"m{i}", "q", "test", p_yes=0.95, realised=(1 if i < 5 else 0), pick="YES")
        for i in range(10)
    ]
    _, ece = _mod.compute_decile_calibration(rows)
    assert ece > 0.4


# --- Acceptance ---

def test_acceptance_passes_on_good_metrics():
    deciles = [{"bucket": "0.0-0.1", "n": 20, "gap": 0.02, "mean_predicted": 0.05, "realised_rate": 0.03}]
    passed, reason = _mod.check_acceptance(0.04, deciles)
    assert passed is True
    assert reason == "passed"


def test_acceptance_fails_on_high_brier():
    deciles = [{"bucket": "0.0-0.1", "n": 20, "gap": 0.02, "mean_predicted": 0.05, "realised_rate": 0.03}]
    passed, reason = _mod.check_acceptance(0.08, deciles)
    assert passed is False
    assert "brier=" in reason


def test_acceptance_fails_on_large_decile_gap():
    deciles = [{"bucket": "0.9-1.0", "n": 30, "gap": 0.15, "mean_predicted": 0.95, "realised_rate": 0.80}]
    passed, reason = _mod.check_acceptance(0.04, deciles)
    assert passed is False
    assert "bucket 0.9-1.0" in reason


def test_acceptance_tolerates_small_buckets():
    """Buckets with n<10 should be tolerated (too few to judge)."""
    deciles = [{"bucket": "0.1-0.2", "n": 5, "gap": 0.30, "mean_predicted": 0.15, "realised_rate": 0.45}]
    passed, _ = _mod.check_acceptance(0.04, deciles)
    assert passed is True  # small sample not counted


# --- Cache ---

def test_cache_store_and_lookup(tmp_path):
    db_path = tmp_path / "cache.db"
    _mod._cache_store(db_path, "m1", "groq-kimi", "YES", 0.75)
    cached = _mod._cache_lookup(db_path, "m1", "groq-kimi")
    assert cached == ("YES", 0.75)


def test_cache_lookup_miss(tmp_path):
    db_path = tmp_path / "cache.db"
    assert _mod._cache_lookup(db_path, "unknown", "any") is None


def test_cache_different_models_separate(tmp_path):
    """Same market but two different models → two distinct cached rows."""
    db_path = tmp_path / "cache.db"
    _mod._cache_store(db_path, "m1", "groq-kimi", "YES", 0.7)
    _mod._cache_store(db_path, "m1", "ollama-glm", "NO", 0.3)
    assert _mod._cache_lookup(db_path, "m1", "groq-kimi") == ("YES", 0.7)
    assert _mod._cache_lookup(db_path, "m1", "ollama-glm") == ("NO", 0.3)


# --- score_one with injected call ---

def test_score_one_happy_path(tmp_path):
    cache = tmp_path / "cache.db"
    def fake_call(model_id, prompt):
        return '{"pick": "YES", "p_yes": 0.82, "dispute_risk": 0.05, "confidence": 0.75, "rationale": "x"}'
    row = _mod.score_one("mid1", "Will X happen?", "groq-kimi",
                         call_fn=fake_call, cache_db_path=cache)
    assert row is not None
    assert row.pick == "YES"
    assert row.p_yes == 0.82
    # Second call uses cache.
    row2 = _mod.score_one("mid1", "Will X happen?", "groq-kimi",
                          call_fn=None, cache_db_path=cache)
    assert row2 is not None and row2.pick == "YES"


def test_score_one_returns_none_on_bad_output(tmp_path):
    def bad_call(model_id, prompt):
        return "I am not returning valid JSON"
    row = _mod.score_one("mid2", "q", "groq-kimi", call_fn=bad_call,
                         cache_db_path=tmp_path / "cache.db")
    assert row is None


def test_score_one_swallows_call_exception(tmp_path):
    def raising_call(model_id, prompt):
        raise RuntimeError("upstream 503")
    row = _mod.score_one("mid3", "q", "groq-kimi", call_fn=raising_call,
                         cache_db_path=tmp_path / "cache.db")
    assert row is None


# --- Report rendering ---

def test_format_report_md_contains_sections():
    report = _mod.CalibrationReport(
        model_id="test-model",
        n_total=100, n_skipped=5,
        overall_brier=0.05, overall_ece=0.04,
        deciles=[
            {"bucket": "0.0-0.1", "n": 20, "mean_predicted": 0.05, "realised_rate": 0.03, "gap": 0.02},
            {"bucket": "0.9-1.0", "n": 30, "mean_predicted": 0.95, "realised_rate": 0.93, "gap": 0.02},
        ],
        passed_acceptance=True, verdict="passed",
    )
    md = _mod.format_report_md(report, sample_size=120)
    assert "# Bot B Scorer Calibration — test-model" in md
    assert "Brier score:" in md
    assert "PASSED" in md
    assert "0.0-0.1" in md


def test_format_report_md_failure_analysis_included_on_fail():
    report = _mod.CalibrationReport(
        model_id="m",
        n_total=50, n_skipped=0,
        overall_brier=0.15, overall_ece=0.20,
        deciles=[],
        passed_acceptance=False,
        verdict="brier=0.15 above threshold 0.06",
    )
    md = _mod.format_report_md(report, sample_size=50)
    assert "Failure analysis" in md
    assert "brier=0.15" in md


# --- load_resolved_markets ---

def test_load_resolved_markets_sqlite(tmp_path):
    db_path = tmp_path / "cal.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE resolved_markets (
            market_id TEXT, question TEXT, yes_outcome INTEGER
        )
    """)
    conn.executemany(
        "INSERT INTO resolved_markets VALUES (?, ?, ?)",
        [("m1", "q1", 1), ("m2", "q2", 0)],
    )
    conn.commit()
    conn.close()
    rows = _mod.load_resolved_markets_from_sqlite(db_path)
    assert rows == [("m1", "q1", 1), ("m2", "q2", 0)]


def test_load_resolved_markets_sqlite_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        _mod.load_resolved_markets_from_sqlite(tmp_path / "nonexistent.db")


def test_load_resolved_markets_sqlite_respects_limit(tmp_path):
    db_path = tmp_path / "cal.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE resolved_markets (market_id TEXT, question TEXT, yes_outcome INTEGER)")
    for i in range(10):
        conn.execute("INSERT INTO resolved_markets VALUES (?, ?, ?)", (f"m{i}", f"q{i}", i % 2))
    conn.commit()
    conn.close()
    rows = _mod.load_resolved_markets_from_sqlite(db_path, limit=3)
    assert len(rows) == 3


def test_load_resolved_markets_parquet_no_outcome_returns_empty(tmp_path):
    """Parquet without outcome column → empty (caller falls back)."""
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    tbl = pa.table({
        "market_id": pa.array(["m1"], type=pa.string()),
        "question": pa.array(["q1"], type=pa.string()),
    })
    path = tmp_path / "markets.parquet"
    pq.write_table(tbl, path)
    rows = _mod.load_resolved_markets_from_parquet(path)
    assert rows == []


def test_load_resolved_markets_parquet_normalizes_outcome(tmp_path):
    """Accepts string YES/NO, ints, bools."""
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    tbl = pa.table({
        "market_id": pa.array(["m1", "m2", "m3"], type=pa.string()),
        "question": pa.array(["q1", "q2", "q3"], type=pa.string()),
        "outcome": pa.array(["YES", "no", "true"], type=pa.string()),
    })
    path = tmp_path / "markets.parquet"
    pq.write_table(tbl, path)
    rows = _mod.load_resolved_markets_from_parquet(path)
    assert {m: y for m, _q, y in rows} == {"m1": 1, "m2": 0, "m3": 1}


# --- Parse args ---

def test_parse_args_default_dry_run():
    args = _mod.parse_args(["--calibration-db", "x.db"])
    assert args.execute is False
    assert args.sample_size == 200
    assert args.scorer_model is None  # resolved to default inside main


# --- Model resolution ---

def test_resolve_models_explicit_scorer_models():
    args = _mod.parse_args([
        "--calibration-db", "x.db",
        "--scorer-model", "groq-qwen3",
        "--scorer-model", "ollama-kimi",
    ])
    assert _mod.resolve_models(args) == ["groq-qwen3", "ollama-kimi"]


def test_resolve_models_preset_a():
    args = _mod.parse_args(["--calibration-db", "x.db", "--preset", "a"])
    assert _mod.resolve_models(args) == ["groq-qwen3", "ollama-kimi"]


def test_resolve_models_preset_b_is_operator_approved_default():
    args = _mod.parse_args(["--calibration-db", "x.db", "--preset", "b"])
    out = _mod.resolve_models(args)
    assert out == ["groq-qwen3", "ollama-kimi", "deepseek-v3"]
    # Also matches the module-level DEFAULT_PRESET.
    assert _mod.MODEL_PRESETS[_mod.DEFAULT_PRESET] == out


def test_resolve_models_preset_b_plus_adds_gemini():
    args = _mod.parse_args(["--calibration-db", "x.db", "--preset", "b+"])
    assert "gemini-pro" in _mod.resolve_models(args)


def test_resolve_models_consensus_csv():
    args = _mod.parse_args([
        "--calibration-db", "x.db",
        "--consensus", "groq-qwen3,ollama-kimi,deepseek-v3",
    ])
    assert _mod.resolve_models(args) == ["groq-qwen3", "ollama-kimi", "deepseek-v3"]


def test_resolve_models_falls_back_to_default_preset():
    """With nothing specified, returns the operator-approved Option B trio."""
    args = _mod.parse_args(["--calibration-db", "x.db"])
    assert _mod.resolve_models(args) == ["groq-qwen3", "ollama-kimi", "deepseek-v3"]


def test_resolve_models_scorer_beats_preset():
    """--scorer-model takes precedence over --preset."""
    args = _mod.parse_args([
        "--calibration-db", "x.db",
        "--preset", "a",
        "--scorer-model", "deepseek-v3",
    ])
    assert _mod.resolve_models(args) == ["deepseek-v3"]


def test_default_preset_is_b():
    """Regression guard: Option B must remain the operator-approved default."""
    assert _mod.DEFAULT_PRESET == "b"
    assert _mod.MODEL_PRESETS["b"] == ["groq-qwen3", "ollama-kimi", "deepseek-v3"]


def test_groq_kimi_is_not_referenced_anywhere():
    """Regression guard: groq-kimi was removed from models.yaml on 2026-04-17.
    This test locks in that no preset accidentally re-adds it."""
    for preset_models in _mod.MODEL_PRESETS.values():
        assert "groq-kimi" not in preset_models
