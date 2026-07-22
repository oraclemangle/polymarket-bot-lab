#!/usr/bin/env python3
"""Settlement join backfill for the on-chain wallet observer.

The VPS observer DB records CTF token_ids from OrderFilled logs. Gamma
settlement data is keyed by condition_id and outcome index, so this
script first maps token_id -> condition_id/outcome_index, then stores
market resolutions. It is read-only against Gamma and writes only to
the local observer DB's helper tables.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from bots.wallet_observer import config as cfg
from bots.wallet_observer.schema import ensure_settlement_schema

GAMMA_API = "https://gamma-api.polymarket.com"
USER_AGENT = "longshot-research-wallet-observer-settlement-join/1.0"
DEFAULT_CHUNK_SIZE = 25
DEFAULT_RATE_LIMIT_SEC = 0.5
DEFAULT_HTTP_TIMEOUT_SEC = 30.0

log = logging.getLogger("wallet_observer_settlement_join")


@dataclass(frozen=True)
class JoinStats:
    unmapped_tokens: int
    token_market_rows: int
    token_rows_upserted: int
    unresolved_conditions: int
    resolution_market_rows: int
    newly_settled: int
    labelled_fills: int


def _connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"observer DB not found at {path}")
    con = sqlite3.connect(str(path), timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=10000")
    _require_observer_schema(con)
    ensure_settlement_schema(con)
    return con


def _require_observer_schema(con: sqlite3.Connection) -> None:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='wallet_observed_fills'"
    ).fetchone()
    if row is None:
        raise RuntimeError("wallet_observed_fills table not found; wrong observer DB")


def _json_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _end_date_has_passed(raw: object, *, now: datetime | None = None) -> bool:
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
    return dt.astimezone(UTC) < (now or datetime.now(UTC))


def _parse_outcome_prices(raw: object) -> tuple[int | None, int | None, str]:
    """Return (strict_winning_index, proxy_winning_index, raw_string)."""
    if raw is None:
        return None, None, ""
    raw_str = str(raw)
    values = _json_list(raw)
    if len(values) < 2:
        return None, None, raw_str
    try:
        prices = [float(v) for v in values]
    except (TypeError, ValueError):
        return None, None, raw_str

    strict = [i for i, p in enumerate(prices) if abs(p - 1.0) < 1e-9]
    if len(strict) == 1 and all(
        i == strict[0] or abs(p) < 1e-9 for i, p in enumerate(prices)
    ):
        return strict[0], strict[0], raw_str

    proxy = [i for i, p in enumerate(prices) if p >= 0.999]
    if len(proxy) == 1 and all(i == proxy[0] or p <= 0.001 for i, p in enumerate(prices)):
        return None, proxy[0], raw_str
    return None, None, raw_str


def find_unmapped_tokens(con: sqlite3.Connection, *, limit: int) -> list[str]:
    rows = con.execute(
        """
        SELECT f.token_id, MAX(f.block_ts) AS latest_ts
        FROM wallet_observed_fills f
        LEFT JOIN wallet_market_tokens mt ON mt.token_id = f.token_id
        WHERE mt.token_id IS NULL
        GROUP BY f.token_id
        ORDER BY latest_ts DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [str(r["token_id"]) for r in rows if r["token_id"]]


