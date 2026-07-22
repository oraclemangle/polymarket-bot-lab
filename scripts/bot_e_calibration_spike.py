"""Bot E Phase 0d calibration spike.

Replays the recorder DB, reconstructs OBI signals from last_trade_price events,
determines market outcomes from CEX price data, and computes per-bucket
calibration statistics.

Produces:
  data/bot_e_calibration.json   — GO file (gate for paper trading)
  data/bot-e-calibration-report.md  — human-readable summary

Resolution detection method:
  For "Up or Down" markets, use CEX BTC/ETH/SOL price at market START and END
  to determine the outcome. YES = price went UP over the window. This works for
  all resolved markets regardless of whether post-expiry pm_events exist.

  Market start time is parsed from the question text (e.g. "5:00AM-5:15AM ET").
  ET is assumed EDT (UTC-4) for April dates.

  Non-"Up or Down" markets (e.g. "Bitcoin above X") are excluded from calibration
  since they require a different outcome model.

OBI reconstruction:
  Uses last_trade_price events (size field). Rolling 120-second window.
  Minimum 2 trades, minimum $1 volume.

Entry window gate:
  Only signals fired in the t-10min to t-5min window before resolution are
  counted (per ADR-022 spec).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "bot_e_recorder.db"
OUT_JSON = REPO / "data" / "bot_e_calibration.json"
OUT_MD = REPO / "data" / "bot-e-calibration-report.md"

# ---------------------------------------------------------------------------
# Config (mirrors bots/bot_e_btc_scalp/config.py defaults)
# ---------------------------------------------------------------------------
OBI_WINDOW_SEC = 120.0
OBI_THRESHOLD_DEFAULT = 0.20
OBI_MIN_TRADES = 2
OBI_MIN_VOLUME = 1.0
ENTRY_WINDOW_MIN_SEC = 300.0   # t-5min
ENTRY_WINDOW_MAX_SEC = 600.0   # t-10min
REGIME_CHOPPINESS_MAX = 0.65
LOOKBACK_ENV = "BOT_E_CALIBRATION_LOOKBACK_HOURS"

# ET offset: April = EDT = UTC-4
ET_OFFSET_HOURS = 4

# Calibration pass thresholds
MIN_SIGNALS_FOR_GO = 200
MIN_REALISED_WR_FOR_GO = 0.52
MAX_ECE_FOR_GO = 0.10
# Phase 4 audit 2026-04-17: maker-fill + adverse-selection gates.
MIN_FILL_RATE_FOR_GO = 0.30
MAX_ADVERSE_RATE_FOR_GO = 0.60

# OBI bucket boundaries for analysis
OBI_BUCKETS = [
    (0.20, 0.30, "0.20-0.30"),
    (0.30, 0.40, "0.30-0.40"),
    (0.40, 0.50, "0.40-0.50"),
    (0.50, 0.65, "0.50-0.65"),
    (0.65, 1.01, "0.65+"),
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SubState:
    sub_id: str
    yes_token_id: str | None = None
    no_token_id: str | None = None
    trades: list[tuple[int, str, float]] = field(default_factory=list)

    def prune(self, now_ms: int, window_ms: int) -> None:
        cutoff = now_ms - window_ms
        self.trades = [t for t in self.trades if t[0] >= cutoff]

    def compute_obi(self, now_ms: int) -> tuple[float | None, int, float]:
        window_ms = int(OBI_WINDOW_SEC * 1000)
        self.prune(now_ms, window_ms)
        n = len(self.trades)
        if n < OBI_MIN_TRADES or not self.yes_token_id:
            return None, n, 0.0
        yes_vol = sum(sz for _, a, sz in self.trades if a == self.yes_token_id)
        no_vol = sum(sz for _, a, sz in self.trades if a == self.no_token_id)
        total = yes_vol + no_vol
        if total < OBI_MIN_VOLUME:
            return None, n, total
        obi = (yes_vol - no_vol) / total
        return obi, n, total


@dataclass
class MarketMeta:
    condition_id: str
    question: str
    end_date_iso: str
    yes_token_id: str | None
    no_token_id: str | None
    start_ms: int | None = None
    end_ms: int | None = None
    is_up_down: bool = False
    symbol: str | None = None  # "BTC", "ETH", "SOL"
    cex_symbol: str | None = None  # "BTCUSDT", "ETHUSDT", "SOLUSDT"

    def _parse(self) -> None:
        if self.end_ms is not None:
            return
        try:
            dt = datetime.fromisoformat(self.end_date_iso)
            self.end_ms = int(dt.timestamp() * 1000)
        except Exception:
            self.end_ms = None

        # Parse start time from question
        m = re.search(r"(\d+:\d+(?:AM|PM))-(\d+:\d+(?:AM|PM)) ET", self.question)
        if m:
            self.is_up_down = True
            start_str = m.group(1)
            try:
                # April = EDT = UTC-4
                base_date = datetime.fromisoformat(self.end_date_iso).date()
                start_naive = datetime.strptime(start_str, "%I:%M%p")
                start_dt = datetime(
                    base_date.year, base_date.month, base_date.day,
                    start_naive.hour, start_naive.minute,
                    tzinfo=timezone.utc
                ) + timedelta(hours=ET_OFFSET_HOURS)
                self.start_ms = int(start_dt.timestamp() * 1000)
            except Exception:
                self.start_ms = None

        if "Bitcoin" in self.question or "bitcoin" in self.question:
            self.symbol = "BTC"
            self.cex_symbol = "BTCUSDT"
        elif "Ethereum" in self.question or "ethereum" in self.question:
            self.symbol = "ETH"
            self.cex_symbol = "ETHUSDT"
        elif "Solana" in self.question or "solana" in self.question:
            self.symbol = "SOL"
            self.cex_symbol = "SOLUSDT"

    def end_timestamp_ms(self) -> int | None:
        self._parse()
        return self.end_ms

    def start_timestamp_ms(self) -> int | None:
        self._parse()
        return self.start_ms


@dataclass
class SignalObs:
    sub_id: str
    obi: float
    abs_obi: float
    side: str           # "BUY_YES" | "BUY_NO"
    ts_ms: int
    end_ms: int
    min_to_expiry: float
    outcome_yes_won: bool | None = None
    # Phase 4 audit 2026-04-17: realistic maker-fill simulation fields.
    asset_id_at_signal: str | None = None     # YES token id if BUY_YES, NO token id if BUY_NO
    signal_price: float | None = None          # last-trade price on target asset at signal time
    maker_limit: float | None = None           # limit we'd have placed (signal_price - 10bps)
    filled: bool = False                       # did the book cross our limit within fill_timeout?
    fill_ts_ms: int | None = None
    fill_price: float | None = None
    # Adverse-selection: price on the same asset N seconds after fill.
    midpoint_after_fill: float | None = None
    moved_against: bool | None = None


# ---------------------------------------------------------------------------
# Step 1: Load market metadata
# ---------------------------------------------------------------------------

def load_markets(conn: sqlite3.Connection) -> dict[str, MarketMeta]:
    """Load one canonical row per condition_id (latest scan)."""
    rows = conn.execute("""
        SELECT m.condition_id, m.question, m.yes_token_id, m.no_token_id, m.end_date_iso
        FROM markets m
        INNER JOIN (
            SELECT condition_id, MAX(scan_at_ms) AS latest
            FROM markets GROUP BY condition_id
        ) latest ON m.condition_id = latest.condition_id
                   AND m.scan_at_ms = latest.latest
        GROUP BY m.condition_id
    """).fetchall()
    metas = {}
    for cond, q, yt, nt, end in rows:
        meta = MarketMeta(
            condition_id=cond, question=q,
            end_date_iso=end or "",
            yes_token_id=yt, no_token_id=nt,
        )
        meta._parse()
        metas[cond] = meta
    return metas


def build_token_to_market(metas: dict[str, MarketMeta]) -> dict[str, MarketMeta]:
    t2m = {}
    for m in metas.values():
        if m.yes_token_id:
            t2m[m.yes_token_id] = m
        if m.no_token_id:
            t2m[m.no_token_id] = m
    return t2m


def build_sub_to_market(
    conn: sqlite3.Connection,
    token_to_market: dict[str, MarketMeta],
    *,
    since_ms: int | None = None,
    until_ms: int | None = None,
) -> dict[str, MarketMeta]:
    """Map subscription_id → MarketMeta via asset_id lookup."""
    sub_to_meta: dict[str, MarketMeta] = {}
    where = ["event_type = 'last_trade_price'", "asset_id IS NOT NULL"]
    params: list[int] = []
    if since_ms is not None:
        where.append("received_at_ms >= ?")
        params.append(since_ms)
    if until_ms is not None:
        where.append("received_at_ms <= ?")
        params.append(until_ms)
    rows = conn.execute(
        """
        SELECT subscription_id, asset_id
        FROM pm_events
        WHERE """ + " AND ".join(where) + """
        GROUP BY subscription_id, asset_id
        """,
        params,
    ).fetchall()
    for sub_id, asset_id in rows:
        if sub_id in sub_to_meta:
            continue
        meta = token_to_market.get(str(asset_id))
        if meta:
            sub_to_meta[sub_id] = meta
    return sub_to_meta


# ---------------------------------------------------------------------------
# Step 2: Determine resolution outcomes via CEX prices
# ---------------------------------------------------------------------------

def load_cex_prices(
    conn: sqlite3.Connection,
    symbols: list[str],
    *,
    since_ms: int | None = None,
    until_ms: int | None = None,
) -> dict[str, list[tuple[int, float]]]:
    """Load CEX trade prices per symbol as (trade_time_ms, price) list."""
    result = {}
    for sym in symbols:
        where = ["symbol = ?"]
        params: list[object] = [sym]
        if since_ms is not None:
            where.append("trade_time_ms >= ?")
            params.append(since_ms)
        if until_ms is not None:
            where.append("trade_time_ms <= ?")
            params.append(until_ms)
        rows = conn.execute(
            """
            SELECT trade_time_ms, price FROM cex_trades
            WHERE """ + " AND ".join(where) + """
            ORDER BY trade_time_ms
            """,
            params,
        ).fetchall()
        result[sym] = rows
    return result


def price_at(
    timeline: list[tuple[int, float]],
    target_ms: int,
    window_ms: int = 30_000,
) -> float | None:
    """Return average price in (target_ms ± window_ms/2) from a sorted timeline."""
    lo = target_ms - window_ms // 2
    hi = target_ms + window_ms // 2
    prices = [p for t, p in timeline if lo <= t <= hi]
    if not prices:
        return None
    return sum(prices) / len(prices)


def detect_resolutions_via_cex(
    metas: dict[str, MarketMeta],
    cex_prices: dict[str, list[tuple[int, float]]],
    db_start_ms: int,
    db_end_ms: int,
) -> dict[str, bool]:
    """Returns {condition_id: True=YES_won (price went UP), False=NO_won}.

    Only processes "Up or Down" markets that resolved within the data window.
    Markets that resolve after db_end_ms are excluded (no outcome available).
    """
    outcomes: dict[str, bool] = {}

    for cond, meta in metas.items():
        if not meta.is_up_down:
            continue
        if not meta.cex_symbol:
            continue
        end_ms = meta.end_timestamp_ms()
        start_ms = meta.start_timestamp_ms()
        if end_ms is None or start_ms is None:
            continue

        # Only include markets that resolved before our data ends
        if end_ms > db_end_ms:
            continue

        timeline = cex_prices.get(meta.cex_symbol, [])
        if not timeline:
            continue

        p_start = price_at(timeline, start_ms)
        p_end = price_at(timeline, end_ms)

        if p_start is None or p_end is None:
            continue

        yes_won = p_end > p_start  # YES = price went UP
        outcomes[cond] = yes_won

    return outcomes


# ---------------------------------------------------------------------------
# Step 3: Replay pm_events to build OBI signals
# ---------------------------------------------------------------------------

def replay_signals(
    conn: sqlite3.Connection,
    token_to_market: dict[str, MarketMeta],
    sub_to_meta: dict[str, MarketMeta],
    *,
    entry_window_min_sec: float | None = None,
    entry_window_max_sec: float | None = None,
    since_ms: int | None = None,
    until_ms: int | None = None,
) -> tuple[list[SignalObs], int]:
    """Stream last_trade_price events chronologically, build rolling OBI,
    emit signals whenever abs(OBI) > threshold in the entry window.

    OQ-035 (audit 2026-04-18): entry_window_min_sec / _max_sec are now
    per-call args so `bot_e_fit_model.py --horizon-sweep` can actually vary
    the extraction window per horizon. Default preserves pre-fix behaviour
    (5-10min t-to-expiry).

    Returns (signals, n_events_processed).
    """
    win_min = entry_window_min_sec if entry_window_min_sec is not None else ENTRY_WINDOW_MIN_SEC
    win_max = entry_window_max_sec if entry_window_max_sec is not None else ENTRY_WINDOW_MAX_SEC
    states: dict[str, SubState] = {}
    signals: list[SignalObs] = []
    last_fired: dict[str, int] = {}  # sub_id -> ts_ms of last signal (30s cooldown)
    n_processed = 0

    # E-2 prep (2026-04-26): optional time-window filter at SQL level so
    # downstream extractors can skip walking the full 16+ GB recorder DB
    # when they only want a slice. Defaults preserve the original
    # full-DB behaviour used by the in-tree calibration spike.
    where = ["event_type IN ('last_trade_price', 'reconnect')"]
    params: list[int] = []
    if since_ms is not None:
        where.append("received_at_ms >= ?")
        params.append(since_ms)
    if until_ms is not None:
        where.append("received_at_ms <= ?")
        params.append(until_ms)
    rows = conn.execute(
        "SELECT received_at_ms, subscription_id, event_type, asset_id, "
        "payload_json FROM pm_events WHERE "
        + " AND ".join(where)
        + " ORDER BY received_at_ms",
        params,
    )

    for ts_ms, sub_id, etype, asset_id, raw_json in rows:
        n_processed += 1

        if etype == "reconnect":
            states.pop(sub_id, None)
            continue

        # Get market metadata for this subscription
        meta = sub_to_meta.get(sub_id)
        if meta is None:
            # Try to learn from asset_id
            if asset_id and str(asset_id) in token_to_market:
                meta = token_to_market[str(asset_id)]
                sub_to_meta[sub_id] = meta

        if meta is None or not meta.is_up_down:
            continue

        end_ms = meta.end_timestamp_ms()
        if end_ms is None:
            continue

        # Entry window gate — per-horizon override via replay_signals kwargs.
        sec_to_expiry = (end_ms - ts_ms) / 1000.0
        if not (win_min <= sec_to_expiry <= win_max):
            continue

        st = states.setdefault(sub_id, SubState(sub_id=sub_id))
        if st.yes_token_id is None:
            st.yes_token_id = meta.yes_token_id
            st.no_token_id = meta.no_token_id

        try:
            p = json.loads(raw_json) if raw_json else {}
            size = float(p.get("size", 0) or 0)
            trade_price = float(p.get("price", 0) or 0)
        except Exception:
            continue

        if size <= 0 or not asset_id:
            continue

        st.trades.append((ts_ms, str(asset_id), size))
        # Phase 4: track most recent trade price on each asset for fill-sim anchor.
        if not hasattr(st, "_last_price_yes"):
            st._last_price_yes = None
            st._last_price_no = None
        if asset_id == st.yes_token_id and trade_price > 0:
            st._last_price_yes = trade_price
        elif asset_id == st.no_token_id and trade_price > 0:
            st._last_price_no = trade_price

        # Compute OBI
        obi, n_trades, total_vol = st.compute_obi(ts_ms)
        if obi is None or abs(obi) < OBI_THRESHOLD_DEFAULT:
            continue

        # Cooldown: max 1 signal per subscription per 30s
        last = last_fired.get(sub_id, 0)
        if ts_ms - last < 30_000:
            continue
        last_fired[sub_id] = ts_ms

        side = "BUY_YES" if obi > 0 else "BUY_NO"
        # Phase 4: record the asset we'd buy and the most recent trade price
        # on that asset; maker_limit = signal_price - 10bps.
        if side == "BUY_YES":
            asset_at_signal = st.yes_token_id
            signal_price = getattr(st, "_last_price_yes", None)
        else:
            asset_at_signal = st.no_token_id
            signal_price = getattr(st, "_last_price_no", None)
        maker_limit = None
        if signal_price is not None and signal_price > 0:
            maker_limit = max(0.001, signal_price - 0.010)
        signals.append(SignalObs(
            sub_id=sub_id,
            obi=obi,
            abs_obi=abs(obi),
            side=side,
            ts_ms=ts_ms,
            end_ms=end_ms,
            min_to_expiry=sec_to_expiry / 60.0,
            asset_id_at_signal=asset_at_signal,
            signal_price=signal_price,
            maker_limit=maker_limit,
        ))

    return signals, n_processed


# ---------------------------------------------------------------------------
# Step 4: Attach outcomes to signals
# ---------------------------------------------------------------------------

def attach_outcomes(
    signals: list[SignalObs],
    outcomes: dict[str, bool],
    sub_to_meta: dict[str, MarketMeta],
) -> list[SignalObs]:
    resolved = []
    for sig in signals:
        meta = sub_to_meta.get(sig.sub_id)
        if meta is None:
            continue
        outcome = outcomes.get(meta.condition_id)
        if outcome is None:
            continue
        sig.outcome_yes_won = outcome
        resolved.append(sig)
    return resolved


# ---------------------------------------------------------------------------
# Phase 4 audit 2026-04-17: realistic maker-fill simulation
# ---------------------------------------------------------------------------


def simulate_maker_fills(
    conn: sqlite3.Connection,
    signals: list[SignalObs],
    *,
    fill_timeout_sec: float = 60.0,
    since_ms: int | None = None,
    until_ms: int | None = None,
) -> None:
    """Mutate each signal in-place with fill/unfill status.

    Rule: a maker BUY_YES at price P fills if within `fill_timeout_sec` we
    observe ANY last_trade_price on the YES token at price <= P. (Symmetric
    for BUY_NO on the NO token.)

    Limitation: this ignores queue position. A real book with $10k ahead of
    our $10 order at the same limit wouldn't fill for the first 1000 ticks;
    we can't measure queue position from recorder data alone. This gives
    an OPTIMISTIC upper-bound fill rate — bot_e's real fill rate will be
    lower than this simulator reports. Use the result as a ceiling, not
    a forecast.
    """
    if not signals:
        return
    # Load all last_trade_price events once, grouped by asset_id → [(ts_ms, price)].
    by_asset: dict[str, list[tuple[int, float]]] = {}
    where = ["event_type = 'last_trade_price'"]
    params: list[int] = []
    if since_ms is not None:
        where.append("received_at_ms >= ?")
        params.append(since_ms)
    if until_ms is not None:
        where.append("received_at_ms <= ?")
        params.append(until_ms)
    rows = conn.execute(
        "SELECT received_at_ms, asset_id, payload_json FROM pm_events "
        "WHERE " + " AND ".join(where) + " ORDER BY received_at_ms",
        params,
    )
    for ts, aid, raw_json in rows:
        try:
            p = json.loads(raw_json) if raw_json else {}
            price = float(p.get("price", 0) or 0)
        except Exception:
            continue
        if not aid or price <= 0:
            continue
        by_asset.setdefault(str(aid), []).append((int(ts), price))

    for sig in signals:
        if sig.asset_id_at_signal is None or sig.maker_limit is None:
            continue
        stream = by_asset.get(str(sig.asset_id_at_signal), [])
        if not stream:
            continue
        deadline = sig.ts_ms + int(fill_timeout_sec * 1000)
        # Scan forward for the first trade at price <= our maker limit.
        # (Binary search would be faster; linear is fine at current volumes.)
        for ts, price in stream:
            if ts < sig.ts_ms:
                continue
            if ts > deadline:
                break
            if price <= sig.maker_limit:
                sig.filled = True
                sig.fill_ts_ms = ts
                sig.fill_price = price
                break


def measure_adverse_selection(
    conn: sqlite3.Connection,
    signals: list[SignalObs],
    *,
    measure_window_sec: float = 30.0,
    since_ms: int | None = None,
    until_ms: int | None = None,
) -> None:
    """For each FILLED signal, observe the asset's next trade price N seconds
    after fill and set `moved_against` True if it dropped below our fill price
    (BUY_* is "we bought; adverse = price fell below our entry within N seconds").
    """
    by_asset: dict[str, list[tuple[int, float]]] = {}
    where = ["event_type = 'last_trade_price'"]
    params: list[int] = []
    if since_ms is not None:
        where.append("received_at_ms >= ?")
        params.append(since_ms)
    if until_ms is not None:
        where.append("received_at_ms <= ?")
        params.append(until_ms)
    rows = conn.execute(
        "SELECT received_at_ms, asset_id, payload_json FROM pm_events "
        "WHERE " + " AND ".join(where) + " ORDER BY received_at_ms",
        params,
    )
    for ts, aid, raw_json in rows:
        try:
            p = json.loads(raw_json) if raw_json else {}
            price = float(p.get("price", 0) or 0)
        except Exception:
            continue
        if not aid or price <= 0:
            continue
        by_asset.setdefault(str(aid), []).append((int(ts), price))

    for sig in signals:
        if not sig.filled or sig.fill_ts_ms is None or sig.fill_price is None:
            continue
        stream = by_asset.get(str(sig.asset_id_at_signal), [])
        target_ts = sig.fill_ts_ms + int(measure_window_sec * 1000)
        # Pick the latest trade at or before target_ts.
        mid_after: float | None = None
        for ts, price in stream:
            if ts <= sig.fill_ts_ms:
                continue
            if ts > target_ts:
                break
            mid_after = price
        if mid_after is None:
            continue
        sig.midpoint_after_fill = mid_after
        # Both BUY_YES and BUY_NO: adverse = side price fell below fill price.
        sig.moved_against = mid_after < sig.fill_price


def compute_fill_and_adverse_rates(signals: list[SignalObs]) -> dict:
    """Aggregate fill rate + adverse-selection rate across a signal list."""
    n_attempted = sum(1 for s in signals if s.maker_limit is not None)
    n_filled = sum(1 for s in signals if s.filled)
    measured = [s for s in signals if s.moved_against is not None]
    n_adverse = sum(1 for s in measured if s.moved_against)
    return {
        "n_signals_eligible": n_attempted,
        "n_signals_filled": n_filled,
        "fill_rate": (n_filled / n_attempted) if n_attempted else 0.0,
        "n_fills_measured": len(measured),
        "n_fills_adverse": n_adverse,
        "adverse_rate": (n_adverse / len(measured)) if measured else 0.0,
    }


# ---------------------------------------------------------------------------
# Step 5: Regime gate
# ---------------------------------------------------------------------------

def build_btc_regime_timeline(
    conn: sqlite3.Connection,
    *,
    since_ms: int | None = None,
    until_ms: int | None = None,
) -> list[tuple[int, float]]:
    where = ["symbol='BTCUSDT'"]
    params: list[int] = []
    if since_ms is not None:
        where.append("received_at_ms >= ?")
        params.append(since_ms)
    if until_ms is not None:
        where.append("received_at_ms <= ?")
        params.append(until_ms)
    return conn.execute(
        "SELECT received_at_ms, price FROM cex_trades WHERE "
        + " AND ".join(where)
        + " ORDER BY received_at_ms",
        params,
    ).fetchall()


def choppiness_at(
    btc_timeline: list[tuple[int, float]],
    ts_ms: int,
    window_ms: int = 600_000,
) -> float:
    cutoff = ts_ms - window_ms
    in_window = [p for t, p in btc_timeline if cutoff <= t <= ts_ms]
    if len(in_window) < 3:
        return 0.0
    step = max(1, len(in_window) // 20)
    closes = in_window[::step]
    if len(closes) < 3:
        return 0.0
    signs = [1 if closes[i] > closes[i-1] else -1 for i in range(1, len(closes))]
    reversals = sum(1 for i in range(1, len(signs)) if signs[i] != signs[i-1])
    return reversals / max(1, len(signs) - 1)


# ---------------------------------------------------------------------------
# Step 6: Compute calibration statistics
# ---------------------------------------------------------------------------

@dataclass
class BucketStats:
    label: str
    n: int = 0
    n_win: int = 0
    sum_abs_obi: float = 0.0

    @property
    def realised_wr(self) -> float:
        return self.n_win / self.n if self.n else 0.0

    @property
    def predicted_wr(self) -> float:
        # OBI maps to predicted win prob: predicted = 0.5 + abs_obi/2
        # (conservative linear proxy)
        return 0.5 + self.sum_abs_obi / (2 * self.n) if self.n else 0.5

    @property
    def ece(self) -> float:
        return abs(self.predicted_wr - self.realised_wr)


def obi_bucket_label(abs_obi: float) -> str | None:
    for lo, hi, label in OBI_BUCKETS:
        if lo <= abs_obi < hi:
            return label
    return None


# Phase 5 Item 1 audit 2026-04-17: time-to-expiry stratification buckets.
# Lets us separately measure WR/ECE on the signals that correspond to the
# live entry window (5-10 min) vs the wider paper window edges (3-5, 10-15).
# The go-file decision gates on the LIVE bucket, not the aggregate.
TTE_BUCKETS = [
    (3.0, 5.0, "3-5min"),
    (5.0, 7.0, "5-7min"),
    (7.0, 10.0, "7-10min"),
    (10.0, 15.0, "10-15min"),
]
TTE_LIVE_WINDOW_LABEL = "5-10min_aggregate"  # union of 5-7 and 7-10


def tte_bucket_label(min_to_expiry: float) -> str | None:
    for lo, hi, label in TTE_BUCKETS:
        if lo <= min_to_expiry < hi:
            return label
    return None


def compute_stats(
    signals: list[SignalObs],
    btc_timeline: list[tuple[int, float]],
    apply_regime: bool = True,
) -> tuple[dict[str, BucketStats], list[SignalObs], int, dict[str, BucketStats]]:
    """Return (obi_buckets, kept, n_regime_skip, tte_buckets).

    Phase 5 Item 1: also groups kept signals by time-to-expiry so the
    live-window stats can be extracted and gated on separately from the
    wider paper window.
    """
    buckets: dict[str, BucketStats] = {
        label: BucketStats(label=label) for _, _, label in OBI_BUCKETS
    }
    tte_buckets: dict[str, BucketStats] = {
        label: BucketStats(label=label) for _, _, label in TTE_BUCKETS
    }
    # Live-window aggregate (5-7 + 7-10).
    tte_buckets[TTE_LIVE_WINDOW_LABEL] = BucketStats(label=TTE_LIVE_WINDOW_LABEL)
    kept = []
    n_regime_skip = 0

    for sig in signals:
        if sig.outcome_yes_won is None:
            continue

        # Regime gate for BTC subscriptions
        if apply_regime and "btc" in sig.sub_id:
            chop = choppiness_at(btc_timeline, sig.ts_ms)
            if chop > REGIME_CHOPPINESS_MAX:
                n_regime_skip += 1
                continue

        label = obi_bucket_label(sig.abs_obi)
        if label is None:
            continue

        win = sig.outcome_yes_won if sig.side == "BUY_YES" else not sig.outcome_yes_won

        b = buckets[label]
        b.n += 1
        b.sum_abs_obi += sig.abs_obi
        if win:
            b.n_win += 1
        # Phase 5 Item 1: also bucket by TTE.
        tte_label = tte_bucket_label(sig.min_to_expiry)
        if tte_label is not None:
            tb = tte_buckets[tte_label]
            tb.n += 1
            tb.sum_abs_obi += sig.abs_obi
            if win:
                tb.n_win += 1
            # Aggregate 5-10min live-window bucket.
            if tte_label in ("5-7min", "7-10min"):
                tba = tte_buckets[TTE_LIVE_WINDOW_LABEL]
                tba.n += 1
                tba.sum_abs_obi += sig.abs_obi
                if win:
                    tba.n_win += 1
        kept.append(sig)

    return buckets, kept, n_regime_skip, tte_buckets


# ---------------------------------------------------------------------------
# Step 7: Decide GO / NO-GO
# ---------------------------------------------------------------------------

def decide(
    buckets: dict[str, BucketStats],
    overall_wr: float,
    overall_n: int,
    weighted_ece: float,
    fill_stats: dict | None = None,
    tte_buckets: dict[str, BucketStats] | None = None,
) -> tuple[bool, list[str]]:
    reasons = []
    go = True

    if overall_n < MIN_SIGNALS_FOR_GO:
        go = False
        reasons.append(
            f"insufficient sample size: {overall_n} qualifying signals "
            f"(need >= {MIN_SIGNALS_FOR_GO})"
        )

    if overall_n >= 20 and overall_wr < MIN_REALISED_WR_FOR_GO:
        go = False
        reasons.append(
            f"realised win rate {overall_wr:.3f} below threshold {MIN_REALISED_WR_FOR_GO}"
        )

    if overall_n >= 20 and weighted_ece > MAX_ECE_FOR_GO:
        go = False
        reasons.append(
            f"weighted ECE {weighted_ece:.3f} above threshold {MAX_ECE_FOR_GO}"
        )

    # Phase 5 Item 1: additional gate on the live-window TTE bucket.
    # Aggregate stats can paper over a wide window that will never trade.
    if tte_buckets is not None:
        live_bucket = tte_buckets.get(TTE_LIVE_WINDOW_LABEL)
        if live_bucket is not None and live_bucket.n >= 20:
            if live_bucket.realised_wr < MIN_REALISED_WR_FOR_GO:
                go = False
                reasons.append(
                    f"live-window (5-10min) WR {live_bucket.realised_wr:.3f} below "
                    f"threshold {MIN_REALISED_WR_FOR_GO} (n={live_bucket.n})"
                )
            if live_bucket.ece > MAX_ECE_FOR_GO:
                go = False
                reasons.append(
                    f"live-window (5-10min) ECE {live_bucket.ece:.3f} above "
                    f"threshold {MAX_ECE_FOR_GO} (n={live_bucket.n})"
                )

    # Phase 4 audit 2026-04-17: maker-fill reality + adverse-selection gates.
    if fill_stats is not None:
        n_eligible = fill_stats.get("n_signals_eligible", 0)
        fill_rate = fill_stats.get("fill_rate", 0.0)
        adverse_rate = fill_stats.get("adverse_rate", 0.0)
        n_measured = fill_stats.get("n_fills_measured", 0)
        if n_eligible >= 20 and fill_rate < MIN_FILL_RATE_FOR_GO:
            go = False
            reasons.append(
                f"maker fill rate {fill_rate:.3f} below threshold "
                f"{MIN_FILL_RATE_FOR_GO} (n_eligible={n_eligible})"
            )
        if n_measured >= 20 and adverse_rate > MAX_ADVERSE_RATE_FOR_GO:
            go = False
            reasons.append(
                f"adverse-selection rate {adverse_rate:.3f} above threshold "
                f"{MAX_ADVERSE_RATE_FOR_GO} (n_measured={n_measured})"
            )

    return go, reasons


# ---------------------------------------------------------------------------
# Step 8: Write outputs
# ---------------------------------------------------------------------------

def write_go_file(
    go: bool,
    reasons: list[str],
    buckets: dict[str, BucketStats],
    overall_n: int,
    overall_wr: float,
    weighted_ece: float,
    n_resolved: int,
    n_regime_skip: int,
    n_raw_signals: int,
    data_start_ms: int,
    data_end_ms: int,
    fill_stats: dict | None = None,
    tte_buckets: dict[str, BucketStats] | None = None,
) -> None:
    by_bucket = []
    for _, _, label in OBI_BUCKETS:
        b = buckets[label]
        by_bucket.append({
            "bucket": label,
            "n": b.n,
            "predicted_wr": round(b.predicted_wr, 4),
            "realised_wr": round(b.realised_wr, 4),
            "ece": round(b.ece, 4),
        })

    doc = {
        "ready": go,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_window": {
            "start": datetime.fromtimestamp(data_start_ms / 1000, tz=timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(data_end_ms / 1000, tz=timezone.utc).isoformat(),
            "n_pm_events": n_raw_signals,
            "n_signals_raw": n_raw_signals,
            "n_signals_resolved": n_resolved,
            "n_signals_regime_skipped": n_regime_skip,
            "n_signals_calibrated": overall_n,
        },
        "calibration": {
            "overall_ece": round(weighted_ece, 4),
            "overall_realised_winrate": round(overall_wr, 4),
            "n_signals": overall_n,
            "by_obi_bucket": by_bucket,
            "by_tte_bucket": (
                [
                    {
                        "bucket": lbl,
                        "n": tte_buckets[lbl].n,
                        "predicted_wr": round(tte_buckets[lbl].predicted_wr, 4),
                        "realised_wr": round(tte_buckets[lbl].realised_wr, 4),
                        "ece": round(tte_buckets[lbl].ece, 4),
                    }
                    for _, _, lbl in TTE_BUCKETS
                ] + [
                    {
                        "bucket": TTE_LIVE_WINDOW_LABEL,
                        "note": "live trading window aggregate (5-10min); this is the gate",
                        "n": tte_buckets[TTE_LIVE_WINDOW_LABEL].n,
                        "predicted_wr": round(tte_buckets[TTE_LIVE_WINDOW_LABEL].predicted_wr, 4),
                        "realised_wr": round(tte_buckets[TTE_LIVE_WINDOW_LABEL].realised_wr, 4),
                        "ece": round(tte_buckets[TTE_LIVE_WINDOW_LABEL].ece, 4),
                    }
                ]
                if tte_buckets is not None
                else []
            ),
        },
        "fill_realism": (
            {
                "n_signals_eligible": fill_stats.get("n_signals_eligible", 0),
                "n_signals_filled": fill_stats.get("n_signals_filled", 0),
                "fill_rate": round(fill_stats.get("fill_rate", 0.0), 4),
                "n_fills_measured": fill_stats.get("n_fills_measured", 0),
                "n_fills_adverse": fill_stats.get("n_fills_adverse", 0),
                "adverse_rate": round(fill_stats.get("adverse_rate", 0.0), 4),
                "min_fill_rate_threshold": MIN_FILL_RATE_FOR_GO,
                "max_adverse_rate_threshold": MAX_ADVERSE_RATE_FOR_GO,
                "maker_offset_used_bps": 10,
                "fill_timeout_sec": 60.0,
                "adverse_measure_window_sec": 30.0,
                "limitations": (
                    "Simulator ignores queue position; real fill rate will be "
                    "lower than reported. Use as ceiling, not forecast."
                ),
            }
            if fill_stats is not None
            else None
        ),
        "validated_params": {
            "obi_threshold": float(OBI_THRESHOLD_DEFAULT),
            "obi_window_sec": OBI_WINDOW_SEC,
            "regime_choppiness_max": REGIME_CHOPPINESS_MAX,
            "kelly_fraction_recommended": 0.25,
            "fixed_size_usd_first_200_trades": 30.0,
        },
        "tripwires": {
            "halt_if_realised_wr_below": 0.50,
            "halt_if_daily_drawdown_above_pct": 5.0,
            "halt_after_n_consecutive_losses": 10,
        },
        "no_go_reasons": reasons if not go else [],
        "notes": (
            "Calibration run on the selected bounded recorder window. "
            "OBI signals from last_trade_price events, 120s rolling window. "
            "Resolution outcomes from CEX BTC/ETH/SOL price at market start vs end. "
            "Entry window: t-10min to t-5min. Regime gate on BTC subscriptions."
        ),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(doc, f, indent=2)
    print(f"  Written: {OUT_JSON}")


_EMPTY_SYM_TABLE = "| (none) | 0 | — |\n"


def write_report(
    go: bool,
    reasons: list[str],
    buckets: dict[str, BucketStats],
    kept_signals: list[SignalObs],
    overall_n: int,
    overall_wr: float,
    weighted_ece: float,
    n_resolved: int,
    n_raw_signals: int,
    n_regime_skip: int,
    data_start_ms: int,
    data_end_ms: int,
) -> None:
    start_str = datetime.fromtimestamp(
        data_start_ms / 1000, tz=timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")
    end_str = datetime.fromtimestamp(
        data_end_ms / 1000, tz=timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")
    duration_hours = (data_end_ms - data_start_ms) / 3_600_000
    verdict = "GO" if go else "NO-GO"

    ci_95 = 1.96 * (0.5 / max(1, overall_n) ** 0.5) if overall_n > 0 else 0.5
    verdict_detail = "Signal passes all calibration thresholds." if go else "; ".join(reasons)
    sample_status = (
        "PASS" if overall_n >= MIN_SIGNALS_FOR_GO else f"FAIL ({overall_n} signals)"
    )
    wr_status = (
        "PASS"
        if overall_n < 20 or overall_wr >= MIN_REALISED_WR_FOR_GO
        else f"FAIL ({overall_wr:.3f})"
    )
    ece_status = (
        "PASS"
        if overall_n < 20 or weighted_ece <= MAX_ECE_FOR_GO
        else f"FAIL ({weighted_ece:.3f})"
    )
    recommendation = (
        "The signal shows sufficient directional bias to proceed to paper trading. "
        "Activate with fixed $30/trade. Monitor tripwires: halt if realised WR "
        "drops below 50% over trailing 50 trades or daily drawdown exceeds 5%."
        if go
        else (
            "Do not activate paper trading yet. Continue recording for at least "
            "7 additional days to accumulate sufficient signal volume. The "
            "architecture appears sound — the blocker is sample size, not signal "
            "quality. Re-run this script after 7+ days of recording. The directional "
            "bias in existing signals (where measured) provides preliminary evidence "
            "but is not statistically reliable at this sample size."
        )
    )

    # Symbol breakdown
    by_symbol: dict[str, dict] = defaultdict(lambda: {"n": 0, "wins": 0})
    for sig in kept_signals:
        sym = sig.sub_id.split("-")[0].upper()
        by_symbol[sym]["n"] += 1
        win = sig.outcome_yes_won if sig.side == "BUY_YES" else not sig.outcome_yes_won
        if win:
            by_symbol[sym]["wins"] += 1

    sym_table = ""
    for sym, d in sorted(by_symbol.items()):
        if d["n"] > 0:
            wr = d["wins"] / d["n"]
            sym_table += f"| {sym} | {d['n']} | {wr:.3f} |\n"

    bucket_rows = ""
    for _, _, label in OBI_BUCKETS:
        b = buckets[label]
        if b.n == 0:
            bucket_rows += f"| {label} | 0 | — | — | — |\n"
        else:
            bucket_rows += (
                f"| {label} | {b.n} | {b.predicted_wr:.3f} | "
                f"{b.realised_wr:.3f} | {b.ece:.3f} |\n"
            )

    report = f"""# Bot E Phase 0d Calibration Report

