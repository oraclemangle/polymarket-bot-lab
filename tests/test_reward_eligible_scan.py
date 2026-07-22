"""Tests for reward eligibility reporting helpers."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from scripts.reward_eligible_scan import RewardMarket, _order_reward_check, build_report


def _market() -> RewardMarket:
    return RewardMarket(
        condition_id="cid_reward",
        question="Will the test market resolve Yes?",
        market_slug="test-market",
        event_slug="test-event",
        reward_per_day=Decimal("12.50"),
        rewards_min_size=Decimal("100"),
        rewards_max_spread_cents=Decimal("3"),
        spread=Decimal("0.02"),
        volume_24hr=Decimal("1000"),
        tokens=({"token_id": "tok_yes", "price": "0.45"},),
    )


def test_order_reward_check_accepts_maker_order_inside_band():
    order = SimpleNamespace(
        order_type="GTC",
        price=Decimal("0.47"),
        size=Decimal("150"),
        token_id="tok_yes",
    )

    ok, reason = _order_reward_check(order, _market())

    assert ok is True
    assert reason == "inside reward band"


def test_order_reward_check_rejects_below_min_size_before_band():
    order = SimpleNamespace(
        order_type="GTC",
        price=Decimal("0.46"),
        size=Decimal("50"),
        token_id="tok_yes",
    )

    ok, reason = _order_reward_check(order, _market())

    assert ok is False
    assert reason == "size 50 < min 100"


def test_build_report_counts_reward_overlap_and_fee_candidates():
    orders = [
        SimpleNamespace(
            bot_id="bot_live",
            condition_id="cid_reward",
            token_id="tok_yes",
            status="OPEN",
            order_type="GTC",
            price=Decimal("0.46"),
            size=Decimal("120"),
        )
    ]
    trades = [
        SimpleNamespace(
            bot_id="bot_live",
            condition_id="cid_reward",
            price=Decimal("0.45"),
            size=Decimal("10"),
        )
    ]

    report = build_report(
        markets=[_market()],
        orders=orders,
        trades=trades,
        fee_info={"cid_reward": {"tbf": "0.25"}},
        lookback_hours=24,
    )

    assert "`bot_live` | 1 | 1 | 1 | 1 | $4.50 | 1" in report
    assert "currently reward-scoring candidate" in report
