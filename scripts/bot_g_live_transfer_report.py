#!/usr/bin/env python3
"""Read-only Bot G live-transfer report.

This report measures whether Bot G Prime paper setups transfer into the live
ledger after real timing, CLOB submission, fills/no-fills, and settlement.
It does not place orders or change any bot settings.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

from scripts.bot_g_feature_analysis import (
    fetch_trades,
    fifo_match,
)

DEFAULT_DB = Path("data/main.db")


def _connect_ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _has_table(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _cutoff_sql(cutoff: datetime) -> str:
    return cutoff.strftime("%Y-%m-%d %H:%M:%S")


def _json_payload(raw: object) -> dict[str, Any]:
    try:
        loaded = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def price_zone(price: object) -> str:
    try:
        p = float(price or 0)
    except (TypeError, ValueError):
        return "unknown"
    if 0.035 <= p < 0.04:
        return "3.5c-4c"
    if 0.04 <= p <= 0.05:
        return "4c-5c"
    if 0.05 < p <= 0.055:
        return "5c-5.5c"
    if p < 0.035:
        return "<3.5c"
    return ">5.5c"


def setup_label(payload: dict[str, Any]) -> str:
    cex = payload.get("cex") or {}
    if isinstance(cex, dict) and cex.get("skipped"):
        return "label_skipped"
    if not isinstance(cex, dict) or cex.get("move_bps") is None:
        return "unknown"
    try:
        move = abs(float(cex.get("move_bps") or 0))
        threshold = abs(float(cex.get("min_move_bps") or 1.5))
    except (TypeError, ValueError):
        return "unknown"
    if move < threshold:
        return "dead_market"
    if cex.get("confirmed") is True:
        return "continuation"
    return "countertrend_or_choppy"


def fresh_lead_bucket(value: object) -> str:
    try:
        lead = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if lead < 5:
        return "<5s"
    if lead < 15:
        return "5s-15s"
    if lead < 30:
        return "15s-30s"
    return ">=30s"


def symbol_label(payload: dict[str, Any], question: object = None) -> str:
    cex = payload.get("cex") or {}
    if isinstance(cex, dict):
        raw = str(cex.get("symbol") or "").upper()
        if raw:
            return raw.removesuffix("USDT")
    q = str(question or "").upper()
    for symbol, needles in {
        "BTC": ("BTC", "BITCOIN"),
        "ETH": ("ETH", "ETHEREUM"),
        "SOL": ("SOL", "SOLANA"),
        "XRP": ("XRP", "RIPPLE"),
        "DOGE": ("DOGE", "DOGECOIN"),
    }.items():
        if any(needle in q for needle in needles):
            return symbol
    return "unknown"


def _market_questions(con: sqlite3.Connection) -> dict[str, str]:
    if not _has_table(con, "markets"):
        return {}
    out = {}
    for row in con.execute(
        """
        SELECT condition_id, question
        FROM markets
        WHERE condition_id IS NOT NULL
        GROUP BY condition_id
        """
    ):
        out[str(row["condition_id"])] = str(row["question"] or "")
    return out


def _entry_events(
    con: sqlite3.Connection,
    *,
    bot_id: str,
    cutoff: datetime,
) -> dict[str, dict[str, Any]]:
    if not _has_table(con, "events"):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in con.execute(
        """
        SELECT created_at, payload
        FROM events
        WHERE bot_id = ?
          AND event_type = 'bot_g.entry_placed'
          AND created_at >= ?
          AND payload IS NOT NULL
        ORDER BY created_at
        """,
        (bot_id, _cutoff_sql(cutoff)),
    ):
        payload = _json_payload(row["payload"])
        order_id = str(payload.get("order_id") or "")
        if order_id:
            payload["_created_at"] = row["created_at"]
            out[order_id] = payload
    return out


def _stale_rejects(
    con: sqlite3.Connection,
    *,
    bot_id: str,
    cutoff: datetime,
) -> list[dict[str, Any]]:
    if not _has_table(con, "events"):
        return []
    questions = _market_questions(con)
    rows = []
    for row in con.execute(
        """
        SELECT created_at, payload
        FROM events
        WHERE bot_id = ?
          AND event_type = 'bot_g.entry_stale_time_rejected'
          AND created_at >= ?
        ORDER BY created_at
        """,
        (bot_id, _cutoff_sql(cutoff)),
    ):
        payload = _json_payload(row["payload"])
        question = questions.get(str(payload.get("condition_id") or ""))
        rows.append(
            {
                "created_at": row["created_at"],
                "condition_id": payload.get("condition_id"),
                "token_id": payload.get("token_id"),
                "price_zone": price_zone(
                    payload.get("observed_ask_price") or payload.get("limit_price")
                ),
                "fresh_t_to_res_sec": payload.get("fresh_t_to_res_sec"),
                "initial_t_to_res_sec": payload.get("initial_t_to_res_sec"),
                "fresh_lead_bucket": fresh_lead_bucket(payload.get("fresh_t_to_res_sec")),
                "symbol": symbol_label(payload, question),
                "setup_label": setup_label(payload),
                "timing_ms": payload.get("timing_ms") or {},
            }
        )
    return rows


def _event_count(
    con: sqlite3.Connection,
    *,
    bot_id: str,
    event_type: str,
    cutoff: datetime,
) -> int:
    if not _has_table(con, "events"):
        return 0
    row = con.execute(
        """
        SELECT COUNT(*) AS n
        FROM events
        WHERE bot_id = ?
          AND event_type = ?
          AND created_at >= ?
        """,
        (bot_id, event_type, _cutoff_sql(cutoff)),
    ).fetchone()
    return int(row["n"] or 0) if row else 0


def _trade_counts_by_order(
    con: sqlite3.Connection,
    *,
    bot_id: str,
    cutoff: datetime,
) -> dict[str, dict[str, Any]]:
    if not _has_table(con, "trades"):
        return {}
    out: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"buy_fills": 0, "settlement_fills": 0, "fill_price": None, "filled_at": None}
    )
    for row in con.execute(
        """
        SELECT order_id, side, price, filled_at
        FROM trades
        WHERE bot_id = ?
          AND filled_at >= ?
        ORDER BY filled_at
        """,
        (bot_id, _cutoff_sql(cutoff)),
    ):
        order_id = str(row["order_id"] or "")
        if not order_id:
            continue
        side = str(row["side"] or "").upper()
        if side.startswith("BUY"):
            out[order_id]["buy_fills"] += 1
            if out[order_id]["fill_price"] is None:
                out[order_id]["fill_price"] = float(row["price"] or 0)
                out[order_id]["filled_at"] = row["filled_at"]
        elif side.startswith("SELL"):
            out[order_id]["settlement_fills"] += 1
    return dict(out)


def _order_price_by_id(
    con: sqlite3.Connection,
    *,
    bot_id: str,
    order_ids: set[str],
) -> dict[str, float]:
    if not order_ids or not _has_table(con, "orders"):
        return {}
    placeholders = ",".join("?" for _ in order_ids)
    rows = con.execute(
        f"""
        SELECT order_id, price
        FROM orders
        WHERE bot_id = ?
          AND order_id IN ({placeholders})
        """,
        (bot_id, *sorted(order_ids)),
    )
    return {str(row["order_id"]): float(row["price"] or 0) for row in rows}


def _live_orders(
    con: sqlite3.Connection,
    *,
    bot_id: str,
    cutoff: datetime,
) -> list[dict[str, Any]]:
    if not _has_table(con, "orders"):
        return []
    entry_payloads = _entry_events(con, bot_id=bot_id, cutoff=cutoff)
    trade_counts = _trade_counts_by_order(con, bot_id=bot_id, cutoff=cutoff)
    questions = _market_questions(con)
    out = []
    for row in con.execute(
        """
        SELECT order_id, condition_id, token_id, price, size, status, placed_at
        FROM orders
        WHERE bot_id = ?
          AND placed_at >= ?
        ORDER BY placed_at
        """,
        (bot_id, _cutoff_sql(cutoff)),
    ):
        order_id = str(row["order_id"] or "")
        payload = entry_payloads.get(order_id, {})
        fills = trade_counts.get(order_id, {})
        question = questions.get(str(row["condition_id"] or ""))
        buy_fills = int(fills.get("buy_fills") or 0)
        status = str(row["status"] or "")
        if buy_fills:
            outcome = "filled"
        elif status == "EXCHANGE_CLOSED":
            outcome = "exchange_closed_no_fill"
        elif status.upper() in {"OPEN", "PARTIAL", "LIVE"}:
            outcome = "open"
        else:
            outcome = "unfilled_or_pending"
        fill_price = fills.get("fill_price")
        limit_price = float(row["price"] or 0)
        out.append(
            {
                "order_id": order_id,
                "condition_id": row["condition_id"],
                "token_id": row["token_id"],
                "price": limit_price,
                "size": float(row["size"] or 0),
                "status": status,
                "placed_at": row["placed_at"],
                "outcome": outcome,
                "buy_fills": buy_fills,
                "fill_price": fill_price,
                "filled_at": fills.get("filled_at"),
                "price_improvement_cents": (
                    round((limit_price - float(fill_price)) * 100, 4)
                    if fill_price is not None
                    else None
                ),
                "price_zone": price_zone(payload.get("observed_ask_price") or limit_price),
                "setup_label": setup_label(payload),
                "fresh_t_to_res_sec": payload.get("fresh_t_to_res_sec"),
                "fresh_lead_bucket": fresh_lead_bucket(payload.get("fresh_t_to_res_sec")),
                "symbol": symbol_label(payload, question),
                "timing_ms": payload.get("timing_ms") or {},
            }
        )
    return out


def _closed_roundtrips(
    con: sqlite3.Connection,
    *,
    bot_id: str,
    cutoff: datetime,
) -> list[dict[str, Any]]:
    events = _entry_events(con, bot_id=bot_id, cutoff=cutoff)
    trades = [
        t
        for t in fetch_trades(con, bot_ids=(bot_id,))
        if (dt := _parse_dt(t.get("filled_at"))) is not None and dt >= cutoff
    ]
    order_prices = _order_price_by_id(
        con,
        bot_id=bot_id,
        order_ids={str(t.get("order_id") or "") for t in trades if t.get("order_id")},
    )
    rows = fifo_match(trades, entry_events=events, con=con)
    for row in rows:
        payload = events.get(str(row.get("order_id") or ""), {})
        order_price = order_prices.get(str(row.get("order_id") or ""))
        zone_basis = payload.get("observed_ask_price") or payload.get("limit_price")
        row["setup_price_zone"] = price_zone(zone_basis or order_price or row.get("buy_price"))
        row["setup_label"] = setup_label(payload)
    return rows


def _summarise_outcomes(rows: list[dict[str, Any]], stale: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "placed": len(rows),
        "filled": sum(1 for row in rows if row["outcome"] == "filled"),
        "exchange_closed_no_fill": sum(
            1 for row in rows if row["outcome"] == "exchange_closed_no_fill"
        ),
        "open": sum(1 for row in rows if row["outcome"] == "open"),
        "stale_rejected": len(stale),
    }
    denominator = out["placed"] + out["stale_rejected"]
    out["fill_rate_pct_of_placed"] = (
        round(out["filled"] / out["placed"] * 100, 2) if out["placed"] else None
    )
    out["fill_rate_pct_of_signal_denominator"] = (
        round(out["filled"] / denominator * 100, 2) if denominator else None
    )
    return out


def _group_counts(rows: list[dict[str, Any]], stale: list[dict[str, Any]], key: str) -> dict[str, Any]:
    labels = sorted({str(row.get(key) or "unknown") for row in [*rows, *stale]})
    return {
        label: _summarise_outcomes(
            [row for row in rows if str(row.get(key) or "unknown") == label],
            [row for row in stale if str(row.get(key) or "unknown") == label],
        )
        for label in labels
    }


def _timing_summary(rows: list[dict[str, Any]], stale: list[dict[str, Any]]) -> dict[str, Any]:
    timings: dict[str, list[float]] = defaultdict(list)
    for row in [*rows, *stale]:
        timing = row.get("timing_ms") or {}
        if not isinstance(timing, dict):
            continue
        for key, value in timing.items():
            try:
                timings[str(key)].append(float(value))
            except (TypeError, ValueError):
                continue
    return {
        key: {
            "n": len(values),
            "avg_ms": round(mean(values), 3),
            "max_ms": round(max(values), 3),
        }
        for key, values in sorted(timings.items())
        if values
    }


def _roi_by_zone(roundtrips: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for zone in ("3.5c-4c", "4c-5c", "5c-5.5c", "<3.5c", ">5.5c", "unknown"):
        rows = [
            rt
            for rt in roundtrips
            if str(rt.get("setup_price_zone") or price_zone(rt.get("buy_price"))) == zone
        ]
        if not rows:
            continue
        pnl = sum(float(rt.get("pnl_usd") or 0) for rt in rows)
        cost = sum(float(rt.get("buy_price") or 0) * float(rt.get("size") or 0) for rt in rows)
        out[zone] = {
            "closed": len(rows),
            "wins": sum(1 for rt in rows if rt.get("win")),
            "pnl_usd": round(pnl, 4),
            "cost_usd": round(cost, 4),
            "roi_pct": round(pnl / cost * 100, 2) if cost else None,
        }
    return out


def _paper_live_pairs(
    con: sqlite3.Connection,
    *,
    paper_bot_id: str,
    live_bot_id: str,
    cutoff: datetime,
) -> dict[str, Any]:
    paper = _entry_events(con, bot_id=paper_bot_id, cutoff=cutoff)
    live = _entry_events(con, bot_id=live_bot_id, cutoff=cutoff)
    live_keys = {
        (str(payload.get("condition_id") or ""), str(payload.get("token_id") or ""))
        for payload in live.values()
    }
    paper_rows = [
        payload
        for payload in paper.values()
        if price_zone(payload.get("observed_ask_price") or payload.get("price"))
        in {"3.5c-4c", "4c-5c", "5c-5.5c"}
    ]
    matched = [
        payload
        for payload in paper_rows
        if (str(payload.get("condition_id") or ""), str(payload.get("token_id") or ""))
        in live_keys
    ]
    return {
        "paper_candidate_entries": len(paper_rows),
        "live_entries": len(live),
        "paper_entries_with_matching_live_entry": len(matched),
        "paper_live_match_rate_pct": (
            round(len(matched) / len(paper_rows) * 100, 2) if paper_rows else None
        ),
    }


def build_report(
    con: sqlite3.Connection,
    *,
    cutoff: datetime,
    live_bot_id: str,
    paper_bot_id: str,
) -> dict[str, Any]:
    live_rows = _live_orders(con, bot_id=live_bot_id, cutoff=cutoff)
    stale = _stale_rejects(con, bot_id=live_bot_id, cutoff=cutoff)
    roundtrips = _closed_roundtrips(con, bot_id=live_bot_id, cutoff=cutoff)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "cutoff": cutoff.isoformat(),
        "live_bot_id": live_bot_id,
        "paper_bot_id": paper_bot_id,
        "overall": _summarise_outcomes(live_rows, stale),
        "funnel": {
            "spread_rejected": _event_count(
                con, bot_id=live_bot_id, event_type="bot_g.spread_rejected", cutoff=cutoff
            ),
            "prime_rejected": _event_count(
                con, bot_id=live_bot_id, event_type="bot_g.prime_rejected", cutoff=cutoff
            ),
            "stale_rejected": len(stale),
            "submit_failed": _event_count(
                con, bot_id=live_bot_id, event_type="bot_g.entry_place_failed", cutoff=cutoff
            ),
            "placed": len(live_rows),
            "filled": sum(1 for row in live_rows if row["outcome"] == "filled"),
            "exchange_closed_no_fill": sum(
                1 for row in live_rows if row["outcome"] == "exchange_closed_no_fill"
            ),
            "open": sum(1 for row in live_rows if row["outcome"] == "open"),
        },
        "by_price_zone": _group_counts(live_rows, stale, "price_zone"),
        "by_setup_label": _group_counts(live_rows, stale, "setup_label"),
        "by_symbol": _group_counts(live_rows, stale, "symbol"),
        "by_fresh_lead": _group_counts(live_rows, stale, "fresh_lead_bucket"),
        "timing": _timing_summary(live_rows, stale),
        "live_roi_by_price_zone": _roi_by_zone(roundtrips),
        "paper_live_pairing": _paper_live_pairs(
            con,
            paper_bot_id=paper_bot_id,
            live_bot_id=live_bot_id,
            cutoff=cutoff,
        ),
        "recent_live_orders": live_rows[-12:],
        "recent_stale_rejects": stale[-12:],
    }


def _pct_text(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.1f}%"


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Bot G Live Transfer Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Window start: `{report['cutoff']}`",
        "",
        "## Overall",
        "",
    ]
    overall = report["overall"]
    lines.extend([
        "| placed | filled | exchange-closed/no-fill | open | stale rejected | fill rate placed | fill rate denominator |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {overall['placed']} | {overall['filled']} | "
            f"{overall['exchange_closed_no_fill']} | {overall['open']} | "
            f"{overall['stale_rejected']} | "
            f"{_pct_text(overall['fill_rate_pct_of_placed'])} | "
            f"{_pct_text(overall['fill_rate_pct_of_signal_denominator'])} |"
        ),
        "",
        "## Funnel",
        "",
        "| spread rejected | prime rejected | stale rejected | submit failed | placed | filled | no-fill | open |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    funnel = report["funnel"]
    lines.extend([
        (
            f"| {funnel['spread_rejected']} | {funnel['prime_rejected']} | "
            f"{funnel['stale_rejected']} | {funnel['submit_failed']} | "
            f"{funnel['placed']} | {funnel['filled']} | "
            f"{funnel['exchange_closed_no_fill']} | {funnel['open']} |"
        ),
        "",
        "## Price Zones",
        "",
        "| zone | placed | filled | no-fill | stale | fill rate placed |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for zone, row in report["by_price_zone"].items():
        lines.append(
            f"| {zone} | {row['placed']} | {row['filled']} | "
            f"{row['exchange_closed_no_fill']} | {row['stale_rejected']} | "
            f"{_pct_text(row['fill_rate_pct_of_placed'])} |"
        )
    lines.extend(["", "## Setup Labels", "", "| label | placed | filled | no-fill | stale | fill rate placed |", "|---|---:|---:|---:|---:|---:|"])
    for label, row in report["by_setup_label"].items():
        lines.append(
            f"| {label} | {row['placed']} | {row['filled']} | "
            f"{row['exchange_closed_no_fill']} | {row['stale_rejected']} | "
            f"{_pct_text(row['fill_rate_pct_of_placed'])} |"
        )
    lines.extend(["", "## Symbols", "", "| symbol | placed | filled | no-fill | stale | fill rate placed |", "|---|---:|---:|---:|---:|---:|"])
    for symbol, row in report["by_symbol"].items():
        lines.append(
            f"| {symbol} | {row['placed']} | {row['filled']} | "
            f"{row['exchange_closed_no_fill']} | {row['stale_rejected']} | "
            f"{_pct_text(row['fill_rate_pct_of_placed'])} |"
        )
    lines.extend(["", "## Fresh Lead", "", "| lead bucket | placed | filled | no-fill | stale | fill rate placed |", "|---|---:|---:|---:|---:|---:|"])
    for bucket, row in report["by_fresh_lead"].items():
        lines.append(
            f"| {bucket} | {row['placed']} | {row['filled']} | "
            f"{row['exchange_closed_no_fill']} | {row['stale_rejected']} | "
            f"{_pct_text(row['fill_rate_pct_of_placed'])} |"
        )
    lines.extend(["", "## Live ROI By Price Zone", "", "| zone | closed | wins | pnl | cost | ROI |", "|---|---:|---:|---:|---:|---:|"])
    for zone, row in report["live_roi_by_price_zone"].items():
        lines.append(
            f"| {zone} | {row['closed']} | {row['wins']} | "
            f"${row['pnl_usd']:+.2f} | ${row['cost_usd']:.2f} | "
            f"{_pct_text(row['roi_pct'])} |"
        )
    pairing = report["paper_live_pairing"]
    lines.extend([
        "",
        "## Paper vs Live Pairing",
        "",
        f"- Paper candidate entries: `{pairing['paper_candidate_entries']}`",
        f"- Live entries: `{pairing['live_entries']}`",
        f"- Paper entries with matching live entry: `{pairing['paper_entries_with_matching_live_entry']}`",
        f"- Match rate: `{_pct_text(pairing['paper_live_match_rate_pct'])}`",
        "",
        "## Timing",
        "",
        "| checkpoint | n | avg ms | max ms |",
        "|---|---:|---:|---:|",
    ])
    if report["timing"]:
        for key, row in report["timing"].items():
            lines.append(f"| {key} | {row['n']} | {row['avg_ms']:.3f} | {row['max_ms']:.3f} |")
    else:
        lines.append("| no timing payloads yet | 0 | n/a | n/a |")
    lines.extend([
        "",
        "## Recent Live Orders",
        "",
        "| placed | zone | outcome | limit | fill | fresh lead | status |",
        "|---|---|---|---:|---:|---:|---|",
    ])
    for row in report["recent_live_orders"]:
        fill_price = row["fill_price"]
        fill_text = "n/a" if fill_price is None else f"{float(fill_price):.4f}"
        lines.append(
            f"| {row['placed_at']} | {row['price_zone']} | {row['outcome']} | "
            f"{row['price']:.4f} | {fill_text} | "
            f"{row['fresh_t_to_res_sec']} | {row['status']} |"
        )
    if not report["recent_live_orders"]:
        lines.append("| none | | | | | | |")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bot G live-transfer report.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--lookback-hours", type=float, default=24.0)
    parser.add_argument("--live-bot-id", default="bot_g_prime_live")
    parser.add_argument("--paper-bot-id", default="bot_g_prime")
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cutoff = datetime.now(UTC) - timedelta(hours=args.lookback_hours)
    con = _connect_ro(args.db)
    try:
        report = build_report(
            con,
            cutoff=cutoff,
            live_bot_id=args.live_bot_id,
            paper_bot_id=args.paper_bot_id,
        )
    finally:
        con.close()
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
