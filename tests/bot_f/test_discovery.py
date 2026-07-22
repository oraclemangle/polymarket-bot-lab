"""Tests for Bot F Hunter — filter logic + metric computation.

Network fetches are NOT tested here; they're tested manually with the CLI.
These tests cover the pure functions: metric math, filter application.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bots.bot_f.discovery import (
    WalletMetrics,
    _compute_metrics,
    _compute_position_pnl,
    _passes_filters,
)
from core.backtest_db import (
    ResolvedMarket,
    get_backtest_session_factory,
)


@pytest.fixture
def tmp_backtest_db(tmp_path):
    return tmp_path / "backtest.db"


def _make_resolved_market(cid: str, yes_token: str, no_token: str, yes_won: bool) -> ResolvedMarket:
    return ResolvedMarket(
        condition_id=cid,
        question=f"Will {cid}?",
        category="test",
        end_date=datetime.now(timezone.utc),
        closed_time=datetime.now(timezone.utc),
        outcome_yes_price=Decimal("1.0") if yes_won else Decimal("0.0"),
        outcome_no_price=Decimal("0.0") if yes_won else Decimal("1.0"),
        yes_token_id=yes_token,
        no_token_id=no_token,
        is_neg_risk=0,
        volume_usd=Decimal("1000"),
        fetched_at=datetime.now(timezone.utc),
    )


def test_compute_pnl_buy_and_hold_winning_yes():
    """Buy 10 YES at $0.30; YES wins; P&L = 10 * (1.0 - 0.30) = $7.00."""
    trades = [
        {"conditionId": "c1", "asset": "yes1", "size": 10.0, "price": 0.30,
         "side": "BUY", "timestamp": 1700000000},
    ]
    resolved = {"c1": _make_resolved_market("c1", "yes1", "no1", yes_won=True)}
    results = _compute_position_pnl(trades, resolved)
    assert len(results) == 1
    cid, notional, pnl, ts = results[0]
    assert cid == "c1"
    assert notional == pytest.approx(3.0)  # 10 * 0.30
    assert pnl == pytest.approx(7.0)


def test_compute_pnl_buy_and_hold_losing_yes():
    """Buy 10 YES at $0.30; NO wins; P&L = -3.0."""
    trades = [
        {"conditionId": "c2", "asset": "yes2", "size": 10.0, "price": 0.30,
         "side": "BUY", "timestamp": 1700000000},
    ]
    resolved = {"c2": _make_resolved_market("c2", "yes2", "no2", yes_won=False)}
    _, _, pnl, _ = _compute_position_pnl(trades, resolved)[0]
    assert pnl == pytest.approx(-3.0)


def test_compute_pnl_closed_position_before_resolution():
    """Buy 10 at $0.30, sell 10 at $0.50. Closed position P&L = +2.0."""
    trades = [
        {"conditionId": "c3", "asset": "yes3", "size": 10.0, "price": 0.30,
         "side": "BUY", "timestamp": 1700000000},
        {"conditionId": "c3", "asset": "yes3", "size": 10.0, "price": 0.50,
         "side": "SELL", "timestamp": 1700001000},
    ]
    resolved = {"c3": _make_resolved_market("c3", "yes3", "no3", yes_won=False)}
    _, _, pnl, _ = _compute_position_pnl(trades, resolved)[0]
    # cost_net = 10*0.30 - 10*0.50 = -2.0; pnl = -cost_net = +2.0
    assert pnl == pytest.approx(2.0)


def test_compute_pnl_skips_unresolved_market():
    trades = [{"conditionId": "unknown", "asset": "xxx", "size": 10.0, "price": 0.30,
               "side": "BUY", "timestamp": 1700000000}]
    results = _compute_position_pnl(trades, {})
    assert results == []


def test_metrics_win_rate_and_profit_factor():
    """3 wins @ +$5, 2 losses @ -$3: WR 0.6, PF = 15/6 = 2.5."""
    trades = []
    resolved = {}
    now_ts = int(datetime.now(timezone.utc).timestamp())
    # 3 winning YES plays
    for i in range(3):
        cid = f"win{i}"
        trades.append({"conditionId": cid, "asset": f"yes_{cid}", "size": 10.0,
                       "price": 0.5, "side": "BUY", "timestamp": now_ts - i * 3600})
        resolved[cid] = _make_resolved_market(cid, f"yes_{cid}", f"no_{cid}", yes_won=True)
    # 2 losing YES plays
    for i in range(2):
        cid = f"lose{i}"
        trades.append({"conditionId": cid, "asset": f"yes_{cid}", "size": 10.0,
                       "price": 0.3, "side": "BUY", "timestamp": now_ts - (i + 5) * 3600})
        resolved[cid] = _make_resolved_market(cid, f"yes_{cid}", f"no_{cid}", yes_won=False)
    m = _compute_metrics("0xabc", "test", trades, resolved)
    assert m.resolved_trade_count == 5
    assert m.win_rate == pytest.approx(0.6)
    # Wins: 3 * (10 * (1 - 0.5)) = 15
    # Losses: 2 * -3.0 = -6
    # PF = 15/6 = 2.5
    assert m.profit_factor == pytest.approx(2.5)


def test_filters_reject_low_trade_count():
    m = WalletMetrics(
        wallet="0x1", pseudonym=None, trade_count=5, resolved_trade_count=5,
        win_rate=0.8, profit_factor=3.0, sharpe=1.0,
        realised_pnl_usd=100, total_notional_usd=500,
        recent_edge_ratio=1.0, p7d_share=0.5, top_categories=[],
    )
    ok, reason = _passes_filters(m)
    assert not ok
    assert "min_trades" in reason


def test_filters_reject_low_win_rate():
    m = WalletMetrics(
        wallet="0x1", pseudonym=None, trade_count=200, resolved_trade_count=200,
        win_rate=0.55, profit_factor=3.0, sharpe=1.0,
        realised_pnl_usd=100, total_notional_usd=500,
        recent_edge_ratio=1.0, p7d_share=0.5, top_categories=[],
    )
    ok, reason = _passes_filters(m)
    assert not ok
    assert "win_rate" in reason


def test_filters_reject_low_recent_edge():
    m = WalletMetrics(
        wallet="0x1", pseudonym=None, trade_count=200, resolved_trade_count=200,
        win_rate=0.65, profit_factor=2.0, sharpe=1.0,
        realised_pnl_usd=100, total_notional_usd=500,
        recent_edge_ratio=0.3, p7d_share=0.8, top_categories=[],
    )
    ok, reason = _passes_filters(m)
    assert not ok
    assert "recent_edge" in reason


def test_filters_reject_p7d_share_low():
    m = WalletMetrics(
        wallet="0x1", pseudonym=None, trade_count=200, resolved_trade_count=200,
        win_rate=0.65, profit_factor=2.0, sharpe=1.0,
        realised_pnl_usd=100, total_notional_usd=500,
        recent_edge_ratio=1.0, p7d_share=0.2, top_categories=[],
    )
    ok, reason = _passes_filters(m)
    assert not ok
    assert "p7d_share" in reason


def test_filters_reject_blacklisted_category():
    m = WalletMetrics(
        wallet="0x1", pseudonym=None, trade_count=200, resolved_trade_count=200,
        win_rate=0.65, profit_factor=2.0, sharpe=1.0,
        realised_pnl_usd=100, total_notional_usd=500,
        recent_edge_ratio=1.0, p7d_share=0.6,
        top_categories=["trump-vs-biden-politics-2024"],
    )
    ok, reason = _passes_filters(m)
    assert not ok
    assert "category" in reason


def test_filters_accept_good_wallet():
    m = WalletMetrics(
        wallet="0x1", pseudonym="sharpwhale", trade_count=200, resolved_trade_count=200,
        win_rate=0.70, profit_factor=2.5, sharpe=1.2,
        realised_pnl_usd=5000, total_notional_usd=50000,
        recent_edge_ratio=1.1, p7d_share=0.65, top_categories=["sports-nba"],
    )
    ok, reason = _passes_filters(m)
    assert ok
    assert reason == "ok"


def test_filters_skip_winrate_pf_for_closed_positions_source():
    """Audit fix 2026-04-16: when metrics come from /closed-positions
    (winner-biased), the win_rate / profit_factor gates are skipped because
    the source can't honestly produce a meaningful value for them.
    The min_trades and category gates still fire."""
    m = WalletMetrics(
        wallet="0x1", pseudonym="biased_source", trade_count=200, resolved_trade_count=200,
        # These would normally fail the gate (WR<0.62, PF<1.8) — but the
        # source disclaims them, so they should be ignored.
        win_rate=0.40, profit_factor=0.5, sharpe=0.1,
        realised_pnl_usd=50000, total_notional_usd=200000,
        recent_edge_ratio=None, p7d_share=None, top_categories=["sports-nba"],
    )
    ok, reason = _passes_filters(m, source="closed_positions")
    assert ok is True
    # And the same wallet would still fail with synthesised source.
    ok2, reason2 = _passes_filters(m, source="synthesised")
    assert ok2 is False
    assert "win_rate" in reason2


def test_filters_missing_recent_edge_passes():
    """Wallet with <2 months of resolved trades has None recent_edge_ratio —
    should pass (no data yet, not a fail signal)."""
    m = WalletMetrics(
        wallet="0x1", pseudonym=None, trade_count=200, resolved_trade_count=200,
        win_rate=0.65, profit_factor=2.0, sharpe=1.0,
        realised_pnl_usd=100, total_notional_usd=500,
        recent_edge_ratio=None, p7d_share=None, top_categories=[],
    )
    ok, reason = _passes_filters(m)
    assert ok
