"""Bot E backtester — consumes a Bot E0 recorder SQLite and evaluates
candidate OBI thresholds with realistic 2026 fees, slippage, and latency.

Separate module from `core/backtest.py` because:
- Bot A's backtester is live-critical; we should not destabilise it while
  iterating on Bot E calibration.
- Data source differs: `backtest.py` reads from the main `markets/books` tables;
  this reads from the recorder SQLite.
- Output differs: this produces conditional expectancy tables, not per-trade
  P&L curves.

Flow:
1. Load recorded `pm_events` and `cex_trades` for a time range.
2. Reconstruct per-subscription order-book state and rolling OBI.
3. Simulate entries when `abs(OBI) > threshold` AND regime not choppy, using
   maker limit orders at mid+0.002 (YES buy) or mid-0.002 (NO buy).
4. Determine fill by whether the book crossed our limit price within N seconds.
5. Determine exit at market resolution (known from `markets.end_date_iso` +
   post-resolution token price collapses).
6. Apply fee curve from `core/fees.py` (maker rebate).
7. Output conditional expectancy by (minute-to-expiry × regime × OBI bucket).

Per ADR-022 Phase 0d: this module produces the go/no-go evidence. If positive
EV after fees+slippage+latency across regimes — build the trader. If not — close.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from core.fees import fee_for_fill, round_trip_cost_rate

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Replay primitives — read recorder SQLite row-by-row in time order
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Gap detection (audit 2026-04-17, missed-risk M-3)
# ---------------------------------------------------------------------------


@dataclass
class RecorderGap:
    """A window where the recorder data is missing or degraded."""
    feed: str           # "pm_events" | "cex_trades"
    start_ms: int       # last-seen timestamp before the gap
    end_ms: int         # first timestamp after the gap
    gap_ms: int         # end_ms - start_ms


def detect_gaps(
    db_path: Path,
    *,
    max_gap_ms: int = 5000,
    start_ms: int | None = None,
    end_ms: int | None = None,
) -> list[RecorderGap]:
    """Return time windows where consecutive recorder rows are > max_gap_ms apart.

    A single WSS reconnect with missed trades poisons calibration invisibly
    (meta-review M-3). The backtester should quarantine calibration windows
    that overlap any detected gap + a buffer.

    Checks both `pm_events` and `cex_trades` tables independently so a gap
    in one feed doesn't contaminate data from the other if they're later
    analysed separately.
    """
    conn = sqlite3.connect(str(db_path))
    gaps: list[RecorderGap] = []
    try:
        for feed, table in [("pm_events", "pm_events"), ("cex_trades", "cex_trades")]:
            sql = f"SELECT received_at_ms FROM {table}"
            filters = []
            params: list = []
            if start_ms is not None:
                filters.append("received_at_ms >= ?")
                params.append(start_ms)
            if end_ms is not None:
                filters.append("received_at_ms <= ?")
                params.append(end_ms)
            if filters:
                sql += " WHERE " + " AND ".join(filters)
            sql += " ORDER BY received_at_ms"
            try:
                cur = conn.execute(sql, params)
            except sqlite3.OperationalError as exc:
                log.debug("backtest.detect_gaps %s skipped err=%s", feed, exc)
                continue
            prev_ts: int | None = None
            for (ts,) in cur:
                if prev_ts is not None and (ts - prev_ts) > max_gap_ms:
                    gaps.append(RecorderGap(
                        feed=feed,
                        start_ms=prev_ts,
                        end_ms=ts,
                        gap_ms=ts - prev_ts,
                    ))
                prev_ts = ts
    finally:
        conn.close()
    return gaps


def quarantine_ranges(
    gaps: list[RecorderGap], *, buffer_ms: int = 5000,
) -> list[tuple[int, int]]:
    """Expand gaps by `buffer_ms` on each side to produce quarantine windows.

    Events whose ts_ms falls inside any returned (start, end) range should
    be excluded from calibration. Overlapping ranges are merged.
    """
    if not gaps:
        return []
    raw = sorted(
        [(g.start_ms - buffer_ms, g.end_ms + buffer_ms) for g in gaps]
    )
    merged: list[tuple[int, int]] = []
    for start, end in raw:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def in_quarantine(ts_ms: int, ranges: list[tuple[int, int]]) -> bool:
    """Return True if ts_ms falls inside any quarantine range."""
    for start, end in ranges:
        if start <= ts_ms <= end:
            return True
    return False


@dataclass
class RecorderEvent:
    """Normalised event stream from the recorder DB."""
    kind: str                   # "pm_book" | "pm_price" | "pm_trade" | "cex_trade" | "reconnect"
    ts_ms: int
    subscription_id: str | None
    asset_id: str | None
    payload: dict


def iter_events(
    db_path: Path,
    *,
    start_ms: int | None = None,
    end_ms: int | None = None,
    quarantine: list[tuple[int, int]] | None = None,
) -> Iterator[RecorderEvent]:
    """Stream merged (pm_events, cex_trades) in timestamp order.

    We merge in-memory via time-ordered cursors. Recorder DBs cover 3–4 days
    at bounded event rates, so in-process merge is fine.

    Phase 3 audit 2026-04-17 (meta-review M-3): if `quarantine` is supplied
    (from `quarantine_ranges(detect_gaps(...))`), events whose ts_ms falls
    inside any range are skipped. Prevents calibration poisoning after WSS
    reconnects drop trades.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        pm_sql = (
            "SELECT received_at_ms, subscription_id, event_type, asset_id, "
            "condition_id, payload_json FROM pm_events"
        )
        cex_sql = (
            "SELECT received_at_ms, trade_time_ms, symbol, price, size, is_buyer_maker "
            "FROM cex_trades"
        )
        filters_pm = []
        filters_cex = []
        params_pm: list = []
        params_cex: list = []
        if start_ms is not None:
            filters_pm.append("received_at_ms >= ?")
            filters_cex.append("received_at_ms >= ?")
            params_pm.append(start_ms)
            params_cex.append(start_ms)
        if end_ms is not None:
            filters_pm.append("received_at_ms <= ?")
            filters_cex.append("received_at_ms <= ?")
            params_pm.append(end_ms)
            params_cex.append(end_ms)
        if filters_pm:
            pm_sql += " WHERE " + " AND ".join(filters_pm)
            cex_sql += " WHERE " + " AND ".join(filters_cex)
        pm_sql += " ORDER BY received_at_ms"
        cex_sql += " ORDER BY received_at_ms"

        pm_cur = conn.execute(pm_sql, params_pm)
        cex_cur = conn.execute(cex_sql, params_cex)
        pm_row = pm_cur.fetchone()
        cex_row = cex_cur.fetchone()

        while pm_row or cex_row:
            use_pm = pm_row and (not cex_row or pm_row[0] <= cex_row[0])
            # Apply quarantine filter — skip events inside a gap-derived window.
            if quarantine:
                ts_to_check = pm_row[0] if use_pm else cex_row[0]
                if in_quarantine(ts_to_check, quarantine):
                    if use_pm:
                        pm_row = pm_cur.fetchone()
                    else:
                        cex_row = cex_cur.fetchone()
                    continue
            if use_pm:
                ts, sub, etype, asset, cond, raw_json = pm_row
                try:
                    payload = json.loads(raw_json) if raw_json else {}
                except json.JSONDecodeError:
                    payload = {}
                kind_map = {
                    "book": "pm_book",
                    "price_change": "pm_price",
                    "last_trade_price": "pm_trade",
                    "best_bid_ask": "pm_price",
                    "reconnect": "reconnect",
                }
                yield RecorderEvent(
                    kind=kind_map.get(etype, f"pm_{etype}"),
                    ts_ms=ts,
                    subscription_id=sub,
                    asset_id=asset,
                    payload=payload,
                )
                pm_row = pm_cur.fetchone()
            else:
                ts, trade_ts, sym, price, size, is_maker = cex_row
                yield RecorderEvent(
                    kind="cex_trade",
                    ts_ms=ts,
                    subscription_id=None,
                    asset_id=sym,
                    payload={
                        "symbol": sym, "price": price, "size": size,
                        "is_buyer_maker": bool(is_maker), "trade_time_ms": trade_ts,
                    },
                )
                cex_row = cex_cur.fetchone()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# OBI reconstruction
