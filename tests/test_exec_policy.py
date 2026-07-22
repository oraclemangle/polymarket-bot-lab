"""Tests for core/exec_policy.py — toxicity filter + ladder state machine.

Covers:
- compute_toxicity on both BUY and SELL sides
- should_place block/allow around threshold
- next_ladder_action priority: freeze > book-move cancel > age-cancel > step
- LadderManager integration: state transitions, cancel-storm breaker
"""
from __future__ import annotations

import pytest

from core.exec_policy import (
    ActiveLimit,
    BookSnapshot,
    FlowWindow,
    LadderManager,
    LadderPolicy,
    LadderState,
    book_ref_price,
    compute_toxicity,
    next_ladder_action,
    should_place,
)


def _book(**overrides) -> BookSnapshot:
    base = dict(
        best_yes_bid=0.45, best_yes_ask=0.47,
        best_no_bid=0.53, best_no_ask=0.55,
        yes_bid_depth_usd=500.0, yes_ask_depth_usd=500.0,
        no_bid_depth_usd=500.0, no_ask_depth_usd=500.0,
        ts=1000.0,
    )
    base.update(overrides)
    return BookSnapshot(**base)


def _flow(**overrides) -> FlowWindow:
    base = dict(
        ts_start=940.0, ts_end=1000.0,
        aggressive_buy_yes_usd=0.0, aggressive_sell_yes_usd=0.0,
        aggressive_buy_no_usd=0.0, aggressive_sell_no_usd=0.0,
    )
    base.update(overrides)
    return FlowWindow(**base)


# --- toxicity -------------------------------------------------------------


def test_toxicity_yes_buy_blocked_by_aggressive_yes_sellers():
    flow = _flow(aggressive_sell_yes_usd=9000, aggressive_buy_yes_usd=1000)
    tox = compute_toxicity(flow, "YES_BUY")
    assert 0.89 < tox < 0.91


def test_toxicity_yes_buy_zero_when_only_buyers():
    flow = _flow(aggressive_buy_yes_usd=9000)
    assert compute_toxicity(flow, "YES_BUY") == 0.0


def test_toxicity_no_buy_independent_of_yes_flow():
    """YES-side flow should not affect toxicity for a NO_BUY limit."""
    flow = _flow(aggressive_sell_yes_usd=9000)
    assert compute_toxicity(flow, "NO_BUY") == 0.0


def test_toxicity_empty_flow_returns_zero():
    assert compute_toxicity(_flow(), "YES_BUY") == 0.0


def test_toxicity_symmetric_flow_is_half():
    flow = _flow(aggressive_buy_yes_usd=5000, aggressive_sell_yes_usd=5000)
    tox = compute_toxicity(flow, "YES_BUY")
    assert abs(tox - 0.5) < 1e-6


def test_toxicity_unknown_side_raises():
    with pytest.raises(ValueError):
        compute_toxicity(_flow(), "BOGUS")  # type: ignore[arg-type]


def test_toxicity_yes_sell_uses_buy_flow_as_against():
    """For a YES_SELL limit, aggressive BUY YES is against us (buyers lifting)."""
    flow = _flow(aggressive_buy_yes_usd=9000, aggressive_sell_yes_usd=1000)
    tox = compute_toxicity(flow, "YES_SELL")
    assert 0.89 < tox < 0.91


# --- should_place ---------------------------------------------------------


def test_should_place_blocks_on_high_toxicity():
    policy = LadderPolicy()
    flow = _flow(aggressive_sell_yes_usd=9000, aggressive_buy_yes_usd=1000)
    ok, reason = should_place(policy, "YES_BUY", flow)
    assert not ok
    assert reason.startswith("toxicity_block")


def test_should_place_allows_on_benign_flow():
    policy = LadderPolicy()
    flow = _flow(aggressive_buy_yes_usd=5000, aggressive_sell_yes_usd=1000)
    ok, reason = should_place(policy, "YES_BUY", flow)
    assert ok
    assert reason == "ok"


