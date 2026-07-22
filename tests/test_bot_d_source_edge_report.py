from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from scripts.bot_d_source_edge_report import build_report, render_markdown


def _dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_source_edge_report_summarises_late_certainty_and_residuals(tmp_path):
    now = datetime(2026, 5, 5, 16, tzinfo=UTC)
    db = tmp_path / "main.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE events (bot_id TEXT, event_type TEXT, severity TEXT, message TEXT, payload TEXT, created_at TEXT)"
    )
    source_payload = {
        "condition_id": "gamma-nyc",
        "city": "NYC",
        "date": "2026-05-05",
        "temp_type": "high",
        "bucket_low_f": 74,
        "bucket_high_f": 76,
        "settlement_station": "KLGA",
        "market_yes_price": "0.22",
        "bucket_state": "already_no",
        "bucket_locked": False,
        "bucket_impossible": True,
        "station_metric_f": 77,
        "lock_age_seconds": 3600,
        "raw_station_age_seconds": 600,
        "source_lag_seconds": 420,
        "source_station_status": "ok",
        "source_matches_station_metric": True,
        "source_snapshot": {
            "sample_count": 8,
            "raw_max_settlement_f": 77,
            "raw_min_settlement_f": 65,
        },
    }
    entry_payload = {
        "condition_id": "gamma-nyc",
        "city": "NYC",
        "date": "2026-05-05",
        "temp_type": "high",
        "settlement_station": "KLGA",
        "forecast_mean_f": 75,
    }
    conn.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
        ("bot_d", "bot_d.source_snapshot", "info", "", json.dumps(source_payload), _dt(now - timedelta(minutes=5))),
    )
    conn.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
        ("bot_d", "bot_d.forecast_entry", "info", "", json.dumps(entry_payload), _dt(now - timedelta(minutes=4))),
    )
    conn.commit()
    conn.close()

    report = build_report(db, bot_id="bot_d", now=now, lookback_hours=24)

    assert report["source_snapshots"]["late_certain"] == 1
    assert report["source_snapshots"]["bucket_impossible"] == 1
    assert report["source_snapshots"]["source_visible_matches"] == 1
    assert report["source_snapshots"]["avg_source_lag_seconds"] == 420.0
    assert report["forecast_residuals"]["matched_entries"] == 1
    assert report["forecast_residuals"]["avg_residual_f"] == -2.0
    md = render_markdown(report)
    assert "Bot D Source Edge Report" in md
    assert "already_no" in md


def test_source_edge_report_filters_by_bot_id(tmp_path):
    now = datetime(2026, 5, 5, 16, tzinfo=UTC)
    db = tmp_path / "main.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE events (bot_id TEXT, event_type TEXT, severity TEXT, message TEXT, payload TEXT, created_at TEXT)"
    )
    live_payload = {"condition_id": "live", "bucket_state": "already_no", "settlement_station": "KLGA"}
    paper_payload = {"condition_id": "paper", "bucket_state": "unknown", "settlement_station": "KLGA"}
    conn.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
        (
            "bot_d_live_probe",
            "bot_d.source_snapshot",
            "info",
            "",
            json.dumps(live_payload),
            _dt(now - timedelta(minutes=5)),
        ),
    )
    conn.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
        (
            "bot_d",
            "bot_d.source_snapshot",
            "info",
            "",
            json.dumps(paper_payload),
            _dt(now - timedelta(minutes=4)),
        ),
    )
    conn.commit()
    conn.close()

    report = build_report(db, now=now, lookback_hours=24)

    assert report["bot_id"] == "bot_d_live_probe"
    assert report["source_snapshots"]["snapshots"] == 1
    assert report["source_snapshots"]["by_bucket_state"] == {"already_no": 1}
