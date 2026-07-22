"""Regression tests for Session 22 post-deploy ops fixes (2026-04-23).

Covers:
1. Bot G heartbeat log at INFO even when markets_in_window=0.
2. Watchdog recorder-freshness alert includes actionable `systemctl
   reset-failed` instructions when systemd state is `failed`.
"""
from __future__ import annotations

import inspect


def test_bot_g_heartbeat_on_empty_scan():
    """Bot G's run_loop must log bot_g.scan_empty at INFO when markets
    returns empty. Previously silent, which was indistinguishable from
    a recorder stall."""
    import bots.bot_g_longshot.__main__ as mod
    src = inspect.getsource(mod.run_loop)
    assert "bot_g.scan_empty" in src, (
        "Bot G main loop missing heartbeat log for empty-scan branch"
    )
    # Throttle is present so we don't spam every 10s.
    assert "_last_empty_scan_log" in src


def test_watchdog_recorder_alert_has_actionable_recovery_command():
    """The recorder-freshness alert message must include explicit
    `systemctl reset-failed` recovery instructions when the service is
    in the permanent-failed state — regression for the 2026-04-21
    incident where the recorder sat in failed state for 31 hours.
    """
    from core.watchdog import Watchdog
    src = inspect.getsource(Watchdog._check_recorder_freshness)
    assert "reset-failed" in src, (
        "recorder-freshness alert missing recovery instructions"
    )
    # Either joined ("systemctl is-failed") or list-form (["systemctl", "is-failed"]).
    assert "is-failed" in src, (
        "recorder-freshness check not probing systemd `is-failed` state"
    )
    assert "permanent_failed" in src.lower() or "PERMANENTLY FAILED" in src
