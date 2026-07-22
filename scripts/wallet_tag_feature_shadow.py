#!/usr/bin/env python3
"""Wallet-tag feature shadow paper ledger.

Copies observed BUY rows from `wallet_tag_forward.db` into a separate
paper ledger and updates outcome/P&L as settlement labels arrive. This
is not copy-trading and it does not place orders; it measures whether
the low-bot-score wallet feature keeps positive forward value.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.research.wallet_observer_report import _trade_token_is_yes

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OBSERVER_DB = REPO_ROOT / "data" / "wallet_tag_forward.db"
DEFAULT_SHADOW_DB = REPO_ROOT / "data" / "wallet_tag_feature_shadow.db"
DEFAULT_REPORT_DIR = REPO_ROOT / "data" / "reports" / "wallet_tag_feature_shadow"
DEFAULT_ELITE_SUFFIXES = ("95618e", "0dfdce", "67e9ca", "8c9c23")

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=10000;

CREATE TABLE IF NOT EXISTS paper_entries (
    entry_key TEXT PRIMARY KEY,
    wallet TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    condition_id TEXT,
    market_id TEXT,
    observed_at_s INTEGER NOT NULL,
    taker_direction TEXT NOT NULL,
    outcome TEXT,
    outcome_index INTEGER,
    token_is_yes INTEGER,
    price REAL NOT NULL,
    size_shares REAL NOT NULL,
    entry_cost_usd REAL NOT NULL,
    fee_usd REAL NOT NULL,
    settlement_label_type TEXT,
    token_won INTEGER,
    status TEXT NOT NULL,
    pnl_usd REAL,
    roi REAL,
    inserted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_wallet_tag_shadow_status
    ON paper_entries(status, observed_at_s);
CREATE INDEX IF NOT EXISTS ix_wallet_tag_shadow_condition
    ON paper_entries(condition_id);

CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    scanned_buy_rows INTEGER NOT NULL,
    upserted_entries INTEGER NOT NULL,
    closed_entries INTEGER NOT NULL,
    notes TEXT
);
"""


def _connect_ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=20)
    con.row_factory = sqlite3.Row
    return con


def _connect_shadow(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA_SQL)
    return con


def _observer_rows(
    con: sqlite3.Connection,
    *,
    min_timestamp_s: int | None,
    wallet_suffixes: tuple[str, ...] = (),
) -> list[sqlite3.Row]:
    market_cols = {
        str(row["name"])
        for row in con.execute("PRAGMA table_info(observed_markets)").fetchall()
    }
    proxy_expr = "0"
    if "proxy_settled" in market_cols:
        proxy_expr = "COALESCE(m.proxy_settled, 0)"
    params: list[Any] = []
    min_clause = ""
    if min_timestamp_s is not None:
        min_clause = " AND t.timestamp_s >= ?"
        params.append(min_timestamp_s)
    suffix_clause = ""
    suffixes = tuple(s.lower().removeprefix("0x") for s in wallet_suffixes if s.strip())
    if suffixes:
        suffix_clause = " AND (" + " OR ".join("LOWER(t.wallet) LIKE ?" for _ in suffixes) + ")"
        params.extend(f"%{suffix}" for suffix in suffixes)
    return con.execute(
        f"""
        SELECT t.wallet, t.asset_id, t.timestamp_s, t.taker_direction,
               t.price, t.token_amount, t.condition_id, t.market_id,
               t.outcome, t.outcome_index, m.yes_won, m.settled,
               {proxy_expr} AS proxy_settled
        FROM observed_trades t
        LEFT JOIN observed_markets m ON t.condition_id = m.condition_id
        WHERE t.taker_direction = 'BUY'
          AND t.price IS NOT NULL
          AND t.token_amount IS NOT NULL
          {min_clause}
          {suffix_clause}
        """
        ,
        params,
    ).fetchall()


def _entry_key(row: sqlite3.Row) -> str:
    return "|".join(
        [
            str(row["wallet"]),
            str(row["asset_id"]),
            str(row["timestamp_s"]),
            str(row["taker_direction"]),
            f"{float(row['price']):.8f}",
            f"{float(row['token_amount']):.8f}",
        ]
    )


