"""Task 3 — Book-reload signal prototype for Bot G (v2: causal).

Hypothesis: if the cheap side's book-depth is DECLINING without refilling
in the approach to entry time, MMs are exiting — a leading indicator of
a flip. If depth keeps refilling, MMs are confident the tail is dead.

### v2 revision (2026-04-24 — GLM-5.1 audit Q3 fix)

The v1 prototype (preserved in git history) computed
`depletion_ratio = final_ask_depth / avg_ask_depth` where
`final_ask_depth` was at t=0 (resolution). That's a lookahead leak:
Bot G's entry decision fires at T_entry = entry_seconds_before_res
BEFORE resolution. Using depth data that doesn't exist at decision
time produces a spuriously-predictive signal.

v2 fix: strictly causal two-window ratio at T_entry (default t-60s):

    recent_depth    = median(book_depth in [T_entry - 10s, T_entry])
    trailing_depth  = median(book_depth in [T_entry - 60s, T_entry - 10s])
    depletion_ratio = recent_depth / trailing_depth

Both windows end at or before T_entry. No data after T_entry informs
the signal. Outcome (cheap-side win/lose) labels the sample, never a
feature.

Deployment caveat: first run on the bot host over 6.3M events timed out at
>6 min. Follow-up session should add a composite index on
`pm_events(event_type, received_at_ms, asset_id)` before running.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime

DB = "data/bot_e_recorder.db"
DEFAULT_OUTPUT = "/tmp/bot_g_book_reload_analysis.json"


# --- Market parsing (copied pattern from backtest_strategies.py) ------------

RE_UP_DOWN = re.compile(
    r"^(BTC|Bitcoin|ETH|Ethereum|SOL|Solana|XRP|Ripple).*Up or Down.*(\d{1,2}:\d{2}(?:AM|PM)?)-(\d{1,2}:\d{2}(?:AM|PM)?)",
    re.IGNORECASE,
)


def extract_symbol_from_question(q: str) -> str | None:
    qu = (q or "").upper()
    for sym, keys in [
        ("BTC", ["BTC", "BITCOIN"]),
        ("ETH", ["ETH", "ETHEREUM"]),
        ("SOL", ["SOL", "SOLANA"]),
        ("XRP", ["XRP", "RIPPLE"]),
    ]:
        if any(k in qu for k in keys):
            return sym
    return None


# --- Outcome oracle via CEX price closest to market end --------------------

def cex_symbol_for(sym: str) -> str | None:
    mapping = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}
    return mapping.get(sym)


def outcome_from_cex(
    con: sqlite3.Connection, sym: str, start_ms: int, end_ms: int
) -> bool | None:
    """Return True if YES won (price went up from start to end), else False."""
    csym = cex_symbol_for(sym)
    if csym is None:
        return None
    row_start = con.execute(
        "SELECT price FROM cex_trades WHERE symbol = ? AND trade_time_ms >= ? "
        "ORDER BY trade_time_ms ASC LIMIT 1",
        (csym, start_ms),
    ).fetchone()
    row_end = con.execute(
        "SELECT price FROM cex_trades WHERE symbol = ? AND trade_time_ms <= ? "
        "ORDER BY trade_time_ms DESC LIMIT 1",
        (csym, end_ms),
    ).fetchone()
    if row_start is None or row_end is None:
        return None
    return float(row_end[0]) > float(row_start[0])


# --- Book-reload signal ----------------------------------------------------

def book_depth_at_cheap(payload: dict, cheap_side: str) -> tuple[float, float]:
    """Given a book-event payload and the cheap side label ('YES' or 'NO'),
    return (best_ask_price, best_ask_depth). Returns (1.0, 0.0) if missing.

    Polymarket book event payload shape:
        {"asks": [{"price": 0.02, "size": 200}, ...], "bids": [...], ...}
    """
    asks = payload.get("asks") or []
    if not asks:
        return (1.0, 0.0)
    # asks sorted ascending by price — cheapest first
    asks_sorted = sorted(
        [(float(a.get("price", 1.0)), float(a.get("size", 0.0))) for a in asks]
    )
    if not asks_sorted:
        return (1.0, 0.0)
    return asks_sorted[0]


ENTRY_SECONDS_BEFORE_RES_DEFAULT = 60  # matches BOT_G_ENTRY_SECONDS_BEFORE_RES (jackpot)
RECENT_WINDOW_SEC = 10
TRAILING_WINDOW_SEC = 50  # covers [T_entry - 60s, T_entry - 10s]


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def analyze_market(
    con: sqlite3.Connection,
    market: dict,
    outcome_yes_won: bool,
    entry_seconds_before_res: int = ENTRY_SECONDS_BEFORE_RES_DEFAULT,
) -> list[dict]:
    """Causal book-reload sampler (v2 — no lookahead).

    Entry time T_entry = market_end − entry_seconds_before_res. Only
    book events STRICTLY BEFORE T_entry inform the signal. Outcome
    labels the sample; it is never a feature.
    """
    end_ms = market["end_ms"]
    t_entry_ms = end_ms - entry_seconds_before_res * 1000
    window_start_ms = t_entry_ms - (RECENT_WINDOW_SEC + TRAILING_WINDOW_SEC) * 1000
    yes_tok = market["yes_token_id"]
    no_tok = market["no_token_id"]
    samples: list[dict] = []

    # Query per asset so SQLite can use ix_pm_events_asset_time. The older
    # single IN query tended to choose event_type/time and scan too much V2 tape.
    rows = []
    for token_id in (yes_tok, no_tok):
        rows.extend(
            con.execute(
                """
                SELECT received_at_ms, asset_id, payload_json FROM pm_events
                WHERE asset_id = ?
                  AND received_at_ms BETWEEN ? AND ?
                  AND event_type = 'book'
                ORDER BY received_at_ms
                """,
                (token_id, window_start_ms, t_entry_ms),
            ).fetchall()
        )
    rows.sort(key=lambda row: row[0])
    if not rows:
        return samples

    by_side: dict[str, list[tuple[int, float, float]]] = {"YES": [], "NO": []}
    for ts, aid, raw in rows:
        try:
            p = json.loads(raw) if raw else {}
        except Exception:
            continue
        side = "YES" if str(aid) == yes_tok else "NO"
        ask_px, ask_sz = book_depth_at_cheap(p, side)
        by_side[side].append((int(ts), ask_px, ask_sz))

    # Cheap side decision uses ONLY data strictly before T_entry (causal).
    def min_ask(sd: str) -> float:
        return min((x[1] for x in by_side.get(sd, [])), default=1.0)

    yes_min, no_min = min_ask("YES"), min_ask("NO")
    if yes_min < no_min and yes_min <= 0.10:
        cheap = "YES"
    elif no_min < yes_min and no_min <= 0.10:
        cheap = "NO"
    else:
        return samples

    trace = by_side[cheap]
    if len(trace) < 4:  # need enough samples for both windows
        return samples

    recent_cutoff_ms = t_entry_ms - RECENT_WINDOW_SEC * 1000
    trailing_depths = [sz for ts, _, sz in trace if ts < recent_cutoff_ms]
    recent_depths = [sz for ts, _, sz in trace if ts >= recent_cutoff_ms]
    if not trailing_depths or not recent_depths:
        return samples

    trailing_med = _median(trailing_depths)
    recent_med = _median(recent_depths)
    depletion_ratio = (recent_med / trailing_med) if trailing_med > 0 else 1.0

    cheap_won = (cheap == "YES" and outcome_yes_won) or (
        cheap == "NO" and not outcome_yes_won
    )

    samples.append({
        "condition_id": market["condition_id"],
        "question": market["question"],
        "cheap_side": cheap,
        "min_ask_at_entry": min_ask(cheap),
        "trailing_depth_median": trailing_med,
        "recent_depth_median": recent_med,
        "depletion_ratio": depletion_ratio,
        "n_trailing_samples": len(trailing_depths),
        "n_recent_samples": len(recent_depths),
        "cheap_won": cheap_won,
    })
    return samples


def _bucket_for_ratio(r: float) -> str:
    if r <= 0.2:
        return "1:depleted_80%+ (<=0.2)"
    if r <= 0.5:
        return "2:depleted_50-80% (0.2-0.5)"
    if r <= 0.9:
        return "3:slight_drop (0.5-0.9)"
    if r <= 1.1:
        return "4:flat (0.9-1.1)"
    return "5:refilled (>1.1)"


def _bucket_summary(samples: list[dict]) -> dict[str, dict[str, float | int]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        buckets[_bucket_for_ratio(float(sample["depletion_ratio"]))].append(sample)
    out: dict[str, dict[str, float | int]] = {}
    for key, grp in sorted(buckets.items()):
        wins = sum(1 for s in grp if s["cheap_won"])
        out[key] = {
            "n": len(grp),
            "wins": wins,
            "win_rate_pct": round(wins / len(grp) * 100, 2) if grp else 0.0,
        }
    return out


def analyze_entry_events(main_db: str) -> list[dict]:
    """Fast path: analyze realised Bot G entries that already logged depletion.

    This is the production-friendly mode. It uses the causal depletion fields
    written at entry time, then labels them with later FIFO-matched paper
    outcomes from ``main.db``. No recorder-table scan is needed.
    """
    from scripts.bot_g_feature_analysis import fetch_entry_events, fetch_trades, fifo_match

    con = sqlite3.connect(main_db)
    try:
        trades = fetch_trades(con, bot_ids=("bot_g_prime",))
        events = fetch_entry_events(con)
        closed = fifo_match(trades, entry_events=events, con=None)
    finally:
        con.close()
    samples: list[dict] = []
    for row in closed:
        if row.get("depletion_ratio") is None:
            continue
        samples.append(
            {
                "condition_id": row.get("condition_id"),
                "order_id": row.get("order_id"),
                "question": row.get("question"),
                "cheap_side": row.get("event", {}).get("side_token"),
                "min_ask_at_entry": row.get("buy_price"),
                "depletion_ratio": float(row["depletion_ratio"]),
                "cex_confirmed": row.get("cex_confirmed"),
                "cheap_won": bool(row.get("win")),
                "pnl_usd": row.get("pnl_usd"),
            }
        )
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=DB)
    parser.add_argument(
        "--main-db",
        help="Fast mode: analyze Bot G entry_placed depletion payloads from main.db.",
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--entry-seconds-before-res",
        type=int,
        default=ENTRY_SECONDS_BEFORE_RES_DEFAULT,
        help="Decision timestamp relative to resolution; defaults to old G 60s.",
    )
    parser.add_argument(
        "--since-end-iso",
        help="Only analyze markets ending at or after this ISO timestamp/date.",
    )
    parser.add_argument("--max-markets", type=int, help="Cap parseable markets for smoke runs.")
    args = parser.parse_args()

    if args.main_db:
        all_samples = analyze_entry_events(args.main_db)
        print(f"Loaded {len(all_samples)} realised Bot G entries with causal depletion telemetry")
        if not all_samples:
            return 0
        print("\n=== WR by depletion_ratio bucket (entry payload, causal) ===")
        summary = _bucket_summary(all_samples)
        print(f"| {'bucket':<30} | n | wins | WR    |")
        print(f"|{'-'*32}|---|------|-------|")
        for key, row in summary.items():
            print(
                f"| {key:<30} | {row['n']:>1} | {row['wins']:>4} | "
                f"{row['win_rate_pct']:>5.1f}% |"
            )
        with open(args.output, "w") as f:
            json.dump(
                {
                    "mode": "main_db_entry_events",
                    "n_samples": len(all_samples),
                    "bucket_summary": summary,
                    "samples": all_samples,
                },
                f,
                default=str,
                indent=2,
            )
        print(f"\nWrote {args.output}")
        return 0

    con = sqlite3.connect(args.db)
    since_ms = None
    if args.since_end_iso:
        try:
            since_dt = datetime.fromisoformat(args.since_end_iso.replace("Z", "+00:00"))
            since_ms = int(since_dt.timestamp() * 1000)
        except Exception:
            since_ms = None
    # Pull resolved markets with parseable windows
    rows = con.execute(
        """
        SELECT DISTINCT condition_id, question, end_date_iso, yes_token_id, no_token_id
        FROM markets
        WHERE question LIKE '%Up or Down%' AND end_date_iso IS NOT NULL
        """
    ).fetchall()
    print(f"Found {len(rows)} 'Up or Down' market rows")

    markets = []
    for cond, q, end_iso, yt, nt in rows:
        sym = extract_symbol_from_question(q or "")
        if sym is None or not yt or not nt:
            continue
        try:
            end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        except Exception:
            continue
        end_ms = int(end_dt.timestamp() * 1000)
        if since_ms is not None and end_ms < since_ms:
            continue
        start_ms = end_ms - 15 * 60 * 1000  # 15-min market
        markets.append({
            "condition_id": cond, "question": q, "symbol": sym,
            "yes_token_id": yt, "no_token_id": nt,
            "start_ms": start_ms, "end_ms": end_ms,
        })
        if args.max_markets and len(markets) >= args.max_markets:
            break
    print(f"Parseable markets: {len(markets)}")

    # Resolve outcomes
    with_outcome = []
    for m in markets:
        outcome = outcome_from_cex(con, m["symbol"], m["start_ms"], m["end_ms"])
        if outcome is None:
            continue
        m["yes_won"] = outcome
        with_outcome.append(m)
    print(f"Markets with CEX-confirmed outcome: {len(with_outcome)}")

    # Analyze book-reload signal
    all_samples = []
    for m in with_outcome:
        for s in analyze_market(
            con,
            m,
            m["yes_won"],
            entry_seconds_before_res=args.entry_seconds_before_res,
        ):
            all_samples.append(s)
    print(f"Markets with cheap-side book traces before T_entry: {len(all_samples)}")

    if not all_samples:
        return 0

    # Bucket by depletion_ratio — recent(10s) median / trailing(50s) median
    # STRICTLY BEFORE T_entry (causal, no lookahead; see module docstring).
    print("\n=== WR by depletion_ratio bucket (recent_med / trailing_med, causal) ===")
    buckets: dict[str, list[dict]] = defaultdict(list)
    for s in all_samples:
        buckets[_bucket_for_ratio(float(s["depletion_ratio"]))].append(s)

    print(f"| {'bucket':<30} | n | wins | WR    |")
    print(f"|{'-'*32}|---|------|-------|")
    for k in sorted(buckets.keys()):
        grp = buckets[k]
        wins = sum(1 for s in grp if s["cheap_won"])
        wr = (wins / len(grp) * 100) if grp else 0
        print(f"| {k:<30} | {len(grp):>1} | {wins:>4} | {wr:>5.1f}% |")

    # Sample output
    print("\n=== top 10 depletion-80+% cheap-side samples ===")
    depleted = sorted(
        [s for s in all_samples if s["depletion_ratio"] <= 0.5],
        key=lambda s: s["depletion_ratio"],
    )[:10]
    for s in depleted:
        print(
            f"  {s['condition_id'][:12]} cheap={s['cheap_side']} "
            f"min_ask={s['min_ask_at_entry']:.3f} "
            f"trailing={s['trailing_depth_median']:.0f} "
            f"recent={s['recent_depth_median']:.0f} "
            f"ratio={s['depletion_ratio']:.2f} "
            f"{'WIN' if s['cheap_won'] else 'lose'}"
        )

    # Persist
    with open(args.output, "w") as f:
        json.dump({
            "n_samples": len(all_samples),
            "entry_seconds_before_res": args.entry_seconds_before_res,
            "bucket_summary": _bucket_summary(all_samples),
            "samples": all_samples,
        }, f, default=str, indent=2)
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
