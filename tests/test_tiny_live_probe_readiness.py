from __future__ import annotations

from decimal import Decimal

from bots.bot_d_spike.config import LIVE_PROBE_SPEC as SPIKE_SPEC
from bots.bot_d_weather.station_lock import STATION_LOCK_LIVE_PROBE_SPEC
from bots.bot_l_complete_set.live_probe import CompleteSetBundlePlan, check_bundle_plan
from core.tiny_live_probe import ProbeReadinessInput, check_probe_entry, evaluate_kill_gates
from scripts.tiny_live_probe_readiness import build_report


def test_station_lock_caps_and_live_guard():
    ok = check_probe_entry(
        STATION_LOCK_LIVE_PROBE_SPEC,
        ProbeReadinessInput(action="BUY_NO", order_notional_usd=Decimal("5")),
    )
    assert ok.allowed is True

    over_order = check_probe_entry(
        STATION_LOCK_LIVE_PROBE_SPEC,
        ProbeReadinessInput(action="BUY_NO", order_notional_usd=Decimal("5.01")),
    )
    assert over_order.allowed is False
    assert "max_order_cap" in over_order.failures

    live = check_probe_entry(
        STATION_LOCK_LIVE_PROBE_SPEC,
        ProbeReadinessInput(
            action="BUY_NO",
            order_notional_usd=Decimal("1"),
            dry_run=False,
            live_enabled=True,
            wallet_material_present=True,
        ),
    )
    assert live.allowed is False
    assert live.failures[:3] == (
        "live_enabled_without_operator_approval",
        "non_dry_run_forbidden_in_readiness",
        "wallet_material_present",
    )


def test_spike_daily_open_and_overlap_caps():
    daily = check_probe_entry(
        SPIKE_SPEC,
        ProbeReadinessInput(
            action="BUY_YES",
            order_notional_usd=Decimal("2"),
            daily_gross_used_usd=Decimal("9"),
        ),
    )
    assert daily.allowed is False
    assert daily.reason == "daily_gross_cap"

    open_cap = check_probe_entry(
        SPIKE_SPEC,
        ProbeReadinessInput(
            action="BUY_YES",
            order_notional_usd=Decimal("2"),
            open_positions=10,
        ),
    )
    assert open_cap.reason == "max_concurrent_positions"

    overlap = check_probe_entry(
        SPIKE_SPEC,
        ProbeReadinessInput(
            action="BUY_YES",
            order_notional_usd=Decimal("2"),
            same_condition_overlap=True,
        ),
    )
    assert overlap.reason == "same_condition_overlap"


def test_bot_l_buy_merge_only_depth_and_gas_caps():
    sell = check_bundle_plan(
        CompleteSetBundlePlan(action="SELL_COMPLETE_SET", gross_cost_usd=Decimal("1"))
    )
    assert sell.allowed is False
    assert sell.reason == "action_not_allowed:SELL_COMPLETE_SET"

    no_depth = check_bundle_plan(
        CompleteSetBundlePlan(
            action="BUY_COMPLETE_SET",
            gross_cost_usd=Decimal("1"),
            depth_join_ok=False,
        )
    )
    assert no_depth.reason == "depth_join_required"

    gas = check_bundle_plan(
        CompleteSetBundlePlan(
            action="BUY_COMPLETE_SET",
            gross_cost_usd=Decimal("1"),
            gas_estimate_usd=Decimal("0.26"),
        )
    )
    assert gas.reason == "gas_cap"


def test_kill_gate_evaluation_for_all_three_lanes():
    assert evaluate_kill_gates(
        "bot_d_station_lock",
        {"hard_lock_losses": 2, "realised_pnl_usd": "-10"},
    ) == ("two_hard_lock_losses", "realised_pnl_lte_minus_10")
    assert evaluate_kill_gates(
        "bot_d_spike",
        {"consecutive_resolved_losses": 5, "overlaps_other_bot_d_live_exposure": True},
    ) == ("five_consecutive_resolved_losses", "overlap_with_other_bot_d_live_exposure")
    assert evaluate_kill_gates(
        "bot_l_complete_set",
        {"unhedged_leg_usd": "2.01", "merge_failure": True},
    ) == ("unhedged_leg_gt_2", "merge_failure")


def test_readiness_report_stays_operator_blocked_and_no_wallet():
    report = build_report()
    assert report["deployment_state"] == "operator_approved_dashboard_live_not_deployed"
    assert report["fund_safety"]["reads_wallet_or_keystore"] is False
    assert report["fund_safety"]["activation_adr"] == "ADR-165"
    assert len(report["lanes"]) == 3
    for lane in report["lanes"]:
        assert lane["readiness_state"] == "operator_approved_not_deployed"
        assert lane["dry_run_preflight"]["allowed"] is True
        assert lane["live_mode_guard"]["allowed"] is False
        assert "approval_question" in lane