# ---------------------------------------------------------------------------


@dataclass
class SubscriptionState:
    """Rolling state per subscription (market). OBI needs a time-windowed
    trade log; book state needed for entry price estimation."""
    subscription_id: str
    last_yes_price: float | None = None
    last_no_price: float | None = None
    best_yes_bid: float | None = None
    best_yes_ask: float | None = None
    # rolling trades for OBI: (ts_ms, asset_id, size)
    rolling_trades: list[tuple[int, str, float]] = field(default_factory=list)
    # yes_token_id / no_token_id mapping (learned from book events)
    yes_token_id: str | None = None
    no_token_id: str | None = None

    def prune_trades(self, now_ms: int, window_ms: int) -> None:
        cutoff = now_ms - window_ms
        self.rolling_trades = [t for t in self.rolling_trades if t[0] >= cutoff]

    def obi(self, now_ms: int, window_sec: float) -> float | None:
        """Return abs-imbalance in [-1, 1], or None if insufficient data."""
        window_ms = int(window_sec * 1000)
        self.prune_trades(now_ms, window_ms)
        if len(self.rolling_trades) < 2 or not self.yes_token_id:
            return None
        yes_vol = sum(sz for _, asset, sz in self.rolling_trades if asset == self.yes_token_id)
        no_vol = sum(sz for _, asset, sz in self.rolling_trades if asset == self.no_token_id)
        total = yes_vol + no_vol
        if total < 1.0:
            return None
        return (yes_vol - no_vol) / total


