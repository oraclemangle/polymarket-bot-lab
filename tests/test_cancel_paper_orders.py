"""Tests for scripts/cancel_paper_orders.py.

Covers the pure DB-logic core: dry run is no-op, execute flips
bankroll-reserving statuses to CANCELLED, audit events are emitted,
the script is idempotent, and bots are correctly isolated by ``bot_id``.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.db import Base, Event, Market, Order

_SPEC = importlib.util.spec_from_file_location(
    "cancel_paper_orders",
    Path(__file__).resolve().parent.parent / "scripts" / "cancel_paper_orders.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["cancel_paper_orders"] = _mod
_SPEC.loader.exec_module(_mod)


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _add_order(s, *, order_id: str, bot_id: str, status: str,
               side: str = "BUY", price: str = "0.5", size: str = "10",
               condition_id: str = "cid", placed_at: datetime | None = None):
    placed_at = placed_at or datetime.now(timezone.utc)
    s.add(Order(
        order_id=order_id,
        bot_id=bot_id,
        condition_id=condition_id,
        token_id="tok",
        side=side,
        price=Decimal(price),
        size=Decimal(size),
        status=status,
        order_type="GTC",
        placed_at=placed_at,
        last_updated=placed_at,
    ))
    s.commit()


def _add_market(s, *, condition_id: str, end_date: datetime):
    s.add(Market(
        condition_id=condition_id,
        category="weather",
        question=f"market {condition_id}",
        end_date=end_date,
        fee_rate_bps=0,
    ))
    s.commit()


def test_no_orders_returns_zero(session_factory):
    count, ids = _mod.cancel_paper_orders(session_factory, "bot_c", execute=True)
    assert count == 0
    assert ids == []


def test_dry_run_does_not_mutate(session_factory):
    with session_factory() as s:
        _add_order(s, order_id="o1", bot_id="bot_c", status="PAPER_OPEN")
        _add_order(s, order_id="o2", bot_id="bot_c", status="PAPER_OPEN")

    count, ids = _mod.cancel_paper_orders(session_factory, "bot_c", execute=False)
    assert count == 2
    assert set(ids) == {"o1", "o2"}

    with session_factory() as s:
        statuses = sorted(s.scalars(select(Order.status)).all())
        assert statuses == ["PAPER_OPEN", "PAPER_OPEN"]
        assert s.scalars(select(Event)).all() == []


def test_execute_cancels_paper_open(session_factory):
    with session_factory() as s:
        _add_order(s, order_id="o1", bot_id="bot_c", status="PAPER_OPEN", price="0.55")
        _add_order(s, order_id="o2", bot_id="bot_c", status="PAPER_OPEN", price="0.91")

    count, ids = _mod.cancel_paper_orders(session_factory, "bot_c", execute=True)
    assert count == 2

    with session_factory() as s:
        statuses = sorted(s.scalars(select(Order.status)).all())
        assert statuses == ["CANCELLED", "CANCELLED"]
        events = s.scalars(select(Event)).all()
        assert len(events) == 2
        assert all(e.event_type == "order.cancel.sweep" for e in events)
        assert all(e.severity == "info" for e in events)
        assert all(e.bot_id == "bot_c" for e in events)
        assert {e.payload["order_id"] for e in events} == {"o1", "o2"}
        assert all(e.payload["prior_status"] == "PAPER_OPEN" for e in events)


def test_cancels_all_reserving_statuses(session_factory):
    """Should match the full set used by core/fleet.py:209-214 for bankroll
    reservation: OPEN, PARTIAL, PAPER_OPEN, live, MATCHED. Non-reserving
    statuses (FILLED, CANCELLED) must be left alone."""
    with session_factory() as s:
        _add_order(s, order_id="open", bot_id="bot_c", status="OPEN")
        _add_order(s, order_id="partial", bot_id="bot_c", status="PARTIAL")
        _add_order(s, order_id="paper", bot_id="bot_c", status="PAPER_OPEN")
        _add_order(s, order_id="live", bot_id="bot_c", status="live")
        _add_order(s, order_id="matched", bot_id="bot_c", status="MATCHED")
        _add_order(s, order_id="filled", bot_id="bot_c", status="FILLED")
        _add_order(s, order_id="cancelled", bot_id="bot_c", status="CANCELLED")

    count, _ = _mod.cancel_paper_orders(session_factory, "bot_c", execute=True)
    assert count == 5

    with session_factory() as s:
        for oid in ("open", "partial", "paper", "live", "matched"):
            assert s.get(Order, oid).status == "CANCELLED"
        assert s.get(Order, "filled").status == "FILLED"
        # The pre-existing CANCELLED row should NOT have been re-touched
        # — it was excluded by the status filter.
        assert s.get(Order, "cancelled").status == "CANCELLED"


def test_does_not_touch_other_bots(session_factory):
    with session_factory() as s:
        _add_order(s, order_id="c1", bot_id="bot_c", status="PAPER_OPEN")
        _add_order(s, order_id="b1", bot_id="bot_b", status="PAPER_OPEN")
        _add_order(s, order_id="d1", bot_id="bot_d", status="PAPER_OPEN")

    count, _ = _mod.cancel_paper_orders(session_factory, "bot_c", execute=True)
    assert count == 1

    with session_factory() as s:
        assert s.get(Order, "c1").status == "CANCELLED"
        assert s.get(Order, "b1").status == "PAPER_OPEN"
        assert s.get(Order, "d1").status == "PAPER_OPEN"


def test_idempotent(session_factory):
    with session_factory() as s:
        _add_order(s, order_id="o1", bot_id="bot_c", status="PAPER_OPEN")

    n1, _ = _mod.cancel_paper_orders(session_factory, "bot_c", execute=True)
    n2, _ = _mod.cancel_paper_orders(session_factory, "bot_c", execute=True)
    assert n1 == 1
    assert n2 == 0

    with session_factory() as s:
        events = s.scalars(select(Event)).all()
        assert len(events) == 1


def test_payload_captures_size_and_price(session_factory):
    with session_factory() as s:
        _add_order(s, order_id="big", bot_id="bot_c", status="PAPER_OPEN",
                   price="0.008", size="1250")

    _mod.cancel_paper_orders(session_factory, "bot_c", execute=True)

    with session_factory() as s:
        e = s.scalars(select(Event)).one()
        # Numeric(18, 8) serialises to 8 decimal places.
        assert Decimal(e.payload["price"]) == Decimal("0.008")
        assert Decimal(e.payload["size"]) == Decimal("1250")
        assert e.payload["side"] == "BUY"
        assert e.payload["reason"] == "archive_sweep"


def test_custom_reason_recorded(session_factory):
    with session_factory() as s:
        _add_order(s, order_id="o1", bot_id="bot_c", status="PAPER_OPEN")

    _mod.cancel_paper_orders(
        session_factory, "bot_c", execute=True, reason="bot_c_adr_034_cleanup",
    )

    with session_factory() as s:
        e = s.scalars(select(Event)).one()
        assert e.payload["reason"] == "bot_c_adr_034_cleanup"
        assert "bot_c_adr_034_cleanup" in e.message


def test_min_lockup_hours_filters_weekly_like_orders(session_factory):
    placed = datetime.now(timezone.utc) - timedelta(hours=1)
    with session_factory() as s:
        _add_market(s, condition_id="daily", end_date=placed + timedelta(hours=24))
        _add_market(s, condition_id="weekly", end_date=placed + timedelta(hours=72))
        _add_order(
            s,
            order_id="daily-order",
            bot_id="bot_d",
            status="PAPER_OPEN",
            condition_id="daily",
            placed_at=placed,
        )
        _add_order(
            s,
            order_id="weekly-order",
            bot_id="bot_d",
            status="PAPER_OPEN",
            condition_id="weekly",
            placed_at=placed,
        )

    count, ids = _mod.cancel_paper_orders(
        session_factory,
        "bot_d",
        execute=True,
        min_lockup_hours=48,
        reason="daily_only_cleanup",
    )

    assert count == 1
    assert ids == ["weekly-order"]
    with session_factory() as s:
        assert s.get(Order, "daily-order").status == "PAPER_OPEN"
        assert s.get(Order, "weekly-order").status == "CANCELLED"
        event = s.scalars(select(Event)).one()
        assert event.payload["min_lockup_hours"] == 48