def find_unresolved_conditions(con: sqlite3.Connection, *, limit: int) -> list[str]:
    rows = con.execute(
        """
        SELECT mt.condition_id, MAX(f.block_ts) AS latest_ts
        FROM wallet_market_tokens mt
        JOIN wallet_observed_fills f ON f.token_id = mt.token_id
        LEFT JOIN wallet_market_resolutions mr
          ON mr.condition_id = mt.condition_id
        WHERE mr.condition_id IS NULL
           OR (mr.settled = 0 AND mr.proxy_settled = 0)
        GROUP BY mt.condition_id
        ORDER BY latest_ts DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [str(r["condition_id"]) for r in rows if r["condition_id"]]


def fetch_gamma_markets_by_tokens(
    client: httpx.Client,
    token_ids: list[str],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    rate_limit_sec: float = DEFAULT_RATE_LIMIT_SEC,
) -> list[dict[str, Any]]:
    if not token_ids:
        return []
    out: list[dict[str, Any]] = []
    for i in range(0, len(token_ids), chunk_size):
        chunk = token_ids[i : i + chunk_size]
        params: list[tuple[str, str]] = [("clob_token_ids", token) for token in chunk]
        params.append(("limit", str(max(len(chunk), 1))))
        resp = client.get(f"{GAMMA_API}/markets", params=params, timeout=DEFAULT_HTTP_TIMEOUT_SEC)
        if resp.status_code == 429:
            log.warning("wallet_observer_settlement_join.rate_limited lookup=tokens")
            time.sleep(5.0)
            continue
        if resp.status_code != 200:
            log.warning(
                "wallet_observer_settlement_join.bad_status lookup=tokens status=%s",
                resp.status_code,
            )
            continue
        data = resp.json()
        if isinstance(data, list):
            out.extend(data)
        elif isinstance(data, dict) and isinstance(data.get("data"), list):
            out.extend(data["data"])
        if rate_limit_sec > 0:
            time.sleep(rate_limit_sec)
    return out


def fetch_gamma_markets_by_conditions(
    client: httpx.Client,
    condition_ids: list[str],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    rate_limit_sec: float = DEFAULT_RATE_LIMIT_SEC,
) -> list[dict[str, Any]]:
    if not condition_ids:
        return []
    out: list[dict[str, Any]] = []
    for i in range(0, len(condition_ids), chunk_size):
        chunk = condition_ids[i : i + chunk_size]
        params: list[tuple[str, str]] = [("condition_ids", cid) for cid in chunk]
        resp = client.get(f"{GAMMA_API}/markets", params=params, timeout=DEFAULT_HTTP_TIMEOUT_SEC)
        if resp.status_code == 429:
            log.warning("wallet_observer_settlement_join.rate_limited lookup=conditions")
            time.sleep(5.0)
            continue
        if resp.status_code != 200:
            log.warning(
                "wallet_observer_settlement_join.bad_status lookup=conditions status=%s",
                resp.status_code,
            )
            continue
        data = resp.json()
        if isinstance(data, list):
            out.extend(data)
        elif isinstance(data, dict) and isinstance(data.get("data"), list):
            out.extend(data["data"])
        if rate_limit_sec > 0:
            time.sleep(rate_limit_sec)
    return out


def upsert_market(con: sqlite3.Connection, market: dict[str, Any], *, now_s: int) -> int:
    """Upsert token mapping and resolution. Returns token rows upserted."""
    gamma_market_id = market.get("id") or market.get("marketId")
    condition_id = market.get("conditionId") or market.get("condition_id")
    if not condition_id:
        return 0

    tokens = _json_list(market.get("clobTokenIds"))
    outcomes = _json_list(market.get("outcomes"))
    if len(tokens) != len(outcomes):
        tokens = []
        outcomes = []

    question = market.get("question")
    event_title = market.get("eventTitle") or (
        (market.get("event") or {}).get("title") if isinstance(market.get("event"), dict) else None
    )
    end_date_iso = market.get("endDate") or market.get("end_date")
    outcome_prices_raw = market.get("outcomePrices")
    strict_idx, proxy_idx, outcome_prices = _parse_outcome_prices(outcome_prices_raw)
    closed = 1 if bool(market.get("closed")) else 0
    end_past = _end_date_has_passed(end_date_iso)
    settled = 1 if closed and strict_idx is not None else 0
    proxy_settled = 1 if not settled and end_past and proxy_idx is not None else 0
    winning_idx = strict_idx if strict_idx is not None else proxy_idx
    if settled:
        method = "strict_closed_exact_outcome"
    elif proxy_settled:
        method = "proxy_near_final_after_end"
    else:
        method = None
    payload = json.dumps(market, default=str)

    token_rows = 0
    for idx, token in enumerate(tokens):
        if token in (None, ""):
            continue
        con.execute(
            """
            INSERT INTO wallet_market_tokens
                (token_id, condition_id, outcome, outcome_index, gamma_market_id,
                 question, event_title, end_date_iso, payload, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(token_id) DO UPDATE SET
                condition_id = excluded.condition_id,
                outcome = excluded.outcome,
                outcome_index = excluded.outcome_index,
                gamma_market_id = excluded.gamma_market_id,
                question = excluded.question,
                event_title = excluded.event_title,
                end_date_iso = excluded.end_date_iso,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                str(token),
                str(condition_id),
                str(outcomes[idx]) if idx < len(outcomes) else None,
                idx,
                str(gamma_market_id) if gamma_market_id is not None else None,
                str(question) if question else None,
                str(event_title) if event_title else None,
                str(end_date_iso) if end_date_iso else None,
                payload,
                now_s,
            ),
        )
        token_rows += 1

    con.execute(
        """
        INSERT INTO wallet_market_resolutions
            (condition_id, gamma_market_id, question, event_title, end_date_iso,
             closed, settled, proxy_settled, settlement_method,
             winning_outcome_index, outcome_prices, payload, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(condition_id) DO UPDATE SET
            gamma_market_id = COALESCE(excluded.gamma_market_id, wallet_market_resolutions.gamma_market_id),
            question = COALESCE(excluded.question, wallet_market_resolutions.question),
            event_title = COALESCE(excluded.event_title, wallet_market_resolutions.event_title),
            end_date_iso = COALESCE(excluded.end_date_iso, wallet_market_resolutions.end_date_iso),
            closed = MAX(wallet_market_resolutions.closed, excluded.closed),
            settled = MAX(wallet_market_resolutions.settled, excluded.settled),
            proxy_settled = MAX(wallet_market_resolutions.proxy_settled, excluded.proxy_settled),
            settlement_method = COALESCE(excluded.settlement_method, wallet_market_resolutions.settlement_method),
            winning_outcome_index = COALESCE(excluded.winning_outcome_index, wallet_market_resolutions.winning_outcome_index),
            outcome_prices = COALESCE(excluded.outcome_prices, wallet_market_resolutions.outcome_prices),
            payload = excluded.payload,
            updated_at = excluded.updated_at
        """,
        (
            str(condition_id),
            str(gamma_market_id) if gamma_market_id is not None else None,
            str(question) if question else None,
            str(event_title) if event_title else None,
            str(end_date_iso) if end_date_iso else None,
            closed,
            settled,
            proxy_settled,
            method,
            winning_idx,
            outcome_prices if outcome_prices else None,
            payload,
            now_s,
        ),
    )
    return token_rows


