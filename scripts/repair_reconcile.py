#!/usr/bin/env python3
"""One-shot: repair positions created with empty condition_id.

Deletes Trade + Position rows that were created before the market_id fix,
then re-runs reconcile_live_fills for bot_a and bot_b. Safe to re-run
(idempotent after first pass — on_fill checks trade_id uniqueness).

Usage:
    python scripts/repair_reconcile.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)

from dotenv import load_dotenv
load_dotenv(".env")

from core.config import reset_settings, get_settings
reset_settings()

from sqlalchemy import select, delete
from core.db import get_session_factory, Position, Trade, init_db
from core.portfolio import Portfolio
from core.clob_v2 import ClobWrapperV2 as ClobWrapper
from core.keystore import Keystore

init_db()
sf = get_session_factory()
settings = get_settings()

# Step 1: Delete positions with empty condition_id (the bad data).
with sf() as s:
    bad_positions = list(s.scalars(
        select(Position).where(Position.condition_id == "")
    ))
    print(f"bad positions (empty cid): {len(bad_positions)}")
    for p in bad_positions:
        print(f"  deleting: bot={p.bot_id} token={p.token_id[:20]}.. side={p.side} sz={p.size}")
        s.delete(p)
    s.commit()

# Step 2: Delete ALL Trade rows so they can be re-imported with correct condition_id.
with sf() as s:
    trade_count = s.execute(select(Trade)).all()
    print(f"deleting {len(trade_count)} trade rows for re-import")
    s.execute(delete(Trade))
    s.commit()

# Step 3: Re-reconcile with the fixed code.
if not settings.is_live():
    print("SKIP: not in live mode")
    sys.exit(0)

ks = Keystore.load(settings.polymarket_keystore_path, settings.polymarket_passphrase_path)
clob = ClobWrapper(keystore=ks)
clob.load_preflight_from_db()
p = Portfolio()

for bot_id in ("bot_a", "bot_b"):
    # Reset the fill cursor so reconcile starts from the beginning.
    from core.db import Event
    with sf() as s:
        cursors = list(s.scalars(
            select(Event).where(Event.event_type == f"portfolio.fill_cursor.{bot_id}")
        ))
        for c in cursors:
            s.delete(c)
        s.commit()

    n = p.reconcile_live_fills(clob, bot_id)
    print(f"{bot_id}: reconciled {n} fills")

# Step 4: Show result.
with sf() as s:
    positions = list(s.scalars(select(Position)))
    print(f"\nfinal positions: {len(positions)}")
    for pos in positions:
        cid = pos.condition_id[:28] if pos.condition_id else "(empty)"
        print(f"  {pos.bot_id} cid={cid}.. side={pos.side} sz={pos.size} avg={pos.avg_price} cost=${pos.cost_basis_usd} status={pos.status}")

    trades = list(s.scalars(select(Trade)))
    print(f"\ntrades: {len(trades)}")
    for t in trades[:5]:
        cid = t.condition_id[:28] if t.condition_id else "(empty)"
        print(f"  {t.bot_id} cid={cid}.. side={t.side} px={t.price} sz={t.size}")

# Step 5: Cancel duplicate live orders.
# For each condition_id with multiple live orders, keep the earliest and cancel the rest.
# For condition_ids that already have a matched fill, cancel ALL remaining live orders.
print("\n=== cancelling duplicate orders ===")
with sf() as s:
    from core.db import Order
    from sqlalchemy import func

    # Find condition_ids with matched fills — cancel ALL live on these.
    matched_cids = {r[0] for r in s.execute(
        select(Order.condition_id).where(
            Order.bot_id == "bot_a",
            Order.status == "matched",
        ).group_by(Order.condition_id)
    )}
    print(f"condition_ids with fills: {len(matched_cids)}")

    # Find condition_ids with >1 live order — keep first, cancel rest.
    dupe_cids = {r[0] for r in s.execute(
        select(Order.condition_id).where(
            Order.bot_id == "bot_a",
            Order.status == "live",
        ).group_by(Order.condition_id).having(func.count() > 1)
    )}
    print(f"condition_ids with duplicate live orders: {len(dupe_cids)}")

cancel_count = 0
for cid in matched_cids | dupe_cids:
    with sf() as s:
        orders = list(s.scalars(
            select(Order).where(
                Order.bot_id == "bot_a",
                Order.condition_id == cid,
                Order.status == "live",
            ).order_by(Order.placed_at)
        ))
    if not orders:
        continue

    if cid in matched_cids:
        # Already have a position — cancel ALL live orders for this market.
        to_cancel = orders
    else:
        # Keep the first (earliest) order, cancel the rest.
        to_cancel = orders[1:]

    for o in to_cancel:
        try:
            ok = clob.cancel_order(o.order_id)
            if ok:
                with sf() as s:
                    db_o = s.get(Order, o.order_id)
                    if db_o:
                        db_o.status = "CANCELLED"
                        s.commit()
                cancel_count += 1
                print(f"  cancelled {o.order_id[:20]}.. cid={cid[:24]}.. px={o.price}")
        except Exception as e:
            print(f"  FAILED to cancel {o.order_id[:20]}.. : {e}")

print(f"\ncancelled {cancel_count} duplicate orders")
print("\ndone")
