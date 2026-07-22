#!/usr/bin/env python3
"""Read-only Bot D wallet-readiness report.

The report focuses on the current Bot D blocker: paper capital lock-up and
stale/open state. It does not place, cancel, reconcile, or mutate anything.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bots.bot_d_weather.config import (  # noqa: E402
    BOT_D_ALLOW_NWS_FALLBACK_ENTRY,
    BOT_D_DEPTH_GATE_ENABLED,
    BOT_D_ENTRY_HALT,
    BOT_D_EXIT_STALE_MIN,
    BOT_D_LIVE_APPROVED_AT,
    BOT_D_LIVE_AUTHORIZED,
    BOT_D_LIVE_EXIT_LIMIT_OFFSET,
    BOT_D_LIVE_FIXED_SHARES,
    BOT_D_LIVE_MAX_CONCURRENT_POSITIONS,
    BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD,
    BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD,
    BOT_D_LIVE_MAX_ORDER_USD,
    BOT_D_LIVE_PROBE_MODE,
    BOT_D_LIVE_WALLET_USD,
    BOT_D_MAX_LOCKUP_HOURS,
    BOT_D_MIN_ENTRY_DEPTH_USD,
    BOT_D_PAPER_EXIT_SLIPPAGE_BPS,
    BOT_D_REQUIRE_KNOWN_END_DATE,
    BOT_D_REQUIRE_VERIFIED_SETTLEMENT,
    BOT_D_REQUIRE_WAVE_FOR_ENTRY,
    settlement_coverage_rows,
)

BOT_ID = "bot_d"
DEPTH_TARGETS_USD = (25.0, 50.0)
MIN_DEPTH_SAMPLES = 10
MIN_25_USD_DEPTH_COVERAGE_PCT = 50.0
MIN_DAILY_CLOSED_SAMPLE = 30


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _sqlite_dt(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _has_table(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}


def _money(value: object) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _payload(raw: object) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _loads_levels(raw: str | None) -> list[tuple[float, float]]:
    if not raw:
        return []
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(rows, list):
        return []
    out: list[tuple[float, float]] = []
    for row in rows:
        try:
            if isinstance(row, dict):
                price = float(row.get("price"))
                size = float(row.get("size") or row.get("amount") or row.get("quantity"))
            else:
                price = float(row[0])
                size = float(row[1])
        except (TypeError, ValueError, IndexError):
            continue
        if 0 <= price <= 1 and size > 0:
            out.append((price, size))
    return out


def _book_depth_notional(levels: list[tuple[float, float]], limit_price: float) -> float:
    return sum(price * size for price, size in levels if price <= limit_price + 1e-12)


def _nearest_entry_book_capacity(
    conn: sqlite3.Connection,
    *,
    token_id: str,
    ts: datetime,
    limit_price: float,
) -> dict[str, Any] | None:
    if not token_id or limit_price <= 0 or not _has_table(conn, "books"):
        return None
    ts_sql = _sqlite_dt(ts)
    row = conn.execute(
        """
        SELECT asks, snapshot_at
        FROM books
        WHERE token_id = ?
          AND snapshot_at <= ?
        ORDER BY snapshot_at DESC
        LIMIT 1
        """,
        (token_id, ts_sql),
    ).fetchone()
    if row is None:
        row = conn.execute(
            """
            SELECT asks, snapshot_at
            FROM books
            WHERE token_id = ?
              AND snapshot_at > ?
            ORDER BY snapshot_at
            LIMIT 1
            """,
            (token_id, ts_sql),
        ).fetchone()
    if row is None:
        return None
    levels = _loads_levels(row["asks"] if isinstance(row, sqlite3.Row) else row[0])
    depth = _book_depth_notional(levels, limit_price)
    return {
        "snapshot_at": row["snapshot_at"] if isinstance(row, sqlite3.Row) else row[1],
        "notional_at_limit": round(depth, 4),
        "targets": {
            str(int(target)): depth >= target - 1e-9
            for target in DEPTH_TARGETS_USD
        },
    }


def _classify_duration(placed_at: datetime | None, end_date: datetime | None) -> str:
    if placed_at is None or end_date is None:
        return "unknown"
    hours = (end_date - placed_at).total_seconds() / 3600
    if hours <= 48:
        return "daily_low_lockup"
    if hours <= 192:
        return "weekly_lockup"
    return "long_lockup"


def _summarise_rows(rows: list[sqlite3.Row], now: datetime) -> dict[str, Any]:
    by_duration: dict[str, dict[str, Any]] = {}
    stale_orders = 0
    max_age_hours = 0.0
    missing_market = 0
    total_notional = 0.0
    for row in rows:
        placed = _parse_dt(row["placed_at"])
        end = _parse_dt(row["end_date"])
        bucket = _classify_duration(placed, end)
        age = (now - placed).total_seconds() / 3600 if placed else 0.0
        max_age_hours = max(max_age_hours, age)
        if age >= 48:
            stale_orders += 1
        if end is None:
            missing_market += 1
        notional = float(row["notional"] or 0)
        total_notional += notional
        item = by_duration.setdefault(bucket, {"count": 0, "notional": 0.0})
        item["count"] += 1
        item["notional"] += notional
    for item in by_duration.values():
        item["notional"] = _money(item["notional"])
    return {
        "count": len(rows),
        "notional": _money(total_notional),
        "by_duration": by_duration,
        "stale_48h_count": stale_orders,
        "missing_market_count": missing_market,
        "max_age_hours": round(max_age_hours, 2) if rows else 0.0,
    }


def _open_orders(conn: sqlite3.Connection, now: datetime) -> dict[str, Any]:
    if not _has_table(conn, "orders"):
        return _summarise_rows([], now)
    rows = conn.execute(
        """
        SELECT o.order_id, o.condition_id, o.status, o.placed_at,
               COALESCE(o.price, 0) * COALESCE(o.size, 0) AS notional,
               m.end_date
        FROM orders o
        LEFT JOIN markets m ON m.condition_id = o.condition_id
        WHERE o.bot_id = ?
          AND o.status IN ('PAPER_OPEN', 'OPEN', 'PARTIAL', 'MATCHED', 'live')
        ORDER BY o.placed_at DESC
        """,
        (BOT_ID,),
    ).fetchall()
    return _summarise_rows(rows, now)


def _open_positions(conn: sqlite3.Connection, now: datetime) -> dict[str, Any]:
    if not _has_table(conn, "positions"):
        return {
            "count": 0,
            "cost_basis": 0.0,
            "stale_48h_count": 0,
            "max_age_hours": 0.0,
        }
    rows = conn.execute(
        """
        SELECT p.condition_id, p.cost_basis_usd, p.opened_at, m.end_date
        FROM positions p
        LEFT JOIN markets m ON m.condition_id = p.condition_id
        WHERE p.bot_id = ?
          AND p.status = 'OPEN'
        """,
        (BOT_ID,),
    ).fetchall()
    ages: list[float] = []
    stale = 0
    for row in rows:
        opened = _parse_dt(row["opened_at"])
        age = (now - opened).total_seconds() / 3600 if opened else 0.0
        ages.append(age)
        if age >= 48:
            stale += 1
    return {
        "count": len(rows),
        "cost_basis": _money(sum(float(row["cost_basis_usd"] or 0) for row in rows)),
        "stale_48h_count": stale,
        "max_age_hours": round(max(ages), 2) if ages else 0.0,
    }


def _recent_orders(conn: sqlite3.Connection, cutoff: datetime) -> dict[str, Any]:
    if not _has_table(conn, "orders"):
        return {"count": 0, "notional": 0.0, "by_status": {}}
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS n,
               COALESCE(SUM(COALESCE(price, 0) * COALESCE(size, 0)), 0) AS notional
        FROM orders
        WHERE bot_id = ?
          AND placed_at >= ?
        GROUP BY status
        ORDER BY status
        """,
        (BOT_ID, _sqlite_dt(cutoff)),
    ).fetchall()
    total = sum(int(row["n"] or 0) for row in rows)
    notional = sum(float(row["notional"] or 0) for row in rows)
    return {
        "count": total,
        "notional": _money(notional),
        "by_status": {
            str(row["status"]): {
                "count": int(row["n"] or 0),
                "notional": _money(row["notional"]),
            }
            for row in rows
        },
    }


