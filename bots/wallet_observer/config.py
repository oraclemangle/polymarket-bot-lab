"""Wallet observer configuration."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

WALLET_OBSERVER_BOT_ID = os.getenv("WALLET_OBSERVER_BOT_ID", "wallet_observer")

# Source of truth: the WANGZJ retail-tier mining cross-reference (Session 212)
WHITELIST_CSV = Path(os.getenv(
    "WALLET_OBSERVER_WHITELIST_CSV",
    str(REPO_ROOT / "data" / "retail_wallets_xref_2026-05-07.csv"),
))

# Tiers to include in the observation set. Default: A + B.
# Tier A = profitable + PolyVerify-confirmed human + ≥100 trades (97 wallets)
# Tier B = profitable + outside PolyVerify top-1000 + ≥100 trades + ≥20% ROI (148 wallets)
INCLUDED_TIERS = {
    t.strip()
    for t in os.getenv(
        "WALLET_OBSERVER_TIERS",
        "A_human_profitable,B_unknown_profitable",
    ).split(",")
    if t.strip()
}

# Polymarket V2 exchange contract addresses (deployed Apr 28 2026).
# V1 addresses (0x4bFb41d5..., 0xC5d563A3...) are deprecated; V2 carries
# all current trade flow. Verified live 2026-05-07: V2 sees ~22K events/hr
# vs ~0 OrderFilled on V1.
CTF_EXCHANGE_ADDRESS = "0xE111180000d2663C0091e4f400237545B87B996B"
NEG_RISK_CTF_EXCHANGE_ADDRESS = "0xe2222d279d744050d28e00520010520000310F59"

# V2 OrderFilled event signature (per Blockscout ABI 2026-05-07):
# event OrderFilled(
#     bytes32 indexed orderHash,
#     address indexed maker,
#     address indexed taker,
#     uint8 side,                    // 0=BUY, 1=SELL (from MAKER's perspective)
#     uint256 tokenId,               // the share token ID
#     uint256 makerAmountFilled,     // amount maker provided (6-decimal)
#     uint256 takerAmountFilled,     // amount taker provided (6-decimal)
#     uint256 fee,                   // fee amount (6-decimal)
#     bytes32 builder,               // builder code attribution
#     bytes32 metadata               // V2 metadata
# )
ORDER_FILLED_TOPIC0 = (
    "0xF00D00000000000000000000000000000000000562980ba90b1a89f2ea84d8ee"
)

# V2 collateral and shares both use 6 decimals (USDC standard).
V2_DECIMALS = 6
V2_SCALE = 10 ** V2_DECIMALS

# Polygon RPC. Defaults to public node. Override for production via
# WALLET_OBSERVER_POLYGON_RPC_URL or POLYGON_RPC_URL env vars.
POLYGON_RPC_URL = (
    os.getenv("WALLET_OBSERVER_POLYGON_RPC_URL")
    or os.getenv("POLYGON_RPC_URL")
    or "https://polygon-bor.publicnode.com"
)

# Poll cadence. Polygon block time ~2s. 30s = ~15-block lag (acceptable
# for forward observation; sub-second isn't needed since we don't trade).
POLL_INTERVAL_S = float(os.getenv("WALLET_OBSERVER_POLL_INTERVAL_S", "30"))

# Lookback when first starting. 1000 blocks ≈ 33 minutes.
INITIAL_LOOKBACK_BLOCKS = int(os.getenv("WALLET_OBSERVER_LOOKBACK_BLOCKS", "1000"))

# Per-poll block range cap (avoid hammering RPC).
MAX_BLOCK_RANGE_PER_POLL = int(os.getenv("WALLET_OBSERVER_MAX_RANGE", "2000"))

# Public Polygon RPCs can briefly expose logs before block headers are
# available. Stay a few blocks behind the tip so log and timestamp reads are
# consistent.
FINALITY_LAG_BLOCKS = int(os.getenv("WALLET_OBSERVER_FINALITY_LAG_BLOCKS", "10"))

# Database. Separate from main.db per Bot E recorder pattern (write-heavy
# event capture must not contend with strategy services).
WALLET_OBSERVER_DB = Path(os.getenv(
    "WALLET_OBSERVER_DB",
    str(REPO_ROOT / "data" / "wallet_observer.db"),
))

# State file: tracks last processed block so the observer is resumable.
WALLET_OBSERVER_STATE = Path(os.getenv(
    "WALLET_OBSERVER_STATE",
    str(REPO_ROOT / "data" / "wallet_observer_state.json"),
))

# Halt flag — observer continues to scan but stops writing.
ENTRY_HALT = os.getenv("WALLET_OBSERVER_HALT", "false").strip().lower() in {
    "1", "true", "yes", "on",
}
