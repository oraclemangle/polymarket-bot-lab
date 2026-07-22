"""Resolution backfill for the Bot H Maker V2 recorder.

Reads `markets` from `data/maker_recorder.db`, finds rows that are not
yet known-settled, and queries Polymarket Gamma `/markets` in batches to
populate the resolution side. Designed to run on a slow cadence (every
6h) since markets close infrequently and Gamma rate-limits hard.

Read-only against Polymarket Gamma. Writes only to the `markets` table:
`yes_won`, `resolved_at_ms`, `outcome_yes_price`,
`last_resolution_check_ms`. Status flips to `RESOLVED` for closed
markets with a determinate yes_won (0 or 1); 50/50-void markets stay
`ACTIVE` with `last_resolution_check_ms` updated so future scans skip
them faster.

The output of this backfill unlocks `scripts/research/maker_flow_recorder_replay.py`
to compute realised PnL on recorder-derived trades.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from bots.bot_h_maker_v2.schema import _ensure_resolution_columns

GAMMA_API = "https://gamma-api.polymarket.com"
USER_AGENT = (
    "longshot-research-bot-h-maker-v2-resolutions/1.0 (read-only research)"
)

# Throttle: 25 condition_ids per chunk, 0.5s gap. Same posture as
# scripts/research/wallet_observer_resolutions.py.
DEFAULT_CHUNK_SIZE = 25
DEFAULT_RATE_LIMIT_SEC = 0.5
DEFAULT_HTTP_TIMEOUT_SEC = 30.0

# Throttle re-checks of the same market. Once we've checked a market in
# the last RECHECK_THROTTLE_SEC seconds, skip it on the next pass.
# Markets that resolved still bypass this — we only re-check the
# unresolved ones.
DEFAULT_RECHECK_THROTTLE_SEC = 4 * 3600  # 4 hours

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackfillStats:
    candidates: int
    queried: int
    resolved_now: int
    rechecked: int
    api_errors: int


def _connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"recorder DB not found at {path}")
    con = sqlite3.connect(str(path), timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=10000")
    return con


def find_unresolved_markets(
    con: sqlite3.Connection,
    *,
    limit: int,
    recheck_throttle_sec: int,
    now_ms: int | None = None,
) -> list[str]:
    """Return condition_ids of markets we still need resolution data for.

    A market qualifies if:
      - status != 'RESOLVED' (already known settled with determinate outcome)
      - yes_won IS NULL
      - either we've never checked it OR the last check was longer ago
        than recheck_throttle_sec

    Markets are returned in `last_seen_at_ms DESC` order so the most
    recently active markets are queried first when the limit is binding.
    """
    now_ms = now_ms or int(datetime.now(UTC).timestamp() * 1000)
    threshold_ms = now_ms - recheck_throttle_sec * 1000
    rows = con.execute(
        """
        SELECT condition_id
        FROM markets
        WHERE status != 'RESOLVED'
          AND yes_won IS NULL
          AND (last_resolution_check_ms IS NULL
               OR last_resolution_check_ms < ?)
        ORDER BY last_seen_at_ms DESC
        LIMIT ?
        """,
        (threshold_ms, limit),
    ).fetchall()
    return [str(r["condition_id"]) for r in rows]


def _parse_outcome_prices(raw: object) -> tuple[int | None, float | None]:
    """Parse Gamma's outcomePrices field. Returns (yes_won, yes_price).

    Convention: outcomePrices is a JSON-encoded list `["x", "y"]` where
    `x` is the YES price and `y` is the NO price. After resolution the
    pair is `("1", "0")` for YES win, `("0", "1")` for NO win, and
    `("0.5", "0.5")` for void.
    """
    if raw is None:
        return None, None
    s = str(raw).strip()
    parsed: object | None = None
    try:
        parsed = json.loads(s)
    except (json.JSONDecodeError, TypeError):
        cleaned = s.strip("[]").replace("'", "").replace('"', "")
        parts = [p.strip() for p in cleaned.split(",")]
        if len(parts) == 2:
            parsed = parts
    if not isinstance(parsed, list) or len(parsed) != 2:
        return None, None
    try:
        yes_price = float(parsed[0])
    except (TypeError, ValueError):
        return None, None
    if abs(yes_price - 1.0) < 1e-9:
        return 1, yes_price
    if abs(yes_price) < 1e-9:
        return 0, yes_price
    return None, yes_price


def fetch_gamma_resolutions(
    client: httpx.Client,
    condition_ids: list[str],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    rate_limit_sec: float = DEFAULT_RATE_LIMIT_SEC,
) -> tuple[list[dict[str, Any]], int]:
    """Batch-fetch market state from Gamma.

    Returns `(rows, n_api_errors)`. Rows include all fields Gamma
    returns; the caller picks `closed`, `outcomePrices`, `endDate`. We
    log failures but don't raise — partial results are still useful.
    """
    if not condition_ids:
        return [], 0
    out: list[dict[str, Any]] = []
    n_api_errors = 0
    for i in range(0, len(condition_ids), chunk_size):
        chunk = condition_ids[i : i + chunk_size]
        params = [("condition_ids", cid) for cid in chunk]
        try:
            resp = client.get(
                f"{GAMMA_API}/markets",
                params=params,
                timeout=DEFAULT_HTTP_TIMEOUT_SEC,
            )
        except httpx.HTTPError as exc:
            log.warning(
                "bot_h_maker_v2.resolution_backfill.http_error chunk=%d err=%s",
                i,
                exc,
            )
            n_api_errors += 1
            continue
        if resp.status_code == 429:
            log.warning("bot_h_maker_v2.resolution_backfill.rate_limited backing_off=5s")
            time.sleep(5.0)
            n_api_errors += 1
            continue
        if resp.status_code != 200:
            log.warning(
                "bot_h_maker_v2.resolution_backfill.bad_status status=%s",
                resp.status_code,
            )
            n_api_errors += 1
            continue
        try:
            data = resp.json()
        except json.JSONDecodeError:
            n_api_errors += 1
            continue
        if isinstance(data, list):
            out.extend(data)
        elif isinstance(data, dict) and isinstance(data.get("data"), list):
            out.extend(data["data"])
        time.sleep(rate_limit_sec)
    return out, n_api_errors


def upsert_resolution(
    con: sqlite3.Connection,
    market: dict[str, Any],
    *,
    now_ms: int,
) -> bool:
    """Persist Gamma resolution state into `markets`. Returns True if
    the row transitioned to RESOLVED on this call (i.e. yes_won was
    None before and is determinate now)."""
    condition_id = market.get("conditionId") or market.get("condition_id")
    if not condition_id:
        return False
    closed = bool(market.get("closed"))
    yes_won, yes_price = _parse_outcome_prices(market.get("outcomePrices"))

    prior = con.execute(
        "SELECT yes_won, status FROM markets WHERE condition_id = ?",
        (str(condition_id),),
    ).fetchone()
    if prior is None:
        # We haven't seen this market in our recorder filter; ignore.
        # The discovery loop adds rows for our scope; this script never
        # CREATES rows.
        return False
    prior_yes_won = prior["yes_won"]
    prior_status = prior["status"]

    new_yes_won = yes_won if yes_won is not None else prior_yes_won
    new_status = (
        "RESOLVED"
        if (closed and yes_won is not None)
        else prior_status
    )
    resolved_at_ms = now_ms if (closed and yes_won is not None and prior_yes_won is None) else None

    if resolved_at_ms is not None:
        con.execute(
            """
            UPDATE markets SET
              yes_won = ?,
              outcome_yes_price = ?,
              resolved_at_ms = ?,
              status = ?,
              last_resolution_check_ms = ?
            WHERE condition_id = ?
            """,
            (
                new_yes_won,
                yes_price,
                resolved_at_ms,
                new_status,
                now_ms,
                str(condition_id),
            ),
        )
        return True
    else:
        con.execute(
            """
            UPDATE markets SET
              yes_won = COALESCE(?, yes_won),
              outcome_yes_price = COALESCE(?, outcome_yes_price),
              last_resolution_check_ms = ?
            WHERE condition_id = ?
            """,
            (
                new_yes_won,
                yes_price,
                now_ms,
                str(condition_id),
            ),
        )
        return False


def run_backfill(
    *,
    db_path: Path,
    max_markets: int,
    recheck_throttle_sec: int = DEFAULT_RECHECK_THROTTLE_SEC,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    rate_limit_sec: float = DEFAULT_RATE_LIMIT_SEC,
    http_client: httpx.Client | None = None,
) -> BackfillStats:
    """Run one pass of the resolution backfill.

    Returns `BackfillStats` so the systemd unit and cron observers can
    surface progress without having to query the DB themselves.
    """
    con = _connect(db_path)
    # Defensive: ensure the resolution columns exist on this connection
    # before we query them. The recorder process may have opened the DB
    # before this migration shipped; running the helper here is cheap
    # and idempotent and decouples us from the recorder's restart cycle.
    added = _ensure_resolution_columns(con)
    if added:
        log.info(
            "bot_h_maker_v2.resolution_backfill.schema_migrated added=%s",
            ",".join(added),
        )
    owns_client = http_client is None
    client = http_client or httpx.Client(
        headers={"User-Agent": USER_AGENT},
    )
    try:
        candidates = find_unresolved_markets(
            con,
            limit=max_markets,
            recheck_throttle_sec=recheck_throttle_sec,
        )
        if not candidates:
            log.info("bot_h_maker_v2.resolution_backfill.no_candidates")
            return BackfillStats(0, 0, 0, 0, 0)
        log.info(
            "bot_h_maker_v2.resolution_backfill.start candidates=%d",
            len(candidates),
        )
        rows, n_errors = fetch_gamma_resolutions(
            client,
            candidates,
            chunk_size=chunk_size,
            rate_limit_sec=rate_limit_sec,
        )
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        resolved_now = 0
        rechecked = 0
        for market in rows:
            try:
                transitioned = upsert_resolution(con, market, now_ms=now_ms)
            except Exception as exc:
                log.warning(
                    "bot_h_maker_v2.resolution_backfill.upsert_error condition_id=%s err=%s",
                    market.get("conditionId"),
                    exc,
                )
                continue
            if transitioned:
                resolved_now += 1
            else:
                rechecked += 1
        con.commit()
        stats = BackfillStats(
            candidates=len(candidates),
            queried=len(rows),
            resolved_now=resolved_now,
            rechecked=rechecked,
            api_errors=n_errors,
        )
        log.info(
            "bot_h_maker_v2.resolution_backfill.done candidates=%d queried=%d resolved=%d rechecked=%d errors=%d",
            stats.candidates,
            stats.queried,
            stats.resolved_now,
            stats.rechecked,
            stats.api_errors,
        )
        return stats
    finally:
        if owns_client:
            client.close()
        con.close()
