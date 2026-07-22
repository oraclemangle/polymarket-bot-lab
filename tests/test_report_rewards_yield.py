"""Tests for scripts.report_rewards_yield aggregation + verdict logic."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from scripts.report_rewards_yield import (
    DEFAULT_GATE,
    _aggregate,
    _latest_per_date,
    _load_snapshots,
    render,
)


def _row(date: str, run_at: str, rewards: str, eligible: dict, total: dict) -> dict:
    return {
        "date": date,
        "run_at": run_at,
        "rewards_received_usd": rewards,
        "maker_notional_on_eligible_by_bot": eligible,
        "maker_notional_by_bot": total,
    }


def test_latest_per_date_keeps_newest_run():
    rows = [
        _row("2026-04-01", "2026-04-01T00:30:00+00:00", "0", {}, {}),
        _row("2026-04-01", "2026-04-01T01:00:00+00:00", "1.0", {"bot_e": "100"}, {"bot_e": "100"}),
        _row("2026-04-02", "2026-04-02T00:30:00+00:00", "0.5", {}, {}),
    ]
    kept = _latest_per_date(rows)
    assert [r["date"] for r in kept] == ["2026-04-01", "2026-04-02"]
    assert kept[0]["rewards_received_usd"] == "1.0"


def test_aggregate_filters_by_bot():
    rows = [
        _row("2026-04-01", "x", "1.0", {"bot_e": "100", "bot_g": "20"}, {"bot_e": "100", "bot_g": "20"}),
        _row("2026-04-02", "y", "2.0", {"bot_e": "200"}, {"bot_e": "200"}),
    ]
    agg = _aggregate(rows, focus_bot="bot_e")
    assert agg["rewards_total_usd"] == Decimal("3.0")
    assert agg["eligible_notional_by_bot"] == {"bot_e": Decimal("300")}


def test_render_wait_under_min_days(capsys):
    rows = [_row("2026-04-01", "x", "0.5", {"bot_e": "100"}, {"bot_e": "100"})]
    rc = render(rows, gate=DEFAULT_GATE, min_days=14, focus_bot=None)
    out = capsys.readouterr().out
    assert "WAIT" in out
    assert rc == 3


def test_render_fold_when_yield_above_gate(capsys):
    # 14 days, $1/day, $1 eligible notional/day → daily_yield = 1.0 ≫ 0.20 gate.
    rows = [
        _row(f"2026-04-{i:02d}", f"2026-04-{i:02d}T00:30:00+00:00", "1.0", {"bot_e": "1"}, {"bot_e": "1"})
        for i in range(1, 15)
    ]
    rc = render(rows, gate=DEFAULT_GATE, min_days=14, focus_bot=None)
    out = capsys.readouterr().out
    assert "FOLD INTO EV" in out
    assert rc == 0


def test_render_ignore_when_yield_below_gate(capsys):
    # 14 days, $0.01/day, $1 eligible/day → daily_yield = 0.01 ≪ 0.20.
    rows = [
        _row(f"2026-04-{i:02d}", f"2026-04-{i:02d}T00:30:00+00:00", "0.01", {"bot_e": "1"}, {"bot_e": "1"})
        for i in range(1, 15)
    ]
    rc = render(rows, gate=DEFAULT_GATE, min_days=14, focus_bot=None)
    out = capsys.readouterr().out
    assert "IGNORE FOREVER" in out
    assert rc == 0


def test_render_indeterminate_when_no_eligible_notional(capsys):
    rows = [
        _row(f"2026-04-{i:02d}", f"2026-04-{i:02d}T00:30:00+00:00", "0", {}, {})
        for i in range(1, 15)
    ]
    rc = render(rows, gate=DEFAULT_GATE, min_days=14, focus_bot=None)
    out = capsys.readouterr().out
    assert "indeterminate" in out
    assert rc == 2


def test_load_snapshots_skips_malformed(tmp_path: Path):
    path = tmp_path / "snap.jsonl"
    path.write_text(
        '\n'.join([
            json.dumps(_row("2026-04-01", "x", "1.0", {}, {})),
            "this is not json",
            json.dumps(_row("2026-04-02", "y", "2.0", {}, {})),
            "",
        ])
    )
    rows = _load_snapshots(path)
    assert len(rows) == 2
    assert rows[0]["date"] == "2026-04-01"
