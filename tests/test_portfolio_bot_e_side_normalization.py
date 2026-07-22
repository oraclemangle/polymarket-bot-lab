"""Regression tests for the 2026-04-17 Bot E paper-fill pipeline fix.

Root cause observed in production:
- Bot E persists orders with side="BUY_YES" / "BUY_NO" (signal convention).
- Portfolio._apply_to_position only handled side == "BUY" / "SELL".
- Neither branch matched, so Position rows were silently never created.
- 226 Trade rows accumulated with $6,780 of paper cost basis, but zero
  Position rows existed — breaking sizer caps, loss halts, exposure
  tracking, and P&L snapshotting.

Secondary root cause:
- simulate_paper_fills re-queried the markets table by token_id to find
  condition_id. Bot E's discovered markets aren't persisted there, so
  the lookup returned None and condition_id was ""; every Bot E Trade
  row had a blank condition_id, breaking audit traceability.
- Fix: prefer the Order row's own condition_id (populated at placement).

Third root cause:
- Bot E main loop never called portfolio.snapshot_daily(), so no daily
  P&L row was ever written. Covered by a separate test.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.db import Base, Market, Order, Position, Trade
from core.portfolio import Portfolio


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def portfolio(session_factory):
    return Portfolio(session_factory=session_factory)


# ---------- Side normalization in _apply_to_position ----------

def test_buy_yes_creates_position(portfolio, session_factory):
    """Bot E's 'BUY_YES' must create a Position row just like plain 'BUY'."""
    portfolio.on_fill(
        bot_id="bot_e",
        trade_id="t-bot-e-1",
        order_id="paper-e-1",
        condition_id="0xcid1",
        token_id="tok_yes_1",
        side="BUY_YES",
        price=Decimal("0.50"),
        size=Decimal("100"),
        fee_usd=Decimal("0"),
        filled_at=datetime.now(UTC),
    )
    with session_factory() as s:
        pos = s.scalars(select(Position).where(Position.bot_id == "bot_e")).first()
    assert pos is not None, "BUY_YES must create a Position row"
    assert pos.size == Decimal("100")
    assert pos.avg_price == Decimal("0.50")
    assert pos.cost_basis_usd == Decimal("50.00")
    assert pos.token_id == "tok_yes_1"


def test_buy_no_creates_position(portfolio, session_factory):
    portfolio.on_fill(
        bot_id="bot_e",
        trade_id="t-bot-e-2",
        order_id="paper-e-2",
        condition_id="0xcid2",
        token_id="tok_no_1",
        side="BUY_NO",
        price=Decimal("0.30"),
        size=Decimal("200"),
        fee_usd=Decimal("0"),
        filled_at=datetime.now(UTC),
    )
    with session_factory() as s:
        pos = s.scalars(select(Position).where(Position.bot_id == "bot_e")).first()
    assert pos is not None
    assert pos.size == Decimal("200")
    assert pos.avg_price == Decimal("0.30")


def test_plain_buy_still_works(portfolio, session_factory):
    """Bot A/B/C/D convention must be unaffected."""
    portfolio.on_fill(
        bot_id="bot_a",
        trade_id="t-bot-a-1",
        order_id="live-a-1",
        condition_id="0xcid3",
        token_id="tok_a",
        side="BUY",
        price=Decimal("0.97"),
        size=Decimal("50"),
        fee_usd=Decimal("0"),
        filled_at=datetime.now(UTC),
    )
    with session_factory() as s:
        pos = s.scalars(select(Position).where(Position.bot_id == "bot_a")).first()
    assert pos is not None
    assert pos.size == Decimal("50")