**Generated:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
**Verdict: {verdict}**

{verdict_detail}

---

## Data

| Field | Value |
|---|---|
| Data window | {start_str} to {end_str} |
| Duration | ~{duration_hours:.1f} hours |
| Raw OBI signals in entry window | {n_raw_signals} |
| Signals with resolved outcomes | {n_resolved} |
| Regime-skipped (choppy BTC) | {n_regime_skip} |
| Final calibration signals | {overall_n} |

---

## Methodology

1. **OBI reconstruction**: Rolled `last_trade_price` events through 120s window per
   subscription. Signal fires if `abs(OBI) >= {OBI_THRESHOLD_DEFAULT}` and timestamp
   falls in t-10min to t-5min entry window. 30s cooldown per subscription.

2. **Resolution outcome**: For "Up or Down" markets, CEX price (Binance) at market
   START vs END determines YES (price UP) or NO (price DOWN). 30s averaging window
   at each timestamp. This works for all resolved markets, not just those with
   post-expiry WSS events.

3. **Win condition**: OBI sign predicts direction (BUY_YES / BUY_NO). Win if outcome
   matches predicted direction.

4. **Regime gate**: Choppiness ratio from 10-min BTC CEX window. Skip if > 0.65.
   Applied to BTC subscriptions only.

5. **Predicted WR model**: `predicted_wr = 0.5 + abs(OBI)/2` (conservative linear
   proxy used only for ECE; not a calibrated probability model).

