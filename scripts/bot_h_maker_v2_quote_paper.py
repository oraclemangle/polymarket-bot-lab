#!/usr/bin/env python3
"""Bot H Maker V2 quote-paper simulator.

Writes paper-only maker quote/fill rows into `maker_recorder.db`.
It reads the recorder's markets and pm_events tables, posts one
static paper SELL-YES quote per eligible target-cell market, marks a
fill when a future taker BUY print trades at or above our quote, and
settles filled quotes when the recorder's resolution columns are set.

No CLOB client, no wallet keys, no live orders.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bots.bot_h_maker_v2.config import ACTIVE_QUOTE_CELLS

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "maker_recorder.db"

SCHEMA_SQL = """
PRAGMA busy_timeout=10000;

CREATE TABLE IF NOT EXISTS maker_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    posted_at_ms INTEGER NOT NULL,
    cancelled_at_ms INTEGER,
    condition_id TEXT NOT NULL,
    yes_token_id TEXT NOT NULL,
    side TEXT NOT NULL DEFAULT 'SELL_YES',
    quoted_price REAL NOT NULL,
    quoted_size_shares REAL NOT NULL,
    quoted_size_usd REAL NOT NULL,
    cell_label TEXT NOT NULL,
    cancelled_reason TEXT
);
CREATE INDEX IF NOT EXISTS ix_maker_quotes_token_time
    ON maker_quotes(yes_token_id, posted_at_ms);
CREATE INDEX IF NOT EXISTS ix_maker_quotes_cell
    ON maker_quotes(cell_label);
CREATE UNIQUE INDEX IF NOT EXISTS ux_maker_quotes_condition_once
    ON maker_quotes(condition_id);

CREATE TABLE IF NOT EXISTS maker_paper_fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filled_at_ms INTEGER NOT NULL,
    quote_id INTEGER NOT NULL REFERENCES maker_quotes(id),
    triggering_pm_event_id INTEGER NOT NULL REFERENCES pm_events(id),
    fill_price REAL NOT NULL,
    fill_size_shares REAL NOT NULL,
    fill_size_usd REAL NOT NULL,
    yes_won INTEGER,
    realised_pnl_usd REAL,
    builder_rebate_usd REAL,
    net_pnl_usd REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_maker_paper_fills_quote
    ON maker_paper_fills(quote_id);
CREATE INDEX IF NOT EXISTS ix_paper_fills_time
    ON maker_paper_fills(filled_at_ms);

CREATE TABLE IF NOT EXISTS maker_quote_paper_run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    quotes_posted INTEGER NOT NULL,
    fills_marked INTEGER NOT NULL,
    quotes_cancelled INTEGER NOT NULL,
    fills_settled INTEGER NOT NULL,
    notes TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"recorder DB not found: {path}")
    con = sqlite3.connect(str(path), timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA_SQL)
    return con


def now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def cell_for(category: str, price: float) -> str | None:
    for cell in ACTIVE_QUOTE_CELLS:
        if cell.contains(category, cell.price_min.__class__(str(price))):
            return cell.label
    return None


def _payload_price(payload_json: str) -> float | None:
    try:
        payload = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError):
        return None
    for key in ("price", "best_ask", "ask"):
        if key in payload:
            try:
                return float(payload[key])
            except (TypeError, ValueError):
                return None
    if "asks" in payload:
        try:
            asks = [float(a["price"]) for a in payload.get("asks") or []]
        except (TypeError, ValueError, KeyError):
            asks = []
        if asks:
            return min(asks)
    return None


def latest_yes_price(con: sqlite3.Connection, yes_token_id: str, fallback: float | None) -> float | None:
    rows = con.execute(
        """
        SELECT payload_json
        FROM pm_events
        WHERE asset_id=?
          AND event_type IN ('book', 'best_bid_ask', 'price_change', 'last_trade_price')
        ORDER BY received_at_ms DESC
        LIMIT 50
        """,
        (yes_token_id,),
    ).fetchall()
    for row in rows:
        price = _payload_price(row["payload_json"])
        if price is not None and 0 < price < 1:
            return price
    return fallback


