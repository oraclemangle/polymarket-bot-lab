"""Daily health report for the Bot H Maker V2 Phase 1 recorder.

Reads `data/maker_recorder.db` read-only and produces a snapshot of:

- Event volume by type (book, price_change, last_trade_price,
  best_bid_ask, new_market, reconnect) over the last 24h and lifetime.
- Market coverage across the 4 target categories (politics, sports,
  awards, crypto).
- WSS health: heartbeat continuity, longest gap, reconnect count.
- DB size growth and estimated days-to-cap (10 GB per ADR-134).
- Per-category event throughput (events/hour) so the operator can spot
  which cells are quietest and which are most active.

Output: human-readable Markdown to stdout AND a JSON file at
`data/reports/bot_h_maker_v2_recorder/latest.json` for dashboard
consumption.

Usage:
    python -m scripts.bot_h_maker_v2_recorder_daily_report \
        [--db-path /home/operator/longshot-research/data/maker_recorder.db]
        [--lookback-hours 24]
        [--json-out data/reports/bot_h_maker_v2_recorder/latest.json]
        [--md-out data/reports/bot_h_maker_v2_recorder/latest.md]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

from scripts.research.markov_state_replay import estimate_transition_matrix, stationary_distribution

# Match ADR-134 disk budget so the alarm fires at the right moment.
# Amended Session 256: 10 GB → 30 GB after the 95%-of-traffic-is-broadcast
# diagnosis combined with the write-time filter in capture.py. The 30 GB
# budget plus the filter (estimated 95% volume cut) buys ≥1 year of
# headroom at observed event rates.
DISK_BUDGET_BYTES = 30 * 1024 * 1024 * 1024  # 30 GB

# Heartbeats fire every HEARTBEAT_INTERVAL_SEC seconds (default 30).
# A gap >= GAP_ALERT_SEC indicates the recorder stalled silently.
GAP_ALERT_SEC = 120
EXPECTED_CATEGORIES = ("politics", "sports", "awards", "crypto")
TOP_OF_BOOK_EVENT_TYPES = ("best_bid_ask", "book")

log = logging.getLogger(__name__)


def _connect(path: Path) -> sqlite3.Connection:
    """Open the recorder DB read-only so this script can never corrupt
    the live writer."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    for unit in ("KB", "MB", "GB"):
        n_f = n / 1024
        if n_f < 1024:
            return f"{n_f:.1f} {unit}"
        n = int(n_f)
    return f"{n / 1024:.1f} TB"


def _scalar(con: sqlite3.Connection, sql: str, params: tuple = ()) -> Any:
    cur = con.execute(sql, params)
    row = cur.fetchone()
    if row is None:
        return None
    return row[0]


def _event_summary(con: sqlite3.Connection, since_ms: int) -> dict[str, int]:
    """Count events by type over the lookback window AND lifetime."""
    rows = con.execute(
        """
        SELECT event_type, COUNT(*) AS n
        FROM pm_events
        WHERE received_at_ms >= ?
        GROUP BY event_type
        ORDER BY n DESC
        """,
        (since_ms,),
    ).fetchall()
    return {str(r["event_type"]): int(r["n"]) for r in rows}


def _category_coverage(con: sqlite3.Connection) -> dict[str, int]:
    """Markets per category. Static between gamma scans (5-min cadence)."""
    rows = con.execute(
        """
        SELECT category, COUNT(*) AS n
        FROM markets
        WHERE status='ACTIVE'
        GROUP BY category
        ORDER BY n DESC
        """
    ).fetchall()
    return {str(r["category"]): int(r["n"]) for r in rows}


def _per_category_events(con: sqlite3.Connection, since_ms: int) -> dict[str, int]:
    """Event count per category over lookback. Joins via condition_id."""
    rows = con.execute(
        """
        SELECT m.category, COUNT(*) AS n
        FROM pm_events e
        LEFT JOIN markets m ON m.condition_id = e.condition_id
        WHERE e.received_at_ms >= ?
        GROUP BY m.category
        ORDER BY n DESC
        """,
        (since_ms,),
    ).fetchall()
    return {(str(r["category"]) if r["category"] else "_unknown"): int(r["n"]) for r in rows}


