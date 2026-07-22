"""Tests for replay quality checklist."""
from __future__ import annotations

from scripts.replay_quality import ReplayQualityInput, assess_replay_quality


def test_replay_quality_decision_grade_when_all_guards_present():
    result = assess_replay_quality(
        ReplayQualityInput(
            has_l2_or_book_depth=True,
            models_latency=True,
            models_queue_position=True,
            has_fee_model=True,
            has_missing_data_policy=True,
            uses_public_wallet_fills_as_entries=False,
            has_negative_controls=True,
            has_outlier_trim=True,
        )
    )

    assert result["posture"] == "decision_grade"
    assert result["missing"] == []


def test_replay_quality_supporting_only_for_current_recorder_style():
    result = assess_replay_quality(
        ReplayQualityInput(
            has_l2_or_book_depth=True,
            models_latency=False,
            models_queue_position=False,
            has_fee_model=True,
            has_missing_data_policy=True,
            uses_public_wallet_fills_as_entries=False,
            has_negative_controls=True,
            has_outlier_trim=True,
        )
    )

    assert result["posture"] == "supporting_only"
    assert result["missing"] == ["latency_model", "queue_position_model"]


def test_replay_quality_public_wallet_fills_are_research_only():
    result = assess_replay_quality(
        ReplayQualityInput(
            has_l2_or_book_depth=False,
            models_latency=False,
            models_queue_position=False,
            has_fee_model=True,
            has_missing_data_policy=True,
            uses_public_wallet_fills_as_entries=True,
            has_negative_controls=True,
            has_outlier_trim=True,
        )
    )

    assert result["posture"] == "research_only"
    assert "public_wallet_fills_not_entry_lifecycle" in result["missing"]

