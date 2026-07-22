"""Configuration for crypto fair-value paper bots."""
from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

LIVE_SECRET_ENV_KEYS = (
    "POLYMARKET_PRIVATE_KEY",
    "PRIVATE_KEY",
    "POLYMARKET_KEYSTORE_PATH",
    "POLYMARKET_KEYSTORE_PASSPHRASE",
    "POLYMARKET_KEYSTORE_PASSPHRASE_FILE",
)


def _env_bool(key: str, default: str) -> bool:
    return os.environ.get(key, default).lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: str) -> int:
    return int(os.environ.get(key, default))


def _env_float(key: str, default: str) -> float:
    return float(os.environ.get(key, default))


def _env_decimal(key: str, default: str) -> Decimal:
    return Decimal(os.environ.get(key, default))


def _env_symbols(key: str, default: str) -> frozenset[str]:
    return frozenset(s.strip().upper() for s in os.environ.get(key, default).split(",") if s.strip())


def _env_durations(key: str, default: str) -> frozenset[int]:
    return frozenset(int(x.strip()) for x in os.environ.get(key, default).split(",") if x.strip())


@dataclass(frozen=True)
class CryptoFairValueConfig:
    bot_id: str
    strategy: str
    execution_style: str
    enabled: bool
    dry_run: bool
    recorder_db_path: Path
    symbols: frozenset[str]
    durations: frozenset[int]
    min_seconds_to_close: int
    max_seconds_to_close_5m: int
    max_seconds_to_close_15m: int
    min_edge: Decimal
    min_model_mid_gap: Decimal
    min_entry_edge: Decimal
    min_price: Decimal
    max_price: Decimal
    max_spread: Decimal
    min_top_depth_usd: Decimal
    stake_usd: Decimal
    max_cex_age_sec: float
    max_book_age_sec: float
    chaos_max_abs_move_60s: float
    brownian_max_abs_move_60s: float
    scan_interval_s: float
    paper_resolve_interval_s: float

    @property
    def event_prefix(self) -> str:
        return "crypto_fair_value"


def load_config(strategy: str) -> CryptoFairValueConfig:
    strategy = strategy.strip().lower()
    if strategy not in {"probability_gap", "brownian_fair_value"}:
        raise ValueError(f"unknown crypto fair-value strategy: {strategy}")

    prefix = "CRYPTO_PROB_GAP" if strategy == "probability_gap" else "CRYPTO_BROWNIAN_FV"
    execution_style = os.environ.get(f"{prefix}_EXECUTION_STYLE", "taker").strip().lower()
    base_bot_id = (
        "crypto_probability_gap_paper"
        if strategy == "probability_gap"
        else "crypto_brownian_fv_paper"
    )
    default_bot_id = base_bot_id if execution_style != "maker" else f"{base_bot_id}_maker"
    return CryptoFairValueConfig(
        bot_id=os.environ.get(f"{prefix}_BOT_ID", default_bot_id),
        strategy=strategy,
        execution_style=execution_style,
        enabled=_env_bool(f"{prefix}_ENABLED", "true"),
        dry_run=_env_bool(f"{prefix}_DRY_RUN", "true"),
        recorder_db_path=Path(
            os.environ.get(
                f"{prefix}_RECORDER_DB_PATH",
                os.environ.get(
                    "BOT_E_RECORDER_DB_PATH",
                    "data/bot_e_recorder.db",
                ),
            )
        ),
        symbols=_env_symbols(f"{prefix}_SYMBOLS", "BTC,ETH,SOL"),
        durations=_env_durations(f"{prefix}_DURATIONS", "5,15"),
        min_seconds_to_close=_env_int(f"{prefix}_MIN_SECONDS_TO_CLOSE", "30"),
        max_seconds_to_close_5m=_env_int(f"{prefix}_MAX_SECONDS_TO_CLOSE_5M", "300"),
        max_seconds_to_close_15m=_env_int(f"{prefix}_MAX_SECONDS_TO_CLOSE_15M", "600"),
        min_edge=_env_decimal(f"{prefix}_MIN_EDGE", "0.07"),
        min_model_mid_gap=_env_decimal(f"{prefix}_MIN_MODEL_MID_GAP", "0.04"),
        min_entry_edge=_env_decimal(f"{prefix}_MIN_ENTRY_EDGE", "0.03"),
        min_price=_env_decimal(f"{prefix}_MIN_PRICE", "0.03"),
        max_price=_env_decimal(f"{prefix}_MAX_PRICE", "0.85"),
        max_spread=_env_decimal(f"{prefix}_MAX_SPREAD", "0.04"),
        min_top_depth_usd=_env_decimal(f"{prefix}_MIN_TOP_DEPTH_USD", "30"),
        stake_usd=_env_decimal(f"{prefix}_STAKE_USD", "5"),
        max_cex_age_sec=_env_float(f"{prefix}_MAX_CEX_AGE_SEC", "2"),
        max_book_age_sec=_env_float(f"{prefix}_MAX_BOOK_AGE_SEC", "5"),
        chaos_max_abs_move_60s=_env_float(f"{prefix}_CHAOS_MAX_ABS_MOVE_60S", "0.015"),
        brownian_max_abs_move_60s=_env_float(
            f"{prefix}_BROWNIAN_MAX_ABS_MOVE_60S", "0.0025"
        ),
        scan_interval_s=_env_float(f"{prefix}_SCAN_INTERVAL_S", "5"),
        paper_resolve_interval_s=_env_float(f"{prefix}_PAPER_RESOLVE_INTERVAL_S", "3600"),
    )


