from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from scripts.fast_roi_report import build_report, render_markdown


def _make_main_db(path, now: datetime) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE orders (
            order_id TEXT,
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            status TEXT,
            placed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE trades (
            trade_id TEXT,
            bot_id TEXT,
            order_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            fee_usd REAL,
            filled_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE positions (
            bot_id TEXT,
            status TEXT,
            cost_basis_usd REAL,
            opened_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE events (
            bot_id TEXT,
            event_type TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE books (
            token_id TEXT,
            snapshot_at TEXT,
            bids TEXT,
            asks TEXT
        )
        """
    )
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("o1", "bot_e", "c1", "t1", "BUY", 0.5, 10, "FILLED", ts),
    )
    conn.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("o2", "bot_e", "c1", "t1", "BUY", 0.5, 10, "CANCELLED", ts),
    )
    conn.execute(
        "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("tr1", "bot_e", "o1", "c1", "t1", "BUY", 0.5, 10, 0.01, ts),
    )
    conn.execute(
        "INSERT INTO positions VALUES (?, ?, ?, ?)",
        (
            "bot_d",
            "OPEN",
            50.0,
            (now - timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.execute("INSERT INTO events VALUES (?, ?, ?)", ("bot_e", "bot_e.signal", ts))
    conn.execute(
        "INSERT INTO books VALUES (?, ?, ?, ?)",
        (
            "tf",
            now.strftime("%Y-%m-%d %H:%M:%S.%f"),
            '[["0.49", "10"]]',
            '[["0.51", "10"]]',
        ),
    )
    conn.execute(
        "INSERT INTO books VALUES (?, ?, ?, ?)",
        (
            "tf",
            (now + timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S.%f"),
            '[["0.54", "10"]]',
            '[["0.56", "10"]]',
        ),
    )
    conn.commit()
    conn.close()


def _make_bot_f_db(path, now: datetime) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE crowd_signals (
            detected_at TEXT,
            market_id TEXT,
            dominant_side TEXT,
            gross_usd REAL,
            n_wallets INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE mirror_signals (
            detected_at TEXT,
            token_id TEXT,
            side TEXT,
            price REAL
        )
        """
    )
    conn.execute(
        "INSERT INTO crowd_signals VALUES (?, ?, ?, ?, ?)",
        (now.strftime("%Y-%m-%d %H:%M:%S"), "c1", "BUY_YES", 600.0, 8),
    )
    conn.execute(
        "INSERT INTO mirror_signals VALUES (?, ?, ?, ?)",
        (now.strftime("%Y-%m-%d %H:%M:%S"), "tf", "BUY_YES", 0.5),
    )
    conn.commit()
    conn.close()


def test_build_report_summarizes_fast_roi_inputs(tmp_path):
    now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    main_db = tmp_path / "main.db"
    bot_f_db = tmp_path / "bot_f.db"
    _make_main_db(main_db, now)
    _make_bot_f_db(bot_f_db, now)

    report = build_report(main_db, bot_f_db=bot_f_db, lookback_hours=24, now=now)

    bot_e = next(row for row in report["bots"] if row["bot_id"] == "bot_e")
    bot_d = next(row for row in report["bots"] if row["bot_id"] == "bot_d")
    assert bot_e["fill_rate"] == 0.5
    assert bot_e["trades"]["fills"] == 1
    assert bot_e["trades"]["notional"] == 5.0
    assert bot_d["open_positions"]["open_cost_basis"] == 50.0
    assert bot_d["open_positions"]["avg_open_age_hours"] == 30.0
    assert report["crowd_sensor"]["cascade_count"] == 1
    assert report["crowd_sensor_drift"]["signals"] == 1
    assert report["crowd_sensor_drift"]["horizons_sec"]["60"]["favorable"] == 1
    probe = report["bot_g_paper_validation"]["tiny_live_probe"]
    assert probe["status"] == "paper_observing"
    assert probe["approval_required"] is True
    assert probe["does_not_authorize_live"] is True
    assert probe["proposed_starting_trade_usd"] == 1.0


def test_render_markdown_contains_bot_f_sensor_note(tmp_path):
    now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    main_db = tmp_path / "main.db"
    bot_f_db = tmp_path / "bot_f.db"
    _make_main_db(main_db, now)
    _make_bot_f_db(bot_f_db, now)

    md = render_markdown(build_report(main_db, bot_f_db=bot_f_db, lookback_hours=24, now=now))

    assert "# Fast ROI Report" in md
    assert "Bot G Paper Validation" in md
    assert "Bot G Tiny-Live Probe Plan" in md
    assert "Does not authorize live" in md
    assert "Bot G $25 Capacity Labels" in md
    assert "Bot G Depletion/Reload Labels" in md
    assert "Crowd Sensor" in md
    assert "Crowd Signal Drift" in md
    assert "`bot_e`" in md
