from __future__ import annotations

import sqlite3

from scripts.bot_d_spike_daily_report import build_report, render_markdown


def test_bot_d_spike_report_summarises_orders_positions_and_pnl(tmp_path):
    db = tmp_path / "main.db"
    con = sqlite3.connect(db)
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
        CREATE TABLE positions (
            id INTEGER PRIMARY KEY,
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            size REAL,
            avg_price REAL,
            cost_basis_usd REAL,
            status TEXT,
            opened_at TEXT,
            closed_at TEXT
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
            filled_at TEXT
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
        """
    )
    con.execute(
        """
        INSERT INTO orders VALUES
        ('paper-1','bot_d_spike','c1','yes1','BUY',0.05,40,'FILLED','2026-05-07 01:00:00')
        """
    )
    con.execute(
        """
        INSERT INTO positions VALUES
        (1,'bot_d_spike','c2','yes2','YES',30,0.05,1.5,'OPEN','2026-05-07 02:00:00',NULL)
        """
    )
    con.executemany(
        "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("buy-1", "bot_d_spike", "paper-1", "c1", "yes1", "BUY", 0.05, 40, 0, "2026-05-07 01:00:00"),
            ("paper-resolve-1", "bot_d_spike", None, "c1", "yes1", "SELL", 1.0, 40, 0, "2026-05-07 12:00:00"),
        ],
    )
    con.execute(
        """
        INSERT INTO events (bot_id,event_type,severity,message,payload,created_at)
        VALUES ('bot_d_spike','bot_d_spike.entry_placed','info','',
                '{"city":"Hong Kong","bucket":"19C","best_ask":"0.05","hours_to_resolution":"8"}',
                '2026-05-07 01:00:00')
        """
    )
    con.commit()
    con.close()

    report = build_report(db)
    assert report["orders"]["total"] == 1
    assert report["positions"]["open"] == 1
    assert report["pnl"]["cumulative"]["closed_positions"] == 1
    assert report["pnl"]["cumulative"]["wins"] == 1
    assert "Bot D-Spike Daily Report" in render_markdown(report)
