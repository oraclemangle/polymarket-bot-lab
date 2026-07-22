"""Bot A lifecycle (tick) tests — paper mode."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from bots.bot_a.config import BOT_ID
from bots.bot_a.executor import BotAExecutor
from bots.bot_a.lifecycle import tick
from core import config
from core.clob import ClobWrapper
from core.db import Book, HaltFlag, Market, Order, Position, get_session_factory


@pytest.fixture
def exe(tmp_db, monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    config.reset_settings()
    return BotAExecutor(clob=ClobWrapper(keystore=None))


def _seed_market(
    s, cid: str, category: str = "politics", neg_risk: bool = False, volume: Decimal | None = None
):
    s.add(
        Market(
            condition_id=cid,
            category=category,
            question=f"Will {cid} happen?",
            fee_rate_bps=40,
            yes_token_id=f"yes_{cid}",
            no_token_id=f"no_{cid}",
            is_neg_risk=1 if neg_risk else 0,
            end_date=datetime.now(UTC) + timedelta(days=60),
            volume_24h_usd=volume if volume is not None else Decimal("0"),
        )
    )


def _seed_book(s, token_id: str, best: Decimal):
    s.add(
        Book(
            token_id=token_id,
            snapshot_at=datetime.now(UTC),
            bids=[[str(best - Decimal("0.01")), "1000"]],
            asks=[[str(best), "1000"]],
        )
    )


def test_tick_places_entry_when_filters_pass(exe):
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1")
        _seed_book(s, "yes_c1", Decimal("0.04"))
        _seed_book(s, "no_c1", Decimal("0.96"))
        s.commit()

    volume_map = {"c1": Decimal("10000")}
    result = tick(exe, bankroll_usd=Decimal("100000"), volume_map=volume_map)
    assert result.entries_placed == 1
    assert result.exits_placed == 0

    with Session() as s:
        orders = list(s.scalars(select(Order)))
        assert len(orders) == 1
        assert orders[0].side == "BUY"


def test_tick_skips_when_halted(exe):
    Session = get_session_factory()
    with Session() as s:
        s.add(HaltFlag(bot_id=BOT_ID, halted=1, reason="test"))
        _seed_market(s, "c1")
        _seed_book(s, "yes_c1", Decimal("0.04"))
        _seed_book(s, "no_c1", Decimal("0.96"))
        s.commit()

    result = tick(exe, bankroll_usd=Decimal("100000"), volume_map={"c1": Decimal("10000")})
    assert result.entries_placed == 0


def test_tick_filters_reject_bad_category(exe):
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1", category="sports")
        _seed_book(s, "yes_c1", Decimal("0.04"))
        _seed_book(s, "no_c1", Decimal("0.96"))
        s.commit()

    result = tick(exe, bankroll_usd=Decimal("100000"), volume_map={"c1": Decimal("10000")})
    assert result.entries_placed == 0
    assert result.skip_reasons.get("filter_reject", 0) == 1


def test_tick_triggers_cut_loss(exe):
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1")
        s.add(
            Position(
                bot_id=BOT_ID,
                condition_id="c1",
                token_id="no_c1",
                side="NO",
                size=Decimal("10"),
                avg_price=Decimal("0.96"),
                cost_basis_usd=Decimal("9.60"),
                status="OPEN",
            )
        )
        s.commit()

    # Simulate YES spiking to 0.30 → cut-loss fires
    def yes_price(token_id):
        return Decimal("0.30")

    result = tick(
        exe,
        bankroll_usd=Decimal("100000"),
        volume_map={},
        current_yes_price_fn=yes_price,
    )
    assert result.exits_placed == 1


def test_tick_idempotent_no_duplicate_orders(exe):
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1")
        _seed_book(s, "yes_c1", Decimal("0.04"))
        _seed_book(s, "no_c1", Decimal("0.96"))
        s.commit()

    volume_map = {"c1": Decimal("10000")}
    first = tick(exe, bankroll_usd=Decimal("100000"), volume_map=volume_map)
    second = tick(exe, bankroll_usd=Decimal("100000"), volume_map=volume_map)
    assert first.entries_placed == 1
    assert second.entries_placed == 0  # order_exists blocks
    assert second.skip_reasons.get("order_exists", 0) == 1


def test_tick_reads_volume_from_db_column(exe):
    """No volume_map passed — daemon path.  Volume must come from the markets row."""
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1", volume=Decimal("25000"))
        _seed_book(s, "yes_c1", Decimal("0.04"))
        _seed_book(s, "no_c1", Decimal("0.96"))
        s.commit()

    result = tick(exe, bankroll_usd=Decimal("100000"), volume_map=None)
    assert result.entries_placed == 1


def test_tick_rejects_when_db_volume_below_threshold(exe):
    Session = get_session_factory()
    with Session() as s:
        _seed_market(s, "c1", volume=Decimal("100"))  # below $5k
        _seed_book(s, "yes_c1", Decimal("0.04"))
        _seed_book(s, "no_c1", Decimal("0.96"))
        s.commit()
    result = tick(exe, bankroll_usd=Decimal("100000"), volume_map=None)
    assert result.entries_placed == 0
