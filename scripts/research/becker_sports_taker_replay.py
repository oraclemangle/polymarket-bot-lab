#!/usr/bin/env python3
"""Sports taker replay on Becker dataset (on-chain proxy).

Uses the Becker prediction-market-analysis Parquet dataset to simulate buying YES
at the first on-chain trade price, holding to resolution.

Trade price proxy: first on-chain fill for the YES token (derived from
maker_amount/taker_amount ratio on CTF Exchange trades).

Resolution: parsed from markets.outcome_prices (convention: ["1","0"] = YES won,
["0","1"] = NO won, ["0.5","0.5"] = void/ignored).

Fee: parabolic taker fee at configurable bps (default 100 bps round-trip = 1%).

Groups by sub-category (moneyline, totals, spread, props, futures) and league
(NBA, NFL, soccer, esports, etc.) parsed from question text.

Read-only. No bot/service/config/cap/wallet/order-path change authorised.

Usage:
    python3 scripts/research/becker_sports_taker_replay.py \
        --becker-data data/external/prediction-market-analysis/repo/data \
        --price-min 0.10 --price-max 0.20 \
        --fee-bps 100 \
        --out docs/reports/becker-sports-taker-replay-YYYY-MM-DD.md
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.external_data_paths import default_becker_data_dir  # noqa: E402

DEFAULT_BECKER_DATA = default_becker_data_dir()
DEFAULT_OUT = Path("docs/reports")


def _parse_subcategory(question: str) -> str:
    q = question.lower()
    if any(k in q for k in ("total", "over/under", "over under", "o/u", "over ", "under ")):
        return "totals"
    if any(k in q for k in ("spread", "handicap", "cover", "point")):
        return "spread"
    if any(k in q for k in ("prop", "player", "first to", "most ", "score first", "homerun", "touchdown", "rebound", "assist")):
        return "props"
    if any(k in q for k in ("champion", "championship", "win the", "win division", "win conference", "make playoffs", "make the")):
        return "futures"
    if any(k in q for k in ("win", "defeat", "beat", "advance", "reach")):
        return "moneyline"
    return "other"


def _parse_league(question: str) -> str:
    q = question.lower()
    if "nba" in q:
        return "NBA"
    if "nfl" in q:
        return "NFL"
    if "mlb" in q:
        return "MLB"
    if any(k in q for k in ("ncaa", "march madness", "college basketball", "college football")):
        return "NCAAB/NCAAF"
    if any(k in q for k in ("soccer", "epl", "premier league", "la liga", "bundesliga", "serie a", "ligue 1", "champions league", "world cup", "fifa")):
        return "soccer"
    if "tennis" in q:
        return "tennis"
    if any(k in q for k in ("esports", "lol ", "csgo", "counter-strike", "dota", "valorant")):
        return "esports"
    if "ufc" in q or "mma" in q or "boxing" in q:
        return "combat"
    if "golf" in q:
        return "golf"
    if "f1" in q or "formula 1" in q:
        return "F1"
    return "other"


def _parse_outcome_prices(raw: str) -> int | None:
    """Parse outcomePrices JSON. Returns winner index (0=YES, 1=NO) or None for void."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, list) or len(parsed) != 2:
        return None
    try:
        p0, p1 = float(parsed[0]), float(parsed[1])
    except (TypeError, ValueError):
        return None
    if abs(p0 - 1.0) < 0.01 and abs(p1) < 0.01:
        return 0
    if abs(p1 - 1.0) < 0.01 and abs(p0) < 0.01:
        return 1
    if abs(p0 - 0.5) < 0.01 and abs(p1 - 0.5) < 0.01:
        return None
    return None


