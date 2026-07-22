"""Bot F paper mirror — Step 1 of ADR-037-era Bot F graduation.

Polls `bot_f.db::mirror_signals` for freshly-detected trades by wallets on
the SHARPS_ALLOWLIST and — if the signal is `would_have_traded=1` (i.e.
age <= 90s when detected) — places a paper order sized at
`BOT_F_MIRROR_TRADE_SIZE_USD` via `ClobWrapper(paper_override=True)`.

Safety belts (three layers, matching the 2026-04-22 Bot B fix):
 1. Startup check: `BOT_F_MIRROR_ENV` MUST equal "paper" or the process
    exits immediately. No keystore is loaded.
 2. ClobWrapper is instantiated with `keystore=None, paper_override=True`
    (hard-coded — no code path flips this).
 3. Every place_limit call confirms `clob.paper_override` is True before
    dispatch.

This executor is the Step 1 of the Bot F graduation plan (see ADR-037 /
ADR-032). The goal for the first 2 weeks is measurement only: can we
actually execute close to the whale's entry price? What's our own fill
P&L vs the whale's eventual P&L? Success here is the precondition for an
ADR reversal to full paper/live.

Scope:
 - bot_id tag: `bot_f_mirror` (distinct from sensor `bot_f`).
 - Wallet allowlist baked at config level; editing requires a redeploy.
 - One mirror per (wallet, condition_id, side) pair per day — prevents
   runaway sizing if a whale scalps a market repeatedly.
"""
from __future__ import annotations

import logging
import os
import signal
import sqlite3
import sys
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from core.clob_v2 import ClobWrapperV2 as ClobWrapper, OrderType, Side
from core.config import get_settings
from core.portfolio import Portfolio

log = logging.getLogger("bot_f_mirror")

BOT_ID = "bot_f_mirror"

# The 4 validated sharps from 2026-04-22 wallet P&L retrospective.
# Realised / closes / WR / notes.
#   0x17db3fcd — +$153,926 / 91 closes / 70.3% (biggest defensible sample)
#   0x94a428cf — +$65,088 / 9 closes / 55.6%  (small sample, credible WR)
#   0x93abbc02 — +$30,637 / 7 closes / 85.7%  (and fired 3 would_have_trades)
#   0xb786b8b6 — +$25,526 / 704 closes / 51.9% (LARGEST sample, smallest edge)
# NOT included: 0xe9ad918c (+$1.48M, 100% WR over 28 closes) — suspicious,
# almost certainly market-maker or contract wallet that nets hedges off-trades.
SHARPS_ALLOWLIST: frozenset[str] = frozenset({
    "0xF00D0000000000000000000000000000000000df",
    "0xF00D0000000000000000000000000000000000e0",
    "0xF00D0000000000000000000000000000000000e1",
    "0xF00D0000000000000000000000000000000000e2",
})


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_decimal(name: str, default: str) -> Decimal:
    return Decimal(_env(name, default))


POLL_INTERVAL_SECONDS = int(_env("BOT_F_MIRROR_POLL_S", "60"))
TRADE_SIZE_USD = _env_decimal("BOT_F_MIRROR_TRADE_SIZE_USD", "5")
LOOKBACK_MINUTES = int(_env("BOT_F_MIRROR_LOOKBACK_MIN", "5"))

# T2-E (2026-04-23, Session 24): trailing-stop exit + staleness filters
# derived from G3-DEV-AGENCY/polymarket-copy-trading-bot's behaviour
# (clean-room; no code copied). Paper-only — same 3-layer safety holds.
TRAILING_STOP_PCT = _env_decimal("BOT_F_MIRROR_TRAILING_STOP_PCT", "0.20")
# Only arm the stop after the position has shown at least this much
# unrealised gain — prevents whipsaws on entry noise.
MIN_UNREALISED_FOR_STOP_PCT = _env_decimal("BOT_F_MIRROR_MIN_UNREALISED_PCT", "0.10")
# Hard floor relative to entry: exit if price drops this much below the
# *entry* (not the peak). Belts-and-braces alongside the trailing stop.
MAX_DRAWDOWN_FROM_ENTRY_PCT = _env_decimal("BOT_F_MIRROR_MAX_DD_PCT", "0.40")
# Staleness gate for the incoming signal itself (on top of the 90s
# `would_have_traded=1` filter in bot_f.db).
MAX_SIGNAL_AGE_SECONDS = int(_env("BOT_F_MIRROR_MAX_SIGNAL_AGE_S", "90"))
# Proximity-to-resolution gate: don't enter within N seconds of the
# market's end_date. Avoids mirroring whales that are just closing out.
MIN_TTR_FOR_ENTRY_SECONDS = int(_env("BOT_F_MIRROR_MIN_TTR_S", "300"))
# Maximum acceptable copy slippage versus the whale's observed entry. Used
# only when the recorder has a fresh current ask; if the ask is inside this
# band, paper mode fills at our actual reachable price.
MAX_COPY_SLIPPAGE = _env_decimal("BOT_F_MIRROR_MAX_COPY_SLIPPAGE", "0.02")


