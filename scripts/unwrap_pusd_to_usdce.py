#!/usr/bin/env python3
"""Unwrap pUSD → USDC.e via the Polymarket V2 CollateralOfframp.

Symmetric counterpart to scripts/wrap_usdce_to_pusd.py. Same safety model:
dry run by default, --execute --yes required for real submission.

Two-transaction flow:

  1. pusd.approve(COLLATERAL_OFFRAMP, amount)   # if allowance insufficient
  2. offramp.unwrap(USDC_E, recipient, amount)

The `_asset` arg in unwrap() is the USDC.e address (the target asset the
caller wants back), matching the wrap() signature. 1:1 ratio.

Usage
-----
    python scripts/unwrap_pusd_to_usdce.py --amount-usd 500
    python scripts/unwrap_pusd_to_usdce.py --all --execute --yes
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from core.config import get_settings
from core.keystore import Keystore
from core.polymarket_v2 import (
    COLLATERAL_OFFRAMP,
    POLYGON_CHAIN_ID,
    PUSD_DECIMALS,
    PUSD_TOKEN_PROXY,
    USDC_E,
)


MAX_UINT256 = 2**256 - 1

ERC20_ABI = [
    {"inputs": [{"name": "account", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "owner", "type": "address"},
                {"name": "spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "spender", "type": "address"},
                {"name": "amount", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}],
     "stateMutability": "nonpayable", "type": "function"},
]

OFFRAMP_ABI = [
    {"inputs": [{"name": "_asset", "type": "address"},
                {"name": "_to", "type": "address"},
                {"name": "_amount", "type": "uint256"}],
     "name": "unwrap", "outputs": [],
     "stateMutability": "nonpayable", "type": "function"},
]


def _gas_fees(w3: Web3) -> tuple[int, int]:
    latest = w3.eth.get_block("latest")
    base = latest.get("baseFeePerGas", 0)
    priority = w3.to_wei(50, "gwei")
    max_fee = max(int(base * 2) + priority, w3.to_wei(150, "gwei"))
    max_fee = min(max_fee, w3.to_wei(500, "gwei"))
    return max_fee, priority


def _send_tx(w3: Web3, acct, tx: dict, label: str) -> str:
    signed = acct.sign_transaction(tx)
    h = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"[{label}] tx sent: {h.hex()} — waiting for receipt...")
    rcpt = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    if rcpt.status != 1:
        raise RuntimeError(f"{label} reverted: {h.hex()}")
    print(f"[{label}] mined in block {rcpt.blockNumber}")
    return h.hex()


def _amount_to_wei(amount_usd: Decimal) -> int:
    scaled = amount_usd * Decimal(10) ** PUSD_DECIMALS
    if scaled != scaled.to_integral_value():
        raise ValueError(
            f"amount {amount_usd} has sub-micro precision; pUSD supports {PUSD_DECIMALS} decimals"
        )
    return int(scaled)


def _wei_to_usd_str(wei: int) -> str:
    return f"{Decimal(wei) / Decimal(10) ** PUSD_DECIMALS:.6f}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Unwrap pUSD → USDC.e.")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--amount-usd", type=Decimal,
                       help="Amount of pUSD to unwrap.")
    group.add_argument("--all", action="store_true",
                       help="Unwrap the entire pUSD balance.")
    p.add_argument("--execute", action="store_true",
                   help="Submit real transactions. Default: dry run.")
    p.add_argument("--yes", action="store_true",
                   help="Skip interactive confirmation.")
    p.add_argument("--recipient", default=None,
                   help="USDC.e recipient address. Defaults to signer wallet.")
    p.add_argument("--show-full-address", action="store_true",
                   help="Print full wallet addresses (default masks to 0xABCD…1234).")
    return p.parse_args(argv)


def _fmt_addr(addr: str, show_full: bool) -> str:
    """Mask wallet addresses by default (Codex A-16)."""
    if show_full or not addr:
        return addr
    return f"{addr[:6]}…{addr[-4:]}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    rpc_url = os.environ.get("POLYGON_RPC")
    if not rpc_url:
        print("POLYGON_RPC env var not set.", file=sys.stderr)
        return 2
    try:
        ks = Keystore.load_from_settings(get_settings())
    except Exception as e:
        print(f"keystore load failed: {e}", file=sys.stderr)
        return 3
    acct = ks.signer()
    owner = acct.address
    recipient = args.recipient or owner

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    if w3.eth.chain_id != POLYGON_CHAIN_ID:
        print(f"RPC returned chain_id={w3.eth.chain_id}, expected {POLYGON_CHAIN_ID}",
              file=sys.stderr)
        return 4

    pusd = w3.eth.contract(
        address=Web3.to_checksum_address(PUSD_TOKEN_PROXY), abi=ERC20_ABI
    )
    offramp = w3.eth.contract(
        address=Web3.to_checksum_address(COLLATERAL_OFFRAMP), abi=OFFRAMP_ABI
    )

    balance_wei = pusd.functions.balanceOf(owner).call()
    print(f"[wallet] owner={_fmt_addr(owner, args.show_full_address)}")
    print(f"[wallet] pUSD balance: {_wei_to_usd_str(balance_wei)}")

    if args.all:
        amount_wei = balance_wei
        if amount_wei == 0:
            print("[wallet] zero pUSD balance — nothing to unwrap.")
            return 0
    else:
        amount_wei = _amount_to_wei(args.amount_usd)

    if amount_wei > balance_wei:
        print(f"requested {_wei_to_usd_str(amount_wei)} pUSD but balance is "
              f"{_wei_to_usd_str(balance_wei)}", file=sys.stderr)
        return 5

    current_allow = pusd.functions.allowance(
        owner, Web3.to_checksum_address(COLLATERAL_OFFRAMP)
    ).call()
    print(f"[allowance] offramp allowance: {current_allow}")
    needs_approve = current_allow < amount_wei

    print(f"[plan] unwrap {_wei_to_usd_str(amount_wei)} pUSD → USDC.e "
          f"(recipient={recipient})")
    if needs_approve:
        print("[plan] approve Offramp to spend pUSD (one-time, unlimited)")

    if not args.execute:
        print("\n=== DRY RUN. Re-run with --execute --yes to submit txs. ===")
        return 0

    if not args.yes:
        resp = input(
            f"About to unwrap {_wei_to_usd_str(amount_wei)} pUSD on-chain. "
            "Type 'yes' to proceed: "
        ).strip().lower()
        if resp != "yes":
            print("aborted.")
            return 1

    nonce = w3.eth.get_transaction_count(owner)
    max_fee, priority = _gas_fees(w3)

    if needs_approve:
        tx = pusd.functions.approve(
            Web3.to_checksum_address(COLLATERAL_OFFRAMP), MAX_UINT256
        ).build_transaction({
            "from": owner, "nonce": nonce, "chainId": POLYGON_CHAIN_ID,
            "gas": 80_000, "maxFeePerGas": max_fee, "maxPriorityFeePerGas": priority,
        })
        _send_tx(w3, acct, tx, "approve-offramp")
        nonce += 1

    tx = offramp.functions.unwrap(
        Web3.to_checksum_address(USDC_E),
        Web3.to_checksum_address(recipient),
        amount_wei,
    ).build_transaction({
        "from": owner, "nonce": nonce, "chainId": POLYGON_CHAIN_ID,
        "gas": 300_000, "maxFeePerGas": max_fee, "maxPriorityFeePerGas": priority,
    })
    _send_tx(w3, acct, tx, "unwrap-pusd")

    usdce = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E), abi=ERC20_ABI
    )
    usdce_balance = usdce.functions.balanceOf(recipient).call()
    print(f"[done] USDC.e balance on {recipient}: "
          f"{Decimal(usdce_balance) / Decimal(10) ** 6:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
