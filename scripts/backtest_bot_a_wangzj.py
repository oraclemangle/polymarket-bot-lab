#!/usr/bin/env python3
"""Bot A hit-rate backtest against SII-WANGZJ/Polymarket_data.

Shape-specific variant of `scripts/backtest_bot_a_historical.py`. This one
accepts the actual wangzj schema directly:

  markets.parquet columns (734,790 rows, 68 MB):
    id, question, slug, condition_id, token1, token2, answer1, answer2,
    closed, active, archived, outcome_prices, volume, event_id,
    event_slug, event_title, created_at, end_date, updated_at, neg_risk

Why this script exists
----------------------
The generic backtest expected a static `yes_price` column + a clean
`outcome` column. Neither exists. We:
  - Extract outcomes from `outcome_prices` (Python-repr'd list; resolved
    markets have '0'/'1' values).
  - Synthesize entries only where the market MIGHT have been at a
    low-yes tail per Bot A's filter. Without historical trade prices,
    we cannot reconstruct the exact entry price — so we report the
    BASE RATE question: of ALL binary markets matching Bot A's
    structural filter (YN resolved, vol ≥ $5k, DTR 21-180), what
    fraction resolved NO?
  - If that base rate is 85-95%, Bot A's thesis has empirical support.
  - If it's 55-70%, the thesis probably needs a stricter entry-price
    filter that we can't test without trades.parquet.

Category breakdowns use `event_slug` keyword matching (politics,
finance/economics, crypto, sports, culture, weather) — rough heuristic,
but tells us which market-types drive the overall hit rate.

Usage
-----
    python scripts/backtest_bot_a_wangzj.py                  # dry-run stats
    python scripts/backtest_bot_a_wangzj.py --execute        # write full report
    python scripts/backtest_bot_a_wangzj.py --min-dtr 21 \\
                                             --max-dtr 180 \\
                                             --min-volume-usd 5000 \\
                                             --execute
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

log = logging.getLogger(__name__)


DATASET_REPO = "SII-WANGZJ/Polymarket_data"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs"


# Rough keyword-based category mapping against event_slug (heuristic, not
# a substitute for true category metadata). Ordering matters — first
# match wins. `_other` catches anything unmatched.
CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "crypto_scalp": ("updown", "-up-down", "-1h-", "btc-", "eth-", "sol-", "bnb-",
                     "xrp-", "doge-", "bitcoin-up", "ethereum-up"),
    "politics": ("election", "president", "senate", "congress", "governor", "primary",
                 "caucus", "vote", "democrat", "republican", "trump", "biden", "harris",
                 "desantis", "newsom", "shelton", "fed-chair", "supreme-court",
                 "prime-minister", "parliament", "uk-general-election", "chancellor"),
    "finance_economics": ("fed-", "interest-rate", "rate-cut", "rate-hike", "inflation",
                          "cpi", "gdp", "recession", "unemployment", "jobs-report",
                          "stock", "sp500", "spy-", "qqq-", "nasdaq", "nvda-", "aapl-",
                          "msft-", "amzn-", "googl-", "meta-", "nflx-", "tsla-"),
    "geopolitics": ("ukraine", "russia", "russian", "putin", "zelensky", "israel",
                    "palestine", "gaza", "hamas", "iran", "china", "taiwan", "nato",
                    "sanctions", "ceasefire", "war-", "north-korea", "kim-jong"),
    "sports": ("nba", "nfl", "mlb", "mls", "epl", "la-liga", "seriea", "bundesliga",
               "champions-league", "world-cup", "euro-2024", "f1-", "ufc-",
               "-vs-", "btts", "over-under", "spread"),
    "culture_mentions": ("taylor-swift", "elon-musk", "celebrity", "movie", "oscars",
                         "emmys", "grammys", "netflix-", "instagram-"),
    "weather": ("temperature", "hurricane", "tornado", "snowfall", "heatwave",
                "weather-"),
}


@dataclass
class MarketRow:
    id: str
    condition_id: str
    question: str
    event_slug: str
    volume: float
    outcome_yes_won: int  # 1 if YES resolved, 0 if NO
    created_ts_ms: int
    end_ts_ms: int
    category: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--markets-parquet", default=None,
                   help="Override local markets.parquet path. Default: auto-download from HF.")
    p.add_argument("--min-dtr", type=int, default=21, help="Minimum days to resolution.")
    p.add_argument("--max-dtr", type=int, default=180, help="Maximum days to resolution.")
    p.add_argument("--min-volume-usd", type=float, default=5000,
                   help="Minimum lifetime volume in USD.")
    p.add_argument("--output-dir", default=str(OUTPUT_DIR))
    p.add_argument("--execute", action="store_true",
                   help="Write the full report. Without this, print summary only.")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap the markets scanned (debug).")
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


def download_markets(cache_dir: str | None = None) -> Path:
    from huggingface_hub import hf_hub_download
    log.info("downloading markets.parquet from %s", DATASET_REPO)
    local = hf_hub_download(
        repo_id=DATASET_REPO, repo_type="dataset",
        filename="markets.parquet", cache_dir=cache_dir,
    )
    return Path(local)


_OUTCOME_RE = re.compile(r"^\s*\[\s*'([01](?:\.\d+)?)'\s*,\s*'([01](?:\.\d+)?)'\s*\]\s*$")


def parse_outcome(raw: str | None) -> int | None:
    """Parse outcome_prices string.

    Returns:
      1 if YES resolved (first element = '1')
      0 if NO resolved (second element = '1')
      None if unresolved (neither element is exactly '0' or '1', or raw is invalid)
    """
    if not raw:
        return None
    m = _OUTCOME_RE.match(raw)
    if m is None:
        return None
    a, b = m.group(1), m.group(2)
    if a == "1" and b == "0":
        return 1  # YES resolved
    if a == "0" and b == "1":
        return 0  # NO resolved
    return None  # fractional (unresolved-at-close)


def infer_category(event_slug: str | None) -> str:
    if not event_slug:
        return "_other"
    s = event_slug.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in s:
                return cat
    return "_other"


def to_ts_ms(value) -> int:
    import pandas as pd
    if value is None or (hasattr(pd, "isna") and pd.isna(value)):
        return 0
    try:
        dt = pd.to_datetime(value, utc=True, errors="coerce")
        if pd.isna(dt):
            return 0
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def filter_and_tag(parquet_path: Path, args: argparse.Namespace) -> list[MarketRow]:
    """Single pass over markets.parquet; apply Bot A's structural filter."""
    import pyarrow.parquet as pq
    tbl = pq.read_table(parquet_path)
    if args.limit:
        tbl = tbl.slice(0, args.limit)
    log.info("loaded %d markets from %s", tbl.num_rows, parquet_path)

    rows: list[MarketRow] = []
    dtr_min_ms = args.min_dtr * 86400 * 1000
    dtr_max_ms = args.max_dtr * 86400 * 1000
    skipped = {"not_closed": 0, "not_yn": 0, "low_volume": 0, "unresolved": 0,
               "no_dates": 0, "dtr_out_of_range": 0}

    # Columnar extraction for speed.
    col = {n: tbl.column(n).to_pylist() for n in (
        "id", "condition_id", "question", "event_slug", "volume",
        "closed", "answer1", "answer2", "outcome_prices",
        "created_at", "end_date",
    )}

    n = tbl.num_rows
    for i in range(n):
        if col["closed"][i] != 1:
            skipped["not_closed"] += 1
            continue
        if col["answer1"][i] != "Yes" or col["answer2"][i] != "No":
            skipped["not_yn"] += 1
            continue
        vol = float(col["volume"][i] or 0)
        if vol < args.min_volume_usd:
            skipped["low_volume"] += 1
            continue
        outcome = parse_outcome(col["outcome_prices"][i])
        if outcome is None:
            skipped["unresolved"] += 1
            continue
        created_ts = to_ts_ms(col["created_at"][i])
        end_ts = to_ts_ms(col["end_date"][i])
        if created_ts == 0 or end_ts == 0:
            skipped["no_dates"] += 1
            continue
        dtr_ms = end_ts - created_ts
        if dtr_ms < dtr_min_ms or dtr_ms > dtr_max_ms:
            skipped["dtr_out_of_range"] += 1
            continue
        rows.append(MarketRow(
            id=str(col["id"][i]),
            condition_id=str(col["condition_id"][i]),
            question=str(col["question"][i] or "")[:200],
            event_slug=str(col["event_slug"][i] or ""),
            volume=vol,
            outcome_yes_won=outcome,
            created_ts_ms=created_ts,
            end_ts_ms=end_ts,
            category=infer_category(col["event_slug"][i]),
        ))
        if (i + 1) % 100000 == 0:
            log.info("  scanned %d/%d — kept %d", i + 1, n, len(rows))
    log.info("filtered %d -> %d qualifying markets; skipped %s",
             n, len(rows), skipped)
    return rows


