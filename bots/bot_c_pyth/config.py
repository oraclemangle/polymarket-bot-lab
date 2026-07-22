"""Bot C configuration. Reads env via python-dotenv; matches repo convention."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from core.pyth_feeds import Feed, FEEDS, active_feeds


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "bot_c_pyth.db"
ENV_PATH = REPO_ROOT / ".env"

# Load .env once on import. override=False so real env wins.
load_dotenv(ENV_PATH, override=False)


@dataclass(frozen=True)
class BotCConfig:
    pyth_token: str | None
    endpoint: str
    db_path: Path
    include_pro: bool
    include_hermes: bool
    feeds: list[Feed]
    # Bot-C-scoped trading mode. Independent of the global POLYMARKET_ENV
    # so Bot C can run paper while Bot A/B are live (or vice versa).
    # Values: "paper" (default, safe) | "live". Reads BOT_C_ENV from env.
    trading_mode: str = "paper"


def _parse_symbols(csv: str | None) -> list[Feed]:
    if not csv:
        return active_feeds()
    out: list[Feed] = []
    for sym in (s.strip().upper() for s in csv.split(",") if s.strip()):
        feed = FEEDS.get(sym)
        if feed is None:
            raise ValueError(f"unknown symbol {sym!r}; see core/pyth_feeds.py")
        if feed.id is None:
            raise ValueError(f"symbol {sym!r} has no resolved Pyth id yet (TODO)")
        out.append(feed)
    return out


def load_config(
    *,
    endpoint: str | None = None,
    symbols: str | None = None,
    db_path: str | None = None,
) -> BotCConfig:
    selected_endpoint = endpoint or os.getenv("BOT_C_ENDPOINT", "both")
    selected_endpoint = selected_endpoint.strip().lower()
    if selected_endpoint not in ("both", "pro", "hermes"):
        raise ValueError(
            f"endpoint must be both|pro|hermes, got {selected_endpoint!r}"
        )
    # Prefer the centralized Settings surface so SecretStr protection
    # and .env loading are consistent (audit C21). Fall back to raw env
    # for operators running Bot C in isolation without the full stack.
    try:
        from core.config import get_settings
        secret = get_settings().pyth_token.get_secret_value()
        token = secret or os.getenv("PYTH_TOKEN") or None
    except Exception:
        token = os.getenv("PYTH_TOKEN") or None
    trading_mode = os.getenv("BOT_C_ENV", "paper").strip().lower()
    if trading_mode not in ("paper", "live"):
        raise ValueError(
            f"BOT_C_ENV must be paper|live, got {trading_mode!r}"
        )
    return BotCConfig(
        pyth_token=token,
        endpoint=selected_endpoint,
        db_path=Path(db_path) if db_path else DEFAULT_DB_PATH,
        include_pro=selected_endpoint in ("both", "pro"),
        include_hermes=selected_endpoint in ("both", "hermes"),
        feeds=_parse_symbols(symbols),
        trading_mode=trading_mode,
    )
