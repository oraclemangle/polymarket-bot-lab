"""Bot Longshot Fade (G) — unit tests.

Focused on the pure-logic pieces (config validation, entry gating).
Integration with recorder DB + ClobWrapper is exercised by live paper
running on the bot host, not in unit tests.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_config_defaults_validate():
    from bots.bot_g_longshot import config
    errors = config.validate()
    assert errors == [], f"default config should validate cleanly, got {errors}"


def test_bot_id_env_override(monkeypatch):
    """ADR-044 split: BOT_G_ID_OVERRIDE lets the same code run as
    bot_g_jackpot or bot_g_scalp in parallel systemd units without
    colliding P&L ledgers."""
    import importlib
    monkeypatch.setenv("BOT_G_ID_OVERRIDE", "bot_g_jackpot")
    from bots.bot_g_longshot import config as bot_g_config
    importlib.reload(bot_g_config)
    assert bot_g_config.BOT_ID == "bot_g_jackpot"
    monkeypatch.delenv("BOT_G_ID_OVERRIDE", raising=False)
    importlib.reload(bot_g_config)
    assert bot_g_config.BOT_ID == "bot_g"


def test_prime_systemd_unit_disables_legacy_modes():
    """Prime must run as its own ledger and not accidentally fire raw regimes."""
    root = Path(__file__).resolve().parents[1]
    prime = (root / "systemd/polymarket-bot-g-prime.service").read_text()

    assert 'Environment="BOT_G_ID_OVERRIDE=bot_g_prime"' in prime
    assert 'Environment="BOT_G_PRIME_MODE_ENABLED=true"' in prime
    assert 'Environment="BOT_G_JACKPOT_MODE_ENABLED=false"' in prime
    assert 'Environment="BOT_G_SCALP_MODE_ENABLED=false"' in prime
    assert 'Environment="BOT_G_PRIME_ENTRY_SECONDS=45"' in prime
    assert 'Environment="BOT_G_MIN_ENTRY_PRICE=0.04"' in prime
    assert 'Environment="BOT_G_MAX_ENTRY_PRICE=0.08"' in prime
    assert 'Environment="BOT_G_LIVE_MAX_DAILY_ENTRIES=20"' in prime
    assert 'Environment="BOT_G_LIVE_MAX_CONCURRENT_POSITIONS=10"' in prime
    assert 'Environment="BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD=100"' in prime
    assert 'Environment="BOT_G_LIVE_WALLET_USD=200"' in prime
    assert 'Environment="BOT_G_PRIME_REQUIRE_CEX_CONFIRM=false"' in prime
    assert 'Environment="BOT_G_ALLOWED_SYMBOLS=BTC,ETH,SOL,XRP,DOGE"' in prime

    live = (root / "systemd/polymarket-bot-g-prime-live.service").read_text()
    assert 'Environment="BOT_G_ENV=live"' in live
    assert 'Environment="BOT_G_DRY_RUN=false"' in live
    assert 'Environment="POLYMARKET_ENV=live"' in live
    assert 'Environment="BOT_G_LIVE_APPROVED_AT=2026-05-10"' in live
    assert 'Environment="BOT_G_ID_OVERRIDE=bot_g_prime_live"' in live
    assert 'Environment="BOT_G_MIN_ENTRY_PRICE=0.06"' in live
    assert 'Environment="BOT_G_MAX_ENTRY_PRICE=0.08"' in live
    assert 'Environment="BOT_G_PRIME_ENTRY_SECONDS=45"' in live
    assert 'Environment="BOT_G_ENTRY_SECONDS_BEFORE_RES=45"' in live
    assert 'Environment="BOT_G_SCAN_INTERVAL_S=2"' in live
    assert 'Environment="BOT_G_MIN_ENTRY_LEAD_SECONDS=5"' in live
    assert 'Environment="BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS=1"' in live
    assert 'Environment="BOT_G_LIVE_MAX_DAILY_ENTRIES=20"' in live
    assert 'Environment="BOT_G_LIVE_MAX_CONCURRENT_POSITIONS=10"' in live
    assert 'Environment="BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD=100"' in live
    assert 'Environment="BOT_G_LIVE_WALLET_USD=200"' in live
    assert 'Environment="BOT_G_FIXED_TRADE_USD=1"' in live
    assert 'Environment="BOT_G_JACKPOT_MODE_ENABLED=false"' in live
    assert 'Environment="BOT_G_SCALP_MODE_ENABLED=false"' in live
    assert 'Environment="BOT_G_ALLOWED_SYMBOLS=ETH,SOL"' in live
    assert 'Environment="BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_ENABLED=true"' in live
    assert 'Environment="BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_PRICE=0.50"' in live

    take_profit = (
        root / "systemd/archived/polymarket-bot-g-prime-take-profit.service"
    ).read_text()
    assert 'Environment="BOT_G_ENV=paper"' in take_profit
    assert 'Environment="BOT_G_DRY_RUN=true"' in take_profit
    assert 'Environment="BOT_G_ID_OVERRIDE=bot_g_prime_take_profit"' in take_profit
    assert 'Environment="BOT_G_MIN_ENTRY_PRICE=0.035"' in take_profit
    assert 'Environment="BOT_G_MAX_ENTRY_PRICE=0.055"' in take_profit
    assert 'Environment="BOT_G_ENTRY_SECONDS_BEFORE_RES=60"' in take_profit
    assert 'Environment="BOT_G_PAPER_TAKE_PROFIT_ENABLED=true"' in take_profit
    assert 'Environment="BOT_G_PAPER_TAKE_PROFIT_PRICE=0.50"' in take_profit
    assert 'Environment="BOT_G_PAPER_TAKE_PROFIT_START_SECONDS=25"' in take_profit
    assert 'Environment="BOT_G_PAPER_TAKE_PROFIT_END_SECONDS=8"' in take_profit

    take_profit_vps = (
        root / "systemd/archived/polymarket-bot-g-prime-take-profit-vps.service"
    ).read_text()
    assert 'Environment="BOT_G_PAPER_TAKE_PROFIT_PRICE=0.50"' in take_profit_vps

    live_vps = (root / "systemd/polymarket-bot-g-prime-live-vps.service").read_text()
    assert 'Environment="BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_ENABLED=true"' in live_vps
    assert 'Environment="BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_PRICE=0.50"' in live_vps
    assert 'Environment="BOT_G_MIN_ENTRY_PRICE=0.06"' in live_vps
    assert 'Environment="BOT_G_MAX_ENTRY_PRICE=0.08"' in live_vps
    assert 'Environment="BOT_G_ALLOWED_SYMBOLS=ETH,SOL"' in live_vps

    high_tail_vps = (
        root / "systemd/polymarket-bot-g-prime-high-tail-vps.service"
    ).read_text()
    assert 'Environment="BOT_G_ID_OVERRIDE=bot_g_prime_high_tail"' in high_tail_vps
    assert 'Environment="BOT_G_MIN_ENTRY_PRICE=0.06"' in high_tail_vps
    assert 'Environment="BOT_G_MAX_ENTRY_PRICE=0.08"' in high_tail_vps
    assert 'Environment="BOT_G_PRIME_ENTRY_SECONDS=45"' in high_tail_vps
    assert 'Environment="BOT_G_FIXED_TRADE_USD=1"' in high_tail_vps
    assert 'Environment="BOT_G_ALLOWED_SYMBOLS=BTC,ETH,SOL,XRP,DOGE"' in high_tail_vps

    shadow_maker = (
        root / "systemd/polymarket-bot-g-prime-shadow-maker-paper.service"
    ).read_text()
    assert 'Environment="BOT_G_DRY_RUN=true"' in shadow_maker
    assert 'Environment="BOT_G_ID_OVERRIDE=bot_g_prime_shadow_maker"' in shadow_maker
    assert 'Environment="BOT_G_EXECUTION_STYLE=maker"' in shadow_maker
    assert 'Environment="BOT_G_MIN_ENTRY_PRICE=0.03"' in shadow_maker
    assert 'Environment="BOT_G_MAX_ENTRY_PRICE=0.06"' in shadow_maker
    assert 'Environment="BOT_G_MIN_COUNTERPARTY_PRICE=0.90"' in shadow_maker
    assert 'Environment="BOT_G_ALLOWED_SYMBOLS=BTC,ETH,SOL"' in shadow_maker

    high_tail_maker = (
        root / "systemd/polymarket-bot-g-prime-high-tail-maker-paper.service"
    ).read_text()
    assert 'Environment="BOT_G_DRY_RUN=true"' in high_tail_maker
    assert 'Environment="BOT_G_ID_OVERRIDE=bot_g_prime_high_tail_maker"' in high_tail_maker
    assert 'Environment="BOT_G_EXECUTION_STYLE=maker"' in high_tail_maker
    assert 'Environment="BOT_G_MIN_ENTRY_PRICE=0.02"' in high_tail_maker
    assert 'Environment="BOT_G_MAX_ENTRY_PRICE=0.08"' in high_tail_maker
    assert 'Environment="BOT_G_FIXED_TRADE_USD=1"' in high_tail_maker
    assert 'Environment="BOT_G_ALLOWED_SYMBOLS=BTC,ETH,SOL,XRP,DOGE"' in high_tail_maker

    late_cheap = (
        root / "systemd/archived/polymarket-bot-g-prime-late-cheap.service"
    ).read_text()
    assert 'Environment="BOT_G_ID_OVERRIDE=bot_g_prime_late_cheap"' in late_cheap
    assert 'Environment="BOT_G_MIN_ROLLING_ROI_PCT=-100"' in late_cheap

    late_cheap_vps = (
        root / "systemd/archived/polymarket-bot-g-prime-late-cheap-vps.service"
    ).read_text()
    assert 'Environment="BOT_G_MIN_ROLLING_ROI_PCT=-100"' in late_cheap_vps


def test_recorder_schema_has_bot_g_hot_path_indexes():
    """Bot G live-transfer latency depends on indexed recorder lookups."""
    from bots.bot_e_recorder import schema

    sql = schema.SCHEMA_SQL
    assert "ix_pm_events_asset_type_time" in sql
    assert "ON pm_events(asset_id, event_type, received_at_ms)" in sql
    assert "ix_cex_trades_symbol_trade_time" in sql
    assert "ON cex_trades(symbol, trade_time_ms)" in sql


def test_config_rejects_zero_trade_size(monkeypatch):
    # Re-import after env mutation.
    monkeypatch.setenv("BOT_G_FIXED_TRADE_USD", "0")
    import importlib

    from bots.bot_g_longshot import config
    importlib.reload(config)
    errors = config.validate()
    assert any("BOT_G_FIXED_TRADE_USD" in e for e in errors)
    # Restore.
    monkeypatch.delenv("BOT_G_FIXED_TRADE_USD", raising=False)
    importlib.reload(config)


def test_config_rejects_invalid_runtime_state_heartbeat(monkeypatch):
    monkeypatch.setenv("BOT_G_RUNTIME_STATE_HEARTBEAT_INTERVAL_S", "0")
    import importlib

    from bots.bot_g_longshot import config
    importlib.reload(config)
    errors = config.validate()
    assert any("BOT_G_RUNTIME_STATE_HEARTBEAT_INTERVAL_S" in e for e in errors)
    monkeypatch.delenv("BOT_G_RUNTIME_STATE_HEARTBEAT_INTERVAL_S", raising=False)
    importlib.reload(config)


def test_runtime_state_heartbeat_due(monkeypatch):
    from bots.bot_g_longshot import __main__ as bot_g_main

    monkeypatch.setattr(
        bot_g_main.config,
        "BOT_G_RUNTIME_STATE_HEARTBEAT_INTERVAL_S",
        300,
    )
    assert bot_g_main._runtime_state_heartbeat_due(1000.0, None) is True
    assert bot_g_main._runtime_state_heartbeat_due(1299.9, 1000.0) is False
    assert bot_g_main._runtime_state_heartbeat_due(1300.0, 1000.0) is True


def test_config_rejects_wide_max_entry_price(monkeypatch):
    monkeypatch.setenv("BOT_G_MAX_ENTRY_PRICE", "0.50")
    import importlib

    from bots.bot_g_longshot import config
    importlib.reload(config)
    errors = config.validate()
    assert any("BOT_G_MAX_ENTRY_PRICE" in e for e in errors), (
        "0.50 should violate the thesis-scope guard (tail prices only)"
    )
    monkeypatch.delenv("BOT_G_MAX_ENTRY_PRICE", raising=False)
    importlib.reload(config)


def test_config_rejects_prime_live_band_drift(monkeypatch):
    monkeypatch.setenv("BOT_G_ID_OVERRIDE", "bot_g_prime_live")
    monkeypatch.setenv("BOT_G_MIN_ENTRY_PRICE", "0.03")
    monkeypatch.setenv("BOT_G_MAX_ENTRY_PRICE", "0.08")
    import importlib

    from bots.bot_g_longshot import config
    importlib.reload(config)
    errors = config.validate()
    assert any("ADR-149 high-tail guard" in e for e in errors)
    monkeypatch.delenv("BOT_G_ID_OVERRIDE", raising=False)
    monkeypatch.delenv("BOT_G_MIN_ENTRY_PRICE", raising=False)
    monkeypatch.delenv("BOT_G_MAX_ENTRY_PRICE", raising=False)
    importlib.reload(config)


def test_config_allows_approved_prime_live_high_tail(monkeypatch):
    monkeypatch.setenv("BOT_G_ID_OVERRIDE", "bot_g_prime_live")
    monkeypatch.setenv("BOT_G_ENV", "live")
    monkeypatch.setenv("BOT_G_DRY_RUN", "false")
    monkeypatch.setenv("BOT_G_MIN_ENTRY_PRICE", "0.06")
    monkeypatch.setenv("BOT_G_MAX_ENTRY_PRICE", "0.08")
    monkeypatch.setenv("BOT_G_PRIME_ENTRY_SECONDS", "45")
    monkeypatch.setenv("BOT_G_ENTRY_SECONDS_BEFORE_RES", "45")
    monkeypatch.setenv("BOT_G_ALLOWED_SYMBOLS", "ETH,SOL")
    monkeypatch.setenv("BOT_G_FIXED_TRADE_USD", "1")
    import importlib

    from bots.bot_g_longshot import config
    importlib.reload(config)
    errors = config.validate()
    assert errors == [], f"approved high-tail live profile should validate: {errors}"
    for key in (
        "BOT_G_ID_OVERRIDE",
        "BOT_G_ENV",
        "BOT_G_DRY_RUN",
        "BOT_G_MIN_ENTRY_PRICE",
        "BOT_G_MAX_ENTRY_PRICE",
        "BOT_G_PRIME_ENTRY_SECONDS",
        "BOT_G_ENTRY_SECONDS_BEFORE_RES",
        "BOT_G_ALLOWED_SYMBOLS",
        "BOT_G_FIXED_TRADE_USD",
    ):
        monkeypatch.delenv(key, raising=False)
    importlib.reload(config)


def test_config_rejects_trade_size_above_bankroll(monkeypatch):
    monkeypatch.setenv("BOT_G_BANKROLL_USD", "10")
    monkeypatch.setenv("BOT_G_FIXED_TRADE_USD", "20")
    import importlib

    from bots.bot_g_longshot import config
    importlib.reload(config)
    errors = config.validate()
    assert any("BOT_G_FIXED_TRADE_USD" in e and "BOT_G_BANKROLL_USD" in e for e in errors)
    monkeypatch.delenv("BOT_G_BANKROLL_USD", raising=False)
    monkeypatch.delenv("BOT_G_FIXED_TRADE_USD", raising=False)
    importlib.reload(config)


def test_config_rejects_invalid_live_caps(monkeypatch):
    monkeypatch.setenv("BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "0")
    import importlib

    from bots.bot_g_longshot import config
    importlib.reload(config)
    errors = config.validate()
    assert any("BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD" in e for e in errors)
    monkeypatch.delenv("BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", raising=False)
    importlib.reload(config)


def test_config_rejects_trade_size_above_live_wallet(monkeypatch):
    monkeypatch.setenv("BOT_G_LIVE_WALLET_USD", "4")
    monkeypatch.setenv("BOT_G_FIXED_TRADE_USD", "5")
    import importlib

    from bots.bot_g_longshot import config
    importlib.reload(config)
    errors = config.validate()
    assert any(
        "BOT_G_FIXED_TRADE_USD" in e and "BOT_G_LIVE_WALLET_USD" in e
        for e in errors
    )
    monkeypatch.delenv("BOT_G_LIVE_WALLET_USD", raising=False)
    monkeypatch.delenv("BOT_G_FIXED_TRADE_USD", raising=False)
    importlib.reload(config)


def test_config_rejects_empty_allowed_symbols(monkeypatch):
    monkeypatch.setenv("BOT_G_ALLOWED_SYMBOLS", "")
    import importlib

    from bots.bot_g_longshot import config
    importlib.reload(config)
    errors = config.validate()
    assert any("BOT_G_ALLOWED_SYMBOLS" in e for e in errors)
    monkeypatch.delenv("BOT_G_ALLOWED_SYMBOLS", raising=False)
    importlib.reload(config)


def test_entry_gate_picks_cheapest_side():
    """When both YES and NO qualify, Bot G enters the cheaper side (max
    asymmetric upside)."""
    # Purely algorithmic: simulate what _try_enter_market does in-memory.
    yes_ask = Decimal("0.02")
    no_ask = Decimal("0.01")
    yes_size = Decimal("100")
    no_size = Decimal("100")
    candidates = []
    if yes_ask <= Decimal("0.02") and yes_size >= Decimal("20"):
        candidates.append(("YES", yes_ask))
    if no_ask <= Decimal("0.02") and no_size >= Decimal("20"):
        candidates.append(("NO", no_ask))
    candidates.sort(key=lambda x: x[1])
    assert candidates[0] == ("NO", Decimal("0.01"))


def test_entry_gate_rejects_thin_book():
    """Book with <BOT_G_MIN_BOOK_SIZE shares at best should be rejected."""
    yes_ask = Decimal("0.02")
    yes_size = Decimal("5")  # below 20
    qualified = yes_ask <= Decimal("0.02") and yes_size >= Decimal("20")
    assert qualified is False


def test_entry_gate_rejects_price_above_threshold():
    yes_ask = Decimal("0.05")  # 5c, above 2c threshold
    qualified = yes_ask <= Decimal("0.02")
    assert qualified is False


def test_prime_rejects_one_cent_toxic_band_even_with_cex_confirmation(
    tmp_db, monkeypatch,
):
    """Prime avoids the empirically-dead 1-3c raw jackpot zone."""
    import asyncio
    from datetime import datetime, timedelta

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.clob import ClobWrapper
    from core.portfolio import Portfolio

    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 30)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_ENTRY_PRICE", Decimal("0.04"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MAX_ENTRY_PRICE", Decimal("0.08"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_COUNTERPARTY_PRICE", Decimal("0.88"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_CEX_CONFIRM", True)

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.98"), Decimal("0.99"), Decimal("500"))
        return (Decimal("0.001"), Decimal("0.01"), Decimal("500"))

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)
    monkeypatch.setattr(
        bot_g_main,
        "_cex_confirmation",
        lambda *_args, **_kwargs: {"confirmed": True, "move_bps": "-5.0"},
    )
    monkeypatch.setattr(bot_g_main, "_book_depletion_signal", lambda *_args, **_kwargs: None)

    now_utc = datetime.now(UTC)
    market_dict = {
        "condition_id": "0xbot_g_prime_rejects_1c",
        "question": "Bitcoin Up or Down - test",
        "end_date_iso": (now_utc + timedelta(seconds=20)).isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }

    placed = asyncio.run(bot_g_main._try_enter_market(
        market_dict,
        int(now_utc.timestamp() * 1000),
        ClobWrapper(keystore=None, paper_override=True),
        Portfolio(),
        set(),
    ))

    assert placed == 0


def test_prime_accepts_four_to_eight_cent_cex_confirmed_tail(
    tmp_db, monkeypatch,
):
    """Prime's candidate edge is the 4-8c late dislocation, not raw cheapness."""
    import asyncio
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core import portfolio as portfolio_mod
    from core.clob import ClobWrapper
    from core.db import Order, Position, get_session_factory
    from core.portfolio import Portfolio

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 30)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_ENTRY_PRICE", Decimal("0.04"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MAX_ENTRY_PRICE", Decimal("0.08"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_COUNTERPARTY_PRICE", Decimal("0.88"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_CEX_CONFIRM", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_DEPLETION", False)

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.94"), Decimal("0.95"), Decimal("500"))
        return (Decimal("0.04"), Decimal("0.05"), Decimal("500"))

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)
    monkeypatch.setattr(
        bot_g_main,
        "_cex_confirmation",
        lambda *_args, **_kwargs: {"confirmed": True, "move_bps": "-6.5"},
    )
    monkeypatch.setattr(
        bot_g_main,
        "_book_depletion_signal",
        lambda *_args, **_kwargs: {"depletion_ratio": "0.7000"},
    )

    now_utc = datetime.now(UTC)
    market_dict = {
        "condition_id": "0xbot_g_prime_accepts_5c",
        "question": "Bitcoin Up or Down - test",
        "end_date_iso": (now_utc + timedelta(seconds=20)).isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }

    placed = asyncio.run(bot_g_main._try_enter_market(
        market_dict,
        int(now_utc.timestamp() * 1000),
        ClobWrapper(keystore=None, paper_override=True),
        Portfolio(),
        set(),
    ))

    assert placed == 1
    session_factory = get_session_factory()
    with session_factory() as s:
        order = s.scalars(select(Order).where(
            Order.condition_id == "0xbot_g_prime_accepts_5c",
        )).one()
        pos = s.scalars(select(Position).where(
            Position.condition_id == "0xbot_g_prime_accepts_5c",
        )).one()
        assert order.status == "FILLED"
        assert order.price == Decimal("0.05")
        assert pos.token_id == "no_tok"