def _heartbeat_health(con: sqlite3.Connection, since_ms: int) -> dict[str, Any]:
    """Heartbeat continuity: count, longest gap, last seen."""
    rows = con.execute(
        """
        SELECT received_at_ms
        FROM heartbeats
        WHERE received_at_ms >= ?
        ORDER BY received_at_ms ASC
        """,
        (since_ms,),
    ).fetchall()
    timestamps = [int(r["received_at_ms"]) for r in rows]
    if not timestamps:
        return {
            "count": 0,
            "longest_gap_sec": None,
            "last_heartbeat_age_sec": None,
        }
    gaps_sec = []
    for i in range(1, len(timestamps)):
        gaps_sec.append((timestamps[i] - timestamps[i - 1]) / 1000.0)
    longest_gap = max(gaps_sec) if gaps_sec else 0.0
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    last_age_sec = (now_ms - timestamps[-1]) / 1000.0
    return {
        "count": len(timestamps),
        "longest_gap_sec": longest_gap,
        "last_heartbeat_age_sec": last_age_sec,
    }


def _event_gaps(
    con: sqlite3.Connection,
    since_ms: int,
    *,
    threshold_sec: int = GAP_ALERT_SEC,
) -> dict[str, Any]:
    rows = con.execute(
        """
        SELECT received_at_ms
        FROM pm_events
        WHERE received_at_ms >= ?
        ORDER BY received_at_ms ASC
        """,
        (since_ms,),
    ).fetchall()
    timestamps = [int(r["received_at_ms"]) for r in rows]
    gaps: list[dict[str, Any]] = []
    for prev, curr in pairwise(timestamps):
        gap_sec = (curr - prev) / 1000.0
        if gap_sec > threshold_sec:
            gaps.append({
                "start_ms": prev,
                "end_ms": curr,
                "gap_sec": gap_sec,
            })
    return {
        "threshold_sec": threshold_sec,
        "count": len(gaps),
        "longest_gap_sec": max((g["gap_sec"] for g in gaps), default=0.0),
        "gaps": gaps[:20],
    }


def _percentile_nearest_rank(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int((percentile / 100.0) * len(ordered) + 0.999999))
    return ordered[min(rank, len(ordered)) - 1]


def _freshness_percentiles(ages_sec: list[float]) -> dict[str, Any]:
    return {
        "count": len(ages_sec),
        "p50_sec": _percentile_nearest_rank(ages_sec, 50),
        "p90_sec": _percentile_nearest_rank(ages_sec, 90),
        "p95_sec": _percentile_nearest_rank(ages_sec, 95),
        "p99_sec": _percentile_nearest_rank(ages_sec, 99),
        "max_sec": max(ages_sec) if ages_sec else None,
    }


def _active_market_tokens(con: sqlite3.Connection) -> list[dict[str, str]]:
    rows = con.execute(
        """
        SELECT condition_id, category, yes_token_id, no_token_id
        FROM markets
        WHERE status='ACTIVE'
        ORDER BY category, condition_id
        """
    ).fetchall()
    tokens: list[dict[str, str]] = []
    for row in rows:
        for side, token_key in (("yes", "yes_token_id"), ("no", "no_token_id")):
            token_id = row[token_key]
            if not token_id:
                continue
            tokens.append({
                "asset_id": str(token_id),
                "side": side,
                "condition_id": str(row["condition_id"]),
                "category": str(row["category"]),
            })
    return tokens


def _latest_top_of_book_by_asset(
    con: sqlite3.Connection,
    since_ms: int,
) -> dict[str, int]:
    rows = con.execute(
        """
        SELECT asset_id, MAX(received_at_ms) AS last_seen_ms
        FROM pm_events
        WHERE received_at_ms >= ?
          AND event_type IN ('best_bid_ask', 'book')
          AND asset_id IS NOT NULL
        GROUP BY asset_id
        """,
        (since_ms,),
    ).fetchall()
    return {str(r["asset_id"]): int(r["last_seen_ms"]) for r in rows if r["asset_id"]}


