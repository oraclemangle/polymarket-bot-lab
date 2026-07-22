"""One-off backfill: reconstruct Bot E positions + P&L from trade history.

Context (2026-04-17): Bot E ran 226 paper fills today but the
simulate_paper_fills path silently no-opped on position creation due to a
side-string mismatch (BUY_YES vs BUY). Result: 226 Trade rows with blank
`condition_id`, zero Position rows, zero pnl_snapshots rows. The forward
pipeline was fixed in a separate commit; this script recovers the past.

Steps:
  1. Backfill `condition_id` on bot_e trades via the Order row's copy.
  2. Reconstruct Position rows by replaying trades per (token_id, side).
  3. Mark-to-market using recorder DB latest prices, compute realised +
     unrealised, write one pnl_snapshots row for today.

The script is idempotent: re-running after a successful run is safe.
Positions that already exist (from the forward-fix pipeline on new fills)
are skipped. pnl_snapshots is upserted by (bot_id, date).

Run on the bot host:
    pct exec <ctid> -- sudo -u bot python3 scripts/backfill_bot_e_positions.py --apply

Dry-run first (reads + prints, no writes):
    pct exec <ctid> -- sudo -u bot python3 scripts/backfill_bot_e_positions.py
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

BOT_ID = "bot_e"


@dataclass
class ReconstructedPosition:
    bot_id: str
    condition_id: str
    token_id: str
    side: str          # YES or NO (Position convention)
    size: Decimal
    avg_price: Decimal
    cost_basis_usd: Decimal
    status: str        # OPEN or CLOSED
    opened_at: str
    closed_at: str | None


def _d(v):
    return Decimal(str(v)) if v is not None else Decimal("0")


def backfill_condition_ids(main_db: sqlite3.Connection, apply: bool) -> int:
    """UPDATE trades.condition_id from orders.condition_id for bot_e.

    Returns rows affected (or would-be-affected in dry-run).
    """
    cur = main_db.cursor()
    # Count rows that would change.
    cur.execute("""
        SELECT COUNT(*) FROM trades t
        JOIN orders o ON o.order_id = t.order_id
        WHERE t.bot_id = ? AND (t.condition_id IS NULL OR t.condition_id = '')
          AND o.condition_id IS NOT NULL AND o.condition_id != ''
    """, (BOT_ID,))
    n = cur.fetchone()[0]

    if apply and n > 0:
        cur.execute("""
            UPDATE trades SET condition_id = (
                SELECT o.condition_id FROM orders o
                WHERE o.order_id = trades.order_id
            )
            WHERE bot_id = ? AND (condition_id IS NULL OR condition_id = '')
              AND order_id IN (
                SELECT order_id FROM orders
                WHERE condition_id IS NOT NULL AND condition_id != ''
              )
        """, (BOT_ID,))
        main_db.commit()

    return n


def reconstruct_positions(main_db: sqlite3.Connection) -> list[ReconstructedPosition]:
    """Replay trades per (token_id, side) to compute net position."""
    cur = main_db.cursor()
    cur.execute("""
        SELECT condition_id, token_id, side, price, size, fee_usd, filled_at
        FROM trades WHERE bot_id = ?
        ORDER BY filled_at ASC
    """, (BOT_ID,))
    trades = cur.fetchall()

    # Group by (token_id) — side on Position is derived from token→market mapping,
    # but for Bot E YES-side buys land on yes_token, NO-side on no_token. So
    # token_id uniquely identifies one position entity per bot.
    groups: dict[str, dict] = defaultdict(lambda: {
        "condition_id": "",
        "token_id": "",
        "buys_size": Decimal("0"),
        "buys_cost": Decimal("0"),
        "sells_size": Decimal("0"),
        "sells_proceeds": Decimal("0"),
        "sell_fees": Decimal("0"),
        "first_ts": None,
        "last_sell_ts": None,
        "yes_or_no": None,   # derived from side string
    })
    for cid, tok, side, price, size, fee_usd, filled_at in trades:
        g = groups[tok]
        g["condition_id"] = g["condition_id"] or (cid or "")
        g["token_id"] = tok
        g["first_ts"] = g["first_ts"] or filled_at

        # Side: BUY_YES / BUY_NO / SELL_YES / SELL_NO / BUY / SELL
        s = side or ""
        is_buy = s.startswith("BUY")
        is_sell = s.startswith("SELL")
        if g["yes_or_no"] is None:
            if "_YES" in s or s == "BUY":
                # Default assumption for historical Bot A/B ambiguity is YES;
                # Bot E we're specifically handling is explicit.
                g["yes_or_no"] = "YES" if ("_YES" in s or s == "BUY") else "NO"
            elif "_NO" in s:
                g["yes_or_no"] = "NO"

        px, sz, fee = _d(price), _d(size), _d(fee_usd)
        if is_buy:
            g["buys_size"] += sz
            g["buys_cost"] += px * sz + fee
        elif is_sell:
            g["sells_size"] += sz
            g["sells_proceeds"] += px * sz
            g["sell_fees"] += fee
            g["last_sell_ts"] = filled_at

    results: list[ReconstructedPosition] = []
    for tok, g in groups.items():
        net_size = g["buys_size"] - g["sells_size"]
        # Re-compute avg_price on the open portion. After a partial close,
        # avg_price on what remains is unchanged (FIFO cost-basis proportional).
        avg_price = (
            g["buys_cost"] / g["buys_size"] if g["buys_size"] > 0 else Decimal("0")
        )
        # Cost basis on open portion = avg_price × open_size
        cost_basis = (avg_price * net_size).quantize(Decimal("0.00000001"))
        # Determine side (YES/NO). If tokens weren't tagged in side string,
        # we can look up markets later in mark-to-market step.
        position_side = g["yes_or_no"] or "YES"
        status = "OPEN" if net_size > 0 else "CLOSED"
        results.append(ReconstructedPosition(
            bot_id=BOT_ID,
            condition_id=g["condition_id"],
            token_id=tok,
            side=position_side,
            size=net_size,
            avg_price=avg_price,
            cost_basis_usd=cost_basis,
            status=status,
            opened_at=g["first_ts"],
            closed_at=g["last_sell_ts"] if status == "CLOSED" else None,
        ))
    return results


def refine_position_side(
    main_db: sqlite3.Connection,
    recorder_db_path: Path,
    positions: list[ReconstructedPosition],
) -> None:
    """Update position.side (YES/NO) by cross-referencing the token_id
    against the recorder's markets table or main.db markets table."""
    cur = main_db.cursor()
    for p in positions:
        cur.execute(
            "SELECT CASE WHEN yes_token_id=? THEN 'YES' WHEN no_token_id=? THEN 'NO' END "
            "FROM markets WHERE yes_token_id=? OR no_token_id=?",
            (p.token_id, p.token_id, p.token_id, p.token_id),
        )
        row = cur.fetchone()
        if row and row[0]:
            p.side = row[0]
            continue
        # Fallback: check recorder DB
        if recorder_db_path.exists():
            try:
                r = sqlite3.connect(f"file:{recorder_db_path}?mode=ro", uri=True, timeout=2.0)
                rc = r.cursor()
                rc.execute(
                    "SELECT CASE WHEN yes_token_id=? THEN 'YES' "
                    "WHEN no_token_id=? THEN 'NO' END "
                    "FROM markets WHERE yes_token_id=? OR no_token_id=?",
                    (p.token_id, p.token_id, p.token_id, p.token_id),
                )
                rr = rc.fetchone()
                r.close()
                if rr and rr[0]:
                    p.side = rr[0]
            except Exception:
                pass