def post_quotes(con: sqlite3.Connection, *, quote_size_usd: float, per_cell_cap: int) -> int:
    ts = now_ms()
    posted = 0
    active_by_cell = {
        row["cell_label"]: int(row["n"] or 0)
        for row in con.execute(
            """
            SELECT cell_label, COUNT(*) AS n
            FROM maker_quotes
            WHERE cancelled_at_ms IS NULL
            GROUP BY cell_label
            """
        )
    }
    rows = con.execute(
        """
        SELECT condition_id, yes_token_id, category, initial_yes_price
        FROM markets
        WHERE COALESCE(status, 'ACTIVE') = 'ACTIVE'
          AND yes_won IS NULL
        ORDER BY COALESCE(volume_24h_usd, 0) DESC, last_seen_at_ms DESC
        """
    ).fetchall()
    for row in rows:
        if con.execute(
            "SELECT 1 FROM maker_quotes WHERE condition_id=?",
            (row["condition_id"],),
        ).fetchone():
            continue
        try:
            fallback = float(row["initial_yes_price"]) if row["initial_yes_price"] is not None else None
        except (TypeError, ValueError):
            fallback = None
        price = latest_yes_price(con, str(row["yes_token_id"]), fallback)
        if price is None or not (0 < price < 1):
            continue
        cell = cell_for(str(row["category"]), price)
        if cell is None:
            continue
        if int(active_by_cell.get(cell, 0)) >= per_cell_cap:
            continue
        shares = quote_size_usd / price
        cur = con.execute(
            """
            INSERT OR IGNORE INTO maker_quotes (
                posted_at_ms, condition_id, yes_token_id, side, quoted_price,
                quoted_size_shares, quoted_size_usd, cell_label
            )
            VALUES (?, ?, ?, 'SELL_YES', ?, ?, ?, ?)
            """,
            (
                ts,
                row["condition_id"],
                row["yes_token_id"],
                price,
                shares,
                quote_size_usd,
                cell,
            ),
        )
        if cur.rowcount:
            active_by_cell[cell] = int(active_by_cell.get(cell, 0)) + 1
            posted += 1
    return posted


def _event_trade(payload_json: str) -> tuple[str, float, float] | None:
    try:
        payload = json.loads(payload_json)
    except (TypeError, json.JSONDecodeError):
        return None
    side = str(payload.get("side") or "").upper()
    if side != "BUY":
        return None
    try:
        price = float(payload.get("price"))
        size = float(payload.get("size"))
    except (TypeError, ValueError):
        return None
    if price <= 0 or size <= 0:
        return None
    return side, price, size


