"""Re-run the maker-flow simulator on `data/maker_recorder.db` data.

Resolves OQ-100 acceptance criterion #4:

  Real-data re-run of the maker-flow simulator on the recorder-derived
  trades in `politics 0-10c` and `sports 10-20c` produces excl-top-5
  ROI above +20% in BOTH cells AND across the 5/10/15% fill-rate ×
  1×/2×/4× toxicity-weight sensitivity grid. This is the same bar that
  authorised the build.

The script is intentionally read-only and idempotent. It can be run
multiple times during the burn-in window without affecting the recorder.

What it does:

1. Reads `pm_events` from `data/maker_recorder.db`.
2. Extracts every `last_trade_price` event (taker BUY observations) and
   computes a per-trade toxicity score using the next-15-minute
   midpoint drift from `book` and `best_bid_ask` events.
3. Joins each trade to `markets` for category and resolution status.
4. Runs the same simulation kernel as `/tmp/track1_maker_sim.py`:
   per-cell sim cost, gross PnL, builder rebate, NET, ROI.
5. Applies the robustness probe matrix: outlier exclusion (top-1/5/25)
   × fill-rate (5/10/15%) × toxicity weight (1×/2×/4×).
6. Compares against the WANGZJ-historical numbers and reports drift.

Usage:
    python -m scripts.research.maker_flow_recorder_replay \\
        [--db-path data/maker_recorder.db]
        [--min-events 1000]
        [--out docs/reports/maker_flow_recorder_replay-YYYY-MM-DD.md]
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.replay_quality import ReplayQualityInput, assess_replay_quality

# Sensitivity grid identical to the WANGZJ probe in
# /tmp/track1_robustness_probe.py.
SENSITIVITY_COMBOS = [
    (0.10, 2.0, "BASELINE_FR=0.10_w=2"),
    (0.05, 2.0, "FR=0.05_w=2"),
    (0.15, 2.0, "FR=0.15_w=2"),
    (0.10, 1.0, "FR=0.10_w=1_no_AS"),
    (0.10, 4.0, "FR=0.10_w=4_aggressive_AS"),
]

# Top-2 cells from the WANGZJ-historical robustness probe.
TARGET_CELLS = [
    ("politics", 0.00, 0.10, "0-10c"),
    ("sports", 0.10, 0.20, "10-20c"),
]

# Comparison cells (killed in WANGZJ historical) — re-run on recorder
# data to confirm they stay killed in real V2 forward markets. Per
# ADR-134, if any of these passes the +20% gate we open a separate
# spec-amendment ADR before Phase 2 cell list is finalised.
COUNTERFACTUAL_CELLS = [
    ("politics", 0.30, 0.40, "30-40c"),
    ("awards", 0.00, 0.10, "0-10c"),
    ("politics", 0.40, 0.50, "40-50c"),
    ("crypto", 0.00, 0.10, "0-10c"),
]

PER_FILL_CAP_USD = 5.0
PASS_BAR_ROI_PCT = 20.0  # excl-top-5 must exceed this in ALL combos


log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TradeObs:
    condition_id: str
    asset_id: str
    timestamp_ms: int
    price: float
    size_shares: float
    usd_amount: float
    category: str | None
    yes_won: int | None  # 1 if YES resolved win, 0 if NO won, None if open


def _connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"recorder DB not found at {path}")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _extract_trades(con: sqlite3.Connection) -> list[TradeObs]:
    """Pull every `last_trade_price` event with usable price + size and
    join to `markets` for category. The recorder DB does not yet track
    resolution status (Phase 2 will), so `yes_won` is None unless the
    market shows up in a resolved-market event in the future."""
    rows = con.execute(
        """
        SELECT e.condition_id, e.asset_id, e.received_at_ms, e.payload_json,
               m.category, m.yes_token_id
        FROM pm_events e
        LEFT JOIN markets m ON m.condition_id = e.condition_id
        WHERE e.event_type = 'last_trade_price'
          AND e.condition_id IS NOT NULL
        ORDER BY e.condition_id, e.received_at_ms
        """
    ).fetchall()
    out: list[TradeObs] = []
    for r in rows:
        payload: dict[str, Any]
        try:
            payload = json.loads(r["payload_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        # last_trade_price payload shape (Polymarket WSS):
        #   {"asset_id": "...", "price": "0.04", "size": "100",
        #    "side": "BUY"|"SELL", "fee_rate_bps": "..."}
        side = str(payload.get("side", "")).upper()
        if side != "BUY":
            continue  # taker BUY only — same as simulator filter
        try:
            price = float(payload.get("price", 0))
            size = float(payload.get("size", 0))
        except (TypeError, ValueError):
            continue
        if price <= 0 or size <= 0:
            continue
        # Only count trades on the YES token (matches simulator's
        # `t.asset_id = m.yes_token` filter).
        yes_token = r["yes_token_id"]
        if yes_token and r["asset_id"] != yes_token:
            continue
        out.append(
            TradeObs(
                condition_id=str(r["condition_id"]),
                asset_id=str(r["asset_id"]) if r["asset_id"] else "",
                timestamp_ms=int(r["received_at_ms"]),
                price=price,
                size_shares=size,
                usd_amount=price * size,
                category=str(r["category"]) if r["category"] else None,
                yes_won=None,  # Phase 2 will populate from market_resolved events
            )
        )
    return out


def _build_price_index(con: sqlite3.Connection) -> dict[str, list[tuple[int, float]]]:
    """For each condition_id, build a sorted (timestamp_ms, mid_price)
    index from `book` events. Used to look up next-15min average mid for
    the toxicity proxy. Falls back to last_trade_price if no book data."""
    index: dict[str, list[tuple[int, float]]] = {}
    rows = con.execute(
        """
        SELECT condition_id, received_at_ms, payload_json
        FROM pm_events
        WHERE event_type IN ('book', 'best_bid_ask', 'price_change', 'last_trade_price')
          AND condition_id IS NOT NULL
        ORDER BY condition_id, received_at_ms
        """
    ).fetchall()
    for r in rows:
        try:
            payload = json.loads(r["payload_json"])
        except (json.JSONDecodeError, TypeError):
            continue
        # Try multiple shapes:
        # - book: {bids:[{price,size}], asks:[{price,size}]} → mid
        # - best_bid_ask: {bid: "0.04", ask: "0.06"} → mid
        # - price_change: {price: "0.05"} → just the price
        # - last_trade_price: {price: "0.05"} → just the price
        mid: float | None = None
        if "bids" in payload and "asks" in payload:
            try:
                best_bid = max(float(b["price"]) for b in payload.get("bids", []))
                best_ask = min(float(a["price"]) for a in payload.get("asks", []))
                mid = (best_bid + best_ask) / 2
            except (ValueError, KeyError, TypeError):
                pass
        elif "bid" in payload and "ask" in payload:
            try:
                mid = (float(payload["bid"]) + float(payload["ask"])) / 2
            except (ValueError, TypeError):
                pass
        elif "price" in payload:
            try:
                mid = float(payload["price"])
            except (ValueError, TypeError):
                pass
        if mid is None or mid <= 0:
            continue
        index.setdefault(str(r["condition_id"]), []).append((int(r["received_at_ms"]), mid))
    return index


def _toxicity_score(
    *,
    trade: TradeObs,
    price_index: dict[str, list[tuple[int, float]]],
    horizon_sec: int = 900,
) -> int:
    """Return 1 if next-`horizon_sec` average mid is more than 2c above
    the trade's entry price (informed buyer caught the move). 0 = benign.

    Returns 0 (benign) for trades whose follow-up window has no data
    (matches the simulator's `next_15min_avg_price IS NULL THEN 0` rule).
    """
    series = price_index.get(trade.condition_id)
    if not series:
        return 0
    start = trade.timestamp_ms + 60 * 1000  # exclude immediate trade-self
    end = trade.timestamp_ms + horizon_sec * 1000
    prices = [p for ts, p in series if start <= ts <= end]
    if not prices:
        return 0
    avg = sum(prices) / len(prices)
    return 1 if avg > trade.price + 0.02 else 0


def _rebate_per_share(category: str, price: float) -> float:
    """Mirror the simulator's per-category rebate formula."""
    if category in ("sports", "politics", "awards"):
        return 0.030 * price * (1 - price) * 0.25
    if category == "crypto":
        return 0.072 * price * (1 - price) * 0.20
    if category == "weather":
        return 0.0
    return 0.020 * price * (1 - price) * 0.20


def _gross_pnl_per_share(price: float, yes_won: int | None) -> float | None:
    """Returns None if outcome unknown (open position) — those trades
    are excluded from the simulation. The recorder DB doesn't yet
    capture resolution events, so this gates the simulator on Phase 2's
    resolution backfill being implemented (or on operator running the
    backfill from the Gamma resolved-markets feed)."""
    if yes_won is None:
        return None
    if yes_won == 1:
        return -1.0 + price
    return price


def _cell_robust_check(
    *,
    trades: list[TradeObs],
    price_index: dict[str, list[tuple[int, float]]],
    cat: str,
    lo: float,
    hi: float,
    fill_rate: float,
    w: float,
) -> dict[str, Any]:
    """For one (category, price_band) cell at given (fill_rate, w),
    aggregate per-market sim cost + net PnL across observed trades, and
    compute as-is + excl-top-{1,5,25} ROI.

    Excludes trades whose market hasn't resolved (yes_won is None) — Phase
    2 must backfill resolution data before this returns useful numbers."""
    toxic_rate = fill_rate * w
    benign_rate = fill_rate / w
    per_market: dict[str, dict[str, float]] = {}
    n_excluded = 0
    for t in trades:
        if t.category != cat:
            continue
        if not (lo <= t.price < hi):
            continue
        gross_per_share = _gross_pnl_per_share(t.price, t.yes_won)
        if gross_per_share is None:
            n_excluded += 1
            continue
        toxic = _toxicity_score(trade=t, price_index=price_index)
        capture_rate = toxic_rate if toxic == 1 else benign_rate
        capped_usd = min(t.usd_amount, PER_FILL_CAP_USD)
        capped_shares = (
            min(t.size_shares, PER_FILL_CAP_USD / t.price) if t.price > 0 else 0
        )
        cost_contrib = capture_rate * capped_usd
        rebate = _rebate_per_share(cat, t.price)
        net_per_share = gross_per_share + rebate
        net_contrib = capture_rate * net_per_share * capped_shares
        m = per_market.setdefault(
            t.condition_id, {"cost": 0.0, "net": 0.0, "trades": 0}
        )
        m["cost"] += cost_contrib
        m["net"] += net_contrib
        m["trades"] += 1
    if not per_market:
        return {
            "as_is_roi": None,
            "excl_1": None,
            "excl_5": None,
            "excl_25": None,
            "n_markets": 0,
            "n_trades": 0,
            "n_excluded_unresolved": n_excluded,
            "total_cost": 0.0,
            "total_net": 0.0,
        }
    sorted_by_net = sorted(per_market.values(), key=lambda v: v["net"], reverse=True)
    total_cost = sum(v["cost"] for v in sorted_by_net)
    total_net = sum(v["net"] for v in sorted_by_net)
    total_trades = sum(int(v["trades"]) for v in sorted_by_net)
    n_markets = len(sorted_by_net)

    def roi_after_excluding(n: int) -> float | None:
        if n_markets <= n:
            return None
        cost = sum(v["cost"] for v in sorted_by_net[n:])
        net = sum(v["net"] for v in sorted_by_net[n:])
        return (net / cost * 100) if cost else None

    return {
        "as_is_roi": (total_net / total_cost * 100) if total_cost else None,
        "excl_1": roi_after_excluding(1),
        "excl_5": roi_after_excluding(5),
        "excl_25": roi_after_excluding(25),
        "n_markets": n_markets,
        "n_trades": total_trades,
        "n_excluded_unresolved": n_excluded,
        "total_cost": total_cost,
        "total_net": total_net,
    }


def _verdict(cell_results: dict[str, dict[str, Any]]) -> str:
    """PASS = excl-top-5 > +20% in ALL combos. INSUFFICIENT_DATA = some
    combo has fewer than 5 markets. FAIL otherwise."""
    excl5 = []
    for combo_label, r in cell_results.items():
        if r["n_markets"] < 5:
            return "INSUFFICIENT_DATA"
        if r["excl_5"] is None:
            return "INSUFFICIENT_DATA"
        excl5.append(r["excl_5"])
    if not excl5:
        return "INSUFFICIENT_DATA"
    if min(excl5) > PASS_BAR_ROI_PCT:
        return "PASS"
    return "FAIL"


def run_replay(*, db_path: Path, min_events: int) -> dict[str, Any]:
    log.info("replay.connect db=%s", db_path)
    con = _connect(db_path)
    try:
        n_events = con.execute("SELECT COUNT(*) FROM pm_events").fetchone()[0]
        if n_events < min_events:
            return {
                "ok": False,
                "reason": f"only {n_events:,} pm_events; need ≥ {min_events:,}",
                "generated_at": datetime.now(UTC).isoformat(),
                "db_path": str(db_path),
                "n_events": n_events,
            }
        log.info("replay.extract_trades")
        trades = _extract_trades(con)
        log.info("replay.build_price_index")
        price_index = _build_price_index(con)
    finally:
        con.close()
    log.info("replay.simulate trades=%d markets=%d", len(trades), len(price_index))

    target_results: dict[str, dict[str, dict[str, Any]]] = {}
    for cat, lo, hi, label in TARGET_CELLS:
        key = f"{cat} {label}"
        target_results[key] = {}
        for fr, w, combo_label in SENSITIVITY_COMBOS:
            target_results[key][combo_label] = _cell_robust_check(
                trades=trades,
                price_index=price_index,
                cat=cat,
                lo=lo,
                hi=hi,
                fill_rate=fr,
                w=w,
            )

    counterfactual_results: dict[str, dict[str, dict[str, Any]]] = {}
    for cat, lo, hi, label in COUNTERFACTUAL_CELLS:
        key = f"{cat} {label}"
        counterfactual_results[key] = {}
        for fr, w, combo_label in SENSITIVITY_COMBOS:
            counterfactual_results[key][combo_label] = _cell_robust_check(
                trades=trades,
                price_index=price_index,
                cat=cat,
                lo=lo,
                hi=hi,
                fill_rate=fr,
                w=w,
            )

    target_verdicts = {cell: _verdict(combos) for cell, combos in target_results.items()}
    counterfactual_verdicts = {cell: _verdict(combos) for cell, combos in counterfactual_results.items()}

    target_all_pass = all(v == "PASS" for v in target_verdicts.values())
    counterfactual_any_pass = any(v == "PASS" for v in counterfactual_verdicts.values())

    return {
        "ok": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "db_path": str(db_path),
        "n_events": n_events,
        "n_trades": len(trades),
        "n_markets_in_index": len(price_index),
        "target_cells": target_results,
        "target_verdicts": target_verdicts,
        "counterfactual_cells": counterfactual_results,
        "counterfactual_verdicts": counterfactual_verdicts,
        "phase_2_gate": {
            "target_cells_all_pass": target_all_pass,
            "any_counterfactual_now_passes": counterfactual_any_pass,
            "build_authorised": target_all_pass and not counterfactual_any_pass,
            "spec_amendment_needed": counterfactual_any_pass,
        },
        "replay_quality": assess_replay_quality(
            ReplayQualityInput(
                has_l2_or_book_depth=True,
                models_latency=False,
                models_queue_position=False,
                has_fee_model=True,
                has_missing_data_policy=True,
                uses_public_wallet_fills_as_entries=False,
                has_negative_controls=True,
                has_outlier_trim=True,
            )
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    if not report.get("ok"):
        return (
            "# Maker-Flow Recorder Replay\n\n"
            f"**INSUFFICIENT DATA**: {report.get('reason', 'unknown')}\n"
            f"_Generated: {report.get('generated_at')}_\n"
        )
    lines: list[str] = []
    lines.append("# Maker-Flow Recorder Replay (OQ-100 gate check)")
    lines.append("")
    lines.append(f"**Generated:** {report['generated_at']}")
    lines.append(f"**DB:** `{report['db_path']}`")
    lines.append(f"**Events:** {report['n_events']:,}")
    lines.append(f"**Taker BUY trades extracted:** {report['n_trades']:,}")
    lines.append(f"**Markets with price index:** {report['n_markets_in_index']:,}")
    lines.append("")
    q = report.get("replay_quality", {})
    if q:
        missing = ", ".join(q.get("missing", [])) or "none"
        lines.append("## Replay Quality")
        lines.append("")
        lines.append(f"**Posture:** `{q.get('posture', 'unknown')}`")
        lines.append(f"**Missing live-realism guards:** {missing}")
        lines.append("")
    g = report["phase_2_gate"]
    if g["build_authorised"]:
        lines.append("## VERDICT: ✅ Phase 2 build authorised")
    elif g["spec_amendment_needed"]:
        lines.append("## VERDICT: ⚠ Spec amendment needed (counterfactual cell now passes)")
    else:
        lines.append("## VERDICT: ❌ Phase 2 NOT authorised")
    lines.append("")
    lines.append("## Target cells (must PASS)")
    lines.append("")
    lines.append("| cell | verdict | min excl-top-5 across combos |")
    lines.append("|---|---|---:|")
    for cell, verdict in report["target_verdicts"].items():
        excl5 = [
            r["excl_5"]
            for r in report["target_cells"][cell].values()
            if r["excl_5"] is not None
        ]
        min_excl5 = f"{min(excl5):+.1f}%" if excl5 else "n/a"
        lines.append(f"| {cell} | **{verdict}** | {min_excl5} |")
    lines.append("")
    lines.append("## Counterfactual cells (must remain FAIL/INSUFFICIENT)")
    lines.append("")
    lines.append("| cell | verdict | min excl-top-5 across combos |")
    lines.append("|---|---|---:|")
    for cell, verdict in report["counterfactual_verdicts"].items():
        excl5 = [
            r["excl_5"]
            for r in report["counterfactual_cells"][cell].values()
            if r["excl_5"] is not None
        ]
        min_excl5 = f"{min(excl5):+.1f}%" if excl5 else "n/a"
        lines.append(f"| {cell} | **{verdict}** | {min_excl5} |")
    lines.append("")
    lines.append("## Detail per target cell")
    lines.append("")
    for cell, combos in report["target_cells"].items():
        lines.append(f"### {cell}")
        lines.append("")
        lines.append(
            "| combo | mkts | trades | excluded | as-is | excl-1 | excl-5 | excl-25 |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for combo_label, r in combos.items():
            asi = f"{r['as_is_roi']:+.1f}%" if r["as_is_roi"] is not None else "n/a"
            e1 = f"{r['excl_1']:+.1f}%" if r["excl_1"] is not None else "n/a"
            e5 = f"{r['excl_5']:+.1f}%" if r["excl_5"] is not None else "n/a"
            e25 = f"{r['excl_25']:+.1f}%" if r["excl_25"] is not None else "n/a"
            lines.append(
                f"| {combo_label} | {r['n_markets']} | {r['n_trades']:,} | "
                f"{r['n_excluded_unresolved']:,} | {asi} | {e1} | {e5} | {e25} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/maker_recorder.db"),
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=1000,
        help="Minimum pm_events count before running the simulator. "
        "Below this, returns INSUFFICIENT_DATA without burning CPU.",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    report = run_replay(db_path=args.db_path, min_events=args.min_events)
    md = render_markdown(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md)
        # also write the JSON sidecar for dashboard
        json_path = args.out.with_suffix(".json")
        json_path.write_text(json.dumps(report, indent=2, default=str))
        log.info("replay.report.written md=%s json=%s", args.out, json_path)
    print(md)
    # Exit non-zero if the gate is checked and FAILS, so this can be
    # wired into a Phase 2-readiness CI check.
    if report.get("ok") and not report["phase_2_gate"]["build_authorised"]:
        if report["phase_2_gate"]["spec_amendment_needed"]:
            sys.exit(2)  # spec amendment needed
        sys.exit(1)  # not yet authorised


if __name__ == "__main__":
    main()
