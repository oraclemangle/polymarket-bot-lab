#!/usr/bin/env python3
"""Read-only report for Bot D Ensemble Ladder paper events."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DB = REPO_ROOT / "data" / "main.db"
DEFAULT_OUT_MD = REPO_ROOT / "data" / "bot_d_ensemble_ladder_report.md"
DEFAULT_OUT_JSON = REPO_ROOT / "data" / "bot_d_ensemble_ladder_report.json"
BOT_ID = "bot_d_ensemble_ladder"


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
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


def _dec(value: object, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _recent_events(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    since: datetime,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT event_type, payload, created_at FROM events "
        "WHERE bot_id=? AND event_type=? AND created_at >= ? ORDER BY created_at ASC",
        (BOT_ID, event_type, _sqlite_dt(since)),
    ).fetchall()
    out = []
    for row in rows:
        payload = _payload(row["payload"])
        payload["_created_at"] = row["created_at"]
        out.append(payload)
    return out


def build_report(*, db_path: Path = DEFAULT_DB, lookback_hours: int = 168) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(hours=lookback_hours)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        plans = _recent_events(conn, event_type="bot_d_ensemble_ladder.plan", since=since)
        scans = _recent_events(conn, event_type="bot_d_ensemble_ladder.scan_summary", since=since)
    finally:
        conn.close()

    city_counts = Counter(str(p.get("city") or "unknown") for p in plans)
    temp_counts = Counter(str(p.get("temp_type") or "unknown") for p in plans)
    leg_counts = Counter(str(len(p.get("legs") or [])) for p in plans)
    skip_counts: Counter[str] = Counter()
    for scan in scans:
        for reason, count in (scan.get("skip_reasons") or {}).items():
            try:
                skip_counts[str(reason)] += int(count)
            except Exception:
                continue

    planned_stake = sum(
        (_dec(p.get("planned_stake_usd")) for p in plans),
        Decimal("0"),
    )
    avg_total_yes_price = (
        sum(_dec(p.get("total_yes_price")) for p in plans) / Decimal(len(plans))
        if plans else Decimal("0")
    )
    latest_plan = plans[-1] if plans else None
    latest_scan = scans[-1] if scans else None

    return {
        "bot_id": BOT_ID,
        "lookback_hours": lookback_hours,
        "generated_at": datetime.now(UTC).isoformat(),
        "plans": len(plans),
        "scans": len(scans),
        "planned_stake_usd": str(planned_stake.quantize(Decimal("0.01"))),
        "avg_total_yes_price": str(avg_total_yes_price.quantize(Decimal("0.0001"))),
        "by_city": dict(city_counts.most_common()),
        "by_temp_type": dict(temp_counts.most_common()),
        "by_leg_count": dict(leg_counts.most_common()),
        "skip_reasons": dict(skip_counts.most_common()),
        "latest_plan": latest_plan,
        "latest_scan": latest_scan,
    }


def _table(rows: list[tuple[str, object]]) -> str:
    if not rows:
        return "_None._"
    lines = ["| Key | Value |", "|---|---:|"]
    for key, value in rows:
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines)


def render_markdown(report: dict[str, Any]) -> str:
    latest_plan = report.get("latest_plan") or {}
    latest_scan = report.get("latest_scan") or {}
    lines = [
        "# Bot D Ensemble Ladder Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Lookback:** {report['lookback_hours']}h",
        f"**Bot ID:** `{report['bot_id']}`",
        "",
        "## Summary",
        "",
        _table([
            ("plans", report["plans"]),
            ("scans", report["scans"]),
            ("planned_stake_usd", report["planned_stake_usd"]),
            ("avg_total_yes_price", report["avg_total_yes_price"]),
        ]),
        "",
        "## Plans By City",
        "",
        _table(list((report.get("by_city") or {}).items())),
        "",
        "## Plans By Temperature Type",
        "",
        _table(list((report.get("by_temp_type") or {}).items())),
        "",
        "## Plans By Leg Count",
        "",
        _table(list((report.get("by_leg_count") or {}).items())),
        "",
        "## Skip Reasons",
        "",
        _table(list((report.get("skip_reasons") or {}).items())),
        "",
        "## Latest Plan",
        "",
    ]
    if latest_plan:
        lines.extend([
            f"- Event: `{latest_plan.get('event_key')}`",
            f"- Center: `{latest_plan.get('center_native')}` {latest_plan.get('unit')}",
            f"- Models: `{latest_plan.get('model_values_native')}`",
            f"- Legs: `{len(latest_plan.get('legs') or [])}`",
            f"- Total YES price: `{latest_plan.get('total_yes_price')}`",
            f"- Planned stake: `${latest_plan.get('planned_stake_usd')}`",
        ])
    else:
        lines.append("_No plans in lookback._")
    lines.extend([
        "",
        "## Latest Scan",
        "",
        "```json",
        json.dumps(latest_scan, indent=2, sort_keys=True),
        "```",
        "",
    ])
    return "\n".join(lines)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--lookback-hours", type=int, default=168)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_report(db_path=args.db, lookback_hours=args.lookback_hours)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    args.out_md.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {args.out_md}")
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
