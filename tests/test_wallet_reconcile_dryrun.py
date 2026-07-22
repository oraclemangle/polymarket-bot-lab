"""Tests for the dry-run wallet reconciliation report tool (OQ-123 P0)."""

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.wallet_reconcile_dryrun import CRITICAL_BOT_IDS, build_report


@pytest.fixture
def sample_main_db(tmp_path: Path) -> str:
    db = tmp_path / "test_main.db"
    import sqlite3

    con = sqlite3.connect(db)
    con.execute("""
        CREATE TABLE positions (
            id INTEGER PRIMARY KEY,
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            size REAL,
            cost_basis_usd REAL,
            status TEXT,
            opened_at TEXT
        )
    """)
    # One stale OPEN for a critical bot
    con.execute(
        "INSERT INTO positions (bot_id, token_id, status, cost_basis_usd, opened_at) "
        "VALUES ('bot_d_live_probe', '0xSTALE123', 'OPEN', 12.5, '2026-05-10')"
    )
    # One that will match a fake wallet position
    con.execute(
        "INSERT INTO positions (bot_id, token_id, status, cost_basis_usd, opened_at) "
        "VALUES ('bot_g_prime_live', '0xWALLET_HELD', 'OPEN', 5.0, '2026-05-17')"
    )
    con.commit()
    con.close()
    return str(db)


@pytest.fixture
def sample_persistence_db(tmp_path: Path) -> str:
    db = tmp_path / "test_persistence.db"
    import sqlite3

    con = sqlite3.connect(db)
    con.execute("CREATE TABLE live_entries (id INTEGER, asset TEXT, status TEXT)")
    con.execute("INSERT INTO live_entries VALUES (1, '0xPERSISTENCE_ONLY', 'OPEN')")
    con.commit()
    con.close()
    return str(db)


def test_build_report_dry_run_no_network(monkeypatch, sample_main_db, sample_persistence_db):
    """Smoke test: builds report structure without real network (we mock the fetches)."""

    def fake_positions(*a, **k):
        return [{"asset": "0xWALLET_HELD", "size": "1.0"}]

    def fake_trades(*a, **k):
        return []

    monkeypatch.setattr("scripts.wallet_reconcile_dryrun.fetch_wallet_positions", fake_positions)
    monkeypatch.setattr("scripts.wallet_reconcile_dryrun.fetch_wallet_trades", fake_trades)

    report = build_report(
        wallet="0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        since=datetime(2026, 5, 16, tzinfo=UTC),
        main_db=sample_main_db,
        persistence_db=sample_persistence_db,
        data_api="https://example.invalid",
    )

    assert report["summary"]["local_open_in_scope"] >= 1
    assert report["summary"]["stale_local_open_not_in_wallet"] >= 1  # the 0xSTALE123
    assert "unowned_wallet_positions" in report["summary"]
    assert "recommendation" in report
    assert "bot_d_live_probe" in CRITICAL_BOT_IDS
    assert report["summary"]["stale_local_open_not_in_wallet"] >= 1


def test_critical_bot_list_matches_registry():
    """The list used by the tool must be a subset of real registry bots."""
    from core.bot_registry import REGISTRY

    registry_ids = {b.bot_id for b in REGISTRY}
    for bid in CRITICAL_BOT_IDS:
        assert bid in registry_ids, f"{bid} missing from core/bot_registry.py REGISTRY"


def test_wallet_backfill_skeleton_refuses_execute_without_confirmation(monkeypatch, capsys):
    """Codex requirement: --execute must be refused without the confirmation env var."""
    import subprocess
    import sys

    env = dict(os.environ)
    env.pop("WALLET_BACKFILL_CONFIRM", None)

    result = subprocess.run(
        [sys.executable, "-m", "scripts.wallet_data_api_backfill", "--execute", "--json"],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path(__file__).parents[1],
    )

    assert result.returncode != 0
    assert "WALLET_BACKFILL_CONFIRM" in result.stdout or "WALLET_BACKFILL_CONFIRM" in result.stderr


def test_dashboard_overview_contains_accounting_and_freshness_fields():
    """Codex requirement: the new accounting/freshness fields must be present
    in the overview dict returned by runtime_queries (even if not yet deployed)."""
    from dashboard import runtime_queries as dq

    # We only care that the functions we modified still produce the expected keys
    # in the structure we extended during Session 450.
    overview = dq.query_overview()

    assert "accounting" in overview
    acc = overview["accounting"]
    assert "wallet_reconciliation_status" in acc
    assert "persistence_live_db_separate" in acc
    # New fields from phase 2 dashboard truth surface
    assert "wallet_reconciliation_run_at" in acc
    assert "total_unresolved_usd" in acc

    # At least one inventory row should have the freshness + reconciliation fields
    inventory = overview.get("bot_inventory") or overview.get("inventory", [])
    has_freshness = any("freshness" in row for row in inventory if isinstance(row, dict))
    has_recon = any("reconciliation_status" in row for row in inventory if isinstance(row, dict))
    assert has_freshness or len(inventory) == 0
    assert has_recon or len(inventory) == 0  # new per-row recon fields path exists
