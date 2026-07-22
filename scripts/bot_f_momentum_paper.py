#!/usr/bin/env python3
"""Bot F same-side momentum paper ledger.

Promotes the 2026-05-08 Bot F crowd-momentum PASS cells into a paper-only
forward ledger. It reads Bot F `mirror_signals`, records executable BUY-side
same-token entries for the strongest PASS-cell slices, and marks each entry
30 minutes later using public trade prints.

No wallet key is loaded. No CLOB client is constructed. No order is placed.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.research.bot_f_anti_crowd_join_diagnostic import (  # noqa: E402
    fetch_market_trades,
    nearest_trade_price,
    parse_dt,
    signal_time,
)
from scripts.research.bot_f_crowd_momentum_ev_report import (  # noqa: E402
    bucket_age,
    bucket_price,
    bucket_size,
    classify_category,
    payload,
)
from scripts.research.math_formula_common import connect_ro, table_exists, to_float  # noqa: E402

DEFAULT_BOT_F_DB = REPO_ROOT / "data" / "bot_f.db"
DEFAULT_PAPER_DB = REPO_ROOT / "data" / "bot_f_momentum_paper.db"
DEFAULT_HORIZON_SEC = 1800
DEFAULT_TOLERANCE_SEC = 300
DEFAULT_SIZE_USD = 5.0
DEFAULT_COST_CENTS = 1.0


@dataclass(frozen=True)
class Candidate:
    signal_id: int
    signal_at: datetime
    detected_at: datetime
    wallet: str
    condition_id: str
    token_id: str
    side: str
    price: float
    size_shares_source: float
    category: str
    price_bucket: str
    signal_age_bucket: str
    trade_size_bucket: str
    cells: tuple[str, ...]


def _utc_sql(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


def _init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_signal_id INTEGER NOT NULL UNIQUE,
            entered_at TEXT NOT NULL,
            signal_at TEXT NOT NULL,
            detected_at TEXT NOT NULL,
            wallet TEXT NOT NULL,
            condition_id TEXT NOT NULL,
            token_id TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            size_shares REAL NOT NULL,
            size_usd REAL NOT NULL,
            cost_cents REAL NOT NULL,
            cells_json TEXT NOT NULL,
            status TEXT NOT NULL,
            exit_due_at TEXT NOT NULL,
            exit_checked_at TEXT,
            exit_price REAL,
            fee_usd REAL,
            pnl_usd REAL,
            roi REAL,
            close_reason TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS run_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            candidates INTEGER NOT NULL,
            inserted INTEGER NOT NULL,
            closed INTEGER NOT NULL,
            skipped_sell INTEGER NOT NULL,
            notes TEXT
        )
        """
    )
    con.commit()
    return con


def _match_cells(
    *,
    category: str,
    price_bucket: str,
    signal_age_bucket: str,
    trade_size_bucket: str,
) -> tuple[str, ...]:
    cells: list[str] = []
    if category == "sports":
        cells.append("sports_1800s_same_side_1c")
    if price_bucket == "25c-50c":
        cells.append("price_25c_50c_1800s_same_side_1c")
    if signal_age_bucket == "90s-5m":
        cells.append("age_90s_5m_1800s_same_side_1c")
    if trade_size_bucket == "<100":
        cells.append("size_under_100_1800s_same_side_1c")
    return tuple(cells)


