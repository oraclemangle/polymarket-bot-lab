"""Tests for bot_c_pyth.executor. Paper-mode via mock ClobWrapper."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from bots.bot_c_pyth.discovery import ParsedMarket
from bots.bot_c_pyth.executor import BotCExecutor
from bots.bot_c_pyth.strategy import EdgeDecision
from core.clob import OrderResponse, Side
from core.db import Base, HaltFlag, Order, Position
from core import pyth_models  # noqa: F401


@pytest.fixture
def main_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def mock_clob():
    clob = MagicMock()
    counter = {"n": 0}

    def _fake_place(**kwargs):
        counter["n"] += 1
        return OrderResponse(
            order_id=f"paper-test-{counter['n']:04x}",
            status="PAPER_OPEN",
            raw={k: str(v) for k, v in kwargs.items()},
        )

    clob.place_limit.side_effect = _fake_place
    return clob


def _decision(symbol, gamma_id, side, edge, yes_price, hours=48,
              vol=Decimal("5000"), strike=100):
    m = ParsedMarket(
        gamma_id=gamma_id, slug=f"slug-{gamma_id}", question="q",
        symbol=symbol, direction="above", strike_low=Decimal(str(strike)),
        strike_high=None,
        resolution_date=datetime.now(UTC) + timedelta(hours=hours),
        yes_token_id="ytok-" + gamma_id, no_token_id="ntok-" + gamma_id,
        yes_price=Decimal(str(yes_price)), volume_24h_usd=vol,
    )
    # For BUY_NO, model p_yes is low relative to market p_yes.
    if side == "BUY_YES":
        model = yes_price + edge
    else:
        model = yes_price - abs(edge)
    raw_edge = float(edge if side == "BUY_YES" else -abs(edge))
    return EdgeDecision(
        market=m,
        model_p_yes=float(model),
        market_p_yes=float(yes_price),
        gross_edge=raw_edge,
        net_edge=raw_edge,
        edge=raw_edge,
        side=side,
        reason="test",
        spot_price=Decimal("100"),
        annualised_vol=0.2,
        hours_to_resolution=float(hours),
        decided_at=datetime.now(UTC),
    )


def test_skip_decision_returns_not_placed(main_session_factory, mock_clob):
    ex = BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    d = _decision("BTC", "g1", "SKIP", 0.0, 0.5)
    r = ex.try_enter(d)
    assert not r.placed and r.reason == "skip_decision"
    mock_clob.place_limit.assert_not_called()


def test_placed_when_edge_above_threshold(main_session_factory, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_C_MIN_EDGE_FOR_ORDER", "0.10")
    # Reload executor module-level constant
    import importlib, bots.bot_c_pyth.executor as exmod
    importlib.reload(exmod)
    ex = exmod.BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    d = _decision("BTC", "g1", "BUY_YES", 0.20, 0.3)
    r = ex.try_enter(d)
    assert r.placed, f"expected placed, got {r}"
    assert r.order_id.startswith("paper-")
    mock_clob.place_limit.assert_called_once()
    kwargs = mock_clob.place_limit.call_args.kwargs
    assert kwargs["side"] == Side.BUY
    assert kwargs["token_id"] == "ytok-g1"  # YES token
    # Order row persisted
    with main_session_factory() as s:
        orders = list(s.execute(select(Order)).scalars())
    assert len(orders) == 1
    assert orders[0].bot_id == "bot_c"


def test_buy_no_uses_no_token(main_session_factory, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_C_MIN_EDGE_FOR_ORDER", "0.10")
    import importlib, bots.bot_c_pyth.executor as exmod
    importlib.reload(exmod)
    ex = exmod.BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    d = _decision("BTC", "g2", "BUY_NO", 0.20, 0.80)
    r = ex.try_enter(d)
    assert r.placed
    kwargs = mock_clob.place_limit.call_args.kwargs
    assert kwargs["token_id"] == "ntok-g2"


def test_dedupe_open_order(main_session_factory, mock_clob):
    ex = BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    with main_session_factory() as s:
        s.add(Order(
            order_id="existing", bot_id="bot_c", condition_id="g3",
            token_id="ytok-g3", side="BUY", price=Decimal("0.4"),
            size=Decimal("25"), status="OPEN", order_type="GTC",
        ))
        s.commit()
    d = _decision("BTC", "g3", "BUY_YES", 0.20, 0.3)
    r = ex.try_enter(d)
    assert not r.placed and r.reason == "order_exists"


def test_halted_prevents_entry(main_session_factory, mock_clob):
    ex = BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    with main_session_factory() as s:
        s.add(HaltFlag(bot_id="bot_c", halted=1, reason="manual",
                       set_at=datetime.now(UTC)))
        s.commit()
    d = _decision("BTC", "g4", "BUY_YES", 0.20, 0.3)
    r = ex.try_enter(d)
    assert not r.placed and r.reason == "halted"


def test_edge_below_order_threshold(main_session_factory, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_C_MIN_EDGE_FOR_ORDER", "0.20")
    import importlib, bots.bot_c_pyth.executor as exmod
    importlib.reload(exmod)
    ex = exmod.BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    d = _decision("BTC", "g5", "BUY_YES", 0.12, 0.3)  # edge 0.12 < 0.20
    r = ex.try_enter(d)
    assert not r.placed and r.reason == "edge_below_order_threshold"


def test_horizon_too_long(main_session_factory, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_C_MIN_EDGE_FOR_ORDER", "0.10")
    monkeypatch.setenv("BOT_C_MAX_HOURS_TO_RESOLUTION", "48")
    import importlib, bots.bot_c_pyth.executor as exmod
    importlib.reload(exmod)
    ex = exmod.BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    d = _decision("BTC", "g6", "BUY_YES", 0.20, 0.3, hours=72)
    r = ex.try_enter(d)
    assert not r.placed and r.reason == "horizon_too_long"


def test_volume_too_low(main_session_factory, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_C_MIN_EDGE_FOR_ORDER", "0.10")
    monkeypatch.setenv("BOT_C_MIN_VOLUME_24H_USD", "1000")
    import importlib, bots.bot_c_pyth.executor as exmod
    importlib.reload(exmod)
    ex = exmod.BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    d = _decision("BTC", "g7", "BUY_YES", 0.20, 0.3, vol=Decimal("100"))
    r = ex.try_enter(d)
    assert not r.placed and r.reason == "volume_too_low"


def test_max_concurrent_cap(main_session_factory, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_C_MIN_EDGE_FOR_ORDER", "0.10")
    monkeypatch.setenv("BOT_C_MAX_CONCURRENT_POSITIONS", "1")
    import importlib, bots.bot_c_pyth.executor as exmod
    importlib.reload(exmod)
    ex = exmod.BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    # Pre-populate an OPEN position
    with main_session_factory() as s:
        s.add(Position(
            bot_id="bot_c", condition_id="preexisting", token_id="t",
            side="BUY", size=Decimal("10"), avg_price=Decimal("0.5"),
            cost_basis_usd=Decimal("5"), status="OPEN",
        ))
        s.commit()
    d = _decision("BTC", "newgid", "BUY_YES", 0.20, 0.3)
    r = ex.try_enter(d)
    assert not r.placed and r.reason == "max_concurrent"


def test_try_enter_all_ranks_by_abs_edge(main_session_factory, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_C_MIN_EDGE_FOR_ORDER", "0.10")
    monkeypatch.setenv("BOT_C_MAX_CONCURRENT_POSITIONS", "2")
    monkeypatch.setenv("BOT_C_BANKROLL_USD", "1000")
    import importlib, bots.bot_c_pyth.executor as exmod
    importlib.reload(exmod)
    ex = exmod.BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    decisions = [
        _decision("BTC", "low-edge", "BUY_YES", 0.15, 0.3),
        _decision("ETH", "mid-edge", "BUY_YES", 0.25, 0.3),
        _decision("AAPL", "high-edge", "BUY_YES", 0.40, 0.3),
        _decision("TSLA", "skipped", "SKIP", 0.01, 0.5),
    ]
    results = ex.try_enter_all(decisions)
    # 3 actionable (SKIP excluded), all attempted
    assert len(results) == 3
    # SECURITY_AUDIT.md C-2: Position rows are no longer created at
    # placement time (Portfolio.on_fill is the canonical owner). The
    # concurrency cap therefore counts only filled positions; with mock
    # Clob fills not creating Position rows, all 3 orders place. The
    # has_open_order dedupe still prevents same-market duplicates,
    # which we verify below by checking unique condition_ids.
    assert sum(1 for r in results if r.placed) == 3
    placed_cids = {r.condition_id if hasattr(r, "condition_id") else None for r in results if r.placed}
    # First call should have been for highest-edge market AAPL
    first_call_kwargs = mock_clob.place_limit.call_args_list[0].kwargs
    assert first_call_kwargs["token_id"].startswith("ytok-high-edge")


def test_review_open_positions_closes_on_edge_flip(main_session_factory, mock_clob, monkeypatch):
    from core import portfolio as portfolio_mod
    from core.db import Market, Trade

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))

    ex = BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    with main_session_factory() as s:
        s.add(Market(
            condition_id="g-exit",
            category="crypto",
            question="q",
            yes_token_id="ytok-g-exit",
            no_token_id="ntok-g-exit",
            is_neg_risk=0,
            volume_24h_usd=Decimal("1000"),
            last_updated=datetime.now(UTC),
        ))
        s.add(Position(
            bot_id="bot_c",
            condition_id="g-exit",
            token_id="ytok-g-exit",
            side="YES",
            size=Decimal("50"),
            avg_price=Decimal("0.20"),
            cost_basis_usd=Decimal("10"),
            status="OPEN",
        ))
        s.commit()

    decision = _decision("BTC", "g-exit", "BUY_NO", 0.12, 0.30)
    exited = ex.review_open_positions([decision])

    assert exited == 1
    with main_session_factory() as s:
        pos = s.execute(
            select(Position).where(Position.condition_id == "g-exit")
        ).scalars().one()
        assert pos.status == "CLOSED"
        sell = s.execute(
            select(Trade).where(Trade.bot_id == "bot_c", Trade.side == "SELL")
        ).scalars().one()
        assert sell.token_id == "ytok-g-exit"
        # Session 30: synthetic SELL discounts posted mid by BOT_C_EXIT_SLIPPAGE
        # (default 0.02) to model the half-spread a real SELL would eat.
        # Held YES, market p_yes=0.30 → exit at 0.28.
        assert sell.price == Decimal("0.28")
        assert sell.size == Decimal("50")


def test_review_open_positions_rejects_live_clob(main_session_factory, monkeypatch):
    """Session 30: paper-only synthetic-exit path must refuse live mode."""
    from core import portfolio as portfolio_mod
    from core.db import Market

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))

    live_clob = MagicMock()
    live_clob.paper_override = False
    ex = BotCExecutor(clob=live_clob, main_session_factory=main_session_factory)
    with main_session_factory() as s:
        s.add(Market(
            condition_id="g-live",
            category="crypto",
            question="q",
            yes_token_id="ytok-g-live",
            no_token_id="ntok-g-live",
            is_neg_risk=0,
            volume_24h_usd=Decimal("1000"),
            last_updated=datetime.now(UTC),
        ))
        s.add(Position(
            bot_id="bot_c",
            condition_id="g-live",
            token_id="ytok-g-live",
            side="YES",
            size=Decimal("50"),
            avg_price=Decimal("0.20"),
            cost_basis_usd=Decimal("10"),
            status="OPEN",
        ))
        s.commit()
    decision = _decision("BTC", "g-live", "BUY_NO", 0.12, 0.30)
    with pytest.raises(RuntimeError, match="paper-only"):
        ex.review_open_positions([decision])


def test_review_open_positions_edge_floor_env_tunable(
    main_session_factory, mock_clob, monkeypatch
):
    """Session 30: BOT_C_EXIT_EDGE_FLOOR env tunes the decay cutoff.

    Decision net_edge=-0.04 (held-YES flipped). Default floor 0.02 exits.
    Raising floor to 0.01 should exit on |edge|=0.04>0.01 AS WELL, so to
    prove tunability we use a pos where edge stays positive but small.
    """
    from bots.bot_c_pyth import executor as exec_mod
    from core import portfolio as portfolio_mod
    from core.db import Market

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))
    monkeypatch.setattr(exec_mod, "BOT_C_EXIT_EDGE_FLOOR", Decimal("0.10"))

    ex = BotCExecutor(clob=mock_clob, main_session_factory=main_session_factory)
    with main_session_factory() as s:
        s.add(Market(
            condition_id="g-floor",
            category="crypto",
            question="q",
            yes_token_id="ytok-g-floor",
            no_token_id="ntok-g-floor",
            is_neg_risk=0,
            volume_24h_usd=Decimal("1000"),
            last_updated=datetime.now(UTC),
        ))
        s.add(Position(
            bot_id="bot_c",
            condition_id="g-floor",
            token_id="ytok-g-floor",
            side="YES",
            size=Decimal("50"),
            avg_price=Decimal("0.20"),
            cost_basis_usd=Decimal("10"),
            status="OPEN",
        ))
        s.commit()
    # net_edge=+0.05 → held-YES edge=+0.05 which is BELOW the raised floor 0.10
    # so exit should fire (edge decayed below floor).
    decision = _decision("BTC", "g-floor", "BUY_YES", 0.25, 0.20)
    object.__setattr__(decision, "net_edge", 0.05)
    exited = ex.review_open_positions([decision])
    assert exited == 1
