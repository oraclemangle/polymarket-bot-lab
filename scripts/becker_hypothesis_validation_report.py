#!/usr/bin/env python3
"""Becker hypothesis validation — tests Track 1 hypotheses on 49M historical fills.

Tier A: counterparty archetype (#1), multi-wallet cascade (#3), time-of-day (#4).
Tier B: cross-asset BTC lead-lag (#5), final-15s window (#6), price-level (#11).
Tier C: volatility regime (#12) — tests both directions.
Tier D: CEX reversal (#14), drift (#15) — research validators only.

All time windows used for entry-gate hypotheses are strictly causal. Tier D
items deliberately use post-fill windows and are flagged in the report as
research-only — they cannot become entry rules without re-introducing the
look-ahead bias that flipped the original Becker conclusion.

Read-only. No bot config, service, paper parameter, live parameter, cap,
wallet, order path, or running service is touched. Output is Markdown +
JSON in `docs/reports/`.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.crypto_fair_value_becker_fill_report import load_token_rows  # noqa: E402
from scripts.external_data_paths import (  # noqa: E402
    default_becker_data_dir,
    default_binance_klines_1m_dir,
)

UTC = timezone.utc

DEFAULT_BECKER_DATA = default_becker_data_dir()
DEFAULT_KLINES = default_binance_klines_1m_dir()
DEFAULT_OUT_MD = Path("docs/reports/becker-hypothesis-validation-2026-05-06.md")
DEFAULT_OUT_JSON = Path("docs/reports/becker-hypothesis-validation-2026-05-06.json")

WALK_FORWARD_CUTOFF = "2025-12-01"
COSTS = (0.0, 0.01, 0.02)
SYMBOL_TO_BINANCE = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--becker-data", default=str(DEFAULT_BECKER_DATA))
    p.add_argument("--klines-dir", default=str(DEFAULT_KLINES))
    p.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    p.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    p.add_argument("--max-lead-sec", type=int, default=600)
    p.add_argument("--min-lead-sec", type=int, default=5)
    p.add_argument("--memory-limit", default="6GB")
    p.add_argument("--min-end-date", default=None, help="UTC date lower bound, YYYY-MM-DD")
    p.add_argument("--max-end-date", default=None, help="UTC date upper bound, YYYY-MM-DD")
    return p.parse_args()


def _fetch_dicts(con: Any) -> list[dict[str, Any]]:
    cols = [d[0] for d in con.description]
    return [
        {cols[idx]: row[idx] for idx in range(len(cols))}
        for row in con.fetchall()
    ]


def _wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _cost_select(prefix: str = "") -> str:
    parts = []
    for cost in COSTS:
        key = int(cost * 1000)
        parts.append(
            "AVG(((CASE WHEN won THEN 1.0 ELSE 0.0 END) "
            f"- price - {cost}) / NULLIF(price + {cost}, 0)) "
            f"AS {prefix}avg_net_roi_{key:03d}mp"
        )
    return ",\n            ".join(parts)


def _build_fill_events(con: Any, data_dir: Path, args: argparse.Namespace) -> int:
    trades_path = (data_dir / "polymarket" / "trades" / "*.parquet").as_posix()
    blocks_path = (data_dir / "polymarket" / "blocks" / "*.parquet").as_posix()
    min_fill_ts, max_fill_ts = con.execute(
        "SELECT MIN(end_ts) - INTERVAL '600 seconds', MAX(end_ts) FROM token_map"
    ).fetchone()
    block_min, block_max = con.execute(
        f"""
        SELECT MIN(block_number), MAX(block_number)
        FROM '{blocks_path}'
        WHERE timestamp::TIMESTAMPTZ BETWEEN ? AND ?
        """,
        (min_fill_ts, max_fill_ts),
    ).fetchone()
    if block_min is None or block_max is None:
        raise SystemExit("No block timestamps overlap selected crypto markets")
    con.execute(
        f"""
        CREATE TEMP TABLE fill_events AS
        SELECT
            tm.symbol,
            tm.duration_minutes,
            tm.side,
            tm.won,
            tm.condition_id,
            t.maker AS maker_addr,
            t.taker AS taker_addr,
            CASE
                WHEN t.maker_asset_id = '0'
                    THEN t.maker_amount::DOUBLE / NULLIF(t.taker_amount::DOUBLE, 0)
                ELSE t.taker_amount::DOUBLE / NULLIF(t.maker_amount::DOUBLE, 0)
            END AS price,
            b.timestamp::TIMESTAMPTZ AS fill_ts,
            date_diff('second', b.timestamp::TIMESTAMPTZ, tm.end_ts) AS lead_sec,
            tm.end_ts
        FROM '{trades_path}' t
        INNER JOIN token_map tm ON tm.token_id = (
            CASE WHEN t.maker_asset_id = '0' THEN t.taker_asset_id ELSE t.maker_asset_id END
        )
        INNER JOIN '{blocks_path}' b ON b.block_number = t.block_number
        WHERE t.block_number BETWEEN {int(block_min)} AND {int(block_max)}
          AND tm.duration_minutes = 15
          AND t.maker_amount > 0
          AND t.taker_amount > 0
          AND (t.maker_asset_id = '0' OR t.taker_asset_id = '0')
          AND date_diff('second', b.timestamp::TIMESTAMPTZ, tm.end_ts) BETWEEN {int(args.min_lead_sec)} AND {int(args.max_lead_sec)}
        """
    )
    return con.execute("SELECT COUNT(*) FROM fill_events").fetchone()[0]


def _build_klines(con: Any, klines_dir: Path) -> None:
    parts = []
    for symbol, binance_symbol in SYMBOL_TO_BINANCE.items():
        path = (klines_dir / binance_symbol / "*.parquet").as_posix()
        parts.append(
            f"SELECT '{symbol}' AS symbol, open_time::TIMESTAMPTZ AS bar_ts, close "
            f"FROM '{path}'"
        )
    union_sql = "\n            UNION ALL\n            ".join(parts)
    con.execute(
        f"""
        CREATE TEMP TABLE klines AS
        SELECT
            symbol,
            bar_ts,
            close,
            LAG(close, 1) OVER (PARTITION BY symbol ORDER BY bar_ts) AS prev_close,
            LAG(close, 2) OVER (PARTITION BY symbol ORDER BY bar_ts) AS close_2m_ago,
            LEAD(close, 1) OVER (PARTITION BY symbol ORDER BY bar_ts) AS next_close,
            STDDEV(close) OVER (
                PARTITION BY symbol ORDER BY bar_ts
                ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING
            ) AS realized_vol_60m_prior,
            AVG(close) OVER (
                PARTITION BY symbol ORDER BY bar_ts
                ROWS BETWEEN 60 PRECEDING AND 1 PRECEDING
            ) AS avg_close_60m_prior
        FROM ({union_sql})
        """
    )
    con.execute("CREATE INDEX klines_idx ON klines(symbol, bar_ts)")


def _annotate_strictly_causal(con: Any) -> None:
    """Strictly causal join: prior-minute return only. No bar containing the fill."""
    con.execute(
        """
        CREATE TEMP TABLE fe_annot AS
        SELECT
            f.*,
            EXTRACT(hour FROM f.fill_ts AT TIME ZONE 'UTC')::INTEGER AS utc_hour,
            EXTRACT(dow FROM f.fill_ts AT TIME ZONE 'UTC')::INTEGER AS utc_dow,
            CASE WHEN f.fill_ts < TIMESTAMP '2025-12-01' THEN 'train' ELSE 'test' END AS split,
            kp.close AS prior_min_close,
            kp.prev_close AS two_min_close,
            CASE
                WHEN kp.prev_close IS NULL OR kp.prev_close = 0 THEN NULL
                ELSE (kp.close - kp.prev_close) / kp.prev_close
            END AS prior_min_return,
            kp.realized_vol_60m_prior / NULLIF(kp.avg_close_60m_prior, 0) AS realized_vol_60m_pct
        FROM fill_events f
        LEFT JOIN klines kp
          ON kp.symbol = f.symbol
         AND kp.bar_ts = date_trunc('minute', f.fill_ts) - INTERVAL '1 minute'
        """
    )
    con.execute("CREATE INDEX fe_idx ON fe_annot(condition_id, fill_ts)")


def _annotate_post_fill(con: Any) -> None:
    """Post-fill features for Tier D research validators. Adds the 1m bar
    containing the fill plus the next bar."""
    con.execute(
        """
        CREATE TEMP TABLE fe_post AS
        SELECT
            f.condition_id,
            f.fill_ts,
            kc.close AS containing_close,
            kc.next_close AS next_min_close,
            CASE
                WHEN kc.close IS NULL OR kc.close = 0 THEN NULL
                ELSE (kc.next_close - kc.close) / kc.close
            END AS post_min_return
        FROM fill_events f
        LEFT JOIN klines kc
          ON kc.symbol = f.symbol
         AND kc.bar_ts = date_trunc('minute', f.fill_ts)
        """
    )


def _classify_wallets(con: Any) -> None:
    con.execute(
        """
        CREATE TEMP TABLE wallet_profile AS
        SELECT
            wallet,
            SUM(is_maker) AS maker_fills,
            SUM(1 - is_maker) AS taker_fills,
            SUM(is_maker) + SUM(1 - is_maker) AS total_fills,
            COUNT(DISTINCT condition_id) AS distinct_markets
        FROM (
            SELECT maker_addr AS wallet, condition_id, 1 AS is_maker FROM fill_events
            UNION ALL
            SELECT taker_addr AS wallet, condition_id, 0 AS is_maker FROM fill_events
        )
        WHERE wallet IS NOT NULL
        GROUP BY wallet
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE wallet_archetype AS
        SELECT
            wallet,
            total_fills,
            maker_fills,
            taker_fills,
            distinct_markets,
            CASE
                WHEN total_fills >= 100000 AND maker_fills > taker_fills THEN 'mm_l1'
                WHEN total_fills >= 10000 AND maker_fills > taker_fills THEN 'mm_l2'
                WHEN total_fills >= 1000 AND maker_fills > taker_fills THEN 'mm_l3'
                WHEN total_fills >= 10000 AND taker_fills > maker_fills THEN 'taker_heavy'
                WHEN total_fills >= 1000 AND taker_fills > maker_fills THEN 'taker_active'
                WHEN total_fills >= 100 THEN 'mixed_mid'
                ELSE 'light'
            END AS archetype
        FROM wallet_profile
        """
    )


def _h1_counterparty_archetype(con: Any) -> dict[str, Any]:
    """Tier A #1 — counterparty archetype, with walk-forward."""
    cost_sql = _cost_select()
    con.execute(
        f"""
        SELECT
            wm.archetype AS maker_archetype,
            wt.archetype AS taker_archetype,
            split,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            {cost_sql}
        FROM fe_annot f
        LEFT JOIN wallet_archetype wm ON wm.wallet = f.maker_addr
        LEFT JOIN wallet_archetype wt ON wt.wallet = f.taker_addr
        GROUP BY wm.archetype, wt.archetype, split
        HAVING fills >= 1000
        ORDER BY avg_net_roi_020mp DESC NULLS LAST
        """
    )
    by_pair_split = _fetch_dicts(con)

    con.execute(
        f"""
        SELECT
            wm.archetype AS maker_archetype,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            {cost_sql}
        FROM fe_annot f
        LEFT JOIN wallet_archetype wm ON wm.wallet = f.maker_addr
        GROUP BY wm.archetype
        ORDER BY avg_net_roi_020mp DESC NULLS LAST
        """
    )
    by_maker = _fetch_dicts(con)

    return {
        "title": "Tier A #1 — counterparty maker archetype (taker = Bot G analogue)",
        "by_maker": by_maker,
        "by_pair_split": by_pair_split,
    }


