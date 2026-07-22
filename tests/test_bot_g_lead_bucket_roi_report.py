from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from scripts.bot_g_lead_bucket_roi_report import (
    build_report,
    limit_price_bucket,
    report_lead_bucket,
    wilson_interval,
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
            scan_at_ms INTEGER,
            condition_id TEXT,
            question TEXT,
            end_date_iso TEXT,
            yes_token_id TEXT,
            no_token_id TEXT,
            symbol TEXT,
            duration_minutes INTEGER,
            volume_24h_usd REAL,
            yes_price REAL
        );
        """
    )
    return con


def test_limit_price_bucket_boundaries():
    assert limit_price_bucket(0.024) == "1c-2.5c"
    assert limit_price_bucket(0.025) == "2.5c-3.5c"
    assert limit_price_bucket(0.045) == "4.5c-5.5c"
    assert limit_price_bucket(0.08) == "6.5c-8c"
    assert limit_price_bucket(0.081) == ">8c"


def test_report_lead_bucket_uses_exclusive_upper_bounds():
    assert report_lead_bucket(29.99) == "<30s"
    assert report_lead_bucket(30) == "30s-45s"
    assert report_lead_bucket(44.99) == "30s-45s"
    assert report_lead_bucket(45) == "45s-60s"
    assert report_lead_bucket(60) == ">=60s"


def test_wilson_interval_returns_percent_ready_bounds():
    lo, hi = wilson_interval(1, 10)
    assert lo is not None and hi is not None
    assert 0 < lo < hi < 1


def test_build_report_groups_live_and_paper_rows():
    main = _main_db()
    recorder = _recorder_db()
    cutoff = datetime(2026, 5, 5, tzinfo=UTC)
    recorder.executemany(
        """
        INSERT INTO markets (
            scan_at_ms, condition_id, question, end_date_iso, yes_token_id,
            no_token_id, symbol, duration_minutes, volume_24h_usd, yes_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (1, "c1", "Bitcoin Up or Down", "2026-05-05T00:01:00+00:00", "yes1", "no1", "BTC", 5, 100, 0.95),
            (2, "c2", "Ethereum Up or Down", "2026-05-05T00:01:00+00:00", "yes2", "no2", "ETH", 15, 100, 0.95),
        ],
    )
    main.executemany(
        """
        INSERT INTO orders (
            order_id, bot_id, condition_id, token_id, side, price, size, status, placed_at
        ) VALUES (?, ?, ?, ?, 'BUY', ?, ?, ?, ?)
        """,
        [
            ("live-win", "bot_g_prime_live", "c1", "no1", 0.045, 100, "MATCHED", "2026-05-05 00:00:20"),
            ("paper-loss", "bot_g_prime", "c2", "no2", 0.06, 100, "PAPER_OPEN", "2026-05-05 00:00:40"),
            ("paper-nofill", "bot_g_prime", "c2", "no2", 0.06, 100, "EXCHANGE_CLOSED", "2026-05-05 00:00:45"),
        ],
    )
    main.executemany(
        """
        INSERT INTO events (bot_id, event_type, severity, message, payload, created_at)
        VALUES (?, 'bot_g.entry_placed', 'info', '', ?, ?)
        """,
        [
            ("bot_g_prime_live", '{"order_id":"live-win","side_token":"NO","execution_mode":"live","fresh_t_to_res_sec":40}', "2026-05-05 00:00:20"),
            ("bot_g_prime", '{"order_id":"paper-loss","side_token":"NO","execution_mode":"paper","fresh_t_to_res_sec":20}', "2026-05-05 00:00:40"),
            ("bot_g_prime", '{"order_id":"paper-nofill","side_token":"NO","execution_mode":"paper","fresh_t_to_res_sec":15}', "2026-05-05 00:00:45"),
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
            ("t1", "bot_g_prime_live", "live-win", "c1", "no1", "BUY", 0.045, 100, "2026-05-05 00:00:21"),
            ("t2", "bot_g_prime_live", "", "c1", "no1", "SELL", 1.0, 100, "2026-05-05 00:01:01"),
            ("t3", "bot_g_prime", "paper-loss", "c2", "no2", "BUY", 0.06, 100, "2026-05-05 00:00:41"),
            ("t4", "bot_g_prime", "", "c2", "no2", "SELL", 0.0, 100, "2026-05-05 00:01:01"),
        ],
    )

    report = build_report(
        main,
        recorder,
        cutoff=cutoff,
        bot_ids=("bot_g_prime_live", "bot_g_prime"),
    )

    assert report["overall"]["bot_g_prime_live"]["won"] == 1
    assert report["overall"]["bot_g_prime"]["n_orders"] == 2
    assert any(row["side_token"] == "NO" for row in report["groups"].values())