def test_should_place_allows_on_empty_flow():
    ok, reason = should_place(LadderPolicy(), "YES_BUY", _flow())
    assert ok


# --- book_ref_price -------------------------------------------------------


def test_book_ref_price_yes_buy_returns_yes_bid():
    assert book_ref_price(_book(), "YES_BUY") == 0.45


def test_book_ref_price_no_buy_returns_no_bid():
    assert book_ref_price(_book(), "NO_BUY") == 0.53


def test_book_ref_price_yes_sell_returns_yes_ask():
    assert book_ref_price(_book(), "YES_SELL") == 0.47


def test_book_ref_price_unknown_side_raises():
    with pytest.raises(ValueError):
        book_ref_price(_book(), "BOGUS")  # type: ignore[arg-type]


# --- next_ladder_action ---------------------------------------------------


def _limit(**overrides) -> ActiveLimit:
    base = dict(
        order_id="order-1",
        bot_name="bot_a",
        side="YES_BUY",
        original_price=0.45,
        current_price=0.45,
        placed_ts=1000.0,
        state=LadderState.PLACED,
        step_count=0,
    )
    base.update(overrides)
    return ActiveLimit(**base)


def test_freeze_overrides_stepping():
    """When toxicity trips the freeze threshold, stepping is suppressed."""
    limit = _limit(placed_ts=0.0)  # very old
    hostile = _flow(aggressive_sell_yes_usd=9000, aggressive_buy_yes_usd=1000)
    book = _book()
    state, new_price = next_ladder_action(
        limit, book, hostile, atr=0.01, policy=LadderPolicy(), now_ts=2000.0,
    )
    assert state == LadderState.FROZEN
    assert new_price is None


def test_book_move_against_cancels():
    """Book move > k*ATR from original should cancel."""
    limit = _limit(original_price=0.45)
    book = _book(best_yes_bid=0.50)  # moved 5c
    state, new_price = next_ladder_action(
        limit, book, _flow(), atr=0.01, policy=LadderPolicy(book_move_cancel_atr=2.0),
        now_ts=1100.0,
    )
    # 5c move vs 2*0.01 = 2c threshold -> cancel
    assert state == LadderState.CANCELLED
    assert new_price is None


def test_age_cancel_at_or_after_threshold():
    limit = _limit(placed_ts=0.0)
    policy = LadderPolicy(cancel_age_s=1800)
    state, _ = next_ladder_action(
        limit, _book(), _flow(), atr=0.01, policy=policy, now_ts=1801.0,
    )
    assert state == LadderState.CANCELLED


def test_step_1_progression():
    limit = _limit(placed_ts=1000.0, current_price=0.45)
    policy = LadderPolicy(step_1_age_s=300, tick_step=0.01)
    state, new_price = next_ladder_action(
        limit, _book(), _flow(), atr=0.01, policy=policy, now_ts=1310.0,
    )
    assert state == LadderState.STEP_1
    assert new_price == pytest.approx(0.46)


def test_step_2_progression():
    limit = _limit(placed_ts=1000.0, current_price=0.46, state=LadderState.STEP_1, step_count=1)
    policy = LadderPolicy(step_1_age_s=300, step_2_age_s=900, tick_step=0.01)
    state, new_price = next_ladder_action(
        limit, _book(), _flow(), atr=0.01, policy=policy, now_ts=1910.0,
    )
    assert state == LadderState.STEP_2
    # step_2 path uses original current_price + 2*tick_step
    assert new_price == pytest.approx(0.48)


def test_no_step_before_threshold():
    limit = _limit(placed_ts=1000.0)
    state, new_price = next_ladder_action(
        limit, _book(), _flow(), atr=0.01, policy=LadderPolicy(),
        now_ts=1200.0,  # only 200s — below step_1=300
    )
    assert state == LadderState.PLACED
    assert new_price is None