def _entry_from_row(
    row: sqlite3.Row,
    *,
    fee_rate: float,
    now_iso: str,
    max_entry_cost_usd: float | None,
    min_entry_cost_usd: float,
) -> dict[str, Any] | None:
    token_is_yes = _trade_token_is_yes(row["outcome"], row["outcome_index"])
    if token_is_yes is None:
        return None
    price = float(row["price"])
    original_size = float(row["token_amount"])
    per_share_cost = price + price * (1.0 - price) * fee_rate
    if per_share_cost <= 0:
        return None
    size = original_size
    entry_cost = per_share_cost * size
    if max_entry_cost_usd is not None and entry_cost > max_entry_cost_usd:
        size = max_entry_cost_usd / per_share_cost
        entry_cost = per_share_cost * size
    if entry_cost < min_entry_cost_usd:
        return None
    fee = price * (1.0 - price) * fee_rate * size
    yes_won = row["yes_won"]
    status = "OPEN"
    token_won = None
    pnl = None
    roi = None
    label_type = None
    if yes_won is not None and (int(row["settled"] or 0) or int(row["proxy_settled"] or 0)):
        market_yes_won = int(yes_won)
        token_won = market_yes_won if token_is_yes else 1 - market_yes_won
        payout = float(token_won) * size
        pnl = payout - entry_cost
        roi = pnl / entry_cost if entry_cost else None
        status = "CLOSED"
        label_type = "strict" if int(row["settled"] or 0) else "proxy"
    return {
        "entry_key": _entry_key(row),
        "wallet": row["wallet"],
        "asset_id": row["asset_id"],
        "condition_id": row["condition_id"],
        "market_id": row["market_id"],
        "observed_at_s": int(row["timestamp_s"]),
        "taker_direction": row["taker_direction"],
        "outcome": row["outcome"],
        "outcome_index": row["outcome_index"],
        "token_is_yes": 1 if token_is_yes else 0,
        "price": price,
        "size_shares": size,
        "entry_cost_usd": entry_cost,
        "fee_usd": fee,
        "settlement_label_type": label_type,
        "token_won": token_won,
        "status": status,
        "pnl_usd": pnl,
        "roi": roi,
        "inserted_at": now_iso,
        "updated_at": now_iso,
    }


