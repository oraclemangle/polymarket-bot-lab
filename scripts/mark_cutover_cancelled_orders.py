#!/usr/bin/env python3
"""Mark local V1-era open orders as cancelled after the CLOB V2 cutover.

Polymarket wiped all resting V1 orders during the 2026-04-28 CLOB V2
cutover. Local ``orders`` rows do not disappear automatically, and the
portfolio cap code treats OPEN/PARTIAL/live/MATCHED orders as reserving
bankroll. This script performs a local DB-only cleanup: no CLOB calls, no
wallet access, no orders placed or cancelled on-chain.

Default mode is dry-run. Use ``--execute`` to write status updates and emit
one audit Event per affected bot.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import select

from core.db import Event, Order, get_session_factory, init_db
from core.polymarket_v2 import MIGRATION_CUTOVER_UTC_ISO

RESERVING_STATUSES = ("OPEN", "PARTIAL", "PAPER_OPEN", "live", "MATCHED")
TARGET_STATUSES = ("OPEN", "PARTIAL", "live", "MATCHED")
CUTOVER_CANCELLED_STATUS = "CANCELLED_CUTOVER"


def _parse_cutover(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _order_is_before_cutover(order: Order, cutover: datetime) -> bool:
    placed_at = order.placed_at
    if placed_at.tzinfo is None:
        placed_at = placed_at.replace(tzinfo=UTC)
    return placed_at.astimezone(UTC) < cutover


def find_cutover_cancel_candidates(cutover: datetime) -> list[Order]:
    """Return non-paper reserving orders placed before the V2 cutover."""
    with get_session_factory()() as s:
        orders = list(
            s.scalars(
                select(Order).where(
                    Order.status.in_(TARGET_STATUSES),
                    ~Order.order_id.like("paper-%"),
                )
            )
        )
    return [o for o in orders if _order_is_before_cutover(o, cutover)]


def mark_candidates_cancelled(cutover: datetime) -> int:
    """Write CANCELLED_CUTOVER to local DB rows and emit audit Events."""
    with get_session_factory()() as s:
        orders = list(
            s.scalars(
                select(Order).where(
                    Order.status.in_(TARGET_STATUSES),
                    ~Order.order_id.like("paper-%"),
                )
            )
        )
        candidates = [o for o in orders if _order_is_before_cutover(o, cutover)]
        by_bot: Counter[str] = Counter()
        for order in candidates:
            old_status = order.status
            order.status = CUTOVER_CANCELLED_STATUS
            order.last_updated = datetime.now(UTC)
            by_bot[order.bot_id] += 1
            s.add(
                Event(
                    bot_id=order.bot_id,
                    event_type="orders.cutover_cancelled",
                    severity="info",
                    message="Marked V1-era open order cancelled after CLOB V2 cutover",
                    payload={
                        "order_id": order.order_id,
                        "prior_status": old_status,
                        "new_status": CUTOVER_CANCELLED_STATUS,
                        "cutover_utc": cutover.isoformat(),
                    },
                )
            )
        if candidates:
            s.add(
                Event(
                    bot_id=None,
                    event_type="orders.cutover_cancelled.summary",
                    severity="info",
                    message="Marked V1-era open orders cancelled after CLOB V2 cutover",
                    payload={
                        "count": len(candidates),
                        "by_bot": dict(sorted(by_bot.items())),
                        "cutover_utc": cutover.isoformat(),
                    },
                )
            )
        s.commit()
        return len(candidates)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true",
                   help="Write DB changes. Default: dry-run only.")
    p.add_argument("--cutover-utc", default=MIGRATION_CUTOVER_UTC_ISO,
                   help="ISO timestamp for the V2 cutover. Defaults to core.polymarket_v2.")
    args = p.parse_args(argv)

    init_db()
    cutover = _parse_cutover(args.cutover_utc)
    candidates = find_cutover_cancel_candidates(cutover)
    by_bot = Counter(o.bot_id for o in candidates)

    print(f"[init] cutover_utc={cutover.isoformat()}")
    print(f"[scan] candidates={len(candidates)}")
    for bot_id, count in sorted(by_bot.items()):
        print(f"[scan] {bot_id}: {count}")

    if not args.execute:
        print("[dry-run] no DB changes made. Re-run with --execute to mark rows.")
        return 0

    changed = mark_candidates_cancelled(cutover)
    print(f"[done] marked {changed} order(s) {CUTOVER_CANCELLED_STATUS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
