"""Bot D weather backtest — replays the strategy against historical ensemble
forecasts and resolved Polymarket weather markets.

Data sources:
  - data/backtest.db resolved_markets   — for market text, outcome, yes_token_id, resolution time
  - data/backtest.db price_history      — for yes_price at a given timestamp
  - Open-Meteo ensemble-api             — historical 51-member ensemble forecasts (free, no key)

Strategy replayed:
  For each resolved weather market:
    1. Parse the question to extract city, date, temp_type, range (via bot_d_weather.discovery)
    2. Fetch the ensemble forecast (51 members) AS-OF the market's end_date (1 day ahead horizon)
    3. Compute model probability via Gaussian CDF on ensemble mean/std
    4. Pick yes_price at a decision moment ~24h before end_date
    5. Compute net edge after fees
    6. If |edge| > threshold, simulate entry at yes_price (BUY_YES if edge>0, else BUY_NO)
    7. Settle at resolution using market.outcome_yes_price

Limitations:
  - "Previous run" historical forecasts may not be available for all past dates.
    We use the ensemble-api with past start_date, which returns a reanalysis-style
    forecast valid at that date (not strictly the forecast-as-of-T).
  - No METAR adjustment in backtest (real-time feature only).
"""

from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

from bots.bot_d_weather.config import BOT_D_EDGE_THRESHOLD, BOT_D_BLACKLIST_EXACT_TEMP, CITIES, resolve_city
from bots.bot_d_weather.discovery import _parse_date, _c_to_f  # type: ignore
from bots.bot_d_weather.strategy import range_probability, _polymarket_taker_fee
from core.backtest_db import (
    DEFAULT_BACKTEST_DB,
    PriceHistory,
    ResolvedMarket,
    get_backtest_session_factory,
)

log = logging.getLogger(__name__)

OPEN_METEO_ENSEMBLE = "https://ensemble-api.open-meteo.com/v1/ensemble"


# --- Question parsing (simplified, based on bot_d_weather.discovery) ---

# Real Polymarket weather question formats (2026 sample):
#   "Will the highest temperature in Atlanta be 92°F or higher on April 15?"
#   "Will the highest temperature in New York City be 78°F or below on April 16?"
#   "Will the highest temperature in New York City be between 90-91°F on April 15?"
#   "Will the lowest temperature in Tokyo be 10°C or higher on April 18?"
RE_TEMP_BETWEEN = re.compile(
    r"(highest|lowest)\s+temperature\s+in\s+([a-zA-Z\s]+?)\s+be\s+"
    r"between\s+(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\s*°?([CF])"
    r"(?:\s+on\s+(.+?))?\??\s*$",
    re.IGNORECASE,
)
RE_TEMP_OR_BOUND = re.compile(
    r"(highest|lowest)\s+temperature\s+in\s+([a-zA-Z\s]+?)\s+be\s+"
    r"(\d+(?:\.\d+)?)\s*°?([CF])\s+or\s+(higher|lower|above|below|more|less)"
    r"(?:\s+on\s+(.+?))?\??\s*$",
    re.IGNORECASE,
)
RE_TEMP_DIR_BOUND = re.compile(
    r"(highest|lowest)\s+temperature\s+in\s+([a-zA-Z\s]+?)\s+be\s+"
    r"(above|below|at\s+least|at\s+most|over|under)\s+"
    r"(\d+(?:\.\d+)?)\s*°?([CF])"
    r"(?:\s+on\s+(.+?))?\??\s*$",
    re.IGNORECASE,
)
RE_TEMP_EXACT = re.compile(
    r"(highest|lowest)\s+temperature\s+in\s+([a-zA-Z\s]+?)\s+be\s+"
    r"(\d+(?:\.\d+)?)\s*°?([CF])(?:\s+on\s+(.+?))?\??\s*$",
    re.IGNORECASE,
)


@dataclass
class ParsedWeather:
    city: str
    date_iso: str
    temp_type: str      # "high" | "low"
    range_low_f: float | None
    range_high_f: float | None


