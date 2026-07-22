#!/usr/bin/env python3
"""Read-only fast-ROI report for Longshot Prime, Weather Fade, and Maker Flow.

The report answers a narrow operator question: which paper bot can turn
meaningful capital fastest without hiding behind fake fills, long lock-up,
or jackpot/outlier noise?
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from core.bot_g_live_probe import bot_g_tiny_live_probe_plan
from scripts.bot_g_feature_analysis import (
    fetch_entry_events,
)
from scripts.bot_g_feature_analysis import (
    fetch_trades as fetch_bot_g_trades,
)
from scripts.bot_g_feature_analysis import (
    fifo_match as fifo_match_bot_g,
)
from scripts.bot_g_feature_analysis import (
    live_candidate_gate as bot_g_live_candidate_gate,
)
from scripts.bot_g_feature_analysis import (
    live_transfer_summary as bot_g_live_transfer_summary,
)
from scripts.bot_g_feature_analysis import (
    validation_splits as bot_g_validation_splits,
)

DEFAULT_BOTS = ("bot_e", "bot_g_prime", "bot_d")


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _rows_as_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _money(value: object) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _hours_since(dt: datetime | None, now: datetime) -> float | None:
    if dt is None:
        return None
    return round((now - dt).total_seconds() / 3600, 2)


def _orders(conn: sqlite3.Connection, bot_id: str, cutoff: datetime) -> list[dict[str, Any]]:
    if not _has_table(conn, "orders"):
        return []
    rows = conn.execute(
        """
        SELECT status,
               COUNT(*) AS n,
               COALESCE(SUM(COALESCE(price, 0) * COALESCE(size, 0)), 0) AS notional,
               MIN(placed_at) AS first_seen,
               MAX(placed_at) AS last_seen
        FROM orders
        WHERE bot_id = ?
          AND placed_at >= ?
        GROUP BY status
        ORDER BY status
        """,
        (bot_id, cutoff.strftime("%Y-%m-%d %H:%M:%S")),
    ).fetchall()
    return _rows_as_dicts(rows)


def _trades(conn: sqlite3.Connection, bot_id: str, cutoff: datetime) -> dict[str, Any]:
    if not _has_table(conn, "trades"):
        return {"fills": 0, "notional": 0.0, "fees": 0.0, "first_seen": None, "last_seen": None}
    row = conn.execute(
        """
        SELECT COUNT(*) AS fills,
               COALESCE(SUM(price * size), 0) AS notional,
               COALESCE(SUM(fee_usd), 0) AS fees,
               MIN(filled_at) AS first_seen,
               MAX(filled_at) AS last_seen
        FROM trades
        WHERE bot_id = ?
          AND filled_at >= ?
        """,
        (bot_id, cutoff.strftime("%Y-%m-%d %H:%M:%S")),
    ).fetchone()
    return dict(row) if row else {"fills": 0, "notional": 0.0, "fees": 0.0}


def _bot_g_trade_mode_counts(conn: sqlite3.Connection) -> dict[str, int]:
    if not _has_table(conn, "trades"):
        return {"paper_fills_count": 0, "live_fills_count": 0}
    order_status_by_id: dict[str, str] = {}
    if _has_table(conn, "orders"):
        order_rows = conn.execute(
            """
            SELECT DISTINCT t.order_id, o.status
            FROM trades t
            LEFT JOIN orders o ON o.order_id = t.order_id
            WHERE t.bot_id = 'bot_g_prime'
            """
        ).fetchall()
        order_status_by_id = {str(row["order_id"]): str(row["status"] or "") for row in order_rows}
    rows = conn.execute(
        """
        SELECT trade_id, order_id
        FROM trades
        WHERE bot_id = 'bot_g_prime'
        """
    ).fetchall()
    paper = 0
    live = 0
    for row in rows:
        order_id = str(row["order_id"] or "")
        trade_id = str(row["trade_id"] or "")
        is_paper = (
            order_id.startswith("paper-")
            or trade_id.startswith("paper-")
            or order_status_by_id.get(order_id, "").startswith("PAPER")
        )
        if is_paper:
            paper += 1
        else:
            live += 1
    return {"paper_fills_count": paper, "live_fills_count": live}


def _open_positions(conn: sqlite3.Connection, bot_id: str, now: datetime) -> dict[str, Any]:
    if not _has_table(conn, "positions"):
        return {"open_positions": 0, "open_cost_basis": 0.0, "avg_open_age_hours": None}
    rows = conn.execute(
        """
        SELECT cost_basis_usd, opened_at
        FROM positions
        WHERE bot_id = ?
          AND status = 'OPEN'
        """,
        (bot_id,),
    ).fetchall()
    ages = [
        (now - dt).total_seconds() / 3600
        for row in rows
        if (dt := _parse_dt(row["opened_at"])) is not None
    ]
    return {
        "open_positions": len(rows),
        "open_cost_basis": _money(sum(float(row["cost_basis_usd"] or 0) for row in rows)),
        "avg_open_age_hours": round(sum(ages) / len(ages), 2) if ages else None,
        "max_open_age_hours": round(max(ages), 2) if ages else None,
    }


def _events(conn: sqlite3.Connection, bot_id: str, cutoff: datetime) -> dict[str, int]:
    if not _has_table(conn, "events"):
        return {}
    rows = conn.execute(
        """
        SELECT event_type, COUNT(*) AS n
        FROM events
        WHERE bot_id = ?
          AND created_at >= ?
        GROUP BY event_type
        ORDER BY n DESC, event_type
        """,
        (bot_id, cutoff.strftime("%Y-%m-%d %H:%M:%S")),
    ).fetchall()
    return {str(row["event_type"]): int(row["n"]) for row in rows}


def _crowd_sensor_summary(bot_f_db: Path, cutoff: datetime) -> dict[str, Any]:
    if not bot_f_db.exists():
        return {"available": False, "cascade_count": 0, "top_markets": []}
    conn = sqlite3.connect(str(bot_f_db))
    conn.row_factory = sqlite3.Row
    try:
        if not _has_table(conn, "crowd_signals"):
            return {"available": False, "cascade_count": 0, "top_markets": []}
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM crowd_signals WHERE detected_at >= ?",
            (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchone()["n"]
        top = conn.execute(
            """
            SELECT market_id, dominant_side, COUNT(*) AS n,
                   MAX(gross_usd) AS max_gross_usd,
                   MAX(n_wallets) AS max_wallets
            FROM crowd_signals
            WHERE detected_at >= ?
            GROUP BY market_id, dominant_side
            ORDER BY max_gross_usd DESC
            LIMIT 10
            """,
            (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()
    finally:
        conn.close()
    return {
        "available": True,
        "cascade_count": int(count),
        "top_markets": _rows_as_dicts(top),
    }


def _midpoint_from_book(row: sqlite3.Row | None) -> float | None:
    if row is None:
        return None
    try:
        bids = json.loads(row["bids"] or "[]")
        asks = json.loads(row["asks"] or "[]")
    except (TypeError, json.JSONDecodeError):
        return None
    try:
        best_bid = max(float(level[0]) for level in bids if level)
        best_ask = min(float(level[0]) for level in asks if level)
    except (TypeError, ValueError, IndexError):
        return None
    return round((best_bid + best_ask) / 2, 6)


def _nearest_mid(conn: sqlite3.Connection, token_id: str, ts: datetime) -> float | None:
    if not _has_table(conn, "books"):
        return None
    ts_sql = ts.strftime("%Y-%m-%d %H:%M:%S.%f")
    row = conn.execute(
        """
        SELECT bids, asks
        FROM books
        WHERE token_id = ?
          AND snapshot_at >= ?
        ORDER BY snapshot_at
        LIMIT 1
        """,
        (token_id, ts_sql),
    ).fetchone()
    return _midpoint_from_book(row)


def _crowd_sensor_drift_summary(
    conn: sqlite3.Connection,
    *,
    bot_f_db: Path,
    cutoff: datetime,
    horizons_sec: tuple[int, ...] = (60, 300, 1800, 21600),
) -> dict[str, Any]:
    """Measure post-signal mid drift for legacy mirror signals using main books."""
    if not bot_f_db.exists() or not _has_table(conn, "books"):
        return {"available": False, "signals": 0, "horizons_sec": {}, "reason": "missing_db_or_books"}
    bf = sqlite3.connect(str(bot_f_db))
    bf.row_factory = sqlite3.Row
    try:
        if not _has_table(bf, "mirror_signals"):
            return {"available": False, "signals": 0, "horizons_sec": {}, "reason": "missing_mirror_signals"}
        rows = bf.execute(
            """
            SELECT detected_at, token_id, side, price
            FROM mirror_signals
            WHERE detected_at >= ?
            ORDER BY detected_at DESC
            LIMIT 500
            """,
            (cutoff.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchall()
    finally:
        bf.close()
    by_horizon = {
        str(h): {"measured": 0, "favorable": 0, "mean_mid_drift": None}
        for h in horizons_sec
    }
    drift_values: dict[str, list[float]] = {str(h): [] for h in horizons_sec}
    for row in rows:
        detected = _parse_dt(row["detected_at"])
        if detected is None:
            continue
        token_id = str(row["token_id"] or "")
        side = str(row["side"] or "").upper()
        start_mid = _nearest_mid(conn, token_id, detected)
        if start_mid is None:
            try:
                start_mid = float(row["price"] or 0)
            except (TypeError, ValueError):
                continue
        for horizon in horizons_sec:
            key = str(horizon)
            end_mid = _nearest_mid(conn, token_id, detected + timedelta(seconds=horizon))
            if end_mid is None:
                continue
            drift = end_mid - start_mid
            favorable = drift > 0 if "BUY" in side else drift < 0
            drift_values[key].append(drift)
            by_horizon[key]["measured"] += 1
            if favorable:
                by_horizon[key]["favorable"] += 1
    for key, values in drift_values.items():
        if values:
            by_horizon[key]["mean_mid_drift"] = round(sum(values) / len(values), 5)
            by_horizon[key]["favorable_rate"] = round(
                by_horizon[key]["favorable"] / by_horizon[key]["measured"],
                4,
            )
        else:
            by_horizon[key]["favorable_rate"] = None
    return {
        "available": True,
        "signals": len(rows),
        "horizons_sec": by_horizon,
    }


def _bot_g_paper_validation(conn: sqlite3.Connection) -> dict[str, Any]:
    """Current Bot G Prime paper evidence, split by exact entry bucket."""
    try:
        trades = fetch_bot_g_trades(conn, bot_ids=("bot_g_prime",))
        entry_events = fetch_entry_events(conn)
        closed = fifo_match_bot_g(trades, entry_events=entry_events, con=conn)
        splits = bot_g_validation_splits(closed)
        gate = bot_g_live_candidate_gate(splits)
        live_transfer = bot_g_live_transfer_summary(conn, closed)
        latest_entry = _latest_bot_g_entry_payload(conn)
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc)[:200],
            "posture": "paper_only",
            "current_collection_band": "4c-8c",
            "positive_signal_band": "4c-5c",
            "tiny_live_probe": bot_g_tiny_live_probe_plan(
                dry_run=os.environ.get("BOT_G_DRY_RUN", "true").lower() == "true",
                env=os.environ.get("BOT_G_ENV", "paper"),
                global_env=os.environ.get("POLYMARKET_ENV", "paper"),
                live_wallet_usd=os.environ.get("BOT_G_LIVE_WALLET_USD", "200"),
                trade_metrics=_bot_g_trade_mode_counts(conn),
                order_metrics={},
                validation={},
            ),
        }
    return {
        "available": True,
        "posture": "paper_only",
        "current_collection_band": "4c-8c",
        "positive_signal_band": "4c-5c",
        "live_ready": gate["live_ready"],
        "live_candidate_gate": gate,
        "interpretation": (
            "Keep collecting 4c-8c paper data; only 4c-5c currently has "
            "positive signal, and capacity/outlier gates remain open."
        ),
        "live_transfer": live_transfer,
        "latest_entry_telemetry": latest_entry,
        "tiny_live_probe": bot_g_tiny_live_probe_plan(
            dry_run=os.environ.get("BOT_G_DRY_RUN", "true").lower() == "true",
            env=os.environ.get("BOT_G_ENV", "paper"),
            global_env=os.environ.get("POLYMARKET_ENV", "paper"),
            live_wallet_usd=os.environ.get("BOT_G_LIVE_WALLET_USD", "200"),
            trade_metrics=_bot_g_trade_mode_counts(conn),
            order_metrics={},
            validation={"live_ready": gate["live_ready"], "live_candidate_gate": gate},
        ),
        "splits": splits,
    }


def _latest_bot_g_entry_payload(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _has_table(conn, "events"):
        return {"available": False, "has_capacity_depth": False}
    cols = {str(row[1]) for row in conn.execute("PRAGMA table_info(events)")}
    if "payload" not in cols:
        return {"available": False, "has_capacity_depth": False}
    row = conn.execute(
        """
        SELECT created_at, payload
        FROM events
        WHERE bot_id = 'bot_g_prime'
          AND event_type = 'bot_g.entry_placed'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {"available": False, "has_capacity_depth": False}
    try:
        payload = json.loads(row["payload"] or "{}")
    except json.JSONDecodeError:
        payload = {}
    cap = payload.get("capacity_depth")
    return {
        "available": True,
        "created_at": row["created_at"],
        "has_capacity_depth": isinstance(cap, dict),
        "depth_ticks": sorted(cap.keys()) if isinstance(cap, dict) else [],
    }