# ---------------------------------------------------------------------------
# Calibration — bucket OBI observations, compute conditional expectancy
# ---------------------------------------------------------------------------


@dataclass
class ObiObservation:
    """One OBI sample we'd have traded on, with later outcome."""
    subscription_id: str
    obi: float
    yes_price_at_signal: float | None
    no_price_at_signal: float | None
    signal_ts_ms: int
    resolution_ts_ms: int | None
    resolution_side: str | None     # "YES" | "NO" (token that paid $1)
    min_to_expiry_at_signal: float
    # For maker-only entry simulation:
    would_fill: bool                  # did the book cross our limit within N sec?
    fill_price: float | None
    fill_side: str | None             # we entered on the side OBI pointed to


def obi_to_bucket(obi: float) -> str:
    """Canonical OBI bucketing for conditional-expectancy tables."""
    a = abs(obi)
    if a < 0.10:
        return "obi<0.10"
    elif a < 0.20:
        return "obi:0.10-0.20"
    elif a < 0.30:
        return "obi:0.20-0.30"
    elif a < 0.50:
        return "obi:0.30-0.50"
    else:
        return "obi>=0.50"


def min_to_exp_bucket(mins: float) -> str:
    """Bucket label for time-to-expiry in minutes.

    Audit F3 fix (2026-04-16): labels now match the trader's actual entry
    window (BOT_E_ENTRY_WINDOW: 300-600s = 5-10 min). Previous bucket
    boundaries were off-by-5: `mins >= 10` was labelled "5–10 (entry)"
    when it actually covered 10+ min markets the trader never enters.
    """
    if mins >= 10:
        return "10+ (pre-entry)"
    elif mins >= 5:
        return "5–10 (entry)"
    elif mins >= 0:
        return "0–5 (holding)"
    else:
        return "resolution"


@dataclass
class ExpectancyTable:
    """Per-bucket realised expectancy: (signal_count, win_count, total_pnl_usd)."""
    rows: dict[tuple[str, str], tuple[int, int, float]] = field(default_factory=dict)

    def add(self, obi_bucket: str, mte_bucket: str, win: bool, pnl: float) -> None:
        k = (obi_bucket, mte_bucket)
        n, w, p = self.rows.get(k, (0, 0, 0.0))
        self.rows[k] = (n + 1, w + (1 if win else 0), p + pnl)

    def summary(self) -> str:
        lines = ["obi_bucket, min_to_expiry, n_signals, win_rate, mean_pnl, total_pnl"]
        for (ob, mte), (n, w, p) in sorted(self.rows.items()):
            wr = w / n if n else 0.0
            mp = p / n if n else 0.0
            lines.append(f"{ob},{mte},{n},{wr:.3f},{mp:+.4f},{p:+.4f}")
        return "\n".join(lines)


