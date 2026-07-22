#!/usr/bin/env python3
"""Probe Bot L recorder quote payloads for usable top-of-book sizes."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bots.bot_l_complete_set.simulator import DEFAULT_RECORDER_DB

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "reports" / "bot_l_complete_set"


def _connect_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _positive_float(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _levels_have_size(levels: Any) -> bool:
    if not isinstance(levels, list):
        return False
    return any(isinstance(level, dict) and _positive_float(level.get("size")) for level in levels)


def probe_depth_sources(recorder_db_path: Path, lookback_hours: float) -> dict[str, Any]:
    conn = _connect_ro(recorder_db_path)
    try:
        since_ms = int(datetime.now(UTC).timestamp() * 1000 - lookback_hours * 3_600_000)
        btc_5m_conditions = {
            str(row["condition_id"])
            for row in conn.execute(
                """
                SELECT DISTINCT condition_id
                FROM markets
                WHERE symbol = 'BTC'
                  AND duration_minutes = 5
                """
            )
        }
        rows = conn.execute(
            """
            SELECT condition_id, event_type, payload_json
            FROM pm_events
            WHERE received_at_ms >= ?
              AND event_type IN ('best_bid_ask', 'book')
            """,
            (since_ms,),
        ).fetchall()
    finally:
        conn.close()

    by_type: dict[str, dict[str, int]] = {}
    for row in rows:
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            payload = {}
        condition_id = row["condition_id"] or payload.get("market")
        if str(condition_id) not in btc_5m_conditions:
            continue
        event_type = str(row["event_type"] or "unknown")
        bucket = by_type.setdefault(
            event_type,
            {
                "rows": 0,
                "direct_bid_size": 0,
                "direct_ask_size": 0,
                "book_bid_size": 0,
                "book_ask_size": 0,
                "invalid_payload": 0,
            },
        )
        bucket["rows"] += 1
        if not payload:
            bucket["invalid_payload"] += 1
            continue
        if _positive_float(payload.get("best_bid_size")):
            bucket["direct_bid_size"] += 1
        if _positive_float(payload.get("best_ask_size")):
            bucket["direct_ask_size"] += 1
        if _levels_have_size(payload.get("bids")):
            bucket["book_bid_size"] += 1
        if _levels_have_size(payload.get("asks")):
            bucket["book_ask_size"] += 1
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "recorder_db_path": str(recorder_db_path),
        "lookback_hours": lookback_hours,
        "by_event_type": by_type,
        "posture": {
            "paper_only": True,
            "wallet": False,
            "live_orders": False,
            "adr": "ADR-159",
            "open_question": "OQ-111",
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Bot L Depth Source Probe",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Lookback hours: `{report['lookback_hours']}`",
        "",
        "| event_type | rows | direct_bid_size | direct_ask_size | book_bid_size | book_ask_size | invalid |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for event_type, row in sorted((report.get("by_event_type") or {}).items()):
        lines.append(
            "| {event_type} | {rows} | {direct_bid} | {direct_ask} | {book_bid} | {book_ask} | {invalid} |".format(
                event_type=event_type,
                rows=row.get("rows", 0),
                direct_bid=row.get("direct_bid_size", 0),
                direct_ask=row.get("direct_ask_size", 0),
                book_bid=row.get("book_bid_size", 0),
                book_ask=row.get("book_ask_size", 0),
                invalid=row.get("invalid_payload", 0),
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_text = json.dumps(report, indent=2, sort_keys=True)
    md_text = render_markdown(report)
    json_path = out_dir / f"bot_l_complete_set_depth_probe_{stamp}.json"
    md_path = out_dir / f"bot_l_complete_set_depth_probe_{stamp}.md"
    latest_json = out_dir / "latest_depth_probe.json"
    latest_md = out_dir / "latest_depth_probe.md"
    json_path.write_text(json_text + "\n", encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    latest_json.write_text(json_text + "\n", encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "latest_json": str(latest_json),
        "latest_markdown": str(latest_md),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recorder-db-path", type=Path, default=DEFAULT_RECORDER_DB)
    parser.add_argument("--lookback-hours", type=float, default=168.0)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    report = probe_depth_sources(args.recorder_db_path, args.lookback_hours)
    paths = write_outputs(report, args.out_dir)
    print(json.dumps({"generated_at": report["generated_at"], "paths": paths}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
