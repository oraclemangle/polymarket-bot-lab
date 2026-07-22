from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from core.crowd_signals import crowd_pressure_for_market, recent_cascades_for_market


def _make_bot_f_db(path, now: datetime) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE crowd_signals (
            detected_at TEXT,
            market_id TEXT,
            cascade_start_ts INTEGER,
            cascade_end_ts INTEGER,
            n_wallets INTEGER,
            dominant_side TEXT,
            gross_usd REAL,
            dominant_ratio REAL
        )
        """
    )
    conn.execute(
        "INSERT INTO crowd_signals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            now.strftime("%Y-%m-%d %H:%M:%S"),
            "m1",
            100,
            120,
            7,
            "BUY_YES",
            750.0,
            0.9,
        ),
    )
    conn.execute(
        "INSERT INTO crowd_signals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (now - timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S"),
            "m1",
            1,
            2,
            9,
            "BUY_NO",
            900.0,
            0.95,
        ),
    )
    conn.commit()
    conn.close()


def test_recent_cascades_for_market_filters_by_time(tmp_path):
    now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    db = tmp_path / "bot_f.db"
    _make_bot_f_db(db, now)

    rows = recent_cascades_for_market("m1", bot_f_db=db, within_hours=6, now=now)

    assert len(rows) == 1
    assert rows[0].dominant_side == "BUY_YES"
    assert rows[0].gross_usd == 750.0


def test_crowd_pressure_summarizes_top_recent_cascade(tmp_path):
    now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    db = tmp_path / "bot_f.db"
    _make_bot_f_db(db, now)

    pressure = crowd_pressure_for_market("m1", bot_f_db=db, within_hours=6, now=now)

    assert pressure.has_recent_cascade is True
    assert pressure.cascade_count == 1
    assert pressure.top_side == "BUY_YES"
    assert pressure.top_gross_usd == 750.0
    assert pressure.top_wallets == 7


def test_missing_bot_f_db_is_no_signal(tmp_path):
    pressure = crowd_pressure_for_market("m1", bot_f_db=tmp_path / "missing.db")

    assert pressure.has_recent_cascade is False
    assert pressure.cascade_count == 0

