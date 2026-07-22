#!/usr/bin/env python3
"""Phase B2 offline maker-side fillability simulator.

Read-only research script for OQ-083. It reconstructs recorder order books,
posts hypothetical maker SELL quotes on BTC/ETH/SOL 15-minute Up/Down markets,
and reports whether the cheap-tail maker edge survives conservative queue-ahead
fills, cancel-latency stress, quarantine windows, and adverse-selection checks.

This script does not place orders, write to the recorder DB, touch bot config,
restart services, or create a runtime package.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from itertools import pairwise
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_RECORDER_DB = Path("data/bot_e_recorder.db")
DEFAULT_OUT_MD = Path("docs/reports/maker-simulator-paper-2026-05-06.md")
DEFAULT_OUT_JSON = Path("docs/reports/maker-simulator-paper-2026-05-06.json")

QUOTE_SIZE = Decimal("5")
DEFAULT_TICK_SIZE = Decimal("0.001")
MIN_QUOTE_PRICE = Decimal("0.001")
MAX_QUOTE_PRICE = Decimal("0.999")
STALE_BOOK_SEC = 30
EXIT_LEAD_SEC = 30
RESOLUTION_WINDOW_MS = 300_000
NEW_QUOTE_LEAD_FLOOR_SEC = 60
LOW_TRADE_DENSITY_LOOKBACK_SEC = 300
MIN_PRIOR_TOKEN_TRADES = 5
TOXIC_TRAIN_START_MS = int(datetime(2025, 9, 1, tzinfo=UTC).timestamp() * 1000)
TOXIC_TRAIN_END_MS = int(datetime(2025, 12, 1, tzinfo=UTC).timestamp() * 1000)
KNOWN_SYMBOLS = ("BTC", "ETH", "SOL")
LADDERS = (
    "join_best_ask",
    "improve_best_ask_by_1_tick",
    "worse_than_best_ask_by_1_tick",
)


@dataclass(frozen=True)
class PriceBand:
    label: str
    lo: Decimal
    hi: Decimal

    def contains(self, price: Decimal) -> bool:
        return self.lo <= price < self.hi


@dataclass
class BookState:
    bids: dict[Decimal, Decimal] = field(default_factory=dict)
    asks: dict[Decimal, Decimal] = field(default_factory=dict)
    tick_size: Decimal = DEFAULT_TICK_SIZE
    valid: bool = False
    last_update_ms: int | None = None

    def copy(self) -> BookState:
        return BookState(
            bids=dict(self.bids),
            asks=dict(self.asks),
            tick_size=self.tick_size,
            valid=self.valid,
            last_update_ms=self.last_update_ms,
        )

    @property
    def best_bid(self) -> Decimal | None:
        return max(self.bids) if self.bids else None

    @property
    def best_ask(self) -> Decimal | None:
        return min(self.asks) if self.asks else None

    def ask_size_at(self, price: Decimal) -> Decimal:
        return self.asks.get(price, Decimal("0"))

    def bid_size_at(self, price: Decimal) -> Decimal:
        return self.bids.get(price, Decimal("0"))


@dataclass(frozen=True)
class MarketMeta:
    condition_id: str
    question: str
    symbol: str
    start_ms: int
    end_ms: int
    yes_token_id: str
    no_token_id: str


@dataclass(frozen=True)
class Resolution:
    winner_token_id: str | None
    path: str
    strict_winner_token_id: str | None = None
    baseline_winner_token_id: str | None = None
    inclusive_winner_token_id: str | None = None
    yes_close: float | None = None
    no_close: float | None = None


@dataclass(frozen=True)
class TradeEvent:
    ts_ms: int
    price: Decimal
    size: Decimal
    side: str
    taker_addr: str | None = None
    transaction_hash: str | None = None


@dataclass(frozen=True)
class ToxicTrainingFill:
    taker_addr: str
    lead_sec: float
    price: Decimal
    size: Decimal
    won: bool
    ts_ms: int | None = None


@dataclass(frozen=True)
class QuoteSpec:
    ladder: str
    condition_id: str
    symbol: str
    side: str
    token_id: str
    posted_at_ms: int
    end_ms: int
    quote_price: Decimal
    quote_size: Decimal
    queue_ahead_at_post: Decimal
    tick_size: Decimal
    cancel_intent_ms: int | None
    cancel_reason: str | None

    def active_until_ms(self, latency_ms: int) -> int:
        close_exit_ms = self.end_ms - EXIT_LEAD_SEC * 1000
        if self.cancel_intent_ms is None:
            return max(self.posted_at_ms, close_exit_ms)
        return min(max(self.posted_at_ms, close_exit_ms), self.cancel_intent_ms + latency_ms)


@dataclass
class FillResult:
    lower_fill_size: Decimal = Decimal("0")
    lower_fill_at_ms: int | None = None
    lower_fill_during_cancel: bool = False
    upper_fill_size: Decimal = Decimal("0")
    upper_fill_at_ms: int | None = None
    queue_consumed_by_trades: Decimal = Decimal("0")
    queue_consumed_by_cancels: Decimal = Decimal("0")
    taker_fill_sizes: dict[str, Decimal] = field(default_factory=dict)
    unknown_taker_fill_size: Decimal = Decimal("0")

    @property
    def lower_filled(self) -> bool:
        return self.lower_fill_size > 0

    @property
    def upper_filled(self) -> bool:
        return self.upper_fill_size > 0 or self.lower_filled


@dataclass
class QuoteOutcome:
    quote: QuoteSpec
    latency_ms: int
    won: bool | None
    resolution_path: str
    lower_fill_size: Decimal
    lower_fill_at_ms: int | None
    lower_fill_during_cancel: bool
    upper_fill_size: Decimal
    upper_fill_at_ms: int | None
    attempted_collateral_dollar_minutes: Decimal
    taker_fill_sizes: dict[str, Decimal] = field(default_factory=dict)
    unknown_taker_fill_size: Decimal = Decimal("0")

    @property
    def lower_filled(self) -> bool:
        return self.lower_fill_size > 0

    @property
    def upper_filled(self) -> bool:
        return self.upper_fill_size > 0 or self.lower_filled

    @property
    def pnl(self) -> Decimal:
        if self.won is None or not self.lower_filled:
            return Decimal("0")
        won_price = Decimal("1") if self.won else Decimal("0")
        return (self.quote.quote_price - won_price) * self.lower_fill_size

    @property
    def per_fill_collateral_roi(self) -> Decimal | None:
        if not self.lower_filled or self.won is None:
            return None
        collateral = (Decimal("1") - self.quote.quote_price) * self.lower_fill_size
        if collateral <= 0:
            return None
        return self.pnl / collateral

    def toxic_fill_size(self, toxic_wallets: set[str] | frozenset[str]) -> Decimal:
        if not toxic_wallets:
            return Decimal("0")
        return _sum_decimal(
            size for addr, size in self.taker_fill_sizes.items() if addr in toxic_wallets
        )

    def pnl_excluding_toxic(self, toxic_wallets: set[str] | frozenset[str]) -> Decimal:
        if self.won is None or not self.lower_filled:
            return Decimal("0")
        clean_fill_size = self.lower_fill_size - self.toxic_fill_size(toxic_wallets)
        if clean_fill_size <= 0:
            return Decimal("0")
        won_price = Decimal("1") if self.won else Decimal("0")
        return (self.quote.quote_price - won_price) * clean_fill_size


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--recorder-db", default=str(DEFAULT_RECORDER_DB))
    p.add_argument("--lookback-days", type=int, default=42)
    p.add_argument("--target-band", default="5.5-15c")
    p.add_argument("--target-lead-min-sec", type=int, default=300)
    p.add_argument("--target-lead-max-sec", type=int, default=600)
    p.add_argument("--cancel-latency-ms", default="200,300,500,1000")
    p.add_argument("--cex-cancel-bps-threshold", type=float, default=3.0)
    p.add_argument("--cex-cancel-window-sec", type=int, default=30)
    p.add_argument("--quote-size", type=str, default=str(QUOTE_SIZE))
    p.add_argument("--stale-book-sec", type=int, default=STALE_BOOK_SEC)
    p.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    p.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    p.add_argument("--label", default="the bot container")
    p.add_argument("--max-markets", type=int, default=None)
    return p.parse_args()


def connect_ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = ON")
    return con


def parse_iso_to_ms(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return None


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite():
        return None
    return d


def _norm_price(value: Any) -> Decimal | None:
    d = decimal_or_none(value)
    if d is None:
        return None
    return d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP).normalize()


def _norm_size(value: Any) -> Decimal | None:
    d = decimal_or_none(value)
    if d is None or d < 0:
        return None
    return d


def _levels(raw: Any) -> dict[Decimal, Decimal]:
    out: dict[Decimal, Decimal] = {}
    if not isinstance(raw, list):
        return out
    for row in raw:
        if isinstance(row, dict):
            price_raw = row.get("price")
            size_raw = row.get("size")
        elif isinstance(row, (list, tuple)) and len(row) >= 2:
            price_raw = row[0]
            size_raw = row[1]
        else:
            continue
        price = _norm_price(price_raw)
        size = _norm_size(size_raw)
        if price is None or size is None or size <= 0:
            continue
        out[price] = out.get(price, Decimal("0")) + size
    return out


def parse_book_snapshot(payload: dict[str, Any], *, received_at_ms: int | None = None) -> BookState:
    tick = decimal_or_none(payload.get("tick_size")) or DEFAULT_TICK_SIZE
    return BookState(
        bids=_levels(payload.get("bids")),
        asks=_levels(payload.get("asks")),
        tick_size=tick,
        valid=True,
        last_update_ms=received_at_ms,
    )


def apply_delta(
    state: BookState,
    payload: dict[str, Any],
    *,
    asset_id: str | None = None,
    received_at_ms: int | None = None,
) -> BookState:
    next_state = state.copy()
    changes = payload.get("price_changes")
    if not isinstance(changes, list):
        changes = [payload]
    for change in changes:
        if not isinstance(change, dict):
            continue
        change_asset = change.get("asset_id")
        if asset_id is not None and change_asset is not None and str(change_asset) != str(asset_id):
            continue
        price = _norm_price(change.get("price"))
        size = _norm_size(change.get("size"))
        side = str(change.get("side") or "").upper()
        if price is None or size is None:
            continue
        book_side = next_state.bids if side == "BUY" else next_state.asks if side == "SELL" else None
        if book_side is None:
            continue
        if size <= 0:
            book_side.pop(price, None)
        else:
            book_side[price] = size
    next_state.valid = True
    next_state.last_update_ms = received_at_ms
    return next_state


def invalidate_book(state: BookState, *, received_at_ms: int | None = None) -> BookState:
    return BookState(tick_size=state.tick_size, valid=False, last_update_ms=received_at_ms)


def is_book_fresh(state: BookState, at_ms: int, stale_book_sec: int) -> bool:
    return (
        state.valid
        and state.best_ask is not None
        and state.last_update_ms is not None
        and at_ms - state.last_update_ms <= stale_book_sec * 1000
    )


def parse_target_band(raw: str) -> PriceBand:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)c\s*", raw)
    if not match:
        raise ValueError(f"unsupported target band: {raw!r}")
    lo_c, hi_c = match.groups()
    return PriceBand(raw.strip(), Decimal(lo_c) / Decimal("100"), Decimal(hi_c) / Decimal("100"))


def price_band_label(price: Decimal) -> str:
    bands = [
        (Decimal("0"), Decimal("0.035"), "<3.5c"),
        (Decimal("0.035"), Decimal("0.055"), "3.5-5.5c"),
        (Decimal("0.055"), Decimal("0.08"), "5.5-8c"),
        (Decimal("0.08"), Decimal("0.10"), "8-10c"),
        (Decimal("0.10"), Decimal("0.15"), "10-15c"),
        (Decimal("0.15"), Decimal("0.20"), "15-20c"),
        (Decimal("0.20"), Decimal("0.30"), "20-30c"),
        (Decimal("0.30"), Decimal("0.50"), "30-50c"),
    ]
    for lo, hi, label in bands:
        if lo <= price < hi:
            return label
    return "50c+"


def lead_bucket(lead_sec: float) -> str:
    if lead_sec < 60:
        return "0-60s"
    if lead_sec < 300:
        return "60-300s"
    if lead_sec <= 600:
        return "300-600s"
    return "600s+"


def is_weekend_utc(ts_ms: int) -> bool:
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).weekday() >= 5


def should_skip_new_quote_for_final_window(
    *,
    end_ms: int,
    post_ms: int,
    floor_sec: int = NEW_QUOTE_LEAD_FLOOR_SEC,
) -> bool:
    return end_ms - post_ms < floor_sec * 1000


def prior_trade_count(
    trades: Iterable[TradeEvent],
    *,
    post_ms: int,
    lookback_sec: int = LOW_TRADE_DENSITY_LOOKBACK_SEC,
) -> int:
    start_ms = post_ms - lookback_sec * 1000
    return sum(1 for trade in trades if start_ms <= trade.ts_ms <= post_ms)


def low_trade_density_quarantine_ms(
    trade_times_ms: Iterable[int],
    *,
    start_ms: int,
    end_ms: int,
    min_trades: int = MIN_PRIOR_TOKEN_TRADES,
    lookback_sec: int = LOW_TRADE_DENSITY_LOOKBACK_SEC,
) -> int:
    if end_ms <= start_ms:
        return 0
    lookback_ms = lookback_sec * 1000
    trade_times = sorted(int(ts) for ts in trade_times_ms)
    breakpoints = {start_ms, end_ms}
    for ts in trade_times:
        if start_ms - lookback_ms <= ts <= end_ms:
            if start_ms <= ts <= end_ms:
                breakpoints.add(ts)
            expiry = ts + lookback_ms + 1
            if start_ms < expiry < end_ms:
                breakpoints.add(expiry)
    points = sorted(breakpoints)
    low_ms = 0
    for left, right in pairwise(points):
        if right <= left:
            continue
        probe = left
        count = sum(1 for ts in trade_times if probe - lookback_ms <= ts <= probe)
        if count < min_trades:
            low_ms += right - left
    return low_ms


def compute_queue_ahead(book: BookState, ladder: str) -> tuple[Decimal, Decimal] | None:
    best_ask = book.best_ask
    if best_ask is None:
        return None
    tick = book.tick_size or DEFAULT_TICK_SIZE
    if ladder == "join_best_ask":
        quote_price = best_ask
        queue_ahead = book.ask_size_at(best_ask)
    elif ladder == "improve_best_ask_by_1_tick":
        quote_price = best_ask - tick
        best_bid = book.best_bid
        if quote_price < MIN_QUOTE_PRICE or (best_bid is not None and quote_price <= best_bid):
            return None
        queue_ahead = Decimal("0")
    elif ladder == "worse_than_best_ask_by_1_tick":
        quote_price = best_ask + tick
        if quote_price > MAX_QUOTE_PRICE:
            return None
        queue_ahead = sum(size for price, size in book.asks.items() if price < quote_price)
    else:
        raise ValueError(f"unknown ladder {ladder!r}")
    return quote_price, queue_ahead


def buyer_aggressive(trade: TradeEvent, prior_best_ask: Decimal | None = None) -> bool:
    if trade.side.upper() == "BUY":
        return True
    return prior_best_ask is not None and trade.price >= prior_best_ask


def lower_bound_fill_count(
    trades: Iterable[TradeEvent],
    *,
    quote_price: Decimal,
    quote_size: Decimal,
    queue_ahead: Decimal,
    cancel_intent_ms: int | None = None,
    cancel_latency_ms: int = 0,
    active_from_ms: int | None = None,
    active_until_ms: int | None = None,
) -> FillResult:
    result = FillResult()
    queue_remaining = max(queue_ahead, Decimal("0"))
    fill_remaining = quote_size
    cancel_effective_ms = (
        cancel_intent_ms + cancel_latency_ms if cancel_intent_ms is not None else None
    )
    for trade in sorted(trades, key=lambda t: t.ts_ms):
        if active_from_ms is not None and trade.ts_ms < active_from_ms:
            continue
        if active_until_ms is not None and trade.ts_ms > active_until_ms:
            break
        if cancel_effective_ms is not None and trade.ts_ms > cancel_effective_ms:
            break
        if trade.price < quote_price or not buyer_aggressive(trade):
            continue
        size_left = trade.size
        if queue_remaining > 0:
            consumed = min(queue_remaining, size_left)
            queue_remaining -= consumed
            size_left -= consumed
            result.queue_consumed_by_trades += consumed
        if size_left <= 0:
            continue
        fill = min(fill_remaining, size_left)
        if fill <= 0:
            continue
        result.lower_fill_size += fill
        fill_remaining -= fill
        if trade.taker_addr:
            result.taker_fill_sizes[trade.taker_addr] = (
                result.taker_fill_sizes.get(trade.taker_addr, Decimal("0")) + fill
            )
        else:
            result.unknown_taker_fill_size += fill
        if result.lower_fill_at_ms is None:
            result.lower_fill_at_ms = trade.ts_ms
            if cancel_intent_ms is not None and trade.ts_ms >= cancel_intent_ms:
                result.lower_fill_during_cancel = True
        if fill_remaining <= 0:
            break
    return result


def cancel_latency_filter(
    trades: Iterable[TradeEvent],
    *,
    cancel_intent_ms: int,
    cancel_latency_ms: int,
) -> list[TradeEvent]:
    cancel_effective_ms = cancel_intent_ms + cancel_latency_ms
    return [t for t in trades if cancel_intent_ms <= t.ts_ms <= cancel_effective_ms]


def _extract_taker_addr(payload: dict[str, Any]) -> str | None:
    for key in (
        "taker_addr",
        "taker",
        "takerAddress",
        "taker_address",
        "buyer",
        "buyer_addr",
        "proxy_wallet",
        "proxyWallet",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None


def _wilson(wins: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return centre - margin, centre + margin


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
            if v is None:
                cells.append("")
            elif fmt == "int":
                cells.append(f"{int(v):,}")
            elif fmt == "pct":
                cells.append(f"{float(v):.2f}%")
            elif fmt == "roi":
                cells.append(f"{float(v) * 100:.2f}%")
            elif fmt == "price":
                cells.append(f"{float(v):.4f}")
            else:
                cells.append(str(v))
        body.append("| " + " | ".join(cells) + " |")
    return "\n".join([header, align, *body])


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in con.execute(f"PRAGMA table_info({table})")}


def _has_table(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _first_col(cols: set[str], names: tuple[str, ...]) -> str | None:
    for name in names:
        if name in cols:
            return name
    return None


def detect_toxic_wallets(
    fills: Iterable[ToxicTrainingFill],
    *,
    min_last_60s_fills: int = 30,
    min_last_60s_win_rate: float = 0.65,
    min_last_60s_pnl_usd: Decimal = Decimal("1000"),
) -> tuple[set[str], list[dict[str, Any]]]:
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "last_60s_fills": 0,
            "last_60s_wins": 0,
            "last_60s_pnl_usd": Decimal("0"),
            "total_lookback_volume_usd": Decimal("0"),
        }
    )
    for fill in fills:
        taker = fill.taker_addr.lower()
        notional = fill.price * fill.size
        stats[taker]["total_lookback_volume_usd"] += notional
        if fill.lead_sec > NEW_QUOTE_LEAD_FLOOR_SEC:
            continue
        stats[taker]["last_60s_fills"] += 1
        if fill.won:
            stats[taker]["last_60s_wins"] += 1
        won_price = Decimal("1") if fill.won else Decimal("0")
        stats[taker]["last_60s_pnl_usd"] += fill.size * (won_price - fill.price)

    toxic: set[str] = set()
    rows: list[dict[str, Any]] = []
    for taker, row in stats.items():
        last_60s_fills = int(row["last_60s_fills"])
        win_rate = (
            row["last_60s_wins"] / last_60s_fills if last_60s_fills else None
        )
        is_toxic = (
            last_60s_fills >= min_last_60s_fills
            and win_rate is not None
            and win_rate >= min_last_60s_win_rate
            and row["last_60s_pnl_usd"] >= min_last_60s_pnl_usd
        )
        if is_toxic:
            toxic.add(taker)
        rows.append({
            "taker_addr": taker,
            "last_60s_fills": last_60s_fills,
            "last_60s_win_rate": float(win_rate) if win_rate is not None else None,
            "last_60s_pnl_usd": float(row["last_60s_pnl_usd"]),
            "total_lookback_volume_usd": float(row["total_lookback_volume_usd"]),
            "toxic": is_toxic,
        })
    rows.sort(key=lambda r: (not r["toxic"], -int(r["last_60s_fills"]), r["taker_addr"]))
    return toxic, rows


def load_toxic_wallets(con: sqlite3.Connection) -> tuple[set[str], dict[str, Any]]:
    if not _has_table(con, "fill_events"):
        return set(), {
            "source": "fill_events table not present",
            "available": False,
            "toxic_wallet_count": 0,
            "training_wallet_rows": 0,
        }
    cols = _columns(con, "fill_events")
    taker_col = _first_col(cols, ("taker_addr", "taker", "taker_address", "takerAddress"))
    lead_col = _first_col(cols, ("lead_sec", "lead_seconds"))
    price_col = _first_col(cols, ("price", "fill_price"))
    size_col = _first_col(cols, ("shares", "size", "fill_size"))
    won_col = _first_col(cols, ("won", "token_won"))
    ts_col = _first_col(cols, ("fill_ts_ms", "ts_ms", "timestamp_ms", "received_at_ms"))
    required = {
        "taker": taker_col,
        "lead_sec": lead_col,
        "price": price_col,
        "size": size_col,
        "won": won_col,
    }
    missing = [name for name, col in required.items() if col is None]
    if missing:
        return set(), {
            "source": "fill_events table missing required columns",
            "available": False,
            "missing_columns": missing,
            "toxic_wallet_count": 0,
            "training_wallet_rows": 0,
        }

    where = ""
    params: tuple[Any, ...] = ()
    if ts_col:
        where = f"WHERE {ts_col} >= ? AND {ts_col} < ?"
        params = (TOXIC_TRAIN_START_MS, TOXIC_TRAIN_END_MS)
    rows = con.execute(
        f"""
        SELECT {taker_col} AS taker_addr,
               {lead_col} AS lead_sec,
               {price_col} AS price,
               {size_col} AS size,
               {won_col} AS won
        FROM fill_events
        {where}
        """,
        params,
    ).fetchall()
    fills: list[ToxicTrainingFill] = []
    for row in rows:
        taker = row["taker_addr"]
        price = decimal_or_none(row["price"])
        size = decimal_or_none(row["size"])
        lead = row["lead_sec"]
        if not taker or price is None or size is None or lead is None:
            continue
        fills.append(ToxicTrainingFill(
            taker_addr=str(taker),
            lead_sec=float(lead),
            price=price,
            size=size,
            won=bool(row["won"]),
        ))
    toxic, wallet_rows = detect_toxic_wallets(fills)
    return toxic, {
        "source": "fill_events",
        "available": True,
        "train_start_ms": TOXIC_TRAIN_START_MS,
        "train_end_ms": TOXIC_TRAIN_END_MS,
        "training_fill_rows": len(fills),
        "training_wallet_rows": len(wallet_rows),
        "toxic_wallet_count": len(toxic),
        "top_wallets": wallet_rows[:25],
    }


def _extract_symbol(question: str) -> str | None:
    q = (question or "").upper()
    for sym, needles in (
        ("BTC", ("BTC", "BITCOIN")),
        ("ETH", ("ETH", "ETHEREUM")),
        ("SOL", ("SOL", "SOLANA")),
    ):
        if any(n in q for n in needles):
            return sym
    return None


_QUESTION_RANGE_PATTERN = re.compile(
    r"(?P<h1>\d{1,2}):(?P<m1>\d{2})\s*(?P<ap1>AM|PM)?\s*-\s*"
    r"(?P<h2>\d{1,2}):(?P<m2>\d{2})\s*(?P<ap2>AM|PM)",
    re.IGNORECASE,
)
_MINUTE_LABEL_PATTERN = re.compile(r"\b(?P<minutes>5|15)\s*min(?:ute)?s?\b", re.IGNORECASE)


def _infer_duration_minutes(question: str) -> int | None:
    label = _MINUTE_LABEL_PATTERN.search(question or "")
    if label:
        return int(label.group("minutes"))
    match = _QUESTION_RANGE_PATTERN.search(question or "")
    if not match:
        return None

    def to_minutes(hour_s: str, minute_s: str, ampm: str | None) -> int:
        hour = int(hour_s)
        minute = int(minute_s)
        if ampm:
            ap = ampm.upper()
            if ap == "PM" and hour != 12:
                hour += 12
            elif ap == "AM" and hour == 12:
                hour = 0
        return hour * 60 + minute

    ap1 = match.group("ap1") or match.group("ap2")
    start = to_minutes(match.group("h1"), match.group("m1"), ap1)
    end = to_minutes(match.group("h2"), match.group("m2"), match.group("ap2"))
    if end < start:
        end += 24 * 60
    duration = end - start
    return duration if duration in (5, 15) else None


def build_candidate_markets(
    con: sqlite3.Connection,
    *,
    lookback_days: int,
    max_markets: int | None = None,
) -> list[MarketMeta]:
    cols = _columns(con, "markets")
    symbol_expr = "symbol" if "symbol" in cols else "NULL AS symbol"
    duration_expr = "duration_minutes" if "duration_minutes" in cols else "NULL AS duration_minutes"
    cutoff_ms = int((datetime.now(UTC) - timedelta(days=lookback_days)).timestamp() * 1000)
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    rows = con.execute(
        f"""
        SELECT condition_id, question, end_date_iso, yes_token_id, no_token_id,
               {symbol_expr}, {duration_expr}, MAX(scan_at_ms) AS latest_scan_at_ms
        FROM markets
        WHERE end_date_iso IS NOT NULL
          AND yes_token_id IS NOT NULL
          AND no_token_id IS NOT NULL
        GROUP BY condition_id
        ORDER BY end_date_iso
        """
    ).fetchall()
    markets: list[MarketMeta] = []
    for row in rows:
        end_ms = parse_iso_to_ms(row["end_date_iso"])
        if end_ms is None or end_ms < cutoff_ms or end_ms >= now_ms - 30_000:
            continue
        question = str(row["question"] or "")
        symbol = row["symbol"] or _extract_symbol(question)
        duration = row["duration_minutes"] or _infer_duration_minutes(question)
        if symbol not in KNOWN_SYMBOLS or int(duration or 0) != 15:
            continue
        markets.append(MarketMeta(
            condition_id=str(row["condition_id"]),
            question=question,
            symbol=str(symbol),
            start_ms=end_ms - 15 * 60 * 1000,
            end_ms=end_ms,
            yes_token_id=str(row["yes_token_id"]),
            no_token_id=str(row["no_token_id"]),
        ))
        if max_markets is not None and len(markets) >= max_markets:
            break
    return markets


def _last_trade_price(
    con: sqlite3.Connection,
    token_id: str,
    start_ms: int,
    end_ms: int,
) -> float | None:
    row = con.execute(
        """
        SELECT payload_json
        FROM pm_events
        WHERE asset_id = ?
          AND event_type = 'last_trade_price'
          AND received_at_ms BETWEEN ? AND ?
        ORDER BY received_at_ms DESC
        LIMIT 1
        """,
        (token_id, start_ms, end_ms),
    ).fetchone()
    if row is None:
        return None
    try:
        return float(json.loads(row["payload_json"]).get("price"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _threshold_winner(
    yes_token_id: str,
    no_token_id: str,
    yes_price: float | None,
    no_price: float | None,
    *,
    winner_threshold: float,
    loser_threshold: float,
) -> str | None:
    yes_win = yes_price is not None and yes_price >= winner_threshold
    no_win = no_price is not None and no_price >= winner_threshold
    yes_lose = yes_price is not None and yes_price <= loser_threshold
    no_lose = no_price is not None and no_price <= loser_threshold
    if yes_win and no_lose and not no_win:
        return yes_token_id
    if no_win and yes_lose and not yes_win:
        return no_token_id
    if yes_win and no_price is None:
        return yes_token_id
    if no_win and yes_price is None:
        return no_token_id
    if yes_lose and no_price is None:
        return no_token_id
    if no_lose and yes_price is None:
        return yes_token_id
    return None


def resolve_market(con: sqlite3.Connection, market: MarketMeta) -> Resolution:
    row = con.execute(
        """
        SELECT payload_json
        FROM pm_events
        WHERE event_type = 'market_resolved'
          AND (condition_id = ? OR payload_json LIKE ?)
        ORDER BY received_at_ms DESC
        LIMIT 1
        """,
        (market.condition_id, f"%{market.condition_id}%"),
    ).fetchone()
    if row is not None:
        try:
            payload = json.loads(row["payload_json"])
            winner = payload.get("winning_asset_id") or payload.get("winningAssetId")
            if winner:
                return Resolution(str(winner), "market_resolved")
        except json.JSONDecodeError:
            pass

    yes_close = _last_trade_price(
        con,
        market.yes_token_id,
        market.end_ms - RESOLUTION_WINDOW_MS,
        market.end_ms + RESOLUTION_WINDOW_MS,
    )
    no_close = _last_trade_price(
        con,
        market.no_token_id,
        market.end_ms - RESOLUTION_WINDOW_MS,
        market.end_ms + RESOLUTION_WINDOW_MS,
    )
    strict = _threshold_winner(
        market.yes_token_id,
        market.no_token_id,
        yes_close,
        no_close,
        winner_threshold=0.98,
        loser_threshold=0.02,
    )
    baseline = _threshold_winner(
        market.yes_token_id,
        market.no_token_id,
        yes_close,
        no_close,
        winner_threshold=0.95,
        loser_threshold=0.05,
    )
    inclusive = _threshold_winner(
        market.yes_token_id,
        market.no_token_id,
        yes_close,
        no_close,
        winner_threshold=0.90,
        loser_threshold=0.10,
    )
    return Resolution(
        baseline,
        "price_threshold_baseline" if baseline else "unresolved",
        strict_winner_token_id=strict,
        baseline_winner_token_id=baseline,
        inclusive_winner_token_id=inclusive,
        yes_close=yes_close,
        no_close=no_close,
    )


def _cex_symbol(symbol: str) -> str:
    return f"{symbol}USDT"


def first_adverse_cex_signal(
    con: sqlite3.Connection,
    *,
    symbol: str,
    side: str,
    start_ms: int,
    end_ms: int,
    window_sec: int,
    threshold_bps: Decimal,
) -> int | None:
    rows = con.execute(
        """
        SELECT trade_time_ms, price
        FROM cex_trades
        WHERE symbol = ?
          AND trade_time_ms BETWEEN ? AND ?
        ORDER BY trade_time_ms
        """,
        (_cex_symbol(symbol), start_ms - window_sec * 1000, end_ms),
    ).fetchall()
    window: deque[tuple[int, Decimal]] = deque()
    threshold = threshold_bps
    for row in rows:
        ts = int(row["trade_time_ms"])
        price = decimal_or_none(row["price"])
        if price is None or price <= 0:
            continue
        window.append((ts, price))
        while window and window[0][0] < ts - window_sec * 1000:
            window.popleft()
        if ts < start_ms or not window:
            continue
        ref_price = window[0][1]
        if ref_price <= 0:
            continue
        move_bps = (price / ref_price - Decimal("1")) * Decimal("10000")
        if side == "UP" and move_bps >= threshold:
            return ts
        if side == "DOWN" and move_bps <= -threshold:
            return ts
    return None


def _event_rows_for_market(
    con: sqlite3.Connection,
    market: MarketMeta,
    *,
    start_ms: int,
    end_ms: int,
) -> list[sqlite3.Row]:
    sub_id = _subscription_id_for_market(market)
    rows = con.execute(
        """
        SELECT received_at_ms, asset_id, condition_id, event_type, payload_json
        FROM pm_events
        WHERE subscription_id = ?
          AND received_at_ms BETWEEN ? AND ?
        ORDER BY received_at_ms, id
        """,
        (sub_id, start_ms, end_ms),
    ).fetchall()
    if rows:
        return rows
    return con.execute(
        """
        SELECT received_at_ms, asset_id, condition_id, event_type, payload_json
        FROM pm_events
        WHERE (
            asset_id IN (?, ?, ?)
            OR condition_id = ?
            OR subscription_id = ?
        )
          AND received_at_ms BETWEEN ? AND ?
        ORDER BY received_at_ms, id
        """,
        (
            market.yes_token_id,
            market.no_token_id,
            market.condition_id,
            market.condition_id,
            sub_id,
            start_ms,
            end_ms,
        ),
    ).fetchall()


def _gap_ranges_for_market(
    con: sqlite3.Connection,
    market: MarketMeta,
    start_ms: int,
    end_ms: int,
) -> list[tuple[int, int]]:
    sub_id = _subscription_id_for_market(market)
    try:
        rows = con.execute(
            """
            SELECT gap_start_ms, gap_end_ms
            FROM gaps
            WHERE gap_end_ms >= ?
              AND gap_start_ms <= ?
              AND (subscription_id IS NULL OR subscription_id = ?)
            """,
            (start_ms, end_ms, sub_id),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [
        (max(start_ms, int(row["gap_start_ms"])), min(end_ms, int(row["gap_end_ms"])))
        for row in rows
    ]


def _subscription_id_for_market(market: MarketMeta) -> str:
    end = datetime.fromtimestamp(market.end_ms / 1000, tz=UTC)
    return f"{market.symbol.lower()}-{end.strftime('%Y%m%dT%H%M')}"


def _overlap_ms(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def _ms_to_iso(ts_ms: int | None) -> str | None:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=UTC).isoformat()


def simulate_market(
    con: sqlite3.Connection,
    market: MarketMeta,
    resolution: Resolution,
    *,
    target_band: PriceBand,
    min_lead_sec: int,
    max_lead_sec: int,
    cancel_latency_ms_values: list[int],
    cancel_bps_threshold: Decimal,
    cancel_window_sec: int,
    quote_size: Decimal,
    stale_book_sec: int,
) -> tuple[list[QuoteOutcome], dict[str, Any]]:
    entry_ms = market.end_ms - max_lead_sec * 1000
    min_window_ms = market.end_ms - min_lead_sec * 1000
    event_start_ms = max(
        market.start_ms,
        entry_ms - max(stale_book_sec, LOW_TRADE_DENSITY_LOOKBACK_SEC) * 1000,
    )
    event_end_ms = market.end_ms + RESOLUTION_WINDOW_MS
    rows = _event_rows_for_market(con, market, start_ms=event_start_ms, end_ms=event_end_ms)
    gap_ranges = _gap_ranges_for_market(con, market, entry_ms, min_window_ms)
    token_sides = {
        market.yes_token_id: "UP",
        market.no_token_id: "DOWN",
    }
    books: dict[str, BookState] = {
        market.yes_token_id: BookState(),
        market.no_token_id: BookState(),
    }
    quotes: dict[tuple[str, str], QuoteSpec] = {}
    trades_by_token: dict[str, list[TradeEvent]] = defaultdict(list)
    upper_seen: dict[tuple[str, str], FillResult] = {}
    quarantine_reason_ms: dict[str, int] = defaultdict(int)
    stats = {
        "condition_id": market.condition_id,
        "symbol": market.symbol,
        "question": market.question,
        "entry_iso": _ms_to_iso(entry_ms),
        "end_iso": _ms_to_iso(market.end_ms),
        "quotes_posted": 0,
        "quotes_skipped_no_fresh_book": 0,
        "quotes_skipped_outside_band": 0,
        "quotes_skipped_invalid_ladder": 0,
        "quotes_skipped_final_60s": 0,
        "quotes_skipped_low_trade_density": 0,
        "quarantine_ms": 0,
        "candidate_window_ms": max(0, (min_window_ms - entry_ms) * 2),
        "gap_quarantine_ms": sum(_overlap_ms(s, e, entry_ms, min_window_ms) for s, e in gap_ranges) * 2,
        "low_trade_density_quarantine_ms": 0,
        "final_60s_quarantine_ms": 0,
        "tick_size_changes": 0,
        "reconnects": 0,
    }

    last_ts_by_token: dict[str, int] = {market.yes_token_id: entry_ms, market.no_token_id: entry_ms}

    def accrue_stale(token_id: str, to_ms: int) -> None:
        last_ts = last_ts_by_token[token_id]
        if to_ms <= last_ts:
            return
        state = books[token_id]
        start = last_ts
        end = min(to_ms, min_window_ms)
        if end <= entry_ms:
            last_ts_by_token[token_id] = to_ms
            return
        interval_start = max(start, entry_ms)
        if interval_start < end:
            if not state.valid or state.last_update_ms is None:
                quarantine_reason_ms["stale_book"] += end - interval_start
            else:
                stale_start = max(interval_start, state.last_update_ms + stale_book_sec * 1000)
                if stale_start < end:
                    quarantine_reason_ms["stale_book"] += end - stale_start
        last_ts_by_token[token_id] = to_ms

    def maybe_post(token_id: str, ts_ms: int) -> None:
        side = token_sides[token_id]
        existing = any(k[0] == token_id for k in quotes)
        if existing or ts_ms < entry_ms or ts_ms > min_window_ms:
            return
        if should_skip_new_quote_for_final_window(end_ms=market.end_ms, post_ms=ts_ms):
            stats["quotes_skipped_final_60s"] += len(LADDERS)
            return
        state = books[token_id]
        if not is_book_fresh(state, ts_ms, stale_book_sec):
            return
        if prior_trade_count(trades_by_token[token_id], post_ms=ts_ms) < MIN_PRIOR_TOKEN_TRADES:
            stats["quotes_skipped_low_trade_density"] += len(LADDERS)
            return
        planned: list[tuple[str, Decimal, Decimal]] = []
        for ladder in LADDERS:
            ladder_quote = compute_queue_ahead(state, ladder)
            if ladder_quote is None:
                stats["quotes_skipped_invalid_ladder"] += 1
                continue
            quote_price, queue_ahead = ladder_quote
            if not target_band.contains(quote_price):
                stats["quotes_skipped_outside_band"] += 1
                continue
            planned.append((ladder, quote_price, queue_ahead))
        if not planned:
            return
        cancel_intent_ms = first_adverse_cex_signal(
            con,
            symbol=market.symbol,
            side=side,
            start_ms=ts_ms,
            end_ms=min_window_ms,
            window_sec=cancel_window_sec,
            threshold_bps=cancel_bps_threshold,
        )
        for ladder, quote_price, queue_ahead in planned:
            quote = QuoteSpec(
                ladder=ladder,
                condition_id=market.condition_id,
                symbol=market.symbol,
                side=side,
                token_id=token_id,
                posted_at_ms=ts_ms,
                end_ms=market.end_ms,
                quote_price=quote_price,
                quote_size=quote_size,
                queue_ahead_at_post=queue_ahead,
                tick_size=state.tick_size,
                cancel_intent_ms=cancel_intent_ms,
                cancel_reason="cex_adverse" if cancel_intent_ms is not None else None,
            )
            quotes[(token_id, ladder)] = quote
            upper_seen[(token_id, ladder)] = FillResult()
            stats["quotes_posted"] += 1

    for row in rows:
        ts_ms = int(row["received_at_ms"])
        asset_id = str(row["asset_id"] or "")
        etype = str(row["event_type"] or "")
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            continue

        affected_tokens: list[str]
        if etype == "price_change":
            raw_changes = payload.get("price_changes") if isinstance(payload, dict) else None
            affected_tokens = [
                str(ch.get("asset_id"))
                for ch in raw_changes or []
                if isinstance(ch, dict) and str(ch.get("asset_id")) in token_sides
            ]
        elif asset_id in token_sides:
            affected_tokens = [asset_id]
        elif etype in {"reconnect", "disconnect"}:
            affected_tokens = list(token_sides)
        else:
            affected_tokens = []

        for token_id in affected_tokens:
            accrue_stale(token_id, ts_ms)

        if etype in {"reconnect", "disconnect"}:
            stats["reconnects"] += 1
            for token_id in token_sides:
                books[token_id] = invalidate_book(books[token_id], received_at_ms=ts_ms)
            continue

        if etype == "tick_size_change" and asset_id in token_sides:
            stats["tick_size_changes"] += 1
            books[asset_id] = invalidate_book(books[asset_id], received_at_ms=ts_ms)
            continue

        if etype == "book" and asset_id in token_sides:
            books[asset_id] = parse_book_snapshot(payload, received_at_ms=ts_ms)
            maybe_post(asset_id, ts_ms)
            for ladder in LADDERS:
                quote = quotes.get((asset_id, ladder))
                if quote is None:
                    continue
                current_size = books[asset_id].ask_size_at(quote.quote_price)
                if current_size <= 0 and upper_seen[(asset_id, ladder)].upper_fill_at_ms is None:
                    upper_seen[(asset_id, ladder)].upper_fill_size = quote.quote_size
                    upper_seen[(asset_id, ladder)].upper_fill_at_ms = ts_ms
            continue

        if etype == "price_change":
            for token_id in affected_tokens:
                before = books[token_id].copy()
                books[token_id] = apply_delta(
                    books[token_id],
                    payload,
                    asset_id=token_id,
                    received_at_ms=ts_ms,
                )
                maybe_post(token_id, ts_ms)
                for ladder in LADDERS:
                    quote = quotes.get((token_id, ladder))
                    if quote is None:
                        continue
                    before_size = before.ask_size_at(quote.quote_price)
                    after_size = books[token_id].ask_size_at(quote.quote_price)
                    if before_size > after_size:
                        result = upper_seen[(token_id, ladder)]
                        result.queue_consumed_by_cancels += before_size - after_size
                        if after_size <= 0 and result.upper_fill_at_ms is None:
                            result.upper_fill_size = quote.quote_size
                            result.upper_fill_at_ms = ts_ms
            continue

        if etype == "last_trade_price" and asset_id in token_sides:
            price = decimal_or_none(payload.get("price"))
            size = decimal_or_none(payload.get("size"))
            if price is None or size is None or size <= 0:
                continue
            trades_by_token[asset_id].append(TradeEvent(
                ts_ms=ts_ms,
                price=price,
                size=size,
                side=str(payload.get("side") or "").upper(),
                taker_addr=_extract_taker_addr(payload),
                transaction_hash=(
                    str(payload.get("transaction_hash"))
                    if payload.get("transaction_hash") is not None else None
                ),
            ))

    for token_id in token_sides:
        accrue_stale(token_id, min_window_ms)
        if not any(k[0] == token_id for k in quotes):
            stats["quotes_skipped_no_fresh_book"] += len(LADDERS)

    quarantine_reason_ms["gap"] += stats["gap_quarantine_ms"]
    final_floor_start = max(entry_ms, market.end_ms - NEW_QUOTE_LEAD_FLOOR_SEC * 1000)
    final_60_ms = max(0, min(min_window_ms, market.end_ms) - final_floor_start) * 2
    stats["final_60s_quarantine_ms"] = final_60_ms
    quarantine_reason_ms["final_60s_no_new_quote"] += final_60_ms
    low_density_ms = 0
    for token_id in token_sides:
        low_density_ms += low_trade_density_quarantine_ms(
            (trade.ts_ms for trade in trades_by_token[token_id]),
            start_ms=entry_ms,
            end_ms=min_window_ms,
        )
    stats["low_trade_density_quarantine_ms"] = low_density_ms
    quarantine_reason_ms["low_trade_density"] += low_density_ms
    stats["quarantine_by_reason_ms"] = dict(quarantine_reason_ms)
    stats["quarantine_ms"] = min(
        int(stats["candidate_window_ms"]),
        sum(int(v) for v in quarantine_reason_ms.values()),
    )

    outcomes: list[QuoteOutcome] = []
    for quote in quotes.values():
        won = None if resolution.winner_token_id is None else quote.token_id == resolution.winner_token_id
        for latency_ms in cancel_latency_ms_values:
            active_until = quote.active_until_ms(latency_ms)
            lower = lower_bound_fill_count(
                trades_by_token.get(quote.token_id, []),
                quote_price=quote.quote_price,
                quote_size=quote.quote_size,
                queue_ahead=quote.queue_ahead_at_post,
                cancel_intent_ms=quote.cancel_intent_ms,
                cancel_latency_ms=latency_ms,
                active_from_ms=quote.posted_at_ms,
                active_until_ms=active_until,
            )
            upper = upper_seen.get((quote.token_id, quote.ladder), FillResult())
            if lower.lower_filled and not upper.upper_filled:
                upper.upper_fill_size = lower.lower_fill_size
                upper.upper_fill_at_ms = lower.lower_fill_at_ms
            duration_ms = max(0, active_until - quote.posted_at_ms)
            attempted_collateral_minutes = (
                (Decimal("1") - quote.quote_price)
                * quote.quote_size
                * Decimal(duration_ms)
                / Decimal("60000")
            )
            outcomes.append(QuoteOutcome(
                quote=quote,
                latency_ms=latency_ms,
                won=won,
                resolution_path=resolution.path,
                lower_fill_size=lower.lower_fill_size,
                lower_fill_at_ms=lower.lower_fill_at_ms,
                lower_fill_during_cancel=lower.lower_fill_during_cancel,
                upper_fill_size=max(upper.upper_fill_size, lower.lower_fill_size),
                upper_fill_at_ms=upper.upper_fill_at_ms or lower.lower_fill_at_ms,
                attempted_collateral_dollar_minutes=attempted_collateral_minutes,
                taker_fill_sizes=dict(lower.taker_fill_sizes),
                unknown_taker_fill_size=lower.unknown_taker_fill_size,
            ))
    return outcomes, stats


def _sum_decimal(values: Iterable[Decimal]) -> Decimal:
    total = Decimal("0")
    for value in values:
        total += value
    return total


def aggregate_outcomes(
    outcomes: list[QuoteOutcome],
    group_keys: tuple[str, ...],
    *,
    toxic_wallets: set[str] | frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[QuoteOutcome]] = defaultdict(list)
    for outcome in outcomes:
        key_parts: list[str] = []
        for key in group_keys:
            if key == "ladder":
                key_parts.append(outcome.quote.ladder)
            elif key == "symbol":
                key_parts.append(outcome.quote.symbol)
            elif key == "side":
                key_parts.append(outcome.quote.side)
            elif key == "price_band":
                key_parts.append(price_band_label(outcome.quote.quote_price))
            elif key == "lead_bucket":
                lead_sec = (outcome.quote.end_ms - outcome.quote.posted_at_ms) / 1000.0
                key_parts.append(lead_bucket(lead_sec))
            elif key == "latency_ms":
                key_parts.append(str(outcome.latency_ms))
            elif key == "resolution_path":
                key_parts.append(outcome.resolution_path)
            else:
                raise ValueError(f"unknown group key {key!r}")
        groups[tuple(key_parts)].append(outcome)

    rows: list[dict[str, Any]] = []
    for key_values, group in groups.items():
        attempts = len(group)
        lower_fills = [g for g in group if g.lower_filled]
        upper_fills = [g for g in group if g.upper_filled]
        wins = sum(1 for g in lower_fills if g.won)
        known_fills = sum(1 for g in lower_fills if g.won is not None)
        total_pnl = _sum_decimal(g.pnl for g in group)
        total_pnl_excluding_toxic = _sum_decimal(
            g.pnl_excluding_toxic(toxic_wallets) for g in group
        )
        total_collateral_minutes = _sum_decimal(g.attempted_collateral_dollar_minutes for g in group)
        total_fill_collateral = _sum_decimal(
            (Decimal("1") - g.quote.quote_price) * g.lower_fill_size for g in lower_fills
        )
        total_clean_fill_collateral = _sum_decimal(
            (Decimal("1") - g.quote.quote_price)
            * (g.lower_fill_size - g.toxic_fill_size(toxic_wallets))
            for g in lower_fills
        )
        toxic_fill_size = _sum_decimal(g.toxic_fill_size(toxic_wallets) for g in lower_fills)
        toxic_fills = sum(1 for g in lower_fills if g.toxic_fill_size(toxic_wallets) > 0)
        unknown_taker_fills = sum(1 for g in lower_fills if g.unknown_taker_fill_size > 0)
        per_fill_roi = total_pnl / total_fill_collateral if total_fill_collateral > 0 else None
        per_fill_roi_excluding_toxic = (
            total_pnl_excluding_toxic / total_clean_fill_collateral
            if total_clean_fill_collateral > 0 else None
        )
        dollar_minute_roi = (
            total_pnl / total_collateral_minutes if total_collateral_minutes > 0 else None
        )
        dollar_minute_roi_excluding_toxic = (
            total_pnl_excluding_toxic / total_collateral_minutes
            if total_collateral_minutes > 0 else None
        )
        ci_lo, ci_hi = _wilson(wins, known_fills)
        row = {k: v for k, v in zip(group_keys, key_values, strict=True)}
        row.update({
            "attempts": attempts,
            "lower_fills": len(lower_fills),
            "upper_fills": len(upper_fills),
            "lower_fill_rate_pct": 100.0 * len(lower_fills) / attempts if attempts else 0.0,
            "upper_fill_rate_pct": 100.0 * len(upper_fills) / attempts if attempts else 0.0,
            "lower_upper_ratio": (
                len(lower_fills) / len(upper_fills) if upper_fills else None
            ),
            "wins": wins,
            "known_fills": known_fills,
            "win_rate_pct": 100.0 * wins / known_fills if known_fills else None,
            "wilson_lo_pct": 100.0 * ci_lo if ci_lo is not None else None,
            "wilson_hi_pct": 100.0 * ci_hi if ci_hi is not None else None,
            "avg_quote_price": (
                float(_sum_decimal(g.quote.quote_price for g in group) / attempts)
                if attempts else None
            ),
            "total_pnl": float(total_pnl),
            "total_pnl_excluding_toxic": float(total_pnl_excluding_toxic),
            "collateral_dollar_minute_roi": float(dollar_minute_roi)
            if dollar_minute_roi is not None else None,
            "roi_all_fills": float(dollar_minute_roi)
            if dollar_minute_roi is not None else None,
            "roi_excluding_toxic": float(dollar_minute_roi_excluding_toxic)
            if dollar_minute_roi_excluding_toxic is not None else None,
            "per_fill_collateral_roi": float(per_fill_roi) if per_fill_roi is not None else None,
            "per_fill_collateral_roi_excluding_toxic": (
                float(per_fill_roi_excluding_toxic)
                if per_fill_roi_excluding_toxic is not None else None
            ),
            "fills_during_cancel": sum(1 for g in lower_fills if g.lower_fill_during_cancel),
            "toxic_fills": toxic_fills,
            "toxic_fill_size": float(toxic_fill_size),
            "unknown_taker_fills": unknown_taker_fills,
        })
        rows.append(row)
    return sorted(rows, key=lambda r: tuple(str(r.get(k) or "") for k in group_keys))


def adverse_selection_rows(outcomes: list[QuoteOutcome]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[QuoteOutcome]] = defaultdict(list)
    for outcome in outcomes:
        key = (
            outcome.quote.symbol,
            outcome.quote.side,
            price_band_label(outcome.quote.quote_price),
            outcome.quote.ladder,
        )
        groups[key].append(outcome)
    rows: list[dict[str, Any]] = []
    for (symbol, side, band, ladder), group in groups.items():
        filled = [g for g in group if g.lower_filled and g.won is not None]
        unfilled = [g for g in group if not g.lower_filled and g.won is not None]
        filled_wins = sum(1 for g in filled if g.won)
        unfilled_wins = sum(1 for g in unfilled if g.won)
        filled_wr = filled_wins / len(filled) if filled else None
        unfilled_wr = unfilled_wins / len(unfilled) if unfilled else None
        rows.append({
            "symbol": symbol,
            "side": side,
            "price_band": band,
            "ladder": ladder,
            "filled": len(filled),
            "unfilled": len(unfilled),
            "filled_win_rate_pct": 100.0 * filled_wr if filled_wr is not None else None,
            "unfilled_win_rate_pct": 100.0 * unfilled_wr if unfilled_wr is not None else None,
            "filled_minus_unfilled_pp": (
                100.0 * (filled_wr - unfilled_wr)
                if filled_wr is not None and unfilled_wr is not None else None
            ),
        })
    return sorted(rows, key=lambda r: (r["symbol"], r["side"], r["price_band"], r["ladder"]))


def counterparty_diagnostics(outcomes: list[QuoteOutcome]) -> dict[str, Any]:
    wallet_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "fills": 0,
            "wins": 0,
            "fill_size": Decimal("0"),
            "pnl": Decimal("0"),
            "collateral": Decimal("0"),
        }
    )
    unknown_fills = 0
    for outcome in outcomes:
        if not outcome.lower_filled or outcome.won is None:
            continue
        won_price = Decimal("1") if outcome.won else Decimal("0")
        if not outcome.taker_fill_sizes:
            unknown_fills += 1
        for addr, fill_size in outcome.taker_fill_sizes.items():
            row = wallet_stats[addr]
            row["fills"] += 1
            row["wins"] += int(outcome.won)
            row["fill_size"] += fill_size
            row["pnl"] += (outcome.quote.quote_price - won_price) * fill_size
            row["collateral"] += (Decimal("1") - outcome.quote.quote_price) * fill_size

    rows: list[dict[str, Any]] = []
    for addr, row in wallet_stats.items():
        collateral = row["collateral"]
        fills = int(row["fills"])
        rows.append({
            "taker_addr": addr,
            "fills": fills,
            "wins": int(row["wins"]),
            "fill_size": float(row["fill_size"]),
            "win_rate_pct": 100.0 * int(row["wins"]) / fills if fills else None,
            "collateral_roi": (
                float(row["pnl"] / collateral) if collateral > 0 else None
            ),
            "pnl": float(row["pnl"]),
            "collateral": float(collateral),
        })
    rows.sort(key=lambda r: (-int(r["fills"]), r["taker_addr"]))

    def cohort_summary(cohort: list[dict[str, Any]]) -> dict[str, Any]:
        fills = sum(int(r["fills"]) for r in cohort)
        if fills <= 0:
            return {"fills": 0, "win_rate_pct": None, "collateral_roi": None}
        wins = sum(int(r.get("wins") or 0) for r in cohort)
        pnl = sum(Decimal(str(r.get("pnl") or 0.0)) for r in cohort)
        collateral = sum(Decimal(str(r.get("collateral") or 0.0)) for r in cohort)
        return {
            "fills": fills,
            "win_rate_pct": 100.0 * wins / fills,
            "collateral_roi": float(pnl / collateral) if collateral > 0 else None,
        }

    known_fills = sum(int(r["fills"]) for r in rows)
    top_10 = rows[:10]
    rest = rows[10:]
    top_summary = cohort_summary(top_10)
    rest_summary = cohort_summary(rest)
    top_share = top_summary["fills"] / known_fills if known_fills else None
    gap_pp = (
        top_summary["win_rate_pct"] - rest_summary["win_rate_pct"]
        if top_summary["win_rate_pct"] is not None
        and rest_summary["win_rate_pct"] is not None else None
    )
    return {
        "data_available": known_fills > 0,
        "known_taker_fills": known_fills,
        "unknown_taker_fills": unknown_fills,
        "top_10_taker_wallets_share_of_fills": top_share,
        "top_10_taker_wallets_avg_win_rate_pct": top_summary["win_rate_pct"],
        "top_10_taker_wallets_avg_collateral_roi": top_summary["collateral_roi"],
        "remaining_taker_wallets_avg_win_rate_pct": rest_summary["win_rate_pct"],
        "remaining_taker_wallets_avg_collateral_roi": rest_summary["collateral_roi"],
        "top_10_minus_rest_win_rate_gap_pp": gap_pp,
        "top_100": rows[:100],
    }


def toxic_fill_summary(
    outcomes: list[QuoteOutcome],
    toxic_wallets: set[str] | frozenset[str],
) -> dict[str, Any]:
    lower_fills = [outcome for outcome in outcomes if outcome.lower_filled]
    toxic_fills = [
        outcome for outcome in lower_fills if outcome.toxic_fill_size(toxic_wallets) > 0
    ]
    known_taker_fills = sum(1 for outcome in lower_fills if outcome.taker_fill_sizes)
    return {
        "total_lower_fills": len(lower_fills),
        "known_taker_lower_fills": known_taker_fills,
        "unknown_taker_lower_fills": len(lower_fills) - known_taker_fills,
        "toxic_lower_fills": len(toxic_fills),
        "toxic_lower_fill_share": (
            len(toxic_fills) / len(lower_fills) if lower_fills else None
        ),
    }


def acceptance_rows(
    outcomes: list[QuoteOutcome],
    market_stats: list[dict[str, Any]],
    adverse_rows: list[dict[str, Any]],
    toxic_wallets: set[str] | frozenset[str],
    counterparty: dict[str, Any],
) -> list[dict[str, Any]]:
    primary = [
        o for o in outcomes
        if o.quote.side == "UP"
        and price_band_label(o.quote.quote_price) in {"5.5-8c", "8-10c", "10-15c"}
    ]
    primary_300 = [o for o in primary if o.latency_ms == 300]
    agg_primary_300 = aggregate_outcomes(
        primary_300,
        ("side", "latency_ms"),
        toxic_wallets=toxic_wallets,
    )
    p300 = agg_primary_300[0] if agg_primary_300 else {}
    lower_fills = int(p300.get("lower_fills") or 0)
    cdmin_roi = p300.get("collateral_dollar_minute_roi")
    roi_excluding_toxic = p300.get("roi_excluding_toxic")
    ratio = p300.get("lower_upper_ratio")
    total_quarantine = sum(int(s.get("quarantine_ms") or 0) for s in market_stats)
    total_candidate = sum(int(s.get("candidate_window_ms") or 0) for s in market_stats)
    quarantine_frac = total_quarantine / total_candidate if total_candidate else None
    worst_adverse_pp = None
    for row in adverse_rows:
        if row["side"] != "UP":
            continue
        delta = row.get("filled_minus_unfilled_pp")
        if delta is not None:
            worst_adverse_pp = delta if worst_adverse_pp is None else min(worst_adverse_pp, delta)
    cell_rows = aggregate_outcomes(
        primary_300,
        ("symbol", "side", "price_band", "ladder", "latency_ms"),
        toxic_wallets=toxic_wallets,
    )
    pass_cells = [
        r for r in cell_rows
        if r.get("collateral_dollar_minute_roi") is not None
        and float(r["collateral_dollar_minute_roi"]) > 0
    ]
    min_pass_cell_fills = min((int(r.get("lower_fills") or 0) for r in pass_cells), default=0)
    down_rows = aggregate_outcomes(
        [o for o in outcomes if o.quote.side == "DOWN" and o.latency_ms == 300],
        ("side", "latency_ms"),
        toxic_wallets=toxic_wallets,
    )
    down_roi = down_rows[0].get("collateral_dollar_minute_roi") if down_rows else None
    top10_share = counterparty.get("top_10_taker_wallets_share_of_fills")
    top10_gap = counterparty.get("top_10_minus_rest_win_rate_gap_pp")
    concentration_pass = bool(counterparty.get("data_available")) and (
        (top10_share is not None and top10_share < 0.30)
        or (top10_gap is not None and top10_gap < 10.0)
    )
    rows = [
        {
            "criterion": "UP lower-bound fills at 300ms",
            "threshold": ">= 150",
            "value": lower_fills,
            "pass": lower_fills >= 150,
        },
        {
            "criterion": "UP collateral dollar-minute ROI at 300ms",
            "threshold": "> 0%",
            "value": cdmin_roi,
            "pass": cdmin_roi is not None and cdmin_roi > 0,
        },
        {
            "criterion": "300ms cancel-latency ROI stays positive",
            "threshold": "> 0%",
            "value": cdmin_roi,
            "pass": cdmin_roi is not None and cdmin_roi > 0,
        },
        {
            "criterion": "Lower-bound / upper-bound fill ratio",
            "threshold": ">= 0.33",
            "value": ratio,
            "pass": ratio is not None and ratio >= 0.33,
        },
        {
            "criterion": "Quarantine fraction",
            "threshold": "< 5%",
            "value": quarantine_frac,
            "pass": quarantine_frac is not None and quarantine_frac < 0.05,
        },
        {
            "criterion": "Adverse selection filled win-rate penalty",
            "threshold": ">= -5pp",
            "value": worst_adverse_pp,
            "pass": worst_adverse_pp is not None and worst_adverse_pp >= -5.0,
        },
        {
            "criterion": "Minimum fills for positive pass-labelled cell",
            "threshold": ">= 50",
            "value": min_pass_cell_fills,
            "pass": bool(pass_cells) and min_pass_cell_fills >= 50,
        },
        {
            "criterion": "ROI excluding toxic-marked counterparty fills",
            "threshold": "> 0%",
            "value": roi_excluding_toxic,
            "pass": roi_excluding_toxic is not None and roi_excluding_toxic > 0,
        },
        {
            "criterion": "Top-10 taker wallet concentration",
            "threshold": "<30% fills OR <10pp win-rate gap",
            "value": {
                "share": top10_share,
                "win_rate_gap_pp": top10_gap,
                "data_available": counterparty.get("data_available"),
            },
            "pass": concentration_pass,
        },
        {
            "criterion": "DOWN control does not beat UP",
            "threshold": "DOWN <= UP",
            "value": down_roi,
            "pass": (
                cdmin_roi is not None
                and down_roi is not None
                and float(down_roi) <= float(cdmin_roi)
            ),
        },
    ]
    return rows


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, Path):
        return str(obj)
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def build_output(con: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    target_band = parse_target_band(args.target_band)
    cancel_latencies = [int(x.strip()) for x in str(args.cancel_latency_ms).split(",") if x.strip()]
    quote_size = decimal_or_none(args.quote_size) or QUOTE_SIZE
    cancel_bps = Decimal(str(args.cex_cancel_bps_threshold))
    toxic_wallets, toxic_detector = load_toxic_wallets(con)
    markets = build_candidate_markets(
        con,
        lookback_days=args.lookback_days,
        max_markets=args.max_markets,
    )
    outcomes: list[QuoteOutcome] = []
    market_stats: list[dict[str, Any]] = []
    resolution_counter: Counter[str] = Counter()
    sensitivity_counter: Counter[str] = Counter()

    for idx, market in enumerate(markets, start=1):
        candidate_window_ms = (
            args.target_lead_max_sec - args.target_lead_min_sec
        ) * 1000 * 2
        if is_weekend_utc(market.end_ms):
            market_stats.append({
                "condition_id": market.condition_id,
                "symbol": market.symbol,
                "question": market.question,
                "end_iso": _ms_to_iso(market.end_ms),
                "quotes_posted": 0,
                "weekend_excluded": True,
                "candidate_window_ms": candidate_window_ms,
                "quarantine_ms": candidate_window_ms,
                "quarantine_by_reason_ms": {"weekend": candidate_window_ms},
            })
            continue
        print(
            f"[{idx}/{len(markets)}] simulating {market.symbol} {market.condition_id}",
            flush=True,
        )
        resolution = resolve_market(con, market)
        resolution_counter[resolution.path] += 1
        if resolution.strict_winner_token_id:
            sensitivity_counter["strict"] += 1
        if resolution.baseline_winner_token_id:
            sensitivity_counter["baseline"] += 1
        if resolution.inclusive_winner_token_id:
            sensitivity_counter["inclusive"] += 1
        if resolution.winner_token_id is None:
            market_stats.append({
                "condition_id": market.condition_id,
                "symbol": market.symbol,
                "quotes_posted": 0,
                "unresolved": True,
                "candidate_window_ms": candidate_window_ms,
                "quarantine_ms": 0,
                "quarantine_by_reason_ms": {},
            })
            continue
        market_outcomes, stats = simulate_market(
            con,
            market,
            resolution,
            target_band=target_band,
            min_lead_sec=args.target_lead_min_sec,
            max_lead_sec=args.target_lead_max_sec,
            cancel_latency_ms_values=cancel_latencies,
            cancel_bps_threshold=cancel_bps,
            cancel_window_sec=args.cex_cancel_window_sec,
            quote_size=quote_size,
            stale_book_sec=args.stale_book_sec,
        )
        outcomes.extend(market_outcomes)
        market_stats.append(stats)

    adverse = adverse_selection_rows([o for o in outcomes if o.latency_ms == 300])
    primary_300_outcomes = [
        o for o in outcomes
        if o.latency_ms == 300
        and o.quote.side == "UP"
        and price_band_label(o.quote.quote_price) in {"5.5-8c", "8-10c", "10-15c"}
    ]
    counterparty = counterparty_diagnostics(primary_300_outcomes)
    toxicity = toxic_fill_summary(primary_300_outcomes, toxic_wallets)
    acceptance = acceptance_rows(
        outcomes,
        market_stats,
        adverse,
        toxic_wallets,
        counterparty,
    )
    quarantine_by_reason = Counter()
    for stats in market_stats:
        quarantine_by_reason.update({
            key: int(value)
            for key, value in dict(stats.get("quarantine_by_reason_ms") or {}).items()
        })
    weekend_excluded = sum(1 for stats in market_stats if stats.get("weekend_excluded"))
    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "recorder_db": str(Path(args.recorder_db).resolve()),
        "label": args.label,
        "lookback_days": args.lookback_days,
        "target_band": args.target_band,
        "target_lead_min_sec": args.target_lead_min_sec,
        "target_lead_max_sec": args.target_lead_max_sec,
        "cancel_latency_ms": cancel_latencies,
        "cancel_latency_regime_keys": {
            f"cancel_latency_{latency_ms}ms": True for latency_ms in cancel_latencies
        },
        "cex_cancel_bps_threshold": args.cex_cancel_bps_threshold,
        "cex_cancel_window_sec": args.cex_cancel_window_sec,
        "quote_size": float(quote_size),
        "fee_model": {
            "maker_fee": 0.0,
            "maker_rebate_base_case": 0.0,
            "crypto_maker_rebate_upside_only": 0.20,
        },
        "coverage": {
            "candidate_markets": len(markets),
            "weekday_candidate_markets": len(markets) - weekend_excluded,
            "weekend_excluded_markets": weekend_excluded,
            "weekend_excluded_fraction": weekend_excluded / len(markets) if markets else None,
            "simulated_quote_outcomes": len(outcomes),
            "quote_attempts_unique": len({
                (
                    o.quote.condition_id,
                    o.quote.token_id,
                    o.quote.ladder,
                )
                for o in outcomes
            }),
            "quote_attempts_by_latency": len(outcomes),
            "markets_with_quotes": len({o.quote.condition_id for o in outcomes}),
        },
        "resolution_paths": dict(resolution_counter),
        "resolution_sensitivity": dict(sensitivity_counter),
        "quarantine": {
            "quarantine_ms": sum(int(s.get("quarantine_ms") or 0) for s in market_stats),
            "candidate_window_ms": sum(int(s.get("candidate_window_ms") or 0) for s in market_stats),
            "by_reason_ms": dict(quarantine_by_reason),
        },
        "by_ladder": aggregate_outcomes(
            outcomes,
            ("ladder", "latency_ms"),
            toxic_wallets=toxic_wallets,
        ),
        "by_symbol_side": aggregate_outcomes(
            outcomes,
            ("symbol", "side", "latency_ms"),
            toxic_wallets=toxic_wallets,
        ),
        "by_cell": aggregate_outcomes(
            outcomes,
            ("symbol", "side", "price_band", "lead_bucket", "ladder", "latency_ms"),
            toxic_wallets=toxic_wallets,
        ),
        "by_resolution_path": aggregate_outcomes(
            outcomes,
            ("resolution_path", "latency_ms"),
            toxic_wallets=toxic_wallets,
        ),
        "adverse_selection": adverse,
        "manipulation_defense": {
            "toxic_detector": toxic_detector,
            "toxicity": toxicity,
            "counterparty": counterparty,
            "primary_question_pass": None,
        },
        "acceptance": acceptance,
        "market_stats": market_stats,
    }
    q = output["quarantine"]
    if q["candidate_window_ms"]:
        q["fraction"] = q["quarantine_ms"] / q["candidate_window_ms"]
    else:
        q["fraction"] = None
    output["verdict"] = "PASS" if all(row["pass"] for row in acceptance) else "FAIL"
    primary_question_pass = (
        output["verdict"] == "PASS"
        and bool(counterparty.get("data_available"))
    )
    output["manipulation_defense"]["primary_question_pass"] = primary_question_pass
    return output


def render_md(out: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Maker Simulator Paper Report (Phase B2)")
    lines.append("")
    lines.append(f"Generated: `{out['generated_at']}`")
    lines.append(f"Label: `{out['label']}`")
    lines.append(f"Recorder DB: `{out['recorder_db']}`")
    lines.append(f"Verdict: **{out['verdict']}**")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append(
        "Offline read-only simulator for OQ-083. No bot package, service, "
        "dashboard, wallet, cap, or order path is created or modified."
    )
    lines.append("")
    lines.append("## Coverage")
    lines.append("")
    cov = out["coverage"]
    lines.append(f"- Candidate markets: `{cov['candidate_markets']:,}`")
    lines.append(f"- Weekday candidate markets: `{cov['weekday_candidate_markets']:,}`")
    lines.append(
        f"- Weekend excluded markets: `{cov['weekend_excluded_markets']:,}` "
        f"(`{(cov.get('weekend_excluded_fraction') or 0) * 100:.2f}%`)"
    )
    lines.append(f"- Markets with posted quotes: `{cov['markets_with_quotes']:,}`")
    lines.append(f"- Unique quote attempts: `{cov['quote_attempts_unique']:,}`")
    lines.append(f"- Quote outcomes including latency regimes: `{cov['quote_attempts_by_latency']:,}`")
    lines.append(
        f"- Target: `{out['target_band']}`, lead "
        f"`{out['target_lead_min_sec']}-{out['target_lead_max_sec']}s`, "
        f"quote size `{out['quote_size']}` shares"
    )
    lines.append("")
    lines.append("## Fee Assumption")
    lines.append("")
    lines.append(
        "Base case uses maker fee `0` and maker rebate `0`. Crypto maker "
        "rebate is tracked as upside only and is not included in any gate."
    )
    lines.append("")
    lines.append("## Per-Ladder Summary")
    lines.append("")
    lines.append(_table(out["by_ladder"], [
        ("ladder", "ladder", "str"),
        ("latency_ms", "latency ms", "str"),
        ("attempts", "attempts", "int"),
        ("lower_fills", "lower fills", "int"),
        ("upper_fills", "upper fills", "int"),
        ("lower_fill_rate_pct", "lower fill %", "pct"),
        ("lower_upper_ratio", "lower/upper", "price"),
        ("win_rate_pct", "win %", "pct"),
        ("wilson_lo_pct", "Wilson lo", "pct"),
        ("wilson_hi_pct", "Wilson hi", "pct"),
        ("collateral_dollar_minute_roi", "collateral $-min ROI", "roi"),
        ("roi_excluding_toxic", "ROI excl toxic", "roi"),
        ("per_fill_collateral_roi", "per-fill coll ROI", "roi"),
    ]))
    lines.append("")
    lines.append("## Symbol x Side")
    lines.append("")
    lines.append(_table(out["by_symbol_side"], [
        ("symbol", "symbol", "str"),
        ("side", "side", "str"),
        ("latency_ms", "latency ms", "str"),
        ("attempts", "attempts", "int"),
        ("lower_fills", "lower fills", "int"),
        ("upper_fills", "upper fills", "int"),
        ("win_rate_pct", "win %", "pct"),
        ("collateral_dollar_minute_roi", "collateral $-min ROI", "roi"),
        ("roi_excluding_toxic", "ROI excl toxic", "roi"),
        ("per_fill_collateral_roi", "per-fill coll ROI", "roi"),
    ]))
    lines.append("")
    lines.append("## Per-Cell Detail")
    lines.append("")
    lines.append(_table(out["by_cell"], [
        ("symbol", "symbol", "str"),
        ("side", "side", "str"),
        ("price_band", "price band", "str"),
        ("lead_bucket", "lead", "str"),
        ("ladder", "ladder", "str"),
        ("latency_ms", "latency ms", "str"),
        ("attempts", "attempts", "int"),
        ("lower_fills", "lower fills", "int"),
        ("upper_fills", "upper fills", "int"),
        ("win_rate_pct", "win %", "pct"),
        ("wilson_lo_pct", "Wilson lo", "pct"),
        ("wilson_hi_pct", "Wilson hi", "pct"),
        ("collateral_dollar_minute_roi", "collateral $-min ROI", "roi"),
        ("roi_excluding_toxic", "ROI excl toxic", "roi"),
        ("toxic_fills", "toxic fills", "int"),
    ]))
    lines.append("")
    lines.append("## Cancel-Latency Comparison")
    lines.append("")
    lines.append(_table(out["by_symbol_side"], [
        ("symbol", "symbol", "str"),
        ("side", "side", "str"),
        ("latency_ms", "latency ms", "str"),
        ("lower_fills", "lower fills", "int"),
        ("fills_during_cancel", "fills during cancel", "int"),
        ("collateral_dollar_minute_roi", "collateral $-min ROI", "roi"),
    ]))
    lines.append("")
    lines.append("## Adverse Selection")
    lines.append("")
    lines.append(_table(out["adverse_selection"], [
        ("symbol", "symbol", "str"),
        ("side", "side", "str"),
        ("price_band", "price band", "str"),
        ("ladder", "ladder", "str"),
        ("filled", "filled", "int"),
        ("unfilled", "unfilled", "int"),
        ("filled_win_rate_pct", "filled win %", "pct"),
        ("unfilled_win_rate_pct", "unfilled win %", "pct"),
        ("filled_minus_unfilled_pp", "delta pp", "price"),
    ]))
    lines.append("")
    lines.append("## Manipulation Defense")
    lines.append("")
    md = out["manipulation_defense"]
    toxic_detector = md["toxic_detector"]
    toxicity = md["toxicity"]
    counterparty = md["counterparty"]
    lines.append("### Toxic-Wallet Detection")
    lines.append("")
    lines.append(f"- Detector source: `{toxic_detector.get('source')}`")
    lines.append(f"- Detector data available: `{toxic_detector.get('available')}`")
    lines.append(f"- Toxic wallets found: `{toxic_detector.get('toxic_wallet_count', 0):,}`")
    lines.append(f"- Primary lower fills: `{toxicity['total_lower_fills']:,}`")
    lines.append(f"- Known-taker lower fills: `{toxicity['known_taker_lower_fills']:,}`")
    lines.append(f"- Unknown-taker lower fills: `{toxicity['unknown_taker_lower_fills']:,}`")
    lines.append(f"- Toxic-marked lower fills: `{toxicity['toxic_lower_fills']:,}`")
    toxic_share = toxicity.get("toxic_lower_fill_share")
    lines.append(f"- Toxic fill share: `{(toxic_share or 0) * 100:.2f}%`")
    lines.append("")
    lines.append("### Counterparty Concentration")
    lines.append("")
    lines.append(f"- Data available: `{counterparty.get('data_available')}`")
    top_share = counterparty.get("top_10_taker_wallets_share_of_fills")
    gap = counterparty.get("top_10_minus_rest_win_rate_gap_pp")
    lines.append(f"- Top-10 taker wallet share of fills: `{(top_share or 0) * 100:.2f}%`")
    lines.append(f"- Top-10 minus rest win-rate gap: `{gap if gap is not None else 'n/a'}`")
    lines.append("")
    lines.append(_table(counterparty.get("top_100") or [], [
        ("taker_addr", "taker", "str"),
        ("fills", "fills", "int"),
        ("win_rate_pct", "win %", "pct"),
        ("collateral_roi", "collateral ROI", "roi"),
    ]))
    lines.append("")
    lines.append("### ROI All vs Excluding Toxic")
    lines.append("")
    primary_cells = [
        row for row in out["by_cell"]
        if row.get("latency_ms") == "300"
        and row.get("side") == "UP"
        and row.get("price_band") in {"5.5-8c", "8-10c", "10-15c"}
    ]
    lines.append(_table(primary_cells, [
        ("symbol", "symbol", "str"),
        ("price_band", "price band", "str"),
        ("ladder", "ladder", "str"),
        ("attempts", "attempts", "int"),
        ("lower_fills", "lower fills", "int"),
        ("roi_all_fills", "ROI all fills", "roi"),
        ("roi_excluding_toxic", "ROI excl toxic", "roi"),
        ("toxic_fills", "toxic fills", "int"),
        ("unknown_taker_fills", "unknown taker fills", "int"),
    ]))
    lines.append("")
    lines.append("## Quarantine")
    lines.append("")
    q = out["quarantine"]
    frac = q.get("fraction")
    lines.append(f"- Quarantined minutes: `{q['quarantine_ms'] / 60000:.2f}`")
    lines.append(f"- Candidate-window minutes: `{q['candidate_window_ms'] / 60000:.2f}`")
    lines.append(f"- Quarantine fraction: `{(frac or 0) * 100:.2f}%`")
    if q.get("by_reason_ms"):
        lines.append("")
        lines.append("Breakdown by reason (reasons can overlap; total fraction is capped per market):")
        for reason, value in sorted(q["by_reason_ms"].items()):
            lines.append(f"- `{reason}`: `{int(value) / 60000:.2f}` minutes")
    lines.append("")
    lines.append("## Resolution Paths")
    lines.append("")
    for key, value in sorted(out["resolution_paths"].items()):
        lines.append(f"- `{key}`: `{value:,}` markets")
    if out["resolution_sensitivity"]:
        lines.append("")
        lines.append("Sensitivity counts with price-threshold fallback:")
        for key, value in sorted(out["resolution_sensitivity"].items()):
            lines.append(f"- `{key}`: `{value:,}` markets")
    lines.append("")
    lines.append("## Acceptance Gate")
    lines.append("")
    lines.append(_table(out["acceptance"], [
        ("criterion", "criterion", "str"),
        ("threshold", "threshold", "str"),
        ("value", "value", "str"),
        ("pass", "pass", "str"),
    ]))
    lines.append("")
    lines.append("## Readout")
    lines.append("")
    if out["verdict"] == "PASS":
        lines.append(
            "The offline simulator clears OQ-083. The next step is a separate ADR "
            "for a paper-only maker research lane; this report itself authorizes no runtime."
        )
    else:
        lines.append(
            "The offline simulator does not clear OQ-083. Do not build a maker "
            "runtime from this result without a new decision record."
        )
    lines.append("")
    lines.append(
        "Manipulation-defense question: does this earn positive ROI excluding "
        "toxic-marked fills under 300ms cancel latency on weekday markets only? "
        f"**{'YES' if out['manipulation_defense']['primary_question_pass'] else 'NO'}**."
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    db_path = Path(args.recorder_db).expanduser().resolve()
    if not db_path.exists():
        raise SystemExit(f"recorder DB not found at {db_path}")
    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    if args.label:
        out_md = out_md.with_stem(out_md.stem + "-" + args.label)
        out_json = out_json.with_stem(out_json.stem + "-" + args.label)
    if not out_md.is_absolute():
        out_md = REPO_ROOT / out_md
    if not out_json.is_absolute():
        out_json = REPO_ROOT / out_json

    con = connect_ro(db_path)
    try:
        output = build_output(con, args)
    finally:
        con.close()

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_md(output), encoding="utf-8")
    out_json.write_text(json.dumps(output, indent=2, default=_json_safe), encoding="utf-8")
    print(f"wrote {out_md}", flush=True)
    print(f"wrote {out_json}", flush=True)


if __name__ == "__main__":
    main()
