"""Regression tests for Codex Bot E audit fixes (2026-04-16).

F1: trader consumes recorder pm_events, not synthetic midpoint trades
F2: live orders persisted + TTL cancel + reconcile wiring
F3: backtester bucket labels match trader's actual entry window
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from bots.bot_e_btc_scalp import __main__ as main_mod


# F1: _recent_recorder_trades reads from recorder DB
def test_recorder_trades_reader_returns_real_trades(tmp_path, monkeypatch):
    """Seed a fake recorder DB with last_trade_price events and verify
    the reader returns them as (ts_ms, asset_id, size) tuples."""
    db = tmp_path / "recorder.db"
    con = sqlite3.connect(db)
    con.execute("""
        CREATE TABLE pm_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at_ms INTEGER NOT NULL,
            subscription_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            asset_id TEXT,
            condition_id TEXT,
            payload_json TEXT NOT NULL
        )
    """)
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    con.executemany(
        "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, asset_id, payload_json) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (now_ms - 5000, "sub1", "last_trade_price", "yes_tok_1", '{"size": "10.5"}'),
            (now_ms - 4000, "sub1", "last_trade_price", "no_tok_1", '{"size": "5.25"}'),
            # Event outside token filter — should be skipped
            (now_ms - 3000, "sub1", "last_trade_price", "other_tok", '{"size": "100"}'),
            # Non-trade event — should be skipped
            (now_ms - 2000, "sub1", "price_change", "yes_tok_1", '{"size": "1"}'),
        ],
    )
    con.commit()
    con.close()

    monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(db))
    trades = main_mod._recent_recorder_trades(
        token_ids=["yes_tok_1", "no_tok_1"],
        since_ms=now_ms - 10000,
    )
    assert len(trades) == 2
    assert trades[0][1] == "yes_tok_1"
    assert trades[0][2] == Decimal("10.5")
    assert trades[1][1] == "no_tok_1"
    assert trades[1][2] == Decimal("5.25")


def test_recorder_trades_reader_empty_on_missing_db(monkeypatch):
    """Missing DB → return empty list silently (don't crash trader)."""
    monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", "/nonexistent/path/recorder.db")
    trades = main_mod._recent_recorder_trades(
        token_ids=["any_tok"], since_ms=0,
    )
    assert trades == []


def test_recorder_trades_reader_empty_token_list():
    """Empty token list → empty result (no DB query attempted)."""
    trades = main_mod._recent_recorder_trades(token_ids=[], since_ms=0)
    assert trades == []


# F2: _persist_order works for both paper and live
def test_persist_order_writes_live_order_to_db(tmp_db):
    """Live orders (status != PAPER_OPEN) must now be persisted."""
    from core.db import Order, get_session_factory
    from sqlalchemy import select

    order_id = main_mod._persist_order(
        order_id="live-order-xyz-123",
        condition_id="cid1",
        token_id="tok1",
        side="BUY_YES",
        price=Decimal("0.55"),
        size=Decimal("20"),
        status="live",
        strategy_signal="obi_1.0",
        reason_code="test",
        kelly_would_have=Decimal("30"),
    )
    assert order_id == "live-order-xyz-123"
    with get_session_factory()() as s:
        row = s.scalar(select(Order).where(Order.order_id == order_id))
        assert row is not None
        assert row.bot_id == "bot_e"
        assert row.status == "live"
        assert row.price == Decimal("0.55")


def test_persist_order_writes_paper_order_to_db(tmp_db):
    """Paper orders still work the same as before."""
    from core.db import Order, get_session_factory
    from sqlalchemy import select

    order_id = main_mod._persist_order(
        order_id="paper-abc",
        condition_id="cid2",
        token_id="tok2",
        side="BUY_NO",
        price=Decimal("0.45"),
        size=Decimal("15"),
        status="PAPER_OPEN",
        strategy_signal="obi_-1.0",
        reason_code="test",
        kelly_would_have=None,
    )
    assert order_id == "paper-abc"
    with get_session_factory()() as s:
        row = s.scalar(select(Order).where(Order.order_id == order_id))
        assert row is not None
        assert row.status == "PAPER_OPEN"


def test_cancel_stale_orders_cancels_old_open_orders(tmp_db):
    """Orders older than ttl_sec should be cancelled."""
    from core.db import Order, get_session_factory
    from sqlalchemy import select

    # Seed 3 Bot E orders: 2 stale, 1 fresh
    now = datetime.now(UTC)
    with get_session_factory()() as s:
        s.add(Order(
            order_id="stale-1", bot_id="bot_e", condition_id="c1", token_id="t1",
            side="BUY", price=Decimal("0.5"), size=Decimal("10"),
            status="live", order_type="GTC",
            placed_at=now - timedelta(seconds=120),
        ))
        s.add(Order(
            order_id="stale-2", bot_id="bot_e", condition_id="c2", token_id="t2",
            side="BUY", price=Decimal("0.5"), size=Decimal("10"),
            status="PAPER_OPEN", order_type="GTC",
            placed_at=now - timedelta(seconds=120),
        ))
        s.add(Order(
            order_id="fresh-1", bot_id="bot_e", condition_id="c3", token_id="t3",
            side="BUY", price=Decimal("0.5"), size=Decimal("10"),
            status="live", order_type="GTC",
            placed_at=now - timedelta(seconds=10),
        ))
        s.commit()

    mock_clob = MagicMock()
    mock_clob.cancel_order.return_value = True
    cancelled = main_mod._cancel_stale_orders(mock_clob, ttl_sec=60.0)
    assert cancelled == 2

    # Verify DB state
    with get_session_factory()() as s:
        stale1 = s.scalar(select(Order).where(Order.order_id == "stale-1"))
        stale2 = s.scalar(select(Order).where(Order.order_id == "stale-2"))
        fresh = s.scalar(select(Order).where(Order.order_id == "fresh-1"))
        assert stale1.status == "CANCELLED"
        assert stale2.status == "CANCELLED"
        assert fresh.status == "live"  # Untouched


# F3: bucket labels match trader's actual entry window
def test_bucket_labels_match_trader_entry_window():
    from core.backtest_bot_e import min_to_exp_bucket
    # 12 min was mislabelled as "5-10 (entry)" before — trader rejects this
    assert min_to_exp_bucket(12) == "10+ (pre-entry)"
    # 7 min IS in the actual entry zone (5-10 min)
    assert min_to_exp_bucket(7) == "5–10 (entry)"
    # 3 min is holding
    assert min_to_exp_bucket(3) == "0–5 (holding)"
    # After expiry
    assert min_to_exp_bucket(-0.5) == "resolution"