def _h3_cascade(con: Any) -> dict[str, Any]:
    """Tier A #3 — multi-wallet taker cascade detection in 15s window per condition+side."""
    cost_sql = _cost_select()
    con.execute(
        """
        CREATE TEMP TABLE fe_cascade AS
        SELECT
            *,
            COUNT(DISTINCT taker_addr) OVER (
                PARTITION BY condition_id, side
                ORDER BY EXTRACT(epoch FROM fill_ts)
                RANGE BETWEEN 15 PRECEDING AND 0 PRECEDING
            ) AS cascade_takers_15s
        FROM fe_annot
        """
    )
    con.execute(
        f"""
        SELECT
            CASE
                WHEN cascade_takers_15s <= 1 THEN 'isolated'
                WHEN cascade_takers_15s = 2 THEN 'pair'
                WHEN cascade_takers_15s <= 4 THEN 'small_group'
                ELSE 'cascade'
            END AS cascade_bucket,
            split,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            {cost_sql}
        FROM fe_cascade
        GROUP BY cascade_bucket, split
        ORDER BY cascade_bucket, split
        """
    )
    return {
        "title": "Tier A #3 — multi-wallet taker cascade in 15s window (per condition+side)",
        "by_bucket_split": _fetch_dicts(con),
    }


def _h4_time_of_day(con: Any) -> dict[str, Any]:
    cost_sql = _cost_select()
    con.execute(
        f"""
        SELECT
            utc_hour,
            split,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            {cost_sql}
        FROM fe_annot
        GROUP BY utc_hour, split
        ORDER BY utc_hour, split
        """
    )
    return {
        "title": "Tier A #4 — time-of-day session (UTC hour) by split",
        "by_hour_split": _fetch_dicts(con),
    }


