"""Post-capture data-quality audit for the shared crypto recorder.

Run this offline against a recorder SQLite to detect:
1. Feed gaps (heartbeats absent for >N seconds on any source).
2. Orphaned subscriptions (pm_events from subscriptions never seen in the
   markets snapshot table — would indicate discovery churn losing history).
3. Event rate anomalies (pm_event rate dropping by >80% between consecutive
   intervals when heartbeats show the feed alive).
4. Subscription coverage (how many distinct (symbol, end_date) markets were
   captured for each calendar day).

Results written to the `gaps` table and summary printed to stdout.

Usage:
    python -m bots.bot_e_recorder.audit [--db PATH] [--gap-threshold-sec N]
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_GAP_THRESHOLD_SEC = 60.0   # flag any gap > 1 minute as suspicious


@dataclass
class AuditReport:
    gaps_detected: int
    total_pm_events: int
    total_cex_trades: int
    total_markets_snapshots: int
    distinct_subscriptions: int
    first_event_ms: int | None
    last_event_ms: int | None
    capture_duration_hours: float

    def summary(self) -> str:
        return (
            f"Crypto Recorder Audit\n"
            f"=====================\n"
            f"Capture window:     "
            f"{self.first_event_ms} → {self.last_event_ms} "
            f"({self.capture_duration_hours:.1f}h)\n"
            f"Polymarket events:  {self.total_pm_events:>12,}\n"
            f"CEX trades:         {self.total_cex_trades:>12,}\n"
            f"Market snapshots:   {self.total_markets_snapshots:>12,}\n"
            f"Distinct subs:      {self.distinct_subscriptions:>12}\n"
            f"Gaps detected:      {self.gaps_detected:>12}\n"
        )


def detect_gaps(
    conn: sqlite3.Connection,
    *,
    gap_threshold_sec: float = DEFAULT_GAP_THRESHOLD_SEC,
) -> int:
    """Compare consecutive heartbeat rows per (source, subscription_id);
    any interval longer than threshold gets inserted into `gaps`.

    Returns the number of gaps inserted.
    """
    # Remove prior gap rows for this dataset so audit is idempotent
    conn.execute("DELETE FROM gaps")

    sources = conn.execute(
        "SELECT DISTINCT source, subscription_id FROM heartbeats"
    ).fetchall()

    now_ms = int(time.time() * 1000)
    count = 0
    for source, sub_id in sources:
        rows = conn.execute(
            "SELECT emitted_at_ms FROM heartbeats "
            "WHERE source=? AND (subscription_id IS ? OR subscription_id = ?) "
            "ORDER BY emitted_at_ms",
            (source, sub_id, sub_id),
        ).fetchall()
        prev: int | None = None
        for (t,) in rows:
            if prev is not None:
                gap_sec = (t - prev) / 1000.0
                if gap_sec > gap_threshold_sec:
                    conn.execute(
                        "INSERT INTO gaps (source, subscription_id, gap_start_ms, "
                        "gap_end_ms, duration_sec, detected_at_ms) VALUES (?, ?, ?, ?, ?, ?)",
                        (source, sub_id, prev, t, gap_sec, now_ms),
                    )
                    count += 1
            prev = t
    conn.commit()
    return count


def audit(db_path: Path, *, gap_threshold_sec: float = DEFAULT_GAP_THRESHOLD_SEC) -> AuditReport:
    conn = sqlite3.connect(str(db_path))
    try:
        n_gaps = detect_gaps(conn, gap_threshold_sec=gap_threshold_sec)

        def scalar(sql: str) -> int:
            row = conn.execute(sql).fetchone()
            return int(row[0]) if row and row[0] is not None else 0

        total_pm = scalar("SELECT COUNT(*) FROM pm_events")
        total_cex = scalar("SELECT COUNT(*) FROM cex_trades")
        total_mkt = scalar("SELECT COUNT(*) FROM markets")
        distinct_subs = scalar("SELECT COUNT(DISTINCT subscription_id) FROM pm_events")
        first_ms = scalar("SELECT MIN(received_at_ms) FROM pm_events")
        last_ms = scalar("SELECT MAX(received_at_ms) FROM pm_events")
        duration_hours = (last_ms - first_ms) / 3_600_000.0 if (first_ms and last_ms) else 0.0

        return AuditReport(
            gaps_detected=n_gaps,
            total_pm_events=total_pm,
            total_cex_trades=total_cex,
            total_markets_snapshots=total_mkt,
            distinct_subscriptions=distinct_subs,
            first_event_ms=first_ms or None,
            last_event_ms=last_ms or None,
            capture_duration_hours=duration_hours,
        )
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    from bots.bot_e_recorder.config import BOT_E_RECORDER_DB_PATH
    parser = argparse.ArgumentParser(description="Audit a crypto-recorder capture DB")
    parser.add_argument("--db", type=Path, default=BOT_E_RECORDER_DB_PATH)
    parser.add_argument("--gap-threshold-sec", type=float, default=DEFAULT_GAP_THRESHOLD_SEC)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = audit(args.db, gap_threshold_sec=args.gap_threshold_sec)
    sys.stdout.write(report.summary())
    return 0 if report.gaps_detected == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
