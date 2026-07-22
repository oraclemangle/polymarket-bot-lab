#!/usr/bin/env python3
"""Read-only Bot D source-lag and station-bias report.

Consumes `bot_d.source_snapshot` plus existing forecast-entry events. It never
places, cancels, reconciles, or mutates orders.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import fmean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DB = REPO_ROOT / "data" / "main.db"
DEFAULT_OUT_JSON = REPO_ROOT / "data" / "bot_d_source_edge_report.json"
DEFAULT_OUT_MD = REPO_ROOT / "data" / "bot_d_source_edge_report.md"


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


def _avg(values: list[float]) -> float | None:
    return round(fmean(values), 3) if values else None


def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 2) if d else 0.0


def _recent_events(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    bot_id: str,
    cutoff: datetime,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT bot_id, event_type, payload, created_at FROM events "
        "WHERE bot_id=? AND event_type=? AND created_at >= ? ORDER BY created_at ASC",
        (bot_id, event_type, _sqlite_dt(cutoff)),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = _payload(row["payload"])
        payload["_bot_id"] = row["bot_id"]
        payload["_created_at"] = row["created_at"]
        out.append(payload)
    return out


def _source_summary(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    state_counts = Counter(str(p.get("bucket_state") or "unknown") for p in snapshots)
    city_counts = Counter(str(p.get("city") or "unknown") for p in snapshots)
    station_counts = Counter(str(p.get("settlement_station") or "unknown") for p in snapshots)
    sample_counts = [
        int((p.get("source_snapshot") or {}).get("sample_count") or 0)
        for p in snapshots
    ]
    raw_ages = [
        v for p in snapshots
        if (v := _to_float(p.get("raw_station_age_seconds"))) is not None
    ]
    lock_ages = [
        v for p in snapshots
        if (v := _to_float(p.get("lock_age_seconds"))) is not None
    ]
    source_lags = [
        v for p in snapshots
        if (v := _to_float(p.get("source_lag_seconds"))) is not None
    ]
    tomorrow_status_counts = Counter(
        str((p.get("tomorrow_io_snapshot") or {}).get("status") or "unknown")
        for p in snapshots
    )
    tomorrow_gaps = [
        v for p in snapshots
        if (v := _to_float(p.get("tomorrow_io_gap_to_station_f"))) is not None
    ]
    source_status_counts = Counter(
        str(p.get("source_station_status") or "unknown") for p in snapshots
    )
    source_matches = sum(1 for p in snapshots if bool(p.get("source_matches_station_metric")))
    late_certain = sum(
        1
        for p in snapshots
        if str(p.get("bucket_state")) in {"already_yes", "already_no", "locked_yes", "locked_no"}
    )
    impossible = sum(1 for p in snapshots if bool(p.get("bucket_impossible")))
    locked = sum(1 for p in snapshots if bool(p.get("bucket_locked")))
    return {
        "snapshots": len(snapshots),
        "by_bucket_state": dict(state_counts.most_common()),
        "by_city": dict(city_counts.most_common()),
        "by_station": dict(station_counts.most_common()),
        "late_certain": late_certain,
        "late_certain_pct": _pct(late_certain, len(snapshots)),
        "bucket_locked": locked,
        "bucket_impossible": impossible,
        "avg_station_samples": _avg([float(v) for v in sample_counts]),
        "avg_raw_station_age_seconds": _avg(raw_ages),
        "avg_lock_age_seconds": _avg(lock_ages),
        "source_visible_matches": source_matches,
        "source_visible_match_pct": _pct(source_matches, len(snapshots)),
        "avg_source_lag_seconds": _avg(source_lags),
        "by_source_station_status": dict(source_status_counts.most_common()),
        "by_tomorrow_io_status": dict(tomorrow_status_counts.most_common()),
        "tomorrow_io_matched_station_days": len(tomorrow_gaps),
        "tomorrow_io_avg_gap_to_station_f": _avg(tomorrow_gaps),
        "tomorrow_io_avg_abs_gap_to_station_f": _avg([abs(v) for v in tomorrow_gaps]),
    }


def _latest_snapshot_by_condition(
    snapshots: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for payload in snapshots:
        cid = str(payload.get("condition_id") or "")
        if not cid:
            continue
        created = _parse_dt(payload.get("_created_at")) or datetime.min.replace(tzinfo=UTC)
        prev = latest.get(cid)
        prev_created = (
            _parse_dt(prev.get("_created_at")) if prev is not None else None
        )
        if prev is None or prev_created is None or created >= prev_created:
            latest[cid] = payload
    return latest


def _forecast_residuals(
    snapshots: list[dict[str, Any]],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    latest = _latest_snapshot_by_condition(snapshots)
    by_station: dict[str, list[float]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    for entry in entries:
        cid = str(entry.get("condition_id") or "")
        snap = latest.get(cid)
        if not snap:
            continue
        temp_type = str(entry.get("temp_type") or snap.get("temp_type") or "")
        source_snapshot = snap.get("source_snapshot") or {}
        actual = _to_float(
            source_snapshot.get("raw_max_settlement_f")
            if temp_type == "high"
            else source_snapshot.get("raw_min_settlement_f")
        )
        forecast = _to_float(entry.get("forecast_mean_f"))
        if actual is None or forecast is None:
            continue
        residual = round(forecast - actual, 3)
        station = str(entry.get("settlement_station") or snap.get("settlement_station") or "unknown")
        by_station[station].append(residual)
        rows.append({
            "condition_id": cid,
            "city": entry.get("city") or snap.get("city"),
            "station": station,
            "date": entry.get("date") or snap.get("date"),
            "temp_type": temp_type,
            "forecast_mean_f": forecast,
            "station_actual_f": actual,
            "residual_f": residual,
            "bucket_state": snap.get("bucket_state"),
        })
    return {
        "matched_entries": len(rows),
        "avg_residual_f": _avg([float(r["residual_f"]) for r in rows]),
        "by_station": {
            station: {
                "n": len(vals),
                "avg_residual_f": _avg(vals),
                "avg_abs_residual_f": _avg([abs(v) for v in vals]),
            }
            for station, vals in sorted(by_station.items())
        },
        "recent_rows": rows[-20:],
    }


def _latest_late_certainty(snapshots: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    certain = [
        p for p in snapshots
        if str(p.get("bucket_state")) in {"already_yes", "already_no", "locked_yes", "locked_no"}
    ]
    certain.sort(key=lambda p: str(p.get("_created_at") or ""), reverse=True)
    out: list[dict[str, Any]] = []
    for p in certain[:limit]:
        out.append({
            "created_at": p.get("_created_at"),
            "condition_id": p.get("condition_id"),
            "city": p.get("city"),
            "station": p.get("settlement_station"),
            "date": p.get("date"),
            "temp_type": p.get("temp_type"),
            "bucket": [p.get("bucket_low_f"), p.get("bucket_high_f")],
            "state": p.get("bucket_state"),
            "yes_price": p.get("market_yes_price"),
            "station_metric_f": p.get("station_metric_f"),
            "lock_age_seconds": p.get("lock_age_seconds"),
        })
    return out


def build_report(
    db_path: Path = DEFAULT_DB,
    *,
    bot_id: str = "bot_d_live_probe",
    now: datetime | None = None,
    lookback_hours: int = 24,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=lookback_hours)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        snapshots = _recent_events(conn, event_type="bot_d.source_snapshot", bot_id=bot_id, cutoff=cutoff)
        entries = _recent_events(conn, event_type="bot_d.forecast_entry", bot_id=bot_id, cutoff=cutoff)
    finally:
        conn.close()
    return {
        "generated_at": now.isoformat(),
        "bot_id": bot_id,
        "lookback_hours": lookback_hours,
        "source_snapshots": _source_summary(snapshots),
        "forecast_residuals": _forecast_residuals(snapshots, entries),
        "latest_late_certainty": _latest_late_certainty(snapshots),
        "notes": [
            "source_lag_seconds is null until a market-visible final source poller is added.",
            "raw_station_age_seconds measures how stale the latest station observation was at snapshot time.",
            "lock_age_seconds measures how long the bucket had been physically locked/impossible before the snapshot.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    src = report["source_snapshots"]
    res = report["forecast_residuals"]
    lines = [
        "# Bot D Source Edge Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Lookback: `{report['lookback_hours']}h`",
        "",
        "## Source Snapshots",
        "",
        f"- Snapshots: `{src['snapshots']}`",
        f"- Late-certain buckets: `{src['late_certain']}` (`{src['late_certain_pct']}%`)",
        f"- Bucket locked YES: `{src['bucket_locked']}`",
        f"- Bucket impossible for YES: `{src['bucket_impossible']}`",
        f"- Avg station samples/snapshot: `{src['avg_station_samples']}`",
        f"- Avg raw station age seconds: `{src['avg_raw_station_age_seconds']}`",
        f"- Avg lock age seconds: `{src['avg_lock_age_seconds']}`",
        f"- Source-visible matches: `{src.get('source_visible_matches', 0)}` (`{src.get('source_visible_match_pct', 0.0)}%`)",
        f"- Avg source lag seconds: `{src.get('avg_source_lag_seconds')}`",
        f"- Tomorrow.io station-day matches: `{src.get('tomorrow_io_matched_station_days', 0)}`",
        f"- Tomorrow.io avg gap to station: `{src.get('tomorrow_io_avg_gap_to_station_f')}` F",
        f"- Tomorrow.io avg abs gap to station: `{src.get('tomorrow_io_avg_abs_gap_to_station_f')}` F",
        "",
        "### Bucket States",
        "",
    ]
    for state, n in (src.get("by_bucket_state") or {}).items():
        lines.append(f"- `{state}`: `{n}`")
    lines.extend(["", "### Stations", ""])
    for station, n in (src.get("by_station") or {}).items():
        lines.append(f"- `{station}`: `{n}`")
    lines.extend(["", "### Source Station Status", ""])
    for status, n in (src.get("by_source_station_status") or {}).items():
        lines.append(f"- `{status}`: `{n}`")
    lines.extend(["", "### Tomorrow.io Status", ""])
    for status, n in (src.get("by_tomorrow_io_status") or {}).items():
        lines.append(f"- `{status}`: `{n}`")
    lines.extend([
        "",
        "## Forecast Residuals",
        "",
        f"- Matched forecast entries: `{res['matched_entries']}`",
        f"- Avg residual forecast-minus-station: `{res['avg_residual_f']}` F",
        "",
        "| Station | N | Avg Residual F | Avg Abs Residual F |",
        "|---|---:|---:|---:|",
    ])
    for station, row in (res.get("by_station") or {}).items():
        lines.append(
            f"| {station} | {row['n']} | {row['avg_residual_f']} | {row['avg_abs_residual_f']} |"
        )
    lines.extend(["", "## Latest Late-Certainty Rows", ""])
    lines.append("| Time | City | Station | Date | Type | Bucket | State | YES | Metric F | Lock Age S |")
    lines.append("|---|---|---|---|---|---|---|---:|---:|---:|")
    for row in report.get("latest_late_certainty") or []:
        bucket = row.get("bucket") or []
        lines.append(
            f"| {row.get('created_at')} | {row.get('city')} | {row.get('station')} | "
            f"{row.get('date')} | {row.get('temp_type')} | {bucket} | {row.get('state')} | "
            f"{row.get('yes_price')} | {row.get('station_metric_f')} | {row.get('lock_age_seconds')} |"
        )
    lines.extend(["", "## Notes", ""])
    for note in report.get("notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--bot-id", default="bot_d_live_probe")
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    report = build_report(args.db, bot_id=args.bot_id, lookback_hours=args.lookback_hours)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
