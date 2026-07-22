"""Bot D Station Lock — read-only paper performance report.

Queries bot_d.station_lock.* events from the local DB and prints a
structured summary. Safe to run at any time; never writes to the DB.

Usage:
    python scripts/bot_d_station_lock_report.py [--days 7]
    python scripts/bot_d_station_lock_report.py --json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any


def _load_events(db_path: str, *, lookback_days: int = 7) -> list[dict[str, Any]]:
    """Return station_lock events from the past N days."""
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    cutoff_text = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT event_type, message, payload, created_at
            FROM events
            WHERE bot_id = ?
              AND created_at >= ?
            ORDER BY created_at
            """,
            ("bot_d_station_lock", cutoff_text),
        ).fetchall()
    finally:
        conn.close()

    events: list[dict[str, Any]] = []
    for row in rows:
        payload_raw = row["payload"]
        if isinstance(payload_raw, dict):
            payload = payload_raw
        else:
            try:
                parsed = json.loads(payload_raw or "{}")
            except (TypeError, json.JSONDecodeError):
                parsed = {}
            payload = parsed if isinstance(parsed, dict) else {}
        events.append(
            {
                "event_type": row["event_type"],
                "message": row["message"],
                "payload": payload,
                "created_at": row["created_at"],
            }
        )
    return events


def build_report(db_path: str, *, lookback_days: int = 7) -> dict[str, Any]:
    events = _load_events(db_path, lookback_days=lookback_days)

    candidates = [e for e in events if e["event_type"] == "bot_d.station_lock.candidate"]
    entries = [e for e in events if e["event_type"] == "bot_d.station_lock.entry_attempt"]
    fills = [e for e in events if e["event_type"] == "bot_d.station_lock.paper_fill"]
    skips = [e for e in events if e["event_type"] == "bot_d.station_lock.skip"]
    resolutions = [e for e in events if e["event_type"] == "bot_d.station_lock.resolution"]
    mutations = [e for e in events if e["event_type"] == "bot_d.station_lock.source_mutation"]

    # Candidate breakdown
    by_city: Counter = Counter()
    by_station: Counter = Counter()
    by_source: Counter = Counter()
    by_state: Counter = Counter()
    by_confidence: Counter = Counter()
    rounding_disagreements = 0
    wu_mutations = len(mutations)

    for e in candidates:
        p = e["payload"]
        by_city[p.get("city", "?")] += 1
        by_station[p.get("station", "?")] += 1
        by_source[p.get("source", "?")] += 1
        by_state[p.get("state", "?")] += 1
        by_confidence[p.get("confidence", "?")] += 1
        if p.get("rounding_disagreement"):
            rounding_disagreements += 1

    # Skip reasons
    skip_reasons: Counter = Counter()
    for e in skips:
        skip_reasons[e["payload"].get("skip_reason_code", "unknown")] += 1

    total_paper_usd = sum(
        Decimal(str(e["payload"].get("paper_trade_usd", "0") or "0"))
        for e in fills
    )
    realised_pnl = sum(
        Decimal(str(e["payload"].get("paper_realised_pnl_usd", "0") or "0"))
        for e in resolutions
    )

    # Lag: time from entry to repricing (not yet tracked without exit events)
    # Resolution correctness
    hard_correct = hard_total = soft_correct = soft_total = 0
    for e in resolutions:
        p = e["payload"]
        conf = p.get("confidence", "")
        correct = bool(p.get("resolved_correct"))
        if conf == "hard":
            hard_total += 1
            if correct:
                hard_correct += 1
        elif conf == "soft":
            soft_total += 1
            if correct:
                soft_correct += 1

    # Best/worst (by edge at entry)
    sorted_entries = sorted(
        entries,
        key=lambda e: float(e["payload"].get("edge_after_buffer") or 0),
        reverse=True,
    )
    best = [
        {
            "condition_id": e["payload"].get("condition_id"),
            "city": e["payload"].get("city"),
            "side": e["payload"].get("certain_side"),
            "state": e["payload"].get("state"),
            "edge": e["payload"].get("edge_after_buffer"),
            "date": e["payload"].get("date"),
        }
        for e in sorted_entries[:5]
    ]
    worst = [
        {
            "condition_id": e["payload"].get("condition_id"),
            "city": e["payload"].get("city"),
            "side": e["payload"].get("certain_side"),
            "state": e["payload"].get("state"),
            "edge": e["payload"].get("edge_after_buffer"),
            "date": e["payload"].get("date"),
        }
        for e in reversed(sorted_entries[-5:])
        if e["payload"].get("edge_after_buffer") is not None
    ]

    return {
        "lookback_days": lookback_days,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "candidates": len(candidates),
            "entries": len(entries),
            "fills": len(fills),
            "skips": len(skips),
            "resolutions": len(resolutions),
            "total_paper_usd": str(total_paper_usd),
            "realised_pnl_usd": str(realised_pnl),
        },
        "candidates_by_city": dict(by_city.most_common()),
        "candidates_by_station": dict(by_station.most_common()),
        "candidates_by_source": dict(by_source.most_common()),
        "candidates_by_state": dict(by_state.most_common()),
        "candidates_by_confidence": dict(by_confidence.most_common()),
        "skip_reasons": dict(skip_reasons.most_common()),
        "resolution_correctness": {
            "hard_correct": hard_correct,
            "hard_total": hard_total,
            "hard_rate": round(hard_correct / hard_total, 4) if hard_total else None,
            "soft_correct": soft_correct,
            "soft_total": soft_total,
            "soft_rate": round(soft_correct / soft_total, 4) if soft_total else None,
            "rounding_disagreement_count": rounding_disagreements,
            "wu_station_mutation_count": wu_mutations,
        },
        "best_entries": best,
        "worst_entries": worst,
    }


