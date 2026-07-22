"""Tests for scripts/bot_e_audit_recorder_data.py.

Builds a synthetic recorder DB with controlled gaps and asserts the
audit catches them at the right thresholds, with the right counts and
durations. Also checks the simultaneous-blackout detector.
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest


_SPEC = importlib.util.spec_from_file_location(
    "bot_e_audit_recorder_data",
    Path(__file__).resolve().parent.parent / "scripts" / "bot_e_audit_recorder_data.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["bot_e_audit_recorder_data"] = _mod
_SPEC.loader.exec_module(_mod)


def _build_db(tmp_path: Path) -> Path:
    """Minimal recorder schema for the audit tests."""
    db = tmp_path / "rec.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE pm_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at_ms INTEGER NOT NULL,
            subscription_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            asset_id TEXT,
            condition_id TEXT,
            payload_json TEXT NOT NULL
        );
        CREATE TABLE cex_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at_ms INTEGER NOT NULL,
            trade_time_ms INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            size REAL NOT NULL,
            is_buyer_maker INTEGER NOT NULL
        );
        CREATE TABLE heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emitted_at_ms INTEGER NOT NULL,
            source TEXT NOT NULL,
            subscription_id TEXT,
            last_message_age_sec REAL,
            metadata_json TEXT
        );
    """)
    conn.commit()
    conn.close()
    return db


def _add_pm(db: Path, sub_id: str, ts_list: list[int]):
    conn = sqlite3.connect(str(db))
    for ts in ts_list:
        conn.execute(
            "INSERT INTO pm_events "
            "(received_at_ms, subscription_id, event_type, payload_json) "
            "VALUES (?, ?, 'book', '{}')",
            (ts, sub_id),
        )
    conn.commit()
    conn.close()


def _add_cex(db: Path, symbol: str, ts_list: list[int]):
    conn = sqlite3.connect(str(db))
    for ts in ts_list:
        conn.execute(
            "INSERT INTO cex_trades "
            "(received_at_ms, trade_time_ms, symbol, price, size, is_buyer_maker) "
            "VALUES (?, ?, ?, 50000.0, 0.01, 0)",
            (ts, ts, symbol),
        )
    conn.commit()
    conn.close()


def _add_hb(db: Path, source: str, ts_list: list[int]):
    conn = sqlite3.connect(str(db))
    for ts in ts_list:
        conn.execute(
            "INSERT INTO heartbeats (emitted_at_ms, source) VALUES (?, ?)",
            (ts, source),
        )
    conn.commit()
    conn.close()


class TestAuditStream:
    def test_empty_stream_returns_zero_events(self, tmp_path: Path):
        db = _build_db(tmp_path)
        conn = sqlite3.connect(str(db))
        try:
            r = _mod.audit_stream(
                conn, table="pm_events", key_col="subscription_id",
                key_value="missing", ts_col="received_at_ms",
                threshold_s=60.0, since_ms=None,
            )
        finally:
            conn.close()
        assert r.n_events == 0
        assert r.gap_count == 0
        assert r.coverage_ratio == 0.0

    def test_no_gaps_in_dense_stream(self, tmp_path: Path):
        db = _build_db(tmp_path)
        # 10 events, 1s apart — no gap larger than 60s.
        _add_pm(db, "sub1", [1_000_000_000_000 + i * 1_000 for i in range(10)])
        conn = sqlite3.connect(str(db))
        try:
            r = _mod.audit_stream(
                conn, table="pm_events", key_col="subscription_id",
                key_value="sub1", ts_col="received_at_ms",
                threshold_s=60.0, since_ms=None,
            )
        finally:
            conn.close()
        assert r.n_events == 10
        assert r.gap_count == 0
        assert r.gap_total_s == 0.0
        assert r.coverage_ratio == 1.0

    def test_one_large_gap_detected(self, tmp_path: Path):
        db = _build_db(tmp_path)
        # Two events 100s apart — single gap.
        t0 = 1_000_000_000_000
        _add_pm(db, "sub1", [t0, t0 + 100_000])
        conn = sqlite3.connect(str(db))
        try:
            r = _mod.audit_stream(
                conn, table="pm_events", key_col="subscription_id",
                key_value="sub1", ts_col="received_at_ms",
                threshold_s=60.0, since_ms=None,
            )
        finally:
            conn.close()
        assert r.n_events == 2
        assert r.gap_count == 1
        assert r.gap_total_s == 100.0
        assert r.longest_gap_s == 100.0
        assert r.longest_gap_at_ms == t0

    def test_gap_under_threshold_ignored(self, tmp_path: Path):
        db = _build_db(tmp_path)
        t0 = 1_000_000_000_000
        # 50s gap — under the 60s threshold.
        _add_pm(db, "sub1", [t0, t0 + 50_000])
        conn = sqlite3.connect(str(db))
        try:
            r = _mod.audit_stream(
                conn, table="pm_events", key_col="subscription_id",
                key_value="sub1", ts_col="received_at_ms",
                threshold_s=60.0, since_ms=None,
            )
        finally:
            conn.close()
        assert r.gap_count == 0

    def test_since_filter_excludes_earlier_events(self, tmp_path: Path):
        db = _build_db(tmp_path)
        t0 = 1_000_000_000_000
        # 5 events, 1s apart, then a 200s gap, then 5 more 1s apart.
        early = [t0 + i * 1_000 for i in range(5)]
        late = [t0 + 200_000 + i * 1_000 for i in range(5)]
        _add_pm(db, "sub1", early + late)
        conn = sqlite3.connect(str(db))
        try:
            # without since: 1 gap (the 200s one)
            r_full = _mod.audit_stream(
                conn, table="pm_events", key_col="subscription_id",
                key_value="sub1", ts_col="received_at_ms",
                threshold_s=60.0, since_ms=None,
            )
            assert r_full.gap_count == 1
            # with since after the gap: 0 gaps
            r_late = _mod.audit_stream(
                conn, table="pm_events", key_col="subscription_id",
                key_value="sub1", ts_col="received_at_ms",
                threshold_s=60.0, since_ms=t0 + 199_000,
            )
            assert r_late.gap_count == 0
            assert r_late.n_events == 5
        finally:
            conn.close()

    def test_coverage_ratio(self, tmp_path: Path):
        db = _build_db(tmp_path)
        t0 = 1_000_000_000_000
        # 100s window, 80s gap → 20s of coverage.
        _add_pm(db, "sub1", [t0, t0 + 80_000, t0 + 100_000])
        conn = sqlite3.connect(str(db))
        try:
            r = _mod.audit_stream(
                conn, table="pm_events", key_col="subscription_id",
                key_value="sub1", ts_col="received_at_ms",
                threshold_s=60.0, since_ms=None,
            )
        finally:
            conn.close()
        # 80s gap detected; total wall = 100s; coverage = (100-80)/100 = 0.20
        assert r.gap_count == 1
        assert r.coverage_ratio == pytest.approx(0.20)


