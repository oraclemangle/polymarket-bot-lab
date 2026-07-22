"""Tests for bot_e_btc_scalp/executor.py — pre-trade chain + halts."""
from __future__ import annotations

from decimal import Decimal

import pytest

from bots.bot_e_btc_scalp.executor import (
    EntryDecision,
    TAG_OBI_NO,
    TAG_OBI_YES,
    TraderState,
    _compute_maker_limit,
    record_outcome,
    should_halt_trailing,
    try_enter,
)
from bots.bot_e_btc_scalp.signal import ObiSignal


def _signal(side="BUY_YES", yes=Decimal("0.55"), no=Decimal("0.45"), obi=0.4):
    return ObiSignal(
        subscription_id="btc-202604171500",
        side=side,
        obi=obi,
        abs_obi=abs(obi),
        window_sec=120,
        n_trades=10,
        total_volume=Decimal("100"),
        yes_price=yes,
        no_price=no,
        ts_ms=1000,
    )


def _kw(**overrides):
    base = dict(
        state=TraderState(),
        bankroll_usd=Decimal("100"),
        fixed_trade_usd=Decimal("2"),
        per_trade_cap_frac=Decimal("0.025"),
        crypto_bucket_cap_frac=Decimal("0.15"),
        aggregate_cap_frac=Decimal("0.30"),
        maker_offset=Decimal("0.001"),
        maker_only=True,
        stale_feed_ms=500,
        consecutive_loss_halt_n=5,
        is_halted=False,
        dry_run=True,
        last_feed_age_ms=100,
        symbol="BTC",
        minutes_to_resolution=7.5,   # within t-5 to t-10 window
        entry_window_min_sec=300,
        entry_window_max_sec=600,
    )
    base.update(overrides)
    return base


class TestComputeMakerLimit:
    def test_buy_yes_places_below_yes_price(self):
        limit = _compute_maker_limit(
            signal_side="BUY_YES",
            yes_price=Decimal("0.55"),
            no_price=Decimal("0.45"),
            maker_offset=Decimal("0.001"),
        )
        # Below yes_price by offset, quantized to 0.001
        assert limit == Decimal("0.549")

    def test_buy_no_places_below_no_price(self):
        limit = _compute_maker_limit(
            signal_side="BUY_NO",
            yes_price=Decimal("0.25"),
            no_price=Decimal("0.75"),
            maker_offset=Decimal("0.001"),
        )
        assert limit == Decimal("0.749")

    def test_clamps_to_floor(self):
        limit = _compute_maker_limit(
            signal_side="BUY_YES",
            yes_price=Decimal("0.0005"),
            no_price=Decimal("0.9995"),
            maker_offset=Decimal("0.001"),
        )
        # Would compute 0.0005 - 0.001 = -0.0005, clamped to 0.001
        assert limit == Decimal("0.001")

    def test_missing_price_returns_none(self):
        assert _compute_maker_limit(
            signal_side="BUY_YES", yes_price=None, no_price=Decimal("0.5"),
            maker_offset=Decimal("0.001"),
        ) is None


class TestTryEnter:
    def test_accepts_valid_dry_run(self):
        d = try_enter(_signal(), **_kw())
        assert d.accepted is True
        assert d.reason == "dry_run"
        assert d.strategy_signal == TAG_OBI_YES
        assert d.reason_code == "liquidity_weak"
        assert d.reason_detail is not None and "obi=" in d.reason_detail

    def test_sets_obi_no_tag_for_no_side(self):
        d = try_enter(_signal(side="BUY_NO"), **_kw())
        assert d.strategy_signal == TAG_OBI_NO

    def test_rejects_when_halted(self):
        d = try_enter(_signal(), **_kw(is_halted=True))
        assert d.accepted is False
        assert d.reason == "halted"

    def test_rejects_stale_feed(self):
        d = try_enter(_signal(), **_kw(last_feed_age_ms=1000, stale_feed_ms=500))
        assert d.accepted is False
        assert "stale_feed" in d.reason

    def test_rejects_pre_entry_window(self):
        d = try_enter(_signal(), **_kw(minutes_to_resolution=15))  # 900s > max 600
        assert d.accepted is False
        assert "pre_entry_window" in d.reason

    def test_rejects_past_entry_window(self):
        d = try_enter(_signal(), **_kw(minutes_to_resolution=4))  # 240s < min 300
        assert d.accepted is False
        assert "past_entry_window" in d.reason

    def test_rejects_when_maker_only_disabled(self):
        d = try_enter(_signal(), **_kw(maker_only=False))
        assert d.accepted is False
        assert "maker_only_required" in d.reason

    def test_rejects_consecutive_losses(self):
        state = TraderState(consecutive_losses=5)
        d = try_enter(_signal(), **_kw(state=state, consecutive_loss_halt_n=5))
        assert d.accepted is False
        assert "consecutive_loss_halt" in d.reason

    def test_rejects_no_price_for_maker(self):
        sig = _signal(yes=None, no=None)
        d = try_enter(sig, **_kw())
        assert d.accepted is False
        assert "no_price_for_maker_limit" in d.reason


class TestHaltMachinery:
    def test_record_outcome_win_resets_streak(self):
        state = TraderState(consecutive_losses=3)
        record_outcome(state, win=True, now_ms=1000)
        assert state.consecutive_losses == 0

    def test_record_outcome_loss_increments(self):
        state = TraderState(consecutive_losses=0)
        record_outcome(state, win=False, now_ms=1000)
        record_outcome(state, win=False, now_ms=2000)
        assert state.consecutive_losses == 2

    def test_trailing_halt_fires(self):
        state = TraderState()
        # 12 losses in last 20
        for i in range(20):
            record_outcome(state, win=(i >= 12), now_ms=1000 + i)
        # recent_outcomes: [L]*12 + [W]*8  → 12 losses
        assert should_halt_trailing(state, trailing_n=12, trailing_window=20) is True

    def test_trailing_halt_does_not_fire_without_enough_data(self):
        state = TraderState()
        for i in range(5):
            record_outcome(state, win=False, now_ms=1000 + i)
        assert should_halt_trailing(state, trailing_n=12, trailing_window=20) is False
