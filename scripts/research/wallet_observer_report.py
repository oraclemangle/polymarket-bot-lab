#!/usr/bin/env python3
"""Forward Murphy decomposition over the wallet_observer DB.

Run after the observer has accumulated enough samples. The forward
window is 7 days (operator decision 2026-05-08), with these gate
thresholds calibrated for the smaller sample:

- Cohort-level decision: ≥ 200 settled trades, resolution > 0.001,
  top-2 P&L < 50%, 95% CI lower > 0
- Per-wallet sub-cohort: ≥ 30 settled trades for a wallet to be scored
  individually (informational; cohort gate dominates)

Joins observed trades to settled markets (populated by
`wallet_observer_resolutions.py` from Polymarket Gamma) and applies
the same math primitives as the historical Murphy decomposition.
Reports whether the historical edge survives in the live forward
sample.

Read-only against `data/wallet_tag_forward.db`. Writes Markdown + JSON
under `data/reports/wallet_observer/`.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.research.math_primitives.hazard import (  # noqa: E402
    bootstrap_roi_ci_by_day,
    top_k_pnl_concentration,
)
from scripts.research.math_primitives.proper_scoring import (  # noqa: E402
    log_loss,
    murphy_decomposition,
    spherical_score,
)

DEFAULT_OBSERVER_DB = REPO_ROOT / "data" / "wallet_tag_forward.db"
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "reports" / "wallet_observer"

_MIN_TRADES_FOR_VERDICT = 200
_MIN_RESOLUTION = 0.001
_MAX_TOP_2_CONCENTRATION = 0.50


def _connect_ro(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"DB not found: {path}")
    con = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro", uri=True, timeout=10.0
    )
    con.row_factory = sqlite3.Row
    return con


def load_observed_trades_with_outcomes(
    con: sqlite3.Connection, fee_rate: float = 0.04
) -> list[dict[str, Any]]:
    """Pull settled BUY trades and compute per-trade P&L.

    The Data API row's `outcome` / `outcome_index` identifies the token
    bought by the observed wallet. Gamma's first outcome-price element is
    YES, so NO buys win when `yes_won == 0`.
    """
    market_cols = {
        str(row["name"])
        for row in con.execute("PRAGMA table_info(observed_markets)").fetchall()
    }
    settlement_clause = "m.settled = 1"
    proxy_expr = "0"
    if "proxy_settled" in market_cols:
        proxy_expr = "COALESCE(m.proxy_settled, 0)"
        strict_count = int(
            con.execute(
                """
                SELECT COUNT(*)
                FROM observed_trades t
                JOIN observed_markets m ON t.condition_id = m.condition_id
                WHERE m.settled = 1
                  AND t.taker_direction = 'BUY'
                  AND t.token_amount IS NOT NULL
                  AND t.price IS NOT NULL
                  AND m.yes_won IS NOT NULL
                """
            ).fetchone()[0]
            or 0
        )
        if strict_count < _MIN_TRADES_FOR_VERDICT:
            settlement_clause = "(m.settled = 1 OR COALESCE(m.proxy_settled, 0) = 1)"
    rows = con.execute(
        f"""
        SELECT t.wallet, t.market_id, t.timestamp_s, t.price,
               t.token_amount, t.usd_amount, t.taker_direction,
               t.condition_id, t.outcome, t.outcome_index,
               m.yes_won, m.end_date_iso, m.settled,
               {proxy_expr} AS proxy_settled
        FROM observed_trades t
        JOIN observed_markets m ON t.condition_id = m.condition_id
        WHERE {settlement_clause}
          AND t.taker_direction = 'BUY'
          AND t.token_amount IS NOT NULL
          AND t.price IS NOT NULL
          AND m.yes_won IS NOT NULL
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        token_is_yes = _trade_token_is_yes(r["outcome"], r["outcome_index"])
        if token_is_yes is None:
            continue
        price = float(r["price"])
        size = float(r["token_amount"])
        notional = float(r["usd_amount"]) if r["usd_amount"] else price * size
        yes_won = int(r["yes_won"]) if r["yes_won"] is not None else 0
        token_won = yes_won if token_is_yes else 1 - yes_won
        fee_per_share = price * (1.0 - price) * fee_rate
        entry_cost = price * size + fee_per_share * size
        payout = float(token_won) * size
        pnl = payout - entry_cost
        roi = pnl / max(entry_cost, 1e-9)
        end_date = str(r["end_date_iso"] or "")
        trading_day = end_date.split("T")[0] if "T" in end_date else end_date[:10]
        out.append(
            {
                "wallet": r["wallet"],
                "market_id": r["market_id"],
                "condition_id": r["condition_id"],
                "outcome": r["outcome"],
                "outcome_index": r["outcome_index"],
                "price": price,
                "size": size,
                "notional": notional,
                "yes_won": token_won,
                "market_yes_won": yes_won,
                "settlement_label_type": (
                    "strict" if int(r["settled"] or 0) == 1 else "proxy"
                ),
                "pnl": pnl,
                "roi": roi,
                "trading_day": trading_day,
            }
        )
    return out