def compute_stats(rows: list[MarketRow]) -> dict:
    if not rows:
        return {"n_qualifying": 0}

    total = len(rows)
    no_wins = sum(1 for r in rows if r.outcome_yes_won == 0)
    hit_rate_overall = no_wins / total

    # Per-category breakdown.
    cats: dict[str, list[MarketRow]] = {}
    for r in rows:
        cats.setdefault(r.category, []).append(r)
    by_category = []
    for cat in sorted(cats.keys()):
        bucket = cats[cat]
        n_cat = len(bucket)
        no_cat = sum(1 for r in bucket if r.outcome_yes_won == 0)
        by_category.append({
            "category": cat, "n": n_cat,
            "hit_rate_no": no_cat / n_cat,
            "mean_volume": sum(r.volume for r in bucket) / n_cat,
        })

    # Per-DTR-bucket breakdown.
    dtr_buckets: dict[str, list[MarketRow]] = {
        "21-30d": [], "30-60d": [], "60-90d": [], "90-180d": [],
    }
    for r in rows:
        days = (r.end_ts_ms - r.created_ts_ms) / (86400 * 1000)
        if days < 30:
            dtr_buckets["21-30d"].append(r)
        elif days < 60:
            dtr_buckets["30-60d"].append(r)
        elif days < 90:
            dtr_buckets["60-90d"].append(r)
        else:
            dtr_buckets["90-180d"].append(r)
    by_dtr = []
    for bk in ("21-30d", "30-60d", "60-90d", "90-180d"):
        b = dtr_buckets[bk]
        if not b:
            by_dtr.append({"bucket": bk, "n": 0, "hit_rate_no": None})
            continue
        no_b = sum(1 for r in b if r.outcome_yes_won == 0)
        by_dtr.append({"bucket": bk, "n": len(b), "hit_rate_no": no_b / len(b)})

    # Per-volume-bucket breakdown.
    vol_buckets: dict[str, list[MarketRow]] = {
        "5k-10k": [], "10k-100k": [], "100k-1M": [], ">1M": [],
    }
    for r in rows:
        v = r.volume
        if v < 10_000:
            vol_buckets["5k-10k"].append(r)
        elif v < 100_000:
            vol_buckets["10k-100k"].append(r)
        elif v < 1_000_000:
            vol_buckets["100k-1M"].append(r)
        else:
            vol_buckets[">1M"].append(r)
    by_vol = []
    for bk in ("5k-10k", "10k-100k", "100k-1M", ">1M"):
        b = vol_buckets[bk]
        if not b:
            by_vol.append({"bucket": bk, "n": 0, "hit_rate_no": None})
            continue
        no_b = sum(1 for r in b if r.outcome_yes_won == 0)
        by_vol.append({"bucket": bk, "n": len(b), "hit_rate_no": no_b / len(b)})

    return {
        "n_qualifying": total,
        "no_wins": no_wins,
        "hit_rate_no_overall": hit_rate_overall,
        "by_category": by_category,
        "by_dtr": by_dtr,
        "by_volume": by_vol,
    }


