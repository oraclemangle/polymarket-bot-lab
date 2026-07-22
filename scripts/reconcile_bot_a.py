#!/usr/bin/env python3
"""Reconcile Bot A live fills — OQ-030.

CLI wrapper around `core.portfolio.Portfolio.reconcile_live_fills(...)`.

Background
----------
After the Patch A orphan-SELL accounting fix (commit 6811edd, 2026-04-16),
Bot A's realised P&L reports $0 even though the bot earned some spread via
the CTF split-sell mechanic. The missing BUY legs should be recoverable
via the existing `reconcile_live_fills` method, which fetches the CLOB's
user-trades API with a cursor.

This script runs that reconciliation idempotently (the underlying method
uses an Event-row cursor so repeat invocations skip already-imported
fills). Pre-flight verification checks:
  1. A before-state snapshot: count of `trades` rows + sum of `cost_basis_usd`
     + sum of `realised_pnl` per Position.
  2. The reconciliation pass.
  3. An after-state snapshot + diff report.

Safety
------
- Dry-run by default (`--execute` required for real calls).
- Even in `--execute` mode, only adds missing BUY/SELL Trade rows and updates
  Position rows via `Portfolio.on_fill`; never deletes existing data.
- Can be run under `POLYMARKET_ENV=paper`, but the CLOB will return an empty
  trade list (no live fills to reconcile), so this is effectively a no-op.
- Emits an audit Event row summarising the diff.

Usage
-----
    # Dry run (prints plan, doesn't hit CLOB):
    POLYMARKET_ENV=live .venv/bin/python scripts/reconcile_bot_a.py

    # Execute:
    POLYMARKET_ENV=live .venv/bin/python scripts/reconcile_bot_a.py --execute

    # Bot G live-safe backfill, importing only fills for known local orders:
    POLYMARKET_ENV=live .venv/bin/python scripts/reconcile_bot_a.py \
      --bot-id bot_g_prime_live --require-known-order \
      --cursor-key portfolio.fill_cursor.bot_g_prime_live.backfill-2026-05-02 \
      --execute

Exit codes
----------
    0 = success (reconciliation complete or dry-run shown)
    2 = keystore / CLOB initialization failed
    3 = reconciliation raised an unexpected exception
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select

from core.clob_v2 import ClobWrapperV2 as ClobWrapper
from core.config import get_settings
from core.db import Event, Position, Trade, get_session_factory
from core.keystore import Keystore
from core.portfolio import Portfolio

log = logging.getLogger(__name__)

DEFAULT_BOT_ID = "bot_a"
AUDIT_EVENT = "portfolio.reconcile.cli"


@dataclass(frozen=True)
class StateSnapshot:
    trade_count: int
    open_position_count: int
    total_cost_basis_usd: Decimal
    total_size: Decimal


def snapshot(session_factory, bot_id: str) -> StateSnapshot:
    with session_factory() as s:
        trade_n = s.scalar(
            select(func.count()).select_from(Trade).where(Trade.bot_id == bot_id)
        ) or 0
        open_n = s.scalar(
            select(func.count()).select_from(Position).where(
                Position.bot_id == bot_id, Position.status == "OPEN"
            )
        ) or 0
        cost_basis = s.scalar(
            select(func.sum(Position.cost_basis_usd)).where(
                Position.bot_id == bot_id, Position.status == "OPEN"
            )
        ) or Decimal("0")
        total_size = s.scalar(
            select(func.sum(Position.size)).where(
                Position.bot_id == bot_id, Position.status == "OPEN"
            )
        ) or Decimal("0")
    return StateSnapshot(
        trade_count=int(trade_n),
        open_position_count=int(open_n),
        total_cost_basis_usd=Decimal(str(cost_basis)),
        total_size=Decimal(str(total_size)),
    )


def print_snapshot(label: str, s: StateSnapshot) -> None:
    print(f"[{label}] trades={s.trade_count}  open_positions={s.open_position_count}  "
          f"cost_basis_usd=${s.total_cost_basis_usd}  total_shares={s.total_size}")


def diff_snapshots(before: StateSnapshot, after: StateSnapshot) -> dict:
    return {
        "trades_added": after.trade_count - before.trade_count,
        "positions_delta": after.open_position_count - before.open_position_count,
        "cost_basis_delta_usd": str(after.total_cost_basis_usd - before.total_cost_basis_usd),
        "shares_delta": str(after.total_size - before.total_size),
    }


def emit_audit_event(session_factory, bot_id: str, diff: dict, fills_reconciled: int) -> None:
    try:
        with session_factory() as s:
            s.add(Event(
                bot_id=bot_id,
                event_type=AUDIT_EVENT,
                severity="info",
                message=f"OQ-030 reconcile: +{fills_reconciled} fills",
                payload={
                    "fills_reconciled": fills_reconciled,
                    "diff": diff,
                    "ran_at": datetime.now(UTC).isoformat(),
                },
            ))
            s.commit()
    except Exception:
        log.exception("failed to emit audit event")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Reconcile Bot A live fills (OQ-030).")
    p.add_argument("--bot-id", default=DEFAULT_BOT_ID,
                   help="Bot ID to reconcile. Default: bot_a.")
    p.add_argument("--execute", action="store_true",
                   help="Actually call the CLOB and import fills. "
                        "Default: dry run (snapshot only).")
    p.add_argument("--cursor-key", default=None,
                   help="Override the Event-row cursor key. Default: "
                        "portfolio.fill_cursor.<bot_id>.")
    p.add_argument("--require-known-order", action="store_true",
                   help="Import only trades whose order_id maps to a local "
                        "Order row for the target bot. Use this for Bot G "
                        "live backfills to avoid importing unrelated wallet "
                        "history.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    session_factory = get_session_factory()
    settings = get_settings()

    # Keystore + CLOB only required for the --execute path.
    keystore: Keystore | None = None
    if args.execute:
        if not settings.is_live():
            print(f"warning: POLYMARKET_ENV={settings.polymarket_env!r} but --execute set. "
                  "CLOB will return empty trade list in paper/dev mode.", file=sys.stderr)
        if settings.is_live():
            try:
                keystore = Keystore.load_from_settings(settings)
            except Exception as e:
                print(f"keystore load failed: {e}", file=sys.stderr)
                return 2

    clob = ClobWrapper(keystore=keystore)
    portfolio = Portfolio(session_factory=session_factory)

    print("\n=== Bot A reconcile_live_fills (OQ-030) ===")
    print(f"bot_id: {args.bot_id}")
    print(f"mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"polymarket_env: {settings.polymarket_env}")
    print(f"require_known_order: {args.require_known_order}")
    print()

    before = snapshot(session_factory, args.bot_id)
    print_snapshot("before", before)

    if not args.execute:
        print("\n=== DRY RUN. No CLOB calls made. Re-run with --execute to reconcile. ===")
        return 0

    try:
        fills = portfolio.reconcile_live_fills(
            clob,
            args.bot_id,
            cursor_key=args.cursor_key,
            require_known_order=args.require_known_order,
        )
    except Exception:
        log.exception("reconcile_live_fills raised")
        return 3

    after = snapshot(session_factory, args.bot_id)
    print_snapshot("after", after)

    diff = diff_snapshots(before, after)
    print(f"\n[diff] {diff}")
    print(f"[result] fills_reconciled={fills}")

    emit_audit_event(session_factory, args.bot_id, diff, fills)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
