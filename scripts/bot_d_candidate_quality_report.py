#!/usr/bin/env python3
"""Read-only Bot D candidate-quality report.

This report answers the narrow live-probe question: is Bot D seeing
high-quality weather candidates that are blocked by operational gates, or is
the current lane simply not finding enough edge yet?

It only reads SQLite and optional public trade-tape CSV data. It does not place,
cancel, reconcile, or mutate orders.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bots.bot_d_weather import labels as botd_labels  # noqa: E402

DEFAULT_DB = REPO_ROOT / "data" / "main.db"
DEFAULT_OUT_JSON = REPO_ROOT / "data" / "bot_d_candidate_quality_report.json"
DEFAULT_OUT_MD = REPO_ROOT / "data" / "bot_d_candidate_quality_report.md"
BOT_IDS = ("bot_d", "bot_d_live_probe")
CANDIDATE_EVENTS = ("bot_d.nws_veto", "bot_d.forecast_entry", "bot_d.entry_attempt")
SCAN_EVENT = "bot_d.scan_summary"


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(text.split(".")[0], "%Y-%m-%d %H:%M:%S")
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
    return botd_labels.to_float(value)


def _to_bool(value: object) -> bool:
    return botd_labels.to_bool(value)


def _bucket_width(payload: dict[str, Any]) -> float | None:
    low = _to_float(payload.get("bucket_low_f"))
    high = _to_float(payload.get("bucket_high_f"))
    if low is None or high is None:
        return None
    return abs(high - low)


def _edge(payload: dict[str, Any]) -> float | None:
    return botd_labels.edge(payload)


def _forecast_source(payload: dict[str, Any]) -> str:
    return botd_labels.forecast_source(payload)


def _is_ensemble_source(source: str) -> bool:
    return botd_labels.is_ensemble_source(source)


def _nws_threshold(payload: dict[str, Any], floor_f: float | None) -> float | None:
    return botd_labels.nws_threshold(payload, floor_f)


def _would_clear_nws(payload: dict[str, Any], floor_f: float | None) -> bool:
    return botd_labels.would_clear_nws(payload, floor_f)


def _setup_tier(payload: dict[str, Any]) -> tuple[str, str]:
    return botd_labels.setup_tier(payload)


class TapeSummary:
    def __init__(self) -> None:
        self.trade_count = 0
        self.usd_amount = 0.0
        self.min_price: float | None = None
        self.max_price: float | None = None
        self.last_price: float | None = None

    def add(self, price: float | None, usd: float | None) -> None:
        self.trade_count += 1
        if usd is not None:
            self.usd_amount += usd
        if price is None:
            return
        self.min_price = price if self.min_price is None else min(self.min_price, price)
        self.max_price = price if self.max_price is None else max(self.max_price, price)
        self.last_price = price

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_count": self.trade_count,
            "usd_amount": round(self.usd_amount, 2),
            "min_price": self.min_price,
            "max_price": self.max_price,
            "last_price": self.last_price,
        }


def _load_trade_tape(path: Path | None) -> dict[str, TapeSummary]:
    if path is None:
        return {}
    by_market: dict[str, TapeSummary] = defaultdict(TapeSummary)
    if not path.exists():
        raise FileNotFoundError(f"trade tape CSV not found: {path}")
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            market_id = (
                row.get("market_id")
                or row.get("condition_id")
                or row.get("gamma_id")
                or row.get("market")
            )
            if not market_id:
                continue
            price = _to_float(row.get("price") or row.get("event_price") or row.get("avg_price"))
            usd = _to_float(
                row.get("usd_amount")
                or row.get("notional")
                or row.get("volume_usd")
                or row.get("amount_usd")
            )
            by_market[str(market_id)].add(price, usd)
    return by_market


def _candidate_events(conn: sqlite3.Connection, cutoff: datetime) -> list[dict[str, Any]]:
    if not _has_table(conn, "events"):
        return []
    columns = _table_columns(conn, "events")
    if "payload" not in columns:
        return []
    placeholders = ", ".join("?" for _ in CANDIDATE_EVENTS)
    rows = conn.execute(
        f"""
        SELECT bot_id, event_type, created_at, payload
        FROM events
        WHERE bot_id IN (?, ?)
          AND event_type IN ({placeholders})
          AND created_at >= ?
        ORDER BY created_at DESC
        """,
        (*BOT_IDS, *CANDIDATE_EVENTS, _sqlite_dt(cutoff)),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = _payload(row["payload"])
        payload["_bot_id"] = row["bot_id"]
        payload["_event_type"] = row["event_type"]
        payload["_created_at"] = row["created_at"]
        out.append(payload)
    return out


def _recent_scan_summaries(conn: sqlite3.Connection, cutoff: datetime) -> list[dict[str, Any]]:
    if not _has_table(conn, "events") or "payload" not in _table_columns(conn, "events"):
        return []
    rows = conn.execute(
        """
        SELECT bot_id, created_at, payload
        FROM events
        WHERE bot_id IN (?, ?)
          AND event_type = ?
          AND created_at >= ?
        ORDER BY created_at DESC
        """,
        (*BOT_IDS, SCAN_EVENT, _sqlite_dt(cutoff)),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = _payload(row["payload"])
        payload["_bot_id"] = row["bot_id"]
        payload["_created_at"] = row["created_at"]
        out.append(payload)
    return out


def _orders_summary(conn: sqlite3.Connection, cutoff: datetime) -> dict[str, Any]:
    if not _has_table(conn, "orders"):
        return {"recent_orders": 0, "open_orders": 0, "by_bot": {}}
    rows = conn.execute(
        """
        SELECT bot_id, status, COUNT(*) AS n
        FROM orders
        WHERE bot_id IN (?, ?)
          AND placed_at >= ?
        GROUP BY bot_id, status
        """,
        (*BOT_IDS, _sqlite_dt(cutoff)),
    ).fetchall()
    by_status: Counter[str] = Counter()
    by_bot: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        bot_id = str(row["bot_id"])
        status = str(row["status"])
        n = int(row["n"] or 0)
        by_status[status] += n
        by_bot[bot_id][status] += n
    open_orders = sum(
        n
        for status, n in by_status.items()
        if status in {"OPEN", "PARTIAL", "PAPER_OPEN", "live", "MATCHED"}
    )
    return {
        "recent_orders": sum(by_status.values()),
        "open_orders": open_orders,
        "by_status": dict(sorted(by_status.items())),
        "by_bot": {bot_id: dict(sorted(counts.items())) for bot_id, counts in sorted(by_bot.items())},
    }


def _trades_summary(conn: sqlite3.Connection, cutoff: datetime) -> dict[str, Any]:
    if not _has_table(conn, "trades"):
        return {"fills": 0, "notional": 0.0, "by_bot": {}}
    rows = conn.execute(
        """
        SELECT bot_id, COUNT(*) AS fills, SUM(price * size) AS notional
        FROM trades
        WHERE bot_id IN (?, ?)
          AND filled_at >= ?
        GROUP BY bot_id
        """,
        (*BOT_IDS, _sqlite_dt(cutoff)),
    ).fetchall()
    by_bot = {
        str(row["bot_id"]): {
            "fills": int(row["fills"] or 0),
            "notional": round(float(row["notional"] or 0), 2),
        }
        for row in rows
    }
    return {
        "fills": sum(row["fills"] for row in by_bot.values()),
        "notional": round(sum(row["notional"] for row in by_bot.values()), 2),
        "by_bot": by_bot,
    }


def _candidate_row(payload: dict[str, Any], tape: dict[str, TapeSummary]) -> dict[str, Any]:
    event_type = str(payload.get("_event_type") or "")
    inferred_reason = str(payload.get("entry_attempt_reason") or payload.get("reason") or "")
    if not inferred_reason and event_type == "bot_d.nws_veto":
        inferred_reason = "nws_disagrees"
    elif not inferred_reason and event_type == "bot_d.forecast_entry":
        inferred_reason = "model entry"
    labels = botd_labels.enrich_payload(
        payload,
        reason=inferred_reason,
    )
    tier = str(payload.get("setup_tier") or labels.get("setup_tier") or "C")
    reason = str(payload.get("setup_tier_reason") or labels.get("setup_tier_reason") or "")
    edge = _edge(payload)
    condition_id = str(payload.get("condition_id") or "")
    tape_summary = tape.get(condition_id, TapeSummary()).as_dict()
    disagreement = _to_float(payload.get("nws_disagreement_f"))
    return {
        "created_at": payload.get("_created_at"),
        "bot_id": payload.get("_bot_id"),
        "event_type": payload.get("_event_type"),
        "city": payload.get("city"),
        "date": payload.get("date"),
        "temp_type": payload.get("temp_type"),
        "bucket_low_f": payload.get("bucket_low_f"),
        "bucket_high_f": payload.get("bucket_high_f"),
        "condition_id": condition_id or None,
        "settlement_verified": _to_bool(payload.get("settlement_verified")),
        "forecast_source": _forecast_source(payload),
        "ensemble_count": payload.get("ensemble_count"),
        "market_probability": _to_float(payload.get("market_probability")),
        "model_probability": _to_float(payload.get("gfs_probability")),
        "net_edge": edge,
        "abs_edge": abs(edge) if edge is not None else None,
        "nws_disagreement_f": disagreement,
        "nws_current_threshold_f": _to_float(payload.get("veto_threshold_f")),
        "would_clear_floor_3f": _would_clear_nws(payload, 3.0),
        "would_clear_floor_4f": _would_clear_nws(payload, 4.0),
        "would_clear_nws_off": _would_clear_nws(payload, None),
        "setup_tier": tier,
        "tier_reason": reason,
        "skip_reason_code": payload.get("skip_reason_code") or labels.get("skip_reason_code"),
        "entry_attempt_reason": payload.get("entry_attempt_reason"),
        "nws_lane": payload.get("nws_lane") or labels.get("nws_lane"),
        "source_confident": _to_bool(payload.get("source_confident", labels.get("source_confident"))),
        "exact_station_match": _to_bool(
            payload.get("exact_station_match", labels.get("exact_station_match"))
        ),
        "near_threshold": _to_bool(payload.get("near_threshold", labels.get("near_threshold"))),
        "distance_from_threshold_f": _to_float(
            payload.get("distance_from_threshold_f", labels.get("distance_from_threshold_f"))
        ),
        "wave_supported": _to_bool(payload.get("wave_supported", labels.get("wave_supported"))),
        "depth_usd": _to_float(payload.get("depth_usd")),
        "required_depth_usd": _to_float(payload.get("required_depth_usd")),
        "depth_lane": payload.get("depth_lane") or labels.get("depth_lane"),
        "trade_tape": tape_summary,
    }


def _summarise_candidates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tier_rank = {"A": 0, "B": 1, "C": 2}
    rows = sorted(
        rows,
        key=lambda row: (
            tier_rank.get(str(row.get("setup_tier")), 9),
            -(float(row["abs_edge"]) if row.get("abs_edge") is not None else 0.0),
            str(row.get("created_at") or ""),
        ),
    )
    by_event = Counter(str(row["event_type"]) for row in rows)
    by_tier = Counter(str(row["setup_tier"]) for row in rows)
    by_source = Counter(str(row["forecast_source"]) for row in rows)
    by_city = Counter(str(row["city"]) for row in rows if row.get("city"))
    by_skip_reason = Counter(str(row["skip_reason_code"]) for row in rows)
    by_nws_lane = Counter(str(row["nws_lane"]) for row in rows)
    by_depth_lane = Counter(str(row["depth_lane"]) for row in rows)
    by_source_confidence = Counter("confident" if row["source_confident"] else "uncertain" for row in rows)
    by_near_threshold = Counter("near" if row["near_threshold"] else "far_or_unknown" for row in rows)
    vetoes = [row for row in rows if row["event_type"] == "bot_d.nws_veto"]
    entries = [row for row in rows if row["event_type"] == "bot_d.forecast_entry"]
    attempts = [row for row in rows if row["event_type"] == "bot_d.entry_attempt"]
    live_attempts = [row for row in attempts if row.get("bot_id") == "bot_d_live_probe"]

    def _count_clear(key: str) -> int:
        return sum(1 for row in vetoes if row.get(key))

    abs_edges = [float(row["abs_edge"]) for row in rows if row.get("abs_edge") is not None]
    tape_rows = [row for row in rows if row["trade_tape"]["trade_count"] > 0]
    return {
        "count": len(rows),
        "entries": len(entries),
        "vetoes": len(vetoes),
        "entry_attempts": len(attempts),
        "live_entry_attempts": len(live_attempts),
        "by_event": dict(sorted(by_event.items())),
        "by_setup_tier": dict(sorted(by_tier.items())),
        "by_forecast_source": dict(sorted(by_source.items())),
        "by_city": dict(by_city.most_common(10)),
        "by_skip_reason_code": dict(by_skip_reason.most_common()),
        "by_nws_lane": dict(by_nws_lane.most_common()),
        "by_depth_lane": dict(by_depth_lane.most_common()),
        "by_source_confidence": dict(sorted(by_source_confidence.items())),
        "by_near_threshold": dict(sorted(by_near_threshold.items())),
        "entry_attempt_reasons": dict(
            Counter(str(row.get("entry_attempt_reason") or "unknown") for row in attempts).most_common()
        ),
        "live_entry_attempt_reasons": dict(
            Counter(str(row.get("entry_attempt_reason") or "unknown") for row in live_attempts).most_common()
        ),
        "avg_abs_edge": round(sum(abs_edges) / len(abs_edges), 4) if abs_edges else None,
        "veto_shadow": {
            "would_clear_floor_3f": _count_clear("would_clear_floor_3f"),
            "would_clear_floor_4f": _count_clear("would_clear_floor_4f"),
            "would_clear_nws_off": _count_clear("would_clear_nws_off"),
        },
        "trade_tape_matched_candidates": len(tape_rows),
        "top_candidates": rows[:12],
    }


def _summarise_scans(scans: list[dict[str, Any]]) -> dict[str, Any]:
    if not scans:
        return {
            "count": 0,
            "latest": None,
            "nws_shadow_totals": {},
            "skip_reasons": {},
            "forecast_sources": {},
        }
    shadow_totals: Counter[str] = Counter()
    skip_reasons: Counter[str] = Counter()
    forecast_sources: Counter[str] = Counter()
    for scan in scans:
        for key, val in (scan.get("nws_shadow") or {}).items():
            if isinstance(val, (int, float)):
                shadow_totals[str(key)] += int(val)
        for key, val in (scan.get("skip_reasons") or {}).items():
            if isinstance(val, (int, float)):
                skip_reasons[str(key)] += int(val)
        for key, val in (scan.get("forecast_sources") or {}).items():
            if isinstance(val, (int, float)):
                forecast_sources[str(key)] += int(val)
    return {
        "count": len(scans),
        "latest": scans[0],
        "nws_shadow_totals": dict(sorted(shadow_totals.items())),
        "skip_reasons": dict(skip_reasons.most_common()),
        "forecast_sources": dict(forecast_sources.most_common()),
    }


def _recommendation(candidate_summary: dict[str, Any], scan_summary: dict[str, Any], trades: dict[str, Any]) -> dict[str, Any]:
    tier_a = int(candidate_summary["by_setup_tier"].get("A", 0))
    entries = int(candidate_summary["entries"])
    live_attempts = int(candidate_summary.get("live_entry_attempts") or 0)
    live_fills = int((trades.get("by_bot") or {}).get("bot_d_live_probe", {}).get("fills", 0) or 0)
    paper_fills = int((trades.get("by_bot") or {}).get("bot_d", {}).get("fills", 0) or 0)
    shadow = scan_summary.get("nws_shadow_totals") or {}
    tradeable_3f = int(shadow.get("would_tradeable_floor_3f", 0) or 0)
    tradeable_4f = int(shadow.get("would_tradeable_floor_4f", 0) or 0)
    tradeable_off = int(shadow.get("would_tradeable_nws_off", 0) or 0)

    if live_fills > 0:
        return {
            "status": "review_live_fills",
            "next_action": "Compare live fill prices against paper candidate marks before loosening further.",
        }
    if live_attempts > 0:
        return {
            "status": "live_attempts_no_fills",
            "next_action": "Review live entry-attempt reasons and depth/cap lanes before changing NWS or size.",
        }
    if paper_fills > 0:
        return {
            "status": "paper_fills_no_live_fills",
            "next_action": "Keep the live probe active and compare the paper-filled candidates against live depth/order caps.",
        }
    if tier_a > 0 and entries == 0:
        return {
            "status": "candidate_blocked_before_entry",
            "next_action": "Inspect depth/wave/order caps for A-tier candidates; do not change forecast logic yet.",
        }
    if tradeable_4f > tradeable_3f:
        return {
            "status": "watch_4f_shadow",
            "next_action": "Keep current 3F live floor and collect 4F shadow evidence until at least 5 would-tradeable candidates appear.",
        }
    if tradeable_off > tradeable_4f:
        return {
            "status": "nws_veto_still_binding",
            "next_action": "Do not disable NWS veto; first prove the blocked candidates would pass spread/depth and settle profitably.",
        }
    return {
        "status": "insufficient_candidate_pressure",
        "next_action": "Leave tiny-live probe running; current evidence does not justify another loosen.",
    }


def build_report(
    db_path: Path = DEFAULT_DB,
    *,
    now: datetime | None = None,
    lookback_hours: int = 72,
    trade_tape_csv: Path | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=lookback_hours)
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tape = _load_trade_tape(trade_tape_csv)
        candidate_payloads = _candidate_events(conn, cutoff)
        candidate_rows = [_candidate_row(payload, tape) for payload in candidate_payloads]
        scan_summary = _summarise_scans(_recent_scan_summaries(conn, cutoff))
        candidate_summary = _summarise_candidates(candidate_rows)
        orders = _orders_summary(conn, cutoff)
        trades = _trades_summary(conn, cutoff)
    finally:
        conn.close()
    return {
        "generated_at": now.isoformat(),
        "db_path": str(db_path),
        "lookback_hours": lookback_hours,
        "trade_tape_csv": str(trade_tape_csv) if trade_tape_csv else None,
        "bot_ids": list(BOT_IDS),
        "orders": orders,
        "trades": trades,
        "candidates": candidate_summary,
        "scans": scan_summary,
        "recommendation": _recommendation(candidate_summary, scan_summary, trades),
    }


def render_markdown(report: dict[str, Any]) -> str:
    c = report["candidates"]
    scans = report["scans"]
    rec = report["recommendation"]
    shadow = scans.get("nws_shadow_totals") or {}
    latest = scans.get("latest") or {}
    lines = [
        "# Bot D Candidate-Quality Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Lookback: `{report['lookback_hours']}h`",
        f"Bot IDs: `{', '.join(report['bot_ids'])}`",
        "",
        "## Recommendation",
        "",
        f"- Status: `{rec['status']}`",
        f"- Next action: {rec['next_action']}",
        "",
        "## Candidate Flow",
        "",
        f"- Candidates: `{c['count']}`",
        f"- Forecast entries: `{c['entries']}`",
        f"- NWS veto candidates: `{c['vetoes']}`",
        f"- Entry attempts: `{c.get('entry_attempts', 0)}`",
        f"- Live entry attempts: `{c.get('live_entry_attempts', 0)}`",
        f"- Avg absolute edge: `{c['avg_abs_edge']}`",
        f"- Setup tiers: `{json.dumps(c['by_setup_tier'], sort_keys=True)}`",
        f"- Forecast sources: `{json.dumps(c['by_forecast_source'], sort_keys=True)}`",
        f"- Skip reason labels: `{json.dumps(c.get('by_skip_reason_code') or {}, sort_keys=True)}`",
        f"- NWS lanes: `{json.dumps(c.get('by_nws_lane') or {}, sort_keys=True)}`",
        f"- Depth lanes: `{json.dumps(c.get('by_depth_lane') or {}, sort_keys=True)}`",
        f"- Source confidence: `{json.dumps(c.get('by_source_confidence') or {}, sort_keys=True)}`",
        f"- Threshold distance: `{json.dumps(c.get('by_near_threshold') or {}, sort_keys=True)}`",
        f"- Top cities: `{json.dumps(c['by_city'], sort_keys=True)}`",
        f"- Trade-tape matched candidates: `{c['trade_tape_matched_candidates']}`",
        "",
        "## Live-Order Root Cause",
        "",
        f"- Live entry attempts: `{c.get('live_entry_attempts', 0)}`",
        f"- Live attempt reasons: `{json.dumps(c.get('live_entry_attempt_reasons') or {}, sort_keys=True)}`",
        f"- All attempt reasons: `{json.dumps(c.get('entry_attempt_reasons') or {}, sort_keys=True)}`",
        f"- Scan skip reasons: `{json.dumps(scans.get('skip_reasons') or {}, sort_keys=True)}`",
        "",
        "## NWS Shadow",
        "",
        f"- Candidate vetoes clearing 3F: `{c['veto_shadow']['would_clear_floor_3f']}`",
        f"- Candidate vetoes clearing 4F: `{c['veto_shadow']['would_clear_floor_4f']}`",
        f"- Candidate vetoes clearing NWS-off: `{c['veto_shadow']['would_clear_nws_off']}`",
        f"- Scan shadow totals: `{json.dumps(shadow, sort_keys=True)}`",
        "",
        "## Recent Bot Flow",
        "",
        f"- Recent orders: `{report['orders']['recent_orders']}`",
        f"- Open orders: `{report['orders']['open_orders']}`",
        f"- Recent fills: `{report['trades']['fills']}`",
        f"- Recent notional: `${report['trades']['notional']:.2f}`",
        "",
        "## Latest Scan",
        "",
    ]
    if latest:
        lines.extend(
            [
                f"- Created: `{latest.get('_created_at')}`",
                f"- Raw / kept / evaluated: `{latest.get('raw_markets', 0)} / {latest.get('kept_markets', 0)} / {latest.get('evaluated', 0)}`",
                f"- Non-skip / tradeable: `{latest.get('non_skip', 0)} / {latest.get('tradeable', 0)}`",
                f"- Skip reasons: `{json.dumps(latest.get('skip_reasons') or {}, sort_keys=True)}`",
                f"- Forecast sources: `{json.dumps(latest.get('forecast_sources') or {}, sort_keys=True)}`",
            ]
        )
    else:
        lines.append("- No scan summaries in lookback.")
    lines.extend(
        [
            "",
            "## Top Candidates",
            "",
            "| Created | Event | Tier | City | Date | Edge | Source | NWS lane | Depth | Reason |",
            "|---|---|---:|---|---|---:|---|---|---|---|",
        ]
    )
    for row in c["top_candidates"][:10]:
        lines.append(
            "| {created} | `{event}` | {tier} | {city} | {date} | {edge} | {source} | {nws} | {depth} | {reason} |".format(
                created=row.get("created_at") or "",
                event=row.get("event_type") or "",
                tier=row.get("setup_tier") or "",
                city=row.get("city") or "",
                date=row.get("date") or "",
                edge=f"{float(row['net_edge']):+.3f}" if row.get("net_edge") is not None else "n/a",
                source=row.get("forecast_source") or "",
                nws=row.get("nws_lane") or "n/a",
                depth=row.get("depth_lane") or "n/a",
                reason=row.get("entry_attempt_reason") or row.get("skip_reason_code") or "n/a",
            )
        )
    if not c["top_candidates"]:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--lookback-hours", type=int, default=72)
    parser.add_argument("--trade-tape-csv", type=Path, default=None)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    parser.add_argument("--now", default=None, help="Optional ISO timestamp for deterministic tests")
    args = parser.parse_args()

    now = _parse_dt(args.now) if args.now else None
    report = build_report(
        args.db,
        now=now,
        lookback_hours=args.lookback_hours,
        trade_tape_csv=args.trade_tape_csv,
    )
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"out_json": str(args.out_json), "out_md": str(args.out_md), "status": report["recommendation"]["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
