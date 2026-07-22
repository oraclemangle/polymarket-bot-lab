"""Regression tests for the 2026-04-18 full-repo meta-audit fixes.

Covers the P0 + P1 items implemented in Session 17j:
  U-13  — synth paper-fill tagging + Event emission
  U-20  — Bot E archetype relabel (short_obi_reversion → momentum_obi)
  U-11  — Bot C emergency halt wiring
  U-01  — Bot C/D fleet cap wiring
  U-12  — watchdog _halt idempotency
  M-01  — fleet cap live/paper mode split
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.db import Base, Event, HaltFlag, Market, Order, Position, Trade


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_db(monkeypatch):
    """Give core.db a fresh in-memory engine so each test is isolated."""
    from core import db as db_mod
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SF = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db_mod, "_engine", engine)
    monkeypatch.setattr(db_mod, "_SessionLocal", SF)
    return SF


# ---------------------------------------------------------------------------
# U-20: Bot E archetype must be "momentum_obi"
# ---------------------------------------------------------------------------


def test_u20_bot_e_archetype_is_momentum_not_reversion():
    from core.fleet import BOT_ARCHETYPE
    assert BOT_ARCHETYPE["bot_e"] == "momentum_obi"
    # Crucially, NOT the misleading prior label.
    assert BOT_ARCHETYPE["bot_e"] != "short_obi_reversion"


# ---------------------------------------------------------------------------
# U-20: _symbol_from_market derives BTC/ETH/SOL from question text
# ---------------------------------------------------------------------------


def test_u20_symbol_from_market_btc():
    from bots.bot_e_btc_scalp.__main__ import _symbol_from_market

    class _M:
        question = "Will Bitcoin be Up or Down at 14:00 UTC?"
    assert _symbol_from_market(_M()) == "BTC"


def test_u20_symbol_from_market_eth():
    from bots.bot_e_btc_scalp.__main__ import _symbol_from_market

    class _M:
        question = "Will Ethereum close above $3500 at 15:00?"
    assert _symbol_from_market(_M()) == "ETH"


def test_u20_symbol_from_market_fallback():
    from bots.bot_e_btc_scalp.__main__ import _symbol_from_market
    # None or empty question returns the conservative BTC fallback.
    assert _symbol_from_market(None) == "BTC"


# ---------------------------------------------------------------------------
# U-13: synthetic no-book paper fills are tagged and logged
# ---------------------------------------------------------------------------


def test_u13_synth_paper_fill_tagged_and_event_emitted(isolated_db, monkeypatch):
    """A paper order that fills via the 60s no-book fallback gets
    a `synth-paper-fill-` trade_id and an Event row."""
    SF = isolated_db
    from core.portfolio import Portfolio
    # Default env preserves existing behaviour (synth fills allowed).
    monkeypatch.setenv("PAPER_NO_BOOK_SYNTH_FILLS", "true")

    placed = datetime.now(UTC) - timedelta(seconds=120)
    with SF() as s:
        s.add(Order(
            order_id="paper-xyz",
            bot_id="bot_test",
            condition_id="cid_123",
            token_id="tok_y",
            side="BUY_YES",
            price=Decimal("0.50"),
            size=Decimal("10"),
            status="PAPER_OPEN",
            order_type="GTC",
            placed_at=placed,
        ))
        s.commit()

    p = Portfolio(SF)
    filled = p.simulate_paper_fills("bot_test")
    assert filled == 1

    with SF() as s:
        trade = s.scalars(select(Trade)).first()
        events = list(s.scalars(
            select(Event).where(Event.event_type == "portfolio.synth_paper_fill")
        ))
    assert trade is not None
    assert trade.trade_id.startswith("synth-paper-fill-"), trade.trade_id
    assert len(events) == 1
    assert events[0].severity == "warn"


def test_u13_synth_fill_disabled_when_env_false(isolated_db, monkeypatch):
    SF = isolated_db
    from core.portfolio import Portfolio
    monkeypatch.setenv("PAPER_NO_BOOK_SYNTH_FILLS", "false")

    placed = datetime.now(UTC) - timedelta(seconds=120)
    with SF() as s:
        s.add(Order(
            order_id="paper-abc",
            bot_id="bot_test",
            condition_id="cid_xx",
            token_id="tok_y",
            side="BUY_YES",
            price=Decimal("0.50"),
            size=Decimal("10"),
            status="PAPER_OPEN",
            order_type="GTC",
            placed_at=placed,
        ))
        s.commit()

    p = Portfolio(SF)
    # No book persisted; synth disabled → zero fills.
    filled = p.simulate_paper_fills("bot_test")
    assert filled == 0


def test_u13_book_confirmed_fill_unaffected(isolated_db, monkeypatch):
    """Normal book-confirmed fills are NOT tagged synth."""
    SF = isolated_db
    from core.db import Book
    from core.portfolio import Portfolio
    monkeypatch.setenv("PAPER_NO_BOOK_SYNTH_FILLS", "true")

    with SF() as s:
        s.add(Market(
            condition_id="cid_xyz",
            category="crypto",
            question="BTC Up?",
            yes_token_id="tok_yes",
            no_token_id="tok_no",
        ))
        s.add(Book(
            token_id="tok_yes",
            snapshot_at=datetime.now(UTC),
            bids=[[0.49, 100]],
            asks=[[0.50, 100]],
        ))
        s.add(Order(
            order_id="paper-bk1",
            bot_id="bot_test",
            condition_id="cid_xyz",
            token_id="tok_yes",
            side="BUY",
            price=Decimal("0.50"),
            size=Decimal("10"),
            status="PAPER_OPEN",
            order_type="GTC",
            placed_at=datetime.now(UTC) - timedelta(seconds=120),
        ))
        s.commit()

    p = Portfolio(SF)
    filled = p.simulate_paper_fills("bot_test")
    assert filled == 1

    with SF() as s:
        trade = s.scalars(select(Trade)).first()
        events = list(s.scalars(
            select(Event).where(Event.event_type == "portfolio.synth_paper_fill")
        ))
    assert trade is not None
    assert trade.trade_id.startswith("paper-fill-"), trade.trade_id
    assert not trade.trade_id.startswith("synth-"), trade.trade_id
    assert len(events) == 0


# ---------------------------------------------------------------------------
# U-11: Bot C must check is_emergency_halted()
# ---------------------------------------------------------------------------


def test_u11_bot_c_blocks_on_emergency_halt(isolated_db, monkeypatch):
    """When the repo-wide halt is active, Bot C try_enter returns
    emergency_halt without placing an order."""
    from bots.bot_c_pyth.executor import BotCExecutor
    from bots.bot_c_pyth.strategy import EdgeDecision

    class _Market:
        gamma_id = "cid_x"
        yes_token_id = "tok_y"
        no_token_id = "tok_n"
        symbol = "TEST"
        volume_24h_usd = Decimal("1000")

    decision = EdgeDecision(
        market=_Market(),
        model_p_yes=0.8,
        market_p_yes=0.2,
        gross_edge=0.6,
        net_edge=0.5,
        edge=0.5,
        side="BUY_YES",
        reason="test",
        spot_price=Decimal("60000"),
        annualised_vol=0.4,
        hours_to_resolution=1.0,
        decided_at=datetime.now(UTC),
    )
    clob = MagicMock()
    ex = BotCExecutor(clob=clob, main_session_factory=isolated_db)

    # Trigger the repo-wide emergency halt via env var.
    monkeypatch.setenv("EMERGENCY_HALT", "true")
    r = ex.try_enter(decision)
    assert r.placed is False
    assert r.reason == "emergency_halt"
    # Order must never have been placed.
    clob.place_limit.assert_not_called()


# ---------------------------------------------------------------------------
# U-01: Bot C and Bot D must block on fleet cap breach
# ---------------------------------------------------------------------------


def test_u01_bot_c_blocks_on_fleet_cap_breach(isolated_db, monkeypatch):
    """With an artificially tiny fleet cap, Bot C's fleet check must
    refuse placement."""
    from bots.bot_c_pyth.executor import BotCExecutor
    from bots.bot_c_pyth.strategy import EdgeDecision
    monkeypatch.setenv("FLEET_WALLET_USD", "1")
    monkeypatch.setenv("FLEET_DEPLOYABLE_FRAC", "0.80")
    monkeypatch.setenv("BOT_C_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_C_MIN_EDGE_FOR_ORDER", "0.10")
    import importlib
    import core.fleet as fl
    import bots.bot_c_pyth.executor as cxmod
    importlib.reload(fl)
    importlib.reload(cxmod)

    class _Market:
        gamma_id = "cid_c1"
        yes_token_id = "tok_y"
        no_token_id = "tok_n"
        symbol = "TEST"
        volume_24h_usd = Decimal("1000")

    decision = EdgeDecision(
        market=_Market(),
        model_p_yes=0.8,
        market_p_yes=0.2,
        gross_edge=0.6,
        net_edge=0.5,
        edge=0.5,
        side="BUY_YES",
        reason="test",
        spot_price=Decimal("60000"),
        annualised_vol=0.4,
        hours_to_resolution=1.0,
        decided_at=datetime.now(UTC),
    )
    clob = MagicMock()
    ex = cxmod.BotCExecutor(clob=clob, main_session_factory=isolated_db)
    r = ex.try_enter(decision)
    assert r.placed is False
    assert r.reason == "fleet_cap_breach"
    clob.place_limit.assert_not_called()


# ---------------------------------------------------------------------------
# M-01: fleet cap splits live vs paper mode
# ---------------------------------------------------------------------------


def test_m01_fleet_snapshot_live_mode_ignores_paper_exposure(isolated_db, monkeypatch):
    """Paper bot exposure must not count against a live bot's cap."""
    from core.fleet import snapshot_fleet_exposure
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    monkeypatch.setenv("BOT_A_ENV", "live")
    monkeypatch.setenv("BOT_B_ENV", "live")
    monkeypatch.setenv("BOT_C_ENV", "paper")
    monkeypatch.setenv("BOT_D_ENV", "paper")
    monkeypatch.setenv("BOT_E_ENV", "paper")

    with isolated_db() as s:
        s.add(Position(
            bot_id="bot_d_live_probe",
            condition_id="cid_live",
            token_id="tok_l",
            side="YES",
            size=Decimal("10"),
            avg_price=Decimal("0.5"),
            cost_basis_usd=Decimal("5"),
            status="OPEN",
        ))
        s.add(Position(
            bot_id="bot_d",
            condition_id="cid_paper",
            token_id="tok_p",
            side="YES",
            size=Decimal("100"),
            avg_price=Decimal("0.5"),
            cost_basis_usd=Decimal("500"),
            status="OPEN",
        ))
        s.commit()

    live_snap = snapshot_fleet_exposure(mode="live")
    paper_snap = snapshot_fleet_exposure(mode="paper")
    combined = snapshot_fleet_exposure(mode="combined")

    assert live_snap.positions_usd == Decimal("5")
    assert paper_snap.positions_usd == Decimal("500")
    assert combined.positions_usd == Decimal("505")


