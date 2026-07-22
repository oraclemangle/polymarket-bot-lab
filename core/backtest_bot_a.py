"""Bot A backtest using historical Polymarket data from data/backtest.db.

Strategy replayed:
  For each resolved market in target categories with sufficient volume and
  days-to-resolution in [MIN, MAX]:
    - Walk its yes_price time series in chronological order
    - When yes_price <= MAX_YES_ENTRY_PRICE (0.05), simulate a NO-side entry
      at price (1 - yes_price), size = ENTRY_SIZE_USD / (1 - yes_price) shares
    - Hold to resolution OR cut loss if yes_price >= ABNORMAL_EXIT_YES_PRICE
      (exit at 1 - yes_price - 0.01 for fill safety)
    - If no cut-loss, settle at resolution: NO pays $1 if outcome is NO, else $0

Limitations (documented):
  - Uses mid-price from /prices-history as a proxy for the full orderbook.
    No spread modelling — assumes a 1c spread for entry math.
  - No depth / slippage modelling; assumes full fill at notional size.
  - Ignores MIN_24H_VOLUME_USD filter (backfill doesn't capture volume
    per-day; we use the aggregate volume_usd as a coarse filter).
  - One entry per market (no re-entry after cut-loss).

Output:
  SimResultBotA dataclass with per-trade records + aggregate metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from bots.bot_a.config import (
    ABNORMAL_EXIT_YES_PRICE,
    ENTRY_SIZE_USD,
    MAX_DAYS_TO_RESOLUTION,
    MAX_YES_ENTRY_PRICE,
    MIN_DAYS_TO_RESOLUTION,
    TARGET_CATEGORIES,
)
from core.backtest_db import (
    DEFAULT_BACKTEST_DB,
    PriceHistory,
    ResolvedMarket,
    get_backtest_session_factory,
)

log = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    condition_id: str
    question: str
    category: str | None
    entry_ts: int              # unix seconds
    entry_yes_price: float
    entry_no_price: float      # = 1 - yes
    size_shares: float
    notional_usd: float
    exit_ts: int | None
    exit_no_price: float | None
    exit_reason: str           # "resolution_won" | "resolution_lost" | "cut_loss"
    pnl_usd: float


@dataclass
class BacktestResult:
    trades: list[BacktestTrade] = field(default_factory=list)
    markets_evaluated: int = 0
    markets_entered: int = 0
    markets_skipped_price: int = 0    # no yes_price <= 0.05 in window
    markets_skipped_dates: int = 0    # failed MIN/MAX days-to-resolution
    markets_skipped_missing: int = 0  # no price history
    start: datetime | None = None
    end: datetime | None = None

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl_usd for t in self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.pnl_usd > 0)
        return wins / len(self.trades)

    @property
    def total_notional(self) -> float:
        return sum(t.notional_usd for t in self.trades)

    @property
    def roi_pct(self) -> float:
        if self.total_notional <= 0:
            return 0.0
        return 100.0 * self.total_pnl / self.total_notional

    def summary(self) -> dict:
        by_reason: dict[str, int] = {}
        for t in self.trades:
            by_reason[t.exit_reason] = by_reason.get(t.exit_reason, 0) + 1
        return {
            "markets_evaluated": self.markets_evaluated,
            "markets_entered": self.markets_entered,
            "markets_skipped_price": self.markets_skipped_price,
            "markets_skipped_dates": self.markets_skipped_dates,
            "markets_skipped_missing": self.markets_skipped_missing,
            "n_trades": len(self.trades),
            "total_pnl_usd": round(self.total_pnl, 2),
            "total_notional_usd": round(self.total_notional, 2),
            "roi_pct": round(self.roi_pct, 2),
            "win_rate": round(self.win_rate, 4),
            "exits": by_reason,
            "avg_pnl_per_trade": round(self.total_pnl / max(len(self.trades), 1), 2),
        }


def _load_yes_prices(
    session_factory, yes_token_id: str
) -> list[tuple[int, float]]:
    """Return [(ts, yes_price)] sorted by ts for a given YES token."""
    with session_factory() as s:
        rows = list(
            s.execute(
                select(PriceHistory.ts, PriceHistory.price)
                .where(PriceHistory.token_id == yes_token_id)
                .order_by(PriceHistory.ts)
            )
        )
    return [(int(r[0]), float(r[1])) for r in rows]


def _days_between(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 86400.0


def run_bot_a_backtest(
    start: datetime | None = None,
    end: datetime | None = None,
    entry_size_usd: Decimal | None = None,
    min_volume_usd: float = 500.0,
    db_path: Path | None = None,
    target_categories: set[str] | None = None,
) -> BacktestResult:
    """Replay Bot A against resolved markets in the backtest DB.

    Args:
      start/end: only consider markets with end_date in this range
      entry_size_usd: per-trade notional (defaults to Bot A's config)
      min_volume_usd: filter out low-volume markets (proxy for MIN_24H_VOLUME)
      db_path: optional override of BACKTEST_DB_PATH
      target_categories: which categories to consider (defaults to Bot A's)
    """
    sf = get_backtest_session_factory(db_path or DEFAULT_BACKTEST_DB)
    notional = float(entry_size_usd if entry_size_usd is not None else ENTRY_SIZE_USD)
    cats = target_categories or set(TARGET_CATEGORIES)

    result = BacktestResult(start=start, end=end)

    with sf() as s:
        stmt = select(ResolvedMarket)
        if start is not None:
            stmt = stmt.where(ResolvedMarket.end_date >= start)
        if end is not None:
            stmt = stmt.where(ResolvedMarket.end_date <= end)
        markets = list(s.scalars(stmt))

    for m in markets:
        result.markets_evaluated += 1
        if not m.yes_token_id or not m.no_token_id:
            continue
        if m.is_neg_risk:
            continue
        if m.category and m.category.lower() not in cats:
            continue
        if m.volume_usd is None or float(m.volume_usd) < min_volume_usd:
            continue
        if m.outcome_yes_price is None:
            continue

        yes_prices = _load_yes_prices(sf, m.yes_token_id)
        if not yes_prices:
            result.markets_skipped_missing += 1
            continue

        end_date = m.end_date or m.closed_time
        if end_date is None:
            continue
        # SQLite strips tzinfo on read — reattach UTC so arithmetic with
        # tz-aware datetimes works.
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        entered = False
        for ts, yes_px in yes_prices:
            t = datetime.fromtimestamp(ts, tz=timezone.utc)
            days_to_res = _days_between(t, end_date)
            if days_to_res < MIN_DAYS_TO_RESOLUTION or days_to_res > MAX_DAYS_TO_RESOLUTION:
                continue
            if yes_px > float(MAX_YES_ENTRY_PRICE):
                continue

            # Enter NO at (1 - yes_px).
            no_entry = 1.0 - yes_px
            size_shares = notional / no_entry
            entry_ts = ts
            entry_yes = yes_px

            # Walk forward looking for cut-loss OR resolution.
            exit_ts: int | None = None
            exit_no_price: float | None = None
            exit_reason = ""
            for ts2, yes_px2 in yes_prices:
                if ts2 <= entry_ts:
                    continue
                if yes_px2 >= float(ABNORMAL_EXIT_YES_PRICE):
                    # Cut loss: exit NO at (1 - yes_px2 - 0.01)
                    exit_ts = ts2
                    exit_no_price = max(0.0, 1.0 - yes_px2 - 0.01)
                    exit_reason = "cut_loss"
                    break
            if exit_ts is None:
                # Hold to resolution.
                exit_ts = int(end_date.timestamp())
                no_outcome = float(m.outcome_no_price or 0)
                exit_no_price = no_outcome
                exit_reason = "resolution_won" if no_outcome >= 0.99 else "resolution_lost"

            pnl_per_share = (exit_no_price or 0.0) - no_entry
            pnl_usd = pnl_per_share * size_shares

            result.trades.append(
                BacktestTrade(
                    condition_id=m.condition_id,
                    question=m.question,
                    category=m.category,
                    entry_ts=entry_ts,
                    entry_yes_price=entry_yes,
                    entry_no_price=no_entry,
                    size_shares=size_shares,
                    notional_usd=notional,
                    exit_ts=exit_ts,
                    exit_no_price=exit_no_price,
                    exit_reason=exit_reason,
                    pnl_usd=pnl_usd,
                )
            )
            result.markets_entered += 1
            entered = True
            break  # one entry per market

        if not entered:
            # Did any yes_price <= threshold exist? Skip-accounting.
            had_eligible = any(p <= float(MAX_YES_ENTRY_PRICE) for _, p in yes_prices)
            if not had_eligible:
                result.markets_skipped_price += 1
            else:
                result.markets_skipped_dates += 1

    return result
