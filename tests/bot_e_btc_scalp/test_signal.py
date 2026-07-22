"""Tests for bot_e_btc_scalp/signal.py — OBI signal engine."""
from __future__ import annotations

from decimal import Decimal

import pytest

from bots.bot_e_btc_scalp.signal import (
    SubscriptionTrades,
    maybe_fire,
)


class TestSubscriptionTrades:
    def test_record_and_prune(self):
        s = SubscriptionTrades(subscription_id="sub1")
        s.set_tokens("Y", "N")
        # All trades at or before "now" (1500ms). Window=500ms → cutoff=1000ms.
        for ts, asset, sz in [(100, "Y", 1), (200, "Y", 1), (1000, "N", 1), (1400, "Y", 1)]:
            s.record_trade(ts, asset, Decimal(str(sz)))
        s.prune(now_ms=1500, window_ms=500)
        # Should keep trades at ts >= 1000: (1000, N, 1) and (1400, Y, 1)
        assert len(s.trades) == 2
        assert s.trades[0][0] == 1000
        assert s.trades[1][0] == 1400

    def test_obi_without_tokens_returns_none(self):
        s = SubscriptionTrades(subscription_id="sub1")
        s.record_trade(100, "Y", Decimal("1"))
        s.record_trade(200, "N", Decimal("1"))
        obi, n, vol = s.compute_obi(1000, 60.0, 2, Decimal("1"))
        assert obi is None

    def test_obi_with_sufficient_data(self):
        s = SubscriptionTrades(subscription_id="sub1")
        s.set_tokens("Y", "N")
        s.record_trade(100, "Y", Decimal("10"))
        s.record_trade(200, "N", Decimal("2"))
        obi, n, vol = s.compute_obi(1000, 60.0, 2, Decimal("1"))
        # (10-2)/(10+2) = 2/3
        assert obi is not None
        assert abs(obi - 2/3) < 1e-6
        assert n == 2
        assert vol == Decimal("12")

    def test_obi_insufficient_trades(self):
        s = SubscriptionTrades(subscription_id="sub1")
        s.set_tokens("Y", "N")
        s.record_trade(100, "Y", Decimal("10"))
        obi, n, vol = s.compute_obi(1000, 60.0, min_trades=2, min_volume=Decimal("1"))
        assert obi is None
        assert n == 1

    def test_obi_insufficient_volume(self):
        s = SubscriptionTrades(subscription_id="sub1")
        s.set_tokens("Y", "N")
        s.record_trade(100, "Y", Decimal("0.1"))
        s.record_trade(200, "N", Decimal("0.1"))
        obi, n, vol = s.compute_obi(1000, 60.0, min_trades=2, min_volume=Decimal("1"))
        assert obi is None
        assert vol == Decimal("0.2")


class TestMaybeFire:
    def test_returns_none_if_no_obi(self):
        s = SubscriptionTrades(subscription_id="sub1")
        sig = maybe_fire(
            s, now_ms=1000,
            window_sec=60, threshold=Decimal("0.2"),
            min_trades=2, min_volume=Decimal("1"),
        )
        assert sig is None

    def test_returns_none_below_threshold(self):
        s = SubscriptionTrades(subscription_id="sub1")
        s.set_tokens("Y", "N")
        # small imbalance
        s.record_trade(100, "Y", Decimal("5.5"))
        s.record_trade(200, "N", Decimal("4.5"))
        sig = maybe_fire(
            s, now_ms=1000,
            window_sec=60, threshold=Decimal("0.2"),
            min_trades=2, min_volume=Decimal("1"),
        )
        # (5.5-4.5)/10 = 0.1, below 0.2 → no fire
        assert sig is None

    def test_fires_buy_yes_when_obi_positive(self):
        s = SubscriptionTrades(subscription_id="sub1")
        s.set_tokens("Y", "N")
        s.last_yes_price = Decimal("0.55")
        s.last_no_price = Decimal("0.45")
        s.record_trade(100, "Y", Decimal("10"))
        s.record_trade(200, "N", Decimal("2"))
        sig = maybe_fire(
            s, now_ms=1000,
            window_sec=60, threshold=Decimal("0.2"),
            min_trades=2, min_volume=Decimal("1"),
        )
        assert sig is not None
        assert sig.side == "BUY_YES"
        assert sig.abs_obi > 0.2
        assert sig.yes_price == Decimal("0.55")
        assert sig.subscription_id == "sub1"

    def test_fires_buy_no_when_obi_negative(self):
        s = SubscriptionTrades(subscription_id="sub1")
        s.set_tokens("Y", "N")
        s.last_yes_price = Decimal("0.25")
        s.last_no_price = Decimal("0.75")
        s.record_trade(100, "Y", Decimal("2"))
        s.record_trade(200, "N", Decimal("10"))
        sig = maybe_fire(
            s, now_ms=1000,
            window_sec=60, threshold=Decimal("0.2"),
            min_trades=2, min_volume=Decimal("1"),
        )
        assert sig is not None
        assert sig.side == "BUY_NO"
        assert sig.no_price == Decimal("0.75")
