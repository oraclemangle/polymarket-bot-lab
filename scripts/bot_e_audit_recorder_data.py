#!/usr/bin/env python3
"""Audit the Bot E recorder DB for data continuity.

Step 0 of the E-2 (replacement model) build per
`docs/bot-e-model-replacement-plan.md`. Before fitting a model on the
recorder tape we need to know whether the dataset is contaminated by
recorder downtime. A 90-second gap in pm_events for a subscription
that's supposed to be live every few seconds means we're missing
exactly the high-information moments around price moves — silent
selection bias.

This script walks the recorder DB and emits a structured report:

  - Per pm_events subscription_id: total events, gap count
    (>= --gap-threshold-s), gap distribution, longest gap.
  - Per cex_trades symbol: same.
  - Per heartbeat source: same.
  - Suspicious overall windows where ALL streams went silent
    simultaneously (likely recorder crash periods).

Exit codes
----------
    0 = audit complete (regardless of findings)
    2 = unexpected exception
    3 = invalid args / DB not found

Usage
-----
    .venv/bin/python scripts/bot_e_audit_recorder_data.py
    .venv/bin/python scripts/bot_e_audit_recorder_data.py --gap-threshold-s 60
    .venv/bin/python scripts/bot_e_audit_recorder_data.py --since '2026-04-25 21:00:00'
"""
from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = "data/bot_e_recorder.db"
DEFAULT_GAP_THRESHOLD_S = 60.0

log = logging.getLogger("bot_e_audit_recorder_data")


@dataclass
class StreamReport:
    """Continuity audit for a single (table, key) stream."""
    table: str
    key: str
    n_events: int
    first_ms: int | None
    last_ms: int | None
    gap_count: int
    gap_total_s: float
    longest_gap_s: float
    longest_gap_at_ms: int | None
    threshold_s: float

    @property
    def coverage_ratio(self) -> float:
        if self.first_ms is None or self.last_ms is None:
            return 0.0
        wall_s = (self.last_ms - self.first_ms) / 1000.0
        if wall_s <= 0:
            return 1.0
        return max(0.0, (wall_s - self.gap_total_s) / wall_s)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--db", default=DEFAULT_DB,
                   help=f"Recorder DB path (default: {DEFAULT_DB!r})")
    p.add_argument("--gap-threshold-s", type=float, default=DEFAULT_GAP_THRESHOLD_S,
                   help=f"Gap threshold in seconds (default: {DEFAULT_GAP_THRESHOLD_S})")
    p.add_argument("--since", default=None,
                   help="Only audit events at or after this UTC timestamp "
                        "(format: 'YYYY-MM-DD HH:MM:SS')")
    p.add_argument("--max-streams", type=int, default=20,
                   help="Limit per-stream output to this many (default: 20)")
    return p.parse_args(argv)


