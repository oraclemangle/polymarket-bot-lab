#!/usr/bin/env python3
"""Unified backtest framework for 15-min / 5-min crypto Up/Down markets.

Reads from the Bot E recorder DB (pm_events + cex_trades + markets tables)
and replays each resolved market chronologically against one or more
Strategy implementations. Produces apples-to-apples comparison of:

  1. OBI Scalp — Bot E v1 directional thesis (book imbalance → direction).
  2. Longshot Fade — buy ≤1¢ seconds before resolution, hope for CEX spike.
  3. Correlation Arb — pair-trade across BTC/ETH/SOL when Polymarket
     probabilities diverge more than historical correlation permits.

Usage:
    python scripts/backtest_strategies.py [--db PATH] [--since YYYY-MM-DD]
                                          [--limit N_MARKETS] [--strategies ...]

Design choices (documented to explain judgment calls during autonomous build):

  * **Outcome determination** uses Binance spot price from cex_trades,
    sampling the last trade before (start_time, end_time). Polymarket's
    actual resolution source may use mark price or a different timestamp
    rule — we accept ~0.01% noise rather than replicate the exact oracle.

  * **Window parsing** parses start/end from the question text regex. We
    store `end_date_iso` in markets but not start; derive from question.
    Falls back to end - 15min if the question is unparseable.

  * **Fill simulation** uses best_bid_ask events as the canonical book
    signal (cleanest per event-type sample). BUY limit fills when
    best_ask <= limit; SELL when best_bid >= limit. One-fill-per-order
    (no partial). This matches Portfolio.simulate_paper_fills behaviour.

  * **Fees** are zero in v1. Polymarket fee model is maker rebate / taker
    fee depending on side; flat 1% round-trip adds a clean pessimism
    shift to all three strategies equally, noted as TODO.

  * **Per-asset vs cross-asset replay**: Method 3 needs cross-asset
    state. We replay markets grouped by overlapping time windows so
    Method 3 sees multiple markets' current state at each tick.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator, Protocol

log = logging.getLogger("backtest")


# ===========================================================================
# Market metadata
# ===========================================================================

_QUESTION_RE = re.compile(
    r"(Bitcoin|Ethereum|Solana)\s+Up or Down\s*-\s*"
    r"(\w+ \d+),\s*"                                       # "April 19"
    r"(\d{1,2}(?::\d{2})?(?:AM|PM))"                       # "5:20PM" or "10AM"
    r"(?:\s*-\s*(\d{1,2}(?::\d{2})?(?:AM|PM)))?\s*ET",     # "5:25PM" optional
    re.IGNORECASE,
)

_SYMBOL_MAP = {"BITCOIN": "BTCUSDT", "ETHEREUM": "ETHUSDT", "SOLANA": "SOLUSDT"}


@dataclass
class MarketMeta:
    condition_id: str
    question: str
    symbol: str                   # "BTCUSDT" etc.
    yes_token_id: str
    no_token_id: str
    start_ms: int                 # window start (UTC ms)
    end_ms: int                   # window end / resolution (UTC ms)


def _parse_et_time(date_str: str, time_str: str, year: int) -> datetime | None:
    """Parse "April 19, 5:20PM" as a naive datetime (ET)."""
    full = f"{date_str} {year} {time_str.upper()}"
    for fmt in ("%B %d %Y %I:%M%p", "%B %d %Y %I%p"):
        try:
            return datetime.strptime(full, fmt)
        except ValueError:
            continue
    return None


def parse_market_window(question: str, end_date_iso: str) -> tuple[str, int, int] | None:
    """Extract (symbol, start_ms, end_ms) from question + stored end_date.

    Returns None if the question can't be parsed. ET → UTC conversion uses
    the stored end_date_iso as the source of truth for the UTC end; start is
    end - window_minutes (5, 15, etc.) derived from the question's start vs
    end times.
    """
    m = _QUESTION_RE.search(question)
    if m is None:
        return None
    asset, date_str, start_str, end_str = m.groups()
    symbol = _SYMBOL_MAP.get(asset.upper())
    if symbol is None:
        return None
    end_dt = datetime.fromisoformat(end_date_iso.replace("Z", "+00:00"))
    end_ms = int(end_dt.timestamp() * 1000)
    # Derive window minutes from start/end strings if both present; else 15.
    minutes = 15
    if end_str:
        year = end_dt.year
        start_et = _parse_et_time(date_str, start_str, year)
        end_et = _parse_et_time(date_str, end_str, year)
        if start_et and end_et and end_et > start_et:
            minutes = int((end_et - start_et).total_seconds() // 60)
    start_ms = end_ms - minutes * 60 * 1000
    return symbol, start_ms, end_ms


# ===========================================================================
# Replay state
# ===========================================================================

@dataclass
class BookState:
    """Per-asset book tracker. One per (market, token).

    We track full top-5 levels of depth so fill simulation can cap orders
    to real book size (crucial for longshot fade — unbounded depth
    produced unrealistic 5000-share jackpots in the first run).
    """
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    # Full top-5 levels (price, size), ordered best-first:
    bids: list[tuple[Decimal, Decimal]] = field(default_factory=list)
    asks: list[tuple[Decimal, Decimal]] = field(default_factory=list)
    last_trade_price: Decimal | None = None
    last_trade_size: Decimal | None = None
    last_trade_ts_ms: int = 0

    def mid(self) -> Decimal | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / Decimal("2")

    def available_at_or_below(self, limit: Decimal, side: str) -> Decimal:
        """Total depth available for a BUY up to limit (asks) or SELL
        down to limit (bids). Returns size in shares."""
        if side == "BUY":
            return sum((sz for px, sz in self.asks if px <= limit), Decimal("0"))
        else:
            return sum((sz for px, sz in self.bids if px >= limit), Decimal("0"))


@dataclass
class MarketTick:
    """Snapshot passed to each strategy on each tick."""
    market: MarketMeta
    now_ms: int
    t_to_res_ms: int              # end_ms - now_ms
    yes: BookState
    no: BookState
    cex_spot_now: Decimal | None
    cex_spot_start: Decimal | None   # spot at start_ms (for directional ref)
    # For Method 3: snapshot of all currently-open markets, keyed by symbol.
    # Populated only when strategies opt-in via `needs_cross_market=True`.
    cross: dict[str, "MarketTick"] = field(default_factory=dict)


@dataclass
class Order:
    market_id: str
    token: str              # "YES" or "NO"
    side: str               # "BUY" or "SELL"
    limit_price: Decimal
    size: Decimal
    placed_ms: int
    tag: str = ""           # optional free-form tag for analysis


@dataclass
class Fill:
    order: Order
    fill_price: Decimal
    fill_ms: int


# ===========================================================================
# Strategy protocol + three implementations
# ===========================================================================

class Strategy(Protocol):
    name: str
    needs_cross_market: bool

    def on_tick(self, tick: MarketTick) -> list[Order]: ...
    def on_fill(self, fill: Fill) -> None: ...
    def on_resolution(self, market: MarketMeta, yes_won: bool) -> None: ...


# ---------------------------------------------------------------------------
# Method 1 — OBI Scalp (directional, Bot E v1-like)
# ---------------------------------------------------------------------------

@dataclass
class OBIScalpStrategy:
    name: str = "obi_scalp"
    needs_cross_market: bool = False

    # Tuning matches current Bot E config; see bots/bot_e_btc_scalp/config.py.
    obi_threshold: Decimal = Decimal("0.10")
    entry_window_min_sec: int = 120
    entry_window_max_sec: int = 900
    trade_size_usd: Decimal = Decimal("5")
    depth_min_usd: Decimal = Decimal("5")

    # Per-market state: cumulative buy-size vs sell-size in OBI window.
    _buy_by_mkt: dict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))
    _sell_by_mkt: dict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))
    _entered: set[str] = field(default_factory=set)
    _last_trades: dict[str, list[tuple[int, Decimal, str]]] = field(default_factory=lambda: defaultdict(list))

    def record_trade(self, market_id: str, ts_ms: int, size: Decimal, side: str) -> None:
        self._last_trades[market_id].append((ts_ms, size, side))

    def _obi(self, market_id: str, now_ms: int, window_sec: int = 300) -> Decimal:
        cutoff = now_ms - window_sec * 1000
        trades = [t for t in self._last_trades[market_id] if t[0] >= cutoff]
        self._last_trades[market_id] = trades
        if not trades:
            return Decimal("0")
        buys = sum(t[1] for t in trades if t[2] == "BUY")
        sells = sum(t[1] for t in trades if t[2] == "SELL")
        total = buys + sells
        if total <= 0:
            return Decimal("0")
        return (buys - sells) / total

    def on_tick(self, tick: MarketTick) -> list[Order]:
        mid = tick.market.condition_id
        if mid in self._entered:
            return []
        t_sec = tick.t_to_res_ms // 1000
        if not (self.entry_window_min_sec <= t_sec <= self.entry_window_max_sec):
            return []
        obi = self._obi(mid, tick.now_ms)
        if abs(obi) < self.obi_threshold:
            return []
        # Direction: positive OBI → buy YES; negative → buy NO.
        side_token = "YES" if obi > 0 else "NO"
        book = tick.yes if side_token == "YES" else tick.no
        if book.best_ask is None or book.best_ask >= Decimal("0.99"):
            return []
        # Depth gate: best_ask * trade_size must be ≤ our depth_min trust floor
        # (simplified — real gate checks book depth at best. We use trade size
        # as a proxy: if size <= depth_min_usd, trust the quoted price).
        limit = book.best_ask
        size = self.trade_size_usd / limit
        self._entered.add(mid)
        return [Order(
            market_id=mid, token=side_token, side="BUY", limit_price=limit,
            size=size, placed_ms=tick.now_ms, tag=f"obi={obi:.3f}",
        )]

    def on_fill(self, fill: Fill) -> None:
        pass

    def on_resolution(self, market: MarketMeta, yes_won: bool) -> None:
        pass


# ---------------------------------------------------------------------------
# Method 2 — Longshot Fade (low-prob, high-payoff tail bet)
# ---------------------------------------------------------------------------

@dataclass
class LongshotFadeStrategy:
    """Longshot fade — buy ≤max_entry_price side in final N seconds.

    Session 17s 2026-04-20 (Grok round-2 feedback): added two refinements:
    * ``min_gap_bps`` — optional filter requiring the CEX spot to have moved
      at least this many bps from start_of_window. Below threshold the
      "cheap" side is just noise-priced; above threshold it's a structural
      reversal bet.
    * ``entry_seconds_before_res`` is now the SWEEP variable — callers can
      construct multiple instances with different values and compare.
    """
    name: str = "longshot_fade"
    needs_cross_market: bool = False

    # Enter only in final N seconds before resolution on the cheapest side.
    entry_seconds_before_res: int = 60
    max_entry_price: Decimal = Decimal("0.02")    # ≤2¢
    trade_size_usd: Decimal = Decimal("5")
    # Gap filter: |cex_spot_now - cex_spot_start| / cex_spot_start * 10_000
    # must be >= this (in basis points). 0 means no filter. Grok's
    # intuition: 20-25bps minimum to exclude noise-priced quotes.
    min_gap_bps: Decimal = Decimal("0")

    _entered: set[str] = field(default_factory=set)

    def _compute_gap_bps(self, tick: MarketTick) -> Decimal | None:
        if tick.cex_spot_now is None or tick.cex_spot_start is None:
            return None
        if tick.cex_spot_start <= 0:
            return None
        move = (tick.cex_spot_now - tick.cex_spot_start) / tick.cex_spot_start
        return abs(move) * Decimal("10000")

    def on_tick(self, tick: MarketTick) -> list[Order]:
        mid = tick.market.condition_id
        if mid in self._entered:
            return []
        t_sec = tick.t_to_res_ms // 1000
        if t_sec < 0 or t_sec > self.entry_seconds_before_res:
            return []
        # Gap filter.
        if self.min_gap_bps > 0:
            gap = self._compute_gap_bps(tick)
            if gap is None or gap < self.min_gap_bps:
                return []
        # Pick the cheapest side.
        candidates = []
        if tick.yes.best_ask is not None and tick.yes.best_ask <= self.max_entry_price:
            candidates.append(("YES", tick.yes.best_ask))
        if tick.no.best_ask is not None and tick.no.best_ask <= self.max_entry_price:
            candidates.append(("NO", tick.no.best_ask))
        if not candidates:
            return []
        token, limit = min(candidates, key=lambda x: x[1])
        size = self.trade_size_usd / max(limit, Decimal("0.001"))
        self._entered.add(mid)
        gap_tag = ""
        if self.min_gap_bps > 0:
            g = self._compute_gap_bps(tick)
            gap_tag = f"_gap{g:.0f}bps" if g is not None else ""
        return [Order(
            market_id=mid, token=token, side="BUY", limit_price=limit,
            size=size, placed_ms=tick.now_ms,
            tag=f"longshot_{token}_{limit}_t{t_sec}s{gap_tag}",
        )]

    def on_fill(self, fill: Fill) -> None:
        pass

    def on_resolution(self, market: MarketMeta, yes_won: bool) -> None:
        pass


# ---------------------------------------------------------------------------
# Method 3 — Cross-Asset Correlation Arb (market-neutral pair trade)
# ---------------------------------------------------------------------------

@dataclass
class CorrelationArbStrategy:
    name: str = "correlation_arb"
    needs_cross_market: bool = True

    # Divergence threshold in probability units (e.g. 0.08 = 8 percentage points).
    spread_threshold: Decimal = Decimal("0.08")
    # Only trade when both markets have at least this many ms left (more time
    # = more chance for spread to converge; too-close-to-res = noise).
    min_t_to_res_ms: int = 120_000    # 2 min
    trade_size_usd: Decimal = Decimal("5")
    # Pairs we compare. (a, b) trades long-a + short-b (via NO-side).
    pairs: tuple[tuple[str, str], ...] = (
        ("BTCUSDT", "ETHUSDT"),
        ("BTCUSDT", "SOLUSDT"),
        ("ETHUSDT", "SOLUSDT"),
    )

    # Per-pair-of-market state: have we already entered this pair?
    _entered_pairs: set[tuple[str, str]] = field(default_factory=set)

    def _pair_key(self, a_mkt: str, b_mkt: str) -> tuple[str, str]:
        return (a_mkt, b_mkt) if a_mkt < b_mkt else (b_mkt, a_mkt)

    def on_tick(self, tick: MarketTick) -> list[Order]:
        # Only fire when we have cross-market context.
        if not tick.cross:
            return []
        if tick.t_to_res_ms < self.min_t_to_res_ms:
            return []
        my_sym = tick.market.symbol
        my_yes_mid = tick.yes.mid()
        if my_yes_mid is None:
            return []
        orders: list[Order] = []
        for sym_a, sym_b in self.pairs:
            if my_sym not in (sym_a, sym_b):
                continue
            other_sym = sym_b if my_sym == sym_a else sym_a
            other_tick = tick.cross.get(other_sym)
            if other_tick is None or other_tick.t_to_res_ms < self.min_t_to_res_ms:
                continue
            other_yes_mid = other_tick.yes.mid()
            if other_yes_mid is None:
                continue
            # Only trade same-window-ish pairs (end times within 5 min).
            if abs(other_tick.market.end_ms - tick.market.end_ms) > 5 * 60 * 1000:
                continue
            spread = my_yes_mid - other_yes_mid      # my - other
            if abs(spread) < self.spread_threshold:
                continue
            key = self._pair_key(tick.market.condition_id, other_tick.market.condition_id)
            if key in self._entered_pairs:
                continue
            # My YES > other YES beyond threshold:
            #   my is overpriced → SHORT my YES via BUY my NO
            #   other is underpriced → LONG other YES via BUY other YES
            # But we only place orders on the tick's own market; the paired
            # order will fire on the other market's tick (it'll see the same
            # divergence).
            if spread > 0:
                # My YES is expensive → buy my NO.
                if tick.no.best_ask is not None and tick.no.best_ask < Decimal("0.99"):
                    size = self.trade_size_usd / tick.no.best_ask
                    orders.append(Order(
                        market_id=tick.market.condition_id, token="NO",
                        side="BUY", limit_price=tick.no.best_ask,
                        size=size, placed_ms=tick.now_ms,
                        tag=f"corr_short_{my_sym}_vs_{other_sym}_spread={spread:+.3f}",
                    ))
                    self._entered_pairs.add(key)
            else:
                # My YES is cheap → buy my YES.
                if tick.yes.best_ask is not None and tick.yes.best_ask < Decimal("0.99"):
                    size = self.trade_size_usd / tick.yes.best_ask
                    orders.append(Order(
                        market_id=tick.market.condition_id, token="YES",
                        side="BUY", limit_price=tick.yes.best_ask,
                        size=size, placed_ms=tick.now_ms,
                        tag=f"corr_long_{my_sym}_vs_{other_sym}_spread={spread:+.3f}",
                    ))
                    self._entered_pairs.add(key)
        return orders

    def on_fill(self, fill: Fill) -> None:
        pass

    def on_resolution(self, market: MarketMeta, yes_won: bool) -> None:
        pass


# ===========================================================================
# Replay engine
# ===========================================================================

@dataclass
class ReplayEngine:
    db_path: str
    strategies: list[Strategy]
    # Session 17s 2026-04-21: real-trade verification + fee model.
    # When require_real_trade=True, a simulated fill is only counted if
    # an actual last_trade_price event on the same token at price <= our
    # fill happened within ±verification_window_ms of the fill_ms.
    # This is the Kimi-flagged "phantom fill" defense. Off by default
    # for backwards compat; enable via CLI flag.
    require_real_trade: bool = False
    verification_window_ms: int = 90_000
    apply_fees: bool = False
    # Polymarket taker fee formula (Grok round-2): fee = shares × 0.072 × p × (1-p)
    fee_rate: Decimal = Decimal("0.072")
    # Collect one record per (strategy, market_id) for final reporting.
    fills: list[tuple[str, Fill]] = field(default_factory=list)
    rejected_fills: list[tuple[str, Fill]] = field(default_factory=list)
    resolutions: list[tuple[str, MarketMeta, bool]] = field(default_factory=list)

    def _has_real_trade_at_or_below(
        self, conn: sqlite3.Connection, token_id: str, fill_ms: int,
        price: Decimal, side: str,
    ) -> bool:
        """Check if a last_trade_price event exists on this token within
        `verification_window_ms` of fill_ms, at price ≤ ours (BUY) or ≥
        ours (SELL). Real evidence the market traded there."""
        lo = fill_ms - self.verification_window_ms
        hi = fill_ms + self.verification_window_ms
        rows = conn.execute(
            "SELECT payload_json FROM pm_events WHERE asset_id=? "
            "AND event_type='last_trade_price' "
            "AND received_at_ms>=? AND received_at_ms<=?",
            (token_id, lo, hi),
        ).fetchall()
        for r in rows:
            try:
                p = json.loads(r[0])
                px = Decimal(str(p.get("price", 0)))
                if px <= 0:
                    continue
                if side == "BUY" and px <= price:
                    return True
                if side == "SELL" and px >= price:
                    return True
            except Exception:
                continue
        return False

    def _fee_for_fill(self, price: Decimal, size: Decimal) -> Decimal:
        """Polymarket taker fee: C × 0.072 × p × (1-p) where C = shares."""
        if not self.apply_fees:
            return Decimal("0")
        return size * self.fee_rate * price * (Decimal("1") - price)

    def run(self, since_ms: int | None = None, until_ms: int | None = None,
            limit: int | None = None) -> None:
        """Replay all resolved markets in the window."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")

        markets = self._fetch_resolved_markets(conn, since_ms, until_ms, limit)
        log.info("loaded %d resolved markets for replay", len(markets))

        # Group by overlapping end-time bucket so Method 3 can see cross-market
        # state within each bucket.
        needs_cross = any(s.needs_cross_market for s in self.strategies)
        if needs_cross:
            buckets = self._group_by_time_bucket(markets, bucket_min=10)
            log.info("cross-market mode: %d time buckets", len(buckets))
            for bucket in buckets:
                self._replay_bucket(conn, bucket)
        else:
            for i, m in enumerate(markets):
                if i % 50 == 0:
                    log.info("market %d/%d", i, len(markets))
                self._replay_bucket(conn, [m])
        conn.close()

    def _fetch_resolved_markets(
        self, conn: sqlite3.Connection, since_ms, until_ms, limit,
    ) -> list[MarketMeta]:
        # Pick the latest metadata row per condition_id for token ids.
        cutoff_iso = datetime.now(timezone.utc).isoformat()
        where = ["end_date_iso IS NOT NULL", "end_date_iso < ?"]
        params: list[Any] = [cutoff_iso]
        if since_ms:
            since_iso = datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc).isoformat()
            where.append("end_date_iso >= ?")
            params.append(since_iso)
        if until_ms:
            until_iso = datetime.fromtimestamp(until_ms / 1000, tz=timezone.utc).isoformat()
            where.append("end_date_iso < ?")
            params.append(until_iso)
        sql = (
            "SELECT condition_id, question, end_date_iso, yes_token_id, no_token_id "
            "FROM markets WHERE " + " AND ".join(where) + " "
            "GROUP BY condition_id HAVING scan_at_ms = MAX(scan_at_ms) "
            "ORDER BY end_date_iso DESC"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = conn.execute(sql, params).fetchall()
        out: list[MarketMeta] = []
        for r in rows:
            parsed = parse_market_window(r["question"], r["end_date_iso"])
            if parsed is None:
                continue
            symbol, start_ms, end_ms = parsed
            if not (r["yes_token_id"] and r["no_token_id"]):
                continue
            out.append(MarketMeta(
                condition_id=r["condition_id"], question=r["question"],
                symbol=symbol, yes_token_id=str(r["yes_token_id"]),
                no_token_id=str(r["no_token_id"]),
                start_ms=start_ms, end_ms=end_ms,
            ))
        return out

    def _group_by_time_bucket(
        self, markets: list[MarketMeta], bucket_min: int = 10,
    ) -> list[list[MarketMeta]]:
        bucket_ms = bucket_min * 60 * 1000
        by_bucket: dict[int, list[MarketMeta]] = defaultdict(list)
        for m in markets:
            by_bucket[m.end_ms // bucket_ms].append(m)
        # Return buckets that have ≥2 markets (correlation arb needs pairs);
        # solo-market buckets still need processing for Methods 1/2.
        return list(by_bucket.values())

    def _cex_spot(self, conn: sqlite3.Connection, symbol: str, at_ms: int) -> Decimal | None:
        """Spot price: last CEX trade at or before at_ms within 60s."""
        r = conn.execute(
            "SELECT price FROM cex_trades WHERE symbol=? AND received_at_ms<=? "
            "AND received_at_ms>=? ORDER BY received_at_ms DESC LIMIT 1",
            (symbol, at_ms, at_ms - 60_000),
        ).fetchone()
        return Decimal(str(r["price"])) if r else None

    def _determine_outcome(
        self, conn: sqlite3.Connection, market: MarketMeta,
    ) -> bool | None:
        """Return True if YES won, False if NO, None if indeterminate."""
        start = self._cex_spot(conn, market.symbol, market.start_ms)
        end = self._cex_spot(conn, market.symbol, market.end_ms)
        if start is None or end is None:
            return None
        return end > start  # Up = YES

    def _replay_bucket(self, conn: sqlite3.Connection, markets: list[MarketMeta]) -> None:
        # Per-market book state per token
        state: dict[tuple[str, str], BookState] = {}
        for m in markets:
            state[(m.condition_id, "YES")] = BookState()
            state[(m.condition_id, "NO")] = BookState()

        # Pre-determine outcomes for all markets in the bucket.
        outcomes: dict[str, bool] = {}
        for m in markets:
            o = self._determine_outcome(conn, m)
            if o is not None:
                outcomes[m.condition_id] = o

        # Token-id → (condition_id, "YES"/"NO") map for event routing.
        token_to_key: dict[str, tuple[str, str]] = {}
        for m in markets:
            token_to_key[m.yes_token_id] = (m.condition_id, "YES")
            token_to_key[m.no_token_id] = (m.condition_id, "NO")

        earliest_start = min(m.start_ms for m in markets)
        latest_end = max(m.end_ms for m in markets)

        # Query all pm_events for the bucket's markets in time order.
        sub_ids = []  # we'll use asset_id instead (more reliable than sub_id)
        asset_ids = list(token_to_key.keys())
        if not asset_ids:
            return
        placeholders = ",".join("?" for _ in asset_ids)
        sql = (
            f"SELECT received_at_ms, asset_id, event_type, payload_json "
            f"FROM pm_events WHERE asset_id IN ({placeholders}) "
            f"AND received_at_ms BETWEEN ? AND ? "
            f"ORDER BY received_at_ms"
        )
        params = [*asset_ids, earliest_start, latest_end]
        cur = conn.execute(sql, params)

        # Track open orders per strategy, to simulate fills.
        open_orders: list[tuple[int, Order]] = []   # (strategy_idx, Order)
        last_tick_ms: dict[str, int] = defaultdict(int)
        TICK_GAP_MS = 1000   # throttle per-market ticks to 1 Hz

        # We need per-strategy independent fill tracking.
        # Tracks filled orders so we don't double-fill.
        for row in cur:
            ts_ms = row["received_at_ms"]
            asset_id = row["asset_id"] or ""
            et = row["event_type"]
            if asset_id not in token_to_key:
                # Some price_change events have asset_id=condition_id; skip
                # those (we get the same data per-asset).
                continue
            cond_id, token = token_to_key[asset_id]
            bs = state[(cond_id, token)]

            try:
                payload = json.loads(row["payload_json"])
            except Exception:
                continue

            if et == "best_bid_ask":
                b = payload.get("best_bid")
                a = payload.get("best_ask")
                if b is not None and a is not None:
                    bs.best_bid = Decimal(str(b))
                    bs.best_ask = Decimal(str(a))
            elif et == "book":
                bids = payload.get("bids") or []
                asks = payload.get("asks") or []
                # Parse to (price, size) tuples, sort best-first, keep top 5.
                b_tuples = sorted(
                    [(Decimal(str(x["price"])), Decimal(str(x["size"])))
                     for x in bids if x.get("price") is not None],
                    key=lambda t: t[0], reverse=True,
                )[:5]
                a_tuples = sorted(
                    [(Decimal(str(x["price"])), Decimal(str(x["size"])))
                     for x in asks if x.get("price") is not None],
                    key=lambda t: t[0],
                )[:5]
                if b_tuples:
                    bs.bids = b_tuples
                    bs.best_bid = b_tuples[0][0]
                if a_tuples:
                    bs.asks = a_tuples
                    bs.best_ask = a_tuples[0][0]
            elif et == "price_change":
                for pc in payload.get("price_changes") or []:
                    pc_asset = str(pc.get("asset_id") or "")
                    if pc_asset in token_to_key:
                        pcc, pct = token_to_key[pc_asset]
                        pbs = state[(pcc, pct)]
                        bb = pc.get("best_bid")
                        ba = pc.get("best_ask")
                        if bb is not None: pbs.best_bid = Decimal(str(bb))
                        if ba is not None: pbs.best_ask = Decimal(str(ba))
                        # Record trade activity for OBI.
                        tsize = pc.get("size")
                        tside = pc.get("side") or ""
                        if tsize:
                            for i, s in enumerate(self.strategies):
                                if isinstance(s, OBIScalpStrategy):
                                    s.record_trade(pcc, ts_ms, Decimal(str(tsize)), tside)
            elif et == "last_trade_price":
                bs.last_trade_price = Decimal(str(payload.get("price", 0)))
                bs.last_trade_size = Decimal(str(payload.get("size", 0)))
                bs.last_trade_ts_ms = ts_ms
                # OBI trade record (more trustworthy than price_change.size).
                side_str = payload.get("side") or ""
                for s in self.strategies:
                    if isinstance(s, OBIScalpStrategy):
                        s.record_trade(cond_id, ts_ms, bs.last_trade_size, side_str)

            # Throttle per-market tick callbacks.
            if ts_ms - last_tick_ms[cond_id] < TICK_GAP_MS:
                continue
            last_tick_ms[cond_id] = ts_ms

            # Build tick for the market whose event just landed.
            market = next(m for m in markets if m.condition_id == cond_id)
            yes_bs = state[(cond_id, "YES")]
            no_bs = state[(cond_id, "NO")]
            cex_now = self._cex_spot(conn, market.symbol, ts_ms)
            cex_start = self._cex_spot(conn, market.symbol, market.start_ms)
            tick = MarketTick(
                market=market, now_ms=ts_ms,
                t_to_res_ms=max(0, market.end_ms - ts_ms),
                yes=yes_bs, no=no_bs, cex_spot_now=cex_now, cex_spot_start=cex_start,
            )
            # Cross-market snapshot for Method 3.
            needs_cross = any(s.needs_cross_market for s in self.strategies)
            if needs_cross:
                cross: dict[str, MarketTick] = {}
                for om in markets:
                    if om.condition_id == cond_id:
                        continue
                    o_yes = state[(om.condition_id, "YES")]
                    o_no = state[(om.condition_id, "NO")]
                    cross[om.symbol] = MarketTick(
                        market=om, now_ms=ts_ms,
                        t_to_res_ms=max(0, om.end_ms - ts_ms),
                        yes=o_yes, no=o_no,
                        cex_spot_now=None, cex_spot_start=None,
                    )
                tick.cross = cross

            # Dispatch + collect orders.
            for si, strat in enumerate(self.strategies):
                new_orders = strat.on_tick(tick)
                for o in new_orders:
                    open_orders.append((si, o))

            # Simulate fills (depth-aware). Walk book levels: BUY consumes
            # asks best→worse up to limit; SELL consumes bids best→worse
            # down to limit. Cap fill size at available depth. Compute
            # volume-weighted avg fill price. If no depth available, order
            # stays open.
            still_open: list[tuple[int, Order]] = []
            for si, o in open_orders:
                if o.market_id != cond_id:
                    still_open.append((si, o))
                    continue
                obs = state[(o.market_id, o.token)]
                levels = obs.asks if o.side == "BUY" else obs.bids
                # Filter levels within our limit.
                if o.side == "BUY":
                    ok_levels = [(p, s) for p, s in levels if p <= o.limit_price]
                else:
                    ok_levels = [(p, s) for p, s in levels if p >= o.limit_price]
                if not ok_levels:
                    still_open.append((si, o))
                    continue
                # Walk levels consuming up to o.size.
                filled = Decimal("0")
                cost_sum = Decimal("0")
                for lp, ls in ok_levels:
                    take = min(ls, o.size - filled)
                    if take <= 0:
                        break
                    filled += take
                    cost_sum += take * lp
                    if filled >= o.size:
                        break
                if filled <= 0:
                    still_open.append((si, o))
                    continue
                avg_fill = cost_sum / filled
                # If partial fill (less than requested size), keep the
                # order alive at remaining size on the next tick.
                filled_order = Order(
                    market_id=o.market_id, token=o.token, side=o.side,
                    limit_price=o.limit_price, size=filled,
                    placed_ms=o.placed_ms, tag=o.tag,
                )
                fill = Fill(order=filled_order, fill_price=avg_fill, fill_ms=ts_ms)
                # Real-trade verification: only count this fill if an actual
                # trade at or below our price happened within the window.
                if self.require_real_trade:
                    ok = self._has_real_trade_at_or_below(
                        conn, o.token_id if hasattr(o, "token_id") else "",
                        ts_ms, avg_fill, o.side,
                    )
                    # We don't have token_id on Order. Reconstruct from market.
                    market = next((m for m in markets if m.condition_id == o.market_id), None)
                    if market is not None:
                        tok_id = market.yes_token_id if o.token == "YES" else market.no_token_id
                        ok = self._has_real_trade_at_or_below(
                            conn, tok_id, ts_ms, avg_fill, o.side,
                        )
                    if not ok:
                        # Phantom fill. Record separately for reporting.
                        self.rejected_fills.append((self.strategies[si].name, fill))
                        # Order stays unfilled; keep alive until book changes.
                        still_open.append((si, o))
                        continue
                self.strategies[si].on_fill(fill)
                self.fills.append((self.strategies[si].name, fill))
                if filled < o.size:
                    # Partial fill — keep remainder open.
                    remainder = Order(
                        market_id=o.market_id, token=o.token, side=o.side,
                        limit_price=o.limit_price, size=o.size - filled,
                        placed_ms=o.placed_ms, tag=o.tag + "|partial_cont",
                    )
                    still_open.append((si, remainder))
            open_orders = still_open

        # At end of replay window, resolve each market: notify strategies.
        for m in markets:
            if m.condition_id not in outcomes:
                continue
            yes_won = outcomes[m.condition_id]
            for s in self.strategies:
                s.on_resolution(m, yes_won)
            self.resolutions.append((m.condition_id, m, yes_won))


# ===========================================================================
# Report
# ===========================================================================

@dataclass
class Report:
    strategy: str
    n_fills: int
    n_closed: int
    wins: int
    losses: int
    total_pnl: Decimal
    total_cost: Decimal
    winners_avg_pnl: Decimal
    losers_avg_pnl: Decimal

    def print_row(self) -> str:
        wr = (self.wins / self.n_closed * 100) if self.n_closed else 0
        roi = (self.total_pnl / self.total_cost * 100) if self.total_cost > 0 else Decimal("0")
        return (
            f"{self.strategy:18s} "
            f"fills={self.n_fills:4d} closed={self.n_closed:4d} "
            f"W/L={self.wins:3d}/{self.losses:3d} WR={wr:5.1f}% "
            f"P&L=${self.total_pnl:+8.2f} cost=${self.total_cost:7.2f} "
            f"ROI={roi:+6.2f}% "
            f"avgW=${self.winners_avg_pnl:+6.2f} avgL=${self.losers_avg_pnl:+6.2f}"
        )


def compute_reports(engine: ReplayEngine) -> list[Report]:
    # Group fills by strategy.
    by_strat: dict[str, list[Fill]] = defaultdict(list)
    for sname, fill in engine.fills:
        by_strat[sname].append(fill)
    # Lookup outcome by condition_id.
    outcome_by_mid = {m.condition_id: won for _mid, m, won in engine.resolutions}

    reports: list[Report] = []
    for strat in engine.strategies:
        fills = by_strat.get(strat.name, [])
        wins = losses = 0
        total_pnl = Decimal("0")
        total_cost = Decimal("0")
        winner_pnls: list[Decimal] = []
        loser_pnls: list[Decimal] = []
        n_closed = 0
        for f in fills:
            o = f.order
            won = outcome_by_mid.get(o.market_id)
            if won is None:
                # Indeterminate market — not closed for accounting purposes.
                continue
            # Settlement: if we bought YES and YES won → $1 * size; else $0.
            if o.token == "YES":
                settle = Decimal("1") if won else Decimal("0")
            else:
                settle = Decimal("0") if won else Decimal("1")
            proceeds = settle * o.size
            cost = f.fill_price * o.size
            fee = engine._fee_for_fill(f.fill_price, o.size)
            pnl = proceeds - cost - fee
            total_pnl += pnl
            total_cost += cost
            n_closed += 1
            if pnl > 0:
                wins += 1
                winner_pnls.append(pnl)
            else:
                losses += 1
                loser_pnls.append(pnl)
        reports.append(Report(
            strategy=strat.name,
            n_fills=len(fills),
            n_closed=n_closed,
            wins=wins, losses=losses,
            total_pnl=total_pnl,
            total_cost=total_cost,
            winners_avg_pnl=(sum(winner_pnls) / len(winner_pnls)) if winner_pnls else Decimal("0"),
            losers_avg_pnl=(sum(loser_pnls) / len(loser_pnls)) if loser_pnls else Decimal("0"),
        ))
    return reports


# ===========================================================================
# CLI
# ===========================================================================

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--db", default="data/bot_e_recorder.db")
    p.add_argument("--since", help="ISO date, e.g. 2026-04-15")
    p.add_argument("--until", help="ISO date, e.g. 2026-04-19")
    p.add_argument("--limit", type=int, default=None, help="Max markets to replay")
    p.add_argument(
        "--strategies", nargs="+",
        default=["obi_scalp", "longshot_fade", "correlation_arb"],
        choices=["obi_scalp", "longshot_fade", "correlation_arb"],
    )
    p.add_argument("--log-level", default="INFO")
    p.add_argument("--out-csv", help="Write per-fill CSV to this path")
    # Session 17s Grok round-2 refinements:
    p.add_argument(
        "--longshot-sweep", action="store_true",
        help="Run longshot_fade at t-N seconds for N in {60,30,15,10,5} and "
             "across gap-bps filter in {0,10,20,30}; prints a comparison matrix.",
    )
    p.add_argument(
        "--longshot-entry-seconds", type=int, default=60,
        help="Override entry_seconds_before_res for longshot_fade (default 60).",
    )
    p.add_argument(
        "--longshot-min-gap-bps", type=Decimal, default=Decimal("0"),
        help="Minimum |gap| from market start for longshot entry (bps). 0 = no filter.",
    )
    # Session 17s 2026-04-21: phantom-fill + fee realism flags.
    p.add_argument(
        "--require-real-trade", action="store_true",
        help="Only count fills where a last_trade_price event at ≤ our fill "
             "price actually happened within ±90s on the same token. Rejects "
             "phantom fills (Kimi-flagged failure mode).",
    )
    p.add_argument(
        "--verification-window-ms", type=int, default=90_000,
        help="±window around fill_ms to search for a validating real trade.",
    )
    p.add_argument(
        "--apply-fees", action="store_true",
        help="Subtract Polymarket taker fee (C × 0.072 × p × (1-p)) per fill.",
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    since_ms = None
    until_ms = None
    if args.since:
        since_ms = int(datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc).timestamp() * 1000)
    if args.until:
        until_ms = int(datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc).timestamp() * 1000)

    if args.longshot_sweep:
        # Session 17s Grok round-2: sweep (t-seconds × gap-bps) to find
        # regime where longshot edge concentrates.
        sweep_entry_secs = [60, 30, 15, 10, 5]
        sweep_gap_bps = [Decimal("0"), Decimal("10"), Decimal("20"), Decimal("30")]
        strategies = []
        for t_sec in sweep_entry_secs:
            for gap in sweep_gap_bps:
                s = LongshotFadeStrategy(
                    entry_seconds_before_res=t_sec, min_gap_bps=gap,
                )
                s.name = f"longshot_t{t_sec}s_gap{int(gap)}bps"
                strategies.append(s)
    else:
        strat_map: dict[str, Strategy] = {
            "obi_scalp": OBIScalpStrategy(),
            "longshot_fade": LongshotFadeStrategy(
                entry_seconds_before_res=args.longshot_entry_seconds,
                min_gap_bps=args.longshot_min_gap_bps,
            ),
            "correlation_arb": CorrelationArbStrategy(),
        }
        strategies = [strat_map[n] for n in args.strategies]

    engine = ReplayEngine(
        db_path=args.db, strategies=strategies,
        require_real_trade=args.require_real_trade,
        verification_window_ms=args.verification_window_ms,
        apply_fees=args.apply_fees,
    )
    log.info("starting replay strategies=%s", [s.name for s in strategies])
    t0 = time.time()
    engine.run(since_ms=since_ms, until_ms=until_ms, limit=args.limit)
    elapsed = time.time() - t0
    log.info("replay done in %.1fs — %d fills, %d resolutions",
             elapsed, len(engine.fills), len(engine.resolutions))

    print("\n" + "=" * 130)
    flags = []
    if engine.require_real_trade:
        flags.append("real-trade-verified")
    if engine.apply_fees:
        flags.append("fees-applied")
    flag_str = f" [{', '.join(flags)}]" if flags else ""
    print(f"BACKTEST RESULTS{flag_str} "
          f"({len(engine.resolutions)} markets replayed in {elapsed:.1f}s, "
          f"{len(engine.fills)} fills accepted, {len(engine.rejected_fills)} phantom-rejected)")
    print("=" * 130)
    reports = compute_reports(engine)
    for r in reports:
        print(r.print_row())
    print("=" * 130)

    if args.out_csv:
        import csv
        with open(args.out_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["strategy", "market_id", "token", "side",
                        "limit_price", "fill_price", "size", "placed_ms",
                        "fill_ms", "tag", "outcome_yes_won"])
            outcome_by_mid = {mid: won for mid, _m, won in engine.resolutions}
            for sname, fill in engine.fills:
                w.writerow([
                    sname, fill.order.market_id, fill.order.token,
                    fill.order.side, fill.order.limit_price, fill.fill_price,
                    fill.order.size, fill.order.placed_ms, fill.fill_ms,
                    fill.order.tag, outcome_by_mid.get(fill.order.market_id, ""),
                ])
        log.info("wrote per-fill CSV to %s", args.out_csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
