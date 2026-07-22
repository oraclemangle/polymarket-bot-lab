"""Tests for Bot A exec-policy wiring (ADR-031).

Covers the integration contract documented in docs/decisions-log.md ADR-031:
- Default None exec_policy preserves pre-wiring behaviour.
- Passing a LadderPolicy activates the toxicity gate in try_enter.
- A benign flow passes; a hostile flow blocks with exec_policy:toxicity_block reason.
- Shadow signal is written on block.
- Flow-source failure degrades open (never blocks the bot on its own infra error).
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from bots.bot_a.executor import BotAExecutor, EntryDecision
from bots.bot_a.filters import Candidate
from core.exec_policy import FlowWindow, LadderPolicy


def _candidate(**overrides) -> Candidate:
    """Build a minimally valid Bot A candidate for try_enter."""
    from datetime import UTC, datetime, timedelta
    base = dict(
        condition_id="0xdeadbeef",
        category="politics",
        question="Will X happen by Y?",
        yes_token_id="yes_tok",
        no_token_id="no_tok",
        best_yes_ask=Decimal("0.05"),
        best_no_ask=Decimal("0.95"),
        no_ask_depth_within_2c_usd=Decimal("1000"),
        volume_24h_usd=Decimal("10000"),
        end_date=datetime.now(UTC) + timedelta(days=90),
        is_neg_risk=False,
    )
    base.update(overrides)
    return Candidate(**base)


class _FakeClob:
    """Minimal CLOB stub for Bot A tests — records what was placed."""
    def __init__(self):
        self.last_place_args: dict | None = None

    def place_limit(self, token_id, price, size, side, order_type):
        self.last_place_args = dict(
            token_id=token_id, price=price, size=size,
            side=side, order_type=order_type,
        )
        resp = MagicMock()
        resp.order_id = "fake-order-1"
        resp.status = "OPEN"
        return resp

    def cancel_order(self, order_id):
        return True

    def cancel_all(self):
        return 0


class _FakePortfolio:
    def get_total_exposure(self, bot_id):
        return Decimal("0")


@pytest.fixture
def mocks(tmp_db, monkeypatch):
    """Shared harness: no-halt, no-existing-position, no-fleet-breach.

    Note: check_fleet_exposure and is_emergency_halted are imported inline
    inside try_enter, so we monkeypatch at the SOURCE module path.
    size_position and shares_from_notional are imported at module level
    in bots.bot_a.executor, so we patch there.
    """
    monkeypatch.setattr(
        "core.fleet.check_fleet_exposure",
        lambda bot_id, notional: MagicMock(ok=True),
    )
    monkeypatch.setattr(
        "core.emergency_halt.is_emergency_halted",
        lambda: False,
    )
    monkeypatch.setattr(
        "bots.bot_a.executor.size_position",
        lambda bankroll, depth: Decimal("30"),
    )
    monkeypatch.setattr(
        "bots.bot_a.executor.shares_from_notional",
        lambda notional, price: Decimal("30"),
    )
    return object()


# --- Baseline: no policy preserves legacy behaviour -------------------------


def test_default_no_policy_places_order(mocks, tmp_db):
    clob = _FakeClob()
    ex = BotAExecutor(clob=clob, portfolio=_FakePortfolio())
    assert ex.exec_policy is None  # no policy wired by default in tests
    decision = ex.try_enter(_candidate(), bankroll_usd=Decimal("1000"))
    assert decision.placed is True
    assert decision.order_id == "fake-order-1"
    assert clob.last_place_args is not None


# --- Policy wired: benign flow allows placement -----------------------------


def test_policy_wired_benign_flow_allows(mocks, tmp_db):
    clob = _FakeClob()
    def benign_flow(market_id, lookback_s, now_ts=None):
        return FlowWindow(
            ts_start=0, ts_end=60,
            aggressive_buy_yes_usd=5000,
            aggressive_sell_yes_usd=500,
            aggressive_buy_no_usd=0,
            aggressive_sell_no_usd=0,
        )
    ex = BotAExecutor(
        clob=clob,
        portfolio=_FakePortfolio(),
        exec_policy=LadderPolicy(),
        flow_source=benign_flow,
    )
    decision = ex.try_enter(_candidate(), bankroll_usd=Decimal("1000"))
    assert decision.placed is True


# --- Policy wired: hostile flow blocks --------------------------------------


def test_policy_wired_hostile_flow_blocks(mocks, tmp_db):
    clob = _FakeClob()
    def hostile_flow(market_id, lookback_s, now_ts=None):
        # 90% aggressive SELLs on NO token = very hostile for NO_BUY
        return FlowWindow(
            ts_start=0, ts_end=60,
            aggressive_buy_yes_usd=0,
            aggressive_sell_yes_usd=0,
            aggressive_buy_no_usd=1000,
            aggressive_sell_no_usd=9000,
        )
    ex = BotAExecutor(
        clob=clob,
        portfolio=_FakePortfolio(),
        exec_policy=LadderPolicy(toxicity_place_block_threshold=0.80),
        flow_source=hostile_flow,
    )
    decision = ex.try_enter(_candidate(), bankroll_usd=Decimal("1000"))
    assert decision.placed is False
    assert decision.reason is not None
    assert decision.reason.startswith("exec_policy:toxicity_block")
    assert clob.last_place_args is None  # never reached CLOB


def test_policy_wired_hostile_flow_logs_shadow_signal(mocks, tmp_db):
    """On block, a shadow-signal event must be persisted for later analysis."""
    from sqlalchemy import select
    from core.db import Event, get_session_factory

    clob = _FakeClob()
    def hostile_flow(market_id, lookback_s, now_ts=None):
        return FlowWindow(
            ts_start=0, ts_end=60,
            aggressive_buy_yes_usd=0,
            aggressive_sell_yes_usd=0,
            aggressive_buy_no_usd=500,
            aggressive_sell_no_usd=9500,
        )
    ex = BotAExecutor(
        clob=clob,
        portfolio=_FakePortfolio(),
        exec_policy=LadderPolicy(),
        flow_source=hostile_flow,
    )
    ex.try_enter(_candidate(), bankroll_usd=Decimal("1000"))

    sf = get_session_factory()
    with sf() as s:
        events = list(s.scalars(
            select(Event).where(Event.event_type == "bot_a.shadow.signal")
        ))
    assert len(events) == 1
    ev = events[0]
    assert ev.message.startswith("would-have-traded")
    assert "exec_policy:toxicity_block" in ev.message or (
        ev.payload and "exec_policy" in str(ev.payload.get("blocked_by", ""))
    )


# --- Policy wired: flow-source crash degrades open --------------------------


def test_policy_wired_flow_source_crash_allows_trade(mocks, tmp_db):
    """If the flow source raises, try_enter must NOT block on its own infra
    error. Exec-policy is a guardrail, not a dependency. The trade proceeds.
    """
    clob = _FakeClob()
    def crashing_flow(market_id, lookback_s, now_ts=None):
        raise RuntimeError("simulated feed failure")
    ex = BotAExecutor(
        clob=clob,
        portfolio=_FakePortfolio(),
        exec_policy=LadderPolicy(),
        flow_source=crashing_flow,
    )
    decision = ex.try_enter(_candidate(), bankroll_usd=Decimal("1000"))
    assert decision.placed is True   # degraded open — trade proceeds


# --- Flow-source stub direct tests ------------------------------------------


def test_flow_source_stub_returns_zero_flow():
    from bots.bot_a.flow_source import build_flow_window
    fw = build_flow_window(market_id="0xdeadbeef", lookback_s=60, now_ts=1000.0)
    assert fw.aggressive_buy_yes_usd == 0.0
    assert fw.aggressive_sell_yes_usd == 0.0
    assert fw.aggressive_buy_no_usd == 0.0
    assert fw.aggressive_sell_no_usd == 0.0
    assert fw.ts_start == 940.0
    assert fw.ts_end == 1000.0


def test_flow_source_stub_uses_current_time_by_default():
    import time
    from bots.bot_a.flow_source import build_flow_window
    before = time.time()
    fw = build_flow_window(market_id="0xdeadbeef", lookback_s=30)
    after = time.time()
    assert before <= fw.ts_end <= after
    assert fw.ts_end - fw.ts_start == pytest.approx(30.0, abs=1.0)
