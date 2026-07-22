#!/usr/bin/env python3
"""Daily maker-vs-taker comparator for the crypto conversion goal.

Read-only. Does not place orders, mutate DB rows, change services, or decide
live conversion by itself.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

DEFAULT_MAIN_DB = Path("data/main.db")
DEFAULT_OUT = Path("docs/reports")
DEFAULT_PERSISTENCE_TAKER_DB = Path("data/persistence_paper.db")
DEFAULT_PERSISTENCE_MAKER_DB = Path("data/persistence_maker_paper.db")
DEFAULT_PERSISTENCE_LIVE_MAKER_DB = Path(
    "data/persistence_live_maker_paper.db"
)
DEFAULT_CELL_C_MAKER_DB = Path("data/persistence_cell_c_maker_paper.db")

BOT_G_PAIRS = (
    ("bot_g_prime_live", "bot_g_prime_live_maker", "Bot G live high-tail"),
    ("bot_g_prime", "bot_g_prime_maker", "Bot G Prime paper"),
    ("bot_g_prime_shadow", "bot_g_prime_shadow_maker", "Bot G live-mirror paper"),
    ("bot_g_prime_high_tail", "bot_g_prime_high_tail_maker", "Bot G high-tail paper"),
)
CRYPTO_FV_PAIRS = (
    (
        "crypto_probability_gap_paper",
        "crypto_probability_gap_paper_maker",
        "Crypto FV probability gap",
    ),
    (
        "crypto_brownian_fv_paper",
        "crypto_brownian_fv_paper_maker",
        "Crypto FV Brownian",
    ),
)


@dataclass(frozen=True)
class Summary:
    orders: int = 0
    fills: int = 0
    closed: int = 0
    wins: int = 0
    cost: Decimal = Decimal("0")
    pnl: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")

    @property
    def fill_rate(self) -> Decimal | None:
        if self.orders <= 0:
            return None
        return Decimal(self.fills) / Decimal(self.orders)

    @property
    def roi(self) -> Decimal | None:
        if self.cost <= 0:
            return None
        return (self.pnl - self.fees) / self.cost


def _connect_ro(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _fmt_money(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:.2f}"


def _fmt_pct(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * Decimal('100'):+.2f}%"


def _payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _trade_summary(con: sqlite3.Connection, bot_id: str) -> Summary:
    orders = int(
        con.execute("SELECT COUNT(*) FROM orders WHERE bot_id = ?", (bot_id,)).fetchone()[0]
        or 0
    )
    fills = 0
    cost = Decimal("0")
    fees = Decimal("0")
    lots: dict[str, list[list[Decimal]]] = {}
    pnl = Decimal("0")
    closed = wins = 0
    rows = con.execute(
        """
        SELECT trade_id, token_id, side, price, size, fee_usd, filled_at
        FROM trades
        WHERE bot_id = ?
        ORDER BY filled_at, trade_id
        """,
        (bot_id,),
    ).fetchall()
    for row in rows:
        side = str(row["side"] or "")
        if side.startswith(("BUY_", "BUY-")):
            side = "BUY"
        elif side.startswith(("SELL_", "SELL-")):
            side = "SELL"
        price = _decimal(row["price"])
        size = _decimal(row["size"])
        fee = _decimal(row["fee_usd"])
        fees += fee
        token_id = str(row["token_id"] or "")
        if side == "BUY":
            fills += 1
            cost += price * size
            lots.setdefault(token_id, []).append([size, price])
            continue
        if side != "SELL":
            continue
        remaining = size
        sell_pnl = Decimal("0")
        for lot in list(lots.get(token_id, [])):
            if remaining <= 0:
                break
            matched = min(lot[0], remaining)
            sell_pnl += (price - lot[1]) * matched
            lot[0] -= matched
            remaining -= matched
            if lot[0] <= 0:
                lots[token_id].pop(0)
        pnl += sell_pnl
        closed += 1
        if sell_pnl > 0:
            wins += 1
    return Summary(orders=orders, fills=fills, closed=closed, wins=wins, cost=cost, pnl=pnl, fees=fees)


def _persistence_summary(path: Path, *, execution_style: str, cell_label: str | None = None) -> Summary:
    con = _connect_ro(path)
    if con is None:
        return Summary()
    try:
        columns = {row["name"] for row in con.execute("PRAGMA table_info(paper_entries)")}
        where = []
        params: list[str] = []
        if "execution_style" in columns:
            where.append("execution_style = ?")
            params.append(execution_style)
        if cell_label is not None:
            where.append("cell_label = ?")
            params.append(cell_label)
        style_filter = "WHERE " + " AND ".join(where) if where else ""
        cost_column = "bid_high" if execution_style == "maker" else "ask_high"
        row = con.execute(
            f"""
            SELECT COUNT(*) AS n,
                   SUM(won) AS wins,
                   SUM(pnl_usd) AS pnl,
                   SUM(fee_usd) AS fees,
                   SUM({cost_column}) AS cost
            FROM paper_entries
            {style_filter}
            """,
            tuple(params),
        ).fetchone()
    finally:
        con.close()
    n = int(row["n"] or 0)
    return Summary(
        orders=n,
        fills=n,
        closed=n,
        wins=int(row["wins"] or 0),
        cost=_decimal(row["cost"]),
        pnl=_decimal(row["pnl"]),
        fees=_decimal(row["fees"]),
    )


def _crypto_fv_summary(con: sqlite3.Connection, bot_id: str) -> Summary:
    settlements: dict[tuple[str, str], Decimal] = {}
    for row in con.execute(
        """
        SELECT payload
        FROM events
        WHERE bot_id = ? AND event_type = 'portfolio.paper_resolve'
        """,
        (bot_id,),
    ):
        payload = _payload(row["payload"])
        condition_id = str(payload.get("condition_id") or "")
        token_id = str(payload.get("token_id") or "")
        if condition_id and token_id:
            settlements[(condition_id, token_id)] = _decimal(payload.get("settle_price"))

    rows = con.execute(
        """
        SELECT payload
        FROM events
        WHERE bot_id = ? AND event_type = 'crypto_fair_value.signal'
        """,
        (bot_id,),
    ).fetchall()
    signals = fills = closed = wins = 0
    cost = pnl = fees = Decimal("0")
    for row in rows:
        payload = _payload(row["payload"])
        main_track = str(payload.get("main_fill_track") or "")
        condition_id = str(payload.get("condition_id") or "")
        token_id = str(payload.get("token_id") or "")
        for track in payload.get("fill_tracks") or []:
            if not isinstance(track, dict) or str(track.get("fill_track") or "") != main_track:
                continue
            signals += 1
            if not track.get("filled"):
                continue
            fills += 1
            stake = _decimal(track.get("stake_usd"))
            size = _decimal(track.get("size"))
            cost += stake
            fees += _decimal(track.get("fee_usd"))
            settle = settlements.get((condition_id, token_id))
            if settle is None:
                continue
            closed += 1
            if settle >= Decimal("1"):
                wins += 1
            pnl += (settle * size) - stake
    return Summary(orders=signals, fills=fills, closed=closed, wins=wins, cost=cost, pnl=pnl, fees=fees)


def _decision(maker: Summary, taker: Summary) -> str:
    if maker.closed < 50:
        return "WAIT: resolved maker sample < n>=50"
    if maker.roi is not None and taker.roi is not None and maker.roi >= taker.roi + Decimal("0.02"):
        return "S6_READY: maker >= +2pp vs taker"
    if maker.roi is not None and maker.roi > 0 and (taker.roi is None or taker.roi < 0):
        return "S6_REVIEW: maker positive, taker negative"
    return "WAIT_OR_REJECT: gate not met"


def _cell_c_decision(maker: Summary) -> str:
    if maker.closed < 50:
        return "WAIT: resolved maker sample < n>=50"
    if maker.roi is None:
        return "WAIT_OR_REJECT: no maker ROI"
    if maker.roi > Decimal("0.01"):
        return "S7_READY: maker ROI > +1%; $5 live packet review"
    if maker.roi >= Decimal("-0.01"):
        return "S7_BORDERLINE: -1% <= maker ROI <= +1%; $1 probe review"
    return "S7_REJECT: maker ROI <= -1%"


def _row(
    label: str,
    taker_id: str,
    maker_id: str,
    taker: Summary,
    maker: Summary,
    decision: str | None = None,
) -> str:
    decision = decision or _decision(maker, taker)
    return (
        f"| {label} | `{taker_id}` | `{maker_id}` | "
        f"{taker.orders}/{taker.fills}/{taker.closed} | {_fmt_pct(taker.fill_rate)} | "
        f"{_fmt_pct(taker.roi)} | {_fmt_money(taker.pnl - taker.fees)} | "
        f"{maker.orders}/{maker.fills}/{maker.closed} | {_fmt_pct(maker.fill_rate)} | "
        f"{_fmt_pct(maker.roi)} | {_fmt_money(maker.pnl - maker.fees)} | "
        f"{decision} |"
    )


def build_report(
    *,
    main_db: Path,
    persistence_taker_db: Path,
    persistence_maker_db: Path,
    persistence_live_maker_db: Path,
    cell_c_maker_db: Path = DEFAULT_CELL_C_MAKER_DB,
) -> str:
    generated = datetime.now(UTC).isoformat()
    lines = [
        "# Maker vs Taker Daily Comparator",
        "",
        f"Generated: `{generated}`",
        f"Main DB: `{main_db}`",
        "",
        "Counts are `orders/fills/closed`. Rebate income is assumed `0` for headline numbers.",
        "",
        "| lane | taker baseline | maker shadow | taker counts | taker fill rate | taker ROI | taker P&L | maker counts | maker fill rate | maker ROI | maker P&L | decision |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]

    con = _connect_ro(main_db)
    if con is None:
        con_summaries: dict[str, Summary] = {}
    else:
        try:
            bot_ids = {bid for pair in BOT_G_PAIRS + CRYPTO_FV_PAIRS for bid in pair[:2]}
            con_summaries = {
                bot_id: (
                    _crypto_fv_summary(con, bot_id)
                    if bot_id.startswith("crypto_")
                    else _trade_summary(con, bot_id)
                )
                for bot_id in bot_ids
            }
        finally:
            con.close()

    for taker_id, maker_id, label in BOT_G_PAIRS:
        lines.append(
            _row(
                label,
                taker_id,
                maker_id,
                con_summaries.get(taker_id, Summary()),
                con_summaries.get(maker_id, Summary()),
            )
        )

    persistence_taker = _persistence_summary(persistence_taker_db, execution_style="taker")
    persistence_maker = _persistence_summary(persistence_maker_db, execution_style="maker")
    persistence_live_maker = _persistence_summary(
        persistence_live_maker_db,
        execution_style="maker",
    )
    cell_c_maker = _persistence_summary(
        cell_c_maker_db,
        execution_style="maker",
        cell_label="C_tail_5m_15m_95_99",
    )
    lines.append(
        _row(
            "Bot I Persistence",
            "bot_i_persistence",
            "bot_i_persistence_maker",
            persistence_taker,
            persistence_maker,
        )
    )
    lines.append(
        _row(
            "Bot I Persistence Live shadow",
            "bot_i_persistence_live",
            "bot_i_persistence_live_maker",
            Summary(),
            persistence_live_maker,
        )
    )
    lines.append(
        _row(
            "Bot I Cell C maker candidate",
            "bot_i_cell_c_baseline",
            "bot_i_cell_c_maker",
            Summary(),
            cell_c_maker,
            decision=_cell_c_decision(cell_c_maker),
        )
    )

    for taker_id, maker_id, label in CRYPTO_FV_PAIRS:
        lines.append(
            _row(
                label,
                taker_id,
                maker_id,
                con_summaries.get(taker_id, Summary()),
                con_summaries.get(maker_id, Summary()),
            )
        )

    total_taker_cost = Decimal("0")
    total_taker_pnl = Decimal("0")
    total_maker_cost = Decimal("0")
    total_maker_pnl = Decimal("0")
    for taker_id, maker_id, _label in BOT_G_PAIRS + CRYPTO_FV_PAIRS:
        taker = con_summaries.get(taker_id, Summary())
        maker = con_summaries.get(maker_id, Summary())
        total_taker_cost += taker.cost
        total_taker_pnl += taker.pnl - taker.fees
        total_maker_cost += maker.cost
        total_maker_pnl += maker.pnl - maker.fees
    total_taker_cost += persistence_taker.cost
    total_taker_pnl += persistence_taker.pnl - persistence_taker.fees
    total_maker_cost += persistence_maker.cost + persistence_live_maker.cost + cell_c_maker.cost
    total_maker_pnl += (
        persistence_maker.pnl
        - persistence_maker.fees
        + persistence_live_maker.pnl
        - persistence_live_maker.fees
        + cell_c_maker.pnl
        - cell_c_maker.fees
    )
    taker_roi = total_taker_pnl / total_taker_cost if total_taker_cost > 0 else None
    maker_roi = total_maker_pnl / total_maker_cost if total_maker_cost > 0 else None
    lift = maker_roi - taker_roi if maker_roi is not None and taker_roi is not None else None
    s6_decisions = [
        _decision(con_summaries.get(maker_id, Summary()), con_summaries.get(taker_id, Summary()))
        for taker_id, maker_id, _label in BOT_G_PAIRS + CRYPTO_FV_PAIRS
    ]
    s6_decisions.extend(
        [
            _decision(persistence_maker, persistence_taker),
            _decision(persistence_live_maker, Summary()),
            _decision(cell_c_maker, Summary()),
        ]
    )
    if any(decision.startswith("S6_") for decision in s6_decisions):
        s6_status = (
            "- S6 live conversion: REVIEW required for rows marked S6_READY/S6_REVIEW; "
            "this report does not authorize live orders."
        )
    else:
        s6_status = (
            "- S6 live conversion: WAIT until resolved maker sample reaches n>=50 per bot "
            "or 5-day gate."
        )
    cell_c_decision = _cell_c_decision(cell_c_maker)
    if cell_c_decision.startswith("S7_READY"):
        s7_status = (
            "- S7 Cell C: REVIEW. Maker evidence clears the non-borderline n>=50 gate; "
            "live deployment still requires ADR/cap validation before any live order."
        )
    elif cell_c_decision.startswith("S7_BORDERLINE"):
        s7_status = (
            "- S7 Cell C: BORDERLINE. Maker evidence is inside the -1% to +1% Z5 band "
            "on n>=50; the $1 probe path requires ADR/cap validation before any live order."
        )
    elif cell_c_decision.startswith("S7_REJECT"):
        s7_status = "- S7 Cell C: REJECT. Maker evidence is <= -1% on n>=50."
    else:
        s7_status = "- S7 Cell C: WAIT. Current maker evidence is below the n>=50 decision gate."
    lines.extend(
        [
            "",
            "## Fleet Lift Snapshot",
            "",
            f"- Taker baseline P&L: `{_fmt_money(total_taker_pnl)}` on `{_fmt_money(total_taker_cost)}` cost, ROI `{_fmt_pct(taker_roi)}`.",
            f"- Maker paper P&L: `{_fmt_money(total_maker_pnl)}` on `{_fmt_money(total_maker_cost)}` cost, ROI `{_fmt_pct(maker_roi)}`.",
            f"- ROI lift: `{_fmt_pct(lift)}`.",
            "",
            "## Gate Status",
            "",
            s6_status,
            s7_status,
            "- Live orders: none authorized by this report.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-db", type=Path, default=DEFAULT_MAIN_DB)
    parser.add_argument("--persistence-taker-db", type=Path, default=DEFAULT_PERSISTENCE_TAKER_DB)
    parser.add_argument("--persistence-maker-db", type=Path, default=DEFAULT_PERSISTENCE_MAKER_DB)
    parser.add_argument(
        "--persistence-live-maker-db",
        type=Path,
        default=DEFAULT_PERSISTENCE_LIVE_MAKER_DB,
    )
    parser.add_argument("--cell-c-maker-db", type=Path, default=DEFAULT_CELL_C_MAKER_DB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(
        main_db=args.main_db,
        persistence_taker_db=args.persistence_taker_db,
        persistence_maker_db=args.persistence_maker_db,
        persistence_live_maker_db=args.persistence_live_maker_db,
        cell_c_maker_db=args.cell_c_maker_db,
    )
    out = args.out_dir / f"maker-vs-taker-daily-{args.date}.md"
    out.write_text(report)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
