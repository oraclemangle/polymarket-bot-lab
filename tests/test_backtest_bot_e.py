"""Tests for core/backtest_bot_e.py — OBI calibration harness."""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from bots.bot_e_recorder.schema import init_db
from core.backtest_bot_e import (
    ExpectancyTable,
    RecorderEvent,
    SubscriptionState,
    iter_events,
    min_to_exp_bucket,
    obi_to_bucket,
)


class TestBucketing:
    def test_obi_buckets(self):
        assert obi_to_bucket(0.05) == "obi<0.10"
        assert obi_to_bucket(0.10) == "obi:0.10-0.20"
        assert obi_to_bucket(0.15) == "obi:0.10-0.20"
        assert obi_to_bucket(0.25) == "obi:0.20-0.30"
        assert obi_to_bucket(0.40) == "obi:0.30-0.50"
        assert obi_to_bucket(0.50) == "obi>=0.50"
        assert obi_to_bucket(0.95) == "obi>=0.50"
        # symmetry
        assert obi_to_bucket(-0.25) == obi_to_bucket(0.25)

    def test_min_to_expiry_buckets(self):
        # Audit F3 (2026-04-16): labels now match the trader's actual entry
        # window (5-10 min). Previously 12 min was labelled "5-10 (entry)"
        # but the trader rejects it with pre_entry_window.
        assert min_to_exp_bucket(20) == "10+ (pre-entry)"
        assert min_to_exp_bucket(12) == "10+ (pre-entry)"
        assert min_to_exp_bucket(7) == "5–10 (entry)"
        assert min_to_exp_bucket(2) == "0–5 (holding)"
        assert min_to_exp_bucket(-1) == "resolution"


class TestExpectancyTable:
    def test_add_and_summarise(self):
        t = ExpectancyTable()
        t.add("obi:0.20-0.30", "5–10 (entry)", win=True, pnl=0.05)
        t.add("obi:0.20-0.30", "5–10 (entry)", win=False, pnl=-0.02)
        out = t.summary()
        assert "obi:0.20-0.30" in out
        assert "5–10 (entry)" in out
        # Check win rate 1/2 and mean pnl (0.05 - 0.02) / 2 = 0.015
        assert ",2,0.500,+0.0150" in out or "0.015" in out


class TestSubscriptionState:
    def test_obi_empty(self):
        s = SubscriptionState(subscription_id="s")
        assert s.obi(1000, 60.0) is None

    def test_obi_needs_yes_token_set(self):
        s = SubscriptionState(subscription_id="s")
        s.rolling_trades = [(100, "tok_a", 5.0), (200, "tok_a", 5.0)]
        # yes_token_id not set → None
        assert s.obi(1000, 60.0) is None

    def test_obi_all_yes(self):
        s = SubscriptionState(subscription_id="s", yes_token_id="Y", no_token_id="N")
        s.rolling_trades = [(100, "Y", 5.0), (200, "Y", 5.0)]
        # All YES volume → imbalance = +1.0
        v = s.obi(1000, 10.0)  # 10s window, trades at 100/200 ms — all within window
        assert v == 1.0

    def test_obi_split(self):
        s = SubscriptionState(subscription_id="s", yes_token_id="Y", no_token_id="N")
        s.rolling_trades = [(100, "Y", 10.0), (200, "N", 5.0)]
        v = s.obi(1000, 10.0)
        # (10 - 5) / (10 + 5) = 1/3
        assert abs(v - (1/3)) < 1e-6

    def test_obi_all_no(self):
        s = SubscriptionState(subscription_id="s", yes_token_id="Y", no_token_id="N")
        s.rolling_trades = [(100, "N", 5.0), (200, "N", 5.0)]
        v = s.obi(1000, 10.0)
        assert v == -1.0

    def test_obi_window_prunes(self):
        s = SubscriptionState(subscription_id="s", yes_token_id="Y", no_token_id="N")
        # Old trades outside window — should be pruned
        s.rolling_trades = [(100, "Y", 100.0)]   # 900ms old
        # Need >=2 trades AND total >=1 for OBI to compute; after pruning we have 0
        v = s.obi(2000, 0.5)   # 500ms window, trade at 100ms is 1900ms old
        assert v is None

    def test_obi_insufficient_volume(self):
        s = SubscriptionState(subscription_id="s", yes_token_id="Y", no_token_id="N")
        s.rolling_trades = [(100, "Y", 0.1), (200, "N", 0.1)]
        # Total volume 0.2 < 1.0 threshold → None
        assert s.obi(1000, 10.0) is None


class TestIterEvents:
    def test_iter_empty_db(self, tmp_path: Path):
        db_path = tmp_path / "empty.db"
        conn = init_db(db_path)
        conn.close()
        events = list(iter_events(db_path))
        assert events == []

    def test_iter_merged_by_time(self, tmp_path: Path):
        db_path = tmp_path / "data.db"
        conn = init_db(db_path)
        # Insert events out of natural order — iter should reassemble by time
        conn.execute(
            "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, "
            "asset_id, condition_id, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
            (1000, "sub1", "book", "tok1", "c1", json.dumps({"bids": [["0.4", "10"]]})),
        )
        conn.execute(
            "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, "
            "asset_id, condition_id, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
            (3000, "sub1", "last_trade_price", "tok1", "c1", json.dumps({"size": 5})),
        )
        conn.execute(
            "INSERT INTO cex_trades (received_at_ms, trade_time_ms, symbol, "
            "price, size, is_buyer_maker) VALUES (?, ?, ?, ?, ?, ?)",
            (2000, 2000, "BTCUSDT", 68000.0, 0.01, 1),
        )
        conn.commit()
        conn.close()

        events = list(iter_events(db_path))
        assert len(events) == 3
        # Correct time order: 1000, 2000, 3000
        assert [e.ts_ms for e in events] == [1000, 2000, 3000]
        # Correct kind mapping
        assert events[0].kind == "pm_book"
        assert events[1].kind == "cex_trade"
        assert events[2].kind == "pm_trade"

    def test_iter_respects_time_range(self, tmp_path: Path):
        db_path = tmp_path / "data.db"
        conn = init_db(db_path)
        for i, t in enumerate([100, 500, 1000, 1500]):
            conn.execute(
                "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, "
                "asset_id, condition_id, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                (t, "sub1", "book", "tok1", "c1", "{}"),
            )
        conn.commit()
        conn.close()

        events = list(iter_events(db_path, start_ms=400, end_ms=1200))
        assert [e.ts_ms for e in events] == [500, 1000]