def test_prime_rejects_symbol_outside_allowed_universe(tmp_db, monkeypatch):
    import asyncio
    from datetime import datetime, timedelta

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.clob import ClobWrapper
    from core.portfolio import Portfolio

    monkeypatch.setattr(bot_g_main.config, "BOT_G_ALLOWED_SYMBOLS", frozenset({"BTC", "ETH", "SOL"}))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 30)

    now_utc = datetime.now(UTC)
    market_dict = {
        "condition_id": "0xbot_g_rejects_doge_live_universe",
        "question": "Dogecoin Up or Down - test",
        "end_date_iso": (now_utc + timedelta(seconds=20)).isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }

    placed = asyncio.run(bot_g_main._try_enter_market(
        market_dict,
        int(now_utc.timestamp() * 1000),
        ClobWrapper(keystore=None, paper_override=True),
        Portfolio(),
        set(),
    ))

    assert placed == 0


def test_live_entry_persists_live_status_without_eager_fill(tmp_db, monkeypatch):
    """Live placement must not be hidden as PAPER_OPEN or phantom-filled."""
    import asyncio

    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.db import Order, Position, get_session_factory
    from core.portfolio import Portfolio

    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 30)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_ENTRY_PRICE", Decimal("0.04"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MAX_ENTRY_PRICE", Decimal("0.08"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_COUNTERPARTY_PRICE", Decimal("0.88"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_CEX_CONFIRM", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_DEPLETION", False)

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.94"), Decimal("0.95"), Decimal("500"))
        return (Decimal("0.04"), Decimal("0.05"), Decimal("500"))

    class FakeLiveClob:
        def place_limit(self, **_kwargs):
            return SimpleNamespace(order_id="live-order-1", status="OPEN", raw={})

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)
    monkeypatch.setattr(bot_g_main, "_book_depletion_signal", lambda *_a, **_k: None)

    now_utc = datetime.now(UTC)
    monkeypatch.setattr(bot_g_main.time, "time", lambda: now_utc.timestamp())
    market_dict = {
        "condition_id": "0xbot_g_live_status",
        "question": "Bitcoin Up or Down - test",
        "end_date_iso": (now_utc + timedelta(seconds=20)).isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }

    placed = asyncio.run(bot_g_main._try_enter_market(
        market_dict,
        int(now_utc.timestamp() * 1000),
        FakeLiveClob(),
        Portfolio(),
        set(),
    ))

    assert placed == 1
    with get_session_factory()() as s:
        order = s.scalars(select(Order).where(
            Order.condition_id == "0xbot_g_live_status",
        )).one()
        positions = list(s.scalars(select(Position).where(
            Position.condition_id == "0xbot_g_live_status",
        )))
    assert order.order_id == "live-order-1"
    assert order.status == "OPEN"
    assert positions == []


