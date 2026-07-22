"""Tests for scripts/download_wangzj_slice.py.

Covers the pure-logic helpers (column discovery, arg parsing). The HuggingFace
download paths are skipped (would require network + the 68MB markets.parquet).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "download_wangzj_slice",
    Path(__file__).resolve().parent.parent / "scripts" / "download_wangzj_slice.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["download_wangzj_slice"] = _mod
_SPEC.loader.exec_module(_mod)


def test_parse_args_defaults():
    args = _mod.parse_args([])
    assert args.execute is False
    assert "geopolitics" in args.categories
    assert "politics" in args.categories
    assert "finance" in args.categories
    assert "economics" in args.categories


def test_parse_args_custom_categories():
    args = _mod.parse_args(["--categories", "sports,tech"])
    assert args.categories == "sports,tech"


def test_parse_args_skip_files():
    args = _mod.parse_args(["--execute", "--skip-files", "users.parquet,quant.parquet"])
    assert args.execute is True
    assert "users.parquet" in args.skip_files


def test_default_file_list():
    """Guardrail against silent drift if someone adds or removes files."""
    assert _mod.FILES == ("markets.parquet", "trades.parquet", "users.parquet", "quant.parquet")


def test_repo_id_and_type():
    assert _mod.HF_REPO_ID == "SII-WANGZJ/Polymarket_data"
    assert _mod.HF_REPO_TYPE == "dataset"


def test_default_categories():
    assert "geopolitics" in _mod.DEFAULT_CATEGORIES
    assert "politics" in _mod.DEFAULT_CATEGORIES
    assert "finance" in _mod.DEFAULT_CATEGORIES
    assert "economics" in _mod.DEFAULT_CATEGORIES


def test_require_deps_raises_when_missing(monkeypatch):
    """Simulate missing deps: replace the import in the helper module."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name in ("pyarrow", "huggingface_hub"):
            raise ImportError(name)
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError, match="missing dependencies"):
        _mod._require_deps()


def test_discover_category_column_with_direct_name(tmp_path):
    """Synthesize a tiny parquet and verify column discovery."""
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    tbl = pa.table({
        "market_id": pa.array(["cid1", "cid2"], type=pa.string()),
        "category": pa.array(["politics", "sports"], type=pa.string()),
        "question": pa.array(["q1", "q2"], type=pa.string()),
    })
    path = tmp_path / "markets_tiny.parquet"
    pq.write_table(tbl, path)
    assert _mod.discover_category_column(path) == "category"


def test_discover_category_column_alias(tmp_path):
    """Column named 'event_category' should also be found."""
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    tbl = pa.table({
        "market_id": pa.array(["cid1"], type=pa.string()),
        "event_category": pa.array(["politics"], type=pa.string()),
    })
    path = tmp_path / "markets_alias.parquet"
    pq.write_table(tbl, path)
    assert _mod.discover_category_column(path) == "event_category"


def test_discover_category_column_raises_on_absent(tmp_path):
    """Schema with no category-like column should raise."""
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    tbl = pa.table({
        "market_id": pa.array(["cid1"], type=pa.string()),
        "price": pa.array([0.5], type=pa.float64()),
    })
    path = tmp_path / "markets_nocat.parquet"
    pq.write_table(tbl, path)
    with pytest.raises(RuntimeError, match="category column"):
        _mod.discover_category_column(path)


def test_discover_market_id_column_variants(tmp_path):
    """Accept market_id, condition_id, marketId."""
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    for col in ("market_id", "condition_id", "marketId"):
        tbl = pa.table({
            col: pa.array(["m1"], type=pa.string()),
            "other": pa.array([1], type=pa.int64()),
        })
        path = tmp_path / f"x_{col}.parquet"
        pq.write_table(tbl, path)
        assert _mod.discover_market_id_column(path) == col


def test_filter_markets_end_to_end(tmp_path):
    """Full filter cycle on a synthetic markets.parquet."""
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    tbl = pa.table({
        "market_id": pa.array(["m1", "m2", "m3", "m4"], type=pa.string()),
        "category": pa.array(["Politics", "sports", "GEOPOLITICS", "crypto"], type=pa.string()),
        "question": pa.array(["q1", "q2", "q3", "q4"], type=pa.string()),
    })
    path = tmp_path / "markets.parquet"
    pq.write_table(tbl, path)

    # Redirect OUTPUT_DIR to tmp_path.
    original_out = _mod.OUTPUT_DIR
    _mod.OUTPUT_DIR = tmp_path / "out"
    try:
        _, mids = _mod.filter_markets(path, ["geopolitics", "politics"])
    finally:
        _mod.OUTPUT_DIR = original_out
    assert mids == {"m1", "m3"}  # case-insensitive match


def test_filter_secondary_file_streams(tmp_path):
    """Stream-filter on a multi-row-group parquet."""
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    tbl = pa.table({
        "market_id": pa.array(["m1", "m2", "m3", "m4", "m5"], type=pa.string()),
        "price": pa.array([0.1, 0.2, 0.3, 0.4, 0.5], type=pa.float64()),
    })
    input_path = tmp_path / "trades.parquet"
    pq.write_table(tbl, input_path, row_group_size=2)  # 3 row groups

    output_path = tmp_path / "out" / "trades_filtered.parquet"
    rows = _mod.filter_secondary_file(
        input_path, output_path, {"m1", "m3"},
        mid_col_candidates=("market_id",),
    )
    assert rows == 2
    filtered = pq.read_table(output_path)
    assert set(filtered.column("market_id").to_pylist()) == {"m1", "m3"}