def mark_to_market(
    recorder_db_path: Path,
    main_db: sqlite3.Connection,
    positions: list[ReconstructedPosition],
) -> tuple[Decimal, Decimal]:
    """Return (unrealised_usd, open_exposure_usd) using latest recorder prices
    as the mark. Falls back to avg_price when no price is available."""
    unrealised = Decimal("0")
    exposure = Decimal("0")
    if not recorder_db_path.exists():
        for p in positions:
            if p.status == "OPEN":
                exposure += p.cost_basis_usd
        return Decimal("0"), exposure

    r = sqlite3.connect(f"file:{recorder_db_path}?mode=ro", uri=True, timeout=2.0)
    rc = r.cursor()
    for p in positions:
        if p.status != "OPEN":
            continue
        rc.execute(
            "SELECT payload_json FROM pm_events "
            "WHERE event_type='last_trade_price' AND asset_id=? "
            "ORDER BY received_at_ms DESC LIMIT 1",
            (p.token_id,),
        )
        row = rc.fetchone()
        current_price = p.avg_price
        if row:
            try:
                import json
                payload = json.loads(row[0])
                if payload.get("price"):
                    current_price = Decimal(str(payload["price"]))
            except Exception:
                pass
        mark_value = (current_price * p.size).quantize(Decimal("0.00000001"))
        unrealised += mark_value - p.cost_basis_usd
        exposure += mark_value
    r.close()
    return unrealised, exposure


def compute_realised(main_db: sqlite3.Connection) -> Decimal:
    """Realised P&L = sell_proceeds - fees - cost-basis-of-sold-shares.
    We approximate cost-basis-of-sold-shares using the token's overall
    avg_price for simplicity (FIFO-weighted is unnecessary for bot_e which
    has no sell history yet)."""
    cur = main_db.cursor()
    cur.execute("""
        SELECT token_id,
               SUM(CASE WHEN side LIKE 'BUY%' THEN price*size ELSE 0 END) AS buy_cost,
               SUM(CASE WHEN side LIKE 'BUY%' THEN size ELSE 0 END) AS buy_size,
               SUM(CASE WHEN side LIKE 'SELL%' THEN price*size ELSE 0 END) AS sell_proc,
               SUM(CASE WHEN side LIKE 'SELL%' THEN size ELSE 0 END) AS sell_size,
               SUM(fee_usd) AS fees
        FROM trades WHERE bot_id = ? GROUP BY token_id
    """, (BOT_ID,))
    realised = Decimal("0")
    for _tok, bc, bsz, sp, ssz, fees in cur.fetchall():
        bc, bsz, sp, ssz, fees = _d(bc), _d(bsz), _d(sp), _d(ssz), _d(fees)
        if bsz == 0 or ssz == 0:
            continue
        avg_buy = bc / bsz
        cost_of_sold = avg_buy * ssz
        realised += sp - cost_of_sold - fees
    return realised.quantize(Decimal("0.01"))