def _h5_btc_lead_lag(con: Any) -> dict[str, Any]:
    """Tier B #5 — for ETH/SOL fills, condition on BTC prior-minute return."""
    cost_sql = _cost_select()
    con.execute(
        """
        CREATE TEMP TABLE fe_btc AS
        SELECT
            f.symbol,
            f.side,
            f.won,
            f.price,
            f.split,
            f.lead_sec,
            kb.close AS btc_close,
            kb.prev_close AS btc_prev_close,
            CASE
                WHEN kb.prev_close IS NULL OR kb.prev_close = 0 THEN NULL
                ELSE (kb.close - kb.prev_close) / kb.prev_close
            END AS btc_prior_min_return
        FROM fe_annot f
        LEFT JOIN klines kb
          ON kb.symbol = 'BTC'
         AND kb.bar_ts = date_trunc('minute', f.fill_ts) - INTERVAL '1 minute'
        WHERE f.symbol IN ('ETH','SOL')
        """
    )
    con.execute(
        f"""
        SELECT
            symbol,
            split,
            CASE
                WHEN btc_prior_min_return IS NULL THEN 'unknown'
                WHEN ABS(btc_prior_min_return) < 0.0005 THEN 'btc_flat'
                WHEN btc_prior_min_return > 0 THEN 'btc_up'
                ELSE 'btc_down'
            END AS btc_state,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            {cost_sql}
        FROM fe_btc
        GROUP BY symbol, split, btc_state
        ORDER BY symbol, split, btc_state
        """
    )
    return {
        "title": "Tier B #5 — ETH/SOL conditioned on BTC prior-minute return state",
        "by_symbol_state_split": _fetch_dicts(con),
    }