def count_newly_settled_before_after(
    con: sqlite3.Connection,
    before: set[str],
) -> int:
    rows = con.execute(
        """
        SELECT condition_id
        FROM wallet_market_resolutions
        WHERE settled = 1 OR proxy_settled = 1
        """
    ).fetchall()
    after = {str(r["condition_id"]) for r in rows}
    return len(after - before)


def settled_conditions(con: sqlite3.Connection) -> set[str]:
    rows = con.execute(
        """
        SELECT condition_id
        FROM wallet_market_resolutions
        WHERE settled = 1 OR proxy_settled = 1
        """
    ).fetchall()
    return {str(r["condition_id"]) for r in rows}


def labelled_fill_count(con: sqlite3.Connection) -> int:
    row = con.execute(
        """
        SELECT COUNT(*)
        FROM wallet_observed_fills f
        JOIN wallet_market_tokens mt ON mt.token_id = f.token_id
        JOIN wallet_market_resolutions mr ON mr.condition_id = mt.condition_id
        WHERE (mr.settled = 1 OR mr.proxy_settled = 1)
          AND mr.winning_outcome_index IS NOT NULL
          AND mt.outcome_index IS NOT NULL
        """
    ).fetchone()
    return int(row[0] or 0)


def run_join(
    *,
    db_path: Path,
    max_tokens: int,
    max_markets: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    rate_limit_sec: float = DEFAULT_RATE_LIMIT_SEC,
    http_client: httpx.Client | None = None,
) -> JoinStats:
    con = _connect(db_path)
    owns_client = http_client is None
    client = http_client or httpx.Client(headers={"User-Agent": USER_AGENT})
    try:
        before_settled = settled_conditions(con)
        unmapped_tokens = find_unmapped_tokens(con, limit=max_tokens)
        token_markets = fetch_gamma_markets_by_tokens(
            client,
            unmapped_tokens,
            chunk_size=chunk_size,
            rate_limit_sec=rate_limit_sec,
        )
        now_s = int(datetime.now(UTC).timestamp())
        token_rows = 0
        for market in token_markets:
            token_rows += upsert_market(con, market, now_s=now_s)

        unresolved_conditions = find_unresolved_conditions(con, limit=max_markets)
        resolution_markets = fetch_gamma_markets_by_conditions(
            client,
            unresolved_conditions,
            chunk_size=chunk_size,
            rate_limit_sec=rate_limit_sec,
        )
        for market in resolution_markets:
            upsert_market(con, market, now_s=now_s)
        con.commit()

        return JoinStats(
            unmapped_tokens=len(unmapped_tokens),
            token_market_rows=len(token_markets),
            token_rows_upserted=token_rows,
            unresolved_conditions=len(unresolved_conditions),
            resolution_market_rows=len(resolution_markets),
            newly_settled=count_newly_settled_before_after(con, before_settled),
            labelled_fills=labelled_fill_count(con),
        )
    finally:
        if owns_client:
            client.close()
        con.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db", default=str(cfg.WALLET_OBSERVER_DB))
    parser.add_argument("--max-tokens", type=int, default=500)
    parser.add_argument("--max-markets", type=int, default=500)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--rate-limit-sec", type=float, default=DEFAULT_RATE_LIMIT_SEC)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stats = run_join(
        db_path=Path(args.db),
        max_tokens=args.max_tokens,
        max_markets=args.max_markets,
        chunk_size=args.chunk_size,
        rate_limit_sec=args.rate_limit_sec,
    )
    log.info("wallet_observer_settlement_join.complete %s", json.dumps(stats.__dict__))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