def _top_of_book_freshness(
    con: sqlite3.Connection,
    since_ms: int,
    *,
    now_ms: int,
    threshold_sec: int = GAP_ALERT_SEC,
) -> dict[str, Any]:
    active_tokens = _active_market_tokens(con)
    latest_by_asset = _latest_top_of_book_by_asset(con, since_ms)
    stale_tokens: list[dict[str, Any]] = []
    missing_tokens: list[dict[str, Any]] = []
    ages_sec: list[float] = []
    fresh_count = 0
    stale_by_category: dict[str, int] = {}
    top_by_category: dict[str, int] = {}
    for token in active_tokens:
        category = token["category"]
        top_by_category[category] = top_by_category.get(category, 0) + 1
        last_seen_ms = latest_by_asset.get(token["asset_id"])
        if last_seen_ms is None:
            missing_tokens.append(token)
            stale_by_category[category] = stale_by_category.get(category, 0) + 1
            continue
        age_sec = max(0.0, (now_ms - last_seen_ms) / 1000.0)
        ages_sec.append(age_sec)
        if age_sec > threshold_sec:
            stale_by_category[category] = stale_by_category.get(category, 0) + 1
            stale_tokens.append({**token, "age_sec": age_sec})
        else:
            fresh_count += 1
    stale_count = len(stale_tokens)
    missing_count = len(missing_tokens)
    return {
        "active_token_count": len(active_tokens),
        "fresh_token_count": fresh_count,
        "stale_token_count": stale_count,
        "missing_token_count": missing_count,
        "stale_threshold_sec": threshold_sec,
        "stale_tokens": stale_tokens[:20],
        "missing_tokens": missing_tokens[:20],
        "freshness_percentiles": _freshness_percentiles(ages_sec),
        "top_of_book_tokens_by_category": top_by_category,
        "stale_top_of_book_tokens_by_category": stale_by_category,
    }


def _reconnect_heartbeat_timeline(con: sqlite3.Connection, since_ms: int) -> dict[str, Any]:
    reconnect_rows = con.execute(
        """
        SELECT received_at_ms, subscription_id, event_type
        FROM pm_events
        WHERE received_at_ms >= ?
          AND event_type IN ('reconnect', 'disconnect')
        ORDER BY received_at_ms ASC
        """,
        (since_ms,),
    ).fetchall()
    heartbeat_rows = con.execute(
        """
        SELECT received_at_ms, subscription_id
        FROM heartbeats
        WHERE received_at_ms >= ?
        ORDER BY received_at_ms ASC
        """,
        (since_ms,),
    ).fetchall()
    events: list[dict[str, Any]] = []
    for row in reconnect_rows:
        events.append({
            "timestamp_ms": int(row["received_at_ms"]),
            "kind": str(row["event_type"]),
            "subscription_id": str(row["subscription_id"]),
        })
    for row in heartbeat_rows:
        events.append({
            "timestamp_ms": int(row["received_at_ms"]),
            "kind": "heartbeat",
            "subscription_id": str(row["subscription_id"]),
        })
    events.sort(key=lambda e: e["timestamp_ms"])
    return {
        "reconnect_count": sum(1 for e in events if e["kind"] == "reconnect"),
        "disconnect_count": sum(1 for e in events if e["kind"] == "disconnect"),
        "heartbeat_count": sum(1 for e in events if e["kind"] == "heartbeat"),
        "events": events[-50:],
    }


