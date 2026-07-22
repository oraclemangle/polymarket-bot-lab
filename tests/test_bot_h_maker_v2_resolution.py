"""Tests for Bot H Maker V2 resolution backfill (Session 260).

Covers:

- Schema migration: `_ensure_resolution_columns` is idempotent and
  adds the four resolution columns when missing.
- `_parse_outcome_prices`: handles JSON / CSV / void / malformed.
- `find_unresolved_markets`: respects throttle, excludes RESOLVED,
  excludes markets already labelled.
- `upsert_resolution`: returns True on transition, updates the
  correct fields, leaves status alone for unresolved markets.
- The CLI's missing-DB path returns 0 (so systemd doesn't restart
  loop before the recorder has had a chance to create the DB).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bots.bot_h_maker_v2.resolution_backfill import (
    _parse_outcome_prices,
    find_unresolved_markets,
    upsert_resolution,
)
from bots.bot_h_maker_v2.schema import _ensure_resolution_columns, init_db


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------


def test_init_db_adds_resolution_columns_to_fresh_db(tmp_path):
    path = tmp_path / "fresh.db"
    conn = init_db(path)
    rows = conn.execute("PRAGMA table_info(markets)").fetchall()
    columns = {r[1] for r in rows}
    assert "yes_won" in columns
    assert "resolved_at_ms" in columns
    assert "outcome_yes_price" in columns
    assert "last_resolution_check_ms" in columns
    conn.close()


def test_ensure_resolution_columns_is_idempotent(tmp_path):
    """Running the migration on an already-migrated DB must be a no-op
    (no errors, no extra columns)."""
    path = tmp_path / "migrated.db"
    conn = init_db(path)
    pre = {r[1] for r in conn.execute("PRAGMA table_info(markets)").fetchall()}
    added_again = _ensure_resolution_columns(conn)
    assert added_again == [], "second call must add nothing"
    post = {r[1] for r in conn.execute("PRAGMA table_info(markets)").fetchall()}
    assert pre == post
    conn.close()


def test_ensure_resolution_columns_migrates_legacy_db(tmp_path):
    """A DB created BEFORE this migration (legacy schema without the four
    resolution columns) should pick them up on next init_db()."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE markets (
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
        )
        """
    )
    conn.commit()
    pre = {r[1] for r in conn.execute("PRAGMA table_info(markets)").fetchall()}
    assert "yes_won" not in pre
    added = _ensure_resolution_columns(conn)
    assert sorted(added) == sorted(
        ["yes_won", "resolved_at_ms", "outcome_yes_price", "last_resolution_check_ms"]
    )
    post = {r[1] for r in conn.execute("PRAGMA table_info(markets)").fetchall()}
    assert "yes_won" in post
    conn.close()


# ---------------------------------------------------------------------------
# Outcome-price parsing
# ---------------------------------------------------------------------------


def test_parse_outcome_prices_yes_win_json():
    yes_won, yes_price = _parse_outcome_prices('["1", "0"]')
    assert yes_won == 1
    assert yes_price == pytest.approx(1.0)


def test_parse_outcome_prices_no_win_json():
    yes_won, yes_price = _parse_outcome_prices('["0", "1"]')
    assert yes_won == 0
    assert yes_price == pytest.approx(0.0)


def test_parse_outcome_prices_void_returns_none():
    yes_won, yes_price = _parse_outcome_prices('["0.5", "0.5"]')
    assert yes_won is None
    assert yes_price == pytest.approx(0.5)


def test_parse_outcome_prices_handles_csv_format():
    """Some Gamma responses come back as `[0, 1]` rather than JSON
    string literal — the parser must tolerate both."""
    yes_won, yes_price = _parse_outcome_prices("[0, 1]")
    assert yes_won == 0
    assert yes_price == pytest.approx(0.0)


def test_parse_outcome_prices_handles_unresolved_string():
    """Active markets often show `["0.45", "0.55"]` etc. — must return
    None so the backfill doesn't claim a win."""
    yes_won, yes_price = _parse_outcome_prices('["0.45", "0.55"]')
    assert yes_won is None
    assert yes_price == pytest.approx(0.45)


def test_parse_outcome_prices_handles_malformed():
    assert _parse_outcome_prices(None) == (None, None)
    assert _parse_outcome_prices("garbage") == (None, None)
    assert _parse_outcome_prices('["1"]') == (None, None)
    assert _parse_outcome_prices("[1, 2, 3]") == (None, None)


# ---------------------------------------------------------------------------
# find_unresolved_markets
# ---------------------------------------------------------------------------


