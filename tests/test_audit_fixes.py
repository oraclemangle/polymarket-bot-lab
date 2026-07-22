"""Regression tests locking in the audit fixes.

Each block below corresponds to one finding in the 2026-04-15 audit. They run
end-to-end against the existing paper-mode harness (SQLite temp DB) so any
future refactor that re-breaks the wiring will fail fast.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from bots.bot_a.executor import BotAExecutor
# Bot B excluded from public export; its tests were removed.
from core import config
from core.clob import ClobWrapper
from core.db import Book, Market, Order, Position, get_session_factory
from core.ingest import BookSnapshotter, build_mark_prices, latest_yes_price_fn
from core.portfolio import Portfolio


@pytest.fixture
def pfo(tmp_db, monkeypatch):
    from core import portfolio

    monkeypatch.setattr(portfolio, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))
    return Portfolio()


def _seed_market(s, cid: str, yes="yes_t", no="no_t", category="politics"):
    s.add(
        Market(
            condition_id=cid,
            category=category,
            question="?",
            fee_rate_bps=40,
            yes_token_id=yes,
            no_token_id=no,
            is_neg_risk=0,
            volume_24h_usd=Decimal("10000"),
            last_updated=datetime.now(UTC),
        )
    )


def _seed_book(s, token_id, bid=Decimal("0.04"), ask=Decimal("0.05")):
    s.add(
        Book(
            token_id=token_id,
            snapshot_at=datetime.now(UTC),
            bids=[[str(bid), "100"]],
            asks=[[str(ask), "100"]],
        )
    )


# --- Finding #5: NO-side position records correctly ---

def test_no_side_buy_creates_no_position(pfo):
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1", yes="y1", no="n1")
        s.commit()
    pfo.on_fill(
        bot_id="bot_a",
        trade_id="t1",
        order_id=None,
        condition_id="c1",
        token_id="n1",
        side="BUY",
        price=Decimal("0.96"),
        size=Decimal("10"),
        fee_usd=Decimal("0"),
        filled_at=datetime.now(UTC),
    )
    with Session() as s:
        pos = s.scalars(select(Position).where(Position.status == "OPEN")).one()
        assert pos.side == "NO"
        assert pos.token_id == "n1"


def test_yes_side_buy_still_creates_yes_position(pfo):
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1", yes="y1", no="n1")
        s.commit()
    pfo.on_fill(
        bot_id="bot_a",
        trade_id="t1",
        order_id=None,
        condition_id="c1",
        token_id="y1",
        side="BUY",
        price=Decimal("0.04"),
        size=Decimal("10"),
        fee_usd=Decimal("0"),
        filled_at=datetime.now(UTC),
    )
    with Session() as s:
        pos = s.scalars(select(Position).where(Position.status == "OPEN")).one()
        assert pos.side == "YES"


# --- Finding #2: open orders count toward exposure ---

def test_open_buy_orders_count_toward_exposure(pfo):
    Session = get_session_factory()
    with Session() as s:
        s.add(
            Order(
                order_id="o1",
                bot_id="bot_a",
                condition_id="c1",
                token_id="t1",
                side="BUY",
                price=Decimal("0.05"),
                size=Decimal("1000"),
                status="PAPER_OPEN",
                order_type="GTC",
            )
        )
        s.commit()
    # Position cost basis is zero, but open-order notional is 50 USD.
    assert pfo.get_open_exposure("bot_a") == Decimal("0")
    assert pfo.get_open_orders_notional("bot_a") == Decimal("50.00")
    assert pfo.get_total_exposure("bot_a") == Decimal("50.00")


def test_total_exposure_ignores_sell_and_cancelled(pfo):
    Session = get_session_factory()
    with Session() as s:
        s.add(Order(order_id="o1", bot_id="bot_a", condition_id="c", token_id="t",
                    side="SELL", price=Decimal("0.5"), size=Decimal("10"),
                    status="PAPER_OPEN", order_type="GTC"))
        s.add(Order(order_id="o2", bot_id="bot_a", condition_id="c", token_id="t",
                    side="BUY", price=Decimal("0.5"), size=Decimal("10"),
                    status="CANCELLED", order_type="GTC"))
        s.commit()
    assert pfo.get_open_orders_notional("bot_a") == Decimal("0")


# --- Finding #3: drawdown uses injected marks ---

def test_drawdown_counts_unrealised_when_marks_passed(pfo):
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1", yes="y1", no="n1")
        s.commit()
    # Bought NO at 0.96; market moves against us — NO drops to 0.40.
    pfo.on_fill(
        bot_id="bot_a",
        trade_id="t1",
        order_id=None,
        condition_id="c1",
        token_id="n1",
        side="BUY",
        price=Decimal("0.96"),
        size=Decimal("100"),
        fee_usd=Decimal("0"),
        filled_at=datetime.now(UTC),
    )
    # Without marks → dd ignores open loss.
    dd_no_marks = pfo.get_drawdown_pct("bot_a", Decimal("1000"))
    dd_with_marks = pfo.get_drawdown_pct(
        "bot_a", Decimal("1000"), mark_prices={"n1": Decimal("0.40")}
    )
    assert dd_with_marks > dd_no_marks
    assert dd_with_marks > Decimal("5")  # (0.56 × 100) / 1000 = 5.6%


# --- Finding #1 + supporting: current_yes_price_fn resolves from latest book ---

def test_latest_yes_price_fn_reads_latest_book(tmp_db):
    Session = get_session_factory()
    with Session() as s:
        _seed_book(s, "yy", bid=Decimal("0.20"), ask=Decimal("0.22"))
        s.commit()
    fn = latest_yes_price_fn()
    px = fn("yy")
    assert px is not None
    assert Decimal("0.20") <= px <= Decimal("0.22")


def test_latest_yes_price_fn_missing_returns_none(tmp_db):
    assert latest_yes_price_fn()("no-such-token") is None


# --- Finding #4: BookSnapshotter.active_token_ids returns both YES and NO ---

def test_active_token_ids_returns_both_sides(tmp_db):
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1", yes="y1", no="n1")
        _seed_market(s, "c2", yes="y2", no="n2")
        s.commit()
    ids = set(BookSnapshotter().active_token_ids())
    assert {"y1", "n1", "y2", "n2"}.issubset(ids)


# --- Finding #6 part a: stale-order repost cancels old BUYs ---

def test_cancel_stale_orders_cancels_old_buys(tmp_db, monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    config.reset_settings()
    Session = get_session_factory()
    ancient = datetime.now(UTC) - timedelta(hours=48)
    fresh = datetime.now(UTC) - timedelta(minutes=5)
    with Session() as s:
        s.add(Order(order_id="old", bot_id="bot_a", condition_id="c", token_id="t",
                    side="BUY", price=Decimal("0.05"), size=Decimal("10"),
                    status="PAPER_OPEN", order_type="GTC", placed_at=ancient,
                    last_updated=ancient))
        s.add(Order(order_id="new", bot_id="bot_a", condition_id="c", token_id="t",
                    side="BUY", price=Decimal("0.05"), size=Decimal("10"),
                    status="PAPER_OPEN", order_type="GTC", placed_at=fresh,
                    last_updated=fresh))
        s.commit()
    exe = BotAExecutor(clob=ClobWrapper(keystore=None))
    cancelled = exe.cancel_stale_orders(older_than_hours=6)
    assert cancelled == 1
    with Session() as s:
        old = s.get(Order, "old")
        new = s.get(Order, "new")
        assert old.status == "CANCELLED"
        assert new.status == "PAPER_OPEN"


# --- Fill reconciliation (paper mode simulator) ---

def test_paper_fill_simulator_fills_crossing_buy(pfo, monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    config.reset_settings()
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1", yes="y1", no="n1")
        _seed_book(s, "n1", bid=Decimal("0.95"), ask=Decimal("0.96"))
        s.add(Order(order_id="paper-abc123", bot_id="bot_a", condition_id="c1",
                    token_id="n1", side="BUY", price=Decimal("0.96"),
                    size=Decimal("10"), status="PAPER_OPEN", order_type="GTC"))
        s.commit()
    filled = pfo.simulate_paper_fills("bot_a")
    assert filled == 1
    with Session() as s:
        pos = s.scalars(select(Position).where(Position.status == "OPEN")).one()
        assert pos.side == "NO"
        assert pos.token_id == "n1"
        # Order marked filled.
        o = s.get(Order, "paper-abc123")
        assert o.status == "FILLED"


def test_paper_fill_simulator_skips_non_crossing(pfo, monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    config.reset_settings()
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1", yes="y1", no="n1")
        _seed_book(s, "n1", bid=Decimal("0.95"), ask=Decimal("0.99"))
        s.add(Order(order_id="paper-zzz", bot_id="bot_a", condition_id="c1",
                    token_id="n1", side="BUY", price=Decimal("0.90"),
                    size=Decimal("10"), status="PAPER_OPEN", order_type="GTC"))
        s.commit()
    assert pfo.simulate_paper_fills("bot_a") == 0


# --- Mark-price builder integrates the above ---

def test_build_mark_prices_uses_no_token_book_for_no_position(pfo):
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1", yes="y1", no="n1")
        _seed_book(s, "n1", bid=Decimal("0.95"), ask=Decimal("0.97"))
        s.add(Position(bot_id="bot_a", condition_id="c1", token_id="n1",
                       side="NO", size=Decimal("10"),
                       avg_price=Decimal("0.96"),
                       cost_basis_usd=Decimal("9.60"), status="OPEN"))
        s.commit()
    marks = build_mark_prices("bot_a")
    assert "n1" in marks
    assert Decimal("0.95") <= marks["n1"] <= Decimal("0.97")
