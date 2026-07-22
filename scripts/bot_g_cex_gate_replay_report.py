#!/usr/bin/env python3
"""Read-only Bot G CEX-gate replay report.

This report asks one narrow question: if Bot G had required CEX confirmation,
which historical Bot G entries would have been accepted, rejected, or left
unknown? It does not place orders, edit config, or mutate either DB.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.bot_g_crypto_replay_grid import (  # noqa: E402
    connect_ro,
    iso_sql,
    load_bot_orders,
    load_entry_payloads,
    parse_dt,
    symbol_from_question,
    table_exists,
)

DEFAULT_MAIN_DB = Path("data/main.db")
DEFAULT_RECORDER_DB = Path("data/bot_e_recorder.db")
DEFAULT_BOT_IDS = (
    "bot_g_prime_live",
    "bot_g_prime",
    "bot_g_prime_shadow",
    "bot_g_prime_late_cheap",
    "bot_g_prime_take_profit",
)
DEFAULT_CEX_WINDOW_SEC = 45
DEFAULT_MIN_CEX_MOVE_BPS = 1.5


@dataclass(frozen=True)
class CexState:
    tag: str
    symbol: str
    move_bps: float | None
    confirmed: bool | None
    source: str
    old_price: float | None = None
    new_price: float | None = None
    window_sec: int | None = None
    reason: str | None = None


def _num(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_symbol(row: dict[str, Any], payload: dict[str, Any]) -> str:
    cex = payload.get("cex") or {}
    raw = str(cex.get("symbol") or row.get("symbol") or "").upper()
    for symbol in ("BTC", "ETH", "SOL", "XRP", "DOGE"):
        if raw.startswith(symbol):
            return f"{symbol}USDT"
    q_symbol = symbol_from_question(row.get("question") or payload.get("question"))
    return f"{q_symbol}USDT" if q_symbol != "unknown" else "unknown"


def cex_tag_for_move(
    *,
    side_token: str,
    move_bps: float | None,
    min_move_bps: float,
) -> str:
    if move_bps is None:
        return "unknown"
    side = side_token.upper()
    if side == "YES":
        if move_bps >= min_move_bps:
            return "agree"
        if move_bps <= -min_move_bps:
            return "disagree"
        return "flat"
    if side == "NO":
        if move_bps <= -min_move_bps:
            return "agree"
        if move_bps >= min_move_bps:
            return "disagree"
        return "flat"
    return "unknown"


def reconstruct_cex_state(
    recorder: sqlite3.Connection,
    *,
    symbol: str,
    side_token: str,
    at_ms: int,
    window_sec: int,
    min_move_bps: float,
) -> CexState:
    if symbol == "unknown":
        return CexState("unknown", symbol, None, None, "reconstructed", reason="unknown_symbol")
    if not table_exists(recorder, "cex_trades"):
        return CexState("unknown", symbol, None, None, "reconstructed", reason="missing_cex_trades_table")
    start_ms = at_ms - window_sec * 1000
    try:
        older = recorder.execute(
            """
            SELECT price, trade_time_ms
            FROM cex_trades
            WHERE symbol = ?
              AND trade_time_ms >= ?
              AND trade_time_ms <= ?
            ORDER BY trade_time_ms ASC
            LIMIT 1
            """,
            (symbol, start_ms, at_ms),
        ).fetchone()
        latest = recorder.execute(
            """
            SELECT price, trade_time_ms
            FROM cex_trades
            WHERE symbol = ?
              AND trade_time_ms <= ?
            ORDER BY trade_time_ms DESC
            LIMIT 1
            """,
            (symbol, at_ms),
        ).fetchone()
    except sqlite3.Error as exc:
        return CexState("unknown", symbol, None, None, "reconstructed", reason=str(exc))
    if older is None or latest is None:
        return CexState("unknown", symbol, None, None, "reconstructed", reason="insufficient_cex_window")
    old_price = _num(older["price"])
    new_price = _num(latest["price"])
    if old_price is None or new_price is None or old_price <= 0:
        return CexState("unknown", symbol, None, None, "reconstructed", reason="invalid_cex_price")
    move_bps = (new_price - old_price) / old_price * 10000
    tag = cex_tag_for_move(side_token=side_token, move_bps=move_bps, min_move_bps=min_move_bps)
    return CexState(
        tag=tag,
        symbol=symbol,
        move_bps=move_bps,
        confirmed=tag == "agree",
        source="reconstructed",
        old_price=old_price,
        new_price=new_price,
        window_sec=window_sec,
    )


def cex_state_for_row(
    recorder: sqlite3.Connection,
    row: dict[str, Any],
    payload: dict[str, Any],
    *,
    default_window_sec: int,
    min_move_bps: float,
) -> CexState:
    side = str(row.get("side_token") or payload.get("side_token") or "").upper()
    cex = payload.get("cex") or {}
    symbol = _extract_symbol(row, payload)
    if cex and not cex.get("skipped"):
        move_bps = _num(cex.get("move_bps"))
        window_sec = int(_num(cex.get("window_sec")) or default_window_sec)
        tag = cex_tag_for_move(side_token=side, move_bps=move_bps, min_move_bps=min_move_bps)
        return CexState(
            tag=tag,
            symbol=symbol,
            move_bps=move_bps,
            confirmed=bool(cex.get("confirmed")) if cex.get("confirmed") is not None else tag == "agree",
            source="payload",
            old_price=_num(cex.get("old_price")),
            new_price=_num(cex.get("new_price")),
            window_sec=window_sec,
            reason=str(cex.get("reason") or "") or None,
        )
    placed_at = parse_dt(row.get("placed_at"))
    if placed_at is None:
        return CexState("unknown", symbol, None, None, "reconstructed", reason="missing_placed_at")
    return reconstruct_cex_state(
        recorder,
        symbol=symbol,
        side_token=side,
        at_ms=int(placed_at.timestamp() * 1000),
        window_sec=default_window_sec,
        min_move_bps=min_move_bps,
    )


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    phat = wins / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
    return ((centre - margin) / denom, (centre + margin) / denom)


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in rows if row.get("closed")]
    won = sum(1 for row in closed if row.get("win"))
    cost = sum(float(row.get("buy_notional") or 0) for row in closed)
    pnl = sum(float(row.get("pnl_usd") or 0) for row in closed)
    ci_lo, ci_hi = wilson_interval(won, len(closed))
    return {
        "orders": len(rows),
        "fills": sum(1 for row in rows if row.get("filled")),
        "resolved": len(closed),
        "won": won,
        "lost": len(closed) - won,
        "cost_basis_usd": round(cost, 4),
        "realized_pnl_usd": round(pnl, 4),
        "roi_pct": round(pnl / cost * 100, 2) if cost else None,
        "win_rate_pct": round(won / len(closed) * 100, 2) if closed else None,
        "wilson_ci_lo_pct": round(ci_lo * 100, 2) if ci_lo is not None else None,
        "wilson_ci_hi_pct": round(ci_hi * 100, 2) if ci_hi is not None else None,
    }


def enrich_rows(
    main: sqlite3.Connection,
    recorder: sqlite3.Connection,
    *,
    bot_ids: tuple[str, ...],
    cutoff: datetime,
    default_window_sec: int,
    min_move_bps: float,
) -> list[dict[str, Any]]:
    rows = load_bot_orders(main, recorder, bot_ids=bot_ids, cutoff=cutoff)
    payloads = load_entry_payloads(main, bot_ids=bot_ids, cutoff=cutoff)
    enriched: list[dict[str, Any]] = []
    for row in rows:
        payload = payloads.get(str(row.get("order_id") or ""), {})
        state = cex_state_for_row(
            recorder,
            row,
            payload,
            default_window_sec=default_window_sec,
            min_move_bps=min_move_bps,
        )
        row_symbol = str(row.get("symbol") or "unknown")
        if row_symbol == "unknown" and state.symbol != "unknown":
            row_symbol = state.symbol.removesuffix("USDT")
        enriched.append(
            {
                **row,
                "symbol": row_symbol,
                "cex_tag": state.tag,
                "cex_symbol": state.symbol,
                "cex_move_bps": round(state.move_bps, 4) if state.move_bps is not None else None,
                "cex_confirmed": state.confirmed,
                "cex_source": state.source,
                "cex_old_price": state.old_price,
                "cex_new_price": state.new_price,
                "cex_window_sec": state.window_sec,
                "cex_reason": state.reason,
                "gate_counterfactual": (
                    "would_enter" if state.tag == "agree"
                    else "would_skip" if state.tag in {"disagree", "flat"}
                    else "unknown"
                ),
            }
        )
    return enriched


def group_rows(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    keys = sorted({tuple(str(row.get(field) or "unknown") for field in fields) for row in rows})
    out: dict[str, dict[str, Any]] = {}
    for key in keys:
        group = [
            row for row in rows
            if tuple(str(row.get(field) or "unknown") for field in fields) == key
        ]
        out["|".join(key)] = {field: value for field, value in zip(fields, key, strict=True)}
        out["|".join(key)].update(summarise(group))
    return out


def build_report(
    main: sqlite3.Connection,
    recorder: sqlite3.Connection,
    *,
    bot_ids: tuple[str, ...],
    cutoff: datetime,
    default_window_sec: int = DEFAULT_CEX_WINDOW_SEC,
    min_move_bps: float = DEFAULT_MIN_CEX_MOVE_BPS,
) -> dict[str, Any]:
    rows = enrich_rows(
        main,
        recorder,
        bot_ids=bot_ids,
        cutoff=cutoff,
        default_window_sec=default_window_sec,
        min_move_bps=min_move_bps,
    )
    resolved_known = [
        row for row in rows
        if row.get("closed") and row.get("cex_tag") in {"agree", "disagree", "flat"}
    ]
    agree_summary = summarise([row for row in resolved_known if row.get("cex_tag") == "agree"])
    disagree_summary = summarise([row for row in resolved_known if row.get("cex_tag") == "disagree"])
    agree_wr = agree_summary.get("win_rate_pct")
    disagree_wr = disagree_summary.get("win_rate_pct")
    wr_gap = (
        round(float(agree_wr) - float(disagree_wr), 2)
        if agree_wr is not None and disagree_wr is not None
        else None
    )
    enough_sample = len(resolved_known) >= 50
    supports_paper_shadow = (
        enough_sample
        and wr_gap is not None
        and wr_gap >= 5
        and agree_summary.get("roi_pct") is not None
        and float(agree_summary["roi_pct"]) >= 0
        and disagree_summary.get("roi_pct") is not None
        and float(disagree_summary["roi_pct"]) < 0
    )
    if not enough_sample:
        verdict = "sample_too_small"
    elif supports_paper_shadow:
        verdict = "supports_paper_shadow_cex_test"
    else:
        verdict = "does_not_support_cex_gate_yet"
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "cutoff": cutoff.isoformat(),
        "bot_ids": list(bot_ids),
        "cex_window_sec": default_window_sec,
        "min_move_bps": min_move_bps,
        "verdict": verdict,
        "success_checks": {
            "resolved_known_cex_rows": len(resolved_known),
            "sample_minimum": 50,
            "sample_pass": enough_sample,
            "agree_minus_disagree_win_rate_pp": wr_gap,
            "agree_roi_pct": agree_summary.get("roi_pct"),
            "disagree_roi_pct": disagree_summary.get("roi_pct"),
            "paper_shadow_test_supported": supports_paper_shadow,
        },
        "overall": summarise(rows),
        "by_cex_tag": group_rows(rows, ("cex_tag",)),
        "by_bot_cex_tag": group_rows(rows, ("bot_id", "cex_tag")),
        "by_bot_symbol_side_cex": group_rows(rows, ("bot_id", "symbol", "side_token", "cex_tag")),
        "by_bot_lead_cex": group_rows(rows, ("bot_id", "lead_bucket", "cex_tag")),
        "by_counterfactual": group_rows(rows, ("bot_id", "gate_counterfactual")),
        "recent_rows": rows[-40:],
    }


def pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.1f}%"


def money(value: object) -> str:
    return f"${float(value or 0):+.2f}"


def _table(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> list[str]:
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    if not rows:
        lines.append("| " + " | ".join("n/a" for _ in columns) + " |")
        return lines
    for row in rows:
        values: list[str] = []
        for column in columns:
            if column == "pnl":
                values.append(money(row.get("realized_pnl_usd")))
            elif column == "roi":
                values.append(pct(row.get("roi_pct")))
            elif column == "win_rate":
                values.append(pct(row.get("win_rate_pct")))
            elif column == "wilson_95":
                values.append(f"{pct(row.get('wilson_ci_lo_pct'))}-{pct(row.get('wilson_ci_hi_pct'))}")
            else:
                values.append(str(row.get(column) if row.get(column) is not None else "n/a"))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    checks = report["success_checks"]
    lines = [
        "# Bot G CEX-Gate Replay Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Window start: `{report['cutoff']}`",
        f"CEX gate: `{report['cex_window_sec']}s`, `{report['min_move_bps']} bps` threshold",
        f"Verdict: `{report['verdict']}`",
        "",
        "## Read This First",
        "",
        "This is read-only research. It does not change live trading, paper services, caps, sizing, wallets, or halt logic.",
        "Live rows with skipped CEX metadata are reconstructed from the recorder at order placement time, matching when the bot would have made the entry decision.",
        "",
        "## Gate Checks",
        "",
        f"- Resolved rows with known CEX state: `{checks['resolved_known_cex_rows']}` / `{checks['sample_minimum']}`",
        f"- Sample pass: `{checks['sample_pass']}`",
        f"- Agree minus disagree win-rate gap: `{checks['agree_minus_disagree_win_rate_pp']}` percentage points",
        f"- Agree ROI: `{pct(checks['agree_roi_pct'])}`",
        f"- Disagree ROI: `{pct(checks['disagree_roi_pct'])}`",
        f"- Paper-shadow CEX test supported: `{checks['paper_shadow_test_supported']}`",
        "",
        "## Overall By CEX Tag",
        "",
    ]
    tag_rows = sorted(report["by_cex_tag"].values(), key=lambda row: row["cex_tag"])
    lines.extend(_table(tag_rows, ("cex_tag", "orders", "fills", "resolved", "won", "lost", "pnl", "roi", "win_rate", "wilson_95")))
    lines.extend([
        "",
        "## Bot By CEX Tag",
        "",
    ])
    bot_rows = sorted(report["by_bot_cex_tag"].values(), key=lambda row: (row["bot_id"], row["cex_tag"]))
    lines.extend(_table(bot_rows, ("bot_id", "cex_tag", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Counterfactual Gate Result",
        "",
        "`would_enter` means CEX agreed with the side. `would_skip` means CEX was flat or against it. `unknown` means the report could not prove the gate state.",
        "",
    ])
    cf_rows = sorted(report["by_counterfactual"].values(), key=lambda row: (row["bot_id"], row["gate_counterfactual"]))
    lines.extend(_table(cf_rows, ("bot_id", "gate_counterfactual", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Symbol x Side x CEX",
        "",
    ])
    symbol_rows = sorted(
        report["by_bot_symbol_side_cex"].values(),
        key=lambda row: (row["bot_id"], row["symbol"], row["side_token"], row["cex_tag"]),
    )
    lines.extend(_table(symbol_rows, ("bot_id", "symbol", "side_token", "cex_tag", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Lead x CEX",
        "",
    ])
    lead_rows = sorted(
        report["by_bot_lead_cex"].values(),
        key=lambda row: (row["bot_id"], row["lead_bucket"], row["cex_tag"]),
    )
    lines.extend(_table(lead_rows, ("bot_id", "lead_bucket", "cex_tag", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Recent Rows",
        "",
        "| bot | placed | symbol | side | lead | limit | CEX | move bps | source | outcome | P&L |",
        "|---|---|---|---|---|---:|---|---:|---|---|---:|",
    ])
    for row in report["recent_rows"]:
        lines.append(
            f"| {row.get('bot_id')} | {row.get('placed_at')} | {row.get('symbol')} | "
            f"{row.get('side_token')} | {row.get('lead_bucket')} | "
            f"{float(row.get('limit_price') or 0):.4f} | {row.get('cex_tag')} | "
            f"{row.get('cex_move_bps') if row.get('cex_move_bps') is not None else 'n/a'} | "
            f"{row.get('cex_source')} | {row.get('outcome')} | {money(row.get('pnl_usd'))} |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    today = datetime.now(UTC).date().isoformat()
    parser = argparse.ArgumentParser(description="Build read-only Bot G CEX-gate replay report.")
    parser.add_argument("--db", "--main-db", dest="db", type=Path, default=DEFAULT_MAIN_DB)
    parser.add_argument("--recorder-db", type=Path, default=DEFAULT_RECORDER_DB)
    parser.add_argument("--lookback-hours", type=float, default=168.0)
    parser.add_argument("--bot-id", action="append", dest="bot_ids")
    parser.add_argument("--cex-window-sec", type=int, default=DEFAULT_CEX_WINDOW_SEC)
    parser.add_argument("--min-move-bps", type=float, default=DEFAULT_MIN_CEX_MOVE_BPS)
    parser.add_argument("--out-json", "--output-json", dest="output_json", type=Path)
    parser.add_argument(
        "--out-md",
        "--output-md",
        dest="output_md",
        type=Path,
        default=Path(f"docs/reports/bot-g-cex-gate-replay-{today}.md"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    bot_ids = tuple(args.bot_ids or DEFAULT_BOT_IDS)
    cutoff = datetime.now(UTC) - timedelta(hours=args.lookback_hours)
    main_con = connect_ro(args.db)
    recorder_con = connect_ro(args.recorder_db)
    try:
        report = build_report(
            main_con,
            recorder_con,
            bot_ids=bot_ids,
            cutoff=cutoff,
            default_window_sec=args.cex_window_sec,
            min_move_bps=args.min_move_bps,
        )
    finally:
        main_con.close()
        recorder_con.close()
    markdown = render_markdown(report)
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True))
    if not args.output_md:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
