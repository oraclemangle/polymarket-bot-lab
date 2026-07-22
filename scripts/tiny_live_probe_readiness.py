#!/usr/bin/env python3
"""Render tiny live-probe readiness packets.

Read-only. Does not create CLOB clients, read wallet material, place orders,
enable services, or restart anything.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bots.bot_d_spike.config import LIVE_PROBE_SPEC as BOT_D_SPIKE_SPEC
from bots.bot_d_weather.station_lock import STATION_LOCK_LIVE_PROBE_SPEC
from bots.bot_l_complete_set.live_probe import LIVE_PROBE_SPEC as BOT_L_SPEC
from core.tiny_live_probe import ProbeReadinessInput, check_probe_entry, spec_to_dict

SPECS = (STATION_LOCK_LIVE_PROBE_SPEC, BOT_D_SPIKE_SPEC, BOT_L_SPEC)


def build_report() -> dict[str, Any]:
    lanes = []
    for spec in SPECS:
        dry_check = check_probe_entry(
            spec,
            ProbeReadinessInput(
                action=spec.allowed_actions[0],
                order_notional_usd=spec.max_order_usd,
                dry_run=True,
                live_enabled=False,
                wallet_material_present=False,
                depth_join_ok=True,
                gas_estimate_usd=spec.gas_cap_usd,
            ),
        )
        live_check = check_probe_entry(
            spec,
            ProbeReadinessInput(
                action=spec.allowed_actions[0],
                order_notional_usd=spec.max_order_usd,
                dry_run=False,
                live_enabled=True,
                wallet_material_present=True,
                depth_join_ok=True,
                gas_estimate_usd=spec.gas_cap_usd,
            ),
        )
        lanes.append(
            {
                **spec_to_dict(spec),
                "readiness_state": "operator_approved_not_deployed",
                "dry_run_preflight": {
                    "allowed": dry_check.allowed,
                    "reason": dry_check.reason,
                    "failures": list(dry_check.failures),
                },
                "live_mode_guard": {
                    "allowed": live_check.allowed,
                    "reason": live_check.reason,
                    "failures": list(live_check.failures),
                },
            }
        )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "deployment_state": "operator_approved_dashboard_live_not_deployed",
        "fund_safety": {
            "places_live_orders": False,
            "reads_wallet_or_keystore": False,
            "enables_services": False,
            "activation_adr": "ADR-165",
            "requires_noel_approval": False,
            "requires_deploy_before_orders": True,
        },
        "lanes": lanes,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Tiny Live-Probe Readiness Packet",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Safety State",
        "",
        f"- Deployment state: `{report['deployment_state']}`",
        "- No live orders, wallet reads, service enables, restarts, or deployments are performed by this packet.",
        "- the operator approval is recorded in ADR-165; runtime deployment and service enablement were not performed by this report.",
        "",
        "## Lane Caps",
        "",
        "| lane | max order | daily gross | open exposure | concurrent | allowed actions | max loss |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for lane in report["lanes"]:
        lines.append(
            "| {name} | ${max_order} | ${daily} | ${open_exp} | {concurrent} | {actions} | ${max_loss} |".format(
                name=lane["display_name"],
                max_order=lane["max_order_usd"],
                daily=lane["daily_gross_cap_usd"],
                open_exp=lane["open_exposure_cap_usd"],
                concurrent=lane["max_concurrent_positions"],
                actions=", ".join(lane["allowed_actions"]),
                max_loss=lane["max_loss_usd"],
            )
        )
    for lane in report["lanes"]:
        lines.extend(
            [
                "",
                f"## {lane['display_name']}",
                "",
                f"- Bot id: `{lane['bot_id']}`",
                f"- Market scope: {lane['market_scope']}",
                f"- Live service template: `{lane['live_service_name']}`",
                f"- Dry-run preflight: `{lane['dry_run_preflight']['reason']}`",
                f"- Live-mode guard: `{lane['live_mode_guard']['reason']}`",
                "- Kill switches:",
            ]
        )
        lines.extend(f"  - {item}" for item in lane["kill_switches"])
        lines.append("- Rollback:")
        lines.extend(f"  - {item}" for item in lane["rollback_plan"])
        lines.extend(["", "**Approval question:**", "", lane["approval_question"]])
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"tiny_live_probe_readiness_{stamp}.json"
    md_path = out_dir / f"tiny_live_probe_readiness_{stamp}.md"
    latest_json = out_dir / "latest.json"
    latest_md = out_dir / "latest.md"
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    md_text = render_markdown(report)
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "latest_json": str(latest_json),
        "latest_markdown": str(latest_md),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("data/reports/tiny_live_probe_readiness"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        paths = write_outputs(report, args.out_dir)
        print(json.dumps({"generated_at": report["generated_at"], "paths": paths}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