def write_positions(
    main_db: sqlite3.Connection, positions: list[ReconstructedPosition], apply: bool
) -> int:
    cur = main_db.cursor()
    inserted = 0
    for p in positions:
        if p.size <= 0 and p.status == "OPEN":
            continue  # sanity
        # Skip if this position already exists (forward-pipeline wrote it).
        cur.execute(
            "SELECT id FROM positions WHERE bot_id=? AND token_id=? AND status='OPEN'",
            (BOT_ID, p.token_id),
        )
        if cur.fetchone():
            continue
        if apply:
            cur.execute(
                "INSERT INTO positions "
                "(bot_id, condition_id, token_id, side, size, avg_price, "
                " cost_basis_usd, status, opened_at, closed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (p.bot_id, p.condition_id, p.token_id, p.side,
                 str(p.size), str(p.avg_price), str(p.cost_basis_usd),
                 p.status, p.opened_at, p.closed_at),
            )
        inserted += 1
    if apply:
        main_db.commit()
    return inserted


def write_snapshot(
    main_db: sqlite3.Connection,
    realised: Decimal,
    unrealised: Decimal,
    exposure: Decimal,
    initial_usd: Decimal,
    apply: bool,
) -> bool:
    cur = main_db.cursor()
    today = datetime.now(UTC).date().isoformat()
    dd_pct = Decimal("0")
    if initial_usd > 0:
        nav = initial_usd + realised + unrealised
        if nav < initial_usd:
            dd_pct = ((initial_usd - nav) / initial_usd * Decimal("100")).quantize(Decimal("0.01"))
    if apply:
        cur.execute(
            "INSERT OR REPLACE INTO pnl_snapshots "
            "(bot_id, snapshot_date, realised_usd, unrealised_usd, open_exposure_usd, drawdown_pct) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (BOT_ID, today, str(realised), str(unrealised),
             str(exposure), str(dd_pct)),
        )
        main_db.commit()
    print(f"  snapshot: date={today} realised=${realised} unrealised=${unrealised} "
          f"exposure=${exposure} dd={dd_pct}%")
    return True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true",
                   help="Write changes (default: dry-run, reads only)")
    p.add_argument("--main-db",
                   default="data/main.db",
                   help="Path to main.db")
    p.add_argument("--recorder-db",
                   default="data/bot_e_recorder.db",
                   help="Path to bot_e_recorder.db")
    p.add_argument("--initial-bankroll-usd", default="2000",
                   help="Initial USD bankroll for drawdown % (default 2000)")
    args = p.parse_args()

    main_db_path = Path(args.main_db)
    recorder_db_path = Path(args.recorder_db)
    if not main_db_path.exists():
        print(f"ERROR: main.db not found at {main_db_path}", file=sys.stderr)
        return 2

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"=== Bot E backfill [{mode}] ===")
    print(f"main.db:     {main_db_path}")
    print(f"recorder.db: {recorder_db_path}  (exists: {recorder_db_path.exists()})")
    print()

    conn = sqlite3.connect(main_db_path)

    # Step 1: condition_id backfill
    n_cid = backfill_condition_ids(conn, args.apply)
    print(f"[1] condition_id backfill: {n_cid} trade rows "
          f"{'updated' if args.apply else 'would update'}")

    # Step 2: position reconstruction
    positions = reconstruct_positions(conn)
    refine_position_side(conn, recorder_db_path, positions)
    print(f"[2] reconstructed {len(positions)} position entities:")
    for pos in positions[:20]:
        print(f"    {pos.token_id[:20]:22} side={pos.side} "
              f"size={pos.size} avg={pos.avg_price} "
              f"cost=${pos.cost_basis_usd} status={pos.status}")
    if len(positions) > 20:
        print(f"    ... ({len(positions)-20} more)")

    n_inserted = write_positions(conn, positions, args.apply)
    print(f"    {n_inserted} position rows "
          f"{'inserted' if args.apply else 'would insert'} "
          f"(existing OPEN positions skipped)")

    # Step 3: mark-to-market + snapshot
    realised = compute_realised(conn)
    unrealised, exposure = mark_to_market(recorder_db_path, conn, positions)
    print(f"[3] P&L computation:")
    print(f"    realised   = ${realised}")
    print(f"    unrealised = ${unrealised.quantize(Decimal('0.01'))}")
    print(f"    exposure   = ${exposure.quantize(Decimal('0.01'))}")

    write_snapshot(
        conn, realised, unrealised.quantize(Decimal("0.01")),
        exposure.quantize(Decimal("0.01")),
        Decimal(args.initial_bankroll_usd), args.apply,
    )

    conn.close()
    print()
    if args.apply:
        print("=== APPLIED ===")
    else:
        print("=== DRY-RUN complete. Re-run with --apply to write changes. ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
