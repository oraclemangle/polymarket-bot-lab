"""Bot E cancel autopsy report.

Reads recent Bot E paper orders and estimates how many would have filled under
longer TTLs or less-passive maker offsets using recorded book snapshots. This
is a read-only diagnostic: it does not place, cancel, or mutate orders.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import median

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO / "data" / "main.db"
DEFAULT_OUT_JSON = REPO / "data" / "bot_e_cancel_autopsy.json"
DEFAULT_OUT_MD = REPO / "data" / "bot_e_cancel_autopsy.md"
CAPACITY_TARGETS_USD = (25.0, 50.0)


def _sqlite_dt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


@dataclass(frozen=True)
class OrderRow:
    order_id: str
    condition_id: str
    token_id: str
    side: str
    price: Decimal
    size: Decimal
    status: str
    placed_at: datetime
    last_updated: datetime | None


def _parse_dt(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _loads_book(raw: str | None) -> list[list[object]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _levels(raw: str | None) -> list[tuple[Decimal, Decimal]]:
    levels: list[tuple[Decimal, Decimal]] = []
    for row in _loads_book(raw):
        try:
            price = Decimal(str(row[0]))
            size = Decimal(str(row[1]))
        except (IndexError, TypeError, ValueError):
            continue
        if price >= 0 and size > 0:
            levels.append((price, size))
    return levels


def _best_ask(raw: str | None) -> Decimal | None:
    asks = _loads_book(raw)
    prices = [Decimal(str(row[0])) for row in asks if row and row[0] is not None]
    return min(prices) if prices else None


def _best_bid(raw: str | None) -> Decimal | None:
    bids = _loads_book(raw)
    prices = [Decimal(str(row[0])) for row in bids if row and row[0] is not None]
    return max(prices) if prices else None


def _midpoint(bids_raw: str | None, asks_raw: str | None) -> Decimal | None:
    bid = _best_bid(bids_raw)
    ask = _best_ask(asks_raw)
    if bid is None or ask is None:
        return None
    return (bid + ask) / Decimal("2")


def _fetch_orders(
    conn: sqlite3.Connection,
    *,
    bot_id: str,
    lookback_hours: float,
) -> list[OrderRow]:
    since = datetime.now(UTC) - timedelta(hours=lookback_hours)
    rows = conn.execute(
        """
        SELECT order_id, condition_id, token_id, side, price, size, status,
               placed_at, last_updated
        FROM orders
        WHERE bot_id = ?
          AND placed_at >= ?
          AND order_id LIKE 'paper-%'
          AND price IS NOT NULL
          AND size IS NOT NULL
        ORDER BY placed_at
        """,
        (bot_id, _sqlite_dt(since)),
    ).fetchall()
    orders: list[OrderRow] = []
    for row in rows:
        orders.append(
            OrderRow(
                order_id=str(row[0]),
                condition_id=str(row[1]),
                token_id=str(row[2]),
                side=str(row[3]).upper(),
                price=Decimal(str(row[4])),
                size=Decimal(str(row[5])),
                status=str(row[6]),
                placed_at=_parse_dt(str(row[7])),
                last_updated=_parse_dt(str(row[8])) if row[8] else None,
            )
        )
    return orders


def _book_rows(
    conn: sqlite3.Connection,
    *,
    token_id: str,
    start: datetime,
    end: datetime,
) -> Iterable[sqlite3.Row]:
    return conn.execute(
        """
        SELECT snapshot_at, bids, asks
        FROM books
        WHERE token_id = ?
          AND snapshot_at >= ?
          AND snapshot_at <= ?
        ORDER BY snapshot_at
        """,
        (token_id, _sqlite_dt(start), _sqlite_dt(end)),
    )


def _has_book_coverage(
    conn: sqlite3.Connection,
    *,
    token_id: str,
    start: datetime,
    end: datetime,
) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM books
        WHERE token_id = ?
          AND snapshot_at >= ?
          AND snapshot_at <= ?
        LIMIT 1
        """,
        (token_id, _sqlite_dt(start), _sqlite_dt(end)),
    ).fetchone()
    return row is not None


