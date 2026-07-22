#!/usr/bin/env python3
"""Persistence — daily paper run for the two-cell strategy from ADR-128.

Cells:
  A: Borderline (5m markets), mid_high in [0.50, 0.55], buy favoured
  B: Tail       (15m markets), mid_high in [0.85, 0.95], buy favoured

Reuses the calibration-sweep simulator's per-market processing.
Writes to a separate paper DB; idempotent on rerun (UNIQUE constraint).
Emits cumulative report and a halt flag if cumulative post-fee
ROI < -5% on n >= 100.

Read-only on the recorder DB. No order placement, no wallet calls.

Designed to run via systemd timer at 06:30 UTC daily.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bot_moonshot_late_lean_replay import (  # noqa: E402
    Market,
    connect_ro,
    determine_outcome,
    load_markets,
)
from btc_updown_calibration_sweep import fee, find_first_high_tick  # noqa: E402

from core.bot_registry import meta as bot_meta  # noqa: E402

BASE_CELLS = {
    "A_borderline_5m_15m": {
        "min_mid_high": 0.50, "max_mid_high": 0.55,
        "durations": [5, 15], "description": "Borderline persistence (5m+15m, mid 0.50-0.55)",
    },
    "B_tail_15m": {
        "min_mid_high": 0.85, "max_mid_high": 0.95,
        "durations": [15], "description": "Near-certain tail (15m, mid 0.85-0.95)",
    },
}
CELL_C = {
    "C_tail_5m_15m_95_99": {
        "min_mid_high": 0.95, "max_mid_high": 0.99,
        "durations": [5, 15], "description": "Cell C high-tail candidate (5m+15m, mid 0.95-0.99)",
    },
}
CELLS = dict(BASE_CELLS)


def selected_cells(*, include_cell_c: bool = False, only_cell_c: bool = False) -> dict[str, dict]:
    if only_cell_c:
        return dict(CELL_C)
    cells = dict(BASE_CELLS)
    if include_cell_c:
        cells.update(CELL_C)
    return cells

PAPER_SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inserted_at_ms INTEGER NOT NULL,
    cell_label TEXT NOT NULL,
    market_id TEXT NOT NULL,
    crypto TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    end_ts_ms INTEGER NOT NULL,
    execution_style TEXT NOT NULL DEFAULT 'taker',
    side TEXT NOT NULL,
    bid_high REAL NOT NULL,
    ask_high REAL NOT NULL,
    mid_high REAL NOT NULL,
    bid_low REAL NOT NULL,
    ask_low REAL NOT NULL,
    won INTEGER NOT NULL,
    pnl_usd REAL NOT NULL,
    fee_usd REAL NOT NULL,
    UNIQUE(cell_label, market_id)
);
CREATE INDEX IF NOT EXISTS ix_paper_end_ts ON paper_entries(end_ts_ms);
CREATE INDEX IF NOT EXISTS ix_paper_cell ON paper_entries(cell_label);

CREATE TABLE IF NOT EXISTS run_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at_ms INTEGER NOT NULL,
    completed_at_ms INTEGER,
    n_markets_considered INTEGER,
    n_added_total INTEGER,
    n_added_per_cell TEXT,
    cumulative_post_fee_roi REAL,
    halted INTEGER DEFAULT 0,
    notes TEXT,
    band_histogram_json TEXT
);
"""

# Bands for the diagnostic histogram (where the FIRST qualifying tick landed).
# Lets us tell apart regime issues (most ticks at 0.95+ on directional days)
# from coverage gaps (no ticks anywhere) when a daily run adds 0 entries.
_HIST_BANDS = [
    (0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70), (0.70, 0.75),
    (0.75, 0.80), (0.80, 0.85), (0.85, 0.90), (0.90, 0.95), (0.95, 1.00),
]


def _band_label(mid: float) -> str | None:
    for lo, hi in _HIST_BANDS:
        if lo <= mid < hi:
            return f"{lo:.2f}-{hi:.2f}"
    return None


