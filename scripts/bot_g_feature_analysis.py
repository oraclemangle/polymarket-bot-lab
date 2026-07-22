"""Task 2 — Bot G winner-feature analysis.

Objective: identify which features separate winning longshot-fade entries
from losing ones, so we can build a filter that concentrates the edge.

Data source: main.db trades joined with markets for context. FIFO-matched
per token_id to attribute SELL → BUY → outcome cleanly.
Defaults to the archived raw cohorts plus Bot G Prime; override with
BOT_G_FEATURE_BOT_IDS=bot_g_prime if you want the current service only.

Outputs:
  - Per-bucket WR and ROI tables (entry_price, symbol, hour_of_day)
  - JSON dump to /tmp/bot_g_feature_analysis.json
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from core.fees import taker_fee_per_share

DB = "data/main.db"
CAPACITY_TARGETS_USD = (25.0, 50.0)
CAPACITY_TICK_SIZE = 0.01
BOT_G_GATE_MIN_4C_5C_CLOSED = 20
BOT_G_GATE_MIN_25_AT_LIMIT_COVERAGE_PCT = 50.0
BOT_G_GATE_MIN_50_AT_PLUS2_COVERAGE_PCT = 25.0
BOT_G_LIVE_TRANSFER_EXAMPLES = 5


def _bot_ids() -> list[str]:
    raw = os.environ.get(
        "BOT_G_FEATURE_BOT_IDS",
        "bot_g,bot_g_jackpot,bot_g_scalp,bot_g_prime",
    )
    return [x.strip() for x in raw.split(",") if x.strip()]


def _output_path() -> Path:
    raw = os.environ.get("BOT_G_FEATURE_OUTPUT", "/tmp/bot_g_feature_analysis.json")
    path = Path(raw)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    except PermissionError:
        fallback = Path.cwd() / "data" / "bot_g_feature_analysis.json"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


def fetch_trades(
    con: sqlite3.Connection,
    bot_ids: list[str] | tuple[str, ...] | None = None,
) -> list[dict]:
    bot_ids = list(bot_ids or _bot_ids())
    placeholders = ",".join("?" for _ in bot_ids)
    rows = con.execute(
        f"""
        SELECT
            t.trade_id, t.bot_id, t.token_id, t.side, t.price, t.size,
            t.fee_usd, t.filled_at, t.order_id, t.condition_id,
            m.question, m.category
        FROM trades t
        LEFT JOIN markets m ON m.condition_id = t.condition_id
        WHERE t.bot_id IN ({placeholders})
        ORDER BY t.filled_at
        """,
        bot_ids,
    ).fetchall()
    return [
        dict(
            trade_id=r[0], bot_id=r[1], token_id=r[2], side=r[3],
            price=Decimal(str(r[4] or 0)), size=Decimal(str(r[5] or 0)),
            fee_usd=Decimal(str(r[6] or 0)), filled_at=r[7],
            order_id=r[8] or "", condition_id=r[9] or "",
            question=r[10] or "", category=r[11] or "",
        )
        for r in rows
    ]


def fetch_entry_events(con: sqlite3.Connection) -> dict[str, dict]:
    """Return order_id -> bot_g.entry_placed payload."""
    rows = con.execute(
        """
        SELECT payload
        FROM events
        WHERE bot_id IN ('bot_g_prime', 'bot_g', 'bot_g_jackpot', 'bot_g_scalp')
          AND event_type = 'bot_g.entry_placed'
          AND payload IS NOT NULL
        ORDER BY created_at
        """
    ).fetchall()
    out: dict[str, dict] = {}
    for (raw,) in rows:
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            continue
        oid = str(payload.get("order_id") or "")
        if oid:
            out[oid] = payload
    return out


def _loads_levels(raw: str | None) -> list[tuple[float, float]]:
    if not raw:
        return []
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out: list[tuple[float, float]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        try:
            if isinstance(row, dict):
                price = float(row.get("price"))
                size = float(row.get("size") or row.get("amount") or row.get("quantity"))
            else:
                price = float(row[0])
                size = float(row[1])
        except (TypeError, ValueError, IndexError):
            continue
        if price >= 0 and size > 0:
            out.append((price, size))
    return out


def _depth_by_tick(levels: list[tuple[float, float]], limit_price: float) -> list[dict]:
    out: list[dict] = []
    for ticks in range(3):
        max_price = limit_price + (ticks * CAPACITY_TICK_SIZE)
        eligible = [(price, size) for price, size in levels if price <= max_price + 1e-12]
        shares = sum(size for _price, size in eligible)
        notional = sum(price * size for price, size in eligible)
        out.append(
            {
                "ticks_above_limit": ticks,
                "max_price": round(max_price, 4),
                "shares": round(shares, 8),
                "notional_usd": round(notional, 4),
                "targets": {
                    str(int(t)): notional >= t - 1e-9
                    for t in CAPACITY_TARGETS_USD
                },
            }
        )
    return out


def book_capacity_at_entry(
    con: sqlite3.Connection,
    token_id: str,
    filled_at: str,
    limit_price: float,
) -> dict:
    """Estimate buy-side capacity from the nearest book snapshot at entry.

    Uses ask depth priced at or below the recorded entry limit. This is a
    conservative paper-capacity check for "could $25/$50 have filled without
    walking beyond the bot's intended price?"
    """
    try:
        row = con.execute(
            """
            SELECT asks, snapshot_at
            FROM books
            WHERE token_id = ?
              AND snapshot_at <= ?
            ORDER BY snapshot_at DESC
            LIMIT 1
            """,
            (token_id, filled_at),
        ).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is None:
        try:
            row = con.execute(
                """
                SELECT asks, snapshot_at
                FROM books
                WHERE token_id = ?
                  AND snapshot_at > ?
                ORDER BY snapshot_at
                LIMIT 1
                """,
                (token_id, filled_at),
            ).fetchone()
        except sqlite3.OperationalError:
            row = None
    if row is None:
        return {
            "snapshot_at": None,
            "shares_at_or_better": 0.0,
            "notional_at_limit": 0.0,
            "targets": {str(int(t)): False for t in CAPACITY_TARGETS_USD},
            "depth_by_tick": _depth_by_tick([], limit_price),
        }
    levels = _loads_levels(row[0])
    depth_by_tick = _depth_by_tick(levels, limit_price)
    at_limit = depth_by_tick[0]
    return {
        "snapshot_at": row[1],
        "shares_at_or_better": at_limit["shares"],
        "notional_at_limit": at_limit["notional_usd"],
        "targets": at_limit["targets"],
        "depth_by_tick": depth_by_tick,
    }


def capacity_label(capacity: dict | None, target_usd: int) -> str:
    """Classify recorded entry depth for a target notional.

    Observational only: used by reports to learn whether edge survives outside
    toy paper fills. It does not affect order placement.
    """
    depths = (capacity or {}).get("depth_by_tick") or []
    target_key = str(int(target_usd))
    labels = ("sizeable_at_limit", "sizeable_at_plus1", "sizeable_at_plus2")
    for tick, label in enumerate(labels):
        if tick < len(depths) and (depths[tick].get("targets") or {}).get(target_key):
            return label
    return "toy_fill_only"


def depletion_label(depletion_ratio: float | None) -> str:
    if depletion_ratio is None:
        return "unknown"
    if depletion_ratio > 1.1:
        return "refilled"
    return "depleted_or_slight_drop"


def extract_symbol(question: str) -> str:
    q = (question or "").upper()
    if "BTC" in q or "BITCOIN" in q:
        return "BTC"
    if "ETH" in q or "ETHEREUM" in q:
        return "ETH"
    if "SOL" in q or "SOLANA" in q:
        return "SOL"
    if "XRP" in q or "RIPPLE" in q:
        return "XRP"
    if "DOGE" in q or "DOGECOIN" in q:
        return "DOGE"
    return "OTHER"


def symbol_from_event_or_question(event: dict | None, question: str) -> str:
    if event:
        cex = event.get("cex") or {}
        raw = str(cex.get("symbol") or "").upper()
        for sym in ("BTC", "ETH", "SOL", "XRP", "DOGE"):
            if raw.startswith(sym):
                return sym
    return extract_symbol(question)


def fifo_match(
    trades: list[dict],
    *,
    entry_events: dict[str, dict] | None = None,
    con: sqlite3.Connection | None = None,
) -> list[dict]:
    """Match each SELL to the oldest BUY on the same token_id.

    Returns a list of closed round-trip records with outcome labels.
    """
    buys_by_bot_token: dict[tuple[str, str], list[dict]] = defaultdict(list)
    closed: list[dict] = []
    for t in trades:
        side = (t["side"] or "").upper()
        key = (t["bot_id"], t["token_id"])
        if side.startswith("BUY"):
            event = (entry_events or {}).get(str(t.get("order_id") or ""))
            buy_price = t["price"]
            size = t["size"]
            capacity = (
                book_capacity_at_entry(
                    con,
                    str(t["token_id"]),
                    str(t["filled_at"]),
                    float(buy_price),
                )
                if con is not None
                else {}
            )
            buys_by_bot_token[key].append({
                "bot_id": t["bot_id"],
                "buy_price": buy_price,
                "remaining": size,
                "filled_at": t["filled_at"],
                "question": t["question"],
                "order_id": t["order_id"],
                "condition_id": t["condition_id"],
                "token_id": t["token_id"],
                "event": event,
                "symbol": symbol_from_event_or_question(event, t["question"]),
                "cex_confirmed": (
                    bool((event.get("cex") or {}).get("confirmed"))
                    if event else None
                ),
                "cex_move_bps": (
                    float((event.get("cex") or {}).get("move_bps"))
                    if event and (event.get("cex") or {}).get("move_bps") is not None
                    else None
                ),
                "depletion_ratio": (
                    float((event.get("depletion") or {}).get("depletion_ratio"))
                    if event and (event.get("depletion") or {}).get("depletion_ratio") is not None
                    else None
                ),
                "capacity": capacity,
            })
        elif side.startswith("SELL"):
            sell_px = t["price"]
            sell_size = t["size"]
            remaining = sell_size
            lots = buys_by_bot_token.get(key, [])
            while remaining > 0 and lots:
                lot = lots[0]
                match_size = min(remaining, lot["remaining"])
                pnl = (sell_px - lot["buy_price"]) * match_size
                entry_fee = taker_fee_per_share(lot["buy_price"], "crypto") * match_size
                exit_fee = taker_fee_per_share(sell_px, "crypto") * match_size
                closed.append({
                    "bot_id": lot["bot_id"],
                    "buy_price": float(lot["buy_price"]),
                    "sell_price": float(sell_px),
                    "size": float(match_size),
                    "pnl_usd": float(pnl),
                    "pnl_entry_taker_exit_maker": float(pnl - entry_fee),
                    "pnl_entry_maker_exit_taker": float(pnl - exit_fee),
                    "pnl_both_taker": float(pnl - entry_fee - exit_fee),
                    "entry_taker_fee_usd": float(entry_fee),
                    "exit_taker_fee_usd": float(exit_fee),
                    "win": sell_px > lot["buy_price"],
                    "buy_filled_at": lot["filled_at"],
                    "sell_filled_at": t["filled_at"],
                    "question": lot["question"],
                    "order_id": lot["order_id"],
                    "condition_id": lot["condition_id"],
                    "token_id": lot["token_id"],
                    "symbol": lot["symbol"],
                    "cex_confirmed": lot["cex_confirmed"],
                    "cex_move_bps": lot["cex_move_bps"],
                    "depletion_ratio": lot["depletion_ratio"],
                    "capacity": lot["capacity"],
                })
                lot["remaining"] -= match_size
                remaining -= match_size
                capacity_label_25 = capacity_label(lot["capacity"], 25)
                capacity_label_50 = capacity_label(lot["capacity"], 50)
                reload_label = depletion_label(lot["depletion_ratio"])
                closed[-1]["capacity_label_25"] = capacity_label_25
                closed[-1]["capacity_label_50"] = capacity_label_50
                closed[-1]["capacity_label"] = capacity_label_25
                closed[-1]["depletion_label"] = reload_label
                if lot["remaining"] <= 0:
                    lots.pop(0)
    return closed


def bucket_entry_price(p: float) -> str:
    if p <= 0.01:
        return "01:<=0.01"
    if p <= 0.02:
        return "02:0.01-0.02"
    if p <= 0.03:
        return "03:0.02-0.03"
    if p <= 0.05:
        return "04:0.03-0.05"
    if p <= 0.08:
        return "05:0.05-0.08"
    return "06:>0.08"


def bucket_entry_price_exact(p: float) -> str:
    if p < 0.03:
        return "01:<0.03"
    if p < 0.04:
        return "02:0.03-0.04"
    if p <= 0.05:
        return "03:0.04-0.05"
    if p <= 0.08:
        return "04:0.05-0.08"
    return "05:>0.08"


def hour_of_day(iso_str: str) -> int:
    if not iso_str:
        return -1
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.hour
    except Exception:
        return -1


def summarise(closed: list[dict], key_fn, title: str) -> str:
    groups: dict = defaultdict(lambda: {"n": 0, "wins": 0, "pnl": 0.0, "cost": 0.0})
    for rt in closed:
        k = key_fn(rt)
        g = groups[k]
        g["n"] += 1
        g["wins"] += 1 if rt["win"] else 0
        g["pnl"] += rt["pnl_usd"]
        g["cost"] += rt["buy_price"] * rt["size"]
    lines = [f"\n### {title}\n"]
    lines.append(f"| {'key':<16} | n | wins | WR    | pnl       | cost     | ROI     |")
    lines.append(f"|{'-'*18}|---|------|-------|-----------|----------|---------|")
    for k in sorted(groups.keys()):
        g = groups[k]
        wr = (g["wins"] / g["n"] * 100) if g["n"] else 0
        roi = (g["pnl"] / g["cost"] * 100) if g["cost"] else 0
        lines.append(
            f"| {k!s:<16} | {g['n']:>1} | {g['wins']:>4} | "
            f"{wr:>5.1f}% | ${g['pnl']:>+8.2f} | ${g['cost']:>7.2f} | "
            f"{roi:>+6.1f}% |"
        )
    return "\n".join(lines)


def summarise_fee_stress(closed: list[dict]) -> str:
    cases = [
        ("maker_entry_maker_exit", "pnl_usd"),
        ("taker_entry_maker_exit", "pnl_entry_taker_exit_maker"),
        ("maker_entry_taker_exit", "pnl_entry_maker_exit_taker"),
        ("taker_entry_taker_exit", "pnl_both_taker"),
    ]
    lines = ["\n### V2 crypto fee stress\n"]
    lines.append("| case | pnl | cost | ROI |")
    lines.append("|---|---:|---:|---:|")
    cost = sum(float(rt["buy_price"]) * float(rt["size"]) for rt in closed)
    for label, key in cases:
        pnl = sum(float(rt.get(key) or 0) for rt in closed)
        roi = pnl / cost * 100 if cost else 0.0
        lines.append(f"| {label} | ${pnl:+.2f} | ${cost:.2f} | {roi:+.1f}% |")
    return "\n".join(lines)


def summarise_capacity(closed: list[dict]) -> str:
    lines = ["\n### Entry book capacity\n"]
    lines.append("| target | at limit | limit+1c | limit+2c | total |")
    lines.append("|---|---:|---:|---:|---:|")
    total = len(closed)
    for target in CAPACITY_TARGETS_USD:
        key = str(int(target))
        counts = []
        for tick in range(3):
            covered = 0
            for rt in closed:
                depths = (rt.get("capacity") or {}).get("depth_by_tick") or []
                if tick < len(depths) and (depths[tick].get("targets") or {}).get(key):
                    covered += 1
            pct = covered / total * 100 if total else 0.0
            counts.append(f"{covered} ({pct:.1f}%)")
        lines.append(f"| ${int(target)} | {counts[0]} | {counts[1]} | {counts[2]} | {total} |")
    avg_depth = []
    for tick in range(3):
        values = []
        for rt in closed:
            depths = (rt.get("capacity") or {}).get("depth_by_tick") or []
            if tick < len(depths):
                values.append(float(depths[tick].get("notional_usd") or 0))
        avg_depth.append(sum(values) / len(values) if values else 0.0)
    lines.extend([
        "",
        "| depth | average notional |",
        "|---|---:|",
        f"| entry limit | ${avg_depth[0]:.2f} |",
        f"| limit+1c | ${avg_depth[1]:.2f} |",
        f"| limit+2c | ${avg_depth[2]:.2f} |",
    ])
    return "\n".join(lines)


def outlier_adjusted_summary(closed: list[dict]) -> dict:
    total_pnl = sum(float(rt["pnl_usd"]) for rt in closed)
    total_cost = sum(float(rt["buy_price"]) * float(rt["size"]) for rt in closed)
    wins = sorted(
        (rt for rt in closed if float(rt["pnl_usd"]) > 0),
        key=lambda rt: float(rt["pnl_usd"]),
        reverse=True,
    )

    def without_top_wins(n: int) -> dict:
        removed = set(id(rt) for rt in wins[:n])
        kept = [rt for rt in closed if id(rt) not in removed]
        pnl = sum(float(rt["pnl_usd"]) for rt in kept)
        cost = sum(float(rt["buy_price"]) * float(rt["size"]) for rt in kept)
        return {
            "n": len(kept),
            "pnl": round(pnl, 4),
            "cost": round(cost, 4),
            "roi_pct": round(pnl / cost * 100, 2) if cost else None,
        }

    largest_win = float(wins[0]["pnl_usd"]) if wins else 0.0
    return {
        "all": {
            "n": len(closed),
            "pnl": round(total_pnl, 4),
            "cost": round(total_cost, 4),
            "roi_pct": round(total_pnl / total_cost * 100, 2) if total_cost else None,
        },
        "largest_win_pnl": round(largest_win, 4),
        "largest_win_share_of_profit": (
            round(largest_win / total_pnl, 4) if total_pnl > 0 and largest_win > 0 else None
        ),
        "ex_largest_win": without_top_wins(1),
        "ex_largest_two_wins": without_top_wins(2),
    }


def _roi_summary(rows: list[dict]) -> dict:
    pnl = sum(float(rt["pnl_usd"]) for rt in rows)
    cost = sum(float(rt["buy_price"]) * float(rt["size"]) for rt in rows)
    return {
        "closed": len(rows),
        "wins": sum(1 for rt in rows if rt["win"]),
        "pnl": round(pnl, 4),
        "cost": round(cost, 4),
        "roi_pct": round(pnl / cost * 100, 2) if cost else None,
        "outlier_adjusted": outlier_adjusted_summary(rows),
    }


def _capacity_summary(rows: list[dict]) -> dict:
    total = len(rows)
    by_target: dict[str, dict[str, dict[str, float | int]]] = {}
    for target in CAPACITY_TARGETS_USD:
        target_key = str(int(target))
        by_tick: dict[str, dict[str, float | int]] = {}
        for tick in range(3):
            covered = 0
            for rt in rows:
                depths = (rt.get("capacity") or {}).get("depth_by_tick") or []
                if tick < len(depths) and (depths[tick].get("targets") or {}).get(target_key):
                    covered += 1
            by_tick[str(tick)] = {
                "covered": covered,
                "total": total,
                "coverage_pct": round(covered / total * 100, 2) if total else 0.0,
            }
        by_target[target_key] = by_tick
    average_depth_by_tick: dict[str, float] = {}
    for tick in range(3):
        values = []
        for rt in rows:
            depths = (rt.get("capacity") or {}).get("depth_by_tick") or []
            if tick < len(depths):
                values.append(float(depths[tick].get("notional_usd") or 0))
        average_depth_by_tick[str(tick)] = round(sum(values) / len(values), 4) if values else 0.0
    return {
        "targets_usd": by_target,
        "average_depth_notional_by_tick": average_depth_by_tick,
    }


def _capacity_coverage(capacity: dict, target_usd: int, tick: int) -> float:
    target = ((capacity.get("targets_usd") or {}).get(str(target_usd)) or {})
    row = target.get(str(tick)) or {}
    return float(row.get("coverage_pct") or 0.0)


def capacity_policy_summary(split: dict) -> dict:
    """Summarise whether recorded depth supports $25/$50 execution sizes."""
    capacity = split.get("capacity") or {}
    avg_depth = capacity.get("average_depth_notional_by_tick") or {}
    targets = {}
    for target in (25, 50):
        coverages = {
            "at_limit": _capacity_coverage(capacity, target, 0),
            "limit_plus_1c": _capacity_coverage(capacity, target, 1),
            "limit_plus_2c": _capacity_coverage(capacity, target, 2),
        }
        minimum_required_tick = None
        for tick, label in ((0, "at_limit"), (1, "limit_plus_1c"), (2, "limit_plus_2c")):
            if _capacity_coverage(capacity, target, tick) > 0:
                minimum_required_tick = label
                break
        targets[str(target)] = {
            **coverages,
            "minimum_required_tick": minimum_required_tick,
        }
    return {
        "sample": int(split.get("closed") or 0),
        "targets_usd": targets,
        "average_depth_notional": {
            "at_limit": float(avg_depth.get("0") or 0.0),
            "limit_plus_1c": float(avg_depth.get("1") or 0.0),
            "limit_plus_2c": float(avg_depth.get("2") or 0.0),
        },
        "thresholds": {
            "min_25_at_limit_coverage_pct": BOT_G_GATE_MIN_25_AT_LIMIT_COVERAGE_PCT,
            "min_50_at_plus2_coverage_pct": BOT_G_GATE_MIN_50_AT_PLUS2_COVERAGE_PCT,
        },
    }


def live_candidate_gate(splits: dict[str, dict]) -> dict:
    """Turn Bot G validation evidence into an operator-facing gate status.

    This is a reporting gate only. It does not change Bot G order placement,
    sizing, bankroll, live mode, or wallet settings.
    """
    core = splits.get("4c_5c") or {}
    outliers = core.get("outlier_adjusted") or {}
    ex1_roi = (outliers.get("ex_largest_win") or {}).get("roi_pct")
    ex2_roi = (outliers.get("ex_largest_two_wins") or {}).get("roi_pct")
    capacity_policy = capacity_policy_summary(core)
    cap25 = (capacity_policy["targets_usd"].get("25") or {}).get("at_limit", 0.0)
    cap50 = (capacity_policy["targets_usd"].get("50") or {}).get("limit_plus_2c", 0.0)

    checks = {
        "min_4c_5c_closed": {
            "pass": int(core.get("closed") or 0) >= BOT_G_GATE_MIN_4C_5C_CLOSED,
            "value": int(core.get("closed") or 0),
            "threshold": BOT_G_GATE_MIN_4C_5C_CLOSED,
        },
        "ex_largest_win_roi_positive": {
            "pass": ex1_roi is not None and float(ex1_roi) > 0,
            "value": ex1_roi,
            "threshold": 0,
        },
        "ex_largest_two_roi_positive": {
            "pass": ex2_roi is not None and float(ex2_roi) > 0,
            "value": ex2_roi,
            "threshold": 0,
        },
        "capacity_25_at_limit": {
            "pass": cap25 >= BOT_G_GATE_MIN_25_AT_LIMIT_COVERAGE_PCT,
            "value": round(cap25, 2),
            "threshold": BOT_G_GATE_MIN_25_AT_LIMIT_COVERAGE_PCT,
        },
        "capacity_50_at_limit_plus_2c": {
            "pass": cap50 >= BOT_G_GATE_MIN_50_AT_PLUS2_COVERAGE_PCT,
            "value": round(cap50, 2),
            "threshold": BOT_G_GATE_MIN_50_AT_PLUS2_COVERAGE_PCT,
        },
    }
    reasons = [
        name
        for name, check in checks.items()
        if not check["pass"]
    ]
    if not checks["ex_largest_win_roi_positive"]["pass"] or not checks["ex_largest_two_roi_positive"]["pass"]:
        status = "blocked_by_trimmed_roi"
    elif not checks["capacity_25_at_limit"]["pass"] or not checks["capacity_50_at_limit_plus_2c"]["pass"]:
        status = "blocked_by_capacity"
    elif not checks["min_4c_5c_closed"]["pass"]:
        status = "collecting_sample"
    else:
        status = "candidate"
    return {
        "status": status,
        "live_ready": status == "candidate",
        "reasons": reasons,
        "checks": checks,
        "capacity_policy": capacity_policy,
        "rule": (
            "Candidate only when 4c-5c has >=20 closed trades, ex-largest-win "
            "and ex-largest-two ROI are positive, $25 at-limit coverage is "
            ">=50%, and $50 limit+2c coverage is >=25%."
        ),
    }


def _cex_summary(rows: list[dict]) -> dict:
    return {
        label: _roi_summary([
            rt for rt in rows
            if (
                (label == "confirmed" and rt.get("cex_confirmed") is True)
                or (label == "unconfirmed" and rt.get("cex_confirmed") is False)
                or (label == "unknown" and rt.get("cex_confirmed") is None)
            )
        ])
        for label in ("confirmed", "unconfirmed", "unknown")
    }


def _label_summary(rows: list[dict], key: str) -> dict:
    labels = sorted({str(rt.get(key) or "unknown") for rt in rows})
    return {
        label: _roi_summary([rt for rt in rows if str(rt.get(key) or "unknown") == label])
        for label in labels
    }


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator * 100, 2)


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in con.execute(f"PRAGMA table_info({table})")}
    except sqlite3.OperationalError:
        return set()


def _depth_notional(rt: dict, tick: int) -> float:
    depths = (rt.get("capacity") or {}).get("depth_by_tick") or []
    if tick >= len(depths):
        return 0.0
    return float(depths[tick].get("notional_usd") or 0.0)


def _matching_live_orders(
    con: sqlite3.Connection,
    rt: dict,
    *,
    live_bot_id: str,
) -> list[dict]:
    cols = _table_columns(con, "orders")
    required = {"bot_id", "condition_id", "token_id", "price", "order_id", "status", "placed_at"}
    if not required.issubset(cols):
        return []
    condition_id = str(rt.get("condition_id") or "")
    token_id = str(rt.get("token_id") or "")
    if not condition_id or not token_id:
        return []
    return [
        {
            "order_id": row[0],
            "status": row[1],
            "price": row[2],
            "size": row[3],
            "placed_at": row[4],
        }
        for row in con.execute(
            """
            SELECT order_id, status, price, size, placed_at
            FROM orders
            WHERE bot_id = ?
              AND condition_id = ?
              AND token_id = ?
              AND ABS(COALESCE(price, 0) - ?) < 0.000001
            ORDER BY placed_at
            """,
            (live_bot_id, condition_id, token_id, float(rt["buy_price"])),
        )
    ]


def _live_trade_count_for_orders(
    con: sqlite3.Connection,
    order_ids: list[str],
    *,
    live_bot_id: str,
) -> int:
    if not order_ids:
        return 0
    cols = _table_columns(con, "trades")
    required = {"bot_id", "order_id"}
    if not required.issubset(cols):
        return 0
    placeholders = ",".join("?" for _ in order_ids)
    row = con.execute(
        f"""
        SELECT COUNT(*)
        FROM trades
        WHERE bot_id = ?
          AND order_id IN ({placeholders})
        """,
        [live_bot_id, *order_ids],
    ).fetchone()
    return int(row[0] if row else 0)


def live_transfer_summary(
    con: sqlite3.Connection | None,
    closed: list[dict],
    *,
    paper_bot_id: str = "bot_g_prime",
    live_bot_id: str = "bot_g_prime_live",
) -> dict:
    """Compare paper 4c-5c wins with the separate live Prime ledger.

    This is reporting only. It answers whether paper wins were mechanically
    transferable into real fills, which is distinct from paper ROI.
    """
    rows = [
        rt for rt in closed
        if rt.get("bot_id") == paper_bot_id and 0.04 <= float(rt["buy_price"]) <= 0.05
    ]
    if con is None:
        return {"available": False, "reason": "no_db_connection"}
    if not rows:
        return {
            "available": True,
            "paper_bot_id": paper_bot_id,
            "live_bot_id": live_bot_id,
            "paper_closed_4c_5c": 0,
            "paper_wins_4c_5c": 0,
            "paper_orders_with_live_order": 0,
            "paper_orders_with_live_fill": 0,
            "paper_win_live_filled": 0,
            "paper_win_no_live_fill": 0,
            "paper_win_no_live_order": 0,
            "paper_win_zero_at_limit_depth": 0,
            "paper_win_zero_plus2_depth": 0,
            "paper_win_toy_fill_only": 0,
            "live_fill_transfer_rate_pct": None,
            "paper_win_transfer_rate_pct": None,
            "examples": [],
        }

    paper_wins = [rt for rt in rows if rt.get("win")]
    with_live_order = 0
    with_live_fill = 0
    win_live_filled = 0
    win_no_live_fill = 0
    win_no_live_order = 0
    win_zero_at_limit = 0
    win_zero_plus2 = 0
    win_toy_only = 0
    examples: list[dict] = []

    for rt in rows:
        live_orders = _matching_live_orders(con, rt, live_bot_id=live_bot_id)
        live_order_ids = [str(row.get("order_id") or "") for row in live_orders if row.get("order_id")]
        live_trade_count = _live_trade_count_for_orders(
            con,
            live_order_ids,
            live_bot_id=live_bot_id,
        )
        if live_orders:
            with_live_order += 1
        if live_trade_count > 0:
            with_live_fill += 1
        if rt.get("win"):
            if live_trade_count > 0:
                win_live_filled += 1
            else:
                win_no_live_fill += 1
                if not live_orders:
                    win_no_live_order += 1
                if _depth_notional(rt, 0) <= 0:
                    win_zero_at_limit += 1
                if _depth_notional(rt, 2) <= 0:
                    win_zero_plus2 += 1
                if str(rt.get("capacity_label_25") or "") == "toy_fill_only":
                    win_toy_only += 1
                if len(examples) < BOT_G_LIVE_TRANSFER_EXAMPLES:
                    examples.append(
                        {
                            "condition_id": rt.get("condition_id"),
                            "token_id": rt.get("token_id"),
                            "paper_order_id": rt.get("order_id"),
                            "paper_buy_price": rt.get("buy_price"),
                            "paper_pnl_usd": rt.get("pnl_usd"),
                            "paper_buy_filled_at": rt.get("buy_filled_at"),
                            "paper_sell_filled_at": rt.get("sell_filled_at"),
                            "depth_notional_at_limit": round(_depth_notional(rt, 0), 4),
                            "depth_notional_plus2": round(_depth_notional(rt, 2), 4),
                            "live_orders": live_orders,
                            "live_trade_count": live_trade_count,
                        }
                    )

    return {
        "available": True,
        "paper_bot_id": paper_bot_id,
        "live_bot_id": live_bot_id,
        "paper_closed_4c_5c": len(rows),
        "paper_wins_4c_5c": len(paper_wins),
        "paper_orders_with_live_order": with_live_order,
        "paper_orders_with_live_fill": with_live_fill,
        "paper_win_live_filled": win_live_filled,
        "paper_win_no_live_fill": win_no_live_fill,
        "paper_win_no_live_order": win_no_live_order,
        "paper_win_zero_at_limit_depth": win_zero_at_limit,
        "paper_win_zero_plus2_depth": win_zero_plus2,
        "paper_win_toy_fill_only": win_toy_only,
        "live_fill_transfer_rate_pct": _pct(with_live_fill, len(rows)),
        "paper_win_transfer_rate_pct": _pct(win_live_filled, len(paper_wins)),
        "examples": examples,
        "read": (
            "Transfer proof requires paper candidates to have matching live fills. "
            "Paper-only wins with zero entry depth are not live edge evidence."
        ),
    }


def validation_splits(closed: list[dict]) -> dict[str, dict]:
    splits = {
        "3_5c_5_5c": [rt for rt in closed if 0.035 <= float(rt["buy_price"]) <= 0.055],
        "4c_5c": [rt for rt in closed if 0.04 <= float(rt["buy_price"]) <= 0.05],
        "5c_8c": [rt for rt in closed if 0.05 < float(rt["buy_price"]) <= 0.08],
        "all_4c_8c": [rt for rt in closed if 0.04 <= float(rt["buy_price"]) <= 0.08],
    }
    out: dict[str, dict] = {}
    for label, rows in splits.items():
        summary = _roi_summary(rows)
        summary["cex"] = _cex_summary(rows)
        summary["capacity"] = _capacity_summary(rows)
        summary["capacity_policy"] = capacity_policy_summary(summary)
        summary["diagnostic_labels"] = {
            "capacity_25": _label_summary(rows, "capacity_label_25"),
            "capacity_50": _label_summary(rows, "capacity_label_50"),
            "depletion": _label_summary(rows, "depletion_label"),
        }
        out[label] = summary
    return out


def summarise_validation_splits(splits: dict[str, dict]) -> str:
    labels = [
        ("3_5c_5_5c", "3.5c-5.5c"),
        ("4c_5c", "4c-5c"),
        ("5c_8c", "5c-8c"),
        ("all_4c_8c", "all 4c-8c"),
    ]
    lines = ["\n### Bot G paper validation splits\n"]
    lines.append("| split | closed | wins | pnl | cost | ROI | ex-largest-win ROI | ex-largest-two ROI |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for key, label in labels:
        row = splits[key]
        out = row["outlier_adjusted"]
        lines.append(
            "| {label} | {closed} | {wins} | ${pnl:+.2f} | ${cost:.2f} | {roi} | {ex1} | {ex2} |".format(
                label=label,
                closed=row["closed"],
                wins=row["wins"],
                pnl=row["pnl"],
                cost=row["cost"],
                roi="n/a" if row["roi_pct"] is None else f"{row['roi_pct']:+.1f}%",
                ex1="n/a" if out["ex_largest_win"]["roi_pct"] is None else f"{out['ex_largest_win']['roi_pct']:+.1f}%",
                ex2="n/a" if out["ex_largest_two_wins"]["roi_pct"] is None else f"{out['ex_largest_two_wins']['roi_pct']:+.1f}%",
            )
        )
    return "\n".join(lines)


def main() -> int:
    con = sqlite3.connect(DB)
    trades = fetch_trades(con)
    entry_events = fetch_entry_events(con)
    print(f"Loaded {len(trades)} bot_g trade rows")
    closed = fifo_match(trades, entry_events=entry_events, con=con)
    print(f"FIFO-matched {len(closed)} closed round-trips")
    if not closed:
        print("No closed round-trips yet.")
        return 0
    wr = sum(1 for rt in closed if rt["win"]) / len(closed)
    total_pnl = sum(rt["pnl_usd"] for rt in closed)
    total_cost = sum(rt["buy_price"] * rt["size"] for rt in closed)
    outliers = outlier_adjusted_summary(closed)
    splits = validation_splits(closed)
    live_transfer = live_transfer_summary(con, closed)
    print(
        f"Overall: WR={wr:.1%} pnl=${total_pnl:+.2f} "
        f"cost=${total_cost:.2f} roi={total_pnl/total_cost*100:+.1f}%"
    )
    print(
        "Outlier check: largest_win=${largest:+.2f} profit_share={share} "
        "ex_largest_win_roi={roi}% ex_largest_two_wins_roi={roi2}%".format(
            largest=outliers["largest_win_pnl"],
            share=outliers["largest_win_share_of_profit"],
            roi=outliers["ex_largest_win"]["roi_pct"],
            roi2=outliers["ex_largest_two_wins"]["roi_pct"],
        )
    )

    # Feature tables
    by_bot = summarise(closed, lambda rt: rt["bot_id"], "By bot cohort")
    by_bucket = summarise(
        closed,
        lambda rt: bucket_entry_price(rt["buy_price"]),
        "By entry-price bucket",
    )
    by_exact_bucket = summarise(
        closed,
        lambda rt: bucket_entry_price_exact(rt["buy_price"]),
        "By exact entry-price bucket",
    )
    by_symbol = summarise(closed, lambda rt: rt.get("symbol") or "OTHER", "By symbol")
    by_cex = summarise(
        closed,
        lambda rt: (
            "confirmed" if rt.get("cex_confirmed") is True
            else "unconfirmed" if rt.get("cex_confirmed") is False
            else "unknown"
        ),
        "By CEX confirmation",
    )
    by_hour = summarise(
        closed,
        lambda rt: (
            f"{hour_of_day(rt['buy_filled_at']):02d}"
            if hour_of_day(rt["buy_filled_at"]) >= 0
            else "??"
        ),
        "By entry hour-of-day (UTC)",
    )
    print(by_bot)
    print(by_bucket)
    print(by_exact_bucket)
    print(by_symbol)
    print(by_cex)
    print(by_hour)
    print(summarise_validation_splits(splits))
    if live_transfer.get("available"):
        print("\n### Bot G paper-to-live transfer check\n")
        print(
            "4c-5c paper closed={closed} wins={wins} live_order_matches={orders} "
            "live_fill_matches={fills} paper_win_no_live_fill={misses} "
            "win_transfer_rate={rate}".format(
                closed=live_transfer.get("paper_closed_4c_5c", 0),
                wins=live_transfer.get("paper_wins_4c_5c", 0),
                orders=live_transfer.get("paper_orders_with_live_order", 0),
                fills=live_transfer.get("paper_orders_with_live_fill", 0),
                misses=live_transfer.get("paper_win_no_live_fill", 0),
                rate=live_transfer.get("paper_win_transfer_rate_pct"),
            )
        )
    print(summarise_fee_stress(closed))
    print(summarise_capacity(closed))

    # Write JSON dump for downstream use
    out = {
        "overall": {"n": len(closed), "wr": wr, "pnl": total_pnl, "cost": total_cost},
        "outlier_adjusted": outliers,
        "validation_splits": splits,
        "live_transfer": live_transfer,
        "fee_stress": {
            "maker_entry_maker_exit": sum(float(rt["pnl_usd"]) for rt in closed),
            "taker_entry_maker_exit": sum(float(rt["pnl_entry_taker_exit_maker"]) for rt in closed),
            "maker_entry_taker_exit": sum(float(rt["pnl_entry_maker_exit_taker"]) for rt in closed),
            "taker_entry_taker_exit": sum(float(rt["pnl_both_taker"]) for rt in closed),
        },
        "closed": closed,
    }
    output = _output_path()
    with output.open("w") as f:
        json.dump(out, f, default=str, indent=2)
    print(f"\nWrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
