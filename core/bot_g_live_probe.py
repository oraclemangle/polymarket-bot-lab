"""Reporting-only Bot G tiny-live probe plan.

This module intentionally contains no order-placement logic. It exists so the
dashboard, hourly report, and docs can use one shared readiness vocabulary.
"""

from __future__ import annotations

from typing import Any

PROPOSED_STARTING_TRADE_USD = 1.0
PROPOSED_LIVE_WALLET_USD = 200.0
PROPOSED_DAILY_ENTRY_CAP = 20
PROPOSED_GROSS_NOTIONAL_CAP_USD = 100.0
PROPOSED_MAX_OPEN_POSITIONS = 10


def _pct(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def bot_g_tiny_live_probe_plan(
    *,
    dry_run: bool,
    env: str,
    global_env: str = "paper",
    effective_paper: bool | None = None,
    runtime_source: str = "dashboard_env",
    live_approved_at: str = "",
    live_wallet_usd: float | str | None = None,
    trade_metrics: dict[str, Any] | None = None,
    order_metrics: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the operator-facing Bot G tiny-live readiness plan.

    The returned object is diagnostic/reporting state only. It must not be used
    as an execution gate by a trader process.
    """
    trade_metrics = trade_metrics or {}
    order_metrics = order_metrics or {}
    validation = validation or {}
    try:
        proposed_live_wallet_usd = float(
            live_wallet_usd if live_wallet_usd is not None else PROPOSED_LIVE_WALLET_USD
        )
    except (TypeError, ValueError):
        proposed_live_wallet_usd = PROPOSED_LIVE_WALLET_USD
    gate = validation.get("live_candidate_gate") or {}
    live_intent = (str(env).lower() == "live") and not dry_run
    if effective_paper is None:
        effective_paper = (not live_intent) or str(global_env).lower() != "live"
    runtime_live = not bool(effective_paper)
    gate_candidate = bool(validation.get("live_ready")) and gate.get("status") == "candidate"
    approval_recorded = bool(live_approved_at)

    checklist = [
        {
            "key": "runtime_paper",
            "label": "Current runtime stays paper/effective-paper",
            "pass": bool(effective_paper),
            "detail": (
                f"BOT_G_ENV={env}; BOT_G_DRY_RUN={str(dry_run).lower()}; "
                f"POLYMARKET_ENV={global_env}; source={runtime_source}"
            ),
        },
        {
            "key": "candidate_gate",
            "label": "ADR-073 candidate gate clears",
            "pass": gate_candidate,
            "detail": gate.get("status") or "unknown",
        },
        {
            "key": "explicit_approval",
            "label": "the operator explicitly approves live activation",
            "pass": approval_recorded,
            "detail": (
                f"BOT_G_LIVE_APPROVED_AT={live_approved_at}"
                if live_approved_at
                else "Required before any env, wallet, or order-path change."
            ),
        },
        {
            "key": "tiny_caps",
            "label": "Tiny-live caps are accepted",
            "pass": approval_recorded,
            "detail": (
                f"${proposed_live_wallet_usd:.0f} wallet, "
                f"${PROPOSED_STARTING_TRADE_USD:.0f}/entry, "
                f"{PROPOSED_DAILY_ENTRY_CAP}/day, "
                f"${PROPOSED_GROSS_NOTIONAL_CAP_USD:.0f}/day gross notional."
            ),
        },
        {
            "key": "rollback_runbook",
            "label": "Paper rollback runbook exists",
            "pass": True,
            "detail": "docs/bot-g-tiny-live-runbook-2026-05-02.md",
        },
        {
            "key": "live_reconciler",
            "label": "Live fill reconciler is wired",
            "pass": True,
            "detail": "Bot G polls Portfolio.reconcile_live_fills when effective-paper is false.",
        },
        {
            "key": "live_caps",
            "label": "Tiny-live caps are code-visible",
            "pass": True,
            "detail": (
                f"Live-only caps: {PROPOSED_DAILY_ENTRY_CAP}/day, "
                f"${PROPOSED_GROSS_NOTIONAL_CAP_USD:.0f}/day gross, "
                f"{PROPOSED_MAX_OPEN_POSITIONS} max open, "
                f"${proposed_live_wallet_usd:.0f} live wallet."
            ),
        },
    ]
    failed = [item["key"] for item in checklist if not item["pass"]]
    status = "live_probe_active" if runtime_live else "paper_observing"
    return {
        "status": status,
        "live_probe_active": runtime_live,
        "runtime_source": runtime_source,
        "bot_env": str(env),
        "bot_dry_run": bool(dry_run),
        "global_polymarket_env": str(global_env),
        "effective_paper": bool(effective_paper),
        "live_intent": live_intent,
        "live_approved_at": live_approved_at,
        "approval_required": not approval_recorded,
        "does_not_authorize_live": not runtime_live,
        "activation_blocked": not runtime_live and bool(failed),
        "activation_blockers": failed,
        "proposed_live_wallet_usd": proposed_live_wallet_usd,
        "proposed_starting_trade_usd": PROPOSED_STARTING_TRADE_USD,
        "proposed_starting_trade_wallet_pct": _pct(
            PROPOSED_STARTING_TRADE_USD,
            proposed_live_wallet_usd,
        ),
        "proposed_daily_entry_cap": PROPOSED_DAILY_ENTRY_CAP,
        "proposed_gross_notional_cap_usd": PROPOSED_GROSS_NOTIONAL_CAP_USD,
        "proposed_gross_notional_wallet_pct": _pct(
            PROPOSED_GROSS_NOTIONAL_CAP_USD,
            proposed_live_wallet_usd,
        ),
        "proposed_max_open_positions": PROPOSED_MAX_OPEN_POSITIONS,
        "proposed_max_open_notional_usd": (
            PROPOSED_STARTING_TRADE_USD * PROPOSED_MAX_OPEN_POSITIONS
        ),
        "proposed_max_open_wallet_pct": _pct(
            PROPOSED_STARTING_TRADE_USD * PROPOSED_MAX_OPEN_POSITIONS,
            proposed_live_wallet_usd,
        ),
        "paper_fills_count": int(trade_metrics.get("paper_fills_count") or 0),
        "live_fills_count": int(trade_metrics.get("live_fills_count") or 0),
        "open_orders": int(order_metrics.get("open_orders") or 0),
        "paper_open_orders": int(order_metrics.get("paper_open_orders") or 0),
        "live_open_orders": int(order_metrics.get("live_open_orders") or 0),
        "checklist": checklist,
        "success_criteria": [
            {
                "milestone": "10 live fills",
                "criterion": "No auth, sizing, reject-loop, or unexpected-price errors.",
            },
            {
                "milestone": "20 live fills",
                "criterion": (
                    "Median live entry slippage stays within one tick of paper "
                    "expectation."
                ),
            },
            {
                "milestone": "50 live fills",
                "criterion": (
                    "Live fills remain comparable to the paper 4c-5c cohort "
                    "after outlier review."
                ),
            },
            {
                "milestone": "50 live fills",
                "criterion": "Ex-largest-two-wins ROI stays positive before any size increase.",
            },
        ],
    }