---

## Per-Bucket Results

| OBI bucket | N signals | Predicted WR | Realised WR | ECE |
|---|---|---|---|---|
{bucket_rows}
**Overall**: {overall_n} signals, realised WR = {overall_wr:.3f}, weighted ECE = {weighted_ece:.3f}

95% confidence interval on WR (binomial, N={overall_n}): ±{ci_95:.3f}

---

## By Symbol

| Symbol | N | Win Rate |
|---|---|---|
{sym_table if sym_table else _EMPTY_SYM_TABLE}

---

## Red Flags

- **Bounded data window**: This report only covers the selected recorder window.
  Standard error at N={overall_n} is ±{ci_95:.3f} — treat win rate estimate as
  uncertain unless the window spans multiple clean market sessions.

- **Recorder closes subscriptions on resolution**: The recorder design closes WSS when
  a market expires. This is correct operationally but means post-expiry price cascades
  are only captured for markets that resolve while a new subscription is starting up.
  CEX-based outcome detection was used to work around this.

- **OBI entry window low coverage**: Most subscriptions had low trade counts in the
  t-10min to t-5min window. The 30s cooldown limited signals to ~1 per subscription
  per 30s, reducing the dataset.

- **Maker fill not modelled**: We assume entry fills. In practice, maker-only orders
  may not fill in the 5-min entry window. Fill rate is a separate open question.

