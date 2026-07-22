"""Tests for scripts/liquidate_positions.py.

Focus on the pure-logic pieces: plan-building, order filtering, slippage
math. The live CLOB + keystore paths are skipped (integration test only).
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.db import Base, Event, Position


_SPEC = importlib.util.spec_from_file_location(
    "liquidate_positions",
    Path(__file__).resolve().parent.parent / "scripts" / "liquidate_positions.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["liquidate_positions"] = _mod
_SPEC.loader.exec_module(_mod)


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@dataclass
class _FakeBook:
    """Mimics core.clob.OrderBook: bids is a list of (price, size) tuples."""
    def __init__(self, bid_prices):
        from decimal import Decimal
        self.bids = [(Decimal(str(p)), Decimal("100")) for p in bid_prices]


class _FakeClob:
    def __init__(self, book_by_token):
        self._books = book_by_token
    def get_book(self, token_id):
        return self._books[token_id]


def _make_position(s, **kwargs):
    p = Position(
        bot_id=kwargs.get("bot_id", "bot_a"),
        condition_id=kwargs.get("condition_id", "0xcid1"),
        token_id=kwargs.get("token_id", "tok1"),
        side=kwargs.get("side", "BUY_NO"),
        size=Decimal(str(kwargs.get("size", "100"))),
        avg_price=Decimal(str(kwargs.get("avg_price", "0.97"))),
        cost_basis_usd=Decimal(str(kwargs.get("cost_basis_usd", "97"))),
        status=kwargs.get("status", "OPEN"),
        opened_at=datetime.now(UTC),
    )
    s.add(p)
    s.commit()
    s.refresh(p)
    return p


def test_build_plans_skips_empty_book(session_factory):
    with session_factory() as s:
        _make_position(s)
    clob = _FakeClob({"tok1": _FakeBook([])})  # no bids
    plans = _mod.build_plans(
        session_factory, clob, ["bot_a"], set(), set(), Decimal("0.01")
    )
    assert plans == []


def test_build_plans_produces_plan_for_open_position(session_factory):
    with session_factory() as s:
        _make_position(s, token_id="tok1", size=100)
    clob = _FakeClob({"tok1": _FakeBook([0.95, 0.94, 0.93])})
    plans = _mod.build_plans(
        session_factory, clob, ["bot_a"], set(), set(), Decimal("0.01")
    )
    assert len(plans) == 1
    plan = plans[0]
    assert plan.best_bid == Decimal("0.95")
    # exit_limit = best_bid - slippage = 0.94
    assert plan.exit_limit == Decimal("0.94")
    assert plan.notional_usd == Decimal("94.00")


def test_build_plans_respects_bot_filter(session_factory):
    with session_factory() as s:
        _make_position(s, bot_id="bot_a", token_id="tokA")
        _make_position(s, bot_id="bot_b", token_id="tokB")
    clob = _FakeClob({
        "tokA": _FakeBook([0.95]),
        "tokB": _FakeBook([0.90]),
    })
    a_only = _mod.build_plans(
        session_factory, clob, ["bot_a"], set(), set(), Decimal("0.01")
    )
    assert [p.bot_id for p in a_only] == ["bot_a"]
    both = _mod.build_plans(
        session_factory, clob, ["bot_a", "bot_b"], set(), set(), Decimal("0.01")
    )
    assert sorted(p.bot_id for p in both) == ["bot_a", "bot_b"]


def test_build_plans_respects_only_cid(session_factory):
    with session_factory() as s:
        _make_position(s, condition_id="cid1", token_id="tok1")
        _make_position(s, condition_id="cid2", token_id="tok2")
    clob = _FakeClob({"tok1": _FakeBook([0.95]), "tok2": _FakeBook([0.95])})
    plans = _mod.build_plans(
        session_factory, clob, ["bot_a"], {"cid1"}, set(), Decimal("0.01")
    )
    assert [p.condition_id for p in plans] == ["cid1"]


def test_build_plans_respects_skip_cid(session_factory):
    with session_factory() as s:
        _make_position(s, condition_id="cid1", token_id="tok1")
        _make_position(s, condition_id="cid2", token_id="tok2")
    clob = _FakeClob({"tok1": _FakeBook([0.95]), "tok2": _FakeBook([0.95])})
    plans = _mod.build_plans(
        session_factory, clob, ["bot_a"], set(), {"cid1"}, Decimal("0.01")
    )
    assert [p.condition_id for p in plans] == ["cid2"]


def test_build_plans_excludes_closed_positions(session_factory):
    """Position with status != 'OPEN' must not appear in the liquidation plan."""
    with session_factory() as s:
        _make_position(s, status="CLOSED")
        _make_position(s, status="CLOSED_V2_MIGRATION", token_id="tok2")
    clob = _FakeClob({"tok1": _FakeBook([0.95]), "tok2": _FakeBook([0.95])})
    plans = _mod.build_plans(
        session_factory, clob, ["bot_a"], set(), set(), Decimal("0.01")
    )
    assert plans == []


def test_build_plans_clamps_extreme_exit_price(session_factory):
    """exit_limit below 0.005 gets clamped to 0.005."""
    with session_factory() as s:
        _make_position(s, token_id="tok1", size=100)
    # best_bid 0.01; slippage 0.01 → raw exit = 0.00 → clamp to 0.005.
    clob = _FakeClob({"tok1": _FakeBook([0.01])})
    plans = _mod.build_plans(
        session_factory, clob, ["bot_a"], set(), set(), Decimal("0.01")
    )
    assert len(plans) == 1
    assert plans[0].exit_limit == Decimal("0.005")


def test_build_plans_clamps_high_exit_price(session_factory):
    with session_factory() as s:
        _make_position(s, token_id="tok1", size=100)
    clob = _FakeClob({"tok1": _FakeBook([0.999])})
    plans = _mod.build_plans(
        session_factory, clob, ["bot_a"], set(), set(), Decimal("0.01")
    )
    # 0.999 - 0.01 = 0.989 → not clamped (still below 0.995).
    assert plans[0].exit_limit == Decimal("0.99")  # quantize to 0.01


def test_print_plans_returns_total(session_factory, capsys):
    plan = _mod.LiquidationPlan(
        position_id=1, bot_id="bot_a", condition_id="cid1", token_id="tok1",
        size=Decimal("100"), best_bid=Decimal("0.95"),
        exit_limit=Decimal("0.94"), notional_usd=Decimal("94.00"),
    )
    total = _mod.print_plans([plan])
    assert total == Decimal("94.00")
    out = capsys.readouterr().out
    assert "cid1" in out
    assert "0.95" in out


def test_liquidate_one_dry_run_does_not_touch_db(session_factory):
    with session_factory() as s:
        pos = _make_position(s, token_id="tok1")
    plan = _mod.LiquidationPlan(
        position_id=pos.id, bot_id="bot_a", condition_id="cid1", token_id="tok1",
        size=Decimal("100"), best_bid=Decimal("0.95"),
        exit_limit=Decimal("0.94"), notional_usd=Decimal("94"),
    )
    clob = MagicMock()
    result = _mod.liquidate_one(
        session_factory, clob, plan, fill_timeout_sec=1, execute=False
    )
    assert result == "dry-run"
    clob.place_limit.assert_not_called()
    with session_factory() as s:
        unchanged = s.get(Position, pos.id)
        assert unchanged.status == "OPEN"


def test_liquidate_one_skips_already_liquidated(session_factory):
    """Idempotency: re-running on an already CLOSED_V2_MIGRATION row is a no-op."""
    with session_factory() as s:
        pos = _make_position(
            s, token_id="tok1", status=_mod.CLOSED_STATUS
        )
    plan = _mod.LiquidationPlan(
        position_id=pos.id, bot_id="bot_a", condition_id="cid1", token_id="tok1",
        size=Decimal("100"), best_bid=Decimal("0.95"),
        exit_limit=Decimal("0.94"), notional_usd=Decimal("94"),
    )
    clob = MagicMock()
    result = _mod.liquidate_one(
        session_factory, clob, plan, fill_timeout_sec=1, execute=True
    )
    assert result == "skipped"
    clob.place_limit.assert_not_called()


def test_liquidate_one_place_failed_emits_event(session_factory):
    with session_factory() as s:
        pos = _make_position(s, token_id="tok1")
    plan = _mod.LiquidationPlan(
        position_id=pos.id, bot_id="bot_a", condition_id="cid1", token_id="tok1",
        size=Decimal("100"), best_bid=Decimal("0.95"),
        exit_limit=Decimal("0.94"), notional_usd=Decimal("94"),
    )
    clob = MagicMock()
    clob.place_limit.side_effect = RuntimeError("clob nack")
    result = _mod.liquidate_one(
        session_factory, clob, plan, fill_timeout_sec=1, execute=True
    )
    assert result == "stalled"
    with session_factory() as s:
        events = list(s.scalars(select(Event).where(
            Event.event_type == _mod.AUDIT_EVENT_TYPE
        )))
    assert len(events) == 1
    assert events[0].severity == "warn"
    assert "place_failed" in events[0].message
