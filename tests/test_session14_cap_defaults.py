"""Session 14 regression tests — exposure cap defaults to bankroll.

Pre-Session-14 bug: BOT_X_BANKROLL_GBP set the per-trade sizing math but
NOT the aggregate exposure cap. The cap defaulted to $1000 / £800
regardless. Result: a £40 'bankroll' bot could spend up to ~£800.

Fix: when BOT_X_EXPOSURE_CAP is unset, it follows BOT_X_BANKROLL.
Operators who deliberately want a different cap can still set the
EXPOSURE_CAP env var explicitly.
"""
from __future__ import annotations

import importlib
import os
from decimal import Decimal


def _reload(module_path: str, env_overrides: dict[str, str]):
    # Strip every relevant env var so we test the ACTUAL default behaviour
    for k in list(os.environ.keys()):
        if k.startswith("BOT_A_") or k.startswith("BOT_B_") or k == "DEFAULT_GBP_USD_RATE":
            del os.environ[k]
    for k, v in env_overrides.items():
        os.environ[k] = v
    import importlib
    mod = importlib.import_module(module_path)
    importlib.reload(mod)
    return mod


def test_bot_a_cap_follows_bankroll_when_only_bankroll_set():
    """Operator sets BOT_A_BANKROLL_GBP=150 → cap = 150 × 1.35 = $202.50"""
    cfg = _reload("bots.bot_a.config", {"BOT_A_BANKROLL_GBP": "150"})
    assert cfg.AGGREGATE_EXPOSURE_CAP_USD == Decimal("150") * Decimal("1.35")


def test_bot_a_cap_explicit_override_wins():
    """Explicit BOT_A_EXPOSURE_CAP_USD beats the bankroll-derived default."""
    cfg = _reload("bots.bot_a.config", {
        "BOT_A_BANKROLL_GBP": "150",
        "BOT_A_EXPOSURE_CAP_USD": "500",
    })
    assert cfg.AGGREGATE_EXPOSURE_CAP_USD == Decimal("500")


def test_bot_a_cap_legacy_default_when_nothing_set():
    """No env vars at all → legacy $1000 fallback (preserves prior behaviour
    for anyone not yet using BOT_A_BANKROLL_GBP)."""
    cfg = _reload("bots.bot_a.config", {})
    assert cfg.AGGREGATE_EXPOSURE_CAP_USD == Decimal("1000")


def test_bot_a_custom_gbp_usd_rate_used():
    """If operator sets DEFAULT_GBP_USD_RATE, use it for the conversion."""
    cfg = _reload("bots.bot_a.config", {
        "BOT_A_BANKROLL_GBP": "100",
        "DEFAULT_GBP_USD_RATE": "1.50",
    })
    assert cfg.AGGREGATE_EXPOSURE_CAP_USD == Decimal("100") * Decimal("1.50")

