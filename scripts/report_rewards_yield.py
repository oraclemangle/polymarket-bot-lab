#!/usr/bin/env python3
"""Maker-rewards yield report — verdict on whether LRP is worth chasing.

Reads `data/rewards_snapshot.jsonl` (produced by
`scripts/log_rewards_daily.py`) and renders the per-day reward yield
per dollar of *day-summed* eligible maker notional. Because the
denominator already sums daily notional across the window, the ratio
is itself a per-day rate — no further division by N_days.

  daily_yield_per_dollar = sum(rewards_received_usd) / sum(eligible_notional)
  apr_estimate           = daily_yield_per_dollar * 365

The decision gate is binary, set in advance per ADR (no
"let's see how it goes"):

  daily_yield_per_dollar >= GATE_DAILY_YIELD  → fold rewards into
                                                Bot E EV math
  daily_yield_per_dollar <  GATE_DAILY_YIELD  → ignore rewards forever

GATE_DAILY_YIELD defaults to 0.20 (20¢/day per $1) per the original
Session 35 plan; override with --gate.

Usage:
    python -m scripts.report_rewards_yield [--in PATH] [--gate FLOAT]
                                           [--min-days N] [--bot bot_e]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.rewards_monitor import DEFAULT_SNAPSHOT_PATH  # noqa: E402

DEFAULT_GATE = Decimal("0.20")  # USD/day per $1 of eligible maker notional
DEFAULT_MIN_DAYS = 14


def _load_snapshots(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"warn: skipping malformed row: {e}", file=sys.stderr)
    return out


def _latest_per_date(rows: list[dict]) -> list[dict]:
    """If the runner fired more than once on a date, keep the latest."""
    by_date: dict[str, dict] = {}
    for r in rows:
        d = r.get("date")
        if not d:
            continue
        prior = by_date.get(d)
        if prior is None or (r.get("run_at", "") > prior.get("run_at", "")):
            by_date[d] = r
    return [by_date[d] for d in sorted(by_date)]


def _aggregate(rows: list[dict], focus_bot: str | None) -> dict:
    eligible_by_bot: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    total_by_bot: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    rewards_total = Decimal(0)
    for r in rows:
        rewards_total += Decimal(str(r.get("rewards_received_usd") or 0))
        for bot, n in (r.get("maker_notional_on_eligible_by_bot") or {}).items():
            if focus_bot and bot != focus_bot:
                continue
            eligible_by_bot[bot] += Decimal(str(n))
        for bot, n in (r.get("maker_notional_by_bot") or {}).items():
            if focus_bot and bot != focus_bot:
                continue
            total_by_bot[bot] += Decimal(str(n))
    return {
        "rewards_total_usd": rewards_total,
        "eligible_notional_by_bot": dict(eligible_by_bot),
        "total_notional_by_bot": dict(total_by_bot),
    }


def render(rows: list[dict], gate: Decimal, min_days: int, focus_bot: str | None) -> int:
    rows = _latest_per_date(rows)
    if not rows:
        print("no snapshots found — has the daily timer run yet?")
        return 1
    n_days = len(rows)
    agg = _aggregate(rows, focus_bot)
    rewards_total = agg["rewards_total_usd"]
    eligible_total = sum(agg["eligible_notional_by_bot"].values()) or Decimal(0)

    print(f"date_range:           {rows[0]['date']} → {rows[-1]['date']} ({n_days} days)")
    print(f"rewards_received_usd: {rewards_total}")
    print(f"eligible_notional:    {eligible_total} (sum across kept bots)")
    print()
    print("per-bot eligible notional:")
    for bot, n in sorted(agg["eligible_notional_by_bot"].items()):
        print(f"  {bot:20s} {n}")
    print()

    if eligible_total == 0:
        print("eligible_notional == 0 — no maker fills on reward-eligible markets.")
        print("verdict: indeterminate. wire HOT_WALLET_ADDRESS or check Bot E quoting.")
        return 2

    daily_yield = rewards_total / eligible_total
    apr = daily_yield * Decimal(365)

    print(f"daily_yield_per_$:     {daily_yield}")
    print(f"apr_estimate:          {apr}")
    print(f"gate_daily_yield:      {gate}")
    print()

    if n_days < min_days:
        print(f"verdict: WAIT — only {n_days} days of data, need >= {min_days}.")
        return 3
    if daily_yield >= gate:
        print("verdict: FOLD INTO EV — rewards materially shift Bot E unit economics.")
        return 0
    print("verdict: IGNORE FOREVER — rewards are below gate; stop instrumenting.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--in", dest="path", default=str(DEFAULT_SNAPSHOT_PATH))
    ap.add_argument("--gate", type=Decimal, default=DEFAULT_GATE)
    ap.add_argument("--min-days", type=int, default=DEFAULT_MIN_DAYS)
    ap.add_argument("--bot", help="restrict to one bot_id (default: all bots)")
    args = ap.parse_args()
    rows = _load_snapshots(Path(args.path))
    return render(rows, args.gate, args.min_days, args.bot)


if __name__ == "__main__":
    raise SystemExit(main())