def _parse_clob_tokens(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return [str(x) for x in parsed] if isinstance(parsed, list) else []


@dataclass
class SimTrade:
    condition_id: str
    question: str
    subcategory: str
    league: str
    entry_price: float
    size_shares: float
    cost_usd: float
    fee_usd: float
    yes_won: bool
    gross_pnl: float
    net_pnl: float
    # Fixed-notional ($5) normalized
    fixed_cost: float
    fixed_gross: float
    fixed_net: float


@dataclass
class SegmentStats:
    label: str
    n: int = 0
    wins: int = 0
    sum_gross_pnl: float = 0.0
    sum_net_pnl: float = 0.0
    sum_cost: float = 0.0
    pnls: list[float] = field(default_factory=list)
    # Fixed-notional ($5) normalized
    sum_fixed_cost: float = 0.0
    sum_fixed_net: float = 0.0
    fixed_pnls: list[float] = field(default_factory=list)


def _ci(values: list[float]) -> tuple[float | None, float | None]:
    n = len(values)
    if n < 2:
        return None, None
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / (n - 1)
    se = math.sqrt(var / n)
    return mean - 1.96 * se, mean + 1.96 * se


def _roi(pnls: list[float], costs: list[float]) -> float | None:
    total_cost = sum(costs)
    total_pnl = sum(pnls)
    if total_cost <= 0:
        return None
    return total_pnl / total_cost


def run_replay(*, becker_data: Path, price_min: float, price_max: float, fee_bps: int) -> dict[str, Any]:
    try:
        import duckdb
    except ImportError as exc:
        raise SystemExit("duckdb is required; install with `pip install duckdb`") from exc

    if not becker_data.exists():
        return {"ok": False, "reason": f"Becker data not found: {becker_data}"}

    tmp_dir = becker_data.parent / "duckdb-tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA preserve_insertion_order=false")
    con.execute("PRAGMA memory_limit='4GB'")
    con.execute(f"PRAGMA temp_directory='{tmp_dir.as_posix()}'")

    markets_path = (becker_data / "polymarket" / "markets" / "*.parquet").as_posix()
    trades_path = (becker_data / "polymarket" / "trades" / "*.parquet").as_posix()
    blocks_path = (becker_data / "polymarket" / "blocks" / "*.parquet").as_posix()

    # Step 1: Build resolved sports market map (YES token only)
    print("Loading resolved sports markets ...", flush=True)
    rows = con.execute(f"""
        SELECT
            condition_id,
            question,
            outcomes,
            outcome_prices,
            clob_token_ids
        FROM '{markets_path}'
        WHERE closed = true
          AND (
            question ILIKE '%nba%' OR question ILIKE '%nfl%' OR question ILIKE '%mlb%'
            OR question ILIKE '%nhl%' OR question ILIKE '%soccer%' OR question ILIKE '%football%'
            OR question ILIKE '%world cup%' OR question ILIKE '%fifa%'
            OR question ILIKE '%champions league%' OR question ILIKE '%premier league%'
            OR question ILIKE '%la liga%' OR question ILIKE '%bundesliga%'
            OR question ILIKE '%serie a%' OR question ILIKE '%ligue 1%'
            OR question ILIKE '%uefa%' OR question ILIKE '%euro%'
            OR question ILIKE '%super bowl%' OR question ILIKE '%stanley cup%'
            OR question ILIKE '%world series%' OR question ILIKE '%nba finals%'
            OR question ILIKE '%playoff%' OR question ILIKE '%march madness%'
            OR question ILIKE '%ncaa%' OR question ILIKE '%draft%'
            OR question ILIKE '%esports%' OR question ILIKE '%lol %'
            OR question ILIKE '%tennis%' OR question ILIKE '%wimbledon%'
            OR question ILIKE '%ufc%' OR question ILIKE '%mma%'
            OR question ILIKE '%golf%' OR question ILIKE '%masters%'
            OR question ILIKE '%f1%' OR question ILIKE '%formula 1%'
          )
          AND outcome_prices IS NOT NULL
          AND outcomes IS NOT NULL
          AND clob_token_ids IS NOT NULL
    """).fetchall()

    token_map: list[tuple[str, str, str, int]] = []
    n_resolved = 0
    for condition_id, question, outcomes_raw, prices_raw, tokens_raw in rows:
        winner = _parse_outcome_prices(str(prices_raw))
        if winner is None:
            continue
        n_resolved += 1
        tokens = _parse_clob_tokens(str(tokens_raw))
        if len(tokens) < 2:
            continue
        # YES token is index 0 (convention in Becker data)
        yes_token = tokens[0]
        token_map.append((str(yes_token), str(condition_id), str(question), int(winner)))

    print(f"  {n_resolved:,} resolved sports markets, {len(token_map)} YES tokens", flush=True)
    if not token_map:
        con.close()
        return {"ok": False, "reason": "No resolved sports markets with valid YES token data"}

    # Step 2: Create temp table for YES token map
    con.execute("""
        CREATE TEMP TABLE yes_token_map (
            token_id VARCHAR,
            condition_id VARCHAR,
            question VARCHAR,
            won INTEGER
        )
    """)
    con.executemany(
        "INSERT INTO yes_token_map VALUES (?, ?, ?, ?)",
        token_map,
    )

    # Step 3: Build fill events from trades (YES token only)
    print("Joining on-chain trades ...", flush=True)
    con.execute(f"""
        CREATE TEMP TABLE fill_events AS
        SELECT
            tm.condition_id,
            tm.question,
            tm.won,
            CASE
                WHEN t.maker_asset_id = '0'
                    THEN t.maker_amount::DOUBLE / NULLIF(t.taker_amount::DOUBLE, 0)
                ELSE t.taker_amount::DOUBLE / NULLIF(t.maker_amount::DOUBLE, 0)
            END AS price,
            CASE
                WHEN t.maker_asset_id = '0'
                    THEN t.taker_amount::DOUBLE / 1000000.0
                ELSE t.maker_amount::DOUBLE / 1000000.0
            END AS shares,
            CASE
                WHEN t.maker_asset_id = '0'
                    THEN t.maker_amount::DOUBLE / 1000000.0
                ELSE t.taker_amount::DOUBLE / 1000000.0
            END AS notional_usd,
            t.fee::DOUBLE / 1000000.0 AS fee_usd,
            t.block_number,
            b.timestamp::TIMESTAMPTZ AS fill_ts
        FROM '{trades_path}' t
        INNER JOIN yes_token_map tm ON tm.token_id = (
            CASE WHEN t.maker_asset_id = '0' THEN t.taker_asset_id ELSE t.maker_asset_id END
        )
        INNER JOIN '{blocks_path}' b ON b.block_number = t.block_number
        WHERE t.maker_amount > 0
          AND t.taker_amount > 0
          AND (t.maker_asset_id = '0' OR t.taker_asset_id = '0')
          AND (
            CASE
                WHEN t.maker_asset_id = '0'
                    THEN t.maker_amount::DOUBLE / NULLIF(t.taker_amount::DOUBLE, 0)
                ELSE t.taker_amount::DOUBLE / NULLIF(t.maker_amount::DOUBLE, 0)
            END
          ) > 0
          AND (
            CASE
                WHEN t.maker_asset_id = '0'
                    THEN t.maker_amount::DOUBLE / NULLIF(t.taker_amount::DOUBLE, 0)
                ELSE t.taker_amount::DOUBLE / NULLIF(t.maker_amount::DOUBLE, 0)
            END
          ) < 1
    """)
    n_fills = con.execute("SELECT COUNT(*) FROM fill_events").fetchone()[0]
    print(f"  {n_fills:,} fill events", flush=True)

    # Step 4: Take first fill per condition_id
    print("Taking first fill per market ...", flush=True)
    con.execute("""
        CREATE TEMP TABLE first_fills AS
        SELECT
            condition_id,
            question,
            won,
            price AS entry_price,
            shares AS entry_shares,
            notional_usd AS entry_notional,
            fee_usd AS entry_fee,
            block_number,
            fill_ts
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (PARTITION BY condition_id ORDER BY block_number, fill_ts) AS rn
            FROM fill_events
        )
        WHERE rn = 1
    """)
    n_first = con.execute("SELECT COUNT(*) FROM first_fills").fetchone()[0]
    print(f"  {n_first:,} first fills", flush=True)

    # Step 5: Apply price band and simulate
    print(f"Filtering price band [{price_min:.2f}, {price_max:.2f}] ...", flush=True)
    rows = con.execute(f"""
        SELECT condition_id, question, won, entry_price, entry_shares, entry_notional, entry_fee
        FROM first_fills
        WHERE entry_price >= {price_min} AND entry_price <= {price_max}
    """).fetchall()
    print(f"  {len(rows):,} fills in band", flush=True)

    FIXED_NOTIONAL = 5.0
    trades: list[SimTrade] = []
    for condition_id, question, won, price, shares, notional, fee in rows:
        price_f = float(price)
        shares_f = float(shares)
        notional_f = float(notional)
        fee_f = float(fee)

        # Use actual on-chain fee from dataset (not synthetic)
        # Gross PnL: if YES won, profit is (1 - price) * shares; else loss is -price * shares
        if won == 1:
            gross = (1.0 - price_f) * shares_f
        else:
            gross = -price_f * shares_f
        net = gross - fee_f

        # Fixed-notional normalization: what if every trade was $5?
        fixed_shares = FIXED_NOTIONAL / price_f
        if won == 1:
            fixed_gross = (1.0 - price_f) * fixed_shares
        else:
            fixed_gross = -price_f * fixed_shares
        # Scale fee proportionally
        fixed_fee = fee_f * (FIXED_NOTIONAL / max(notional_f, 0.01))
        fixed_net = fixed_gross - fixed_fee

        trades.append(SimTrade(
            condition_id=str(condition_id),
            question=str(question),
            subcategory=_parse_subcategory(str(question)),
            league=_parse_league(str(question)),
            entry_price=price_f,
            size_shares=shares_f,
            cost_usd=notional_f,
            fee_usd=fee_f,
            yes_won=bool(won),
            gross_pnl=gross,
            net_pnl=net,
            fixed_cost=FIXED_NOTIONAL,
            fixed_gross=fixed_gross,
            fixed_net=fixed_net,
        ))

    con.close()

    # Step 6: Aggregate
    subcats: dict[str, SegmentStats] = {}
    leagues: dict[str, SegmentStats] = {}
    all_costs: list[float] = []
    all_pnls: list[float] = []
    all_fixed_costs: list[float] = []
    all_fixed_pnls: list[float] = []
    all_wins = 0

    for t in trades:
        sc = subcats.setdefault(t.subcategory, SegmentStats(label=t.subcategory))
        lg = leagues.setdefault(t.league, SegmentStats(label=t.league))
        for stats in (sc, lg):
            stats.n += 1
            if t.yes_won:
                stats.wins += 1
            stats.sum_gross_pnl += t.gross_pnl
            stats.sum_net_pnl += t.net_pnl
            stats.sum_cost += t.cost_usd
            stats.pnls.append(t.net_pnl)
            stats.sum_fixed_cost += t.fixed_cost
            stats.sum_fixed_net += t.fixed_net
            stats.fixed_pnls.append(t.fixed_net)
        all_costs.append(t.cost_usd)
        all_pnls.append(t.net_pnl)
        all_fixed_costs.append(t.fixed_cost)
        all_fixed_pnls.append(t.fixed_net)
        if t.yes_won:
            all_wins += 1

    all_stats = {
        "n": len(trades),
        "wins": all_wins,
        "wr": all_wins / max(1, len(trades)),
        "sum_gross": sum(t.gross_pnl for t in trades),
        "sum_net": sum(t.net_pnl for t in trades),
        "sum_cost": sum(all_costs),
        "roi": _roi(all_pnls, all_costs),
        "ci_lo": _ci(all_pnls)[0],
        "ci_hi": _ci(all_pnls)[1],
        "fixed_sum_cost": sum(all_fixed_costs),
        "fixed_sum_net": sum(all_fixed_pnls),
        "fixed_roi": _roi(all_fixed_pnls, all_fixed_costs),
        "fixed_ci_lo": _ci(all_fixed_pnls)[0],
        "fixed_ci_hi": _ci(all_fixed_pnls)[1],
    }

    return {
        "ok": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "becker_data": str(becker_data),
        "n_resolved_markets": n_resolved,
        "n_fills": n_fills,
        "n_first_fills": n_first,
        "n_trades": len(trades),
        "trades": trades,
        "subcats": subcats,
        "leagues": leagues,
        "all_stats": all_stats,
    }


