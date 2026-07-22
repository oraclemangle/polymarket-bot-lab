#!/usr/bin/env python3
"""Run a read-only Bot L parameter sweep into disposable paper DBs."""

from __future__ import annotations

import argparse
import itertools
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bots.bot_l_complete_set.simulator import DEFAULT_RECORDER_DB, run_once

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "reports" / "bot_l_complete_set"


def _parse_float_list(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def _parse_int_list(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def run_sweep(
    *,
    recorder_db_path: Path,
    lookback_hours: float,
    raw_buy_thresholds: list[float],
    raw_sell_thresholds: list[float],
    slippage_per_legs: list[float],
    max_pair_age_ms_values: list[int],
    gross_cost_usd: float,
    min_depth_shares: float,
    require_depth: bool = False,
    max_depth_age_ms: int = 1000,
) -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat()
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="bot-l-sweep-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        combos = itertools.product(
            raw_buy_thresholds,
            raw_sell_thresholds,
            slippage_per_legs,
            max_pair_age_ms_values,
        )
        for index, (raw_buy, raw_sell, slippage, max_pair_age_ms) in enumerate(combos, start=1):
            adjusted_buy = raw_buy - (2 * slippage)
            adjusted_sell = raw_sell + (2 * slippage)
            paper_db = tmp_root / f"sweep-{index}.db"
            summary = run_once(
                recorder_db_path=recorder_db_path,
                paper_db_path=paper_db,
                lookback_hours=lookback_hours,
                raw_buy_threshold=raw_buy,
                adjusted_buy_threshold=adjusted_buy,
                raw_sell_threshold=raw_sell,
                adjusted_sell_threshold=adjusted_sell,
                slippage_per_leg=slippage,
                gross_cost_usd=gross_cost_usd,
                min_depth_shares=min_depth_shares,
                require_depth=require_depth,
                max_pair_age_ms=max_pair_age_ms,
                max_depth_age_ms=max_depth_age_ms,
                incremental=False,
            )
            results.append(
                {
                    "raw_buy_threshold": raw_buy,
                    "adjusted_buy_threshold": adjusted_buy,
                    "raw_sell_threshold": raw_sell,
                    "adjusted_sell_threshold": adjusted_sell,
                    "slippage_per_leg": slippage,
                    "max_pair_age_ms": max_pair_age_ms,
                    "gross_cost_usd": gross_cost_usd,
                    "min_depth_shares": min_depth_shares,
                    "require_depth": require_depth,
                    "max_depth_age_ms": max_depth_age_ms,
                    "summary": summary,
                }
            )
    results.sort(
        key=lambda row: (
            row["summary"].get("executable_pnl_usd", 0.0),
            row["summary"].get("executable_signals", 0),
            row["summary"].get("signals", 0),
        ),
        reverse=True,
    )
    return {
        "generated_at": generated_at,
        "recorder_db_path": str(recorder_db_path),
        "lookback_hours": lookback_hours,
        "posture": {
            "paper_only": True,
            "wallet": False,
            "live_orders": False,
            "adr": "ADR-159",
            "open_question": "OQ-111",
        },
        "results": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Bot L Complete-Set Sensitivity Sweep",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Lookback hours: `{report['lookback_hours']}`",
        "",
        "Paper-only ADR-159 / OQ-111 analysis. Uses disposable local paper DBs only.",
        "",
        "| rank | raw_buy | raw_sell | slip | pair_age_ms | signals | executable | exec_pnl | buy_exec_pnl | sell_exec_pnl |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(report.get("results", []), start=1):
        summary = row["summary"]
        lines.append(
            "| {rank} | {raw_buy:.4f} | {raw_sell:.4f} | {slip:.4f} | {age} | "
            "{signals} | {exec_signals} | {exec_pnl:.4f} | {buy_pnl:.4f} | {sell_pnl:.4f} |".format(
                rank=rank,
                raw_buy=row["raw_buy_threshold"],
                raw_sell=row["raw_sell_threshold"],
                slip=row["slippage_per_leg"],
                age=row["max_pair_age_ms"],
                signals=summary.get("signals", 0),
                exec_signals=summary.get("executable_signals", 0),
                exec_pnl=summary.get("executable_pnl_usd", 0.0),
                buy_pnl=summary.get("buy_executable_pnl_usd", 0.0),
                sell_pnl=summary.get("sell_executable_pnl_usd", 0.0),
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    json_text = json.dumps(report, indent=2, sort_keys=True)
    md_text = render_markdown(report)
    json_path = out_dir / f"bot_l_complete_set_sensitivity_{stamp}.json"
    md_path = out_dir / f"bot_l_complete_set_sensitivity_{stamp}.md"
    latest_json = out_dir / "latest_sensitivity.json"
    latest_md = out_dir / "latest_sensitivity.md"
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
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--lookback-hours", type=float, default=168.0)
    parser.add_argument("--raw-buy-thresholds", default="0.990,0.995")
    parser.add_argument("--raw-sell-thresholds", default="1.005,1.010")
    parser.add_argument("--slippage-per-legs", default="0,0.005,0.010")
    parser.add_argument("--max-pair-age-ms-values", default="500,1000,2000")
    parser.add_argument("--gross-cost-usd", type=float, default=1.0)
    parser.add_argument("--min-depth-shares", type=float, default=0.0)
    parser.add_argument("--require-depth", action="store_true")
    parser.add_argument("--max-depth-age-ms", type=int, default=1000)
    args = parser.parse_args()
    report = run_sweep(
        recorder_db_path=args.recorder_db_path,
        lookback_hours=args.lookback_hours,
        raw_buy_thresholds=_parse_float_list(args.raw_buy_thresholds),
        raw_sell_thresholds=_parse_float_list(args.raw_sell_thresholds),
        slippage_per_legs=_parse_float_list(args.slippage_per_legs),
        max_pair_age_ms_values=_parse_int_list(args.max_pair_age_ms_values),
        gross_cost_usd=args.gross_cost_usd,
        min_depth_shares=args.min_depth_shares,
        require_depth=args.require_depth,
        max_depth_age_ms=args.max_depth_age_ms,
    )
    paths = write_outputs(report, args.out_dir)
    print(json.dumps({"generated_at": report["generated_at"], "paths": paths}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
