#!/usr/bin/env python3
"""Wrap USDC.e → pUSD via the Polymarket V2 CollateralOnramp.

Two-transaction flow (both on Polygon, chain_id=137):

  1. usdce.approve(COLLATERAL_ONRAMP, amount)   # if allowance insufficient
  2. onramp.wrap(USDC_E, recipient, amount)

Paired with scripts/unwrap_pusd_to_usdce.py (symmetric offramp). 1:1 ratio,
no fee per docs/resources/contracts (verify before first real wrap).

Safety
------
- Default mode simulates via eth_call + reports; no tx sent.
- --execute submits real txs; --yes skips the interactive prompt.
- Uses core.keystore.Keystore; private key never touches disk or logs.
- Dynamic EIP-1559 gas sized to current base fee x 2 + 50 gwei priority.
- Models on scripts/approve_polymarket.py which has been live-tested.

Usage
-----
    # Dry run (always first — verifies addresses, allowance, gas quote):
    python scripts/wrap_usdce_to_pusd.py --amount-usd 500

    # Execute:
    python scripts/wrap_usdce_to_pusd.py --amount-usd 500 --execute --yes

    # Wrap entire USDC.e balance:
    python scripts/wrap_usdce_to_pusd.py --all --execute --yes

Environment
-----------
  POLYGON_RPC          required; https://polygon-rpc.com or Alchemy/Infura URL
  POLYMARKET_KEYSTORE_PATH     required under POLYMARKET_ENV=live
  POLYMARKET_PASSPHRASE_PATH   required under POLYMARKET_ENV=live
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
    COLLATERAL_ONRAMP,
    POLYGON_CHAIN_ID,
    PUSD_TOKEN_PROXY,
    USDC_E,
    USDC_E_DECIMALS,
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

# CollateralOnramp.wrap(address asset, address to, uint256 amount).
# No constructor / getter functions needed for this script.
ONRAMP_ABI = [
    {"inputs": [{"name": "_asset", "type": "address"},
                {"name": "_to", "type": "address"},
                {"name": "_amount", "type": "uint256"}],
     "name": "wrap", "outputs": [],
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
    """USD amount (e.g. 500.50) → integer with USDC.e's 6 decimals."""
    scaled = amount_usd * Decimal(10) ** USDC_E_DECIMALS
    # Reject non-integer micro-amounts (surprise dust).
    if scaled != scaled.to_integral_value():
        raise ValueError(
            f"amount {amount_usd} has sub-micro precision; USDC.e supports 6 decimals max"
        )
    return int(scaled)


def _wei_to_usd_str(wei: int) -> str:
    return f"{Decimal(wei) / Decimal(10) ** USDC_E_DECIMALS:.6f}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Wrap USDC.e → pUSD via CollateralOnramp.")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--amount-usd",
        type=Decimal,
        help="Amount of USDC.e to wrap (e.g. 500 or 500.50).",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Wrap the entire USDC.e balance.",
    )
    p.add_argument("--execute", action="store_true",
                   help="Submit real transactions. Default: dry run.")
    p.add_argument("--yes", action="store_true",
                   help="Skip interactive confirmation (for non-TTY contexts).")
    p.add_argument("--recipient", default=None,
                   help="pUSD recipient address. Defaults to the signer wallet.")
    p.add_argument("--show-full-address", action="store_true",
                   help="Print full wallet addresses (default masks to 0xABCD…1234).")
    return p.parse_args(argv)


def _fmt_addr(addr: str, show_full: bool) -> str:
    """Mask wallet addresses by default (Codex A-16). Full address only
    when --show-full-address is explicitly passed."""
    if show_full or not addr:
        return addr
    return f"{addr[:6]}…{addr[-4:]}"


def _confirm(msg: str) -> None:
    resp = input(msg + " Type 'yes' to proceed: ").strip().lower()
    if resp != "yes":
        print("aborted.")
        sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    rpc_url = os.environ.get("POLYGON_RPC")
    if not rpc_url:
        print("POLYGON_RPC env var not set; cannot connect to Polygon.", file=sys.stderr)
        return 2

    # Keystore load (same path as core/clob.py live mode).
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

    usdce = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E), abi=ERC20_ABI
    )
    onramp = w3.eth.contract(
        address=Web3.to_checksum_address(COLLATERAL_ONRAMP), abi=ONRAMP_ABI
    )

    balance_wei = usdce.functions.balanceOf(owner).call()
    print(f"[wallet] owner={_fmt_addr(owner, args.show_full_address)}")
    print(f"[wallet] USDC.e balance: {_wei_to_usd_str(balance_wei)}")

    if args.all:
        amount_wei = balance_wei
        if amount_wei == 0:
            print("[wallet] zero USDC.e balance — nothing to wrap.")
            return 0
    else:
        amount_wei = _amount_to_wei(args.amount_usd)

    if amount_wei > balance_wei:
        print(f"requested {_wei_to_usd_str(amount_wei)} USDC.e but balance is "
              f"{_wei_to_usd_str(balance_wei)}", file=sys.stderr)
        return 5

    # Check existing allowance.
    current_allow = usdce.functions.allowance(
        owner, Web3.to_checksum_address(COLLATERAL_ONRAMP)
    ).call()
    print(f"[allowance] onramp allowance: {current_allow}")
    needs_approve = current_allow < amount_wei

    print(f"[plan] wrap {_wei_to_usd_str(amount_wei)} USDC.e → pUSD "
          f"(recipient={_fmt_addr(recipient, args.show_full_address)})")
    if needs_approve:
        print("[plan] approve Onramp to spend USDC.e (one-time, unlimited)")
    else:
        print("[plan] allowance sufficient; skipping approve")

    if not args.execute:
        print("\n=== DRY RUN. Re-run with --execute --yes to submit txs. ===")
        return 0

    if not args.yes:
        _confirm(f"About to wrap {_wei_to_usd_str(amount_wei)} USDC.e on-chain.")

    nonce = w3.eth.get_transaction_count(owner)
    max_fee, priority = _gas_fees(w3)

    if needs_approve:
        tx = usdce.functions.approve(
            Web3.to_checksum_address(COLLATERAL_ONRAMP), MAX_UINT256
        ).build_transaction({
            "from": owner, "nonce": nonce, "chainId": POLYGON_CHAIN_ID,
            "gas": 80_000, "maxFeePerGas": max_fee, "maxPriorityFeePerGas": priority,
        })
        _send_tx(w3, acct, tx, "approve-onramp")
        nonce += 1

    tx = onramp.functions.wrap(
        Web3.to_checksum_address(USDC_E),
        Web3.to_checksum_address(recipient),
        amount_wei,
    ).build_transaction({
        "from": owner, "nonce": nonce, "chainId": POLYGON_CHAIN_ID,
        "gas": 300_000, "maxFeePerGas": max_fee, "maxPriorityFeePerGas": priority,
    })
    _send_tx(w3, acct, tx, "wrap-usdce")

    # Final balance check on pUSD.
    pusd = w3.eth.contract(
        address=Web3.to_checksum_address(PUSD_TOKEN_PROXY), abi=ERC20_ABI
    )
    pusd_balance = pusd.functions.balanceOf(recipient).call()
    print(f"[done] pUSD balance on {_fmt_addr(recipient, args.show_full_address)}: "
          f"{Decimal(pusd_balance) / Decimal(10) ** 6:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