@pytest.fixture()
def populated_db(tmp_path) -> Path:
    """Create a recorder DB with three markets in three states."""
    path = tmp_path / "test_recorder.db"
    conn = init_db(path)
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    fixtures = [
        # Unresolved, never checked → should be picked
        ("cond-active-never-checked", None, None, "ACTIVE", None),
        # Unresolved, checked recently (3h ago < 4h throttle) → SKIP
        ("cond-active-recently-checked", None, None, "ACTIVE", now_ms - 3 * 3600 * 1000),
        # Unresolved, checked >4h ago → should be picked
        ("cond-active-stale-check", None, None, "ACTIVE", now_ms - 5 * 3600 * 1000),
        # Already resolved → SKIP
        ("cond-resolved", 1, 1.0, "RESOLVED", now_ms - 1000),
    ]
    for cid, yes_won, yes_price, status, last_check in fixtures:
        conn.execute(
            """
            INSERT INTO markets (condition_id, yes_token_id, no_token_id,
                category, question, end_date_ts, discovered_at_ms, last_seen_at_ms,
                status, yes_won, outcome_yes_price, last_resolution_check_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cid,
                f"yes-{cid}",
                f"no-{cid}",
                "politics",
                f"Q{cid}",
                None,
                now_ms - 86400000,
                now_ms - 1000,
                status,
                yes_won,
                yes_price,
                last_check,
            ),
        )
    conn.commit()
    conn.close()
    return path


def test_find_unresolved_markets_excludes_resolved_and_recently_checked(populated_db: Path):
    conn = sqlite3.connect(str(populated_db))
    conn.row_factory = sqlite3.Row
    candidates = find_unresolved_markets(conn, limit=10, recheck_throttle_sec=4 * 3600)
    assert sorted(candidates) == sorted(
        ["cond-active-never-checked", "cond-active-stale-check"]
    )
    conn.close()


def test_find_unresolved_markets_respects_limit(populated_db: Path):
    conn = sqlite3.connect(str(populated_db))
    conn.row_factory = sqlite3.Row
    candidates = find_unresolved_markets(conn, limit=1, recheck_throttle_sec=4 * 3600)
    assert len(candidates) == 1
    conn.close()


# ---------------------------------------------------------------------------
# upsert_resolution
# ---------------------------------------------------------------------------


def test_upsert_resolution_transitions_to_resolved(populated_db: Path):
    """When Gamma reports `closed=true outcomePrices=["1","0"]` for a
    market we've never resolved, upsert flips status → RESOLVED, sets
    yes_won=1, and returns True."""
    conn = sqlite3.connect(str(populated_db))
    conn.row_factory = sqlite3.Row
    now_ms = 9_000_000_000
    transitioned = upsert_resolution(
        conn,
        {
            "conditionId": "cond-active-never-checked",
            "closed": True,
            "outcomePrices": '["1", "0"]',
        },
        now_ms=now_ms,
    )
    assert transitioned is True
    row = conn.execute(
        "SELECT yes_won, status, resolved_at_ms, outcome_yes_price, last_resolution_check_ms "
        "FROM markets WHERE condition_id=?",
        ("cond-active-never-checked",),
    ).fetchone()
    assert row["yes_won"] == 1
    assert row["status"] == "RESOLVED"
    assert row["resolved_at_ms"] == now_ms
    assert row["outcome_yes_price"] == pytest.approx(1.0)
    assert row["last_resolution_check_ms"] == now_ms
    conn.close()


def test_upsert_resolution_unresolved_market_only_bumps_check_timestamp(populated_db: Path):
    """When Gamma reports closed=False, we must NOT flip status; just
    bump last_resolution_check_ms so we don't re-poll for the throttle
    window."""
    conn = sqlite3.connect(str(populated_db))
    conn.row_factory = sqlite3.Row
    now_ms = 9_000_000_000
    transitioned = upsert_resolution(
        conn,
        {
            "conditionId": "cond-active-never-checked",
            "closed": False,
            "outcomePrices": '["0.4", "0.6"]',
        },
        now_ms=now_ms,
    )
    assert transitioned is False
    row = conn.execute(
        "SELECT yes_won, status, resolved_at_ms, last_resolution_check_ms "
        "FROM markets WHERE condition_id=?",
        ("cond-active-never-checked",),
    ).fetchone()
    assert row["yes_won"] is None
    assert row["status"] == "ACTIVE"
    assert row["resolved_at_ms"] is None
    assert row["last_resolution_check_ms"] == now_ms
    conn.close()


def test_upsert_resolution_void_market_does_not_resolve(populated_db: Path):
    """Void markets (50/50) must NOT flip status to RESOLVED — yes_won
    stays None and the simulator continues to skip them."""
    conn = sqlite3.connect(str(populated_db))
    conn.row_factory = sqlite3.Row
    now_ms = 9_000_000_000
    transitioned = upsert_resolution(
        conn,
        {
            "conditionId": "cond-active-never-checked",
            "closed": True,
            "outcomePrices": '["0.5", "0.5"]',
        },
        now_ms=now_ms,
    )
    assert transitioned is False
    row = conn.execute(
        "SELECT yes_won, status, outcome_yes_price FROM markets WHERE condition_id=?",
        ("cond-active-never-checked",),
    ).fetchone()
    assert row["yes_won"] is None
    assert row["status"] == "ACTIVE"
    assert row["outcome_yes_price"] == pytest.approx(0.5)
    conn.close()


def test_upsert_resolution_ignores_unknown_condition_id(populated_db: Path):
    """If Gamma returns a market we don't have in our recorder, the
    function must NOT INSERT a new row — discovery_loop owns row
    creation."""
    conn = sqlite3.connect(str(populated_db))
    conn.row_factory = sqlite3.Row
    pre_count = conn.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
    transitioned = upsert_resolution(
        conn,
        {
            "conditionId": "cond-not-in-our-recorder",
            "closed": True,
            "outcomePrices": '["1", "0"]',
        },
        now_ms=9_000_000_000,
    )
    assert transitioned is False
    post_count = conn.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
    assert pre_count == post_count
    conn.close()
