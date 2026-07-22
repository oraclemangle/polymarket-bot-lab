"""Read-only fleet trade-flow report.

Summarises which bots are merely online versus which are producing orders,
fills, and rejection/veto telemetry. Intended for daily tuning decisions before
loosening any strategy gate.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO / "data" / "main.db"
DEFAULT_OUT_JSON = REPO / "data" / "fleet_tradeflow_report.json"
DEFAULT_OUT_MD = REPO / "data" / "fleet_tradeflow_report.md"


def _sqlite_dt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


WATCHED_EVENT_TYPES = (
    "bot_d.nws_veto",
    "bot_d.forecast_entry",
    "bot_e.scan_summary",
    "bot_e.signal",
    "bot_e.cex_cvd_skip",
    "bot_e.depth_skip",
    "bot_e.rejected",
    "bot_e.ttl_cancel",
    "bot_f.mirror_signal",
    "bot_g.candidate_summary",
    "bot_g.entry_placed",
    "bot_g.prime_rejected",
    "watchdog.halt",
    "watchdog.unhalt",
)


def _rows_as_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description or []]
    return [dict(zip(cols, row, strict=False)) for row in cursor.fetchall()]


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def run_report(db_path: Path, *, lookback_hours: float) -> dict:
    since = datetime.now(UTC) - timedelta(hours=lookback_hours)
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        orders = []
        trades = []
        events = []
        halt_flags = []
        recent_watchdog = []
        if _has_table(conn, "orders"):
            orders = _rows_as_dicts(
                conn.execute(
                    """
                    SELECT bot_id, status, COUNT(*) AS n,
                           ROUND(SUM(COALESCE(price, 0) * COALESCE(size, 0)), 2) AS notional,
                           MIN(placed_at) AS first_seen,
                           MAX(placed_at) AS last_seen
                    FROM orders
                    WHERE placed_at >= ?
                    GROUP BY bot_id, status
                    ORDER BY bot_id, status
                    """,
                    (_sqlite_dt(since),),
                )
            )
        if _has_table(conn, "trades"):
            trades = _rows_as_dicts(
                conn.execute(
                    """
                    SELECT bot_id, COUNT(*) AS fills,
                           ROUND(SUM(COALESCE(price, 0) * COALESCE(size, 0)), 2) AS notional,
                           MIN(filled_at) AS first_seen,
                           MAX(filled_at) AS last_seen
                    FROM trades
                    WHERE filled_at >= ?
                    GROUP BY bot_id
                    ORDER BY bot_id
                    """,
                    (_sqlite_dt(since),),
                )
            )
        if _has_table(conn, "events"):
            placeholders = ",".join("?" for _ in WATCHED_EVENT_TYPES)
            events = _rows_as_dicts(
                conn.execute(
                    f"""
                    SELECT COALESCE(bot_id, '') AS bot_id, event_type,
                           COUNT(*) AS n,
                           MIN(created_at) AS first_seen,
                           MAX(created_at) AS last_seen
                    FROM events
                    WHERE created_at >= ?
                      AND event_type IN ({placeholders})
                    GROUP BY bot_id, event_type
                    ORDER BY bot_id, event_type
                    """,
                    (_sqlite_dt(since), *WATCHED_EVENT_TYPES),
                )
            )
            recent_watchdog = _rows_as_dicts(
                conn.execute(
                    """
                    SELECT COALESCE(bot_id, '') AS bot_id, event_type, severity,
                           message, created_at
                    FROM events
                    WHERE created_at >= ?
                      AND event_type IN ('watchdog.halt', 'watchdog.unhalt')
                    ORDER BY created_at DESC
                    LIMIT 25
                    """,
                    (_sqlite_dt(since),),
                )
            )
        if _has_table(conn, "halt_flags"):
            halt_flags = _rows_as_dicts(
                conn.execute(
                    """
                    SELECT bot_id, halted, COALESCE(reason, '') AS reason, set_at
                    FROM halt_flags
                    ORDER BY bot_id
                    """
                )
            )
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "db_path": str(db_path),
            "lookback_hours": lookback_hours,
            "halt_flags": halt_flags,
            "orders": orders,
            "trades": trades,
            "events": events,
            "recent_watchdog": recent_watchdog,
        }
    finally:
        conn.close()


def write_markdown(report: dict, out_path: Path) -> None:
    lines = [
        "# Fleet Trade-Flow Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Lookback: `{report['lookback_hours']}h`",
        "",
        "## Orders",
        "",
        "| Bot | Status | Count | Notional | Last seen |",
        "|---|---|---:|---:|---|",
    ]
    for row in report["orders"]:
        lines.append(
            f"| `{row['bot_id']}` | `{row['status']}` | {row['n']} | "
            f"{row['notional'] or 0} | `{row['last_seen']}` |"
        )
    if not report["orders"]:
        lines.append("| n/a | n/a | 0 | 0 | n/a |")

    lines += [
        "",
        "## Fills",
        "",
        "| Bot | Fills | Notional | Last seen |",
        "|---|---:|---:|---|",
    ]
    for row in report["trades"]:
        lines.append(
            f"| `{row['bot_id']}` | {row['fills']} | {row['notional'] or 0} | "
            f"`{row['last_seen']}` |"
        )
    if not report["trades"]:
        lines.append("| n/a | 0 | 0 | n/a |")

    lines += [
        "",
        "## Halt Flags",
        "",
        "| Bot | Halted | Reason | Set at |",
        "|---|---:|---|---|",
    ]
    for row in report["halt_flags"]:
        lines.append(
            f"| `{row['bot_id']}` | {row['halted']} | `{row['reason']}` | "
            f"`{row['set_at']}` |"
        )
    if not report["halt_flags"]:
        lines.append("| n/a | 0 | n/a | n/a |")

    lines += [
        "",
        "## Events",
        "",
        "| Bot | Event | Count | Last seen |",
        "|---|---|---:|---|",
    ]
    for row in report["events"]:
        lines.append(
            f"| `{row['bot_id']}` | `{row['event_type']}` | {row['n']} | "
            f"`{row['last_seen']}` |"
        )
    if not report["events"]:
        lines.append("| n/a | n/a | 0 | n/a |")

    lines += [
        "",
        "## Recent Watchdog",
        "",
        "| Time | Bot | Event | Message |",
        "|---|---|---|---|",
    ]
    for row in report["recent_watchdog"]:
        lines.append(
            f"| `{row['created_at']}` | `{row['bot_id']}` | `{row['event_type']}` | "
            f"`{row['message']}` |"
        )
    if not report["recent_watchdog"]:
        lines.append("| n/a | n/a | n/a | n/a |")

    lines.append("")
    lines.append(
        "Interpretation: loosen a bot only when this report shows enough current "
        "blocked flow to identify the bottleneck."
    )
    out_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--lookback-hours", type=float, default=24.0)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    parser.add_argument(
        "--stdout-json",
        action="store_true",
        help="print the status packet for a local LLM hook instead of writing files",
    )
    args = parser.parse_args()

    report = run_report(args.db, lookback_hours=args.lookback_hours)
    if args.stdout_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_markdown(report, args.out_md)
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_md}")


if __name__ == "__main__":
    main()
