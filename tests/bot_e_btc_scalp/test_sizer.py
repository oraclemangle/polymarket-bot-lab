"""Tests for bot_e_btc_scalp/sizer.py — maker-entry sizing + caps."""
from __future__ import annotations

from decimal import Decimal

import pytest

from bots.bot_e_btc_scalp.sizer import OpenPosition, size_maker_entry


def _kw(**overrides):
    """Default kwargs for size_maker_entry; override per test."""
    base = dict(
        signal_side="BUY_YES",
        limit_price=Decimal("0.5"),
        bankroll_usd=Decimal("100"),
        fixed_trade_usd=Decimal("2"),
        per_trade_cap_frac=Decimal("0.025"),
        crypto_bucket_cap_frac=Decimal("0.15"),
        aggregate_cap_frac=Decimal("0.30"),
        open_positions=[],
        symbol="BTC",
        is_crypto=True,
    )
    base.update(overrides)
    return base


class TestBasic:
    def test_accepts_first_trade(self):
        d = size_maker_entry(**_kw())
        assert d.can_enter is True
        assert d.reason == "ok"
        assert d.proposed_notional == Decimal("2")
        # $2 @ $0.5 = 4 shares
        assert d.proposed_shares == Decimal("4")

    def test_rejects_zero_limit(self):
        d = size_maker_entry(**_kw(limit_price=Decimal("0")))
        assert d.can_enter is False
        assert "bad_limit_price" in d.reason

    def test_rejects_limit_gte_1(self):
        d = size_maker_entry(**_kw(limit_price=Decimal("1.0")))
        assert d.can_enter is False


class TestCaps:
    def test_per_trade_cap_trims_fixed(self):
        # $10 fixed trade on $100 bankroll with 2.5% cap → capped at $2.50
        d = size_maker_entry(**_kw(fixed_trade_usd=Decimal("10")))
        assert d.can_enter is True
        assert d.proposed_notional == Decimal("2.5")

    def test_crypto_bucket_rejects_when_full(self):
        # Bankroll $100, crypto cap 15% = $15. Already $14 in open crypto.
        # New $2 trade would push to $16, over cap.
        pos = [OpenPosition(
            subscription_id="sub1", symbol="BTC", side="BUY_YES",
            notional_usd=Decimal("14"), is_crypto=True,
        )]
        d = size_maker_entry(**_kw(open_positions=pos))
        assert d.can_enter is False
        assert "crypto_bucket_cap" in d.reason

    def test_crypto_bucket_allows_when_headroom_exists(self):
        pos = [OpenPosition(
            subscription_id="sub1", symbol="BTC", side="BUY_YES",
            notional_usd=Decimal("10"), is_crypto=True,
        )]
        # $10 + $2 = $12 < $15 cap
        d = size_maker_entry(**_kw(open_positions=pos))
        assert d.can_enter is True

    def test_aggregate_cap_rejects_when_full(self):
        # Mix of crypto and non-crypto filling aggregate cap
        pos = [
            OpenPosition("sub1", "BTC", "BUY_YES", Decimal("10"), is_crypto=True),
            OpenPosition("sub2", "X", "BUY_YES", Decimal("19"), is_crypto=False),
        ]
        # Total 29, cap 30, new $2 would push over
        d = size_maker_entry(**_kw(open_positions=pos))
        assert d.can_enter is False
        assert "aggregate_cap" in d.reason

    def test_non_crypto_skips_crypto_bucket(self):
        # 99% of crypto bucket full, but we're placing non-crypto → only aggregate matters
        pos = [OpenPosition(
            subscription_id="sub1", symbol="BTC", side="BUY_YES",
            notional_usd=Decimal("14"), is_crypto=True,
        )]
        d = size_maker_entry(**_kw(open_positions=pos, is_crypto=False, symbol="OTHER"))
        # crypto_now = $14, non-crypto new = $2, total $16, aggregate cap $30 → ok
        assert d.can_enter is True


class TestShareQuantization:
    def test_shares_quantized_to_001(self):
        # $2 notional at $0.43 → 4.6511... → 4.65 shares.
        # (ADR-037 filter: entries < $0.40 rejected; use $0.43.)
        d = size_maker_entry(**_kw(limit_price=Decimal("0.43")))
        assert d.can_enter is True
        assert d.proposed_shares == Decimal("4.65")

    def test_rejects_below_minimum(self):
        # Notional too small to buy 0.01 shares at high price
        # $0.001 / $0.99 = 0.001... → quantized to 0
        d = size_maker_entry(
            **_kw(
                bankroll_usd=Decimal("10"),
                fixed_trade_usd=Decimal("0.001"),
                per_trade_cap_frac=Decimal("1"),
                limit_price=Decimal("0.99"),
            ),
        )
        assert d.can_enter is False


class TestAdr037Filters:
    """ADR-037: post-drill-down tuning — min entry price + max shares."""

    def test_rejects_entry_below_min_price(self):
        # $0.30 < BOT_E_MIN_ENTRY_PRICE (0.40 default)
        d = size_maker_entry(**_kw(limit_price=Decimal("0.30")))
        assert d.can_enter is False
        assert "below_min_entry_price" in d.reason

    def test_accepts_entry_at_min_price(self):
        d = size_maker_entry(**_kw(limit_price=Decimal("0.40")))
        assert d.can_enter is True

    def test_share_cap_clips_tail_at_low_price(self):
        # A $30 paper fixed-USD at $0.44 would naively buy ~68 shares.
        # Cap (default 15) should clip it. Use larger bankroll so the
        # crypto-bucket + aggregate caps don't reject the $30 notional first.
        d = size_maker_entry(
            **_kw(
                bankroll_usd=Decimal("1000"),
                limit_price=Decimal("0.44"),
                fixed_trade_usd=Decimal("30"),
                per_trade_cap_frac=Decimal("1"),
            )
        )
        assert d.can_enter is True
        assert d.proposed_shares <= Decimal("15.00")