def load_candidates(bot_f_db: Path, *, since: datetime, limit: int) -> tuple[list[Candidate], int]:
    if not bot_f_db.exists():
        return [], 0
    skipped_sell = 0
    out: list[Candidate] = []
    with connect_ro(bot_f_db) as con:
        if not table_exists(con, "mirror_signals"):
            return [], 0
        rows = con.execute(
            """
            SELECT id, detected_at, wallet, condition_id, token_id, side, price,
                   size_shares, whale_tx_ts, signal_age_ms, raw_payload
            FROM mirror_signals
            WHERE detected_at >= ?
            ORDER BY detected_at ASC
            LIMIT ?
            """,
            (_utc_sql(since), int(limit)),
        ).fetchall()
    for row in rows:
        side = str(row["side"] or "").upper()
        if side != "BUY":
            skipped_sell += 1
            continue
        detected = parse_dt(row["detected_at"])
        sig_at = signal_time(row)
        price = to_float(row["price"])
        source_size = to_float(row["size_shares"], 0.0) or 0.0
        token_id = str(row["token_id"] or "")
        condition_id = str(row["condition_id"] or "")
        if detected is None or sig_at is None or price is None or price <= 0 or price >= 1:
            continue
        if not token_id or not condition_id:
            continue
        raw = payload(row["raw_payload"])
        text = " ".join(
            str(raw.get(k) or "")
            for k in ("title", "slug", "event_slug", "eventSlug", "outcome")
        )
        age_ms = to_float(row["signal_age_ms"])
        age_sec = age_ms / 1000.0 if age_ms is not None else None
        category = classify_category(text)
        price_bucket = bucket_price(price)
        signal_age_bucket = bucket_age(age_sec)
        trade_size_bucket = bucket_size(source_size)
        cells = _match_cells(
            category=category,
            price_bucket=price_bucket,
            signal_age_bucket=signal_age_bucket,
            trade_size_bucket=trade_size_bucket,
        )
        if not cells:
            continue
        out.append(
            Candidate(
                signal_id=int(row["id"]),
                signal_at=sig_at,
                detected_at=detected,
                wallet=str(row["wallet"] or "").lower(),
                condition_id=condition_id,
                token_id=token_id,
                side=side,
                price=float(price),
                size_shares_source=float(source_size),
                category=category,
                price_bucket=price_bucket,
                signal_age_bucket=signal_age_bucket,
                trade_size_bucket=trade_size_bucket,
                cells=cells,
            )
        )
    return out, skipped_sell


def insert_candidates(
    con: sqlite3.Connection,
    candidates: list[Candidate],
    *,
    size_usd: float,
    cost_cents: float,
    horizon_sec: int,
) -> int:
    inserted = 0
    now = datetime.now(UTC)
    for c in candidates:
        shares = size_usd / c.price
        exit_due = c.signal_at + timedelta(seconds=horizon_sec)
        cur = con.execute(
            "SELECT 1 FROM paper_entries WHERE source_signal_id = ?",
            (c.signal_id,),
        ).fetchone()
        if cur:
            continue
        con.execute(
            """
            INSERT INTO paper_entries (
                source_signal_id, entered_at, signal_at, detected_at, wallet,
                condition_id, token_id, side, entry_price, size_shares, size_usd,
                cost_cents, cells_json, status, exit_due_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
            """,
            (
                c.signal_id,
                _utc_sql(now),
                _utc_sql(c.signal_at),
                _utc_sql(c.detected_at),
                c.wallet,
                c.condition_id,
                c.token_id,
                c.side,
                c.price,
                shares,
                size_usd,
                cost_cents,
                json.dumps(list(c.cells), separators=(",", ":")),
                _utc_sql(exit_due),
            ),
        )
        inserted += 1
    con.commit()
    return inserted


