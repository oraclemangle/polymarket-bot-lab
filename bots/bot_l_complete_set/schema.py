"""SQLite schema for Bot L complete-set paper evidence.

Bot L is paper/research only. It reads the shared crypto recorder DB and
writes simulated complete-set opportunities into its own DB. It does not
create CLOB clients, read wallet keys, or place live orders.
"""

from __future__ import annotations

import sqlite3
from contextlib import suppress
from pathlib import Path

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=10000;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS bot_l_complete_set_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_event_id INTEGER NOT NULL,
    detected_at_ms INTEGER NOT NULL,
    condition_id TEXT NOT NULL,
    question TEXT,
    symbol TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    signal_type TEXT NOT NULL,
    yes_token_id TEXT NOT NULL,
    no_token_id TEXT NOT NULL,
    yes_price REAL NOT NULL,
    no_price REAL NOT NULL,
    raw_sum REAL NOT NULL,
    adjusted_sum REAL NOT NULL,
    yes_size REAL,
    no_size REAL,
    simulated_cost_usd REAL NOT NULL,
    simulated_return_usd REAL NOT NULL,
    simulated_pnl_usd REAL NOT NULL,
    simulated_roi REAL NOT NULL,
    executable INTEGER NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_bot_l_signal_event_type
    ON bot_l_complete_set_signals(recorder_event_id, signal_type);
CREATE INDEX IF NOT EXISTS ix_bot_l_signals_condition_time
    ON bot_l_complete_set_signals(condition_id, detected_at_ms);
CREATE INDEX IF NOT EXISTS ix_bot_l_signals_type_time
    ON bot_l_complete_set_signals(signal_type, detected_at_ms);

CREATE TABLE IF NOT EXISTS bot_l_complete_set_run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    recorder_db_path TEXT NOT NULL,
    source_events_seen INTEGER NOT NULL,
    signals_written INTEGER NOT NULL,
    last_recorder_event_id INTEGER NOT NULL,
    config_json TEXT NOT NULL
);
"""


def init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    with suppress(sqlite3.OperationalError):
        conn.executescript(SCHEMA_SQL)
    return conn
