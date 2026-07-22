"""One-off repair: close locally-OPEN Bot D live positions the wallet no
longer holds.

Dry-run by default. Use ``--execute`` to actually mutate the local
ledger. Never touches the CLOB, wallet, or keystore — only the local
``positions`` table and an audit ``Event`` per closed row.

Usage
-----

::

    # Preview what would change (always safe; no DB mutation):
    python -m scripts.bot_d_reconcile_live_positions \\
        --wallet 0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA

    # Apply (after the dry-run output looks right):
    python -m scripts.bot_d_reconcile_live_positions \\
        --wallet 0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA --execute

If ``--wallet`` is omitted, the script reads ``POLYMARKET_WALLET`` from
the environment, or — when run on a Bot-D-live host with the keystore
available — derives it from the loaded keystore. The script refuses to
run if no wallet address can be resolved.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select

from core.db import Position, get_session_factory
from core.portfolio import Portfolio


log = logging.getLogger("bot_d_reconcile_live_positions")


def _resolve_wallet(arg_wallet: str | None) -> str:
    if arg_wallet:
        return arg_wallet
    env = os.environ.get("POLYMARKET_WALLET")
    if env:
        return env.strip()
    # Last-resort: keystore derivation (Bot D live host only).
    try:
        from core.config import get_settings
        from core.keystore import Keystore

        ks = Keystore.load_from_settings(get_settings())
        return ks.address
    except Exception as exc:  # keystore.age missing, passphrase not on tmpfs, etc.
        raise SystemExit(
            f"Could not resolve wallet address: pass --wallet, set "
            f"POLYMARKET_WALLET, or run on the live host with the "
            f"keystore mounted. ({exc})"
        )


def _summarise_local(bot_id: str) -> dict[str, object]:
    sf = get_session_factory()
    with sf() as s:
        rows = list(
            s.scalars(
                select(Position).where(
                    Position.bot_id == bot_id, Position.status == "OPEN"
                )
            )
        )
    cost = sum((Decimal(str(p.cost_basis_usd or 0)) for p in rows), Decimal("0"))
    return {
        "open_count": len(rows),
        "total_cost_basis_usd": float(cost),
    }


def _format_position(row: dict[str, str]) -> str:
    token_short = row["token_id"][:10] + "…" if len(row["token_id"]) > 10 else row["token_id"]
    return (
        f"  id={row['id']:>4}  token={token_short}  size={row['size']}  "
        f"cost=${row['cost_basis_usd']}  side={row['side']}"
    )


def run(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Close stale Bot D live OPEN positions that the wallet no longer holds.",
    )
    parser.add_argument("--bot-id", default="bot_d_live_probe", help="Local bot_id (default: bot_d_live_probe)")
    parser.add_argument("--wallet", default=None, help="Hot wallet address (0x...); falls back to env/keystore")
    parser.add_argument(
        "--data-api",
        default=os.environ.get("POLYMARKET_DATA_API", "https://data-api.polymarket.com"),
        help="Polymarket Data API base URL",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually mutate local rows. Default is dry-run (preview only).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the reconciler result as JSON instead of human text.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python log level (default INFO).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    wallet = _resolve_wallet(args.wallet)
    before = _summarise_local(args.bot_id)

    log.info(
        "before: bot_id=%s open_count=%d cost_basis=$%.2f wallet=%s%s",
        args.bot_id,
        before["open_count"],
        before["total_cost_basis_usd"],
        wallet[:10] + "…",
        " (DRY-RUN)" if not args.execute else "",
    )

    portfolio = Portfolio()
    result = portfolio.reconcile_live_positions_against_wallet(
        args.bot_id,
        wallet,
        data_api=args.data_api,
        dry_run=not args.execute,
    )

    if not result.get("ok"):
        log.error(
            "reconcile.degraded reason=%s — local ledger left unchanged.",
            result.get("reason"),
        )
        if args.json:
            print(json.dumps(result, default=str))
        return 2

    after = _summarise_local(args.bot_id)
    summary = {
        "bot_id": args.bot_id,
        "wallet": wallet,
        "data_api": args.data_api,
        "dry_run": not args.execute,
        "before": before,
        "after": after,
        "checked": result.get("checked"),
        "kept_open": result.get("kept_open"),
        "closed_count": result.get("closed_count"),
        "closed_positions": result.get("closed_positions"),
    }

    if args.json:
        print(json.dumps(summary, default=str, indent=2))
        return 0

    print()
    print("=" * 72)
    print(f"Bot D live ledger reconcile — {'DRY-RUN' if not args.execute else 'EXECUTE'}")
    print("=" * 72)
    print(f"  bot_id              {args.bot_id}")
    print(f"  wallet              {wallet}")
    print(f"  data_api            {args.data_api}")
    print()
    print(f"  before  open_count  {before['open_count']}")
    print(f"          cost_basis  ${before['total_cost_basis_usd']:.2f}")
    print(f"  after   open_count  {after['open_count']}")
    print(f"          cost_basis  ${after['total_cost_basis_usd']:.2f}")
    print()
    print(f"  checked       {result.get('checked')}")
    print(f"  kept_open     {result.get('kept_open')}  (wallet still holds)")
    print(f"  closed_count  {result.get('closed_count')}  (status -> CLOSED_EXTERNAL_SYNC)")
    if result.get("closed_positions"):
        print()
        print(f"  {'WOULD CLOSE' if not args.execute else 'CLOSED'}:")
        for row in result["closed_positions"]:
            print(_format_position(row))
    print()
    if not args.execute:
        print("  No changes were written. Re-run with --execute to apply.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(run())
