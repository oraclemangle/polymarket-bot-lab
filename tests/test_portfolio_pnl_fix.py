"""Regression tests for portfolio.get_realised_pnl + simulate_paper_fills fallback."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.db import Base, Order, Position, Trade
from core.portfolio import Portfolio


@pytest.fixture
def sf(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    # Override the global session factory Portfolio uses.
    import core.portfolio as pf
    monkeypatch.setattr(pf, "get_session_factory", lambda: factory)
    return factory


def test_realised_pnl_zero_when_only_buys(sf):
    """Before fix: 2 BUYs at $10 = -$20 realised (wrong).
    After fix: no SELLs means realised = 0 (no closed trades yet)."""
    now = datetime.now(UTC)
    with sf() as s:
        for i, cost in enumerate([10.0, 10.0]):
            s.add(Trade(
                trade_id=f"t{i}", bot_id="bot_c", order_id=f"o{i}",
                condition_id=f"cond{i}", token_id=f"tok{i}",
                side="BUY", price=Decimal("0.5"),
                size=Decimal(str(cost / 0.5)),
                fee_usd=Decimal("0"), filled_at=now,
                usd_gbp_rate=Decimal("0.8"), gbp_notional=Decimal("8"),
            ))
        s.commit()
    p = Portfolio()
    assert p.get_realised_pnl("bot_c") == Decimal("0")


def test_realised_pnl_correct_on_closing_sell(sf):
    """Buy at 0.5 × 20 shares = $10. Sell at 0.8 × 20 shares = $16. Realised = +$6."""
    now = datetime.now(UTC)
    with sf() as s:
        s.add(Trade(
            trade_id="buy1", bot_id="bot_x", order_id="o1",
            condition_id="cond1", token_id="tokA",
            side="BUY", price=Decimal("0.5"), size=Decimal("20"),
            fee_usd=Decimal("0"), filled_at=now,
            usd_gbp_rate=Decimal("0.8"), gbp_notional=Decimal("8"),
        ))
        s.add(Trade(
            trade_id="sell1", bot_id="bot_x", order_id="o2",
            condition_id="cond1", token_id="tokA",
            side="SELL", price=Decimal("0.8"), size=Decimal("20"),
            fee_usd=Decimal("0"), filled_at=now,
            usd_gbp_rate=Decimal("0.8"), gbp_notional=Decimal("12.8"),
        ))
        s.commit()
    p = Portfolio()
    # (0.8 - 0.5) × 20 = 6.00
    assert p.get_realised_pnl("bot_x") == Decimal("6.00")


def test_realised_pnl_loss_on_sell_below_entry(sf):
    """Buy at 0.6 × 10 = $6. Sell at 0.4 × 10 = $4. Realised = -$2."""
    now = datetime.now(UTC)
    with sf() as s:
        s.add(Trade(
            trade_id="b", bot_id="bot_y", order_id="o1",
            condition_id="c", token_id="t",
            side="BUY", price=Decimal("0.6"), size=Decimal("10"),
            fee_usd=Decimal("0"), filled_at=now,
            usd_gbp_rate=Decimal("0.8"), gbp_notional=Decimal("4.8"),
        ))
        s.add(Trade(
            trade_id="s", bot_id="bot_y", order_id="o2",
            condition_id="c", token_id="t",
            side="SELL", price=Decimal("0.4"), size=Decimal("10"),
            fee_usd=Decimal("0"), filled_at=now,
            usd_gbp_rate=Decimal("0.8"), gbp_notional=Decimal("3.2"),
        ))
        s.commit()
    p = Portfolio()
    assert p.get_realised_pnl("bot_y") == Decimal("-2.00")


def test_realised_pnl_fees_subtracted(sf):
    """Fees on both legs reduce realised P&L."""
    now = datetime.now(UTC)
    with sf() as s:
        s.add(Trade(
            trade_id="b", bot_id="bot_z", order_id="o1",
            condition_id="c", token_id="t",
            side="BUY", price=Decimal("0.5"), size=Decimal("10"),
            fee_usd=Decimal("0.1"), filled_at=now,
            usd_gbp_rate=Decimal("0.8"), gbp_notional=Decimal("4"),
        ))
        s.add(Trade(
            trade_id="s", bot_id="bot_z", order_id="o2",
            condition_id="c", token_id="t",
            side="SELL", price=Decimal("0.6"), size=Decimal("10"),
            fee_usd=Decimal("0.1"), filled_at=now,
            usd_gbp_rate=Decimal("0.8"), gbp_notional=Decimal("4.8"),
        ))
        s.commit()
    p = Portfolio()
    # (0.6 - 0.5) * 10 - (0.1 + 0.1) = 1.0 - 0.2 = 0.8
    assert p.get_realised_pnl("bot_z") == Decimal("0.80")


def test_paper_fill_fallback_after_60s(sf, monkeypatch):
    """When no Book exists for a paper order's token_id and age > 60s,
    simulate_paper_fills falls back to filling at limit price.

    Codex A-12 (2026-04-22): the synth-fill fallback is OFF by default
    now; test explicitly opts in to exercise the fallback path.
    """
    monkeypatch.setenv("PAPER_NO_BOOK_SYNTH_FILLS", "true")
    old = datetime.now(UTC) - timedelta(seconds=120)
    with sf() as s:
        s.add(Order(
            order_id="paper-test1", bot_id="bot_x",
            condition_id="c1", token_id="tokNoBook",
            side="BUY", price=Decimal("0.25"), size=Decimal("40"),
            status="PAPER_OPEN", order_type="GTC",
            placed_at=old,
        ))
        s.commit()
    p = Portfolio()
    filled = p.simulate_paper_fills("bot_x")
    assert filled == 1
    # Verify the order is now FILLED and a Trade exists.
    with sf() as s:
        o = s.get(Order, "paper-test1")
        assert o.status == "FILLED"
        trades = list(s.query(Trade).filter(Trade.bot_id == "bot_x").all())
        assert len(trades) == 1
        assert trades[0].side == "BUY"
        assert trades[0].price == Decimal("0.25")


def test_paper_fill_fallback_skips_fresh_order(sf):
    """Orders younger than 60s should NOT be auto-filled via fallback."""
    recent = datetime.now(UTC) - timedelta(seconds=10)
    with sf() as s:
        s.add(Order(
            order_id="paper-test-fresh", bot_id="bot_x",
            condition_id="c1", token_id="tokNoBook",
            side="BUY", price=Decimal("0.25"), size=Decimal("40"),
            status="PAPER_OPEN", order_type="GTC",
            placed_at=recent,
        ))
        s.commit()
    p = Portfolio()
    filled = p.simulate_paper_fills("bot_x")
    assert filled == 0
