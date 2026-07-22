from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


def test_fleet_tradeflow_report_summarises_orders_trades_events(tmp_path):
    from scripts.fleet_tradeflow_report import run_report

    db = tmp_path / "main.db"
    now = datetime.now(UTC).isoformat()
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "CREATE TABLE orders (bot_id TEXT, status TEXT, price NUMERIC, "
            "size NUMERIC, placed_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE trades (bot_id TEXT, price NUMERIC, size NUMERIC, "
            "filled_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE events (bot_id TEXT, event_type TEXT, severity TEXT, "
            "message TEXT, created_at TEXT)"
        )
        conn.execute(
            "CREATE TABLE halt_flags (bot_id TEXT, halted INTEGER, reason TEXT, set_at TEXT)"
        )
        conn.execute("INSERT INTO orders VALUES ('bot_e', 'CANCELLED', 0.5, 10, ?)", (now,))
        conn.execute("INSERT INTO trades VALUES ('bot_f_mirror', 0.2, 5, ?)", (now,))
        conn.execute(
            "INSERT INTO events VALUES ('bot_d', 'bot_d.nws_veto', 'info', '', ?)",
            (now,),
        )
        conn.execute(
            "INSERT INTO events VALUES ('bot_e', 'watchdog.halt', 'kill', 'halted', ?)",
            (now,),
        )
        conn.execute("INSERT INTO halt_flags VALUES ('bot_e', 1, 'watchdog: test', ?)", (now,))
        conn.commit()
    finally:
        conn.close()

    report = run_report(db, lookback_hours=1)

    assert report["orders"][0]["bot_id"] == "bot_e"
    assert report["orders"][0]["n"] == 1
    assert report["trades"][0]["bot_id"] == "bot_f_mirror"
    assert report["trades"][0]["fills"] == 1
    assert report["events"][0]["event_type"] == "bot_d.nws_veto"
    assert report["halt_flags"][0]["bot_id"] == "bot_e"
    assert report["recent_watchdog"][0]["event_type"] == "watchdog.halt"
