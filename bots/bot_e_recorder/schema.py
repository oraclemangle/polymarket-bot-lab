"""Crypto recorder — SQLite schema for captured events.

Separate from the main `core/db.py` schema so:
- Schema can evolve without Alembic migrations on the main DB.
- Capture volume (~5-50 events/sec peak) does not slow main-DB writes.
- DB can be rsynced off the capture host to a dev machine for analysis.

Tables:
  pm_events       — raw Polymarket CLOB WSS messages, typed
  cex_trades      — raw CEX (Binance) trade ticks
  markets         — Gamma market metadata snapshots (one row per (market, snapshot_time))
  heartbeats      — periodic liveness rows from each subscription
  gaps            — detected gaps (computed post-hoc by audit.py)

Schema is flat and denormalised. Analysis scripts filter by (subscription, ts).
The historical module path remains ``bots.bot_e_recorder`` because the recorder
started as Bot E0, but the data asset is now the shared crypto recorder for
Bot G / Longshot Prime research.
"""
import sqlite3
from contextlib import suppress
from pathlib import Path

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
-- Session 39 / OQ-056 (2026-04-26): dropped from NORMAL to OFF to skip
-- the per-commit fsync. Under WAL+NORMAL on a 16+ GB ZFS/lz4 DB, each
-- commit's fsync was slow enough that sustained PM event load (~110/s)
-- outpaced the writer's drain rate (~100/s under one fsync per ~2 s
-- flush). Result: write_queue saturated at the 50,000-slot cap every
-- 56-99 minutes, dropping heartbeats and triggering the external
-- recorder.freshness watchdog. With synchronous=OFF the writer drains
-- ~5-10x faster; the recovered headroom is several multiples of
-- sustained input rate.
--
-- Trade-off: power-loss or kernel-panic during a commit can corrupt
-- the WAL or leave torn writes. The recorder DB is research/
-- calibration data on a UPS-backed homelab on a redundant ZFS pool;
-- corruption risk is acceptable, and the data is replaceable by
-- re-recording from the upstream feeds. The trade does NOT apply to
-- ``data/main.db`` (trades, positions, halt flags, events) — that DB
-- is governed separately in core/db.py and remains at its default
-- safer mode.
PRAGMA synchronous=OFF;
PRAGMA busy_timeout=10000;
PRAGMA foreign_keys=ON;

-- ========================================================================
-- Polymarket CLOB WSS events (book, price_change, last_trade_price,
-- best_bid_ask, reconnect, disconnect, heartbeat).
-- ========================================================================
CREATE TABLE IF NOT EXISTS pm_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at_ms INTEGER NOT NULL,   -- local UTC ms at receipt
    subscription_id TEXT NOT NULL,     -- e.g. "btc-2026-04-17-12:15"
    event_type TEXT NOT NULL,          -- "book" | "price_change" | ...
    asset_id TEXT,                     -- token_id (YES or NO) if present
    condition_id TEXT,                 -- parent market if resolvable
    payload_json TEXT NOT NULL         -- raw event body as JSON
);
CREATE INDEX IF NOT EXISTS ix_pm_events_sub_time
    ON pm_events(subscription_id, received_at_ms);
CREATE INDEX IF NOT EXISTS ix_pm_events_asset_time
    ON pm_events(asset_id, received_at_ms);
CREATE INDEX IF NOT EXISTS ix_pm_events_asset_type_time
    ON pm_events(asset_id, event_type, received_at_ms);
CREATE INDEX IF NOT EXISTS ix_pm_events_type_time
    ON pm_events(event_type, received_at_ms);

-- ========================================================================
-- CEX (Binance) trade ticks for reference price.
-- ========================================================================
CREATE TABLE IF NOT EXISTS cex_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at_ms INTEGER NOT NULL,   -- local UTC ms at receipt
    trade_time_ms INTEGER NOT NULL,    -- exchange timestamp
    symbol TEXT NOT NULL,              -- "BTCUSDT" etc.
    price REAL NOT NULL,
    size REAL NOT NULL,
    is_buyer_maker INTEGER NOT NULL    -- 1/0
);
CREATE INDEX IF NOT EXISTS ix_cex_trades_symbol_time
    ON cex_trades(symbol, received_at_ms);