def _print_report(report: dict[str, Any]) -> None:
    s = report["summary"]
    print(f"\n=== Bot D Station Lock Report ({report['lookback_days']}d) ===")
    print(f"Generated: {report['generated_at']}")
    print()
    print(f"Candidates:  {s['candidates']}")
    print(f"Entries:     {s['entries']}")
    print(f"Fills:       {s['fills']}")
    print(f"Skips:       {s['skips']}")
    print(f"Resolutions: {s['resolutions']}")
    print(f"Paper USD:   ${s['total_paper_usd']}")
    print(f"Realised P&L:${s['realised_pnl_usd']}")
    print()

    rc = report["resolution_correctness"]
    print("Resolution correctness:")
    if rc["hard_total"]:
        print(
            f"  Hard:  {rc['hard_correct']}/{rc['hard_total']} "
            f"({rc['hard_rate']:.1%})"
        )
    else:
        print("  Hard:  no resolved entries yet")
    print(f"  Rounding disagreements: {rc['rounding_disagreement_count']}")
    print(f"  WU station mutations:   {rc['wu_station_mutation_count']}")
    print()

    if report["candidates_by_city"]:
        print("Candidates by city:")
        for city, n in list(report["candidates_by_city"].items())[:10]:
            print(f"  {city}: {n}")
        print()

    if report["candidates_by_state"]:
        print("Candidates by state:")
        for state, n in report["candidates_by_state"].items():
            print(f"  {state}: {n}")
        print()

    if report["skip_reasons"]:
        print("Skip reasons:")
        for reason, n in report["skip_reasons"].items():
            print(f"  {reason}: {n}")
        print()

    if report["best_entries"]:
        print("Best entries (by edge):")
        for e in report["best_entries"]:
            print(
                f"  {e['city']} {e['date']} {e['side']} "
                f"state={e['state']} edge={e['edge']}"
            )
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bot D Station Lock report")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--db", default="data/main.db", help="SQLite DB path")
    args = parser.parse_args(argv)

    report = build_report(args.db, lookback_days=args.days)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
