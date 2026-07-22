"""Tests for the dashboard's Maker Flow query and archived Bot F surface.

Maker Flow queries must:
- Return a coherent shape when their backing DB is missing (`db_exists=False`).
- Compute headline metrics correctly when seeded with a small fixture DB.
- Be safe to call from the overview tile path (no exceptions on partial data).

Legacy Bot F data remains available to reports as shared crowd-sensor input, but
Bot F is no longer an active dashboard tab or API surface.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from bots.bot_e_recorder.schema import init_db as init_bot_e_db
from core.db import Order, Trade, get_session_factory


@pytest.fixture(autouse=True)
def detailed_dashboard_tabs(monkeypatch):
    monkeypatch.setenv("DASHBOARD_DETAILED_BOT_TABS", "true")


# -----------------------------------------------------------------------------
# Fixtures: seeded recorder DB
# -----------------------------------------------------------------------------


@pytest.fixture
def seeded_bot_e_db(tmp_path: Path) -> Path:
    db = tmp_path / "bot_e_recorder.db"
    conn = init_bot_e_db(db)
    try:
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        # 5 events on one subscription, 3 on another, all in last 5 min
        for i in range(5):
            conn.execute(
                "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, "
                "asset_id, condition_id, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                (now_ms - 60_000 + i * 1000, "btc-2026-04-16T1200", "book", "tok1", "c1",
                 json.dumps({"event_type": "book"})),
            )
        for i in range(3):
            conn.execute(
                "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, "
                "asset_id, condition_id, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
                (now_ms - 30_000 + i * 1000, "eth-2026-04-16T1205", "price_change", "tok2", "c2",
                 json.dumps({"event_type": "price_change", "price": 0.5})),
            )
        # Some CEX trades
        for i in range(20):
            conn.execute(
                "INSERT INTO cex_trades (received_at_ms, trade_time_ms, symbol, "
                "price, size, is_buyer_maker) VALUES (?, ?, ?, ?, ?, ?)",
                (now_ms - 10_000 + i * 100, now_ms - 10_000 + i * 100,
                 "BTCUSDT", 85000.0, 0.001, 1),
            )
        # Markets snapshot — single scan with 2 markets
        scan_at = now_ms - 5000
        for i, (cond, q) in enumerate([("c1", "Bitcoin Up or Down 12:00"), ("c2", "ETH Up or Down 12:05")]):
            conn.execute(
                "INSERT INTO markets (scan_at_ms, condition_id, question, end_date_iso, "
                "yes_token_id, no_token_id, volume_24h_usd, yes_price, category, raw_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (scan_at, cond, q, "2026-04-16T12:00:00+00:00",
                 f"yes-{i}", f"no-{i}", 1234.5, 0.5, "crypto", "{}"),
            )
        # Heartbeats
        for source in ("pm", "cex", "discovery"):
            conn.execute(
                "INSERT INTO heartbeats (emitted_at_ms, source, subscription_id, "
                "last_message_age_sec, metadata_json) VALUES (?, ?, ?, ?, ?)",
                (now_ms - 1000, source, "sub", 5.0, None),
            )
        conn.commit()
    finally:
        conn.close()
    return db


# -----------------------------------------------------------------------------
# query_bot_e
# -----------------------------------------------------------------------------


def test_query_bot_e_handles_missing_db(monkeypatch, tmp_path):
    monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(tmp_path / "doesnt_exist.db"))
    monkeypatch.setenv("BOT_E_CALIBRATION_GO_PATH", str(tmp_path / "no_cal.json"))
    monkeypatch.setenv("BOT_E_INITIAL_USD", "0")
    monkeypatch.delenv("BOT_E_BANKROLL_USD", raising=False)
    from dashboard import runtime_queries
    payload = runtime_queries.query_bot_e()
    assert payload["recorder"]["db_exists"] is False
    assert payload["recorder"]["calibration_ready"] is False
    assert payload["recorder"]["status"] == "no_db"
    assert payload["trader"]["bankroll_usd"] == "0"


def test_query_bot_e_with_seeded_db(monkeypatch, seeded_bot_e_db, tmp_db):
    monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(seeded_bot_e_db))
    monkeypatch.setenv("BOT_E_CALIBRATION_GO_PATH", str(seeded_bot_e_db.parent / "no_cal.json"))
    now = datetime.now(UTC)
    sf = get_session_factory()
    with sf() as session:
        session.add_all([
            Order(
                order_id="ord-e-live-buy",
                bot_id="bot_e",
                condition_id="e1",
                token_id="tok-e1",
                side="BUY",
                price=0.40,
                size=10,
                status="FILLED",
                placed_at=now - timedelta(minutes=3),
                last_updated=now - timedelta(minutes=3),
            ),
            Order(
                order_id="ord-e-live-sell",
                bot_id="bot_e",
                condition_id="e1",
                token_id="tok-e1",
                side="SELL",
                price=0.55,
                size=10,
                status="FILLED",
                placed_at=now - timedelta(minutes=2),
                last_updated=now - timedelta(minutes=2),
            ),
            Order(
                order_id="paper-e-fill",
                bot_id="bot_e",
                condition_id="e2",
                token_id="tok-e2",
                side="BUY",
                price=0.48,
                size=8,
                status="FILLED",
                placed_at=now - timedelta(minutes=1),
                last_updated=now - timedelta(minutes=1),
            ),
            Order(
                order_id="paper-e-open",
                bot_id="bot_e",
                condition_id="e3",
                token_id="tok-e3",
                side="BUY",
                price=0.50,
                size=10,
                status="PAPER_OPEN",
                placed_at=now,
                last_updated=now,
            ),
            Trade(
                trade_id="trd-e-live-buy",
                bot_id="bot_e",
                order_id="ord-e-live-buy",
                condition_id="e1",
                token_id="tok-e1",
                side="BUY",
                price=0.40,
                size=10,
                fee_usd=0,
                filled_at=now - timedelta(minutes=3),
                usd_gbp_rate=Decimal("0.80"),
                gbp_notional=Decimal("3.20"),
            ),
            Trade(
                trade_id="trd-e-live-sell",
                bot_id="bot_e",
                order_id="ord-e-live-sell",
                condition_id="e1",
                token_id="tok-e1",
                side="SELL",
                price=0.55,
                size=10,
                fee_usd=0,
                filled_at=now - timedelta(minutes=2),
                usd_gbp_rate=Decimal("0.80"),
                gbp_notional=Decimal("4.40"),
            ),
            Trade(
                trade_id="paper-fill-e2",
                bot_id="bot_e",
                order_id="paper-e-fill",
                condition_id="e2",
                token_id="tok-e2",
                side="BUY",
                price=0.48,
                size=8,
                fee_usd=0,
                filled_at=now - timedelta(minutes=1),
                usd_gbp_rate=Decimal("0.80"),
                gbp_notional=Decimal("3.07"),
            ),
        ])
        session.commit()
    from dashboard import runtime_queries
    payload = runtime_queries.query_bot_e()
    rec = payload["recorder"]
    trader = payload["trader"]
    assert rec["db_exists"] is True
    assert rec["counts"]["pm_events"] == 8
    assert rec["counts"]["cex_trades"] == 20
    assert rec["counts"]["markets"] == 2
    assert rec["counts"]["heartbeats"] == 3
    # Active subs computed from last 5 min
    assert len(rec["active_subscriptions"]) == 2
    assert rec["active_subscriptions"][0]["n"] >= 1
    # Latest markets includes both
    assert len(rec["latest_markets"]) == 2
    questions = {m["question"] for m in rec["latest_markets"]}
    assert "Bitcoin Up or Down 12:00" in questions
    # Capture timestamps populated
    assert rec["capture"]["pm_events_per_min"] >= 0
    assert rec["capture"]["seconds_since_last_event"] is not None
    assert trader["order_total"] == 4
    assert trader["paper_open_count"] == 1
    assert trader["order_metrics"]["open_orders"] == 1
    assert trader["order_metrics"]["paper_open_orders"] == 1
    assert trader["order_metrics"]["reserved_notional_usd"] == pytest.approx(5.0)
    assert trader["trade_metrics"]["filled_trades_count"] == 3
    assert trader["trade_metrics"]["paper_fills_count"] == 1
    assert trader["trade_metrics"]["live_fills_count"] == 2
    assert trader["trade_metrics"]["sell_fills_count"] == 1
    assert trader["trade_metrics"]["win_rate_pct"] == pytest.approx(100.0)
    assert trader["recent_trades"][0]["execution_mode"] == "paper"
    assert trader["recent_trades"][1]["execution_mode"] == "live"


def test_retained_bot_e_recorder_tile_helper(monkeypatch, seeded_bot_e_db):
    monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(seeded_bot_e_db))
    from dashboard import runtime_queries
    tile = runtime_queries._overview_bot_e_tile()
    assert tile["pm_events"] == 8
    assert tile["cex_trades"] == 20
    assert tile["markets"] == 2
    assert tile["n_active_subscriptions"] == 2
    assert tile["fresh"] is True


# -----------------------------------------------------------------------------
# Routes integration: dashboard server exposes retained recorders, not legacy F
# -----------------------------------------------------------------------------


def test_routes_expose_bot_e_recorder_but_archive_bot_f():
    from dashboard import server
    assert "/api/bot-e" in server.ROUTES
    assert "/api/bot-f" not in server.ROUTES
    assert "/api/bot-d" in server.ROUTES


# -----------------------------------------------------------------------------
# Active dashboard inventory
# -----------------------------------------------------------------------------


def test_services_list_keeps_recorder_and_archives_trader_bot_f():
    """Active dashboard inventory keeps Bot E recorder but excludes retired trader."""
    from dashboard import runtime_queries
    assert "polymarket-bot-e-recorder" in runtime_queries.SERVICES
    assert "polymarket-bot-e-trader" not in runtime_queries.SERVICES
    assert "polymarket-bot-f-mirror" not in runtime_queries.SERVICES
    assert "polymarket-bot-f-paper-mirror" not in runtime_queries.SERVICES
    assert "polymarket-bot-f-hunter" not in runtime_queries.TIMER_SERVICES
    assert "polymarket-dashboard" in runtime_queries.SERVICES


def test_services_summary_counts_active_and_degraded_services(monkeypatch, tmp_db):
    """Overview service summary tracks the current active dashboard inventory."""
    from dashboard import runtime_queries
    monkeypatch.setattr(runtime_queries, "service_states", lambda: {
        "polymarket-bot-g-prime": "active",
        "polymarket-bot-e-recorder": "active",
        "polymarket-bot-c": "failed",  # one genuine fail
    })
    monkeypatch.setattr(runtime_queries, "_fetch_balances_uncached",
                         lambda: {"pol": "0", "usdce": "0", "fetched_at": "2026-04-16T00:00:00+00:00"})
    overview = runtime_queries.query_overview()
    summary = overview["services_summary"]
    assert summary["active"] == 2
    assert summary["degraded"] == 1


def test_query_state_archives_bot_e_and_bot_f(monkeypatch, tmp_db, seeded_bot_e_db):
    """Legacy /api/state follows the current dashboard surface."""
    monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(seeded_bot_e_db))
    monkeypatch.setattr("dashboard.runtime_queries._fetch_balances_uncached",
                         lambda: {"pol": "0", "usdce": "0", "fetched_at": "2026-04-16T00:00:00+00:00"})
    monkeypatch.setattr("dashboard.runtime_queries.service_states",
                         lambda: {"polymarket-bot-e-recorder": "active"})
    from dashboard import runtime_queries
    state = runtime_queries.query_state()
    assert "bot_e" not in state
    assert "bot_f" not in state


def test_risk_summary_splits_positions_from_reserved_orders():
    """Audit Finding 2: the headline 'current_exposure_usd' was positions
    plus open orders, but the breakdown only iterated positions. Now we
    expose both fields so the UI can show the split.

    Scenario: positions cost basis = $30, but portfolio total exposure
    (positions + reserved buys) = $50 → reserved_orders_usd should equal $20.
    """
    from dashboard.runtime_queries import _risk_summary
    open_positions = [
        {"bot_id": "bot_a", "cost_basis_usd": 10.0, "market": "M1", "side": "YES",
         "size": 100, "entry_price": "0.10", "current_price": "0.11", "pnl_usd": 1.0},
        {"bot_id": "bot_b", "cost_basis_usd": 20.0, "market": "M2", "side": "NO",
         "size": 50, "entry_price": "0.40", "current_price": "0.41", "pnl_usd": 0.5},
    ]
    pnl_project = {"exposure_usd": "50.00"}  # i.e. $20 of resting orders
    risk = _risk_summary(open_positions, pnl_project)
    assert risk["positions_exposure_usd"] == 30.0
    assert risk["reserved_orders_usd"] == 20.0
    # Backwards-compat: the original headline value still exposed
    assert risk["current_exposure_usd"] == "50.00"
    # exposure_by_bot still iterates only positions
    eb = {row["bot_id"]: row["exposure_usd"] for row in risk["exposure_by_bot"]}
    assert eb["bot_a"] == 10.0
    assert eb["bot_b"] == 20.0


def test_risk_summary_negative_reserve_clamped_to_zero():
    """Defensive: if portfolio reports lower total than position sum (data
    inconsistency window), reserved_orders should clamp to 0 not go negative."""
    from dashboard.runtime_queries import _risk_summary
    open_positions = [
        {"bot_id": "bot_a", "cost_basis_usd": 100.0, "market": "M1", "side": "YES",
         "size": 100, "entry_price": "1.00", "current_price": "1.00", "pnl_usd": 0.0},
    ]
    pnl_project = {"exposure_usd": "50.00"}  # total < positions (shouldn't happen but guard)
    risk = _risk_summary(open_positions, pnl_project)
    assert risk["positions_exposure_usd"] == 100.0
    assert risk["reserved_orders_usd"] == 0.0  # clamped, not -50


def test_trade_metrics_matches_partial_sells_to_closed_round_trips(tmp_db):
    from dashboard.runtime_queries import _trade_metrics

    now = datetime.now(UTC)
    sf = get_session_factory()
    with sf() as session:
        session.add_all([
            Order(order_id="ord-1", bot_id="bot_x", condition_id="c1", token_id="tok1", side="BUY",
                  price=Decimal("0.40"), size=Decimal("10"), status="FILLED", placed_at=now, last_updated=now),
            Order(order_id="ord-2", bot_id="bot_x", condition_id="c1", token_id="tok1", side="SELL",
                  price=Decimal("0.50"), size=Decimal("5"), status="FILLED", placed_at=now, last_updated=now),
            Order(order_id="ord-3", bot_id="bot_x", condition_id="c1", token_id="tok1", side="SELL",
                  price=Decimal("0.30"), size=Decimal("5"), status="FILLED", placed_at=now, last_updated=now),
            Trade(trade_id="buy-1", bot_id="bot_x", order_id="ord-1", condition_id="c1", token_id="tok1",
                  side="BUY", price=Decimal("0.40"), size=Decimal("10"), fee_usd=Decimal("0"),
                  filled_at=now - timedelta(minutes=3), usd_gbp_rate=Decimal("0.80"), gbp_notional=Decimal("3.20")),
            Trade(trade_id="sell-1", bot_id="bot_x", order_id="ord-2", condition_id="c1", token_id="tok1",
                  side="SELL", price=Decimal("0.50"), size=Decimal("5"), fee_usd=Decimal("0"),
                  filled_at=now - timedelta(minutes=2), usd_gbp_rate=Decimal("0.80"), gbp_notional=Decimal("2.00")),
            Trade(trade_id="sell-2", bot_id="bot_x", order_id="ord-3", condition_id="c1", token_id="tok1",
                  side="SELL", price=Decimal("0.30"), size=Decimal("5"), fee_usd=Decimal("0"),
                  filled_at=now - timedelta(minutes=1), usd_gbp_rate=Decimal("0.80"), gbp_notional=Decimal("1.20")),
        ])
        session.commit()

    metrics = _trade_metrics("bot_x")
    assert metrics["closed_trades"] == 2
    assert metrics["wins"] == 1
    assert metrics["win_rate_pct"] == pytest.approx(50.0)
    assert metrics["realised_pnl_usd"] == pytest.approx(0.0)
