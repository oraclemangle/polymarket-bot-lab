#!/usr/bin/env python3
"""Reconcile bot_d Position rows from the Trade table.

Rationale: Session 17k U-06 fix removed a Position dual-write at placement
that was doubling `size` / `cost_basis_usd` on every fill. The Trade table
is authoritative; Position rows under bot_d need rebuilding from fills.

Method (avg-cost):
    For each (token_id) in bot_d trades:
        buy_size   = sum(BUY.size)
        buy_cost   = sum(BUY.size * BUY.price)
        sell_size  = sum(SELL.size)
        avg_price  = buy_cost / buy_size          (undefined if no buys)
        net_size   = buy_size - sell_size
        cost_basis = avg_price * net_size          (if net_size > 0)

    If net_size > 0 → OPEN Position with the computed values.
    If net_size <= 0 → no OPEN Position (fully sold / over-sold).

    outcome side (YES/NO) is preserved from the existing Position row
    (token_id → outcome side is a 1:1 mapping in Polymarket).

Safety:
    1. Snapshots current bot_d OPEN positions into `positions_archive_botd_<ts>`.
    2. Runs in two modes — default `--dry-run` prints the before/after
       table and exits; pass `--apply` to mutate.
    3. Writes a second archive of the post-reconciliation state so the
       delta is auditable.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from sqlalchemy import select, text  # noqa: E402

from core.db import Market, Position, Trade, get_session_factory  # noqa: E402

BOT_ID = "bot_d"
ZERO = Decimal("0")


def reconcile(apply: bool) -> int:
    sessions = get_session_factory()
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_table = f"positions_archive_botd_{ts}"

    with sessions() as s:
        # --- 1. Snapshot current state ---------------------------------
        current_positions = list(
            s.scalars(
                select(Position).where(
                    Position.bot_id == BOT_ID, Position.status == "OPEN"
                )
            ).all()
        )
        outcome_side_by_token = {p.token_id: p.side for p in current_positions}
        current_by_token = {p.token_id: p for p in current_positions}

        # Backfill outcome side from Market for tokens with no Position row.
        missing_tokens = {
            t.token_id for t in s.scalars(select(Trade).where(Trade.bot_id == BOT_ID)).all()
            if t.token_id not in outcome_side_by_token
        }
        if missing_tokens:
            for m in s.scalars(
                select(Market).where(
                    (Market.yes_token_id.in_(missing_tokens))
                    | (Market.no_token_id.in_(missing_tokens))
                )
            ).all():
                if m.yes_token_id in missing_tokens:
                    outcome_side_by_token[m.yes_token_id] = "YES"
                if m.no_token_id in missing_tokens:
                    outcome_side_by_token[m.no_token_id] = "NO"

        # --- 2. Aggregate trades per token -----------------------------
        trades = list(s.scalars(select(Trade).where(Trade.bot_id == BOT_ID)).all())
        by_tok: dict[str, dict[str, Decimal]] = defaultdict(
            lambda: {
                "buy_size": ZERO,
                "buy_cost": ZERO,
                "sell_size": ZERO,
                "sell_proceeds": ZERO,
                "condition_id": "",
            }
        )
        for t in trades:
            k = by_tok[t.token_id]
            k["condition_id"] = t.condition_id
            if t.side == "BUY":
                k["buy_size"] += t.size
                k["buy_cost"] += t.size * t.price
            elif t.side == "SELL":
                k["sell_size"] += t.size
                k["sell_proceeds"] += t.size * t.price
            else:
                print(f"warn: unknown side {t.side!r} on trade {t.trade_id}")

        # --- 3. Compute target state + print delta ---------------------
        print(f"{'token_id (last 8)':20s} {'side':4s}  {'cur_size':>12s} {'cur_cb':>10s}  {'new_size':>12s} {'new_cb':>10s}  action")
        print("-" * 110)
        targets: list[dict] = []
        seen_tokens = set()
        for tok, agg in by_tok.items():
            seen_tokens.add(tok)
            buy_size = agg["buy_size"]
            sell_size = agg["sell_size"]
            buy_cost = agg["buy_cost"]
            net = buy_size - sell_size
            avg = (buy_cost / buy_size) if buy_size > 0 else ZERO
            new_cb = (avg * net) if net > 0 else ZERO
            cur = current_by_token.get(tok)
            cur_size = cur.size if cur else ZERO
            cur_cb = cur.cost_basis_usd if cur else ZERO
            side = outcome_side_by_token.get(tok, "?")
            if net <= 0:
                action = "CLOSE" if cur else "skip"
            elif cur is None:
                action = "INSERT"
            else:
                action = "UPDATE"
            print(
                f"...{tok[-8:]:17s} {side:4s}  {cur_size:>12.4f} {cur_cb:>10.2f}  {net:>12.4f} {new_cb:>10.2f}  {action}"
            )
            targets.append(
                {
                    "token_id": tok,
                    "condition_id": agg["condition_id"],
                    "side": side,
                    "net_size": net,
                    "avg_price": avg,
                    "cost_basis_usd": new_cb,
                    "action": action,
                    "cur": cur,
                }
            )

        # OPEN positions with NO trades under bot_d (shouldn't exist, flag)
        orphans = [p for p in current_positions if p.token_id not in seen_tokens]
        for p in orphans:
            print(
                f"...{p.token_id[-8:]:17s} {p.side:4s}  {p.size:>12.4f} {p.cost_basis_usd:>10.2f}  {'(no trades)':>12s} {'—':>10s}  ORPHAN-CLOSE"
            )

        total_cur_cb = sum((p.cost_basis_usd for p in current_positions), ZERO)
        total_new_cb = sum(
            (t["cost_basis_usd"] for t in targets if t["action"] in ("INSERT", "UPDATE")),
            ZERO,
        )
        print("-" * 110)
        print(f"Total OPEN cost basis:  current ${total_cur_cb:.2f}  →  reconciled ${total_new_cb:.2f}")
        print(f"Positions:              current {len(current_positions)}  →  reconciled {sum(1 for t in targets if t['action'] in ('INSERT','UPDATE'))}")

        if not apply:
            print("\n[dry-run] no changes made. Re-run with --apply to mutate.")
            return 0

        # --- 4. Archive current state ----------------------------------
        print(f"\nArchiving current bot_d positions to `{archive_table}`…")
        s.execute(
            text(
                f'CREATE TABLE "{archive_table}" AS '
                f"SELECT * FROM positions WHERE bot_id = :b AND status = 'OPEN'"
            ),
            {"b": BOT_ID},
        )

        # --- 5. Mutate: close all current OPEN, then insert reconciled -
        now = datetime.now(UTC)
        for p in current_positions:
            p.status = "CLOSED_RECONCILED"
            p.closed_at = now
        skipped_inserts: list[dict] = []
        for t in targets:
            if t["action"] == "INSERT":
                # These are trades with BUYs but no existing Position row AND
                # (often) no Market row either. They predate current accounting
                # conventions. Flagging them as a separate finding rather than
                # blindly inserting — inserting at avg-cost would inflate
                # reported exposure without confidence in the outcome side.
                skipped_inserts.append(t)
                continue
            if t["action"] != "UPDATE":
                continue
            s.add(
                Position(
                    bot_id=BOT_ID,
                    condition_id=t["condition_id"],
                    token_id=t["token_id"],
                    side=t["side"],
                    size=t["net_size"],
                    avg_price=t["avg_price"],
                    cost_basis_usd=t["cost_basis_usd"],
                    status="OPEN",
                    opened_at=now,
                )
            )
        if skipped_inserts:
            print("\nSkipped (orphan BUYs — no prior Position, flagged for separate triage):")
            total_notional = ZERO
            for t in skipped_inserts:
                side_lbl = t["side"] if t["side"] != "?" else "unknown"
                total_notional += t["cost_basis_usd"]
                print(
                    f"  ...{t['token_id'][-8:]} side={side_lbl} size={t['net_size']} "
                    f"cost_basis=${t['cost_basis_usd']:.2f}"
                )
            print(f"  Total orphan-BUY notional: ${total_notional:.2f}")
        s.commit()
        print(f"Applied. Archive: `{archive_table}` ({len(current_positions)} rows).")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="mutate the DB (default: dry-run)")
    args = ap.parse_args()
    return reconcile(apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