_running = True


def _sigterm(_signum, _frame):
    global _running
    log.info("bot_f_mirror.daemon.stop")
    _running = False


def _assert_paper_mode() -> None:
    """Belt-and-braces paper-only lock. Exit immediately if not paper.

    History: operator reports a prior bot accidentally traded live when
    BOT_*_ENV=paper was set at .env level but only POLYMARKET_ENV was read.
    This executor enforces paper mode three ways; this is layer 1.
    """
    env = _env("BOT_F_MIRROR_ENV", "").lower()
    if env != "paper":
        print(
            "FATAL: bot_f_mirror requires BOT_F_MIRROR_ENV=paper. "
            f"Got: {env!r}. Refusing to start.",
            file=sys.stderr,
        )
        sys.exit(2)


def _recent_mirrors(sf, cutoff: datetime) -> set[tuple[str, str, str]]:
    """Return the set of (wallet, condition_id, side) already mirrored today.

    Wallet is not persisted on Order rows, so we widen to
    (condition_id, side) — any wallet mirroring the same market/side today
    blocks further mirrors. Safer direction for a 3-layer paper guard.
    The wallet slot is kept for caller-side key compatibility and is
    populated with a sentinel.
    """
    from sqlalchemy import select, and_
    from core.db import Order
    with sf() as s:
        rows = s.scalars(
            select(Order).where(
                and_(
                    Order.bot_id == BOT_ID,
                    Order.placed_at >= cutoff,
                )
            )
        )
        return {("*", o.condition_id, o.side) for o in rows}


def _read_new_signals(bot_f_db: Path, since_ts: datetime) -> list[dict]:
    """Query bot_f.db for fresh mirror_signals matching our allowlist."""
    if not bot_f_db.exists():
        return []
    c = sqlite3.connect(str(bot_f_db))
    c.row_factory = sqlite3.Row
    rows = c.execute(
        """
        SELECT id, detected_at, wallet, condition_id, token_id, side,
               price, size_shares, whale_tx_ts, signal_age_ms, would_have_traded
        FROM mirror_signals
        WHERE would_have_traded = 1
          AND detected_at >= ?
        ORDER BY detected_at ASC
        """,
        (since_ts.strftime("%Y-%m-%d %H:%M:%S"),),
    ).fetchall()
    c.close()
    out = []
    for r in rows:
        # Polymarket data-api returns checksummed wallet addresses
        # (0x17Db3fCd...); the allowlist is all-lowercase. Normalise before
        # matching so case differences don't silently reject every signal.
        wallet = (r["wallet"] or "").lower()
        if wallet not in SHARPS_ALLOWLIST:
            continue
        d = dict(r)
        d["wallet"] = wallet
        out.append(d)
    return out