def _trade_token_is_yes(outcome: object, outcome_index: object) -> bool | None:
    """Return whether the bought token is YES."""
    if outcome_index is not None:
        try:
            idx = int(outcome_index)
        except (TypeError, ValueError):
            idx = None
        if idx == 0:
            return True
        if idx == 1:
            return False
    label = str(outcome or "").strip().lower()
    if label in {"yes", "y"}:
        return True
    if label in {"no", "n"}:
        return False
    return None


def cohort_metrics(label: str, trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"label": label, "n": 0, "skipped": "empty"}
    p = [t["price"] for t in trades]
    y = [t["yes_won"] for t in trades]
    pnls = [t["pnl"] for t in trades]
    rois = [t["roi"] for t in trades]
    decomp = murphy_decomposition(p, y, n_bins=10)
    daily: dict[str, list[float]] = defaultdict(list)
    for t in trades:
        daily[t["trading_day"]].append(t["roi"])
    daily_means = [sum(v) / len(v) for v in daily.values()]
    ci_lo, ci_hi = bootstrap_roi_ci_by_day(
        daily_means, n_resamples=10_000, alpha=0.05
    )
    conc = top_k_pnl_concentration(pnls, k_values=(1, 2, 5))
    n_wins = sum(1 for t in trades if t["yes_won"])
    mean_implied = sum(p) / len(p)
    edge_pp = (n_wins / len(trades)) - mean_implied
    return {
        "label": label,
        "n": len(trades),
        "n_wins": n_wins,
        "hit_rate": n_wins / len(trades),
        "mean_implied": mean_implied,
        "edge_pp": edge_pp,
        "mean_roi": sum(rois) / len(rois),
        "total_pnl_usd": round(sum(pnls), 2),
        "trading_days": len(daily),
        "brier": decomp.brier,
        "log_loss": log_loss(p, y),
        "spherical": spherical_score(p, y),
        "reliability": decomp.reliability,
        "resolution": decomp.resolution,
        "uncertainty": decomp.uncertainty,
        "roi_ci_95_lower": ci_lo,
        "roi_ci_95_upper": ci_hi,
        "top_1_concentration": conc[1],
        "top_2_concentration": conc[2],
        "top_5_concentration": conc[5],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Wallet Observer Forward Murphy Decomposition",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Observer DB: `{report['observer_db']}`",
        "",
        "## Sample",
        "",
        f"- Settled wallet trades: `{report['n_total']}`",
        f"- Strict-settled trades: `{report['n_strict']}`",
        f"- Proxy-settled trades: `{report['n_proxy']}`",
        f"- Settlement scoring mode: `{report['settlement_mode']}`",
        f"- Unique wallets observed: `{report['n_wallets']}`",
        "",
        "## Cohort comparison",
        "",
        "| Cohort | n | Hit | Implied | Edge pp | Resolution | Top-2 | 95% CI ROI | Verdict |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for c in report["cohorts"]:
        if c.get("skipped"):
            lines.append(f"| {c['label']} | _{c['skipped']}_ | | | | | | | |")
            continue
        res_ok = c["resolution"] > _MIN_RESOLUTION
        conc_ok = c["top_2_concentration"] < _MAX_TOP_2_CONCENTRATION
        ci_ok = c["roi_ci_95_lower"] > 0
        n_ok = c["n"] >= _MIN_TRADES_FOR_VERDICT
        if not n_ok:
            verdict = "INSUFFICIENT"
        elif res_ok and conc_ok and ci_ok:
            verdict = "PASS"
        else:
            verdict = "FAIL"
        lines.append(
            f"| {c['label']} | {c['n']} | {c['hit_rate']:.1%} | "
            f"{c['mean_implied']:.1%} | {c['edge_pp']:+.1%} | "
            f"{c['resolution']:.5f} | {c['top_2_concentration']:.0%} | "
            f"({c['roi_ci_95_lower']:+.1%}, {c['roi_ci_95_upper']:+.1%}) | "
            f"{verdict} |"
        )
    lines.append("")
    lines.append("## Gate (7-day forward window)")
    lines.append("")
    lines.append(
        f"- **PASS** = `n ≥ {_MIN_TRADES_FOR_VERDICT}` AND "
        f"`resolution > {_MIN_RESOLUTION}` AND "
        f"`top_2_concentration < {_MAX_TOP_2_CONCENTRATION:.0%}` AND "
        "`roi_ci_95_lower > 0`."
    )
    lines.append(
        f"- **INSUFFICIENT** = sample below {_MIN_TRADES_FOR_VERDICT} "
        "settled trades. Wait for more observation."
    )
    lines.append("- **FAIL** = sample is large enough but a gate fails.")
    lines.append("")
    lines.append("## Caveats")
    lines.append("")
    lines.append(
        "- Forward sample is live observation only; settlement labels "
        "come from the observer DB, populated by "
        "`wallet_observer_resolutions.py` polling Polymarket Gamma "
        "on the configured timer cadence."
    )
    lines.append(
        "- Compare resolution + 95% CI lower bound to the historical "
        "WANGZJ panel (see "
        "`data/reports/wallet_tag_math/wallet_tag_murphy_recent_90d_*`). "
        "If forward results are materially weaker, the historical edge "
        "was survivorship-biased."
    )
    lines.append(
        "- All SQLite connections use mode=ro; no live state mutated."
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--observer-db", default=str(DEFAULT_OBSERVER_DB))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--fee-rate", type=float, default=0.04)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    con = _connect_ro(Path(args.observer_db))
    try:
        trades = load_observed_trades_with_outcomes(con, fee_rate=args.fee_rate)
    finally:
        con.close()
    if not trades:
        print("no settled trades observed yet — nothing to score")
        out_md = out_dir / f"forward_murphy_{stamp}.md"
        out_md.write_text(
            "# Wallet Observer Forward Murphy Decomposition\n\n"
            f"Generated: `{datetime.now(UTC).isoformat()}`\n\n"
            "_No settled trades observed yet._\n",
            encoding="utf-8",
        )
        return 0

    n_strict = sum(1 for t in trades if t.get("settlement_label_type") == "strict")
    n_proxy = sum(1 for t in trades if t.get("settlement_label_type") == "proxy")
    n_wallets = len(set(t["wallet"] for t in trades))

    by_wallet: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        by_wallet[t["wallet"]].append(t)

    cohorts = [
        cohort_metrics("all_observed_wallets", trades),
    ]
    # Per-wallet cohorts for wallets with at least 30 settled trades
    for wallet, ts in by_wallet.items():
        if len(ts) >= 30:
            cohorts.append(cohort_metrics(f"wallet={wallet[:10]}...", ts))

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "observer_db": str(args.observer_db),
        "n_total": len(trades),
        "n_strict": n_strict,
        "n_proxy": n_proxy,
        "settlement_mode": (
            "strict_only" if n_strict >= _MIN_TRADES_FOR_VERDICT else "strict_plus_proxy"
        ),
        "n_wallets": n_wallets,
        "cohorts": cohorts,
    }
    out_md = out_dir / f"forward_murphy_{stamp}.md"
    out_json = out_dir / f"forward_murphy_{stamp}.json"
    out_md.write_text(render_markdown(report), encoding="utf-8")
    out_json.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    print(f"wrote {out_md}")
    print(f"wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