def _category_coverage_detail(
    con: sqlite3.Connection,
    since_ms: int,
    *,
    top_of_book: dict[str, Any],
) -> dict[str, Any]:
    def empty_category() -> dict[str, int]:
        return {
            "active_markets": 0,
            "resolved_markets": 0,
            "replayable_markets": 0,
            "events_24h": 0,
            "top_of_book_tokens": 0,
            "stale_top_of_book_tokens": 0,
        }

    active_rows = con.execute(
        """
        SELECT
            category,
            COUNT(*) AS active_markets
        FROM markets
        WHERE status='ACTIVE'
        GROUP BY category
        """
    ).fetchall()
    resolved_rows = con.execute(
        """
        SELECT category, COUNT(*) AS resolved_markets
        FROM markets
        WHERE yes_won IS NOT NULL
        GROUP BY category
        """
    ).fetchall()
    event_rows = con.execute(
        """
        SELECT m.category, COUNT(e.id) AS events_24h
        FROM pm_events e
        JOIN markets m ON m.condition_id = e.condition_id
        WHERE e.received_at_ms >= ?
        GROUP BY m.category
        """,
        (since_ms,),
    ).fetchall()
    replayable_rows = con.execute(
        """
        SELECT m.category, COUNT(DISTINCT m.condition_id) AS replayable_markets
        FROM markets m
        JOIN pm_events e ON e.condition_id = m.condition_id AND e.received_at_ms >= ?
        WHERE m.yes_won IS NOT NULL
        GROUP BY m.category
        """,
        (since_ms,),
    ).fetchall()
    categories: dict[str, dict[str, int]] = {cat: empty_category() for cat in EXPECTED_CATEGORIES}
    for row in active_rows:
        cat = str(row["category"])
        categories.setdefault(cat, empty_category())
        categories[cat]["active_markets"] = int(row["active_markets"] or 0)
    for row in resolved_rows:
        cat = str(row["category"])
        categories.setdefault(cat, empty_category())
        categories[cat]["resolved_markets"] = int(row["resolved_markets"] or 0)
    for row in event_rows:
        cat = str(row["category"])
        categories.setdefault(cat, empty_category())
        categories[cat]["events_24h"] = int(row["events_24h"] or 0)
    for row in replayable_rows:
        cat = str(row["category"])
        categories.setdefault(cat, empty_category())
        categories[cat]["replayable_markets"] = int(row["replayable_markets"] or 0)
    top_by_category = top_of_book.get("top_of_book_tokens_by_category", {})
    stale_by_category = top_of_book.get("stale_top_of_book_tokens_by_category", {})
    for cat, n in top_by_category.items():
        categories.setdefault(cat, empty_category())
        categories[cat]["top_of_book_tokens"] = int(n)
    for cat, n in stale_by_category.items():
        categories.setdefault(cat, empty_category())
        categories[cat]["stale_top_of_book_tokens"] = int(n)
    missing_categories = [
        cat for cat in EXPECTED_CATEGORIES
        if categories[cat]["active_markets"] == 0
    ]
    return {
        "expected_categories": list(EXPECTED_CATEGORIES),
        "missing_categories": missing_categories,
        "categories": categories,
    }


def _data_quality(con: sqlite3.Connection, since_ms: int, *, now_ms: int) -> dict[str, Any]:
    event_gaps = _event_gaps(con, since_ms)
    top_of_book = _top_of_book_freshness(con, since_ms, now_ms=now_ms)
    reconnect_timeline = _reconnect_heartbeat_timeline(con, since_ms)
    category_coverage = _category_coverage_detail(
        con,
        since_ms,
        top_of_book=top_of_book,
    )
    return {
        "event_gaps": event_gaps,
        "top_of_book": top_of_book,
        "freshness_percentiles": top_of_book["freshness_percentiles"],
        "reconnect_heartbeat_timeline": reconnect_timeline,
        "category_coverage": category_coverage,
        "markov_event_states": _markov_event_states(con, since_ms),
    }


def _event_state(event_type: str) -> str:
    if event_type in TOP_OF_BOOK_EVENT_TYPES:
        return "top_of_book"
    if event_type == "last_trade_price":
        return "trade"
    if event_type in {"reconnect", "disconnect"}:
        return event_type
    if event_type == "price_change":
        return "price_change"
    return "other"


