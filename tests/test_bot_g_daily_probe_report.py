from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from scripts.bot_g_daily_probe_report import build_report, render_markdown


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
        CREATE TABLE cex_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at_ms INTEGER,
            trade_time_ms INTEGER,
            symbol TEXT,
            price REAL,
            size REAL,
            is_buyer_maker INTEGER
        );
        """
    )
    return con


def test_daily_probe_groups_live_by_watch_buckets():
    main = _main_db()
    recorder = _recorder_db()
    cutoff = datetime(2026, 5, 7, 0, 0, tzinfo=UTC)

    recorder.execute(
        """
        INSERT INTO markets (
            scan_at_ms, condition_id, question, end_date_iso, yes_token_id,
            no_token_id, symbol, duration_minutes, volume_24h_usd, yes_price
        ) VALUES (?, 'c1', 'Solana Up or Down', '2026-05-07T00:01:00+00:00',
                  'yes1', 'no1', 'SOL', 15, 100, 0.95)
        """,
        (int(datetime(2026, 5, 7, 0, 0, 1, tzinfo=UTC).timestamp() * 1000),),
    )
    main.execute(
        """
        INSERT INTO orders (
            order_id, bot_id, condition_id, token_id, side, price, size, status, placed_at
        ) VALUES ('o1', 'bot_g_prime_live', 'c1', 'no1', 'BUY', 0.04, 100, 'MATCHED',
                  '2026-05-07 00:00:30')
        """
    )
    main.execute(
        """
        INSERT INTO events (bot_id, event_type, severity, message, payload, created_at)
        VALUES (
            'bot_g_prime_live',
            'bot_g.entry_placed',
            'info',
            '',
            '{"order_id":"o1","side_token":"NO","fresh_t_to_res_sec":30,"observed_ask_price":0.04}',
            '2026-05-07 00:00:30'
        )
        """
    )
    main.executemany(
        """
        INSERT INTO trades (
            trade_id, bot_id, order_id, condition_id, token_id, side, price,
            size, fee_usd, filled_at, usd_gbp_rate, gbp_notional
        ) VALUES (?, 'bot_g_prime_live', ?, 'c1', 'no1', ?, ?, 100, 0, ?, 1, 0)
        """,
        [
            ("buy-o1", "o1", "BUY", 0.04, "2026-05-07 00:00:31"),
            ("sell-o1", "", "SELL", 1.0, "2026-05-07 00:01:01"),
        ],
    )
    recorder.executemany(
        """
        INSERT INTO cex_trades (
            received_at_ms, trade_time_ms, symbol, price, size, is_buyer_maker
        ) VALUES (?, ?, 'SOLUSDT', ?, 1, 0)
        """,
        [
            (1_000, 1_000, 100.0),
            (30_000, 30_000, 99.99),
        ],
    )

    report = build_report(
        main,
        recorder,
        bot_ids=("bot_g_prime_live",),
        cutoff=cutoff,
    )

    overall = report["overall_by_bot"][0]
    assert overall["orders"] == 1
    assert overall["won"] == 1
    assert report["by_live_symbol_side"][0]["symbol"] == "SOL"
    assert report["by_live_price_sub_band"][0]["price_sub_band"] == "3.5c-4.5c"
    assert report["by_live_price_point"][0]["price_point_bucket"] == "4c-5c"
    assert report["sub8_winners"][0]["price_point"] == "4c-5c"
    assert report["sub8_winners"][0]["symbol"] == "SOL"
    assert report["sub8_winners"][0]["pnl_usd"] == 96.0
    assert report["by_sub8_symbol_price_point"][0]["price_point_bucket"] == "4c-5c"
    assert report["markov_live_microstates"]["posture"] == "research_only_no_live_gate"
    assert report["markov_live_microstates"]["n_rows"] == 1
    assert report["markov_live_microstates"]["top_states"][0]["orders"] == 1
    assert any(
        row["watch_bucket"] == "SOL / SOL-NO"
        and row["orders"] == 1
        for row in report["by_live_watch_bucket"]
    )

    markdown = render_markdown(report)
    assert "Bot G Daily Probe Report" in markdown
    assert "Live Watch Buckets" in markdown
    assert "3.5c-4.5c" in markdown
    assert "Sub-8c Winner Tape" in markdown
    assert "4c-5c" in markdown
    assert "Live Markov Microstates" in markdown
