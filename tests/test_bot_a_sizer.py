"""Bot A position sizing tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from bots.bot_a.sizer import shares_from_notional, size_position


def test_fixed_size_at_large_bankroll():
    n = size_position(bankroll_usd=Decimal("100000"), no_ask_depth_usd=Decimal("10000"))
    assert n == Decimal("30.00")


def test_bankroll_cap_binds_at_small_bankroll():
    # 5% of $400 = $20; should win over $30 fixed.
    n = size_position(bankroll_usd=Decimal("400"), no_ask_depth_usd=Decimal("10000"))
    assert n == Decimal("20.00")


def test_depth_cap_binds_at_thin_book():
    # 5% of $400 = $20; should win.
    n = size_position(bankroll_usd=Decimal("100000"), no_ask_depth_usd=Decimal("400"))
    assert n == Decimal("20.00")


def test_all_three_caps_intersect():
    # bankroll cap 5% of $400 = $20, depth cap 5% of $400 = $20, fixed $30 — $20 wins.
    n = size_position(bankroll_usd=Decimal("400"), no_ask_depth_usd=Decimal("400"))
    assert n == Decimal("20.00")


def test_shares_conversion():
    shares = shares_from_notional(Decimal("30"), Decimal("0.96"))
    # $30 at 96¢ = 31.25 shares
    assert shares == Decimal("31.25")


def test_invalid_price_rejected():
    with pytest.raises(ValueError):
        shares_from_notional(Decimal("30"), Decimal("0"))
