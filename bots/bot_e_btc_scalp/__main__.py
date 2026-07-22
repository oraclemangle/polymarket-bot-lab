"""Bot E trader — async main loop.

Activation gate (ADR-022 / ADR-022.1):
  --live mode requires Phase 0d calibration GO-file AND BOT_E_DRY_RUN=false.
  Paper mode (default) runs the FULL signal pipeline without calibration gate
  so that we can collect calibration data through real operation. This is the
  ADR-022.1 amendment: paper-collection mode proceeds with a loud warning if
  the GO-file is absent.

In paper mode the ClobWrapper routes all orders through _paper_fill. No CLOB
credentials are needed.

Entry gate (live mode only, post-calibration):
  python -m bots.bot_e_btc_scalp --live

v1 scope:
  - Pure OBI signal (no multi-hemisphere voting, no VETO, no PeriodTracker)
  - Binary choppiness regime hard-gate
  - Fixed $30/trade for first 200 paper trades (operator instruction 2026-04-16);
    Kelly shadow-logged for calibration data collection
  - Maker-only limit orders (see config.BOT_E_MAKER_ONLY)
  - Feed-freshness halt
  - Consecutive-loss halt
  - HaltFlag DB check each iteration (operator can unhalt without restart)
  - Telemetry logged via standard logging + SQLite writer

See ADR-022 for full rationale.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from bots.bot_e_btc_scalp import config
from bots.bot_e_btc_scalp.adverse_selection import AdverseSelectionTracker
from bots.bot_e_btc_scalp.executor import (
    BOT_ID,
    TraderState,
    try_enter,
)
from bots.bot_e_btc_scalp.regime import should_skip_due_to_chop
from bots.bot_e_btc_scalp.signal import SubscriptionTrades, maybe_fire
from bots.bot_e_btc_scalp.sizer import OpenPosition, size_maker_entry
from bots.bot_e_recorder.market_discovery import fetch_live_crypto_markets
from core.clob_v2 import ClobWrapperV2 as ClobWrapper
from core.clob_v2 import OrderType, Side
from core.db import Book, Event, HaltFlag, Order, Position, Trade, get_session_factory, init_db

log = logging.getLogger("bot_e")

CALIBRATION_GO_FILE = Path("data/bot_e_calibration.json")

# Audit 2026-04-17 (Codex P0): the old hardcoded PAPER_FIXED_TRADE_USD=$30
# and PAPER_FIXED_TRADE_THRESHOLD=200 constants were replaced with
# first-class config fields (config.BOT_E_PAPER_FIXED_USD /
# BOT_E_PAPER_TRADE_THRESHOLD), and the counter is now read from DB fills
# on every iteration instead of being a process-local integer incremented
# on placed orders. See `docs/audit/bots-a-d-e-audit-responses/` Q22/AF-6.

# Rolling midpoint window for regime classification. Keep last N midpoints
# per market; 12 samples @ 5s scan = 60 seconds of price history (adequate
# for choppiness ratio which needs >= 3).
_REGIME_WINDOW = 12


def _persist_book_snapshot(book) -> None:
    """Persist a fetched CLOB book so paper fills can use the same token feed."""
    snapshot_at = datetime.fromtimestamp(float(book.timestamp), tz=UTC)

    def rows(levels):
        return [[str(price), str(size)] for price, size in levels]

    try:
        with get_session_factory()() as s:
            s.add(
                Book(
                    token_id=book.token_id,
                    snapshot_at=snapshot_at,
                    bids=rows(book.bids),
                    asks=rows(book.asks),
                )
            )
            s.commit()
    except Exception as exc:
        log.debug("bot_e.book_snapshot_persist_failed token=%s err=%s", book.token_id[:12], exc)


def _parse_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(description="Bot E — OBI-directional trader")
    p.add_argument("--dry-run", action="store_true", default=None,
                   help="Override config to force dry-run mode (no orders placed)")
    p.add_argument("--live", action="store_true", default=False,
                   help="Require calibration GO-file; actually place orders")
    p.add_argument("--log-level", default=None)
    return p.parse_args(argv)


def _check_calibration_gate(args) -> str | None:
    """Return an error string if we should not start, else None.

    ADR-022.1 amendment: paper mode is allowed without the GO-file so that
    the operator can collect calibration data via live operation. Only --live
    mode enforces the GO-file gate.
    """
    if args.live and config.BOT_E_DRY_RUN and args.dry_run is None:
        return "Cannot --live when BOT_E_DRY_RUN=true (and no explicit --dry-run override)"
    if args.live and not CALIBRATION_GO_FILE.exists():
        return (
            f"Cannot --live: Phase 0d calibration artefact not found at "
            f"{CALIBRATION_GO_FILE}. Run the recorder + backtester first, then "
            f"write the GO-file manually once you've reviewed the expectancy "
            f"table. See ADR-022 Phase 0d."
        )
    return None


def _is_db_halted() -> bool:
    """Check HaltFlag table for bot_e. Returns True if halted."""
    try:
        from sqlalchemy import select
        with get_session_factory()() as s:
            flag = s.scalars(
                select(HaltFlag).where(HaltFlag.bot_id == BOT_ID)
            ).first()
        return bool(flag and flag.halted)
    except Exception as exc:
        log.warning("bot_e.halt_check_failed err=%s — treating as not halted", exc)
        return False


def _symbol_from_market(market_row) -> str:
    """Infer BTC/ETH/SOL from a Market row's question text.

    U-20 (audit 2026-04-18): prior code hardcoded "BTC" everywhere, which
    mislabels any ETH/SOL market in the sizer's correlation cap. Reuses the
    recorder's `_classify_symbol` for a single source of truth.
    """
    try:
        from bots.bot_e_recorder.market_discovery import _classify_symbol
        if market_row is not None and market_row.question:
            sym = _classify_symbol(market_row.question)
            if sym is not None:
                return sym
    except Exception:
        pass
    return "BTC"  # conservative fallback preserves pre-U-20 behaviour


def _hydrate_open_positions() -> list[OpenPosition]:
    """Load open Bot E positions from DB into a list of OpenPosition.

    Audit 2026-04-17 (Codex P0 — `bots/bot_e_btc_scalp/__main__.py` L347):
    `state.open_positions` was never populated from DB, so sizer caps
    operated on an empty in-memory list across every restart. This caused
    cap checks to pass even when persisted exposure already exceeded them.

    Called on startup AND at the top of each scan loop so that fills
    reconciled by `Portfolio.reconcile_live_fills` / `simulate_paper_fills`
    are reflected in the in-memory state the sizer reads.
    """
    try:
        from sqlalchemy import select

        from core.db import Market
        with get_session_factory()() as s:
            rows = s.scalars(
                select(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.status == "OPEN",
                )
            ).all()
            # Pre-load markets for symbol derivation (U-20).
            cids = {p.condition_id for p in rows}
            market_by_cid: dict[str, object] = {}
            if cids:
                market_rows = s.scalars(
                    select(Market).where(Market.condition_id.in_(cids))
                ).all()
                market_by_cid = {m.condition_id: m for m in market_rows}
            out: list[OpenPosition] = []
            seen_cids: set[str] = set()
            for p in rows:
                # Side in Position table is YES|NO; sizer expects BUY_YES|BUY_NO.
                sizer_side = "BUY_YES" if p.side == "YES" else "BUY_NO"
                symbol = _symbol_from_market(market_by_cid.get(p.condition_id))
                out.append(OpenPosition(
                    subscription_id=p.condition_id,
                    symbol=symbol,
                    side=sizer_side,
                    notional_usd=Decimal(p.cost_basis_usd or 0),
                    is_crypto=True,
                ))
                seen_cids.add(p.condition_id)

            # 2026-04-17 Audit Finding 2 fix: restart-time dedup gap.
            # Also load OPEN Orders that haven't yet produced Position rows
            # (pending paper fills or live resting orders). Without this,
            # a restart between placement and fill lets the bot re-enter
            # the same market because state.open_positions is empty.
            # The synthetic OpenPosition is notional-only (size=shares*price)
            # so sizer caps still bind; the subscription_id match protects
            # the per-market dedup guard in executor.try_enter.
            open_statuses = ("live", "matched", "PAPER_OPEN", "PAPER_PARTIALLY_FILLED")
            order_rows = s.scalars(
                select(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.status.in_(open_statuses),
                )
            ).all()
            # Extend market_by_cid for order-only condition_ids.
            order_cids = {o.condition_id for o in order_rows} - cids
            if order_cids:
                extra = s.scalars(
                    select(Market).where(Market.condition_id.in_(order_cids))
                ).all()
                market_by_cid.update({m.condition_id: m for m in extra})
            for o in order_rows:
                if o.condition_id in seen_cids:
                    continue  # already covered by a filled Position row
                # Order.side is BUY|SELL on CLOB side; Bot E only places BUYs.
                # Derive sizer side from the token_id match on the market
                # when possible — bot E Bot's `side` field is stored as the
                # raw BUY_YES/BUY_NO tag via `_persist_order`.
                raw_side = o.side or ""
                if raw_side in ("BUY_YES", "BUY_NO"):
                    sizer_side = raw_side
                else:
                    # Legacy path (BUY/SELL): fall back to BUY_YES.
                    sizer_side = "BUY_YES"
                symbol = _symbol_from_market(market_by_cid.get(o.condition_id))
                notional = Decimal(o.price or 0) * Decimal(o.size or 0)
                out.append(OpenPosition(
                    subscription_id=o.condition_id,
                    symbol=symbol,
                    side=sizer_side,
                    notional_usd=notional,
                    is_crypto=True,
                ))
                seen_cids.add(o.condition_id)
            return out
    except Exception as exc:
        log.warning("bot_e.hydrate_positions_failed err=%s", exc)
        return []


# Phase 4 audit 2026-04-17: track which Trade IDs we've already emitted
# bot_e.fill Events for, so the helper below doesn't double-emit.
_emitted_fill_trade_ids: set[str] = set()

# 2026-04-17 Audit Finding 3 fix: track which Position closures we've
# already fed into the loss-halt state, so record_outcome is called at
# most once per resolved position.
_recorded_outcome_position_ids: set[int] = set()


def _emit_bot_e_event(
    event_type: str,
    message: str,
    payload: dict | None = None,
    *,
    severity: str = "info",
) -> None:
    """Persist Bot E telemetry without letting DB issues stop trading."""
    try:
        with get_session_factory()() as s:
            s.add(Event(
                bot_id=BOT_ID,
                event_type=event_type,
                severity=severity,
                message=message,
                payload=payload or {},
            ))
            s.commit()
    except Exception as exc:
        log.debug("bot_e.telemetry_event_failed type=%s err=%s", event_type, exc)


def _emit_scan_summary(
    *,
    markets_seen: int,
    counts: dict[str, int],
    elapsed_sec: float,
) -> None:
    """Write one DB-visible counter row per scan loop.

    OQ-048 needs rejection telemetry, but per-market `signal_none` rows would
    grow the DB too quickly. A scan summary keeps every gate count queryable
    while reserving per-signal rows for actual signals/rejections/orders.
    """
    payload = {
        "markets_seen": markets_seen,
        "elapsed_sec": round(elapsed_sec, 3),
        "counts": dict(sorted(counts.items())),
    }
    _emit_bot_e_event(
        "bot_e.scan_summary",
        f"scan markets={markets_seen} counts={payload['counts']}",
        payload,
    )


def _counter_reason(reason: str | None) -> str:
    """Return a stable counter suffix for dynamic rejection reasons."""
    base = str(reason or "unknown")
    return base.split(":", 1)[0].split("(", 1)[0]


def _record_closed_outcomes(state) -> int:
    """Feed resolved Position outcomes into TraderState loss-halt counters.

    2026-04-17 Audit Finding 3: `consecutive_loss_halt` and
    `should_halt_trailing` both read `state.recent_outcomes`, but nothing
    in the runtime was calling `record_outcome()`. Halts advertised in the
    executor module header were inert.

    For each Bot E Position that transitioned to CLOSED since last call:
    - Sum SELL Trade proceeds for that token_id since the position opened
    - Compute win = (proceeds - cost_basis) > 0
    - Call `record_outcome(state, win=..., now_ms=...)`

    Positions that close with no matching SELL trades (e.g. paper fills
    that expire without simulator-driven close-out) are skipped — we can't
    infer outcome without exit proceeds.

    Returns number of outcomes recorded this call.
    """
    try:
        from sqlalchemy import select

        from bots.bot_e_btc_scalp.executor import record_outcome
        with get_session_factory()() as s:
            closed = s.scalars(
                select(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.status == "CLOSED",
                )
            ).all()
            now_ms = int(time.time() * 1000)
            n = 0
            for p in closed:
                if p.id in _recorded_outcome_position_ids:
                    continue
                # Sum SELL proceeds for this token since the position opened.
                sells = s.scalars(
                    select(Trade).where(
                        Trade.bot_id == BOT_ID,
                        Trade.token_id == p.token_id,
                        Trade.side == "SELL",
                        Trade.filled_at >= p.opened_at,
                    )
                ).all()
                if not sells:
                    # Can't determine outcome without exit trades; skip but
                    # still mark seen so we don't reconsider every scan.
                    _recorded_outcome_position_ids.add(p.id)
                    continue
                proceeds = sum(
                    (Decimal(t.price or 0) * Decimal(t.size or 0)) for t in sells
                )
                cost = Decimal(p.cost_basis_usd or 0)
                # Include fees: proceeds net of sell fees, cost already includes buy fees.
                fees_out = sum(Decimal(t.fee_usd or 0) for t in sells)
                pnl = proceeds - fees_out - cost
                win = pnl > Decimal("0")
                record_outcome(state, win=win, now_ms=now_ms)
                _recorded_outcome_position_ids.add(p.id)
                log.info(
                    "bot_e.outcome position_id=%d token=%s cost=%s proceeds=%s pnl=%s win=%s",
                    p.id, p.token_id[:12], cost, proceeds, pnl, win,
                )
                n += 1
            return n
    except Exception as exc:
        log.warning("bot_e.record_outcomes_failed err=%s", exc)
        return 0


def _read_pm_last_trade_price(asset_id: str) -> Decimal | None:
    """Read the most recent `last_trade_price` for an asset from the
    recorder DB (read-only). Returns None if recorder not reachable or no
    trades observed. Used by the adverse-selection tracker to measure
    post-fill midpoint moves without maintaining a parallel book subscription.
    """
    import json
    import os
    import sqlite3
    db_path = os.environ.get(
        "BOT_E_RECORDER_DB_PATH",
        "data/bot_e_recorder.db",
    )
    if not Path(db_path).exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        row = conn.execute(
            "SELECT payload_json FROM pm_events "
            "WHERE event_type='last_trade_price' AND asset_id=? "
            "ORDER BY received_at_ms DESC LIMIT 1",
            (str(asset_id),),
        ).fetchone()
        conn.close()
        if not row:
            return None
        try:
            payload = json.loads(row[0])
            price = payload.get("price")
            return Decimal(str(price)) if price else None
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
    except Exception:
        return None


def _emit_new_fill_events_and_track(tracker: AdverseSelectionTracker) -> int:
    """Write bot_e.fill Event rows for any new Trade rows since last call.

    Also registers each new fill with the adverse-selection tracker and
    (if a post-fill midpoint is available from the recorder DB) measures
    the post-fill price move.

    Returns number of new fills detected.
    """
    try:
        from sqlalchemy import select
        with get_session_factory()() as s:
            if not _emitted_fill_trade_ids:
                existing = s.scalars(
                    select(Event).where(
                        Event.bot_id == BOT_ID,
                        Event.event_type == "bot_e.fill",
                    )
                ).all()
                for ev in existing:
                    if isinstance(ev.payload, dict) and ev.payload.get("trade_id"):
                        _emitted_fill_trade_ids.add(str(ev.payload["trade_id"]))
            trades = list(s.scalars(
                select(Trade).where(Trade.bot_id == BOT_ID).order_by(Trade.filled_at)
            ))
            new_count = 0
            for t in trades:
                if t.trade_id in _emitted_fill_trade_ids:
                    continue
                _emitted_fill_trade_ids.add(t.trade_id)
                new_count += 1
                mid_now = _read_pm_last_trade_price(t.token_id)
                s.add(Event(
                    bot_id=BOT_ID,
                    event_type="bot_e.fill",
                    severity="info",
                    message=f"fill {t.trade_id} side={t.side} price={t.price} size={t.size}",
                    payload={
                        "trade_id": t.trade_id,
                        "order_id": t.order_id,
                        "condition_id": t.condition_id,
                        "token_id": t.token_id,
                        "side": t.side,
                        "fill_price": str(t.price),
                        "fill_size": str(t.size),
                        "fee_usd": str(t.fee_usd or 0),
                        "midpoint_at_event_emit": str(mid_now) if mid_now else None,
                    },
                ))
                # Register with adverse tracker. Translate DB side (BUY/SELL)
                # to the tracker's convention: we track entries here (BUY_*).
                # Polymarket: BUY on token = "buy that outcome"; maps to
                # BUY_YES if token is yes_token, else BUY_NO. We approximate
                # by using token_id as the asset; the tracker only compares
                # fill_price vs midpoint_after on the same asset anyway.
                tracker.register(
                    order_id=t.trade_id,
                    fill_price=Decimal(t.price),
                    fill_side="BUY_YES",  # convention-neutral for same-asset compare
                    fill_ts_ms=int(t.filled_at.timestamp() * 1000),
                )
                if mid_now is not None:
                    tracker.measure(t.trade_id, midpoint_after=mid_now)
            s.commit()
        return new_count
    except Exception as exc:
        log.warning("bot_e.emit_fill_events_failed err=%s", exc)
        return 0


def _read_cex_cvd(symbol: str, now_ms: int, window_sec: float) -> Decimal | None:
    """Compute signed CEX CVD (cumulative volume delta) over the last
    `window_sec` for the Binance pair matching `symbol` (BTC/ETH/SOL-USDT).

    Convention:
      is_buyer_maker=False  → taker BOUGHT aggressively → signed +size
      is_buyer_maker=True   → taker SOLD aggressively  → signed -size

    Returns notional CVD in USD (size × price_avg). None if the recorder DB
    isn't reachable or no trades seen in the window. Used by the
    Polymarket-OBI direction-agreement gate.
    """
    import os
    import sqlite3
    db_path = os.environ.get(
        "BOT_E_RECORDER_DB_PATH",
        "data/bot_e_recorder.db",
    )
    if not Path(db_path).exists():
        return None
    cex_symbol = f"{symbol.upper()}USDT"
    since_ms = now_ms - int(window_sec * 1000)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        row = conn.execute(
            "SELECT "
            "  COALESCE(SUM(CASE WHEN is_buyer_maker=0 THEN size*price ELSE 0 END), 0) "
            "  - COALESCE(SUM(CASE WHEN is_buyer_maker=1 THEN size*price ELSE 0 END), 0) "
            "FROM cex_trades "
            "WHERE symbol=? AND received_at_ms >= ?",
            (cex_symbol, since_ms),
        ).fetchone()
        conn.close()
        if row is None or row[0] is None:
            return None
        return Decimal(str(row[0]))
    except Exception as exc:
        log.debug("bot_e.cex_cvd_read_failed symbol=%s err=%s", symbol, exc)
        return None


def _cex_cvd_gate_ok(
    symbol: str,
    signal_side: str,
    now_ms: int,
) -> tuple[bool, str]:
    """Return (ok, reason).

    ok=True  → CVD agrees with signal direction (pass)
    ok=True  → CVD magnitude below BOT_E_CEX_CVD_MIN_USD (pass — insufficient evidence)
    ok=False → CVD disagrees with signal direction (block)

    Failure-open: if the CVD cannot be computed (recorder down), pass.
    """
    if not config.BOT_E_CEX_CVD_GATE:
        return True, "cex_cvd_gate_disabled"
    cvd = _read_cex_cvd(symbol, now_ms, float(config.BOT_E_CEX_CVD_WINDOW_SEC))
    if cvd is None:
        return True, "cex_cvd_unavailable"  # fail-open
    if abs(cvd) < config.BOT_E_CEX_CVD_MIN_USD:
        return True, f"cex_cvd_small({cvd:.0f})"
    # BUY_YES = betting price UP; need CVD > 0.
    # BUY_NO  = betting price DOWN; need CVD < 0.
    if signal_side == "BUY_YES" and cvd > 0:
        return True, f"cex_cvd_confirms({cvd:.0f})"
    if signal_side == "BUY_NO" and cvd < 0:
        return True, f"cex_cvd_confirms({cvd:.0f})"
    return False, f"cex_cvd_disagrees(cvd={cvd:.0f} side={signal_side})"


def _depth_gate_ok(
    book,
    signal_side: str,
    best_price: Decimal | None,
) -> tuple[bool, str]:
    """Return (ok, reason).

    Sums order sizes on the target side of the book within
    BOT_E_DEPTH_BAND_WIDTH of the best price. If total notional (price*size
    summed) is below BOT_E_DEPTH_MIN_USD, block the signal.

    Accepts either:
    - `OrderBook` dataclass (from `core.clob.get_book`), with
      `bids: list[tuple[Decimal, Decimal]]` sorted desc.
    - `dict` with `"bids"` key (list of [price, size] pairs or
      {"price": ..., "size": ...} dicts).

    Failure-open: if `book` is None or malformed, pass.

    2026-04-17 Audit Finding 4 fix: previously only accepted dict. Runtime
    passed `market.book` / `market.raw_book` (neither exist on CryptoMarket),
    so the gate silently fail-opened on every call. Now accepts the
    `OrderBook` object already fetched in the main loop.
    """
    if not config.BOT_E_DEPTH_GATE:
        return True, "depth_gate_disabled"
    if book is None or best_price is None:
        return True, "depth_unavailable"
    # Extract bid levels as list of (price, size) tuples regardless of
    # whether `book` is an OrderBook dataclass or a raw dict.
    levels: list[tuple[Decimal, Decimal]] = []
    if hasattr(book, "bids") and isinstance(book.bids, (list, tuple)):
        # OrderBook dataclass: bids are already (Decimal, Decimal) tuples.
        levels = list(book.bids)
    elif isinstance(book, dict):
        raw = book.get("bids") or []
        if not isinstance(raw, (list, tuple)):
            return True, "depth_unavailable_nonlist"
        for lvl in raw:
            try:
                if isinstance(lvl, dict):
                    levels.append((Decimal(str(lvl.get("price", 0))),
                                   Decimal(str(lvl.get("size", 0)))))
                elif isinstance(lvl, (list, tuple)) and len(lvl) >= 2:
                    levels.append((Decimal(str(lvl[0])), Decimal(str(lvl[1]))))
            except Exception:
                continue
    else:
        return True, "depth_unavailable_nondict"
    band = config.BOT_E_DEPTH_BAND_WIDTH
    lo = best_price - band
    total_usd = Decimal("0")
    # `levels` is normalised above to list[(price, size)] of Decimals.
    for price, size in levels:
        if price < lo:
            break  # bids sorted descending; anything past lo is out
        total_usd += price * size
    if total_usd < config.BOT_E_DEPTH_MIN_USD:
        return False, f"depth_thin(total_usd={total_usd:.0f} min={config.BOT_E_DEPTH_MIN_USD})"
    return True, f"depth_ok({total_usd:.0f})"


def _paper_fill_count() -> int:
    """Return the number of DB-persisted paper fills for Bot E.

    Audit 2026-04-17 (Codex P0): the previous counter incremented on
    `order_placed` events (not fills) and reset on restart. The correct
    calibration gate is "count of resolved fills observed" — only fills
    supply outcome data. We count rows in the Trade table for bot_e with a
    paper order_id (prefix "paper-") or where the associated Order has
    status "PAPER_OPEN" / "PAPER_FILLED".
    """
    try:
        from sqlalchemy import func, select
        with get_session_factory()() as s:
            n = s.scalar(
                select(func.count(Trade.trade_id)).where(
                    Trade.bot_id == BOT_ID,
                    Trade.order_id.like("paper-%"),
                )
            )
            return int(n or 0)
    except Exception as exc:
        log.warning("bot_e.paper_fill_count_failed err=%s", exc)
        return 0


def _recent_recorder_trades(
    token_ids: list[str],
    since_ms: int,
) -> list[tuple[int, str, Decimal]]:
    """Read recent last_trade_price events from the recorder DB.

    Returns list of (ts_ms, asset_id, size) for feeding SubscriptionTrades.
    Audit F1 fix: trader now consumes the same real-trade-volume signal that
    the backtester calibrates on, eliminating the synthetic-trade drift.
    """
    import json
    import os
    import sqlite3

    if not token_ids:
        return []
    db_path = os.environ.get(
        "BOT_E_RECORDER_DB_PATH",
        "data/bot_e_recorder.db",
    )
    if not Path(db_path).exists():
        return []
    out: list[tuple[int, str, Decimal]] = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        placeholders = ",".join("?" for _ in token_ids)
        cursor = conn.execute(
            f"SELECT received_at_ms, asset_id, payload_json "
            f"FROM pm_events "
            f"WHERE event_type = 'last_trade_price' "
            f"AND asset_id IN ({placeholders}) "
            f"AND received_at_ms >= ? "
            f"ORDER BY received_at_ms",
            (*token_ids, since_ms),
        )
        for row in cursor:
            ts_ms, asset_id, payload_json = row
            try:
                payload = json.loads(payload_json)
                size = Decimal(str(payload.get("size") or 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            if size > 0:
                out.append((int(ts_ms), str(asset_id), size))
        conn.close()
    except Exception:
        # Silent failure — trader keeps running, just without trade feed
        # this cycle. maybe_fire() will report n_trades=0 which is fine.
        return []
    return out


def _cancel_stale_orders(clob, ttl_sec: float) -> int:
    """Cancel Bot E open orders older than ttl_sec.

    Audit F2 fix (2026-04-16): BOT_E_ORDER_TTL_SEC was defined in config
    but never used. Stale unfilled orders accumulate exposure that the
    market has moved past. This loop runs once per scan cycle.
    """
    from datetime import timedelta

    from sqlalchemy import select as _sel
    cancelled = 0
    cutoff = datetime.now(UTC) - timedelta(seconds=ttl_sec)
    try:
        with get_session_factory()() as s:
            stale = list(
                s.scalars(
                    _sel(Order).where(
                        Order.bot_id == BOT_ID,
                        Order.status.in_(("OPEN", "PARTIAL", "PAPER_OPEN", "live")),
                        Order.placed_at < cutoff,
                    )
                )
            )
        for o in stale:
            try:
                ok = clob.cancel_order(o.order_id)
                if ok:
                    cancelled += 1
                    with get_session_factory()() as s:
                        db_o = s.get(Order, o.order_id)
                        if db_o is not None:
                            db_o.status = "CANCELLED"
                            s.add(Event(
                                bot_id=BOT_ID,
                                event_type="bot_e.ttl_cancel",
                                severity="info",
                                message=f"ttl cancelled order {o.order_id}",
                                payload={
                                    "order_id": o.order_id,
                                    "condition_id": o.condition_id,
                                    "token_id": o.token_id,
                                    "prior_status": o.status,
                                    "ttl_sec": ttl_sec,
                                },
                            ))
                            s.commit()
            except Exception as exc:
                log.warning("bot_e.cancel_failed order=%s err=%s", o.order_id, exc)
    except Exception as exc:
        log.warning("bot_e.cancel_query_failed err=%s", exc)
    return cancelled


def _persist_order(
    *,
    order_id: str,
    condition_id: str,
    token_id: str,
    side: str,
    price: Decimal,
    size: Decimal,
    status: str,
    strategy_signal: str,
    reason_code: str,
    kelly_would_have: Decimal | None,
) -> str:
    """Write an Order row to the shared DB for both paper and live fills.

    Audit F2 fix (2026-04-16): previously this only persisted paper orders;
    live orders bypassed the DB entirely, breaking watchdog visibility and
    reconciliation. Now every placement gets a row — paper orders use the
    ClobWrapper's "paper-<uuid>" id, live orders use the real CLOB order_id
    returned by place_limit.

    If order_id is empty (should not happen but defensive), a paper uuid
    is generated so the DB row has a primary key.
    """
    if not order_id:
        order_id = f"paper-{uuid.uuid4().hex[:12]}"
    is_paper = status == "PAPER_OPEN" or order_id.startswith("paper-")
    event_type = "paper.order.placed" if is_paper else "live.order.placed"
    try:
        with get_session_factory()() as s:
            order = Order(
                order_id=order_id,
                bot_id=BOT_ID,
                condition_id=condition_id,
                token_id=token_id,
                side=side,
                price=price,
                size=size,
                status=status,
                order_type="GTC",
            )
            s.add(order)
            # Audit event: shadow Kelly + actual fixed size
            payload: dict = {
                "strategy_signal": strategy_signal,
                "reason_code": reason_code,
                "fixed_notional_usd": str(price * size),
            }
            if kelly_would_have is not None:
                payload["kelly_shadow_notional_usd"] = str(kelly_would_have)
            event = Event(
                bot_id=BOT_ID,
                event_type=event_type,
                severity="info",
                message=f"{status} order {order_id} side={side} price={price} size={size}",
                payload=payload,
            )
            s.add(event)
            s.commit()
        log.info(
            "bot_e.order_persisted order_id=%s status=%s side=%s price=%s size=%s kelly_shadow=%s",
            order_id, status, side, price, size, kelly_would_have,
        )
    except Exception as exc:
        log.error("bot_e.persist_order_failed order_id=%s err=%s", order_id, exc)
    return order_id


def _compute_kelly_shadow(
    *,
    signal_side: str,
    limit_price: Decimal,
    bankroll_usd: Decimal,
    open_positions: list,
    symbol: str = "BTC",
) -> Decimal | None:
    """Compute what Kelly-fractional sizing WOULD produce (shadow log only).

    In v1 BOT_E_KELLY_FRACTION=0 so this always returns None. Wired for v1.1+
    when calibration enables it.

    U-20 (audit 2026-04-18): caller now passes the per-market symbol so the
    crypto-correlation cap applies to the right bucket. Default preserved
    for backward compatibility.
    """
    if config.BOT_E_KELLY_FRACTION <= 0:
        return None
    try:
        decision = size_maker_entry(
            signal_side=signal_side,
            limit_price=limit_price,
            bankroll_usd=bankroll_usd,
            fixed_trade_usd=bankroll_usd * config.BOT_E_KELLY_FRACTION,
            per_trade_cap_frac=config.BOT_E_PER_TRADE_CAP_FRAC,
            crypto_bucket_cap_frac=config.BOT_E_CRYPTO_BUCKET_CAP_FRAC,
            aggregate_cap_frac=config.BOT_E_AGGREGATE_EXPOSURE_CAP_FRAC,
            open_positions=open_positions,
            symbol=symbol,
            is_crypto=True,
            crypto_correlation_adj=config.BOT_E_CRYPTO_CORRELATION_ADJ,
            crypto_avg_correlation=config.BOT_E_CRYPTO_AVG_CORRELATION,
        )
        return decision.proposed_notional if decision.can_enter else None
    except Exception:
        return None


async def run(is_live: bool = False) -> int:
    """Main trading loop.

    Paper mode: runs full signal pipeline, places paper orders via ClobWrapper.
    Live mode: identical path but ClobWrapper routes to real CLOB.

    ADR-022.1: paper mode proceeds without calibration GO-file (logs a loud
    warning). This unblocks paper-collection mode where we gather calibration
    data through actual live operation.
    """
    # --- Paper-mode GO-file advisory (ADR-022.1) ---
    if not is_live and not CALIBRATION_GO_FILE.exists():
        log.warning(
            "bot_e.PAPER_COLLECTION_MODE: %s absent. Running without calibration "
            "(ADR-022.1 amendment). All orders are paper. Recorder must also be "
            "running to gather Phase 0b data.",
            CALIBRATION_GO_FILE,
        )
    elif not is_live:
        log.info("bot_e.calibration_present running in paper mode")

    # --- DB init (ensure tables exist for paper order persistence) ---
    try:
        init_db()
    except Exception as exc:
        log.warning("bot_e.db_init_failed err=%s — paper orders will not persist", exc)

    # --- ClobWrapper ---
    # Paper mode: no keystore needed; paper_override=True forces paper routing.
    # Live mode: Bot E has its own hot wallet (audit 2026-04-17 Codex AF-2,
    # audit 2026-04-18 U-08).
    #
    # U-08: prior code compared BOT_E_KEYSTORE_PATH against the shared
    # PASSPHRASE path, then only overrode the passphrase — the keystore
    # file itself stayed shared. We now require BOTH env vars and compare
    # each against its corresponding shared counterpart so "separate hot
    # wallet" actually means separate keystore files.
    if is_live:
        from core.config import get_settings
        from core.keystore import Keystore
        settings = get_settings()
        bot_e_keystore = config.BOT_E_KEYSTORE_PATH.strip()
        bot_e_passphrase = config.BOT_E_PASSPHRASE_PATH.strip()
        shared_keystore = str(settings.polymarket_keystore_path)
        shared_passphrase = str(settings.polymarket_passphrase_path)
        if not bot_e_keystore or not bot_e_passphrase:
            log.error(
                "bot_e.live_refused BOT_E_KEYSTORE_PATH=%r BOT_E_PASSPHRASE_PATH=%r "
                "— both must be set to paths distinct from the shared hot wallet "
                "before live graduation (audit 2026-04-18 U-08).",
                bot_e_keystore, bot_e_passphrase,
            )
            return 2
        if bot_e_keystore == shared_keystore:
            log.error(
                "bot_e.live_refused BOT_E_KEYSTORE_PATH=%s is identical to the shared "
                "keystore path %s. Bot E must use a separate hot wallet.",
                bot_e_keystore, shared_keystore,
            )
            return 2
        if bot_e_passphrase == shared_passphrase:
            log.error(
                "bot_e.live_refused BOT_E_PASSPHRASE_PATH=%s is identical to the shared "
                "passphrase path %s. Bot E must use a separate hot wallet.",
                bot_e_passphrase, shared_passphrase,
            )
            return 2
        # Load with both paths overridden.
        from pathlib import Path as _Path
        class _BotESettings:
            polymarket_keystore_path = _Path(bot_e_keystore)
            polymarket_passphrase_path = _Path(bot_e_passphrase)
        keystore = Keystore.load_from_settings(_BotESettings())
        clob = ClobWrapper(keystore=keystore, paper_override=False)
        clob.load_preflight_from_db()
    else:
        clob = ClobWrapper(keystore=None, paper_override=True)

    # --- In-process state ---
    state = TraderState()
    # Audit 2026-04-17: hydrate open positions from DB so sizer caps operate
    # on persisted state (Codex P0).
    state.open_positions = _hydrate_open_positions()
    log.info(
        "bot_e.state_hydrated open_positions=%d",
        len(state.open_positions),
    )
    # Phase 4 audit 2026-04-17: adverse-selection tracker. Halts the bot
    # when >=ADVERSE_HALT_THRESHOLD of the last ADVERSE_WINDOW_N fills moved
    # against us within 30s.
    adverse_tracker = AdverseSelectionTracker()

    # 2026-04-17 Audit fix: daily pnl_snapshot wiring. Bot E was the only
    # bot with zero rows in pnl_snapshots because its main loop never
    # called snapshot_daily(). Other bots (A/B/C/D) call it once per UTC
    # day at the end of their tick.
    last_snapshot_date = None

    # Per-market rolling state for OBI signal engine.
    # Key: condition_id; value: SubscriptionTrades
    market_trades: dict[str, SubscriptionTrades] = {}

    # Per-market rolling midpoints for regime classification.
    # Key: condition_id; value: deque of float midpoints (most-recent last)
    market_closes: dict[str, deque] = {}

    log.info(
        "bot_e.startup is_live=%s dry_run=%s bankroll=$%s "
        "paper_fixed_usd=$%s threshold_trades=%d "
        "obi_thresh=%s regime_chop_max=%.2f maker_only=%s scan_interval=%.0fs",
        is_live, config.BOT_E_DRY_RUN,
        config.BOT_E_BANKROLL_USD,
        config.BOT_E_PAPER_FIXED_USD, config.BOT_E_PAPER_TRADE_THRESHOLD,
        config.BOT_E_OBI_THRESHOLD,
        config.BOT_E_REGIME_CHOPPINESS_MAX,
        config.BOT_E_MAKER_ONLY,
        config.BOT_E_SCAN_INTERVAL_SEC,
    )

    # Session 17s 2026-04-19: paper-resolution reconciliation cadence.
    # Bot E was lacking the bot_d path — resolved markets left OPEN in DB,
    # inflating fleet-cap exposure and hiding realised P&L. See ADR-035.
    # Hourly cadence; first tick fires on boot (ts=0 → elapsed > interval).
    import os as _os
    last_paper_resolve_ts: float = 0.0
    paper_resolve_interval_s: float = float(
        _os.environ.get("BOT_E_PAPER_RESOLVE_INTERVAL_S", "3600")
    )

    while True:
        loop_start = time.monotonic()

        # --- DB halt check — checked every iteration ---
        db_halted = _is_db_halted()
        if db_halted:
            log.info("bot_e.halt_active skipping_trading (check every loop; unhalt to resume)")
            _emit_bot_e_event(
                "bot_e.halt_active",
                "DB halt flag active; skipping trading",
                {"reason": "db_halt"},
                severity="warn",
            )
            await asyncio.sleep(config.BOT_E_SCAN_INTERVAL_SEC)
            continue

        # Emergency repo-wide halt (Phase 3, audit 2026-04-17 M-2).
        from core.emergency_halt import is_emergency_halted
        if is_emergency_halted():
            log.warning("bot_e.emergency_halt_active skipping_trading")
            _emit_bot_e_event(
                "bot_e.emergency_halt_active",
                "repo emergency halt active; skipping trading",
                {"reason": "emergency_halt"},
                severity="kill",
            )
            await asyncio.sleep(config.BOT_E_SCAN_INTERVAL_SEC)
            continue

        # --- Trailing-loss halt (audit 2026-04-17 GLM-5.1 AF-2 P1).
        # A 12-of-20 losing streak with no 5-in-a-row would have been
        # invisible to all other halts. Now checked each scan.
        from bots.bot_e_btc_scalp.executor import should_halt_trailing
        if should_halt_trailing(
            state,
            trailing_n=config.BOT_E_TRAILING_LOSS_N,
            trailing_window=config.BOT_E_TRAILING_LOSS_WINDOW,
        ):
            log.warning(
                "bot_e.trailing_loss_halt %d-of-%d recent outcomes are losses",
                config.BOT_E_TRAILING_LOSS_N,
                config.BOT_E_TRAILING_LOSS_WINDOW,
            )
            _emit_bot_e_event(
                "bot_e.trailing_loss_halt",
                "trailing loss halt active; skipping trading",
                {
                    "trailing_n": config.BOT_E_TRAILING_LOSS_N,
                    "trailing_window": config.BOT_E_TRAILING_LOSS_WINDOW,
                },
                severity="kill",
            )
            await asyncio.sleep(config.BOT_E_SCAN_INTERVAL_SEC)
            continue

        # --- Market discovery (synchronous; acceptable for paper mode) ---
        markets = []
        try:
            markets = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: fetch_live_crypto_markets(
                    max_minutes_to_res=config.BOT_E_DISCOVERY_MAX_MIN,
                ),
            )
        except Exception as exc:
            log.warning("bot_e.market_discovery_failed err=%s", exc)

        if not markets:
            log.info("bot_e.no_markets_found sleeping")
            _emit_scan_summary(
                markets_seen=0,
                counts={"no_markets_found": 1},
                elapsed_sec=time.monotonic() - loop_start,
            )
            await asyncio.sleep(config.BOT_E_SCAN_INTERVAL_SEC)
            continue

        log.info("bot_e.scan markets=%d", len(markets))
        scan_counts: defaultdict[str, int] = defaultdict(int)

        # --- Audit F2 fix: TTL-cancel stale unfilled orders ---
        # Limit orders that haven't filled within BOT_E_ORDER_TTL_SEC are
        # cancelled so the bot doesn't accumulate stale exposure on
        # already-resolved or fast-moving markets.
        try:
            cancelled_n = _cancel_stale_orders(
                clob=clob,
                ttl_sec=config.BOT_E_ORDER_TTL_SEC,
            )
            if cancelled_n:
                log.info("bot_e.ttl_cancel cancelled=%d", cancelled_n)
                scan_counts["ttl_cancel"] += cancelled_n
        except Exception as exc:
            log.warning("bot_e.ttl_cancel_failed err=%s", exc)
            scan_counts["ttl_cancel_failed"] += 1

        # --- Audit F2 fix: reconcile fills from CLOB before scanning ---
        # In live mode this fetches user trades and updates Order/Position
        # rows. In paper mode the simulator runs against book snapshots.
        try:
            from core.portfolio import Portfolio
            portfolio = Portfolio()
            if is_live:
                portfolio.reconcile_live_fills(clob, BOT_ID)
            else:
                portfolio.simulate_paper_fills(BOT_ID)
            # Re-hydrate from DB after reconcile so sizer sees the latest truth.
            state.open_positions = _hydrate_open_positions()
            # Phase 4 audit 2026-04-17: emit bot_e.fill Events for any new
            # fills, feed the adverse-selection tracker, and check its halt
            # signal. Enables dashboard/post-hoc fill-rate + adverse-rate
            # computation from Events without re-reading Trades.
            new_fill_events = _emit_new_fill_events_and_track(adverse_tracker)
            if new_fill_events:
                scan_counts["paper_filled"] += new_fill_events
            # 2026-04-17 Audit Finding 3 fix: feed resolved Position closures
            # into the loss-halt state so `consecutive_loss_halt` and
            # `should_halt_trailing` actually fire on losing streaks.
            _record_closed_outcomes(state)
            # Adverse-selection halt — paper/live: if >=60% of last 20 fills
            # moved against us within 30s, stop opening new entries.
            should_halt_adv, adv_msg = adverse_tracker.should_halt(
                last_n=config.BOT_E_ADVERSE_WINDOW_N,
                adverse_threshold=float(config.BOT_E_ADVERSE_HALT_THRESHOLD),
            )
            if should_halt_adv:
                log.warning("bot_e.adverse_selection_halt %s", adv_msg)
                scan_counts["adverse_selection_halt"] += 1
                _emit_bot_e_event(
                    "bot_e.adverse_selection_halt",
                    adv_msg,
                    {"message": adv_msg},
                    severity="kill",
                )
                _emit_scan_summary(
                    markets_seen=len(markets),
                    counts=scan_counts,
                    elapsed_sec=time.monotonic() - loop_start,
                )
                await asyncio.sleep(config.BOT_E_SCAN_INTERVAL_SEC)
                continue
        except Exception as exc:
            log.warning("bot_e.reconcile_failed err=%s", exc)
            scan_counts["reconcile_failed"] += 1

        # Session 17s 2026-04-19: paper-resolution reconciliation (hourly).
        # Closes OPEN positions whose markets resolved on Gamma — paper mode
        # has no on-chain on_redeem path so these would otherwise stay OPEN
        # forever, inflating fleet-cap exposure and hiding realised P&L.
        # See ADR-035.
        now_ts = time.time()
        if not is_live and (now_ts - last_paper_resolve_ts) >= paper_resolve_interval_s:
            try:
                from core.portfolio import Portfolio
                pfo = Portfolio()
                settled = await asyncio.to_thread(
                    pfo.reconcile_paper_resolutions, BOT_ID
                )
                if settled:
                    log.info("bot_e.paper_resolve.settled count=%d", settled)
                    # Re-hydrate since closed positions change exposure/sizer view.
                    state.open_positions = _hydrate_open_positions()
                last_paper_resolve_ts = now_ts
            except Exception as exc:
                log.warning("bot_e.paper_resolve.fail: %s", exc)
                scan_counts["paper_resolve_failed"] += 1

        # --- Per-market tick ---
        for market in markets:
            scan_counts["market_seen"] += 1
            cid = market.condition_id
            now_ms = int(time.time() * 1000)

            # Ensure per-market state exists
            if cid not in market_trades:
                sub = SubscriptionTrades(subscription_id=cid)
                sub.set_tokens(market.yes_token_id, market.no_token_id)
                market_trades[cid] = sub
                market_closes[cid] = deque(maxlen=_REGIME_WINDOW)
                log.info("bot_e.new_market cid=%s symbol=%s question=%r",
                         cid, market.symbol, market.question[:60])

            sub = market_trades[cid]

            # --- Fetch order book (HTTP polling; adequate for paper mode) ---
            book_age_ms = 9999
            try:
                yes_book = await asyncio.get_event_loop().run_in_executor(
                    None, clob.get_book, market.yes_token_id
                )
                _persist_book_snapshot(yes_book)
                if market.no_token_id:
                    no_book = await asyncio.get_event_loop().run_in_executor(
                        None, clob.get_book, market.no_token_id
                    )
                    _persist_book_snapshot(no_book)
                book_age_ms = int((time.time() - yes_book.timestamp) * 1000)

                # Update prices in the subscription state
                best_bid = yes_book.best_bid()
                best_ask = yes_book.best_ask()
                if best_bid is not None:
                    sub.last_yes_price = best_bid
                if best_ask is not None:
                    # NO price is approximately 1 - YES_ask
                    sub.last_no_price = (Decimal("1") - best_ask).quantize(Decimal("0.001"))

                # Midpoint for regime classification
                mid = yes_book.midpoint()
                if mid is not None:
                    market_closes[cid].append(float(mid))

                # Audit F1 fix (2026-04-16): read REAL trade flow from the
                # recorder DB instead of synthesising from midpoint. The
                # recorder subscribes to Polymarket WSS and captures every
                # last_trade_price event; querying it here gives the trader
                # the same data distribution the backtester calibrates on.
                # Prior synthetic-one-unit-trade-per-midpoint-flip approach
                # was a strategy drift that Codex audit flagged as Critical.
                # 2026-04-17 Audit Finding 1 fix: use the per-subscription
                # cursor so we never re-ingest trades already seen in prior
                # scans. First scan reads the full window; subsequent scans
                # read only events strictly newer than last_ingested_ts_ms.
                window_floor_ms = now_ms - int(config.BOT_E_OBI_WINDOW_SEC * 1000)
                since_ms = max(window_floor_ms, sub.last_ingested_ts_ms + 1)
                recent_trades = _recent_recorder_trades(
                    token_ids=[t for t in (market.yes_token_id, market.no_token_id) if t],
                    since_ms=since_ms,
                )
                for t_ts, t_asset, t_size in recent_trades:
                    sub.record_trade(t_ts, t_asset, t_size)

            except Exception as exc:
                log.warning("bot_e.book_fetch_failed cid=%s err=%s", cid, exc)
                scan_counts["book_fetch_failed"] += 1
                _emit_bot_e_event(
                    "bot_e.book_fetch_failed",
                    f"book fetch failed cid={cid}",
                    {"condition_id": cid, "error": str(exc)},
                    severity="warn",
                )
                continue

            # --- Regime gate ---
            closes = list(market_closes[cid])
            if should_skip_due_to_chop(closes, choppiness_max=config.BOT_E_REGIME_CHOPPINESS_MAX):
                log.debug("bot_e.regime_chop cid=%s closes=%d", cid, len(closes))
                scan_counts["regime_chop"] += 1
                continue

            # --- OBI signal ---
            signal = maybe_fire(
                sub,
                now_ms,
                window_sec=config.BOT_E_OBI_WINDOW_SEC,
                threshold=config.BOT_E_OBI_THRESHOLD,
                min_trades=config.BOT_E_OBI_MIN_TRADES,
                min_volume=config.BOT_E_OBI_MIN_VOLUME_USD,
                decay_half_life_sec=config.BOT_E_OBI_DECAY_HALF_LIFE_SEC,
            )
            if signal is None:
                scan_counts["signal_none"] += 1
                continue

            scan_counts["signal"] += 1
            log.info(
                "bot_e.signal cid=%s side=%s obi=%.3f n_trades=%d",
                cid, signal.side, signal.obi, signal.n_trades,
            )
            _emit_bot_e_event(
                "bot_e.signal",
                f"signal cid={cid} side={signal.side}",
                {
                    "condition_id": cid,
                    "symbol": market.symbol,
                    "side": signal.side,
                    "obi": float(signal.obi),
                    "abs_obi": float(signal.abs_obi),
                    "n_trades": signal.n_trades,
                    "total_volume": str(signal.total_volume),
                    "yes_price": str(signal.yes_price),
                    "no_price": str(signal.no_price),
                },
            )

            # --- Phase 5 Item 2: CEX CVD confirmation gate ---
            cvd_ok, cvd_reason = _cex_cvd_gate_ok(
                symbol=market.symbol,
                signal_side=signal.side,
                now_ms=now_ms,
            )
            if not cvd_ok:
                log.info("bot_e.cex_cvd_skip cid=%s %s", cid, cvd_reason)
                scan_counts["cex_cvd_skip"] += 1
                _emit_bot_e_event(
                    "bot_e.cex_cvd_skip",
                    f"cex cvd skip cid={cid} reason={cvd_reason}",
                    {
                        "condition_id": cid,
                        "symbol": market.symbol,
                        "side": signal.side,
                        "reason": cvd_reason,
                    },
                )
                continue
            scan_counts["cex_cvd_pass"] += 1
            log.debug("bot_e.cex_cvd_pass cid=%s %s", cid, cvd_reason)

            # --- Phase 5 Item 3: depth-at-best gate ---
            # Use the book fetched in market discovery; best-price anchor
            # is yes_price (maker buys YES) or no_price (maker buys NO).
            best_anchor = signal.yes_price if signal.side == "BUY_YES" else signal.no_price
            # 2026-04-17 Audit Finding 4 fix: CryptoMarket has no `book` or
            # `raw_book` field, so the prior getattr fallback always yielded
            # None and the gate silently fail-opened. Pass `yes_book` — the
            # OrderBook object already fetched above in this loop. The
            # bid-side depth it reports is the support for our maker entry.
            depth_ok, depth_reason = _depth_gate_ok(
                book=yes_book,
                signal_side=signal.side,
                best_price=best_anchor,
            )
            if not depth_ok:
                log.info("bot_e.depth_skip cid=%s %s", cid, depth_reason)
                scan_counts["depth_skip"] += 1
                _emit_bot_e_event(
                    "bot_e.depth_skip",
                    f"depth skip cid={cid} reason={depth_reason}",
                    {
                        "condition_id": cid,
                        "symbol": market.symbol,
                        "side": signal.side,
                        "reason": depth_reason,
                        "best_anchor": str(best_anchor),
                    },
                )
                continue
            scan_counts["depth_pass"] += 1
            log.debug("bot_e.depth_pass cid=%s %s", cid, depth_reason)

            # --- Time-to-resolution check ---
            minutes_to_res = market.minutes_to_resolution()

            # --- Determine effective fixed trade size (DB-backed gate).
            # Audit 2026-04-17: counter now reads Trade rows for paper fills,
            # not placed orders, and persists across restarts.
            paper_fills_observed = _paper_fill_count() if not is_live else 0
            if not is_live and paper_fills_observed < config.BOT_E_PAPER_TRADE_THRESHOLD:
                effective_fixed = config.BOT_E_PAPER_FIXED_USD
            else:
                effective_fixed = config.BOT_E_FIXED_TRADE_USD

            # --- try_enter: full pre-trade chain ---
            decision = try_enter(
                signal,
                state,
                bankroll_usd=config.BOT_E_BANKROLL_USD,
                fixed_trade_usd=effective_fixed,
                per_trade_cap_frac=config.BOT_E_PER_TRADE_CAP_FRAC,
                crypto_bucket_cap_frac=config.BOT_E_CRYPTO_BUCKET_CAP_FRAC,
                aggregate_cap_frac=config.BOT_E_AGGREGATE_EXPOSURE_CAP_FRAC,
                maker_offset=config.BOT_E_MAKER_OFFSET,
                maker_only=config.BOT_E_MAKER_ONLY,
                stale_feed_ms=config.BOT_E_STALE_FEED_MS,
                consecutive_loss_halt_n=config.BOT_E_CONSECUTIVE_LOSS_HALT_N,
                is_halted=db_halted,
                dry_run=False,  # we handle placement here, not in executor
                last_feed_age_ms=book_age_ms,
                symbol=market.symbol,
                minutes_to_resolution=minutes_to_res,
                # Audit 2026-04-17 (Q18): live uses narrow 5-10m window;
                # paper keeps wide 3-15m window for data collection.
                entry_window_min_sec=(
                    config.BOT_E_LIVE_ENTRY_WINDOW_MIN_SEC if is_live
                    else config.BOT_E_ENTRY_WINDOW_MIN_SEC
                ),
                entry_window_max_sec=(
                    config.BOT_E_LIVE_ENTRY_WINDOW_MAX_SEC if is_live
                    else config.BOT_E_ENTRY_WINDOW_MAX_SEC
                ),
                # order_style: live = maker-only (audit 2026-04-17 Q18);
                # paper = honor BOT_E_ORDER_STYLE env so paper trades fill.
                order_style=("maker" if is_live else config.BOT_E_ORDER_STYLE),
                crypto_correlation_adj=config.BOT_E_CRYPTO_CORRELATION_ADJ,
                crypto_avg_correlation=config.BOT_E_CRYPTO_AVG_CORRELATION,
            )

            if not decision.accepted:
                log.debug("bot_e.rejected reason=%s cid=%s", decision.reason, cid)
                scan_counts["rejected"] += 1
                scan_counts[f"rejected_{_counter_reason(decision.reason)}"] += 1
                _emit_bot_e_event(
                    "bot_e.rejected",
                    f"rejected cid={cid} reason={decision.reason}",
                    {
                        "condition_id": cid,
                        "symbol": market.symbol,
                        "side": signal.side,
                        "reason": decision.reason,
                        "reason_code": decision.reason_code,
                    },
                )
                continue

            # --- Fleet cap check (audit 2026-04-17, atomic pre-trade).
            # Blocks cross-bot overcap even if per-bot caps pass.
            from core.fleet import check_fleet_exposure
            fleet_check = check_fleet_exposure(BOT_ID, decision.notional_usd or Decimal("0"))
            if not fleet_check.ok:
                log.info(
                    "bot_e.fleet_cap_breach cid=%s intended=%s current=%s cap=%s",
                    cid, fleet_check.intended_usd,
                    fleet_check.current_total_usd, fleet_check.deployable_cap_usd,
                )
                scan_counts["fleet_cap_breach"] += 1
                _emit_bot_e_event(
                    "bot_e.fleet_cap_breach",
                    f"fleet cap breach cid={cid}",
                    {
                        "condition_id": cid,
                        "intended_usd": str(fleet_check.intended_usd),
                        "current_total_usd": str(fleet_check.current_total_usd),
                        "deployable_cap_usd": str(fleet_check.deployable_cap_usd),
                    },
                    severity="warn",
                )
                continue

            # --- Place the order (paper or live via ClobWrapper) ---
            limit_price = decision.limit_price
            shares = decision.shares

            # Shadow: what would Kelly have done?
            kelly_shadow = _compute_kelly_shadow(
                signal_side=signal.side,
                limit_price=limit_price,
                bankroll_usd=config.BOT_E_BANKROLL_USD,
                open_positions=state.open_positions,
                symbol=market.symbol,  # U-20: pass real symbol not hardcoded BTC
            )

            # Determine token_id for the side we're buying
            token_id = (
                market.yes_token_id if signal.side == "BUY_YES"
                else market.no_token_id
            )
            clob_side = Side.BUY

            try:
                resp = clob.place_limit(
                    token_id=token_id,
                    price=limit_price,
                    size=shares,
                    side=clob_side,
                    order_type=OrderType.GTC,
                )
                log.info(
                    "bot_e.order_placed order_id=%s status=%s side=%s "
                    "limit=%s shares=%s notional=%s kelly_shadow=%s cid=%s",
                    resp.order_id, resp.status, signal.side,
                    limit_price, shares, decision.notional_usd,
                    kelly_shadow, cid,
                )
                scan_counts["order_placed"] += 1

                # Persist Order row for BOTH paper and live paths.
                # Audit F2 fix (2026-04-16): live orders were previously not
                # written to the DB — watchdog and dashboard had no local
                # truth about exposure. Now every placement gets an Order
                # row regardless of env, so reconciliation and TTL cancel
                # can operate on the same data model as Bot A/B/D.
                is_paper_order = (
                    resp.status == "PAPER_OPEN" or resp.order_id.startswith("paper-")
                )
                _persist_order(
                    order_id=resp.order_id,
                    condition_id=cid,
                    token_id=token_id,
                    side=signal.side,
                    price=limit_price,
                    size=shares,
                    status=resp.status or ("PAPER_OPEN" if is_paper_order else "live"),
                    strategy_signal=decision.strategy_signal or "",
                    reason_code=decision.reason_code or "",
                    kelly_would_have=kelly_shadow,
                )
                # Session 17f audit 2026-04-17: synthesize an in-memory
                # OpenPosition so subsequent signals in this scan iteration
                # (or before the next reconcile+hydrate cycle catches up)
                # see the market as "already entered" and dedup. Next
                # `_hydrate_open_positions()` call will overwrite this list
                # from the canonical DB state, so there's no persistence risk.
                state.open_positions.append(OpenPosition(
                    subscription_id=cid,
                    symbol=market.symbol,
                    side=signal.side,
                    notional_usd=decision.notional_usd or Decimal("0"),
                    is_crypto=True,
                ))
                if is_paper_order:
                    scan_counts["paper_order_placed"] += 1
                    # Audit 2026-04-17: we no longer maintain a process-local
                    # counter. The fixed-size gate reads fill count from the
                    # Trade table at the top of each scan loop; order placement
                    # is only logged here.
                    log.info(
                        "bot_e.paper_order_placed fills_observed=%d threshold=%d "
                        "fixed_usd=%s",
                        paper_fills_observed,
                        config.BOT_E_PAPER_TRADE_THRESHOLD,
                        effective_fixed,
                    )

            except Exception as exc:
                log.error(
                    "bot_e.order_failed cid=%s side=%s err=%s",
                    cid, signal.side, exc,
                )
                scan_counts["order_failed"] += 1
                _emit_bot_e_event(
                    "bot_e.order_failed",
                    f"order failed cid={cid} side={signal.side}",
                    {
                        "condition_id": cid,
                        "symbol": market.symbol,
                        "side": signal.side,
                        "error": str(exc),
                    },
                    severity="warn",
                )

        # --- OQ-048 DB-visible rejection counters ---
        _emit_scan_summary(
            markets_seen=len(markets),
            counts=scan_counts,
            elapsed_sec=time.monotonic() - loop_start,
        )

        # --- Daily P&L snapshot (2026-04-17 audit fix) ---
        # Every other bot writes a pnl_snapshots row once per UTC day; Bot E
        # was silently excluded because its async main loop never had the
        # wiring. Without this, paper trades run with no measurable P&L
        # history, defeating the audit purpose. Call once per UTC date.
        try:
            today = datetime.now(UTC).date()
            if last_snapshot_date != today:
                from core.ingest import build_mark_prices
                from core.portfolio import Portfolio as _Portfolio
                _Portfolio().snapshot_daily(
                    BOT_ID,
                    Decimal(str(config.BOT_E_BANKROLL_USD)),
                    mark_prices=build_mark_prices(BOT_ID),
                    on_date=today,
                )
                last_snapshot_date = today
                log.info("bot_e.pnl_snapshot.taken on_date=%s", today.isoformat())
        except Exception as exc:
            log.warning("bot_e.pnl_snapshot_failed err=%s", exc)

        # --- Sleep until next scan ---
        elapsed = time.monotonic() - loop_start
        sleep_for = max(0.0, config.BOT_E_SCAN_INTERVAL_SEC - elapsed)
        log.debug("bot_e.loop_done elapsed=%.2fs sleeping=%.2fs", elapsed, sleep_for)
        await asyncio.sleep(sleep_for)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # CLI overrides env
    if args.dry_run is not None:
        import os
        os.environ["BOT_E_DRY_RUN"] = "true" if args.dry_run else "false"
        # Reload config module
        import importlib
        importlib.reload(config)

    errors = config.validate()
    if errors:
        for e in errors:
            sys.stderr.write(f"config error: {e}\n")
        return 2

    gate_err = _check_calibration_gate(args)
    if gate_err:
        sys.stderr.write(f"refusing to start: {gate_err}\n")
        return 3

    logging.basicConfig(
        level=getattr(logging, args.log_level or config.BOT_E_LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    is_live = args.live and not config.BOT_E_DRY_RUN

    loop = asyncio.new_event_loop()
    task = loop.create_task(run(is_live=is_live))

    def _stop(*_args):
        log.info("bot_e.signal_received stopping")
        task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    try:
        return loop.run_until_complete(task) or 0
    except asyncio.CancelledError:
        return 0
    finally:
        loop.close()


if __name__ == "__main__":
    sys.exit(main())