def init_paper_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path.as_posix(), timeout=30.0)
    con.row_factory = sqlite3.Row
    con.executescript(PAPER_SCHEMA)
    # Idempotent migration: add band_histogram_json to pre-existing run_log tables.
    cols = {row[1] for row in con.execute("PRAGMA table_info(run_log)")}
    if "band_histogram_json" not in cols:
        con.execute("ALTER TABLE run_log ADD COLUMN band_histogram_json TEXT")
    entry_cols = {row[1] for row in con.execute("PRAGMA table_info(paper_entries)")}
    if "execution_style" not in entry_cols:
        con.execute("ALTER TABLE paper_entries ADD COLUMN execution_style TEXT NOT NULL DEFAULT 'taker'")
    con.execute("PRAGMA journal_mode=WAL")
    con.commit()
    return con


def upsert_entry(con: sqlite3.Connection, *, cell_label: str, market: Market,
                 tick, fee_rate_bps: int, execution_style: str) -> bool:
    """Insert one entry; returns True if new, False if dedup."""
    entry_price = tick.bid_high if execution_style == "maker" else tick.ask_high
    f = 0.0 if execution_style == "maker" else fee(entry_price, fee_rate_bps)
    pnl = (1.0 - entry_price) if tick.won_high else (-entry_price)
    try:
        con.execute(
            """INSERT INTO paper_entries
               (inserted_at_ms, cell_label, market_id, crypto, duration_minutes,
                end_ts_ms, execution_style, side, bid_high, ask_high, mid_high,
                bid_low, ask_low, won, pnl_usd, fee_usd)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (int(time.time() * 1000), cell_label, market.condition_id, market.crypto,
             market.duration_minutes, market.end_ts_ms, execution_style, tick.side_high,
             tick.bid_high, tick.ask_high, tick.mid_high,
             tick.bid_low, tick.ask_low,
             1 if tick.won_high else 0, pnl, f),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def cumulative_stats(paper_con: sqlite3.Connection, execution_style: str) -> dict[str, dict]:
    """Per cell + 'all'."""
    rows = paper_con.execute(
        """SELECT cell_label, COUNT(*) AS n, SUM(won) AS wins,
                  SUM(pnl_usd) AS sum_pnl, SUM(fee_usd) AS sum_fees,
                  SUM(CASE WHEN execution_style = 'maker' THEN bid_high ELSE ask_high END) AS sum_ask,
                  AVG(mid_high) AS implied,
                  GROUP_CONCAT(pnl_usd, ',') AS pnls
           FROM paper_entries WHERE execution_style = ? GROUP BY cell_label""",
        (execution_style,),
    ).fetchall()
    out: dict[str, dict] = {}
    all_pnls: list[float] = []
    a_n = a_wins = 0
    a_pnl = a_fees = a_ask = a_implied_w = 0.0
    for r in rows:
        pnls = [float(x) for x in (r["pnls"] or "").split(",") if x]
        s = {
            "n": int(r["n"]), "wins": int(r["wins"] or 0),
            "implied": float(r["implied"] or 0),
            "sum_pnl": float(r["sum_pnl"] or 0),
            "sum_fees": float(r["sum_fees"] or 0),
            "sum_ask": float(r["sum_ask"] or 0),
            "pnls": pnls,
        }
        out[r["cell_label"]] = s
        all_pnls.extend(pnls)
        a_n += s["n"]
        a_wins += s["wins"]
        a_pnl += s["sum_pnl"]
        a_fees += s["sum_fees"]
        a_ask += s["sum_ask"]
        a_implied_w += s["implied"] * s["n"]
    if a_n > 0:
        out["all"] = {
            "n": a_n, "wins": a_wins,
            "implied": a_implied_w / a_n,
            "sum_pnl": a_pnl, "sum_fees": a_fees, "sum_ask": a_ask,
            "pnls": all_pnls,
        }
    return out


def wilson_ci(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    denom = 1.0 + z*z/n
    center = (p + z*z/(2*n)) / denom
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def normal_ci_roi(s: dict) -> tuple[float | None, float | None]:
    pnls = s.get("pnls", [])
    if len(pnls) < 2 or s["sum_ask"] <= 0:
        return None, None
    mean = sum(pnls) / len(pnls)
    var = sum((x - mean) ** 2 for x in pnls) / (len(pnls) - 1)
    se = math.sqrt(var / len(pnls))
    mean_ask = s["sum_ask"] / s["n"]
    return (mean - 1.96*se) / mean_ask, (mean + 1.96*se) / mean_ask


def write_halt_flag(paper_db_path: Path, reason: str) -> None:
    flag = paper_db_path.parent / (paper_db_path.stem + ".halt")
    flag.write_text(f"{datetime.now(UTC).isoformat()}\n{reason}\n")


def render_cumulative_report(stats: dict, run_log: list[dict],
                              paper_db: Path, fee_rate_bps: int, execution_style: str,
                              cells: dict[str, dict] | None = None) -> str:
    def pct(x): return "n/a" if x is None else f"{x * 100:+.2f}%"

    lines = [
        "# Persistence — Cumulative Paper Report",
        "",
        f"Generated: `{datetime.now(UTC).isoformat()}`",
        f"Paper DB: `{paper_db}`",
        f"Execution style: `{execution_style}`",
        f"Fee assumption: `{fee_rate_bps}` bps round-trip",
        "",
        "## Cumulative headline (per cell)",
        "",
        "| cell | n | wins | WR | Wilson WR CI | Cal gap | Post-fee ROI | ROI 95% CI |",
        "|---|---:|---:|---:|---|---:|---:|---|",
    ]
    halt = False
    cells = cells or BASE_CELLS
    for key in [*cells.keys(), "all"]:
        s = stats.get(key)
        if not s or s["n"] == 0:
            continue
        wr = s["wins"] / s["n"]
        wr_lo, wr_hi = wilson_ci(wr, s["n"])
        post_fee_roi = (s["sum_pnl"] - s["sum_fees"]) / s["sum_ask"] if s["sum_ask"] else 0.0
        roi_lo, roi_hi = normal_ci_roi(s)
        lines.append(
            f"| {key} | {s['n']} | {s['wins']} | {pct(wr)} | "
            f"[{pct(wr_lo)}, {pct(wr_hi)}] | {(wr - s['implied'])*100:+.2f} pp | "
            f"{pct(post_fee_roi)} | [{pct(roi_lo)}, {pct(roi_hi)}] |"
        )
        if key == "all" and s["n"] >= 100 and post_fee_roi < -0.05:
            halt = True

    a = stats.get("A_borderline_5m_15m", {})
    b = stats.get("B_tail_15m", {})
    a_roi_lo = normal_ci_roi(a)[0] if a.get("n", 0) > 0 else None
    b_roi_lo = normal_ci_roi(b)[0] if b.get("n", 0) > 0 else None

    early_look_a = a.get("wins", 0) / max(1, a.get("n", 1)) if a.get("n", 0) >= 25 else None
    early_look_b = b.get("wins", 0) / max(1, b.get("n", 1)) if b.get("n", 0) >= 25 else None
    early_look_warn = []
    if early_look_a is not None and early_look_a < 0.47:  # Cell A break-even ~52%, fail at -5pp
        early_look_warn.append(f"Cell A WR {early_look_a*100:.1f}% < 47% (-5pp from breakeven)")
    if early_look_b is not None and early_look_b < 0.85:  # Cell B break-even ~90%
        early_look_warn.append(f"Cell B WR {early_look_b*100:.1f}% < 85%")
    lines.extend([
        "",
        "## ADR-128/S7 acceptance gates",
        "",
        f"- **P1/S7 sample** (n_total ≥ 100, Cell C decision at n>=50): "
        f"{'PASS' if stats.get('all', {}).get('n', 0) >= 100 else 'WAITING'} "
        f"(n={stats.get('all', {}).get('n', 0)})",
        f"- **P2 Cell A ROI 95% lo > 0 at n_A ≥ 50**: "
        f"{'PASS' if a.get('n', 0) >= 50 and a_roi_lo and a_roi_lo > 0 else 'WAITING'} "
        f"(n_A={a.get('n', 0)}, ROI_lo={pct(a_roi_lo)})",
        f"- **P3 Cell B ROI 95% lo > 0 at n_B ≥ 50**: "
        f"{'PASS' if b.get('n', 0) >= 50 and b_roi_lo and b_roi_lo > 0 else 'WAITING'} "
        f"(n_B={b.get('n', 0)}, ROI_lo={pct(b_roi_lo)})",
        "- **EARLY-LOOK at n=25/cell**: " +
        (("**WARN: " + "; ".join(early_look_warn) + "**")
         if early_look_warn else
         (f"clean (Cell A WR={early_look_a*100:.1f}% n={a.get('n', 0)}, "
          f"Cell B WR={early_look_b*100:.1f}% n={b.get('n', 0)})"
          if early_look_a is not None and early_look_b is not None else
          "WAITING (need n>=25 in each cell)")),
        "",
    ])
    c = stats.get("C_tail_5m_15m_95_99", {})
    c_roi = ((c["sum_pnl"] - c["sum_fees"]) / c["sum_ask"]) if c.get("sum_ask") else None
    if "C_tail_5m_15m_95_99" in cells:
        if c.get("n", 0) < 50:
            c_decision = "WAITING (need n>=50)"
        elif c_roi is not None and c_roi > 0.01:
            c_decision = "S7_READY: ROI > +1%"
        elif c_roi is not None and c_roi < -0.01:
            c_decision = "S7_REJECT_CANDIDATE: ROI < -1%"
        else:
            c_decision = "S7_BORDERLINE: -1% <= ROI <= +1%"
        lines.extend([
            f"- **S7 Cell C decision gate**: {c_decision} "
            f"(n_C={c.get('n', 0)}, ROI={pct(c_roi)})",
            "",
        ])

    if halt:
        lines.append("**KILL SWITCH FIRED: cumulative post-fee ROI < -5% on n ≥ 100 — timer disabled**")
        lines.append("")

    # Today's first-tick band histogram (helps diagnose 0-add days: regime vs coverage gap)
    today_run = run_log[0] if run_log else None
    today_hist_json = today_run.get("band_histogram_json") if today_run else None
    if today_hist_json:
        try:
            today_hist = json.loads(today_hist_json)
        except (TypeError, ValueError):
            today_hist = None
        if today_hist:
            band_keys = [f"{lo:.2f}-{hi:.2f}" for lo, hi in _HIST_BANDS]
            lines.extend([
                "## Latest run — first-tick band histogram",
                "",
                "Where the first qualifying tick (mid_high ≥ 0.50 in last 60s) landed, "
                "stratified by market duration. Cell A bucket is `0.50-0.55`. Cell B bucket "
                "is `0.85-0.90` and `0.90-0.95` for 15m only. Other bands are diagnostic; "
                "they do not produce entries.",
                "",
                "| band | 5m | 15m | total |",
                "|---|---:|---:|---:|",
            ])
            d5 = today_hist.get("5m", {})
            d15 = today_hist.get("15m", {})
            for k in band_keys:
                a_n = int(d5.get(k, 0))
                b_n = int(d15.get(k, 0))
                marker = ""
                if k == "0.50-0.55":
                    marker = " ← Cell A"
                elif k in ("0.85-0.90", "0.90-0.95"):
                    marker = " ← Cell B (15m)"
                lines.append(f"| {k}{marker} | {a_n} | {b_n} | {a_n + b_n} |")
            tot5 = sum(int(v) for v in d5.values())
            tot15 = sum(int(v) for v in d15.values())
            lines.append(f"| **total ticks** | **{tot5}** | **{tot15}** | **{tot5 + tot15}** |")
            lines.append("")

    lines.extend([
        "## Run log (most recent 14)",
        "",
        "| run | started | n_markets | added | total_n | cum_roi | halted |",
        "|---:|---|---:|---:|---:|---:|---|",
    ])
    for r in run_log[:14]:
        ts = datetime.fromtimestamp(r["started_at_ms"]/1000, tz=UTC).strftime("%Y-%m-%d %H:%M")
        roi = r.get("cumulative_post_fee_roi")
        roi_str = f"{roi*100:+.2f}%" if roi is not None else "n/a"
        lines.append(
            f"| {r['id']} | {ts} | {r.get('n_markets_considered', 0)} | "
            f"{r.get('n_added_total', 0)} | {stats.get('all', {}).get('n', 0)} | "
            f"{roi_str} | {'YES' if r.get('halted') else 'no'} |"
        )

    return "\n".join(lines) + "\n", halt


def main() -> None:
    # Narrow P0 guard (ADR-181 / OQ-123):
    # Only the *live daily report* unit should exit early when the live Bot I
    # variants are paused. Paper runs (maker-paper, Cell C paper, etc.) must
    # continue collecting evidence even while live Bot I is paused.
    #
    # The live report unit must be invoked with --live-bot-i-report for the
    # guard to trigger. Paper systemd units do not pass this flag.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-bot-i-report",
        action="store_true",
        help="Internal flag used only by the live Bot I daily-report systemd unit. "
             "When set and live Bot I variants are paused/archived in the registry, "
             "exit 0 cleanly to prevent the unit from staying in 'failed' state.",
    )
    parser.add_argument("--recorder-db", type=Path, required=True)
    parser.add_argument("--paper-db", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--cryptos", nargs="+", default=["ETH", "SOL"], choices=["BTC", "ETH", "SOL"])
    parser.add_argument("--lookback-hours", type=int, default=25)
    parser.add_argument("--late-secs", type=int, default=60)
    parser.add_argument("--fee-bps", type=int, default=70)
    parser.add_argument("--execution-style", choices=["taker", "maker"], default="taker")
    parser.add_argument("--include-cell-c", action="store_true",
                        help="Also evaluate Cell C: 5m+15m, mid_high 0.95-0.99.")
    parser.add_argument("--only-cell-c", action="store_true",
                        help="Evaluate only Cell C for the maker-conversion S7 gate.")
    parser.add_argument("--report-suffix", default=None,
                        help="Override cumulative report suffix; defaults to execution style.")
    parser.add_argument("--bootstrap", action="store_true",
                        help="On first run, scan ALL recorder data (not just lookback). "
                             "Useful for initial baseline.")
    args = parser.parse_args()

    # Narrow P0 guard (ADR-181 / OQ-123):
    # Only trigger for the specific live daily-report invocation (identified by the
    # --live-bot-i-report flag). Paper runs never pass this flag, so they continue
    # even while live Bot I is paused.
    if args.live_bot_i_report:
        for bid in ("bot_i_persistence_live", "bot_i_persistence_live_maker"):
            m = bot_meta(bid)
            if m and m.status in ("paused", "archived"):
                print(
                    f"INFO: {bid} registry status={m.status} (ADR-181/OQ-123, --live-bot-i-report). "
                    "Live daily report exiting 0 cleanly — prevents persistent 'failed' unit. "
                    "Paper runs are unaffected because they do not pass this flag."
                )
                sys.exit(0)
                return

    started_at_ms = int(time.time() * 1000)
    cutoff_ts_ms = 0 if args.bootstrap else started_at_ms - args.lookback_hours * 3600 * 1000
    cells = selected_cells(include_cell_c=args.include_cell_c, only_cell_c=args.only_cell_c)

    rec_con = connect_ro(args.recorder_db)
    paper_con = init_paper_db(args.paper_db)
    args.report_dir.mkdir(parents=True, exist_ok=True)

    print(f"loading markets (cryptos={args.cryptos}, "
          f"{'bootstrap=full history' if args.bootstrap else f'last {args.lookback_hours}h'}) ...",
          flush=True)
    all_markets = load_markets(rec_con, args.cryptos)
    markets = [m for m in all_markets
               if m.end_ts_ms >= cutoff_ts_ms and m.end_ts_ms <= started_at_ms]
    print(f"  {len(markets):,} markets in window", flush=True)

    n_added_per_cell = {label: 0 for label in cells}
    n_skipped_no_outcome = n_skipped_no_tick = 0
    # Diagnostic: where the first qualifying tick landed, stratified by duration.
    band_hist: dict[str, dict[str, int]] = {"5m": {}, "15m": {}}

    for i, m in enumerate(markets):
        if i % 200 == 0 and i > 0:
            print(f"  {i:,}/{len(markets):,}", flush=True)
        # Apply Cell A or Cell B duration filter
        active_cells = [
            (label, conf) for label, conf in cells.items()
            if m.duration_minutes in conf["durations"]
        ]
        if not active_cells:
            continue

        outcome = determine_outcome(rec_con, m)
        if outcome is None:
            n_skipped_no_outcome += 1
            continue

        tick = find_first_high_tick(rec_con, m, late_secs=args.late_secs)
        if tick is None:
            n_skipped_no_tick += 1
            continue
        tick.won_high = (tick.side_high == outcome)

        # Record where the first tick landed (diagnostic only — does not affect cell match).
        band = _band_label(tick.mid_high)
        if band:
            dur_key = f"{m.duration_minutes}m"
            band_hist[dur_key][band] = band_hist[dur_key].get(band, 0) + 1

        for cell_label, conf in active_cells:
            if (
                conf["min_mid_high"] <= tick.mid_high < conf["max_mid_high"]
                and upsert_entry(
                    paper_con,
                    cell_label=cell_label,
                    market=m,
                    tick=tick,
                    fee_rate_bps=args.fee_bps,
                    execution_style=args.execution_style,
                )
            ):
                n_added_per_cell[cell_label] += 1

    paper_con.commit()

    stats = cumulative_stats(paper_con, args.execution_style)
    a_total = stats.get("all", {}).get("n", 0)
    cum_roi = ((stats["all"]["sum_pnl"] - stats["all"]["sum_fees"])
               / stats["all"]["sum_ask"]
               if stats.get("all", {}).get("sum_ask") else 0.0)

    halted = a_total >= 100 and cum_roi < -0.05
    if halted:
        write_halt_flag(args.paper_db, f"cum_roi={cum_roi:.4f} on n={a_total}")

    band_hist_json = json.dumps(band_hist)
    paper_con.execute(
        """INSERT INTO run_log (started_at_ms, completed_at_ms, n_markets_considered,
                                 n_added_total, n_added_per_cell,
                                 cumulative_post_fee_roi, halted, notes,
                                 band_histogram_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (started_at_ms, int(time.time() * 1000), len(markets),
         sum(n_added_per_cell.values()), json.dumps(n_added_per_cell),
         cum_roi, 1 if halted else 0,
         f"skipped_no_outcome={n_skipped_no_outcome},skipped_no_tick={n_skipped_no_tick}",
         band_hist_json),
    )
    paper_con.commit()

    run_log_rows = paper_con.execute(
        "SELECT id, started_at_ms, n_markets_considered, n_added_total, "
        "cumulative_post_fee_roi, halted, band_histogram_json FROM run_log "
        "ORDER BY started_at_ms DESC LIMIT 14"
    ).fetchall()
    run_log = [dict(r) for r in run_log_rows]

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    report, _halt_flag = render_cumulative_report(
        stats, run_log, args.paper_db, args.fee_bps, args.execution_style, cells
    )
    suffix = args.report_suffix or ("maker-cell-c" if args.only_cell_c else args.execution_style)
    report_path = args.report_dir / f"persistence-cumulative-{suffix}-{today}.md"
    report_path.write_text(report)

    print(f"\nadded {sum(n_added_per_cell.values())} new (cell breakdown: {n_added_per_cell})",
          flush=True)
    print(f"cumulative n={a_total}, post-fee ROI={cum_roi:+.4f}, halted={halted}", flush=True)
    print(f"report: {report_path}", flush=True)


if __name__ == "__main__":
    main()
