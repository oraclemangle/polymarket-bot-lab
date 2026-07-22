#!/usr/bin/env python3
"""Emergency cancel-all: clear every live order on the wallet, bypassing
all bot-level halt/archive gating.

Context (2026-04-19): on-chain forensics showed a BUY order placed days
earlier filled at 16:01 UTC today despite Bot A being archived
(ADR-033) and Bot B operator-halted. Root cause: when a bot is archived
(`BOT_A_ARCHIVED=true`) or operator-halted, the watchdog's
`dispatch_cancel` in `bots/watchdog_daemon.py` intentionally stops
calling `cancel_all` for that bot. Resting orders become orphaned until
they fill or expire. EOA-signed orders with `expiration=0` never expire.

This script is the escape hatch: it opens the live CLOB client via the
keystore, enumerates every live order on the wallet (ignoring DB
attribution), and cancels them all in one call. Use before the V2
cutover, or any time the fleet transitions halt/archive state.

Usage
-----
    # Dry run (shows live orders, takes no action):
    POLYMARKET_ENV=live .venv/bin/python scripts/emergency_cancel_all.py

    # Execute cancel-all:
    POLYMARKET_ENV=live .venv/bin/python scripts/emergency_cancel_all.py --execute --yes
"""
from __future__ import annotations

import argparse
import logging
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--execute", action="store_true",
                   help="Actually call cancel_all. Default: dry-run only.")
    p.add_argument("--yes", action="store_true",
                   help="Skip the interactive confirmation prompt.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    from core.clob_v2 import ClobWrapperV2 as ClobWrapper
    from core.config import get_settings
    from core.keystore import Keystore

    settings = get_settings()
    if not settings.is_live():
        print("POLYMARKET_ENV != live — this script only makes sense in live mode.",
              file=sys.stderr)
        return 3

    try:
        ks = Keystore.load_from_settings(settings)
    except Exception as e:
        print(f"keystore load failed: {e}", file=sys.stderr)
        return 3

    clob = ClobWrapper(keystore=ks)
    clob.load_preflight_from_db()

    live = clob.get_user_orders()
    if not live:
        print("no live orders on the wallet.")
        return 0

    print(f"\n{len(live)} live order(s) on wallet:")
    for o in live:
        print(f"  {o.order_id}  {o.side.name:<4} {o.price} x {o.size}  "
              f"token={o.token_id[:16]}...  status={o.status}")

    if not args.execute:
        print("\n=== DRY RUN. Re-run with --execute --yes to cancel all. ===")
        return 0

    if not args.yes:
        resp = input(
            f"\nAbout to cancel ALL {len(live)} live orders on wallet. "
            f"Type 'yes' to proceed: "
        ).strip().lower()
        if resp != "yes":
            print("aborted.")
            return 1

    n = clob.cancel_all()
    print(f"\ncancel_all reported {n} cancellations.")

    remaining = clob.get_user_orders()
    if remaining:
        print(f"WARN: {len(remaining)} order(s) still live after cancel_all:")
        for o in remaining:
            print(f"  {o.order_id}  {o.side.name:<4} {o.price} x {o.size}")
        return 2
    print("verified: 0 live orders remaining.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
