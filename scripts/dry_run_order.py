#!/usr/bin/env python3
"""$5 place-and-cancel sanity check.

Mainnet only. The Amoy CLOB endpoint (`clob-amoy.polymarket.com`) was
decommissioned around the 2026-04 V2 rollout and no longer resolves, so
the former Amoy default path now errors cleanly. The mainnet
unfillable-price path is the sole remaining end-to-end
signing/routing/auth test; price defaults to $0.01 so the order will
never fill before it's cancelled.

Safeguards:
  - Refuses to run unless POLYMARKET_ENV=live AND --mainnet passed.
  - Price is set at a deliberately unfillable $0.01 (no accidental fill).
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from core.clob_v2 import ClobWrapperV2 as ClobWrapper, OrderType, Side
from core.config import get_settings
from core.keystore import Keystore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-id", required=True, help="YES or NO token to place against")
    parser.add_argument("--size", default="5", help="order size USD")
    parser.add_argument(
        "--price", default="0.01", help="deliberately unfillable limit price"
    )
    parser.add_argument("--mainnet", action="store_true")
    args = parser.parse_args(argv)

    s = get_settings()
    if args.mainnet:
        if not s.is_live():
            print("error: --mainnet requires POLYMARKET_ENV=live", file=sys.stderr)
            return 2
    else:
        print(
            "error: Amoy CLOB (clob-amoy.polymarket.com) was decommissioned in the "
            "2026-04 V2 rollout and no longer resolves. Pass --mainnet with "
            "POLYMARKET_ENV=live and an unfillable price (default 0.01) instead. "
            "See docs/decisions-log.md ADR-017.",
            file=sys.stderr,
        )
        return 2

    ks = Keystore.load(s.polymarket_keystore_path, s.polymarket_passphrase_path)
    try:
        print(f"→ Loaded keystore for {ks.address}")
        w = ClobWrapper(keystore=ks, chain_id=s.chain_id, host=s.polymarket_host)
        # Mark preflight manually for the dry-run (OQ-006/007/008 verified out-of-band).
        w.mark_preflight_done(hmac=True, addrs=True, collateral=True)

        resp = w.place_limit(
            token_id=args.token_id,
            price=Decimal(args.price),
            size=Decimal(args.size),
            side=Side.BUY,
            order_type=OrderType.GTC,
        )
        print(f"→ Place response: order_id={resp.order_id} status={resp.status}")
        if not resp.order_id:
            print("error: no order id returned", file=sys.stderr)
            return 1

        ok = w.cancel_order(resp.order_id)
        print(f"→ Cancel result: {ok}")
        if not ok:
            return 1
        return 0
    finally:
        ks.close()


if __name__ == "__main__":
    sys.exit(main())
