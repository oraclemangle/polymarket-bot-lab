#!/usr/bin/env python3
"""Liquidate all open Bot A / Bot B positions pre-V2-migration.

Option A from the V2 migration plan (2026-04-17): sell all live real-money
positions before the 2026-04-22 11:00 UTC cutover. Accept realized losses
on tight books in exchange for a clean paper-only posture across the
migration. Generalises the Session 14 Bolsonaro sell pattern
(`/tmp/_sell_bolsonaro.py`) to bulk-close all open positions idempotently.

Execution model
---------------
For each open Position row (bot_id in {bot_a, bot_b}, status='OPEN'):
  1. Fetch the current order book for the position's token_id.
  2. Compute an exit limit price at best_bid - `slippage_cents` (default 1¢).
  3. Place a GTC SELL limit for the full position size.
  4. Poll user_orders every 5s for up to `fill_timeout_sec` (default 120s).
  5. On fill: mark Position status='CLOSED_V2_MIGRATION', emit audit Event.
  6. On timeout: leave position OPEN, emit `liquidate.stalled` Event, move on.

Safety
------
- Dry run by default. --execute required for real orders.
- Per-position opt-out via --skip-cid / --only-cid filters.
- Hard halt on the first unexpected exception (operator inspects before resuming).
- Tracks progress so a re-run is idempotent (skips already-CLOSED_V2_MIGRATION rows).

Usage
-----
    # Plan only (prints what would happen):
    python scripts/liquidate_positions.py

    # Execute all Bot A + Bot B opens:
    python scripts/liquidate_positions.py --execute

    # Execute a specific subset:
    python scripts/liquidate_positions.py --execute --only-cid 0xabc... --only-cid 0xdef...
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import and_, select

from core.clob_v2 import ClobWrapperV2 as ClobWrapper, OrderType, Side
from core.db import Event, Order, Position, get_session_factory
from core.keystore import Keystore

log = logging.getLogger(__name__)


CLOSED_STATUS = "CLOSED_V2_MIGRATION"
AUDIT_EVENT_TYPE = "liquidate.v2_migration"


@dataclass(frozen=True)
class LiquidationPlan:
    position_id: int
    bot_id: str
    condition_id: str
    token_id: str
    size: Decimal
    best_bid: Decimal
    exit_limit: Decimal
    notional_usd: Decimal


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Liquidate open Bot A/B positions pre-V2-migration."
    )
    p.add_argument("--execute", action="store_true",
                   help="Submit real SELL orders. Default: dry run (plan only).")
    p.add_argument("--yes", action="store_true",
                   help="Skip interactive confirmation.")
    p.add_argument("--slippage-cents", type=Decimal, default=Decimal("0.01"),
                   help="Cents below best_bid to place the exit SELL (default 0.01).")
    p.add_argument("--fill-timeout-sec", type=int, default=120,
                   help="Seconds to wait for each fill before moving on.")
    p.add_argument("--bots", default="bot_a,bot_b",
                   help="Comma-separated list of bot_ids to liquidate.")
    p.add_argument("--only-cid", action="append", default=[],
                   help="Restrict to these condition_ids (repeatable).")
    p.add_argument("--skip-cid", action="append", default=[],
                   help="Skip these condition_ids (repeatable).")
    return p.parse_args(argv)


def _book_best_bid(clob: ClobWrapper, token_id: str) -> Decimal:
    """Return best-bid price from the CLOB; 0 if empty book.

    ClobWrapper.get_book returns OrderBook with `bids` as a list of
    (Decimal, Decimal) tuples (price, size), NOT objects with .price.
    See core/clob.py OrderBook dataclass.
    """
    try:
        book = clob.get_book(token_id)
    except Exception as e:
        log.warning("book_fetch_failed token=%s err=%s", token_id, e)
        return Decimal("0")
    bids = getattr(book, "bids", []) or []
    if not bids:
        return Decimal("0")
    # bids: [(price, size), ...] sorted desc by price.
    prices: list[Decimal] = []
    for b in bids:
        if isinstance(b, tuple) and len(b) >= 1:
            prices.append(Decimal(str(b[0])))
        elif hasattr(b, "price"):
            prices.append(Decimal(str(b.price)))
    return max(prices) if prices else Decimal("0")


def build_plans(
    session_factory,
    clob: ClobWrapper,
    bots: list[str],
    only_cids: set[str],
    skip_cids: set[str],
    slippage_cents: Decimal,
) -> list[LiquidationPlan]:
    plans: list[LiquidationPlan] = []
    with session_factory() as s:
        rows = list(s.scalars(
            select(Position).where(
                and_(
                    Position.bot_id.in_(bots),
                    Position.status == "OPEN",
                )
            )
        ))
    for p in rows:
        if only_cids and p.condition_id not in only_cids:
            continue
        if p.condition_id in skip_cids:
            continue
        best_bid = _book_best_bid(clob, p.token_id)
        if best_bid <= 0:
            log.warning("no_bid cid=%s token=%s — skipping", p.condition_id, p.token_id)
            continue
        exit_limit = (best_bid - slippage_cents).quantize(Decimal("0.01"))
        # Clamp to safe range.
        if exit_limit <= Decimal("0.005"):
            exit_limit = Decimal("0.005")
        if exit_limit >= Decimal("0.995"):
            exit_limit = Decimal("0.995")
        size = Decimal(str(p.size))
        if size <= 0:
            continue
        notional = (size * exit_limit).quantize(Decimal("0.01"))
        plans.append(LiquidationPlan(
            position_id=p.id,
            bot_id=p.bot_id,
            condition_id=p.condition_id,
            token_id=p.token_id,
            size=size,
            best_bid=best_bid,
            exit_limit=exit_limit,
            notional_usd=notional,
        ))
    return plans


def print_plans(plans: list[LiquidationPlan]) -> Decimal:
    total = Decimal("0")
    print(f"\n{'bot':<6}  {'cid':<20}  {'size':>10}  {'best_bid':>9}  "
          f"{'exit_limit':>10}  {'notional':>10}")
    print("-" * 80)
    for p in plans:
        cid_short = (p.condition_id[:17] + "...") if len(p.condition_id) > 20 else p.condition_id
        print(f"{p.bot_id:<6}  {cid_short:<20}  {p.size:>10}  {p.best_bid:>9}  "
              f"{p.exit_limit:>10}  {p.notional_usd:>10}")
        total += p.notional_usd
    print("-" * 80)
    print(f"{'TOTAL':<6}  {'':<20}  {'':>10}  {'':>9}  "
          f"{'':>10}  {total:>10}")
    return total


def liquidate_one(
    session_factory,
    clob: ClobWrapper,
    plan: LiquidationPlan,
    fill_timeout_sec: int,
    execute: bool,
) -> str:
    """Execute a single liquidation. Returns 'filled' | 'stalled' | 'dry-run' | 'skipped'."""
    if not execute:
        return "dry-run"
    # Idempotency: skip if already marked liquidated.
    with session_factory() as s:
        current = s.get(Position, plan.position_id)
        if current is None:
            return "skipped"
        if current.status == CLOSED_STATUS:
            return "skipped"
    # Place SELL.
    try:
        resp = clob.place_limit(
            token_id=plan.token_id,
            price=plan.exit_limit,
            size=plan.size,
            side=Side.SELL,
            order_type=OrderType.GTC,
        )
    except Exception as e:
        _emit_event(session_factory, plan, severity="warn",
                    status="place_failed", detail=str(e)[:300])
        return "stalled"
    order_id = resp.order_id
    if not order_id:
        _emit_event(session_factory, plan, severity="warn",
                    status="no_order_id", detail=str(getattr(resp, "status", "")))
        return "stalled"
    # Record the SELL Order row.
    with session_factory() as s:
        s.add(Order(
            order_id=order_id,
            bot_id=plan.bot_id,
            condition_id=plan.condition_id,
            token_id=plan.token_id,
            side="SELL",
            price=plan.exit_limit,
            size=plan.size,
            status=getattr(resp, "status", None) or "OPEN",
            order_type="GTC",
        ))
        s.commit()
    # Poll for fill.
    filled = _poll_for_fill(clob, order_id, fill_timeout_sec)
    if not filled:
        _emit_event(session_factory, plan, severity="warn",
                    status="fill_timeout", detail=f"order_id={order_id}")
        return "stalled"
    # Mark position CLOSED_V2_MIGRATION.
    with session_factory() as s:
        pos = s.get(Position, plan.position_id)
        if pos is not None:
            pos.status = CLOSED_STATUS
            pos.closed_at = datetime.now(UTC)
            s.commit()
    _emit_event(session_factory, plan, severity="info",
                status="filled", detail=f"order_id={order_id}")
    return "filled"


def _poll_for_fill(clob: ClobWrapper, order_id: str, timeout_sec: int) -> bool:
    """Poll CLOB user_orders endpoint; order absent from open list → assume filled."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            open_orders = clob.get_user_orders() or []
        except Exception as e:
            log.warning("user_orders_fetch_failed err=%s", e)
            time.sleep(5)
            continue
        ids = {getattr(o, "order_id", None) for o in open_orders}
        if order_id not in ids:
            return True
        time.sleep(5)
    return False