def _apply_paper_constraints(
    entries: list[dict[str, Any]],
    *,
    one_entry_per_wallet_market: bool,
    max_open_exposure_usd: float | None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    kept: list[dict[str, Any]] = []
    seen_wallet_markets: set[tuple[str, str]] = set()
    open_exposure = 0.0
    skipped_duplicate = 0
    skipped_exposure = 0
    for entry in sorted(entries, key=lambda item: (item["observed_at_s"], item["entry_key"])):
        wallet_market = (str(entry["wallet"]), str(entry["condition_id"] or entry["market_id"] or ""))
        if one_entry_per_wallet_market and wallet_market in seen_wallet_markets:
            skipped_duplicate += 1
            continue
        entry_cost = float(entry["entry_cost_usd"] or 0)
        is_open = entry["status"] == "OPEN"
        if (
            max_open_exposure_usd is not None
            and is_open
            and open_exposure + entry_cost > max_open_exposure_usd
        ):
            skipped_exposure += 1
            continue
        kept.append(entry)
        seen_wallet_markets.add(wallet_market)
        if is_open:
            open_exposure += entry_cost
    return kept, {
        "skipped_duplicate_wallet_market": skipped_duplicate,
        "skipped_open_exposure_cap": skipped_exposure,
    }


def run_once(
    *,
    observer_db: Path,
    shadow_db: Path,
    report_dir: Path,
    fee_rate: float,
    min_observed_at: datetime | None,
    wallet_suffixes: tuple[str, ...] = (),
    max_entry_cost_usd: float | None = None,
    min_entry_cost_usd: float = 0.0,
    max_open_exposure_usd: float | None = None,
    one_entry_per_wallet_market: bool = False,
) -> dict[str, Any]:
    started = datetime.now(UTC)
    obs = _connect_ro(observer_db)
    try:
        rows = _observer_rows(
            obs,
            min_timestamp_s=int(min_observed_at.timestamp()) if min_observed_at else None,
            wallet_suffixes=wallet_suffixes,
        )
    finally:
        obs.close()
    now_iso = datetime.now(UTC).isoformat()
    entries = [
        entry
        for row in rows
        if (
            entry := _entry_from_row(
                row,
                fee_rate=fee_rate,
                now_iso=now_iso,
                max_entry_cost_usd=max_entry_cost_usd,
                min_entry_cost_usd=min_entry_cost_usd,
            )
        )
        is not None
    ]
    entries, constraint_counts = _apply_paper_constraints(
        entries,
        one_entry_per_wallet_market=one_entry_per_wallet_market,
        max_open_exposure_usd=max_open_exposure_usd,
    )
    con = _connect_shadow(shadow_db)
    upserted = 0
    try:
        if min_observed_at is not None:
            con.execute(
                "DELETE FROM paper_entries WHERE observed_at_s < ?",
                (int(min_observed_at.timestamp()),),
            )
        for entry in entries:
            con.execute(
                """
                INSERT INTO paper_entries (
                    entry_key, wallet, asset_id, condition_id, market_id,
                    observed_at_s, taker_direction, outcome, outcome_index,
                    token_is_yes, price, size_shares, entry_cost_usd, fee_usd,
                    settlement_label_type, token_won, status, pnl_usd, roi,
                    inserted_at, updated_at
                )
                VALUES (
                    :entry_key, :wallet, :asset_id, :condition_id, :market_id,
                    :observed_at_s, :taker_direction, :outcome, :outcome_index,
                    :token_is_yes, :price, :size_shares, :entry_cost_usd, :fee_usd,
                    :settlement_label_type, :token_won, :status, :pnl_usd, :roi,
                    :inserted_at, :updated_at
                )
                ON CONFLICT(entry_key) DO UPDATE SET
                    settlement_label_type=excluded.settlement_label_type,
                    token_won=excluded.token_won,
                    status=excluded.status,
                    pnl_usd=excluded.pnl_usd,
                    roi=excluded.roi,
                    updated_at=excluded.updated_at
                """,
                entry,
            )
            upserted += 1
        summary = con.execute(
            """
            SELECT COUNT(*) AS n,
                   SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END) AS closed,
                   SUM(CASE WHEN status='CLOSED' AND pnl_usd > 0 THEN 1 ELSE 0 END) AS wins,
                   COALESCE(SUM(CASE WHEN status='CLOSED' THEN pnl_usd ELSE 0 END), 0) AS pnl,
                   COALESCE(SUM(CASE WHEN status='CLOSED' THEN entry_cost_usd ELSE 0 END), 0) AS cost,
                   SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS open_entries
            FROM paper_entries
            """
        ).fetchone()
        closed = int(summary["closed"] or 0)
        con.execute(
            """
            INSERT INTO run_log (
                started_at, finished_at, scanned_buy_rows, upserted_entries,
                closed_entries, notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                started.isoformat(),
                datetime.now(UTC).isoformat(),
                len(rows),
                upserted,
                closed,
                json.dumps(
                    {
                        "fee_rate": fee_rate,
                        "wallet_suffixes": wallet_suffixes,
                        "max_entry_cost_usd": max_entry_cost_usd,
                        "min_entry_cost_usd": min_entry_cost_usd,
                        "max_open_exposure_usd": max_open_exposure_usd,
                        "one_entry_per_wallet_market": one_entry_per_wallet_market,
                        **constraint_counts,
                    },
                    sort_keys=True,
                ),
            ),
        )
        con.commit()
    finally:
        con.close()
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "observer_db": str(observer_db),
        "shadow_db": str(shadow_db),
        "scanned_buy_rows": len(rows),
        "upserted_entries": upserted,
        "n_entries": int(summary["n"] or 0),
        "closed": closed,
        "wins": int(summary["wins"] or 0),
        "open_entries": int(summary["open_entries"] or 0),
        "pnl_usd": round(float(summary["pnl"] or 0), 2),
        "post_fee_roi": round(float(summary["pnl"] or 0) / float(summary["cost"]), 4)
        if float(summary["cost"] or 0)
        else 0.0,
        "min_observed_at": min_observed_at.isoformat() if min_observed_at else None,
        "wallet_suffixes": list(wallet_suffixes),
        "max_entry_cost_usd": max_entry_cost_usd,
        "min_entry_cost_usd": min_entry_cost_usd,
        "max_open_exposure_usd": max_open_exposure_usd,
        "one_entry_per_wallet_market": one_entry_per_wallet_market,
        **constraint_counts,
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observer-db", type=Path, default=DEFAULT_OBSERVER_DB)
    parser.add_argument("--shadow-db", type=Path, default=DEFAULT_SHADOW_DB)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--fee-rate", type=float, default=0.04)
    parser.add_argument(
        "--wallet-suffix",
        action="append",
        default=[],
        help="Only include wallets whose address ends with this suffix. Can be repeated.",
    )
    parser.add_argument(
        "--elite-wallet-set",
        action="store_true",
        help="Use the audited 2026-05-26 profitable wallet suffix set.",
    )
    parser.add_argument("--max-entry-cost-usd", type=float, default=None)
    parser.add_argument("--min-entry-cost-usd", type=float, default=0.0)
    parser.add_argument("--max-open-exposure-usd", type=float, default=None)
    parser.add_argument("--one-entry-per-wallet-market", action="store_true")
    parser.add_argument(
        "--min-observed-at",
        default=None,
        help="ISO timestamp lower bound for observed trade timestamps.",
    )
    args = parser.parse_args()
    min_observed_at = None
    if args.min_observed_at:
        min_observed_at = datetime.fromisoformat(args.min_observed_at.replace("Z", "+00:00"))
        if min_observed_at.tzinfo is None:
            min_observed_at = min_observed_at.replace(tzinfo=UTC)
    wallet_suffixes = tuple(args.wallet_suffix or ())
    if args.elite_wallet_set:
        wallet_suffixes = (*wallet_suffixes, *DEFAULT_ELITE_SUFFIXES)
    report = run_once(
        observer_db=args.observer_db,
        shadow_db=args.shadow_db,
        report_dir=args.report_dir,
        fee_rate=args.fee_rate,
        min_observed_at=min_observed_at,
        wallet_suffixes=wallet_suffixes,
        max_entry_cost_usd=args.max_entry_cost_usd,
        min_entry_cost_usd=args.min_entry_cost_usd,
        max_open_exposure_usd=args.max_open_exposure_usd,
        one_entry_per_wallet_market=args.one_entry_per_wallet_market,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