def test_max_step_count_respected():
    limit = _limit(step_count=2, state=LadderState.STEP_2, placed_ts=1000.0)
    policy = LadderPolicy(max_step_count=2)
    state, new_price = next_ladder_action(
        limit, _book(), _flow(), atr=0.01, policy=policy, now_ts=1910.0,
    )
    # Step count already at max; no further step, but also age hasn't hit cancel_age_s.
    assert state == limit.state
    assert new_price is None


def test_atr_zero_skips_book_move_check():
    """When ATR is zero (insufficient data), don't cancel on book move."""
    limit = _limit(original_price=0.45)
    book = _book(best_yes_bid=0.55)
    state, _ = next_ladder_action(
        limit, book, _flow(), atr=0.0, policy=LadderPolicy(), now_ts=1100.0,
    )
    assert state == LadderState.PLACED  # no move-based cancel


def test_negative_atr_raises():
    with pytest.raises(ValueError):
        next_ladder_action(
            _limit(), _book(), _flow(), atr=-0.01, policy=LadderPolicy(), now_ts=1000.0,
        )


# --- LadderManager --------------------------------------------------------


def test_manager_register_and_tick_no_action_in_window():
    mgr = LadderManager(policy=LadderPolicy(), bot_name="bot_a")
    mgr.register(_limit(placed_ts=1000.0))
    actions = mgr.tick(_book(), _flow(), atr=0.01, now_ts=1100.0)
    assert actions == []


def test_manager_step_produces_action():
    mgr = LadderManager(policy=LadderPolicy(step_1_age_s=300), bot_name="bot_a")
    mgr.register(_limit(placed_ts=1000.0))
    actions = mgr.tick(_book(), _flow(), atr=0.01, now_ts=1310.0)
    assert len(actions) == 1
    oid, state, new_price = actions[0]
    assert oid == "order-1"
    assert state == LadderState.STEP_1
    assert new_price == pytest.approx(0.46)
    # Manager must have updated its stored state
    assert mgr._active["order-1"].state == LadderState.STEP_1
    assert mgr._active["order-1"].step_count == 1


def test_manager_forget_removes_limit():
    mgr = LadderManager(policy=LadderPolicy(), bot_name="bot_a")
    mgr.register(_limit())
    assert "order-1" in mgr._active
    mgr.forget("order-1")
    assert "order-1" not in mgr._active


def test_manager_cancel_storm_breaker_trips():
    """If cancel count exceeds limit within window, tick returns [] and trips."""
    mgr = LadderManager(
        policy=LadderPolicy(cancel_age_s=100),
        bot_name="bot_a",
        cancels_per_window_limit=3,
        window_s=60,
    )
    # Register 4 limits all aged enough to cancel
    for i in range(4):
        mgr.register(ActiveLimit(
            order_id=f"order-{i}",
            bot_name="bot_a",
            side="YES_BUY",
            original_price=0.45,
            current_price=0.45,
            placed_ts=0.0,
        ))
    actions = mgr.tick(_book(), _flow(), atr=0.01, now_ts=200.0)
    # All 4 should emit CANCELLED, but the breaker trips at 3.
    # Implementation emits all actions in this single tick (breaker evaluated
    # AFTER each append), so subsequent ticks are the ones that return [].
    cancelled = [a for a in actions if a[1] == LadderState.CANCELLED]
    assert len(cancelled) == 4  # all cancellations in this tick
    assert mgr.tripped is True
    # Subsequent tick returns nothing
    actions2 = mgr.tick(_book(), _flow(), atr=0.01, now_ts=210.0)
    assert actions2 == []


def test_manager_reset_breaker():
    mgr = LadderManager(policy=LadderPolicy(), bot_name="bot_a")
    mgr.tripped = True
    mgr._recent_cancels = [1.0, 2.0, 3.0]
    mgr.reset_breaker()
    assert mgr.tripped is False
    assert mgr._recent_cancels == []
