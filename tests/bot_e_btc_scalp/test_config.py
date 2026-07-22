"""Tests for bot_e_btc_scalp/config.py validation logic."""
from __future__ import annotations

import importlib
import os

import pytest


def _reload(env_overrides: dict[str, str]):
    """Clear env, apply overrides, reload config module, return it."""
    # Clean prior env
    for k in list(os.environ.keys()):
        if k.startswith("BOT_E_"):
            del os.environ[k]
    for k, v in env_overrides.items():
        os.environ[k] = v
    from bots.bot_e_btc_scalp import config
    importlib.reload(config)
    return config


def test_default_config_validates():
    # With defaults, config should pass validation.
    cfg = _reload({})
    errors = cfg.validate()
    assert errors == [], f"unexpected errors: {errors}"


def test_live_with_dry_run_rejected():
    cfg = _reload({"BOT_E_ENV": "live", "BOT_E_DRY_RUN": "true"})
    errors = cfg.validate()
    assert any("contradictory" in e for e in errors)


def test_bad_env_rejected():
    cfg = _reload({"BOT_E_ENV": "prod"})
    errors = cfg.validate()
    assert any("BOT_E_ENV" in e for e in errors)


def test_negative_bankroll_rejected():
    cfg = _reload({"BOT_E_BANKROLL_USD": "-1"})
    errors = cfg.validate()
    assert any("BOT_E_BANKROLL_USD" in e for e in errors)


def test_fixed_trade_exceeds_per_trade_cap_rejected():
    # $10 trade on $100 bankroll with 2.5% cap = $2.50 max → $10 rejects
    cfg = _reload({"BOT_E_BANKROLL_USD": "100", "BOT_E_FIXED_TRADE_USD": "10"})
    errors = cfg.validate()
    assert any("exceeds per-trade cap" in e for e in errors)


def test_kelly_out_of_range_rejected():
    cfg = _reload({"BOT_E_KELLY_FRACTION": "1.5"})
    errors = cfg.validate()
    assert any("KELLY_FRACTION" in e for e in errors)


def test_aggregate_below_crypto_cap_rejected():
    cfg = _reload({
        "BOT_E_CRYPTO_BUCKET_CAP_FRAC": "0.5",
        "BOT_E_AGGREGATE_EXPOSURE_CAP_FRAC": "0.3",
    })
    errors = cfg.validate()
    assert any("AGGREGATE_EXPOSURE_CAP_FRAC" in e for e in errors)


def test_entry_window_ordering_rejected():
    cfg = _reload({
        "BOT_E_ENTRY_WINDOW_MIN_SEC": "600",
        "BOT_E_ENTRY_WINDOW_MAX_SEC": "300",
    })
    errors = cfg.validate()
    assert any("ENTRY_WINDOW_MIN_SEC" in e for e in errors)


def test_obi_threshold_range():
    for bad in ["0", "1.5", "-0.1"]:
        cfg = _reload({"BOT_E_OBI_THRESHOLD": bad})
        errors = cfg.validate()
        assert any("OBI_THRESHOLD" in e for e in errors), f"should reject {bad}"


def test_global_drawdown_below_daily_rejected():
    cfg = _reload({
        "BOT_E_DAILY_LOSS_KILL_FRAC": "0.5",
        "BOT_E_GLOBAL_DRAWDOWN_KILL_FRAC": "0.3",
    })
    errors = cfg.validate()
    assert any("GLOBAL_DRAWDOWN_KILL_FRAC" in e for e in errors)


def test_trailing_n_exceeds_window_rejected():
    cfg = _reload({
        "BOT_E_TRAILING_LOSS_N": "25",
        "BOT_E_TRAILING_LOSS_WINDOW": "20",
    })
    errors = cfg.validate()
    assert any("TRAILING_LOSS_N" in e for e in errors)


def test_summary_reflects_values():
    cfg = _reload({"BOT_E_BANKROLL_USD": "250", "BOT_E_FIXED_TRADE_USD": "3"})
    # $3 on $250 = 1.2% of bankroll, under 2.5% cap → should validate
    assert cfg.validate() == []
    s = cfg.summary()
    from decimal import Decimal
    assert s.bankroll == Decimal("250")
    assert s.fixed_trade == Decimal("3")
    assert s.maker_only is True  # default
