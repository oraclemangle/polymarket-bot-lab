#!/usr/bin/env python3
"""Bot F crowd-flow same-side momentum vs fade EV report.

Read-only OQ-059 follow-up. Uses Bot F mirror signals plus public Polymarket
trade prints keyed by condition id to test whether crowd flow should be
followed or faded at several horizons. No bot state is changed.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.research.bot_f_anti_crowd_join_diagnostic import (  # noqa: E402
    fetch_market_trades,
    nearest_trade_price,
    parse_dt,
    parse_since,
    signal_time,
)
from scripts.research.math_formula_common import (  # noqa: E402
    connect_ro,
    table_exists,
    to_float,
    write_report_pair,
)

DEFAULT_BOT_F_DB = REPO_ROOT / "data" / "bot_f.db"
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "reports" / "bot_f_momentum"
DEFAULT_DOCS_REPORT = REPO_ROOT / "docs" / "reports" / "bot-f-crowd-momentum-ev-2026-05-08.md"
DEFAULT_HORIZONS = (60, 300, 1800, 21600)
DEFAULT_COSTS_CENTS = (1.0, 2.0, 4.0)


@dataclass(frozen=True)
class Signal:
    detected_at: datetime
    signal_at: datetime
    wallet: str
    condition_id: str
    token_id: str
    side: str
    price: float
    size_shares: float
    signal_age_sec: float | None
    title: str
    slug: str
    event_slug: str
    outcome: str
    category: str
    wallet_cohort: str
    price_bucket: str
    signal_age_bucket: str
    trade_size_bucket: str

    @property
    def market_day(self) -> str:
        return f"{self.condition_id}|{self.signal_at.date().isoformat()}"


@dataclass(frozen=True)
class Observation:
    signal: Signal
    horizon_sec: int
    end_price: float
    same_side_edge: float

    @property
    def fade_edge(self) -> float:
        return -self.same_side_edge


def sql_dt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")


def payload(raw: object) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def classify_category(text: str) -> str:
    h = text.lower()
    if any(term in h for term in ("bitcoin", "ethereum", "solana", "dogecoin", "xrp", "crypto")):
        return "crypto"
    if any(term in h for term in ("temperature", "hottest", "coldest", "weather", "rain", "snow", "°", "fahrenheit", "celsius")):
        return "weather"
    if any(term in h for term in ("election", "trump", "biden", "congress", "senate", "president", "politic")):
        return "politics"
    if any(term in h for term in ("oscar", "grammy", "emmy", "award")):
        return "awards"
    if any(
        term in h
        for term in (
            " vs ",
            "spread:",
            "o/u",
            "nba",
            "nfl",
            "mlb",
            "nhl",
            "tennis",
            "wta",
            "atp",
            "fc ",
            "sc ",
            "will ",
            "win on",
        )
    ):
        return "sports"
    return "unknown"


def bucket_price(price: float) -> str:
    if price < 0.05:
        return "<5c"
    if price < 0.10:
        return "5c-10c"
    if price < 0.25:
        return "10c-25c"
    if price < 0.50:
        return "25c-50c"
    if price < 0.75:
        return "50c-75c"
    return "75c+"


def bucket_age(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"
    if seconds <= 90:
        return "<=90s"
    if seconds <= 300:
        return "90s-5m"
    if seconds <= 1800:
        return "5m-30m"
    return ">30m"


def bucket_size(size: float) -> str:
    if size < 100:
        return "<100"
    if size < 1_000:
        return "100-1k"
    if size < 10_000:
        return "1k-10k"
    if size < 100_000:
        return "10k-100k"
    return "100k+"


def wallet_cohorts(con: sqlite3.Connection) -> dict[str, str]:
    if not table_exists(con, "hunter_rankings"):
        return {}
    row = con.execute(
        "SELECT run_id FROM hunter_rankings ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        return {}
    latest_run = row["run_id"]
    out: dict[str, str] = {}
    for r in con.execute(
        """
        SELECT wallet, rank
        FROM hunter_rankings
        WHERE run_id = ?
        """,
        (latest_run,),
    ):
        rank = int(r["rank"])
        if rank <= 10:
            cohort = "rank_1_10"
        elif rank <= 40:
            cohort = "rank_11_40"
        elif rank <= 100:
            cohort = "rank_41_100"
        else:
            cohort = "rank_100+"
        out[str(r["wallet"]).lower()] = cohort
    return out


def load_signals(bot_f_db: Path, since: datetime | None, limit: int) -> list[Signal]:
    if not bot_f_db.exists():
        return []
    with connect_ro(bot_f_db) as con:
        if not table_exists(con, "mirror_signals"):
            return []
        cohorts = wallet_cohorts(con)
        params: list[Any] = []
        clause = ""
        if since is not None:
            clause = "WHERE detected_at >= ?"
            params.append(sql_dt(since))
        rows = con.execute(
            f"""
            SELECT detected_at, wallet, condition_id, token_id, side, price,
                   size_shares, whale_tx_ts, signal_age_ms, raw_payload
            FROM mirror_signals
            {clause}
            ORDER BY detected_at DESC
            LIMIT {int(limit)}
            """,
            params,
        ).fetchall()
    out: list[Signal] = []
    for row in rows:
        detected = parse_dt(row["detected_at"])
        signal_at = signal_time(row)
        price = to_float(row["price"])
        size = to_float(row["size_shares"], 0.0) or 0.0
        token_id = str(row["token_id"] or "")
        condition_id = str(row["condition_id"] or "")
        if detected is None or signal_at is None or price is None or not token_id or not condition_id:
            continue
        raw = payload(row["raw_payload"])
        title = str(raw.get("title") or "")
        slug = str(raw.get("slug") or "")
        event_slug = str(raw.get("event_slug") or raw.get("eventSlug") or "")
        outcome = str(raw.get("outcome") or "")
        text = " ".join([title, slug, event_slug, outcome])
        age_ms = to_float(row["signal_age_ms"])
        age_sec = age_ms / 1000.0 if age_ms is not None else None
        wallet = str(row["wallet"] or "").lower()
        out.append(
            Signal(
                detected_at=detected,
                signal_at=signal_at,
                wallet=wallet,
                condition_id=condition_id,
                token_id=token_id,
                side=str(row["side"] or "").upper(),
                price=price,
                size_shares=size,
                signal_age_sec=age_sec,
                title=title,
                slug=slug,
                event_slug=event_slug,
                outcome=outcome,
                category=classify_category(text),
                wallet_cohort=cohorts.get(wallet, "unranked"),
                price_bucket=bucket_price(price),
                signal_age_bucket=bucket_age(age_sec),
                trade_size_bucket=bucket_size(size),
            )
        )
    return out


def fetch_trade_cache(
    signals: list[Signal],
    *,
    horizons: tuple[int, ...],
    tolerance_sec: int,
    api_limit: int,
    api_max_pages: int,
    api_sleep_sec: float,
    max_api_markets: int,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_market: dict[str, list[Signal]] = defaultdict(list)
    for signal in signals:
        by_market[signal.condition_id].append(signal)
    cache: dict[str, list[dict[str, Any]]] = {}
    errors: Counter[str] = Counter()
    fetched = 0
    for condition_id, rows in by_market.items():
        if fetched >= max_api_markets:
            errors["max_api_markets_reached"] += 1
            continue
        earliest = min(int(row.signal_at.timestamp()) for row in rows) - tolerance_sec
        # Need enough history before earliest signal and enough recent rows
        # after the largest horizon. Offset pagination returns newest first.
        trades, error = fetch_market_trades(
            condition_id,
            limit=api_limit,
            max_pages=api_max_pages,
            sleep_sec=api_sleep_sec,
            stop_before_ts=earliest,
        )
        cache[condition_id] = trades
        fetched += 1
        if error:
            errors[error] += 1
    return cache, {
        "markets_requested": len(by_market),
        "markets_fetched": fetched,
        "api_errors": dict(sorted(errors.items())),
    }


def build_observations(
    signals: list[Signal],
    trades_by_market: dict[str, list[dict[str, Any]]],
    *,
    horizons: tuple[int, ...],
    tolerance_sec: int,
) -> tuple[list[Observation], dict[str, Any]]:
    observations: list[Observation] = []
    missing_by_horizon: Counter[str] = Counter()
    for signal in signals:
        trades = trades_by_market.get(signal.condition_id, [])
        for horizon in horizons:
            target = int(signal.signal_at.timestamp()) + horizon
            end_price, _end_ts = nearest_trade_price(
                trades,
                token_id=signal.token_id,
                target_ts=target,
                tolerance_sec=tolerance_sec,
            )
            if end_price is None:
                missing_by_horizon[str(horizon)] += 1
                continue
            edge = end_price - signal.price if signal.side == "BUY" else signal.price - end_price
            observations.append(
                Observation(
                    signal=signal,
                    horizon_sec=horizon,
                    end_price=end_price,
                    same_side_edge=edge,
                )
            )
    return observations, {
        "observations": len(observations),
        "missing_by_horizon": dict(sorted(missing_by_horizon.items())),
    }


def top2_concentration(values: list[float]) -> float:
    if not values:
        return 0.0
    total = sum(values)
    if total <= 0:
        return 0.0
    return sum(sorted(values, reverse=True)[:2]) / total


def bootstrap_cluster_ci(
    values_by_cluster: dict[str, list[float]],
    *,
    n_resamples: int,
    alpha: float,
    seed: int,
) -> tuple[float | None, float | None]:
    if not values_by_cluster:
        return None, None
    clusters = list(values_by_cluster)
    if len(clusters) < 2:
        mean_value = sum(values_by_cluster[clusters[0]]) / len(values_by_cluster[clusters[0]])
        return mean_value, mean_value
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(n_resamples):
        vals: list[float] = []
        for _i in clusters:
            cluster = rng.choice(clusters)
            vals.extend(values_by_cluster[cluster])
        samples.append(sum(vals) / len(vals))
    samples.sort()
    lo_idx = max(0, int((alpha / 2.0) * len(samples)))
    hi_idx = min(len(samples) - 1, int((1.0 - alpha / 2.0) * len(samples)))
    return samples[lo_idx], samples[hi_idx]


def group_key(signal: Signal, group_type: str) -> str:
    if group_type == "all":
        return "all"
    if group_type == "category":
        return signal.category
    if group_type == "price_bucket":
        return signal.price_bucket
    if group_type == "wallet_cohort":
        return signal.wallet_cohort
    if group_type == "signal_age_bucket":
        return signal.signal_age_bucket
    if group_type == "trade_size_bucket":
        return signal.trade_size_bucket
    raise ValueError(group_type)


def summarise_cell(
    observations: list[Observation],
    *,
    horizon: int,
    mode: str,
    cost_cents: float,
    group_type: str,
    segment: str,
    min_cell_n: int,
    n_bootstrap: int,
    seed: int,
) -> dict[str, Any]:
    cost = cost_cents / 100.0
    net_edges: list[float] = []
    gross_edges: list[float] = []
    by_cluster: dict[str, list[float]] = defaultdict(list)
    for obs in observations:
        gross = obs.same_side_edge if mode == "same_side" else obs.fade_edge
        net = gross - cost
        gross_edges.append(gross)
        net_edges.append(net)
        by_cluster[obs.signal.market_day].append(net)
    mean_gross = sum(gross_edges) / len(gross_edges) if gross_edges else None
    mean_net = sum(net_edges) / len(net_edges) if net_edges else None
    ci_lo, ci_hi = bootstrap_cluster_ci(
        by_cluster,
        n_resamples=n_bootstrap,
        alpha=0.05,
        seed=seed,
    )
    top2 = top2_concentration(net_edges)
    pass_gate = (
        len(net_edges) >= min_cell_n
        and mean_net is not None
        and mean_net > 0
        and ci_lo is not None
        and ci_lo > 0
        and top2 < 0.50
    )
    return {
        "horizon_sec": horizon,
        "mode": mode,
        "cost_cents": cost_cents,
        "group_type": group_type,
        "segment": segment,
        "n": len(net_edges),
        "n_market_days": len(by_cluster),
        "mean_gross_edge_cents": None if mean_gross is None else mean_gross * 100.0,
        "mean_net_edge_cents": None if mean_net is None else mean_net * 100.0,
        "ci95_lower_cents": None if ci_lo is None else ci_lo * 100.0,
        "ci95_upper_cents": None if ci_hi is None else ci_hi * 100.0,
        "net_positive_rate": (
            sum(1 for value in net_edges if value > 0) / len(net_edges)
            if net_edges
            else None
        ),
        "top2_concentration": top2,
        "pass_gate": pass_gate,
    }


def summarise(
    observations: list[Observation],
    *,
    horizons: tuple[int, ...],
    costs_cents: tuple[float, ...],
    group_types: tuple[str, ...],
    min_cell_n: int,
    n_bootstrap: int,
    seed: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in horizons:
        obs_h = [obs for obs in observations if obs.horizon_sec == horizon]
        for group_type in group_types:
            grouped: dict[str, list[Observation]] = defaultdict(list)
            for obs in obs_h:
                grouped[group_key(obs.signal, group_type)].append(obs)
            for segment, vals in sorted(grouped.items()):
                for mode in ("same_side", "fade"):
                    for cost in costs_cents:
                        rows.append(
                            summarise_cell(
                                vals,
                                horizon=horizon,
                                mode=mode,
                                cost_cents=cost,
                                group_type=group_type,
                                segment=segment,
                                min_cell_n=min_cell_n,
                                n_bootstrap=n_bootstrap,
                                seed=seed + horizon + len(rows),
                            )
                        )
    return rows


def build_report(
    *,
    bot_f_db: Path,
    since: datetime | None,
    limit: int,
    horizons: tuple[int, ...],
    tolerance_sec: int,
    costs_cents: tuple[float, ...],
    api_limit: int,
    api_max_pages: int,
    api_sleep_sec: float,
    max_api_markets: int,
    min_cell_n: int,
    n_bootstrap: int,
    seed: int,
) -> dict[str, Any]:
    signals = load_signals(bot_f_db, since, limit)
    trades_by_market, fetch_diag = fetch_trade_cache(
        signals,
        horizons=horizons,
        tolerance_sec=tolerance_sec,
        api_limit=api_limit,
        api_max_pages=api_max_pages,
        api_sleep_sec=api_sleep_sec,
        max_api_markets=max_api_markets,
    )
    observations, obs_diag = build_observations(
        signals,
        trades_by_market,
        horizons=horizons,
        tolerance_sec=tolerance_sec,
    )
    rows = summarise(
        observations,
        horizons=horizons,
        costs_cents=costs_cents,
        group_types=(
            "all",
            "category",
            "price_bucket",
            "wallet_cohort",
            "signal_age_bucket",
            "trade_size_bucket",
        ),
        min_cell_n=min_cell_n,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "bot_f_db": str(bot_f_db),
        "since": since.isoformat() if since else "all",
        "limit": limit,
        "horizons_sec": list(horizons),
        "tolerance_sec": tolerance_sec,
        "costs_cents": list(costs_cents),
        "min_cell_n": min_cell_n,
        "n_bootstrap": n_bootstrap,
        "signals_loaded": len(signals),
        "fetch_diagnostics": fetch_diag,
        "observation_diagnostics": obs_diag,
        "category_counts": dict(sorted(Counter(signal.category for signal in signals).items())),
        "price_bucket_counts": dict(sorted(Counter(signal.price_bucket for signal in signals).items())),
        "wallet_cohort_counts": dict(sorted(Counter(signal.wallet_cohort for signal in signals).items())),
        "rows": rows,
        "passing_rows": [row for row in rows if row["pass_gate"]],
    }


def fmt_c(value: float | None) -> str:
    return "" if value is None else f"{value:+.2f}c"


def fmt_pct(value: float | None) -> str:
    return "" if value is None else f"{value:.1%}"


def render_markdown(report: dict[str, Any]) -> str:
    passing = report["passing_rows"]
    lines = [
        "# Bot F Crowd Momentum EV Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Bot F DB: `{report['bot_f_db']}`",
        f"Since: `{report['since']}`",
        "",
        "## Verdict",
        "",
    ]
    if passing:
        lines.append(f"- PASS: `{len(passing)}` cells clear the sample, net-edge, CI, and concentration gate.")
    else:
        lines.append("- FAIL: no cell clears the sample, net-edge, CI, and concentration gate.")
    lines.extend(
        [
            "",
            "## Sample",
            "",
            f"- Signals loaded: `{report['signals_loaded']}`",
            f"- Markets requested: `{report['fetch_diagnostics']['markets_requested']}`",
            f"- Markets fetched: `{report['fetch_diagnostics']['markets_fetched']}`",
            f"- Observations measured: `{report['observation_diagnostics']['observations']}`",
            f"- Tolerance seconds: `{report['tolerance_sec']}`",
            f"- Bootstrap resamples: `{report['n_bootstrap']}` by market/day cluster",
            "",
        ]
    )
    if report["fetch_diagnostics"].get("api_errors"):
        lines.append("API errors: " + ", ".join(f"{k}={v}" for k, v in report["fetch_diagnostics"]["api_errors"].items()))
        lines.append("")
    lines.extend(
        [
            "## Best Cells",
            "",
            "| Horizon | Mode | Cost | Group | Segment | n | Market-days | Net edge | CI95 | Net+ | Top2 | Gate |",
            "|---:|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    display_rows = sorted(
        report["rows"],
        key=lambda row: (
            not row["pass_gate"],
            -(row["mean_net_edge_cents"] if row["mean_net_edge_cents"] is not None else -999),
            -row["n"],
        ),
    )
    for row in display_rows[:80]:
        ci = (
            ""
            if row["ci95_lower_cents"] is None
            else f"{row['ci95_lower_cents']:+.2f}c..{row['ci95_upper_cents']:+.2f}c"
        )
        lines.append(
            f"| {row['horizon_sec']}s | {row['mode']} | {row['cost_cents']:.0f}c | "
            f"{row['group_type']} | {row['segment']} | {row['n']} | {row['n_market_days']} | "
            f"{fmt_c(row['mean_net_edge_cents'])} | {ci} | {fmt_pct(row['net_positive_rate'])} | "
            f"{fmt_pct(row['top2_concentration'])} | {'PASS' if row['pass_gate'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## Caveats and known limitations",
            "",
            "- Public trade prints are not executable order-book quotes; treat this as signal discovery, not tradable EV.",
            "- Same-side mode for SELL signals means the token price fell after the crowd sold; it does not imply a live short route exists.",
            "- Cost stress is per share and does not model queue position, market impact, or minimum order constraints.",
            "- Bootstrap resamples market/day clusters, but clustered wallet behavior can still overstate independence.",
            "- No live bot state, service, wallet, cap, or systemd unit is touched.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--bot-f-db", default=str(DEFAULT_BOT_F_DB))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--docs-report", default=str(DEFAULT_DOCS_REPORT))
    parser.add_argument("--since", default="all")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--tolerance-sec", type=int, default=300)
    parser.add_argument("--horizon-sec", action="append", type=int, dest="horizons")
    parser.add_argument("--cost-cents", action="append", type=float, dest="costs")
    parser.add_argument("--api-limit", type=int, default=1000)
    parser.add_argument("--api-max-pages", type=int, default=6)
    parser.add_argument("--api-sleep-sec", type=float, default=0.05)
    parser.add_argument("--max-api-markets", type=int, default=150)
    parser.add_argument("--min-cell-n", type=int, default=100)
    parser.add_argument("--n-bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1729)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    horizons = tuple(args.horizons or DEFAULT_HORIZONS)
    costs = tuple(args.costs or DEFAULT_COSTS_CENTS)
    report = build_report(
        bot_f_db=Path(args.bot_f_db),
        since=parse_since(args.since),
        limit=args.limit,
        horizons=horizons,
        tolerance_sec=args.tolerance_sec,
        costs_cents=costs,
        api_limit=args.api_limit,
        api_max_pages=args.api_max_pages,
        api_sleep_sec=args.api_sleep_sec,
        max_api_markets=args.max_api_markets,
        min_cell_n=args.min_cell_n,
        n_bootstrap=args.n_bootstrap,
        seed=args.seed,
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    markdown = render_markdown(report)
    out_json, out_md = write_report_pair(Path(args.out_dir), f"bot_f_crowd_momentum_ev_{stamp}", report, markdown)
    docs_report = Path(args.docs_report)
    docs_report.parent.mkdir(parents=True, exist_ok=True)
    docs_report.write_text(markdown, encoding="utf-8")
    print(f"wrote {out_md}")
    print(f"wrote {out_json}")
    print(f"wrote {docs_report}")
    print(f"passing_cells={len(report['passing_rows'])} observations={report['observation_diagnostics']['observations']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
