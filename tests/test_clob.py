"""CLOB wrapper tests — unit-level, no network."""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from core import config
from core.clob import (
    ClobNotReadyError,
    ClobWrapper,
    OrderBook,
    OrderType,
    Side,
    TokenBucket,
)


def test_orderbook_helpers():
    ob = OrderBook(
        token_id="t1",
        bids=[(Decimal("0.04"), Decimal("100")), (Decimal("0.03"), Decimal("50"))],
        asks=[(Decimal("0.06"), Decimal("80")), (Decimal("0.07"), Decimal("20"))],
        timestamp=time.time(),
    )
    assert ob.best_bid() == Decimal("0.04")
    assert ob.best_ask() == Decimal("0.06")
    assert ob.midpoint() == Decimal("0.05")


def test_orderbook_empty_side():
    ob = OrderBook(token_id="t1", bids=[], asks=[], timestamp=0.0)
    assert ob.best_bid() is None
    assert ob.best_ask() is None
    assert ob.midpoint() is None


def test_token_bucket_refills():
    b = TokenBucket(capacity=10, refill_period_seconds=1.0)
    for _ in range(10):
        assert b.acquire(blocking=False)
    assert not b.acquire(blocking=False)
    time.sleep(0.15)  # should refill ~1.5 tokens
    assert b.acquire(blocking=False)


def test_live_guard_blocks_without_preflight(monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    config.reset_settings()
    w = ClobWrapper(keystore=None)
    with pytest.raises(ClobNotReadyError):
        w.place_limit(
            token_id="t1",
            price=Decimal("0.04"),
            size=Decimal("10"),
            side=Side.BUY,
            order_type=OrderType.GTC,
        )
    # Restore paper mode for other tests.
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    config.reset_settings()


def test_live_guard_allows_after_preflight(monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    config.reset_settings()
    w = ClobWrapper(keystore=None)
    w.mark_preflight_done(hmac=True, addrs=True, collateral=True)
    # Still can't call live — keystore is None — but the specific error changes.
    with pytest.raises(Exception) as ex:
        w.place_limit(
            token_id="t1",
            price=Decimal("0.04"),
            size=Decimal("10"),
            side=Side.BUY,
        )
    assert "ClobNotReadyError" not in str(type(ex.value))
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    config.reset_settings()


def test_paper_place_returns_synthetic_order(monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    config.reset_settings()
    w = ClobWrapper(keystore=None)
    resp = w.place_limit(
        token_id="t1",
        price=Decimal("0.04"),
        size=Decimal("10"),
        side=Side.BUY,
    )
    assert resp.order_id.startswith("paper-")
    assert resp.status == "PAPER_OPEN"


def test_paper_cancel_always_succeeds(monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    config.reset_settings()
    w = ClobWrapper(keystore=None)
    assert w.cancel_order("paper-abc123") is True
    assert w.cancel_all() == 0
