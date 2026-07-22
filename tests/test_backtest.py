"""Backtest harness tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from core.backtest import Backtest
from core.db import Book, Market, get_session_factory


@pytest.fixture
def seeded(tmp_db):
    """Seed a market and 3 book snapshots: ascending asks."""
    Session = get_session_factory()
    now = datetime.now(UTC)
    with Session() as s:
        s.add(
            Market(
                condition_id="c1",
                category="geopolitics",
                question="?",
                fee_rate_bps=0,
                yes_token_id="yes1",
                no_token_id="no1",
            )
        )
        for i, price in enumerate((0.05, 0.06, 0.08)):
            s.add(
                Book(
                    token_id="yes1",
                    snapshot_at=now + timedelta(minutes=i),
                    bids=[[str(price - 0.01), "100"]],
                    asks=[[str(price), "100"]],
                )
            )
        s.commit()
    return now


def test_buy_fills_at_touch(seeded, tmp_path):
    bt = Backtest(outdir=tmp_path)

    def buy_once(session, book, market):
        # Buy on first snapshot at limit = ask.
        best_ask = min(Decimal(str(a[0])) for a in book.asks)
        return [(book.token_id, "BUY", best_ask, Decimal("10"))]

    result = bt.run(buy_once, start=seeded - timedelta(seconds=1), end=seeded + timedelta(hours=1))
    assert len(result.trades) == 3  # fires on every snapshot
    # All fills at the ask.
    assert result.trades[0].price == Decimal("0.05")
    assert result.trades[1].price == Decimal("0.06")


def test_sell_without_bid_no_fill(seeded, tmp_path):
    """If limit price is above best bid, no fill."""
    bt = Backtest(outdir=tmp_path)

    def sell_above_bid(session, book, market):
        return [(book.token_id, "SELL", Decimal("0.99"), Decimal("5"))]

    result = bt.run(
        sell_above_bid, start=seeded - timedelta(seconds=1), end=seeded + timedelta(hours=1)
    )
    assert len(result.trades) == 0


def test_output_json_written(seeded, tmp_path):
    bt = Backtest(outdir=tmp_path)
    def noop(session, book, market):
        return []
    result = bt.run(noop, start=seeded - timedelta(seconds=1), end=seeded + timedelta(hours=1))
    path = tmp_path / f"{result.run_id}.json"
    assert path.exists()
    assert "run_id" in path.read_text()