def test_live_prime_skips_optional_labels_when_gates_disabled(tmp_db, monkeypatch):
    """Observation-only CEX/depletion labels must not consume the live entry window."""
    import asyncio

    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.db import Event, get_session_factory
    from core.portfolio import Portfolio

    monkeypatch.setattr(bot_g_main, "BOT_ID", "bot_g_prime_live")
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ALLOWED_SYMBOLS", frozenset({"BTC"}))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 45)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_ENTRY_PRICE", Decimal("0.035"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MAX_ENTRY_PRICE", Decimal("0.055"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_COUNTERPARTY_PRICE", Decimal("0.91"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_CEX_CONFIRM", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_DEPLETION", False)

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.94"), Decimal("0.95"), Decimal("500"))
        return (Decimal("0.04"), Decimal("0.045"), Decimal("25"))

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("optional live label lookup should be skipped")

    class FakeLiveClob:
        paper_override = False

        def _effective_paper(self):
            return False

        def place_limit(self, **_kwargs):
            return SimpleNamespace(order_id="live-skip-labels", status="OPEN", raw={})

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)
    monkeypatch.setattr(bot_g_main, "_cex_confirmation", should_not_run)
    monkeypatch.setattr(bot_g_main, "_book_depletion_signal", should_not_run)

    now_utc = datetime.now(UTC)
    monkeypatch.setattr(bot_g_main.time, "time", lambda: now_utc.timestamp())
    market_dict = {
        "condition_id": "0xbot_g_skip_optional_labels",
        "question": "Bitcoin Up or Down - test",
        "end_date_iso": (now_utc + timedelta(seconds=35)).isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }

    placed = asyncio.run(bot_g_main._try_enter_market(
        market_dict,
        int(now_utc.timestamp() * 1000),
        FakeLiveClob(),
        Portfolio(),
        set(),
    ))

    assert placed == 1
    with get_session_factory()() as s:
        event = s.scalars(select(Event).where(
            Event.event_type == "bot_g.entry_placed",
        )).one()
    assert event.payload["cex"]["skipped"] is True
    assert event.payload["depletion"]["skipped"] is True
    assert "timing_cumulative_ms" in event.payload