def _parse_since_to_ms(since: str | None) -> int | None:
    if since is None:
        return None
    dt = datetime.strptime(since, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def audit_stream(
    conn: sqlite3.Connection,
    *,
    table: str,
    key_col: str,
    key_value: str,
    ts_col: str,
    threshold_s: float,
    since_ms: int | None,
) -> StreamReport:
    """Walk ``table`` filtered by ``key_col=key_value`` ordered by ``ts_col``
    and detect gaps between consecutive events larger than ``threshold_s``."""
    threshold_ms = threshold_s * 1000.0

    where = f"WHERE {key_col} = ?"
    params: list = [key_value]
    if since_ms is not None:
        where += f" AND {ts_col} >= ?"
        params.append(since_ms)

    cur = conn.execute(
        f"SELECT {ts_col} FROM {table} {where} ORDER BY {ts_col}",
        params,
    )
    timestamps = [row[0] for row in cur]

    if not timestamps:
        return StreamReport(
            table=table, key=key_value, n_events=0,
            first_ms=None, last_ms=None,
            gap_count=0, gap_total_s=0.0,
            longest_gap_s=0.0, longest_gap_at_ms=None,
            threshold_s=threshold_s,
        )

    gap_count = 0
    gap_total_s = 0.0
    longest_gap_s = 0.0
    longest_gap_at_ms: int | None = None

    for prev, curr in zip(timestamps, timestamps[1:]):
        delta_ms = curr - prev
        if delta_ms > threshold_ms:
            gap_count += 1
            gap_s = delta_ms / 1000.0
            gap_total_s += gap_s
            if gap_s > longest_gap_s:
                longest_gap_s = gap_s
                longest_gap_at_ms = prev

    return StreamReport(
        table=table, key=key_value, n_events=len(timestamps),
        first_ms=timestamps[0], last_ms=timestamps[-1],
        gap_count=gap_count, gap_total_s=gap_total_s,
        longest_gap_s=longest_gap_s, longest_gap_at_ms=longest_gap_at_ms,
        threshold_s=threshold_s,
    )


def list_keys(conn: sqlite3.Connection, table: str, key_col: str,
              since_ms: int | None) -> list[str]:
    """Distinct keys present in the table (optionally filtered by since)."""
    where = ""
    params: list = []
    if since_ms is not None:
        # Pick a sensible ts column for each table.
        ts_col = "received_at_ms" if table != "heartbeats" else "emitted_at_ms"
        where = f"WHERE {ts_col} >= ?"
        params.append(since_ms)
    cur = conn.execute(
        f"SELECT DISTINCT {key_col} FROM {table} {where} "
        f"ORDER BY {key_col}",
        params,
    )
    return [row[0] for row in cur if row[0] is not None]


def format_report(reports: list[StreamReport], max_streams: int) -> str:
    if not reports:
        return "  (no streams)"
    # Worst-coverage first, but only show up to max_streams.
    sorted_reports = sorted(reports, key=lambda r: r.coverage_ratio)[:max_streams]
    lines = [
        f"  {'key':<40} {'n':>8} {'gaps':>6} {'longest':>9} "
        f"{'cov':>6}  longest_gap_at",
    ]
    for r in sorted_reports:
        ts = (
            datetime.fromtimestamp(r.longest_gap_at_ms / 1000, timezone.utc)
            .isoformat()
            if r.longest_gap_at_ms is not None else "--"
        )
        lines.append(
            f"  {r.key[:40]:<40} {r.n_events:>8} {r.gap_count:>6} "
            f"{r.longest_gap_s:>9.1f} {r.coverage_ratio*100:>5.1f}%  {ts}"
        )
    if len(reports) > max_streams:
        lines.append(f"  ... ({len(reports) - max_streams} more streams hidden)")
    return "\n".join(lines)


def find_simultaneous_gaps(
    conn: sqlite3.Connection,
    *,
    threshold_s: float,
    since_ms: int | None,
) -> list[tuple[int, float]]:
    """Find time windows where BOTH pm_events and cex_trades went silent.

    A simultaneous gap is a strong signal of recorder downtime. We
    detect by: take the union timeline of (pm_events.received_at_ms,
    cex_trades.received_at_ms), find adjacent pairs where the delta
    exceeds threshold_s. Returns [(gap_start_ms, gap_seconds), ...].
    """
    threshold_ms = threshold_s * 1000.0

    where_pm = ""
    where_cex = ""
    params_pm: list = []
    params_cex: list = []
    if since_ms is not None:
        where_pm = "WHERE received_at_ms >= ?"
        where_cex = "WHERE received_at_ms >= ?"
        params_pm.append(since_ms)
        params_cex.append(since_ms)

    pm_ts = [r[0] for r in conn.execute(
        f"SELECT received_at_ms FROM pm_events {where_pm} "
        f"ORDER BY received_at_ms",
        params_pm,
    )]
    cex_ts = [r[0] for r in conn.execute(
        f"SELECT received_at_ms FROM cex_trades {where_cex} "
        f"ORDER BY received_at_ms",
        params_cex,
    )]

    # Merge two sorted streams.
    merged: list[int] = []
    i = j = 0
    while i < len(pm_ts) and j < len(cex_ts):
        if pm_ts[i] <= cex_ts[j]:
            merged.append(pm_ts[i])
            i += 1
        else:
            merged.append(cex_ts[j])
            j += 1
    merged.extend(pm_ts[i:])
    merged.extend(cex_ts[j:])

    gaps: list[tuple[int, float]] = []
    for prev, curr in zip(merged, merged[1:]):
        delta_ms = curr - prev
        if delta_ms > threshold_ms:
            gaps.append((prev, delta_ms / 1000.0))
    return gaps


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"recorder DB not found: {db_path}", file=sys.stderr)
        return 3

    try:
        since_ms = _parse_since_to_ms(args.since)
    except ValueError as exc:
        print(f"bad --since: {exc}", file=sys.stderr)
        return 3

    try:
        conn = sqlite3.connect(str(db_path))
    except Exception as exc:
        log.exception("failed to open DB: %s", exc)
        return 2

    try:
        # --- pm_events per subscription_id ---
        pm_keys = list_keys(conn, "pm_events", "subscription_id", since_ms)
        pm_reports = [
            audit_stream(
                conn, table="pm_events", key_col="subscription_id",
                key_value=k, ts_col="received_at_ms",
                threshold_s=args.gap_threshold_s, since_ms=since_ms,
            )
            for k in pm_keys
        ]

        # --- cex_trades per symbol ---
        cex_keys = list_keys(conn, "cex_trades", "symbol", since_ms)
        cex_reports = [
            audit_stream(
                conn, table="cex_trades", key_col="symbol",
                key_value=k, ts_col="received_at_ms",
                threshold_s=args.gap_threshold_s, since_ms=since_ms,
            )
            for k in cex_keys
        ]

        # --- heartbeats per source ---
        hb_keys = list_keys(conn, "heartbeats", "source", since_ms)
        hb_reports = [
            audit_stream(
                conn, table="heartbeats", key_col="source",
                key_value=k, ts_col="emitted_at_ms",
                threshold_s=args.gap_threshold_s, since_ms=since_ms,
            )
            for k in hb_keys
        ]

        sim_gaps = find_simultaneous_gaps(
            conn, threshold_s=args.gap_threshold_s, since_ms=since_ms,
        )
    finally:
        conn.close()

    # --- Print report ---
    print()
    print("=" * 78)
    print("Bot E recorder data continuity audit")
    print("=" * 78)
    print(f"  DB:                {db_path}")
    print(f"  Gap threshold:     {args.gap_threshold_s}s")
    print(f"  Since:             {args.since or '(beginning)'}")
    print()
    print(f"-- pm_events ({len(pm_reports)} subscriptions) --")
    print(format_report(pm_reports, args.max_streams))
    print()
    print(f"-- cex_trades ({len(cex_reports)} symbols) --")
    print(format_report(cex_reports, args.max_streams))
    print()
    print(f"-- heartbeats ({len(hb_reports)} sources) --")
    print(format_report(hb_reports, args.max_streams))
    print()
    print(f"-- Simultaneous-blackout windows "
          f"(both pm_events AND cex_trades silent for >{args.gap_threshold_s}s) --")
    if not sim_gaps:
        print("  (none)")
    else:
        # Worst (longest) first, cap at 10.
        sim_gaps.sort(key=lambda x: -x[1])
        for start_ms, gap_s in sim_gaps[:10]:
            ts = datetime.fromtimestamp(start_ms / 1000, timezone.utc).isoformat()
            print(f"  {ts}  +{gap_s:>8.1f}s")
        if len(sim_gaps) > 10:
            print(f"  ... ({len(sim_gaps) - 10} more)")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