class TestSimultaneousGaps:
    def test_no_gap_when_streams_alternate(self, tmp_path: Path):
        db = _build_db(tmp_path)
        t0 = 1_000_000_000_000
        # Interleaved every 10s, no gap > 60s in the merged stream.
        _add_pm(db, "sub1", [t0 + i * 10_000 for i in range(10)])
        _add_cex(db, "BTCUSDT", [t0 + i * 10_000 + 5_000 for i in range(10)])
        conn = sqlite3.connect(str(db))
        try:
            gaps = _mod.find_simultaneous_gaps(
                conn, threshold_s=60.0, since_ms=None,
            )
        finally:
            conn.close()
        assert gaps == []

    def test_simultaneous_blackout_detected(self, tmp_path: Path):
        db = _build_db(tmp_path)
        t0 = 1_000_000_000_000
        # Both streams active early, both silent for 200s, both active late.
        _add_pm(db, "sub1", [t0 + i * 1_000 for i in range(5)])
        _add_pm(db, "sub1", [t0 + 200_000 + i * 1_000 for i in range(5)])
        _add_cex(db, "BTCUSDT", [t0 + 500 + i * 1_000 for i in range(5)])
        _add_cex(db, "BTCUSDT", [t0 + 200_500 + i * 1_000 for i in range(5)])
        conn = sqlite3.connect(str(db))
        try:
            gaps = _mod.find_simultaneous_gaps(
                conn, threshold_s=60.0, since_ms=None,
            )
        finally:
            conn.close()
        assert len(gaps) == 1
        start, dur = gaps[0]
        assert dur > 60.0  # detected
        # Gap starts ~ t0+5500 (last cex event before silence) — within 1s
        assert abs(start - (t0 + 4_500)) < 5_000

    def test_one_stream_alive_no_simultaneous_gap(self, tmp_path: Path):
        db = _build_db(tmp_path)
        t0 = 1_000_000_000_000
        # PM silent for 200s, but CEX keeps streaming throughout.
        _add_pm(db, "sub1", [t0])
        _add_pm(db, "sub1", [t0 + 200_000])
        _add_cex(db, "BTCUSDT", [t0 + i * 1_000 for i in range(220)])
        conn = sqlite3.connect(str(db))
        try:
            gaps = _mod.find_simultaneous_gaps(
                conn, threshold_s=60.0, since_ms=None,
            )
        finally:
            conn.close()
        # PM silent but CEX kept going — merged stream has no gap > 60s
        assert gaps == []


class TestListKeys:
    def test_distinct_keys_returned(self, tmp_path: Path):
        db = _build_db(tmp_path)
        t0 = 1_000_000_000_000
        _add_pm(db, "btc-2026", [t0])
        _add_pm(db, "eth-2026", [t0 + 1_000])
        _add_pm(db, "sol-2026", [t0 + 2_000])
        conn = sqlite3.connect(str(db))
        try:
            keys = _mod.list_keys(conn, "pm_events", "subscription_id", None)
        finally:
            conn.close()
        assert keys == ["btc-2026", "eth-2026", "sol-2026"]

    def test_since_filter_excludes_earlier_keys(self, tmp_path: Path):
        db = _build_db(tmp_path)
        t0 = 1_000_000_000_000
        _add_pm(db, "early-only", [t0])
        _add_pm(db, "late-only", [t0 + 1_000_000])
        conn = sqlite3.connect(str(db))
        try:
            keys = _mod.list_keys(
                conn, "pm_events", "subscription_id",
                since_ms=t0 + 500_000,
            )
        finally:
            conn.close()
        assert keys == ["late-only"]
