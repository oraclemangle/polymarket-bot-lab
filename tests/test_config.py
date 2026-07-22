"""Tests for core.config."""

from __future__ import annotations

from decimal import Decimal

import pytest

from core import config
from core.config import RunMode, Settings, get_settings


def test_default_paper_mode(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("POLYMARKET_ENV", raising=False)
    config.reset_settings()
    s = get_settings()
    assert s.polymarket_env == RunMode.PAPER
    assert not s.is_live()


def test_env_live_mode(monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    config.reset_settings()
    s = get_settings()
    assert s.is_live()


def test_polymarket_signature_type_env(monkeypatch):
    monkeypatch.setenv("POLYMARKET_SIGNATURE_TYPE", "2")
    monkeypatch.setenv("POLYMARKET_FUNDER_ADDRESS", "0x1111111111111111111111111111111111111111")
    config.reset_settings()
    s = get_settings()
    assert s.polymarket_signature_type == 2
    assert s.polymarket_funder_address == "0x1111111111111111111111111111111111111111"


def test_invalid_polymarket_signature_type(monkeypatch):
    monkeypatch.setenv("POLYMARKET_SIGNATURE_TYPE", "9")
    config.reset_settings()
    with pytest.raises(Exception):
        Settings()


def test_invalid_drawdown_pct(monkeypatch):
    monkeypatch.setenv("BOT_A_DRAWDOWN_KILL_PCT", "150")
    config.reset_settings()
    with pytest.raises(Exception):
        Settings()


def test_chat_id_allowlist_parsing(monkeypatch):
    monkeypatch.setenv("TELEGRAM_CHAT_ID_ALLOWLIST", "123, 456,789")
    config.reset_settings()
    s = Settings()
    assert s.allowed_chat_ids() == [123, 456, 789]


def test_contract_address_constants():
    # Sanity — these addresses must never silently drift.
    # A future change requires an ADR + open-questions update.
    assert config.CTF_EXCHANGE_ADDRESS.startswith("0x")
    assert len(config.CTF_EXCHANGE_ADDRESS) == 42
    assert config.NEG_RISK_CTF_EXCHANGE_ADDRESS != config.CTF_EXCHANGE_ADDRESS


def test_default_polygon_rpc_is_publicnode():
    s = Settings()
    assert s.polygon_rpc_url == "https://polygon-bor.publicnode.com"


def test_fee_table_sanity():
    # 2026-04-22 GLM-5.1 review A8: FEE_RATE_BY_CATEGORY_BPS is now
    # derived from core/fees.py::TAKER_FEE_RATE_BY_CATEGORY as
    # `baseRate × 10000`. crypto baseRate 0.0720 → 720 bps.
    # Old value 72 was off by 10× and inconsistent with the 1.80% peak.
    assert config.FEE_RATE_BY_CATEGORY_BPS["geopolitics"] == 0
    assert config.FEE_RATE_BY_CATEGORY_BPS["crypto"] == 720
    # Bot A's target categories (archived) were ≤50 bps under the OLD
    # 10×-off scale. Under the canonical scale they are ≤500 bps
    # (peak ≤ 1.25%), which still bounds Bot A's edge thesis.
    for cat in ("geopolitics", "politics", "finance", "economics"):
        assert config.FEE_RATE_BY_CATEGORY_BPS[cat] <= 500
