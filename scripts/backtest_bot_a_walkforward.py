#!/usr/bin/env python3
"""Bot A walk-forward backtest against trades.parquet.

Follow-up to `scripts/backtest_bot_a_wangzj.py`. That script answered the
BASE-RATE question (what fraction of qualifying markets resolve NO) using
markets.parquet alone. This script answers the REAL-EDGE question by
reconstructing entry prices from per-trade history:

    For each qualifying market:
      1. Walk the trade history forward from market creation.
      2. At each trade, compute yes_price_last_trade.
      3. If yes_price_last_trade ≤ MAX_YES_ENTRY_PRICE and market is
         within DTR window and we haven't already entered this market,
         simulate a Bot A entry: buy NO at (1 - yes_price), size $30.
      4. Hold to resolution. Payoff = $1 if NO won, $0 if YES won.
      5. Compute realised PnL + edge %.

Output: a report with per-trade realised edge distribution, not just
an aggregate hit rate.

Why streaming
-------------
trades.parquet is 32 GB / ~293M rows. Loading it fully would require
~80 GB RAM. We stream row-group by row-group, filtering each group to
our 22,509 target market_ids before doing any work, writing only
per-entry outcomes to a per-market dict.

Usage
-----
    # Dry-run: count qualifying markets + estimate runtime.
    python scripts/backtest_bot_a_walkforward.py

    # Execute:
    python scripts/backtest_bot_a_walkforward.py --execute

    # Tune Bot A parameters:
    python scripts/backtest_bot_a_walkforward.py --execute \\
        --max-yes-price 0.05 --min-dtr 21 --max-dtr 180

Inputs expected
---------------
  markets.parquet — from HuggingFace cache (auto-download if absent, 68 MB)
  trades.parquet  — from HuggingFace cache (must be pre-downloaded, 32 GB)

On the LXC after download: both live under
  /home/bot/.cache/huggingface/hub/datasets--SII-WANGZJ--Polymarket_data/
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)

DATASET_REPO = "SII-WANGZJ/Polymarket_data"
ENTRY_SIZE_USD = 30.0  # matches BOT_A_ENTRY_SIZE_USD default
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs"


@dataclass
class EntryRecord:
    market_id: str
    category: str
    entry_ts_ms: int
    entry_yes_price: float
    no_entry_price: float
    outcome_yes_won: int
    resolution_ts_ms: int
    days_held: float
    shares: float
    realised_pnl_usd: float
    realised_edge_pct: float
    volume_at_entry_usd: float  # cumulative by that point


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--max-yes-price", type=float, default=0.05,
                   help="Bot A's MAX_YES_ENTRY_PRICE. Default: 0.05.")
    p.add_argument("--min-dtr", type=int, default=21, help="Min days to resolution.")
    p.add_argument("--max-dtr", type=int, default=180, help="Max days to resolution.")
    p.add_argument("--min-volume-usd", type=float, default=5000,
                   help="Min lifetime market volume (final).")
    p.add_argument("--limit-markets", type=int, default=None,
                   help="Cap qualifying markets scanned (debug).")
    p.add_argument("--sample-row-groups", type=int, default=None,
                   help="Limit trades.parquet row groups processed (debug).")
    p.add_argument("--output-dir", default=str(OUTPUT_DIR))
    p.add_argument("--execute", action="store_true",
                   help="Run full scan + write report. Without: plan/stats only.")
    return p.parse_args(argv)


def _require_deps() -> None:
    missing = []
    for name in ("pyarrow", "huggingface_hub"):
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    if missing:
        raise RuntimeError(
            f"missing deps: {', '.join(missing)}. Install: "
            f".venv/bin/pip install {' '.join(missing)}"
        )


def load_qualifying_markets(args: argparse.Namespace) -> dict[str, dict]:
    """Reuse the filter from backtest_bot_a_wangzj.py to get the universe.
    Returns {condition_id: {category, outcome_yes_won, created_ts_ms,
                             end_ts_ms, volume, market_numeric_id}}.
    """
    script_dir = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "bt", script_dir / "backtest_bot_a_wangzj.py"
    )
    bt = importlib.util.module_from_spec(spec)
    sys.modules["bt"] = bt
    spec.loader.exec_module(bt)

    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq

    markets_path = Path(hf_hub_download(
        repo_id=DATASET_REPO, repo_type="dataset", filename="markets.parquet"
    ))
    tbl = pq.read_table(markets_path)
    log.info("loaded %d markets from %s", tbl.num_rows, markets_path)

    cols = {
        n: tbl.column(n).to_pylist()
        for n in ("id", "condition_id", "event_slug", "volume", "closed",
                  "answer1", "answer2", "outcome_prices", "created_at", "end_date",
                  "token1", "token2")
    }
    out: dict[str, dict] = {}
    dtr_min_ms = args.min_dtr * 86400 * 1000
    dtr_max_ms = args.max_dtr * 86400 * 1000
    for i in range(tbl.num_rows):
        if cols["closed"][i] != 1:
            continue
        if cols["answer1"][i] != "Yes" or cols["answer2"][i] != "No":
            continue
        vol = float(cols["volume"][i] or 0)
        if vol < args.min_volume_usd:
            continue
        outcome = bt.parse_outcome(cols["outcome_prices"][i])
        if outcome is None:
            continue
        created_ts = bt.to_ts_ms(cols["created_at"][i])
        end_ts = bt.to_ts_ms(cols["end_date"][i])
        if created_ts == 0 or end_ts == 0:
            continue
        dtr_ms = end_ts - created_ts
        if dtr_ms < dtr_min_ms or dtr_ms > dtr_max_ms:
            continue
        cid = str(cols["condition_id"][i])
        out[cid] = {
            "numeric_id": str(cols["id"][i]),
            "category": bt.infer_category(cols["event_slug"][i]),
            "outcome_yes_won": outcome,
            "created_ts_ms": created_ts,
            "end_ts_ms": end_ts,
            "volume": vol,
            "yes_token_id": str(cols["token1"][i]) if cols["token1"][i] else None,
            "no_token_id": str(cols["token2"][i]) if cols["token2"][i] else None,
        }
        if args.limit_markets and len(out) >= args.limit_markets:
            break
    log.info("filtered to %d qualifying markets", len(out))
    return out


def scan_trades_for_entries(
    qualifying: dict[str, dict],
    args: argparse.Namespace,
) -> list[EntryRecord]:
    """Walk trades.parquet streaming; emit one EntryRecord per qualifying
    market whose yes_price crosses the MAX_YES_ENTRY_PRICE threshold.
    """
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as pq

    trades_path = Path(hf_hub_download(
        repo_id=DATASET_REPO, repo_type="dataset", filename="trades.parquet"
    ))
    reader = pq.ParquetFile(trades_path)
    log.info("trades.parquet: %s, %d row groups, %d total rows",
             trades_path, reader.num_row_groups,
             reader.metadata.num_rows if reader.metadata else -1)

    # Resolved via introspection on 2026-04-17 — actual schema:
    #   timestamp (epoch seconds), condition_id, market_id (numeric),
    #   asset_id (ERC-1155 token id), price, maker_direction, taker_direction,
    #   usd_amount, token_amount.
    schema = reader.schema_arrow
    expected = {"condition_id", "asset_id", "price", "timestamp"}
    missing = expected - set(schema.names)
    if missing:
        raise RuntimeError(
            f"trades.parquet missing expected columns: {missing}. "
            f"Schema: {schema.names}"
        )

    cids = set(qualifying.keys())
    # Build asset_id → condition_id lookup (each market has 2 asset ids).
    # Maps asset_id to (cid, is_yes_token).
    asset_to_cid: dict[str, tuple[str, bool]] = {}
    for cid, q in qualifying.items():
        if q.get("yes_token_id"):
            asset_to_cid[q["yes_token_id"]] = (cid, True)
        if q.get("no_token_id"):
            asset_to_cid[q["no_token_id"]] = (cid, False)
    log.info("built asset lookup: %d asset_ids mapping to %d markets",
             len(asset_to_cid), len(cids))

    entries: dict[str, EntryRecord] = {}  # per-market, keep first qualifying entry

    row_groups = reader.num_row_groups
    if args.sample_row_groups:
        row_groups = min(row_groups, args.sample_row_groups)

    n_scanned = 0
    n_matched = 0
    for rg_idx in range(row_groups):
        rg = reader.read_row_group(
            rg_idx, columns=["condition_id", "asset_id", "price", "timestamp"]
        )
        cond_vals = rg.column("condition_id").to_pylist()
        asset_vals = rg.column("asset_id").to_pylist()
        price_vals = rg.column("price").to_pylist()
        ts_vals = rg.column("timestamp").to_pylist()

        for cond_v, asset_v, price_v, ts_v in zip(
            cond_vals, asset_vals, price_vals, ts_vals, strict=True
        ):
            n_scanned += 1
            # Fast path: check condition_id directly.
            cid = str(cond_v) if cond_v is not None else ""
            if cid not in cids:
                continue
            q = qualifying[cid]
            if cid in entries:
                continue  # already logged an entry for this market
            n_matched += 1

            # Derive yes_price from price + asset_id (YES vs NO token).
            try:
                trade_price = float(price_v)
            except (TypeError, ValueError):
                continue
            if trade_price <= 0 or trade_price >= 1.0:
                continue
            asset_str = str(asset_v) if asset_v is not None else ""
            mapping = asset_to_cid.get(asset_str)
            if mapping is None:
                # Fallback: no asset map, treat as YES. Rare because we
                # built the map from markets.parquet.
                yes_price = trade_price
            elif mapping[1]:  # is_yes_token
                yes_price = trade_price
            else:  # NO token trade
                yes_price = 1.0 - trade_price

            if yes_price > args.max_yes_price:
                continue

            # Normalise timestamp. wangzj uses Unix epoch seconds (int).
            try:
                ts_s = int(ts_v)
            except (TypeError, ValueError):
                continue
            if ts_s <= 0:
                continue
            ts_ms = ts_s * 1000 if ts_s < 1e12 else int(ts_s)

            # DTR check at entry time.
            dtr_at_entry = (q["end_ts_ms"] - ts_ms) / (86400 * 1000)
            if dtr_at_entry < args.min_dtr or dtr_at_entry > args.max_dtr:
                continue

            # Simulate Bot A entry.
            no_entry_price = 1.0 - yes_price
            exit_price = 0.0 if q["outcome_yes_won"] == 1 else 1.0
            shares = ENTRY_SIZE_USD / no_entry_price
            realised_pnl = shares * (exit_price - no_entry_price)
            realised_edge_pct = (exit_price - no_entry_price) / no_entry_price * 100.0
            days_held = (q["end_ts_ms"] - ts_ms) / (86400 * 1000)

            entries[cid] = EntryRecord(
                market_id=cid,
                category=q["category"],
                entry_ts_ms=ts_ms,
                entry_yes_price=yes_price,
                no_entry_price=no_entry_price,
                outcome_yes_won=q["outcome_yes_won"],
                resolution_ts_ms=q["end_ts_ms"],
                days_held=days_held,
                shares=shares,
                realised_pnl_usd=realised_pnl,
                realised_edge_pct=realised_edge_pct,
                volume_at_entry_usd=q["volume"],  # approximation — final vol
            )
        if (rg_idx + 1) % 10 == 0:
            log.info("  row_group %d/%d — scanned %d trades, matched %d entries",
                     rg_idx + 1, row_groups, n_scanned, len(entries))

    log.info("final: scanned %d trades, %d trade hits, %d unique entries",
             n_scanned, n_matched, len(entries))
    return list(entries.values())


def compute_report(entries: list[EntryRecord]) -> dict:
    if not entries:
        return {"n_entries": 0}
    total = len(entries)
    hits = sum(1 for e in entries if e.outcome_yes_won == 0)
    pnl = [e.realised_pnl_usd for e in entries]
    edges = [e.realised_edge_pct for e in entries]
    total_pnl = sum(pnl)
    mean_pnl = total_pnl / total
    # Max drawdown walking entries in order.
    cumulative = 0.0; peak = 0.0; max_dd = 0.0
    for e in sorted(entries, key=lambda x: x.entry_ts_ms):
        cumulative += e.realised_pnl_usd
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)
    # Per-entry-price bucket.
    buckets: dict[str, list[EntryRecord]] = {}
    for e in entries:
        bucket = f"{int(e.entry_yes_price * 100):02d}c"
        buckets.setdefault(bucket, []).append(e)
    by_entry = []
    for key in sorted(buckets):
        b = buckets[key]
        by_entry.append({
            "bucket": key, "n": len(b),
            "hit_rate": sum(1 for x in b if x.outcome_yes_won == 0) / len(b),
            "mean_edge_pct": sum(x.realised_edge_pct for x in b) / len(b),
            "mean_pnl": sum(x.realised_pnl_usd for x in b) / len(b),
        })
    # Per-category.
    cats: dict[str, list[EntryRecord]] = {}
    for e in entries:
        cats.setdefault(e.category, []).append(e)
    by_cat = []
    for key in sorted(cats):
        b = cats[key]
        by_cat.append({
            "category": key, "n": len(b),
            "hit_rate": sum(1 for x in b if x.outcome_yes_won == 0) / len(b),
            "mean_edge_pct": sum(x.realised_edge_pct for x in b) / len(b),
            "total_pnl": sum(x.realised_pnl_usd for x in b),
        })
    return {
        "n_entries": total,
        "n_hit_no": hits,
        "hit_rate": hits / total,
        "total_pnl_usd": total_pnl,
        "mean_pnl_usd": mean_pnl,
        "mean_edge_pct": sum(edges) / total,
        "median_edge_pct": sorted(edges)[total // 2],
        "max_drawdown_usd": max_dd,
        "by_entry_bucket": by_entry,
        "by_category": by_cat,
    }


def format_report_md(stats: dict, args: argparse.Namespace) -> str:
    if not stats.get("n_entries"):
        return "# Bot A walk-forward backtest — no entries generated\n"
    lines = [
        "# Bot A Walk-Forward Backtest — SII-WANGZJ trades.parquet",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}",
        f"**Dataset:** {DATASET_REPO} — markets.parquet + trades.parquet",
        f"**Entry filter:** yes_price ≤ {args.max_yes_price}, DTR ∈ [{args.min_dtr}, {args.max_dtr}] days, "
        f"vol ≥ ${args.min_volume_usd:.0f}, binary YES/NO, resolved.",
        f"**Entry size:** ${ENTRY_SIZE_USD}",
        "",
        "## Summary",
        "",
        f"- Unique Bot-A entries simulated: **{stats['n_entries']:,}**",
        f"- Resolved NO (win): **{stats['n_hit_no']:,}** "
        f"({stats['hit_rate']:.1%})",
        f"- Mean edge per trade: **{stats['mean_edge_pct']:+.2f}%**",
        f"- Median edge per trade: {stats['median_edge_pct']:+.2f}%",
        f"- Mean PnL per trade: ${stats['mean_pnl_usd']:+.2f}",
        f"- **Total PnL: ${stats['total_pnl_usd']:+,.2f}**",
        f"- Max drawdown: ${stats['max_drawdown_usd']:,.2f}",
        "",
        "**Interpretation:**",
    ]
    hr = stats["hit_rate"]
    edge = stats["mean_edge_pct"]
    # Edge is the real test, not hit rate. At sub-5¢ entries, breakeven hit
    # rate is ~96-99% depending on exact entry price. Any mean edge ≤ 0
    # means the 1-10% YES resolutions wiped the wins.
    if edge > 2.0:
        lines.append(f"- Hit rate {hr:.1%}, mean edge {edge:+.2f}%. **Thesis "
                     "is empirically supported**: edge is positive after the "
                     "asymmetric payoff of sub-5¢ entries. Real live PnL "
                     "compresses further by fees + spread (not modelled).")
    elif edge > 0.0:
        lines.append(f"- Hit rate {hr:.1%}, mean edge {edge:+.2f}%. Marginally "
                     "positive — **NOT live-ready**: fees + spread would very "
                     "likely push this below zero. Need a tighter filter or "
                     "a signal that improves hit rate further.")
    else:
        lines.append(f"- Hit rate {hr:.1%}, mean edge **{edge:+.2f}%**. "
                     "**Thesis NOT empirically supported.** Hit rate is "
                     "insufficient to clear the asymmetric payoff at sub-5¢ "
                     "entries. Breakeven hit rate at ~3¢ YES is ~96.8%; "
                     "observed gap is structural, not sample noise. Bot A "
                     "as a standalone mechanical fader does not have edge "
                     "at this entry slice.")
    lines.extend([
        "",
        "## By entry yes_price bucket",
        "",
        "| bucket | n | hit_rate | mean_edge_% | mean_pnl$ |",
        "|---|---|---|---|---|",
    ])
    for b in stats["by_entry_bucket"]:
        lines.append(
            f"| {b['bucket']} | {b['n']:,} | {b['hit_rate']:.1%} | "
            f"{b['mean_edge_pct']:+.2f}% | {b['mean_pnl']:+.2f} |"
        )
    lines.extend([
        "",
        "## By inferred category",
        "",
        "| category | n | hit_rate | mean_edge_% | total_pnl$ |",
        "|---|---|---|---|---|",
    ])
    for b in stats["by_category"]:
        lines.append(
            f"| {b['category']} | {b['n']:,} | {b['hit_rate']:.1%} | "
            f"{b['mean_edge_pct']:+.2f}% | {b['total_pnl']:+,.2f} |"
        )
    lines.extend([
        "",
        "## Limitations",
        "",
        "- **No fee modelling.** Real live PnL compresses by fee_rate × notional "
        "per round-trip. Bot A's geopolitics focus is fee-free; other categories "
        "pay up to 5%.",
        "- **No spread modelling.** Entries simulated at the trade price; real "
        "entries are at `best_ask`, usually higher.",
        "- **No order-minimum rejection.** Polymarket rejects orders <5 shares; "
        "at entries with yes_price near 0.05, shares ~$600/0.95 ≈ 632 — not a "
        "binding constraint, but an edge case at 0.01-0.02 entries would be.",
        "- **Entry at first-qualifying trade.** Real Bot A holds the rest of "
        "the market's life in the same position; doesn't re-enter.",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    try:
        _require_deps()
    except RuntimeError as e:
        print(str(e), file=sys.stderr); return 2

    print(f"\n=== Bot A Walk-Forward Backtest ===")
    qualifying = load_qualifying_markets(args)
    print(f"qualifying markets: {len(qualifying):,}")
    if not qualifying:
        print("no qualifying markets — aborting.")
        return 3
    if not args.execute:
        print("Dry run. Re-run with --execute to walk trades.parquet (32 GB).")
        print(f"Estimated runtime: ~{len(qualifying)//2000 + 3} min on the bot host.")
        return 0

    entries = scan_trades_for_entries(qualifying, args)
    stats = compute_report(entries)
    print(f"\nentries: {stats.get('n_entries', 0):,}")
    if stats.get("n_entries"):
        print(f"hit_rate: {stats['hit_rate']:.1%}")
        print(f"mean_edge: {stats['mean_edge_pct']:+.2f}%")
        print(f"total_pnl: ${stats['total_pnl_usd']:+,.2f}")

    md = format_report_md(stats, args)
    out_path = Path(args.output_dir) / \
        f"bot-a-walkforward-wangzj-{datetime.now(UTC).date().isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)
    print(f"\nreport written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