def _recent_trades(conn: sqlite3.Connection, cutoff: datetime) -> dict[str, Any]:
    if not _has_table(conn, "trades"):
        return {"fills": 0, "notional": 0.0}
    row = conn.execute(
        """
        SELECT COUNT(*) AS fills,
               COALESCE(SUM(COALESCE(price, 0) * COALESCE(size, 0)), 0) AS notional
        FROM trades
        WHERE bot_id = ?
          AND filled_at >= ?
        """,
        (BOT_ID, _sqlite_dt(cutoff)),
    ).fetchone()
    return {
        "fills": int(row["fills"] or 0) if row else 0,
        "notional": _money(row["notional"] if row else 0),
    }


def _recent_events(conn: sqlite3.Connection, cutoff: datetime) -> dict[str, int]:
    if not _has_table(conn, "events"):
        return {}
    rows = conn.execute(
        """
        SELECT event_type, COUNT(*) AS n
        FROM events
        WHERE bot_id = ?
          AND created_at >= ?
          AND event_type IN (
              'bot_d.nws_veto',
              'bot_d.forecast_entry',
              'bot_d.forecast_resolution',
              'bot_d.scan_summary',
              'bot_d.skewnorm_fallback',
              'bot_d.live_exit.stale'
          )
        GROUP BY event_type
        ORDER BY event_type
        """,
        (BOT_ID, _sqlite_dt(cutoff)),
    ).fetchall()
    return {str(row["event_type"]): int(row["n"] or 0) for row in rows}


