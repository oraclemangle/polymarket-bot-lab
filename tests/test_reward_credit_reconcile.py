"""Tests for reward credit reconciliation reporting."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from scripts.reward_credit_reconcile import LocalMakerFill, _render_report


def test_render_report_keeps_credit_totals_separate_from_local_notional():
    report = _render_report(
        run_at=datetime(2026, 5, 16, tzinfo=UTC),
        days=[date(2026, 5, 16)],
        signer_address="0x" + "11" * 20,
        maker_address="0x" + "22" * 20,
        totals_by_day={"2026-05-16": {"total": "0.75"}},
        totals_errors={"2026-05-16": None},
        user_market_rows=[{"earnings": "0.25"}],
        user_market_error=None,
        reward_percentages={"cid": 12.5},
        reward_percentages_error=None,
        rebate_rows=[{"date": "2026-05-16", "condition_id": "cid", "rebated_fees_usdc": "0.10"}],
        rebate_errors=[],
        local_fills=[
            LocalMakerFill(
                bot_id="crypto_probability_gap_live_maker",
                condition_id="cid",
                notional=Decimal("12.50"),
                fill_count=3,
            )
        ],
    )

    assert "Authenticated reward total" in report
    assert "$0.75" in report
    assert "Public maker rebates" in report
    assert "$0.1" in report
    assert "`crypto_probability_gap_live_maker` | 3 | $12.5" in report
