from __future__ import annotations

import importlib
from decimal import InvalidOperation

import pytest


def test_config_rejects_live_non_dry_run(monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    monkeypatch.setenv("CRYPTO_PROB_GAP_DRY_RUN", "false")
    from bots.crypto_fair_value import config as cfg

    importlib.reload(cfg)
    loaded = cfg.load_config("probability_gap")
    errors = cfg.validate(loaded)
    assert any("paper-only" in err for err in errors)
    assert any("dry-run=true" in err for err in errors)


def test_config_rejects_wallet_env(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "redacted-test-value")
    from bots.crypto_fair_value.config import load_config, validate

    errors = validate(load_config("brownian_fair_value"))
    assert any("live wallet/keystore" in err for err in errors)


def test_config_keeps_fair_value_scoring_to_btc_eth_sol(monkeypatch):
    monkeypatch.setenv("CRYPTO_PROB_GAP_SYMBOLS", "BTC,ETH,SOL,XRP,DOGE")
    from bots.crypto_fair_value.config import load_config, validate

    loaded = load_config("probability_gap")
    assert loaded.symbols == {"BTC", "ETH", "SOL", "XRP", "DOGE"}
    errors = validate(loaded)
    assert any("subset of BTC,ETH,SOL" in err for err in errors)


def test_config_rejects_empty_and_unsupported_durations(monkeypatch):
    monkeypatch.setenv("CRYPTO_PROB_GAP_DURATIONS", "")
    from bots.crypto_fair_value.config import load_config, validate

    loaded = load_config("probability_gap")
    assert loaded.durations == frozenset()
    errors = validate(loaded)
    assert any("durations must be a non-empty subset" in err for err in errors)

    monkeypatch.setenv("CRYPTO_PROB_GAP_DURATIONS", "5,60")
    loaded = load_config("probability_gap")
    errors = validate(loaded)
    assert any("durations must be a non-empty subset" in err for err in errors)


def test_config_invalid_numeric_env_fails_fast(monkeypatch):
    monkeypatch.setenv("CRYPTO_PROB_GAP_MIN_PRICE", "not-a-decimal")
    from bots.crypto_fair_value.config import load_config

    with pytest.raises(InvalidOperation):
        load_config("probability_gap")


def test_config_reads_maker_book_age_env(monkeypatch):
    monkeypatch.setenv("CRYPTO_PROB_GAP_MAX_BOOK_AGE_SEC", "45")
    monkeypatch.setenv("CRYPTO_PROB_GAP_EXECUTION_STYLE", "maker")
    from bots.crypto_fair_value.config import load_config

    loaded = load_config("probability_gap")
    assert loaded.execution_style == "maker"
    assert loaded.max_book_age_sec == 45.0


def test_config_rejects_price_and_time_bounds(monkeypatch):
    monkeypatch.setenv("CRYPTO_PROB_GAP_MIN_PRICE", "0")
    monkeypatch.setenv("CRYPTO_PROB_GAP_MAX_PRICE", "1")
    monkeypatch.setenv("CRYPTO_PROB_GAP_MIN_SECONDS_TO_CLOSE", "-1")
    monkeypatch.setenv("CRYPTO_PROB_GAP_MAX_SECONDS_TO_CLOSE_5M", "-2")
    from bots.crypto_fair_value.config import load_config, validate

    errors = validate(load_config("probability_gap"))
    assert any("min seconds to close must be non-negative" in err for err in errors)
    assert any("5m max seconds to close must be >= min seconds" in err for err in errors)
    assert any("entry price bounds" in err for err in errors)