def _entry_ttr_ok(condition_id: str) -> tuple[bool, str]:
    """Return (True, "ok") if the market resolves more than
    MIN_TTR_FOR_ENTRY_SECONDS from now. Unknown market → allow (we do
    NOT gate on missing data; the mirror pipeline's other checks
    remain authoritative).
    """
    rec_db = os.environ.get("BOT_E_RECORDER_DB", "./data/bot_e_recorder.db")
    if not Path(rec_db).exists():
        return True, "ok"
    conn = sqlite3.connect(rec_db)
    try:
        row = conn.execute(
            "SELECT end_date_iso FROM markets WHERE condition_id=? "
            "ORDER BY scan_at_ms DESC LIMIT 1",
            (condition_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None or row[0] is None:
        return True, "ok"
    try:
        end_dt = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
    except Exception:
        return True, "ok"
    ttr = (end_dt - datetime.now(UTC)).total_seconds()
    if ttr < MIN_TTR_FOR_ENTRY_SECONDS:
        return False, f"ttr={int(ttr)}s<{MIN_TTR_FOR_ENTRY_SECONDS}s"
    return True, "ok"


# In-memory peak-price tracker keyed by Position.id. Lost on restart — that's
# acceptable for paper; the stop will re-arm from the next observed price
# above `MIN_UNREALISED_FOR_STOP_PCT` over entry.
_POSITION_PEAK_PRICE: dict[int, Decimal] = {}


def _current_ask_from_recorder(token_id: str, condition_id: str) -> Decimal | None:
    """Read the freshest top-of-book ask for this token from Bot E's
    recorder DB. Returns None if no event within 120s.

    We use the RECORDER's DB (not main.db books) because it has per-tick
    updates via WSS. Staleness >120s means we trust the last observed
    price too little to trigger an exit.
    """
    import json as _json
    rec_db = os.environ.get("BOT_E_RECORDER_DB", "./data/bot_e_recorder.db")
    if not Path(rec_db).exists():
        return None
    now_ms = int(time.time() * 1000)
    cutoff = now_ms - 120_000
    conn = sqlite3.connect(rec_db)
    try:
        rows = conn.execute(
            "SELECT event_type, payload_json, received_at_ms FROM pm_events "
            "WHERE (asset_id=? OR asset_id=?) "
            "  AND event_type IN ('best_bid_ask', 'price_change', 'book') "
            "  AND received_at_ms >= ? "
            "ORDER BY received_at_ms DESC LIMIT 20",
            (token_id, condition_id, cutoff),
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        try:
            payload = _json.loads(row[1])
        except Exception:
            continue
        et = row[0]
        if et == "best_bid_ask":
            ba = payload.get("best_ask")
            if ba is not None:
                return Decimal(str(ba))
        elif et == "book":
            asks = payload.get("asks") or []
            if asks:
                try:
                    return min(
                        Decimal(str(a["price"]))
                        for a in asks
                        if a.get("price") is not None
                    )
                except Exception:
                    continue
        elif et == "price_change":
            for pc in payload.get("price_changes") or []:
                if str(pc.get("asset_id") or "") != token_id:
                    continue
                ba = pc.get("best_ask")
                if ba is not None:
                    return Decimal(str(ba))
    return None


def _close_paper_position(
    pos, exit_price: Decimal, portfolio: Portfolio, reason: str,
) -> bool:
    """Close a paper position via a synthetic SELL fill at `exit_price`.
    Uses `Portfolio.on_fill` so cost-basis / P&L accounting is consistent
    with real exits. Emits a `bot_f_mirror.trailing_stop_exit` Event.
    """
    from core.db import Event, get_session_factory
    try:
        trade_id = f"paper-exit-{pos.id}-{int(time.time() * 1000)}"
        portfolio.on_fill(
            bot_id=BOT_ID,
            trade_id=trade_id,
            order_id=None,
            condition_id=pos.condition_id,
            token_id=pos.token_id,
            side="SELL",
            price=exit_price,
            size=Decimal(str(pos.size)),
            fee_usd=Decimal("0"),
            filled_at=datetime.now(UTC),
        )
        sf = get_session_factory()
        with sf() as s:
            peak = _POSITION_PEAK_PRICE.get(pos.id, Decimal(str(pos.avg_price)))
            s.add(Event(
                bot_id=BOT_ID,
                event_type="bot_f_mirror.trailing_stop_exit",
                severity="info",
                message=(
                    f"exit pos={pos.id} cid={pos.condition_id[:16]} "
                    f"entry={pos.avg_price} peak={peak} exit={exit_price} "
                    f"reason={reason}"
                ),
                payload={
                    "position_id": pos.id,
                    "condition_id": pos.condition_id,
                    "token_id": pos.token_id,
                    "entry_price": str(pos.avg_price),
                    "peak_price": str(peak),
                    "exit_price": str(exit_price),
                    "size": str(pos.size),
                    "reason": reason,
                },
            ))
            s.commit()
        _POSITION_PEAK_PRICE.pop(pos.id, None)
        return True
    except Exception as exc:
        log.warning(
            "bot_f_mirror.exit_failed pos=%s cid=%s err=%s",
            pos.id, pos.condition_id[:16], exc,
        )
        return False


def _update_trailing_stops(portfolio: Portfolio) -> int:
    """Scan OPEN bot_f_mirror positions; exit any whose current price has
    trailed `TRAILING_STOP_PCT` below the peak observed since entry, or
    dropped `MAX_DRAWDOWN_FROM_ENTRY_PCT` below entry. Returns exit count.

    Trailing-stop is only armed once unrealised gain exceeds
    `MIN_UNREALISED_FOR_STOP_PCT` — this prevents whipsaw exits on
    entry-noise during the first few ticks.
    """
    from sqlalchemy import select
    from core.db import Position, get_session_factory
    exits = 0
    sf = get_session_factory()
    with sf() as s:
        open_positions = s.scalars(select(Position).where(
            Position.bot_id == BOT_ID,
            Position.status == "OPEN",
        )).all()
    for pos in open_positions:
        cur = _current_ask_from_recorder(pos.token_id, pos.condition_id)
        if cur is None or cur <= 0:
            continue
        entry = Decimal(str(pos.avg_price))
        if entry <= 0:
            continue
        peak = _POSITION_PEAK_PRICE.get(pos.id, entry)
        if cur > peak:
            peak = cur
            _POSITION_PEAK_PRICE[pos.id] = peak
        # Hard-floor drawdown check runs independent of unrealised gain.
        dd_from_entry = (entry - cur) / entry
        if dd_from_entry >= MAX_DRAWDOWN_FROM_ENTRY_PCT:
            if _close_paper_position(pos, cur, portfolio, "max_drawdown"):
                exits += 1
            continue
        unrealised_pct = (peak - entry) / entry
        if unrealised_pct < MIN_UNREALISED_FOR_STOP_PCT:
            continue
        stop_price = peak * (Decimal("1") - TRAILING_STOP_PCT)
        if cur <= stop_price:
            if _close_paper_position(pos, cur, portfolio, "trailing_stop"):
                exits += 1
    return exits


def _mirror_signal(
    sig: dict,
    clob: ClobWrapper,
    portfolio: Portfolio,
    trade_size_usd: Decimal,
    recent: set[tuple[str, str, str]],
) -> bool:
    """Place a paper order mirroring the whale's side at their observed price.

    Returns True if placed, False if skipped.
    """
    # Layer 3 safety: confirm paper mode on the ClobWrapper before dispatch.
    if not clob.paper_override:
        log.error("bot_f_mirror.abort clob_not_paper wallet=%s cid=%s",
                  sig["wallet"], sig["condition_id"][:16])
        return False
    side_norm = sig["side"].upper()
    dedup_key = ("*", sig["condition_id"], side_norm)
    if dedup_key in recent:
        return False

    # T2-E staleness filter: the db column `signal_age_ms` captures the
    # whale-tx → detected-at delta. Even though bot_f's ingest marks
    # `would_have_traded=1` when age <= 90s, we allow the operator to
    # tighten this gate here without touching the ingest side.
    age_ms = sig.get("signal_age_ms")
    if age_ms is not None and age_ms > MAX_SIGNAL_AGE_SECONDS * 1000:
        log.info(
            "bot_f_mirror.stale_signal wallet=%s cid=%s age_ms=%s",
            sig["wallet"][:10], sig["condition_id"][:16], age_ms,
        )
        return False

    # T2-E proximity-to-resolution filter: read market end_date from the
    # recorder's markets table and skip if within MIN_TTR_FOR_ENTRY_SECONDS.
    ttr_ok, ttr_reason = _entry_ttr_ok(sig["condition_id"])
    if not ttr_ok:
        log.info(
            "bot_f_mirror.skipped_by_ttr wallet=%s cid=%s reason=%s",
            sig["wallet"][:10], sig["condition_id"][:16], ttr_reason,
        )
        return False

    try:
        whale_price = Decimal(str(sig["price"]))
        if whale_price <= 0 or whale_price >= 1:
            return False
        live_ask = _current_ask_from_recorder(sig["token_id"], sig["condition_id"])
        price = whale_price
        if side_norm == "BUY" and live_ask is not None:
            if live_ask > whale_price + MAX_COPY_SLIPPAGE:
                log.info(
                    "bot_f_mirror.slippage_reject wallet=%s cid=%s whale_px=%s ask=%s max_slip=%s",
                    sig["wallet"][:10], sig["condition_id"][:16],
                    whale_price, live_ask, MAX_COPY_SLIPPAGE,
                )
                return False
            price = live_ask
        shares = (trade_size_usd / price).quantize(Decimal("0.01"))
        if shares <= 0:
            return False
        # ClobWrapper.place_limit takes positional scalars, not OrderArgs.
        # Only BUY/SELL are valid from the data-api; anything else is a
        # schema change — warn and skip rather than silently default.
        if side_norm == "BUY":
            side = Side.BUY
        elif side_norm == "SELL":
            side = Side.SELL
        else:
            log.warning("bot_f_mirror.bad_side %s", side_norm)
            return False
        resp = clob.place_limit(
            token_id=sig["token_id"],
            price=price,
            size=shares,
            side=side,
            order_type=OrderType.GTC,
        )
        order_id = getattr(resp, "order_id", "") or ""
        if not order_id or order_id.startswith("SKIPPED"):
            log.info(
                "bot_f_mirror.skipped wallet=%s cid=%s status=%s",
                sig["wallet"][:10], sig["condition_id"][:16],
                getattr(resp, "status", "?"),
            )
            return False
        from core.db import Order, get_session_factory
        sf = get_session_factory()
        with sf() as s:
            s.add(Order(
                order_id=order_id,
                bot_id=BOT_ID,
                condition_id=sig["condition_id"],
                token_id=sig["token_id"],
                side=side_norm,
                price=price,
                size=shares,
                status=getattr(resp, "status", "PAPER_OPEN"),
                placed_at=datetime.now(UTC),
            ))
            s.commit()
        # Synthetic paper fill at the recorder ask. `price == live_ask` is
        # already guaranteed by the BUY-branch assignment above (after the
        # slippage check), so the previous `live_ask <= price` guard was
        # trivially true; dropped for clarity.
        if (
            portfolio is not None
            and side_norm == "BUY"
            and order_id.startswith("paper-")
            and live_ask is not None
        ):
            try:
                portfolio.on_fill(
                    bot_id=BOT_ID,
                    trade_id=f"paper-fill-{order_id}",
                    order_id=order_id,
                    condition_id=sig["condition_id"],
                    token_id=sig["token_id"],
                    side="BUY",
                    price=price,
                    size=shares,
                    fee_usd=Decimal("0"),
                    filled_at=datetime.now(UTC),
                )
                with sf() as s:
                    db_o = s.get(Order, order_id)
                    if db_o is not None:
                        db_o.status = "FILLED"
                        s.commit()
            except Exception as exc:
                log.warning(
                    "bot_f_mirror.paper_fill_failed order=%s cid=%s err=%s",
                    order_id, sig["condition_id"][:16], exc,
                )
        recent.add(dedup_key)
        log.info(
            "bot_f_mirror.placed wallet=%s cid=%s side=%s shares=%s price=%s order_id=%s",
            sig["wallet"][:10], sig["condition_id"][:16], side_norm, shares, price,
            order_id,
        )
        return True
    except Exception as exc:
        log.warning(
            "bot_f_mirror.place_failed wallet=%s cid=%s err=%s",
            sig["wallet"][:10], sig["condition_id"][:16], exc,
        )
        return False


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _assert_paper_mode()
    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    log.info(
        "bot_f_mirror.daemon.start allowlist=%d poll=%ds trade_usd=%s",
        len(SHARPS_ALLOWLIST), POLL_INTERVAL_SECONDS, TRADE_SIZE_USD,
    )

    # Layer 2 safety: hard-code paper_override=True. No code path flips it.
    clob = ClobWrapper(keystore=None, paper_override=True)
    if not clob.paper_override:
        log.error("bot_f_mirror.abort clob_not_paper_at_startup")
        return 3

    portfolio = Portfolio()
    bot_f_db = Path(os.environ.get("BOT_F_DB_PATH", "./data/bot_f.db"))
    last_poll = datetime.now(UTC) - timedelta(minutes=LOOKBACK_MINUTES)
    from core.db import get_session_factory
    sf = get_session_factory()

    while _running:
        try:
            now = datetime.now(UTC)
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            recent = _recent_mirrors(sf, day_start)
            signals = _read_new_signals(bot_f_db, last_poll)
            placed = 0
            for sig in signals:
                if _mirror_signal(sig, clob, portfolio, TRADE_SIZE_USD, recent):
                    placed += 1
            if signals:
                log.info(
                    "bot_f_mirror.tick signals=%d placed=%d",
                    len(signals), placed,
                )
            # T2-E: trailing-stop + max-drawdown exit scan every tick.
            try:
                exits = _update_trailing_stops(portfolio)
                if exits:
                    log.info("bot_f_mirror.trailing_stops exits=%d", exits)
            except Exception as exc:
                log.warning("bot_f_mirror.trailing_stops_failed err=%s", exc)
            last_poll = now
        except Exception as e:
            log.error("bot_f_mirror.tick_failed err=%s", e)
        time.sleep(POLL_INTERVAL_SECONDS)

    return 0


if __name__ == "__main__":
    sys.exit(main())
