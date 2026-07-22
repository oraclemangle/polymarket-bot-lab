"""Regression tests for the 2026-04-22 GLM-5.1 fleet-review fixes.

Covers: A4 (paper_override read-only), A5 (dashboard auth empty-string
+ timing-safe compare), A6 (Bot E adverse_selection BUY_NO semantics),
A10 (snapshot_daily single-call FIFO replay).
"""
from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import patch

import pytest


# --- A4: paper_override is read-only after construction -----------------------

def test_paper_override_readonly_v1():
    from core.clob import ClobWrapper
    wrapper = ClobWrapper(keystore=None, paper_override=True)
    assert wrapper.paper_override is True
    with pytest.raises(PermissionError, match="read-only"):
        wrapper.paper_override = False
    # State unchanged after failed write.
    assert wrapper.paper_override is True


def test_paper_override_readonly_v2():
    from core.clob_v2 import ClobWrapperV2
    wrapper = ClobWrapperV2(keystore=None, paper_override=True)
    assert wrapper.paper_override is True
    with pytest.raises(PermissionError, match="read-only"):
        wrapper.paper_override = False
    assert wrapper.paper_override is True


def test_paper_override_false_stays_false():
    """Read-only applies in both directions — no setter can flip paper_override
    from False to True either, preventing a live bot from claiming it's paper."""
    from core.clob import ClobWrapper
    wrapper = ClobWrapper(keystore=None, paper_override=False)
    assert wrapper.paper_override is False
    with pytest.raises(PermissionError):
        wrapper.paper_override = True
    assert wrapper.paper_override is False


# --- A5: dashboard auth empty-string + timing-safe --------------------------

def test_dashboard_api_key_empty_string_disables_auth_with_warning(
    monkeypatch, caplog,
):
    """Empty string DASHBOARD_API_KEY disables auth AND emits a warning.

    Backwards-compat: some deploy scripts export DASHBOARD_API_KEY="" which
    was silently treated as unset. Behaviour preserved, but now loud.
    """
    import dashboard.server as srv
    monkeypatch.setenv("DASHBOARD_API_KEY", "")
    srv._EMPTY_KEY_WARNED = False  # reset one-shot guard
    caplog.set_level("WARNING", logger="dashboard")
    got = srv._require_api_key()
    assert got is None
    assert any("empty string" in r.message for r in caplog.records)


def test_dashboard_api_key_unset_returns_none(monkeypatch):
    import dashboard.server as srv
    monkeypatch.delenv("DASHBOARD_API_KEY", raising=False)
    assert srv._require_api_key() is None


def test_dashboard_api_key_nonempty_returns_value(monkeypatch):
    import dashboard.server as srv
    monkeypatch.setenv("DASHBOARD_API_KEY", "supersecret")
    assert srv._require_api_key() == "supersecret"


def test_dashboard_auth_uses_compare_digest():
    """_check_auth must use hmac.compare_digest for key comparison to
    avoid timing side-channels. Regression test: the source line must
    reference `hmac.compare_digest`, not `supplied == key` direct."""
    import dashboard.server as srv
    import inspect
    src = inspect.getsource(srv.DashboardHandler._check_auth)
    assert "hmac.compare_digest" in src, "timing-unsafe string compare detected"
    # Non-comment source lines must not contain `return supplied == key`.
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "return supplied == key" not in stripped, (
            "direct-equality auth comparison still present"
        )


# --- A6: Bot E adverse_selection uses same-side convention -------------------

def test_adverse_selection_same_side_convention():
    """Both BUY_YES and BUY_NO treat adverse as 'same-side midpoint fell
    below fill_price'. This matches the same-side documentation and
    removes the dead-code BUY_NO branch that GLM-5.1 flagged as a logic bug."""
    from bots.bot_e_btc_scalp.adverse_selection import AdverseSelectionTracker

    tracker = AdverseSelectionTracker()
    # BUY_YES: fill at 0.55, mid drops to 0.54 → adverse.
    tracker.register(
        order_id="ord_yes_adv",
        fill_price=Decimal("0.55"),
        fill_side="BUY_YES",
        fill_ts_ms=0,
    )
    out = tracker.measure("ord_yes_adv", Decimal("0.54"))
    assert out is not None
    assert out.moved_against is True

    # BUY_YES: fill at 0.55, mid rises to 0.56 → favorable.
    tracker.register(
        order_id="ord_yes_fav",
        fill_price=Decimal("0.55"),
        fill_side="BUY_YES",
        fill_ts_ms=0,
    )
    out = tracker.measure("ord_yes_fav", Decimal("0.56"))
    assert out.moved_against is False

    # BUY_NO: fill at 0.45 (NO price), NO midpoint drops to 0.44 → adverse.
    tracker.register(
        order_id="ord_no_adv",
        fill_price=Decimal("0.45"),
        fill_side="BUY_NO",
        fill_ts_ms=0,
    )
    out = tracker.measure("ord_no_adv", Decimal("0.44"))
    assert out.moved_against is True

    # BUY_NO: fill at 0.45 (NO price), NO midpoint rises to 0.46 → favorable.
    tracker.register(
        order_id="ord_no_fav",
        fill_price=Decimal("0.45"),
        fill_side="BUY_NO",
        fill_ts_ms=0,
    )
    out = tracker.measure("ord_no_fav", Decimal("0.46"))
    assert out.moved_against is False


# --- A10: snapshot_daily calls get_realised_pnl exactly once ----------------

def test_snapshot_daily_calls_get_realised_pnl_once(tmp_db):
    """GLM-5.1 A10: snapshot_daily used to call get_realised_pnl directly
    AND again inside get_drawdown_pct. For Bot E with thousands of trades,
    that doubled per-snapshot FIFO replay cost. Regression: the new
    precomputed-kwarg path must keep the count at exactly one."""
    from core.portfolio import Portfolio
    portfolio = Portfolio()
    call_count = {"n": 0}
    real = Portfolio.get_realised_pnl

    def counting_get_realised_pnl(self, bot_id, since=None):
        call_count["n"] += 1
        return real(self, bot_id, since=since)

    with patch.object(Portfolio, "get_realised_pnl", counting_get_realised_pnl):
        portfolio.snapshot_daily(
            bot_id="bot_e",
            initial_usd=Decimal("1000"),
            mark_prices={},
        )
    assert call_count["n"] == 1, (
        f"snapshot_daily should call get_realised_pnl exactly once; "
        f"got {call_count['n']}"
    )


def test_get_drawdown_pct_accepts_precomputed_values(tmp_db):
    """Drawdown result must be identical whether realised/unrealised are
    passed in or computed internally."""
    from core.portfolio import Portfolio
    portfolio = Portfolio()
    dd_internal = portfolio.get_drawdown_pct(
        bot_id="bot_e",
        initial_usd=Decimal("1000"),
        mark_prices={},
    )
    dd_passed = portfolio.get_drawdown_pct(
        bot_id="bot_e",
        initial_usd=Decimal("1000"),
        mark_prices={},
        realised_pnl=Decimal("0"),
        unrealised_pnl=Decimal("0"),
    )
    assert dd_internal == dd_passed
