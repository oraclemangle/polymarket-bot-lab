#!/usr/bin/env python3
"""
wallet_reconcile_dryrun.py — Read-only wallet Data API vs local DB(s) gap report.

Always dry-run / read-only. Never mutates DB, never places orders, never uses keys.

Purpose (P0 for OQ-123 / ADR-181):
- Fetch current wallet holdings from Data API /positions
- Fetch recent activity (/trades) since a start date
- Compare against main.db (all critical bots) + persistence_live.db (Bot I)
- Report:
  - Local OPEN rows not present in current wallet positions (stale)
  - Wallet positions / recent redeems with no matching local bot row (unowned / manual)
  - Basic rebate/redeem volume in the window
- Produces human + JSON output for operator review before any backfill job.

Usage (safe, local or the bot container):
    python -m scripts.wallet_reconcile_dryrun \\
        --wallet 0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA \\
        --since 2026-05-16 \\
        --json

No --execute. No secrets printed. Uses only public Data API reads by wallet address.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

CRITICAL_BOT_IDS = [
    "bot_d_live_probe",
    "bot_d_maker_live_probe",
    "bot_g_prime_live",
    "crypto_brownian_fv_live_maker",
    "crypto_probability_gap_live_maker",
    "bot_i_persistence_live",
]

DEFAULT_MAIN_DB = "data/main.db"
DEFAULT_PERSISTENCE_DB = "data/persistence_live.db"
DEFAULT_DATA_API = "https://data-api.polymarket.com"


def _get_db_path(name: str) -> str:
    env = os.environ.get(f"POLYMARKET_{name.upper()}_DB")
    if env:
        return env
    return DEFAULT_MAIN_DB if name == "main" else DEFAULT_PERSISTENCE_DB


def fetch_wallet_positions(data_api: str, wallet: str) -> list[dict[str, Any]]:
    """Public Data API /positions for the wallet (read-only, no auth)."""
    url = f"{data_api}/positions"
    try:
        r = httpx.get(url, params={"user": wallet, "limit": 500}, timeout=30.0)
        r.raise_for_status()
        data = r.json() or []
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        return [d for d in data if isinstance(d, dict)]
    except Exception as exc:
        print(f"WARNING: Data API /positions failed: {exc}", file=sys.stderr)
        return []


def fetch_wallet_trades(data_api: str, wallet: str, since: datetime) -> list[dict[str, Any]]:
    """Recent /trades for the wallet (historical buys, sells, redeems)."""
    url = f"{data_api}/trades"
    since_ms = int(since.timestamp() * 1000)
    try:
        r = httpx.get(
            url,
            params={"user": wallet, "limit": 1000, "start": since_ms},
            timeout=60.0,
        )
        r.raise_for_status()
        data = r.json() or []
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        return [d for d in data if isinstance(d, dict)]
    except Exception as exc:
        print(f"WARNING: Data API /trades failed: {exc}", file=sys.stderr)
        return []


def fetch_wallet_activity(data_api: str, wallet: str, since: datetime) -> list[dict[str, Any]]:
    """Full activity feed (/activity). This is where REDEEM events (including zero-value)
    and richer historical actions reliably appear, unlike /trades."""
    url = f"{data_api}/activity"
    since_ms = int(since.timestamp() * 1000)
    try:
        r = httpx.get(
            url,
            params={"user": wallet, "limit": 1000, "start": since_ms},
            timeout=60.0,
        )
        r.raise_for_status()
        data = r.json() or []
        if isinstance(data, dict) and "data" in data:
            data = data["data"]
        return [d for d in data if isinstance(d, dict)]
    except Exception as exc:
        print(f"WARNING: Data API /activity failed: {exc}", file=sys.stderr)
        return []


def load_local_open_positions(db_path: str, bot_ids: list[str]) -> list[dict[str, Any]]:
    if not Path(db_path).exists():
        return []
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        q = """
            SELECT bot_id, id, condition_id, token_id, side, size, cost_basis_usd, status, opened_at
            FROM positions
            WHERE bot_id IN ({}) AND status IN ('OPEN', 'CLOSED_RECONCILED')
            ORDER BY opened_at DESC
        """.format(",".join("?" * len(bot_ids)))
        rows = cur.execute(q, bot_ids).fetchall()
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        con.close()


def load_persistence_live_entries(db_path: str) -> list[dict[str, Any]]:
    if not Path(db_path).exists():
        return []
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = con.cursor()
        # Best-effort for the known live_entries schema in persistence_live.db
        try:
            rows = cur.execute(
                "SELECT * FROM live_entries WHERE status IN ('OPEN', 'active') LIMIT 500"
            ).fetchall()
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in rows]
        except sqlite3.OperationalError:
            return []
    finally:
        con.close()


def build_report(
    wallet: str, since: datetime, main_db: str, persistence_db: str, data_api: str
) -> dict[str, Any]:
    positions = fetch_wallet_positions(data_api, wallet)
    trades = fetch_wallet_trades(data_api, wallet, since)
    activity = fetch_wallet_activity(data_api, wallet, since)

    wallet_token_ids = {
        str(p.get("asset") or p.get("tokenId") or p.get("token_id") or "")
        for p in positions
    }
    wallet_token_ids.discard("")

    local_open = load_local_open_positions(main_db, CRITICAL_BOT_IDS)
    persistence_entries = load_persistence_live_entries(persistence_db)

    local_tokens = {str(r.get("token_id", "")) for r in local_open}
    persistence_tokens = {
        str(r.get("token_id") or r.get("asset") or "") for r in persistence_entries
    }

    stale_local = [
        r for r in local_open if str(r.get("token_id", "")) not in wallet_token_ids
    ]
    unowned_wallet = [
        p
        for p in positions
        if str(p.get("asset") or "") not in local_tokens | persistence_tokens
    ]

    # Categorize activity (the proper source for REDEEMs, zero-value redeems, rebates, etc.)
    activity_by_type: dict[str, int] = {}
    zero_value_redeems = 0
    rebates = 0
    for a in activity:
        t = str(a.get("type") or a.get("eventType") or a.get("action") or "UNKNOWN").upper()
        activity_by_type[t] = activity_by_type.get(t, 0) + 1
        if "REDEEM" in t:
            amt = float(a.get("amount") or a.get("usdcAmount") or a.get("size") or 0)
            if amt == 0:
                zero_value_redeems += 1
        if "REBATE" in t or "REWARD" in t:
            rebates += 1

    # Legacy approx from /trades (kept for comparison, but no longer authoritative)
    legacy_redeem_volume = sum(
        float(t.get("price", 0)) * float(t.get("size", 0) or t.get("amount", 0))
        for t in trades
        if str(t.get("side", "")).upper() in ("REDEEM", "SELL") and t.get("price")
    )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "wallet": wallet,
        "since": since.isoformat(),
        "data_api": data_api,
        "summary": {
            "wallet_current_positions": len(positions),
            "wallet_trades_in_window": len(trades),
            "wallet_activity_in_window": len(activity),
            "local_open_in_scope": len(local_open),
            "persistence_live_entries": len(persistence_entries),
            "stale_local_open_not_in_wallet": len(stale_local),
            "unowned_wallet_positions": len(unowned_wallet),
            "activity_by_type": activity_by_type,
            "zero_value_redeems": zero_value_redeems,
            "rebate_events": rebates,
            "legacy_redeem_volume_usd_from_trades_only": round(legacy_redeem_volume, 2),
        },
        "stale_local_open": stale_local[:20],
        "unowned_wallet_samples": unowned_wallet[:10],
        "activity_samples": activity[:5],
        "recommendation": (
            "Use /activity (not just /trades) for authoritative REDEEM/rebate/zero-value accounting. "
            "Run a full backfill job that classifies every row across main.db + persistence_live.db. "
            "Only after the resulting report is reviewed should paused live paths be considered."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser(
        description="Dry-run wallet vs local DB reconciliation report (OQ-123)"
    )
    p.add_argument("--wallet", required=True, help="Hot wallet 0x address")
    p.add_argument("--since", default="2026-05-16", help="ISO date for activity window")
    p.add_argument("--main-db", default=DEFAULT_MAIN_DB)
    p.add_argument("--persistence-db", default=DEFAULT_PERSISTENCE_DB)
    p.add_argument("--data-api", default=DEFAULT_DATA_API)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    since = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
    report = build_report(args.wallet, since, args.main_db, args.persistence_db, args.data_api)

    if args.json:
        print(json.dumps(report, default=str, indent=2))
    else:
        print(json.dumps(report["summary"], indent=2))
        print("\n# Full report available with --json")
        print("# Recommendation:", report["recommendation"])

    # Always exit 0 — this is a reporting tool
    return 0


if __name__ == "__main__":
    sys.exit(main())
