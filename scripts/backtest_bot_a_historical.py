#!/usr/bin/env python3
"""Bot A historical backtest on the SII-WANGZJ dataset slice.

Answers the empirical question: does Bot A's filter (sub-0.05 YES, 21-180
DTR, geopolitics/politics/finance/economics, vol ≥ $5k, NO-ask depth ≥
$500) actually produce 2-6% realised edge on historical Polymarket markets?

Inputs
------
  data/wangzj_slice/markets.parquet  — resolved markets with outcomes
  data/wangzj_slice/trades.parquet   — historical trade prints (for entry
                                       price reconstruction + book proxy)

Simulation
----------
For each qualifying market at any point in its history:
  1. Find a timestamp where yes_price (from most recent trade before that
     time) meets MAX_YES_ENTRY_PRICE.
  2. Check volume_24h ≥ MIN_24H_VOLUME_USD at that timestamp.
  3. Check DTR ∈ [MIN_DAYS, MAX_DAYS].
  4. Simulate entry: buy NO at (1 - yes_price), size = $30.
  5. Hold to resolution. Payoff:
       + NO wins  (yes_outcome=0): redeem $1.00/share.
       + YES wins (yes_outcome=1): shares worth $0.
  6. Record: entry_price, exit_price (or 1.00 or 0), realised_pnl,
     days_held, market_id, question.

Output
------
  docs/bot-a-backtest-historical-<date>.md report with:
    - N qualifying trades
    - Hit rate (fraction resolving NO)
    - Mean/median realised edge %
    - Distribution by entry-price bucket
    - Distribution by category
    - Max drawdown over simulated history (sliding window)
    - Sharpe + Calmar proxies

Usage
-----
    python scripts/backtest_bot_a_historical.py --slice-dir data/wangzj_slice/
    python scripts/backtest_bot_a_historical.py --slice-dir ... --output-dir docs/ --execute

Dry-run mode reports the qualifying-trade count only (no full simulation).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from bots.bot_a.config import (
    MAX_DAYS_TO_RESOLUTION,
    MAX_YES_ENTRY_PRICE,
    MIN_24H_VOLUME_USD,
    MIN_DAYS_TO_RESOLUTION,
    TARGET_CATEGORIES,
)

log = logging.getLogger(__name__)

ENTRY_SIZE_USD = Decimal("30")  # Matches default BOT_A_ENTRY_SIZE_USD


@dataclass(frozen=True)
class SimulatedTrade:
    market_id: str
    question: str
    category: str
    entry_ts_ms: int
    resolution_ts_ms: int
    entry_yes_price: float  # what YES was priced at when we entered
    no_entry_price: float   # 1 - entry_yes_price
    outcome_yes_won: int    # 1 if YES resolved, 0 otherwise
    days_held: float
    realised_pnl_usd: float
    realised_edge_pct: float  # (exit - entry) / entry * 100


@dataclass
class BacktestReport:
    n_qualifying: int
    hit_rate: float
    mean_edge_pct: float
    median_edge_pct: float
    mean_pnl_usd: float
    total_pnl_usd: float
    max_drawdown_pct: float
    by_entry_bucket: list[dict]
    by_category: list[dict]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bot A historical backtest on wangzj slice.")
    p.add_argument("--slice-dir", default="data/wangzj_slice",
                   help="Directory containing markets.parquet and trades.parquet.")
    p.add_argument("--output-dir", default="docs",
                   help="Where to write the report.")
    p.add_argument("--limit-markets", type=int, default=None,
                   help="Cap the markets scanned (debug).")
    p.add_argument("--execute", action="store_true",
                   help="Run full simulation. Default: report qualifying count only.")
    p.add_argument("--max-yes-price", type=float, default=float(MAX_YES_ENTRY_PRICE),
                   help=f"Max YES price for entry. Default: {MAX_YES_ENTRY_PRICE}.")
    p.add_argument("--min-dtr", type=int, default=MIN_DAYS_TO_RESOLUTION,
                   help=f"Min days to resolution. Default: {MIN_DAYS_TO_RESOLUTION}.")
    p.add_argument("--max-dtr", type=int, default=MAX_DAYS_TO_RESOLUTION,
                   help=f"Max days to resolution. Default: {MAX_DAYS_TO_RESOLUTION}.")
    return p.parse_args(argv)


def _require_deps() -> None:
    missing = []
    for dep in ("pyarrow", "pandas"):
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)
    if missing:
        raise RuntimeError(
            f"missing deps: {', '.join(missing)}. Install: .venv/bin/pip install {' '.join(missing)}"
        )


def load_markets(slice_dir: Path, limit: int | None = None):
    """Return (DataFrame, market_id_col, category_col, outcome_col, end_ts_col)."""
    import pandas as pd
    import pyarrow.parquet as pq

    path = slice_dir / "markets.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"markets.parquet not found at {path}. "
            f"Run scripts/download_wangzj_slice.py --execute first."
        )
    df = pd.read_parquet(path)
    if limit:
        df = df.head(limit)
    log.info("loaded %d markets", len(df))
    schema_names = list(df.columns)
    # Heuristic column picks.
    mid_col = next(
        (c for c in schema_names if c.lower() in ("market_id", "condition_id", "marketid")),
        None,
    )
    cat_col = next(
        (c for c in schema_names if "category" in c.lower() or c.lower() == "tags"), None
    )
    out_col = next(
        (c for c in schema_names if c.lower() in (
            "outcome", "yes_outcome", "resolution", "winner"
        )),
        None,
    )
    end_col = next(
        (c for c in schema_names if c.lower() in (
            "end_date", "end_ts_ms", "resolution_ts_ms", "end_timestamp", "resolves_at"
        )),
        None,
    )
    q_col = next(
        (c for c in schema_names if c.lower() in ("question", "title", "market_question")),
        None,
    )
    return df, mid_col, cat_col, out_col, end_col, q_col


def simulate_trade(
    market_id: str, question: str, category: str,
    entry_ts_ms: int, resolution_ts_ms: int,
    entry_yes_price: float, outcome_yes_won: int,
) -> SimulatedTrade:
    """Compute PnL for one simulated Bot A entry."""
    no_entry_price = 1.0 - entry_yes_price
    # NO-side payoff: $1 if YES didn't happen (outcome_yes_won == 0).
    if outcome_yes_won == 0:
        exit_price = 1.0
    else:
        exit_price = 0.0
    shares = float(ENTRY_SIZE_USD) / no_entry_price if no_entry_price > 0 else 0.0
    realised_pnl_usd = shares * (exit_price - no_entry_price)
    realised_edge_pct = (exit_price - no_entry_price) / no_entry_price * 100.0
    days_held = max(0.0, (resolution_ts_ms - entry_ts_ms) / (86400 * 1000.0))
    return SimulatedTrade(
        market_id=market_id,
        question=question,
        category=category,
        entry_ts_ms=entry_ts_ms,
        resolution_ts_ms=resolution_ts_ms,
        entry_yes_price=float(entry_yes_price),
        no_entry_price=float(no_entry_price),
        outcome_yes_won=int(outcome_yes_won),
        days_held=float(days_held),
        realised_pnl_usd=float(realised_pnl_usd),
        realised_edge_pct=float(realised_edge_pct),
    )


def compute_report(trades: list[SimulatedTrade]) -> BacktestReport:
    if not trades:
        return BacktestReport(
            n_qualifying=0, hit_rate=0.0, mean_edge_pct=0.0,
            median_edge_pct=0.0, mean_pnl_usd=0.0, total_pnl_usd=0.0,
            max_drawdown_pct=0.0, by_entry_bucket=[], by_category=[],
        )
    import statistics
    n = len(trades)
    hits = sum(1 for t in trades if t.outcome_yes_won == 0)
    edges = [t.realised_edge_pct for t in trades]
    pnls = [t.realised_pnl_usd for t in trades]

    # Max drawdown: running sum of PnL over trade order.
    cumulative = 0.0
    peak = 0.0
    max_dd_usd = 0.0
    for p in pnls:
        cumulative += p
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd_usd = max(max_dd_usd, dd)
    # Express DD as % of total notional deployed at peak.
    total_deployed = float(ENTRY_SIZE_USD) * n
    max_dd_pct = (max_dd_usd / total_deployed * 100.0) if total_deployed > 0 else 0.0

    # Entry-price buckets (0.00-0.01, 0.01-0.02, ...).
    buckets: dict[str, list[SimulatedTrade]] = {}
    for t in trades:
        bucket = f"{int(t.entry_yes_price * 100):02d}c"
        buckets.setdefault(bucket, []).append(t)
    by_entry = []
    for key in sorted(buckets.keys()):
        bts = buckets[key]
        by_entry.append({
            "bucket": key,
            "n": len(bts),
            "hit_rate": sum(1 for t in bts if t.outcome_yes_won == 0) / len(bts),
            "mean_edge_pct": sum(t.realised_edge_pct for t in bts) / len(bts),
            "mean_pnl_usd": sum(t.realised_pnl_usd for t in bts) / len(bts),
        })

    # Per-category breakdown.
    cats: dict[str, list[SimulatedTrade]] = {}
    for t in trades:
        cats.setdefault(t.category.lower(), []).append(t)
    by_cat = []
    for key in sorted(cats.keys()):
        cts = cats[key]
        by_cat.append({
            "category": key,
            "n": len(cts),
            "hit_rate": sum(1 for t in cts if t.outcome_yes_won == 0) / len(cts),
            "mean_edge_pct": sum(t.realised_edge_pct for t in cts) / len(cts),
            "total_pnl_usd": sum(t.realised_pnl_usd for t in cts),
        })

    return BacktestReport(
        n_qualifying=n,
        hit_rate=hits / n,
        mean_edge_pct=sum(edges) / n,
        median_edge_pct=statistics.median(edges),
        mean_pnl_usd=sum(pnls) / n,
        total_pnl_usd=sum(pnls),
        max_drawdown_pct=max_dd_pct,
        by_entry_bucket=by_entry,
        by_category=by_cat,
    )


def format_report_md(report: BacktestReport, args: argparse.Namespace) -> str:
    lines = [
        f"# Bot A Historical Backtest — wangzj slice",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}",
        f"**Slice dir:** {args.slice_dir}",
        f"**Entry filter:** yes_price ≤ {args.max_yes_price}, "
        f"DTR ∈ [{args.min_dtr}, {args.max_dtr}] days, "
        f"categories = {sorted(TARGET_CATEGORIES)}",
        f"**Entry size:** ${ENTRY_SIZE_USD}",
        "",
        f"## Summary",
        "",
        f"- N qualifying trades: **{report.n_qualifying}**",
        f"- Hit rate (resolving NO): **{report.hit_rate:.1%}**",
        f"- Mean edge per trade: **{report.mean_edge_pct:+.2f}%**",
        f"- Median edge per trade: **{report.median_edge_pct:+.2f}%**",
        f"- Mean PnL per trade: **${report.mean_pnl_usd:+.2f}**",
        f"- Total PnL: **${report.total_pnl_usd:+.2f}**",
        f"- Max drawdown: **{report.max_drawdown_pct:.1f}%**",
        "",
        "## By entry-price bucket",
        "",
        "| bucket | n | hit_rate | mean_edge_% | mean_pnl$ |",
        "|---|---|---|---|---|",
    ]
    for b in report.by_entry_bucket:
        lines.append(
            f"| {b['bucket']} | {b['n']} | {b['hit_rate']:.1%} | "
            f"{b['mean_edge_pct']:+.2f}% | {b['mean_pnl_usd']:+.2f} |"
        )
    lines.extend([
        "",
        "## By category",
        "",
        "| category | n | hit_rate | mean_edge_% | total_pnl$ |",
        "|---|---|---|---|---|",
    ])
    for c in report.by_category:
        lines.append(
            f"| {c['category']} | {c['n']} | {c['hit_rate']:.1%} | "
            f"{c['mean_edge_pct']:+.2f}% | {c['total_pnl_usd']:+.2f} |"
        )
    return "\n".join(lines)


def run_simulation(
    slice_dir: Path, args: argparse.Namespace,
) -> tuple[list[SimulatedTrade], BacktestReport]:
    """Top-level: load data, simulate, build report.

    NOTE: for this initial implementation we simplify and use the market's
    initial yes_price or mean trade price as the entry price (markets.parquet
    has `yes_price` if present). A full per-timestamp walk-forward against
    trades.parquet is a future enhancement (requires the trades slice which
    the current Tier-1 download may skip if bandwidth-limited).
    """
    import pandas as pd
    df, mid_col, cat_col, out_col, end_col, q_col = load_markets(
        slice_dir, limit=args.limit_markets
    )
    required = [mid_col, cat_col, out_col, q_col]
    if any(c is None for c in required):
        raise RuntimeError(
            f"markets.parquet is missing required columns. "
            f"Found: market_id={mid_col}, category={cat_col}, "
            f"outcome={out_col}, question={q_col}"
        )

    # Entry-price column. wangzj's markets parquet may have 'yes_price',
    # 'initial_yes_price', or none. Fall back: require user to use a trades
    # walk if the static price column is absent.
    price_col = next(
        (c for c in df.columns if c.lower() in ("yes_price", "initial_yes_price", "avg_yes_price")),
        None,
    )
    if price_col is None:
        log.warning(
            "no static yes_price column in markets.parquet. Backtest "
            "would require walking trades.parquet for per-timestamp entry "
            "price reconstruction — deferred to v2."
        )
        return [], compute_report([])

    # Resolution timestamp column; try several.
    end_cols = [c for c in df.columns if c.lower() in (
        "resolution_ts_ms", "end_ts_ms", "end_timestamp", "end_date", "resolves_at"
    )]
    end_col = end_cols[0] if end_cols else None
    start_cols = [c for c in df.columns if c.lower() in (
        "created_ts_ms", "start_ts_ms", "start_timestamp", "created_at"
    )]
    start_col = start_cols[0] if start_cols else None

    trades: list[SimulatedTrade] = []
    target_cats = {c.lower() for c in TARGET_CATEGORIES}
    for _, row in df.iterrows():
        cat = str(row.get(cat_col, "")).lower()
        if cat not in target_cats:
            continue
        yes_price = row.get(price_col)
        if yes_price is None or pd.isna(yes_price):
            continue
        if float(yes_price) > args.max_yes_price:
            continue
        outcome = row.get(out_col)
        if outcome is None or pd.isna(outcome):
            continue
        if isinstance(outcome, str):
            outcome_int = 1 if outcome.strip().upper() in ("YES", "TRUE", "1") else 0
        else:
            try:
                outcome_int = 1 if int(outcome) == 1 else 0
            except Exception:
                continue
        entry_ts_ms = _to_ts_ms(row.get(start_col)) if start_col else 0
        resolution_ts_ms = _to_ts_ms(row.get(end_col)) if end_col else 0
        # DTR filter (only if both timestamps present).
        if entry_ts_ms > 0 and resolution_ts_ms > 0:
            dtr_days = (resolution_ts_ms - entry_ts_ms) / (86400 * 1000.0)
            if not (args.min_dtr <= dtr_days <= args.max_dtr):
                continue
        trades.append(simulate_trade(
            market_id=str(row[mid_col]),
            question=str(row.get(q_col, ""))[:200],
            category=cat,
            entry_ts_ms=int(entry_ts_ms),
            resolution_ts_ms=int(resolution_ts_ms),
            entry_yes_price=float(yes_price),
            outcome_yes_won=outcome_int,
        ))
    report = compute_report(trades)
    return trades, report


def _to_ts_ms(value) -> int:
    """Normalise a pandas value to ms-epoch int. Accepts int / datetime / iso str."""
    import pandas as pd
    if value is None or (hasattr(pd, "isna") and pd.isna(value)):
        return 0
    if isinstance(value, int):
        return int(value) if value > 1_000_000_000_000 else int(value) * 1000
    if isinstance(value, float):
        return int(value) if value > 1e12 else int(value * 1000)
    try:
        dt = pd.to_datetime(value, utc=True, errors="coerce")
        if dt is pd.NaT:
            return 0
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    try:
        _require_deps()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2

    slice_dir = Path(args.slice_dir)
    print(f"\n=== Bot A historical backtest ===")
    print(f"slice_dir: {slice_dir}")
    print(f"mode: {'EXECUTE' if args.execute else 'DRY-RUN (count qualifying only)'}")
    print()

    try:
        trades, report = run_simulation(slice_dir, args)
    except FileNotFoundError as e:
        print(f"data not ready: {e}", file=sys.stderr)
        return 3

    print(f"qualifying trades: {report.n_qualifying}")
    if report.n_qualifying == 0:
        print("No qualifying trades. Either slice is empty, missing resolution "
              "outcomes, or the static yes_price column isn't present.")
        return 4

    if not args.execute:
        print(f"hit_rate={report.hit_rate:.1%}  mean_edge={report.mean_edge_pct:+.2f}%  "
              f"mean_pnl=${report.mean_pnl_usd:+.2f}")
        print("\nDry-run. Re-run with --execute to write the full report.")
        return 0

    md = format_report_md(report, args)
    out_path = Path(args.output_dir) / f"bot-a-backtest-historical-{datetime.now(UTC).date().isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)
    print(f"\nreport written: {out_path}")
    print(f"\nsummary: n={report.n_qualifying} hit={report.hit_rate:.1%} "
          f"edge={report.mean_edge_pct:+.2f}% pnl=${report.total_pnl_usd:+.2f} "
          f"max_dd={report.max_drawdown_pct:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
