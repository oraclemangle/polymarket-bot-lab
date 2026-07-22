"""Shared paths for large external research datasets.

The Becker dataset already lives on the bot container's external mount. Research scripts
should not default to re-downloading or assuming a Mac-local copy exists.
"""
from __future__ import annotations

import os
from pathlib import Path

bot_host_EXTERNAL_ROOT = Path("data/external")
MAC_EXTERNAL_ROOT = Path("/home/operator/Data/longshot-research/external")

bot_host_BECKER_DATA = bot_host_EXTERNAL_ROOT / "prediction-market-analysis" / "repo" / "data"
MAC_BECKER_DATA = MAC_EXTERNAL_ROOT / "prediction-market-analysis" / "repo" / "data"

bot_host_BINANCE_KLINES_1M = bot_host_EXTERNAL_ROOT / "cex" / "binance" / "klines" / "1m"
MAC_BINANCE_KLINES_1M = MAC_EXTERNAL_ROOT / "cex" / "binance" / "klines" / "1m"


def _first_existing(env_name: str, candidates: tuple[Path, ...]) -> Path:
    env_value = os.getenv(env_name)
    if env_value:
        return Path(env_value).expanduser()
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def default_becker_data_dir() -> Path:
    """Return the preferred Becker Parquet data directory."""
    return _first_existing("BECKER_DATA_DIR", (bot_host_BECKER_DATA, MAC_BECKER_DATA))


def default_binance_klines_1m_dir() -> Path:
    """Return the preferred Binance 1m kline directory used with Becker reports."""
    return _first_existing(
        "BINANCE_KLINES_1M_DIR",
        (bot_host_BINANCE_KLINES_1M, MAC_BINANCE_KLINES_1M),
    )