def format_report_md(stats: dict, args: argparse.Namespace) -> str:
    lines = [
        "# Bot A Hit-Rate Backtest — SII-WANGZJ dataset",
        "",
        f"**Generated:** {datetime.now(UTC).isoformat()}",
        f"**Dataset:** {DATASET_REPO}/markets.parquet",
        f"**Filter:** closed=1, answer1=Yes, answer2=No, volume ≥ ${args.min_volume_usd:.0f}, "
        f"DTR ∈ [{args.min_dtr}, {args.max_dtr}] days, "
        f"outcome ∈ {{['0','1'], ['1','0']}}",
        "",
        "## The base-rate question",
        "",
        "Bot A's thesis: 'tail-priced YES markets (≤ 5¢) systematically over-price the low-"
        "probability outcome; fade by buying NO at 95¢+.' The strongest empirical check we "
        "can run from markets.parquet alone (no trade-price history) is the BASE RATE: "
        "across all binary markets matching Bot A's structural shape (category, volume, "
        "DTR), what fraction resolve NO?",
        "",
        "If ≥85% resolve NO, the tail-fade thesis has empirical support at the universe "
        "level. Precise entry-price edge calculation requires trades.parquet (32 GB, not "
        "yet downloaded).",
        "",
        "## Summary",
        "",
        f"- Qualifying markets: **{stats.get('n_qualifying', 0):,}**",
    ]
    if stats.get("n_qualifying", 0) > 0:
        hr = stats["hit_rate_no_overall"]
        lines.append(f"- Resolved NO (YES=0): **{stats['no_wins']:,}** ({hr:.1%})")
        lines.append(f"- Resolved YES: {stats['n_qualifying'] - stats['no_wins']:,} "
                     f"({1 - hr:.1%})")
        # Verdict.
        if hr >= 0.85:
            verdict = "SUPPORTS THESIS — tail-fade base rate is robust across the universe."
        elif hr >= 0.70:
            verdict = "PARTIAL SUPPORT — thesis may work with a stricter entry filter."
        else:
            verdict = "DOES NOT SUPPORT THESIS — base rate too low; edge depends on "\
                     "precise entry-price timing not testable here."
        lines.append("")
        lines.append(f"**Verdict:** {verdict}")

    lines.extend([
        "",
        "## By inferred category (event_slug keyword match)",
        "",
        "| category | n | hit_rate_NO | mean_volume $ |",
        "|---|---|---|---|",
    ])
    for b in stats.get("by_category", []):
        lines.append(
            f"| {b['category']} | {b['n']:,} | {b['hit_rate_no']:.1%} | "
            f"{b['mean_volume']:,.0f} |"
        )

    lines.extend([
        "",
        "## By days-to-resolution bucket",
        "",
        "| bucket | n | hit_rate_NO |",
        "|---|---|---|",
    ])
    for b in stats.get("by_dtr", []):
        hr = f"{b['hit_rate_no']:.1%}" if b.get("hit_rate_no") is not None else "—"
        lines.append(f"| {b['bucket']} | {b['n']:,} | {hr} |")

    lines.extend([
        "",
        "## By volume bucket",
        "",
        "| bucket | n | hit_rate_NO |",
        "|---|---|---|",
    ])
    for b in stats.get("by_volume", []):
        hr = f"{b['hit_rate_no']:.1%}" if b.get("hit_rate_no") is not None else "—"
        lines.append(f"| {b['bucket']} | {b['n']:,} | {hr} |")

    lines.extend([
        "",
        "## Limitations",
        "",
        "- **No entry-price data.** markets.parquet lacks a historical trade-price "
        "column. Bot A's filter requires `yes_price ≤ 0.05` at entry — we cannot verify "
        "that directly here. The `outcome_prices` field contains only the RESOLVED "
        "value (0 or 1) for resolved markets.",
        "- **Category inference is heuristic.** event_slug keyword matching is rough; "
        "`_other` may contain some politics/finance markets miscategorised.",
        "- **Survivorship.** The dataset contains markets Polymarket lists; markets "
        "delisted before resolution are absent.",
        "- **Fee effect not modelled.** Only geopolitics is 0% fee; other categories "
        "pay 1-5% round-trip. Real live PnL would compress by that factor.",
        "",
        "## Next step",
        "",
        "Once `trades.parquet` (32 GB) downloads, re-run with a true entry-price "
        "walk-forward: for each qualifying market, find the earliest timestamp where "
        "the last-trade yes_price ≤ 0.05, simulate an entry, compute realised PnL "
        "at resolution.",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    try:
        _require_deps()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2

    if args.markets_parquet:
        parquet_path = Path(args.markets_parquet)
    else:
        parquet_path = download_markets()
    rows = filter_and_tag(parquet_path, args)
    stats = compute_stats(rows)

    print(f"\n=== Bot A Hit-Rate Backtest — wangzj ===")
    print(f"qualifying markets: {stats.get('n_qualifying', 0):,}")
    if stats.get("n_qualifying", 0) > 0:
        print(f"hit_rate_NO: {stats['hit_rate_no_overall']:.1%}")
    print()

    if not args.execute:
        print("Dry run. Re-run with --execute to write the full report.")
        return 0

    md = format_report_md(stats, args)
    out_path = Path(args.output_dir) / \
        f"bot-a-backtest-wangzj-{datetime.now(UTC).date().isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)
    print(f"report written: {out_path}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
