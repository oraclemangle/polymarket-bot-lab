"""Wallet observer SQLite schema.

Separate DB at `data/wallet_observer.db` (per Bot E recorder pattern):
- Schema can evolve without Alembic migrations on the main DB.
- Event-capture writes don't contend with main strategy services.
- DB is rsync-able to a dev machine for analysis without disrupting bots.

Tables:
  wallet_observed_fills  — every CTF Exchange OrderFilled where maker
                           or taker is in our 245-wallet whitelist
  wallet_market_tokens   — token_id -> condition_id/outcome mapping
  wallet_market_resolutions — market settlement labels by condition_id
  observer_runs          — service start/stop heartbeats for liveness
  collector_state        — last processed block per (chain, exchange)
"""
from __future__ import annotations

import sqlite3
from contextlib import suppress
from pathlib import Path

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=10000;
PRAGMA foreign_keys=ON;

-- Each observed fill is recorded with both the on-chain transaction
-- coordinates (block_number + log_index uniquely identifies it) and a
-- decoded view of the fill semantics.
CREATE TABLE IF NOT EXISTS wallet_observed_fills (
    -- on-chain coordinates
    tx_hash             TEXT NOT NULL,
    log_index           INTEGER NOT NULL,
    block_number        INTEGER NOT NULL,
    block_ts            INTEGER NOT NULL,           -- unix epoch (UTC)
    exchange            TEXT NOT NULL,              -- 'CTF' | 'NegRiskCTF'

    -- V2 OrderFilled decoded fields
    order_hash          TEXT NOT NULL,
    maker_address       TEXT NOT NULL,              -- lowercase 0x...
    taker_address       TEXT NOT NULL,
    side_raw            INTEGER NOT NULL,           -- 0=BUY, 1=SELL (maker POV)
    token_id            TEXT NOT NULL,              -- the share token, decimal string
    maker_amount_filled TEXT NOT NULL,              -- decimal string (6-decimal raw)
    taker_amount_filled TEXT NOT NULL,
    fee_raw             TEXT NOT NULL,
    builder_code        TEXT,                       -- bytes32 hex (0x-prefixed)
    metadata            TEXT,                       -- bytes32 hex

    -- our derived fields
    observed_address    TEXT NOT NULL,              -- which of maker/taker matched whitelist
    observed_role       TEXT NOT NULL,              -- 'maker' | 'taker'
    tier                TEXT NOT NULL,
    user_name           TEXT,
    pv_rank             INTEGER,
    side                TEXT,                       -- 'BUY' | 'SELL' (from observed wallet's POV)
    price               REAL,                       -- USDC per share, 0..1
    size_shares         REAL,                       -- 6-decimal-adjusted

    inserted_at         INTEGER NOT NULL,

    PRIMARY KEY (tx_hash, log_index)
);

CREATE INDEX IF NOT EXISTS idx_obsfills_observed
    ON wallet_observed_fills (observed_address, block_ts);
CREATE INDEX IF NOT EXISTS idx_obsfills_block
    ON wallet_observed_fills (block_number);
CREATE INDEX IF NOT EXISTS idx_obsfills_tier_ts
    ON wallet_observed_fills (tier, block_ts);
CREATE INDEX IF NOT EXISTS idx_obsfills_token_ts
    ON wallet_observed_fills (token_id, block_ts);

-- Token -> market mapping fetched from Gamma. The collector only sees
-- CTF token_id in OrderFilled logs; this table supplies the settlement join.
CREATE TABLE IF NOT EXISTS wallet_market_tokens (
    token_id          TEXT PRIMARY KEY,
    condition_id      TEXT NOT NULL,
    outcome           TEXT,
    outcome_index     INTEGER,
    gamma_market_id   TEXT,
    question          TEXT,
    event_title       TEXT,
    end_date_iso      TEXT,
    payload           TEXT,
    updated_at        INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wallet_market_tokens_condition
    ON wallet_market_tokens (condition_id);

-- Resolution labels keyed by condition_id. `winning_outcome_index` is
-- used instead of a YES-only label so non-YES/NO binaries join correctly.
CREATE TABLE IF NOT EXISTS wallet_market_resolutions (
    condition_id          TEXT PRIMARY KEY,
    gamma_market_id       TEXT,
    question              TEXT,
    event_title           TEXT,
    end_date_iso          TEXT,
    closed                INTEGER NOT NULL DEFAULT 0,
    settled               INTEGER NOT NULL DEFAULT 0,
    proxy_settled         INTEGER NOT NULL DEFAULT 0,
    settlement_method     TEXT,
    winning_outcome_index INTEGER,
    outcome_prices        TEXT,
    payload               TEXT,
    updated_at            INTEGER NOT NULL
);

-- Track service runs for liveness and audit.
CREATE TABLE IF NOT EXISTS observer_runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  INTEGER NOT NULL,
    stopped_at  INTEGER,
    last_block  INTEGER,
    n_fills     INTEGER NOT NULL DEFAULT 0,
    n_polls     INTEGER NOT NULL DEFAULT 0,
    note        TEXT
);

-- Collector progress per (chain, exchange).
CREATE TABLE IF NOT EXISTS collector_state (
    chain         TEXT NOT NULL,                    -- 'polygon'
    exchange      TEXT NOT NULL,                    -- 'CTF' | 'NegRiskCTF'
    last_block    INTEGER NOT NULL,
    last_updated  INTEGER NOT NULL,
    PRIMARY KEY (chain, exchange)
);
"""


SETTLEMENT_SCHEMA_SQL = """
CREATE INDEX IF NOT EXISTS idx_obsfills_token_ts
    ON wallet_observed_fills (token_id, block_ts);

CREATE TABLE IF NOT EXISTS wallet_market_tokens (
    token_id          TEXT PRIMARY KEY,
    condition_id      TEXT NOT NULL,
    outcome           TEXT,
    outcome_index     INTEGER,
    gamma_market_id   TEXT,
    question          TEXT,
    event_title       TEXT,
    end_date_iso      TEXT,
    payload           TEXT,
    updated_at        INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wallet_market_tokens_condition
    ON wallet_market_tokens (condition_id);

CREATE TABLE IF NOT EXISTS wallet_market_resolutions (
    condition_id          TEXT PRIMARY KEY,
    gamma_market_id       TEXT,
    question              TEXT,
    event_title           TEXT,
    end_date_iso          TEXT,
    closed                INTEGER NOT NULL DEFAULT 0,
    settled               INTEGER NOT NULL DEFAULT 0,
    proxy_settled         INTEGER NOT NULL DEFAULT 0,
    settlement_method     TEXT,
    winning_outcome_index INTEGER,
    outcome_prices        TEXT,
    payload               TEXT,
    updated_at            INTEGER NOT NULL
);
"""


def init_db(path: Path | str) -> sqlite3.Connection:
    """Initialize schema (idempotent). Returns a connection in WAL mode."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, timeout=10, isolation_level=None)
    con.executescript(SCHEMA_SQL)
    return con


def ensure_settlement_schema(con: sqlite3.Connection) -> None:
    """Ensure settlement-join helper tables exist on an older observer DB."""
    con.executescript(SETTLEMENT_SCHEMA_SQL)


def open_db(path: Path | str) -> sqlite3.Connection:
    """Open existing DB without re-running DDL.

    Caller is responsible for prior init. Useful for read-only consumers
    (daily report, dashboard).
    """
    return sqlite3.connect(path, timeout=10, isolation_level=None)


def close_quiet(con: sqlite3.Connection | None) -> None:
    if con is None:
        return
    with suppress(Exception):
        con.close()
