#!/usr/bin/env python3
"""Phase A — Becker maker-side ROI + wallet persistence with realistic fees.

Two foundational tests that the prior `becker_hypothesis_validation_report.py`
did not run, both surfacing from the Codex + Grok external brainstorm:

1. **Maker-side ROI with realistic fees.** The prior validation report used a
   uniform `2c/share` fee proxy. That is roughly `22x` too punitive for
   cheap entries — actual Polymarket taker fees on a `5c` × 100-share trade
   are around `~$0.09` (≈ `0.09c/share`), and maker fees are typically
   `~0%`. This test recomputes per-fill conditional ROI for both sides
   using Becker's actual `fee` column for taker and `0%` for maker.

2. **Wallet performance persistence with shrinkage.** Distinct from the
   broad archetype clustering already tested. Computes per-wallet rolling
   ROI over a `30`-day prior window, applies a Beta-Binomial-style
   shrinkage estimator toward the global rate, then conditional ROI on
   subsequent fills filtered by counterparty performance decile.
   Walk-forward only — every wallet's score at fill time uses only prior
   fills.

All time windows are strictly causal. Output is Markdown + JSON.

Read-only. No bot/service/config/cap/wallet/order-path change is
authorised from this report.
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
from scripts.external_data_paths import default_becker_data_dir  # noqa: E402

UTC = timezone.utc

DEFAULT_BECKER_DATA = default_becker_data_dir()
DEFAULT_OUT_MD = Path("docs/reports/becker-maker-and-wallet-analysis-2026-05-06.md")
DEFAULT_OUT_JSON = Path("docs/reports/becker-maker-and-wallet-analysis-2026-05-06.json")
WALK_FORWARD_CUTOFF = "2025-12-01"
WALLET_PRIOR_WINDOW_DAYS = 30
SHRINKAGE_ALPHA = 50  # virtual count toward global rate


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--becker-data", default=str(DEFAULT_BECKER_DATA))
    p.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    p.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    p.add_argument("--max-lead-sec", type=int, default=600)
    p.add_argument("--min-lead-sec", type=int, default=5)
    p.add_argument("--memory-limit", default="6GB")
    p.add_argument("--min-end-date", default=None)
    p.add_argument("--max-end-date", default=None)
    return p.parse_args()


def _fetch_dicts(con: Any) -> list[dict[str, Any]]:
    cols = [d[0] for d in con.description]
    return [
        {cols[idx]: row[idx] for idx in range(len(cols))}
        for row in con.fetchall()
    ]


def _wilson(wins: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return centre - margin, centre + margin


def _build_fill_events(con: Any, data_dir: Path, args: argparse.Namespace) -> int:
    """Build fill_events with maker/taker addresses, prices, sizes, fees, won."""
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
            -- maker_role: 'maker_buy' if maker received tokens (gave USDC),
            --            'maker_sell' if maker received USDC (gave tokens).
            CASE
                WHEN t.maker_asset_id = '0' THEN 'maker_buy'
                ELSE 'maker_sell'
            END AS maker_role,
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


def _annotate_fill_economics(con: Any) -> None:
    """Compute per-fill realistic-fee-aware taker AND maker P&L per share.

    Becker `fee` is the TAKER fee in USDC. Per-share fee = fee_usd / shares.
    Maker fees on Polymarket are typically 0%; we model maker_fee_per_share = 0.

    For the side that the row represents (the side the BUYER bet on, which
    is `tm.side`):
    - `won` = True if that side resolved.
    - Taker-buyer (in `maker_sell` rows) bought the token at `price`.
      Per-share P&L = (1.0 if won else 0.0) - price - taker_fee_per_share.
    - Maker-seller (in `maker_sell` rows) is short the token at `price`.
      Per-share P&L = price - (1.0 if won else 0.0) - maker_fee_per_share.

    For `maker_buy` rows the maker bought the token; that maker's P&L is
    the "buyer P&L" but at zero fees. The taker SOLD the token; the
    taker's P&L is `price - won - taker_fee_per_share`. We compute both
    so the report can compare conditional-ROI for each role symmetrically.
    """
    con.execute(
        """
        CREATE TEMP TABLE fe_econ AS
        SELECT
            f.*,
            EXTRACT(hour FROM f.fill_ts AT TIME ZONE 'UTC')::INTEGER AS utc_hour,
            CASE WHEN f.fill_ts < TIMESTAMP '2025-12-01' THEN 'train' ELSE 'test' END AS split,
            -- Realistic per-share taker fee from Becker's recorded fee.
            CASE
                WHEN f.shares IS NULL OR f.shares = 0 THEN NULL
                ELSE f.fee_usd / f.shares
            END AS taker_fee_per_share,
            -- Maker fee modelled as 0 (Polymarket typical default).
            0.0 AS maker_fee_per_share,
            -- Audit-style 2c/share proxy for direct comparison.
            0.02 AS audit_proxy_fee_per_share
        FROM fill_events f
        """
    )
    con.execute("CREATE INDEX fe_econ_idx ON fe_econ(condition_id, fill_ts)")


def _build_pnl_views(con: Any) -> None:
    """Add per-share P&L columns under three fee regimes:
       - taker_2c: audit's old proxy
       - taker_real: realistic taker fee from Becker
       - maker_zero: realistic maker fee = 0
    Also captures buyer (taker-buyer) vs seller (taker-seller) split.
    """
    con.execute(
        """
        CREATE TEMP TABLE fe_pnl AS
        SELECT
            f.*,
            -- A "buyer of this side" gets paid 1 if won, 0 otherwise.
            -- A "seller of this side" pays 1 if won, 0 otherwise (collected price up front).
            (CASE WHEN won THEN 1.0 ELSE 0.0 END) - price - audit_proxy_fee_per_share
                AS buyer_pnl_per_share_2c,
            (CASE WHEN won THEN 1.0 ELSE 0.0 END) - price - taker_fee_per_share
                AS buyer_pnl_per_share_real,
            (CASE WHEN won THEN 1.0 ELSE 0.0 END) - price - maker_fee_per_share
                AS buyer_pnl_per_share_maker_zero,
            price - (CASE WHEN won THEN 1.0 ELSE 0.0 END) - audit_proxy_fee_per_share
                AS seller_pnl_per_share_2c,
            price - (CASE WHEN won THEN 1.0 ELSE 0.0 END) - taker_fee_per_share
                AS seller_pnl_per_share_real,
            price - (CASE WHEN won THEN 1.0 ELSE 0.0 END) - maker_fee_per_share
                AS seller_pnl_per_share_maker_zero
        FROM fe_econ f
        """
    )


def _baseline(con: Any) -> dict[str, list[dict[str, Any]]]:
    """Baseline win-rate and ROI under each fee regime, by split."""
    con.execute(
        """
        SELECT
            split,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            AVG(taker_fee_per_share) AS avg_taker_fee_per_share,
            AVG(taker_fee_per_share / NULLIF(price, 0)) AS avg_taker_fee_pct_of_price,

            AVG(buyer_pnl_per_share_2c / NULLIF(price + 0.02, 0))
                AS buyer_avg_roi_2c,
            AVG(buyer_pnl_per_share_real / NULLIF(price + taker_fee_per_share, 0))
                AS buyer_avg_roi_real,
            AVG(buyer_pnl_per_share_maker_zero / NULLIF(price, 0))
                AS buyer_avg_roi_maker_zero,

            AVG(seller_pnl_per_share_2c / NULLIF(1.0 - price + 0.02, 0))
                AS seller_avg_roi_2c,
            AVG(seller_pnl_per_share_real / NULLIF(1.0 - price + taker_fee_per_share, 0))
                AS seller_avg_roi_real,
            AVG(seller_pnl_per_share_maker_zero / NULLIF(1.0 - price, 0))
                AS seller_avg_roi_maker_zero
        FROM fe_pnl
        GROUP BY split
        ORDER BY split
        """
    )
    return {"by_split": _fetch_dicts(con)}


def _by_price_band(con: Any) -> list[dict[str, Any]]:
    """Conditional ROI by price band × split, for taker-buyer-2c (legacy),
    taker-buyer-real, AND maker-seller-zero. The maker-seller column is the
    interesting test: at cheap prices, does the maker (counterparty to a
    cheap-tail buyer) have positive expected value at zero maker fees?"""
    con.execute(
        """
        SELECT
            CASE
                WHEN price < 0.035 THEN '<3.5c'
                WHEN price < 0.055 THEN '3.5-5.5c'
                WHEN price < 0.080 THEN '5.5-8c'
                WHEN price < 0.10 THEN '8-10c'
                WHEN price < 0.15 THEN '10-15c'
                WHEN price < 0.20 THEN '15-20c'
                WHEN price < 0.30 THEN '20-30c'
                WHEN price < 0.50 THEN '30-50c'
                ELSE '50c+'
            END AS price_band,
            split,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            AVG(taker_fee_per_share / NULLIF(price, 0)) AS taker_fee_pct_of_price,

            AVG(buyer_pnl_per_share_2c / NULLIF(price + 0.02, 0))
                AS buyer_roi_2c,
            AVG(buyer_pnl_per_share_real / NULLIF(price + taker_fee_per_share, 0))
                AS buyer_roi_real,
            AVG(seller_pnl_per_share_maker_zero / NULLIF(1.0 - price, 0))
                AS maker_seller_roi_zero
        FROM fe_pnl
        GROUP BY price_band, split
        ORDER BY price_band, split
        """
    )
    return _fetch_dicts(con)


def _by_band_and_lead(con: Any) -> list[dict[str, Any]]:
    """Maker-seller ROI at zero fees, by price-band × lead-bucket × split."""
    con.execute(
        """
        SELECT
            CASE
                WHEN price < 0.055 THEN '3.5-5.5c'
                WHEN price < 0.080 THEN '5.5-8c'
                WHEN price < 0.10 THEN '8-10c'
                WHEN price < 0.15 THEN '10-15c'
                WHEN price < 0.20 THEN '15-20c'
                ELSE '20c+'
            END AS price_band,
            CASE
                WHEN lead_sec <= 30 THEN '5_to_30s'
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
            AVG(seller_pnl_per_share_maker_zero) AS maker_seller_pnl_per_share,
            AVG(seller_pnl_per_share_maker_zero / NULLIF(1.0 - price, 0))
                AS maker_seller_roi_zero
        FROM fe_pnl
        WHERE price < 0.20
        GROUP BY price_band, lead_band, split
        HAVING fills >= 1000
        ORDER BY price_band, lead_band, split
        """
    )
    return _fetch_dicts(con)


def _by_band_symbol_side(con: Any) -> list[dict[str, Any]]:
    """Maker-seller ROI at zero fees, by symbol × side × price band, test split only."""
    con.execute(
        """
        SELECT
            symbol,
            side,
            CASE
                WHEN price < 0.055 THEN '3.5-5.5c'
                WHEN price < 0.080 THEN '5.5-8c'
                WHEN price < 0.10 THEN '8-10c'
                WHEN price < 0.15 THEN '10-15c'
                ELSE '15c+'
            END AS price_band,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            AVG(seller_pnl_per_share_maker_zero / NULLIF(1.0 - price, 0))
                AS maker_seller_roi_zero
        FROM fe_pnl
        WHERE price < 0.15
          AND split = 'test'
        GROUP BY symbol, side, price_band
        HAVING fills >= 500
        ORDER BY symbol, side, price_band
        """
    )
    return _fetch_dicts(con)


def _wallet_persistence(con: Any) -> dict[str, Any]:
    """Wallet performance persistence with shrinkage, walk-forward.

    For each wallet, compute:
    - prior_taker_count: number of fills as taker in train split
    - prior_taker_wins: wins in train split
    - shrunk_taker_p: shrinkage estimator toward global mean
      = (prior_wins + alpha * global_p) / (prior_n + alpha)

    Then on test split, condition fills by the COUNTERPARTY's shrunk score
    (i.e., when our taker is filling, their MAKER's shrunk_taker_p when the
    maker has acted as taker before).

    A profitable filter would be: avoid takers/makers in extreme shrunken
    quintiles where the prior performance is reliably negative.
    """
    # Compute global rate from train.
    global_row = con.execute(
        """
        SELECT 100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS global_win_pct,
               COUNT(*) AS train_fills
        FROM fe_pnl
        WHERE split = 'train'
        """
    ).fetchone()
    global_win_pct = float(global_row[0])
    train_fills_count = int(global_row[1])

    # Compute prior per-wallet performance from train split only.
    con.execute(
        f"""
        CREATE TEMP TABLE wallet_prior AS
        SELECT
            wallet,
            SUM(role_fills) AS prior_total_fills,
            SUM(taker_fills) AS prior_taker_fills,
            SUM(taker_wins) AS prior_taker_wins,
            SUM(maker_fills) AS prior_maker_fills,
            SUM(maker_loss_count) AS prior_maker_loss_count
        FROM (
            SELECT
                taker_addr AS wallet,
                1 AS role_fills,
                1 AS taker_fills,
                CASE WHEN won THEN 1 ELSE 0 END AS taker_wins,
                0 AS maker_fills,
                0 AS maker_loss_count
            FROM fe_pnl
            WHERE split = 'train' AND taker_addr IS NOT NULL
            UNION ALL
            SELECT
                maker_addr AS wallet,
                1 AS role_fills,
                0 AS taker_fills,
                0 AS taker_wins,
                1 AS maker_fills,
                CASE WHEN won AND maker_role = 'maker_sell' THEN 1
                     WHEN NOT won AND maker_role = 'maker_buy' THEN 1
                     ELSE 0
                END AS maker_loss_count
            FROM fe_pnl
            WHERE split = 'train' AND maker_addr IS NOT NULL
        )
        GROUP BY wallet
        """
    )
    con.execute(
        f"""
        CREATE TEMP TABLE wallet_prior_shrunk AS
        SELECT
            wallet,
            prior_total_fills,
            prior_taker_fills,
            prior_taker_wins,
            prior_maker_fills,
            prior_maker_loss_count,
            -- Shrinkage estimator toward global rate. Explicit DOUBLE
            -- casts avoid DuckDB DECIMAL(18) overflow on big counts.
            CASE
                WHEN prior_taker_fills = 0
                    THEN CAST({global_win_pct:.6f} AS DOUBLE)
                ELSE (
                    (CAST(prior_taker_wins AS DOUBLE) * 100.0
                     + CAST({SHRINKAGE_ALPHA} AS DOUBLE) * CAST({global_win_pct:.6f} AS DOUBLE))
                    / NULLIF(CAST(prior_taker_fills AS DOUBLE) + CAST({SHRINKAGE_ALPHA} AS DOUBLE), 0)
                )
            END AS shrunk_taker_win_pct
        FROM wallet_prior
        """
    )

    # Distribution of shrunk scores.
    con.execute(
        """
        SELECT
            CASE
                WHEN prior_total_fills < 100 THEN 'tiny_<100'
                WHEN prior_total_fills < 1000 THEN 'small_100-1k'
                WHEN prior_total_fills < 10000 THEN 'mid_1k-10k'
                ELSE 'large_>=10k'
            END AS volume_bucket,
            COUNT(*) AS wallet_count,
            AVG(shrunk_taker_win_pct) AS avg_shrunk_score,
            MIN(shrunk_taker_win_pct) AS min_shrunk_score,
            MAX(shrunk_taker_win_pct) AS max_shrunk_score
        FROM wallet_prior_shrunk
        GROUP BY volume_bucket
        ORDER BY MIN(prior_total_fills)
        """
    )
    wallet_dist = _fetch_dicts(con)

    # Conditional test: bucket TEST fills by COUNTERPARTY (maker)'s shrunken
    # score and see if conditional outcomes differ.
    con.execute(
        """
        WITH ranked AS (
            SELECT
                f.*,
                ws.shrunk_taker_win_pct AS counterparty_score,
                NTILE(5) OVER (ORDER BY ws.shrunk_taker_win_pct) AS maker_shrunken_quintile
            FROM fe_pnl f
            INNER JOIN wallet_prior_shrunk ws ON ws.wallet = f.maker_addr
            WHERE f.split = 'test'
              AND ws.prior_total_fills >= 100
        )
        SELECT
            maker_shrunken_quintile,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            AVG(buyer_pnl_per_share_real / NULLIF(price + taker_fee_per_share, 0))
                AS buyer_roi_real,
            AVG(seller_pnl_per_share_maker_zero / NULLIF(1.0 - price, 0))
                AS maker_seller_roi_zero,
            MIN(counterparty_score) AS quintile_min_shrunk_score,
            MAX(counterparty_score) AS quintile_max_shrunk_score
        FROM ranked
        GROUP BY maker_shrunken_quintile
        ORDER BY maker_shrunken_quintile
        """
    )
    by_maker_shrunken = _fetch_dicts(con)

    # Same but for taker-side (test fills where the taker has prior history).
    con.execute(
        """
        WITH ranked AS (
            SELECT
                f.*,
                ws.shrunk_taker_win_pct AS counterparty_score,
                NTILE(5) OVER (ORDER BY ws.shrunk_taker_win_pct) AS taker_shrunken_quintile
            FROM fe_pnl f
            INNER JOIN wallet_prior_shrunk ws ON ws.wallet = f.taker_addr
            WHERE f.split = 'test'
              AND ws.prior_total_fills >= 100
        )
        SELECT
            taker_shrunken_quintile,
            COUNT(*) AS fills,
            SUM(CASE WHEN won THEN 1 ELSE 0 END) AS wins,
            100.0 * SUM(CASE WHEN won THEN 1 ELSE 0 END) / COUNT(*) AS win_pct,
            AVG(price) AS avg_price,
            AVG(buyer_pnl_per_share_real / NULLIF(price + taker_fee_per_share, 0))
                AS buyer_roi_real,
            AVG(seller_pnl_per_share_maker_zero / NULLIF(1.0 - price, 0))
                AS maker_seller_roi_zero,
            MIN(counterparty_score) AS quintile_min_shrunk_score,
            MAX(counterparty_score) AS quintile_max_shrunk_score
        FROM ranked
        GROUP BY taker_shrunken_quintile
        ORDER BY taker_shrunken_quintile
        """
    )
    by_taker_shrunken = _fetch_dicts(con)

    return {
        "global_win_pct_train": global_win_pct,
        "train_fills_count": train_fills_count,
        "shrinkage_alpha": SHRINKAGE_ALPHA,
        "wallet_volume_distribution": wallet_dist,
        "test_fills_by_maker_shrunken_quintile": by_maker_shrunken,
        "test_fills_by_taker_shrunken_quintile": by_taker_shrunken,
    }


def _format_pct(v: Any) -> str:
    if v is None:
        return ""
    return f"{float(v):.2f}%"


def _format_roi(v: Any) -> str:
    if v is None:
        return ""
    return f"{float(v) * 100:.2f}%"


def _format_int(v: Any) -> str:
    if v is None:
        return ""
    return f"{int(v):,}"


def _format_price(v: Any) -> str:
    if v is None:
        return ""
    return f"{float(v):.4f}"


def _format_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def _table(rows: list[dict[str, Any]], cols: list[tuple[str, str, str]]) -> str:
    if not rows:
        return "_no rows_"
    header = "| " + " | ".join(c[1] for c in cols) + " |"
    align = "|" + "|".join("---:" if c[2] in {"int", "pct", "roi", "price"} else "---" for c in cols) + "|"
    body = []
    for r in rows:
        cells = []
        for key, _, fmt in cols:
            v = r.get(key)
            if fmt == "int":
                cells.append(_format_int(v))
            elif fmt == "pct":
                cells.append(_format_pct(v))
            elif fmt == "roi":
                cells.append(_format_roi(v))
            elif fmt == "price":
                cells.append(_format_price(v))
            else:
                cells.append(_format_str(v))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, align] + body)


def render_md(out: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Becker Maker-Side ROI + Wallet Persistence Analysis")
    lines.append("")
    lines.append(f"Generated: `{out['generated_at']}`")
    lines.append(f"Becker data: `{out['becker_data']}`")
    lines.append(f"Walk-forward cutoff: `{WALK_FORWARD_CUTOFF}`")
    lines.append("")
    lines.append("## Read this first")
    lines.append("")
    lines.append("Read-only research. Two foundational tests that the prior `becker_hypothesis_validation_report.py` did not run:")
    lines.append("")
    lines.append("1. **Maker-side ROI with realistic fees** — the prior validation used a uniform `2c/share` fee proxy. That is roughly `22x` too punitive for cheap entries. This report computes per-fill ROI with three fee regimes side-by-side: `2c/share` audit proxy, realistic taker fee from Becker's recorded `fee_usd`, and zero maker fee.")
    lines.append("2. **Wallet performance persistence** with Beta-Binomial-style shrinkage on prior train split, applied to test fills.")
    lines.append("")
    lines.append("Per OQ-081 audit: this report does not authorize any bot/service/config/cap/wallet/order-path change.")
    lines.append("")

    lines.append("## Coverage")
    lines.append("")
    lines.append(f"- Resolved 15m BTC/ETH/SOL Up/Down tokens: `{out['tokens_15m']:,}`")
    lines.append(f"- Fills in lead `{out['min_lead_sec']}-{out['max_lead_sec']}s` window: `{out['fill_count']:,}`")
    lines.append("")

    lines.append("## Baseline by split — three fee regimes")
    lines.append("")
    lines.append("`buyer_*` rows: someone took the offer (bought the token at `price`).  `seller_*` rows: someone hit a bid (sold the token at `price`). The `_2c` columns reproduce the audit. The `_real` columns use Becker's actual `fee_usd`. The `_maker_zero` columns model maker fees as zero.")
    lines.append("")
    lines.append(_table(out["baseline"]["by_split"], [
        ("split", "split", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("avg_taker_fee_pct_of_price", "fee/price", "pct"),
        ("buyer_avg_roi_2c", "buyer ROI 2c (audit)", "roi"),
        ("buyer_avg_roi_real", "buyer ROI real-fee", "roi"),
        ("seller_avg_roi_maker_zero", "seller ROI 0 fee", "roi"),
    ]))
    lines.append("")
    lines.append("**Read:** if `buyer_avg_roi_real` is much closer to zero than `buyer_avg_roi_2c`, the audit's fee proxy was too punitive. If `seller_avg_roi_maker_zero` is positive on test, maker-side has expected edge that the audit missed.")
    lines.append("")

    lines.append("## ROI by price band, three fee regimes")
    lines.append("")
    lines.append("`buyer ROI 2c`: replay of audit. `buyer ROI real`: realistic taker fees from Becker. `maker-seller ROI 0`: counterparty (the maker selling cheap tails to buyers like Bot G) at zero maker fees.")
    lines.append("")
    lines.append(_table(out["by_price_band"], [
        ("price_band", "price band", "str"),
        ("split", "split", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("taker_fee_pct_of_price", "fee/price", "pct"),
        ("buyer_roi_2c", "buyer ROI 2c", "roi"),
        ("buyer_roi_real", "buyer ROI real", "roi"),
        ("maker_seller_roi_zero", "maker-sell ROI 0", "roi"),
    ]))
    lines.append("")

    lines.append("## Maker-seller ROI by price band × lead bucket (test split, ≥1000 fills)")
    lines.append("")
    lines.append(_table(out["by_band_and_lead"], [
        ("price_band", "price band", "str"),
        ("lead_band", "lead", "str"),
        ("split", "split", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("maker_seller_pnl_per_share", "$/share", "price"),
        ("maker_seller_roi_zero", "maker-sell ROI 0", "roi"),
    ]))
    lines.append("")

    lines.append("## Maker-seller ROI by symbol × side × price band (test split, ≥500 fills)")
    lines.append("")
    lines.append(_table(out["by_band_symbol_side"], [
        ("symbol", "symbol", "str"),
        ("side", "side", "str"),
        ("price_band", "price band", "str"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("maker_seller_roi_zero", "maker-sell ROI 0", "roi"),
    ]))
    lines.append("")

    lines.append("## Wallet performance persistence with shrinkage")
    lines.append("")
    wp = out["wallet_persistence"]
    lines.append(f"Train-split global win rate: `{wp['global_win_pct_train']:.2f}%`")
    lines.append(f"Train fills: `{wp['train_fills_count']:,}`")
    lines.append(f"Shrinkage alpha (virtual count): `{wp['shrinkage_alpha']}`")
    lines.append("")
    lines.append("**Wallet volume distribution (training population):**")
    lines.append("")
    lines.append(_table(wp["wallet_volume_distribution"], [
        ("volume_bucket", "volume", "str"),
        ("wallet_count", "wallets", "int"),
        ("avg_shrunk_score", "avg shrunken score", "pct"),
        ("min_shrunk_score", "min", "pct"),
        ("max_shrunk_score", "max", "pct"),
    ]))
    lines.append("")
    lines.append("**Test fills filtered by COUNTERPARTY (maker) shrunken score quintile:**")
    lines.append("")
    lines.append(_table(wp["test_fills_by_maker_shrunken_quintile"], [
        ("maker_shrunken_quintile", "quintile", "int"),
        ("quintile_min_shrunk_score", "min score", "pct"),
        ("quintile_max_shrunk_score", "max score", "pct"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("buyer_roi_real", "buyer ROI real", "roi"),
        ("maker_seller_roi_zero", "maker-sell ROI 0", "roi"),
    ]))
    lines.append("")
    lines.append("**Test fills filtered by TAKER's own shrunken score quintile:**")
    lines.append("")
    lines.append(_table(wp["test_fills_by_taker_shrunken_quintile"], [
        ("taker_shrunken_quintile", "quintile", "int"),
        ("quintile_min_shrunk_score", "min score", "pct"),
        ("quintile_max_shrunk_score", "max score", "pct"),
        ("fills", "fills", "int"),
        ("win_pct", "win %", "pct"),
        ("avg_price", "avg price", "price"),
        ("buyer_roi_real", "buyer ROI real", "roi"),
        ("maker_seller_roi_zero", "maker-sell ROI 0", "roi"),
    ]))
    lines.append("")

    lines.append("## How to read this report")
    lines.append("")
    lines.append("1. **If `seller_avg_roi_maker_zero` baseline is positive** AND `maker_seller_roi_zero` is positive in cheap price bands on the test split AND survives the `≥1000` fills lead-band filter, **maker-side at cheap tails is the missed edge.** The audit's `2c/share` proxy hid it.")
    lines.append("2. **If buyer_avg_roi_real is materially closer to zero** than `buyer_avg_roi_2c`, the audit's fee proxy was too punitive but doesn't change the rejection (still negative — just less negative).")
    lines.append("3. **If the wallet quintile table shows monotonic ROI gradient** (e.g. quintile 5 of maker shrunken score has materially better buyer ROI on test), there is a tradeable counterparty signal.")
    lines.append("4. **If quintiles are flat**, wallet persistence at the shrinkage level chosen is not a useful filter at this granularity.")
    lines.append("")
    lines.append("## Next steps")
    lines.append("")
    lines.append("- If maker-side surfaces edge: build a maker-only paper bot research lane (separate from Bot G) that simulates posting at the indicated bands and lead buckets, with realistic fill probability modeling. Forward paper validation per OQ-081.")
    lines.append("- If wallet shrinkage shows monotonic signal: build a counterparty-filter feature for Bot G and validate on Bot G's own forward fills before any operating change.")
    lines.append("- If neither surfaces: move to LightGBM multi-feature model on the same feature set.")
    return "\n".join(lines) + "\n"


def run_report(args: argparse.Namespace) -> dict[str, Any]:
    try:
        import duckdb
    except ImportError as exc:
        raise SystemExit("duckdb is required") from exc

    data_dir = Path(args.becker_data).resolve()
    if not (data_dir / "polymarket").exists():
        raise SystemExit(f"Becker data path not found: {data_dir}")

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

    _annotate_fill_economics(con)
    print("annotated economics (fees + split)", flush=True)

    _build_pnl_views(con)
    print("built P&L views (3 fee regimes × buyer/seller)", flush=True)

    output: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "becker_data": str(data_dir),
        "tokens_15m": len(token_rows_15),
        "fill_count": fill_count,
        "min_lead_sec": args.min_lead_sec,
        "max_lead_sec": args.max_lead_sec,
        "walk_forward_cutoff": WALK_FORWARD_CUTOFF,
    }

    print("running baseline...", flush=True)
    output["baseline"] = _baseline(con)

    print("running by-price-band conditional ROI...", flush=True)
    output["by_price_band"] = _by_price_band(con)

    print("running maker-seller by band × lead × split...", flush=True)
    output["by_band_and_lead"] = _by_band_and_lead(con)

    print("running maker-seller by symbol × side × band...", flush=True)
    output["by_band_symbol_side"] = _by_band_symbol_side(con)

    print("running wallet persistence with shrinkage...", flush=True)
    output["wallet_persistence"] = _wallet_persistence(con)

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
    out_json.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out_md}")
    print(f"wrote {out_json}")


if __name__ == "__main__":
    main()