def validate(config: CryptoFairValueConfig) -> list[str]:
    errors: list[str] = []
    global_env = os.environ.get("POLYMARKET_ENV", "paper").lower()
    if global_env == "live" and not config.dry_run:
        errors.append("crypto fair-value bots are paper-only: POLYMARKET_ENV=live with dry-run=false is forbidden")
    if not config.dry_run:
        errors.append("crypto fair-value bots require dry-run=true")
    if config.execution_style not in {"taker", "maker"}:
        errors.append("execution_style must be taker or maker")
    live_secret_keys = [key for key in LIVE_SECRET_ENV_KEYS if os.environ.get(key)]
    if live_secret_keys:
        errors.append(
            "crypto fair-value bots must not request live wallet/keystore settings: "
            + ",".join(live_secret_keys)
        )
    if config.strategy == "probability_gap" and config.bot_id not in {
        "crypto_probability_gap_paper",
        "crypto_probability_gap_paper_maker",
    }:
        errors.append("probability-gap bot_id must be crypto_probability_gap_paper or crypto_probability_gap_paper_maker")
    if config.strategy == "brownian_fair_value" and config.bot_id not in {
        "crypto_brownian_fv_paper",
        "crypto_brownian_fv_paper_maker",
    }:
        errors.append("Brownian FV bot_id must be crypto_brownian_fv_paper or crypto_brownian_fv_paper_maker")
    if not config.symbols or not config.symbols <= {"BTC", "ETH", "SOL"}:
        errors.append("symbols must be a non-empty subset of BTC,ETH,SOL")
    if not config.durations or not config.durations <= {5, 15}:
        errors.append("durations must be a non-empty subset of 5,15")
    if config.min_seconds_to_close < 0:
        errors.append("min seconds to close must be non-negative")
    if config.max_seconds_to_close_5m < config.min_seconds_to_close:
        errors.append("5m max seconds to close must be >= min seconds")
    if config.max_seconds_to_close_15m < config.min_seconds_to_close:
        errors.append("15m max seconds to close must be >= min seconds")
    if config.min_price <= 0 or config.max_price >= 1 or config.min_price > config.max_price:
        errors.append("entry price bounds must satisfy 0 < min <= max < 1")
    if config.max_spread <= 0:
        errors.append("max spread must be positive")
    if config.min_top_depth_usd <= 0:
        errors.append("minimum top depth must be positive")
    if config.stake_usd <= 0:
        errors.append("stake must be positive")
    return errors
