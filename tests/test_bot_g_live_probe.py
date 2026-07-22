from __future__ import annotations

from core.bot_g_live_probe import bot_g_tiny_live_probe_plan


def test_live_probe_distinguishes_live_intent_from_effective_live():
    paper = bot_g_tiny_live_probe_plan(
        dry_run=False,
        env="live",
        global_env="paper",
        trade_metrics={"paper_fills_count": 3, "live_fills_count": 0},
    )
    assert paper["live_intent"] is True
    assert paper["effective_paper"] is True
    assert paper["live_probe_active"] is False
    assert paper["status"] == "paper_observing"

    live = bot_g_tiny_live_probe_plan(
        dry_run=False,
        env="live",
        global_env="live",
        effective_paper=False,
        runtime_source="trader_event",
        trade_metrics={"paper_fills_count": 3, "live_fills_count": 1},
    )
    assert live["effective_paper"] is False
    assert live["live_probe_active"] is True
    assert live["status"] == "live_probe_active"
    assert live["runtime_source"] == "trader_event"


def test_live_probe_exposes_current_200_wallet_sizing_packet():
    probe = bot_g_tiny_live_probe_plan(dry_run=True, env="paper")

    assert probe["proposed_live_wallet_usd"] == 200.0
    assert probe["proposed_starting_trade_usd"] == 1.0
    assert probe["proposed_starting_trade_wallet_pct"] == 0.5
    assert probe["proposed_daily_entry_cap"] == 20
    assert probe["proposed_gross_notional_cap_usd"] == 100.0
    assert probe["proposed_gross_notional_wallet_pct"] == 50.0
    assert probe["proposed_max_open_positions"] == 10
    assert probe["proposed_max_open_notional_usd"] == 10.0
    assert probe["proposed_max_open_wallet_pct"] == 5.0


def test_live_probe_records_approval_stamp():
    probe = bot_g_tiny_live_probe_plan(
        dry_run=False,
        env="live",
        global_env="live",
        effective_paper=False,
        live_approved_at="2026-05-02",
    )

    assert probe["approval_required"] is False
    assert probe["does_not_authorize_live"] is False
    assert "explicit_approval" not in probe["activation_blockers"]
    assert "tiny_caps" not in probe["activation_blockers"]
