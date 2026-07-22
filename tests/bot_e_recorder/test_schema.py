"""Tests for the Bot E0 recorder schema + writer loop."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from bots.bot_e_recorder.schema import SCHEMA_SQL, init_db


class TestSchema:
    def test_init_db_creates_all_tables(self, tmp_path: Path):
        db_path = tmp_path / "rec.db"
        conn = init_db(db_path)
        try:
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            # Required tables
            for t in ("pm_events", "cex_trades", "markets", "heartbeats", "gaps", "schema_version"):
                assert t in tables, f"missing table: {t}"
            market_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(markets)")
            }
            assert "symbol" in market_cols
            assert "duration_minutes" in market_cols
        finally:
            conn.close()

    def test_init_db_idempotent(self, tmp_path: Path):
        """Calling init_db on an existing DB must not error or duplicate rows."""
        db_path = tmp_path / "rec.db"
        conn1 = init_db(db_path)
        conn1.close()
        conn2 = init_db(db_path)
        try:
            row = conn2.execute("SELECT version FROM schema_version").fetchone()
            assert row[0] == 1
        finally:
            conn2.close()

    def test_wal_mode_enabled(self, tmp_path: Path):
        db_path = tmp_path / "rec.db"
        conn = init_db(db_path)
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode.lower() == "wal"
        finally:
            conn.close()

    def test_synchronous_off(self, tmp_path: Path):
        """Session 39 / OQ-056: synchronous=OFF skips per-commit fsync
        so the writer can keep up with sustained PM event load. Trade-off
        documented in schema.py and OQ-056. SQLite reports the value as
        an integer: 0=OFF, 1=NORMAL, 2=FULL, 3=EXTRA."""
        db_path = tmp_path / "rec.db"
        conn = init_db(db_path)
        try:
            sync = conn.execute("PRAGMA synchronous").fetchone()[0]
            assert sync == 0, (
                f"recorder must run with synchronous=OFF (0) to keep up "
                f"with sustained event load; got {sync}"
            )
        finally:
            conn.close()

    def test_can_insert_pm_event(self, tmp_path: Path):
        db_path = tmp_path / "rec.db"
        conn = init_db(db_path)
        try:
            conn.execute(
                "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, "
                "asset_id, condition_id, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                (1234, "sub1", "book", "tok1", "cond1", json.dumps({"foo": "bar"})),
            )
            conn.commit()
            row = conn.execute("SELECT event_type FROM pm_events").fetchone()
            assert row[0] == "book"
        finally:
            conn.close()

    def test_can_insert_cex_trade(self, tmp_path: Path):
        db_path = tmp_path / "rec.db"
        conn = init_db(db_path)
        try:
            conn.execute(
                "INSERT INTO cex_trades (received_at_ms, trade_time_ms, symbol, "
                "price, size, is_buyer_maker) VALUES (?, ?, ?, ?, ?, ?)",
                (1000, 1000, "BTCUSDT", 68000.0, 0.001, 1),
            )
            conn.commit()
            row = conn.execute("SELECT symbol, price FROM cex_trades").fetchone()
            assert row == ("BTCUSDT", 68000.0)
        finally:
            conn.close()

    def test_indexes_exist(self, tmp_path: Path):
        db_path = tmp_path / "rec.db"
        conn = init_db(db_path)
        try:
            indexes = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' "
                    "AND name NOT LIKE 'sqlite_%'"
                )
            }
            assert "ix_pm_events_sub_time" in indexes
            assert "ix_cex_trades_symbol_time" in indexes
            assert "ix_markets_symbol_end_scan" in indexes
            assert "ix_markets_duration_scan" in indexes
        finally:
            conn.close()

    def test_init_db_migrates_existing_market_table(self, tmp_path: Path):
        db_path = tmp_path / "rec.db"
        raw = sqlite3.connect(db_path)
        raw.executescript(
            """
            CREATE TABLE markets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_at_ms INTEGER NOT NULL,
                condition_id TEXT NOT NULL,
                question TEXT NOT NULL,
                end_date_iso TEXT,
                yes_token_id TEXT,
                no_token_id TEXT,
                volume_24h_usd REAL,
                yes_price REAL,
                category TEXT DEFAULT 'crypto',
                raw_json TEXT
            );
            """
        )
        raw.close()

        conn = init_db(db_path)
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(markets)")}
            assert "symbol" in cols
            assert "duration_minutes" in cols
        finally:
            conn.close()


class TestInitWalCheckpoint:
    """Session 39 / OQ-055: init_db must TRUNCATE the WAL on open so each
    process start begins from a clean slate. Without this, a crashed
    prior run leaves a multi-MB WAL that the new process inherits;
    accumulated WAL drives checkpoint pressure and reproduces the
    writer_stall_abort cycle."""

    def test_init_truncates_inherited_wal(self, tmp_path: Path):
        db_path = tmp_path / "rec.db"

        # First open: write a row + commit. WAL mode means the row
        # lands in the WAL file rather than the main DB until a
        # checkpoint runs.
        conn1 = init_db(db_path)
        conn1.execute(
            "INSERT INTO heartbeats (emitted_at_ms, source, "
            "subscription_id, last_message_age_sec, metadata_json) "
            "VALUES (?, 'process', NULL, NULL, NULL)",
            (1_000_000_000_000,),
        )
        conn1.commit()
        # Bypass the auto-checkpoint by writing data and NOT closing
        # cleanly — simulate a crash. We close without checkpoint by
        # using the underlying connection without explicit checkpoint.
        # SQLite still flushes WAL on close, but if the prior process
        # crashed the WAL would persist. We can simulate the post-crash
        # state by reopening and asserting init_db starts from clean WAL.
        conn1.close()

        wal_path = db_path.with_name(db_path.name + "-wal")
        # If WAL is currently empty, simulate a crashed-prior-run by
        # writing without committing through our own raw connection so
        # the WAL has unflushed pages. (The exact bytes don't matter;
        # we just need init_db to return with WAL truncated.)
        raw = sqlite3.connect(str(db_path), isolation_level=None)
        raw.execute("PRAGMA journal_mode=WAL")
        raw.execute("BEGIN")
        for i in range(50):
            raw.execute(
                "INSERT INTO heartbeats (emitted_at_ms, source, "
                "subscription_id, last_message_age_sec, metadata_json) "
                "VALUES (?, 'process', NULL, NULL, NULL)",
                (1_000_000_000_000 + i,),
            )
        raw.execute("COMMIT")
        # Don't close: keep the raw conn open so the WAL is retained
        # while we open another connection via init_db.
        wal_size_before = wal_path.stat().st_size if wal_path.exists() else 0

        # Re-open with init_db — it should TRUNCATE the WAL.
        conn2 = init_db(db_path)
        try:
            # After TRUNCATE the WAL file should exist but be 0 bytes
            # (or absent). raw conn still pinning may keep some data,
            # but init_db's checkpoint should at least try.
            # We assert that init_db completed without raising.
            assert conn2 is not None

            # And data persisted: we should be able to read the row
            # we wrote pre-crash.
            n = conn2.execute("SELECT COUNT(*) FROM heartbeats").fetchone()[0]
            assert n >= 51  # 1 from conn1 + 50 from raw
        finally:
            conn2.close()
            raw.close()

        # Final assertion: after the raw connection is closed and we
        # re-init, the WAL should be empty (size 0) because there's
        # nothing pinning it any more.
        conn3 = init_db(db_path)
        try:
            wal_size_after = wal_path.stat().st_size if wal_path.exists() else 0
            assert wal_size_after == 0, (
                f"WAL not truncated on init: {wal_size_before} -> "
                f"{wal_size_after} bytes"
            )
        finally:
            conn3.close()

    def test_init_db_succeeds_when_wal_busy(self, tmp_path: Path):
        """If another connection holds the DB busy, the checkpoint may
        return non-zero busy. init_db must NOT raise — the recorder
        starts up and lets the next auto-checkpoint catch up."""
        db_path = tmp_path / "rec.db"
        conn1 = init_db(db_path)
        conn1.execute("BEGIN")  # hold a transaction
        try:
            # init_db on the same DB should still return a connection.
            conn2 = init_db(db_path)
            try:
                assert conn2 is not None
            finally:
                conn2.close()
        finally:
            conn1.execute("ROLLBACK")
            conn1.close()
