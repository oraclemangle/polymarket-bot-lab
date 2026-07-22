"""Crypto recorder — capture-phase configuration.

All params env-overridable per operator preference (see
`feedback_risk_vs_profit.md`): defaults are safe; nothing is hard-blocking.

This module keeps the historical ``BOT_E_*`` names for compatibility with the
deployed service, but the recorder is now shared crypto-market telemetry for
Bot G / Longshot Prime research rather than an active Bot E trading component.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_any(names: tuple[str, ...], default: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None:
            return value
    return default


# Where to write recorded events. Defaults to repo-local `data/bot_e_recorder.db`
# on dev, typically overridden to data/bot_e_recorder.db
# on the bot host.
BOT_E_RECORDER_DB_PATH = Path(_env_any(
    ("CRYPTO_RECORDER_DB_PATH", "BOT_E_RECORDER_DB_PATH"),
    str(Path(__file__).resolve().parents[2] / "data" / "bot_e_recorder.db"),
))

# Symbols we care about on the CEX side. Bot G live stays separately gated by
# BOT_G_ALLOWED_SYMBOLS; this recorder list can be wider for paper/research.
BOT_E_CEX_SYMBOLS = [
    s.strip().upper()
    for s in _env_any(
        ("CRYPTO_RECORDER_CEX_SYMBOLS", "BOT_E_CEX_SYMBOLS"),
        "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT",
    ).split(",")
    if s.strip()
]

# Polymarket categories we care about. The 15-min crypto markets live under
# tags like "crypto" / "bitcoin" / "ethereum" / "solana". Discovery logic
# (bots/bot_e_recorder/market_discovery.py) filters on question patterns
# matching "Up or down on BTC/ETH/SOL/XRP/DOGE for the period ending ...".
BOT_E_MARKET_TAGS = [
    t.strip()
    for t in _env_any(
        ("CRYPTO_RECORDER_MARKET_TAGS", "BOT_E_MARKET_TAGS"),
        "crypto,bitcoin,ethereum,solana,xrp,ripple,dogecoin,doge",
    ).split(",")
    if t.strip()
]

# How often to re-scan Gamma for new/upcoming 15-min markets (seconds).
# 60s is plenty: a new 15-min market appears every 15 min per asset.
BOT_E_MARKET_SCAN_INTERVAL_SEC = float(_env_any(
    ("CRYPTO_RECORDER_MARKET_SCAN_INTERVAL_SEC", "BOT_E_MARKET_SCAN_INTERVAL_SEC"),
    "60",
))

# Heartbeat row cadence (seconds). Per Grok S5: detect silent feed stalls.
BOT_E_HEARTBEAT_INTERVAL_SEC = float(_env_any(
    ("CRYPTO_RECORDER_HEARTBEAT_INTERVAL_SEC", "BOT_E_HEARTBEAT_INTERVAL_SEC"),
    "15",
))

# Max minutes-to-resolution to care about subscribing. Polymarket's 5-minute
# crypto Up/Down markets are discoverable up to ~10 hours ahead of resolution
# (verified empirically 2026-04-16). We want to subscribe well before the
# liquidity-meaningful window so we capture the book from birth. Wider window
# costs more WSS subscriptions but the CPU/DB cost is trivial.
BOT_E_MAX_MINUTES_TO_RES = float(_env_any(
    ("CRYPTO_RECORDER_MAX_MINUTES_TO_RES", "BOT_E_MAX_MINUTES_TO_RES"),
    "120",
))

# Minimum 24h volume to bother capturing (USD). Filters empty/dead markets.
BOT_E_MIN_VOLUME_USD = float(_env_any(
    ("CRYPTO_RECORDER_MIN_VOLUME_USD", "BOT_E_MIN_VOLUME_USD"),
    "50",
))

# Log level
BOT_E_LOG_LEVEL = _env("BOT_E_LOG_LEVEL", "INFO")


def validate() -> list[str]:
    """Return list of validation errors. Empty list == ok.

    Per Grok S5 and v96 pattern: bot refuses to start on invalid config.
    """
    errors: list[str] = []
    if not BOT_E_CEX_SYMBOLS:
        errors.append("BOT_E_CEX_SYMBOLS must not be empty")
    if BOT_E_MARKET_SCAN_INTERVAL_SEC <= 0:
        errors.append("BOT_E_MARKET_SCAN_INTERVAL_SEC must be positive")
    if BOT_E_HEARTBEAT_INTERVAL_SEC <= 0:
        errors.append("BOT_E_HEARTBEAT_INTERVAL_SEC must be positive")
    if BOT_E_MAX_MINUTES_TO_RES <= 0:
        errors.append("BOT_E_MAX_MINUTES_TO_RES must be positive")
    if BOT_E_MIN_VOLUME_USD < 0:
        errors.append("BOT_E_MIN_VOLUME_USD must be non-negative")
    # Ensure DB parent dir exists (create if not)
    try:
        BOT_E_RECORDER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        errors.append(f"Cannot create DB parent dir {BOT_E_RECORDER_DB_PATH.parent}: {exc}")
    return errors
