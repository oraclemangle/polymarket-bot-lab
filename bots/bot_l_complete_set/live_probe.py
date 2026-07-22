"""Bot L complete-set tiny live-probe readiness.

The only live-probe shape prepared here is BUY/MERGE. SELL/SPLIT remains
research-only and is deliberately excluded from allowed actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from core.tiny_live_probe import (
    ProbeCheck,
    ProbeReadinessInput,
    TinyLiveProbeSpec,
    check_probe_entry,
)

LIVE_PROBE_SPEC = TinyLiveProbeSpec(
    lane_id="bot_l_complete_set",
    display_name="Bot L Complete-Set BUY/MERGE Tiny Live Probe",
    bot_id="bot_l_complete_set",
    market_scope="BTC 5m complete-set convergence only; BUY both legs then MERGE only.",
    allowed_actions=("BUY_COMPLETE_SET", "MERGE_COMPLETE_SET"),
    max_order_usd=Decimal("1"),
    daily_gross_cap_usd=Decimal("10"),
    open_exposure_cap_usd=Decimal("20"),
    max_concurrent_positions=2,
    gas_cap_usd=Decimal("0.25"),
    requires_depth_join=True,
    kill_switches=(
        "any unhedged leg >$2",
        "net realised <= -$3 after gas",
        "depth join failure",
        "merge failure",
        "stuck inventory",
        "any atomicity/reconciliation anomaly",
    ),
    rollback_plan=(
        "Stop and disable the Bot L live-probe service.",
        "Keep the Bot L paper timer running for depth-validated comparison.",
        "Do not run a SELL/SPLIT path; merge or emergency-cancel through approved tooling only.",
        "Record the kill event in CHANGELOG, MEMORY, and OQ-111 before any restart.",
    ),
    approval_question=(
        "the operator, approve enabling Bot L Complete-Set as a BUY/MERGE-only tiny live probe "
        "with depth-enforced same-asset book joins, max bundle gross $1, daily gross $10, "
        "open exposure $20, max 2 concurrent bundles, gas cap $0.25 per bundle, and "
        "the listed kill switches?"
    ),
    live_service_name="polymarket-bot-l-complete-set-live-probe-vps.service",
    notes=(
        "SELL_COMPLETE_SET and SPLIT/SELL are intentionally not live-probe actions.",
        "Current deployed Bot L unit remains paper-only.",
    ),
)


@dataclass(frozen=True)
class CompleteSetBundlePlan:
    action: str
    gross_cost_usd: Decimal
    daily_gross_used_usd: Decimal = Decimal("0")
    open_exposure_usd: Decimal = Decimal("0")
    open_bundles: int = 0
    depth_join_ok: bool = True
    gas_estimate_usd: Decimal = Decimal("0")
    dry_run: bool = True
    live_enabled: bool = False
    wallet_material_present: bool = False


def check_bundle_plan(plan: CompleteSetBundlePlan) -> ProbeCheck:
    return check_probe_entry(
        LIVE_PROBE_SPEC,
        ProbeReadinessInput(
            action=plan.action,
            order_notional_usd=plan.gross_cost_usd,
            daily_gross_used_usd=plan.daily_gross_used_usd,
            open_exposure_usd=plan.open_exposure_usd,
            open_positions=plan.open_bundles,
            live_enabled=plan.live_enabled,
            dry_run=plan.dry_run,
            wallet_material_present=plan.wallet_material_present,
            depth_join_ok=plan.depth_join_ok,
            gas_estimate_usd=plan.gas_estimate_usd,
        ),
    )