CREATE INDEX IF NOT EXISTS ix_cex_trades_symbol_trade_time
    ON cex_trades(symbol, trade_time_ms);

-- ========================================================================
-- Market metadata snapshots — one row per (condition_id, scan_at).
-- Minimal fields needed for (a) subscription discovery, (b) post-hoc
-- time-to-resolution bucketing.
-- ========================================================================
CREATE TABLE IF NOT EXISTS markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_at_ms INTEGER NOT NULL,
    condition_id TEXT NOT NULL,
    question TEXT NOT NULL,
    end_date_iso TEXT,                 -- Gamma endDate, ISO 8601
    yes_token_id TEXT,
    no_token_id TEXT,
    symbol TEXT,                       -- BTC/ETH/SOL/XRP/DOGE for Bot G replay
    duration_minutes INTEGER,          -- 5 or 15 when inferable from question
    volume_24h_usd REAL,
    yes_price REAL,
    category TEXT DEFAULT 'crypto',
    raw_json TEXT                      -- full Gamma row for debugging
);
CREATE INDEX IF NOT EXISTS ix_markets_condition_scan
    ON markets(condition_id, scan_at_ms);
CREATE INDEX IF NOT EXISTS ix_markets_scan_time
    ON markets(scan_at_ms);

-- ========================================================================
-- Heartbeats: every N seconds, we insert a row per active subscription so
-- analysis can detect silent stalls as "no heartbeat for X sec" windows.
-- ========================================================================
CREATE TABLE IF NOT EXISTS heartbeats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emitted_at_ms INTEGER NOT NULL,
    source TEXT NOT NULL,              -- "pm", "cex", "discovery"
    subscription_id TEXT,              -- optional: specific subscription
    last_message_age_sec REAL,         -- seconds since last message on this source
    metadata_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_heartbeats_source_time
    ON heartbeats(source, emitted_at_ms);

-- ========================================================================
-- Gaps: populated by audit.py post-capture. A gap is a stretch of time
-- where a subscription had no events AND no heartbeat (indicating a
-- silent WSS freeze, not just a quiet market).
-- ========================================================================
CREATE TABLE IF NOT EXISTS gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    subscription_id TEXT,
    gap_start_ms INTEGER NOT NULL,
    gap_end_ms INTEGER NOT NULL,
    duration_sec REAL NOT NULL,
    detected_at_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_gaps_source_start
    ON gaps(source, gap_start_ms);

-- Schema version stamp.
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version (version) VALUES (1);
"""


def _ensure_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    ddl: str,
) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create the recorder DB if it doesn't exist, return a connection.

    U-07 follow-up (Session 17n, 2026-04-19): `check_same_thread=False` is
    required because `writer_loop` now dispatches `_flush_batch` onto
    `asyncio.to_thread` (Session 17k U-07 async-offload fix). Without this,
    every flush raised `SQLite objects created in a thread can only be
    used in that same thread`, dropping 200+ events per batch. The WAL
    journal mode below already provides per-connection write serialisation
    inside SQLite itself, so the only thing missing was the API-level
    cross-thread guard.

    Session 39 / OQ-055 (2026-04-26): WAL is checkpointed (TRUNCATE) on
    init so each process start begins with an empty WAL, preventing
    inheritance of unbounded WAL growth from prior crashed runs. Symptom
    fixed: writer_stall_abort cycles where successive auto-restarts
    inherited an ever-growing WAL until checkpoint pressure caused the
    next stall in 2 minutes instead of 110.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0, check_same_thread=False)
    conn.executescript(SCHEMA_SQL)
    _ensure_column(conn, "markets", "symbol", "TEXT")
    _ensure_column(conn, "markets", "duration_minutes", "INTEGER")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_markets_symbol_end_scan "
        "ON markets(symbol, end_date_iso, scan_at_ms)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_markets_duration_scan "
        "ON markets(duration_minutes, scan_at_ms)"
    )
    conn.commit()
    # Force a WAL checkpoint so we don't inherit a multi-MB WAL from a
    # crashed prior run. TRUNCATE resets the WAL file size to zero on
    # success, restoring clean state. Returns (busy, log_pages,
    # checkpointed_pages) — non-zero busy means another connection
    # held the DB; we tolerate that and continue (the next auto
    # checkpoint will catch up).
    with suppress(sqlite3.OperationalError):
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    return conn