def test_sell_yes_closes_position(portfolio, session_factory):
    """SELL_YES must decrement an open Position."""
    # First open with BUY_YES
    now = datetime.now(UTC)
    portfolio.on_fill(
        bot_id="bot_e", trade_id="t1", order_id="paper-1",
        condition_id="0xcid", token_id="tok_y",
        side="BUY_YES", price=Decimal("0.50"), size=Decimal("100"),
        fee_usd=Decimal("0"), filled_at=now,
    )
    # Then SELL_YES half
    portfolio.on_fill(
        bot_id="bot_e", trade_id="t2", order_id="paper-2",
        condition_id="0xcid", token_id="tok_y",
        side="SELL_YES", price=Decimal("0.60"), size=Decimal("50"),
        fee_usd=Decimal("0"), filled_at=now,
    )
    with session_factory() as s:
        pos = s.scalars(select(Position).where(Position.bot_id == "bot_e")).first()
    assert pos.size == Decimal("50")


# ---------- simulate_paper_fills uses Order's condition_id ----------

def test_simulate_paper_fills_uses_order_condition_id(
    portfolio, session_factory, monkeypatch,
):
    """Bot E discovers markets that aren't in the main.db markets table.
    simulate_paper_fills must NOT yield a blank condition_id when the
    Order row already has it populated.

    Codex A-12 (2026-04-22): synth-fill fallback is OFF by default;
    opt in explicitly to exercise the no-book fallback path.
    """
    monkeypatch.setenv("PAPER_NO_BOOK_SYNTH_FILLS", "true")
    now = datetime.now(UTC)
    cid = "0xbotE-discovered-market"
    with session_factory() as s:
        # Paper order created by Bot E with condition_id set but NO market row.
        s.add(Order(
            order_id="paper-bote-x",
            bot_id="bot_e",
            condition_id=cid,
            token_id="tok_bote",
            side="BUY_YES",
            price=Decimal("0.50"),
            size=Decimal("60"),
            status="PAPER_OPEN",
            order_type="GTC",
            placed_at=now.replace(microsecond=0) - __import__("datetime").timedelta(minutes=5),
            last_updated=now,
        ))
        s.commit()

    n = portfolio.simulate_paper_fills("bot_e")
    assert n == 1, f"Expected 1 fill, got {n}"

    with session_factory() as s:
        trade = s.scalars(select(Trade).where(Trade.bot_id == "bot_e")).first()
        pos = s.scalars(select(Position).where(Position.bot_id == "bot_e")).first()
        order = s.scalars(select(Order).where(Order.order_id == "paper-bote-x")).first()

    # Condition_id must be populated from the Order row, not blank.
    assert trade is not None
    assert trade.condition_id == cid
    # Position must be created (proves side normalization works end-to-end).
    assert pos is not None
    assert pos.condition_id == cid
    assert pos.size == Decimal("60")
    # Order must be marked FILLED.
    assert order.status == "FILLED"


def test_simulate_paper_fills_fallback_to_market_lookup(
    portfolio, session_factory, monkeypatch,
):
    """If the Order row has no condition_id (historic bug), fall back to
    the markets table lookup so the legacy path still works.

    Codex A-12: opt in to synth-fill fallback explicitly.
    """
    monkeypatch.setenv("PAPER_NO_BOOK_SYNTH_FILLS", "true")
    now = datetime.now(UTC)
    with session_factory() as s:
        # Market exists in the markets table.
        s.add(Market(
            condition_id="0xlegacy",
            category="politics",
            question="legacy?",
            yes_token_id="tok_legacy",
            no_token_id="tok_legacy_no",
            is_neg_risk=0,
            last_updated=now,
            volume_24h_usd=Decimal("0"),
        ))
        # Old-style Order with blank condition_id.
        s.add(Order(
            order_id="paper-legacy-1",
            bot_id="bot_e",
            condition_id="",  # blank
            token_id="tok_legacy",
            side="BUY_YES",
            price=Decimal("0.40"),
            size=Decimal("80"),
            status="PAPER_OPEN",
            order_type="GTC",
            placed_at=now - __import__("datetime").timedelta(minutes=5),
            last_updated=now,
        ))
        s.commit()

    portfolio.simulate_paper_fills("bot_e")

    with session_factory() as s:
        trade = s.scalars(select(Trade).where(Trade.bot_id == "bot_e")).first()
    assert trade is not None
    # Fallback resolved it from markets table.
    assert trade.condition_id == "0xlegacy"