def close_due_entries(
    con: sqlite3.Connection,
    *,
    tolerance_sec: int,
    api_limit: int,
    api_max_pages: int,
    api_sleep_sec: float,
) -> int:
    now = datetime.now(UTC)
    due = con.execute(
        """
        SELECT *
        FROM paper_entries
        WHERE status = 'OPEN'
          AND exit_due_at <= ?
        ORDER BY exit_due_at ASC
        """,
        (_utc_sql(now),),
    ).fetchall()
    closed = 0
    trades_cache: dict[str, list[dict[str, Any]]] = {}
    for row in due:
        condition_id = str(row["condition_id"])
        exit_due = parse_dt(row["exit_due_at"])
        signal_at = parse_dt(row["signal_at"])
        if exit_due is None or signal_at is None:
            continue
        if condition_id not in trades_cache:
            stop_before = int(signal_at.timestamp()) - tolerance_sec
            trades, error = fetch_market_trades(
                condition_id,
                limit=api_limit,
                max_pages=api_max_pages,
                sleep_sec=api_sleep_sec,
                stop_before_ts=stop_before,
            )
            if error:
                continue
            trades_cache[condition_id] = trades
        exit_price, exit_ts = nearest_trade_price(
            trades_cache[condition_id],
            token_id=str(row["token_id"]),
            target_ts=int(exit_due.timestamp()),
            tolerance_sec=tolerance_sec,
        )
        if exit_price is None:
            continue
        entry_price = float(row["entry_price"])
        shares = float(row["size_shares"])
        fee_usd = (float(row["cost_cents"]) / 100.0) * shares
        pnl = (float(exit_price) - entry_price) * shares - fee_usd
        cost = entry_price * shares
        roi = pnl / cost if cost > 0 else 0.0
        close_dt = datetime.fromtimestamp(int(exit_ts or exit_due.timestamp()), tz=UTC)
        con.execute(
            """
            UPDATE paper_entries
            SET status='CLOSED',
                exit_checked_at=?,
                exit_price=?,
                fee_usd=?,
                pnl_usd=?,
                roi=?,
                close_reason='horizon_1800s_public_trade'
            WHERE id=?
            """,
            (_utc_sql(close_dt), float(exit_price), fee_usd, pnl, roi, int(row["id"])),
        )
        closed += 1
    con.commit()
    return closed


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = datetime.now(UTC)
    con = _init_db(Path(args.paper_db))
    since = datetime.now(UTC) - timedelta(hours=float(args.lookback_hours))
    candidates, skipped_sell = load_candidates(Path(args.bot_f_db), since=since, limit=args.limit)
    inserted = insert_candidates(
        con,
        candidates,
        size_usd=float(args.size_usd),
        cost_cents=float(args.cost_cents),
        horizon_sec=int(args.horizon_sec),
    )
    closed = close_due_entries(
        con,
        tolerance_sec=int(args.tolerance_sec),
        api_limit=int(args.api_limit),
        api_max_pages=int(args.api_max_pages),
        api_sleep_sec=float(args.api_sleep_sec),
    )
    finished = datetime.now(UTC)
    con.execute(
        """
        INSERT INTO run_log (
            started_at, finished_at, candidates, inserted, closed, skipped_sell, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _utc_sql(started),
            _utc_sql(finished),
            len(candidates),
            inserted,
            closed,
            skipped_sell,
            "PASS-cell BUY-only same-side momentum paper",
        ),
    )
    con.commit()
    summary_row = con.execute(
        """
        SELECT COUNT(*) AS n,
               SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END) AS closed,
               SUM(CASE WHEN status='CLOSED' AND pnl_usd > 0 THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN status='CLOSED' THEN pnl_usd ELSE 0 END) AS pnl,
               SUM(CASE WHEN status='CLOSED' THEN size_usd ELSE 0 END) AS cost
        FROM paper_entries
        """
    ).fetchone()
    out = {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "candidates": len(candidates),
        "inserted": inserted,
        "closed_this_run": closed,
        "skipped_sell": skipped_sell,
        "entries_total": int(summary_row["n"] or 0),
        "closed_total": int(summary_row["closed"] or 0),
        "wins_total": int(summary_row["wins"] or 0),
        "pnl_total": float(summary_row["pnl"] or 0.0),
        "roi_total": (
            float(summary_row["pnl"] or 0.0) / float(summary_row["cost"] or 1.0)
            if float(summary_row["cost"] or 0.0) > 0
            else 0.0
        ),
    }
    con.close()
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--bot-f-db", default=str(DEFAULT_BOT_F_DB))
    p.add_argument("--paper-db", default=str(DEFAULT_PAPER_DB))
    p.add_argument("--lookback-hours", type=float, default=6.0)
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--size-usd", type=float, default=DEFAULT_SIZE_USD)
    p.add_argument("--cost-cents", type=float, default=DEFAULT_COST_CENTS)
    p.add_argument("--horizon-sec", type=int, default=DEFAULT_HORIZON_SEC)
    p.add_argument("--tolerance-sec", type=int, default=DEFAULT_TOLERANCE_SEC)
    p.add_argument("--api-limit", type=int, default=200)
    p.add_argument("--api-max-pages", type=int, default=5)
    p.add_argument("--api-sleep-sec", type=float, default=0.1)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(json.dumps(run(args), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
