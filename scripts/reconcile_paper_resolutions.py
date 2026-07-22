#!/usr/bin/env python3
"""Settle paper-mode OPEN positions against Gamma-resolved outcomes.

CLI wrapper around ``core.portfolio.Portfolio.reconcile_paper_resolutions``.

Background
----------
Paper mode never triggers the on-chain ``on_redeem`` path, and
``simulate_paper_fills`` only closes positions via SELL fills that are never
issued for resolved markets. Result: OPEN paper positions accumulate past
``Market.end_date``, inflating fleet-cap exposure and hiding realised P&L.

Session 17n cleaned up Bot E's 14 stale paper OPENs by hand; Session 17r-ext
surfaced the same pattern on Bot D (17/22 OPEN rows past end_date). This
script is the loop-level replacement for manual SQL cleanup. Safe to re-run;
the underlying ``on_fill`` is idempotent on ``trade_id``.

Usage
-----
    # Dry run (prints plan, doesn't settle):
    POLYMARKET_ENV=paper .venv/bin/python scripts/reconcile_paper_resolutions.py --bot-id bot_d

    # Execute:
    POLYMARKET_ENV=paper .venv/bin/python scripts/reconcile_paper_resolutions.py --bot-id bot_d --execute

Exit codes
----------
    0 = success (dry run shown or settlement complete)
    2 = reconciliation raised an unexpected exception
"""

from __future__ import annotations

import argparse
import logging
import sys
from decimal import Decimal

from sqlalchemy import select

from core.db import Market, Position, get_session_factory
from core.portfolio import Portfolio

log = logging.getLogger("reconcile_paper_resolutions")


def _before_snapshot(bot_id: str) -> dict:
    sf = get_session_factory()
    with sf() as s:
        positions = list(
            s.scalars(
                select(Position).where(
                    Position.bot_id == bot_id, Position.status == "OPEN"
                )
            )
        )
        cids = {p.condition_id for p in positions if p.condition_id}
        markets = {}
        if cids:
            markets = {
                m.condition_id: m
                for m in s.scalars(select(Market).where(Market.condition_id.in_(cids)))
            }
    past_end = 0
    null_end = 0
    missing_market = 0
    future = 0
    total_cost = Decimal("0")
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    for p in positions:
        total_cost += Decimal(p.cost_basis_usd or 0)
        m = markets.get(p.condition_id)
        if m is None:
            missing_market += 1
            continue
        if m.end_date is None:
            null_end += 1
            continue
        ed = m.end_date if m.end_date.tzinfo else m.end_date.replace(tzinfo=UTC)
        if ed < now:
            past_end += 1
        else:
            future += 1
    return {
        "open_count": len(positions),
        "past_end_date": past_end,
        "null_end_date": null_end,
        "missing_market_row": missing_market,
        "future_end_date": future,
        "total_open_cost_basis": total_cost,
    }


def _print_snapshot(label: str, snap: dict) -> None:
    print(f"\n=== {label} ===")
    print(f"  OPEN positions:        {snap['open_count']}")
    print(f"  ├─ past end_date:      {snap['past_end_date']} (expected to settle)")
    print(f"  ├─ NULL end_date:      {snap['null_end_date']} (orphan — ingest gap)")
    print(f"  ├─ no Market row:      {snap['missing_market_row']} (orphan — ingest gap)")
    print(f"  └─ future end_date:    {snap['future_end_date']} (genuinely open)")
    print(f"  Open cost basis USD:   {snap['total_open_cost_basis']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--bot-id", required=True, help="Bot ID (e.g. bot_d)")
    p.add_argument(
        "--execute", action="store_true",
        help="Actually perform settlement. Without this flag, only prints the snapshot.",
    )
    p.add_argument("--log-level", default="INFO")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    before = _before_snapshot(args.bot_id)
    _print_snapshot(f"BEFORE — {args.bot_id}", before)

    if not args.execute:
        print("\nDry run. Pass --execute to settle resolved positions.")
        return 0

    portfolio = Portfolio()
    print(f"\n=== reconcile_paper_resolutions({args.bot_id}) ===")
    try:
        settled = portfolio.reconcile_paper_resolutions(args.bot_id)
    except Exception:
        log.exception("reconcile_paper_resolutions raised")
        return 2

    after = _before_snapshot(args.bot_id)
    _print_snapshot(f"AFTER — {args.bot_id}", after)
    print(f"\nSettled {settled} position(s).")
    print(f"Open count: {before['open_count']} -> {after['open_count']}")
    print(
        "Open cost basis USD: "
        f"{before['total_open_cost_basis']} -> {after['total_open_cost_basis']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