def _markov_event_states(con: sqlite3.Connection, since_ms: int) -> dict[str, Any]:
    rows = con.execute(
        """
        SELECT event_type
        FROM pm_events
        WHERE received_at_ms >= ?
        ORDER BY received_at_ms ASC, id ASC
        """,
        (since_ms,),
    ).fetchall()
    sequence = [_event_state(str(r["event_type"])) for r in rows]
    states = ("top_of_book", "trade", "price_change", "reconnect", "disconnect", "other")
    estimate = estimate_transition_matrix(
        sequence,
        states=states,
        alpha=1.0,
        min_row_count=30,
        min_cell_count=20,
    )
    return {
        "posture": "research_only_no_live_gate",
        "n_events": len(sequence),
        "states": list(estimate.states),
        "transition_counts": estimate.counts,
        "transition_matrix": estimate.matrix,
        "stationary_distribution": stationary_distribution(estimate.matrix),
        "sparse_rows": estimate.sparse_rows,
        "sparse_cell_count": len(estimate.sparse_cells),
    }


def _db_size_bytes(path: Path) -> int:
    """Combined size of main DB + WAL + SHM, since SQLite splits writes
    across all three until checkpoint. Underestimate (excluding WAL)
    would mislead the disk-budget alarm."""
    total = 0
    for suffix in ("", "-wal", "-shm"):
        p = path.with_name(path.name + suffix)
        try:
            total += p.stat().st_size
        except FileNotFoundError:
            continue
    return total


def _estimate_days_to_cap(con: sqlite3.Connection, current_bytes: int) -> dict[str, Any]:
    """Linear extrapolation of disk usage based on the lookback window's
    event count. Assumes constant per-event byte cost. Conservative because
    real growth tapers as gamma cycles in/out fewer markets."""
    first_ts = _scalar(con, "SELECT MIN(received_at_ms) FROM pm_events")
    last_ts = _scalar(con, "SELECT MAX(received_at_ms) FROM pm_events")
    total_events = _scalar(con, "SELECT COUNT(*) FROM pm_events") or 0
    if not first_ts or not last_ts or total_events == 0:
        return {
            "current_bytes": current_bytes,
            "days_to_cap": None,
            "rate_bytes_per_day": None,
        }
    elapsed_sec = (last_ts - first_ts) / 1000.0
    if elapsed_sec <= 0:
        return {
            "current_bytes": current_bytes,
            "days_to_cap": None,
            "rate_bytes_per_day": None,
        }
    rate_bytes_per_sec = current_bytes / elapsed_sec
    rate_bytes_per_day = rate_bytes_per_sec * 86400
    remaining = DISK_BUDGET_BYTES - current_bytes
    days = remaining / rate_bytes_per_day if rate_bytes_per_day > 0 else None
    return {
        "current_bytes": current_bytes,
        "rate_bytes_per_day": rate_bytes_per_day,
        "days_to_cap": days,
    }


