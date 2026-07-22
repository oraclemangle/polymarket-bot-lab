"""Pure model and signal helpers for crypto fair-value paper bots."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise


@dataclass(frozen=True)
class MarketMeta:
    condition_id: str
    question: str
    end_ms: int
    start_ms: int
    symbol: str
    duration_minutes: int
    yes_token_id: str
    no_token_id: str


@dataclass(frozen=True)
class CexState:
    symbol: str
    start_price: float
    current_price: float
    current_ts_ms: int
    realized_vol_tick: float
    move_60s: float


@dataclass(frozen=True)
class BookSide:
    token_id: str
    best_bid: Decimal
    best_ask: Decimal
    top_ask_size: Decimal
    ts_ms: int

    @property
    def top_depth_usd(self) -> Decimal:
        return self.best_ask * self.top_ask_size


@dataclass(frozen=True)
class BookState:
    yes: BookSide
    no: BookSide

    @property
    def effective_spread(self) -> Decimal:
        yes_spread = self.yes.best_ask - self.yes.best_bid
        no_spread = self.no.best_ask - self.no.best_bid
        binary_spread = self.yes.best_ask + self.no.best_ask - Decimal("1")
        return max(Decimal("0"), yes_spread, no_spread, binary_spread)


@dataclass(frozen=True)
class Signal:
    strategy: str
    condition_id: str
    symbol: str
    duration_minutes: int
    side: str
    token_id: str
    ask_price: Decimal
    model_probability_up: float
    model_edge: Decimal
    pm_mid_up: Decimal
    effective_spread: Decimal
    top_depth_usd: Decimal
    seconds_left: float
    decision_ms: int
    cex_move_60s: float

    @property
    def lead_bucket(self) -> str:
        if self.seconds_left < 45:
            return "<45s"
        if self.seconds_left < 120:
            return "45s-120s"
        if self.seconds_left < 300:
            return "120s-300s"
        return "300s+"

    @property
    def probability_bucket(self) -> str:
        p = self.model_probability_up if self.side == "UP" else 1.0 - self.model_probability_up
        lo = int(max(0, min(99, math.floor(p * 10) * 10)))
        return f"{lo:02d}-{lo + 10:02d}%"

    @property
    def ask_bucket(self) -> str:
        cents = int(self.ask_price * 100)
        lo = (cents // 5) * 5
        return f"{lo:02d}-{lo + 5:02d}c"


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def remaining_sigma(sampled_vol: float, seconds_left: float) -> float:
    return max(sampled_vol * math.sqrt(max(seconds_left, 1.0) / 10.0), 0.0002)


def probability_up(
    *,
    current: float,
    start: float,
    seconds_left: float,
    realized_vol_tick: float,
) -> float:
    if current <= 0 or start <= 0:
        return 0.5
    if seconds_left <= 0:
        return 1.0 if current >= start else 0.0
    z = math.log(current / start) / remaining_sigma(realized_vol_tick, seconds_left)
    return max(0.001, min(0.999, normal_cdf(z)))


def realized_vol_tick(prices: list[float]) -> float:
    if len(prices) < 3:
        return 0.0
    returns = [math.log(b / a) for a, b in pairwise(prices) if a > 0 and b > 0]
    if len(returns) < 2:
        return 0.0
    return statistics.stdev(returns)


def probability_gap_signal(
    *,
    meta: MarketMeta,
    book: BookState,
    cex: CexState,
    decision_ms: int,
    min_edge: Decimal,
    min_price: Decimal,
    max_price: Decimal,
) -> Signal | None:
    seconds_left = (meta.end_ms - decision_ms) / 1000.0
    p_up = probability_up(
        current=cex.current_price,
        start=cex.start_price,
        seconds_left=seconds_left,
        realized_vol_tick=cex.realized_vol_tick,
    )
    up_edge = Decimal(str(p_up)) - book.yes.best_ask
    down_edge = Decimal(str(1.0 - p_up)) - book.no.best_ask
    pm_mid_up = (book.yes.best_ask + (Decimal("1") - book.no.best_ask)) / Decimal("2")

    candidates: list[tuple[Decimal, str, BookSide]] = []
    if min_price <= book.yes.best_ask <= max_price and up_edge >= min_edge:
        candidates.append((up_edge, "UP", book.yes))
    if min_price <= book.no.best_ask <= max_price and down_edge >= min_edge:
        candidates.append((down_edge, "DOWN", book.no))
    if not candidates:
        return None
    edge, side, selected = max(candidates, key=lambda item: item[0])
    return Signal(
        strategy="probability_gap",
        condition_id=meta.condition_id,
        symbol=meta.symbol,
        duration_minutes=meta.duration_minutes,
        side=side,
        token_id=selected.token_id,
        ask_price=selected.best_ask,
        model_probability_up=p_up,
        model_edge=edge,
        pm_mid_up=pm_mid_up,
        effective_spread=book.effective_spread,
        top_depth_usd=selected.top_depth_usd,
        seconds_left=seconds_left,
        decision_ms=decision_ms,
        cex_move_60s=cex.move_60s,
    )


def brownian_fair_value_signal(
    *,
    meta: MarketMeta,
    book: BookState,
    cex: CexState,
    decision_ms: int,
    min_model_mid_gap: Decimal,
    min_entry_edge: Decimal,
    min_price: Decimal,
    max_price: Decimal,
) -> Signal | None:
    seconds_left = (meta.end_ms - decision_ms) / 1000.0
    p_up = probability_up(
        current=cex.current_price,
        start=cex.start_price,
        seconds_left=seconds_left,
        realized_vol_tick=cex.realized_vol_tick,
    )
    pm_mid_up = (book.yes.best_ask + (Decimal("1") - book.no.best_ask)) / Decimal("2")
    if abs(Decimal(str(p_up)) - pm_mid_up) < min_model_mid_gap:
        return None

    up_edge = Decimal(str(p_up)) - book.yes.best_ask
    down_edge = Decimal(str(1.0 - p_up)) - book.no.best_ask
    candidates: list[tuple[Decimal, str, BookSide]] = []
    if min_price <= book.yes.best_ask <= max_price and up_edge >= min_entry_edge:
        candidates.append((up_edge, "UP", book.yes))
    if min_price <= book.no.best_ask <= max_price and down_edge >= min_entry_edge:
        candidates.append((down_edge, "DOWN", book.no))
    if not candidates:
        return None
    edge, side, selected = max(candidates, key=lambda item: item[0])
    return Signal(
        strategy="brownian_fair_value",
        condition_id=meta.condition_id,
        symbol=meta.symbol,
        duration_minutes=meta.duration_minutes,
        side=side,
        token_id=selected.token_id,
        ask_price=selected.best_ask,
        model_probability_up=p_up,
        model_edge=edge,
        pm_mid_up=pm_mid_up,
        effective_spread=book.effective_spread,
        top_depth_usd=selected.top_depth_usd,
        seconds_left=seconds_left,
        decision_ms=decision_ms,
        cex_move_60s=cex.move_60s,
    )
