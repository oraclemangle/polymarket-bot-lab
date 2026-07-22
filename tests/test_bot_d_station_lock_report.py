from __future__ import annotations

import json
import sqlite3

from scripts.bot_d_station_lock_report import build_report


def test_station_lock_report_reads_events_without_sqlalchemy(tmp_path):
    db = tmp_path / "main.db"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            bot_id TEXT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            payload TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO events (bot_id, event_type, severity, message, payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "bot_d_station_lock",
            "bot_d.station_lock.candidate",
            "info",
            "candidate",
            json.dumps(
                {
                    "city": "Chicago",
                    "station": "KORD",
                    "source": "aviationweather_metar",
                    "state": "already_no",
                    "confidence": "hard",
                }
            ),
            "2026-05-14 10:00:00",
        ),
    )
    conn.execute(
        """
        INSERT INTO events (bot_id, event_type, severity, message, payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "bot_d_station_lock",
            "bot_d.station_lock.skip",
            "info",
            "skip",
            json.dumps({"skip_reason_code": "edge_below_threshold"}),
            "2026-05-14 10:01:00",
        ),
    )
    conn.commit()
    conn.close()

    report = build_report(str(db), lookback_days=3650)

    assert report["summary"]["candidates"] == 1
    assert report["summary"]["skips"] == 1
    assert report["candidates_by_city"] == {"Chicago": 1}
    assert report["skip_reasons"] == {"edge_below_threshold": 1}
