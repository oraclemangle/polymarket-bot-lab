#!/usr/bin/env python3
"""Read-only QuantStats tearsheet adapter for Longshot bot ledgers.

This script converts closed realised PnL into period returns for analytics
only. It never places orders, mutates SQLite rows, reads secrets, or changes
service state. Longshot trade-level gates remain canonical.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import random
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("data/main.db")
DEFAULT_OUT_DIR = Path("docs/reports")
PERIODS_PER_YEAR = {"daily": 365, "weekly": 52, "monthly": 12}


@dataclass(frozen=True)
class RealisedEvent:
    ts: datetime
    bot_id: str
    source: str
    condition_id: str
    token_id: str
    pnl_usd: Decimal
    entry_cost_usd: Decimal


@dataclass(frozen=True)
class PeriodReturn:
    period_start: date
    pnl_usd: Decimal
    entry_cost_usd: Decimal
    return_pct: Decimal
    events: int


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"DB not found: {path}")
    conn = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _has_table(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _decimal(value: object, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _parse_date_arg(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = _parse_dt(value)
    if parsed is not None:
        return parsed
    try:
        return datetime.fromisoformat(f"{value}T00:00:00+00:00")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid datetime/date: {value}") from exc


def _normalize_side(side: object) -> str:
    text = str(side or "").upper()
    if text.startswith(("BUY_", "BUY-")):
        return "BUY"
    if text.startswith(("SELL_", "SELL-")):
        return "SELL"
    return text


def _payload(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if raw is None:
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _in_window(ts: datetime, since: datetime | None, until: datetime | None) -> bool:
    if since is not None and ts < since:
        return False
    return not (until is not None and ts >= until)


def _trade_cashflows(
    conn: sqlite3.Connection,
    bot_id: str,
    since: datetime | None,
    until: datetime | None,
) -> tuple[list[RealisedEvent], dict[str, int]]:
    if not _has_table(conn, "trades"):
        return [], {"trade_rows": 0, "orphan_sells": 0}

    rows = conn.execute(
        """
        SELECT trade_id, bot_id, condition_id, token_id, side, price, size,
               fee_usd, filled_at
        FROM trades
        WHERE bot_id = ?
        ORDER BY filled_at, trade_id
        """,
        (bot_id,),
    ).fetchall()
    lots: dict[str, list[dict[str, Decimal]]] = {}
    realised: list[RealisedEvent] = []
    orphan_sells = 0
    for row in rows:
        ts = _parse_dt(row["filled_at"])
        if ts is None:
            continue
        side = _normalize_side(row["side"])
        token_id = str(row["token_id"] or "")
        condition_id = str(row["condition_id"] or "")
        price = _decimal(row["price"])
        size = _decimal(row["size"])
        fee = _decimal(row["fee_usd"])
        if size <= 0:
            continue
        if side == "BUY":
            lots.setdefault(token_id, []).append(
                {
                    "size": size,
                    "cost": (price * size) + fee,
                }
            )
            continue
        if side != "SELL":
            continue
        remaining = size
        for lot in list(lots.get(token_id, [])):
            if remaining <= 0:
                break
            lot_size = lot["size"]
            matched = min(lot_size, remaining)
            matched_cost = lot["cost"] * (matched / lot_size)
            fee_share = fee * (matched / size)
            proceeds = (price * matched) - fee_share
            if _in_window(ts, since, until):
                realised.append(
                    RealisedEvent(
                        ts=ts,
                        bot_id=bot_id,
                        source="trade_fifo",
                        condition_id=condition_id,
                        token_id=token_id,
                        pnl_usd=proceeds - matched_cost,
                        entry_cost_usd=matched_cost,
                    )
                )
            lot["size"] = lot_size - matched
            lot["cost"] -= matched_cost
            remaining -= matched
            if lot["size"] <= 0:
                lots[token_id].pop(0)
        if remaining > 0:
            orphan_sells += 1
    return realised, {"trade_rows": len(rows), "orphan_sells": orphan_sells}


def _redeem_cashflows(
    conn: sqlite3.Connection,
    bot_id: str,
    since: datetime | None,
    until: datetime | None,
) -> list[RealisedEvent]:
    if not _has_table(conn, "events"):
        return []
    rows = conn.execute(
        """
        SELECT payload, created_at
        FROM events
        WHERE bot_id = ?
          AND event_type = 'portfolio.redeem'
        ORDER BY created_at, id
        """,
        (bot_id,),
    ).fetchall()
    out: list[RealisedEvent] = []
    for row in rows:
        ts = _parse_dt(row["created_at"])
        if ts is None or not _in_window(ts, since, until):
            continue
        payload = _payload(row["payload"])
        out.append(
            RealisedEvent(
                ts=ts,
                bot_id=bot_id,
                source="portfolio_redeem",
                condition_id=str(payload.get("condition_id") or ""),
                token_id=str(payload.get("token_id") or ""),
                pnl_usd=_decimal(payload.get("realised_usd")),
                entry_cost_usd=_decimal(payload.get("cost_basis")),
            )
        )
    return out


def load_realised_events(
    db_path: Path,
    bot_id: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> tuple[list[RealisedEvent], dict[str, int]]:
    conn = _connect_ro(db_path)
    try:
        trade_events, diagnostics = _trade_cashflows(conn, bot_id, since, until)
        redeem_events = _redeem_cashflows(conn, bot_id, since, until)
    finally:
        conn.close()
    events = sorted(trade_events + redeem_events, key=lambda event: (event.ts, event.source))
    diagnostics["redeem_events"] = len(redeem_events)
    diagnostics["realised_events"] = len(events)
    return events, diagnostics


def _period_start(dt: datetime, period: str) -> date:
    d = dt.date()
    if period == "daily":
        return d
    if period == "weekly":
        return date.fromisocalendar(d.isocalendar().year, d.isocalendar().week, 1)
    if period == "monthly":
        return date(d.year, d.month, 1)
    raise ValueError(f"unknown period: {period}")


def infer_capital_base(events: list[RealisedEvent], explicit: Decimal | None) -> tuple[Decimal, str]:
    if explicit is not None:
        if explicit <= 0:
            raise ValueError("--capital-base-usd must be positive")
        return explicit, "explicit"
    closed_cost = sum((event.entry_cost_usd for event in events), Decimal("0"))
    if closed_cost > 0:
        return closed_cost, "closed_entry_cost_fallback"
    return Decimal("1"), "no_closed_cost_floor_1_usd"


def aggregate_period_returns(
    events: list[RealisedEvent],
    *,
    period: str,
    capital_base_usd: Decimal,
) -> list[PeriodReturn]:
    buckets: dict[date, dict[str, Decimal | int]] = {}
    for event in events:
        key = _period_start(event.ts, period)
        bucket = buckets.setdefault(
            key,
            {"pnl": Decimal("0"), "cost": Decimal("0"), "events": 0},
        )
        bucket["pnl"] = Decimal(bucket["pnl"]) + event.pnl_usd
        bucket["cost"] = Decimal(bucket["cost"]) + event.entry_cost_usd
        bucket["events"] = int(bucket["events"]) + 1
    return [
        PeriodReturn(
            period_start=key,
            pnl_usd=Decimal(bucket["pnl"]),
            entry_cost_usd=Decimal(bucket["cost"]),
            return_pct=Decimal(bucket["pnl"]) / capital_base_usd,
            events=int(bucket["events"]),
        )
        for key, bucket in sorted(buckets.items())
    ]


def _max_drawdown(returns: list[Decimal]) -> Decimal | None:
    if not returns:
        return None
    equity = Decimal("1")
    peak = Decimal("1")
    worst = Decimal("0")
    for ret in returns:
        equity *= Decimal("1") + ret
        if equity > peak:
            peak = equity
        drawdown = (equity / peak) - Decimal("1")
        if drawdown < worst:
            worst = drawdown
    return worst


def _mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def _stdev(values: list[Decimal]) -> Decimal | None:
    if len(values) < 2:
        return None
    mean = _mean(values)
    if mean is None:
        return None
    variance = sum(((value - mean) ** 2 for value in values), Decimal("0")) / Decimal(
        len(values) - 1
    )
    return variance.sqrt()


def _sqrt_decimal(value: int) -> Decimal:
    return Decimal(str(value**0.5))


def _sharpe(returns: list[Decimal], periods_per_year: int) -> Decimal | None:
    mean = _mean(returns)
    stdev = _stdev(returns)
    if mean is None or stdev is None or stdev == 0:
        return None
    return (mean / stdev) * _sqrt_decimal(periods_per_year)


def _sortino(returns: list[Decimal], periods_per_year: int) -> Decimal | None:
    mean = _mean(returns)
    downside = [ret for ret in returns if ret < 0]
    downside_dev = _stdev(downside)
    if mean is None or downside_dev is None or downside_dev == 0:
        return None
    return (mean / downside_dev) * _sqrt_decimal(periods_per_year)


def _cagr(returns: list[Decimal], periods_per_year: int) -> Decimal | None:
    if not returns:
        return None
    equity = Decimal("1")
    for ret in returns:
        equity *= Decimal("1") + ret
    if equity <= 0:
        return Decimal("-1")
    years = Decimal(len(returns)) / Decimal(periods_per_year)
    if years <= 0:
        return None
    return Decimal(str(float(equity) ** (1 / float(years)) - 1))


def _calmar(returns: list[Decimal], periods_per_year: int) -> Decimal | None:
    cagr = _cagr(returns, periods_per_year)
    max_dd = _max_drawdown(returns)
    if cagr is None or max_dd is None or max_dd == 0:
        return None
    return cagr / abs(max_dd)


def _monthly_returns(period_returns: list[PeriodReturn]) -> dict[str, float]:
    buckets: dict[str, Decimal] = {}
    for row in period_returns:
        month = f"{row.period_start.year:04d}-{row.period_start.month:02d}"
        buckets[month] = (buckets.get(month, Decimal("1")) * (Decimal("1") + row.return_pct))
    return {month: round(float(value - Decimal("1")), 6) for month, value in sorted(buckets.items())}


def monte_carlo_bust_probability(
    returns: list[Decimal],
    *,
    simulations: int,
    bust_drawdown_pct: Decimal,
    seed: int,
) -> Decimal | None:
    if not returns or simulations <= 0:
        return None
    floor = Decimal("1") - bust_drawdown_pct
    rng = random.Random(seed)
    busts = 0
    for _ in range(simulations):
        equity = Decimal("1")
        for _ in returns:
            equity *= Decimal("1") + rng.choice(returns)
            if equity <= floor:
                busts += 1
                break
    return Decimal(busts) / Decimal(simulations)


def _float_or_none(value: Decimal | None) -> float | None:
    return round(float(value), 6) if value is not None else None


def build_summary(
    *,
    bot_id: str,
    events: list[RealisedEvent],
    diagnostics: dict[str, int],
    period: str,
    capital_base_usd: Decimal,
    capital_base_source: str,
    simulations: int,
    bust_drawdown_pct: Decimal,
    seed: int,
) -> tuple[dict[str, Any], list[PeriodReturn]]:
    periods = aggregate_period_returns(events, period=period, capital_base_usd=capital_base_usd)
    returns = [row.return_pct for row in periods]
    periods_per_year = PERIODS_PER_YEAR[period]
    total_pnl = sum((event.pnl_usd for event in events), Decimal("0"))
    total_cost = sum((event.entry_cost_usd for event in events), Decimal("0"))
    wins = sum(1 for event in events if event.pnl_usd > 0)
    max_dd = _max_drawdown(returns)
    mc_bust = monte_carlo_bust_probability(
        returns,
        simulations=simulations,
        bust_drawdown_pct=bust_drawdown_pct,
        seed=seed,
    )
    summary = {
        "bot_id": bot_id,
        "period": period,
        "capital_base_usd": round(float(capital_base_usd), 6),
        "capital_base_source": capital_base_source,
        "return_semantics": (
            "period realised PnL divided by capital_base_usd; use trade-level "
            "reports for canonical ROI gates"
        ),
        "realised_events": len(events),
        "winning_realised_events": wins,
        "event_win_rate_pct": round((wins / len(events)) * 100, 2) if events else None,
        "total_realised_pnl_usd": round(float(total_pnl), 6),
        "total_closed_entry_cost_usd": round(float(total_cost), 6),
        "trade_level_roi_pct": round(float(total_pnl / total_cost) * 100, 4)
        if total_cost > 0
        else None,
        "period_count": len(periods),
        "max_drawdown_pct": _float_or_none(max_dd * Decimal("100") if max_dd is not None else None),
        "sharpe": _float_or_none(_sharpe(returns, periods_per_year)),
        "sortino": _float_or_none(_sortino(returns, periods_per_year)),
        "calmar": _float_or_none(_calmar(returns, periods_per_year)),
        "risk_of_ruin_pct": _float_or_none(
            mc_bust * Decimal("100") if mc_bust is not None else None
        ),
        "risk_of_ruin_method": "bootstrap_period_return_resample",
        "monte_carlo_bust_probability_pct": _float_or_none(
            mc_bust * Decimal("100") if mc_bust is not None else None
        ),
        "monte_carlo_simulations": simulations,
        "bust_drawdown_pct": round(float(bust_drawdown_pct * Decimal("100")), 4),
        "monthly_returns": _monthly_returns(periods),
        "diagnostics": diagnostics,
        "caveats": [
            "QuantStats metrics are period-return analytics, not trade-level gates.",
            "Open positions and open orders are intentionally excluded.",
            "Use an explicit --capital-base-usd for wallet-level portfolio returns.",
        ],
    }
    return summary, periods


def _import_quantstats() -> tuple[Any | None, Any | None]:
    try:
        import pandas as pd  # type: ignore[import-not-found]
        import quantstats as qs  # type: ignore[import-not-found]
    except ImportError:
        return None, None
    return pd, qs


def _series_from_periods(periods: list[PeriodReturn], pd: Any) -> Any:
    data = {row.period_start.isoformat(): float(row.return_pct) for row in periods}
    series = pd.Series(data, dtype="float64")
    series.index = pd.to_datetime(series.index)
    return series.sort_index()


def _load_benchmark(path: Path | None, pd: Any) -> Any | None:
    if path is None:
        return None
    frame = pd.read_csv(path)
    if "date" not in frame.columns or "return" not in frame.columns:
        raise ValueError("benchmark CSV must have date,return columns")
    series = pd.Series(frame["return"].astype(float).values, index=pd.to_datetime(frame["date"]))
    return series.sort_index()


def _write_fallback_html(path: Path, summary: dict[str, Any], periods: list[PeriodReturn]) -> None:
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(row.period_start.isoformat())}</td>"
        f"<td>{float(row.pnl_usd):+.4f}</td>"
        f"<td>{float(row.return_pct) * 100:+.4f}%</td>"
        f"<td>{row.events}</td>"
        "</tr>"
        for row in periods
    )
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Longshot Realised Returns - {html.escape(str(summary["bot_id"]))}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 32px; line-height: 1.4; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 16px; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    code {{ background: #f4f4f4; padding: 2px 4px; }}
  </style>
</head>
<body>
  <h1>Longshot Realised Returns - {html.escape(str(summary["bot_id"]))}</h1>
  <p><strong>Fallback report:</strong> install <code>.[analytics]</code> to render the full QuantStats tearsheet.</p>
  <p>Total realised PnL: {summary["total_realised_pnl_usd"]:+.4f} USD. Max drawdown: {summary["max_drawdown_pct"]}%. Sharpe: {summary["sharpe"]}.</p>
  <table>
    <thead><tr><th>Period</th><th>PnL USD</th><th>Return</th><th>Events</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>
"""
    path.write_text(body, encoding="utf-8")