def _first_fill(
    conn: sqlite3.Connection,
    order: OrderRow,
    *,
    ttl_sec: float,
    limit_price: Decimal,
) -> tuple[datetime, Decimal, Decimal] | None:
    end = order.placed_at + timedelta(seconds=ttl_sec)
    for snapshot_at, bids_raw, asks_raw in _book_rows(
        conn, token_id=order.token_id, start=order.placed_at, end=end
    ):
        ts = _parse_dt(str(snapshot_at))
        if order.side == "SELL":
            best = _best_bid(bids_raw)
            crosses = best is not None and best >= limit_price
            levels = [(p, s) for p, s in _levels(bids_raw) if p >= limit_price]
        else:
            best = _best_ask(asks_raw)
            crosses = best is not None and best <= limit_price
            levels = [(p, s) for p, s in _levels(asks_raw) if p <= limit_price]
        if crosses:
            depth_notional = sum(price * size for price, size in levels)
            return ts, limit_price, depth_notional
    return None


def _mid_after(
    conn: sqlite3.Connection,
    *,
    token_id: str,
    fill_ts: datetime,
    horizon_sec: float,
) -> Decimal | None:
    target = fill_ts + timedelta(seconds=horizon_sec)
    row = conn.execute(
        """
        SELECT bids, asks
        FROM books
        WHERE token_id = ?
          AND snapshot_at >= ?
        ORDER BY snapshot_at
        LIMIT 1
        """,
        (token_id, _sqlite_dt(target)),
    ).fetchone()
    if row is None:
        return None
    return _midpoint(row[0], row[1])


def _scenario_label(ttl: float, offset: Decimal) -> str:
    return f"ttl={int(ttl)}s offset={offset}"


def run_autopsy(
    db_path: Path,
    *,
    bot_id: str,
    lookback_hours: float,
    ttls: list[float],
    offsets: list[Decimal],
    baseline_offset: Decimal,
    adverse_horizons: list[float],
) -> dict:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        orders = _fetch_orders(conn, bot_id=bot_id, lookback_hours=lookback_hours)
        scenarios: dict[str, dict] = {}
        for ttl in ttls:
            for offset in offsets:
                label = _scenario_label(ttl, offset)
                attempted = 0
                book_covered = 0
                filled = 0
                depth_samples = 0
                capacity_covered = {str(int(target)): 0 for target in CAPACITY_TARGETS_USD}
                depth_notional_values: list[Decimal] = []
                fill_delays: list[float] = []
                adverse_by_horizon = {
                    str(int(h)): {"measured": 0, "adverse": 0}
                    for h in adverse_horizons
                }
                delta = baseline_offset - offset
                for order in orders:
                    attempted += 1
                    limit = max(Decimal("0.001"), min(Decimal("0.99"), order.price + delta))
                    has_book = _has_book_coverage(
                        conn,
                        token_id=order.token_id,
                        start=order.placed_at,
                        end=order.placed_at + timedelta(seconds=ttl),
                    )
                    if has_book:
                        book_covered += 1
                    fill = _first_fill(conn, order, ttl_sec=ttl, limit_price=limit)
                    if fill is None:
                        continue
                    filled += 1
                    fill_ts, fill_price, depth_notional = fill
                    fill_delays.append((fill_ts - order.placed_at).total_seconds())
                    depth_samples += 1
                    depth_notional_values.append(depth_notional)
                    for target in CAPACITY_TARGETS_USD:
                        if depth_notional >= Decimal(str(target)):
                            capacity_covered[str(int(target))] += 1
                    for horizon in adverse_horizons:
                        mid = _mid_after(
                            conn,
                            token_id=order.token_id,
                            fill_ts=fill_ts,
                            horizon_sec=horizon,
                        )
                        bucket = adverse_by_horizon[str(int(horizon))]
                        if mid is None:
                            continue
                        bucket["measured"] += 1
                        adverse = mid > fill_price if order.side == "SELL" else mid < fill_price
                        if adverse:
                            bucket["adverse"] += 1
                scenarios[label] = {
                    "ttl_sec": ttl,
                    "maker_offset": str(offset),
                    "attempted": attempted,
                    "orders_with_book_coverage": book_covered,
                    "book_coverage_rate": round(book_covered / attempted, 4) if attempted else 0.0,
                    "would_fill": filled,
                    "fill_rate": round(filled / attempted, 4) if attempted else 0.0,
                    "median_fill_delay_sec": round(median(fill_delays), 2) if fill_delays else None,
                    "capacity": {
                        "samples": depth_samples,
                        "average_depth_notional": (
                            round(float(sum(depth_notional_values) / len(depth_notional_values)), 4)
                            if depth_notional_values
                            else 0.0
                        ),
                        "targets_usd": {
                            key: {
                                "covered": covered,
                                "total": depth_samples,
                                "coverage_pct": (
                                    round(covered / depth_samples * 100, 2)
                                    if depth_samples
                                    else 0.0
                                ),
                            }
                            for key, covered in capacity_covered.items()
                        },
                    },
                    "adverse": {
                        h: {
                            **v,
                            "rate": (
                                round(v["adverse"] / v["measured"], 4)
                                if v["measured"]
                                else None
                            ),
                        }
                        for h, v in adverse_by_horizon.items()
                    },
                }
        status_counts: dict[str, int] = {}
        for order in orders:
            status_counts[order.status] = status_counts.get(order.status, 0) + 1
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "db_path": str(db_path),
            "bot_id": bot_id,
            "lookback_hours": lookback_hours,
            "orders_seen": len(orders),
            "status_counts": status_counts,
            "baseline_offset": str(baseline_offset),
            "scenarios": scenarios,
        }
    finally:
        conn.close()