def mark_fills(con: sqlite3.Connection) -> int:
    filled = 0
    quotes = con.execute(
        """
        SELECT id, posted_at_ms, yes_token_id, quoted_price, quoted_size_shares
        FROM maker_quotes
        WHERE cancelled_at_ms IS NULL
        """
    ).fetchall()
    for q in quotes:
        events = con.execute(
            """
            SELECT id, received_at_ms, payload_json
            FROM pm_events
            WHERE asset_id=?
              AND event_type='last_trade_price'
              AND received_at_ms > ?
            ORDER BY received_at_ms ASC
            LIMIT 100
            """,
            (q["yes_token_id"], int(q["posted_at_ms"])),
        ).fetchall()
        for event in events:
            trade = _event_trade(event["payload_json"])
            if trade is None:
                continue
            _side, price, size = trade
            if price < float(q["quoted_price"]):
                continue
            fill_shares = min(float(q["quoted_size_shares"]), size)
            fill_usd = fill_shares * float(q["quoted_price"])
            con.execute(
                """
                INSERT OR IGNORE INTO maker_paper_fills (
                    filled_at_ms, quote_id, triggering_pm_event_id,
                    fill_price, fill_size_shares, fill_size_usd
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(event["received_at_ms"]),
                    int(q["id"]),
                    int(event["id"]),
                    float(q["quoted_price"]),
                    fill_shares,
                    fill_usd,
                ),
            )
            con.execute(
                """
                UPDATE maker_quotes
                SET cancelled_at_ms=?, cancelled_reason='fill'
                WHERE id=? AND cancelled_at_ms IS NULL
                """,
                (int(event["received_at_ms"]), int(q["id"])),
            )
            filled += 1
            break
    return filled


def cancel_resolved_and_drifted(con: sqlite3.Connection, *, drift_cents: float) -> int:
    cancelled = 0
    ts = now_ms()
    rows = con.execute(
        """
        SELECT q.id, q.yes_token_id, q.cell_label, q.quoted_price,
               m.yes_won, m.category
        FROM maker_quotes q
        JOIN markets m ON m.condition_id=q.condition_id
        WHERE q.cancelled_at_ms IS NULL
        """
    ).fetchall()
    cell_upper = {cell.label: float(cell.price_max) for cell in ACTIVE_QUOTE_CELLS}
    for row in rows:
        reason = None
        if row["yes_won"] is not None:
            reason = "market_resolved"
        else:
            latest = latest_yes_price(con, str(row["yes_token_id"]), float(row["quoted_price"]))
            if latest is not None and latest > cell_upper.get(row["cell_label"], 1.0) + drift_cents:
                reason = "price_drift"
        if not reason:
            continue
        con.execute(
            """
            UPDATE maker_quotes
            SET cancelled_at_ms=?, cancelled_reason=?
            WHERE id=? AND cancelled_at_ms IS NULL
            """,
            (ts, reason, int(row["id"])),
        )
        cancelled += 1
    return cancelled


def settle_fills(con: sqlite3.Connection) -> int:
    settled = 0
    rows = con.execute(
        """
        SELECT f.id, f.fill_price, f.fill_size_shares, q.condition_id, m.yes_won, m.category
        FROM maker_paper_fills f
        JOIN maker_quotes q ON q.id=f.quote_id
        JOIN markets m ON m.condition_id=q.condition_id
        WHERE f.yes_won IS NULL
          AND m.yes_won IS NOT NULL
        """
    ).fetchall()
    for row in rows:
        price = float(row["fill_price"])
        shares = float(row["fill_size_shares"])
        yes_won = int(row["yes_won"])
        realised = (price - 1.0) * shares if yes_won == 1 else price * shares
        rebate = 0.030 * price * (1.0 - price) * 0.25 * shares
        con.execute(
            """
            UPDATE maker_paper_fills
            SET yes_won=?, realised_pnl_usd=?, builder_rebate_usd=?, net_pnl_usd=?
            WHERE id=?
            """,
            (yes_won, realised, rebate, realised + rebate, int(row["id"])),
        )
        settled += 1
    return settled


def run_once(
    *,
    db_path: Path,
    quote_size_usd: float,
    per_cell_cap: int,
    drift_cents: float,
) -> dict[str, Any]:
    started = datetime.now(UTC)
    con = connect(db_path)
    try:
        cancelled = cancel_resolved_and_drifted(con, drift_cents=drift_cents)
        posted = post_quotes(con, quote_size_usd=quote_size_usd, per_cell_cap=per_cell_cap)
        fills = mark_fills(con)
        settled = settle_fills(con)
        con.execute(
            """
            INSERT INTO maker_quote_paper_run_log (
                started_at, finished_at, quotes_posted, fills_marked,
                quotes_cancelled, fills_settled, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started.isoformat(),
                datetime.now(UTC).isoformat(),
                posted,
                fills,
                cancelled,
                settled,
                f"quote_size_usd={quote_size_usd}; per_cell_cap={per_cell_cap}",
            ),
        )
        summary = con.execute(
            """
            SELECT
                COUNT(*) AS quotes,
                SUM(CASE WHEN cancelled_at_ms IS NULL THEN 1 ELSE 0 END) AS active_quotes
            FROM maker_quotes
            """
        ).fetchone()
        fill_summary = con.execute(
            """
            SELECT COUNT(*) AS fills,
                   SUM(CASE WHEN net_pnl_usd IS NOT NULL THEN 1 ELSE 0 END) AS settled_fills,
                   COALESCE(SUM(net_pnl_usd), 0) AS net_pnl,
                   COALESCE(SUM(fill_size_usd), 0) AS cost
            FROM maker_paper_fills
            """
        ).fetchone()
        con.commit()
    finally:
        con.close()
    cost = float(fill_summary["cost"] or 0)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "quotes_posted_this_run": posted,
        "fills_marked_this_run": fills,
        "quotes_cancelled_this_run": cancelled,
        "fills_settled_this_run": settled,
        "quotes": int(summary["quotes"] or 0),
        "active_quotes": int(summary["active_quotes"] or 0),
        "fills": int(fill_summary["fills"] or 0),
        "settled_fills": int(fill_summary["settled_fills"] or 0),
        "net_pnl_usd": round(float(fill_summary["net_pnl"] or 0), 2),
        "roi": round(float(fill_summary["net_pnl"] or 0) / cost, 4) if cost else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--quote-size-usd", type=float, default=5.0)
    parser.add_argument("--per-cell-cap", type=int, default=25)
    parser.add_argument("--drift-cents", type=float, default=0.05)
    args = parser.parse_args()
    report = run_once(
        db_path=args.db_path,
        quote_size_usd=args.quote_size_usd,
        per_cell_cap=args.per_cell_cap,
        drift_cents=args.drift_cents,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
