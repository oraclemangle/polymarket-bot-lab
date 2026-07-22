from __future__ import annotations

import csv
import json
import sqlite3
from datetime import UTC, datetime, timedelta

from scripts.bot_d_candidate_quality_report import build_report, render_markdown


def _dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _make_db(path, now: datetime) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE events (
            bot_id TEXT,
            event_type TEXT,
            severity TEXT,
            message TEXT,
            payload TEXT,
            created_at TEXT
        );
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
        );
        CREATE TABLE trades (
            trade_id TEXT,
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            filled_at TEXT
        );
        """
    )
    veto_payload = {
        "city": "Atlanta",
        "date": "2026-05-03",
        "temp_type": "high",
        "bucket_low_f": 80,
        "bucket_high_f": 83,
        "condition_id": "gamma-atl",
        "settlement_verified": True,
        "forecast_source": "multi_model",
        "ensemble_count": 5,
        "market_probability": 0.25,
        "gfs_probability": 0.45,
        "net_edge": 0.20,
        "nws_disagreement_f": 2.6,
        "veto_threshold_f": 2.0,
    }
    entry_payload = {
        "city": "NYC",
        "date": "2026-05-03",
        "temp_type": "high",
        "bucket_low_f": 73,
        "bucket_high_f": 77,
        "condition_id": "gamma-nyc",
        "settlement_verified": True,
        "forecast_source": "multi_model",
        "ensemble_count": 5,
        "market_probability": 0.30,
        "gfs_probability": 0.42,
        "net_edge": 0.12,
        "side": "BUY_YES",
        "limit_price": "0.31",
    }
    scan_payload = {
        "raw_markets": 20,
        "kept_markets": 14,
        "evaluated": 11,
        "non_skip": 0,
        "tradeable": 0,
        "skip_reasons": {"below_threshold": 7, "nws_disagrees": 4},
        "forecast_sources": {"multi_model": 11},
        "nws_shadow": {
            "current_floor_f": 3.0,
            "vetoed": 4,
            "would_clear_edge_floor_3f": 1,
            "would_clear_edge_floor_4f": 2,
            "would_clear_edge_nws_off": 4,
            "would_tradeable_floor_3f": 0,
            "would_tradeable_floor_4f": 1,
            "would_tradeable_nws_off": 2,
        },
    }
    for event_type, payload in (
        ("bot_d.nws_veto", veto_payload),
        ("bot_d.forecast_entry", entry_payload),
        ("bot_d.scan_summary", scan_payload),
    ):
        conn.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
            ("bot_d", event_type, "info", "", json.dumps(payload), _dt(now - timedelta(minutes=5))),
        )
    conn.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("o1", "bot_d_live_probe", "gamma-live", "yes", "BUY", 0.5, 5, "OPEN", _dt(now - timedelta(minutes=3))),
    )
    conn.execute(
        "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("t1", "bot_d_live_probe", "gamma-live", "yes", "BUY", 0.5, 5, _dt(now - timedelta(minutes=2))),
    )
    conn.commit()
    conn.close()


def test_candidate_quality_report_grades_candidates_and_scan_shadow(tmp_path):
    now = datetime(2026, 5, 3, 12, tzinfo=UTC)
    db = tmp_path / "main.db"
    _make_db(db, now)

    report = build_report(db, now=now, lookback_hours=24)

    assert report["candidates"]["count"] == 2
    assert report["candidates"]["entries"] == 1
    assert report["candidates"]["vetoes"] == 1
    assert report["candidates"]["by_setup_tier"] == {"A": 1, "B": 1}
    assert report["candidates"]["by_nws_lane"] == {"entry": 1, "would_clear_3f": 1}
    assert report["candidates"]["by_skip_reason_code"] == {
        "entry_signal": 1,
        "nws_disagrees": 1,
    }
    assert report["candidates"]["by_source_confidence"] == {"uncertain": 2}
    assert report["candidates"]["veto_shadow"]["would_clear_floor_3f"] == 1
    assert report["scans"]["nws_shadow_totals"]["would_tradeable_floor_4f"] == 1
    assert report["orders"]["open_orders"] == 1
    assert report["trades"]["fills"] == 1
    assert report["recommendation"]["status"] == "review_live_fills"


def test_candidate_quality_report_surfaces_live_attempt_root_cause(tmp_path):
    now = datetime(2026, 5, 3, 12, tzinfo=UTC)
    db = tmp_path / "main.db"
    _make_db(db, now)
    conn = sqlite3.connect(db)
    attempt_payload = {
        "city": "Dallas",
        "date": "2026-05-03",
        "temp_type": "high",
        "bucket_low_f": 80,
        "bucket_high_f": 83,
        "condition_id": "gamma-dal",
        "settlement_verified": True,
        "forecast_source": "multi_model",
        "market_probability": 0.20,
        "gfs_probability": 0.38,
        "net_edge": 0.18,
        "entry_attempt_reason": "live_order_notional_cap",
        "depth_usd": "42.5",
        "required_depth_usd": "25",
    }
    conn.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
        (
            "bot_d_live_probe",
            "bot_d.entry_attempt",
            "info",
            "",
            json.dumps(attempt_payload),
            _dt(now - timedelta(minutes=1)),
        ),
    )
    conn.commit()
    conn.close()

    report = build_report(db, now=now, lookback_hours=24)

    assert report["candidates"]["live_entry_attempts"] == 1
    assert report["candidates"]["live_entry_attempt_reasons"] == {
        "live_order_notional_cap": 1
    }
    assert report["candidates"]["by_depth_lane"]["depth_25_to_50"] == 1


def test_candidate_quality_report_can_join_public_trade_tape(tmp_path):
    now = datetime(2026, 5, 3, 12, tzinfo=UTC)
    db = tmp_path / "main.db"
    _make_db(db, now)
    tape = tmp_path / "trades.csv"
    with tape.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["market_id", "price", "usd_amount"])
        writer.writeheader()
        writer.writerow({"market_id": "gamma-atl", "price": "0.27", "usd_amount": "19.5"})
        writer.writerow({"market_id": "gamma-atl", "price": "0.31", "usd_amount": "21.0"})

    report = build_report(db, now=now, lookback_hours=24, trade_tape_csv=tape)

    assert report["candidates"]["trade_tape_matched_candidates"] == 1
    top = report["candidates"]["top_candidates"]
    atl = next(row for row in top if row["condition_id"] == "gamma-atl")
    assert atl["trade_tape"]["trade_count"] == 2
    assert atl["trade_tape"]["usd_amount"] == 40.5
    assert atl["trade_tape"]["last_price"] == 0.31


def test_candidate_quality_markdown_contains_recommendation(tmp_path):
    now = datetime(2026, 5, 3, 12, tzinfo=UTC)
    db = tmp_path / "main.db"
    _make_db(db, now)

    md = render_markdown(build_report(db, now=now, lookback_hours=24))

    assert "# Bot D Candidate-Quality Report" in md
    assert "## Recommendation" in md
    assert "Setup tiers" in md
    assert "Latest Scan" in md
