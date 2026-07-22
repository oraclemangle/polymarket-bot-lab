#!/usr/bin/env python3
"""Passive wallet observer for the bot_score_low_under_30 cohort.

Polls Polymarket Data API for new trades by wallets in
`data/wallet_tag_observer_targets.csv` and persists them locally for
forward validation of the math-found edge. Read-only HTTP polling;
no order placement, no wallet keys, no live state mutated.

Operational stance:
- No live orders (this is observation, not execution).
- No wallet keys loaded.
- Writes only to a dedicated local SQLite DB (`data/wallet_tag_forward.db`).
- Polite rate limiting (default 1 req/s).
- Polite back-off on 429/5xx.

Run modes:
- `--once`: single pass through all wallets, then exit.
- `--loop`: keep polling on `--interval-sec` cadence until interrupted.

Designed to run as a low-frequency systemd timer (e.g. every 30
minutes). The `wallet_observer_report.py` companion script builds the
forward Murphy decomposition from this DB.
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import signal
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TARGETS_CSV = REPO_ROOT / "data" / "wallet_tag_observer_targets.csv"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "wallet_tag_forward.db"

POLYMARKET_DATA_API = "https://data-api.polymarket.com"
USER_AGENT = "longshot-research-wallet-observer/1.0 (read-only research)"

LOG = logging.getLogger("wallet_observer")
_running = True


def _handle_signal(_signum: int, _frame: object) -> None:
    global _running
    _running = False
    LOG.info("wallet_observer.signal_received stopping")


def init_db(path: Path) -> sqlite3.Connection:
    """Initialise the observer DB with the schema we need."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    # The Polymarket Data API /trades endpoint does not expose
    # transaction_hash on a per-trade row, so dedup is on the
    # (wallet, asset, timestamp, side, price, size) tuple.
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS observed_trades (
            wallet TEXT NOT NULL,
            asset_id TEXT NOT NULL,
            timestamp_s INTEGER NOT NULL,
            taker_direction TEXT NOT NULL,
            price REAL NOT NULL,
            token_amount REAL NOT NULL,
            condition_id TEXT,
            market_id TEXT,
            outcome TEXT,
            outcome_index INTEGER,
            usd_amount REAL,
            settlement_price REAL,
            settlement_observed_at TEXT,
            event_slug TEXT,
            title TEXT,
            user_name TEXT,
            payload TEXT,
            ingested_at TEXT NOT NULL,
            PRIMARY KEY (wallet, asset_id, timestamp_s, taker_direction, price, token_amount)
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS ix_obs_trades_wallet_ts "
        "ON observed_trades(wallet, timestamp_s)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS ix_obs_trades_market "
        "ON observed_trades(market_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS ix_obs_trades_condition "
        "ON observed_trades(condition_id)"
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS observed_markets (
            market_id TEXT PRIMARY KEY,
            condition_id TEXT,
            question TEXT,
            event_title TEXT,
            end_date_iso TEXT,
            settled INTEGER NOT NULL DEFAULT 0,
            proxy_settled INTEGER NOT NULL DEFAULT 0,
            settlement_method TEXT,
            yes_won INTEGER,
            outcome_prices TEXT,
            payload TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS poll_log (
            wallet TEXT NOT NULL,
            polled_at TEXT NOT NULL,
            new_trade_count INTEGER NOT NULL,
            http_status INTEGER NOT NULL,
            error_msg TEXT,
            PRIMARY KEY (wallet, polled_at)
        )
        """
    )
    con.commit()
    return con


def load_targets(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"targets CSV not found: {path}")
    out: list[dict[str, Any]] = []
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            wallet = (row.get("wallet") or "").strip().lower()
            if not wallet:
                continue
            out.append(
                {
                    "wallet": wallet,
                    "user_name": row.get("user_name", ""),
                    "rank": int(row.get("rank") or 0),
                    "bot_score": int(row.get("bot_score") or 0),
                }
            )
    return out


def _fetch_wallet_trades(
    client: httpx.Client,
    wallet: str,
    *,
    after_ts: int | None,
    limit: int = 200,
) -> tuple[list[dict[str, Any]], int]:
    """Fetch recent trades for a wallet from the Polymarket Data API.

    Returns (trades, http_status). On non-2xx, returns ([], status).
    Polymarket Data API trades endpoint accepts `user` filter.
    """
    params: dict[str, Any] = {"user": wallet, "limit": limit}
    if after_ts is not None:
        # The API supports `start` epoch-seconds filter on some endpoints;
        # if unsupported, the after_ts filter is applied client-side
        # below.
        params["start"] = after_ts
    try:
        resp = client.get(f"{POLYMARKET_DATA_API}/trades", params=params)
    except httpx.HTTPError as exc:
        LOG.warning("wallet_observer.http_error wallet=%s err=%s", wallet, exc)
        return [], 0
    if resp.status_code != 200:
        return [], resp.status_code
    try:
        data = resp.json()
    except json.JSONDecodeError:
        return [], 200
    if not isinstance(data, list):
        # Some endpoints wrap in {"data": [...]}; handle both.
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        else:
            return [], 200
    return data, 200


def _persist_trade(con: sqlite3.Connection, wallet: str, t: dict[str, Any]) -> bool:
    """Insert one trade row. Returns True if newly inserted.

    The Polymarket Data API /trades schema observed 2026-05-08 has these
    fields per trade: proxyWallet, asset, conditionId, price, size,
    timestamp, side (BUY/SELL), title, eventSlug, outcome, outcomeIndex,
    name. There's no transactionHash, so we compose a PK from
    (wallet, asset, timestamp, side, price, size).
    """
    asset_id = t.get("asset") or t.get("asset_id")
    if not asset_id:
        return False
    condition_id = t.get("conditionId") or t.get("condition_id")
    ts = t.get("timestamp")
    try:
        ts_s = int(ts)
    except (TypeError, ValueError):
        return False
    price = t.get("price")
    if price is None:
        return False
    try:
        price_f = float(price)
    except (TypeError, ValueError):
        return False
    # The Polymarket Data API /trades returns `size` as TOKEN amount
    # (not USD). USD = price * size for taker fills.
    size = t.get("size") or t.get("amount")
    if size is None:
        return False
    try:
        size_f = float(size)
    except (TypeError, ValueError):
        return False
    usd_f = price_f * size_f
    side = (t.get("side") or t.get("taker_direction") or "").upper()
    if not side:
        return False
    outcome = t.get("outcome")
    outcome_index = t.get("outcomeIndex") or t.get("outcome_index")
    event_slug = t.get("eventSlug") or t.get("event_slug")
    title = t.get("title")
    user_name = t.get("name") or t.get("pseudonym")
    # Data API often returns the condition ID in `market`; Gamma's numeric
    # market id is different, so condition_id remains the settlement join key.
    market_id = t.get("market") or t.get("market_id") or condition_id
    payload = json.dumps(t, default=str)
    now_iso = datetime.now(UTC).isoformat()
    cur = con.execute(
        """
        INSERT OR IGNORE INTO observed_trades
            (wallet, asset_id, timestamp_s, taker_direction, price,
             token_amount, condition_id, market_id, outcome, outcome_index,
             usd_amount, event_slug, title, user_name, payload, ingested_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            wallet,
            str(asset_id),
            ts_s,
            side,
            price_f,
            size_f,
            str(condition_id) if condition_id is not None else None,
            str(market_id) if market_id is not None else None,
            str(outcome) if outcome is not None else None,
            int(outcome_index) if outcome_index is not None else None,
            usd_f,
            str(event_slug) if event_slug is not None else None,
            str(title) if title is not None else None,
            str(user_name) if user_name is not None else None,
            payload,
            now_iso,
        ),
    )
    return cur.rowcount > 0


def _last_seen_ts(con: sqlite3.Connection, wallet: str) -> int | None:
    row = con.execute(
        "SELECT MAX(timestamp_s) FROM observed_trades WHERE wallet = ?",
        (wallet,),
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return int(row[0])


def poll_one_wallet(
    client: httpx.Client,
    con: sqlite3.Connection,
    wallet: dict[str, Any],
) -> tuple[int, int]:
    """Fetch + persist new trades for one wallet. Returns (new_count, status)."""
    after_ts = _last_seen_ts(con, wallet["wallet"])
    trades, status = _fetch_wallet_trades(
        client, wallet["wallet"], after_ts=after_ts
    )
    new_count = 0
    for t in trades:
        # Defensive: even if `start` filter is supported, dedupe via PK.
        if _persist_trade(con, wallet["wallet"], t):
            new_count += 1
    if new_count:
        con.commit()
    polled_at = datetime.now(UTC).isoformat()
    con.execute(
        "INSERT OR REPLACE INTO poll_log "
        "(wallet, polled_at, new_trade_count, http_status, error_msg) "
        "VALUES (?, ?, ?, ?, ?)",
        (wallet["wallet"], polled_at, new_count, status, None),
    )
    con.commit()
    return new_count, status


def poll_all_wallets(
    client: httpx.Client,
    con: sqlite3.Connection,
    wallets: list[dict[str, Any]],
    *,
    rate_limit_sec: float = 1.0,
) -> dict[str, Any]:
    """One pass through all wallets with rate-limited HTTP polling."""
    started = datetime.now(UTC)
    total_new = 0
    n_errors = 0
    for w in wallets:
        if not _running:
            break
        new_count, status = poll_one_wallet(client, con, w)
        total_new += new_count
        if status >= 400 or status == 0:
            n_errors += 1
            if status == 429:
                LOG.warning("wallet_observer.rate_limited wallet=%s", w["wallet"])
                time.sleep(5.0 + rate_limit_sec)
            elif 500 <= status < 600:
                LOG.warning("wallet_observer.server_err status=%s", status)
                time.sleep(2.0 + rate_limit_sec)
        time.sleep(rate_limit_sec)
    finished = datetime.now(UTC)
    return {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_sec": (finished - started).total_seconds(),
        "wallets_polled": len(wallets),
        "new_trades_total": total_new,
        "errors": n_errors,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV))
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument(
        "--rate-limit-sec",
        type=float,
        default=1.0,
        help="Seconds between consecutive HTTP requests.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Single pass through all wallets, then exit.",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Keep polling on a fixed cadence until SIGINT.",
    )
    parser.add_argument(
        "--interval-sec",
        type=float,
        default=1800.0,
        help="Seconds between polling rounds when --loop is set.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not args.once and not args.loop:
        args.once = True

    targets = load_targets(Path(args.targets_csv))
    LOG.info("wallet_observer.startup n_wallets=%d", len(targets))

    con = init_db(Path(args.db_path))

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    with httpx.Client(timeout=30.0, headers=headers) as client:
        if args.once:
            stats = poll_all_wallets(
                client, con, targets, rate_limit_sec=args.rate_limit_sec
            )
            LOG.info("wallet_observer.once_complete %s", json.dumps(stats))
        else:
            while _running:
                stats = poll_all_wallets(
                    client, con, targets, rate_limit_sec=args.rate_limit_sec
                )
                LOG.info("wallet_observer.round_complete %s", json.dumps(stats))
                # Sleep but check _running periodically
                slept = 0.0
                while _running and slept < args.interval_sec:
                    time.sleep(min(5.0, args.interval_sec - slept))
                    slept += 5.0
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
