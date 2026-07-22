"""SQLite schema for the Bot H Maker V2 recorder DB.

Pattern matches `bots/bot_e_recorder/schema.py`: flat denormalised tables,
WAL mode, raw SQL via `sqlite3`. Analysis queries filter by
`(asset_id, received_at_ms)` or `(condition_id, received_at_ms)`.

Tables:

- `markets` — one row per discovered politics/sports/awards/crypto market
  in the recorder filter. Updated on every gamma scan with the latest
  `last_seen_at_ms` so we can compute coverage gaps.
- `pm_events` — every Polymarket CLOB WSS event for the subscribed
  tokens. The payload is stored as raw JSON so analysis can derive any
  shape of book snapshot, trade observation, or AS label later.
- `heartbeats` — periodic liveness rows so the audit script can detect
  silent stalls.

Phase 1 captures these. Phase 2 derives:

- maker_quotes (quote-engine output)
- maker_paper_fills (when a taker BUY hits our quoted bid)
- maker_as_labels (per-fill toxicity at 5m / 15m / 60m / resolution)

from `pm_events` plus the Phase 2 quote engine's own writes.
"""

from __future__ import annotations

import sqlite3
from contextlib import suppress
from pathlib import Path

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
-- Recorder DB is research data on a UPS-backed VPS; we accept the
-- power-loss-corruption trade-off in exchange for ~5-10x writer drain
-- speed. Same rationale as bots/bot_e_recorder/schema.py.
PRAGMA synchronous=OFF;
PRAGMA busy_timeout=10000;
PRAGMA foreign_keys=ON;

-- ========================================================================
-- Discovered markets in the recorder filter (politics + sports + awards
-- + crypto, 1c-50c, volume >= $1000). Refreshed on every gamma scan.
-- ========================================================================
CREATE TABLE IF NOT EXISTS markets (
    condition_id     TEXT PRIMARY KEY,
    yes_token_id     TEXT NOT NULL,
    no_token_id      TEXT NOT NULL,
    category         TEXT NOT NULL,
    question         TEXT NOT NULL,
    end_date_ts      INTEGER,
    discovered_at_ms INTEGER NOT NULL,
    last_seen_at_ms  INTEGER NOT NULL,
    initial_yes_price REAL,
    volume_24h_usd   REAL,
    status           TEXT NOT NULL DEFAULT 'ACTIVE'
);
CREATE INDEX IF NOT EXISTS ix_markets_category ON markets(category);
CREATE INDEX IF NOT EXISTS ix_markets_status ON markets(status);
CREATE INDEX IF NOT EXISTS ix_markets_yes_token ON markets(yes_token_id);
CREATE INDEX IF NOT EXISTS ix_markets_no_token ON markets(no_token_id);

-- ========================================================================
-- Polymarket CLOB WSS events. Same shape as bot_e_recorder so analysis
-- scripts can be shared.
-- ========================================================================
CREATE TABLE IF NOT EXISTS pm_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at_ms INTEGER NOT NULL,
    subscription_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    asset_id TEXT,
    condition_id TEXT,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pm_events_sub_time
    ON pm_events(subscription_id, received_at_ms);
CREATE INDEX IF NOT EXISTS ix_pm_events_asset_time
    ON pm_events(asset_id, received_at_ms);
CREATE INDEX IF NOT EXISTS ix_pm_events_asset_type_time
    ON pm_events(asset_id, event_type, received_at_ms);
CREATE INDEX IF NOT EXISTS ix_pm_events_condition_time
    ON pm_events(condition_id, received_at_ms);
CREATE INDEX IF NOT EXISTS ix_pm_events_type_time
    ON pm_events(event_type, received_at_ms);

-- ========================================================================
-- Periodic liveness rows so the audit script can detect silent stalls.
-- ========================================================================
CREATE TABLE IF NOT EXISTS heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at_ms INTEGER NOT NULL,
    subscription_id TEXT NOT NULL,
    asset_id_count INTEGER NOT NULL,
    note TEXT
);
CREATE INDEX IF NOT EXISTS ix_heartbeats_sub_time
    ON heartbeats(subscription_id, received_at_ms);
"""


# Resolution-related columns on `markets`. Added in Session 260 (ADR-134
# Phase 1 follow-on) so the replay simulator can compute realised PnL
# instead of returning INSUFFICIENT_DATA. SQLite doesn't support
# `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, so we introspect the
# `markets` schema and add only the missing columns.
_RESOLUTION_COLUMNS = (
    ("yes_won", "INTEGER"),  # NULL=unresolved, 0=NO won, 1=YES won
    ("resolved_at_ms", "INTEGER"),  # local UTC ms when we observed the resolution
    ("outcome_yes_price", "REAL"),  # final YES price (0.0 / 1.0 / 0.5 for void)
    ("last_resolution_check_ms", "INTEGER"),  # for backoff / throttling
)


def _ensure_resolution_columns(conn: sqlite3.Connection) -> list[str]:
    """Add resolution columns to `markets` if missing. Idempotent.

    Returns the list of columns that were added in this call (empty if
    the schema was already up to date)."""
    rows = conn.execute("PRAGMA table_info(markets)").fetchall()
    existing = {r[1] for r in rows}  # PRAGMA returns (cid, name, type, ...)
    added: list[str] = []
    for name, sql_type in _RESOLUTION_COLUMNS:
        if name in existing:
            continue
        conn.execute(f"ALTER TABLE markets ADD COLUMN {name} {sql_type}")
        added.append(name)
    if "ix_markets_yes_won" not in {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    }:
        with suppress(sqlite3.OperationalError):
            conn.execute("CREATE INDEX IF NOT EXISTS ix_markets_yes_won ON markets(yes_won)")
    return added


def init_db(path: Path) -> sqlite3.Connection:
    """Open or create the recorder DB and run the schema. Returns a
    long-lived connection the writer task uses."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    with suppress(sqlite3.OperationalError):
        conn.executescript(SCHEMA_SQL)
    _ensure_resolution_columns(conn)
    return conn
