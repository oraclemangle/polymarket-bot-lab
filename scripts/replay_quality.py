"""Replay-quality checks shared by research scripts.

This encodes the useful part of the external backtesting-repo audit: before a
replay result is treated as promotion evidence, record which live-realism
guards are present and which are still approximations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReplayQualityInput:
    has_l2_or_book_depth: bool
    models_latency: bool
    models_queue_position: bool
    has_fee_model: bool
    has_missing_data_policy: bool
    uses_public_wallet_fills_as_entries: bool
    has_negative_controls: bool
    has_outlier_trim: bool


def assess_replay_quality(inp: ReplayQualityInput) -> dict[str, Any]:
    """Return a machine-readable checklist and promotion posture.

    Promotion posture is intentionally conservative:
    - ``decision_grade`` only when all live-realism guards are present;
    - ``supporting_only`` when useful guards exist but latency/queue/fill
      realism is still approximate;
    - ``research_only`` for public-wallet-fill or very incomplete replays.
    """
    checks = {
        "book_depth": inp.has_l2_or_book_depth,
        "latency_model": inp.models_latency,
        "queue_position_model": inp.models_queue_position,
        "fee_model": inp.has_fee_model,
        "missing_data_policy": inp.has_missing_data_policy,
        "negative_controls": inp.has_negative_controls,
        "outlier_trim": inp.has_outlier_trim,
        "public_wallet_fills_not_entry_lifecycle": not inp.uses_public_wallet_fills_as_entries,
    }
    missing = [name for name, ok in checks.items() if not ok]
    if inp.uses_public_wallet_fills_as_entries:
        posture = "research_only"
    elif not missing:
        posture = "decision_grade"
    elif (
        inp.has_l2_or_book_depth
        and inp.has_fee_model
        and inp.has_missing_data_policy
        and inp.has_negative_controls
        and inp.has_outlier_trim
    ):
        posture = "supporting_only"
    else:
        posture = "research_only"
    return {
        "posture": posture,
        "checks": checks,
        "missing": missing,
    }