def _parse_backtest_date(date_text: str | None, reference_year: int | None) -> str | None:
    """Parse a Polymarket date string without rolling past dates into next year."""
    if not date_text:
        return None
    text = date_text.strip().rstrip("?").strip()
    for fmt in ("%B %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    if reference_year is None:
        # Fall back to live parser behaviour only when the DB gives no year.
        return _parse_date(text)
    try:
        return datetime.strptime(f"{text} {reference_year}", "%B %d %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _normalize_bound(text: str) -> str | None:
    t = text.lower().replace("or ", "").strip()
    if t in ("higher", "above", "more", "at least", "over"):
        return "above"
    if t in ("lower", "below", "less", "at most", "under"):
        return "below"
    return None


def _parse_weather_question(
    question: str,
    *,
    reference_year: int | None = None,
) -> ParsedWeather | None:
    q = question.strip()
    m = RE_TEMP_BETWEEN.search(q)
    if m:
        temp_raw, city_raw, lo, hi, unit, date_raw = m.groups()
        city = resolve_city(city_raw)
        if city is None:
            return None
        date_iso = _parse_backtest_date(date_raw, reference_year)
        if date_iso is None:
            return None
        lo_f = float(lo) if unit.upper() == "F" else _c_to_f(float(lo))
        hi_f = float(hi) if unit.upper() == "F" else _c_to_f(float(hi))
        return ParsedWeather(
            city=city, date_iso=date_iso,
            temp_type="high" if "high" in temp_raw.lower() else "low",
            range_low_f=lo_f, range_high_f=hi_f,
        )

    m = RE_TEMP_OR_BOUND.search(q)
    if m:
        temp_raw, city_raw, val, unit, bound_raw, date_raw = m.groups()
        city = resolve_city(city_raw)
        if city is None:
            return None
        date_iso = _parse_backtest_date(date_raw, reference_year)
        if date_iso is None:
            return None
        val_f = float(val) if unit.upper() == "F" else _c_to_f(float(val))
        direction = _normalize_bound(bound_raw)
        if direction == "above":
            return ParsedWeather(
                city=city, date_iso=date_iso,
                temp_type="high" if "high" in temp_raw.lower() else "low",
                range_low_f=val_f, range_high_f=None,
            )
        if direction == "below":
            return ParsedWeather(
                city=city, date_iso=date_iso,
                temp_type="high" if "high" in temp_raw.lower() else "low",
                range_low_f=None, range_high_f=val_f,
            )
    m = RE_TEMP_DIR_BOUND.search(q)
    if m:
        temp_raw, city_raw, bound_raw, val, unit, date_raw = m.groups()
        city = resolve_city(city_raw)
        if city is None:
            return None
        date_iso = _parse_backtest_date(date_raw, reference_year)
        if date_iso is None:
            return None
        val_f = float(val) if unit.upper() == "F" else _c_to_f(float(val))
        direction = _normalize_bound(bound_raw)
        if direction == "above":
            return ParsedWeather(
                city=city, date_iso=date_iso,
                temp_type="high" if "high" in temp_raw.lower() else "low",
                range_low_f=val_f, range_high_f=None,
            )
        if direction == "below":
            return ParsedWeather(
                city=city, date_iso=date_iso,
                temp_type="high" if "high" in temp_raw.lower() else "low",
                range_low_f=None, range_high_f=val_f,
            )
    m = RE_TEMP_EXACT.search(q)
    if m:
        if BOT_D_BLACKLIST_EXACT_TEMP:
            return None
        temp_raw, city_raw, val, unit, date_raw = m.groups()
        city = resolve_city(city_raw)
        if city is None:
            return None
        date_iso = _parse_backtest_date(date_raw, reference_year)
        if date_iso is None:
            return None
        val_f = float(val)
        if unit.upper() == "C":
            lo_f = _c_to_f(val_f)
            hi_f = _c_to_f(val_f + 1.0)
        else:
            lo_f = val_f
            hi_f = val_f + 1.0
        return ParsedWeather(
            city=city,
            date_iso=date_iso,
            temp_type="high" if "high" in temp_raw.lower() else "low",
            range_low_f=lo_f,
            range_high_f=hi_f,
        )
    return None


# --- Ensemble forecast fetcher (historical) ---

@dataclass
class HistoricalForecast:
    mean_f: float
    std_f: float
    members: int


def fetch_historical_ensemble(
    client: httpx.Client,
    city: str,
    date_iso: str,
    temp_type: str,
) -> HistoricalForecast | None:
    """Fetch the 51-member ensemble forecast for a city on a past date."""
    cfg = CITIES.get(city)
    if cfg is None:
        return None
    var = "temperature_2m_max" if temp_type == "high" else "temperature_2m_min"
    params = {
        "latitude": cfg.lat,
        "longitude": cfg.lon,
        "start_date": date_iso,
        "end_date": date_iso,
        "daily": var,
        "models": "gfs_seamless",
        "timezone": "UTC",
    }
    try:
        r = client.get(OPEN_METEO_ENSEMBLE, params=params, timeout=15.0)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        log.debug("ensemble fetch failed %s %s: %s", city, date_iso, e)
        return None

    daily = data.get("daily") or {}
    # Collect member values.
    members_c: list[float] = []
    for k, v in daily.items():
        if k.startswith(var) and isinstance(v, list) and v:
            val = v[0]
            if val is not None:
                members_c.append(float(val))
    if len(members_c) < 3:
        return None
    # Convert C → F.
    members_f = [_c_to_f(c) for c in members_c]
    mean = sum(members_f) / len(members_f)
    variance = sum((x - mean) ** 2 for x in members_f) / len(members_f)
    std = math.sqrt(variance)
    return HistoricalForecast(mean_f=mean, std_f=std, members=len(members_f))


# --- Price lookup ---

def _price_at(session_factory, token_id: str, target_ts: int) -> float | None:
    """Find the yes_price nearest to target_ts (but not after)."""
    with session_factory() as s:
        row = s.execute(
            select(PriceHistory.price)
            .where(PriceHistory.token_id == token_id, PriceHistory.ts <= target_ts)
            .order_by(PriceHistory.ts.desc())
            .limit(1)
        ).first()
    return float(row[0]) if row else None


# --- Result dataclasses ---

@dataclass
class BotDTrade:
    condition_id: str
    question: str
    city: str
    date_iso: str
    temp_type: str
    entry_ts: int
    side: str                 # "BUY_YES" | "BUY_NO"
    entry_price: float
    size_usd: float
    exit_price: float
    pnl_usd: float
    model_prob: float
    market_prob: float
    net_edge: float
    exit_reason: str
    regime: str = "unclassified"
    wave_count: int = 1


@dataclass
class BotDResult:
    trades: list[BotDTrade] = field(default_factory=list)
    markets_evaluated: int = 0
    markets_parsed: int = 0
    markets_forecast_missing: int = 0
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
        by_regime: dict[str, int] = {}
        for t in self.trades:
            by_side[t.side] = by_side.get(t.side, 0) + 1
            by_regime[t.regime] = by_regime.get(t.regime, 0) + 1
        return {
            "markets_evaluated": self.markets_evaluated,
            "markets_parsed": self.markets_parsed,
            "markets_forecast_missing": self.markets_forecast_missing,
            "markets_price_missing": self.markets_price_missing,
            "markets_skipped_low_edge": self.markets_skipped_low_edge,
            "n_trades": len(self.trades),
            "total_pnl_usd": round(self.total_pnl, 2),
            "total_notional_usd": round(self.total_notional, 2),
            "roi_pct": round(100 * self.total_pnl / max(self.total_notional, 1e-9), 2),
            "win_rate": round(self.win_rate, 4),
            "sides": by_side,
            "regimes": by_regime,
            "avg_pnl_per_trade": round(self.total_pnl / max(len(self.trades), 1), 3),
        }


def run_bot_d_backtest(
    edge_threshold: float | None = None,
    entry_size_usd: float = 10.0,
    decision_hours_before: float = 24.0,
    db_path: Path | None = None,
    max_markets: int | None = None,
    one_bet_per_event: bool = True,
    wave_filter: bool = False,
    wave_min_markets: int = 3,
    isolated_size_factor: float = 0.50,
    require_wave: bool = False,
) -> BotDResult:
    """Replay Bot D against resolved weather markets in the backtest DB."""
    sf = get_backtest_session_factory(db_path or DEFAULT_BACKTEST_DB)
    threshold = edge_threshold if edge_threshold is not None else BOT_D_EDGE_THRESHOLD
    result = BotDResult()

    with sf() as s:
        markets = list(
            s.scalars(
                select(ResolvedMarket).where(
                    ResolvedMarket.yes_token_id.is_not(None),
                    ResolvedMarket.outcome_yes_price.is_not(None),
                )
            )
        )

    candidates: list[BotDTrade] = []

    with httpx.Client(timeout=15.0, headers={"User-Agent": "botd-backtest/0.1"}) as client:
        for m in markets:
            if max_markets and result.markets_evaluated >= max_markets:
                break
            result.markets_evaluated += 1

            end_date = m.end_date or m.closed_time
            if end_date is None:
                continue
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            parsed = _parse_weather_question(m.question, reference_year=end_date.year)
            if parsed is None:
                continue
            result.markets_parsed += 1

            # Throttle open-meteo: ~5 req/s.
            time.sleep(0.2)
            forecast = fetch_historical_ensemble(
                client, parsed.city, parsed.date_iso, parsed.temp_type
            )
            if forecast is None:
                result.markets_forecast_missing += 1
                continue

            # City RMSE adjustment (same as live strategy).
            city_cfg = CITIES.get(parsed.city)
            rmse = city_cfg.rmse_f if city_cfg else 2.5
            adjusted_std = math.sqrt(forecast.std_f ** 2 + rmse ** 2)

            model_prob = range_probability(
                mean=forecast.mean_f,
                std=adjusted_std,
                low=parsed.range_low_f,
                high=parsed.range_high_f,
            )
            model_prob = max(0.001, min(0.999, model_prob))

            # Decision time = 24h before end_date.
            decision_ts = int((end_date - timedelta(hours=decision_hours_before)).timestamp())

            yes_price = _price_at(sf, m.yes_token_id, decision_ts)
            if yes_price is None or yes_price <= 0 or yes_price >= 1:
                result.markets_price_missing += 1
                continue

            gross = model_prob - yes_price
            fee_rate = _polymarket_taker_fee(yes_price if gross > 0 else 1.0 - yes_price)
            net_edge = gross - fee_rate if gross > 0 else gross + fee_rate

            if abs(net_edge) < threshold:
                result.markets_skipped_low_edge += 1
                continue

            side = "BUY_YES" if net_edge > 0 else "BUY_NO"
            entry_px = yes_price if side == "BUY_YES" else (1.0 - yes_price)
            exit_px_yes = float(m.outcome_yes_price or 0)
            exit_px = exit_px_yes if side == "BUY_YES" else (1.0 - exit_px_yes)
            size_shares = entry_size_usd / entry_px if entry_px > 0 else 0.0
            pnl = (exit_px - entry_px) * size_shares

            candidates.append(
                BotDTrade(
                    condition_id=m.condition_id,
                    question=m.question,
                    city=parsed.city,
                    date_iso=parsed.date_iso,
                    temp_type=parsed.temp_type,
                    entry_ts=decision_ts,
                    side=side,
                    entry_price=entry_px,
                    size_usd=entry_size_usd,
                    exit_price=exit_px,
                    pnl_usd=pnl,
                    model_prob=model_prob,
                    market_prob=yes_price,
                    net_edge=net_edge,
                    exit_reason="resolution",
                )
            )

    trades = _select_backtest_trades(
        candidates,
        one_bet_per_event=one_bet_per_event,
        wave_filter=wave_filter,
        wave_min_markets=wave_min_markets,
        isolated_size_factor=isolated_size_factor,
        require_wave=require_wave,
    )
    result.trades.extend(trades)
    return result


def _select_backtest_trades(
    candidates: list[BotDTrade],
    *,
    one_bet_per_event: bool,
    wave_filter: bool,
    wave_min_markets: int,
    isolated_size_factor: float,
    require_wave: bool,
) -> list[BotDTrade]:
    trades = candidates
    if one_bet_per_event:
        best: dict[tuple[str, str, str], BotDTrade] = {}
        for t in trades:
            key = (t.city, t.date_iso, t.temp_type)
            if key not in best or abs(t.net_edge) > abs(best[key].net_edge):
                best[key] = t
        trades = list(best.values())

    if not wave_filter:
        return trades

    groups: dict[tuple[str, str, str], list[BotDTrade]] = {}
    for t in trades:
        groups.setdefault((t.date_iso, t.temp_type, t.side), []).append(t)

    selected: list[BotDTrade] = []
    for t in trades:
        count = len(groups.get((t.date_iso, t.temp_type, t.side), []))
        if count >= wave_min_markets:
            selected.append(replace(t, regime="wave", wave_count=count))
        elif not require_wave:
            selected.append(
                replace(
                    t,
                    size_usd=t.size_usd * isolated_size_factor,
                    pnl_usd=t.pnl_usd * isolated_size_factor,
                    regime="isolated",
                    wave_count=count,
                )
            )
    return selected
