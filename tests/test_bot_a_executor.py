"""Bot A executor tests (paper mode — no network)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from bots.bot_a.config import BOT_ID
from bots.bot_a.executor import BotAExecutor
from bots.bot_a.filters import Candidate
from core import config
from core.clob import ClobWrapper
from core.db import HaltFlag, Order, Position, get_session_factory


@pytest.fixture
def candidate():
    return Candidate(
        condition_id="c1",
        category="politics",
        question="Will X happen?",
        yes_token_id="yes1",
        no_token_id="no1",
        best_yes_ask=Decimal("0.04"),
        best_no_ask=Decimal("0.96"),
        no_ask_depth_within_2c_usd=Decimal("1000"),
        volume_24h_usd=Decimal("10000"),
        end_date=datetime.now(UTC) + timedelta(days=60),
        is_neg_risk=False,
    )


@pytest.fixture
def exe(tmp_db, monkeypatch):
    # force paper mode
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    config.reset_settings()
    clob = ClobWrapper(keystore=None)
    return BotAExecutor(clob=clob)


def test_enter_happy_path(exe, candidate):
    decision = exe.try_enter(candidate, bankroll_usd=Decimal("100000"))
    assert decision.placed
    assert decision.order_id is not None
    assert decision.order_id.startswith("paper-")
    assert decision.size_usd == Decimal("30.00")  # $30 fixed wins (depth 5% of $1000 = $50)

    Session = get_session_factory()
    with Session() as s:
        o = s.scalars(select(Order)).one()
        assert o.bot_id == BOT_ID
        assert o.side == "BUY"
        assert o.price == Decimal("0.96")
        assert o.size == Decimal("31.25")  # 30 / 0.96 ≈ 31.25


def test_halted_refuses_entry(exe, candidate):
    Session = get_session_factory()
    with Session() as s:
        s.add(HaltFlag(bot_id=BOT_ID, halted=1, reason="test"))
        s.commit()

    decision = exe.try_enter(candidate, bankroll_usd=Decimal("100000"))
    assert not decision.placed
    assert decision.reason == "halted"


def test_no_duplicate_position(exe, candidate):
    Session = get_session_factory()
    with Session() as s:
        s.add(
            Position(
                bot_id=BOT_ID,
                condition_id="c1",
                token_id="no1",
                side="NO",
                size=Decimal("10"),
                avg_price=Decimal("0.96"),
                cost_basis_usd=Decimal("9.60"),
                status="OPEN",
            )
        )
        s.commit()
    decision = exe.try_enter(candidate, bankroll_usd=Decimal("100000"))
    assert not decision.placed
    assert decision.reason == "position_exists"


def test_no_duplicate_order(exe, candidate):
    Session = get_session_factory()
    with Session() as s:
        s.add(
            Order(
                order_id="existing",
                bot_id=BOT_ID,
                condition_id="c1",
                token_id="no1",
                side="BUY",
                price=Decimal("0.96"),
                size=Decimal("10"),
                status="OPEN",
                order_type="GTC",
            )
        )
        s.commit()
    decision = exe.try_enter(candidate, bankroll_usd=Decimal("100000"))
    assert not decision.placed
    assert decision.reason == "order_exists"


def test_aggregate_cap_blocks(exe, candidate, monkeypatch):
    # Force aggregate exposure up against cap.
    from bots.bot_a import executor as exec_mod

    monkeypatch.setattr(
        exec_mod.BotAExecutor, "aggregate_exposure_usd",
        lambda self: Decimal("995"),
    )
    decision = exe.try_enter(candidate, bankroll_usd=Decimal("1000000"))
    assert not decision.placed
    assert decision.reason == "aggregate_cap"


def test_cut_loss_triggers_above_threshold(exe, candidate):
    # Open a position first.
    Session = get_session_factory()
    with Session() as s:
        pos = Position(
            bot_id=BOT_ID,
            condition_id="c1",
            token_id="no1",
            side="NO",
            size=Decimal("10"),
            avg_price=Decimal("0.96"),
            cost_basis_usd=Decimal("9.60"),
            status="OPEN",
        )
        s.add(pos)
        s.commit()
        s.refresh(pos)
        pos_id = pos.id

    with Session() as s:
        pos = s.get(Position, pos_id)
        acted = exe.try_cut_loss(pos, best_yes_price=Decimal("0.30"))  # > 0.25
    assert acted

    with Session() as s:
        sells = list(s.scalars(select(Order).where(Order.side == "SELL")))
        assert len(sells) == 1
        assert sells[0].price == Decimal("0.69")  # 1 - 0.30 - 0.01


def test_cut_loss_below_threshold_noop(exe):
    Session = get_session_factory()
    with Session() as s:
        pos = Position(
            bot_id=BOT_ID,
            condition_id="c1",
            token_id="no1",
            side="NO",
            size=Decimal("10"),
            avg_price=Decimal("0.96"),
            cost_basis_usd=Decimal("9.60"),
            status="OPEN",
        )
        s.add(pos)
        s.commit()
        s.refresh(pos)
        pos_id = pos.id

    with Session() as s:
        pos = s.get(Position, pos_id)
        assert not exe.try_cut_loss(pos, best_yes_price=Decimal("0.10"))
    with Session() as s:
        assert list(s.scalars(select(Order).where(Order.side == "SELL"))) == []


def test_cancel_all_flips_orders(exe):
    Session = get_session_factory()
    with Session() as s:
        for i in range(3):
            s.add(
                Order(
                    order_id=f"paper-{i}",
                    bot_id=BOT_ID,
                    condition_id=f"c{i}",
                    token_id=f"no{i}",
                    side="BUY",
                    price=Decimal("0.96"),
                    size=Decimal("10"),
                    status="OPEN",
                    order_type="GTC",
                )
            )
        s.commit()
    n = exe.cancel_all()
    assert n == 3
    with Session() as s:
        for i in range(3):
            assert s.get(Order, f"paper-{i}").status == "CANCELLED"