def _fill_rate(orders: list[dict[str, Any]]) -> float | None:
    counts = {str(row["status"]): int(row["n"]) for row in orders}
    total = sum(counts.values())
    if total <= 0:
        return None
    return round(counts.get("FILLED", 0) / total, 4)


def _capacity_hint(bot_id: str, trades: dict[str, Any], positions: dict[str, Any]) -> str:
    fills = int(trades.get("fills") or 0)
    avg_age = positions.get("avg_open_age_hours")
    open_cost = float(positions.get("open_cost_basis") or 0)
    if bot_id == "bot_e":
        if fills <= 0:
            return "No current fill sample; prioritize fill-quality before thresholds."
        return "Fast-turnover candidate; next gate is adverse selection at $25/$50."
    if bot_id == "bot_g_prime":
        if fills <= 0:
            return "No current Prime fill sample; keep paper only."
        return "Fast challenger; require ex-largest-win and bucket EV proof."
    if bot_id == "bot_d":
        if open_cost > 0 and avg_age is not None and avg_age > 24:
            return "Capital lock-up visible; split daily vs weekly before scaling."
        return "Craft edge candidate; capacity depends on daily contracts and depth."
    return "Review manually."


def build_report(
    db_path: Path,
    *,
    bot_f_db: Path,
    lookback_hours: int,
    bots: tuple[str, ...] = DEFAULT_BOTS,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=lookback_hours)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        bot_rows = []
        for bot_id in bots:
            orders = _orders(conn, bot_id, cutoff)
            trades = _trades(conn, bot_id, cutoff)
            positions = _open_positions(conn, bot_id, now)
            events = _events(conn, bot_id, cutoff)
            trade_notional = _money(trades.get("notional"))
            open_cost = _money(positions.get("open_cost_basis"))
            bot_rows.append(
                {
                    "bot_id": bot_id,
                    "orders": orders,
                    "fill_rate": _fill_rate(orders),
                    "trades": {
                        "fills": int(trades.get("fills") or 0),
                        "notional": trade_notional,
                        "fees": _money(trades.get("fees")),
                        "first_seen": trades.get("first_seen"),
                        "last_seen": trades.get("last_seen"),
                        "last_fill_age_hours": _hours_since(
                            _parse_dt(trades.get("last_seen")), now
                        ),
                    },
                    "open_positions": positions,
                    "turnover_vs_open_cost": (
                        round(trade_notional / open_cost, 4) if open_cost > 0 else None
                    ),
                    "events_top": dict(list(events.items())[:12]),
                    "capacity_hint": _capacity_hint(bot_id, trades, positions),
                }
            )
        bot_g_validation = _bot_g_paper_validation(conn)
        crowd_sensor_drift = _crowd_sensor_drift_summary(conn, bot_f_db=bot_f_db, cutoff=cutoff)
    finally:
        conn.close()
    return {
        "generated_at": now.isoformat(),
        "db_path": str(db_path),
        "crowd_sensor_db_path": str(bot_f_db),
        "lookback_hours": lookback_hours,
        "bots": bot_rows,
        "bot_g_paper_validation": bot_g_validation,
        "crowd_sensor": _crowd_sensor_summary(bot_f_db, cutoff),
        "crowd_sensor_drift": crowd_sensor_drift,
        "notes": [
            "This is not a realised-P&L report.",
            "Use it to rank fast ROI readiness: turnover, fill flow, lock-up, and sensor overlap.",
            "Legacy Bot F is archived; crowd data is retained as shared signal infrastructure.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    def _append_label_table(lines: list[str], title: str, rows: dict[str, Any]) -> None:
        lines.extend([
            "",
            f"### {title}",
            "",
            "| Label | Closed | Wins | ROI | Ex-largest-win ROI | Ex-largest-two ROI |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        if not rows:
            lines.append("| n/a | 0 | 0 | n/a | n/a | n/a |")
            return
        for label, row in sorted(rows.items()):
            outliers = row.get("outlier_adjusted") or {}
            ex1 = (outliers.get("ex_largest_win") or {}).get("roi_pct")
            ex2 = (outliers.get("ex_largest_two_wins") or {}).get("roi_pct")
            lines.append(
                "| `{label}` | {closed} | {wins} | {roi} | {ex1} | {ex2} |".format(
                    label=label,
                    closed=row.get("closed", 0),
                    wins=row.get("wins", 0),
                    roi="n/a" if row.get("roi_pct") is None else f"{row['roi_pct']:+.1f}%",
                    ex1="n/a" if ex1 is None else f"{ex1:+.1f}%",
                    ex2="n/a" if ex2 is None else f"{ex2:+.1f}%",
                )
            )

    lines = [
        "# Fast ROI Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Lookback: `{report['lookback_hours']}h`",
        "",
        "| Bot | Fill rate | Fills | Trade notional | Open cost | Avg open age | "
        "Turnover/open | Hint |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["bots"]:
        pos = row["open_positions"]
        trades = row["trades"]
        fill_rate = row["fill_rate"]
        lines.append(
            "| `{bot}` | {fill_rate} | {fills} | ${notional:.2f} | ${open_cost:.2f} | "
            "{avg_age}h | {turnover} | {hint} |".format(
                bot=row["bot_id"],
                fill_rate="n/a" if fill_rate is None else f"{fill_rate:.1%}",
                fills=trades["fills"],
                notional=trades["notional"],
                open_cost=pos["open_cost_basis"],
                avg_age="n/a" if pos["avg_open_age_hours"] is None else pos["avg_open_age_hours"],
                turnover=(
                    "n/a"
                    if row["turnover_vs_open_cost"] is None
                    else row["turnover_vs_open_cost"]
                ),
                hint=row["capacity_hint"],
            )
        )
    crowd = report["crowd_sensor"]
    bot_g = report.get("bot_g_paper_validation") or {}
    if bot_g:
        lines.extend(
            [
                "",
                "## Bot G Paper Validation",
                "",
                f"- Posture: `{bot_g.get('posture', 'paper_only')}`",
                f"- Collection band: `{bot_g.get('current_collection_band', '4c-8c')}`",
                f"- Positive signal band: `{bot_g.get('positive_signal_band', '4c-5c')}`",
                f"- Live ready: `{bot_g.get('live_ready', False)}`",
                f"- Candidate gate: `{(bot_g.get('live_candidate_gate') or {}).get('status', 'unknown')}`",
                f"- Gate reasons: `{', '.join((bot_g.get('live_candidate_gate') or {}).get('reasons') or ['none'])}`",
                f"- Read: {bot_g.get('interpretation', 'No validation read available.')}",
                (
                    "- Latest entry capacity telemetry: "
                    f"`{(bot_g.get('latest_entry_telemetry') or {}).get('has_capacity_depth', False)}`"
                ),
                "",
                "| Split | Closed | Wins | ROI | Ex-largest-win ROI | Ex-largest-two ROI | $25 limit/+1/+2 | $50 limit/+1/+2 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for key, label in (
            ("3_5c_5_5c", "3.5c-5.5c"),
            ("4c_5c", "4c-5c"),
            ("5c_8c", "5c-8c"),
            ("all_4c_8c", "all 4c-8c"),
        ):
            split = (bot_g.get("splits") or {}).get(key) or {}
            outliers = split.get("outlier_adjusted") or {}
            ex1 = (outliers.get("ex_largest_win") or {}).get("roi_pct")
            ex2 = (outliers.get("ex_largest_two_wins") or {}).get("roi_pct")
            cap = split.get("capacity") or {}
            targets = cap.get("targets_usd") or {}
            cap25 = targets.get("25") or {}
            cap50 = targets.get("50") or {}

            def _cap_text(target: dict[str, Any]) -> str:
                bits = []
                for tick in ("0", "1", "2"):
                    row = target.get(tick) or {}
                    bits.append(f"{row.get('covered', 0)}/{row.get('total', 0)}")
                return " / ".join(bits)

            lines.append(
                "| {label} | {closed} | {wins} | {roi} | {ex1} | {ex2} | {c25} | {c50} |".format(
                    label=label,
                    closed=split.get("closed", 0),
                    wins=split.get("wins", 0),
                    roi="n/a" if split.get("roi_pct") is None else f"{split['roi_pct']:+.1f}%",
                    ex1="n/a" if ex1 is None else f"{ex1:+.1f}%",
                    ex2="n/a" if ex2 is None else f"{ex2:+.1f}%",
                    c25=_cap_text(cap25),
                    c50=_cap_text(cap50),
                )
            )
        transfer = bot_g.get("live_transfer") or {}
        if transfer.get("available"):
            lines.extend(
                [
                    "",
                    "### Bot G Paper-To-Live Transfer",
                    "",
                    "| Paper 4c-5c closed | Paper wins | Live order matches | Live fill matches | Paper wins with no live fill | Win transfer rate |",
                    "|---:|---:|---:|---:|---:|---:|",
                    "| {closed} | {wins} | {orders} | {fills} | {misses} | {rate} |".format(
                        closed=transfer.get("paper_closed_4c_5c", 0),
                        wins=transfer.get("paper_wins_4c_5c", 0),
                        orders=transfer.get("paper_orders_with_live_order", 0),
                        fills=transfer.get("paper_orders_with_live_fill", 0),
                        misses=transfer.get("paper_win_no_live_fill", 0),
                        rate=(
                            "n/a"
                            if transfer.get("paper_win_transfer_rate_pct") is None
                            else f"{float(transfer['paper_win_transfer_rate_pct']):.1f}%"
                        ),
                    ),
                    "",
                    f"- Paper wins with zero at-limit depth: `{transfer.get('paper_win_zero_at_limit_depth', 0)}`",
                    f"- Paper wins with zero limit+2c depth: `{transfer.get('paper_win_zero_plus2_depth', 0)}`",
                    f"- Read: {transfer.get('read', 'Paper/live transfer summary unavailable.')}",
                ]
            )
        labels = ((bot_g.get("splits") or {}).get("all_4c_8c") or {}).get("diagnostic_labels") or {}
        _append_label_table(lines, "Bot G $25 Capacity Labels (all 4c-8c)", labels.get("capacity_25") or {})
        _append_label_table(lines, "Bot G $50 Capacity Labels (all 4c-8c)", labels.get("capacity_50") or {})
        _append_label_table(lines, "Bot G Depletion/Reload Labels (all 4c-8c)", labels.get("depletion") or {})
        probe = bot_g.get("tiny_live_probe") or {}
        lines.extend(
            [
                "",
                "## Bot G Tiny-Live Probe Plan",
                "",
                f"- Status: `{probe.get('status', 'paper_observing')}`",
                f"- Runtime source: `{probe.get('runtime_source', 'dashboard_env')}`",
                f"- Bot env: `{probe.get('bot_env', 'paper')}`",
                f"- Bot dry-run: `{probe.get('bot_dry_run', True)}`",
                f"- Global Polymarket env: `{probe.get('global_polymarket_env', 'paper')}`",
                f"- Effective paper: `{probe.get('effective_paper', True)}`",
                f"- Approval required: `{probe.get('approval_required', True)}`",
                f"- Does not authorize live: `{probe.get('does_not_authorize_live', True)}`",
                (
                    "- Proposed live wallet: "
                    f"`${float(probe.get('proposed_live_wallet_usd') or 0):.2f}`"
                ),
                (
                    "- Proposed first size: "
                    f"`${float(probe.get('proposed_starting_trade_usd') or 0):.2f}` "
                    f"({float(probe.get('proposed_starting_trade_wallet_pct') or 0):.2f}% "
                    "of wallet)"
                ),
                (
                    "- Proposed daily cap: "
                    f"`{probe.get('proposed_daily_entry_cap', 0)}` entries / "
                    f"`${float(probe.get('proposed_gross_notional_cap_usd') or 0):.2f}` "
                    "gross notional "
                    f"({float(probe.get('proposed_gross_notional_wallet_pct') or 0):.2f}% "
                    "of wallet)"
                ),
                (
                    "- Proposed max open: "
                    f"`{probe.get('proposed_max_open_positions', 0)}` positions / "
                    f"`${float(probe.get('proposed_max_open_notional_usd') or 0):.2f}` "
                    f"({float(probe.get('proposed_max_open_wallet_pct') or 0):.2f}% of wallet)"
                ),
                f"- Paper fills: `{probe.get('paper_fills_count', 0)}`",
                f"- Live fills: `{probe.get('live_fills_count', 0)}`",
                "",
                "| Checklist | Pass | Detail |",
                "|---|---:|---|",
            ]
        )
        for item in probe.get("checklist") or []:
            lines.append(
                "| {label} | {passed} | {detail} |".format(
                    label=item.get("label", "n/a"),
                    passed="YES" if item.get("pass") else "NO",
                    detail=item.get("detail", ""),
                )
            )
        lines.extend(["", "| Milestone | Criterion |", "|---|---|"])
        for item in probe.get("success_criteria") or []:
            lines.append(
                f"| {item.get('milestone', 'n/a')} | {item.get('criterion', '')} |"
            )
    lines.extend(
        [
            "",
            "## Crowd Sensor",
            "",
            f"- Available: `{crowd['available']}`",
            f"- Recent cascades: `{crowd['cascade_count']}`",
        ]
    )
    if crowd["top_markets"]:
        lines.extend(
            [
                "",
                "| Market | Side | Count | Max gross | Max wallets |",
                "|---|---|---:|---:|---:|",
            ]
        )
        for row in crowd["top_markets"]:
            lines.append(
                f"| `{row['market_id']}` | `{row['dominant_side']}` | {row['n']} | "
                f"${float(row['max_gross_usd']):.2f} | {row['max_wallets']} |"
            )
    drift = report.get("crowd_sensor_drift") or {}
    lines.extend(
        [
            "",
            "## Crowd Signal Drift",
            "",
            f"- Available: `{drift.get('available', False)}`",
            f"- Signals sampled: `{drift.get('signals', 0)}`",
        ]
    )
    horizons = drift.get("horizons_sec") or {}
    if horizons:
        lines.extend(
            [
                "",
                "| Horizon | Measured | Favorable | Favorable rate | Mean mid drift |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        labels = {"60": "1m", "300": "5m", "1800": "30m", "21600": "6h"}
        for key in ("60", "300", "1800", "21600"):
            row = horizons.get(key) or {}
            rate = row.get("favorable_rate")
            drift_value = row.get("mean_mid_drift")
            lines.append(
                "| {label} | {measured} | {fav} | {rate} | {drift} |".format(
                    label=labels.get(key, f"{key}s"),
                    measured=row.get("measured", 0),
                    fav=row.get("favorable", 0),
                    rate="n/a" if rate is None else f"{rate:.1%}",
                    drift="n/a" if drift_value is None else f"{drift_value:+.4f}",
                )
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default="./data/main.db")
    p.add_argument("--bot-f-db", default="./data/bot_f.db")
    p.add_argument("--lookback-hours", type=int, default=24)
    p.add_argument("--out-json")
    p.add_argument("--out-md")
    p.add_argument("--stdout-json", action="store_true")
    args = p.parse_args()

    report = build_report(
        Path(args.db),
        bot_f_db=Path(args.bot_f_db),
        lookback_hours=args.lookback_hours,
    )
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.out_md:
        Path(args.out_md).write_text(render_markdown(report))
    if args.stdout_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    if not args.out_json and not args.out_md and not args.stdout_json:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