def _h6_final_15s(con: Any) -> dict[str, Any]:
    """Tier B #6 — final-15s window vs full 5-600s baseline."""
    cost_sql = _cost_select()
    con.execute(
        f"""
        SELECT
            CASE
                WHEN lead_sec <= 15 THEN 'final_5_to_15s'
                WHEN lead_sec <= 30 THEN '15_to_30s'
                WHEN lead_sec <= 60 THEN '30_to_60s'
                WHEN lead_sec <= 120 THEN '60_to_120s'
                WHEN lead_sec <= 300 THEN '120_to_300s'
                ELSE '300_to_600s'
            END AS lead_band,
            split,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            {cost_sql}
        FROM fe_annot
        GROUP BY lead_band, split
        ORDER BY lead_band, split
        """
    )
    return {
        "title": "Tier B #6 — lead-band breakdown (final-15s vs others) by split",
        "by_lead_split": _fetch_dicts(con),
    }


def _h11_price_band(con: Any) -> dict[str, Any]:
    """Tier B #11 — price-level expansion test."""
    cost_sql = _cost_select()
    con.execute(
        f"""
        SELECT
            CASE
                WHEN price < 0.035 THEN '<3.5c'
                WHEN price < 0.055 THEN '3.5-5.5c'
                WHEN price < 0.080 THEN '5.5-8c'
                WHEN price < 0.10 THEN '8-10c'
                WHEN price < 0.20 THEN '10-20c'
                ELSE '20c+'
            END AS price_band,
            split,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            {cost_sql}
        FROM fe_annot
        GROUP BY price_band, split
        ORDER BY price_band, split
        """
    )
    return {
        "title": "Tier B #11 — price-level expansion (3.5-5.5c live band vs alternatives)",
        "by_price_split": _fetch_dicts(con),
    }


