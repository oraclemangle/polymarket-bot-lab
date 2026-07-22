#!/usr/bin/env python3
"""Market-resolution backfill for the wallet observer DB.

Reads `observed_trades` from `data/wallet_tag_forward.db`, finds markets
that are not yet settled in `observed_markets`, and queries Polymarket
Gamma API in batches to populate the resolution side.

Read-only against Polymarket Gamma. Writes only to `observed_markets`
(and bumps `observed_trades.settlement_price` for trades whose market
just settled). No wallet keys, no order placement.

Designed to run on a slow cadence (every 6h is enough). The trade-side
observer (`wallet_observer.py`) runs more frequently.
"""
from __future__ import annotations

import argparse
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
DEFAULT_DB_PATH = REPO_ROOT / "data" / "wallet_tag_forward.db"

GAMMA_API = "https://gamma-api.polymarket.com"
USER_AGENT = (
    "longshot-research-wallet-observer-resolutions/1.0 "
    "(read-only research)"
)

LOG = logging.getLogger("wallet_observer_resolutions")
_running = True


def _handle_signal(_signum: int, _frame: object) -> None:
    global _running
    _running = False
    LOG.info("wallet_observer_resolutions.signal_received stopping")


def _connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"observer DB not found: {path}")
    con = sqlite3.connect(str(path), timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    ensure_resolution_schema(con)
    return con


def ensure_resolution_schema(con: sqlite3.Connection) -> None:
    """Add resolution audit columns to older observer DBs."""
    cols = {
        str(row["name"])
        for row in con.execute("PRAGMA table_info(observed_markets)").fetchall()
    }
    if "proxy_settled" not in cols:
        con.execute(
            "ALTER TABLE observed_markets "
            "ADD COLUMN proxy_settled INTEGER NOT NULL DEFAULT 0"
        )
    if "settlement_method" not in cols:
        con.execute("ALTER TABLE observed_markets ADD COLUMN settlement_method TEXT")
    con.commit()


def find_unresolved_markets(
    con: sqlite3.Connection,
    limit: int,
    *,
    min_trade_ts_s: int | None = None,
) -> list[dict[str, Any]]:
    """Return markets we have trades for that are not yet known-settled.

    If `min_trade_ts_s` is set, only markets with at least one trade
    after that timestamp are returned. The 7-day forward-validation
    horizon uses this to skip ancient markets from the historical
    backfill that Gamma has aged out of its index.
    """
    ensure_resolution_schema(con)
    age_clause = ""
    params: list[Any] = []
    if min_trade_ts_s is not None:
        age_clause = "AND t.timestamp_s >= ?"
        params.append(min_trade_ts_s)
    params.append(limit)
    rows = con.execute(
        f"""
        SELECT t.condition_id,
               MIN(t.market_id) AS market_id,
               COUNT(*) AS n_trades,
               MAX(t.timestamp_s) AS latest_trade_ts
        FROM observed_trades t
        WHERE t.condition_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM observed_markets m
              WHERE m.condition_id = t.condition_id
                AND (m.settled = 1 OR m.proxy_settled = 1)
          )
          {age_clause}
        GROUP BY t.condition_id
        ORDER BY latest_trade_ts DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [
        {
            "market_id": r["market_id"],
            "condition_id": r["condition_id"],
            "n_trades": int(r["n_trades"]),
            "latest_trade_ts": int(r["latest_trade_ts"]) if r["latest_trade_ts"] else 0,
        }
        for r in rows
    ]


def _parse_outcome_prices(raw: object) -> tuple[int | None, int | None, str]:
    """Parse outcomePrices field. Returns (strict_yes_won, proxy_yes_won, raw_str).

    Polymarket Gamma returns outcome_prices as a JSON-encoded string
    of ["x", "y"]. Convention: the FIRST element corresponds to the YES
    outcome. `strict_yes_won` only accepts exact 0/1. `proxy_yes_won`
    accepts near-final 0.999/0.001 shapes once the market end date has passed.
    """
    if raw is None:
        return None, None, ""
    raw_str = str(raw)
    s = raw_str.strip()
    # Try JSON first
    try:
        parsed = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if not isinstance(parsed, list):
        # Fallback: parse as CSV-ish
        # Strip [ ] and quotes
        cleaned = s.strip("[]").replace("'", "").replace('"', "")
        parts = [p.strip() for p in cleaned.split(",")]
        if len(parts) != 2:
            return None, None, raw_str
        parsed = parts
    if len(parsed) != 2:
        return None, None, raw_str
    try:
        first = float(parsed[0])
    except (TypeError, ValueError):
        return None, None, raw_str
    if abs(first - 1.0) < 1e-9:
        return 1, 1, raw_str
    if abs(first) < 1e-9:
        return 0, 0, raw_str
    if first >= 0.999:
        return None, 1, raw_str
    if first <= 0.001:
        return None, 0, raw_str
    # 50/50 or other — treat as unresolved
    return None, None, raw_str


def _end_date_has_passed(raw: object) -> bool:
    """Return whether Gamma's endDate/end_date is in the past."""
    if not raw:
        return False
    value = str(raw).strip()
    if not value:
        return False
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC) < datetime.now(UTC)


def fetch_gamma_markets_batch(
    client: httpx.Client, condition_ids: list[str], *, rate_limit_sec: float = 0.5
) -> list[dict[str, Any]]:
    """Fetch a batch of markets by condition_id. Returns parsed list.

    Polymarket Gamma /markets supports the `condition_ids` param for
    batch retrieval. We chunk to ~25 per request to keep URL length
    reasonable.
    """
    if not condition_ids:
        return []
    out: list[dict[str, Any]] = []
    chunk_size = 25
    for i in range(0, len(condition_ids), chunk_size):
        chunk = condition_ids[i : i + chunk_size]
        params = [("condition_ids", cid) for cid in chunk]
        try:
            resp = client.get(
                f"{GAMMA_API}/markets", params=params, timeout=30.0
            )
        except httpx.HTTPError as exc:
            LOG.warning(
                "wallet_observer_resolutions.http_error chunk=%d err=%s",
                i,
                exc,
            )
            continue
        if resp.status_code != 200:
            LOG.warning(
                "wallet_observer_resolutions.bad_status status=%s",
                resp.status_code,
            )
            if resp.status_code == 429:
                time.sleep(5.0)
            continue
        try:
            data = resp.json()
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            out.extend(data)
        elif isinstance(data, dict) and "data" in data:
            inner = data["data"]
            if isinstance(inner, list):
                out.extend(inner)
        if rate_limit_sec > 0:
            time.sleep(rate_limit_sec)  # polite gap between chunks
    return out


def upsert_market(con: sqlite3.Connection, market: dict[str, Any]) -> bool:
    """Persist Gamma market state into observed_markets. Returns True if
    the row transitioned to strict-settled or proxy-settled this call."""
    ensure_resolution_schema(con)
    gamma_market_id = market.get("id") or market.get("marketId")
    condition_id = market.get("conditionId") or market.get("condition_id")
    if not gamma_market_id and not condition_id:
        return False
    # Data API trades join by condition_id; Gamma's numeric id is preserved
    # in payload but not used as this table's primary key.
    market_id = condition_id or gamma_market_id
    end_date_iso = market.get("endDate") or market.get("end_date")
    question = market.get("question")
    event_title = market.get("eventTitle") or (
        (market.get("event") or {}).get("title") if isinstance(market.get("event"), dict) else None
    )
    closed = bool(market.get("closed"))
    outcome_prices_raw = market.get("outcomePrices")
    strict_yes_won, proxy_yes_won, outcome_prices_str = _parse_outcome_prices(
        outcome_prices_raw
    )
    end_date_past = _end_date_has_passed(end_date_iso)
    settled = 1 if (closed and strict_yes_won is not None) else 0
    proxy_settled = (
        1 if (not settled and end_date_past and proxy_yes_won is not None) else 0
    )
    yes_won = strict_yes_won if strict_yes_won is not None else proxy_yes_won
    if settled:
        settlement_method = "strict_closed_exact_outcome"
    elif proxy_settled:
        settlement_method = "proxy_near_final_after_end"
    else:
        settlement_method = None
    now_iso = datetime.now(UTC).isoformat()
    payload = json.dumps(market, default=str)

    # Was this market previously settled? Legacy rows may have used
    # Gamma's numeric id as market_id, so update that row instead of
    # creating a duplicate for the same condition_id.
    prior_row = con.execute(
        "SELECT market_id, settled, proxy_settled FROM observed_markets "
        "WHERE condition_id = ? OR market_id = ? "
        "ORDER BY CASE WHEN condition_id = ? THEN 0 ELSE 1 END "
        "LIMIT 1",
        (
            str(condition_id) if condition_id else None,
            str(market_id),
            str(condition_id) if condition_id else None,
        ),
    ).fetchone()
    if prior_row and prior_row["market_id"]:
        market_id = prior_row["market_id"]
    prior_settled = int(prior_row["settled"]) if prior_row else 0
    prior_proxy_settled = int(prior_row["proxy_settled"]) if prior_row else 0

    con.execute(
        """
        INSERT INTO observed_markets
            (market_id, condition_id, question, event_title, end_date_iso,
             settled, proxy_settled, settlement_method, yes_won,
             outcome_prices, payload, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(market_id) DO UPDATE SET
            condition_id = COALESCE(excluded.condition_id, observed_markets.condition_id),
            question = COALESCE(excluded.question, observed_markets.question),
            event_title = COALESCE(excluded.event_title, observed_markets.event_title),
            end_date_iso = COALESCE(excluded.end_date_iso, observed_markets.end_date_iso),
            settled = MAX(observed_markets.settled, excluded.settled),
            proxy_settled = MAX(observed_markets.proxy_settled, excluded.proxy_settled),
            settlement_method = COALESCE(excluded.settlement_method, observed_markets.settlement_method),
            yes_won = COALESCE(excluded.yes_won, observed_markets.yes_won),
            outcome_prices = COALESCE(excluded.outcome_prices, observed_markets.outcome_prices),
            payload = excluded.payload,
            updated_at = excluded.updated_at
        """,
        (
            str(market_id),
            str(condition_id) if condition_id else None,
            str(question) if question else None,
            str(event_title) if event_title else None,
            str(end_date_iso) if end_date_iso else None,
            settled,
            proxy_settled,
            settlement_method,
            yes_won,
            outcome_prices_str if outcome_prices_str else None,
            payload,
            now_iso,
        ),
    )
    effective_settled = settled == 1 or proxy_settled == 1
    prior_effective_settled = prior_settled == 1 or prior_proxy_settled == 1
    return effective_settled and not prior_effective_settled


def backfill(
    con: sqlite3.Connection,
    *,
    max_markets: int,
    rate_limit_sec: float,
    max_age_days: int | None = None,
) -> dict[str, Any]:
    """One pass: fetch unresolved markets, query Gamma, upsert."""
    min_ts = None
    if max_age_days is not None:
        min_ts = int(time.time()) - max_age_days * 86400
    unresolved = find_unresolved_markets(con, max_markets, min_trade_ts_s=min_ts)
    if not unresolved:
        return {
            "started_at": datetime.now(UTC).isoformat(),
            "n_unresolved": 0,
            "n_fetched": 0,
            "n_newly_settled": 0,
        }
    started = datetime.now(UTC)

    # Prefer condition_id lookup since Gamma uses it as the canonical key
    cids = [m["condition_id"] for m in unresolved if m["condition_id"]]
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    n_newly_settled = 0
    n_fetched = 0
    with httpx.Client(timeout=30.0, headers=headers) as client:
        markets = fetch_gamma_markets_batch(
            client, cids, rate_limit_sec=rate_limit_sec
        )
        n_fetched = len(markets)
        for m in markets:
            if not _running:
                break
            try:
                if upsert_market(con, m):
                    n_newly_settled += 1
            except sqlite3.Error as exc:
                LOG.warning(
                    "wallet_observer_resolutions.upsert_err err=%s",
                    exc,
                )
        con.commit()

    finished = datetime.now(UTC)
    return {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_sec": (finished - started).total_seconds(),
        "n_unresolved": len(unresolved),
        "n_fetched": n_fetched,
        "n_newly_settled": n_newly_settled,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument(
        "--max-markets",
        type=int,
        default=500,
        help="Max unresolved markets to query per run.",
    )
    parser.add_argument(
        "--rate-limit-sec",
        type=float,
        default=0.5,
        help="Seconds between consecutive HTTP chunks.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=30,
        help=(
            "Skip markets where the most recent observed trade is older "
            "than this many days. Default 30d covers the 7d forward "
            "validation window plus a larger buffer for late-settling markets. "
            "Set to 0 to disable the age filter."
        ),
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    con = _connect(Path(args.db_path))
    try:
        stats = backfill(
            con,
            max_markets=args.max_markets,
            rate_limit_sec=args.rate_limit_sec,
            max_age_days=args.max_age_days if args.max_age_days > 0 else None,
        )
    finally:
        con.close()
    LOG.info("wallet_observer_resolutions.complete %s", json.dumps(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
