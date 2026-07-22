from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.vps_node_status import _bot_g_summary, _bot_l_complete_set_summary


def test_bot_g_summary_exports_realised_pnl_and_entry_cost(tmp_path: Path) -> None:
    db = tmp_path / "bot_g_vps_main.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE orders (
            order_id TEXT,
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            status TEXT,
            placed_at TEXT,
            last_updated TEXT
        );
        CREATE TABLE trades (
            bot_id TEXT,
            trade_id TEXT,
            order_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            fee_usd REAL,
            filled_at TEXT
        );
        CREATE TABLE positions (
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            size REAL,
            avg_price REAL,
            cost_basis_usd REAL,
            status TEXT,
            opened_at TEXT
        );
        CREATE TABLE events (
            bot_id TEXT,
            event_type TEXT,
            created_at TEXT,
            payload TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("paper-entry-win", "bot_g_prime", "cond-a", "tok-a", "BUY", 0.04, 100, "FILLED", "2026-05-08 10:00:00", "2026-05-08 10:00:01"),
            ("paper-entry-loss", "bot_g_prime", "cond-b", "tok-b", "BUY", 0.05, 100, "FILLED", "2026-05-08 10:05:00", "2026-05-08 10:05:01"),
        ],
    )
    conn.executemany(
        "INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("bot_g_prime", "paper-fill-win", "paper-entry-win", "cond-a", "tok-a", "BUY", 0.04, 100, 0, "2026-05-08 10:00:01"),
            ("bot_g_prime", "paper-resolve-win", None, "cond-a", "tok-a", "SELL", 1.0, 100, 0, "2026-05-08 10:10:00"),
            ("bot_g_prime", "paper-fill-loss", "paper-entry-loss", "cond-b", "tok-b", "BUY", 0.05, 100, 0, "2026-05-08 10:05:01"),
            ("bot_g_prime", "paper-resolve-loss", None, "cond-b", "tok-b", "SELL", 0.0, 100, 0, "2026-05-08 10:15:00"),
        ],
    )
    conn.commit()
    conn.close()

    summary = _bot_g_summary(db, bot_ids=("bot_g_prime",))

    metrics = summary["trade_metrics"]["bot_g_prime"]
    assert metrics["entry_cost_usd"] == 9.0
    assert metrics["closed_trades"] == 2
    assert metrics["wins"] == 1
    assert metrics["win_rate_pct"] == 50.0
    assert metrics["realised_pnl_usd"] == 91.0


def test_bot_l_complete_set_summary_exports_signal_counts(tmp_path: Path) -> None:
    db = tmp_path / "bot_l_complete_set_paper.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE bot_l_complete_set_signals (
            signal_type TEXT,
            condition_id TEXT,
            simulated_pnl_usd REAL,
            simulated_cost_usd REAL,
            adjusted_sum REAL,
            executable INTEGER
        );
        CREATE TABLE bot_l_complete_set_run_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finished_at TEXT
        );
        INSERT INTO bot_l_complete_set_signals VALUES
            ('BUY_COMPLETE_SET', 'cond-1', 0.02, 1.0, 0.98, 1),
            ('BUY_COMPLETE_SET', 'cond-2', 0.01, 1.0, 0.99, 0),
            ('SELL_COMPLETE_SET', 'cond-2', 0.03, 1.0, 1.03, 1);
        INSERT INTO bot_l_complete_set_run_log (finished_at)
        VALUES ('2026-05-13T18:00:00+00:00');
        """
    )
    conn.commit()
    conn.close()

    summary = _bot_l_complete_set_summary(db)

    assert summary["signals"] == 3
    assert summary["executable_signals"] == 2
    assert summary["markets"] == 2
    assert summary["pnl_usd"] == 0.06
    assert summary["executable_pnl_usd"] == 0.05
    assert summary["buy_executable_pnl_usd"] == 0.02
    assert summary["sell_executable_pnl_usd"] == 0.03
    assert summary["buy_executable_signals"] == 1
    assert summary["sell_executable_signals"] == 1
    assert summary["executable_pnl_by_side"] == {"buy": 0.02, "sell": 0.03}
    assert summary["by_type"]["BUY_COMPLETE_SET"]["signals"] == 2
    assert summary["by_type"]["BUY_COMPLETE_SET"]["executable_pnl_usd"] == 0.02
    assert summary["by_type"]["SELL_COMPLETE_SET"]["executable_pnl_usd"] == 0.03
    assert summary["last_run"] == "2026-05-13T18:00:00+00:00"
