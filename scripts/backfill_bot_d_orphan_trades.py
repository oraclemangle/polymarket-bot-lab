#!/usr/bin/env python3
"""Backfill synthetic BUY Trade rows for bot_d Position rows that lack them.

Context (K2.6 audit 2026-04-21, finding #5): three legacy bot_d positions
have cost_basis recorded but no matching BUY Trade row, breaking the
double-entry audit trail. Realised P&L computed from trades-only vs
positions-only differs by $34.01.

Pre-Session-17 paper-fill code wrote Orders + Positions but skipped the
Trade ledger. Current code writes all three. This script is a one-shot
migration for the legacy rows — it writes a synthetic BUY Trade
reconstructed from the Position's cost_basis_usd / avg_price / size /
opened_at, tagged with ``legacy-backfill-<position_id>`` so analytics
can distinguish backfill rows from honest fills.

Method:
    For each bot_d Position (OPEN or CLOSED):
        - If a BUY Trade for (bot_id, token_id) already exists: skip.
        - Else: write a synthetic BUY Trade matching the Position's
          cost basis. filled_at = Position.opened_at. usd_gbp_rate
          comes from the most recent Trade on any bot at that time
          (paper mode, so FX fidelity is not critical).

Default mode is ``--dry-run``. Pass ``--apply`` to mutate.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from sqlalchemy import select  # noqa: E402

from core.db import Position, Trade, get_session_factory  # noqa: E402


BOT_ID = "bot_d"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="mutate the DB (default: dry-run)")
    args = ap.parse_args()

    sf = get_session_factory()
    with sf() as s:
        positions = list(s.scalars(select(Position).where(Position.bot_id == BOT_ID)).all())

        # Gather all existing BUY Trade token_ids for bot_d.
        existing_buys = set(
            s.scalars(
                select(Trade.token_id).where(
                    Trade.bot_id == BOT_ID, Trade.side == "BUY"
                )
            ).all()
        )

        needing_backfill: list[Position] = []
        for p in positions:
            if p.token_id in existing_buys:
                continue
            if p.cost_basis_usd is None or p.cost_basis_usd == Decimal("0"):
                continue
            if p.size is None or p.size <= Decimal("0"):
                continue
            needing_backfill.append(p)

        print(f"Scanned {len(positions)} bot_d positions.")
        print(f"Need backfill: {len(needing_backfill)}")
        print()
        print(f"{'pos_id':>6s} {'status':>10s} {'side':>4s} {'cid':>10s} "
              f"{'size':>10s} {'avg_px':>8s} {'cost':>8s} {'opened_at':>20s}")
        print("-" * 90)
        for p in needing_backfill:
            print(
                f"{p.id:>6d} {p.status:>10s} {p.side:>4s} "
                f"{p.condition_id[-10:]:>10s} {p.size:>10.2f} "
                f"{p.avg_price:>8.4f} {p.cost_basis_usd:>8.2f} "
                f"{str(p.opened_at)[:19]:>20s}"
            )

        if not args.apply:
            print("\n[dry-run] no changes made. Pass --apply to write.")
            return 0

        # Pick an FX rate — use the most recent bot_d trade's rate if any,
        # else 1.0 (paper-mode FX fidelity is non-critical).
        last_rate_row = s.execute(
            select(Trade.usd_gbp_rate)
            .where(Trade.bot_id == BOT_ID)
            .order_by(Trade.filled_at.desc())
            .limit(1)
        ).first()
        fx_rate = (last_rate_row[0] if last_rate_row else Decimal("0.78"))

        for p in needing_backfill:
            s.add(
                Trade(
                    trade_id=f"legacy-backfill-{p.id}",
                    bot_id=BOT_ID,
                    order_id=None,
                    condition_id=p.condition_id,
                    token_id=p.token_id,
                    side="BUY",
                    price=p.avg_price,
                    size=p.size,
                    fee_usd=Decimal("0"),
                    filled_at=p.opened_at,
                    usd_gbp_rate=fx_rate,
                    gbp_notional=(p.cost_basis_usd * fx_rate).quantize(Decimal("0.01")),
                )
            )
        s.commit()
        print(f"\nWrote {len(needing_backfill)} synthetic BUY Trade rows "
              f"(trade_id prefix=legacy-backfill-).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
