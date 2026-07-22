"""Bot C backtest — replays the GBM strategy against historical Pyth prices
and resolved Polymarket crypto/commodity markets.

Data sources:
  - data/backtest.db resolved_markets   — markets + outcomes + yes_token_id
  - data/backtest.db price_history      — yes_price time series per token
  - Pyth Benchmarks API                 — historical minute-resolution spot prices

Strategy replayed:
  For each resolved crypto/commodity market:
    1. Parse the question using bots.bot_c_pyth.discovery.fetch_candidate_markets'
       regex patterns (we port _PATTERNS here)
    2. At decision_ts (24h before resolution by default), fetch Pyth spot at that
       timestamp and realized vol over a lookback window
    3. Compute GBM prob for the terminal/barrier question
    4. Compare to yes_price at decision_ts
    5. If net_edge > threshold, simulate entry; settle at resolution

Limitations:
  - Volatility estimation uses a rolling window of Pyth prices at 1h resolution
  - Drift uses ANNUALISED_DRIFT defaults (same as live)
  - Pyth data coverage depends on whether the symbol has a feed registered
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import httpx
from sqlalchemy import select

from bots.bot_c_pyth.discovery import parse_question
from bots.bot_c_pyth.strategy import (
    ANNUALISED_DRIFT,
    _polymarket_taker_fee,
    evaluate_market as strategy_evaluate_market,
    gbm_prob_above,
    gbm_prob_below,
    gbm_prob_between,
)
from core.backtest_db import (
    DEFAULT_BACKTEST_DB,
    PriceHistory,
    ResolvedMarket,
    get_backtest_session_factory,
)
from core.pyth_feeds import feed_by_symbol

log = logging.getLogger(__name__)

PYTH_BENCHMARKS = "https://benchmarks.pyth.network/v1/shims/tradingview/history"


def _pyth_symbol_for(symbol: str) -> str | None:
    """Map Bot C feed key → Pyth Benchmarks TradingView symbol."""
    feed = feed_by_symbol(symbol)
    if feed is None:
        return None
    cat = feed.category.lower() if feed.category else ""
    # Benchmarks API uses Crypto.BTC/USD, FX.EUR/USD, Equity.US.AAPL/USD, etc.
    if cat == "crypto":
        return f"Crypto.{symbol}/USD"
    if cat == "commodity":
        # Gold/Silver live under Metal.
        return f"Metal.{symbol}/USD"
    if cat in ("equity", "stock"):
        return f"Equity.US.{symbol}/USD"
    return None


def fetch_pyth_bars(
    client: httpx.Client,
    symbol: str,
    start_ts: int,
    end_ts: int,
    resolution: str = "60",  # 60-minute bars
) -> list[tuple[int, float]]:
    """Return [(ts, close_price)] over the window."""
    sym = _pyth_symbol_for(symbol)
    if sym is None:
        return []
    try:
        r = client.get(
            PYTH_BENCHMARKS,
            params={
                "symbol": sym, "resolution": resolution,
                "from": start_ts, "to": end_ts,
            },
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.debug("pyth fetch failed %s: %s", sym, e)
        return []
    if data.get("s") != "ok":
        return []
    ts_list = data.get("t") or []
    close = data.get("c") or []
    return [(int(ts_list[i]), float(close[i])) for i in range(min(len(ts_list), len(close)))]


def realized_vol_annualised(bars: list[tuple[int, float]]) -> float:
    """Compute annualised realized volatility from 1h bars."""
    if len(bars) < 5:
        return 0.3  # fallback
    rets: list[float] = []
    for (t1, p1), (t2, p2) in zip(bars[:-1], bars[1:]):
        if p1 > 0 and p2 > 0:
            rets.append(math.log(p2 / p1))
    if len(rets) < 2:
        return 0.3
    n = len(rets)
    mean = sum(rets) / n
    variance = sum((r - mean) ** 2 for r in rets) / max(n - 1, 1)
    hourly_std = math.sqrt(variance)
    # Annualise: 8760 hours per year.
    return hourly_std * math.sqrt(8760)


# --- Question parsing using Bot C's patterns ---

@dataclass
class ParsedCryptoMarket:
    symbol: str
    direction: str        # "above" | "below" | "between"
    strike_low: float | None
    strike_high: float | None
    resolution_date: datetime
    question_kind: str    # "terminal" | "barrier"


def _parse_crypto_market(question: str, end_date: datetime) -> ParsedCryptoMarket | None:
    """Delegate to Bot C's production parser; normalise to our dataclass."""
    parsed = parse_question(question)
    if parsed is None:
        return None
    try:
        strike_low = float(parsed["strike_low"]) if parsed.get("strike_low") is not None else None
        strike_high = float(parsed["strike_high"]) if parsed.get("strike_high") is not None else None
    except (TypeError, ValueError):
        return None
    # Prefer the gamma-reported end_date; fall back to parser's inferred date.
    res_date = end_date or parsed.get("resolution_date")
    if res_date is None:
        return None
    if res_date.tzinfo is None:
        res_date = res_date.replace(tzinfo=timezone.utc)
    return ParsedCryptoMarket(
        symbol=parsed["symbol"],
        direction=parsed["direction"],
        strike_low=strike_low,
        strike_high=strike_high,
        resolution_date=res_date,
        question_kind=parsed.get("question_kind", "terminal"),
    )


