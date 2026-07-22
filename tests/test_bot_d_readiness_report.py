from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from scripts.bot_d_readiness_report import build_report, render_markdown


def _make_db(path, now: datetime) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
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
        );
        CREATE TABLE markets (
            condition_id TEXT PRIMARY KEY,
            end_date TEXT
        );
        CREATE TABLE positions (
            bot_id TEXT,
            condition_id TEXT,
            cost_basis_usd REAL,
            opened_at TEXT,
            status TEXT
        );
        CREATE TABLE trades (
            bot_id TEXT,
            price REAL,
            size REAL,
            filled_at TEXT
        );
        CREATE TABLE events (
            bot_id TEXT,
            event_type TEXT,
            created_at TEXT
        );
        """
    )
    fresh = now - timedelta(hours=4)
    stale = now - timedelta(days=4)
    conn.execute(
        "INSERT INTO markets VALUES (?, ?)",
        ("daily", (fresh + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.execute(
        "INSERT INTO markets VALUES (?, ?)",
        ("weekly", (stale + timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("o1", "bot_d", "daily", "t1", "BUY", 0.1, 50, "PAPER_OPEN", fresh),
    )
    conn.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("o2", "bot_d", "weekly", "t2", "BUY", 0.2, 40, "PAPER_OPEN", stale),
    )
    conn.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("o3", "bot_d", "missing", "t3", "BUY", 0.3, 10, "PAPER_OPEN", fresh),
    )
    conn.execute(
        "INSERT INTO positions VALUES (?, ?, ?, ?, ?)",
        ("bot_d", "weekly", 8.0, stale, "OPEN"),
    )
    conn.execute(
        "INSERT INTO events VALUES (?, ?, ?)",
        ("bot_d", "bot_d.nws_veto", now.strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def test_bot_d_readiness_report_flags_lockup_and_stale_state(tmp_path):
    now = datetime(2026, 5, 1, 12, tzinfo=UTC)
    db = tmp_path / "main.db"
    _make_db(db, now)

    report = build_report(db, now=now)

    assert report["open_orders"]["count"] == 3
    assert report["open_orders"]["notional"] == 16.0
    assert report["open_orders"]["by_duration"]["daily_low_lockup"]["count"] == 1
    assert report["open_orders"]["by_duration"]["weekly_lockup"]["count"] == 1
    assert report["open_orders"]["missing_market_count"] == 1
    assert report["open_orders"]["stale_48h_count"] == 1
    assert report["open_positions"]["stale_48h_count"] == 1
    assert report["readiness"]["wallet_priority"] is True
    assert report["readiness"]["live_ready"] is False
    assert "stale_open_state" in report["readiness"]["blockers"]
    assert "weekly_lockup_present" in report["readiness"]["blockers"]
    assert report["station_coverage"]["total"] > 0
    assert "NYC" not in report["station_coverage"]["missing_station"]
    assert report["entry_policy"]["require_verified_settlement"] is True
    assert report["entry_policy"]["require_known_end_date"] is True
    assert report["entry_policy"]["max_lockup_hours"] == 48.0
    assert report["entry_policy"]["depth_gate_enabled"] is True
    assert report["entry_policy"]["min_entry_depth_usd"] == 25.0
    assert report["entry_policy"]["require_wave_for_entry"] is True
    assert report["entry_policy"]["live_authorized"] is False
    assert report["entry_policy"]["allow_nws_fallback_entry"] is False
    assert report["entry_policy"]["paper_exit_slippage_bps"] == 50.0
    assert report["entry_policy"]["live_exit_limit_offset"] == 0.005
    assert report["entry_policy"]["exit_stale_min"] == 10
    assert "NYC" in report["entry_policy"]["eligible_verified_cities"]
    assert "live_authorization_missing" in report["readiness"]["blockers"]


def test_bot_d_readiness_markdown_contains_verdict(tmp_path):
    now = datetime(2026, 5, 1, 12, tzinfo=UTC)
    db = tmp_path / "main.db"
    _make_db(db, now)

    md = render_markdown(build_report(db, now=now))

    assert "# Bot D Wallet-Readiness Report" in md
    assert "Wallet priority: `True`" in md
    assert "Live ready: `False`" in md
    assert "Station Coverage" in md
    assert "Entry Policy" in md


def test_bot_d_readiness_surfaces_skewnorm_fallback_blocker(tmp_path):
    now = datetime(2026, 5, 1, 12, tzinfo=UTC)
    db = tmp_path / "main.db"
    _make_db(db, now)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO events VALUES (?, ?, ?)",
        ("bot_d", "bot_d.skewnorm_fallback", now.strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()

    report = build_report(db, now=now)

    assert report["recent_events"]["bot_d.skewnorm_fallback"] == 1
    assert "skewnorm_fallback_recent" in report["readiness"]["blockers"]


def test_bot_d_readiness_reports_forecast_depth_and_daily_pnl(tmp_path):
    now = datetime(2026, 5, 1, 12, tzinfo=UTC)
    db = tmp_path / "main.db"
    conn = sqlite3.connect(db)
    conn.executescript(
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
        );
        CREATE TABLE markets (
            condition_id TEXT PRIMARY KEY,
            end_date TEXT
        );
        CREATE TABLE positions (
            bot_id TEXT,
            condition_id TEXT,
            cost_basis_usd REAL,
            opened_at TEXT,
            status TEXT
        );
        CREATE TABLE trades (
            bot_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price REAL,
            size REAL,
            filled_at TEXT
        );
        CREATE TABLE events (
            bot_id TEXT,
            event_type TEXT,
            created_at TEXT,
            payload TEXT
        );
        CREATE TABLE books (
            token_id TEXT,
            snapshot_at TEXT,
            bids TEXT,
            asks TEXT
        );
        """
    )
    buy_ts = now - timedelta(hours=2)
    sell_ts = now - timedelta(hours=1)
    conn.execute(
        "INSERT INTO markets VALUES (?, ?)",
        ("daily", (buy_ts + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.execute(
        "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("bot_d", "daily", "yes-token", "BUY", 0.2, 10, buy_ts.strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.execute(
        "INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("bot_d", "daily", "yes-token", "SELL", 1.0, 10, sell_ts.strftime("%Y-%m-%d %H:%M:%S")),
    )
    payload = {
        "city": "NYC",
        "date": "2026-05-01",
        "side": "BUY_YES",
        "yes_token_id": "yes-token",
        "no_token_id": "no-token",
        "limit_price": "0.20",
        "gfs_probability": 0.7,
        "market_probability": 0.2,
        "empirical_probability": 0.6,
        "settlement_station": "KLGA",
        "observation_station": "KLGA",
        "settlement_source": "wunderground",
        "settlement_rounding": "nearest_int",
        "settlement_unit": "F",
        "settlement_verified": True,
        "forecast_source": "multi_model",
        "forecast_fetched_at": now.isoformat(),
        "forecast_model_timestamp": (now - timedelta(hours=3)).isoformat(),
    }
    conn.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?)",
        (
            "bot_d",
            "bot_d.forecast_entry",
            now.strftime("%Y-%m-%d %H:%M:%S"),
            json.dumps(payload),
        ),
    )
    scan_payload = {
        "raw_markets": 16,
        "kept_markets": 11,
        "evaluated": 11,
        "missing_forecasts": 0,
        "non_skip": 0,
        "tradeable": 0,
        "forecast_sources": {"nws_fallback": 11},
        "skip_reasons": {"below_threshold": 9, "observed_constraint": 2},
        "top_positive_net_edge": 0.035,
        "top_abs_net_edge": 0.035,
    }
    conn.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?)",
        (
            "bot_d",
            "bot_d.scan_summary",
            now.strftime("%Y-%m-%d %H:%M:%S"),
            json.dumps(scan_payload),
        ),
    )
    conn.execute(
        "INSERT INTO books VALUES (?, ?, ?, ?)",
        (
            "yes-token",
            now.strftime("%Y-%m-%d %H:%M:%S.%f"),
            json.dumps([["0.19", "5"]]),
            json.dumps([["0.20", "150"]]),
        ),
    )
    conn.commit()
    conn.close()

    report = build_report(db, now=now)

    fc = report["forecast_entries"]
    assert fc["count"] == 1
    assert fc["latest_has_station_fields"] is True
    assert fc["latest_has_forecast_fields"] is True
    assert fc["avg_abs_edge"] == 0.5
    assert fc["avg_probability_disagreement"] == 0.1
    assert fc["model_age_buckets"]["fresh_lte_6h"] == 1
    assert fc["forecast_sources"] == {"multi_model": 1}
    assert fc["depth"]["targets_usd"]["25"]["covered"] == 1
    assert fc["depth"]["targets_usd"]["50"]["covered"] == 0
    assert report["recent_events"]["bot_d.scan_summary"] == 1
    assert report["latest_scan_summary"]["evaluated"] == 11
    assert report["latest_scan_summary"]["skip_reasons"]["below_threshold"] == 9
    assert "insufficient_depth_sample" in report["readiness"]["blockers"]
    assert "insufficient_resolved_sample" in report["readiness"]["blockers"]
    assert "Latest Scan" in render_markdown(report)
    assert report["resolved_pnl"]["daily_low_lockup"]["closed"] == 1
    assert report["resolved_pnl"]["daily_low_lockup"]["roi_pct"] == 400.0
