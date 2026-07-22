"""
Polymarket CLOB — Minimal Reference: Signed Limit Order

============================================================================
DO NOT RUN THIS FILE AS-IS AGAINST MAINNET.
============================================================================
This file is a READ-FOR-REFERENCE example of how py-clob-client places a
signed limit order. It is deliberately configured to default to Polygon
Amoy testnet (chain_id 80002) and the live POST call is COMMENTED OUT.

Rules of engagement:
  1. Never hardcode a private key in this file or any file in the repo.
  2. Load the key from the environment only (POLYMARKET_PK).
  3. Run against Amoy first; flipping CHAIN_ID to 137 = real money on Polygon
     mainnet. Double-check balances, allowances, and the token_id.
  4. EOA / MetaMask users must set USDC + conditional-token allowances once
     before any order will fill. See py-clob-client README "Token Allowances".
  5. Any uncommented POST call in this file during a commit is a bug; review
     the diff.

Sources (canonical, verified 2026-04-14):
  - https://github.com/Polymarket/py-clob-client (examples/order.py, README)
  - Cross-ref: Polymarket/poly-market-maker poly_market_maker/clob_api.py
  - Cross-ref: Polymarket/agents application/trade.py

Confidence: HIGH for init + order-placement shape (verified against upstream
source tree at /tmp/polymarket-research/py-clob-client). MEDIUM for
signature_type choice — depends on whether your funds are in an EOA or a
Polymarket proxy/Magic wallet.
"""

from __future__ import annotations

import os
import sys

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.constants import AMOY, POLYGON
from py_clob_client.order_builder.constants import BUY  # also: SELL


# ---------------------------------------------------------------------------
# Config — loaded from env only. No secrets in source.
# ---------------------------------------------------------------------------
HOST = os.getenv("CLOB_API_URL", "https://clob.polymarket.com")
CHAIN_ID = int(os.getenv("CHAIN_ID", AMOY))  # default to TESTNET
PRIVATE_KEY = os.getenv("POLYMARKET_PK")  # hex string, 0x-prefixed

# Proxy/Magic-wallet users: set FUNDER to the address that holds USDC.
# EOA (MetaMask/hardware wallet): leave FUNDER unset; signer address is funder.
FUNDER = os.getenv("POLYMARKET_FUNDER") or None

# signature_type: 0 = EOA (default), 1 = email/Magic proxy, 2 = browser proxy
SIGNATURE_TYPE = int(os.getenv("POLYMARKET_SIG_TYPE", "0"))

# Example token_id — REPLACE with a live one from Gamma markets API.
TOKEN_ID = os.getenv(
    "POLYMARKET_TOKEN_ID",
    "71321045679252212594626385532706912750332728571942532289631379312455583992563",
)


def _safety_guard() -> None:
    if CHAIN_ID == POLYGON:
        print(
            "[ABORT] CHAIN_ID=137 (mainnet). This reference script refuses to "
            "run against mainnet. Remove this guard deliberately if you know "
            "what you're doing.",
            file=sys.stderr,
        )
        sys.exit(2)
    if not PRIVATE_KEY:
        print("[ABORT] POLYMARKET_PK not set in env.", file=sys.stderr)
        sys.exit(2)


def build_l2_client() -> ClobClient:
    """L2 client: full read/write. Requires PK + API creds (key/secret/pass)."""
    client = ClobClient(
        HOST,
        key=PRIVATE_KEY,
        chain_id=CHAIN_ID,
        signature_type=SIGNATURE_TYPE if FUNDER else None,
        funder=FUNDER,
    )
    # Derive-or-create API creds. This is idempotent per wallet/nonce.
    # The creds are HMAC credentials used for L2 signing; the PK is NOT
    # transmitted — the derive call is signed with an EIP-712 L1 header.
    client.set_api_creds(client.create_or_derive_api_creds())
    return client


def main() -> None:
    _safety_guard()

    # 1. Read-only book fetch (no auth needed).
    ro = ClobClient(HOST)
    book = ro.get_order_book(TOKEN_ID)
    print("best bid:", book.bids[-1] if book.bids else None)
    print("best ask:", book.asks[-1] if book.asks else None)

    # 2. Full client + sign an order locally (no network POST).
    client = build_l2_client()
    order_args = OrderArgs(
        token_id=TOKEN_ID,
        price=0.01,   # $0.01 per share — well away from any real market
        size=5.0,     # 5 shares
        side=BUY,
    )
    signed = client.create_order(order_args)
    print("signed order (built locally, not posted):")
    print("  salt:", signed.salt)
    print("  maker:", signed.maker)
    print("  signer:", signed.signer)
    print("  signature:", signed.signature[:16] + "...")

    # 3. POST — deliberately COMMENTED OUT. Uncomment ONLY on Amoy after
    #    reviewing the signed order above.
    # resp = client.post_order(signed, orderType=OrderType.GTC, post_only=True)
    # print("post response:", resp)
    # order_id = resp.get("orderID")

    # 4. Cancel flow (requires an order_id returned from post_order).
    # if order_id:
    #     cancel_resp = client.cancel(order_id=order_id)
    #     print("cancel response:", cancel_resp)
    # client.cancel_all()  # nuke everything; useful for emergency stop


if __name__ == "__main__":
    main()
