"""Bot E per-market dedup test (Session 17f audit 2026-04-17).

Bug symptom: 12 paper fills on same cid in 50 seconds because `try_enter`
had no `has_existing_position(subscription_id)` guard. Fix adds the check
right after the halt gates. This file locks the behavior down so no
refactor can silently reintroduce the pile-on.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from bots.bot_e_btc_scalp.executor import (
    EntryDecision,
    TraderState,
    try_enter,
)
from bots.bot_e_btc_scalp.signal import ObiSignal
from bots.bot_e_btc_scalp.sizer import OpenPosition


def _make_signal(sub_id: str = "sol-20260417T1200", side: str = "BUY_YES") -> ObiSignal:
    return ObiSignal(
        subscription_id=sub_id,
        side=side,
        obi=0.9 if side == "BUY_YES" else -0.9,
        abs_obi=0.9,
        window_sec=120.0,
        n_trades=10,
        total_volume=Decimal("500"),
        yes_price=Decimal("0.55"),
        no_price=Decimal("0.45"),
        ts_ms=1_000_000_000,
    )


def _base_kwargs():
    return dict(
        bankroll_usd=Decimal("5000"),
        fixed_trade_usd=Decimal("30"),
        per_trade_cap_frac=Decimal("0.025"),
        crypto_bucket_cap_frac=Decimal("0.10"),
        aggregate_cap_frac=Decimal("0.25"),
        maker_offset=Decimal("0.001"),
        maker_only=True,
        stale_feed_ms=500,
        consecutive_loss_halt_n=5,
        is_halted=False,
        dry_run=True,
        last_feed_age_ms=10,
        symbol="SOL",
        minutes_to_resolution=7.0,
        entry_window_min_sec=300.0,
        entry_window_max_sec=600.0,
    )


class TestBotEPerMarketDedup:
    def test_allows_entry_when_no_existing_position(self):
        state = TraderState()
        assert state.open_positions == []
        decision = try_enter(_make_signal(), state, **_base_kwargs())
        assert decision.accepted is True

    def test_rejects_entry_when_existing_position_same_sub(self):
        state = TraderState()
        state.open_positions = [OpenPosition(
            subscription_id="sol-20260417T1200",
            symbol="SOL",
            side="BUY_YES",
            notional_usd=Decimal("30"),
            is_crypto=True,
        )]
        decision = try_enter(_make_signal("sol-20260417T1200"), state, **_base_kwargs())
        assert decision.accepted is False
        assert decision.reason == "position_exists"

    def test_allows_entry_on_different_subscription(self):
        state = TraderState()
        state.open_positions = [OpenPosition(
            subscription_id="btc-20260417T1200",  # different market
            symbol="BTC",
            side="BUY_YES",
            notional_usd=Decimal("30"),
            is_crypto=True,
        )]
        decision = try_enter(_make_signal("sol-20260417T1200"), state, **_base_kwargs())
        # Different subscription, so should pass the dedup gate; may still be
        # rejected downstream for other reasons but NOT "position_exists".
        assert decision.reason != "position_exists"

    def test_dedup_check_runs_before_feed_freshness(self):
        """A stale signal on an already-entered market should still be
        rejected for position_exists, not stale_feed — dedup comes first
        in the gate order so calibration sees a consistent reject reason.
        """
        state = TraderState()
        state.open_positions = [OpenPosition(
            subscription_id="sol-20260417T1200",
            symbol="SOL",
            side="BUY_YES",
            notional_usd=Decimal("30"),
            is_crypto=True,
        )]
        kw = _base_kwargs()
        kw["last_feed_age_ms"] = 10000  # stale
        decision = try_enter(_make_signal("sol-20260417T1200"), state, **kw)
        assert decision.accepted is False
        assert decision.reason == "position_exists"

    def test_dedup_does_not_fire_when_halted(self):
        """Halt is a harder reject than position_exists — halt reason wins."""
        state = TraderState()
        state.open_positions = [OpenPosition(
            subscription_id="sol-20260417T1200",
            symbol="SOL",
            side="BUY_YES",
            notional_usd=Decimal("30"),
            is_crypto=True,
        )]
        kw = _base_kwargs()
        kw["is_halted"] = True
        decision = try_enter(_make_signal("sol-20260417T1200"), state, **kw)
        assert decision.accepted is False
        assert decision.reason == "halted"

    def test_twelve_consecutive_signals_only_first_passes(self):
        """Simulate the 2026-04-17 10:35 UTC regression. OBI stays above
        threshold across 12 scan iterations. Only the first should pass."""
        from bots.bot_e_btc_scalp.sizer import OpenPosition

        state = TraderState()
        accepted_count = 0
        for _ in range(12):
            decision = try_enter(_make_signal(), state, **_base_kwargs())
            if decision.accepted:
                accepted_count += 1
                # Simulate what __main__.py does post-place: append in-memory.
                state.open_positions.append(OpenPosition(
                    subscription_id="sol-20260417T1200",
                    symbol="SOL",
                    side="BUY_YES",
                    notional_usd=Decimal("30"),
                    is_crypto=True,
                ))
        assert accepted_count == 1