# --- Result dataclasses ---

@dataclass
class BotCTrade:
    condition_id: str
    question: str
    symbol: str
    direction: str
    strike_low: float | None
    strike_high: float | None
    entry_ts: int
    side: str                 # "BUY_YES" | "BUY_NO"
    entry_price: float
    size_usd: float
    exit_price: float
    pnl_usd: float
    model_prob: float
    market_prob: float
    net_edge: float
    spot_at_decision: float
    sigma_ann: float


@dataclass
class BotCResult:
    trades: list[BotCTrade] = field(default_factory=list)
    markets_evaluated: int = 0
    markets_parsed: int = 0
    markets_pyth_missing: int = 0
    markets_price_missing: int = 0
    markets_skipped_low_edge: int = 0

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl_usd for t in self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return sum(1 for t in self.trades if t.pnl_usd > 0) / len(self.trades)

    @property
    def total_notional(self) -> float:
        return sum(t.size_usd for t in self.trades)

    def summary(self) -> dict:
        by_side: dict[str, int] = {}
        by_symbol: dict[str, int] = {}
        for t in self.trades:
            by_side[t.side] = by_side.get(t.side, 0) + 1
            by_symbol[t.symbol] = by_symbol.get(t.symbol, 0) + 1
        return {
            "markets_evaluated": self.markets_evaluated,
            "markets_parsed": self.markets_parsed,
            "markets_pyth_missing": self.markets_pyth_missing,
            "markets_price_missing": self.markets_price_missing,
            "markets_skipped_low_edge": self.markets_skipped_low_edge,
            "n_trades": len(self.trades),
            "total_pnl_usd": round(self.total_pnl, 2),
            "total_notional_usd": round(self.total_notional, 2),
            "roi_pct": round(100 * self.total_pnl / max(self.total_notional, 1e-9), 2),
            "win_rate": round(self.win_rate, 4),
            "sides": by_side,
            "symbols": by_symbol,
            "avg_pnl_per_trade": round(self.total_pnl / max(len(self.trades), 1), 3),
        }


def _price_at(session_factory, token_id: str, target_ts: int) -> float | None:
    with session_factory() as s:
        row = s.execute(
            select(PriceHistory.price)
            .where(PriceHistory.token_id == token_id, PriceHistory.ts <= target_ts)
            .order_by(PriceHistory.ts.desc())
            .limit(1)
        ).first()
    return float(row[0]) if row else None