- **Session coverage**: If the bounded window covers only one market session, it
  still lacks overnight and multi-session variance.

---

## GO/NO-GO Decision

**{verdict}**

Threshold criteria:
- Minimum {MIN_SIGNALS_FOR_GO} calibrated signals: {sample_status}
- Realised WR >= {MIN_REALISED_WR_FOR_GO}: {wr_status}
- Weighted ECE <= {MAX_ECE_FOR_GO}: {ece_status}

{f"Primary blocker: {reasons[0] if reasons else 'none'}" if not go else "All thresholds met."}

---

## Recommendation

{recommendation}
"""

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write(report)
    print(f"  Written: {OUT_MD}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _lookback_hours_from_env() -> float | None:
    raw = os.environ.get(LOOKBACK_ENV)
    if raw in (None, ""):
        return None
    try:
        hours = float(raw)
    except ValueError:
        raise SystemExit(f"ERROR: {LOOKBACK_ENV} must be numeric, got {raw!r}")
    if hours <= 0:
        raise SystemExit(f"ERROR: {LOOKBACK_ENV} must be > 0, got {raw!r}")
    return hours


def main() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: recorder DB not found at {DB_PATH}")
        sys.exit(1)

    print("Bot E Phase 0d Calibration Spike")
    print(f"DB: {DB_PATH} ({DB_PATH.stat().st_size / 1e6:.1f} MB)")
    print()

    conn = sqlite3.connect(str(DB_PATH))
    try:
        row = conn.execute(
            "SELECT MIN(received_at_ms), MAX(received_at_ms) FROM pm_events"
        ).fetchone()
        raw_data_start_ms, data_end_ms = row
        if raw_data_start_ms is None or data_end_ms is None:
            print("ERROR: recorder DB has no pm_events")
            sys.exit(1)
        lookback_hours = _lookback_hours_from_env()
        if lookback_hours is None:
            data_start_ms = raw_data_start_ms
        else:
            data_start_ms = max(
                raw_data_start_ms,
                data_end_ms - int(lookback_hours * 3_600_000),
            )

        start_str = datetime.fromtimestamp(data_start_ms / 1000, tz=timezone.utc).isoformat()
        end_str = datetime.fromtimestamp(data_end_ms / 1000, tz=timezone.utc).isoformat()
        hours = (data_end_ms - data_start_ms) / 3_600_000
        print(f"Data window: {start_str} to {end_str} ({hours:.1f} hours)")
        if lookback_hours is not None:
            print(f"Bounded by {LOOKBACK_ENV}={lookback_hours:g}")

        print("\nStep 1: Loading market metadata...")
        metas = load_markets(conn)
        token_to_market = build_token_to_market(metas)
        updown_count = sum(1 for m in metas.values() if m.is_up_down)
        print(f"  {len(metas)} markets total, {updown_count} are Up/Down type")

        print("\nStep 1b: Building subscription→market mapping...")
        sub_to_meta = build_sub_to_market(
            conn,
            token_to_market,
            since_ms=data_start_ms,
            until_ms=data_end_ms,
        )
        print(f"  {len(sub_to_meta)} subscriptions mapped to markets")

        print("\nStep 2: Loading CEX prices...")
        # Include a small lookback pad for market start/end price windows and
        # choppiness calculations without walking the whole recorder DB.
        cex_since_ms = max(raw_data_start_ms, data_start_ms - 20 * 60_000)
        cex_until_ms = data_end_ms + 60_000
        cex_prices = load_cex_prices(
            conn,
            ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            since_ms=cex_since_ms,
            until_ms=cex_until_ms,
        )
        for sym, data in cex_prices.items():
            print(f"  {sym}: {len(data)} ticks")

        print("\nStep 2b: Detecting resolution outcomes via CEX prices...")
        outcomes = detect_resolutions_via_cex(
            metas, cex_prices, data_start_ms, data_end_ms
        )
        print(f"  {len(outcomes)} markets with CEX-confirmed resolution")
        yes_won = sum(1 for v in outcomes.values() if v)
        no_won = sum(1 for v in outcomes.values() if not v)
        print(f"  YES won: {yes_won}, NO won: {no_won}")

        # Print resolved markets
        for cond, meta in metas.items():
            if cond in outcomes:
                print(f"    {outcomes[cond]} <- {meta.question[:70]}")

        print("\nStep 3: Replaying events and building OBI signals...")
        t0 = time.time()
        signals, n_events_processed = replay_signals(
            conn,
            token_to_market,
            sub_to_meta,
            since_ms=data_start_ms,
            until_ms=data_end_ms,
        )
        elapsed = time.time() - t0
        print(f"  Replay: {n_events_processed} events processed in {elapsed:.1f}s")
        print(f"  {len(signals)} OBI signals in entry window")
        n_raw_signals = len(signals)

        print("\nStep 4: Attaching resolution outcomes...")
        resolved_signals = attach_outcomes(signals, outcomes, sub_to_meta)
        n_resolved = len(resolved_signals)
        print(f"  {n_resolved} of {n_raw_signals} signals have resolved outcomes")

        print("\nStep 4b: Simulating maker-only fills (Phase 4 audit 2026-04-17)...")
        signal_start_ms = min((s.ts_ms for s in resolved_signals), default=data_start_ms)
        signal_end_ms = max((s.ts_ms for s in resolved_signals), default=data_end_ms)
        sim_since_ms = max(raw_data_start_ms, signal_start_ms - 1_000)
        sim_until_ms = min(data_end_ms + 90_000, signal_end_ms + 90_000)
        simulate_maker_fills(
            conn,
            resolved_signals,
            fill_timeout_sec=60.0,
            since_ms=sim_since_ms,
            until_ms=sim_until_ms,
        )
        measure_adverse_selection(
            conn,
            resolved_signals,
            measure_window_sec=30.0,
            since_ms=sim_since_ms,
            until_ms=sim_until_ms,
        )
        fill_stats = compute_fill_and_adverse_rates(resolved_signals)
        print(
            f"  fill rate: {fill_stats['n_signals_filled']}/"
            f"{fill_stats['n_signals_eligible']} = {fill_stats['fill_rate']:.3f}"
        )
        print(
            f"  adverse rate: {fill_stats['n_fills_adverse']}/"
            f"{fill_stats['n_fills_measured']} = {fill_stats['adverse_rate']:.3f}"
        )
        # Filter to filled signals only — unfilled maker orders generate no
        # outcomes in real trading, so calibration should compute on fills.
        filled_signals = [s for s in resolved_signals if s.filled]
        print(f"  {len(filled_signals)} filled signals pass to calibration stats")
        resolved_signals = filled_signals

        print("\nStep 5: Loading CEX BTC regime data...")
        btc_timeline = build_btc_regime_timeline(
            conn,
            since_ms=cex_since_ms,
            until_ms=cex_until_ms,
        )
        print(f"  {len(btc_timeline)} BTC trade ticks")

        print("\nStep 6: Computing calibration statistics...")
        buckets, kept_signals, n_regime_skip, tte_buckets = compute_stats(
            resolved_signals, btc_timeline, apply_regime=True
        )
        overall_n = sum(b.n for b in buckets.values())
        overall_wins = sum(b.n_win for b in buckets.values())
        overall_wr = overall_wins / overall_n if overall_n else 0.0

        top_buckets = [b for b in buckets.values() if b.n >= 5]
        if top_buckets:
            weighted_ece = sum(b.ece * b.n for b in top_buckets) / sum(
                b.n for b in top_buckets
            )
        else:
            weighted_ece = (
                1.0
                if overall_n < 5
                else sum(b.ece * b.n for b in buckets.values() if b.n > 0)
                / max(1, overall_n)
            )

        print(f"  {overall_n} calibration signals ({n_regime_skip} regime-skipped)")
        print()
        print(f"  {'Bucket':<14} {'N':>6} {'Pred WR':>8} {'Realised WR':>12} {'ECE':>7}")
        print(f"  {'-'*14} {'-'*6} {'-'*8} {'-'*12} {'-'*7}")
        for _, _, label in OBI_BUCKETS:
            b = buckets[label]
            if b.n == 0:
                print(f"  {label:<14} {'0':>6} {'—':>8} {'—':>12} {'—':>7}")
            else:
                print(
                    f"  {label:<14} {b.n:>6} {b.predicted_wr:>8.3f} "
                    f"{b.realised_wr:>12.3f} {b.ece:>7.3f}"
                )
        print(f"\n  Overall: N={overall_n}, WR={overall_wr:.3f}, ECE={weighted_ece:.3f}")

        # Phase 5 Item 1: TTE stratification readout.
        print()
        print("  TTE bucket       N     Pred WR   Realised WR    ECE")
        print(f"  {'-'*16} {'-'*5} {'-'*9} {'-'*13} {'-'*6}")
        for _, _, label in TTE_BUCKETS:
            b = tte_buckets[label]
            if b.n == 0:
                print(f"  {label:<16} {'0':>5} {'—':>9} {'—':>13} {'—':>6}")
            else:
                print(
                    f"  {label:<16} {b.n:>5} {b.predicted_wr:>9.3f} "
                    f"{b.realised_wr:>13.3f} {b.ece:>6.3f}"
                )
        lb = tte_buckets[TTE_LIVE_WINDOW_LABEL]
        if lb.n > 0:
            print(
                f"  {TTE_LIVE_WINDOW_LABEL:<16} {lb.n:>5} {lb.predicted_wr:>9.3f} "
                f"{lb.realised_wr:>13.3f} {lb.ece:>6.3f} <- LIVE WINDOW gate"
            )

        print("\nStep 7: Deciding GO / NO-GO...")
        go, reasons = decide(
            buckets, overall_wr, overall_n, weighted_ece,
            fill_stats=fill_stats,
            tte_buckets=tte_buckets,
        )
        print(f"  Decision: {'GO' if go else 'NO-GO'}")
        for r in reasons:
            print(f"  Reason: {r}")

        print("\nStep 8: Writing outputs...")
        write_go_file(
            go, reasons, buckets,
            overall_n, overall_wr, weighted_ece,
            n_resolved, n_regime_skip, n_raw_signals,
            data_start_ms, data_end_ms,
            fill_stats=fill_stats,
            tte_buckets=tte_buckets,
        )
        write_report(
            go, reasons, buckets, kept_signals,
            overall_n, overall_wr, weighted_ece,
            n_resolved, n_raw_signals, n_regime_skip,
            data_start_ms, data_end_ms,
        )

        print()
        print("=" * 60)
        print(f"RESULT: {'GO' if go else 'NO-GO'}")
        if not go:
            for r in reasons:
                print(f"  - {r}")
        print("=" * 60)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