@pytest.mark.parametrize(
    ("observed_ask", "expected_limit"),
    [
        (Decimal("0.06"), Decimal("0.07")),
        (Decimal("0.07"), Decimal("0.08")),
        (Decimal("0.08"), Decimal("0.08")),
    ],
)
def test_live_entry_crosses_one_tick_with_decimal_band_caps(
    tmp_db,
    monkeypatch,
    observed_ask,
    expected_limit,
):
    """Tiny-live improves transfer by one tick, capped at the 8c band top."""
    import asyncio

    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.db import Event, Order, Position, get_session_factory
    from core.portfolio import Portfolio

    monkeypatch.setattr(bot_g_main, "BOT_ID", "bot_g_prime_live")
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ALLOWED_SYMBOLS", frozenset({"BTC"}))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 45)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_ENTRY_PRICE", Decimal("0.06"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MAX_ENTRY_PRICE", Decimal("0.08"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ENTRY_TICK_SIZE", Decimal("0.01"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS", 1)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_COUNTERPARTY_PRICE", Decimal("0.91"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_CEX_CONFIRM", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_DEPLETION", False)

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.94"), Decimal("0.95"), Decimal("500"))
        return (observed_ask - Decimal("0.01"), observed_ask, Decimal("25"))

    class FakeLiveClob:
        paper_override = False
        submitted: dict | None = None

        def _effective_paper(self):
            return False

        def place_limit(self, **kwargs):
            self.submitted = kwargs
            return SimpleNamespace(order_id="live-cross-1", status="OPEN", raw={})

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)
    monkeypatch.setattr(bot_g_main, "_book_depletion_signal", lambda *_a, **_k: None)

    now_utc = datetime.now(UTC)
    monkeypatch.setattr(bot_g_main.time, "time", lambda: now_utc.timestamp())
    market_dict = {
        "condition_id": "0xbot_g_live_cross",
        "question": "Bitcoin Up or Down - test",
        "end_date_iso": (now_utc + timedelta(seconds=35)).isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }
    clob = FakeLiveClob()

    placed = asyncio.run(bot_g_main._try_enter_market(
        market_dict,
        int(now_utc.timestamp() * 1000),
        clob,
        Portfolio(),
        set(),
    ))

    assert placed == 1
    assert clob.submitted is not None
    assert clob.submitted["price"] == expected_limit
    assert clob.submitted["size"] == Decimal("25")

    with get_session_factory()() as s:
        order = s.scalars(select(Order).where(
            Order.condition_id == "0xbot_g_live_cross",
        )).one()
        positions = list(s.scalars(select(Position).where(
            Position.condition_id == "0xbot_g_live_cross",
        )))
        event = s.scalars(select(Event).where(
            Event.event_type == "bot_g.entry_placed",
        )).one()
    assert order.price == expected_limit.quantize(Decimal("0.00000000"))
    assert order.size == Decimal("25.00000000")
    assert positions == []
    assert "timing_ms" in event.payload
    assert "book_lookup_ms" in event.payload["timing_ms"]
    assert "submit_response_ms" in event.payload["timing_ms"]


def test_live_one_dollar_probe_passes_min_notional_guard(tmp_db, monkeypatch):
    """ADR-136's $1 probe should not be rejected by Decimal precision dust."""
    import asyncio

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.portfolio import Portfolio

    monkeypatch.setattr(bot_g_main, "BOT_ID", "bot_g_prime_live")
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ALLOWED_SYMBOLS", frozenset({"BTC"}))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 45)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_ENTRY_PRICE", Decimal("0.06"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MAX_ENTRY_PRICE", Decimal("0.08"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_FIXED_TRADE_USD", Decimal("1"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ENTRY_TICK_SIZE", Decimal("0.01"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS", 1)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_COUNTERPARTY_PRICE", Decimal("0.91"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_CEX_CONFIRM", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_DEPLETION", False)

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.94"), Decimal("0.95"), Decimal("500"))
        return (Decimal("0.052"), Decimal("0.062"), Decimal("500"))

    class FakeLiveClob:
        paper_override = False
        submitted: dict | None = None

        def _effective_paper(self):
            return False

        def place_limit(self, **kwargs):
            self.submitted = kwargs
            return SimpleNamespace(order_id="live-one-dollar", status="OPEN", raw={})

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)
    monkeypatch.setattr(bot_g_main, "_book_depletion_signal", lambda *_a, **_k: None)

    now_utc = datetime.now(UTC)
    monkeypatch.setattr(bot_g_main.time, "time", lambda: now_utc.timestamp())
    market_dict = {
        "condition_id": "0xbot_g_live_one_dollar",
        "question": "Bitcoin Up or Down - test",
        "end_date_iso": (now_utc + timedelta(seconds=35)).isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }
    clob = FakeLiveClob()

    placed = asyncio.run(bot_g_main._try_enter_market(
        market_dict,
        int(now_utc.timestamp() * 1000),
        clob,
        Portfolio(),
        set(),
    ))

    assert placed == 1
    assert clob.submitted is not None
    assert clob.submitted["price"] == Decimal("0.072")
    assert clob.submitted["size"] * clob.submitted["price"] >= Decimal("0.999999")


def test_live_entry_blocks_before_submit_on_fleet_cap_breach(tmp_db, monkeypatch):
    """Bot G live must honour the cross-bot fleet cap before touching CLOB."""
    import asyncio

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core import fleet as fleet_mod
    from core.portfolio import Portfolio

    monkeypatch.setattr(bot_g_main, "BOT_ID", "bot_g_prime_live")
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ALLOWED_SYMBOLS", frozenset({"ETH"}))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 45)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_ENTRY_PRICE", Decimal("0.06"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MAX_ENTRY_PRICE", Decimal("0.08"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_FIXED_TRADE_USD", Decimal("1"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ENTRY_TICK_SIZE", Decimal("0.01"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS", 1)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_COUNTERPARTY_PRICE", Decimal("0.91"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_CEX_CONFIRM", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_DEPLETION", False)

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.93"), Decimal("0.94"), Decimal("500"))
        return (Decimal("0.06"), Decimal("0.07"), Decimal("500"))

    class FakeLiveClob:
        paper_override = False
        submitted = False

        def _effective_paper(self):
            return False

        def place_limit(self, **_kwargs):
            self.submitted = True
            raise AssertionError("fleet cap breach must block before submit")

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)
    monkeypatch.setattr(bot_g_main, "_book_depletion_signal", lambda *_a, **_k: None)
    monkeypatch.setattr(
        fleet_mod,
        "check_fleet_exposure",
        lambda bot_id, intended: SimpleNamespace(
            ok=False,
            intended_usd=intended,
            current_total_usd=Decimal("160"),
            deployable_cap_usd=Decimal("160"),
            reason="fleet_cap_breach",
        ),
    )

    now_utc = datetime.now(UTC)
    monkeypatch.setattr(bot_g_main.time, "time", lambda: now_utc.timestamp())
    market_dict = {
        "condition_id": "0xbot_g_fleet_cap",
        "question": "Ethereum Up or Down - test",
        "end_date_iso": (now_utc + timedelta(seconds=35)).isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }
    clob = FakeLiveClob()

    placed = asyncio.run(bot_g_main._try_enter_market(
        market_dict,
        int(now_utc.timestamp() * 1000),
        clob,
        Portfolio(),
        set(),
    ))

    assert placed == 0
    assert clob.submitted is False


def test_entry_rechecks_fresh_time_before_submit(tmp_db, monkeypatch):
    """A stale scan timestamp must not submit into/after the close."""
    import asyncio

    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.db import Event, Order, get_session_factory
    from core.portfolio import Portfolio

    monkeypatch.setattr(bot_g_main, "BOT_ID", "bot_g_prime_live")
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ALLOWED_SYMBOLS", frozenset({"BTC"}))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 45)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_ENTRY_LEAD_SECONDS", 5)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_ENTRY_PRICE", Decimal("0.06"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MAX_ENTRY_PRICE", Decimal("0.08"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ENTRY_TICK_SIZE", Decimal("0.01"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS", 1)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_COUNTERPARTY_PRICE", Decimal("0.91"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_CEX_CONFIRM", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_REQUIRE_DEPLETION", False)

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.94"), Decimal("0.95"), Decimal("500"))
        return (Decimal("0.06"), Decimal("0.07"), Decimal("100"))

    class FakeLiveClob:
        paper_override = False
        submitted = False

        def _effective_paper(self):
            return False

        def place_limit(self, **_kwargs):
            self.submitted = True
            return SimpleNamespace(order_id="should-not-submit", status="OPEN", raw={})

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)
    monkeypatch.setattr(bot_g_main, "_book_depletion_signal", lambda *_a, **_k: None)

    stale_now = datetime.now(UTC)
    end_at = stale_now + timedelta(seconds=40)
    fresh_now = end_at - timedelta(seconds=2)
    monkeypatch.setattr(bot_g_main.time, "time", lambda: fresh_now.timestamp())
    market_dict = {
        "condition_id": "0xbot_g_stale_time",
        "question": "Bitcoin Up or Down - test",
        "end_date_iso": end_at.isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }
    clob = FakeLiveClob()

    placed = asyncio.run(bot_g_main._try_enter_market(
        market_dict,
        int(stale_now.timestamp() * 1000),
        clob,
        Portfolio(),
        set(),
    ))

    assert placed == 0
    assert clob.submitted is False
    with get_session_factory()() as s:
        orders = list(s.scalars(select(Order).where(
            Order.condition_id == "0xbot_g_stale_time",
        )))
        event = s.scalars(select(Event).where(
            Event.event_type == "bot_g.entry_stale_time_rejected",
        )).one()
    assert orders == []
    assert event.payload["initial_t_to_res_sec"] == 40
    assert event.payload["fresh_t_to_res_sec"] == 2
    assert event.payload["min_lead_sec"] == 5
    assert "timing_ms" in event.payload
    assert "book_lookup_ms" in event.payload["timing_ms"]


def test_reconcile_execution_truth_uses_live_reconciler(monkeypatch):
    from bots.bot_g_longshot import __main__ as bot_g_main

    class FakeLiveClob:
        paper_override = False

        def _effective_paper(self):
            return False

    class FakePortfolio:
        def __init__(self):
            self.live_called = False
            self.paper_called = False
            self.require_known_order = None

        def reconcile_live_fills(self, clob, bot_id, require_known_order=False):
            self.live_called = True
            self.require_known_order = require_known_order
            assert bot_id == "bot_g"
            assert isinstance(clob, FakeLiveClob)
            return 2

        def simulate_paper_fills(self, bot_id):  # pragma: no cover
            self.paper_called = True
            return 0

    monkeypatch.setattr(bot_g_main, "BOT_ID", "bot_g")
    portfolio = FakePortfolio()
    count = bot_g_main._reconcile_execution_truth(portfolio, FakeLiveClob())

    assert count == 2
    assert portfolio.live_called is True
    assert portfolio.require_known_order is True
    assert portfolio.paper_called is False


def test_reconcile_live_open_orders_marks_absent_order_closed(tmp_db, monkeypatch):
    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.db import Event, Order, Trade, get_session_factory

    class FakeLiveClob:
        paper_override = False

        def _effective_paper(self):
            return False

        def get_user_orders(self):
            return []

    monkeypatch.setattr(bot_g_main, "BOT_ID", "bot_g")
    sf = get_session_factory()
    with sf() as s:
        s.add(Order(
            order_id="live-resting-1",
            bot_id="bot_g",
            condition_id="0xbot_g_absent_order",
            token_id="tok",
            side="BUY",
            price=Decimal("0.04"),
            size=Decimal("100"),
            status="live",
        ))
        s.commit()

    closed = bot_g_main._reconcile_live_open_orders(FakeLiveClob())

    assert closed == 1
    with sf() as s:
        order = s.get(Order, "live-resting-1")
        assert order is not None
        assert order.status == "EXCHANGE_CLOSED"
        assert s.scalars(select(Trade).where(Trade.order_id == "live-resting-1")).first() is None
        event = s.scalars(select(Event).where(
            Event.event_type == "bot_g.exchange_order_reconciled",
        )).one()
        assert event.payload["order_id"] == "live-resting-1"


def test_reconcile_live_open_orders_marks_absent_partial_closed(tmp_db, monkeypatch):
    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.db import Event, Order, Trade, get_session_factory

    class FakeLiveClob:
        paper_override = False

        def _effective_paper(self):
            return False

        def get_user_orders(self):
            return []

    monkeypatch.setattr(bot_g_main, "BOT_ID", "bot_g")
    sf = get_session_factory()
    with sf() as s:
        s.add(Order(
            order_id="live-partial-1",
            bot_id="bot_g",
            condition_id="0xbot_g_partial_absent_order",
            token_id="tok",
            side="BUY",
            price=Decimal("0.05"),
            size=Decimal("100"),
            status="PARTIAL",
        ))
        s.add(Trade(
            trade_id="live-partial-fill-1",
            order_id="live-partial-1",
            bot_id="bot_g",
            condition_id="0xbot_g_partial_absent_order",
            token_id="tok",
            side="BUY",
            price=Decimal("0.05"),
            size=Decimal("25"),
            fee_usd=Decimal("0"),
            filled_at=datetime.now(UTC),
            usd_gbp_rate=Decimal("0.8"),
            gbp_notional=Decimal("1"),
        ))
        s.commit()

    closed = bot_g_main._reconcile_live_open_orders(FakeLiveClob())

    assert closed == 1
    with sf() as s:
        order = s.get(Order, "live-partial-1")
        assert order is not None
        assert order.status == "EXCHANGE_CLOSED"
        assert s.scalars(select(Trade).where(Trade.order_id == "live-partial-1")).first() is not None
        event = s.scalars(select(Event).where(
            Event.event_type == "bot_g.exchange_order_reconciled",
        )).one()
        assert event.payload["order_id"] == "live-partial-1"
        assert event.payload["had_fill"] is True