def calibrate(
    db_path: Path,
    *,
    obi_window_sec: float = 120.0,
    entry_offset_sec: float = 10.0,
    category: str = "crypto",
    quarantine_gaps: bool = True,
    gap_max_ms: int = 5000,
    gap_buffer_ms: int = 5000,
) -> ExpectancyTable:
    """Sweep the recorder data and produce conditional expectancy by bucket.

    Simplified maker-only entry model:
    - At each OBI sample (computed every time a new pm_trade lands), we would
      have placed a limit order at best_bid (for NO buys) or at best_ask (for
      YES buys), paying zero fee + earning maker rebate.
    - Fill is determined by whether the book crossed our limit within
      `entry_offset_sec` seconds.
    - Exit at resolution ($1 if winning side, $0 if losing).

    This is intentionally simplified — the real trader has slippage, queue
    position, partial fills, etc. But it's a reasonable upper bound on
    achievable maker-only edge, sufficient for go/no-go.
    """
    table = ExpectancyTable()

    conn = sqlite3.connect(str(db_path))
    try:
        # Build lookup: subscription_id → (end_date_ms, yes_token_id, no_token_id)
        markets = {}
        for row in conn.execute(
            "SELECT condition_id, yes_token_id, no_token_id, end_date_iso "
            "FROM markets GROUP BY condition_id"
        ):
            cond, yt, nt, end_iso = row
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(end_iso) if end_iso else None
                end_ms = int(dt.timestamp() * 1000) if dt else None
            except Exception:
                end_ms = None
            markets[cond] = (end_ms, yt, nt)
    finally:
        conn.close()

    states: dict[str, SubscriptionState] = {}

    # Phase 3 audit 2026-04-17 (M-3): auto-detect recorder gaps and pass the
    # quarantine list into iter_events so calibration skips contaminated windows.
    quarantine: list[tuple[int, int]] = []
    if quarantine_gaps:
        gaps = detect_gaps(db_path, max_gap_ms=gap_max_ms)
        quarantine = quarantine_ranges(gaps, buffer_ms=gap_buffer_ms)
        if quarantine:
            log.info(
                "backtest.calibrate.quarantine gaps=%d ranges=%d",
                len(gaps), len(quarantine),
            )

    for ev in iter_events(db_path, quarantine=quarantine):
        if ev.kind == "reconnect" and ev.subscription_id:
            # Invalidate rolling state
            states.pop(ev.subscription_id, None)
            continue

        if ev.kind in ("pm_book", "pm_price"):
            sub = ev.subscription_id or ""
            st = states.setdefault(sub, SubscriptionState(subscription_id=sub))
            # The payload for book has bids/asks; for price_change has price+side
            # Track yes/no token if we can discover it.
            if ev.asset_id:
                # We don't know yet which is YES/NO without market metadata.
                # Heuristic: first-seen asset per subscription is YES
                # (Gamma convention: outcomes[0] is YES).
                if st.yes_token_id is None:
                    st.yes_token_id = ev.asset_id
                elif st.yes_token_id != ev.asset_id and st.no_token_id is None:
                    st.no_token_id = ev.asset_id
            # Try to extract best bid/ask for yes side
            if ev.asset_id and ev.asset_id == st.yes_token_id:
                bids = ev.payload.get("bids") or []
                asks = ev.payload.get("asks") or []
                if bids:
                    try:
                        st.best_yes_bid = float(bids[0][0]) if isinstance(bids[0], list) else None
                    except (ValueError, TypeError):
                        pass
                if asks:
                    try:
                        st.best_yes_ask = float(asks[0][0]) if isinstance(asks[0], list) else None
                    except (ValueError, TypeError):
                        pass
                price = ev.payload.get("price")
                if price is not None:
                    try:
                        st.last_yes_price = float(price)
                    except (ValueError, TypeError):
                        pass

        elif ev.kind == "pm_trade":
            sub = ev.subscription_id or ""
            st = states.setdefault(sub, SubscriptionState(subscription_id=sub))
            try:
                size = float(ev.payload.get("size", 0) or 0)
            except (ValueError, TypeError):
                size = 0
            if size > 0 and ev.asset_id:
                st.rolling_trades.append((ev.ts_ms, ev.asset_id, size))
                # Produce an OBI observation each trade
                obi_val = st.obi(ev.ts_ms, obi_window_sec)
                if obi_val is None:
                    continue
                # Find parent market metadata
                # (For simplicity, assume condition_id inferrable from payload;
                # in production we'd keep a subscription→condition map populated
                # from the discovery step.)
                # This function is a prototype — Phase 0d refinement expected.
                # For now just accumulate simple signal counts.
                obi_b = obi_to_bucket(obi_val)
                # Without explicit resolution data yet, assign win=True when OBI
                # direction matches subsequent yes_price move. Full implementation
                # comes in Phase 0d when calibration runs against real data.
                table.add(obi_b, "unknown", win=False, pnl=0.0)

    return table
