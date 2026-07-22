#!/usr/bin/env python3
"""Write a daily Bot L complete-set paper report.

Read-only against Bot L's paper DB. This report is for ADR-159 / OQ-111
monitoring only; it does not read wallet state or place orders.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bots.bot_l_complete_set.simulator import DEFAULT_PAPER_DB, build_summary

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "reports" / "bot_l_complete_set"


def _connect_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _run_log_tail(conn: sqlite3.Connection, limit: int = 10) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT started_at, finished_at, source_events_seen,
                   signals_written, last_recorder_event_id, config_json
            FROM bot_l_complete_set_run_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    except sqlite3.Error:
        return []
    return [dict(row) for row in rows]


def _depth_diagnostics_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    try:
        rows = conn.execute(
            """
            SELECT signal_type, payload_json
            FROM bot_l_complete_set_signals
            WHERE payload_json IS NOT NULL
            """
        ).fetchall()
    except sqlite3.Error:
        return {}

    summary: dict[str, Any] = {}
    for row in rows:
        signal_type = str(row["signal_type"] or "UNKNOWN")
        bucket = summary.setdefault(
            signal_type,
            {
                "payloads": 0,
                "size_reasons": {},
                "size_sources": {},
            },
        )
        try:
            payload = json.loads(row["payload_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        bucket["payloads"] += 1
        for leg in ("yes", "no"):
            diag = payload.get(f"{leg}_quote_diagnostics")
            if not isinstance(diag, dict):
                bucket["size_reasons"]["missing_diagnostics"] = (
                    bucket["size_reasons"].get("missing_diagnostics", 0) + 1
                )
                continue
            for key in ("best_bid_size", "best_ask_size"):
                reason = str(diag.get(key) or "missing_diagnostics")
                reason_key = f"{key}:{reason}"
                bucket["size_reasons"][reason_key] = bucket["size_reasons"].get(reason_key, 0) + 1
            for key in ("bid_size_source", "ask_size_source"):
                source = str(diag.get(key) or "missing_diagnostics")
                source_key = f"{key}:{source}"
                bucket["size_sources"][source_key] = bucket["size_sources"].get(source_key, 0) + 1
    return summary


def _ex_largest(values: list[float], trims: tuple[int, ...] = (1, 5, 10, 20)) -> dict[str, float]:
    ordered = sorted(values, reverse=True)
    total = sum(ordered)
    out = {"raw": round(total, 4)}
    for trim in trims:
        out[f"ex_largest_{trim}"] = round(sum(ordered[trim:]), 4)
    return out


def _gate_slices(conn: sqlite3.Connection) -> dict[str, Any]:
    try:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT detected_at_ms, condition_id, signal_type, reason,
                       simulated_pnl_usd, executable, payload_json
                FROM bot_l_complete_set_signals
                """
            )
        ]
    except sqlite3.Error:
        return {}
    executable_rows = [row for row in rows if int(row.get("executable") or 0) == 1]
    total_exec_pnl = sum(float(row.get("simulated_pnl_usd") or 0) for row in executable_rows)
    by_market: dict[str, float] = {}
    ex_largest_by_type: dict[str, Any] = {}
    pair_ages: list[int] = []
    reason_counts: dict[str, int] = {}
    for row in executable_rows:
        condition_id = str(row.get("condition_id") or "")
        by_market[condition_id] = by_market.get(condition_id, 0.0) + float(
            row.get("simulated_pnl_usd") or 0
        )
        signal_type = str(row.get("signal_type") or "UNKNOWN")
        ex_largest_by_type.setdefault(signal_type, []).append(float(row.get("simulated_pnl_usd") or 0))
    for row in rows:
        try:
            payload = json.loads(row.get("payload_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            payload = {}
        pair_age = payload.get("pair_age_ms")
        if isinstance(pair_age, int | float):
            pair_ages.append(int(pair_age))
        reason = str(row.get("reason") or "")
        if reason:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    ranked_markets = sorted(by_market.items(), key=lambda item: item[1], reverse=True)
    top_1 = ranked_markets[0][1] if ranked_markets else 0.0
    top_3 = sum(value for _, value in ranked_markets[:3])
    detected_times = [int(row["detected_at_ms"]) for row in rows if row.get("detected_at_ms") is not None]
    span_hours = 0.0
    if len(detected_times) >= 2:
        span_hours = max((max(detected_times) - min(detected_times)) / 3_600_000, 0.0)
    return {
        "top_market_exec_pnl_usd": round(top_1, 4),
        "top_1_concentration_pct": round((top_1 / total_exec_pnl) * 100, 2) if total_exec_pnl else 0.0,
        "top_3_concentration_pct": round((top_3 / total_exec_pnl) * 100, 2) if total_exec_pnl else 0.0,
        "ex_largest_by_type": {
            signal_type: _ex_largest(values) for signal_type, values in sorted(ex_largest_by_type.items())
        },
        "pair_age_ms": {
            "count": len(pair_ages),
            "max": max(pair_ages) if pair_ages else None,
            "avg": round(sum(pair_ages) / len(pair_ages), 2) if pair_ages else None,
        },
        "reason_counts": reason_counts,
        "signal_rate_per_hour": round(len(rows) / span_hours, 4) if span_hours else 0.0,
        "span_hours": round(span_hours, 2),
    }


def _run_log_diagnostics(run_log: list[dict[str, Any]]) -> dict[str, Any]:
    total_source_events = 0
    total_signals_written = 0
    failure_counts: dict[str, int] = {}
    for row in run_log:
        total_source_events += int(row.get("source_events_seen") or 0)
        total_signals_written += int(row.get("signals_written") or 0)
        try:
            config = json.loads(row.get("config_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            config = {}
        for key, value in (config.get("failure_counts") or {}).items():
            failure_counts[str(key)] = failure_counts.get(str(key), 0) + int(value or 0)
    return {
        "tail_source_events_seen": total_source_events,
        "tail_signals_written": total_signals_written,
        "tail_failure_counts": failure_counts,
    }


def build_report(db_path: Path) -> dict[str, Any]:
    conn = _connect_ro(db_path)
    try:
        summary = build_summary(conn)
        run_log = _run_log_tail(conn)
        depth_diagnostics = _depth_diagnostics_summary(conn)
        gate_slices = _gate_slices(conn)
    finally:
        conn.close()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "paper_db_path": str(db_path),
        "summary": summary,
        "run_log_tail": run_log,
        "depth_diagnostics": depth_diagnostics,
        "gate_slices": gate_slices,
        "run_log_diagnostics": _run_log_diagnostics(run_log),
        "posture": {
            "paper_only": True,
            "wallet": False,
            "live_orders": False,
            "adr": "ADR-159",
            "open_question": "OQ-111",
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    by_type = summary.get("by_type", {})
    lines = [
        "# Bot L Complete-Set Daily Report",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Posture",
        "",
        "- Paper-only ADR-159 lane.",
        "- Reads Bot L paper DB only.",
        "- No wallet, CLOB client, live order path, cap, or bankroll change.",
        "",
        "## Headline",
        "",
        f"- Signals: `{summary.get('signals', 0)}`",
        f"- Executable signals: `{summary.get('executable_signals', 0)}`",
        f"- Markets: `{summary.get('markets', 0)}`",
        f"- Raw P&L: `${summary.get('pnl_usd', 0):.4f}`",
        f"- Executable P&L: `${summary.get('executable_pnl_usd', 0):.4f}`",
        f"- BUY executable P&L: `${summary.get('buy_executable_pnl_usd', 0):.4f}`",
        f"- SELL executable P&L: `${summary.get('sell_executable_pnl_usd', 0):.4f}`",
        "",
        "## Gate Slices",
        "",
    ]
    gate_slices = report.get("gate_slices") or {}
    if not gate_slices:
        lines.append("No gate slices available.")
    else:
        lines.extend([
            f"- Top-1 executable concentration: `{gate_slices.get('top_1_concentration_pct', 0):.2f}%`",
            f"- Top-3 executable concentration: `{gate_slices.get('top_3_concentration_pct', 0):.2f}%`",
            f"- Signal rate: `{gate_slices.get('signal_rate_per_hour', 0):.4f}/hour`",
            f"- Pair-age max: `{(gate_slices.get('pair_age_ms') or {}).get('max')}` ms",
            f"- Pair-age avg: `{(gate_slices.get('pair_age_ms') or {}).get('avg')}` ms",
            "",
            "| signal_type | raw | ex1 | ex5 | ex10 | ex20 |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for signal_type, row in (gate_slices.get("ex_largest_by_type") or {}).items():
            lines.append(
                "| {signal_type} | {raw:.4f} | {ex1:.4f} | {ex5:.4f} | {ex10:.4f} | {ex20:.4f} |".format(
                    signal_type=signal_type,
                    raw=row.get("raw", 0),
                    ex1=row.get("ex_largest_1", 0),
                    ex5=row.get("ex_largest_5", 0),
                    ex10=row.get("ex_largest_10", 0),
                    ex20=row.get("ex_largest_20", 0),
                )
            )
    lines.extend([
        "",
        "## By Side",
        "",
        "| signal_type | signals | executable | pnl_usd | executable_pnl_usd | min_adj | max_adj |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for signal_type in sorted(by_type):
        row = by_type[signal_type]
        lines.append(
            "| {signal_type} | {signals} | {executable} | {pnl:.4f} | "
            "{exec_pnl:.4f} | {min_adj:.4f} | {max_adj:.4f} |".format(
                signal_type=signal_type,
                signals=row.get("signals", 0),
                executable=row.get("executable", 0),
                pnl=row.get("pnl_usd", 0),
                exec_pnl=row.get("executable_pnl_usd", 0),
                min_adj=row.get("min_adjusted_sum", 0),
                max_adj=row.get("max_adjusted_sum", 0),
            )
        )
    lines.extend(["", "## Recent Signals", ""])
    recent = summary.get("recent") or []
    if not recent:
        lines.append("No signals recorded.")
    else:
        lines.extend([
            "| detected_at_ms | type | raw_sum | adjusted_sum | pnl | executable | reason |",
            "|---:|---|---:|---:|---:|---:|---|",
        ])
        for row in recent[:10]:
            lines.append(
                "| {detected_at_ms} | {signal_type} | {raw_sum:.4f} | {adjusted_sum:.4f} | "
                "{pnl:.4f} | {executable} | {reason} |".format(
                    detected_at_ms=row.get("detected_at_ms", 0),
                    signal_type=row.get("signal_type", ""),
                    raw_sum=float(row.get("raw_sum") or 0),
                    adjusted_sum=float(row.get("adjusted_sum") or 0),
                    pnl=float(row.get("simulated_pnl_usd") or 0),
                    executable=int(row.get("executable") or 0),
                    reason=row.get("reason", ""),
                )
            )
    lines.extend(["", "## Latest Runs", ""])
    run_log = report.get("run_log_tail") or []
    if not run_log:
        lines.append("No run log rows recorded.")
    else:
        lines.extend([
            "| finished_at | source_events_seen | signals_written | last_event_id |",
            "|---|---:|---:|---:|",
        ])
        for row in run_log[:10]:
            lines.append(
                "| {finished_at} | {source_events_seen} | {signals_written} | {last_recorder_event_id} |".format(
                    finished_at=row.get("finished_at", ""),
                    source_events_seen=row.get("source_events_seen", 0),
                    signals_written=row.get("signals_written", 0),
                    last_recorder_event_id=row.get("last_recorder_event_id", 0),
                )
            )
    run_diag = report.get("run_log_diagnostics") or {}
    lines.extend(["", "## Forward Diagnostics", ""])
    if not run_diag:
        lines.append("No run-log diagnostics recorded.")
    else:
        failure_counts = run_diag.get("tail_failure_counts") or {}
        lines.extend([
            f"- Tail source events seen: `{run_diag.get('tail_source_events_seen', 0)}`",
            f"- Tail signals written: `{run_diag.get('tail_signals_written', 0)}`",
            "",
            "| reason | count |",
            "|---|---:|",
        ])
        if not failure_counts:
            lines.append("| none | 0 |")
        else:
            for reason, count in sorted(failure_counts.items()):
                lines.append(f"| {reason} | {count} |")
    depth_diagnostics = report.get("depth_diagnostics") or {}
    lines.extend(["", "## Depth Diagnostics", ""])
    if not depth_diagnostics:
        lines.append("No depth diagnostics recorded.")
    else:
        lines.extend([
            "| signal_type | payloads | size_reasons | size_sources |",
            "|---|---:|---|---|",
        ])
        for signal_type in sorted(depth_diagnostics):
            row = depth_diagnostics[signal_type]
            reasons = ", ".join(
                f"{key}={value}" for key, value in sorted(row.get("size_reasons", {}).items())
            )
            sources = ", ".join(
                f"{key}={value}" for key, value in sorted(row.get("size_sources", {}).items())
            )
            lines.append(
                "| {signal_type} | {payloads} | {reasons} | {sources} |".format(
                    signal_type=signal_type,
                    payloads=row.get("payloads", 0),
                    reasons=reasons or "-",
                    sources=sources or "-",
                )
            )
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_text = json.dumps(report, indent=2, sort_keys=True)
    md_text = render_markdown(report)
    json_path = out_dir / f"bot_l_complete_set_daily_{stamp}.json"
    md_path = out_dir / f"bot_l_complete_set_daily_{stamp}.md"
    latest_json = out_dir / "latest.json"
    latest_md = out_dir / "latest.md"
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
    parser.add_argument("--paper-db-path", type=Path, default=DEFAULT_PAPER_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    report = build_report(args.paper_db_path)
    paths = write_outputs(report, args.out_dir)
    print(json.dumps({"generated_at": report["generated_at"], "paths": paths}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
