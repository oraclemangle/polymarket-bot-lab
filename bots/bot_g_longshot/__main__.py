"""Bot Longshot Fade (G) — main loop.

Scans the recorder DB for 15-min crypto Up/Down markets whose end_date is
within `BOT_G_ENTRY_SECONDS_BEFORE_RES` seconds of now. For each such
market, reads the latest best_bid_ask per token, and if either side's entry
price qualifies, places a BUY for BOT_G_FIXED_TRADE_USD notional. In taker
mode the entry price is best_ask; in maker mode it is best_bid and the order
rests until fill reconciliation or the pre-close cancel lead.

Settlement runs hourly via `Portfolio.reconcile_paper_resolutions` (ADR-035).

Usage:
    python -m bots.bot_g_longshot [--log-level INFO]

Key operational notes:
  * Bot G piggybacks on the existing Bot E recorder (BOT_E_RECORDER_DB_PATH
    fallback in config.py). No new WSS subscriptions; no new CEX feed;
    cheap to run.
  * Defaults to `paper-` orders via ClobWrapper(paper_override=True).
  * Respects the halt flag, emergency halt, and the rolling-ROI kill-switch.
  * One entry per (market, side) — tracked in-memory per-process; DB-backed
    via Position rows so restart doesn't re-enter.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sqlite3
import statistics
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from bots.bot_g_longshot import config
from bots.bot_g_longshot.config import BOT_ID

log = logging.getLogger("bot_g")
CAPACITY_TICK_SIZE = Decimal("0.01")


# ---------------------------------------------------------------------------
# Halt / emergency checks
# ---------------------------------------------------------------------------


def _is_db_halted() -> bool:
    try:
        from core.db import HaltFlag, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            flag = s.get(HaltFlag, BOT_ID)
            return bool(flag and flag.halted)
    except Exception as exc:
        log.warning("bot_g.halt_check_failed err=%s", exc)
        return False


def _emergency_halted() -> bool:
    try:
        from core.emergency_halt import is_emergency_halted
        return is_emergency_halted()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Market discovery + book read (from recorder DB, read-only)
# ---------------------------------------------------------------------------


def _recorder_conn() -> sqlite3.Connection | None:
    path = Path(config.BOT_G_RECORDER_DB_PATH)
    if not path.exists():
        return None
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-65536")
        conn.execute("PRAGMA mmap_size=268435456")
    except Exception:
        pass
    return conn


def _active_markets_near_resolution(now_ms: int) -> list[dict]:
    """Return markets whose end_date is within `BOT_G_ENTRY_SECONDS_BEFORE_RES`
    of now (window = [now, now + window_sec]). Deduped by condition_id (latest
    snapshot per market).
    """
    conn = _recorder_conn()
    if conn is None:
        return []
    # Widen to the larger of the two modes' entry windows so both modes
    # see the same market pool; per-mode gating happens in _try_enter_market.
    window_sec = max(
        config.BOT_G_PRIME_ENTRY_SECONDS if config.BOT_G_PRIME_MODE_ENABLED else 0,
        config.BOT_G_JACKPOT_ENTRY_SECONDS if config.BOT_G_JACKPOT_MODE_ENABLED else 0,
        config.BOT_G_SCALP_ENTRY_SECONDS if config.BOT_G_SCALP_MODE_ENABLED else 0,
        config.BOT_G_ENTRY_SECONDS_BEFORE_RES,
    )
    window_ms = window_sec * 1000
    now_iso = datetime.fromtimestamp(now_ms / 1000, tz=UTC).isoformat()
    future_iso = datetime.fromtimestamp(
        (now_ms + window_ms) / 1000, tz=UTC
    ).isoformat()
    min_scan_at_ms = now_ms - config.BOT_G_MARKET_ROW_MAX_AGE_SECONDS * 1000
    try:
        rows = conn.execute(
            "SELECT condition_id, question, end_date_iso, yes_token_id, no_token_id "
            "FROM markets "
            "WHERE end_date_iso IS NOT NULL "
            "  AND end_date_iso >= ? "
            "  AND end_date_iso <= ? "
            "  AND scan_at_ms >= ? "
            "GROUP BY condition_id HAVING scan_at_ms = MAX(scan_at_ms)",
            (now_iso, future_iso, min_scan_at_ms),
        ).fetchall()
    except Exception as exc:
        log.warning("bot_g.market_query_failed err=%s", exc)
        return []
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _extract_bba_from_payload(
    event_type: str, payload: dict, token_id: str,
) -> tuple[Decimal, Decimal] | None:
    """Extract (best_bid, best_ask) for a specific token from one pm_event payload.

    Handles the three event-type shapes the Polymarket WSS emits:
      * `best_bid_ask` — top-level {best_bid, best_ask}, keyed by asset_id.
      * `book`        — top-level {bids:[{price,size}], asks:[{price,size}]};
                        top-of-book is bids[0].price, asks[0].price after
                        sorting (recorder does not guarantee order).
      * `price_change` — top-level {price_changes: [{asset_id, best_bid,
                        best_ask, ...}]}; per-token entries inside the list.

    Returns (best_bid, best_ask) or None if the payload doesn't carry a
    usable quote for this token.
    """
    try:
        if event_type == "best_bid_ask":
            bb = payload.get("best_bid")
            ba = payload.get("best_ask")
            if bb is None or ba is None:
                return None
            return Decimal(str(bb)), Decimal(str(ba))

        if event_type == "book":
            bids = payload.get("bids") or []
            asks = payload.get("asks") or []
            if not bids or not asks:
                return None
            # Highest bid, lowest ask — recorder may write levels unsorted.
            best_bid = max(Decimal(str(x["price"])) for x in bids if x.get("price") is not None)
            best_ask = min(Decimal(str(x["price"])) for x in asks if x.get("price") is not None)
            return best_bid, best_ask

        if event_type == "price_change":
            for pc in payload.get("price_changes") or []:
                if str(pc.get("asset_id") or "") != token_id:
                    continue
                bb = pc.get("best_bid")
                ba = pc.get("best_ask")
                if bb is None or ba is None:
                    return None
                return Decimal(str(bb)), Decimal(str(ba))
            return None
    except Exception:
        return None
    return None


def _extract_crypto_symbol(question: str | None) -> str | None:
    q = (question or "").upper()
    for symbol, needles in (
        ("BTCUSDT", ("BTC", "BITCOIN")),
        ("ETHUSDT", ("ETH", "ETHEREUM")),
        ("SOLUSDT", ("SOL", "SOLANA")),
        ("XRPUSDT", ("XRP", "RIPPLE")),
        ("DOGEUSDT", ("DOGE", "DOGECOIN")),
    ):
        if any(n in q for n in needles):
            return symbol
    return None


def _base_crypto_symbol(question: str | None) -> str | None:
    symbol = _extract_crypto_symbol(question)
    return symbol.removesuffix("USDT") if symbol else None


def _cex_confirmation(
    market: dict,
    side_label: str,
    now_ms: int,
) -> dict | None:
    """Return CEX move metadata if recent spot confirms the cheap side.

    For Polymarket crypto Up/Down markets, YES resolves if the underlying
    moved up over the window and NO resolves if it moved down. Prime mode
    only trades when the external tape is already moving toward the cheap
    side, turning the raw tail collector into a late dislocation detector.
    """
    symbol = _extract_crypto_symbol(market.get("question"))
    if symbol is None:
        return None
    conn = _recorder_conn()
    if conn is None:
        return None
    start_ms = now_ms - config.BOT_G_PRIME_CEX_WINDOW_SEC * 1000
    try:
        older = conn.execute(
            "SELECT price, trade_time_ms FROM cex_trades "
            "WHERE symbol=? AND trade_time_ms >= ? AND trade_time_ms <= ? "
            "ORDER BY trade_time_ms ASC LIMIT 1",
            (symbol, start_ms, now_ms),
        ).fetchone()
        latest = conn.execute(
            "SELECT price, trade_time_ms FROM cex_trades "
            "WHERE symbol=? AND trade_time_ms <= ? "
            "ORDER BY trade_time_ms DESC LIMIT 1",
            (symbol, now_ms),
        ).fetchone()
    except Exception as exc:
        log.debug("bot_g.prime_cex_query_failed symbol=%s err=%s", symbol, exc)
        return None
    finally:
        conn.close()
    if older is None or latest is None:
        return None
    try:
        old_price = Decimal(str(older["price"]))
        new_price = Decimal(str(latest["price"]))
    except Exception:
        return None
    if old_price <= 0:
        return None
    move_bps = ((new_price - old_price) / old_price) * Decimal("10000")
    min_bps = config.BOT_G_PRIME_MIN_CEX_MOVE_BPS
    confirmed = (
        move_bps >= min_bps if side_label == "YES" else move_bps <= -min_bps
    )
    return {
        "symbol": symbol,
        "old_price": str(old_price),
        "new_price": str(new_price),
        "move_bps": str(move_bps.quantize(Decimal("0.0001"))),
        "window_sec": config.BOT_G_PRIME_CEX_WINDOW_SEC,
        "confirmed": confirmed,
    }


def _book_depletion_signal(token_id: str, now_ms: int) -> dict | None:
    """Causal recent-vs-trailing best-ask depth signal for Prime telemetry."""
    import json as _json

    conn = _recorder_conn()
    if conn is None:
        return None
    start_ms = now_ms - 90_000
    recent_cutoff = now_ms - 15_000
    try:
        rows = conn.execute(
            "SELECT received_at_ms, payload_json FROM pm_events "
            "WHERE asset_id=? AND event_type='book' AND received_at_ms BETWEEN ? AND ? "
            "ORDER BY received_at_ms",
            (token_id, start_ms, now_ms),
        ).fetchall()
    except Exception as exc:
        log.debug("bot_g.prime_book_query_failed token=%s err=%s", token_id[:12], exc)
        return None
    finally:
        conn.close()

    trailing: list[float] = []
    recent: list[float] = []
    for row in rows:
        try:
            payload = _json.loads(row["payload_json"])
            asks = payload.get("asks") or []
            if not asks:
                continue
            best = min(
                asks,
                key=lambda level: Decimal(str(level.get("price", "10"))),
            )
            size = float(best.get("size", 0) or 0)
        except Exception:
            continue
        if int(row["received_at_ms"]) >= recent_cutoff:
            recent.append(size)
        else:
            trailing.append(size)

    if not recent or not trailing:
        return None
    trailing_med = Decimal(str(statistics.median(trailing)))
    recent_med = Decimal(str(statistics.median(recent)))
    ratio = recent_med / trailing_med if trailing_med > 0 else Decimal("1")
    return {
        "trailing_depth_median": str(trailing_med),
        "recent_depth_median": str(recent_med),
        "depletion_ratio": str(ratio.quantize(Decimal("0.0001"))),
        "n_trailing": len(trailing),
        "n_recent": len(recent),
    }


def _record_prime_rejection(
    market: dict,
    reason: str,
    payload: dict,
) -> None:
    try:
        from core.db import Event, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            s.add(Event(
                bot_id=BOT_ID,
                event_type="bot_g.prime_rejected",
                severity="info",
                message=f"prime rejected: {reason}",
                payload={
                    "condition_id": market.get("condition_id"),
                    "reason": reason,
                    **payload,
                },
            ))
            s.commit()
    except Exception:
        pass


def _latest_best_bid_ask(
    token_id: str, condition_id: str, now_ms: int,
) -> tuple[Decimal, Decimal, Decimal] | None:
    """Most recent book quote for this token, within last 30s, across any
    of the three event types Polymarket emits (best_bid_ask, price_change,
    book).

    Returns (best_bid, best_ask, best_ask_size) or None if no event in the
    window carries a usable quote. Size comes from the latest `book`
    snapshot's top ask level (may be 0 if no `book` event or no matching
    level; callers gate on BOT_G_MIN_BOOK_SIZE separately).

    Background (OQ-043, 2026-04-23): the old query only read
    `event_type='best_bid_ask'` within 30s, but the recorder writes ~2
    of those per 5 min vs ~570 `price_change` events carrying the same
    fields. Bot G was returning None for nearly every scan and skipping
    every market. This unified fallback raises the hit rate by ~250x.
    """
    import json as _json

    conn = _recorder_conn()
    if conn is None:
        return None
    cutoff = now_ms - 90_000
    try:
        # Query all three event-types in one shot; pick the freshest hit
        # that yields a usable quote for our token. `price_change` events
        # are keyed by asset_id=condition_id in the recorder (they have a
        # top-level `market` field, not `asset_id`), so match on either.
        rows_by_key = []
        for asset_key in (token_id, condition_id):
            rows_by_key.extend(conn.execute(
                "SELECT event_type, payload_json, received_at_ms FROM pm_events "
                "WHERE asset_id=? "
                "  AND event_type IN ('best_bid_ask', 'price_change', 'book') "
                "  AND received_at_ms >= ? "
                "ORDER BY received_at_ms DESC LIMIT 50",
                (asset_key, cutoff),
            ).fetchall())
        rows = sorted(
            rows_by_key,
            key=lambda r: int(r["received_at_ms"] or 0),
            reverse=True,
        )[:50]

        quote: tuple[Decimal, Decimal] | None = None
        for r in rows:
            try:
                payload = _json.loads(r["payload_json"])
            except Exception:
                continue
            q = _extract_bba_from_payload(r["event_type"], payload, token_id)
            if q is not None:
                quote = q
                break

        if quote is None:
            return None
        best_bid, best_ask = quote

        # Depth at best-ask: read from most recent `book` event (last 90s).
        # Book events are snapshot-style and fire ~every 30-60s, so a wider
        # window than the price-freshness window is appropriate.
        rb = conn.execute(
            "SELECT payload_json FROM pm_events "
            "WHERE asset_id=? AND event_type='book' "
            "  AND received_at_ms >= ? "
            "ORDER BY received_at_ms DESC LIMIT 1",
            (token_id, now_ms - 90_000),
        ).fetchone()
        best_ask_size = Decimal("0")
        if rb is not None:
            try:
                book = _json.loads(rb["payload_json"])
                for lvl in book.get("asks") or []:
                    if Decimal(str(lvl.get("price", 0))) == best_ask:
                        best_ask_size = Decimal(str(lvl.get("size", 0)))
                        break
            except Exception:
                pass
        return best_bid, best_ask, best_ask_size
    except Exception as exc:
        log.warning("bot_g.bba_query_failed token=%s err=%s", token_id[:12], exc)
        return None
    finally:
        conn.close()


def _entry_capacity_depth(token_id: str, limit_price: Decimal, now_ms: int) -> dict:
    """Return ask depth at limit, limit+1c, and limit+2c from recorder books."""
    conn = _recorder_conn()
    if conn is None:
        return {"available": False, "reason": "recorder_db_missing", "depth_by_tick": []}
    try:
        row = conn.execute(
            "SELECT payload_json, received_at_ms FROM pm_events "
            "WHERE asset_id=? AND event_type='book' "
            "  AND received_at_ms >= ? "
            "ORDER BY received_at_ms DESC LIMIT 1",
            (token_id, now_ms - 90_000),
        ).fetchone()
        if row is None:
            return {"available": False, "reason": "book_snapshot_missing", "depth_by_tick": []}
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            return {"available": False, "reason": "book_json_invalid", "depth_by_tick": []}
        asks = payload.get("asks") or []
        levels: list[tuple[Decimal, Decimal]] = []
        for level in asks:
            try:
                price = Decimal(str(level.get("price")))
                size = Decimal(str(level.get("size")))
            except Exception:
                continue
            if price >= 0 and size > 0:
                levels.append((price, size))
        depth_by_tick = []
        for ticks in range(3):
            max_price = limit_price + (CAPACITY_TICK_SIZE * ticks)
            eligible = [(price, size) for price, size in levels if price <= max_price]
            shares = sum((size for _price, size in eligible), Decimal("0"))
            notional = sum((price * size for price, size in eligible), Decimal("0"))
            depth_by_tick.append(
                {
                    "ticks_above_limit": ticks,
                    "max_price": str(max_price.quantize(Decimal("0.0001"))),
                    "shares": str(shares.quantize(Decimal("0.01"))),
                    "notional_usd": str(notional.quantize(Decimal("0.0001"))),
                }
            )
        return {
            "available": True,
            "snapshot_ms": int(row["received_at_ms"]),
            "depth_by_tick": depth_by_tick,
        }
    except Exception as exc:
        log.debug("bot_g.capacity_depth_failed token=%s err=%s", token_id[:12], exc)
        return {"available": False, "reason": type(exc).__name__, "depth_by_tick": []}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Daily / rolling-ROI kill switches
# ---------------------------------------------------------------------------


def _todays_entry_count() -> int:
    try:
        from sqlalchemy import func, select

        from core.db import Order, get_session_factory
        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        sf = get_session_factory()
        with sf() as s:
            return int(s.scalar(
                select(func.count(Order.order_id)).where(
                    Order.bot_id == BOT_ID, Order.placed_at >= today_start,
                )
            ) or 0)
    except Exception as exc:
        log.warning("bot_g.daily_count_failed err=%s", exc)
        return 0


def _todays_entry_notional_usd() -> Decimal:
    try:
        from sqlalchemy import select

        from core.db import Order, get_session_factory
        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        sf = get_session_factory()
        with sf() as s:
            orders = list(s.scalars(
                select(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.placed_at >= today_start,
                )
            ))
        total = Decimal("0")
        for order in orders:
            if order.price is None or order.size is None:
                continue
            total += Decimal(order.price) * Decimal(order.size)
        return total
    except Exception as exc:
        log.warning("bot_g.daily_notional_failed err=%s", exc)
        return Decimal("0")


def _open_positions_count() -> int:
    try:
        from sqlalchemy import func, select

        from core.db import Position, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            return int(s.scalar(
                select(func.count(Position.id)).where(
                    Position.bot_id == BOT_ID, Position.status == "OPEN",
                )
            ) or 0)
    except Exception as exc:
        log.warning("bot_g.open_count_failed err=%s", exc)
        return 0


def _closed_positions_count() -> int:
    """How many Bot G positions have reached terminal state (CLOSED/REDEEMED)."""
    try:
        from sqlalchemy import func, select

        from core.db import Position, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            return int(s.scalar(
                select(func.count(Position.id)).where(
                    Position.bot_id == BOT_ID,
                    Position.status.in_(("CLOSED", "REDEEMED")),
                )
            ) or 0)
    except Exception as exc:
        log.warning("bot_g.closed_count_failed err=%s", exc)
        return 0


def _load_fired_milestones() -> set[int]:
    """Read back which milestones we've already notified, so restart doesn't
    re-fire stale alerts. Stored as Event rows with event_type='bot_g.milestone'.
    """
    try:
        from sqlalchemy import select

        from core.db import Event, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            rows = s.scalars(
                select(Event).where(
                    Event.bot_id == BOT_ID,
                    Event.event_type == "bot_g.milestone",
                )
            ).all()
            return {int((ev.payload or {}).get("milestone", 0)) for ev in rows}
    except Exception:
        return set()


def _check_and_fire_milestone(
    thresholds: list[int], already_fired: set[int], n_closed: int,
) -> None:
    """If n_closed has crossed an unfired milestone, send Telegram + log Event."""
    to_fire = [t for t in thresholds if n_closed >= t and t not in already_fired]
    if not to_fire:
        return
    try:
        from core.db import Event, get_session_factory
        from core.notify import send as tg_send
        from core.portfolio import Portfolio
        pfo = Portfolio()
        realised = pfo.get_realised_pnl(BOT_ID)
        for m in to_fire:
            msg = (
                f"Bot Longshot Fade (G) milestone: n={m} closed paper trades. "
                f"Realised ${realised:+.2f}."
            )
            try:
                tg_send("info", msg)
            except Exception as exc:
                log.warning("bot_g.milestone_tg_failed m=%d err=%s", m, exc)
            # Persist so we don't re-fire after restart.
            try:
                sf = get_session_factory()
                with sf() as s:
                    s.add(Event(
                        bot_id=BOT_ID,
                        event_type="bot_g.milestone",
                        severity="info",
                        message=msg,
                        payload={"milestone": m, "realised_usd": str(realised)},
                    ))
                    s.commit()
            except Exception as exc:
                log.warning("bot_g.milestone_persist_failed m=%d err=%s", m, exc)
            already_fired.add(m)
            log.info("bot_g.milestone_fired m=%d n=%d realised=%s", m, n_closed, realised)
    except Exception as exc:
        log.warning("bot_g.milestone_check_failed err=%s", exc)


def _rolling_roi_below_kill_threshold() -> bool:
    """True if the realized ROI on the last N closed trades is below the
    kill threshold. Disabled until we have enough trades to be meaningful.
    """
    try:
        from sqlalchemy import func, select

        from core.db import Position, get_session_factory
        from core.portfolio import Portfolio
        sf = get_session_factory()
        with sf() as s:
            n_closed = int(s.scalar(
                select(func.count(Position.id)).where(
                    Position.bot_id == BOT_ID,
                    Position.status.in_(("CLOSED", "REDEEMED")),
                )
            ) or 0)
        if n_closed < config.BOT_G_ROLLING_WINDOW_TRADES:
            # Below sample-size floor → don't enforce.
            return False
        pfo = Portfolio()
        realised = pfo.get_realised_pnl(BOT_ID)
        # Approx ROI: realised / (n_closed * fixed_trade_usd).
        cost_basis_est = Decimal(n_closed) * config.BOT_G_FIXED_TRADE_USD
        if cost_basis_est <= 0:
            return False
        roi_pct = (realised / cost_basis_est) * Decimal("100")
        if roi_pct < config.BOT_G_MIN_ROLLING_ROI_PCT:
            log.warning(
                "bot_g.rolling_roi_below_threshold realised=%s roi=%.1f%% threshold=%s%%",
                realised, roi_pct, config.BOT_G_MIN_ROLLING_ROI_PCT,
            )
            return True
    except Exception as exc:
        log.warning("bot_g.roi_kill_check_failed err=%s", exc)
    return False


# ---------------------------------------------------------------------------
# Order placement
# ---------------------------------------------------------------------------


async def _try_enter_market(
    market: dict, now_ms: int, clob, portfolio, _entered_this_session: set[tuple[str, str]],
) -> int:
    """Attempt entry on a single market. Returns count of orders placed.

    Two-mode operation (Grok round-3): both jackpot (t=60s) and scalp
    (t=30s) modes may fire on the same market across different scans —
    ``_entered_this_session`` keys are (condition_id, mode) so each mode
    enters at most once per market per process.
    """
    timing_start = time.perf_counter()
    timing_last = timing_start
    timing_ms: dict[str, float] = {}
    timing_cumulative_ms: dict[str, float] = {}

    def mark_timing(label: str) -> None:
        nonlocal timing_last
        now = time.perf_counter()
        timing_ms[label] = round((now - timing_last) * 1000, 3)
        timing_cumulative_ms[label] = round((now - timing_start) * 1000, 3)
        timing_last = now

    cid = market["condition_id"]

    # Determine which mode this tick qualifies for based on t-to-resolution.
    end_iso = market["end_date_iso"]
    end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    t_to_res_sec = int((end_dt.timestamp() * 1000 - now_ms) / 1000)
    if t_to_res_sec < 0:
        return 0

    base_symbol = _base_crypto_symbol(market.get("question"))
    if base_symbol is None or base_symbol not in config.BOT_G_ALLOWED_SYMBOLS:
        return 0

    # Pick the tightest eligible mode. Prime is the current filtered
    # candidate; legacy jackpot/scalp remain for historical cohorts.
    mode: str | None = None
    if config.BOT_G_PRIME_MODE_ENABLED and t_to_res_sec <= config.BOT_G_PRIME_ENTRY_SECONDS:
        mode = "prime"
    elif config.BOT_G_SCALP_MODE_ENABLED and t_to_res_sec <= config.BOT_G_SCALP_ENTRY_SECONDS:
        mode = "scalp"
    elif config.BOT_G_JACKPOT_MODE_ENABLED and t_to_res_sec <= config.BOT_G_JACKPOT_ENTRY_SECONDS:
        mode = "jackpot"
    else:
        return 0

    key = (cid, mode)
    if key in _entered_this_session:
        return 0

    # DB gate (GLM audit #10): check BOTH Position (status=OPEN) AND Order
    # (status=PAPER_OPEN) — if simulate_paper_fills hasn't created the
    # Position yet on a prior scan's order, we'd otherwise double-enter.
    try:
        from sqlalchemy import select

        from core.db import Order, Position, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            existing_pos = s.scalars(
                select(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.condition_id == cid,
                    Position.status == "OPEN",
                )
            ).first()
            if existing_pos is not None:
                _entered_this_session.add(key)
                return 0
            existing_order = s.scalars(
                select(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.condition_id == cid,
                    Order.status.in_(("PAPER_OPEN", "OPEN", "PARTIAL")),
                )
            ).first()
            if existing_order is not None:
                _entered_this_session.add(key)
                return 0
    except Exception as exc:
        log.warning("bot_g.pos_check_failed cid=%s err=%s", cid[:12], exc)
    mark_timing("db_gate_ms")

    # Read best_bid_ask for both sides.
    yes_tok = market["yes_token_id"]
    no_tok = market["no_token_id"]
    if not yes_tok or not no_tok:
        return 0
    yes_book = _latest_best_bid_ask(yes_tok, cid, now_ms)
    no_book = _latest_best_bid_ask(no_tok, cid, now_ms)
    mark_timing("book_lookup_ms")

    # Extract both sides' best-asks (0 if book unavailable, used only for
    # the counterparty-purity check below).
    yes_ask_val = yes_book[1] if yes_book is not None else Decimal("0")
    no_ask_val = no_book[1] if no_book is not None else Decimal("0")

    # Telemetry: record this evaluation for the 5-min candidate-summary
    # emitter. Data-driven tuning of BOT_G_MAX_ENTRY_PRICE depends on the
    # empirical distribution of cheap-side prices in the 60s window.
    _record_candidate_observation(now_ms, yes_ask_val, no_ask_val, t_to_res_sec)

    execution_style = config.BOT_G_EXECUTION_STYLE
    candidates: list[tuple[str, str, Decimal, Decimal, Decimal, Decimal]] = []
    min_entry_price = config.BOT_G_MIN_ENTRY_PRICE
    if yes_book is not None:
        yes_bid, yes_ask, yes_size = yes_book
        yes_entry_price = yes_bid if execution_style == "maker" else yes_ask
        yes_signal_price = yes_ask
        if (
            yes_entry_price > 0
            and yes_signal_price >= min_entry_price
            and yes_signal_price <= config.BOT_G_MAX_ENTRY_PRICE
            and (
                execution_style == "maker"
                or yes_size >= config.BOT_G_MIN_BOOK_SIZE
            )
        ):
            candidates.append(
                ("YES", yes_tok, yes_entry_price, yes_ask, yes_size, yes_signal_price)
            )
    if no_book is not None:
        no_bid, no_ask, no_size = no_book
        no_entry_price = no_bid if execution_style == "maker" else no_ask
        no_signal_price = no_ask
        if (
            no_entry_price > 0
            and no_signal_price >= min_entry_price
            and no_signal_price <= config.BOT_G_MAX_ENTRY_PRICE
            and (
                execution_style == "maker"
                or no_size >= config.BOT_G_MIN_BOOK_SIZE
            )
        ):
            candidates.append(
                ("NO", no_tok, no_entry_price, no_ask, no_size, no_signal_price)
            )

    if not candidates:
        return 0
    mark_timing("candidate_filter_ms")

    # Grok round-5 spread-purity filter: only enter when the OTHER side is
    # near-certainty (≥ BOT_G_MIN_COUNTERPARTY_PRICE). Prevents entries on
    # balanced-uncertainty markets (YES=3¢, NO=4¢) where neither side is
    # the obvious mispriced tail. Log rejection for post-hoc analysis.
    min_cp = config.BOT_G_MIN_COUNTERPARTY_PRICE
    if min_cp > 0:
        max_ask = max(yes_ask_val, no_ask_val)
        if max_ask < min_cp:
            try:
                from core.db import Event, get_session_factory
                sf = get_session_factory()
                with sf() as s:
                    s.add(Event(
                        bot_id=BOT_ID,
                        event_type="bot_g.spread_rejected",
                        severity="info",
                        message=(
                            f"spread-purity filter: max(yes_ask,no_ask)={max_ask} "
                            f"< {min_cp} threshold (both sides look uncertain)"
                        ),
                        payload={
                            "condition_id": cid,
                            "yes_ask": str(yes_ask_val),
                            "no_ask": str(no_ask_val),
                            "max_ask": str(max_ask),
                            "threshold": str(min_cp),
                            "t_to_res_sec": t_to_res_sec,
                            "mode": mode,
                        },
                    ))
                    s.commit()
            except Exception:
                pass
            log.debug(
                "bot_g.spread_rejected cid=%s yes=%s no=%s max=%s < %s",
                cid[:16], yes_ask_val, no_ask_val, max_ask, min_cp,
            )
            return 0

    # Enter the single cheapest side (asymmetric-payoff optimizer).
    candidates.sort(key=lambda x: x[5])
    side_label, token_id, entry_price, ask_price, ask_size, signal_price = candidates[0]
    effective_paper = _clob_effective_paper(clob)
    price_improvement_ticks = 0 if execution_style == "maker" else (
        0 if effective_paper else config.BOT_G_LIVE_ENTRY_PRICE_IMPROVEMENT_TICKS
    )
    limit_price = min(
        config.BOT_G_MAX_ENTRY_PRICE,
        entry_price + config.BOT_G_ENTRY_TICK_SIZE * price_improvement_ticks,
    )

    prime_payload: dict = {}
    if mode == "prime":
        cex = (
            _cex_confirmation(market, side_label, now_ms)
            if config.BOT_G_PRIME_REQUIRE_CEX_CONFIRM or effective_paper
            else {"skipped": True, "reason": "live_gate_disabled_pre_submit"}
        )
        prime_payload["cex"] = cex
        if config.BOT_G_PRIME_REQUIRE_CEX_CONFIRM and not (cex and cex.get("confirmed")):
            _record_prime_rejection(
                market,
                "cex_not_confirmed",
                {
                    "side_token": side_label,
                    "price": str(entry_price),
                    "observed_ask_price": str(ask_price),
                    "signal_price": str(signal_price),
                    "execution_style": execution_style,
                    "cex": cex,
                },
            )
            return 0

        depletion = (
            _book_depletion_signal(token_id, now_ms)
            if config.BOT_G_PRIME_REQUIRE_DEPLETION or effective_paper
            else {"skipped": True, "reason": "live_gate_disabled_pre_submit"}
        )
        prime_payload["depletion"] = depletion
        if config.BOT_G_PRIME_REQUIRE_DEPLETION:
            ratio = (
                Decimal(str(depletion["depletion_ratio"]))
                if depletion and depletion.get("depletion_ratio") is not None
                else None
            )
            if ratio is None or ratio > config.BOT_G_PRIME_MAX_DEPLETION_RATIO:
                _record_prime_rejection(
                    market,
                    "book_not_depleting",
                    {
                        "side_token": side_label,
                        "price": str(entry_price),
                        "observed_ask_price": str(ask_price),
                        "signal_price": str(signal_price),
                        "execution_style": execution_style,
                        "depletion": depletion,
                        "threshold": str(config.BOT_G_PRIME_MAX_DEPLETION_RATIO),
                    },
                )
                return 0
    mark_timing("prime_signal_ms")

    # Refresh the clock immediately before sizing/submission. The scan loop
    # can spend several seconds on DB, CEX, depletion, and CLOB checks; using
    # the original scan timestamp here can make an order look 40s pre-close
    # locally while it reaches the exchange at or after the close.
    fresh_now_ms = int(time.time() * 1000)
    fresh_t_to_res_sec = int((end_dt.timestamp() * 1000 - fresh_now_ms) / 1000)
    if fresh_t_to_res_sec < config.BOT_G_MIN_ENTRY_LEAD_SECONDS:
        try:
            from core.db import Event, get_session_factory
            sf = get_session_factory()
            with sf() as s:
                s.add(Event(
                    bot_id=BOT_ID,
                    event_type="bot_g.entry_stale_time_rejected",
                    severity="warning" if not effective_paper else "info",
                    message=(
                        "entry rejected by fresh pre-submit clock: "
                        f"fresh_t_to_res={fresh_t_to_res_sec}s "
                        f"< min_lead={config.BOT_G_MIN_ENTRY_LEAD_SECONDS}s"
                    ),
                    payload={
                        "condition_id": cid,
                        "mode": mode,
                        "side_token": side_label,
                        "observed_entry_price": str(entry_price),
                        "observed_ask_price": str(ask_price),
                        "signal_price": str(signal_price),
                        "execution_style": execution_style,
                        "initial_t_to_res_sec": t_to_res_sec,
                        "fresh_t_to_res_sec": fresh_t_to_res_sec,
                        "min_lead_sec": config.BOT_G_MIN_ENTRY_LEAD_SECONDS,
                        "execution_mode": "paper" if effective_paper else "live",
                        "timing_ms": timing_ms,
                        "timing_cumulative_ms": timing_cumulative_ms,
                    },
                ))
                s.commit()
        except Exception:
            pass
        log.warning(
            "bot_g.entry_stale_time_rejected mode=%s cid=%s initial_t_to_res=%ds "
            "fresh_t_to_res=%ds min_lead=%ds",
            mode, cid[:16], t_to_res_sec, fresh_t_to_res_sec,
            config.BOT_G_MIN_ENTRY_LEAD_SECONDS,
        )
        return 0
    mark_timing("fresh_clock_ms")

    # Size: taker mode is capped to current ask depth. Maker mode provides
    # resting liquidity at bid, so there is no ask-depth cap on order size.
    # In live mode, size against the submitted limit so the worst-case fill
    # cannot exceed the fixed dollar budget when we cross one tick for transfer.
    dollars = config.BOT_G_FIXED_TRADE_USD
    max_by_dollar = dollars / limit_price
    size = max_by_dollar if execution_style == "maker" else min(max_by_dollar, ask_size)
    if size <= 0:
        return 0
    # GLM audit #8: minimum notional floor — at 20 shares x $0.02 = $0.40,
    # the ~$0.35 fee per order would eat half the bet. Skip entries where
    # actual notional < $1.00.
    actual_notional = size * limit_price
    if actual_notional + Decimal("0.000001") < Decimal("1.00"):
        log.debug(
            "bot_g.entry_skip_min_notional cid=%s notional=$%s < $1.00",
            cid[:16], actual_notional,
        )
        return 0
    # U-01 (audit 2026-05-10): cross-bot fleet cap. Bot D already calls this;
    # Bot G was the gap. Intended notional = actual_notional (sized above).
    from core.fleet import check_fleet_exposure
    fleet_check = check_fleet_exposure(BOT_ID, actual_notional)
    if not fleet_check.ok:
        log.info(
            "bot_g.fleet_cap_breach cid=%s intended=%s current=%s cap=%s reason=%s",
            cid[:16], fleet_check.intended_usd,
            fleet_check.current_total_usd, fleet_check.deployable_cap_usd,
            fleet_check.reason,
        )
        return 0
    capacity_depth = _entry_capacity_depth(token_id, limit_price, fresh_now_ms)
    mark_timing("capacity_depth_ms")

    log.info(
        "bot_g.entry_attempt mode=%s style=%s cid=%s side=BUY_%s entry=%s ask=%s "
        "limit=%s size=%s t_to_res=%ds fresh_t_to_res=%ds depth=%s",
        mode, execution_style, cid[:16], side_label, entry_price, ask_price,
        limit_price, size, t_to_res_sec, fresh_t_to_res_sec,
        capacity_depth.get("depth_by_tick", []),
    )

    # Place via ClobWrapper. `paper_override=True` makes this a paper-mode
    # order (paper-prefix order_id, writes to Order table).
    try:
        from core.clob_v2 import OrderType, Side
        resp = clob.place_limit(
            token_id=token_id,
            price=limit_price,
            size=size,
            side=Side.BUY,
            order_type=OrderType.GTC,
        )
    except Exception as exc:
        log.warning("bot_g.entry_place_failed cid=%s err=%s", cid[:16], exc)
        mark_timing("submit_failed_ms")
        try:
            from core.db import Event, get_session_factory
            sf = get_session_factory()
            with sf() as s:
                s.add(Event(
                    bot_id=BOT_ID,
                    event_type="bot_g.entry_place_failed",
                    severity="warning",
                    message=f"entry place failed: {type(exc).__name__}",
                    payload={
                        "condition_id": cid,
                        "mode": mode,
                        "side_token": side_label,
                        "observed_entry_price": str(entry_price),
                        "observed_ask_price": str(ask_price),
                        "signal_price": str(signal_price),
                        "limit_price": str(limit_price),
                        "size": str(size),
                        "t_to_res_sec": t_to_res_sec,
                        "fresh_t_to_res_sec": fresh_t_to_res_sec,
                        "execution_mode": "paper" if effective_paper else "live",
                        "execution_style": execution_style,
                        "error_type": type(exc).__name__,
                        "timing_ms": timing_ms,
                        "timing_cumulative_ms": timing_cumulative_ms,
                    },
                ))
                s.commit()
        except Exception:
            pass
        return 0
    mark_timing("submit_response_ms")
    is_paper_order = resp.order_id.startswith("paper-") or resp.status == "PAPER_OPEN"
    persisted_status = resp.status or ("PAPER_OPEN" if is_paper_order else "OPEN")

    # Persist Order row for follow-up reconcile/settlement + attribution
    # Event (mode, t_to_res) for dashboard per-mode P&L breakdown.
    try:
        from core.db import Event, Order, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            s.add(Order(
                order_id=resp.order_id,
                bot_id=BOT_ID,
                condition_id=cid,
                token_id=token_id,
                side="BUY",
                price=limit_price,
                size=size,
                status=persisted_status,
                order_type="MAKER_GTC" if execution_style == "maker" else "GTC",
                placed_at=datetime.now(UTC),
            ))
            # Attribution event: order_id → {mode, t_to_res_sec} so the
            # dashboard can split P&L by jackpot vs scalp mode without
            # needing an Order.strategy_mode schema column.
            s.add(Event(
                bot_id=BOT_ID,
                event_type="bot_g.entry_placed",
                severity="info",
                message=(
                    f"{mode} entry order={resp.order_id} cid={cid[:16]} "
                    f"side=BUY_{side_label} t_to_res={fresh_t_to_res_sec}s"
                ),
                payload={
                    "mode": mode,
                    "order_id": resp.order_id,
                    "condition_id": cid,
                    "token_id": token_id,
                    "side_token": side_label,
                    "price": str(limit_price),
                    "observed_entry_price": str(entry_price),
                    "observed_ask_price": str(ask_price),
                    "signal_price": str(signal_price),
                    "live_price_improvement_ticks": price_improvement_ticks,
                    "size": str(size),
                    "notional_usd": str(actual_notional),
                    "t_to_res_sec": t_to_res_sec,
                    "fresh_t_to_res_sec": fresh_t_to_res_sec,
                    "min_lead_sec": config.BOT_G_MIN_ENTRY_LEAD_SECONDS,
                    "capacity_depth": capacity_depth,
                    "execution_mode": "paper" if is_paper_order else "live",
                    "execution_style": execution_style,
                    "maker_cancel_lead_sec": (
                        config.BOT_G_MAKER_CANCEL_LEAD_SECONDS
                        if execution_style == "maker"
                        else None
                    ),
                    "order_status": persisted_status,
                    "timing_ms": timing_ms,
                    "timing_cumulative_ms": timing_cumulative_ms,
                    **prime_payload,
                },
            ))
            s.commit()
    except Exception as exc:
        log.warning("bot_g.order_persist_failed cid=%s err=%s", cid[:16], exc)

    # OQ-044 fix: eager paper-fill at entry. Bot G already verified at entry
    # time that best_ask ≤ limit AND book depth ≥ size. In a live CLOB this
    # order would fill synchronously at best_ask against the resting
    # liquidity. Paper mode should mirror that. Without this, orders sit in
    # PAPER_OPEN forever — `core/portfolio.py::simulate_paper_fills` reads
    # the Book table (populated by Bot A/B/C/D), which the recorder-driven
    # Bot G never writes. Result observed 2026-04-23: 11 entries, 0 fills,
    # 0 P&L.
    #
    # Only fires in paper mode (detected via the `paper-` order_id prefix,
    # set by ClobWrapper._paper_fill). Live mode continues to rely on the
    # CLOB fill-event listener as before — a live GTC limit may not fill
    # instantly, and eager-filling it would create phantom Positions for
    # unfilled orders (this is precisely the ghost-position bug
    # SECURITY_AUDIT.md C-2 closed for Bot C, which we must not reopen).
    #
    # Trade ID uses the same `paper-fill-<order_id>` prefix simulate_paper_fills
    # uses for honest-book fills, and `on_fill` dedupes on trade_id, so even
    # if simulate_paper_fills runs later it cannot double-book this fill.
    if is_paper_order and execution_style != "maker":
        try:
            portfolio.on_fill(
                bot_id=BOT_ID,
                trade_id=f"paper-fill-{resp.order_id}",
                order_id=resp.order_id,
                condition_id=cid,
                token_id=token_id,
                side="BUY",
                price=limit_price,
                size=size,
                fee_usd=Decimal("0"),
                filled_at=datetime.now(UTC),
            )
            from core.db import Order, get_session_factory
            sf = get_session_factory()
            with sf() as s:
                db_o = s.get(Order, resp.order_id)
                if db_o is not None:
                    db_o.status = "FILLED"
                    s.commit()
        except Exception as exc:
            log.warning(
                "bot_g.eager_fill_failed order=%s err=%s (order stays PAPER_OPEN)",
                resp.order_id, exc,
            )

    _entered_this_session.add(key)
    log.info(
        "bot_g.entry_placed mode=%s style=%s cid=%s order_id=%s side=BUY_%s "
        "entry=%s ask=%s limit=%s size=%s",
        mode, execution_style, cid[:16], resp.order_id, side_label,
        entry_price, ask_price, limit_price, size,
    )
    return 1


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


_running = True


# ---------------------------------------------------------------------------
# Diagnostic telemetry (2026-04-23): tunes are blind without an empirical
# distribution of cheap-side prices in the final 60s. For every candidate
# evaluation the bot stores (scan_ms, yes_ask, no_ask, t_to_res_sec) in
# a bounded in-memory ring. `_emit_candidate_summary` runs every 5 min
# from run_loop and logs a percentile summary + "would-qualify-at-X"
# counts for ceilings {0.03, 0.05, 0.08, 0.10, 0.15}. Use this to pick
# the right BOT_G_MAX_ENTRY_PRICE with data, not guesses.
# ---------------------------------------------------------------------------

_CANDIDATE_OBS_CAP = 4096  # ~1h at current scan rate; bounded memory
_CANDIDATE_OBSERVATIONS: list[tuple[int, Decimal, Decimal, int]] = []


def _record_candidate_observation(
    now_ms: int, yes_ask: Decimal, no_ask: Decimal, t_to_res_sec: int,
) -> None:
    """Append one observation per (market, scan).

    Why this accepts single-side quotes: the recorder's WSS subscription
    has per-market gaps (observed 2026-04-23: near-resolution markets
    sometimes lack recent events on one or both sides). Rejecting only
    when BOTH sides are missing lets us still record the cheap-side price
    when at least one book is readable. Missing sides are normalised to
    Decimal("10") — well above any real Polymarket price — so downstream
    min(y,n) selects the side that IS present.
    """
    if yes_ask <= 0 and no_ask <= 0:
        return
    if yes_ask <= 0:
        yes_ask = Decimal("10")
    if no_ask <= 0:
        no_ask = Decimal("10")
    _CANDIDATE_OBSERVATIONS.append((now_ms, yes_ask, no_ask, t_to_res_sec))
    # Bound memory: drop oldest when over cap.
    while len(_CANDIDATE_OBSERVATIONS) > _CANDIDATE_OBS_CAP:
        _CANDIDATE_OBSERVATIONS.pop(0)


def _emit_candidate_summary(now_ms: int) -> None:
    """Log a percentile + would-qualify summary over the last hour's
    candidate evaluations. Also writes an Event row so the dashboard can
    surface the distribution without tailing journald.
    """
    one_hour_ago = now_ms - 3_600_000
    # Trim observations older than 1h.
    while _CANDIDATE_OBSERVATIONS and _CANDIDATE_OBSERVATIONS[0][0] < one_hour_ago:
        _CANDIDATE_OBSERVATIONS.pop(0)
    if not _CANDIDATE_OBSERVATIONS:
        log.info(
            "bot_g.candidate_summary n=0 window=1h no usable quote observations "
            "current_band[%s,%s]",
            config.BOT_G_MIN_ENTRY_PRICE,
            config.BOT_G_MAX_ENTRY_PRICE,
        )
        try:
            from core.db import Event, get_session_factory
            sf = get_session_factory()
            with sf() as s:
                s.add(Event(
                    bot_id=BOT_ID,
                    event_type="bot_g.candidate_summary",
                    severity="info",
                    message=(
                        "1h candidate-distribution: n=0 "
                        "no usable quote observations"
                    ),
                    payload={
                        "n": 0,
                        "reason": "no_usable_quote_observations",
                        "current_min": str(config.BOT_G_MIN_ENTRY_PRICE),
                        "current_ceiling": str(config.BOT_G_MAX_ENTRY_PRICE),
                        "current_band_count": 0,
                        "below_current_min": 0,
                        "above_current_max": 0,
                    },
                ))
                s.commit()
        except Exception as exc:
            log.warning("bot_g.candidate_summary_persist_failed err=%s", exc)
        return

    cheap = sorted(min(y, n) for _, y, n, _ in _CANDIDATE_OBSERVATIONS)
    total = len(cheap)

    def _pct(p: float) -> Decimal:
        idx = max(0, min(total - 1, int(total * p)))
        return cheap[idx]

    p05 = _pct(0.05)
    p10 = _pct(0.10)
    p25 = _pct(0.25)
    p50 = _pct(0.50)
    p75 = _pct(0.75)

    ceilings = [Decimal("0.03"), Decimal("0.05"), Decimal("0.08"),
                Decimal("0.10"), Decimal("0.15")]
    qualify = {str(c): sum(1 for x in cheap if x <= c) for c in ceilings}
    current_min = config.BOT_G_MIN_ENTRY_PRICE
    current_max = config.BOT_G_MAX_ENTRY_PRICE
    current_band = sum(1 for x in cheap if current_min <= x <= current_max)
    below_current_min = sum(1 for x in cheap if x < current_min)
    above_current_max = sum(1 for x in cheap if x > current_max)

    log.info(
        "bot_g.candidate_summary n=%d window=1h p05=%s p10=%s p25=%s p50=%s p75=%s "
        "would_qualify_at_ceiling[n/%d]: 0.03=%d 0.05=%d 0.08=%d 0.10=%d 0.15=%d "
        "current_band[%s,%s]=%d below_min=%d above_max=%d",
        total, p05, p10, p25, p50, p75, total,
        qualify["0.03"], qualify["0.05"], qualify["0.08"],
        qualify["0.10"], qualify["0.15"],
        current_min, current_max, current_band, below_current_min, above_current_max,
    )

    # Persist so the dashboard + post-hoc analysis can find it.
    try:
        from core.db import Event, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            s.add(Event(
                bot_id=BOT_ID,
                event_type="bot_g.candidate_summary",
                severity="info",
                message=(
                    f"1h candidate-distribution: n={total} p50={p50} "
                    f"would-qualify@0.05={qualify['0.05']} "
                    f"@0.08={qualify['0.08']} @0.10={qualify['0.10']}"
                ),
                payload={
                    "n": total,
                    "p05": str(p05), "p10": str(p10), "p25": str(p25),
                    "p50": str(p50), "p75": str(p75),
                    "qualify_counts": qualify,
                    "current_min": str(current_min),
                    "current_ceiling": str(config.BOT_G_MAX_ENTRY_PRICE),
                    "current_band_count": current_band,
                    "below_current_min": below_current_min,
                    "above_current_max": above_current_max,
                },
            ))
            s.commit()
    except Exception as exc:
        log.warning("bot_g.candidate_summary_persist_failed err=%s", exc)


def _handle_signal(signum, _frame):
    global _running
    log.info("bot_g.signal_received signum=%d stopping", signum)
    _running = False


def _clob_effective_paper(clob) -> bool:
    effective_paper = getattr(clob, "_effective_paper", None)
    if callable(effective_paper):
        try:
            return bool(effective_paper())
        except Exception:
            pass
    return bool(getattr(clob, "paper_override", True))


def _persist_runtime_state(clob, *, bot_live_intent: bool, global_env: str) -> None:
    effective_paper = _clob_effective_paper(clob)
    log.info(
        "bot_g.runtime_state bot_env=%s dry_run=%s global_env=%s "
        "paper_override=%s effective_paper=%s live_intent=%s "
        "live_wallet_usd=%s approved_at=%s",
        config.BOT_G_ENV,
        config.BOT_G_DRY_RUN,
        global_env,
        getattr(clob, "paper_override", None),
        effective_paper,
        bot_live_intent,
        config.BOT_G_LIVE_WALLET_USD,
        config.BOT_G_LIVE_APPROVED_AT or "",
    )
    try:
        from core.db import Event, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            s.add(Event(
                bot_id=BOT_ID,
                event_type="bot_g.runtime_state",
                severity="info",
                message=(
                    f"Bot G runtime effective_paper={effective_paper} "
                    f"bot_env={config.BOT_G_ENV} global_env={global_env}"
                ),
                payload={
                    "bot_env": config.BOT_G_ENV,
                    "bot_dry_run": bool(config.BOT_G_DRY_RUN),
                    "global_polymarket_env": global_env,
                    "paper_override": bool(getattr(clob, "paper_override", True)),
                    "effective_paper": effective_paper,
                    "live_intent": bot_live_intent,
                    "live_approved_at": config.BOT_G_LIVE_APPROVED_AT or "",
                    "fixed_trade_usd": str(config.BOT_G_FIXED_TRADE_USD),
                    "paper_max_daily_entries": config.BOT_G_MAX_DAILY_ENTRIES,
                    "paper_max_concurrent_positions": config.BOT_G_MAX_CONCURRENT_POSITIONS,
                    "live_max_daily_entries": config.BOT_G_LIVE_MAX_DAILY_ENTRIES,
                    "live_max_concurrent_positions": (
                        config.BOT_G_LIVE_MAX_CONCURRENT_POSITIONS
                    ),
                    "live_max_daily_gross_notional_usd": str(
                        config.BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD
                    ),
                    "live_wallet_usd": str(config.BOT_G_LIVE_WALLET_USD),
                    "execution_style": config.BOT_G_EXECUTION_STYLE,
                    "maker_cancel_lead_sec": config.BOT_G_MAKER_CANCEL_LEAD_SECONDS,
                },
            ))
            s.commit()
    except Exception as exc:
        log.warning("bot_g.runtime_state_persist_failed err=%s", exc)


def _runtime_state_heartbeat_due(now_ts: float, last_ts: float | None) -> bool:
    """Return whether the runtime-state event should be refreshed."""
    if last_ts is None:
        return True
    return (now_ts - last_ts) >= config.BOT_G_RUNTIME_STATE_HEARTBEAT_INTERVAL_S


def _reconcile_execution_truth(portfolio, clob) -> int:
    if _clob_effective_paper(clob):
        book_fills = int(portfolio.simulate_paper_fills(BOT_ID) or 0)
        maker_fills = _simulate_maker_paper_fills(portfolio)
        return book_fills + maker_fills
    return int(
        portfolio.reconcile_live_fills(
            clob,
            BOT_ID,
            require_known_order=True,
        )
        or 0
    )


def _paper_trade_from_payload(raw_payload: str | None) -> tuple[str, Decimal, Decimal] | None:
    try:
        payload = json.loads(raw_payload or "{}")
    except json.JSONDecodeError:
        return None
    side = str(payload.get("side") or "").upper()
    if side not in {"BUY", "SELL"}:
        return None
    try:
        price = Decimal(str(payload.get("price")))
        size = Decimal(str(payload.get("size")))
    except Exception:
        return None
    if price <= 0 or size <= 0:
        return None
    return side, price, size


def _simulate_maker_paper_fills(portfolio) -> int:
    """Fill paper maker BUY bids from subsequent recorder trade prints.

    Bot G maker mode posts a resting BUY at the observed bid and cancels it
    before market close. Unlike taker paper mode, this must not eager-fill at
    placement. A maker BUY can be filled only by a later taker SELL print at or
    below our bid, so this reads the shared recorder's `last_trade_price`
    stream and writes normal Portfolio fills when that causal condition holds.
    """
    from sqlalchemy import func, select

    from core.db import Event, Order, Trade, get_session_factory

    conn = _recorder_conn()
    if conn is None:
        return 0

    sf = get_session_factory()
    fills = 0
    try:
        with sf() as s:
            orders = list(
                s.scalars(
                    select(Order).where(
                        Order.bot_id == BOT_ID,
                        Order.side == "BUY",
                        Order.order_type == "MAKER_GTC",
                        Order.status.in_(("PAPER_OPEN", "PARTIAL")),
                    )
                )
            )
            for order in orders:
                if not str(order.order_id).startswith("paper-"):
                    continue
                order_size = Decimal(str(order.size or 0))
                already_filled = s.scalar(
                    select(func.coalesce(func.sum(Trade.size), 0)).where(
                        Trade.order_id == order.order_id,
                        Trade.side == "BUY",
                    )
                )
                remaining = order_size - Decimal(str(already_filled or 0))
                if remaining <= 0:
                    continue

                placed_at = order.placed_at
                if placed_at.tzinfo is None:
                    placed_at = placed_at.replace(tzinfo=UTC)
                placed_ms = int(placed_at.timestamp() * 1000)
                rows = conn.execute(
                    """
                    SELECT id, received_at_ms, payload_json
                    FROM pm_events
                    WHERE asset_id=?
                      AND event_type='last_trade_price'
                      AND received_at_ms > ?
                    ORDER BY received_at_ms ASC
                    LIMIT 200
                    """,
                    (order.token_id, placed_ms),
                ).fetchall()
                for row in rows:
                    trade = _paper_trade_from_payload(row["payload_json"])
                    if trade is None:
                        continue
                    side, trade_price, trade_size = trade
                    if side != "SELL" or trade_price > Decimal(str(order.price)):
                        continue
                    fill_size = min(remaining, trade_size)
                    trade_id = f"paper-maker-fill-{order.order_id}-{row['id']}"
                    if s.get(Trade, trade_id) is not None:
                        continue
                    filled_at = datetime.fromtimestamp(
                        int(row["received_at_ms"]) / 1000,
                        tz=UTC,
                    )
                    portfolio.on_fill(
                        bot_id=BOT_ID,
                        trade_id=trade_id,
                        order_id=order.order_id,
                        condition_id=order.condition_id,
                        token_id=order.token_id,
                        side="BUY",
                        price=Decimal(str(order.price)),
                        size=fill_size,
                        fee_usd=Decimal("0"),
                        filled_at=filled_at,
                    )
                    s.add(Event(
                        bot_id=BOT_ID,
                        event_type="bot_g.maker_paper_filled",
                        severity="info",
                        message="maker paper order filled from recorder trade print",
                        payload={
                            "order_id": order.order_id,
                            "condition_id": order.condition_id,
                            "token_id": order.token_id,
                            "fill_price": str(order.price),
                            "fill_size": str(fill_size),
                            "triggering_pm_event_id": int(row["id"]),
                            "trigger_trade_price": str(trade_price),
                            "trigger_trade_size": str(trade_size),
                            "trigger_side": side,
                        },
                    ))
                    s.commit()
                    fills += 1
                    remaining -= fill_size
                    if remaining <= 0:
                        break
    except Exception as exc:
        log.warning("bot_g.maker_paper_fill_failed err=%s", exc)
        return fills
    finally:
        conn.close()
    return fills


def _reconcile_live_open_orders(clob) -> int:
    """Mark local live orders closed when CLOB no longer lists them open.

    A live GTC can expire/close without filling. Fill reconciliation correctly
    leaves no Trade row, but the local Order row otherwise remains `live` and
    makes the dashboard/exposure counters look stuck.
    """
    if _clob_effective_paper(clob):
        return 0
    try:
        exchange_open_ids = {o.order_id for o in (clob.get_user_orders() or [])}
    except Exception as exc:
        log.warning("bot_g.reconcile_open_orders_failed err=%s", exc)
        return 0

    from sqlalchemy import select

    from core.db import Event, Order, Trade, get_session_factory

    sf = get_session_factory()
    closed = 0
    with sf() as s:
        local_orders = list(
            s.scalars(
                select(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.side == "BUY",
                    Order.status.in_(("OPEN", "PARTIAL", "live")),
                )
            )
        )
        for order in local_orders:
            if order.order_id in exchange_open_ids:
                continue
            has_trade = s.scalars(
                select(Trade).where(Trade.order_id == order.order_id)
            ).first()
            old_status = order.status
            order.status = "EXCHANGE_CLOSED"
            order.last_updated = datetime.now(UTC)
            s.add(Event(
                bot_id=BOT_ID,
                event_type="bot_g.exchange_order_reconciled",
                severity="info",
                message=(
                    "Live order absent from CLOB open orders; marked "
                    "EXCHANGE_CLOSED"
                ),
                payload={
                    "order_id": order.order_id,
                    "condition_id": order.condition_id,
                    "old_status": old_status,
                    "new_status": order.status,
                    "exchange_open_count": len(exchange_open_ids),
                    "had_fill": has_trade is not None,
                },
            ))
            closed += 1
        if closed:
            s.commit()
    return closed


def _cancel_expired_maker_orders(clob) -> int:
    """Cancel maker-mode BUY orders at window-end-minus configured lead."""
    from sqlalchemy import select

    from core.db import Event, Order, get_session_factory

    now = datetime.now(UTC)
    effective_paper = _clob_effective_paper(clob)
    sf = get_session_factory()
    cancelled = 0
    with sf() as s:
        orders = list(
            s.scalars(
                select(Order).where(
                    Order.bot_id == BOT_ID,
                    Order.side == "BUY",
                    Order.order_type == "MAKER_GTC",
                    Order.status.in_(("PAPER_OPEN", "OPEN", "PARTIAL", "live")),
                )
            )
        )
        if not orders:
            return 0
        events = list(
            s.scalars(
                select(Event)
                .where(
                    Event.bot_id == BOT_ID,
                    Event.event_type == "bot_g.entry_placed",
                )
                .order_by(Event.created_at.desc())
            )
        )
        events_by_order = {
            row.payload.get("order_id"): row
            for row in events
            if isinstance(row.payload, dict) and row.payload.get("order_id")
        }
        for order in orders:
            event = events_by_order.get(order.order_id)
            if event is None:
                continue
            payload = event.payload or {}
            try:
                fresh_t_to_res = int(payload.get("fresh_t_to_res_sec"))
            except (TypeError, ValueError):
                continue
            cancel_lead = int(
                payload.get("maker_cancel_lead_sec")
                or config.BOT_G_MAKER_CANCEL_LEAD_SECONDS
            )
            cancel_after_s = max(0, fresh_t_to_res - cancel_lead)
            placed_at = order.placed_at
            if placed_at.tzinfo is None:
                placed_at = placed_at.replace(tzinfo=UTC)
            elapsed_s = (now - placed_at).total_seconds()
            if elapsed_s < cancel_after_s:
                continue

            old_status = order.status
            cancelled_on_exchange = True
            if not effective_paper:
                try:
                    cancelled_on_exchange = bool(clob.cancel_order(order.order_id))
                except Exception as exc:
                    s.add(Event(
                        bot_id=BOT_ID,
                        event_type="bot_g.maker_cancel_failed",
                        severity="warning",
                        message=f"maker cancel failed: {type(exc).__name__}",
                        payload={
                            "order_id": order.order_id,
                            "condition_id": order.condition_id,
                            "old_status": old_status,
                            "error_type": type(exc).__name__,
                        },
                    ))
                    continue
            if not cancelled_on_exchange:
                continue
            order.status = "CANCELLED"
            order.last_updated = now
            s.add(Event(
                bot_id=BOT_ID,
                event_type="bot_g.maker_order_cancelled",
                severity="info",
                message="maker order cancelled before market close",
                payload={
                    "order_id": order.order_id,
                    "condition_id": order.condition_id,
                    "old_status": old_status,
                    "new_status": order.status,
                    "fresh_t_to_res_sec": fresh_t_to_res,
                    "maker_cancel_lead_sec": cancel_lead,
                    "elapsed_sec": elapsed_s,
                    "execution_mode": "paper" if effective_paper else "live",
                },
            ))
            cancelled += 1
        if cancelled:
            s.commit()
    return cancelled


def _paper_take_profit_exits(portfolio, clob, *, now: datetime | None = None) -> int:
    """Paper-only proof of the near-close take-profit concept.

    If an open paper position's current best bid reaches the configured
    threshold during the configured final-window slice, synthesize a paper
    SELL fill. This deliberately does not run in live mode.
    """
    if not config.BOT_G_PAPER_TAKE_PROFIT_ENABLED:
        return 0
    if not getattr(clob, "paper_override", True):
        log.warning("bot_g.paper_take_profit.disabled_live bot_id=%s", BOT_ID)
        return 0
    if not _clob_effective_paper(clob):
        log.warning("bot_g.paper_take_profit.disabled_live bot_id=%s", BOT_ID)
        return 0

    from sqlalchemy import select

    from core.db import Event, Market, Position, Trade, get_session_factory

    now = now or datetime.now(UTC)
    now_ms = int(now.timestamp() * 1000)
    sf = get_session_factory()
    with sf() as s:
        positions = list(
            s.scalars(
                select(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.status == "OPEN",
                )
            )
        )
        markets = {
            m.condition_id: m
            for m in s.scalars(
                select(Market).where(
                    Market.condition_id.in_(
                        [p.condition_id for p in positions if p.condition_id]
                    )
                )
            )
        } if positions else {}

    exited = 0
    threshold = config.BOT_G_PAPER_TAKE_PROFIT_PRICE
    start_sec = config.BOT_G_PAPER_TAKE_PROFIT_START_SECONDS
    end_sec = config.BOT_G_PAPER_TAKE_PROFIT_END_SECONDS
    for pos in positions:
        market = markets.get(pos.condition_id)
        if market is None or market.end_date is None:
            continue
        end_dt = market.end_date
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=UTC)
        t_to_res_sec = int((end_dt.timestamp() * 1000 - now_ms) / 1000)
        if t_to_res_sec < end_sec or t_to_res_sec > start_sec:
            continue

        quote = _latest_best_bid_ask(pos.token_id, pos.condition_id, now_ms)
        if quote is None:
            continue
        best_bid, _best_ask, _best_ask_size = quote
        if best_bid < threshold:
            continue

        threshold_tag = str(threshold).replace(".", "p")
        trade_id = f"paper-take-profit-{pos.id}-{threshold_tag}"
        with sf() as s:
            if s.get(Trade, trade_id) is not None:
                continue

        portfolio.on_fill(
            bot_id=BOT_ID,
            trade_id=trade_id,
            order_id=None,
            condition_id=pos.condition_id,
            token_id=pos.token_id,
            side="SELL",
            price=best_bid,
            size=pos.size,
            fee_usd=Decimal("0"),
            filled_at=now,
        )
        with sf() as s:
            s.add(Event(
                bot_id=BOT_ID,
                event_type="bot_g.paper_take_profit_exit",
                severity="info",
                message=(
                    f"paper take-profit exit position={pos.id} bid={best_bid} "
                    f"threshold={threshold}"
                ),
                payload={
                    "position_id": pos.id,
                    "condition_id": pos.condition_id,
                    "token_id": pos.token_id,
                    "side_token": pos.side,
                    "size": str(pos.size),
                    "best_bid": str(best_bid),
                    "threshold": str(threshold),
                    "t_to_res_sec": t_to_res_sec,
                    "window_start_sec": start_sec,
                    "window_end_sec": end_sec,
                    "trade_id": trade_id,
                },
            ))
            s.commit()
        exited += 1
    return exited


def _take_profit_shadow_signals(clob, *, now: datetime | None = None) -> int:
    """Record TP@threshold opportunities without changing positions.

    This is the event-only bridge between the TP@50c counterfactual and any
    future live-exit ADR. It deliberately does not call the CLOB or
    Portfolio.on_fill.
    """
    if not config.BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_ENABLED:
        return 0

    from sqlalchemy import select

    from core.db import Event, Market, Position, get_session_factory

    now = now or datetime.now(UTC)
    now_ms = int(now.timestamp() * 1000)
    sf = get_session_factory()
    with sf() as s:
        positions = list(
            s.scalars(
                select(Position).where(
                    Position.bot_id == BOT_ID,
                    Position.status == "OPEN",
                )
            )
        )
        markets = {
            m.condition_id: m
            for m in s.scalars(
                select(Market).where(
                    Market.condition_id.in_(
                        [p.condition_id for p in positions if p.condition_id]
                    )
                )
            )
        } if positions else {}
        seen = {
            (
                int((ev.payload or {}).get("position_id") or 0),
                str((ev.payload or {}).get("threshold") or ""),
            )
            for ev in s.scalars(
                select(Event).where(
                    Event.bot_id == BOT_ID,
                    Event.event_type == "bot_g.take_profit_shadow_signal",
                )
            )
        }

    emitted = 0
    threshold = config.BOT_G_TAKE_PROFIT_SHADOW_SIGNAL_PRICE
    start_sec = config.BOT_G_TAKE_PROFIT_SHADOW_START_SECONDS
    end_sec = config.BOT_G_TAKE_PROFIT_SHADOW_END_SECONDS
    effective_paper = _clob_effective_paper(clob)
    threshold_key = str(threshold)
    events: list[Event] = []
    for pos in positions:
        if (int(pos.id or 0), threshold_key) in seen:
            continue
        market = markets.get(pos.condition_id)
        if market is None or market.end_date is None:
            continue
        end_dt = market.end_date
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=UTC)
        t_to_res_sec = int((end_dt.timestamp() * 1000 - now_ms) / 1000)
        if t_to_res_sec < end_sec or t_to_res_sec > start_sec:
            continue

        quote = _latest_best_bid_ask(pos.token_id, pos.condition_id, now_ms)
        if quote is None:
            continue
        best_bid, best_ask, best_ask_size = quote
        if best_bid < threshold:
            continue

        events.append(
            Event(
                bot_id=BOT_ID,
                event_type="bot_g.take_profit_shadow_signal",
                severity="info",
                message=(
                    f"shadow take-profit signal position={pos.id} "
                    f"bid={best_bid} threshold={threshold}"
                )[:500],
                payload={
                    "position_id": pos.id,
                    "condition_id": pos.condition_id,
                    "token_id": pos.token_id,
                    "side_token": pos.side,
                    "size": str(pos.size),
                    "best_bid": str(best_bid),
                    "best_ask": str(best_ask),
                    "best_ask_size": str(best_ask_size),
                    "threshold": threshold_key,
                    "t_to_res_sec": t_to_res_sec,
                    "window_start_sec": start_sec,
                    "window_end_sec": end_sec,
                    "effective_paper": effective_paper,
                    "shadow_only": True,
                    "would_exit": True,
                },
            )
        )
        emitted += 1

    if events:
        with sf() as s:
            s.add_all(events)
            s.commit()
    return emitted


async def run_loop(args) -> None:
    log.info(
        "bot_g.startup bankroll=$%s trade_size=$%s max_price=%s entry_window=%ds "
        "max_concurrent=%d max_daily=%d env=%s dry_run=%s",
        config.BOT_G_BANKROLL_USD, config.BOT_G_FIXED_TRADE_USD,
        config.BOT_G_MAX_ENTRY_PRICE, config.BOT_G_ENTRY_SECONDS_BEFORE_RES,
        config.BOT_G_MAX_CONCURRENT_POSITIONS, config.BOT_G_MAX_DAILY_ENTRIES,
        config.BOT_G_ENV, config.BOT_G_DRY_RUN,
    )

    from core.clob_v2 import ClobWrapperV2 as ClobWrapper
    from core.config import get_settings
    from core.portfolio import Portfolio

    settings = get_settings()
    bot_live_intent = config.BOT_G_ENV == "live" and not config.BOT_G_DRY_RUN
    if bot_live_intent:
        if not config.BOT_G_LIVE_APPROVED_AT:
            raise RuntimeError(
                "Bot G live mode requires BOT_G_LIVE_APPROVED_AT=YYYY-MM-DD"
            )
        if BOT_ID == "bot_g_prime":
            raise RuntimeError(
                "Refusing Bot G live mode under bot_g_prime; use bot_g_prime_live "
                "so the 4c-8c paper shadow stays uncontaminated."
            )
        log.warning("bot_g.live_mode — real money WILL be at risk. Confirm this is intentional.")
    keystore = None
    if bot_live_intent and settings.is_live():
        from core.keystore import Keystore
        keystore = Keystore.load_from_settings(settings)
    clob = ClobWrapper(keystore=keystore, paper_override=not bot_live_intent)
    if not _clob_effective_paper(clob):
        clob.load_preflight_from_db()
    portfolio = Portfolio()
    _persist_runtime_state(
        clob,
        bot_live_intent=bot_live_intent,
        global_env=settings.polymarket_env.value,
    )
    last_runtime_state_ts = time.monotonic()

    _entered_this_session: set[tuple[str, str]] = set()
    last_paper_resolve_ts: float = 0.0
    last_candidate_summary_ts: float = 0.0
    candidate_summary_interval_s = 300  # every 5 min
    # Milestone-alert state: fire Telegram on n closed = 1, 10, 25, 50, 100.
    # Read from DB on startup to avoid re-firing after restart.
    _milestone_thresholds: list[int] = [1, 10, 25, 50, 100]
    _milestones_fired: set[int] = _load_fired_milestones()

    while _running:
        loop_start = time.monotonic()
        if _runtime_state_heartbeat_due(loop_start, last_runtime_state_ts):
            _persist_runtime_state(
                clob,
                bot_live_intent=bot_live_intent,
                global_env=settings.polymarket_env.value,
            )
            last_runtime_state_ts = loop_start

        # Halt checks.
        if _is_db_halted():
            log.info("bot_g.halt_active skipping_trading")
            await asyncio.sleep(config.BOT_G_SCAN_INTERVAL_S)
            continue
        if _emergency_halted():
            log.warning("bot_g.emergency_halt_active skipping_trading")
            await asyncio.sleep(config.BOT_G_SCAN_INTERVAL_S)
            continue
        if _rolling_roi_below_kill_threshold():
            log.warning("bot_g.kill_switch_active — edge gone; sleeping")
            await asyncio.sleep(config.BOT_G_SCAN_INTERVAL_S * 10)
            continue

        # Risk caps.
        effective_paper = _clob_effective_paper(clob)
        max_concurrent = (
            config.BOT_G_MAX_CONCURRENT_POSITIONS
            if effective_paper
            else config.BOT_G_LIVE_MAX_CONCURRENT_POSITIONS
        )
        max_daily_entries = (
            config.BOT_G_MAX_DAILY_ENTRIES
            if effective_paper
            else config.BOT_G_LIVE_MAX_DAILY_ENTRIES
        )
        open_n = _open_positions_count()
        daily_n = _todays_entry_count()
        daily_notional = _todays_entry_notional_usd()
        if open_n >= max_concurrent:
            log.debug("bot_g.at_position_cap open=%d", open_n)
        elif daily_n >= max_daily_entries:
            log.info("bot_g.at_daily_cap entries=%d", daily_n)
        elif (
            not effective_paper
            and daily_notional >= config.BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD
        ):
            log.info(
                "bot_g.at_live_daily_notional_cap notional=%s cap=%s",
                daily_notional,
                config.BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD,
            )
        else:
            # Market discovery + entry attempts.
            now_ms = int(time.time() * 1000)
            markets = _active_markets_near_resolution(now_ms)
            n_placed = 0
            for market in markets:
                if open_n + n_placed >= max_concurrent:
                    break
                if daily_n + n_placed >= max_daily_entries:
                    break
                if (
                    not effective_paper
                    and daily_notional
                    + Decimal(n_placed + 1) * config.BOT_G_FIXED_TRADE_USD
                    > config.BOT_G_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD
                ):
                    break
                try:
                    placed = await _try_enter_market(
                        market, now_ms, clob, portfolio, _entered_this_session,
                    )
                    n_placed += placed
                except Exception as exc:
                    log.warning("bot_g.entry_error cid=%s err=%s",
                                market.get("condition_id", "?")[:16], exc)
            if markets:
                log.info(
                    "bot_g.scan markets_in_window=%d placed=%d open=%d daily=%d",
                    len(markets), n_placed, open_n, daily_n,
                )
            else:
                # 2026-04-23 heartbeat: log at INFO every ~5 min even when
                # markets_in_window=0 so ops can distinguish "bot alive but
                # no candidates" from "bot hung or recorder dead". Without
                # this, the service journal was silent for 11h after the
                # recorder died on 2026-04-21, indistinguishable from a
                # healthy idle period.
                if not hasattr(run_loop, "_last_empty_scan_log"):
                    run_loop._last_empty_scan_log = 0.0
                if (time.monotonic() - run_loop._last_empty_scan_log) >= 300:
                    log.info(
                        "bot_g.scan_empty open=%d daily=%d (no markets in %ds window)",
                        open_n, daily_n, config.BOT_G_ENTRY_SECONDS_BEFORE_RES,
                    )
                    run_loop._last_empty_scan_log = time.monotonic()

        # Fill reconciliation runs every scan. Paper sim stays paper-only;
        # effective-live polls CLOB user trades into local DB truth.
        try:
            reconciled = _reconcile_execution_truth(portfolio, clob)
            if reconciled and not _clob_effective_paper(clob):
                log.info("bot_g.live_reconcile.fills count=%d", reconciled)
            closed_orders = _reconcile_live_open_orders(clob)
            if closed_orders:
                log.info("bot_g.live_reconcile.closed_orders count=%d", closed_orders)
            maker_cancels = _cancel_expired_maker_orders(clob)
            if maker_cancels:
                log.info("bot_g.maker_order_cancelled count=%d", maker_cancels)
            if _clob_effective_paper(clob):
                tp_exits = _paper_take_profit_exits(portfolio, clob)
                if tp_exits:
                    log.info("bot_g.paper_take_profit.exits count=%d", tp_exits)
                tp_shadow = _take_profit_shadow_signals(clob)
                if tp_shadow:
                    log.info("bot_g.take_profit_shadow.signals count=%d", tp_shadow)
        except Exception as exc:
            log.warning("bot_g.reconcile_fills_failed err=%s", exc)

        # Hourly resolution settlement (ADR-035).
        now_ts = time.time()
        if (now_ts - last_paper_resolve_ts) >= config.BOT_G_PAPER_RESOLVE_INTERVAL_S:
            try:
                settled = await asyncio.to_thread(
                    portfolio.reconcile_paper_resolutions, BOT_ID,
                )
                if settled:
                    log.info("bot_g.paper_resolve.settled count=%d", settled)
                last_paper_resolve_ts = now_ts
                # Milestone check after settlement — new closures might
                # cross a threshold.
                n_closed = _closed_positions_count()
                _check_and_fire_milestone(
                    _milestone_thresholds, _milestones_fired, n_closed,
                )
            except Exception as exc:
                log.warning("bot_g.paper_resolve.fail err=%s", exc)

        # Diagnostic: emit the 1h candidate-distribution summary every 5
        # min (log + Event row). Used to pick BOT_G_MAX_ENTRY_PRICE with
        # empirical data instead of a guess.
        if (now_ts - last_candidate_summary_ts) >= candidate_summary_interval_s:
            try:
                _emit_candidate_summary(int(time.time() * 1000))
            except Exception as exc:
                log.warning("bot_g.candidate_summary_failed err=%s", exc)
            last_candidate_summary_ts = now_ts

        # Sleep to next tick (accounting for work already done).
        elapsed = time.monotonic() - loop_start
        sleep_s = max(0.0, config.BOT_G_SCAN_INTERVAL_S - elapsed)
        if sleep_s > 0:
            await asyncio.sleep(sleep_s)

    log.info("bot_g.stop")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="bots.bot_g_longshot")
    p.add_argument("--log-level", default="INFO")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if config.BOT_G_ARCHIVED:
        log.warning("bot_g.archived — set BOT_G_ARCHIVED=false to enable")
        return 0

    errors = config.validate()
    if errors:
        for e in errors:
            log.error("bot_g.config_invalid %s", e)
        return 2

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        asyncio.run(run_loop(args))
    except KeyboardInterrupt:
        log.info("bot_g.interrupted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
