"""Tiny live-probe readiness primitives.

This module is intentionally order-path neutral: it validates proposed probe
state, dry-run posture, cap envelopes, and kill gates, but it never creates a
CLOB client or submits an order.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class TinyLiveProbeSpec:
    lane_id: str
    display_name: str
    bot_id: str
    market_scope: str
    allowed_actions: tuple[str, ...]
    max_order_usd: Decimal
    daily_gross_cap_usd: Decimal
    open_exposure_cap_usd: Decimal
    max_concurrent_positions: int
    kill_switches: tuple[str, ...]
    rollback_plan: tuple[str, ...]
    approval_question: str
    live_service_name: str | None = None
    gas_cap_usd: Decimal | None = None
    requires_depth_join: bool = False
    notes: tuple[str, ...] = ()

    @property
    def max_loss_usd(self) -> Decimal:
        """Worst-case funded loss while every position is open."""
        return self.open_exposure_cap_usd


@dataclass(frozen=True)
class ProbeReadinessInput:
    action: str
    order_notional_usd: Decimal
    daily_gross_used_usd: Decimal = Decimal("0")
    open_exposure_usd: Decimal = Decimal("0")
    open_positions: int = 0
    live_enabled: bool = False
    dry_run: bool = True
    wallet_material_present: bool = False
    depth_join_ok: bool = True
    gas_estimate_usd: Decimal | None = None
    same_condition_overlap: bool = False


@dataclass(frozen=True)
class ProbeCheck:
    allowed: bool
    reason: str
    failures: tuple[str, ...] = ()


def check_probe_entry(spec: TinyLiveProbeSpec, state: ProbeReadinessInput) -> ProbeCheck:
    """Validate a single proposed tiny-live entry against immutable caps."""
    failures: list[str] = []
    if state.live_enabled:
        failures.append("live_enabled_without_operator_approval")
    if not state.dry_run:
        failures.append("non_dry_run_forbidden_in_readiness")
    if state.wallet_material_present:
        failures.append("wallet_material_present")
    if state.action not in spec.allowed_actions:
        failures.append(f"action_not_allowed:{state.action}")
    if state.order_notional_usd <= Decimal("0"):
        failures.append("non_positive_order_notional")
    if state.order_notional_usd > spec.max_order_usd:
        failures.append("max_order_cap")
    if state.daily_gross_used_usd + state.order_notional_usd > spec.daily_gross_cap_usd:
        failures.append("daily_gross_cap")
    if state.open_exposure_usd + state.order_notional_usd > spec.open_exposure_cap_usd:
        failures.append("open_exposure_cap")
    if state.open_positions >= spec.max_concurrent_positions:
        failures.append("max_concurrent_positions")
    if spec.requires_depth_join and not state.depth_join_ok:
        failures.append("depth_join_required")
    if spec.gas_cap_usd is not None:
        if state.gas_estimate_usd is None:
            failures.append("gas_estimate_required")
        elif state.gas_estimate_usd > spec.gas_cap_usd:
            failures.append("gas_cap")
    if state.same_condition_overlap:
        failures.append("same_condition_overlap")
    if failures:
        return ProbeCheck(False, failures[0], tuple(failures))
    return ProbeCheck(True, "ok")


def _decimal_metric(metrics: dict[str, Any], key: str) -> Decimal | None:
    value = metrics.get(key)
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def evaluate_kill_gates(lane_id: str, metrics: dict[str, Any]) -> tuple[str, ...]:
    """Return triggered kill gates for the supported tiny-live candidates."""
    triggered: list[str] = []
    if lane_id == "bot_d_station_lock":
        if metrics.get("classifier_settlement_mismatch"):
            triggered.append("classifier_settlement_mismatch")
        if int(metrics.get("hard_lock_losses", 0) or 0) >= 2:
            triggered.append("two_hard_lock_losses")
        pnl = _decimal_metric(metrics, "realised_pnl_usd")
        if pnl is not None and pnl <= Decimal("-10"):
            triggered.append("realised_pnl_lte_minus_10")
        if metrics.get("stale_station_data"):
            triggered.append("stale_station_data")
        if metrics.get("live_order_or_reconcile_anomaly"):
            triggered.append("live_order_or_reconcile_anomaly")
    elif lane_id == "bot_d_spike":
        if metrics.get("rule_violation"):
            triggered.append("rule_violation")
        if int(metrics.get("consecutive_resolved_losses", 0) or 0) >= 5:
            triggered.append("five_consecutive_resolved_losses")
        pnl = _decimal_metric(metrics, "realised_pnl_usd")
        if pnl is not None and pnl <= Decimal("-8"):
            triggered.append("realised_pnl_lte_minus_8")
        if metrics.get("clob_auth_or_reconcile_fault"):
            triggered.append("clob_auth_or_reconcile_fault")
        if metrics.get("overlaps_other_bot_d_live_exposure"):
            triggered.append("overlap_with_other_bot_d_live_exposure")
    elif lane_id == "bot_l_complete_set":
        unhedged = _decimal_metric(metrics, "unhedged_leg_usd")
        if unhedged is not None and unhedged > Decimal("2"):
            triggered.append("unhedged_leg_gt_2")
        pnl = _decimal_metric(metrics, "net_realised_after_gas_usd")
        if pnl is not None and pnl <= Decimal("-3"):
            triggered.append("net_realised_lte_minus_3_after_gas")
        for key in (
            "depth_join_failure",
            "merge_failure",
            "stuck_inventory",
            "atomicity_or_reconciliation_anomaly",
        ):
            if metrics.get(key):
                triggered.append(key)
    else:
        triggered.append("unknown_lane")
    return tuple(triggered)


def spec_to_dict(spec: TinyLiveProbeSpec) -> dict[str, Any]:
    return {
        "lane_id": spec.lane_id,
        "display_name": spec.display_name,
        "bot_id": spec.bot_id,
        "market_scope": spec.market_scope,
        "allowed_actions": list(spec.allowed_actions),
        "max_order_usd": str(spec.max_order_usd),
        "daily_gross_cap_usd": str(spec.daily_gross_cap_usd),
        "open_exposure_cap_usd": str(spec.open_exposure_cap_usd),
        "max_concurrent_positions": spec.max_concurrent_positions,
        "max_loss_usd": str(spec.max_loss_usd),
        "gas_cap_usd": str(spec.gas_cap_usd) if spec.gas_cap_usd is not None else None,
        "requires_depth_join": spec.requires_depth_join,
        "live_service_name": spec.live_service_name,
        "kill_switches": list(spec.kill_switches),
        "rollback_plan": list(spec.rollback_plan),
        "approval_question": spec.approval_question,
        "notes": list(spec.notes),
    }
