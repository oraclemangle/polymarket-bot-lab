#!/usr/bin/env python3
"""Bot G paper-vs-live divergence diagnostic.

Session 174 found that `bot_g_prime` (paper main) made `+82.5%` ROI on
flat-CEX fills while `bot_g_prime_live` (real money) lost `-66.5%` on
the same kind of fills. This script tests whether the gap is an
execution illusion (paper fills at unrealistic prices, ignores fill
latency, never times out) or a real strategic edge.

Read-only research. Reads the bot container `main.db` and `bot_e_recorder.db`.

The report computes three diagnostics:

1. **Fill-price slippage** — for each filled order: `fill_price -
   limit_price`. Live should show negative slippage (limit-order matches
   often clear at 1c floor). Paper should be zero (instant-fill at
   limit assumption).
2. **Fill latency** — for each filled order: `filled_at - placed_at`.
   Live shows real latency. Paper is near-zero.
3. **Status distribution** — paper: ~100% FILLED. Live: a mix of
   `matched`, `FILLED`, `EXCHANGE_CLOSED` (timed out unfilled),
   `CANCELED`, etc.
4. **Same-market paired outcomes** — for the 27 markets where both
   `bot_g_prime` AND `bot_g_prime_live` placed orders: did paper win
   and live lose? At what fill prices?

Outputs:
- `docs/reports/bot-g-paper-vs-live-divergence-2026-05-06-{label}.md`
- `docs/reports/bot-g-paper-vs-live-divergence-2026-05-06-{label}.json`
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

from scripts.bot_g_crypto_replay_grid import (  # noqa: E402
    connect_ro,
    iso_sql,
    load_bot_orders,
    load_entry_payloads,
    parse_dt,
    table_exists,
)

DEFAULT_MAIN_DB = Path("data/main.db")
DEFAULT_RECORDER_DB = Path("data/bot_e_recorder.db")
PAPER_BOT = "bot_g_prime"
LIVE_BOT = "bot_g_prime_live"
DEFAULT_LOOKBACK_DAYS = 30


def _num(v: object) -> float | None:
    try:
        return float(v)
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


def _fmt_int(v: Any) -> str:
    return "" if v is None else f"{int(v):,}"


def _fmt_pct(v: Any) -> str:
    return "" if v is None else f"{float(v):.2f}%"


def _fmt_price(v: Any) -> str:
    return "" if v is None else f"{float(v):.4f}"


def _fmt_str(v: Any) -> str:
    return "" if v is None else str(v)


def _fmt_money(v: Any) -> str:
    if v is None:
        return ""
    return f"${float(v):,.2f}"


def _table(rows: list[dict[str, Any]], cols: list[tuple[str, str, str]]) -> str:
    if not rows:
        return "_no rows_"
    header = "| " + " | ".join(c[1] for c in cols) + " |"
    align = "|" + "|".join("---:" if c[2] in {"int", "pct", "price", "money"} else "---" for c in cols) + "|"
    body = []
    for r in rows:
        cells = []
        for key, _, fmt in cols:
            v = r.get(key)
            if fmt == "int":
                cells.append(_fmt_int(v))
            elif fmt == "pct":
                cells.append(_fmt_pct(v))
            elif fmt == "price":
                cells.append(_fmt_price(v))
            elif fmt == "money":
                cells.append(_fmt_money(v))
            else:
                cells.append(_fmt_str(v))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, align] + body)


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    idx = int(round(q * (len(s) - 1)))
    return s[max(0, min(len(s) - 1, idx))]


def load_orders_and_trades(con: sqlite3.Connection, *, bot_id: str, since: datetime) -> list[dict[str, Any]]:
    rows = con.execute(
        """
        SELECT
            o.order_id, o.bot_id, o.condition_id, o.token_id, o.side,
            o.price AS limit_price, o.size AS order_size, o.status,
            o.placed_at, o.last_updated,
            t.price AS fill_price, t.size AS fill_size, t.fee_usd, t.filled_at
        FROM orders o
        LEFT JOIN trades t ON t.order_id = o.order_id
        WHERE o.bot_id = ? AND o.placed_at >= ?
        ORDER BY o.placed_at
        """,
        (bot_id, iso_sql(since)),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["filled"] = d.get("fill_price") is not None and d.get("fill_size") is not None
        d["limit_cost"] = (
            (_num(d["limit_price"]) or 0) * (_num(d["order_size"]) or 0)
        )
        d["actual_cost"] = (
            (_num(d["fill_price"]) or 0) * (_num(d["fill_size"]) or 0)
        )
        d["slippage_price"] = (
            None if not d["filled"]
            else (_num(d["fill_price"]) or 0) - (_num(d["limit_price"]) or 0)
        )
        d["slippage_bps"] = (
            None if not d["filled"] or _num(d["limit_price"]) in (None, 0)
            else ((_num(d["fill_price"]) or 0) - (_num(d["limit_price"]) or 0))
                 / _num(d["limit_price"]) * 10000
        )
        placed = parse_dt(d.get("placed_at"))
        filled = parse_dt(d.get("filled_at"))
        d["fill_latency_sec"] = (
            None if placed is None or filled is None
            else (filled - placed).total_seconds()
        )
        out.append(d)
    return out


def load_position_outcomes(con: sqlite3.Connection, *, bot_id: str, since: datetime) -> dict[str, dict[str, Any]]:
    """For each condition_id, how did this bot's position resolve?"""
    rows = con.execute(
        """
        SELECT
            condition_id, token_id, status,
            cost_basis_usd, opened_at, closed_at
        FROM positions
        WHERE bot_id = ?
          AND opened_at >= ?
        """,
        (bot_id, iso_sql(since)),
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        out[str(d["condition_id"])] = d
    return out


def load_pnl_by_order(
    main: sqlite3.Connection,
    recorder: sqlite3.Connection,
    *,
    bot_id: str,
    since: datetime,
) -> dict[str, dict[str, Any]]:
    """Use the existing entry-payload route to estimate per-order P&L."""
    rows = load_bot_orders(main, recorder, bot_ids=(bot_id,), cutoff=since)
    return {str(r.get("order_id") or ""): r for r in rows}


def status_distribution(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for o in orders:
        s = str(o.get("status") or "")
        counts[s] = counts.get(s, 0) + 1
    total = len(orders)
    return [
        {"status": s, "count": c, "pct": 100.0 * c / total if total else 0}
        for s, c in sorted(counts.items(), key=lambda kv: -kv[1])
    ]


def slippage_summary(orders: list[dict[str, Any]]) -> dict[str, Any]:
    filled = [o for o in orders if o.get("filled")]
    bps_values = [
        float(o["slippage_bps"]) for o in filled
        if o.get("slippage_bps") is not None
    ]
    price_diffs = [
        float(o["slippage_price"]) for o in filled
        if o.get("slippage_price") is not None
    ]
    cost_at_limit = sum(float(o["limit_cost"] or 0) for o in filled)
    cost_at_fill = sum(float(o["actual_cost"] or 0) for o in filled)
    return {
        "n_filled": len(filled),
        "n_with_slippage_bps": len(bps_values),
        "min_bps": _quantile(bps_values, 0.0),
        "p25_bps": _quantile(bps_values, 0.25),
        "median_bps": _quantile(bps_values, 0.5),
        "p75_bps": _quantile(bps_values, 0.75),
        "max_bps": _quantile(bps_values, 1.0),
        "mean_bps": (sum(bps_values) / len(bps_values)) if bps_values else None,
        "median_price_diff": _quantile(price_diffs, 0.5),
        "min_price_diff": _quantile(price_diffs, 0.0),
        "max_price_diff": _quantile(price_diffs, 1.0),
        "total_cost_at_limit": cost_at_limit,
        "total_cost_at_fill": cost_at_fill,
        "ratio_actual_to_limit": (
            (cost_at_fill / cost_at_limit) if cost_at_limit else None
        ),
    }


def latency_summary(orders: list[dict[str, Any]]) -> dict[str, Any]:
    values = [
        float(o["fill_latency_sec"]) for o in orders
        if o.get("fill_latency_sec") is not None
    ]
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min_sec": _quantile(values, 0.0),
        "p25_sec": _quantile(values, 0.25),
        "median_sec": _quantile(values, 0.5),
        "p75_sec": _quantile(values, 0.75),
        "max_sec": _quantile(values, 1.0),
        "mean_sec": sum(values) / len(values),
    }


def shared_market_pairs(
    paper_orders: list[dict[str, Any]],
    live_orders: list[dict[str, Any]],
    paper_pnl: dict[str, dict[str, Any]],
    live_pnl: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    paper_by_cond: dict[str, list[dict[str, Any]]] = {}
    for o in paper_orders:
        paper_by_cond.setdefault(str(o.get("condition_id") or ""), []).append(o)
    live_by_cond: dict[str, list[dict[str, Any]]] = {}
    for o in live_orders:
        live_by_cond.setdefault(str(o.get("condition_id") or ""), []).append(o)
    shared = sorted(set(paper_by_cond) & set(live_by_cond))
    pairs: list[dict[str, Any]] = []
    paper_wins = 0
    live_wins = 0
    both_won = 0
    both_lost = 0
    paper_only = 0
    live_only = 0
    for cond in shared:
        paper_orders_c = paper_by_cond[cond]
        live_orders_c = live_by_cond[cond]
        # Pick the first filled order from each side for comparison
        paper_filled = next((o for o in paper_orders_c if o.get("filled")), None)
        live_filled = next((o for o in live_orders_c if o.get("filled")), None)

        # P&L from positions for this condition+bot (best effort): use enriched pnl
        paper_pos = next(
            (paper_pnl[oid] for oid in [str(o["order_id"]) for o in paper_orders_c if o.get("order_id")] if oid in paper_pnl),
            {},
        )
        live_pos = next(
            (live_pnl[oid] for oid in [str(o["order_id"]) for o in live_orders_c if o.get("order_id")] if oid in live_pnl),
            {},
        )
        paper_won = bool(paper_pos.get("win")) if paper_pos else False
        live_won = bool(live_pos.get("win")) if live_pos else False
        if paper_won and live_won:
            both_won += 1
        elif paper_won and not live_won:
            paper_only += 1
            paper_wins += 1
        elif live_won and not paper_won:
            live_only += 1
            live_wins += 1
        else:
            both_lost += 1
        if paper_won:
            paper_wins += 0  # already counted above split
        pairs.append(
            {
                "condition_id": cond[:18] + "...",
                "paper_status": paper_orders_c[0].get("status"),
                "paper_limit": _num(paper_orders_c[0].get("limit_price")),
                "paper_fill": _num(paper_filled.get("fill_price")) if paper_filled else None,
                "paper_won": paper_won,
                "paper_pnl_usd": float(paper_pos.get("pnl_usd") or 0),
                "live_status": live_orders_c[0].get("status"),
                "live_limit": _num(live_orders_c[0].get("limit_price")),
                "live_fill": _num(live_filled.get("fill_price")) if live_filled else None,
                "live_won": live_won,
                "live_pnl_usd": float(live_pos.get("pnl_usd") or 0),
                "fill_price_gap": (
                    None if not paper_filled or not live_filled
                    else (_num(live_filled.get("fill_price")) or 0) - (_num(paper_filled.get("fill_price")) or 0)
                ),
            }
        )
    summary = {
        "shared_markets": len(shared),
        "both_won": both_won,
        "paper_only_won": paper_only,
        "live_only_won": live_only,
        "both_lost": both_lost,
    }
    return {"pairs": pairs, "summary": summary}


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    main_db = Path(args.main_db).resolve()
    if not main_db.exists() or main_db.stat().st_size == 0:
        raise SystemExit(f"main.db missing/empty at {main_db}; run on the bot container")
    main = connect_ro(main_db)
    recorder = connect_ro(Path(args.recorder_db).resolve()) if Path(args.recorder_db).exists() else main

    cutoff = datetime.now(UTC) - timedelta(days=args.lookback_days)
    print(f"loading orders since {cutoff.isoformat()}", flush=True)
    paper_orders = load_orders_and_trades(main, bot_id=PAPER_BOT, since=cutoff)
    live_orders = load_orders_and_trades(main, bot_id=LIVE_BOT, since=cutoff)
    print(f"loaded {len(paper_orders)} paper, {len(live_orders)} live", flush=True)

    paper_pnl = load_pnl_by_order(main, recorder, bot_id=PAPER_BOT, since=cutoff)
    live_pnl = load_pnl_by_order(main, recorder, bot_id=LIVE_BOT, since=cutoff)
    print(f"loaded pnl for {len(paper_pnl)} paper orders, {len(live_pnl)} live orders", flush=True)

    paper_status = status_distribution(paper_orders)
    live_status = status_distribution(live_orders)
    paper_slippage = slippage_summary(paper_orders)
    live_slippage = slippage_summary(live_orders)
    paper_latency = latency_summary(paper_orders)
    live_latency = latency_summary(live_orders)

    paper_summary = {
        "n_orders": len(paper_orders),
        "n_filled": sum(1 for o in paper_orders if o.get("filled")),
        "n_resolved": sum(1 for r in paper_pnl.values() if r.get("closed")),
        "n_won": sum(1 for r in paper_pnl.values() if r.get("win")),
        "total_cost_basis_usd": sum(float(r.get("buy_notional") or 0) for r in paper_pnl.values() if r.get("closed")),
        "total_pnl_usd": sum(float(r.get("pnl_usd") or 0) for r in paper_pnl.values() if r.get("closed")),
    }
    live_summary = {
        "n_orders": len(live_orders),
        "n_filled": sum(1 for o in live_orders if o.get("filled")),
        "n_resolved": sum(1 for r in live_pnl.values() if r.get("closed")),
        "n_won": sum(1 for r in live_pnl.values() if r.get("win")),
        "total_cost_basis_usd": sum(float(r.get("buy_notional") or 0) for r in live_pnl.values() if r.get("closed")),
        "total_pnl_usd": sum(float(r.get("pnl_usd") or 0) for r in live_pnl.values() if r.get("closed")),
    }
    for s in (paper_summary, live_summary):
        s["fill_rate_pct"] = (s["n_filled"] / s["n_orders"] * 100) if s["n_orders"] else None
        s["win_rate_pct"] = (s["n_won"] / s["n_resolved"] * 100) if s["n_resolved"] else None
        s["roi_pct"] = (s["total_pnl_usd"] / s["total_cost_basis_usd"] * 100) if s["total_cost_basis_usd"] else None
        ci_lo, ci_hi = _wilson(s["n_won"], s["n_resolved"])
        s["wilson_lo_pct"] = (ci_lo * 100) if ci_lo is not None else None
        s["wilson_hi_pct"] = (ci_hi * 100) if ci_hi is not None else None

    pairs = shared_market_pairs(paper_orders, live_orders, paper_pnl, live_pnl)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "main_db": str(main_db),
        "lookback_days": args.lookback_days,
        "paper_bot_id": PAPER_BOT,
        "live_bot_id": LIVE_BOT,
        "paper_summary": paper_summary,
        "live_summary": live_summary,
        "paper_status_distribution": paper_status,
        "live_status_distribution": live_status,
        "paper_slippage": paper_slippage,
        "live_slippage": live_slippage,
        "paper_latency": paper_latency,
        "live_latency": live_latency,
        "shared_markets": pairs,
    }


def render_md(d: dict[str, Any]) -> str:
    L: list[str] = []
    L.append("# Bot G Paper-vs-Live Divergence Diagnostic")
    L.append("")
    L.append(f"Generated: `{d['generated_at']}`")
    L.append(f"Main DB: `{d['main_db']}`")
    L.append(f"Lookback: `{d['lookback_days']}` days")
    L.append(f"Paper bot: `{d['paper_bot_id']}` Live bot: `{d['live_bot_id']}`")
    L.append("")
    L.append("## Read this first")
    L.append("")
    L.append("Read-only research. Tests whether Session 174's paper-vs-live ROI gap is an execution illusion (paper fills at unrealistic prices, ignores fill latency, never times out) or a real strategic edge.")
    L.append("")
    L.append("Per OQ-081 audit: this report does not authorize any Bot G config, paper, live, cap, wallet, fresh-clock, order-path, or service change.")
    L.append("")
    L.append("## Executive comparison")
    L.append("")
    p, lv = d["paper_summary"], d["live_summary"]
    L.append(_table([
        {"bot": "paper", **p},
        {"bot": "live", **lv},
    ], [
        ("bot", "bot", "str"),
        ("n_orders", "orders", "int"),
        ("n_filled", "filled", "int"),
        ("fill_rate_pct", "fill rate", "pct"),
        ("n_resolved", "resolved", "int"),
        ("n_won", "won", "int"),
        ("win_rate_pct", "win %", "pct"),
        ("wilson_lo_pct", "wilson lo", "pct"),
        ("wilson_hi_pct", "wilson hi", "pct"),
        ("total_cost_basis_usd", "cost basis", "money"),
        ("total_pnl_usd", "pnl", "money"),
        ("roi_pct", "roi", "pct"),
    ]))
    L.append("")

    L.append("## Order status distribution")
    L.append("")
    L.append("**Paper:**")
    L.append("")
    L.append(_table(d["paper_status_distribution"], [
        ("status", "status", "str"),
        ("count", "count", "int"),
        ("pct", "pct", "pct"),
    ]))
    L.append("")
    L.append("**Live:**")
    L.append("")
    L.append(_table(d["live_status_distribution"], [
        ("status", "status", "str"),
        ("count", "count", "int"),
        ("pct", "pct", "pct"),
    ]))
    L.append("")

    L.append("## Fill-price slippage")
    L.append("")
    L.append("Slippage = `fill_price - limit_price`. Negative = filled at lower (better) price than the limit. Paper SHOULD be `0` because paper-fills happen at the limit price by assumption. Live: any negative slippage suggests MMs only filling at adverse prices.")
    L.append("")
    pp, lp = d["paper_slippage"], d["live_slippage"]
    L.append(_table([
        {"bot": "paper", **pp},
        {"bot": "live", **lp},
    ], [
        ("bot", "bot", "str"),
        ("n_filled", "filled", "int"),
        ("median_bps", "median bps", "price"),
        ("p25_bps", "p25 bps", "price"),
        ("p75_bps", "p75 bps", "price"),
        ("min_bps", "min bps", "price"),
        ("max_bps", "max bps", "price"),
        ("median_price_diff", "median Δprice", "price"),
        ("total_cost_at_limit", "cost @ limit", "money"),
        ("total_cost_at_fill", "cost @ fill", "money"),
        ("ratio_actual_to_limit", "actual/limit", "price"),
    ]))
    L.append("")
    pratio = pp.get("ratio_actual_to_limit")
    lratio = lp.get("ratio_actual_to_limit")
    if pratio is not None and lratio is not None:
        L.append(f"**Read:** Paper paid `{pratio:.4f}x` of limit-price-implied cost. Live paid `{lratio:.4f}x`. If live ratio is materially below `1.0`, live is consistently filling at MM-floor prices — adverse selection.")
    L.append("")

    L.append("## Fill latency")
    L.append("")
    L.append("Time from `placed_at` to `filled_at`. Paper should be near zero (instant paper-fill). Live shows real exchange latency.")
    L.append("")
    pl, ll = d["paper_latency"], d["live_latency"]
    L.append(_table([
        {"bot": "paper", **pl},
        {"bot": "live", **ll},
    ], [
        ("bot", "bot", "str"),
        ("n", "n", "int"),
        ("min_sec", "min s", "price"),
        ("p25_sec", "p25 s", "price"),
        ("median_sec", "median s", "price"),
        ("p75_sec", "p75 s", "price"),
        ("max_sec", "max s", "price"),
        ("mean_sec", "mean s", "price"),
    ]))
    L.append("")

    L.append("## Same-market paired outcomes")
    L.append("")
    L.append("Markets where both `bot_g_prime` (paper) AND `bot_g_prime_live` (live) placed an order. The fairest head-to-head comparison.")
    L.append("")
    sm = d["shared_markets"]["summary"]
    L.append(f"- Shared markets: `{sm['shared_markets']}`")
    L.append(f"- Both won: `{sm['both_won']}`")
    L.append(f"- Paper-only won: `{sm['paper_only_won']}`")
    L.append(f"- Live-only won: `{sm['live_only_won']}`")
    L.append(f"- Both lost: `{sm['both_lost']}`")
    L.append("")
    pairs = d["shared_markets"]["pairs"]
    L.append(_table(pairs, [
        ("condition_id", "market", "str"),
        ("paper_status", "p status", "str"),
        ("paper_limit", "p limit", "price"),
        ("paper_fill", "p fill", "price"),
        ("paper_won", "p won", "str"),
        ("paper_pnl_usd", "p pnl", "money"),
        ("live_status", "l status", "str"),
        ("live_limit", "l limit", "price"),
        ("live_fill", "l fill", "price"),
        ("live_won", "l won", "str"),
        ("live_pnl_usd", "l pnl", "money"),
        ("fill_price_gap", "Δfill (l-p)", "price"),
    ]))
    L.append("")

    L.append("## Interpretation")
    L.append("")
    L.append("If the report shows:")
    L.append("")
    L.append("- Paper has near-100% fill rate but live has many `EXCHANGE_CLOSED` (timed out without fill) — paper is in fantasy-land.")
    L.append("- Live median slippage is materially negative (e.g. `-3000 bps`) — live fills are clearing at the price-floor because that's what MMs accept. Adverse selection.")
    L.append("- Live `actual/limit` ratio is much less than `1.0` — live cost basis is far below paper's cost basis on the same orders. The paper bot's reported ROI is on a fictitious cost basis.")
    L.append("- In shared markets: paper-only wins materially exceed live-only wins — paper-fill assumption is generating wins that don't survive real execution.")
    L.append("")
    L.append("Then the conclusion is: **`bot_g_prime` paper is not a meaningful research signal.** Its `+82.5%` ROI is an execution illusion. The live bot's `-66.5%` flat-CEX ROI is the more honest read on Bot G's edge.")
    L.append("")
    L.append("This would mean: stop relying on paper-main's positive ROI as evidence. The live bot's near-flat performance is the actual baseline, and the question becomes whether *any* design change can lift live to positive — which Sessions 173 + 174 already suggest is hard.")
    L.append("")
    L.append("If the report shows the opposite (paper and live look similar in execution metrics), then the divergence is genuinely strategic and we have a different problem to solve.")
    return "\n".join(L) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main-db", default=str(DEFAULT_MAIN_DB))
    p.add_argument("--recorder-db", default=str(DEFAULT_RECORDER_DB))
    p.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    p.add_argument("--out-md", default="docs/reports/bot-g-paper-vs-live-divergence-2026-05-06.md")
    p.add_argument("--out-json", default="docs/reports/bot-g-paper-vs-live-divergence-2026-05-06.json")
    p.add_argument("--label", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    if args.label:
        out_md = out_md.with_stem(out_md.stem + "-" + args.label)
        out_json = out_json.with_stem(out_json.stem + "-" + args.label)
    if not out_md.is_absolute():
        out_md = REPO_ROOT / out_md
    if not out_json.is_absolute():
        out_json = REPO_ROOT / out_json
    data = build_report(args)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_md(data), encoding="utf-8")
    out_json.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out_md}")
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
