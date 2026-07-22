"""Environment + global-constants loader.

Single source of truth for runtime config. All other modules import `settings`
rather than reading env vars directly.
"""

from __future__ import annotations

import os
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Literal


def _default_passphrase_path() -> Path:
    """Resolve the runtime passphrase path against the current UID.

    SECURITY_AUDIT.md M-4: hardcoding /run/user/1000 broke deployments
    where the bot runs as a different user (e.g. the bot host uses bot=999).
    Falls back to the legacy 1000 path on systems without getuid (Windows).
    """
    try:
        uid = os.getuid()
    except AttributeError:
        uid = 1000
    return Path(f"/run/user/{uid}/polymarket/passphrase")

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RunMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    """Runtime settings loaded from env / .env file.

    Secrets (keys, passphrases, tokens) are loaded here but never logged —
    Pydantic's repr suppression is enforced via `SecretStr` on sensitive fields.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Secrets ---
    polymarket_keystore_path: Path = Path("~/.config/polymarket-bot/keystore.age").expanduser()
    polymarket_passphrase_path: Path = Field(default_factory=_default_passphrase_path)
    google_api_key: SecretStr = SecretStr("")
    groq_api_key: SecretStr = SecretStr("")
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id_allowlist: str = ""  # not a secret — it's an allowlist of chat IDs
    # Audit C21: centralise PYTH_TOKEN so it lives in Settings not ad-hoc env reads.
    pyth_token: SecretStr = SecretStr("")

    # --- Deploy config ---
    polymarket_env: RunMode = RunMode.PAPER
    polymarket_db_path: Path = Path("./data/main.db")
    polymarket_log_level: str = "INFO"

    bot_a_bankroll_gbp: Decimal = Decimal("1000")
    bot_b_bankroll_gbp: Decimal = Decimal("1000")
    bot_a_drawdown_kill_pct: Decimal = Decimal("15")
    bot_b_drawdown_kill_pct: Decimal = Decimal("15")
    aggregate_drawdown_kill_pct: Decimal = Decimal("20")
    max_aggregate_exposure_usd: Decimal = Decimal("2000")
    # 2026-04-17: split aggregate caps by mode so paper trading can never
    # halt live bots (and vice versa). Live cap stays tight to protect real
    # capital; paper cap is large to let validation data accumulate freely.
    # The legacy `max_aggregate_exposure_usd` is kept for backward compat
    # but is no longer consulted by the watchdog.
    max_aggregate_exposure_usd_live: Decimal = Decimal("500")
    max_aggregate_exposure_usd_paper: Decimal = Decimal("50000")

    # --- Chain ---
    # 2026-04-29: polygon-rpc.com started returning 401 in production. Use
    # the same public Polygon endpoint as the V2 on-chain maintenance scripts.
    polygon_rpc_url: str = "https://polygon-bor.publicnode.com"
    chain_id: int = 137
    polymarket_host: str = "https://clob.polymarket.com"
    polymarket_gamma_host: str = "https://gamma-api.polymarket.com"
    polymarket_wss_host: str = "wss://ws-subscriptions-clob.polymarket.com"

    # --- Polymarket V2 builder attribution (cutover 2026-04-28) ---
    # bytes32-encoded builderCode obtained from polymarket.com's settings UI.
    # When empty, ``ClobWrapperV2`` substitutes ``BYTES32_ZERO``; orders
    # still post but without builder-fee attribution. Operator-only secret
    # to set; do not commit to repo.
    polymarket_builder_code: str = ""
    # Optional V2 order-signing mode. Leave unset for a standalone EOA.
    # Polymarket.com accounts usually hold funds in a proxy wallet and need
    # POLYMARKET_SIGNATURE_TYPE plus POLYMARKET_FUNDER_ADDRESS at runtime.
    polymarket_signature_type: int | None = None
    polymarket_funder_address: str = ""

    # --- Amoy testnet ---
    amoy_rpc_url: str = "https://rpc-amoy.polygon.technology"
    amoy_chain_id: int = 80002


    @field_validator(
        "bot_a_drawdown_kill_pct",
        "bot_b_drawdown_kill_pct",
        "aggregate_drawdown_kill_pct",
    )
    @classmethod
    def _validate_pct(cls, v: Decimal) -> Decimal:
        if not (Decimal("0") < v <= Decimal("100")):
            raise ValueError(f"drawdown pct must be in (0, 100], got {v}")
        return v

    @field_validator("chain_id", "amoy_chain_id")
    @classmethod
    def _validate_chain(cls, v: int) -> int:
        if v not in (137, 80002):
            raise ValueError(f"chain_id must be 137 (polygon) or 80002 (amoy), got {v}")
        return v

    @field_validator("polymarket_signature_type")
    @classmethod
    def _validate_signature_type(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v not in (0, 1, 2, 3):
            raise ValueError(f"polymarket_signature_type must be one of 0, 1, 2, 3; got {v}")
        return v

    def is_live(self) -> bool:
        return self.polymarket_env == RunMode.LIVE

    def allowed_chat_ids(self) -> list[int]:
        raw = self.telegram_chat_id_allowlist.strip()
        if not raw:
            return []
        return [int(x.strip()) for x in raw.split(",") if x.strip()]


# --- Polymarket contract addresses ---
# VERIFIED 2026-04-15 against py_clob_client/config.py in the pinned version.
# (Resolves OQ-007.) If the pinned py-clob-client version changes, re-verify.
#
# Polygon mainnet (chain_id=137):
CTF_EXCHANGE_ADDRESS: Literal["0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"] = (
    "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
)
NEG_RISK_CTF_EXCHANGE_ADDRESS: Literal["0xC5d563A36AE78145C45a50134d48A1215220f80a"] = (
    "0xC5d563A36AE78145C45a50134d48A1215220f80a"
)
CONDITIONAL_TOKENS_ADDRESS: Literal["0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"] = (
    "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
)

# Collateral on Polygon mainnet = USDC.e per py-clob-client (OQ-008 resolved).
# Native USDC (0x3c499c...) is NOT used by Polymarket; do not approve it.
USDC_E_ADDRESS: Literal["0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"] = (
    "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
)

# Amoy testnet (chain_id=80002):
AMOY_CTF_EXCHANGE_ADDRESS: Literal["0xF00D000000000000000000000000000000000011"] = (
    "0xF00D000000000000000000000000000000000011"
)
AMOY_NEG_RISK_CTF_EXCHANGE_ADDRESS: Literal["0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"] = (
    "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
)
AMOY_COLLATERAL_ADDRESS: Literal["0xF00D000000000000000000000000000000000012"] = (
    "0xF00D000000000000000000000000000000000012"
)
AMOY_CONDITIONAL_TOKENS_ADDRESS: Literal["0xF00D000000000000000000000000000000000013"] = (
    "0xF00D000000000000000000000000000000000013"
)

# Rate limits (per research/clob-spec.md §3.4) — local token bucket runs at 80% of these.
RATE_LIMIT_GENERAL_PER_10S = 9000
RATE_LIMIT_POST_ORDER_PER_10S = 3500
RATE_LIMIT_POST_ORDER_PER_10M = 36000

# Derived from `core/fees.py::TAKER_FEE_RATE_BY_CATEGORY` to avoid the
# duplicate-dict-drift bug flagged by GLM-5.1 review A8 / Codex C1.
# Stored as integer-bps (baseRate × 10000) so downstream consumers that
# expect `fee_rate_bps` on Market rows get a stable-scale value.
# "other" stays as a literal fallback (no entry in the canonical map).
def _derive_fee_rate_bps() -> dict[str, int]:
    from core.fees import TAKER_FEE_RATE_BY_CATEGORY
    out = {
        cat: int(rate * 10000)
        for cat, rate in TAKER_FEE_RATE_BY_CATEGORY.items()
    }
    out.setdefault("other", 500)  # 5% baseRate fallback (peak 1.25%)
    return out


FEE_RATE_BY_CATEGORY_BPS = _derive_fee_rate_bps()


# Singleton — imported by everything else.
# Constructed lazily so tests can override env before it's built.
_settings_instance: Settings | None = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reset_settings() -> None:
    """Test helper.  Forces next `get_settings()` call to re-read env."""
    global _settings_instance
    _settings_instance = None


# Convenience at module level for most callers.
settings = get_settings()