def _latest_scan_summary(conn: sqlite3.Connection, cutoff: datetime) -> dict[str, Any]:
    if not _has_table(conn, "events") or "payload" not in _table_columns(conn, "events"):
        return {}
    row = conn.execute(
        """
        SELECT created_at, payload
        FROM events
        WHERE bot_id = ?
          AND event_type = 'bot_d.scan_summary'
          AND created_at >= ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (BOT_ID, _sqlite_dt(cutoff)),
    ).fetchone()
    if row is None:
        return {}
    payload = _payload(row["payload"])
    payload["created_at"] = row["created_at"]
    return payload


def _recent_forecast_entries(conn: sqlite3.Connection, cutoff: datetime) -> dict[str, Any]:
    """Validate forecast-entry payload shape and model/market probability joins."""
    if not _has_table(conn, "events") or "payload" not in _table_columns(conn, "events"):
        return {
            "count": 0,
            "latest_created_at": None,
            "latest_has_station_fields": False,
            "latest_has_forecast_fields": False,
            "probability_samples": 0,
            "avg_abs_edge": None,
            "avg_probability_disagreement": None,
            "model_timestamp_available": 0,
            "model_age_buckets": {"fresh_lte_6h": 0, "stale_gt_6h": 0, "missing": 0},
            "forecast_sources": {},
            "depth": _empty_depth_summary(),
        }
    rows = conn.execute(
        """
        SELECT created_at, payload
        FROM events
        WHERE bot_id = ?
          AND event_type = 'bot_d.forecast_entry'
          AND created_at >= ?
        ORDER BY created_at DESC
        """,
        (BOT_ID, _sqlite_dt(cutoff)),
    ).fetchall()
    if not rows:
        return {
            "count": 0,
            "latest_created_at": None,
            "latest_has_station_fields": False,
            "latest_has_forecast_fields": False,
            "probability_samples": 0,
            "avg_abs_edge": None,
            "avg_probability_disagreement": None,
            "model_timestamp_available": 0,
            "model_age_buckets": {"fresh_lte_6h": 0, "stale_gt_6h": 0, "missing": 0},
            "forecast_sources": {},
            "depth": _empty_depth_summary(),
        }

    latest_payload = _payload(rows[0]["payload"])
    station_keys = {
        "settlement_station",
        "observation_station",
        "settlement_source",
        "settlement_rounding",
        "settlement_unit",
        "settlement_verified",
    }
    forecast_keys = {
        "forecast_source",
        "forecast_fetched_at",
        "forecast_model_timestamp",
        "gfs_probability",
        "market_probability",
    }
    edge_values: list[float] = []
    disagreements: list[float] = []
    forecast_sources: dict[str, int] = defaultdict(int)
    model_age_buckets = {"fresh_lte_6h": 0, "stale_gt_6h": 0, "missing": 0}
    depth_rows: list[dict[str, Any]] = []
    for row in rows:
        created = _parse_dt(row["created_at"])
        payload = _payload(row["payload"])
        model_p = _to_float(payload.get("gfs_probability"))
        market_p = _to_float(payload.get("market_probability"))
        if model_p is not None and market_p is not None:
            edge_values.append(abs(model_p - market_p))
        empirical_p = _to_float(payload.get("empirical_probability"))
        if empirical_p is not None and model_p is not None:
            disagreements.append(abs(empirical_p - model_p))
        source = str(payload.get("forecast_source") or "missing")
        forecast_sources[source] += 1

        model_ts = _parse_dt(payload.get("forecast_model_timestamp"))
        if created is None or model_ts is None:
            model_age_buckets["missing"] += 1
        else:
            age_h = (created - model_ts).total_seconds() / 3600
            if age_h <= 6:
                model_age_buckets["fresh_lte_6h"] += 1
            else:
                model_age_buckets["stale_gt_6h"] += 1

        side = str(payload.get("side") or "")
        token_id = (
            str(payload.get("yes_token_id") or "")
            if side == "BUY_YES"
            else str(payload.get("no_token_id") or "")
        )
        limit_price = _to_float(payload.get("limit_price"))
        if created is not None and token_id and limit_price is not None:
            cap = _nearest_entry_book_capacity(
                conn,
                token_id=token_id,
                ts=created,
                limit_price=limit_price,
            )
            if cap is not None:
                depth_rows.append(cap)

    return {
        "count": len(rows),
        "latest_created_at": rows[0]["created_at"],
        "latest_has_station_fields": station_keys.issubset(latest_payload.keys()),
        "latest_has_forecast_fields": forecast_keys.issubset(latest_payload.keys()),
        "probability_samples": len(edge_values),
        "avg_abs_edge": round(sum(edge_values) / len(edge_values), 4) if edge_values else None,
        "avg_probability_disagreement": (
            round(sum(disagreements) / len(disagreements), 4)
            if disagreements
            else None
        ),
        "model_timestamp_available": (
            model_age_buckets["fresh_lte_6h"] + model_age_buckets["stale_gt_6h"]
        ),
        "model_age_buckets": model_age_buckets,
        "forecast_sources": dict(sorted(forecast_sources.items())),
        "depth": _depth_summary(depth_rows),
    }


def _empty_depth_summary() -> dict[str, Any]:
    return {
        "samples": 0,
        "average_notional_at_limit": 0.0,
        "targets_usd": {
            str(int(target)): {"covered": 0, "total": 0, "coverage_pct": 0.0}
            for target in DEPTH_TARGETS_USD
        },
    }


def _depth_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return _empty_depth_summary()
    out = _empty_depth_summary()
    out["samples"] = len(rows)
    out["average_notional_at_limit"] = round(
        sum(float(row.get("notional_at_limit") or 0) for row in rows) / len(rows),
        4,
    )
    for target in DEPTH_TARGETS_USD:
        key = str(int(target))
        covered = sum(1 for row in rows if (row.get("targets") or {}).get(key))
        out["targets_usd"][key] = {
            "covered": covered,
            "total": len(rows),
            "coverage_pct": round(covered / len(rows) * 100, 2),
        }
    return out


def _fifo_daily_resolved_pnl(conn: sqlite3.Connection) -> dict[str, Any]:
    """FIFO-match Bot D round trips and split daily/low-lock-up realised P&L."""
    if not _has_table(conn, "trades"):
        return {"all": _pnl_summary([]), "daily_low_lockup": _pnl_summary([])}
    trade_cols = _table_columns(conn, "trades")
    required = {"token_id", "side", "price", "size", "filled_at", "condition_id"}
    if not required.issubset(trade_cols):
        return {"all": _pnl_summary([]), "daily_low_lockup": _pnl_summary([])}
    market_join = "LEFT JOIN markets m ON m.condition_id = t.condition_id"
    rows = conn.execute(
        f"""
        SELECT t.token_id, t.side, t.price, t.size, t.filled_at,
               t.condition_id, m.end_date
        FROM trades t
        {market_join}
        WHERE t.bot_id = ?
        ORDER BY t.filled_at
        """,
        (BOT_ID,),
    ).fetchall()
    buys: dict[str, list[dict[str, Any]]] = defaultdict(list)
    closed: list[dict[str, Any]] = []
    for row in rows:
        side = str(row["side"] or "").upper()
        token_id = str(row["token_id"] or "")
        price = Decimal(str(row["price"] or 0))
        size = Decimal(str(row["size"] or 0))
        if side.startswith("BUY"):
            buys[token_id].append(
                {
                    "remaining": size,
                    "price": price,
                    "filled_at": row["filled_at"],
                    "end_date": row["end_date"],
                }
            )
            continue
        if not side.startswith("SELL"):
            continue
        remaining = size
        lots = buys.get(token_id, [])
        while remaining > 0 and lots:
            lot = lots[0]
            qty = min(remaining, lot["remaining"])
            pnl = (price - lot["price"]) * qty
            buy_cost = lot["price"] * qty
            buy_time = _parse_dt(lot["filled_at"])
            end_time = _parse_dt(lot["end_date"])
            lockup_hours = (
                (end_time - buy_time).total_seconds() / 3600
                if buy_time is not None and end_time is not None
                else None
            )
            closed.append(
                {
                    "pnl": float(pnl),
                    "cost": float(buy_cost),
                    "win": pnl > 0,
                    "lockup_hours": lockup_hours,
                }
            )
            lot["remaining"] -= qty
            remaining -= qty
            if lot["remaining"] <= 0:
                lots.pop(0)
    daily = [
        row for row in closed
        if row["lockup_hours"] is not None and row["lockup_hours"] <= 48
    ]
    return {
        "all": _pnl_summary(closed),
        "daily_low_lockup": _pnl_summary(daily),
    }


def _pnl_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnl = sum(float(row["pnl"]) for row in rows)
    cost = sum(float(row["cost"]) for row in rows)
    wins = [row for row in rows if float(row["pnl"]) > 0]
    wins_sorted = sorted(wins, key=lambda row: float(row["pnl"]), reverse=True)

    def without_wins(n: int) -> dict[str, Any]:
        removed = set(id(row) for row in wins_sorted[:n])
        kept = [row for row in rows if id(row) not in removed]
        kept_pnl = sum(float(row["pnl"]) for row in kept)
        kept_cost = sum(float(row["cost"]) for row in kept)
        return {
            "closed": len(kept),
            "pnl": round(kept_pnl, 4),
            "cost": round(kept_cost, 4),
            "roi_pct": round(kept_pnl / kept_cost * 100, 2) if kept_cost else None,
        }

    return {
        "closed": len(rows),
        "wins": len(wins),
        "pnl": round(pnl, 4),
        "cost": round(cost, 4),
        "roi_pct": round(pnl / cost * 100, 2) if cost else None,
        "ex_largest_win": without_wins(1),
        "ex_largest_two_wins": without_wins(2),
    }


def _verdict(
    open_orders: dict[str, Any],
    open_positions: dict[str, Any],
    recent_trades: dict[str, Any],
    forecast_entries: dict[str, Any],
    resolved_pnl: dict[str, Any],
    recent_events: dict[str, int],
) -> dict[str, Any]:
    blockers: list[str] = []
    if not BOT_D_LIVE_AUTHORIZED:
        blockers.append("live_authorization_missing")
    if recent_events.get("bot_d.skewnorm_fallback", 0):
        blockers.append("skewnorm_fallback_recent")
    if int((forecast_entries.get("forecast_sources") or {}).get("nws_fallback") or 0):
        blockers.append("nws_fallback_entry_recent")
    if open_orders["stale_48h_count"] or open_positions["stale_48h_count"]:
        blockers.append("stale_open_state")
    if open_orders["missing_market_count"]:
        blockers.append("missing_market_end_date")
    if recent_trades["fills"] == 0:
        blockers.append("no_recent_fills")
    if open_orders["by_duration"].get("weekly_lockup", {}).get("count", 0):
        blockers.append("weekly_lockup_present")
    depth = forecast_entries.get("depth") or {}
    depth_samples = int(depth.get("samples") or 0)
    cap25 = ((depth.get("targets_usd") or {}).get("25") or {})
    cap25_coverage = float(cap25.get("coverage_pct") or 0.0)
    if depth_samples < MIN_DEPTH_SAMPLES:
        blockers.append("insufficient_depth_sample")
    if depth_samples and cap25_coverage < MIN_25_USD_DEPTH_COVERAGE_PCT:
        blockers.append("weak_entry_depth")
    daily = (resolved_pnl or {}).get("daily_low_lockup") or {}
    daily_closed = int(daily.get("closed") or 0)
    ex2 = (daily.get("ex_largest_two_wins") or {}).get("roi_pct")
    if daily_closed < MIN_DAILY_CLOSED_SAMPLE:
        blockers.append("insufficient_resolved_sample")
    elif ex2 is None or float(ex2) < 0:
        blockers.append("negative_ex_outlier_roi")
    status = "blocked" if blockers else "watch"
    if "weak_entry_depth" in blockers or "insufficient_depth_sample" in blockers:
        next_action = (
            "Collect only depth-gated Bot D entries until $25 at-limit "
            "coverage and fill evidence are live-shaped."
        )
    elif "negative_ex_outlier_roi" in blockers:
        next_action = (
            "Keep the strict wave/depth paper lane running until daily "
            "ex-largest-two ROI is positive."
        )
    elif blockers:
        next_action = (
            "Split daily/weekly Bot D flow and reconcile stale opens before any live-wallet step."
        )
    else:
        next_action = "Continue strict paper proof; live still requires explicit operator approval."
    return {
        "status": status,
        "wallet_priority": True,
        "live_ready": False,
        "blockers": blockers,
        "next_action": next_action,
    }


def _station_coverage() -> dict[str, Any]:
    rows = settlement_coverage_rows()
    return {
        "cities": rows,
        "total": len(rows),
        "verified": sum(1 for row in rows if row["verified"]),
        "with_station": sum(1 for row in rows if row["station"]),
        "missing_station": [
            row["city"] for row in rows
            if not row["station"]
        ],
        "unverified": [
            row["city"] for row in rows
            if not row["verified"]
        ],
    }


def _entry_policy() -> dict[str, Any]:
    coverage = _station_coverage()
    return {
        "entry_halt": BOT_D_ENTRY_HALT,
        "require_verified_settlement": BOT_D_REQUIRE_VERIFIED_SETTLEMENT,
        "require_known_end_date": BOT_D_REQUIRE_KNOWN_END_DATE,
        "max_lockup_hours": BOT_D_MAX_LOCKUP_HOURS,
        "depth_gate_enabled": BOT_D_DEPTH_GATE_ENABLED,
        "min_entry_depth_usd": float(BOT_D_MIN_ENTRY_DEPTH_USD),
        "require_wave_for_entry": BOT_D_REQUIRE_WAVE_FOR_ENTRY,
        "live_authorized": BOT_D_LIVE_AUTHORIZED,
        "live_approved_at": BOT_D_LIVE_APPROVED_AT,
        "live_probe_mode": BOT_D_LIVE_PROBE_MODE,
        "live_wallet_usd": float(BOT_D_LIVE_WALLET_USD),
        "live_fixed_shares": float(BOT_D_LIVE_FIXED_SHARES),
        "live_max_order_usd": float(BOT_D_LIVE_MAX_ORDER_USD),
        "live_max_daily_gross_notional_usd": float(BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD),
        "live_max_open_exposure_usd": float(BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD),
        "live_max_concurrent_positions": BOT_D_LIVE_MAX_CONCURRENT_POSITIONS,
        "allow_nws_fallback_entry": BOT_D_ALLOW_NWS_FALLBACK_ENTRY,
        "paper_exit_slippage_bps": float(BOT_D_PAPER_EXIT_SLIPPAGE_BPS),
        "live_exit_limit_offset": float(BOT_D_LIVE_EXIT_LIMIT_OFFSET),
        "exit_stale_min": BOT_D_EXIT_STALE_MIN,
        "eligible_verified_cities": [
            row["city"] for row in coverage["cities"]
            if row["verified"] and row["station"]
        ],
    }


def build_report(
    db_path: Path,
    *,
    lookback_hours: int = 24,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=lookback_hours)
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        open_orders = _open_orders(conn, now)
        open_positions = _open_positions(conn, now)
        recent_orders = _recent_orders(conn, cutoff)
        recent_trades = _recent_trades(conn, cutoff)
        recent_events = _recent_events(conn, cutoff)
        latest_scan_summary = _latest_scan_summary(conn, cutoff)
        forecast_entries = _recent_forecast_entries(conn, cutoff)
        resolved_pnl = _fifo_daily_resolved_pnl(conn)
    finally:
        conn.close()
    return {
        "generated_at": now.isoformat(),
        "bot_id": BOT_ID,
        "lookback_hours": lookback_hours,
        "open_orders": open_orders,
        "open_positions": open_positions,
        "recent_orders": recent_orders,
        "recent_trades": recent_trades,
        "recent_events": recent_events,
        "latest_scan_summary": latest_scan_summary,
        "forecast_entries": forecast_entries,
        "resolved_pnl": resolved_pnl,
        "station_coverage": _station_coverage(),
        "entry_policy": _entry_policy(),
        "readiness": _verdict(
            open_orders,
            open_positions,
            recent_trades,
            forecast_entries,
            resolved_pnl,
            recent_events,
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    readiness = report["readiness"]
    lines = [
        "# Bot D Wallet-Readiness Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Lookback: `{report['lookback_hours']}h`",
        "",
        "## Verdict",
        "",
        f"- Wallet priority: `{readiness['wallet_priority']}`",
        f"- Live ready: `{readiness['live_ready']}`",
        f"- Status: `{readiness['status']}`",
        f"- Blockers: `{', '.join(readiness['blockers']) or 'none'}`",
        f"- Next action: {readiness['next_action']}",
        "",
        "## Lock-Up",
        "",
        "| Surface | Count | Notional/cost | Stale 48h | Max age h |",
        "|---|---:|---:|---:|---:|",
        (
            f"| Open orders | {report['open_orders']['count']} | "
            f"${report['open_orders']['notional']:.2f} | "
            f"{report['open_orders']['stale_48h_count']} | "
            f"{report['open_orders']['max_age_hours']} |"
        ),
        (
            f"| Open positions | {report['open_positions']['count']} | "
            f"${report['open_positions']['cost_basis']:.2f} | "
            f"{report['open_positions']['stale_48h_count']} | "
            f"{report['open_positions']['max_age_hours']} |"
        ),
        "",
        "## Open Orders By Duration",
        "",
        "| Duration | Count | Notional |",
        "|---|---:|---:|",
    ]
    for bucket, row in sorted(report["open_orders"]["by_duration"].items()):
        lines.append(f"| `{bucket}` | {row['count']} | ${row['notional']:.2f} |")
    if not report["open_orders"]["by_duration"]:
        lines.append("| n/a | 0 | $0.00 |")
    coverage = report["station_coverage"]
    policy = report["entry_policy"]
    lines.extend(
        [
            "",
            "## Station Coverage",
            "",
            f"- Cities: `{coverage['total']}`",
            f"- With station: `{coverage['with_station']}`",
            f"- Verified: `{coverage['verified']}`",
            f"- Missing station: `{', '.join(coverage['missing_station']) or 'none'}`",
            f"- Unverified: `{', '.join(coverage['unverified']) or 'none'}`",
            "",
            "## Entry Policy",
            "",
            f"- Entry halt: `{policy['entry_halt']}`",
            f"- Require verified settlement: `{policy['require_verified_settlement']}`",
            f"- Require known end date: `{policy['require_known_end_date']}`",
            f"- Max lock-up hours: `{policy['max_lockup_hours']}`",
            f"- Depth gate enabled: `{policy['depth_gate_enabled']}`",
            f"- Min entry depth: `${policy['min_entry_depth_usd']:.2f}`",
            f"- Require wave for entry: `{policy['require_wave_for_entry']}`",
            f"- Live authorized: `{policy['live_authorized']}`",
            f"- Live approved at: `{policy['live_approved_at'] or 'none'}`",
            f"- Live probe mode: `{policy['live_probe_mode'] or 'off'}`",
            f"- Live wallet: `${policy['live_wallet_usd']:.2f}`",
            f"- Live fixed shares: `{policy['live_fixed_shares']:.2f}`",
            f"- Live max order: `${policy['live_max_order_usd']:.2f}`",
            f"- Live daily gross cap: `${policy['live_max_daily_gross_notional_usd']:.2f}`",
            f"- Live open exposure cap: `${policy['live_max_open_exposure_usd']:.2f}`",
            f"- Live max concurrent: `{policy['live_max_concurrent_positions']}`",
            f"- Allow NWS fallback entry: `{policy['allow_nws_fallback_entry']}`",
            f"- Paper exit slippage: `{policy['paper_exit_slippage_bps']:.0f} bps`",
            f"- Live exit offset: `${policy['live_exit_limit_offset']:.3f}`",
            f"- Exit stale minutes: `{policy['exit_stale_min']}`",
            "- Eligible verified cities: "
            f"`{', '.join(policy['eligible_verified_cities']) or 'none'}`",
        ]
    )
    lines.extend(
        [
            "",
            "## Recent Flow",
            "",
            f"- Recent orders: `{report['recent_orders']['count']}`",
            f"- Recent fills: `{report['recent_trades']['fills']}`",
            f"- Recent NWS vetoes: `{report['recent_events'].get('bot_d.nws_veto', 0)}`",
            "- Recent forecast entries: "
            f"`{report['recent_events'].get('bot_d.forecast_entry', 0)}`",
            "- Recent scan summaries: "
            f"`{report['recent_events'].get('bot_d.scan_summary', 0)}`",
        ]
    )
    scan = report.get("latest_scan_summary") or {}
    if scan:
        lines.extend(
            [
                "",
                "## Latest Scan",
                "",
                f"- Created: `{scan.get('created_at')}`",
                f"- Raw / kept / evaluated: "
                f"`{scan.get('raw_markets', 0)} / {scan.get('kept_markets', 0)} / "
                f"{scan.get('evaluated', 0)}`",
                f"- Non-skip / tradeable: "
                f"`{scan.get('non_skip', 0)} / {scan.get('tradeable', 0)}`",
                f"- Missing forecasts: `{scan.get('missing_forecasts', 0)}`",
                f"- Top positive edge: `{float(scan.get('top_positive_net_edge') or 0):+.3f}`",
                f"- Top absolute edge: `{float(scan.get('top_abs_net_edge') or 0):+.3f}`",
                f"- Forecast sources: `{json.dumps(scan.get('forecast_sources') or {}, sort_keys=True)}`",
                f"- Skip reasons: `{json.dumps(scan.get('skip_reasons') or {}, sort_keys=True)}`",
            ]
        )
    fc = report["forecast_entries"]
    depth = fc["depth"]
    cap25 = depth["targets_usd"]["25"]
    cap50 = depth["targets_usd"]["50"]
    lines.extend(
        [
            "",
            "## Forecast Capture",
            "",
            f"- Forecast entries: `{fc['count']}`",
            f"- Latest entry: `{fc['latest_created_at'] or 'none'}`",
            f"- Latest has station fields: `{fc['latest_has_station_fields']}`",
            f"- Latest has forecast fields: `{fc['latest_has_forecast_fields']}`",
            f"- Probability samples: `{fc['probability_samples']}`",
            f"- Avg absolute model-market gap: `{fc['avg_abs_edge']}`",
            f"- Model timestamps present: `{fc['model_timestamp_available']}`",
            (
                "- Model age buckets: "
                f"`{fc['model_age_buckets']['fresh_lte_6h']}` fresh <=6h / "
                f"`{fc['model_age_buckets']['stale_gt_6h']}` stale >6h / "
                f"`{fc['model_age_buckets']['missing']}` missing"
            ),
            "",
            "## Depth",
            "",
            f"- Entry depth samples: `{depth['samples']}`",
            f"- Avg notional at limit: `${depth['average_notional_at_limit']:.2f}`",
            f"- `$25` coverage: `{cap25['covered']}/{cap25['total']}`",
            f"- `$50` coverage: `{cap50['covered']}/{cap50['total']}`",
        ]
    )
    lines.extend(
        [
            "",
            "## Resolved P&L",
            "",
            "| Cohort | Closed | Wins | PnL | Cost | ROI | Ex-largest-win ROI | Ex-largest-two ROI |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for key, label in (("daily_low_lockup", "daily/low-lock-up"), ("all", "all Bot D")):
        row = report["resolved_pnl"][key]
        ex1 = row["ex_largest_win"]["roi_pct"]
        ex2 = row["ex_largest_two_wins"]["roi_pct"]
        lines.append(
            "| {label} | {closed} | {wins} | ${pnl:+.2f} | ${cost:.2f} | {roi} | {ex1} | {ex2} |".format(
                label=label,
                closed=row["closed"],
                wins=row["wins"],
                pnl=row["pnl"],
                cost=row["cost"],
                roi="n/a" if row["roi_pct"] is None else f"{row['roi_pct']:+.1f}%",
                ex1="n/a" if ex1 is None else f"{ex1:+.1f}%",
                ex2="n/a" if ex2 is None else f"{ex2:+.1f}%",
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("./data/main.db"))
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--out-md", type=Path)
    parser.add_argument("--stdout-json", action="store_true")
    args = parser.parse_args()

    report = build_report(args.db, lookback_hours=args.lookback_hours)
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(render_markdown(report))
    if args.stdout_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    if not args.out_json and not args.out_md and not args.stdout_json:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
