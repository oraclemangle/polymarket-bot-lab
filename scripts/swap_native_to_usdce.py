#!/usr/bin/env python3
"""Swap native USDC -> USDC.e on Polygon via Uniswap V3.

Purpose
-------
Coinbase withdraws Polygon-native USDC (0x3c49...3359). Polymarket settles
in USDC.e (0x2791...4174). This script routes the swap through Uniswap V3's
0.01%-fee USDC/USDC.e pool (the canonical tight-peg pool, usually ≤1 bp
slippage for sub-$1k size).

Safety
------
- Default mode is --simulate (runs eth_call against the router; no tx sent).
- --execute sends the real transactions (approve + swap). Requires explicit
  user confirmation at the prompt.
- Decrypts the keystore into memory via core.keystore.Keystore, never
  writes the key to disk, never logs it.
- Slippage guard: amountOutMinimum = input * (1 - slippage_bps / 10_000).
- Aborts if wallet lacks native USDC, if POL gas float is below threshold,
  or if pool liquidity sanity check fails.

Usage
-----
    # Dry run (safe, always do this first):
    python scripts/swap_native_to_usdce.py --amount 119.5

    # Real send, after review:
    python scripts/swap_native_to_usdce.py --amount 119.5 --execute

    # Override slippage (default 50 bps = 0.5%, conservative for $120):
    python scripts/swap_native_to_usdce.py --amount 119.5 --slippage-bps 20 --execute
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

from web3 import Web3
from web3.exceptions import ContractLogicError
from web3.middleware import ExtraDataToPOAMiddleware

from core.keystore import Keystore, KeystoreError

# ---------------------------------------------------------------------------
# Polygon mainnet contract addresses (from core/config.py where available).
# ---------------------------------------------------------------------------

POLYGON_CHAIN_ID = 137

USDC_NATIVE = Web3.to_checksum_address("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359")
USDC_E = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")

# Uniswap V3 SwapRouter (v1) — exactInputSingle with deadline.
UNISWAP_V3_ROUTER = Web3.to_checksum_address("0xE592427A0AEce92De3Edee1F18E0157C05861564")

# Uniswap V3 Quoter V2 — lets us price the swap via eth_call without needing
# an allowance. The main router's exactInputSingle requires transferFrom,
# which reverts under eth_call if allowance is 0.
UNISWAP_V3_QUOTER_V2 = Web3.to_checksum_address("0xF00D00000000000000000000000000000000001c")

# USDC / USDC.e 0.01%-fee pool. Discovered via Uniswap V3 factory; hardcoded
# to fail loudly if the constant ever drifts.
UNISWAP_V3_USDC_USDCE_POOL = Web3.to_checksum_address("0xF00D00000000000000000000000000000000001d")

POOL_FEE_1BPS = 100  # fee tier in hundredths of a bip (100 = 0.01%)

USDC_DECIMALS = 6  # both USDC and USDC.e are 6dp on Polygon

# Minimum POL we require on the wallet before sending txs (gas safety).
MIN_POL_FLOAT = Decimal("0.5")

# ---------------------------------------------------------------------------
# Minimal ABIs (only the functions we call).
# ---------------------------------------------------------------------------

ERC20_ABI = [
    {"inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf",
     "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}],
     "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
]

SWAP_ROUTER_ABI = [
    {
        "inputs": [{
            "components": [
                {"name": "tokenIn", "type": "address"},
                {"name": "tokenOut", "type": "address"},
                {"name": "fee", "type": "uint24"},
                {"name": "recipient", "type": "address"},
                {"name": "deadline", "type": "uint256"},
                {"name": "amountIn", "type": "uint256"},
                {"name": "amountOutMinimum", "type": "uint256"},
                {"name": "sqrtPriceLimitX96", "type": "uint160"},
            ],
            "name": "params", "type": "tuple",
        }],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable", "type": "function",
    }
]

QUOTER_V2_ABI = [
    {
        "inputs": [{
            "components": [
                {"name": "tokenIn", "type": "address"},
                {"name": "tokenOut", "type": "address"},
                {"name": "amountIn", "type": "uint256"},
                {"name": "fee", "type": "uint24"},
                {"name": "sqrtPriceLimitX96", "type": "uint160"},
            ],
            "name": "params", "type": "tuple",
        }],
        "name": "quoteExactInputSingle",
        "outputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "sqrtPriceX96After", "type": "uint160"},
            {"name": "initializedTicksCrossed", "type": "uint32"},
            {"name": "gasEstimate", "type": "uint256"},
        ],
        "stateMutability": "nonpayable", "type": "function",
    }
]

POOL_ABI = [
    {"inputs": [], "name": "liquidity",
     "outputs": [{"name": "", "type": "uint128"}], "stateMutability": "view", "type": "function"},
    {"inputs": [], "name": "slot0",
     "outputs": [
         {"name": "sqrtPriceX96", "type": "uint160"},
         {"name": "tick", "type": "int24"},
         {"name": "observationIndex", "type": "uint16"},
         {"name": "observationCardinality", "type": "uint16"},
         {"name": "observationCardinalityNext", "type": "uint16"},
         {"name": "feeProtocol", "type": "uint8"},
         {"name": "unlocked", "type": "bool"},
     ],
     "stateMutability": "view", "type": "function"},
]


def to_units(amount: Decimal, decimals: int = USDC_DECIMALS) -> int:
    return int(amount * (Decimal(10) ** decimals))


def from_units(raw: int, decimals: int = USDC_DECIMALS) -> Decimal:
    return Decimal(raw) / (Decimal(10) ** decimals)


def preflight(w3: Web3, owner: str, amount_in: int) -> None:
    """Sanity-check chain id, balances, pool liquidity. Raises on failure."""
    cid = w3.eth.chain_id
    if cid != POLYGON_CHAIN_ID:
        raise RuntimeError(f"wrong chain: expected {POLYGON_CHAIN_ID}, got {cid}")

    pol = Decimal(w3.eth.get_balance(owner)) / Decimal(10**18)
    if pol < MIN_POL_FLOAT:
        raise RuntimeError(f"POL balance {pol} below safety floor {MIN_POL_FLOAT}")
    print(f"[preflight] POL gas float: {pol:.4f}")

    usdc = w3.eth.contract(address=USDC_NATIVE, abi=ERC20_ABI)
    bal = usdc.functions.balanceOf(owner).call()
    if bal < amount_in:
        raise RuntimeError(
            f"native USDC balance {from_units(bal)} < amount_in {from_units(amount_in)}"
        )
    print(f"[preflight] native USDC balance: {from_units(bal)}")

    pool = w3.eth.contract(address=UNISWAP_V3_USDC_USDCE_POOL, abi=POOL_ABI)
    liq = pool.functions.liquidity().call()
    if liq == 0:
        raise RuntimeError("pool liquidity is zero — aborting")
    print(f"[preflight] pool liquidity (raw): {liq:,}")


def build_swap_params(owner: str, amount_in: int, amount_out_min: int, deadline: int) -> dict:
    return {
        "tokenIn": USDC_NATIVE,
        "tokenOut": USDC_E,
        "fee": POOL_FEE_1BPS,
        "recipient": owner,
        "deadline": deadline,
        "amountIn": amount_in,
        "amountOutMinimum": amount_out_min,
        "sqrtPriceLimitX96": 0,
    }


def simulate_swap(w3: Web3, owner: str, amount_in: int, slippage_bps: int) -> int:
    """Quote the swap via Uniswap V3 QuoterV2. Returns expected amountOut.

    The main SwapRouter cannot be simulated without a pre-existing allowance
    (eth_call of exactInputSingle reverts with 'STF' when allowance is 0).
    The Quoter is purpose-built for this — it reads pool state without
    moving tokens.
    """
    quoter = w3.eth.contract(address=UNISWAP_V3_QUOTER_V2, abi=QUOTER_V2_ABI)
    params = {
        "tokenIn": USDC_NATIVE,
        "tokenOut": USDC_E,
        "amountIn": amount_in,
        "fee": POOL_FEE_1BPS,
        "sqrtPriceLimitX96": 0,
    }
    try:
        out, _, _, gas_est = quoter.functions.quoteExactInputSingle(params).call({"from": owner})
    except ContractLogicError as e:
        raise RuntimeError(f"quoter reverted: {e}") from e
    guard = int(amount_in * (10_000 - slippage_bps) / 10_000)
    print(f"[simulate] quoted output: {from_units(out)} USDC.e (gas est ≈ {gas_est:,})")
    print(f"[simulate] slippage guard (amountOutMinimum @ {slippage_bps}bps): {from_units(guard)} USDC.e")
    if out < guard:
        raise RuntimeError(
            f"expected output {from_units(out)} below slippage guard {from_units(guard)} — "
            f"pool may be imbalanced or size too large; consider smaller amount or higher --slippage-bps"
        )
    return out


def _gas_fees(w3: Web3) -> tuple[int, int]:
    """Compute EIP-1559 fees as (maxFeePerGas, maxPriorityFeePerGas) in wei.

    Polygon base fee can spike; we use 2x base + 50 gwei priority, capped to
    sane upper bounds. Always prints the chosen values for audit.
    """
    latest = w3.eth.get_block("latest")
    base = latest.get("baseFeePerGas", 0)
    priority = w3.to_wei(50, "gwei")
    max_fee = max(int(base * 2) + priority, w3.to_wei(150, "gwei"))
    # Safety cap: never pay more than 500 gwei total.
    max_fee = min(max_fee, w3.to_wei(500, "gwei"))
    print(f"[gas] base={base/1e9:.1f}gwei  -> maxFee={max_fee/1e9:.1f}gwei  priority={priority/1e9:.1f}gwei")
    return max_fee, priority


def ensure_allowance(w3: Web3, acct, owner: str, amount_in: int, execute: bool) -> int:
    """Returns the nonce that was consumed (or the next unused nonce if skipped)."""
    usdc = w3.eth.contract(address=USDC_NATIVE, abi=ERC20_ABI)
    current = usdc.functions.allowance(owner, UNISWAP_V3_ROUTER).call()
    start_nonce = w3.eth.get_transaction_count(owner, "latest")
    if current >= amount_in:
        print(f"[approve] allowance already sufficient ({from_units(current)})")
        return start_nonce
    print(f"[approve] need approve({from_units(amount_in)}) to router; current={from_units(current)}")
    if not execute:
        print("[approve] SKIPPED (dry run)")
        return start_nonce
    max_fee, priority = _gas_fees(w3)
    tx = usdc.functions.approve(UNISWAP_V3_ROUTER, amount_in).build_transaction({
        "from": owner,
        "nonce": start_nonce,
        "chainId": POLYGON_CHAIN_ID,
        "gas": 80_000,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": priority,
    })
    signed = acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"[approve] tx sent: {h.hex()}  — waiting for receipt...")
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    if rcpt.status != 1:
        raise RuntimeError(f"approve tx reverted: {h.hex()}")
    print(f"[approve] mined in block {rcpt.blockNumber}")
    return start_nonce + 1


def send_swap(w3: Web3, acct, owner: str, amount_in: int, amount_out_min: int, nonce: int) -> str:
    router = w3.eth.contract(address=UNISWAP_V3_ROUTER, abi=SWAP_ROUTER_ABI)
    deadline = int(time.time()) + 600
    params = build_swap_params(owner, amount_in, amount_out_min, deadline)
    max_fee, priority = _gas_fees(w3)
    tx = router.functions.exactInputSingle(params).build_transaction({
        "from": owner,
        "nonce": nonce,
        "chainId": POLYGON_CHAIN_ID,
        "gas": 250_000,
        "maxFeePerGas": max_fee,
        "maxPriorityFeePerGas": priority,
        "value": 0,
    })
    signed = acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"[swap] tx sent: {h.hex()}  — waiting for receipt...")
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    if rcpt.status != 1:
        raise RuntimeError(f"swap tx reverted: {h.hex()}")
    print(f"[swap] mined in block {rcpt.blockNumber}")
    return h.hex()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--amount", type=Decimal, required=True,
                   help="Amount of native USDC to swap (human units, e.g. 119.5)")
    p.add_argument("--slippage-bps", type=int, default=50,
                   help="Slippage tolerance in basis points (default 50 = 0.5%%)")
    p.add_argument("--execute", action="store_true",
                   help="Actually send transactions (default: simulate only)")
    p.add_argument("--yes", action="store_true",
                   help="Skip the interactive SEND prompt (for non-TTY contexts)")
    p.add_argument("--rpc", default=os.environ.get("POLYGON_RPC", "https://polygon-bor.publicnode.com"),
                   help="Polygon RPC URL")
    p.add_argument("--keystore", default=os.environ.get("POLYMARKET_KEYSTORE_PATH",
                                                        "~/.config/polymarket-bot/keystore.age"))
    p.add_argument("--passphrase", default=os.environ.get("POLYMARKET_PASSPHRASE_PATH",
                                                          "/run/user/999/polymarket/passphrase"))
    args = p.parse_args(argv)

    if args.amount <= 0 or args.amount > Decimal("2000"):
        print(f"error: amount {args.amount} out of sane range (0, 2000]", file=sys.stderr)
        return 2
    if not (0 < args.slippage_bps <= 500):
        print(f"error: slippage-bps {args.slippage_bps} out of range (0, 500]", file=sys.stderr)
        return 2

    amount_in = to_units(args.amount)
    w3 = Web3(Web3.HTTPProvider(args.rpc))
    # Polygon is a PoA chain; its extraData field is longer than 32 bytes,
    # which web3.py's default formatter rejects.
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if not w3.is_connected():
        print(f"error: cannot reach RPC {args.rpc}", file=sys.stderr)
        return 2

    print(f"[init] mode: {'EXECUTE' if args.execute else 'SIMULATE'}")
    print(f"[init] amount: {args.amount} native USDC ({amount_in} units)")
    print(f"[init] slippage: {args.slippage_bps} bps")
    print(f"[init] RPC: {args.rpc}")

    try:
        ks = Keystore.load(Path(args.keystore).expanduser(), Path(args.passphrase).expanduser())
    except KeystoreError as e:
        print(f"error: keystore load failed: {e}", file=sys.stderr)
        return 2

    try:
        owner = ks.address
        print(f"[init] wallet: {owner}")
        acct = ks.signer()

        preflight(w3, owner, amount_in)
        expected_out = simulate_swap(w3, owner, amount_in, args.slippage_bps)
        amount_out_min = int(amount_in * (10_000 - args.slippage_bps) / 10_000)

        if not args.execute:
            print("\n[done] Simulation OK. Re-run with --execute to send the real transactions.")
            return 0

        print("\n" + "=" * 60)
        print("ABOUT TO SEND REAL TRANSACTIONS on Polygon mainnet:")
        print(f"  - approve {args.amount} USDC to Uniswap router (if needed)")
        print(f"  - swap {args.amount} USDC -> >= {from_units(amount_out_min)} USDC.e")
        print(f"  - recipient: {owner}")
        print("=" * 60)
        if args.yes:
            print("[--yes] skipping interactive confirmation")
        else:
            confirm = input("Type 'SEND' to proceed, anything else aborts: ").strip()
            if confirm != "SEND":
                print("aborted")
                return 1

        next_nonce = ensure_allowance(w3, acct, owner, amount_in, execute=True)
        tx_hash = send_swap(w3, acct, owner, amount_in, amount_out_min, next_nonce)

        usdce = w3.eth.contract(address=USDC_E, abi=ERC20_ABI)
        final_bal = usdce.functions.balanceOf(owner).call()
        print(f"\n[done] USDC.e balance after swap: {from_units(final_bal)}")
        print(f"[done] swap tx: https://polygonscan.com/tx/{tx_hash}")
        print(f"[done] expected ≈ {from_units(expected_out)} USDC.e (slippage floor: {from_units(amount_out_min)})")
        return 0
    finally:
        ks.close()


if __name__ == "__main__":
    sys.exit(main())
