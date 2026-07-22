"""Tests for Bot K — Sports Taker paper lane."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from bots.bot_k_sports_taker.executor import _already_entered, _find_new_markets, _load_first_ticks


@pytest.fixture
def tmp_recorder_db(tmp_path: Path) -> Path:
    db = tmp_path / "recorder.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE markets (
            condition_id TEXT PRIMARY KEY,
            category TEXT,
            question TEXT,
            initial_yes_price REAL,
            discovered_at_ms INTEGER,
            end_date_ts INTEGER
        );
        CREATE TABLE pm_events (
            id INTEGER PRIMARY KEY,
            condition_id TEXT,
            event_type TEXT,
            received_at_ms INTEGER,
            payload_json TEXT
        );
        """
    )

    # Market in band — NBA futures
    con.execute(
        "INSERT INTO markets (condition_id, category, question, initial_yes_price, discovered_at_ms, end_date_ts) "
        "VALUES ('cond1', 'sports', 'Will Lakers win tomorrow?', 0.15, 1000000, 87400)"
    )
    # Tick within lookback
    con.execute(
        "INSERT INTO pm_events (condition_id, event_type, received_at_ms, payload_json) "
        "VALUES ('cond1', 'best_bid_ask', 1000100, '{\"best_bid\": 0.14, \"best_ask\": 0.15}')"
    )

    # Market in band — no tick
    con.execute(
        "INSERT INTO markets (condition_id, category, question, initial_yes_price, discovered_at_ms, end_date_ts) "
        "VALUES ('cond2', 'sports', 'Will Chiefs win this week?', 0.12, 2000000, 174800)"
    )

    # Market below band — politics (should not appear)
    con.execute(
        "INSERT INTO markets (condition_id, category, question, initial_yes_price, discovered_at_ms, end_date_ts) "
        "VALUES ('cond3', 'politics', 'Will Trump win 2028?', 0.05, 3000000, 174800)"
    )

    # Market above band
    con.execute(
        "INSERT INTO markets (condition_id, category, question, initial_yes_price, discovered_at_ms, end_date_ts) "
        "VALUES ('cond4', 'sports', 'Will Djokovic win Wimbledon 2026?', 0.25, 4000000, 174800)"
    )

    # Tick outside lookback (5 min = 300,000 ms)
    con.execute(
        "INSERT INTO pm_events (condition_id, event_type, received_at_ms, payload_json) "
        "VALUES ('cond4', 'best_bid_ask', 4301000, '{\"best_bid\": 0.24, \"best_ask\": 0.25}')"
    )

    # Market in band but too far from resolution
    con.execute(
        "INSERT INTO markets (condition_id, category, question, initial_yes_price, discovered_at_ms, end_date_ts) "
        "VALUES ('cond5', 'sports', 'Will Team X win the 2027 title?', 0.14, 5000000, 1778800)"
    )

    con.commit()
    con.close()
    return db


def test_find_new_markets(tmp_recorder_db: Path):
    con = sqlite3.connect(f"file:{tmp_recorder_db.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    markets = _find_new_markets(con)
    con.close()

    assert len(markets) == 2
    ids = {m["condition_id"] for m in markets}
    assert ids == {"cond1", "cond2"}


def test_find_new_markets_skips_far_dated_futures(tmp_recorder_db: Path):
    con = sqlite3.connect(f"file:{tmp_recorder_db.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    markets = _find_new_markets(con)
    con.close()

    assert "cond5" not in {m["condition_id"] for m in markets}


def test_load_first_ticks(tmp_recorder_db: Path):
    con = sqlite3.connect(f"file:{tmp_recorder_db.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    markets = _find_new_markets(con)
    ticks = _load_first_ticks(con, markets, lookback_min=5)
    con.close()

    assert "cond1" in ticks
    assert ticks["cond1"]["entry_price"] == pytest.approx(0.16)
    assert "cond2" not in ticks


def test_already_entered_no_db():
    # When run without an initialized main DB, should return False
    assert _already_entered("cond1") is False