def test_size_capped_by_book_depth():
    """Fixed $5 trade at 0.005 = 1000 shares, but book only has 100 → fill 100."""
    fixed_usd = Decimal("5")
    ask_price = Decimal("0.005")
    book_size = Decimal("100")
    max_by_dollar = fixed_usd / ask_price  # 1000
    size = min(max_by_dollar, book_size)
    assert size == Decimal("100")
    # Resulting cost: 100 * 0.005 = $0.50 (deliberately smaller than $5 —
    # book depth ran out).
    assert size * ask_price == Decimal("0.500")


def test_size_uses_full_dollar_budget_on_deep_book():
    fixed_usd = Decimal("5")
    ask_price = Decimal("0.01")
    book_size = Decimal("10000")
    max_by_dollar = fixed_usd / ask_price  # 500
    size = min(max_by_dollar, book_size)
    assert size == Decimal("500")
    assert size * ask_price == Decimal("5")


def test_paper_take_profit_exits_on_threshold(tmp_db, monkeypatch):
    import importlib

    from sqlalchemy import select

    from core import portfolio as portfolio_mod
    from core.clob import ClobWrapper
    from core.db import Event, Market, Position, get_session_factory
    from core.portfolio import Portfolio

    monkeypatch.setenv("BOT_G_PAPER_TAKE_PROFIT_ENABLED", "true")
    monkeypatch.setenv("BOT_G_PAPER_TAKE_PROFIT_PRICE", "0.50")
    from bots.bot_g_longshot import config as bot_g_config
    importlib.reload(bot_g_config)
    from bots.bot_g_longshot import __main__ as bot_g_main
    monkeypatch.setattr(bot_g_main, "config", bot_g_config)
    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))

    now_utc = datetime.now(UTC)
    cid = "0xbot_g_take_profit"
    session_factory = get_session_factory()
    with session_factory() as s:
        s.add(Market(
            condition_id=cid,
            category="crypto",
            question="SOL up 60s?",
            fee_rate_bps=40,
            yes_token_id="yes_tok",
            no_token_id="no_tok",
            end_date=now_utc + timedelta(seconds=12),
            is_neg_risk=0,
            volume_24h_usd=Decimal("1000"),
            last_updated=now_utc,
        ))
        s.add(Position(
            bot_id="bot_g",
            condition_id=cid,
            token_id="no_tok",
            side="NO",
            size=Decimal("50"),
            avg_price=Decimal("0.04"),
            cost_basis_usd=Decimal("2.00"),
            status="OPEN",
        ))
        s.commit()

    def fake_quote(token_id, condition_id, now_ms):
        return (Decimal("0.52"), Decimal("0.55"), Decimal("100"))

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)

    exited = bot_g_main._paper_take_profit_exits(
        Portfolio(),
        ClobWrapper(keystore=None, paper_override=True),
        now=now_utc,
    )
    assert exited == 1

    with session_factory() as s:
        pos = s.scalars(select(Position).where(Position.condition_id == cid)).one()
        assert pos.status == "CLOSED"
        event = s.scalars(
            select(Event).where(Event.event_type == "bot_g.paper_take_profit_exit")
        ).one()
        assert event.payload["best_bid"] == "0.52"
        assert event.payload["threshold"] == "0.50"


def test_paper_take_profit_does_not_run_live(monkeypatch):
    import importlib

    from core.clob import ClobWrapper
    from core.portfolio import Portfolio

    monkeypatch.setenv("BOT_G_PAPER_TAKE_PROFIT_ENABLED", "true")
    from bots.bot_g_longshot import config as bot_g_config
    importlib.reload(bot_g_config)
    from bots.bot_g_longshot import __main__ as bot_g_main
    monkeypatch.setattr(bot_g_main, "config", bot_g_config)

    exited = bot_g_main._paper_take_profit_exits(
        Portfolio(),
        ClobWrapper(keystore=None, paper_override=False),
    )
    assert exited == 0


def test_take_profit_shadow_signal_does_not_sell_live(tmp_db, monkeypatch):
    import importlib

    from sqlalchemy import func, select

    from core.db import Event, Market, Position, Trade, get_session_factory

    monkeypatch.setenv("BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_ENABLED", "true")
    monkeypatch.setenv("BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_PRICE", "0.50")
    from bots.bot_g_longshot import config as bot_g_config

    importlib.reload(bot_g_config)
    from bots.bot_g_longshot import __main__ as bot_g_main

    monkeypatch.setattr(bot_g_main, "config", bot_g_config)

    now_utc = datetime.now(UTC)
    cid = "0xbot_g_live_shadow_tp"
    session_factory = get_session_factory()
    with session_factory() as s:
        s.add(
            Market(
                condition_id=cid,
                category="crypto",
                question="BTC up 60s?",
                fee_rate_bps=40,
                yes_token_id="yes_live_tok",
                no_token_id="no_live_tok",
                end_date=now_utc + timedelta(seconds=12),
                is_neg_risk=0,
                volume_24h_usd=Decimal("1000"),
                last_updated=now_utc,
            )
        )
        s.add(
            Position(
                bot_id="bot_g",
                condition_id=cid,
                token_id="no_live_tok",
                side="NO",
                size=Decimal("60"),
                avg_price=Decimal("0.05"),
                cost_basis_usd=Decimal("3.00"),
                status="OPEN",
            )
        )
        s.commit()

    def fake_quote(token_id, condition_id, now_ms):
        return (Decimal("0.52"), Decimal("0.55"), Decimal("100"))

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)

    clob = SimpleNamespace(paper_override=False)
    emitted = bot_g_main._take_profit_shadow_signals(clob, now=now_utc)
    emitted_again = bot_g_main._take_profit_shadow_signals(clob, now=now_utc)

    assert emitted == 1
    assert emitted_again == 0
    with session_factory() as s:
        pos = s.scalars(select(Position).where(Position.condition_id == cid)).one()
        assert pos.status == "OPEN"
        assert s.scalar(select(func.count(Trade.trade_id))) == 0
        event = s.scalars(
            select(Event).where(Event.event_type == "bot_g.take_profit_shadow_signal")
        ).one()
        assert event.payload["best_bid"] == "0.52"
        assert event.payload["threshold"] == "0.50"
        assert event.payload["effective_paper"] is False
        assert event.payload["shadow_only"] is True


# ---------------------------------------------------------------------------
# OQ-043: _latest_best_bid_ask fallback across event types
# ---------------------------------------------------------------------------


def test_extract_bba_from_best_bid_ask_payload():
    from bots.bot_g_longshot.__main__ import _extract_bba_from_payload
    payload = {"asset_id": "tokA", "best_bid": "0.03", "best_ask": "0.04"}
    q = _extract_bba_from_payload("best_bid_ask", payload, "tokA")
    assert q == (Decimal("0.03"), Decimal("0.04"))


def test_extract_bba_from_book_payload_picks_top_of_book():
    from bots.bot_g_longshot.__main__ import _extract_bba_from_payload
    payload = {
        "asset_id": "tokA",
        "bids": [
            {"price": "0.02", "size": "50"},
            {"price": "0.03", "size": "30"},  # best bid (max)
            {"price": "0.01", "size": "100"},
        ],
        "asks": [
            {"price": "0.06", "size": "40"},
            {"price": "0.04", "size": "25"},  # best ask (min)
            {"price": "0.05", "size": "60"},
        ],
    }
    q = _extract_bba_from_payload("book", payload, "tokA")
    assert q == (Decimal("0.03"), Decimal("0.04"))


def test_extract_bba_from_price_change_payload_matches_inner_asset():
    from bots.bot_g_longshot.__main__ import _extract_bba_from_payload
    payload = {
        "market": "cid-xyz",
        "price_changes": [
            {"asset_id": "tokB", "best_bid": "0.91", "best_ask": "0.92"},
            {"asset_id": "tokA", "best_bid": "0.04", "best_ask": "0.05"},
        ],
    }
    q = _extract_bba_from_payload("price_change", payload, "tokA")
    assert q == (Decimal("0.04"), Decimal("0.05"))


def test_extract_bba_returns_none_when_token_not_in_price_change():
    from bots.bot_g_longshot.__main__ import _extract_bba_from_payload
    payload = {
        "market": "cid-xyz",
        "price_changes": [
            {"asset_id": "tokB", "best_bid": "0.91", "best_ask": "0.92"},
        ],
    }
    q = _extract_bba_from_payload("price_change", payload, "tokA")
    assert q is None


def _make_recorder_db(tmp_path: Path, rows: list[dict]) -> Path:
    """Build a minimal pm_events sqlite DB for _latest_best_bid_ask tests."""
    db = tmp_path / "recorder.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE pm_events ("
        "  received_at_ms INTEGER NOT NULL,"
        "  subscription_id TEXT NOT NULL,"
        "  event_type TEXT NOT NULL,"
        "  asset_id TEXT,"
        "  condition_id TEXT,"
        "  payload_json TEXT NOT NULL"
        ")"
    )
    conn.executemany(
        "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, "
        "asset_id, condition_id, payload_json) VALUES "
        "(:received_at_ms, :subscription_id, :event_type, :asset_id, "
        " :condition_id, :payload_json)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def _make_recorder_markets_db(tmp_path: Path, rows: list[dict]) -> Path:
    db = tmp_path / "markets_recorder.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE markets ("
        "  scan_at_ms INTEGER NOT NULL,"
        "  condition_id TEXT NOT NULL,"
        "  question TEXT NOT NULL,"
        "  end_date_iso TEXT,"
        "  yes_token_id TEXT,"
        "  no_token_id TEXT"
        ")"
    )
    conn.executemany(
        "INSERT INTO markets (scan_at_ms, condition_id, question, end_date_iso, "
        "yes_token_id, no_token_id) VALUES "
        "(:scan_at_ms, :condition_id, :question, :end_date_iso, "
        " :yes_token_id, :no_token_id)",
        rows,
    )
    conn.commit()
    conn.close()
    return db