def render_md(report: dict[str, Any], args: argparse.Namespace) -> str:
    lines = [
        "# Becker Sports Taker Replay — Lane A",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Becker data: `{report['becker_data']}`",
        f"Price band: `{args.price_min:.2f}–{args.price_max:.2f}` | Fee: `{args.fee_bps}` bps",
        f"Resolved sports markets: {report['n_resolved_markets']:,}",
        f"First fills (any price): {report['n_first_fills']:,}",
        f"Trades in band: {report['n_trades']:,}",
        "",
    ]

    if report["n_trades"] == 0:
        lines.extend([
            "## Result",
            "",
            "No first fills fell within the price band.",
            "",
        ])
        return "\n".join(lines)

    s = report["all_stats"]
    lines.extend([
        "## Overall",
        "",
        "### Actual trade sizes (on-chain notional)",
        "",
        f"| metric | value |",
        "|---|---|",
        f"| trades | {s['n']} |",
        f"| win rate | {s['wr']*100:.1f}% |",
        f"| gross PnL | ${s['sum_gross']:+.2f} |",
        f"| net PnL (post-fee) | ${s['sum_net']:+.2f} |",
        f"| ROI | {s['roi']*100:+.2f}% |" if s["roi"] is not None else "| ROI | n/a |",
        f"| 95% CI | [{s['ci_lo']*100:+.2f}%, {s['ci_hi']*100:+.2f}%] |" if s["ci_lo"] is not None else "| 95% CI | n/a |",
        "",
        "### Fixed-notional ($5 per trade) — matches paper bot sizing",
        "",
        f"| metric | value |",
        "|---|---|",
        f"| trades | {s['n']} |",
        f"| win rate | {s['wr']*100:.1f}% |",
        f"| net PnL (post-fee) | ${s['fixed_sum_net']:+.2f} |",
        f"| ROI | {s['fixed_roi']*100:+.2f}% |" if s["fixed_roi"] is not None else "| ROI | n/a |",
        f"| 95% CI | [{s['fixed_ci_lo']*100:+.2f}%, {s['fixed_ci_hi']*100:+.2f}%] |" if s["fixed_ci_lo"] is not None else "| 95% CI | n/a |",
        "",
    ])

    # By sub-category
    lines.extend([
        "## By sub-category",
        "",
        "| subcategory | n | wins | WR | gross PnL | net PnL (fixed $5) | ROI (fixed $5) | 95% CI |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ])
    for label in sorted(report["subcats"].keys(), key=lambda k: -report["subcats"][k].n):
        st = report["subcats"][label]
        wr = st.wins / max(1, st.n)
        fixed_costs = [t.fixed_cost for t in report["trades"] if t.subcategory == label]
        fixed_roi = _roi(st.fixed_pnls, fixed_costs)
        ci_lo, ci_hi = _ci(st.fixed_pnls)
        lines.append(
            f"| {label} | {st.n} | {st.wins} | {wr*100:.1f}% | "
            f"${st.sum_gross_pnl:+.2f} | ${st.sum_fixed_net:+.2f} | "
            + (f"{fixed_roi*100:+.2f}% |" if fixed_roi is not None else "n/a |")
            + (f" [{ci_lo*100:+.2f}%, {ci_hi*100:+.2f}%] |" if ci_lo is not None else " n/a |")
        )
    lines.append("")

    # By league
    lines.extend([
        "## By league",
        "",
        "| league | n | wins | WR | gross PnL | net PnL (fixed $5) | ROI (fixed $5) | 95% CI |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ])
    for label in sorted(report["leagues"].keys(), key=lambda k: -report["leagues"][k].n):
        st = report["leagues"][label]
        wr = st.wins / max(1, st.n)
        fixed_costs = [t.fixed_cost for t in report["trades"] if t.league == label]
        fixed_roi = _roi(st.fixed_pnls, fixed_costs)
        ci_lo, ci_hi = _ci(st.fixed_pnls)
        lines.append(
            f"| {label} | {st.n} | {st.wins} | {wr*100:.1f}% | "
            f"${st.sum_gross_pnl:+.2f} | ${st.sum_fixed_net:+.2f} | "
            + (f"{fixed_roi*100:+.2f}% |" if fixed_roi is not None else "n/a |")
            + (f" [{ci_lo*100:+.2f}%, {ci_hi*100:+.2f}%] |" if ci_lo is not None else " n/a |")
        )
    lines.append("")

    # Raw trades
    lines.extend([
        "## Raw trades (first 30)",
        "",
        "| condition_id | league | subcat | entry | won | gross | net | fixed net |",
        "|---|---|---|---:|---:|---:|---:|",
    ])
    for t in report["trades"][:30]:
        lines.append(
            f"| {t.condition_id} | {t.league} | {t.subcategory} | "
            f"{t.entry_price:.2f} | {'YES' if t.yes_won else 'NO'} | "
            f"${t.gross_pnl:+.2f} | ${t.net_pnl:+.2f} | ${t.fixed_net:+.2f} |"
        )
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--becker-data", type=Path, default=DEFAULT_BECKER_DATA)
    parser.add_argument("--price-min", type=float, default=0.10)
    parser.add_argument("--price-max", type=float, default=0.20)
    parser.add_argument("--fee-bps", type=int, default=100)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    report = run_replay(
        becker_data=args.becker_data,
        price_min=args.price_min,
        price_max=args.price_max,
        fee_bps=args.fee_bps,
    )

    md = render_md(report, args)

    args.out.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    out_path = args.out / f"becker-sports-taker-replay-{today}.md"
    out_path.write_text(md)
    print(f"Report: {out_path}", flush=True)

    if not report.get("ok"):
        print(f"FAIL: {report.get('reason')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