def _h12_volatility(con: Any) -> dict[str, Any]:
    """Tier C #12 — volatility regime, both directions tested."""
    cost_sql = _cost_select()
    con.execute(
        f"""
        WITH ranked AS (
            SELECT
                fa.*,
                NTILE(10) OVER (ORDER BY realized_vol_60m_pct) AS vol_decile
            FROM fe_annot fa
            WHERE realized_vol_60m_pct IS NOT NULL
        )
        SELECT
            vol_decile,
            split,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            AVG(realized_vol_60m_pct) AS avg_realized_vol,
            {cost_sql}
        FROM ranked
        GROUP BY vol_decile, split
        ORDER BY vol_decile, split
        """
    )
    return {
        "title": "Tier C #12 — realized 60m volatility decile (strictly prior bars)",
        "by_decile_split": _fetch_dicts(con),
    }


def _h_post_fill_validators(con: Any) -> dict[str, Any]:
    """Tier D #14/#15 — post-fill validators. RESEARCH ONLY."""
    cost_sql = _cost_select()
    con.execute(
        f"""
        SELECT
            CASE
                WHEN post_min_return IS NULL THEN 'unknown'
                WHEN ABS(post_min_return) < 0.0003 THEN 'true_flat'
                WHEN post_min_return > 0 THEN 'post_up'
                ELSE 'post_down'
            END AS post_state,
            split,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            {cost_sql}
        FROM fe_annot a
        LEFT JOIN fe_post p
          ON p.condition_id = a.condition_id
         AND p.fill_ts = a.fill_ts
        GROUP BY post_state, split
        ORDER BY post_state, split
        """
    )
    return {
        "title": "Tier D #14/#15 — post-fill 1m return (RESEARCH VALIDATOR ONLY, NOT AN ENTRY GATE)",
        "by_post_state_split": _fetch_dicts(con),
    }


def _baseline(con: Any) -> dict[str, Any]:
    cost_sql = _cost_select()
    con.execute(
        f"""
        SELECT
            split,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            {cost_sql}
        FROM fe_annot
        GROUP BY split
        ORDER BY split
        """
    )
    return _fetch_dicts(con)


def _wallet_archetype_counts(con: Any) -> list[dict[str, Any]]:
    con.execute(
        """
        SELECT
            archetype,
            COUNT(*) AS wallet_count,
            SUM(total_fills) AS total_fills,
            SUM(maker_fills) AS maker_fills,
            SUM(taker_fills) AS taker_fills
        FROM wallet_archetype
        GROUP BY archetype
        ORDER BY total_fills DESC
        """
    )
    return _fetch_dicts(con)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _fmt_int(v: Any) -> str:
    if v is None:
        return ""
    return f"{int(v):,}"


def _fmt_pct(v: Any) -> str:
    if v is None:
        return ""
    return f"{float(v):.2f}%"


def _fmt_roi(v: Any) -> str:
    if v is None:
        return ""
    return f"{float(v) * 100:.2f}%"


def _fmt_price(v: Any) -> str:
    if v is None:
        return ""
    return f"{float(v):.4f}"


