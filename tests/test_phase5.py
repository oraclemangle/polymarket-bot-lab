"""Phase 5 audit remediation tests — TTE stratification, CEX CVD gate,
depth-at-best gate."""
from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Item 1: TTE stratification
# ---------------------------------------------------------------------------


class TestTteStratification:
    def test_tte_bucket_label_boundaries(self):
        from scripts.bot_e_calibration_spike import tte_bucket_label
        assert tte_bucket_label(2.5) is None
        assert tte_bucket_label(3.0) == "3-5min"
        assert tte_bucket_label(4.9) == "3-5min"
        assert tte_bucket_label(5.0) == "5-7min"
        assert tte_bucket_label(6.9) == "5-7min"
        assert tte_bucket_label(7.0) == "7-10min"
        assert tte_bucket_label(9.9) == "7-10min"
        assert tte_bucket_label(10.0) == "10-15min"
        assert tte_bucket_label(14.9) == "10-15min"
        assert tte_bucket_label(15.0) is None

    def test_compute_stats_returns_tte_buckets(self):
        from scripts.bot_e_calibration_spike import SignalObs, compute_stats
        sigs = []
        # Three signals in the 5-7min bucket, all BUY_YES, YES won → all wins.
        for i in range(3):
            s = SignalObs(
                sub_id="btc-market-1", obi=0.4, abs_obi=0.4, side="BUY_YES",
                ts_ms=1_000_000 + i * 1000, end_ms=2_000_000,
                min_to_expiry=6.0,  # 5-7min bucket
                outcome_yes_won=True,
            )
            sigs.append(s)
        # One signal in the 10-15min bucket, BUY_NO, YES won → loss.
        s2 = SignalObs(
            sub_id="btc-market-1", obi=-0.5, abs_obi=0.5, side="BUY_NO",
            ts_ms=2_000_000, end_ms=3_000_000,
            min_to_expiry=12.0,
            outcome_yes_won=True,  # YES won but we bought NO → loss
        )
        sigs.append(s2)

        buckets, kept, n_regime_skip, tte = compute_stats(
            sigs, btc_timeline=[], apply_regime=False,
        )
        assert tte["5-7min"].n == 3
        assert tte["5-7min"].n_win == 3
        assert tte["10-15min"].n == 1
        assert tte["10-15min"].n_win == 0
        # Live-window aggregate should count the 5-7 signals.
        assert tte["5-10min_aggregate"].n == 3
        assert tte["5-10min_aggregate"].n_win == 3

    def test_decide_gates_on_live_window(self):
        from scripts.bot_e_calibration_spike import BucketStats, decide
        # Aggregate looks fine but live-window WR is awful.
        buckets = {
            "0.20-0.30": BucketStats("0.20-0.30", n=200, n_win=120, sum_abs_obi=50),
        }
        tte = {
            "3-5min":  BucketStats("3-5min",  n=100, n_win=70, sum_abs_obi=25),
            "5-7min":  BucketStats("5-7min",  n=40,  n_win=15, sum_abs_obi=10),
            "7-10min": BucketStats("7-10min", n=0,   n_win=0,  sum_abs_obi=0),
            "10-15min": BucketStats("10-15min", n=60, n_win=35, sum_abs_obi=15),
            "5-10min_aggregate": BucketStats("5-10min_aggregate", n=40, n_win=15, sum_abs_obi=10),
        }
        go, reasons = decide(
            buckets, overall_wr=0.60, overall_n=200, weighted_ece=0.05,
            tte_buckets=tte,
        )
        assert go is False
        assert any("live-window" in r and "WR" in r for r in reasons)


# ---------------------------------------------------------------------------
# Item 2: CEX CVD gate
# ---------------------------------------------------------------------------


def _make_recorder_with_cex_trades(
    tmp_path: Path,
    pairs: list[tuple[int, str, float, float, int]],  # (ts_ms, symbol, price, size, is_buyer_maker)
) -> Path:
    db = tmp_path / "r.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "CREATE TABLE cex_trades (received_at_ms INTEGER, trade_time_ms INTEGER, "
            "symbol TEXT, price REAL, size REAL, is_buyer_maker INTEGER)"
        )
        conn.execute(
            "CREATE TABLE pm_events (received_at_ms INTEGER, subscription_id TEXT, "
            "event_type TEXT, asset_id TEXT, condition_id TEXT, payload_json TEXT)"
        )
        for ts, sym, price, size, is_bm in pairs:
            conn.execute(
                "INSERT INTO cex_trades VALUES (?, ?, ?, ?, ?, ?)",
                (ts, ts, sym, price, size, is_bm),
            )
        conn.commit()
    finally:
        conn.close()
    return db


