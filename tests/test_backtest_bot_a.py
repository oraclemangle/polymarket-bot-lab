"""Tests for the Bot A historical backtest harness."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from core.backtest_bot_a import run_bot_a_backtest
from core.backtest_db import (
    PriceHistory,
    ResolvedMarket,
    get_backtest_session_factory,
)


@pytest.fixture
def tmp_btdb(tmp_path: Path) -> Path:
    """Isolated backtest DB per test."""
    return tmp_path / "backtest.db"


def _seed_market(
    sf,
    *,
    cid: str,
    yes_token: str,
    no_token: str,
    category: str = "politics",
    end_date: datetime | None = None,
    outcome_yes: float = 0.0,
    outcome_no: float = 1.0,
    volume: float = 10000.0,
    is_neg_risk: int = 0,
) -> None:
    now = datetime.now(timezone.utc)
    with sf() as s:
        s.add(
            ResolvedMarket(
                condition_id=cid,
                question=f"Will {cid} happen?",
                category=category,
                end_date=end_date or (now + timedelta(days=60)),
                closed_time=end_date,
                outcome_yes_price=Decimal(str(outcome_yes)),
                outcome_no_price=Decimal(str(outcome_no)),
                yes_token_id=yes_token,
                no_token_id=no_token,
                is_neg_risk=is_neg_risk,
                volume_usd=Decimal(str(volume)),
                fetched_at=now,
            )
        )
        s.commit()


def _seed_prices(sf, token: str, series: list[tuple[int, float]]) -> None:
    with sf() as s:
        for ts, p in series:
            s.add(PriceHistory(token_id=token, ts=ts, price=p))
        s.commit()


def test_winning_no_entry_held_to_resolution(tmp_btdb):
    """YES at 0.03 entry, resolves NO → full payout 1.0, profit = 0.03 × shares."""
    sf = get_backtest_session_factory(tmp_btdb)
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=45)

    _seed_market(
        sf, cid="c1", yes_token="yes1", no_token="no1",
        end_date=end_date, outcome_yes=0.0, outcome_no=1.0,
    )
    # YES price at 3c 40 days before resolution (so days_to_res = 40, within [14, 180])
    entry_ts = int((end_date - timedelta(days=40)).timestamp())
    _seed_prices(sf, "yes1", [(entry_ts, 0.03)])

    result = run_bot_a_backtest(
        start=now - timedelta(days=1),
        end=end_date + timedelta(days=1),
        entry_size_usd=Decimal("30"),
        db_path=tmp_btdb,
    )
    assert result.markets_entered == 1
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "resolution_won"
    # NO entry at (1 - 0.03) = 0.97. Size = 30 / 0.97 ≈ 30.93. Exit at 1.0.
    assert abs(trade.pnl_usd - (1.0 - 0.97) * (30.0 / 0.97)) < 1e-6


def test_losing_no_entry_resolves_yes(tmp_btdb):
    """YES at 0.04 entry, resolves YES → NO worth 0.0, loss = full cost basis."""
    sf = get_backtest_session_factory(tmp_btdb)
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=50)

    _seed_market(
        sf, cid="c2", yes_token="yes2", no_token="no2",
        end_date=end_date, outcome_yes=1.0, outcome_no=0.0,
    )
    entry_ts = int((end_date - timedelta(days=45)).timestamp())
    _seed_prices(sf, "yes2", [(entry_ts, 0.04)])

    result = run_bot_a_backtest(
        start=now - timedelta(days=1),
        end=end_date + timedelta(days=1),
        entry_size_usd=Decimal("30"),
        db_path=tmp_btdb,
    )
    assert result.markets_entered == 1
    trade = result.trades[0]
    assert trade.exit_reason == "resolution_lost"
    # Loss = (0 - 0.96) × (30/0.96) = -30
    assert trade.pnl_usd == pytest.approx(-30.0, abs=0.1)


def test_cut_loss_triggers_at_25c(tmp_btdb):
    """YES entry at 0.02, later spikes to 0.30 → cut loss fires."""
    sf = get_backtest_session_factory(tmp_btdb)
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=60)
    entry_ts = int((end_date - timedelta(days=55)).timestamp())
    spike_ts = int((end_date - timedelta(days=30)).timestamp())

    _seed_market(
        sf, cid="c3", yes_token="yes3", no_token="no3",
        end_date=end_date, outcome_yes=1.0, outcome_no=0.0,
    )
    _seed_prices(sf, "yes3", [(entry_ts, 0.02), (spike_ts, 0.30)])

    result = run_bot_a_backtest(
        start=now - timedelta(days=1),
        end=end_date + timedelta(days=1),
        entry_size_usd=Decimal("30"),
        db_path=tmp_btdb,
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "cut_loss"
    # Exit at 1 - 0.30 - 0.01 = 0.69. Entry at 0.98. Loss per share = -0.29.
    size = 30.0 / 0.98
    assert trade.pnl_usd == pytest.approx((0.69 - 0.98) * size, abs=0.01)


def test_skip_market_never_below_threshold(tmp_btdb):
    """YES always > 0.05 → no entry, counted as skipped_price."""
    sf = get_backtest_session_factory(tmp_btdb)
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=60)
    _seed_market(sf, cid="c4", yes_token="yes4", no_token="no4", end_date=end_date)
    entry_ts = int((end_date - timedelta(days=50)).timestamp())
    _seed_prices(sf, "yes4", [(entry_ts, 0.20), (entry_ts + 3600, 0.15)])

    result = run_bot_a_backtest(
        start=now - timedelta(days=1),
        end=end_date + timedelta(days=1),
        db_path=tmp_btdb,
    )
    assert result.markets_entered == 0
    assert result.markets_skipped_price == 1


def test_skip_neg_risk(tmp_btdb):
    sf = get_backtest_session_factory(tmp_btdb)
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=60)
    _seed_market(
        sf, cid="c5", yes_token="yes5", no_token="no5",
        end_date=end_date, is_neg_risk=1,
    )
    _seed_prices(sf, "yes5", [(int((end_date - timedelta(days=40)).timestamp()), 0.02)])

    result = run_bot_a_backtest(
        start=now - timedelta(days=1),
        end=end_date + timedelta(days=1),
        db_path=tmp_btdb,
    )
    assert result.markets_entered == 0


def test_skip_outside_category(tmp_btdb):
    sf = get_backtest_session_factory(tmp_btdb)
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=60)
    _seed_market(
        sf, cid="c6", yes_token="yes6", no_token="no6",
        end_date=end_date, category="sports",
    )
    _seed_prices(sf, "yes6", [(int((end_date - timedelta(days=40)).timestamp()), 0.02)])

    result = run_bot_a_backtest(
        start=now - timedelta(days=1),
        end=end_date + timedelta(days=1),
        db_path=tmp_btdb,
    )
    assert result.markets_entered == 0


def test_summary_aggregates(tmp_btdb):
    sf = get_backtest_session_factory(tmp_btdb)
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=60)
    # Two winners, one loser.
    for i, outcome_no in enumerate([1.0, 1.0, 0.0], start=1):
        cid = f"win{i}"
        _seed_market(
            sf, cid=cid, yes_token=f"y{i}", no_token=f"n{i}",
            end_date=end_date + timedelta(days=i),
            outcome_yes=1.0 - outcome_no, outcome_no=outcome_no,
        )
        entry_ts = int((end_date - timedelta(days=40)).timestamp())
        _seed_prices(sf, f"y{i}", [(entry_ts, 0.03)])

    result = run_bot_a_backtest(
        start=now - timedelta(days=1),
        end=end_date + timedelta(days=5),
        entry_size_usd=Decimal("30"),
        db_path=tmp_btdb,
    )
    assert len(result.trades) == 3
    assert result.win_rate == pytest.approx(2 / 3)
    # 2 winners at ~$0.93 profit each, 1 loser at ~-$30.
    summary = result.summary()
    assert summary["n_trades"] == 3
    assert summary["total_notional_usd"] == pytest.approx(90.0, abs=0.01)
