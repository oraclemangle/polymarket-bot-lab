from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

from scripts import quantstats_bot_tearsheet as qbt


def _seed_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE trades (
            trade_id TEXT PRIMARY KEY,
            bot_id TEXT,
            order_id TEXT,
            condition_id TEXT,
            token_id TEXT,
            side TEXT,
            price NUMERIC,
            size NUMERIC,
            fee_usd NUMERIC,
            filled_at TEXT,
            usd_gbp_rate NUMERIC,
            gbp_notional NUMERIC
        );
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            bot_id TEXT,
            event_type TEXT,
            severity TEXT,
            message TEXT,
            payload TEXT,
            created_at TEXT
        );
        """
    )
    rows = [
        ("b1", "bot_x", "o1", "c1", "tok", "BUY_YES", 0.20, 10, 0.20, "2026-05-01T01:00:00+00:00", 0.8, 1.6),
        ("s1", "bot_x", "o2", "c1", "tok", "SELL_NO", 0.50, 5, 0.10, "2026-05-02T01:00:00+00:00", 0.8, 2.0),
        ("s2", "bot_x", "o3", "c1", "tok", "SELL", 0.10, 5, 0.00, "2026-05-03T01:00:00+00:00", 0.8, 0.4),
        ("other", "bot_y", "o4", "c1", "tok", "BUY", 0.20, 10, 0, "2026-05-01T01:00:00+00:00", 0.8, 1.6),
    ]
    conn.executemany("INSERT INTO trades VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    payload = {"realised_usd": "0.75", "cost_basis": "0.25"}
    conn.execute(
        "INSERT INTO events VALUES (?,?,?,?,?,?,?)",
        (
            1,
            "bot_x",
            "portfolio.redeem",
            "info",
            "redeem",
            json.dumps(payload),
            "2026-05-04T01:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()


def test_load_realised_events_uses_fifo_fees_and_redeems(tmp_path):
    db = tmp_path / "main.db"
    _seed_db(db)

    events, diagnostics = qbt.load_realised_events(db, "bot_x")

    assert diagnostics["trade_rows"] == 3
    assert diagnostics["redeem_events"] == 1
    assert [event.source for event in events] == [
        "trade_fifo",
        "trade_fifo",
        "portfolio_redeem",
    ]
    assert events[0].pnl_usd == Decimal("1.30")
    assert events[0].entry_cost_usd == Decimal("1.10")
    assert events[1].pnl_usd == Decimal("-0.60")
    assert events[2].pnl_usd == Decimal("0.75")


def test_build_summary_uses_closed_cost_fallback_and_monthly_returns(tmp_path):
    db = tmp_path / "main.db"
    _seed_db(db)
    events, diagnostics = qbt.load_realised_events(db, "bot_x")
    capital_base, source = qbt.infer_capital_base(events, None)

    summary, periods = qbt.build_summary(
        bot_id="bot_x",
        events=events,
        diagnostics=diagnostics,
        period="daily",
        capital_base_usd=capital_base,
        capital_base_source=source,
        simulations=100,
        bust_drawdown_pct=Decimal("0.50"),
        seed=1,
    )

    assert capital_base == Decimal("2.45")
    assert summary["capital_base_source"] == "closed_entry_cost_fallback"
    assert summary["total_realised_pnl_usd"] == 1.45
    assert summary["trade_level_roi_pct"] == 59.1837
    assert summary["monthly_returns"]["2026-05"] == 0.509575
    assert len(periods) == 3


def test_write_artifacts_falls_back_without_quantstats(tmp_path, monkeypatch):
    db = tmp_path / "main.db"
    _seed_db(db)
    events, diagnostics = qbt.load_realised_events(db, "bot_x")
    capital_base, source = qbt.infer_capital_base(events, Decimal("10"))
    summary, periods = qbt.build_summary(
        bot_id="bot_x",
        events=events,
        diagnostics=diagnostics,
        period="daily",
        capital_base_usd=capital_base,
        capital_base_source=source,
        simulations=10,
        bust_drawdown_pct=Decimal("0.50"),
        seed=1,
    )
    monkeypatch.setattr(qbt, "_import_quantstats", lambda: (None, None))

    json_path, html_path = qbt.write_artifacts(
        summary=summary,
        periods=periods,
        out_dir=tmp_path / "reports",
        benchmark_csv=None,
        require_quantstats=False,
    )

    assert json_path.exists()
    assert html_path.exists()
    payload = json.loads(json_path.read_text())
    assert payload["quantstats_available"] is False
    assert "Fallback report" in html_path.read_text()


def test_since_until_window_filters_realised_events(tmp_path):
    db = tmp_path / "main.db"
    _seed_db(db)

    events, _ = qbt.load_realised_events(
        db,
        "bot_x",
        since=datetime(2026, 5, 3, tzinfo=UTC),
        until=datetime(2026, 5, 4, tzinfo=UTC),
    )

    assert len(events) == 1
    assert events[0].pnl_usd == Decimal("-0.60")