def test_active_markets_near_resolution_requires_fresh_market_row(
    tmp_path, monkeypatch,
):
    from bots.bot_g_longshot import __main__ as bot_g_main

    now_ms = 1_700_000_000_000
    now_dt = datetime.fromtimestamp(now_ms / 1000, tz=UTC)
    end_iso = (now_dt + timedelta(seconds=45)).isoformat()
    db = _make_recorder_markets_db(
        tmp_path,
        [
            {
                "scan_at_ms": now_ms - 5 * 60 * 1000,
                "condition_id": "stale-cid",
                "question": "Bitcoin Up or Down - stale",
                "end_date_iso": end_iso,
                "yes_token_id": "stale-yes",
                "no_token_id": "stale-no",
            },
            {
                "scan_at_ms": now_ms - 30 * 1000,
                "condition_id": "fresh-cid",
                "question": "Bitcoin Up or Down - fresh",
                "end_date_iso": end_iso,
                "yes_token_id": "fresh-yes",
                "no_token_id": "fresh-no",
            },
        ],
    )
    monkeypatch.setattr(bot_g_main.config, "BOT_G_RECORDER_DB_PATH", str(db))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MARKET_ROW_MAX_AGE_SECONDS", 120)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 60)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ENTRY_SECONDS_BEFORE_RES", 60)

    rows = bot_g_main._active_markets_near_resolution(now_ms)

    assert [row["condition_id"] for row in rows] == ["fresh-cid"]


def test_active_markets_near_resolution_allows_one_5m_discovery_cycle(
    tmp_path, monkeypatch,
):
    from bots.bot_g_longshot import __main__ as bot_g_main

    now_ms = 1_700_000_000_000
    now_dt = datetime.fromtimestamp(now_ms / 1000, tz=UTC)
    end_iso = (now_dt + timedelta(seconds=45)).isoformat()
    db = _make_recorder_markets_db(
        tmp_path,
        [
            {
                "scan_at_ms": now_ms - 7 * 60 * 1000,
                "condition_id": "too-old-cid",
                "question": "Bitcoin Up or Down - too old",
                "end_date_iso": end_iso,
                "yes_token_id": "old-yes",
                "no_token_id": "old-no",
            },
            {
                "scan_at_ms": now_ms - 5 * 60 * 1000,
                "condition_id": "cycle-fresh-cid",
                "question": "Bitcoin Up or Down - cycle fresh",
                "end_date_iso": end_iso,
                "yes_token_id": "fresh-yes",
                "no_token_id": "fresh-no",
            },
        ],
    )
    monkeypatch.setattr(bot_g_main.config, "BOT_G_RECORDER_DB_PATH", str(db))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MARKET_ROW_MAX_AGE_SECONDS", 360)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_MODE_ENABLED", True)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_PRIME_ENTRY_SECONDS", 60)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_JACKPOT_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_SCALP_MODE_ENABLED", False)
    monkeypatch.setattr(bot_g_main.config, "BOT_G_ENTRY_SECONDS_BEFORE_RES", 60)

    rows = bot_g_main._active_markets_near_resolution(now_ms)

    assert [row["condition_id"] for row in rows] == ["cycle-fresh-cid"]


def test_latest_bba_falls_back_to_price_change_when_no_best_bid_ask_event(
    tmp_path, monkeypatch,
):
    """Primary OQ-043 case: recorder wrote `price_change` events only. The old
    code returned None here and Bot G skipped the market; the fix reads the
    price_change payload and extracts the same fields."""
    now_ms = 1_700_000_000_000
    rows = [
        {
            "received_at_ms": now_ms - 2_000,
            "subscription_id": "test",
            "event_type": "price_change",
            "asset_id": "cid1",  # recorder stores condition_id here for pc events
            "condition_id": None,
            "payload_json": json.dumps({
                "market": "cid1",
                "price_changes": [
                    {"asset_id": "tokA", "best_bid": "0.04", "best_ask": "0.05"},
                    {"asset_id": "tokB", "best_bid": "0.94", "best_ask": "0.95"},
                ],
            }),
        },
    ]
    db = _make_recorder_db(tmp_path, rows)
    monkeypatch.setattr(
        "bots.bot_g_longshot.config.BOT_G_RECORDER_DB_PATH", str(db),
    )
    from bots.bot_g_longshot.__main__ import _latest_best_bid_ask
    got = _latest_best_bid_ask("tokA", "cid1", now_ms)
    assert got is not None
    bid, ask, size = got
    assert bid == Decimal("0.04")
    assert ask == Decimal("0.05")
    # No book event in the DB, so depth is 0 — caller's MIN_BOOK_SIZE gate
    # will reject. That's expected: we still returned a quote.
    assert size == Decimal("0")


def test_latest_bba_prefers_freshest_event_regardless_of_type(
    tmp_path, monkeypatch,
):
    """When multiple event types are present, pick whichever is most recent.
    A `best_bid_ask` 25s old should NOT beat a `price_change` 1s old."""
    now_ms = 1_700_000_000_000
    rows = [
        {
            "received_at_ms": now_ms - 25_000,
            "subscription_id": "test",
            "event_type": "best_bid_ask",
            "asset_id": "tokA",
            "condition_id": None,
            "payload_json": json.dumps({
                "asset_id": "tokA", "best_bid": "0.10", "best_ask": "0.11",
            }),
        },
        {
            "received_at_ms": now_ms - 1_000,
            "subscription_id": "test",
            "event_type": "price_change",
            "asset_id": "cid1",
            "condition_id": None,
            "payload_json": json.dumps({
                "market": "cid1",
                "price_changes": [
                    {"asset_id": "tokA", "best_bid": "0.04", "best_ask": "0.05"},
                ],
            }),
        },
    ]
    db = _make_recorder_db(tmp_path, rows)
    monkeypatch.setattr(
        "bots.bot_g_longshot.config.BOT_G_RECORDER_DB_PATH", str(db),
    )
    from bots.bot_g_longshot.__main__ import _latest_best_bid_ask
    got = _latest_best_bid_ask("tokA", "cid1", now_ms)
    assert got is not None
    bid, ask, _ = got
    # Fresher price_change wins over 25s-old best_bid_ask.
    assert (bid, ask) == (Decimal("0.04"), Decimal("0.05"))


def test_latest_bba_uses_book_event_for_depth(tmp_path, monkeypatch):
    """Book event provides the ask-size for the MIN_BOOK_SIZE gate."""
    now_ms = 1_700_000_000_000
    rows = [
        {
            "received_at_ms": now_ms - 2_000,
            "subscription_id": "test",
            "event_type": "price_change",
            "asset_id": "cid1",
            "condition_id": None,
            "payload_json": json.dumps({
                "market": "cid1",
                "price_changes": [
                    {"asset_id": "tokA", "best_bid": "0.04", "best_ask": "0.05"},
                ],
            }),
        },
        {
            "received_at_ms": now_ms - 30_000,
            "subscription_id": "test",
            "event_type": "book",
            "asset_id": "tokA",
            "condition_id": None,
            "payload_json": json.dumps({
                "asset_id": "tokA",
                "bids": [{"price": "0.04", "size": "200"}],
                "asks": [
                    {"price": "0.05", "size": "150"},
                    {"price": "0.06", "size": "80"},
                ],
            }),
        },
    ]
    db = _make_recorder_db(tmp_path, rows)
    monkeypatch.setattr(
        "bots.bot_g_longshot.config.BOT_G_RECORDER_DB_PATH", str(db),
    )
    from bots.bot_g_longshot.__main__ import _latest_best_bid_ask
    got = _latest_best_bid_ask("tokA", "cid1", now_ms)
    assert got is not None
    _, ask, size = got
    assert ask == Decimal("0.05")
    assert size == Decimal("150")


def test_try_enter_market_eager_fills_paper_order(tmp_db, monkeypatch):
    """OQ-044: Bot G's paper entries must produce a Position at placement time.

    Pre-fix behaviour: `simulate_paper_fills` requires a `Book` row, which
    the recorder-driven Bot G never writes, so orders sat in PAPER_OPEN
    forever (11 orphans observed on LXC 2026-04-23). After the fix,
    `_try_enter_market` calls `portfolio.on_fill` immediately after the
    paper-mode `clob.place_limit`, so the Position appears synchronously.
    """
    import asyncio
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from core import portfolio as portfolio_mod
    from core.clob import ClobWrapper
    from core.db import Market, Order, Position, get_session_factory
    from core.portfolio import Portfolio

    # Neutralise GBP lookup (no network calls in tests).
    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))

    from bots.bot_g_longshot import __main__ as bot_g_main

    # Bypass the recorder DB read — hand Bot G a fake quote that crosses
    # at 2c with 500 shares of depth (= $10 notional, plenty for $5 fixed).
    def fake_quote(token_id, condition_id, now_ms):
        return (Decimal("0.01"), Decimal("0.02"), Decimal("500"))
    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)

    # Also bypass the counterparty-purity filter by pushing the opposite
    # side to 0.99 (>= 0.90 threshold).
    def fake_quote_mixed(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.98"), Decimal("0.99"), Decimal("500"))
        return (Decimal("0.01"), Decimal("0.02"), Decimal("500"))
    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote_mixed)

    cid = "0xbot_g_eager_fill_test"
    now_utc = datetime.now(UTC)
    session_factory = get_session_factory()
    with session_factory() as s:
        s.add(Market(
            condition_id=cid,
            category="crypto",
            question="ETH up 60s?",
            fee_rate_bps=40,
            yes_token_id="yes_tok",
            no_token_id="no_tok",
            is_neg_risk=0,
            volume_24h_usd=Decimal("1000"),
            last_updated=now_utc,
        ))
        s.commit()

    clob = ClobWrapper(keystore=None, paper_override=True)
    pfo = Portfolio()

    market_dict = {
        "condition_id": cid,
        "question": "ETH up 60s?",
        "end_date_iso": (now_utc + timedelta(seconds=10)).isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }
    now_ms = int(now_utc.timestamp() * 1000)
    entered: set = set()
    placed = asyncio.run(bot_g_main._try_enter_market(
        market_dict, now_ms, clob, pfo, entered,
    ))
    assert placed == 1, "entry should succeed given qualifying quote"

    # Position exists and is OPEN.
    with session_factory() as s:
        pos = s.scalars(select(Position).where(
            Position.bot_id == "bot_g", Position.condition_id == cid,
        )).one()
        assert pos.status == "OPEN"
        assert pos.side == "NO"  # bought the cheap side
        assert pos.token_id == "no_tok"
        assert pos.size == Decimal("250")  # $5 / $0.02 = 250 shares

        # Order row flipped to FILLED (not PAPER_OPEN).
        order = s.scalars(select(Order).where(
            Order.bot_id == "bot_g", Order.condition_id == cid,
        )).one()
        assert order.status == "FILLED", (
            f"expected FILLED, got {order.status} — eager-fill path broke"
        )


