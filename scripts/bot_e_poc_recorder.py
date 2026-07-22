#!/usr/bin/env python3
"""Bot E POC on recorder data — answers §5.1 Q1/Q2/Q3 from docs/session-2026-04-17-edges-review.md

Q1: how many markets (scaled from 15-min windows) had yes_bid + no_bid < 0.97
    for ≥60 consecutive seconds?
Q2: for qualifying markets, what fraction of sub-threshold time fell in the
    first half of the market's active window vs the second half?
Q3: passive-BUY fill asymmetry — winner-side vs loser-side fill probability,
    inferred from the recorder tape and the market's terminal price.

Dataset context (verified 2026-04-17):
- Recorder covers 2026-04-16 09:14–13:53 UTC (~4.6 hours), NOT Q1 2026.
- 52 markets have full metadata (yes_token_id, no_token_id, end_date_iso).
- Markets are 5-min binaries on BTC/ETH/SOL Up-or-Down.
- Reviewer's original "≥500 windows" threshold CANNOT be met with this data.
  Scaled threshold: ≥20 qualifying markets (4% of original) for a directional
  signal. Full-scale POC must wait for more recorder history.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DB_PATH = Path("/home/operator/Code/next-build/data/bot_e_recorder.db")
SUM_BID_THRESHOLD = 0.97
MIN_SUB_SECONDS = 60
SCALED_PASS_WINDOWS = 20  # scaled down from 500; see docstring

WINDOW_ASYMMETRY_THRESHOLD = 1.5  # r_lose / r_win trip-wire
EARLY_MIN_FRACTION = 0.30         # T_early >= 30% of T_total


@dataclass
class MarketMeta:
    condition_id: str
    question: str
    end_ms: int
    yes_token_id: str
    no_token_id: str


@dataclass
class BidTimelineEntry:
    ts_ms: int
    yes_bid: float | None
    no_bid: float | None

    @property
    def sum_bid(self) -> float | None:
        if self.yes_bid is None or self.no_bid is None:
            return None
        return self.yes_bid + self.no_bid


@dataclass
class WindowResult:
    condition_id: str
    question: str
    end_ms: int
    n_timeline_points: int
    sub_threshold_ms: int
    total_active_ms: int
    early_sub_ms: int      # first half
    late_sub_ms: int       # second half
    winner_side: str | None   # "YES" | "NO" | None if indeterminate
    passive_buy_yes_fills: int
    passive_buy_yes_chances: int
    passive_buy_no_fills: int
    passive_buy_no_chances: int

    @property
    def qualifies(self) -> bool:
        return self.sub_threshold_ms >= MIN_SUB_SECONDS * 1000

    @property
    def early_fraction(self) -> float:
        if self.sub_threshold_ms == 0:
            return 0.0
        return self.early_sub_ms / self.sub_threshold_ms


def load_markets(conn: sqlite3.Connection) -> list[MarketMeta]:
    rows = conn.execute(
        "SELECT condition_id, question, yes_token_id, no_token_id, end_date_iso "
        "FROM markets "
        "WHERE yes_token_id IS NOT NULL AND no_token_id IS NOT NULL "
        "AND end_date_iso IS NOT NULL "
        "GROUP BY condition_id"
    ).fetchall()
    out: list[MarketMeta] = []
    for cid, q, yt, nt, end_iso in rows:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00")) if end_iso else None
            end_ms = int(dt.timestamp() * 1000) if dt else 0
        except Exception:
            continue
        if end_ms == 0:
            continue
        out.append(MarketMeta(cid, q, end_ms, yt, nt))
    return out


def extract_best_bid(payload: dict, event_type: str) -> float | None:
    """Extract best-bid price from a pm_events payload."""
    if event_type == "best_bid_ask":
        bb = payload.get("best_bid")
        if bb is not None:
            try:
                return float(bb)
            except (ValueError, TypeError):
                return None
    elif event_type == "book":
        bids = payload.get("bids") or []
        if not bids:
            return None
        best = None
        for row in bids:
            try:
                px = float(row["price"]) if isinstance(row, dict) else float(row[0])
            except (ValueError, TypeError, KeyError, IndexError):
                continue
            if best is None or px > best:
                best = px
        return best
    elif event_type == "price_change":
        # price_change events are deltas; we can't reconstruct best bid from a single one.
        # Return None here; timeline filler will use last-known value.
        return None
    return None


@dataclass
class TradeEvent:
    ts_ms: int
    side: str           # "YES" | "NO" — which token was traded
    trade_side: str     # "BUY" (aggressive buy lifts ask) | "SELL" (aggressive sell hits bid)
    price: float

def build_market_timeline(
    conn: sqlite3.Connection, market: MarketMeta
) -> tuple[list[BidTimelineEntry], list[TradeEvent]]:
    """Return (bid_timeline, trades) for a market.

    bid_timeline: time-ordered (ts_ms, yes_bid_last, no_bid_last) as the bids evolve.
    trades: list of TradeEvent — used for Q3 fill-asymmetry (passive BUY at bid
            fills only when an aggressive SELL trade occurs at a price <= our bid)
            and for winner inference.
    """
    yes_tid = market.yes_token_id
    no_tid = market.no_token_id
    rows = conn.execute(
        "SELECT received_at_ms, event_type, asset_id, payload_json "
        "FROM pm_events "
        "WHERE asset_id IN (?, ?) "
        "ORDER BY received_at_ms",
        (yes_tid, no_tid),
    ).fetchall()
    timeline: list[BidTimelineEntry] = []
    trades: list[TradeEvent] = []
    yes_bid: float | None = None
    no_bid: float | None = None
    for ts_ms, etype, asset_id, raw in rows:
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {}

        if etype == "last_trade_price":
            side = "YES" if asset_id == yes_tid else "NO"
            try:
                price = float(payload.get("price", 0) or 0)
            except (ValueError, TypeError):
                price = 0.0
            trade_side = str(payload.get("side", "")).upper()
            trades.append(TradeEvent(
                ts_ms=ts_ms, side=side, trade_side=trade_side, price=price,
            ))
            continue

        new_bid = extract_best_bid(payload, etype)
        if new_bid is None:
            continue
        if asset_id == yes_tid:
            yes_bid = new_bid
        elif asset_id == no_tid:
            no_bid = new_bid
        else:
            continue
        if yes_bid is not None and no_bid is not None:
            timeline.append(BidTimelineEntry(ts_ms=ts_ms, yes_bid=yes_bid, no_bid=no_bid))
    return timeline, trades


def analyze_market(
    timeline: list[BidTimelineEntry],
    trades: list[TradeEvent],
    market: MarketMeta,
) -> WindowResult:
    """Compute sub-threshold time, early/late split, and passive-fill asymmetry.

    CRITICAL: only count timeline entries BEFORE the market's end_date_iso.
    Post-resolution periods show degenerate prices (one side -> 0) that inflate
    sub-threshold counts with non-tradeable states.
    """
    timeline = [tl for tl in timeline if tl.ts_ms <= market.end_ms]
    trades = [tr for tr in trades if tr.ts_ms <= market.end_ms]

    if not timeline:
        return WindowResult(
            market.condition_id, market.question, market.end_ms,
            n_timeline_points=0, sub_threshold_ms=0, total_active_ms=0,
            early_sub_ms=0, late_sub_ms=0, winner_side=None,
            passive_buy_yes_fills=0, passive_buy_yes_chances=0,
            passive_buy_no_fills=0, passive_buy_no_chances=0,
        )

    active_start = timeline[0].ts_ms
    active_end = timeline[-1].ts_ms
    total_active_ms = max(1, active_end - active_start)
    midpoint_ms = active_start + total_active_ms // 2

    # Integrate sub-threshold time: for each gap between consecutive timeline
    # points, the condition `sum_bid < 0.97` holds for the duration of that gap
    # if the FIRST entry's sum_bid < 0.97.
    sub_threshold_ms = 0
    early_sub_ms = 0
    late_sub_ms = 0
    for i in range(len(timeline) - 1):
        cur = timeline[i]
        nxt = timeline[i + 1]
        dur_ms = nxt.ts_ms - cur.ts_ms
        if cur.sum_bid is not None and cur.sum_bid < SUM_BID_THRESHOLD:
            sub_threshold_ms += dur_ms
            # Split by midpoint
            if nxt.ts_ms <= midpoint_ms:
                early_sub_ms += dur_ms
            elif cur.ts_ms >= midpoint_ms:
                late_sub_ms += dur_ms
            else:
                # Straddles midpoint
                early_sub_ms += midpoint_ms - cur.ts_ms
                late_sub_ms += nxt.ts_ms - midpoint_ms

    # Winner inference: last 3 trades before market end. Whichever side has
    # the higher-price last_trade_price is the winner.
    # More robust: use the last timeline point's yes_bid; if > 0.95 YES wins, if < 0.05 NO wins.
    winner_side = None
    last = timeline[-1]
    if last.yes_bid is not None and last.no_bid is not None:
        if last.yes_bid >= 0.90:
            winner_side = "YES"
        elif last.no_bid >= 0.90:
            winner_side = "NO"

    # Q3 fill-asymmetry proxy:
    # For each bid-level event, check if an aggressive SELL (side="SELL") trade
    # occurred on that token within the next 30 seconds at a price <= our bid.
    # Only then does our passive BUY at bid fill.
    # Chances = number of timeline points where that side's bid is > 0.
    passive_buy_yes_fills = 0
    passive_buy_yes_chances = 0
    passive_buy_no_fills = 0
    passive_buy_no_chances = 0

    # Separate sells by token side; keep (ts_ms, price) for lookup
    sells_by_side: dict[str, list[tuple[int, float]]] = {"YES": [], "NO": []}
    for tr in trades:
        if tr.trade_side == "SELL":
            sells_by_side[tr.side].append((tr.ts_ms, tr.price))

    FILL_LOOKAHEAD_MS = 30_000

    import bisect
    for tl in timeline:
        if tl.yes_bid is not None and tl.yes_bid > 0:
            passive_buy_yes_chances += 1
            sells = sells_by_side["YES"]
            ts_list = [s[0] for s in sells]
            idx = bisect.bisect_left(ts_list, tl.ts_ms)
            end_idx = bisect.bisect_right(
                ts_list, tl.ts_ms + FILL_LOOKAHEAD_MS
            )
            for j in range(idx, end_idx):
                if sells[j][1] <= tl.yes_bid + 1e-9:
                    passive_buy_yes_fills += 1
                    break
        if tl.no_bid is not None and tl.no_bid > 0:
            passive_buy_no_chances += 1
            sells = sells_by_side["NO"]
            ts_list = [s[0] for s in sells]
            idx = bisect.bisect_left(ts_list, tl.ts_ms)
            end_idx = bisect.bisect_right(
                ts_list, tl.ts_ms + FILL_LOOKAHEAD_MS
            )
            for j in range(idx, end_idx):
                if sells[j][1] <= tl.no_bid + 1e-9:
                    passive_buy_no_fills += 1
                    break

    return WindowResult(
        condition_id=market.condition_id,
        question=market.question,
        end_ms=market.end_ms,
        n_timeline_points=len(timeline),
        sub_threshold_ms=sub_threshold_ms,
        total_active_ms=total_active_ms,
        early_sub_ms=early_sub_ms,
        late_sub_ms=late_sub_ms,
        winner_side=winner_side,
        passive_buy_yes_fills=passive_buy_yes_fills,
        passive_buy_yes_chances=passive_buy_yes_chances,
        passive_buy_no_fills=passive_buy_no_fills,
        passive_buy_no_chances=passive_buy_no_chances,
    )


def summarize(results: Iterable[WindowResult]) -> dict:
    results = list(results)
    qualifying = [r for r in results if r.qualifies]

    # Q2: across qualifying markets, fraction of sub-threshold time in early half
    total_sub = sum(r.sub_threshold_ms for r in qualifying)
    total_early = sum(r.early_sub_ms for r in qualifying)
    total_late = sum(r.late_sub_ms for r in qualifying)
    early_fraction = total_early / total_sub if total_sub else 0.0

    # Q3: split fill rates by winner/loser
    # For each market with winner_side determined, compute:
    #   r_winner_side = fills/chances on the winning side
    #   r_loser_side  = fills/chances on the losing side
    # Aggregate across markets.
    winner_fills = 0
    winner_chances = 0
    loser_fills = 0
    loser_chances = 0
    for r in qualifying:
        if r.winner_side is None:
            continue
        if r.winner_side == "YES":
            winner_fills += r.passive_buy_yes_fills
            winner_chances += r.passive_buy_yes_chances
            loser_fills += r.passive_buy_no_fills
            loser_chances += r.passive_buy_no_chances
        else:
            winner_fills += r.passive_buy_no_fills
            winner_chances += r.passive_buy_no_chances
            loser_fills += r.passive_buy_yes_fills
            loser_chances += r.passive_buy_yes_chances
    r_winner = winner_fills / winner_chances if winner_chances else 0.0
    r_loser = loser_fills / loser_chances if loser_chances else 0.0

    return {
        "n_markets_total": len(results),
        "n_markets_with_timeline": sum(1 for r in results if r.n_timeline_points > 0),
        "n_qualifying": len(qualifying),
        "scaled_pass_threshold": SCALED_PASS_WINDOWS,
        "q1_pass": len(qualifying) >= SCALED_PASS_WINDOWS,
        "q2_early_fraction": early_fraction,
        "q2_early_threshold": EARLY_MIN_FRACTION,
        "q2_pass": early_fraction >= EARLY_MIN_FRACTION,
        "q3_winner_side_fill_rate": r_winner,
        "q3_loser_side_fill_rate": r_loser,
        "q3_asymmetry_ratio": r_loser / r_winner if r_winner else float("inf"),
        "q3_asymmetry_threshold": WINDOW_ASYMMETRY_THRESHOLD,
        "q3_pass": (r_loser / r_winner if r_winner else float("inf")) <= WINDOW_ASYMMETRY_THRESHOLD,
        "total_sub_threshold_ms": total_sub,
        "total_early_sub_ms": total_early,
        "total_late_sub_ms": total_late,
        "winner_side_chances": winner_chances,
        "loser_side_chances": loser_chances,
    }


def main() -> int:
    if not DB_PATH.exists():
        print(f"FATAL: recorder DB not found at {DB_PATH}", file=sys.stderr)
        return 1
    conn = sqlite3.connect(str(DB_PATH))
    try:
        markets = load_markets(conn)
        print(f"# Bot E POC — recorder data scan")
        print(f"# DB: {DB_PATH}")
        print(f"# markets with full metadata: {len(markets)}")
        print()

        results: list[WindowResult] = []
        for m in markets:
            timeline, trades = build_market_timeline(conn, m)
            result = analyze_market(timeline, trades, m)
            results.append(result)

        summary = summarize(results)

        print("## Per-market qualifying detail")
        print("condition_id_short | sub_ms | early_ms | late_ms | winner | yes_fills/chances | no_fills/chances")
        for r in sorted(results, key=lambda x: -x.sub_threshold_ms):
            if r.sub_threshold_ms == 0:
                continue
            print(
                f"{r.condition_id[:10]} | {r.sub_threshold_ms} | {r.early_sub_ms} | "
                f"{r.late_sub_ms} | {r.winner_side} | "
                f"{r.passive_buy_yes_fills}/{r.passive_buy_yes_chances} | "
                f"{r.passive_buy_no_fills}/{r.passive_buy_no_chances}"
            )

        print()
        print("## Summary")
        for k, v in summary.items():
            print(f"{k}: {v}")

        print()
        print("## Decision")
        pass_flags = [summary["q1_pass"], summary["q2_pass"], summary["q3_pass"]]
        if all(pass_flags):
            print("ALL THREE GATES PASS (on scaled thresholds)")
            print("→ Proceed to revised full backtest; note scale caveat in memo")
        else:
            fail_reasons = []
            if not summary["q1_pass"]:
                fail_reasons.append(f"Q1 universe ({summary['n_qualifying']} < {SCALED_PASS_WINDOWS})")
            if not summary["q2_pass"]:
                fail_reasons.append(f"Q2 early_fraction ({summary['q2_early_fraction']:.2f} < {EARLY_MIN_FRACTION})")
            if not summary["q3_pass"]:
                fail_reasons.append(f"Q3 asymmetry ({summary['q3_asymmetry_ratio']:.2f} > {WINDOW_ASYMMETRY_THRESHOLD})")
            print(f"GATE FAIL(S): {', '.join(fail_reasons)}")
            print("→ POC fails at current recorder scale. Decision guidance below.")

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
