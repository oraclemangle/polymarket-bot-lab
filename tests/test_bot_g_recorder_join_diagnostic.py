from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from scripts.bot_g_recorder_join_diagnostic import (
    build_rows,
    extract_snapshot,
    improvement_bucket,
)


def _main_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            bot_id TEXT,
            placed_at TEXT,
            token_id TEXT,
            price REAL,
            status TEXT
        );
        CREATE TABLE trades (
            trade_id TEXT PRIMARY KEY,
            bot_id TEXT,
            order_id TEXT,
            side TEXT,
            price REAL,
            filled_at TEXT
        );
        """
    )
    return con


def _recorder_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE pm_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at_ms INTEGER,
            asset_id TEXT,
            event_type TEXT,
            payload_json TEXT
        );
        """
    )
    return con


def test_extract_snapshot_reads_price_change_for_token():
    snap = extract_snapshot(
        "price_change",
        """
        {
          "price_changes": [
            {"asset_id": "other", "best_bid": "0.01", "best_ask": "0.02"},
            {"asset_id": "tok1", "best_bid": "0.035", "best_ask": "0.045", "side": "SELL", "size": "80"}
          ]
        }
        """,
        "tok1",
    )

    assert snap["observed_bid"] == 0.035
    assert snap["observed_ask"] == 0.045
    assert snap["ask_size"] == 80.0


def test_improvement_bucket_boundaries():
    assert improvement_bucket(None) == "no_fill"
    assert improvement_bucket(0) == "no_improvement"
    assert improvement_bucket(0.4) == "<0.5c"
    assert improvement_bucket(0.5) == "0.5c-1c"
    assert improvement_bucket(1.5) == "1c-2c"
    assert improvement_bucket(3.0) == "2c-4c"
    assert improvement_bucket(4.0) == ">4c"


def test_build_rows_joins_live_order_to_nearby_recorder_event_and_keeps_missing_data():
    main = _main_db()
    recorder = _recorder_db()
    cutoff = datetime(2026, 5, 5, tzinfo=UTC)
    main.executemany(
        """
        INSERT INTO orders (order_id, bot_id, placed_at, token_id, price, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("live-1", "bot_g_prime_live", "2026-05-05 00:00:10", "tok1", 0.055, "MATCHED"),
            ("paper-1", "bot_g_prime", "2026-05-05 00:00:11", "tok2", 0.04, "PAPER_OPEN"),
        ],
    )
    main.execute(
        """
        INSERT INTO trades (trade_id, bot_id, order_id, side, price, filled_at)
        VALUES ('t1', 'bot_g_prime_live', 'live-1', 'BUY', 0.035, '2026-05-05 00:00:10')
        """
    )
    recorder.execute(
        """
        INSERT INTO pm_events (received_at_ms, asset_id, event_type, payload_json)
        VALUES (?, 'tok1', 'best_bid_ask', ?)
        """,
        (
            1777939210000,
            '{"asset_id":"tok1","best_bid":"0.034","best_ask":"0.044","ask_size":"90"}',
        ),
    )

    rows = build_rows(
        main,
        recorder,
        bot_ids=("bot_g_prime_live", "bot_g_prime"),
        cutoff=cutoff,
        before_ms=5000,
        after_ms=1000,
    )

    assert len(rows) == 2
    live = rows[0]
    assert live["observed_ask"] == 0.044
    assert live["observed_bid"] == 0.034
    assert live["spread_cents"] == 1.0
    assert live["price_improvement_cents"] == 2.0
    paper = rows[1]
    assert paper["observed_ask"] is None
    assert paper["price_improvement_cents"] is None