def test_try_enter_market_maker_posts_bid_without_eager_fill(tmp_db, monkeypatch):
    import asyncio
    import importlib
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from core import portfolio as portfolio_mod
    from core.clob import ClobWrapper
    from core.db import Event, Market, Order, Position, get_session_factory
    from core.portfolio import Portfolio

    monkeypatch.setenv("BOT_G_EXECUTION_STYLE", "maker")
    monkeypatch.setenv("BOT_G_MIN_ENTRY_PRICE", "0.07")
    monkeypatch.setenv("BOT_G_MAX_ENTRY_PRICE", "0.08")
    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))

    from bots.bot_g_longshot import config as bot_g_config
    importlib.reload(bot_g_config)
    from bots.bot_g_longshot import __main__ as bot_g_main
    monkeypatch.setattr(bot_g_main, "config", bot_g_config)

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.91"), Decimal("0.92"), Decimal("500"))
        return (Decimal("0.06"), Decimal("0.07"), Decimal("0"))

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)

    cid = "0xbot_g_maker_entry"
    now_utc = datetime.now(UTC)
    session_factory = get_session_factory()
    with session_factory() as s:
        s.add(Market(
            condition_id=cid,
            category="crypto",
            question="ETH up 60s?",
            fee_rate_bps=40,
            yes_token_id="yes_tok",
            no_token_id="no_tok",
            is_neg_risk=0,
            volume_24h_usd=Decimal("1000"),
            last_updated=now_utc,
        ))
        s.commit()

    placed = asyncio.run(bot_g_main._try_enter_market(
        {
            "condition_id": cid,
            "question": "ETH up 60s?",
            "end_date_iso": (now_utc + timedelta(seconds=10)).isoformat(),
            "yes_token_id": "yes_tok",
            "no_token_id": "no_tok",
        },
        int(now_utc.timestamp() * 1000),
        ClobWrapper(keystore=None, paper_override=True),
        Portfolio(),
        set(),
    ))

    assert placed == 1
    with session_factory() as s:
        order = s.scalars(select(Order).where(Order.condition_id == cid)).one()
        assert order.price == Decimal("0.06000000")
        assert order.status == "PAPER_OPEN"
        assert order.order_type == "MAKER_GTC"
        assert list(s.scalars(select(Position).where(Position.condition_id == cid))) == []
        event = s.scalars(
            select(Event).where(Event.event_type == "bot_g.entry_placed")
        ).one()
        assert event.payload["execution_style"] == "maker"
        assert event.payload["observed_ask_price"] == "0.07"
        assert event.payload["signal_price"] == "0.07"


def test_cancel_expired_maker_orders_marks_paper_cancelled(tmp_db, monkeypatch):
    from datetime import datetime, timedelta

    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.clob import ClobWrapper
    from core.db import Event, Order, get_session_factory

    now = datetime.now(UTC)
    sf = get_session_factory()
    with sf() as s:
        s.add(Order(
            order_id="paper-maker-cancel",
            bot_id="bot_g",
            condition_id="cond-maker-cancel",
            token_id="tok-maker",
            side="BUY",
            price=Decimal("0.06"),
            size=Decimal("16.66666667"),
            status="PAPER_OPEN",
            order_type="MAKER_GTC",
            placed_at=now - timedelta(seconds=6),
        ))
        s.add(Event(
            bot_id="bot_g",
            event_type="bot_g.entry_placed",
            severity="info",
            message="maker entry",
            payload={
                "order_id": "paper-maker-cancel",
                "fresh_t_to_res_sec": 10,
                "maker_cancel_lead_sec": 5,
            },
            created_at=now - timedelta(seconds=6),
        ))
        s.commit()

    cancelled = bot_g_main._cancel_expired_maker_orders(
        ClobWrapper(keystore=None, paper_override=True)
    )

    assert cancelled == 1
    with sf() as s:
        order = s.get(Order, "paper-maker-cancel")
        assert order.status == "CANCELLED"
        event = s.scalars(
            select(Event).where(Event.event_type == "bot_g.maker_order_cancelled")
        ).one()
        assert event.payload["execution_mode"] == "paper"


def test_maker_paper_fill_requires_later_taker_sell_print(tmp_db, tmp_path, monkeypatch):
    from datetime import datetime

    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core import portfolio as portfolio_mod
    from core.db import Event, Market, Order, Position, Trade, get_session_factory
    from core.portfolio import Portfolio

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))

    rec_db = tmp_path / "recorder.db"
    rec = sqlite3.connect(rec_db)
    rec.execute(
        "CREATE TABLE pm_events ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "received_at_ms INTEGER NOT NULL,"
        "subscription_id TEXT NOT NULL,"
        "event_type TEXT NOT NULL,"
        "asset_id TEXT,"
        "condition_id TEXT,"
        "payload_json TEXT NOT NULL"
        ")"
    )

    now = datetime.now(UTC)
    placed_ms = int(now.timestamp() * 1000)
    token_id = "maker-token"
    condition_id = "maker-fill-cid"
    # BUY prints and SELL prints above our bid do not fill a resting maker BUY.
    rec.execute(
        "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, asset_id, condition_id, payload_json) "
        "VALUES (?, 'sub', 'last_trade_price', ?, ?, ?)",
        (
            placed_ms + 1_000,
            token_id,
            condition_id,
            json.dumps({"side": "BUY", "price": "0.03", "size": "10"}),
        ),
    )
    rec.execute(
        "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, asset_id, condition_id, payload_json) "
        "VALUES (?, 'sub', 'last_trade_price', ?, ?, ?)",
        (
            placed_ms + 2_000,
            token_id,
            condition_id,
            json.dumps({"side": "SELL", "price": "0.04", "size": "10"}),
        ),
    )
    # A later taker SELL at/below our bid fills the paper maker BUY.
    rec.execute(
        "INSERT INTO pm_events (received_at_ms, subscription_id, event_type, asset_id, condition_id, payload_json) "
        "VALUES (?, 'sub', 'last_trade_price', ?, ?, ?)",
        (
            placed_ms + 3_000,
            token_id,
            condition_id,
            json.dumps({"side": "SELL", "price": "0.02", "size": "50"}),
        ),
    )
    rec.commit()
    rec.close()
    monkeypatch.setattr(bot_g_main.config, "BOT_G_RECORDER_DB_PATH", str(rec_db))

    sf = get_session_factory()
    with sf() as s:
        s.add(Market(
            condition_id=condition_id,
            category="crypto",
            question="BTC up?",
            fee_rate_bps=40,
            yes_token_id="yes-token",
            no_token_id=token_id,
            is_neg_risk=0,
            volume_24h_usd=Decimal("1000"),
            last_updated=now,
        ))
        s.add(Order(
            order_id="paper-maker-fill",
            bot_id="bot_g",
            condition_id=condition_id,
            token_id=token_id,
            side="BUY",
            price=Decimal("0.03"),
            size=Decimal("50"),
            status="PAPER_OPEN",
            order_type="MAKER_GTC",
            placed_at=now,
        ))
        s.commit()

    fills = bot_g_main._simulate_maker_paper_fills(Portfolio())
    fills_again = bot_g_main._simulate_maker_paper_fills(Portfolio())

    assert fills == 1
    assert fills_again == 0
    with sf() as s:
        trade = s.scalars(select(Trade).where(Trade.order_id == "paper-maker-fill")).one()
        assert trade.price == Decimal("0.03000000")
        assert trade.size == Decimal("50.00000000")
        assert trade.fee_usd == Decimal("0E-8")
        order = s.get(Order, "paper-maker-fill")
        assert order.status == "FILLED"
        pos = s.scalars(select(Position).where(Position.condition_id == condition_id)).one()
        assert pos.side == "NO"
        event = s.scalars(
            select(Event).where(Event.event_type == "bot_g.maker_paper_filled")
        ).one()
        assert event.payload["trigger_side"] == "SELL"
        assert event.payload["trigger_trade_price"] == "0.02"


def test_counterparty_floor_allows_eight_cent_entry(tmp_db, monkeypatch):
    """Session 27: the default purity floor must move with the entry ceiling.

    With BOT_G_MAX_ENTRY_PRICE=0.08, a real cheap-side book can be 0.08/0.88.
    The old fixed 0.90 counterparty floor rejected it before entry.
    """
    import asyncio
    import importlib
    from datetime import datetime

    from sqlalchemy import select

    from core import portfolio as portfolio_mod
    from core.clob import ClobWrapper
    from core.db import Market, Order, Position, get_session_factory
    from core.portfolio import Portfolio

    monkeypatch.setenv("BOT_G_MAX_ENTRY_PRICE", "0.08")
    monkeypatch.delenv("BOT_G_MIN_COUNTERPARTY_PRICE", raising=False)

    from bots.bot_g_longshot import config as bot_g_config
    importlib.reload(bot_g_config)
    from bots.bot_g_longshot import __main__ as bot_g_main
    monkeypatch.setattr(bot_g_main, "config", bot_g_config)

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.07"), Decimal("0.08"), Decimal("500"))
        return (Decimal("0.87"), Decimal("0.88"), Decimal("500"))

    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)

    cid = "0xbot_g_eight_cent_entry"
    now_utc = datetime.now(UTC)
    session_factory = get_session_factory()
    with session_factory() as s:
        s.add(Market(
            condition_id=cid,
            category="crypto",
            question="ETH up 60s?",
            fee_rate_bps=40,
            yes_token_id="yes_tok",
            no_token_id="no_tok",
            is_neg_risk=0,
            volume_24h_usd=Decimal("1000"),
            last_updated=now_utc,
        ))
        s.commit()

    assert Decimal("0.88") == bot_g_config.BOT_G_MIN_COUNTERPARTY_PRICE

    placed = asyncio.run(bot_g_main._try_enter_market(
        {
            "condition_id": cid,
            "question": "ETH up 60s?",
            "end_date_iso": (now_utc + timedelta(seconds=10)).isoformat(),
            "yes_token_id": "yes_tok",
            "no_token_id": "no_tok",
        },
        int(now_utc.timestamp() * 1000),
        ClobWrapper(keystore=None, paper_override=True),
        Portfolio(),
        set(),
    ))

    assert placed == 1
    with session_factory() as s:
        order = s.scalars(select(Order).where(
            Order.bot_id == "bot_g",
            Order.condition_id == cid,
        )).one()
        pos = s.scalars(select(Position).where(
            Position.bot_id == "bot_g",
            Position.condition_id == cid,
        )).one()
        assert order.status == "FILLED"
        assert pos.status == "OPEN"
        assert pos.token_id == "yes_tok"
        assert pos.avg_price == Decimal("0.08")