def _table(rows: list[dict[str, Any]], cols: list[tuple[str, str, str]]) -> str:
    """cols = list of (key, display, fmt) where fmt in {int, pct, roi, price, str}."""
    if not rows:
        return "_no rows_"
    headers = "| " + " | ".join(c[1] for c in cols) + " |"
    align = "|" + "|".join("---:" if c[2] in {"int", "pct", "roi", "price"} else "---" for c in cols) + "|"
    body_lines = []
    for r in rows:
        cells = []
        for key, _, fmt in cols:
            v = r.get(key)
            if fmt == "int":
                cells.append(_fmt_int(v))
            elif fmt == "pct":
                cells.append(_fmt_pct(v))
            elif fmt == "roi":
                cells.append(_fmt_roi(v))
            elif fmt == "price":
                cells.append(_fmt_price(v))
            else:
                cells.append("" if v is None else str(v))
        body_lines.append("| " + " | ".join(cells) + " |")
    return "\n".join([headers, align] + body_lines)


HYP_COLS = [
    ("split", "split", "str"),
    ("fills", "fills", "int"),
    ("win_pct", "win %", "pct"),
    ("avg_price", "avg price", "price"),
    ("avg_net_roi_000mp", "ROI 0c", "roi"),
    ("avg_net_roi_010mp", "ROI 1c", "roi"),
    ("avg_net_roi_020mp", "ROI 2c", "roi"),
]