def build_report(
    *,
    db_path: Path,
    lookback_hours: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "ok": False,
            "reason": f"recorder DB not found at {db_path}",
            "generated_at": datetime.now(UTC).isoformat(),
        }
    now = now or datetime.now(UTC)
    since_ms = int(now.timestamp() * 1000) - lookback_hours * 3600 * 1000
    con = _connect(db_path)
    try:
        events_by_type_24h = _event_summary(con, since_ms)
        events_by_type_lifetime = _event_summary(con, 0)
        markets_by_category = _category_coverage(con)
        events_by_category = _per_category_events(con, since_ms)
        heartbeat = _heartbeat_health(con, since_ms)
        data_quality = _data_quality(con, since_ms, now_ms=int(now.timestamp() * 1000))
        size_bytes = _db_size_bytes(db_path)
        disk = _estimate_days_to_cap(con, size_bytes)
        total_events_24h = sum(events_by_type_24h.values())
        total_events_lifetime = sum(events_by_type_lifetime.values())
    finally:
        con.close()
    # Health flags
    flags: list[str] = []
    if heartbeat["count"] == 0:
        flags.append("NO_HEARTBEATS_IN_LOOKBACK")
    elif heartbeat["last_heartbeat_age_sec"] and heartbeat["last_heartbeat_age_sec"] > GAP_ALERT_SEC:
        flags.append(f"STALE_LAST_HEARTBEAT({heartbeat['last_heartbeat_age_sec']:.0f}s)")
    if heartbeat.get("longest_gap_sec") and heartbeat["longest_gap_sec"] > GAP_ALERT_SEC:
        flags.append(f"GAP_DETECTED({heartbeat['longest_gap_sec']:.0f}s)")
    if total_events_24h == 0:
        flags.append("NO_EVENTS_IN_LOOKBACK")
    if data_quality["event_gaps"]["count"] > 0:
        flags.append(f"EVENT_GAP_DETECTED({data_quality['event_gaps']['longest_gap_sec']:.0f}s)")
    if data_quality["top_of_book"]["stale_token_count"] > 0:
        flags.append(f"STALE_TOP_OF_BOOK({data_quality['top_of_book']['stale_token_count']})")
    if data_quality["top_of_book"]["missing_token_count"] > 0:
        flags.append(f"MISSING_TOP_OF_BOOK({data_quality['top_of_book']['missing_token_count']})")
    if disk["days_to_cap"] is not None and disk["days_to_cap"] < 30:
        flags.append(f"DISK_BUDGET_RUN_OUT_IN_{disk['days_to_cap']:.0f}D")
    if not markets_by_category:
        flags.append("NO_ACTIVE_MARKETS")
    return {
        "ok": True,
        "generated_at": now.isoformat(),
        "lookback_hours": lookback_hours,
        "db_path": str(db_path),
        "events_by_type_24h": events_by_type_24h,
        "events_by_type_lifetime": events_by_type_lifetime,
        "events_by_category_24h": events_by_category,
        "markets_by_category": markets_by_category,
        "total_events_24h": total_events_24h,
        "total_events_lifetime": total_events_lifetime,
        "heartbeat": heartbeat,
        "data_quality": data_quality,
        "disk": disk,
        "health_flags": flags,
    }