def test_try_enter_market_idempotent_on_rescan(tmp_db, monkeypatch):
    """After eager-fill creates a Position, re-entering the same market in
    the same scan tick must skip (existing Position gate)."""
    import asyncio
    from datetime import datetime

    from sqlalchemy import select

    from core import portfolio as portfolio_mod
    from core.clob import ClobWrapper
    from core.db import Market, Position, get_session_factory
    from core.portfolio import Portfolio

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))

    from bots.bot_g_longshot import __main__ as bot_g_main

    def fake_quote(token_id, condition_id, now_ms):
        if token_id == "yes_tok":
            return (Decimal("0.98"), Decimal("0.99"), Decimal("500"))
        return (Decimal("0.01"), Decimal("0.02"), Decimal("500"))
    monkeypatch.setattr(bot_g_main, "_latest_best_bid_ask", fake_quote)

    cid = "0xbot_g_idempotent"
    now_utc = datetime.now(UTC)
    session_factory = get_session_factory()
    with session_factory() as s:
        s.add(Market(
            condition_id=cid,
            category="crypto",
            question="Bitcoin Up or Down - May 2",
            fee_rate_bps=40,
            yes_token_id="yes_tok",
            no_token_id="no_tok",
            is_neg_risk=0,
            volume_24h_usd=Decimal("1000"),
            last_updated=now_utc,
        ))
        s.commit()

    clob = ClobWrapper(keystore=None, paper_override=True)
    pfo = Portfolio()
    market_dict = {
        "condition_id": cid,
        "question": "Bitcoin Up or Down - May 2",
        "end_date_iso": (now_utc + timedelta(seconds=10)).isoformat(),
        "yes_token_id": "yes_tok",
        "no_token_id": "no_tok",
    }
    now_ms = int(now_utc.timestamp() * 1000)

    # First entry creates a Position.
    entered: set = set()
    n1 = asyncio.run(bot_g_main._try_enter_market(market_dict, now_ms, clob, pfo, entered))
    assert n1 == 1

    # Second call on the same market in a fresh session — Position gate
    # should skip without creating a second order.
    entered.clear()
    n2 = asyncio.run(bot_g_main._try_enter_market(market_dict, now_ms, clob, pfo, entered))
    assert n2 == 0

    with session_factory() as s:
        n_pos = s.scalars(select(Position).where(
            Position.bot_id == "bot_g", Position.condition_id == cid,
        )).all()
        assert len(n_pos) == 1


def test_candidate_observation_recorded_and_summarised():
    """Telemetry helper accumulates observations and produces percentile
    + would-qualify counts over a known window."""
    import time

    from bots.bot_g_longshot import __main__ as bot_g_main

    # Reset the ring so the test is isolated.
    bot_g_main._CANDIDATE_OBSERVATIONS.clear()

    now_ms = int(time.time() * 1000)
    # 10 observations: cheap-side prices span 0.01 to 0.10.
    for i, cheap in enumerate([
        Decimal("0.01"), Decimal("0.02"), Decimal("0.03"), Decimal("0.04"),
        Decimal("0.05"), Decimal("0.06"), Decimal("0.07"), Decimal("0.08"),
        Decimal("0.09"), Decimal("0.10"),
    ]):
        # YES is cheap on even i, NO is cheap on odd i — sanity-check the
        # helper uses min(yes, no).
        if i % 2 == 0:
            bot_g_main._record_candidate_observation(now_ms - i * 100, cheap, Decimal("0.95"), 55)
        else:
            bot_g_main._record_candidate_observation(now_ms - i * 100, Decimal("0.95"), cheap, 55)

    assert len(bot_g_main._CANDIDATE_OBSERVATIONS) == 10

    # Observations with a zero ask on ONE side are now accepted (2026-04-23:
    # the recorder's WSS subscription has per-market gaps, so requiring both
    # sides dropped all observations for near-resolution markets). The
    # missing side is normalised so min(y,n) still picks the present side.
    bot_g_main._record_candidate_observation(now_ms, Decimal("0"), Decimal("0.5"), 30)
    bot_g_main._record_candidate_observation(now_ms, Decimal("0.5"), Decimal("0"), 30)
    assert len(bot_g_main._CANDIDATE_OBSERVATIONS) == 12, (
        "single-side observations must be recorded with missing side normalised"
    )

    # Both sides zero → still dropped (no signal).
    bot_g_main._record_candidate_observation(now_ms, Decimal("0"), Decimal("0"), 30)
    assert len(bot_g_main._CANDIDATE_OBSERVATIONS) == 12, (
        "observations with both sides zero must be dropped"
    )

    # Downstream min() on single-side obs must yield the present side.
    # The two single-side entries had present-side 0.5; the other side was
    # normalised to Decimal("10"), so min = 0.5.
    last_two = bot_g_main._CANDIDATE_OBSERVATIONS[-2:]
    assert all(min(y, n) == Decimal("0.5") for _, y, n, _ in last_two)


def test_candidate_observation_bounded_memory():
    """Ring is capped at _CANDIDATE_OBS_CAP — old observations drop off the front."""
    import time

    from bots.bot_g_longshot import __main__ as bot_g_main

    bot_g_main._CANDIDATE_OBSERVATIONS.clear()
    cap = bot_g_main._CANDIDATE_OBS_CAP
    now_ms = int(time.time() * 1000)
    for i in range(cap + 200):
        bot_g_main._record_candidate_observation(now_ms + i, Decimal("0.02"), Decimal("0.97"), 55)
    assert len(bot_g_main._CANDIDATE_OBSERVATIONS) == cap, (
        f"ring must be bounded at {cap}, got {len(bot_g_main._CANDIDATE_OBSERVATIONS)}"
    )
    # Oldest 200 should have dropped off; the first remaining entry is the 200th insert.
    first_ms = bot_g_main._CANDIDATE_OBSERVATIONS[0][0]
    assert first_ms == now_ms + 200


def test_emit_candidate_summary_trims_old_observations(tmp_db, monkeypatch):
    """Summary emitter drops entries older than 1h + writes an Event row."""
    import time

    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.db import Event, get_session_factory

    bot_g_main._CANDIDATE_OBSERVATIONS.clear()
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MIN_ENTRY_PRICE", Decimal("0"))
    monkeypatch.setattr(bot_g_main.config, "BOT_G_MAX_ENTRY_PRICE", Decimal("0.02"))
    now_ms = int(time.time() * 1000)

    # Two observations >1h old, three fresh.
    bot_g_main._record_candidate_observation(
        now_ms - 4_000_000, Decimal("0.04"), Decimal("0.95"), 55,
    )
    bot_g_main._record_candidate_observation(
        now_ms - 3_700_000, Decimal("0.06"), Decimal("0.95"), 55,
    )
    bot_g_main._record_candidate_observation(now_ms - 60_000, Decimal("0.02"), Decimal("0.98"), 45)
    bot_g_main._record_candidate_observation(now_ms - 30_000, Decimal("0.07"), Decimal("0.90"), 58)
    bot_g_main._record_candidate_observation(now_ms, Decimal("0.09"), Decimal("0.88"), 52)

    bot_g_main._emit_candidate_summary(now_ms)

    # Old-than-1h observations got trimmed.
    assert len(bot_g_main._CANDIDATE_OBSERVATIONS) == 3

    session_factory = get_session_factory()
    with session_factory() as s:
        evs = s.scalars(select(Event).where(
            Event.bot_id == "bot_g",
            Event.event_type == "bot_g.candidate_summary",
        )).all()
        assert len(evs) == 1
        payload = evs[0].payload
        assert payload["n"] == 3
        # 0.02, 0.07, 0.09 → qualifying at 0.05 ceiling = 1 (just 0.02);
        #                    at 0.08 = 2 (0.02 + 0.07); at 0.10 = 3 (all).
        assert payload["qualify_counts"]["0.05"] == 1
        assert payload["qualify_counts"]["0.08"] == 2
        assert payload["qualify_counts"]["0.10"] == 3
        assert payload["current_min"] == "0"
        assert payload["current_ceiling"] == "0.02"
        assert payload["current_band_count"] == 1
        assert payload["below_current_min"] == 0
        assert payload["above_current_max"] == 2


def test_emit_candidate_summary_records_empty_quote_window(tmp_db):
    import time

    from sqlalchemy import select

    from bots.bot_g_longshot import __main__ as bot_g_main
    from core.db import Event, get_session_factory

    bot_g_main._CANDIDATE_OBSERVATIONS.clear()
    bot_g_main._emit_candidate_summary(int(time.time() * 1000))

    session_factory = get_session_factory()
    with session_factory() as s:
        event = s.scalars(
            select(Event).where(Event.event_type == "bot_g.candidate_summary")
        ).one()
        assert event.payload["n"] == 0
        assert event.payload["reason"] == "no_usable_quote_observations"
        assert event.payload["current_band_count"] == 0


def test_latest_bba_returns_none_when_all_events_stale(tmp_path, monkeypatch):
    now_ms = 1_700_000_000_000
    rows = [
        {
            "received_at_ms": now_ms - 120_000,  # beyond 90s window
            "subscription_id": "test",
            "event_type": "price_change",
            "asset_id": "cid1",
            "condition_id": None,
            "payload_json": json.dumps({
                "market": "cid1",
                "price_changes": [
                    {"asset_id": "tokA", "best_bid": "0.04", "best_ask": "0.05"},
                ],
            }),
        },
    ]
    db = _make_recorder_db(tmp_path, rows)
    monkeypatch.setattr(
        "bots.bot_g_longshot.config.BOT_G_RECORDER_DB_PATH", str(db),
    )
    from bots.bot_g_longshot.__main__ import _latest_best_bid_ask
    assert _latest_best_bid_ask("tokA", "cid1", now_ms) is None