def test_m01_check_fleet_exposure_uses_caller_mode(isolated_db, monkeypatch):
    """Live Bot A's fleet cap does not see paper exposure."""
    from core.fleet import check_fleet_exposure
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    monkeypatch.setenv("BOT_A_ENV", "live")
    monkeypatch.setenv("BOT_E_ENV", "paper")
    monkeypatch.setenv("FLEET_WALLET_USD", "100")
    monkeypatch.setenv("FLEET_DEPLOYABLE_FRAC", "0.80")

    # 500 USD in paper exposure would normally breach a combined cap of 80.
    with isolated_db() as s:
        s.add(Position(
            bot_id="bot_e",
            condition_id="cid_paper",
            token_id="tok_p",
            side="YES",
            size=Decimal("100"),
            avg_price=Decimal("0.5"),
            cost_basis_usd=Decimal("500"),
            status="OPEN",
        ))
        s.commit()

    # Live Bot A with $10 intended should NOT be blocked by paper Bot E's
    # $500 exposure.
    r = check_fleet_exposure("bot_a", Decimal("10"))
    assert r.ok is True, f"live caller blocked by paper exposure: {r}"


# ---------------------------------------------------------------------------
# U-12: watchdog _halt is idempotent on same reason family
# ---------------------------------------------------------------------------


def test_u12_halt_skips_cancel_when_same_family_already_halted(isolated_db):
    """Second _halt call for the same reason family must NOT invoke
    cancel_all again."""
    from core.watchdog import Watchdog, WatchdogConfig

    cancel_calls = []

    def _cancel(bot_id: str) -> int:
        cancel_calls.append(bot_id)
        return 0

    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("100"),
        bot_b_initial_usd=Decimal("100"),
    )
    wd = Watchdog(cfg, session_factory=isolated_db, cancel_all=_cancel)

    # First halt — counts.
    wd._halt("bot_b", "scorer stale: last score 180m ago")
    # Second halt, same family — should skip cancel.
    wd._halt("bot_b", "scorer stale: last score 241m ago")
    # Third halt, DIFFERENT family — should fire cancel.
    wd._halt("bot_b", "drawdown 21% ≥ 15%")

    assert cancel_calls == ["bot_b", "bot_b"], (
        f"expected 2 cancels (first + different-family), got {cancel_calls}"
    )
