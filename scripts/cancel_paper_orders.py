#!/usr/bin/env python3
"""Cancel resting paper orders for a specified bot.

Companion to ``scripts/emergency_cancel_all.py`` (which handles LIVE
on-chain orders): this is the DB-only paper equivalent. When a bot is
archived (``BOT_X_ARCHIVED=true``) or operator-halted, the analyst loop
stops placing new orders, but resting ``PAPER_OPEN`` entries in the DB
remain. They continue to reserve bankroll
(see ``core/fleet.py`` and ``core/portfolio.py`` filter sets) and inflate
"open orders" reports.

Background
----------
Bot C archive (ADR-034, 2026-04-18) and the 2026-04-23 manual archive
sweep that flipped 8 open Bot C positions to ``ARCHIVED_STALE_PAPER``
both missed resting orders. By 2026-04-25 Bot C had 10 ``PAPER_OPEN``
BUY orders with no matching positions — one truly orphaned
(``paper-667154cf20ae`` from 2026-04-15) and 9 placed in a brief
unblocked window after the sweep. Together they reserved ~$132 of paper
bankroll for nothing.

What it does
------------
For ``--bot-id <id>``, finds every order with a bankroll-reserving
status (``OPEN``, ``PARTIAL``, ``PAPER_OPEN``, ``live``, ``MATCHED`` —
the same set used by ``core/fleet.py:209-214``), flips it to
``CANCELLED`` with a fresh ``last_updated`` timestamp, and writes one
``Event`` row per cancelled order with ``event_type='order.cancel.sweep'``
for audit. Idempotent: re-running finds nothing to cancel.

This script does NOT call the live CLOB. It only mutates the local DB.
For live on-chain orders, use ``emergency_cancel_all.py``.

Usage
-----
    # Dry run (prints what would be cancelled, takes no action):
    .venv/bin/python scripts/cancel_paper_orders.py --bot-id bot_c

    # Execute:
    .venv/bin/python scripts/cancel_paper_orders.py --bot-id bot_c --execute

Exit codes
----------
    0 = success (dry run shown or cancellation complete)
    2 = unexpected exception
    3 = invalid arguments
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import or_, select

# Same set used by core/fleet.py:209-214 and core/portfolio.py:639 to
# decide which orders reserve bankroll.
RESERVING_STATUSES = ("OPEN", "PARTIAL", "PAPER_OPEN", "live", "MATCHED")
CANCEL_REASON = "archive_sweep"

log = logging.getLogger("cancel_paper_orders")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--bot-id", required=True,
                   help="bot_id whose resting orders to cancel (e.g. bot_c)")
    p.add_argument("--execute", action="store_true",
                   help="Apply the cancel. Default: dry-run only.")
    p.add_argument("--reason", default=CANCEL_REASON,
                   help=f"Free-text reason for the audit trail (default: {CANCEL_REASON!r})")
    p.add_argument("--older-than-hours", type=float,
                   help="Only cancel orders placed at least this many hours ago.")
    p.add_argument("--expired-only", action="store_true",
                   help="Only cancel orders whose joined market end_date is in the past.")
    p.add_argument("--min-lockup-hours", type=float,
                   help="Only cancel orders whose market end_date minus placed_at is at least this many hours.")
    return p.parse_args(argv)


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def cancel_paper_orders(
    session_factory,
    bot_id: str,
    *,
    execute: bool,
    reason: str = CANCEL_REASON,
    older_than_hours: float | None = None,
    expired_only: bool = False,
    min_lockup_hours: float | None = None,
) -> tuple[int, list[str]]:
    """Cancel resting orders for ``bot_id``.

    Returns ``(count, order_ids)`` of orders that were (or would be)
    cancelled.  When ``execute=False`` the DB is unchanged.
    """
    from core.db import Event, Market, Order

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=older_than_hours) if older_than_hours is not None else None
    with session_factory() as s:
        stmt = (
            select(Order, Market.end_date)
            .outerjoin(Market, Market.condition_id == Order.condition_id)
            .where(Order.bot_id == bot_id)
            .where(Order.status.in_(RESERVING_STATUSES))
            .order_by(Order.placed_at.desc())
        )
        if cutoff is not None:
            stmt = stmt.where(Order.placed_at <= cutoff)
        if expired_only:
            stmt = stmt.where(
                Market.end_date.is_not(None),
                or_(Market.end_date <= now, Market.end_date <= now.replace(tzinfo=None)),
            )
        row_pairs = s.execute(stmt).all()
        if min_lockup_hours is not None:
            row_pairs = [
                pair for pair in row_pairs
                if _as_utc(pair[1]) is not None
                and _as_utc(pair[0].placed_at) is not None
                and (
                    (_as_utc(pair[1]) - _as_utc(pair[0].placed_at)).total_seconds()
                    / 3600
                ) >= min_lockup_hours
            ]
        rows = [pair[0] for pair in row_pairs]
        end_by_order = {pair[0].order_id: pair[1] for pair in row_pairs}

        if not rows:
            return 0, []

        order_ids = [r.order_id for r in rows]

        if not execute:
            return len(rows), order_ids

        for r in rows:
            prior_status = r.status
            r.status = "CANCELLED"
            r.last_updated = now
            end_date = _as_utc(end_by_order.get(r.order_id))
            s.add(Event(
                bot_id=bot_id,
                event_type="order.cancel.sweep",
                severity="info",
                message=f"Cancelled {prior_status} order during {reason}",
                payload={
                    "order_id": r.order_id,
                    "prior_status": prior_status,
                    "side": r.side,
                    "price": str(r.price) if r.price is not None else None,
                    "size": str(r.size) if r.size is not None else None,
                    "reason": reason,
                    "placed_at": r.placed_at.isoformat() if r.placed_at else None,
                    "market_end_date": end_date.isoformat() if end_date else None,
                    "older_than_hours": older_than_hours,
                    "expired_only": expired_only,
                    "min_lockup_hours": min_lockup_hours,
                },
            ))
        s.commit()
        return len(rows), order_ids


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(argv)

    if not args.bot_id.strip():
        print("--bot-id must not be empty", file=sys.stderr)
        return 3

    try:
        from core.db import get_session_factory
        sf = get_session_factory()

        count, order_ids = cancel_paper_orders(
            sf,
            args.bot_id,
            execute=args.execute,
            reason=args.reason,
            older_than_hours=args.older_than_hours,
            expired_only=args.expired_only,
            min_lockup_hours=args.min_lockup_hours,
        )
    except Exception:
        log.exception("cancel sweep failed")
        return 2

    if count == 0:
        log.info("no resting orders to cancel for %s", args.bot_id)
        return 0

    log.info(
        "%s %d resting order(s) for %s",
        "cancelled" if args.execute else "would cancel",
        count, args.bot_id,
    )
    for oid in order_ids:
        log.info("  %s %s", "cancelled:" if args.execute else "  would:", oid)

    if not args.execute:
        log.info("=== DRY RUN. Re-run with --execute to apply. ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
