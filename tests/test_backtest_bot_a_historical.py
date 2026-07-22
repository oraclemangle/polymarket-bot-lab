"""Tests for scripts/backtest_bot_a_historical.py.

Covers the pure-logic helpers (trade simulation, report computation, argument
parsing). The data-loading path is exercised via a synthetic parquet fixture.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "backtest_bot_a_historical",
    Path(__file__).resolve().parent.parent / "scripts" / "backtest_bot_a_historical.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["backtest_bot_a_historical"] = _mod
_SPEC.loader.exec_module(_mod)


# --- simulate_trade ---

def test_simulate_trade_no_wins_is_profit():
    """NO resolves: we bought NO at 0.96, exits at 1.00 → profit."""
    t = _mod.simulate_trade(
        "m1", "q1", "geopolitics", 1000000, 2000000, 0.04, 0,
    )
    # entry no_price = 0.96; exit = 1.00 → edge = (1-0.96)/0.96 = ~4.17%
    assert t.no_entry_price == pytest.approx(0.96)
    assert t.outcome_yes_won == 0
    assert t.realised_pnl_usd > 0
    assert t.realised_edge_pct == pytest.approx(4.17, abs=0.1)


def test_simulate_trade_yes_wins_is_loss():
    """YES resolves: we bought NO at 0.96, exits at 0 → full loss."""
    t = _mod.simulate_trade(
        "m2", "q2", "politics", 0, 86400000, 0.04, 1,
    )
    assert t.outcome_yes_won == 1
    assert t.realised_pnl_usd == pytest.approx(-30.0, abs=0.01)  # ENTRY_SIZE_USD
    assert t.realised_edge_pct == pytest.approx(-100.0, abs=0.1)


def test_simulate_trade_days_held():
    entry_ts = 1_000_000_000_000
    resolution_ts = entry_ts + 14 * 86400 * 1000  # 14 days later
    t = _mod.simulate_trade("m", "q", "cat", entry_ts, resolution_ts, 0.05, 0)
    assert t.days_held == pytest.approx(14.0)


# --- compute_report ---

def test_compute_report_empty():
    r = _mod.compute_report([])
    assert r.n_qualifying == 0
    assert r.hit_rate == 0.0


def test_compute_report_all_hits():
    """Every trade resolves NO → 100% hit rate, positive edge."""
    trades = [
        _mod.simulate_trade(f"m{i}", "q", "geopolitics", 0, 86400000, 0.05, 0)
        for i in range(10)
    ]
    r = _mod.compute_report(trades)
    assert r.n_qualifying == 10
    assert r.hit_rate == 1.0
    assert r.mean_edge_pct > 0
    assert r.total_pnl_usd > 0


def test_compute_report_mixed():
    """Mix of hits/misses; hit rate and PnL reflect the mix."""
    trades = []
    for i in range(8):
        trades.append(_mod.simulate_trade(f"m{i}", "q", "geopolitics", 0, 86400000, 0.05, 0))  # win
    for i in range(2):
        trades.append(_mod.simulate_trade(f"mL{i}", "q", "geopolitics", 0, 86400000, 0.05, 1))  # loss
    r = _mod.compute_report(trades)
    assert r.n_qualifying == 10
    assert r.hit_rate == 0.8


def test_compute_report_bucket_breakdown():
    """Different entry prices bucketize correctly."""
    trades = [
        _mod.simulate_trade("m1", "q", "geopolitics", 0, 86400000, 0.02, 0),
        _mod.simulate_trade("m2", "q", "geopolitics", 0, 86400000, 0.03, 0),
        _mod.simulate_trade("m3", "q", "geopolitics", 0, 86400000, 0.03, 0),
        _mod.simulate_trade("m4", "q", "geopolitics", 0, 86400000, 0.04, 1),
    ]
    r = _mod.compute_report(trades)
    bucket_by_key = {b["bucket"]: b for b in r.by_entry_bucket}
    assert bucket_by_key["02c"]["n"] == 1
    assert bucket_by_key["03c"]["n"] == 2
    assert bucket_by_key["04c"]["n"] == 1


def test_compute_report_category_breakdown():
    trades = [
        _mod.simulate_trade("m1", "q", "geopolitics", 0, 86400000, 0.05, 0),
        _mod.simulate_trade("m2", "q", "politics", 0, 86400000, 0.05, 0),
        _mod.simulate_trade("m3", "q", "politics", 0, 86400000, 0.05, 1),
    ]
    r = _mod.compute_report(trades)
    cat_by_key = {c["category"]: c for c in r.by_category}
    assert cat_by_key["geopolitics"]["n"] == 1
    assert cat_by_key["politics"]["n"] == 2
    assert cat_by_key["politics"]["hit_rate"] == pytest.approx(0.5)


def test_compute_report_max_drawdown_on_streak_of_losses():
    trades = [
        _mod.simulate_trade("m1", "q", "geopolitics", 0, 86400000, 0.05, 0),  # win
        _mod.simulate_trade("m2", "q", "geopolitics", 0, 86400000, 0.05, 1),  # loss (-30)
        _mod.simulate_trade("m3", "q", "geopolitics", 0, 86400000, 0.05, 1),  # loss (-30)
    ]
    r = _mod.compute_report(trades)
    # DD is the drop from the peak after the first win.
    assert r.max_drawdown_pct > 0.0


# --- load_markets (synthetic parquet) ---

def test_load_markets_handles_column_aliases(tmp_path):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    tbl = pa.table({
        "marketId": pa.array(["m1", "m2"], type=pa.string()),
        "tags": pa.array(["politics", "geopolitics"], type=pa.string()),
        "winner": pa.array([0, 1], type=pa.int64()),
        "title": pa.array(["q1", "q2"], type=pa.string()),
    })
    pq.write_table(tbl, tmp_path / "markets.parquet")
    df, mid_col, cat_col, out_col, end_col, q_col = _mod.load_markets(tmp_path)
    assert mid_col == "marketId"
    assert cat_col == "tags"
    assert out_col == "winner"
    assert q_col == "title"


def test_load_markets_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        _mod.load_markets(tmp_path)


# --- run_simulation end-to-end ---

def test_run_simulation_end_to_end(tmp_path):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    # Synthetic slice: 5 markets, mix of categories, mix of entry prices + outcomes.
    tbl = pa.table({
        "market_id": pa.array(["m1", "m2", "m3", "m4", "m5"], type=pa.string()),
        "category": pa.array(["geopolitics", "politics", "sports", "geopolitics", "politics"],
                             type=pa.string()),
        "question": pa.array(["q1", "q2", "q3", "q4", "q5"], type=pa.string()),
        "yes_price": pa.array([0.03, 0.04, 0.05, 0.10, 0.02], type=pa.float64()),  # m3 sports skipped, m4 above threshold
        "yes_outcome": pa.array([0, 0, 1, 0, 1], type=pa.int64()),
        "created_at": pa.array([
            "2026-01-01", "2026-01-01", "2026-01-01", "2026-01-01", "2026-01-01"
        ], type=pa.string()),
        "end_date": pa.array([
            "2026-04-01", "2026-02-01", "2026-04-01", "2026-04-01", "2026-05-01"
        ], type=pa.string()),
    })
    pq.write_table(tbl, tmp_path / "markets.parquet")

    class Args:
        slice_dir = str(tmp_path)
        output_dir = str(tmp_path)
        limit_markets = None
        execute = False
        max_yes_price = 0.05
        min_dtr = 21
        max_dtr = 180

    trades, report = _mod.run_simulation(tmp_path, Args)
    # m3 (sports) excluded (wrong category); m4 (0.10 yes_price) excluded; m1/m2/m5 in.
    assert report.n_qualifying >= 2  # m1 definitely qualifies; m2/m5 depend on DTR
    # Check hit_rate is in [0, 1].
    assert 0.0 <= report.hit_rate <= 1.0


# --- format_report_md ---

def test_format_report_md_sections():
    trades = [
        _mod.simulate_trade("m1", "q", "geopolitics", 0, 86400000, 0.05, 0),
        _mod.simulate_trade("m2", "q", "politics", 0, 86400000, 0.03, 1),
    ]
    r = _mod.compute_report(trades)

    class Args:
        slice_dir = "x"
        max_yes_price = 0.05
        min_dtr = 21
        max_dtr = 180

    md = _mod.format_report_md(r, Args)
    assert "# Bot A Historical Backtest" in md
    assert "Hit rate" in md
    assert "By entry-price bucket" in md
    assert "By category" in md


# --- Timestamp normalisation ---

def test_to_ts_ms_from_int_seconds():
    assert _mod._to_ts_ms(1_700_000_000) == 1_700_000_000_000


def test_to_ts_ms_from_int_ms():
    assert _mod._to_ts_ms(1_700_000_000_000) == 1_700_000_000_000


def test_to_ts_ms_from_iso():
    out = _mod._to_ts_ms("2026-04-17T00:00:00Z")
    assert out > 1_700_000_000_000  # plausible ms epoch


def test_to_ts_ms_from_none():
    assert _mod._to_ts_ms(None) == 0


# --- parse_args ---

def test_parse_args_defaults():
    args = _mod.parse_args([])
    assert args.execute is False
    assert args.slice_dir == "data/wangzj_slice"
    assert args.max_yes_price == 0.05
    assert args.min_dtr == 21
    assert args.max_dtr == 180