def render_md(out: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Becker Hypothesis Validation")
    lines.append("")
    lines.append(f"Generated: `{out['generated_at']}`")
    lines.append(f"Becker data: `{out['becker_data']}`")
    lines.append(f"Binance klines: `{out['klines_dir']}`")
    lines.append(f"Walk-forward cutoff: `{WALK_FORWARD_CUTOFF}` (split = `train` if fill_ts < cutoff else `test`)")
    lines.append("")
    lines.append("## Read this first")
    lines.append("")
    lines.append("Read-only research. Tests Track 1 hypotheses on the 49M-fill Becker historical dataset using strictly causal time windows (prior minute only, never the bar containing the fill). Tier D items deliberately use post-fill data and are flagged as research validators only — they cannot become entry rules.")
    lines.append("")
    lines.append("Per OQ-081 audit: this report does not authorize any Bot G, Bot D, Bot B, FV paper, or recorder service change. Authority comes from running these features on Bot G/FV-bot's own forward data and surviving forward paper.")
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- Resolved 15m BTC/ETH/SOL Up/Down tokens: `{out['tokens_15m']:,}`")
    lines.append(f"- Fills in lead `{out['min_lead_sec']}-{out['max_lead_sec']}s` window: `{out['fill_count']:,}`")
    lines.append("")
    lines.append("## Baseline")
    lines.append("")
    lines.append(_table(out["baseline"], HYP_COLS))
    lines.append("")
    lines.append("Use this baseline as the reference. A hypothesis is supportive if its conditional cell shows higher win rate AND higher net ROI than the matching split row above, and the lift is consistent across train and test.")
    lines.append("")
    lines.append("## Wallet archetype distribution")
    lines.append("")
    lines.append(_table(out["wallet_archetype_counts"], [
        ("archetype", "archetype", "str"),
        ("wallet_count", "wallets", "int"),
        ("total_fills", "total fills", "int"),
        ("maker_fills", "as maker", "int"),
        ("taker_fills", "as taker", "int"),
    ]))
    lines.append("")

    h1 = out["h1_counterparty"]
    lines.append(f"## {h1['title']}")
    lines.append("")
    lines.append("**Maker archetype (Bot G analogue is taker, so this is who Bot G fades against):**")
    lines.append("")
    lines.append(_table(h1["by_maker"], [
        ("maker_archetype", "maker archetype", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("avg_net_roi_000mp", "ROI 0c", "roi"),
        ("avg_net_roi_010mp", "ROI 1c", "roi"),
        ("avg_net_roi_020mp", "ROI 2c", "roi"),
    ]))
    lines.append("")
    lines.append("**Maker × taker archetype pairs by split (≥1k fills):**")
    lines.append("")
    lines.append(_table(h1["by_pair_split"], [
        ("maker_archetype", "maker", "str"),
        ("taker_archetype", "taker", "str"),
        ("split", "split", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("avg_net_roi_000mp", "ROI 0c", "roi"),
        ("avg_net_roi_010mp", "ROI 1c", "roi"),
        ("avg_net_roi_020mp", "ROI 2c", "roi"),
    ]))
    lines.append("")

    h3 = out["h3_cascade"]
    lines.append(f"## {h3['title']}")
    lines.append("")
    lines.append(_table(h3["by_bucket_split"], [
        ("cascade_bucket", "cascade", "str"),
        ("split", "split", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("avg_net_roi_000mp", "ROI 0c", "roi"),
        ("avg_net_roi_010mp", "ROI 1c", "roi"),
        ("avg_net_roi_020mp", "ROI 2c", "roi"),
    ]))
    lines.append("")

    h4 = out["h4_time_of_day"]
    lines.append(f"## {h4['title']}")
    lines.append("")
    lines.append(_table(h4["by_hour_split"], [
        ("utc_hour", "utc hr", "int"),
        ("split", "split", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("avg_net_roi_020mp", "ROI 2c", "roi"),
    ]))
    lines.append("")

    h5 = out["h5_btc_lead_lag"]
    lines.append(f"## {h5['title']}")
    lines.append("")
    lines.append(_table(h5["by_symbol_state_split"], [
        ("symbol", "symbol", "str"),
        ("split", "split", "str"),
        ("btc_state", "btc state", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("avg_net_roi_020mp", "ROI 2c", "roi"),
    ]))
    lines.append("")

    h6 = out["h6_final_15s"]
    lines.append(f"## {h6['title']}")
    lines.append("")
    lines.append(_table(h6["by_lead_split"], [
        ("lead_band", "lead", "str"),
        ("split", "split", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("avg_net_roi_020mp", "ROI 2c", "roi"),
    ]))
    lines.append("")

    h11 = out["h11_price_band"]
    lines.append(f"## {h11['title']}")
    lines.append("")
    lines.append(_table(h11["by_price_split"], [
        ("price_band", "price band", "str"),
        ("split", "split", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("avg_net_roi_020mp", "ROI 2c", "roi"),
    ]))
    lines.append("")

    h12 = out["h12_volatility"]
    lines.append(f"## {h12['title']}")
    lines.append("")
    lines.append("Decile 1 = lowest volatility, decile 10 = highest. GLM proposed low-vol; DeepSeek R1 proposed high-vol. Read both ends.")
    lines.append("")
    lines.append(_table(h12["by_decile_split"], [
        ("vol_decile", "decile", "int"),
        ("split", "split", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_realized_vol", "avg vol", "price"),
        ("avg_net_roi_020mp", "ROI 2c", "roi"),
    ]))
    lines.append("")

    hd = out["h_post_fill"]
    lines.append(f"## {hd['title']}")
    lines.append("")
    lines.append("**WARNING — RESEARCH VALIDATOR ONLY.** This uses post-fill 1m data (the bar containing the fill plus the next bar). It cannot be used as an entry rule because the bot does not know post-fill data at decision time. This table is provided to characterise *which* fills won, not to produce a tradeable filter.")
    lines.append("")
    lines.append(_table(hd["by_post_state_split"], [
        ("post_state", "post state", "str"),
        ("split", "split", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("avg_net_roi_020mp", "ROI 2c", "roi"),
    ]))
    lines.append("")

    lines.append("## How to read these tables")
    lines.append("")
    lines.append("1. A hypothesis is **supported** if a conditional cell beats baseline by `>5pp` win rate AND by `>10pp` net ROI 2c, AND the lift is present in BOTH `train` and `test`.")
    lines.append("2. A hypothesis is **rejected** if train shows lift but test does not, or if test ROI is negative.")
    lines.append("3. Sample sizes below `1,000` are flagged. Below `100` is unreliable.")
    lines.append("4. Tier D post-fill rows must NEVER be used as entry rules — they only validate the existence of a winning subset post-hoc.")
    lines.append("")
    lines.append("## Next steps")
    lines.append("")
    lines.append("1. Operator review of which features pass the supported gate above.")
    lines.append("2. For supported features, run Script 2 (recorder microstructure validation) on Bot G's own forward fills to confirm the lift translates from Becker conditions to Bot G's actual fill conditions.")
    lines.append("3. Only then propose any ADR. No paper or live parameter change is authorized from this report alone.")
    return "\n".join(lines) + "\n"


def run_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        import duckdb
    except ImportError as exc:
        raise SystemExit("duckdb is required") from exc

    data_dir = Path(args.becker_data).resolve()
    klines_dir = Path(args.klines_dir).resolve()
    if not (data_dir / "polymarket").exists():
        raise SystemExit(f"Becker data path not found: {data_dir}")
    if not klines_dir.exists():
        raise SystemExit(f"Binance klines path not found: {klines_dir}")

    tmp_dir = data_dir.parent / "duckdb-tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("PRAGMA preserve_insertion_order=false")
    con.execute(f"PRAGMA memory_limit='{args.memory_limit}'")
    con.execute(f"PRAGMA temp_directory='{tmp_dir.as_posix()}'")

    args.max_lead_sec = max(args.max_lead_sec, 600)
    token_rows = load_token_rows(con, data_dir, args)
    token_rows_15 = [r for r in token_rows if r.duration_minutes == 15]
    if not token_rows_15:
        raise SystemExit("No resolved 15m crypto Up/Down tokens found")

    con.execute(
        """
        CREATE TEMP TABLE token_map (
            token_id VARCHAR,
            condition_id VARCHAR,
            symbol VARCHAR,
            duration_minutes INTEGER,
            side VARCHAR,
            won BOOLEAN,
            end_ts TIMESTAMPTZ
        )
        """
    )
    con.executemany(
        "INSERT INTO token_map VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(r.token_id, r.condition_id, r.symbol, r.duration_minutes, r.side, r.won, r.end_ts) for r in token_rows_15],
    )
    print(f"loaded {len(token_rows_15):,} resolved 15m tokens", flush=True)

    fill_count = _build_fill_events(con, data_dir, args)
    print(f"built fill_events: {fill_count:,} fills", flush=True)

    _build_klines(con, klines_dir)
    print("built klines table", flush=True)

    _annotate_strictly_causal(con)
    print("annotated strictly causal features", flush=True)

    _annotate_post_fill(con)
    print("annotated post-fill features (Tier D)", flush=True)

    _classify_wallets(con)
    archetype_counts = _wallet_archetype_counts(con)
    print(f"classified wallets: {sum(r['wallet_count'] for r in archetype_counts):,} unique", flush=True)

    output: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "becker_data": str(data_dir),
        "klines_dir": str(klines_dir),
        "tokens_15m": len(token_rows_15),
        "fill_count": fill_count,
        "min_lead_sec": args.min_lead_sec,
        "max_lead_sec": args.max_lead_sec,
        "walk_forward_cutoff": WALK_FORWARD_CUTOFF,
        "baseline": _baseline(con),
        "wallet_archetype_counts": archetype_counts,
    }

    print("running H1 counterparty archetype...", flush=True)
    output["h1_counterparty"] = _h1_counterparty_archetype(con)
    print("running H3 cascade...", flush=True)
    output["h3_cascade"] = _h3_cascade(con)
    print("running H4 time-of-day...", flush=True)
    output["h4_time_of_day"] = _h4_time_of_day(con)
    print("running H5 BTC lead-lag...", flush=True)
    output["h5_btc_lead_lag"] = _h5_btc_lead_lag(con)
    print("running H6 final-15s...", flush=True)
    output["h6_final_15s"] = _h6_final_15s(con)
    print("running H11 price band...", flush=True)
    output["h11_price_band"] = _h11_price_band(con)
    print("running H12 volatility regime...", flush=True)
    output["h12_volatility"] = _h12_volatility(con)
    print("running post-fill validators...", flush=True)
    output["h_post_fill"] = _h_post_fill_validators(con)

    return output


def main() -> None:
    args = parse_args()
    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    if not out_md.is_absolute():
        out_md = REPO_ROOT / out_md
    if not out_json.is_absolute():
        out_json = REPO_ROOT / out_json

    data = run_report(args)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_md(data), encoding="utf-8")
    out_json.write_text(json.dumps(_jsonable(data), indent=2, default=str), encoding="utf-8")
    print(f"wrote {out_md}")
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