def render_markdown(report: dict[str, Any]) -> str:
    if not report.get("ok"):
        return f"# Bot H Maker V2 — Recorder Health\n\n**FAIL**: {report.get('reason', 'unknown error')}\n"
    lines: list[str] = []
    lines.append("# Bot H Maker V2 — Recorder Health")
    lines.append("")
    lines.append(f"**Generated:** {report['generated_at']}")
    lines.append(f"**DB:** `{report['db_path']}`")
    lines.append(f"**Lookback:** {report['lookback_hours']}h")
    lines.append("")
    flags = report["health_flags"]
    if flags:
        lines.append("## Health flags")
        for f in flags:
            lines.append(f"- ⚠ `{f}`")
        lines.append("")
    else:
        lines.append("## Health: GREEN ✓")
        lines.append("")
    lines.append("## Throughput")
    lines.append("")
    lines.append(f"- 24h events: **{report['total_events_24h']:,}**")
    lines.append(f"- Lifetime events: **{report['total_events_lifetime']:,}**")
    hb = report["heartbeat"]
    lines.append(
        f"- Heartbeats (24h): {hb['count']}, longest gap: "
        f"{hb['longest_gap_sec']:.0f}s, last age: "
        f"{hb['last_heartbeat_age_sec']:.0f}s"
        if hb["count"] else "- Heartbeats: NONE"
    )
    lines.append("")
    lines.append("## Events by type (24h)")
    lines.append("")
    lines.append("| type | count |")
    lines.append("|---|---:|")
    for t, n in sorted(report["events_by_type_24h"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {t} | {n:,} |")
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append("| category | markets active | events 24h |")
    lines.append("|---|---:|---:|")
    cats = sorted(
        set(report["markets_by_category"].keys()) | set(report["events_by_category_24h"].keys())
    )
    for cat in cats:
        n_mkt = report["markets_by_category"].get(cat, 0)
        n_evt = report["events_by_category_24h"].get(cat, 0)
        lines.append(f"| {cat} | {n_mkt} | {n_evt:,} |")
    lines.append("")
    dq = report.get("data_quality", {})
    if dq:
        gaps = dq["event_gaps"]
        tob = dq["top_of_book"]
        pct = dq["freshness_percentiles"]
        timeline = dq["reconnect_heartbeat_timeline"]
        coverage = dq["category_coverage"]
        markov = dq.get("markov_event_states", {})
        lines.append("## Data quality")
        lines.append("")
        lines.append(
            f"- Event gaps >{gaps['threshold_sec']}s: **{gaps['count']}**, "
            f"longest: **{gaps['longest_gap_sec']:.0f}s**"
        )
        lines.append(
            f"- Top-of-book freshness: **{tob['fresh_token_count']}/"
            f"{tob['active_token_count']} fresh**, "
            f"**{tob['stale_token_count']} stale**, "
            f"**{tob['missing_token_count']} missing**"
        )
        if pct["count"]:
            lines.append(
                "- Freshness age percentiles: "
                f"p50 **{pct['p50_sec']:.0f}s**, "
                f"p90 **{pct['p90_sec']:.0f}s**, "
                f"p95 **{pct['p95_sec']:.0f}s**, "
                f"p99 **{pct['p99_sec']:.0f}s**, "
                f"max **{pct['max_sec']:.0f}s**"
            )
        else:
            lines.append("- Freshness age percentiles: no top-of-book events")
        lines.append(
            f"- Reconnects: **{timeline['reconnect_count']}**, "
            f"disconnects: **{timeline['disconnect_count']}**, "
            f"heartbeats: **{timeline['heartbeat_count']}**"
        )
        missing = coverage["missing_categories"]
        if missing:
            missing_label = ", ".join(f"`{cat}`" for cat in missing)
            lines.append(f"- Missing categories: {missing_label}")
        else:
            lines.append("- Missing categories: none")
        lines.append(
            f"- Markov event states: **{markov.get('n_events', 0)} events**, "
            f"**{len(markov.get('sparse_rows') or [])} sparse rows**, "
            f"**{markov.get('sparse_cell_count', 0)} sparse cells**"
        )
        lines.append("")
    lines.append("## Disk")
    lines.append("")
    disk = report["disk"]
    lines.append(f"- Current size: **{_format_bytes(disk['current_bytes'])}**")
    if disk["rate_bytes_per_day"]:
        lines.append(f"- Growth rate: **{_format_bytes(int(disk['rate_bytes_per_day']))}/day**")
    if disk["days_to_cap"] is not None:
        emoji = "⚠" if disk["days_to_cap"] < 30 else "✓"
        budget_label = f"{DISK_BUDGET_BYTES // (1024**3)} GB"
        lines.append(f"- Days to {budget_label} cap: **{disk['days_to_cap']:.1f}d** {emoji}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path(
            os.environ.get(
                "BOT_H_MAKER_V2_RECORDER_DB_PATH",
                "data/maker_recorder.db",
            )
        ),
    )
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path(
            os.environ.get(
                "BOT_H_MAKER_V2_RECORDER_DAILY_REPORT_JSON",
                "data/reports/bot_h_maker_v2_recorder/latest.json",
            )
        ),
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=Path(
            os.environ.get(
                "BOT_H_MAKER_V2_RECORDER_DAILY_REPORT_MD",
                "data/reports/bot_h_maker_v2_recorder/latest.md",
            )
        ),
    )
    parser.add_argument("--no-files", action="store_true", help="stdout only, no file writes")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    report = build_report(db_path=args.db_path, lookback_hours=args.lookback_hours)
    md = render_markdown(report)
    print(md)
    if not args.no_files:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2))
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(md)
        log.info("recorder.report.written json=%s md=%s", args.json_out, args.md_out)


if __name__ == "__main__":
    main()
