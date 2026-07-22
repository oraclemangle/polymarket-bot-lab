"""Hunter — offline nightly whale ranker.

Pipeline:
  1. Pull top-N wallets from Polymarket's leaderboard (profit + volume).
  2. For each wallet, fetch recent trades from the data-api.
  3. Join trades against data/backtest.db resolved_markets to compute P&L per
     position (where markets have resolved).
  4. Compute metrics: trade_count, win_rate, profit_factor, Sharpe,
     recent-edge ratio, 7d-vs-30d share.
  5. Apply filters (min_trades, min_win_rate, min_profit_factor, recent-edge).
  6. Rank by per-trade Sharpe, keep top-N.
  7. Write ranking to data/bot_f.db hunter_rankings.

All data sources are public (Polymarket lb-api, data-api) — no auth.
Zero execution — this is a measurement-only module.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Iterable

import httpx
from sqlalchemy import select

from bots.bot_f.config import (
    DATA_API_URL,
    HUNTER_CATEGORY_BLACKLIST,
    HUNTER_LEADERBOARD_SAMPLE,
    HUNTER_LOOKBACK_DAYS,
    HUNTER_MIN_PROFIT_FACTOR,
    HUNTER_MIN_TRADES,
    HUNTER_MIN_WIN_RATE,
    HUNTER_RECENT_EDGE_RATIO,
    HUNTER_7D_MIN_SHARE,
    HUNTER_TOP_N,
    HUNTER_TRADES_PER_WALLET,
    LB_API_URL,
)
from bots.bot_f.db import HunterRanking, get_bot_f_session_factory
from core.backtest_db import (
    DEFAULT_BACKTEST_DB,
    ResolvedMarket,
    get_backtest_session_factory,
)

log = logging.getLogger(__name__)


# --- Data fetchers ---

def fetch_leaderboard(
    client: httpx.Client,
    interval: str = "1m",
    metric: str = "profit",
    limit: int = 200,
) -> list[dict]:
    """Fetch volume/profit leaderboard. interval: 1d|1w|1m|all."""
    try:
        r = client.get(f"{LB_API_URL}/{metric}", params={"interval": interval, "limit": limit})
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        log.warning("leaderboard.fetch_failed metric=%s interval=%s: %s", metric, interval, e)
        return []


def fetch_wallet_trades(
    client: httpx.Client,
    wallet: str,
    limit: int = 500,
) -> list[dict]:
    """Fetch recent trades for a wallet via data-api."""
    try:
        r = client.get(
            f"{DATA_API_URL}/trades",
            params={"user": wallet, "limit": limit},
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        log.debug("wallet.trades.fetch_failed wallet=%s: %s", wallet[:12], e)
        return []


def fetch_wallet_closed_positions(
    client: httpx.Client,
    wallet: str,
    limit: int = 500,
) -> list[dict]:
    """Fetch all CLOSED (settled) positions with realisedPnl.

    data-api caps pages at 50; we paginate via offset to accumulate up to
    `limit`. The default sort is by P&L descending, so the FIRST pages
    are winners and later pages bring in losses — paginating deep is
    required to compute a real win_rate.
    """
    out: list[dict] = []
    offset = 0
    page_size = 50  # data-api hard cap
    max_pages = max(1, limit // page_size + 1)
    for _ in range(max_pages):
        try:
            r = client.get(
                f"{DATA_API_URL}/closed-positions",
                params={"user": wallet, "limit": page_size, "offset": offset},
                timeout=15.0,
            )
            r.raise_for_status()
            batch = r.json()
            if not isinstance(batch, list) or not batch:
                break
            out.extend(batch)
            if len(batch) < page_size:
                break  # final page
            offset += page_size
            if len(out) >= limit:
                break
            time.sleep(0.05)
        except Exception as e:
            log.debug("wallet.closed_positions.fetch_failed wallet=%s: %s", wallet[:12], e)
            break
    return out[:limit]


# --- Metric computation ---

@dataclass
class WalletMetrics:
    wallet: str
    pseudonym: str | None
    trade_count: int
    resolved_trade_count: int  # subset where we could compute P&L
    win_rate: float
    profit_factor: float
    sharpe: float
    realised_pnl_usd: float
    total_notional_usd: float
    recent_edge_ratio: float | None
    p7d_share: float | None
    top_categories: list[str]


def _compute_position_pnl(
    trades: list[dict],
    resolved_markets: dict[str, ResolvedMarket],
) -> list[tuple[str, float, float, int]]:
    """Group trades by condition_id and compute P&L per resolved position.

    Returns a list of (condition_id, notional_usd, pnl_usd, last_trade_ts)
    for positions that landed in a resolved market.

    Naive netting: for each (wallet, condition_id, asset) aggregate BUY and SELL
    trades. Final position = net_shares. Settled at the resolved outcome:
      YES token: pays 1.0 if outcome_yes_price == 1.0 (YES won), else 0.0
      NO token:  pays 1.0 if outcome_yes_price == 0.0 (NO won), else 0.0
    P&L = settle_value - net_cost.
    """
    # (condition_id, asset) -> {shares_net, cost_net, last_ts}
    positions: dict[tuple[str, str], dict] = {}
    for t in trades:
        cid = t.get("conditionId")
        asset = t.get("asset")
        if not cid or not asset:
            continue
        size = float(t.get("size") or 0)
        price = float(t.get("price") or 0)
        ts = int(t.get("timestamp") or 0)
        side = (t.get("side") or "").upper()
        key = (cid, asset)
        p = positions.setdefault(key, {"shares": 0.0, "cost": 0.0, "last_ts": 0, "notional": 0.0})
        if side == "BUY":
            p["shares"] += size
            p["cost"] += size * price
        elif side == "SELL":
            p["shares"] -= size
            p["cost"] -= size * price  # SELL reduces cost (proceeds received)
        p["notional"] += size * price
        p["last_ts"] = max(p["last_ts"], ts)

    results: list[tuple[str, float, float, int]] = []
    for (cid, _asset), p in positions.items():
        rm = resolved_markets.get(cid)
        if rm is None or rm.outcome_yes_price is None:
            continue
        shares_left = p["shares"]
        if abs(shares_left) < 1e-9:
            # Fully closed — P&L = -cost (cost is negative if net sold at profit)
            pnl = -p["cost"]
        else:
            # Settle remaining shares at outcome.
            # Determine if the asset is YES or NO token of this condition.
            # We match by token_id equality vs rm.yes_token_id / rm.no_token_id.
            asset = _asset
            if rm.yes_token_id and asset == rm.yes_token_id:
                settle = float(rm.outcome_yes_price)
            elif rm.no_token_id and asset == rm.no_token_id:
                settle = float(rm.outcome_no_price or 0)
            else:
                # Can't determine side — skip.
                continue
            pnl = settle * shares_left - p["cost"]
        results.append((cid, p["notional"], pnl, p["last_ts"]))
    return results


def _compute_metrics_from_closed_positions(
    wallet: str,
    pseudonym: str | None,
    positions: list[dict],
) -> WalletMetrics:
    """Metrics from Polymarket's /closed-positions endpoint (direct P&L).

    Each position has: avgPrice, totalBought, realizedPnl, curPrice, endDate,
    eventSlug. We just need to aggregate.

    KNOWN DATA LIMITATION (2026-04-16, verified):
    Polymarket's /closed-positions endpoint appears to return ONLY positions
    with realizedPnl > 0 — losing positions don't appear here (they're either
    in /positions as still-active or classified as abandoned). This inflates
    win_rate to ~1.0 for most wallets. profit_factor also degenerates to inf.
    Treat win_rate and profit_factor from this source as UPPER BOUNDS and
    use realised_pnl_usd + total_notional_usd + effective ROI as the primary
    signals. Phase 1 Mirror will collect true win/loss data by observing
    new positions forward in time against their resolution outcomes.
    """
    pnls: list[float] = []
    ts_list: list[int] = []
    by_category: dict[str, float] = defaultdict(float)
    total_notional = 0.0

    for p in positions:
        try:
            pnl = float(p.get("realizedPnl") or 0)
            bought = float(p.get("totalBought") or 0)
            ts = int(p.get("timestamp") or 0)
        except (TypeError, ValueError):
            continue
        pnls.append(pnl)
        ts_list.append(ts)
        total_notional += bought
        cat = (p.get("eventSlug") or "").lower()
        by_category[cat] += bought

    top_categories = [
        c for c, _ in sorted(by_category.items(), key=lambda x: -x[1])[:3] if c
    ]

    if not pnls:
        return WalletMetrics(
            wallet=wallet, pseudonym=pseudonym,
            trade_count=0, resolved_trade_count=0,
            win_rate=0.0, profit_factor=0.0, sharpe=0.0,
            realised_pnl_usd=0.0, total_notional_usd=0.0,
            recent_edge_ratio=None, p7d_share=None,
            top_categories=top_categories,
        )

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    total_pnl = sum(pnls)
    win_rate = len(wins) / len(pnls)
    if losses:
        profit_factor = sum(wins) / abs(sum(losses)) if sum(losses) != 0 else 0.0
    else:
        profit_factor = float("inf") if wins else 0.0
    mean = total_pnl / len(pnls)
    variance = sum((p - mean) ** 2 for p in pnls) / max(len(pnls) - 1, 1)
    std = math.sqrt(variance) if variance > 0 else 0.0
    sharpe = (mean / std) if std > 0 else 0.0

    # Recent-edge: trailing-30d vs trailing-6m median monthly P&L.
    now_ts = int(datetime.now(UTC).timestamp())
    window_30d = 30 * 86400
    window_7d = 7 * 86400
    window_6m = 180 * 86400
    recent_30d_pnls = [
        pnls[i] for i, ts in enumerate(ts_list) if ts > 0 and now_ts - ts <= window_30d
    ]
    recent_7d_pnls = [
        pnls[i] for i, ts in enumerate(ts_list) if ts > 0 and now_ts - ts <= window_7d
    ]
    # Monthly buckets for 6-month median.
    by_month: dict[str, float] = defaultdict(float)
    for i, ts in enumerate(ts_list):
        if ts <= 0 or now_ts - ts > window_6m:
            continue
        dt = datetime.fromtimestamp(ts, tz=UTC)
        key = f"{dt.year}-{dt.month:02d}"
        by_month[key] += pnls[i]
    monthly_pnls = sorted(by_month.values())
    median_month = median(monthly_pnls) if len(monthly_pnls) >= 2 else 0.0

    recent_edge_ratio: float | None = None
    p7d_share: float | None = None
    if median_month > 0:
        recent_30d = sum(recent_30d_pnls)
        recent_edge_ratio = recent_30d / median_month if median_month != 0 else 0.0
        recent_7d = sum(recent_7d_pnls)
        p7d_share = recent_7d / recent_30d if recent_30d > 0 else 0.0

    return WalletMetrics(
        wallet=wallet, pseudonym=pseudonym,
        trade_count=len(positions), resolved_trade_count=len(pnls),
        win_rate=win_rate, profit_factor=profit_factor, sharpe=sharpe,
        realised_pnl_usd=total_pnl, total_notional_usd=total_notional,
        recent_edge_ratio=recent_edge_ratio, p7d_share=p7d_share,
        top_categories=top_categories,
    )


def _compute_metrics(
    wallet: str,
    pseudonym: str | None,
    trades: list[dict],
    resolved_markets: dict[str, ResolvedMarket],
) -> WalletMetrics:
    pnl_records = _compute_position_pnl(trades, resolved_markets)

    # Categories — top-3 by notional.
    by_category: dict[str, float] = defaultdict(float)
    for t in trades:
        cat = (t.get("eventSlug") or t.get("category") or "").lower()
        by_category[cat] += float(t.get("size") or 0) * float(t.get("price") or 0)
    top_categories = [
        c for c, _ in sorted(by_category.items(), key=lambda x: -x[1])[:3] if c
    ]

    if not pnl_records:
        return WalletMetrics(
            wallet=wallet, pseudonym=pseudonym,
            trade_count=len(trades), resolved_trade_count=0,
            win_rate=0.0, profit_factor=0.0, sharpe=0.0,
            realised_pnl_usd=0.0, total_notional_usd=0.0,
            recent_edge_ratio=None, p7d_share=None,
            top_categories=top_categories,
        )

    pnls = [r[2] for r in pnl_records]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    total_pnl = sum(pnls)
    total_notional = sum(r[1] for r in pnl_records)
    win_rate = len(wins) / len(pnls)
    if losses:
        profit_factor = sum(wins) / abs(sum(losses)) if sum(losses) != 0 else 0.0
    else:
        profit_factor = float("inf") if wins else 0.0
    # Sharpe (per-trade): mean / std (no annualisation since we use per-trade scale)
    mean = total_pnl / len(pnls)
    variance = sum((p - mean) ** 2 for p in pnls) / max(len(pnls) - 1, 1)
    std = math.sqrt(variance) if variance > 0 else 0.0
    sharpe = (mean / std) if std > 0 else 0.0

    # Recent-edge ratio.
    now_ts = int(datetime.now(UTC).timestamp())
    window_30d = 30 * 86400
    window_7d = 7 * 86400
    recent_30d = [r[2] for r in pnl_records if now_ts - r[3] <= window_30d]
    recent_7d = [r[2] for r in pnl_records if now_ts - r[3] <= window_7d]

    # 6-month median monthly P&L — bucket resolved trades into calendar months.
    by_month: dict[str, float] = defaultdict(float)
    for _cid, _notional, pnl, ts in pnl_records:
        dt = datetime.fromtimestamp(ts, tz=UTC)
        # Only last 6 months.
        if (datetime.now(UTC) - dt).days > 180:
            continue
        key = f"{dt.year}-{dt.month:02d}"
        by_month[key] += pnl
    monthly_pnls = sorted(by_month.values())
    if len(monthly_pnls) >= 2:
        median_month = median(monthly_pnls)
    else:
        median_month = 0.0

    recent_edge_ratio: float | None = None
    p7d_share: float | None = None
    if median_month > 0:
        recent_30d_pnl = sum(recent_30d)
        recent_edge_ratio = recent_30d_pnl / median_month if median_month != 0 else 0.0
        recent_7d_pnl = sum(recent_7d)
        # 7d-vs-30d share: is the latest week pulling at least its fair share?
        p7d_share = recent_7d_pnl / recent_30d_pnl if recent_30d_pnl > 0 else 0.0

    return WalletMetrics(
        wallet=wallet, pseudonym=pseudonym,
        trade_count=len(trades), resolved_trade_count=len(pnl_records),
        win_rate=win_rate, profit_factor=profit_factor, sharpe=sharpe,
        realised_pnl_usd=total_pnl, total_notional_usd=total_notional,
        recent_edge_ratio=recent_edge_ratio, p7d_share=p7d_share,
        top_categories=top_categories,
    )


# --- Filters ---

def _passes_filters(m: WalletMetrics, source: str = "synthesised") -> tuple[bool, str]:
    """Apply Hunter filter gates.

    `source` indicates where the metrics came from:
      - "synthesised": from trades JOIN resolved_markets (loss-complete)
      - "closed_positions": from /closed-positions API (winner-biased)

    win_rate and profit_factor gates are DISABLED for winner-biased sources
    because they're upper bounds — applying the gate accepts nothing useful
    (everyone scores 1.0/inf) or rejects nothing (no signal). Audit fix
    2026-04-16. Effective-ROI ranking still produces a meaningful ordering.
    """
    if m.resolved_trade_count < HUNTER_MIN_TRADES:
        return False, f"min_trades {m.resolved_trade_count}<{HUNTER_MIN_TRADES}"
    if source != "closed_positions":
        if m.win_rate < HUNTER_MIN_WIN_RATE:
            return False, f"win_rate {m.win_rate:.3f}<{HUNTER_MIN_WIN_RATE}"
        if m.profit_factor < HUNTER_MIN_PROFIT_FACTOR:
            return False, f"profit_factor {m.profit_factor:.3f}<{HUNTER_MIN_PROFIT_FACTOR}"
    # Recent-edge check (skip if insufficient history to compute).
    if m.recent_edge_ratio is not None and m.recent_edge_ratio < HUNTER_RECENT_EDGE_RATIO:
        return False, f"recent_edge {m.recent_edge_ratio:.3f}<{HUNTER_RECENT_EDGE_RATIO}"
    # 7d share check (Grok addition). Skip if not computable.
    if m.p7d_share is not None and m.p7d_share < HUNTER_7D_MIN_SHARE:
        return False, f"p7d_share {m.p7d_share:.3f}<{HUNTER_7D_MIN_SHARE}"
    # Category blacklist (Bot F can't overlap Bot B's LLM thesis).
    for c in m.top_categories:
        for banned in HUNTER_CATEGORY_BLACKLIST:
            if banned and banned in c:
                return False, f"category blacklisted: {c}"
    return True, "ok"


# --- Main runner ---

@dataclass
class HunterResult:
    run_id: str
    scanned: int = 0
    filtered: int = 0
    ranked: list[WalletMetrics] = field(default_factory=list)
    rejections: list[tuple[str, str]] = field(default_factory=list)  # (wallet, reason)

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "wallets_scanned": self.scanned,
            "wallets_passed_filters": self.filtered,
            "wallets_in_top_N": len(self.ranked),
            "top_N": [
                {
                    "rank": i + 1,
                    "wallet": m.wallet[:12] + "..",
                    "pseudonym": m.pseudonym,
                    "trades": m.resolved_trade_count,
                    "win_rate": round(m.win_rate, 3),
                    "profit_factor": round(m.profit_factor, 2) if m.profit_factor != float("inf") else "inf",
                    "sharpe": round(m.sharpe, 3),
                    "realised_pnl": round(m.realised_pnl_usd, 0),
                    "total_notional": round(m.total_notional_usd, 0),
                    "effective_roi_pct": round(
                        100 * m.realised_pnl_usd / max(m.total_notional_usd, 1), 3
                    ),
                    "recent_edge_ratio": round(m.recent_edge_ratio, 2) if m.recent_edge_ratio else None,
                    "top_categories": m.top_categories,
                }
                for i, m in enumerate(self.ranked)
            ],
        }


def run_hunter(
    leaderboard_sample: int = HUNTER_LEADERBOARD_SAMPLE,
    trades_per_wallet: int = HUNTER_TRADES_PER_WALLET,
    top_n: int = HUNTER_TOP_N,
    db_path: Path | None = None,
    backtest_db_path: Path | None = None,
    max_wallets: int | None = None,
    apply_filters: bool = True,
) -> HunterResult:
    """Full Hunter pipeline: leaderboard → per-wallet metrics → filter → rank → persist."""
    run_id = datetime.now(UTC).strftime("hunter_%Y%m%d_%H%M%S")
    result = HunterResult(run_id=run_id)

    bt_sf = get_backtest_session_factory(backtest_db_path or DEFAULT_BACKTEST_DB)

    # Load resolved markets once for fast joins.
    with bt_sf() as s:
        resolved = list(s.scalars(select(ResolvedMarket)))
    resolved_by_cid: dict[str, ResolvedMarket] = {m.condition_id: m for m in resolved}
    log.info("hunter.loaded_resolved_markets count=%d", len(resolved_by_cid))

    with httpx.Client(
        timeout=20.0, headers={"User-Agent": "bot-f-hunter/0.1"},
    ) as client:
        # Merge profit + volume leaderboards for a broader sample.
        profit_lb = fetch_leaderboard(client, interval="all", metric="profit", limit=leaderboard_sample)
        volume_lb = fetch_leaderboard(client, interval="all", metric="volume", limit=leaderboard_sample)

        seen: dict[str, dict] = {}
        for w in profit_lb + volume_lb:
            wallet = w.get("proxyWallet")
            if wallet and wallet not in seen:
                seen[wallet] = w
        wallets = list(seen.values())
        if max_wallets:
            wallets = wallets[:max_wallets]

        log.info("hunter.leaderboard.loaded wallets=%d", len(wallets))

        for i, w in enumerate(wallets):
            wallet = w.get("proxyWallet")
            pseudonym = w.get("pseudonym")
            if not wallet:
                continue
            result.scanned += 1

            # Polite pacing on data-api.
            time.sleep(0.1)
            # Prefer /closed-positions (direct realisedPnl); falls back to
            # trades+resolved-markets synthesis if empty.
            closed = fetch_wallet_closed_positions(client, wallet, limit=trades_per_wallet)
            if closed:
                m = _compute_metrics_from_closed_positions(wallet, pseudonym, closed)
                source = "closed_positions"
            else:
                trades = fetch_wallet_trades(client, wallet, limit=trades_per_wallet)
                if not trades:
                    result.rejections.append((wallet, "no_data"))
                    continue
                m = _compute_metrics(wallet, pseudonym, trades, resolved_by_cid)
                source = "synthesised"
            if apply_filters:
                ok, reason = _passes_filters(m, source=source)
                if not ok:
                    result.rejections.append((wallet, reason))
                    continue
            result.filtered += 1
            result.ranked.append(m)

            if (i + 1) % 20 == 0:
                log.info(
                    "hunter.progress i=%d scanned=%d passed=%d",
                    i + 1, result.scanned, result.filtered,
                )

    # Rank by effective-ROI (realised_pnl / notional) + absolute P&L.
    # Sharpe/PF from /closed-positions is unreliable due to winner-bias in
    # the data source; effective ROI and absolute P&L survive the bias
    # (a wallet with $10M realised on $500M notional has a real 2% edge,
    # regardless of whether losses are omitted).
    def rank_key(m: WalletMetrics) -> tuple[float, float]:
        eff_roi = m.realised_pnl_usd / max(m.total_notional_usd, 1.0)
        return (eff_roi, m.realised_pnl_usd)

    result.ranked.sort(key=rank_key, reverse=True)
    result.ranked = result.ranked[:top_n]

    # Persist.
    sf = get_bot_f_session_factory(db_path)
    with sf() as s:
        now = datetime.now(UTC)
        for rank, m in enumerate(result.ranked, start=1):
            s.add(
                HunterRanking(
                    run_id=run_id,
                    rank=rank,
                    wallet=m.wallet,
                    pseudonym=m.pseudonym,
                    trade_count=m.resolved_trade_count,
                    win_rate=m.win_rate,
                    profit_factor=(
                        m.profit_factor
                        if m.profit_factor != float("inf")
                        else 999.0
                    ),
                    sharpe=m.sharpe,
                    realised_pnl_usd=m.realised_pnl_usd,
                    total_notional_usd=m.total_notional_usd,
                    recent_edge_ratio=m.recent_edge_ratio,
                    p7d_share=m.p7d_share,
                    top_categories=",".join(m.top_categories),
                    created_at=now,
                )
            )
        s.commit()
    log.info(
        "hunter.persisted run_id=%s ranked=%d rejected=%d",
        run_id, len(result.ranked), len(result.rejections),
    )
    return result