def write_artifacts(
    *,
    summary: dict[str, Any],
    periods: list[PeriodReturn],
    out_dir: Path,
    benchmark_csv: Path | None,
    require_quantstats: bool,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_bot = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in summary["bot_id"])
    stem = f"quantstats-{safe_bot}-{summary['period']}-{stamp}"
    json_path = out_dir / f"{stem}.json"
    html_path = out_dir / f"{stem}.html"

    pd, qs = _import_quantstats()
    summary["quantstats_available"] = pd is not None and qs is not None
    summary["benchmark_enabled"] = benchmark_csv is not None
    if qs is None or pd is None:
        if require_quantstats:
            raise RuntimeError("quantstats extra missing; install with `pip install -e .[analytics]`")
        _write_fallback_html(html_path, summary, periods)
    else:
        returns = _series_from_periods(periods, pd)
        benchmark = _load_benchmark(benchmark_csv, pd)
        if returns.empty:
            _write_fallback_html(html_path, summary, periods)
        else:
            qs.reports.html(
                returns,
                benchmark=benchmark,
                output=str(html_path),
                title=f"Longshot {summary['bot_id']} realised returns",
            )

    summary["artifacts"] = {"json": str(json_path), "html": str(html_path)}
    json_path.write_text(json.dumps(_jsonable(summary), indent=2, sort_keys=True) + "\n")
    return json_path, html_path


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def write_period_csv(path: Path, periods: list[PeriodReturn]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["period_start", "pnl_usd", "entry_cost_usd", "return_pct", "events"],
        )
        writer.writeheader()
        for row in periods:
            writer.writerow(
                {
                    "period_start": row.period_start.isoformat(),
                    "pnl_usd": str(row.pnl_usd),
                    "entry_cost_usd": str(row.entry_cost_usd),
                    "return_pct": str(row.return_pct),
                    "events": row.events,
                }
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bot-id", required=True, help="Bot id to report, e.g. bot_d_live_probe")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite main.db path")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory for HTML/JSON artifacts",
    )
    parser.add_argument(
        "--period",
        choices=sorted(PERIODS_PER_YEAR),
        default="daily",
        help="Return aggregation period",
    )
    parser.add_argument("--since", type=_parse_date_arg, help="Inclusive UTC start date/time")
    parser.add_argument("--until", type=_parse_date_arg, help="Exclusive UTC end date/time")
    parser.add_argument(
        "--capital-base-usd",
        type=lambda value: _decimal(value),
        help="Portfolio capital denominator for period returns",
    )
    parser.add_argument(
        "--benchmark-csv",
        type=Path,
        help="Optional local CSV benchmark with date,return columns; disabled by default",
    )
    parser.add_argument(
        "--monte-carlo-simulations",
        type=int,
        default=1000,
        help="Bootstrap paths for bust probability",
    )
    parser.add_argument(
        "--bust-drawdown-pct",
        type=lambda value: _decimal(value) / Decimal("100"),
        default=Decimal("0.50"),
        help="Drawdown threshold for bust probability, in percent",
    )
    parser.add_argument("--seed", type=int, default=184, help="Bootstrap RNG seed")
    parser.add_argument(
        "--require-quantstats",
        action="store_true",
        help="Fail instead of writing fallback HTML when quantstats is not installed",
    )
    parser.add_argument(
        "--period-csv",
        action="store_true",
        help="Also write the period return series as CSV",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        events, diagnostics = load_realised_events(
            args.db,
            args.bot_id,
            since=args.since,
            until=args.until,
        )
        capital_base, capital_source = infer_capital_base(events, args.capital_base_usd)
        summary, periods = build_summary(
            bot_id=args.bot_id,
            events=events,
            diagnostics=diagnostics,
            period=args.period,
            capital_base_usd=capital_base,
            capital_base_source=capital_source,
            simulations=args.monte_carlo_simulations,
            bust_drawdown_pct=args.bust_drawdown_pct,
            seed=args.seed,
        )
        json_path, html_path = write_artifacts(
            summary=summary,
            periods=periods,
            out_dir=args.out_dir,
            benchmark_csv=args.benchmark_csv,
            require_quantstats=args.require_quantstats,
        )
        if args.period_csv:
            write_period_csv(json_path.with_suffix(".periods.csv"), periods)
        print(json.dumps({"json": str(json_path), "html": str(html_path)}, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"quantstats_bot_tearsheet: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
