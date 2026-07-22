"""Tests for the daily replay wrapper script.

Covers the wrapper-level concerns (prune retention, latest-copy
semantics, dated-filename validation). The replay simulator's
correctness is tested in `test_bot_h_maker_v2_scripts.py`.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest


def _make_dated_files(reports_dir: Path, dates_and_ages: list[tuple[str, int]]) -> None:
    """Helper: create `<date>.md` and `<date>.json` under reports_dir
    with mtime offset N days into the past."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for date_str, age_days in dates_and_ages:
        for ext in (".md", ".json"):
            p = reports_dir / f"{date_str}{ext}"
            p.write_text("placeholder")
            ts = now - age_days * 86400
            os.utime(p, (ts, ts))


def test_prune_old_reports_removes_only_old_dated_files(tmp_path):
    from scripts.bot_h_maker_v2_recorder_daily_replay import _prune_old_reports

    reports = tmp_path / "reports"
    _make_dated_files(
        reports,
        [
            ("2026-01-01", 120),  # very old, both files should go
            ("2026-04-01", 95),   # old, both files should go
            ("2026-04-15", 45),   # within retention, keeps
            ("2026-05-01", 8),    # fresh, keeps
        ],
    )
    # Sentinel files
    (reports / "latest.md").write_text("latest")
    (reports / "latest.json").write_text("latest")
    (reports / "README.md").write_text("docs")

    pruned = _prune_old_reports(reports, retain_days=90)
    assert pruned == 4, "Two old (md+json) for each of 2 expired dates"

    remaining = sorted(p.name for p in reports.iterdir())
    assert remaining == sorted(
        [
            "2026-04-15.json",
            "2026-04-15.md",
            "2026-05-01.json",
            "2026-05-01.md",
            "README.md",
            "latest.json",
            "latest.md",
        ]
    )


def test_prune_keeps_latest_files_regardless_of_age(tmp_path):
    """Even a years-old `latest.md` must not be pruned — the cron may
    have stalled and `latest` is still the most recent successful
    report for the dashboard."""
    from scripts.bot_h_maker_v2_recorder_daily_replay import _prune_old_reports

    reports = tmp_path / "reports"
    reports.mkdir()
    for name in ("latest.md", "latest.json"):
        p = reports / name
        p.write_text("old-but-still-canonical")
        ancient = time.time() - 365 * 86400
        os.utime(p, (ancient, ancient))

    pruned = _prune_old_reports(reports, retain_days=90)
    assert pruned == 0
    assert (reports / "latest.md").exists()
    assert (reports / "latest.json").exists()


def test_prune_skips_files_without_date_prefix(tmp_path):
    """README.md, summary.md, etc. must not match the YYYY-MM-DD
    archive pattern and must be left alone."""
    from scripts.bot_h_maker_v2_recorder_daily_replay import _prune_old_reports

    reports = tmp_path / "reports"
    reports.mkdir()
    for name in ("README.md", "summary.md", "notes-may.md"):
        p = reports / name
        p.write_text("docs")
        ancient = time.time() - 365 * 86400
        os.utime(p, (ancient, ancient))

    pruned = _prune_old_reports(reports, retain_days=90)
    assert pruned == 0
    for name in ("README.md", "summary.md", "notes-may.md"):
        assert (reports / name).exists()


def test_prune_handles_missing_directory(tmp_path):
    """First-run case: reports dir doesn't exist yet."""
    from scripts.bot_h_maker_v2_recorder_daily_replay import _prune_old_reports

    nonexistent = tmp_path / "never_created"
    pruned = _prune_old_reports(nonexistent, retain_days=90)
    assert pruned == 0


def test_prune_skips_non_archive_extensions(tmp_path):
    """Only `.md` and `.json` files are eligible for pruning. Other
    extensions (logs, screenshots) stay even with old mtime."""
    from scripts.bot_h_maker_v2_recorder_daily_replay import _prune_old_reports

    reports = tmp_path / "reports"
    reports.mkdir()
    for name in ("2026-01-01.txt", "2026-01-01.csv", "2026-01-01.png"):
        p = reports / name
        p.write_text("data")
        ancient = time.time() - 200 * 86400
        os.utime(p, (ancient, ancient))

    pruned = _prune_old_reports(reports, retain_days=90)
    assert pruned == 0
    for name in ("2026-01-01.txt", "2026-01-01.csv", "2026-01-01.png"):
        assert (reports / name).exists()


def test_main_short_circuits_when_db_missing(tmp_path, monkeypatch, caplog):
    """Operator may install the timer before the recorder has produced
    a DB. The script must return 0 (success) and log a clear warning,
    not crash."""
    from scripts import bot_h_maker_v2_recorder_daily_replay as wrapper

    nonexistent = tmp_path / "no_db.db"
    reports = tmp_path / "reports"
    monkeypatch.setattr(
        "sys.argv",
        [
            "bot_h_maker_v2_recorder_daily_replay",
            "--db-path",
            str(nonexistent),
            "--reports-dir",
            str(reports),
        ],
    )
    rc = wrapper.main()
    assert rc == 0
    # No reports dir should have been created since the DB was missing
    assert not reports.exists()