class TestCexCvdGate:
    def test_positive_cvd_confirms_buy_yes(self, tmp_path, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        # Aggressive buys: is_buyer_maker=0 → +size.
        # 10 trades of 1 BTC @ 70k = +700k notional
        db = _make_recorder_with_cex_trades(
            tmp_path,
            [(1_080_000 + i * 1000, "BTCUSDT", 70000.0, 1.0, 0) for i in range(10)],
        )
        monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(db))
        monkeypatch.setattr(cfg, "BOT_E_CEX_CVD_GATE", True)
        monkeypatch.setattr(cfg, "BOT_E_CEX_CVD_MIN_USD", Decimal("1000"))
        cvd = m._read_cex_cvd("BTC", 1_100_000, window_sec=60.0)
        assert cvd is not None and cvd > 0
        ok, reason = m._cex_cvd_gate_ok("BTC", "BUY_YES", 1_100_000)
        assert ok is True
        assert "confirms" in reason

    def test_positive_cvd_blocks_buy_no(self, tmp_path, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        db = _make_recorder_with_cex_trades(
            tmp_path,
            [(1_080_000 + i * 1000, "BTCUSDT", 70000.0, 1.0, 0) for i in range(10)],
        )
        monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(db))
        monkeypatch.setattr(cfg, "BOT_E_CEX_CVD_GATE", True)
        monkeypatch.setattr(cfg, "BOT_E_CEX_CVD_MIN_USD", Decimal("1000"))
        ok, reason = m._cex_cvd_gate_ok("BTC", "BUY_NO", 1_100_000)
        assert ok is False
        assert "disagrees" in reason

    def test_gate_fails_open_when_cvd_below_min(self, tmp_path, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        # Only a tiny trade — below the min_usd threshold.
        db = _make_recorder_with_cex_trades(
            tmp_path,
            [(1_000_000, "BTCUSDT", 70000.0, 0.001, 0)],  # notional ~$70
        )
        monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(db))
        monkeypatch.setattr(cfg, "BOT_E_CEX_CVD_GATE", True)
        monkeypatch.setattr(cfg, "BOT_E_CEX_CVD_MIN_USD", Decimal("1000"))
        ok, reason = m._cex_cvd_gate_ok("BTC", "BUY_NO", 1_000_100)
        assert ok is True
        assert "small" in reason

    def test_gate_fails_open_when_db_missing(self, monkeypatch, tmp_path):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(tmp_path / "does_not_exist.db"))
        monkeypatch.setattr(cfg, "BOT_E_CEX_CVD_GATE", True)
        ok, reason = m._cex_cvd_gate_ok("BTC", "BUY_YES", 1_000_000)
        assert ok is True
        assert reason == "cex_cvd_unavailable"

    def test_gate_disabled_via_config(self, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        monkeypatch.setattr(cfg, "BOT_E_CEX_CVD_GATE", False)
        ok, reason = m._cex_cvd_gate_ok("BTC", "BUY_NO", 1_000_000)
        assert ok is True
        assert reason == "cex_cvd_gate_disabled"

    def test_negative_cvd_confirms_buy_no(self, tmp_path, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        # Aggressive sells: is_buyer_maker=1 → -size.
        db = _make_recorder_with_cex_trades(
            tmp_path,
            [(1_080_000 + i * 1000, "BTCUSDT", 70000.0, 1.0, 1) for i in range(10)],
        )
        monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(db))
        monkeypatch.setattr(cfg, "BOT_E_CEX_CVD_GATE", True)
        monkeypatch.setattr(cfg, "BOT_E_CEX_CVD_MIN_USD", Decimal("1000"))
        cvd = m._read_cex_cvd("BTC", 1_100_000, window_sec=60.0)
        assert cvd is not None and cvd < 0
        ok, _reason = m._cex_cvd_gate_ok("BTC", "BUY_NO", 1_100_000)
        assert ok is True


# ---------------------------------------------------------------------------
# Item 3: depth-at-best gate
# ---------------------------------------------------------------------------


class TestDepthGate:
    def test_deep_book_passes(self, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_GATE", True)
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_MIN_USD", Decimal("500"))
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_BAND_WIDTH", Decimal("0.005"))
        book = {"bids": [[0.50, 2000], [0.498, 2000], [0.496, 2000]]}
        ok, reason = m._depth_gate_ok(book=book, signal_side="BUY_YES", best_price=Decimal("0.50"))
        assert ok is True
        assert "depth_ok" in reason

    def test_thin_book_blocks(self, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_GATE", True)
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_MIN_USD", Decimal("500"))
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_BAND_WIDTH", Decimal("0.005"))
        book = {"bids": [[0.50, 50], [0.498, 50]]}
        ok, reason = m._depth_gate_ok(book=book, signal_side="BUY_YES", best_price=Decimal("0.50"))
        assert ok is False
        assert "depth_thin" in reason

    def test_gate_fails_open_when_book_missing(self, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_GATE", True)
        ok, reason = m._depth_gate_ok(book=None, signal_side="BUY_YES", best_price=None)
        assert ok is True
        assert reason == "depth_unavailable"

    def test_gate_disabled_via_config(self, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_GATE", False)
        # Even a thin book passes when disabled.
        book = {"bids": [[0.50, 1], [0.498, 1]]}
        ok, reason = m._depth_gate_ok(book=book, signal_side="BUY_YES", best_price=Decimal("0.50"))
        assert ok is True
        assert reason == "depth_gate_disabled"

    def test_depth_sum_stops_at_band_boundary(self, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_GATE", True)
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_MIN_USD", Decimal("500"))
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_BAND_WIDTH", Decimal("0.005"))
        # Best 0.50, band goes down to 0.495. First level ($300), second in
        # band ($300), third below band should be ignored.
        book = {
            "bids": [
                [0.50, 600],    # 300 USD in band
                [0.496, 600],   # 297.6 USD in band
                [0.490, 10000], # 4900 USD but BELOW band → ignored
            ],
        }
        ok, reason = m._depth_gate_ok(book=book, signal_side="BUY_YES", best_price=Decimal("0.50"))
        # Only first two levels count: 300 + 297.6 = 597.6 >= 500 → ok.
        assert ok is True

    def test_gate_accepts_dict_level_form(self, monkeypatch):
        from bots.bot_e_btc_scalp import __main__ as m
        from bots.bot_e_btc_scalp import config as cfg
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_GATE", True)
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_MIN_USD", Decimal("500"))
        monkeypatch.setattr(cfg, "BOT_E_DEPTH_BAND_WIDTH", Decimal("0.005"))
        book = {"bids": [{"price": 0.50, "size": 2000}, {"price": 0.499, "size": 2000}]}
        ok, _reason = m._depth_gate_ok(book=book, signal_side="BUY_YES", best_price=Decimal("0.50"))
        assert ok is True
