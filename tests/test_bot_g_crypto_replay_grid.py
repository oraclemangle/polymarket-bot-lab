from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from scripts.bot_g_crypto_replay_grid import (
    build_report,
    lead_bucket,
    price_bucket,
)


def _main_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            status TEXT,
            placed_at TEXT
        );
        CREATE TABLE trades (
            trade_id TEXT PRIMARY KEY,
            bot_id TEXT,
            order_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            fee_usd REAL,
            filled_at TEXT,
            usd_gbp_rate REAL,
            gbp_notional REAL
        );
        CREATE TABLE events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id TEXT,
            event_type TEXT,
            severity TEXT,
            message TEXT,
            payload TEXT,
            created_at TEXT
        );
        CREATE TABLE markets (
            condition_id TEXT PRIMARY KEY,
            question TEXT,
            category TEXT
        );
        """
    )
    return con


def _recorder_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE markets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_at_ms INTEGER NOT NULL,
            condition_id TEXT NOT NULL,
            question TEXT NOT NULL,
            end_date_iso TEXT,
            yes_token_id TEXT,
            no_token_id TEXT,
            symbol TEXT,
            duration_minutes INTEGER,
            volume_24h_usd REAL,
            yes_price REAL,
            category TEXT DEFAULT 'crypto',
            raw_json TEXT
        );
        """
    )
    return con


def test_bucket_helpers_match_theory_boundaries():
    assert lead_bucket(29.9) == "<30s"
    assert lead_bucket(30) == "30s-45s"
    assert lead_bucket(45) == "45s-60s"
    assert lead_bucket(60) == "60s-90s"

    assert price_bucket(0.02) == "1c-3c"
    assert price_bucket(0.034) == "3c-3.5c"
    assert price_bucket(0.05) == "3.5c-5.5c"
    assert price_bucket(0.07) == "5.5c-8c"


def test_replay_grid_enriches_entries_and_trims_jackpot_wins():
    main = _main_db()
    recorder = _recorder_db()
    cutoff = datetime(2026, 5, 5, 0, 0, tzinfo=UTC)

    recorder.executemany(
        """
        INSERT INTO markets (
            scan_at_ms, condition_id, question, end_date_iso, yes_token_id,
            no_token_id, symbol, duration_minutes, volume_24h_usd, yes_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                int(datetime(2026, 5, 5, 0, 0, 10, tzinfo=UTC).timestamp() * 1000),
                "c1",
                "Bitcoin Up or Down - May 5, 12:00AM-12:05AM ET",
                "2026-05-05T00:01:00+00:00",
                "yes1",
                "no1",
                "BTC",
                5,
                1000,
                0.95,
            ),
            (
                int(datetime(2026, 5, 5, 0, 0, 20, tzinfo=UTC).timestamp() * 1000),
                "c2",
                "Ethereum Up or Down - May 5, 12:00AM-12:15AM ET",
                "2026-05-05T00:01:00+00:00",
                "yes2",
                "no2",
                "ETH",
                15,
                500,
                0.02,
            ),
        ],
    )
    main.executemany(
        """
        INSERT INTO orders (
            order_id, bot_id, condition_id, token_id, side, price, size, status, placed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("o1", "bot_g_prime_live", "c1", "no1", "BUY", 0.05, 100, "MATCHED", "2026-05-05 00:00:15"),
            ("o2", "bot_g_prime_live", "c2", "yes2", "BUY", 0.02, 100, "MATCHED", "2026-05-05 00:00:35"),
        ],
    )
    main.executemany(
        """
        INSERT INTO trades (
            trade_id, bot_id, order_id, condition_id, token_id, side, price,
            size, fee_usd, filled_at, usd_gbp_rate, gbp_notional
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1, 0)
        """,
        [
            ("t1", "bot_g_prime_live", "o1", "c1", "no1", "BUY", 0.05, 100, "2026-05-05 00:00:16"),
            ("t2", "bot_g_prime_live", "o1", "c1", "no1", "SELL", 1.0, 100, "2026-05-05 00:01:01"),
            ("t3", "bot_g_prime_live", "o2", "c2", "yes2", "BUY", 0.02, 100, "2026-05-05 00:00:36"),
            ("t4", "bot_g_prime_live", "o2", "c2", "yes2", "SELL", 0.0, 100, "2026-05-05 00:01:01"),
        ],
    )

    report = build_report(
        main,
        recorder,
        cutoff=cutoff,
        bot_ids=("bot_g_prime_live",),
        max_recorder_lead_seconds=120,
    )

    overall = report["overall_by_bot"]["bot_g_prime_live"]
    assert overall["placed"] == 2
    assert overall["closed"] == 2
    assert overall["wins"] == 1
    assert overall["roi_pct"] > 0
    assert overall["ex_largest_win_roi_pct"] == -100.0
    lead_grid = report["lead_price_grid_by_bot"]["bot_g_prime_live"]
    assert lead_grid["45s-60s|3.5c-5.5c"]["placed"] == 1
    assert lead_grid["<30s|1c-3c"]["placed"] == 1
    assert any(
        row["symbol"] == "BTC" and row["duration_minutes"] == "5"
        for row in report["actual_entry_grid"].values()
    )
    assert report["recorder_snapshot_grid"]