def _emit_event(session_factory, plan: LiquidationPlan, *,
                severity: str, status: str, detail: str) -> None:
    try:
        with session_factory() as s:
            s.add(Event(
                bot_id=plan.bot_id,
                event_type=AUDIT_EVENT_TYPE,
                severity=severity,
                message=f"liquidate.{status} cid={plan.condition_id}",
                payload={
                    "position_id": plan.position_id,
                    "condition_id": plan.condition_id,
                    "token_id": plan.token_id,
                    "requested_size": str(plan.size),
                    "requested_limit": str(plan.exit_limit),
                    "best_bid_at_plan": str(plan.best_bid),
                    "status": status,
                    "detail": detail,
                },
            ))
            s.commit()
    except Exception:
        log.exception("failed_to_emit_audit_event status=%s", status)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    session_factory = get_session_factory()

    # Keystore required in live mode; paper mode can run without.
    from core.config import get_settings
    settings = get_settings()
    if settings.is_live():
        try:
            ks = Keystore.load_from_settings(settings)
        except Exception as e:
            print(f"keystore load failed: {e}", file=sys.stderr)
            return 3
        clob = ClobWrapper(keystore=ks)
        # Preflight must be ON before any live order; the repo reads it
        # from the DB's preflight.verified event (written once by
        # scripts/preflight_check.py --commit --live).
        clob.load_preflight_from_db()
    else:
        print("[info] POLYMARKET_ENV != live — running in paper mode. "
              "Real liquidation requires live mode.")
        clob = ClobWrapper(keystore=None)

    bots = [b.strip() for b in args.bots.split(",") if b.strip()]
    only = set(args.only_cid)
    skip = set(args.skip_cid)

    plans = build_plans(session_factory, clob, bots, only, skip, args.slippage_cents)
    if not plans:
        print("no qualifying open positions — nothing to liquidate.")
        return 0

    total_notional = print_plans(plans)

    if not args.execute:
        print("\n=== DRY RUN. Re-run with --execute --yes to place SELL orders. ===")
        return 0

    if not args.yes:
        resp = input(
            f"\nAbout to SELL {len(plans)} positions "
            f"(~${total_notional} notional) on-chain. Type 'yes' to proceed: "
        ).strip().lower()
        if resp != "yes":
            print("aborted.")
            return 1

    results = {"filled": 0, "stalled": 0, "skipped": 0, "dry-run": 0}
    for plan in plans:
        outcome = liquidate_one(
            session_factory, clob, plan,
            fill_timeout_sec=args.fill_timeout_sec, execute=args.execute,
        )
        results[outcome] = results.get(outcome, 0) + 1
        print(f"[{plan.bot_id} {plan.condition_id[:20]}] {outcome}")

    print(f"\nresults: {results}")
    if results.get("stalled", 0) > 0:
        print("Some positions stalled; re-run after operator review, or cancel the "
              "stale SELL orders and retry with wider slippage.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