def run_bot_c_backtest(
    edge_threshold: float = 0.10,
    entry_size_usd: float = 10.0,
    decision_hours_before: float = 24.0,
    vol_lookback_days: int = 30,
    db_path: Path | None = None,
    max_markets: int | None = None,
) -> BotCResult:
    """Replay Bot C against resolved crypto/commodity markets in the backtest DB."""
    sf = get_backtest_session_factory(db_path or DEFAULT_BACKTEST_DB)
    result = BotCResult()

    with sf() as s:
        markets = list(
            s.scalars(
                select(ResolvedMarket).where(
                    ResolvedMarket.yes_token_id.is_not(None),
                    ResolvedMarket.outcome_yes_price.is_not(None),
                )
            )
        )

    with httpx.Client(timeout=15.0, headers={"User-Agent": "botc-backtest/0.1"}) as client:
        for m in markets:
            if max_markets and result.markets_evaluated >= max_markets:
                break
            result.markets_evaluated += 1

            end_date = m.end_date or m.closed_time
            if end_date is None:
                continue
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            parsed = _parse_crypto_market(m.question, end_date)
            if parsed is None:
                continue
            result.markets_parsed += 1

            decision_ts = int((end_date - timedelta(hours=decision_hours_before)).timestamp())
            vol_start_ts = decision_ts - vol_lookback_days * 86400

            # Throttle Pyth Benchmarks: ~5 req/sec.
            time.sleep(0.2)
            bars = fetch_pyth_bars(client, parsed.symbol, vol_start_ts, decision_ts)
            if not bars:
                result.markets_pyth_missing += 1
                continue

            spot_f = bars[-1][1]
            sigma_ann = realized_vol_annualised(bars)

            # Drift from feed category.
            feed = feed_by_symbol(parsed.symbol)
            category = feed.category if feed else "equity"
            drift = ANNUALISED_DRIFT.get(category, 0.0)

            dt = max((parsed.resolution_date - datetime.fromtimestamp(decision_ts, tz=timezone.utc)).total_seconds(), 0.0)
            t_years = dt / 31_557_600.0

            if parsed.direction == "above" and parsed.strike_low is not None:
                model_prob = gbm_prob_above(spot_f, parsed.strike_low, sigma_ann, t_years, drift)
            elif parsed.direction == "below" and parsed.strike_low is not None:
                model_prob = gbm_prob_below(spot_f, parsed.strike_low, sigma_ann, t_years, drift)
            elif parsed.direction == "between" and parsed.strike_low is not None and parsed.strike_high is not None:
                model_prob = gbm_prob_between(
                    spot_f, parsed.strike_low, parsed.strike_high, sigma_ann, t_years, drift,
                )
            else:
                continue
            model_prob = max(0.001, min(0.999, model_prob))

            yes_price = _price_at(sf, m.yes_token_id, decision_ts)
            if yes_price is None or yes_price <= 0 or yes_price >= 1:
                result.markets_price_missing += 1
                continue

            gross = model_prob - yes_price
            fee_rate = _polymarket_taker_fee(yes_price if gross > 0 else 1.0 - yes_price)
            net_edge = gross - fee_rate if gross > 0 else gross + fee_rate

            if abs(net_edge) < edge_threshold:
                result.markets_skipped_low_edge += 1
                continue

            side = "BUY_YES" if net_edge > 0 else "BUY_NO"
            entry_px = yes_price if side == "BUY_YES" else (1.0 - yes_price)
            exit_px_yes = float(m.outcome_yes_price or 0)
            exit_px = exit_px_yes if side == "BUY_YES" else (1.0 - exit_px_yes)
            size_shares = entry_size_usd / entry_px if entry_px > 0 else 0.0
            pnl = (exit_px - entry_px) * size_shares

            result.trades.append(
                BotCTrade(
                    condition_id=m.condition_id,
                    question=m.question,
                    symbol=parsed.symbol,
                    direction=parsed.direction,
                    strike_low=parsed.strike_low,
                    strike_high=parsed.strike_high,
                    entry_ts=decision_ts,
                    side=side,
                    entry_price=entry_px,
                    size_usd=entry_size_usd,
                    exit_price=exit_px,
                    pnl_usd=pnl,
                    model_prob=model_prob,
                    market_prob=yes_price,
                    net_edge=net_edge,
                    spot_at_decision=spot_f,
                    sigma_ann=sigma_ann,
                )
            )

    return result
