#!/usr/bin/env python3
"""Read-only daily Bot G microstructure probe report.

This report is for the current `$1` Bot G live data-gathering posture. It
does not place orders, mutate DB rows, change services, or recommend live
parameter changes from a single run.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.bot_g_cex_gate_replay_report import (  # noqa: E402
    DEFAULT_CEX_WINDOW_SEC,
    DEFAULT_MIN_CEX_MOVE_BPS,
    cex_state_for_row,
    reconstruct_cex_state,
)
from scripts.bot_g_crypto_replay_grid import (  # noqa: E402
    connect_ro,
    load_bot_orders,
    load_entry_payloads,
    parse_dt,
)
from scripts.research.markov_state_replay import (  # noqa: E402
    bot_g_micro_state,
    estimate_transition_matrix,
    stationary_distribution,
    walk_forward_forecasts,
)

DEFAULT_MAIN_DB = Path("data/main.db")
DEFAULT_RECORDER_DB = Path("data/bot_e_recorder.db")
DEFAULT_BOT_IDS = (
    "bot_g_prime_live",
    "bot_g_prime",
    "bot_g_prime_shadow",
    "bot_g_prime_high_tail",
    "bot_g_prime_late_cheap",
    "bot_g_prime_take_profit",
)
LIVE_BOT_ID = "bot_g_prime_live"
CEX_WINDOWS_SEC = (5, 15, 30, 45, 60)


def _num(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _wilson(wins: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return centre - margin, centre + margin


def _price_sub_band(value: object) -> str:
    p = _num(value)
    if p is None:
        return "unknown"
    if p < 0.035:
        return "<3.5c"
    if p < 0.045:
        return "3.5c-4.5c"
    if p <= 0.055:
        return "4.5c-5.5c"
    return ">5.5c"


def _entry_price(row: dict[str, Any]) -> float | None:
    return _num(row.get("observed_price") or row.get("limit_price"))


def _price_point_bucket(value: object) -> str:
    p = _num(value)
    if p is None:
        return "unknown"
    if p < 0.01:
        return "<1c"
    if p >= 0.08:
        return ">=8c"
    lower = int(p * 100)
    upper = lower + 1
    return f"{lower}c-{upper}c"


def _volatility_regime(move_bps: object) -> str:
    move = _num(move_bps)
    if move is None:
        return "unknown"
    abs_move = abs(move)
    if abs_move < 1.5:
        return "low"
    if abs_move < 5.0:
        return "medium"
    return "high"


def _session_bucket(hour: int | None) -> str:
    if hour is None:
        return "unknown"
    if 0 <= hour < 7:
        return "asia_overnight"
    if 7 <= hour < 13:
        return "europe_morning"
    if 13 <= hour < 21:
        return "us_overlap"
    return "late_us"


def _macro_window(payload: dict[str, Any]) -> str:
    for key in ("macro_window", "news_window", "event_window", "market_event_window"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return "unclassified"


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [row for row in rows if row.get("closed")]
    won = sum(1 for row in closed if row.get("win"))
    cost = sum(float(row.get("buy_notional") or 0) for row in closed)
    pnl = sum(float(row.get("pnl_usd") or 0) for row in closed)
    ci_lo, ci_hi = _wilson(won, len(closed))
    placed = len(rows)
    filled = sum(1 for row in rows if row.get("filled"))
    no_fill = sum(1 for row in rows if row.get("outcome") == "no_fill")
    return {
        "orders": placed,
        "fills": filled,
        "fill_rate_pct": round(filled / placed * 100, 2) if placed else None,
        "no_fill": no_fill,
        "resolved": len(closed),
        "won": won,
        "lost": len(closed) - won,
        "cost_basis_usd": round(cost, 4),
        "realized_pnl_usd": round(pnl, 4),
        "roi_pct": round(pnl / cost * 100, 2) if cost else None,
        "win_rate_pct": round(won / len(closed) * 100, 2) if closed else None,
        "wilson_lo_pct": round(ci_lo * 100, 2) if ci_lo is not None else None,
        "wilson_hi_pct": round(ci_hi * 100, 2) if ci_hi is not None else None,
    }


def _group_rows(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    keys = sorted({tuple(str(row.get(field) or "unknown") for field in fields) for row in rows})
    out: list[dict[str, Any]] = []
    for key in keys:
        group = [
            row
            for row in rows
            if tuple(str(row.get(field) or "unknown") for field in fields) == key
        ]
        record = {field: value for field, value in zip(fields, key, strict=True)}
        record.update(_summarise(group))
        out.append(record)
    return out


def _sub8_winners(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    winners = [
        row
        for row in rows
        if row.get("win")
        and (price := _entry_price(row)) is not None
        and price < 0.08
    ]
    winners.sort(key=lambda row: str(row.get("placed_at") or ""), reverse=True)
    out: list[dict[str, Any]] = []
    for row in winners:
        out.append(
            {
                "bot_id": row.get("bot_id"),
                "placed_at": row.get("placed_at"),
                "symbol": row.get("symbol"),
                "side_token": row.get("side_token"),
                "entry_price": _entry_price(row),
                "price_point": row.get("price_point_bucket"),
                "lead_bucket": row.get("lead_bucket"),
                "utc_hour": row.get("utc_hour"),
                "session_bucket": row.get("session_bucket"),
                "cex_tag": row.get("cex_tag"),
                "volatility_regime": row.get("volatility_regime"),
                "buy_notional": row.get("buy_notional"),
                "pnl_usd": row.get("pnl_usd"),
                "question": row.get("question"),
            }
        )
    return out


def _cex_multi_window(
    recorder: sqlite3.Connection,
    *,
    row: dict[str, Any],
    payload: dict[str, Any],
    min_move_bps: float,
) -> dict[str, Any]:
    side = str(row.get("side_token") or payload.get("side_token") or "").upper()
    placed_at = parse_dt(row.get("placed_at"))
    default_state = cex_state_for_row(
        recorder,
        row,
        payload,
        default_window_sec=DEFAULT_CEX_WINDOW_SEC,
        min_move_bps=min_move_bps,
    )
    out: dict[str, Any] = {
        "cex_tag": default_state.tag,
        "cex_symbol": default_state.symbol,
        "cex_move_bps": round(default_state.move_bps, 4) if default_state.move_bps is not None else None,
        "cex_source": default_state.source,
        "cex_reason": default_state.reason,
    }
    if placed_at is None or side not in {"YES", "NO"}:
        for window in CEX_WINDOWS_SEC:
            out[f"cex_{window}s_tag"] = "unknown"
            out[f"cex_{window}s_move_bps"] = None
        return out

    at_ms = int(placed_at.timestamp() * 1000)
    for window in CEX_WINDOWS_SEC:
        if window == DEFAULT_CEX_WINDOW_SEC and default_state.tag != "unknown":
            state = default_state
        else:
            state = reconstruct_cex_state(
                recorder,
                symbol=default_state.symbol,
                side_token=side,
                at_ms=at_ms,
                window_sec=window,
                min_move_bps=min_move_bps,
            )
        out[f"cex_{window}s_tag"] = state.tag
        out[f"cex_{window}s_move_bps"] = (
            round(state.move_bps, 4) if state.move_bps is not None else None
        )
    return out


def enrich_rows(
    main: sqlite3.Connection,
    recorder: sqlite3.Connection,
    *,
    bot_ids: tuple[str, ...],
    cutoff: datetime,
    min_move_bps: float = DEFAULT_MIN_CEX_MOVE_BPS,
) -> list[dict[str, Any]]:
    rows = load_bot_orders(main, recorder, bot_ids=bot_ids, cutoff=cutoff)
    payloads = load_entry_payloads(main, bot_ids=bot_ids, cutoff=cutoff)
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = payloads.get(str(row.get("order_id") or ""), {})
        placed_at = parse_dt(row.get("placed_at"))
        hour = placed_at.hour if placed_at is not None else None
        day = placed_at.strftime("%a") if placed_at is not None else "unknown"
        cex = _cex_multi_window(
            recorder,
            row=row,
            payload=payload,
            min_move_bps=min_move_bps,
        )
        record = {
            **row,
            **cex,
            "probe_lane": "live" if row.get("bot_id") == LIVE_BOT_ID else "paper",
            "entry_price": _entry_price(row),
            "price_point_bucket": _price_point_bucket(
                row.get("observed_price") or row.get("limit_price")
            ),
            "sub8_entry": (
                (entry_price := _entry_price(row)) is not None
                and entry_price < 0.08
            ),
            "price_sub_band": _price_sub_band(row.get("observed_price") or row.get("limit_price")),
            "utc_hour": f"{hour:02d}" if hour is not None else "unknown",
            "utc_dow": day,
            "session_bucket": _session_bucket(hour),
            "volatility_regime": _volatility_regime(cex.get("cex_60s_move_bps")),
            "macro_window": _macro_window(payload),
        }
        out.append(record)
    return out


def _promotion_watchlist(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    live_rows = [row for row in rows if row.get("bot_id") == LIVE_BOT_ID]
    candidates: list[dict[str, Any]] = []
    specs = (
        ("CEX-flat", ("cex_tag",), {"cex_tag": "flat"}),
        ("SOL / SOL-NO", ("symbol", "side_token"), {"symbol": "SOL", "side_token": "NO"}),
        ("DOWN/NO side", ("side_token",), {"side_token": "NO"}),
        ("30s-45s lead", ("lead_bucket",), {"lead_bucket": "30s-45s"}),
        ("UTC hour", ("utc_hour",), {}),
        ("volatility regime", ("volatility_regime",), {}),
        ("price sub-band", ("price_sub_band",), {}),
    )
    for label, fields, required in specs:
        source = live_rows
        for key, value in required.items():
            source = [row for row in source if str(row.get(key) or "unknown") == value]
        groups = _group_rows(source, fields)
        for group in groups:
            record = {"watch_bucket": label, **group}
            record["sample_pass"] = (
                int(record.get("resolved") or 0) >= 20
                and int(record.get("won") or 0) >= 2
                and record.get("roi_pct") is not None
                and float(record["roi_pct"]) > 0
            )
            candidates.append(record)
    return candidates


def _markov_live_microstates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    live_rows = [
        row for row in rows
        if row.get("bot_id") == LIVE_BOT_ID and row.get("placed_at")
    ]
    live_rows.sort(key=lambda row: str(row.get("placed_at") or ""))
    sequence = [bot_g_micro_state(row) for row in live_rows]
    estimate = estimate_transition_matrix(
        sequence,
        alpha=1.0,
        min_row_count=30,
        min_cell_count=20,
    )
    forecasts = walk_forward_forecasts(
        sequence,
        lookback=min(50, max(2, len(sequence) // 2)),
        states=estimate.states,
        alpha=1.0,
        min_row_count=30,
        min_cell_count=20,
    ) if len(sequence) >= 4 else []
    state_pnl: dict[str, dict[str, Any]] = {}
    for row, state in zip(live_rows, sequence, strict=True):
        bucket = state_pnl.setdefault(
            state,
            {"orders": 0, "resolved": 0, "won": 0, "pnl_usd": 0.0, "cost_usd": 0.0},
        )
        bucket["orders"] += 1
        if row.get("closed"):
            bucket["resolved"] += 1
            bucket["won"] += 1 if row.get("win") else 0
            bucket["pnl_usd"] += float(row.get("pnl_usd") or 0)
            bucket["cost_usd"] += float(row.get("buy_notional") or 0)
    for bucket in state_pnl.values():
        cost = float(bucket.get("cost_usd") or 0)
        bucket["roi_pct"] = round(float(bucket["pnl_usd"]) / cost * 100, 2) if cost else None
        bucket["pnl_usd"] = round(float(bucket["pnl_usd"]), 4)
        bucket["cost_usd"] = round(cost, 4)
    top_states = sorted(
        (
            {"state": state, **metrics}
            for state, metrics in state_pnl.items()
        ),
        key=lambda row: (-int(row["orders"]), str(row["state"])),
    )[:20]
    return {
        "posture": "research_only_no_live_gate",
        "n_rows": len(live_rows),
        "n_states": len(estimate.states),
        "states": list(estimate.states),
        "transition_counts": estimate.counts,
        "transition_matrix": estimate.matrix,
        "stationary_distribution": stationary_distribution(estimate.matrix),
        "sparse_rows": estimate.sparse_rows,
        "sparse_cell_count": len(estimate.sparse_cells),
        "walk_forward_count": len(forecasts),
        "top_states": top_states,
    }


def build_report(
    main: sqlite3.Connection,
    recorder: sqlite3.Connection,
    *,
    bot_ids: tuple[str, ...],
    cutoff: datetime,
    min_move_bps: float = DEFAULT_MIN_CEX_MOVE_BPS,
) -> dict[str, Any]:
    rows = enrich_rows(
        main,
        recorder,
        bot_ids=bot_ids,
        cutoff=cutoff,
        min_move_bps=min_move_bps,
    )
    sub8_rows = [row for row in rows if row.get("sub8_entry")]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "cutoff": cutoff.isoformat(),
        "bot_ids": list(bot_ids),
        "live_bot_id": LIVE_BOT_ID,
        "min_move_bps": min_move_bps,
        "posture": "read_only_probe_report_no_live_parameter_change",
        "overall": _summarise(rows),
        "overall_by_bot": _group_rows(rows, ("bot_id",)),
        "by_lane_cex": _group_rows(rows, ("probe_lane", "cex_tag")),
        "by_live_watch_bucket": _promotion_watchlist(rows),
        "by_live_symbol_side": _group_rows(
            [row for row in rows if row.get("bot_id") == LIVE_BOT_ID],
            ("symbol", "side_token"),
        ),
        "by_live_lead": _group_rows(
            [row for row in rows if row.get("bot_id") == LIVE_BOT_ID],
            ("lead_bucket",),
        ),
        "by_live_utc_hour": _group_rows(
            [row for row in rows if row.get("bot_id") == LIVE_BOT_ID],
            ("utc_hour",),
        ),
        "by_live_session": _group_rows(
            [row for row in rows if row.get("bot_id") == LIVE_BOT_ID],
            ("session_bucket",),
        ),
        "by_live_volatility": _group_rows(
            [row for row in rows if row.get("bot_id") == LIVE_BOT_ID],
            ("volatility_regime",),
        ),
        "by_live_price_sub_band": _group_rows(
            [row for row in rows if row.get("bot_id") == LIVE_BOT_ID],
            ("price_sub_band",),
        ),
        "by_live_price_point": _group_rows(
            [row for row in rows if row.get("bot_id") == LIVE_BOT_ID],
            ("price_point_bucket",),
        ),
        "by_sub8_price_point": _group_rows(
            sub8_rows,
            ("probe_lane", "price_point_bucket"),
        ),
        "by_sub8_symbol_price_point": _group_rows(
            sub8_rows,
            ("symbol", "side_token", "price_point_bucket"),
        ),
        "sub8_winners": _sub8_winners(rows),
        "by_live_macro_window": _group_rows(
            [row for row in rows if row.get("bot_id") == LIVE_BOT_ID],
            ("macro_window",),
        ),
        "markov_live_microstates": _markov_live_microstates(rows),
        "recent_rows": rows[-40:],
    }


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.1f}%"


def _money(value: object) -> str:
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
        values = []
        for column in columns:
            if column == "pnl":
                values.append(_money(row.get("realized_pnl_usd")))
            elif column in {"roi", "roi_pct"}:
                values.append(_pct(row.get("roi_pct")))
            elif column == "win_rate":
                values.append(_pct(row.get("win_rate_pct")))
            elif column == "fill_rate":
                values.append(_pct(row.get("fill_rate_pct")))
            elif column == "sample_pass":
                values.append(str(bool(row.get("sample_pass"))))
            else:
                values.append(str(row.get(column) if row.get(column) is not None else "n/a"))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Bot G Daily Probe Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Window start: `{report['cutoff']}`",
        f"Posture: `{report['posture']}`",
        "",
        "## Read This First",
        "",
        "This is read-only research for the `$1` Bot G live data-gathering probe. It does not change live trading, paper services, caps, sizing, wallets, order paths, or filters.",
        "",
        "A bucket is not promotable unless it has at least `20` resolved live fills, at least `2` wins, and positive realised ROI. Buckets below that threshold are watch-list evidence only.",
        "",
        "## Overall By Bot",
        "",
    ]
    lines.extend(_table(report["overall_by_bot"], ("bot_id", "orders", "fills", "fill_rate", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Live Watch Buckets",
        "",
    ])
    watch_rows = sorted(
        report["by_live_watch_bucket"],
        key=lambda row: (str(row.get("watch_bucket")), -int(row.get("resolved") or 0)),
    )
    lines.extend(_table(watch_rows, ("watch_bucket", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate", "sample_pass")))
    lines.extend([
        "",
        "## Live By Symbol And Side",
        "",
    ])
    lines.extend(_table(report["by_live_symbol_side"], ("symbol", "side_token", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Live By Lead Bucket",
        "",
    ])
    lines.extend(_table(report["by_live_lead"], ("lead_bucket", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Live By UTC Hour",
        "",
    ])
    lines.extend(_table(report["by_live_utc_hour"], ("utc_hour", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Live By Volatility",
        "",
    ])
    lines.extend(_table(report["by_live_volatility"], ("volatility_regime", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Live By Current Band Slice",
        "",
    ])
    lines.extend(_table(report["by_live_price_sub_band"], ("price_sub_band", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Live By Entry Price Point",
        "",
    ])
    lines.extend(_table(report["by_live_price_point"], ("price_point_bucket", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    markov = report.get("markov_live_microstates") or {}
    lines.extend([
        "",
        "## Live Markov Microstates",
        "",
        f"Posture: `{markov.get('posture', 'research_only_no_live_gate')}`",
        f"Rows: **{markov.get('n_rows', 0)}**; states: **{markov.get('n_states', 0)}**; sparse rows: **{len(markov.get('sparse_rows') or [])}**; sparse cells: **{markov.get('sparse_cell_count', 0)}**",
        "",
        "| state | orders | resolved | won | pnl | roi |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in markov.get("top_states") or []:
        lines.append(
            f"| {row.get('state')} | {row.get('orders')} | {row.get('resolved')} | "
            f"{row.get('won')} | {_money(row.get('pnl_usd'))} | {_pct(row.get('roi_pct'))} |"
        )
    if not markov.get("top_states"):
        lines.append("| n/a | 0 | 0 | 0 | $+0.00 | n/a |")
    lines.extend([
        "",
        "## Sub-8c Entries By Price Point",
        "",
    ])
    lines.extend(_table(report["by_sub8_price_point"], ("probe_lane", "price_point_bucket", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Sub-8c Entries By Symbol / Side / Price",
        "",
    ])
    lines.extend(_table(report["by_sub8_symbol_price_point"], ("symbol", "side_token", "price_point_bucket", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Sub-8c Winner Tape",
        "",
        "| bot | placed | symbol | side | entry | lead | UTC hour | CEX | vol | P&L | question |",
        "|---|---|---|---|---:|---|---:|---|---|---:|---|",
    ])
    if report["sub8_winners"]:
        for row in report["sub8_winners"]:
            entry = row.get("entry_price")
            lines.append(
                f"| {row.get('bot_id')} | {row.get('placed_at')} | {row.get('symbol')} | "
                f"{row.get('side_token')} | {float(entry or 0):.2f} | "
                f"{row.get('lead_bucket')} | {row.get('utc_hour')} | "
                f"{row.get('cex_tag')} | {row.get('volatility_regime')} | "
                f"{_money(row.get('pnl_usd'))} | {row.get('question')} |"
            )
    else:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")
    lines.extend([
        "",
        "## Lane x CEX",
        "",
    ])
    lines.extend(_table(report["by_lane_cex"], ("probe_lane", "cex_tag", "orders", "fills", "resolved", "won", "pnl", "roi", "win_rate")))
    lines.extend([
        "",
        "## Recent Rows",
        "",
        "| bot | placed | symbol | side | lead | price slice | UTC hour | CEX | vol | outcome | P&L |",
        "|---|---|---|---|---|---|---:|---|---|---|---:|",
    ])
    for row in report["recent_rows"]:
        lines.append(
            f"| {row.get('bot_id')} | {row.get('placed_at')} | {row.get('symbol')} | "
            f"{row.get('side_token')} | {row.get('lead_bucket')} | "
            f"{row.get('price_sub_band')} | {row.get('utc_hour')} | "
            f"{row.get('cex_tag')} | {row.get('volatility_regime')} | "
            f"{row.get('outcome')} | {_money(row.get('pnl_usd'))} |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    today = datetime.now(UTC).date().isoformat()
    parser = argparse.ArgumentParser(description="Build read-only Bot G daily probe report.")
    parser.add_argument("--db", "--main-db", dest="db", type=Path, default=DEFAULT_MAIN_DB)
    parser.add_argument("--recorder-db", type=Path, default=DEFAULT_RECORDER_DB)
    parser.add_argument("--lookback-hours", type=float, default=24.0)
    parser.add_argument("--bot-id", action="append", dest="bot_ids")
    parser.add_argument("--min-move-bps", type=float, default=DEFAULT_MIN_CEX_MOVE_BPS)
    parser.add_argument(
        "--out-md",
        "--output-md",
        dest="output_md",
        type=Path,
        default=Path(f"docs/reports/bot-g-daily-probe-{today}.md"),
    )
    parser.add_argument(
        "--out-json",
        "--output-json",
        dest="output_json",
        type=Path,
        default=Path(f"docs/reports/bot-g-daily-probe-{today}.json"),
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
