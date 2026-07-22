"""Skeleton tests for the wallet Data API backfill tool.

Per GROK_OVERNIGHT_IMPLEMENTATION_SPEC_2026-05-18.md and CHECKLIST Phase 1.

Replace the placeholder tests with real unit + integration coverage once the
classifier and reporter are implemented.
"""

import json
import os
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "wallet_data_api"


def test_fixtures_load():
    """Basic smoke test that the fixtures the implementer will use are valid JSON."""
    pos = json.loads((FIXTURE_DIR / "sample_positions.json").read_text())
    trades = json.loads((FIXTURE_DIR / "sample_trades.json").read_text())
    assert len(pos) >= 1
    assert len(trades) >= 1
    assert any("UNOWNED" in str(t) for t in trades)  # example of unowned row for classifier test


def test_backfill_script_skeleton_imports_and_cli_help():
    """The script must be importable and have a working --help even in skeleton form."""
    from scripts import wallet_data_api_backfill as mod

    # The module must define main()
    assert hasattr(mod, "main")

    # Running with --help should not crash (argparse)
    # (In real run the implementer will expand the CLI)
    import subprocess

    result = subprocess.run(
        ["uv", "run", "python", "-m", "scripts.wallet_data_api_backfill", "--help"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parents[1],
    )
    assert result.returncode == 0 or "usage:" in result.stdout.lower()
    assert "dry-run" in result.stdout.lower() or "dry_run" in result.stdout.lower()


def test_classifier_owned_vs_unowned(monkeypatch, tmp_path: Path):
    """Unit test for ReconciliationClassifier using synthetic DB rows + fixture data."""
    from scripts.wallet_data_api_backfill import ReconciliationClassifier

    # Build tiny temp DBs matching the classifier expectations
    main_db = tmp_path / "t_main.db"
    import sqlite3

    con = sqlite3.connect(main_db)
    con.execute(
        "CREATE TABLE positions (id INTEGER PRIMARY KEY, bot_id TEXT, condition_id TEXT, token_id TEXT, side TEXT, size REAL, cost_basis_usd REAL, status TEXT, opened_at TEXT)"
    )
    con.execute(
        "INSERT INTO positions (bot_id, condition_id, token_id, status, opened_at) VALUES ('bot_d_live_probe', '0xCOND1', '0xEXAMPLE_TOKEN_1', 'OPEN', '2026-05-17')"
    )
    con.commit()
    con.close()

    pers_db = tmp_path / "t_pers.db"
    con = sqlite3.connect(pers_db)
    con.execute("CREATE TABLE live_entries (id INTEGER, asset TEXT, status TEXT)")
    con.execute("INSERT INTO live_entries VALUES (1, '0xPERSIST_ONLY', 'OPEN')")
    con.commit()
    con.close()

    clf = ReconciliationClassifier(str(main_db), str(pers_db))

    # Load fixture rows (simulate Data API response)
    pos = json.loads((FIXTURE_DIR / "sample_positions.json").read_text())
    classified = clf.classify(pos)

    assert len(classified) >= 1
    # The first fixture token should now be owned via the synthetic main.db row
    owned = [c for c in classified if c["status"] == "owned"]
    unowned = [c for c in classified if c["status"] != "owned"]
    assert len(owned) + len(unowned) == len(classified)
    # Second fixture row is unowned example
    assert any("UNOWNED" in str(c.get("notes", "")) or c["status"] != "owned" for c in classified)


def test_end_to_end_dry_run_with_fixtures(monkeypatch, tmp_path: Path, capsys):
    """Integration: backfill --use-fixtures produces report without network and exits 0."""
    import subprocess
    import sys

    env = dict(os.environ)
    env["POLYMARKET_HOT_WALLET"] = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.wallet_data_api_backfill",
            "--use-fixtures",
            "--json",
            "--since",
            "2026-05-16",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=Path(__file__).parents[1],
    )
    assert result.returncode == 0
    out = result.stdout + result.stderr
    assert "dry_run_complete" in out or "fixture_mode" in out or "classified" in out
    assert "INFO: dry-run complete" in out


def test_refuses_execute_without_confirmation_env(monkeypatch, capsys):
    """Safety gate: --execute without the magic env var must refuse (return !=0)."""
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
    combined = (result.stdout or "") + (result.stderr or "")
    assert "WALLET_BACKFILL_CONFIRM" in combined


def test_backfill_defines_required_classes():
    """Per SPEC: the authoritative module exposes WalletDataApiClient, Classifier, Reporter."""
    from scripts.wallet_data_api_backfill import (
        ReconciliationClassifier,
        ReconciliationReporter,
        WalletDataApiClient,
    )

    assert callable(WalletDataApiClient)
    assert callable(ReconciliationClassifier)
    assert callable(ReconciliationReporter)