def write_markdown(report: dict, out_path: Path) -> None:
    lines = [
        "# Bot E Cancel Autopsy",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Orders seen: `{report['orders_seen']}`",
        f"Status counts: `{report['status_counts']}`",
        "",
        "| Scenario | Would fill | Fill rate | Median fill delay | "
        "$25 depth | $50 depth | 30s adverse | 60s adverse | 300s adverse |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in report["scenarios"].items():
        def fmt_adv(key: str, adverse: dict = row["adverse"]) -> str:
            item = adverse.get(key, {})
            if item.get("rate") is None:
                return "n/a"
            return f"{item['adverse']}/{item['measured']} ({item['rate']:.1%})"

        delay = row["median_fill_delay_sec"]
        delay_text = "n/a" if delay is None else f"{delay:.0f}s"
        capacity = row.get("capacity") or {}
        targets = capacity.get("targets_usd") or {}
        cap25 = targets.get("25") or {}
        cap50 = targets.get("50") or {}
        lines.append(
            f"| `{label}` | {row['would_fill']}/{row['attempted']} | "
            f"{row['fill_rate']:.1%} "
            f"(book {row['orders_with_book_coverage']}/{row['attempted']}) | "
            f"{delay_text} | {cap25.get('covered', 0)}/{cap25.get('total', 0)} | "
            f"{cap50.get('covered', 0)}/{cap50.get('total', 0)} | {fmt_adv('30')} | "
            f"{fmt_adv('60')} | {fmt_adv('300')} |"
        )
    lines.append("")
    lines.append(
        "Interpretation: this report is an execution autopsy only. It estimates "
        "paper fill opportunity from recorded books; it does not prove strategy EV."
    )
    out_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--bot-id", default="bot_e")
    parser.add_argument("--lookback-hours", type=float, default=24.0)
    parser.add_argument("--ttl", type=float, action="append", default=[300.0, 600.0, 900.0])
    parser.add_argument(
        "--offset",
        type=Decimal,
        action="append",
        default=[Decimal("0.001"), Decimal("0.000"), Decimal("-0.001")],
        help="Candidate maker offset. Negative means one tick more aggressive than touch.",
    )
    parser.add_argument("--baseline-offset", type=Decimal, default=Decimal("0.001"))
    parser.add_argument("--horizon", type=float, action="append", default=[30.0, 60.0, 300.0])
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    report = run_autopsy(
        args.db,
        bot_id=args.bot_id,
        lookback_hours=args.lookback_hours,
        ttls=args.ttl,
        offsets=args.offset,
        baseline_offset=args.baseline_offset,
        adverse_horizons=args.horizon,
    )
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_markdown(report, args.out_md)
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_md}")


if __name__ == "__main__":
    main()
