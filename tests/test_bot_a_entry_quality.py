"""Tests for A-2: Bot A entry-quality instrumentation.

Every successful `try_enter` placement must emit a `bot_a.entry.quality`
Event row with the requested params (limit price, size, book depth, volume).
This forms the entry half of the slippage dataset. The fill half lands
once OQ-030 `reconcile_live_fills` is wired.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from bots.bot_a.executor import BotAExecutor
from bots.bot_a.filters import Candidate
from core.clob import ClobWrapper
from core.db import Base, Event, HaltFlag


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def clob():
    # Paper-mode CLOB — returns synthetic order IDs, no network.
    return ClobWrapper(keystore=None)


def _candidate(cid: str = "cid1") -> Candidate:
    return Candidate(
        condition_id=cid,
        category="geopolitics",
        question="Will X happen?",
        yes_token_id="yes_1",
        no_token_id="no_1",
        best_yes_ask=Decimal("0.03"),
        best_no_ask=Decimal("0.97"),
        no_ask_depth_within_2c_usd=Decimal("1500"),
        volume_24h_usd=Decimal("45000"),
        end_date=datetime.now(UTC) + timedelta(days=60),
        is_neg_risk=False,
    )


def test_entry_quality_event_emitted_on_paper_fill(session_factory, clob, monkeypatch):
    """Happy path: paper fill → Event row with all requested-params fields."""
    from core.portfolio import Portfolio
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    exec_ = BotAExecutor(
        clob=clob,
        portfolio=Portfolio(session_factory=session_factory),
        session_factory=session_factory,
    )
    decision = exec_.try_enter(
        candidate=_candidate(),
        bankroll_usd=Decimal("1000"),
    )
    assert decision.placed is True
    with session_factory() as s:
        events = list(s.scalars(select(Event).where(
            Event.event_type == "bot_a.entry.quality"
        )))
    assert len(events) == 1
    p = events[0].payload
    assert p["condition_id"] == "cid1"
    assert p["requested_limit_price"] == "0.97"
    assert Decimal(p["requested_size_shares"]) > Decimal("0")
    assert p["no_ask_depth_within_2c_usd"] == "1500"
    assert p["volume_24h_usd"] == "45000"
    assert p["best_yes_ask_at_request"] == "0.03"


def test_no_entry_quality_event_when_halted(session_factory, clob):
    """Halt path: no order placed, no entry.quality event."""
    from core.portfolio import Portfolio
    with session_factory() as s:
        s.add(HaltFlag(bot_id="bot_a", halted=True, reason="test halt"))
        s.commit()
    exec_ = BotAExecutor(
        clob=clob,
        portfolio=Portfolio(session_factory=session_factory),
        session_factory=session_factory,
    )
    decision = exec_.try_enter(
        candidate=_candidate(),
        bankroll_usd=Decimal("1000"),
    )
    assert decision.placed is False
    assert decision.reason == "halted"
    with session_factory() as s:
        quality_events = list(s.scalars(select(Event).where(
            Event.event_type == "bot_a.entry.quality"
        )))
    assert quality_events == []
