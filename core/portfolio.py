"""Position and PnL tracking.

Reconciles fills into positions, computes realised and mark-to-market PnL,
exposes per-bot bankroll and drawdown, and writes HMRC-ready rows for every
trade (USD→GBP spot at fill time).

Spot-rate lookup: ECB daily rate via frankfurter.app, cached for the trading
day.  Frankfurter handles weekend/holiday rollover automatically (returns the
most recent business-day rate).  On failure, walks back up to 7 days and
finally falls back to the last-known-good rate with a logged warning.

History: BoE's `bankofengland.co.uk/boeapps/iadb/...` endpoint was used until
the BoE began returning 403 to programmatic clients (2026-04 era) — switched
to frankfurter, which is free, no-key, and ECB-sourced.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, TYPE_CHECKING

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db import Event, Market, Order, PnlSnapshot, Position, Trade, get_session_factory

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


# ECB USD→GBP rate via frankfurter.app: per-date cache.
_FX_CACHE: dict[date, Decimal] = {}
_FX_LAST_GOOD: Decimal | None = None
_FRANKFURTER_URL = "https://api.frankfurter.dev/v1"


def _fetch_usd_gbp(on_date: date) -> Decimal:
    """Frankfurter (ECB-sourced) USD→GBP spot for `on_date`.

    Returns GBP per 1 USD.  Frankfurter rolls weekends/holidays back to
    the most recent business day automatically — the response's `date`
    field tells us which actual day was used.  Raises on transport error
    or unparseable payload; caller decides whether to fall back.
    """
    r = httpx.get(
        f"{_FRANKFURTER_URL}/{on_date.isoformat()}",
        params={"from": "USD", "to": "GBP"},
        timeout=10.0,
        headers={"User-Agent": "longshot-research/1.0"},
        follow_redirects=True,
    )
    r.raise_for_status()
    data = r.json()
    rate = data.get("rates", {}).get("GBP")
    if rate is None:
        raise ValueError(f"frankfurter response missing rates.GBP: {data!r:.200}")
    return Decimal(str(rate)).quantize(Decimal("0.00000001"))


def _gamma_resolved_outcome(
    http_client: httpx.Client,
    gamma_url: str,
    condition_id: str,
) -> tuple[tuple[str, str] | None, str | None, str | None]:
    """Query Gamma for a resolved market by condition_id.

    Returns ``((yes_price, no_price), yes_token, no_token)`` if Gamma reports
    the market as closed with parseable outcome prices, else
    ``(None, None, None)``. Network failure is logged and treated as "not
    yet resolvable" — caller retries on the next loop tick.

    Gamma's ``/markets`` endpoint takes ``condition_ids=`` (0x-prefixed hex)
    *or* ``id=`` (numeric Gamma market id). Bot D stores the latter in
    ``Position.condition_id``; Bot A/B/etc. store the former. We switch on
    the ``0x`` prefix and match the response by whichever field we queried.
    """
    import json
    if not condition_id:
        # Empty condition_id is an upstream-ingest bug; don't burn a Gamma
        # call (which would 422). Caller's orphan path handles the rest.
        return None, None, None
    is_hex = condition_id.startswith("0x")
    param_name = "condition_ids" if is_hex else "id"
    try:
        r = http_client.get(
            gamma_url,
            params={param_name: condition_id, "closed": "true", "limit": 5},
        )
        r.raise_for_status()
        data = r.json() or []
    except Exception as e:
        log.warning(
            "portfolio.paper_resolve.gamma_fail cid=%s err=%s",
            condition_id, e,
        )
        return None, None, None
    if not isinstance(data, list) or not data:
        return None, None, None
    # Match on whichever field we queried; Gamma may return neighbours.
    key = "conditionId" if is_hex else "id"
    match = next(
        (m for m in data if str(m.get(key) or "") == condition_id),
        None,
    )
    if match is None:
        return None, None, None
    if not match.get("closed"):
        return None, None, None
    raw_prices = match.get("outcomePrices")
    raw_tokens = match.get("clobTokenIds")
    try:
        prices = raw_prices if isinstance(raw_prices, list) else json.loads(raw_prices)
        tokens = raw_tokens if isinstance(raw_tokens, list) else json.loads(raw_tokens)
    except Exception:
        return None, None, None
    if not prices or len(prices) < 2:
        return None, None, None
    yes_token = str(tokens[0]) if tokens and len(tokens) >= 1 else None
    no_token = str(tokens[1]) if tokens and len(tokens) >= 2 else None
    return (str(prices[0]), str(prices[1])), yes_token, no_token


def get_usd_to_gbp_rate(on_date: date | None = None) -> Decimal:
    """Return GBP per 1 USD for `on_date` (defaults to today UTC).

    Falls back to:
      1. Cache
      2. Previous-day rate (most recent up to 7 days)
      3. Last-known-good rate with a logged warning
      4. 0.80 as floor
    """
    global _FX_LAST_GOOD
    d = on_date or datetime.now(UTC).date()
    if d in _FX_CACHE:
        return _FX_CACHE[d]
    try:
        rate = _fetch_usd_gbp(d)
        _FX_CACHE[d] = rate
        _FX_LAST_GOOD = rate
        return rate
    except Exception as e:
        for back in range(1, 8):
            try:
                prev = d - timedelta(days=back)
                rate = _fetch_usd_gbp(prev)
                _FX_CACHE[d] = rate
                _FX_LAST_GOOD = rate
                return rate
            except Exception:
                continue
        log.warning("portfolio.fx.fallback", extra={"error": str(e)})
        if _FX_LAST_GOOD is not None:
            return _FX_LAST_GOOD
        # Audit C11: before the hardcoded 0.80 floor, try the most recent
        # persisted rate from the Trade table (usd_gbp_rate column).
        # 0.80 was ~6% too high vs the ~0.75-0.76 market rate — enough to
        # inflate Kelly sizing materially on a prolonged FX outage.
        try:
            from sqlalchemy import select

            from core.db import Trade, get_session_factory
            with get_session_factory()() as s:
                row = s.scalars(
                    select(Trade).order_by(Trade.filled_at.desc()).limit(1)
                ).first()
                if row is not None and row.usd_gbp_rate is not None:
                    log.warning(
                        "portfolio.fx.db_fallback",
                        extra={"rate": str(row.usd_gbp_rate), "source": "trades"},
                    )
                    _FX_LAST_GOOD = row.usd_gbp_rate
                    return row.usd_gbp_rate
        except Exception as e2:
            log.warning("portfolio.fx.db_fallback_fail", extra={"error": str(e2)})
        log.warning("portfolio.fx.hardcoded_floor", extra={"rate": "0.80"})
        return Decimal("0.80")


class Portfolio:
    """Per-bot book-keeping.  Keep all state in DB; this class is stateless."""

    def __init__(self, session_factory=None):
        self._sessions = session_factory or get_session_factory()

    # Phase 3 audit 2026-04-17: orphan-SELL detection as a first-class metric.
    def detect_orphan_sells(
        self,
        bot_id: str,
        max_age_hours: int = 24,
    ) -> list[dict]:
        """Return SELL trades that have no matching BUY (FIFO-exhausted).

        A persistent orphan-SELL after 24h typically means
        `reconcile_live_fills` missed a BUY (data-integrity signal) or a
        CTF split-then-sell occurred on a token we never bought. Emit an
        Event row per orphan so the watchdog + dashboard can surface it.
        """
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        orphans: list[dict] = []
        with self._sessions() as s:
            trades = list(s.scalars(
                select(Trade).where(Trade.bot_id == bot_id)
                             .order_by(Trade.filled_at, Trade.trade_id)
            ))
            # Replay FIFO to find unmatched SELL remainders, restricting to
            # trades older than the cutoff (ignore fresh SELLs awaiting recon).
            open_lots: dict[str, list[list[Decimal]]] = {}
            for t in trades:
                # Same normalization as get_realised_pnl (Session 17s 2026-04-20)
                side = t.side
                if side and (side.startswith("BUY_") or side.startswith("BUY-")):
                    side = "BUY"
                elif side and (side.startswith("SELL_") or side.startswith("SELL-")):
                    side = "SELL"
                if side == "BUY":
                    open_lots.setdefault(t.token_id, []).append(
                        [Decimal(t.size), Decimal(t.price)]
                    )
                    continue
                if side != "SELL":
                    continue
                remaining = Decimal(t.size)
                lots = open_lots.get(t.token_id, [])
                while remaining > 0 and lots:
                    lot = lots[0]
                    match = min(lot[0], remaining)
                    lot[0] -= match
                    remaining -= match
                    if lot[0] <= 0:
                        lots.pop(0)
                # SQLite returns naive datetimes; normalize to UTC-aware.
                filled_at_utc = t.filled_at if t.filled_at.tzinfo else t.filled_at.replace(tzinfo=UTC)
                if remaining > 0 and filled_at_utc <= cutoff:
                    orphans.append({
                        "trade_id": t.trade_id,
                        "token_id": t.token_id,
                        "condition_id": t.condition_id,
                        "unmatched_size": str(remaining),
                        "price": str(t.price),
                        "filled_at": filled_at_utc.isoformat(),
                        "age_hours": (datetime.now(UTC) - filled_at_utc).total_seconds() / 3600.0,
                    })
        return orphans

    def emit_orphan_sell_alert(self, bot_id: str, max_age_hours: int = 24) -> int:
        """Detect + write an Event row per orphan older than cutoff.

        Codex fleet review A-18 (2026-04-22): previously "idempotent-ish" —
        each call re-emitted an Event per orphan, producing the known
        8-alerts-per-scan noise. Now deduplicates by a content hash of
        `(bot_id, trade_id, side, filled_at)` stored in the Event payload:
        if an alert with the same hash already exists for this orphan,
        skip it. Returns the count of NEW emissions.
        """
        orphans = self.detect_orphan_sells(bot_id, max_age_hours=max_age_hours)
        if not orphans:
            return 0
        import hashlib
        new_count = 0
        with self._sessions() as s:
            # Pull existing orphan-alert hashes once so we can filter
            # without opening a session per orphan.
            existing_hashes: set[str] = set()
            for e in s.scalars(
                select(Event).where(
                    Event.bot_id == bot_id,
                    Event.event_type == "portfolio.orphan_sell_alert",
                )
            ):
                if e.payload and isinstance(e.payload, dict):
                    h = e.payload.get("dedup_hash")
                    if h:
                        existing_hashes.add(str(h))
            for o in orphans:
                key = "|".join([
                    bot_id,
                    str(o.get("trade_id", "")),
                    str(o.get("side", "")),
                    str(o.get("filled_at", "")),
                ])
                dedup = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
                if dedup in existing_hashes:
                    continue
                payload = dict(o)
                payload["dedup_hash"] = dedup
                s.add(Event(
                    bot_id=bot_id,
                    event_type="portfolio.orphan_sell_alert",
                    severity="warn",
                    message=(
                        f"orphan SELL age={o['age_hours']:.1f}h "
                        f"size={o['unmatched_size']} "
                        f"token={o['token_id']}"
                    ),
                    payload=payload,
                ))
                existing_hashes.add(dedup)
                new_count += 1
            if new_count:
                s.commit()
        if new_count:
            log.warning(
                "portfolio.orphan_sell_alert bot=%s new=%d total_orphans=%d",
                bot_id, new_count, len(orphans),
            )
        return new_count

    # --- Event handlers ---
    def on_fill(
        self,
        bot_id: str,
        trade_id: str,
        order_id: str | None,
        condition_id: str,
        token_id: str,
        side: str,
        price: Decimal,
        size: Decimal,
        fee_usd: Decimal,
        filled_at: datetime,
    ) -> None:
        with self._sessions() as s:
            self._do_on_fill(
                s, bot_id, trade_id, order_id, condition_id, token_id,
                side, price, size, fee_usd, filled_at
            )
            s.commit()

    def _do_on_fill(
        self,
        s: Session,
        bot_id: str,
        trade_id: str,
        order_id: str | None,
        condition_id: str,
        token_id: str,
        side: str,
        price: Decimal,
        size: Decimal,
        fee_usd: Decimal,
        filled_at: datetime,
    ) -> None:
        existing = s.get(Trade, trade_id)
        if existing is not None:
            # Idempotency — re-delivered WSS event.
            return

        rate = get_usd_to_gbp_rate(filled_at.date())
        notional_usd = price * size
        gbp_notional = (notional_usd * rate).quantize(Decimal("0.00000001"))

        s.add(
            Trade(
                trade_id=trade_id,
                bot_id=bot_id,
                order_id=order_id,
                condition_id=condition_id,
                token_id=token_id,
                side=side,
                price=price,
                size=size,
                fee_usd=fee_usd,
                filled_at=filled_at,
                usd_gbp_rate=rate,
                gbp_notional=gbp_notional,
            )
        )
        if order_id:
            order = s.get(Order, order_id)
            if order is not None:
                try:
                    remaining = Decimal(str(order.size or 0)) - Decimal(str(size or 0))
                except Exception:
                    remaining = Decimal("0")
                order.status = "FILLED" if remaining <= Decimal("0") else "PARTIAL"
                order.last_updated = filled_at
        self._apply_to_position(s, bot_id, condition_id, token_id, side, price, size)

    def _apply_to_position(
        self,
        s: Session,
        bot_id: str,
        condition_id: str,
        token_id: str,
        side: str,
        price: Decimal,
        size: Decimal,
    ) -> None:
        """Update the open position for (bot, token_id).

        BUY increases size at weighted-avg cost; SELL decreases at cost-basis.
        If SELL exceeds current size, the excess opens a short — which shouldn't
        happen on Polymarket's outcome tokens (tokens are non-shortable), so we
        log a `warn` event and cap at zero.
        """
        pos_stmt = select(Position).where(
            Position.bot_id == bot_id,
            Position.token_id == token_id,
            Position.status == "OPEN",
        )
        pos = s.scalars(pos_stmt).first()

        # 2026-04-17: normalise side strings. Bot E records orders with
        # `BUY_YES` / `BUY_NO` (signal-side convention), while Bot A/B/C/D
        # use plain `BUY` / `SELL` (exchange-side convention). Without this
        # mapping, Bot E's paper fills silently no-op here — Trade rows are
        # created but Position rows aren't, breaking sizer caps, loss halts,
        # exposure tracking, and P&L snapshotting. Position.side (YES vs NO)
        # is still resolved below via the market's token_id mapping.
        base_side = side
        if side and (side.startswith("BUY_") or side.startswith("BUY-")):
            base_side = "BUY"
        elif side and (side.startswith("SELL_") or side.startswith("SELL-")):
            base_side = "SELL"

        if base_side == "BUY":
            if pos is None:
                # Derive YES/NO from token_id by looking the market up.
                # Defaults to "YES" only when no market row resolves the mapping
                # (paper fixtures that skip the Market row).
                market = s.scalars(
                    select(Market).where(Market.condition_id == condition_id)
                ).first()
                if market is not None and market.no_token_id == token_id:
                    position_side = "NO"
                elif market is not None and market.yes_token_id == token_id:
                    position_side = "YES"
                else:
                    position_side = "YES"
                pos = Position(
                    bot_id=bot_id,
                    condition_id=condition_id,
                    token_id=token_id,
                    side=position_side,
                    size=size,
                    avg_price=price,
                    cost_basis_usd=price * size,
                    status="OPEN",
                )
                s.add(pos)
            else:
                new_size = pos.size + size
                new_cost = pos.cost_basis_usd + price * size
                pos.size = new_size
                pos.avg_price = (new_cost / new_size).quantize(Decimal("0.00000001"))
                pos.cost_basis_usd = new_cost
        elif base_side == "SELL":
            if pos is None or pos.size <= 0:
                s.add(
                    Event(
                        bot_id=bot_id,
                        event_type="portfolio.sell_without_position",
                        severity="warn",
                        message=f"SELL on {token_id} but no open position",
                        payload={"size": str(size), "price": str(price)},
                    )
                )
                return
            sell_qty = min(size, pos.size)
            pos.size -= sell_qty
            if pos.size <= 0:
                pos.cost_basis_usd = Decimal("0")
                pos.status = "CLOSED"
                pos.closed_at = datetime.now(UTC)
            else:
                # Recompute cost basis using FIFO
                trades = list(s.scalars(
                    select(Trade)
                    .where(Trade.bot_id == bot_id, Trade.token_id == token_id)
                ))
                trades.sort(key=lambda t: (t.filled_at, t.trade_id))
                open_lots: list[list[Decimal]] = []
                for t in trades:
                    tside = t.side
                    if tside and (tside.startswith("BUY_") or tside.startswith("BUY-")):
                        tside = "BUY"
                    elif tside and (tside.startswith("SELL_") or tside.startswith("SELL-")):
                        tside = "SELL"

                    if tside == "BUY":
                        open_lots.append([Decimal(t.size), Decimal(t.price)])
                    elif tside == "SELL":
                        rem = Decimal(t.size)
                        while rem > 0 and open_lots:
                            lot = open_lots[0]
                            match_sz = min(lot[0], rem)
                            lot[0] -= match_sz
                            rem -= match_sz
                            if lot[0] <= 0:
                                open_lots.pop(0)

                fifo_cost = sum(lot[0] * lot[1] for lot in open_lots)
                pos.cost_basis_usd = fifo_cost
                pos.avg_price = (fifo_cost / pos.size).quantize(Decimal("0.00000001"))

    def on_redeem(self, position_id: int, usdc_received: Decimal) -> None:
        with self._sessions() as s:
            pos = s.get(Position, position_id)
            if pos is None:
                return
            pos.status = "REDEEMED"
            pos.closed_at = datetime.now(UTC)
            s.add(
                Event(
                    bot_id=pos.bot_id,
                    event_type="portfolio.redeem",
                    severity="info",
                    message=f"position {position_id} redeemed",
                    payload={
                        "usdc_received": str(usdc_received),
                        "cost_basis": str(pos.cost_basis_usd),
                        "realised_usd": str(usdc_received - pos.cost_basis_usd),
                    },
                )
            )
            s.commit()

    # --- Queries ---
    def get_realised_pnl(self, bot_id: str, since: datetime | None = None) -> Decimal:
        """Realised PnL from CLOSED positions only.

        Audit fix: for each SELL trade, match against the cost basis of the
        same token.

        Semantics (audit 2026-04-17, GLM-5.1/Codex Q25 P1):
          realised = sum_closed((sell_price - entry_price_of_matched_lot) * matched_size) - fees

        This uses **lot-based FIFO matching** rather than lifetime-average
        cost basis. Lifetime-average distorted re-entries: after a full
        round-trip (buy, sell, buy again, sell again) the second round's
        realised P&L was calculated against the blended BUY cost of BOTH
        rounds, not just the second. Lot-based FIFO treats each BUY as a
        distinct inventory parcel and matches SELLs against the oldest
        open parcel first.
        """
        with self._sessions() as s:
            stmt = select(Trade).where(Trade.bot_id == bot_id)
            if since is not None:
                stmt = stmt.where(Trade.filled_at >= since)
            trades = list(s.scalars(stmt))
            # Process trades in time order so FIFO matching is well-defined.
            trades.sort(key=lambda t: (t.filled_at, t.trade_id))

            fees_by_token: dict[str, Decimal] = {}
            # Per-token FIFO lot queue: list of [remaining_size, entry_price].
            open_lots: dict[str, list[list[Decimal]]] = {}
            realised = Decimal("0")

            for t in trades:
                fees_by_token[t.token_id] = (
                    fees_by_token.get(t.token_id, Decimal("0")) + t.fee_usd
                )
                # Session 17s 2026-04-20: normalize side strings the same way
                # _apply_to_position does (line ~286). Bot E records BUYs as
                # "BUY_YES" / "BUY_NO" (signal-side convention); without this
                # map, every Bot E SELL becomes an orphan SELL and bot_e's
                # realised P&L reports $0 despite real closed positions.
                side = t.side
                if side and (side.startswith("BUY_") or side.startswith("BUY-")):
                    side = "BUY"
                elif side and (side.startswith("SELL_") or side.startswith("SELL-")):
                    side = "SELL"
                if side == "BUY":
                    open_lots.setdefault(t.token_id, []).append(
                        [Decimal(t.size), Decimal(t.price)]
                    )
                    continue
                if side != "SELL":
                    continue
                # Match this SELL against the oldest open lot(s) for the token.
                remaining = Decimal(t.size)
                sell_price = Decimal(t.price)
                lots = open_lots.get(t.token_id, [])
                while remaining > 0 and lots:
                    lot = lots[0]
                    lot_size, lot_price = lot
                    match_size = min(lot_size, remaining)
                    realised += (sell_price - lot_price) * match_size
                    lot[0] = lot_size - match_size
                    remaining -= match_size
                    if lot[0] <= 0:
                        lots.pop(0)
                if remaining > 0:
                    # Orphan SELL (Patch A, 2026-04-16 preserved): the SELL
                    # exceeds our matched lots. Conservative: skip the
                    # un-matched remainder rather than treating as pure
                    # profit. Happens on CTF split-then-sell or missed
                    # reconciliation of an earlier BUY.
                    log.warning(
                        "portfolio.realised.orphan_sell",
                        extra={
                            "bot_id": bot_id,
                            "token_id": t.token_id,
                            "trade_id": t.trade_id,
                            "sell_price": str(t.price),
                            "sell_size": str(t.size),
                            "unmatched_size": str(remaining),
                        },
                    )
            # Subtract total fees (all sides).
            for fees in fees_by_token.values():
                realised -= fees
            # Add proceeds from redeems (resolved-market payouts already
            # computed as net P&L in the redeem event).
            for e in s.scalars(
                select(Event).where(
                    Event.bot_id == bot_id, Event.event_type == "portfolio.redeem"
                )
            ):
                if e.payload:
                    realised += Decimal(str(e.payload.get("realised_usd", "0")))
            return realised

    def get_open_exposure(self, bot_id: str) -> Decimal:
        """Cost basis of open positions only. Use `get_total_exposure` for the
        limit check that should also account for pending open orders."""
        with self._sessions() as s:
            positions = list(
                s.scalars(
                    select(Position).where(Position.bot_id == bot_id, Position.status == "OPEN")
                )
            )
            return sum((p.cost_basis_usd for p in positions), Decimal("0"))

    def get_open_orders_notional(self, bot_id: str) -> Decimal:
        """Sum notional (`price * size`) of BUY orders still outstanding.

        Caps should count these because a resting BUY can fill at any moment
        and become a position — if we only measure settled positions the cap
        lets us silently accumulate twice as much risk as intended.

        Status set includes "live" — Polymarket CLOB sets resting orders to
        that status. Missing it caused Bot A to re-enter markets every tick
        (fixed 2026-04-15) and Bot D to accumulate $834 exposure against
        a $500 bankroll cap (fixed 2026-04-16).
        """
        with self._sessions() as s:
            orders = list(
                s.scalars(
                    select(Order).where(
                        Order.bot_id == bot_id,
                        Order.side == "BUY",
                        Order.status.in_(("OPEN", "PARTIAL", "PAPER_OPEN", "live", "MATCHED")),
                    )
                )
            )
            total = Decimal("0")
            for o in orders:
                if o.price is None or o.size is None:
                    continue
                total += o.price * o.size
            return total

    def get_total_exposure(self, bot_id: str) -> Decimal:
        """Position cost basis + open-BUY notional. Canonical cap input."""
        return self.get_open_exposure(bot_id) + self.get_open_orders_notional(bot_id)

    def get_unrealised_pnl(
        self, bot_id: str, mark_prices: dict[str, Decimal] | None = None
    ) -> Decimal:
        """Mark-to-market at best-bid (conservative) unless mark_prices supplied."""
        with self._sessions() as s:
            positions = list(
                s.scalars(
                    select(Position).where(Position.bot_id == bot_id, Position.status == "OPEN")
                )
            )
            unrealised = Decimal("0")
            for p in positions:
                mark = (mark_prices or {}).get(p.token_id)
                if mark is None:
                    continue  # Can't MtM without a price; skip.
                unrealised += (mark - p.avg_price) * p.size
            return unrealised

    def get_bot_bankroll(
        self, bot_id: str, initial_usd: Decimal, mark_prices: dict[str, Decimal] | None = None
    ) -> Decimal:
        return (
            initial_usd
            + self.get_realised_pnl(bot_id)
            + self.get_unrealised_pnl(bot_id, mark_prices)
        )

    def get_drawdown_pct(
        self,
        bot_id: str,
        initial_usd: Decimal,
        mark_prices: dict[str, Decimal] | None = None,
        *,
        realised_pnl: Decimal | None = None,
        unrealised_pnl: Decimal | None = None,
    ) -> Decimal:
        """Peak-to-trough drawdown over recorded PnL snapshots + current live.

        `mark_prices` injects current mid prices per token_id so that live
        unrealised PnL is counted. Without marks, open-position losses are
        invisible — drawdown becomes realised-only and kill-switches don't
        fire until a trade settles.

        `realised_pnl` / `unrealised_pnl` are optional precomputed values
        — callers like `snapshot_daily` that already computed these can
        pass them in to avoid replaying the full FIFO trade history twice
        per snapshot (2026-04-22 GLM-5.1 review A10). Bots with thousands
        of trades saw noticeable per-snapshot CPU from the redundant call.
        """
        with self._sessions() as s:
            snapshots = list(
                s.scalars(
                    select(PnlSnapshot)
                    .where(PnlSnapshot.bot_id == bot_id)
                    .order_by(PnlSnapshot.snapshot_date)
                )
            )
            series: list[Decimal] = [initial_usd]
            running = initial_usd
            for snap in snapshots:
                running = initial_usd + (snap.realised_usd or Decimal("0")) + (
                    snap.unrealised_usd or Decimal("0")
                )
                series.append(running)
            # Include live state with marks so open-position MtM drops are
            # visible to the drawdown check. Use precomputed values when
            # provided (snapshot_daily passes them to avoid double-replay).
            _realised = (
                realised_pnl
                if realised_pnl is not None
                else self.get_realised_pnl(bot_id)
            )
            _unrealised = (
                unrealised_pnl
                if unrealised_pnl is not None
                else self.get_unrealised_pnl(bot_id, mark_prices)
            )
            live = initial_usd + _realised + _unrealised
            series.append(live)

            peak = series[0]
            max_dd = Decimal("0")
            for v in series:
                peak = max(peak, v)
                if peak > 0:
                    dd = (peak - v) / peak * Decimal("100")
                    if dd > max_dd:
                        max_dd = dd
            return max_dd.quantize(Decimal("0.0001"))

    def reconcile_live_fills(
        self,
        clob,
        bot_id: str,
        cursor_key: str | None = None,
        require_known_order: bool = False,
    ) -> int:
        """Poll the exchange for user trades and push each into `on_fill`.

        Called from the daemon loop when not in paper mode. Uses an Event row
        named `portfolio.fill_cursor.<bot>` to track the last processed trade
        timestamp (so restarts don't re-import the entire history). Returns
        the count of new fills reconciled this call.
        """
        key = cursor_key or f"portfolio.fill_cursor.{bot_id}"
        with self._sessions() as s:
            cursor_evt = s.scalars(
                select(Event)
                .where(Event.event_type == key)
                .order_by(Event.created_at.desc())
            ).first()
            since_ts = 0.0
            if cursor_evt and cursor_evt.payload:
                try:
                    since_ts = float(cursor_evt.payload.get("since_ts", 0))
                except (TypeError, ValueError):
                    since_ts = 0.0

        try:
            trades = clob.get_user_trades(since=since_ts) or []
        except Exception as e:
            log.warning("portfolio.reconcile.fetch_fail", extra={"error": str(e), "bot_id": bot_id})
            return 0

        count = 0
        max_ts = since_ts
        with self._sessions() as s:
            with s.begin_nested():
                for t in trades:
                    max_ts = max(max_ts, float(t.filled_at))
                    order = s.get(Order, t.order_id) if t.order_id else None
                    if s.get(Trade, t.trade_id) is not None:
                        continue
                    if require_known_order and order is None:
                        continue
                    if order is not None and order.bot_id != bot_id:
                        continue  # trade belongs to the other bot
                    # Prefer order.condition_id; fall back to the trade's market_id
                    # (CLOB's "market" field, always present in the /trades response).
                    condition_id = (
                        (order.condition_id if order is not None else None)
                        or getattr(t, "market_id", None)
                        or ""
                    )
                    self._do_on_fill(
                        s=s,
                        bot_id=bot_id,
                        trade_id=t.trade_id,
                        order_id=t.order_id,
                        condition_id=condition_id,
                        token_id=t.token_id,
                        side=t.side.value if hasattr(t.side, "value") else str(t.side),
                        price=t.price,
                        size=t.size,
                        fee_usd=t.fee_usd,
                        filled_at=datetime.fromtimestamp(t.filled_at, tz=UTC),
                    )
                    count += 1

                if max_ts > since_ts:
                    s.add(
                        Event(
                            bot_id=bot_id,
                            event_type=key,
                            severity="info",
                            message=f"fill cursor advanced to {max_ts}",
                            payload={"since_ts": max_ts, "fills_reconciled": count},
                        )
                    )
            s.commit()
        return count

    def simulate_paper_fills(self, bot_id: str) -> int:
        """Walk open paper orders and synthesise fills against the latest book.

        A BUY fills when best_ask ≤ limit_price; a SELL fills when best_bid
        ≥ limit_price. Without this, paper mode accumulates orders forever
        and never generates fills, so the "paper phase" tests execution but
        not accounting.

        Returns count of orders that became fills.
        """
        from core.db import Book

        filled = 0
        with self._sessions() as s:
            open_orders = list(
                s.scalars(
                    select(Order).where(
                        Order.bot_id == bot_id,
                        Order.status.in_(("OPEN", "PARTIAL", "PAPER_OPEN")),
                    )
                )
            )
        for o in open_orders:
            if not o.order_id.startswith("paper-"):
                continue
            if o.price is None or o.size is None:
                continue
            with self._sessions() as s:
                book = s.scalars(
                    select(Book)
                    .where(Book.token_id == o.token_id)
                    .order_by(Book.snapshot_at.desc())
                ).first()
            if book is None:
                # Audit fix: for paper orders on markets we don't snapshot
                # (e.g. Bot C/D trading outside the Bot A/B book-watch list),
                # fall back to filling at limit price if the order is older
                # than 60 seconds. In real CLOB practice, a GTC limit at mid
                # that sits on the book for a minute typically fills.
                #
                # U-13 (audit 2026-04-18) + Codex fleet review A-12
                # (2026-04-22): synth fills with no book verification are
                # a real source of calibration-data invalidity. Default
                # flipped to "false" per Codex's recommendation because
                # Bot E/G microstructure experiments assume honest
                # fill-realism. Opt-in via PAPER_NO_BOOK_SYNTH_FILLS=true
                # only if you understand the calibration tradeoff (Bot A
                # archive-era legacy — not needed for active bots).
                #
                # Every synth fill is also:
                #   1. tagged with "synth-" trade_id prefix so analytics
                #      can filter it out from honest calibration;
                #   2. surfaced via a portfolio.synth_paper_fill Event so
                #      the operator can find them on the dashboard.
                import os as _os
                allow_synth = _os.environ.get(
                    "PAPER_NO_BOOK_SYNTH_FILLS", "false"
                ).lower() in ("true", "1", "yes", "on")
                if not allow_synth:
                    continue
                if o.placed_at is None:
                    continue
                placed = o.placed_at
                if placed.tzinfo is None:
                    placed = placed.replace(tzinfo=UTC)
                age_s = (datetime.now(UTC) - placed).total_seconds()
                if age_s < 60:
                    continue
                # Synthesise a fill at the order's limit price.
                crosses = True
                best_ask = o.price
                best_bid = o.price
                is_synth = True
            else:
                is_synth = False
                bids = book.bids or []
                asks = book.asks or []
                best_ask = min((Decimal(str(r[0])) for r in asks), default=None)
                best_bid = max((Decimal(str(r[0])) for r in bids), default=None)
                crosses = False
                # 2026-04-17: tolerate both plain (BUY/SELL) and tagged
                # (BUY_YES/BUY_NO) side conventions. Bot E uses the tagged
                # form; Bot A/B/C/D use plain.
                o_base = (
                    "BUY" if o.side and o.side.startswith("BUY")
                    else "SELL" if o.side and o.side.startswith("SELL")
                    else o.side
                )
                if (o_base == "BUY" and best_ask is not None and best_ask <= o.price) or (o_base == "SELL" and best_bid is not None and best_bid >= o.price):
                    crosses = True
            if not crosses:
                continue
            with self._sessions() as s:
                # 2026-04-17: prefer the condition_id already stored on the
                # Order row (Bot E writes it at placement time). Only fall
                # back to the markets-table lookup if absent — this is what
                # broke Bot E paper fills, since its discovered markets
                # aren't persisted to the markets table by BookSnapshotter.
                if o.condition_id:
                    condition_id = o.condition_id
                else:
                    market = s.scalars(
                        select(Market).where(
                            (Market.yes_token_id == o.token_id)
                            | (Market.no_token_id == o.token_id)
                        )
                    ).first()
                    condition_id = market.condition_id if market else ""
            # U-13: synthetic fills (no book available, 60s fallback) get a
            # distinct trade_id prefix so calibration analytics can filter.
            trade_id = (
                f"synth-paper-fill-{o.order_id}" if is_synth
                else f"paper-fill-{o.order_id}"
            )
            self.on_fill(
                bot_id=bot_id,
                trade_id=trade_id,
                order_id=o.order_id,
                condition_id=condition_id,
                token_id=o.token_id,
                side=o.side,
                price=o.price,
                size=o.size,
                fee_usd=Decimal("0"),
                filled_at=datetime.now(UTC),
            )
            with self._sessions() as s:
                db_o = s.get(Order, o.order_id)
                if db_o is not None:
                    db_o.status = "FILLED"
                if is_synth:
                    # Emit an Event row so dashboard + operators can see
                    # the paper-fill dishonesty volume. Critical for Bot E
                    # because its markets aren't book-snapshotted and so
                    # every paper fill ends up here.
                    s.add(Event(
                        bot_id=bot_id,
                        event_type="portfolio.synth_paper_fill",
                        severity="warn",
                        message=(
                            f"synthetic no-book paper fill {trade_id} "
                            f"side={o.side} price={o.price} size={o.size}"
                        ),
                        payload={
                            "trade_id": trade_id,
                            "order_id": o.order_id,
                            "token_id": o.token_id,
                            "side": o.side,
                            "price": str(o.price),
                            "size": str(o.size),
                        },
                    ))
                s.commit()
            filled += 1
        return filled

    def reconcile_paper_resolutions(
        self,
        bot_id: str,
        *,
        gamma_url: str = "https://gamma-api.polymarket.com/markets",
        http_client: httpx.Client | None = None,
        now: datetime | None = None,
    ) -> int:
        """Settle paper-mode OPEN positions whose markets have resolved on Gamma.

        Paper mode never triggers ``on_redeem`` (no on-chain redemption event),
        and ``simulate_paper_fills`` only closes via SELL fills that are never
        issued for resolved markets. Without this pass, paper positions
        accumulate OPEN indefinitely past ``Market.end_date``, inflating
        fleet-cap exposure and hiding realised P&L (see Session 17n Bot E
        manual cleanup; Session 17r-ext Bot D parity surface).

        For each OPEN position:
          * If the cached Market row has an ``end_date`` in the future, skip
            (still open).
          * Otherwise, query Gamma for the condition_id. If ``closed=true``
            and ``outcomePrices`` is present, synthesise a SELL at the
            settlement price (``$1.00`` for the winning token, ``$0.00`` for
            the losing token) via ``on_fill``, which closes the Position via
            the existing SELL path and writes a Trade row for FIFO P&L.

        The synthetic trade_id uses a ``paper-resolve-<position_id>`` prefix
        so downstream analytics can filter settlement fills from honest
        book-matched paper fills (distinct from ``synth-paper-fill-`` and
        ``paper-fill-``).

        Orphan positions (no Market row or Market row without end_date) are
        still queried against Gamma; if Gamma cannot resolve them, a warn
        event is emitted but the position is left OPEN — upstream ingest gap
        is tracked separately in ``open-questions.md``.

        Returns the count of positions settled this call.
        """
        now = now or datetime.now(UTC)

        with self._sessions() as s:
            positions = list(
                s.scalars(
                    select(Position).where(
                        Position.bot_id == bot_id, Position.status == "OPEN"
                    )
                )
            )
            cids = {p.condition_id for p in positions if p.condition_id}
            markets: dict[str, Market] = {}
            if cids:
                markets = {
                    m.condition_id: m
                    for m in s.scalars(
                        select(Market).where(Market.condition_id.in_(cids))
                    )
                }

        if not positions:
            return 0

        owns_client = http_client is None
        if owns_client:
            http_client = httpx.Client(
                timeout=15.0,
                headers={"User-Agent": "polymarket-bot-reconcile/1.0"},
            )

        count = 0
        try:
            for pos in positions:
                market = markets.get(pos.condition_id)
                # Skip positions whose cached market end_date is clearly in
                # the future — no point burning Gamma calls on open markets.
                if market is not None and market.end_date is not None:
                    ed = market.end_date
                    if ed.tzinfo is None:
                        ed = ed.replace(tzinfo=UTC)
                    if ed > now:
                        continue

                outcome, gamma_yes_token, gamma_no_token = _gamma_resolved_outcome(
                    http_client, gamma_url, pos.condition_id
                )
                if outcome is None:
                    if market is None:
                        # Orphan position: no Market row AND Gamma can't
                        # resolve the condition_id. 2026-04-23 extension
                        # of Codex A-18 idempotency: dedup on
                        # (bot, position) per UTC day. Prior code emitted
                        # once per reconcile cycle, producing 72+
                        # events/day from long-standing orphan positions.
                        import hashlib
                        today = datetime.now(UTC).date().isoformat()
                        dedup = hashlib.sha256(
                            f"{bot_id}|{pos.id}|{today}".encode()
                        ).hexdigest()[:16]
                        with self._sessions() as s:
                            already = s.scalars(
                                select(Event).where(
                                    Event.bot_id == bot_id,
                                    Event.event_type == "portfolio.paper_resolve.orphan",
                                )
                            )
                            skip = any(
                                isinstance(e.payload, dict)
                                and e.payload.get("dedup_hash") == dedup
                                for e in already
                            )
                            if not skip:
                                s.add(
                                    Event(
                                        bot_id=bot_id,
                                        event_type="portfolio.paper_resolve.orphan",
                                        severity="warn",
                                        message=(
                                            f"orphan position {pos.id} cid="
                                            f"{pos.condition_id} has no Market row "
                                            "and Gamma returned no resolution"
                                        ),
                                        payload={
                                            "position_id": pos.id,
                                            "condition_id": pos.condition_id,
                                            "token_id": pos.token_id,
                                            "size": str(pos.size),
                                            "dedup_hash": dedup,
                                        },
                                    )
                                )
                                s.commit()
                    continue

                yes_token = (market.yes_token_id if market else None) or gamma_yes_token
                no_token = (market.no_token_id if market else None) or gamma_no_token
                if pos.token_id == yes_token:
                    settle = Decimal(str(outcome[0]))
                elif pos.token_id == no_token:
                    settle = Decimal(str(outcome[1]))
                else:
                    log.warning(
                        "portfolio.paper_resolve.token_mismatch pos_id=%s token=%s cid=%s",
                        pos.id, pos.token_id[:12], pos.condition_id,
                    )
                    continue

                # Clip: Polymarket outcome tokens settle at exactly $1 or $0.
                # Anything else is a Gamma-side weirdness we don't trust.
                if settle < Decimal("0"):
                    settle = Decimal("0")
                if settle > Decimal("1"):
                    settle = Decimal("1")

                self.on_fill(
                    bot_id=bot_id,
                    trade_id=f"paper-resolve-{pos.id}",
                    order_id=None,
                    condition_id=pos.condition_id,
                    token_id=pos.token_id,
                    side="SELL",
                    price=settle,
                    size=pos.size,
                    fee_usd=Decimal("0"),
                    filled_at=now,
                )
                with self._sessions() as s:
                    s.add(
                        Event(
                            bot_id=bot_id,
                            event_type="portfolio.paper_resolve",
                            severity="info",
                            message=f"position {pos.id} settled at {settle}",
                            payload={
                                "position_id": pos.id,
                                "condition_id": pos.condition_id,
                                "token_id": pos.token_id,
                                "settle_price": str(settle),
                                "size": str(pos.size),
                                "cost_basis_usd": str(pos.cost_basis_usd),
                            },
                        )
                    )
                    s.commit()
                count += 1
        finally:
            if owns_client:
                http_client.close()
        return count

    def snapshot_daily(
        self,
        bot_id: str,
        initial_usd: Decimal,
        mark_prices: dict[str, Decimal] | None = None,
        on_date: date | None = None,
    ) -> None:
        """Write today's pnl_snapshots row.  Idempotent per (bot_id, date)."""
        d = on_date or datetime.now(UTC).date()
        with self._sessions() as s:
            existing = s.get(PnlSnapshot, (bot_id, d))
            realised = self.get_realised_pnl(bot_id)
            unrealised = self.get_unrealised_pnl(bot_id, mark_prices)
            exposure = self.get_open_exposure(bot_id)
            dd = self.get_drawdown_pct(
                bot_id, initial_usd, mark_prices,
                realised_pnl=realised, unrealised_pnl=unrealised,
            )
            if existing is None:
                s.add(
                    PnlSnapshot(
                        bot_id=bot_id,
                        snapshot_date=d,
                        realised_usd=realised,
                        unrealised_usd=unrealised,
                        open_exposure_usd=exposure,
                        drawdown_pct=dd,
                    )
                )
            else:
                existing.realised_usd = realised
                existing.unrealised_usd = unrealised
                existing.open_exposure_usd = exposure
                existing.drawdown_pct = dd
            s.commit()

    # ------------------------------------------------------------------ #
    # Live wallet position reconciliation (ADR-???, 2026-05-14)
    # ------------------------------------------------------------------ #
    def reconcile_live_positions_against_wallet(
        self,
        bot_id: str,
        wallet_address: str,
        *,
        data_api: str = "https://data-api.polymarket.com",
        http_client: httpx.Client | None = None,
        dry_run: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Close locally-OPEN positions that the wallet no longer holds.

        Why this exists
        ---------------
        The local ``positions`` table can hold rows in status='OPEN' that the
        wallet has already exited (sold via SELL, redeemed after resolution,
        or transferred). The CLOB on_fill / on_redeem path catches most of
        these, but historical gaps (notably 2026-04 to 2026-05 Bot D live
        probe) leave stale OPEN rows. These rows then inflate Bot D's
        dashboard exposure card, making the live cap usage look tighter than
        it is and overstating real exposure to the operator.

        What it does
        ------------
        For every OPEN position belonging to ``bot_id``:
          * If the wallet's current Data API ``/positions`` response includes
            the token_id, leave the row alone.
          * If the wallet's response does NOT include the token_id, mark the
            row ``status='CLOSED_EXTERNAL_SYNC'`` with ``closed_at=now`` and
            emit an ``Event`` of type ``bot_d.live_position_reconciled``
            (severity=info) capturing old cost/size/token/condition and
            ``reason='not_in_wallet_positions'``.

        What it does NOT do
        -------------------
          * No CLOB orders, cancels, or redemptions.
          * No wallet/key/passphrase access.
          * No synthetic Trade rows (we don't know fill prices).
          * No PnlSnapshot mutation (next snapshot will recompute).
          * On Data API failure: returns ``ok=False`` with the exception
            string and leaves all local rows unchanged.

        Idempotency
        -----------
        Subsequent calls compare only against ``status='OPEN'`` rows, so
        already-reconciled rows (status='CLOSED_EXTERNAL_SYNC') are skipped.
        Re-running on an unchanged wallet state changes zero rows.

        Returns
        -------
        Dict with keys: ``ok`` (bool), ``bot_id``, ``wallet``, ``checked``,
        ``kept_open``, ``closed_count``, ``closed_positions`` (list of dicts
        with id/token_id/condition_id/size/cost_basis_usd/side), and
        ``dry_run`` (bool). On Data API failure ``ok=False`` and a ``reason``
        key is added.
        """
        now = now or datetime.now(UTC)
        owns_client = http_client is None
        if owns_client:
            http_client = httpx.Client(
                timeout=15.0,
                headers={"User-Agent": "polymarket-bot-reconcile/1.0"},
            )

        try:
            # 1. Snapshot local OPEN positions for this bot.
            with self._sessions() as s:
                rows = list(
                    s.scalars(
                        select(Position).where(
                            Position.bot_id == bot_id,
                            Position.status == "OPEN",
                        )
                    )
                )
                local = [
                    {
                        "id": p.id,
                        "token_id": str(p.token_id),
                        "condition_id": str(p.condition_id),
                        "side": str(p.side),
                        "size": p.size,
                        "cost_basis_usd": p.cost_basis_usd,
                    }
                    for p in rows
                ]

            if not local:
                return {
                    "ok": True,
                    "bot_id": bot_id,
                    "wallet": wallet_address,
                    "checked": 0,
                    "kept_open": 0,
                    "closed_count": 0,
                    "closed_positions": [],
                    "dry_run": dry_run,
                }

            # 2. Fetch wallet's current active positions from Data API.
            try:
                resp = http_client.get(
                    f"{data_api}/positions",
                    params={"user": wallet_address, "limit": 200},
                )
                resp.raise_for_status()
                wallet_positions = resp.json() or []
            except Exception as exc:  # network / HTTP / JSON
                return {
                    "ok": False,
                    "bot_id": bot_id,
                    "wallet": wallet_address,
                    "checked": len(local),
                    "kept_open": len(local),
                    "closed_count": 0,
                    "closed_positions": [],
                    "dry_run": dry_run,
                    "reason": f"data_api_error: {exc}"[:300],
                }

            # 3. Build the set of token_ids the wallet currently holds.
            #    Data API rows use 'asset' for the ERC-1155 token id.
            wallet_token_ids = {
                str(p.get("asset") or p.get("tokenId") or p.get("token_id"))
                for p in wallet_positions
                if isinstance(p, dict)
            }
            wallet_token_ids.discard("None")
            wallet_token_ids.discard("")

            # 4. Decide which local OPEN rows are now stale.
            stale = [row for row in local if row["token_id"] not in wallet_token_ids]
            kept = [row for row in local if row["token_id"] in wallet_token_ids]

            if not stale:
                return {
                    "ok": True,
                    "bot_id": bot_id,
                    "wallet": wallet_address,
                    "checked": len(local),
                    "kept_open": len(kept),
                    "closed_count": 0,
                    "closed_positions": [],
                    "dry_run": dry_run,
                }

            # 5. Close stale rows (unless dry_run).
            closed: list[dict[str, Any]] = []
            if dry_run:
                # Preview only — still emit a structured record so the
                # script can print before/after counts and the operator
                # can inspect what would change.
                for row in stale:
                    closed.append(
                        {
                            "id": int(row["id"]),
                            "token_id": row["token_id"],
                            "condition_id": row["condition_id"],
                            "side": row["side"],
                            "size": str(row["size"]),
                            "cost_basis_usd": str(row["cost_basis_usd"]),
                        }
                    )
            else:
                stale_ids = [int(r["id"]) for r in stale]
                with self._sessions() as s:
                    db_rows = list(
                        s.scalars(
                            select(Position).where(
                                Position.id.in_(stale_ids),
                                Position.status == "OPEN",  # idempotency guard
                            )
                        )
                    )
                    for pos in db_rows:
                        payload = {
                            "position_id": int(pos.id),
                            "token_id": str(pos.token_id),
                            "condition_id": str(pos.condition_id),
                            "side": str(pos.side),
                            "size": str(pos.size),
                            "cost_basis_usd": str(pos.cost_basis_usd),
                            "reason": "not_in_wallet_positions",
                            "data_api_position_count": len(wallet_positions),
                        }
                        pos.status = "CLOSED_EXTERNAL_SYNC"
                        pos.closed_at = now
                        s.add(
                            Event(
                                bot_id=bot_id,
                                event_type="bot_d.live_position_reconciled",
                                severity="info",
                                message=(
                                    f"closed stale OPEN position id={pos.id} "
                                    f"token={str(pos.token_id)[:10]}... "
                                    f"size={pos.size} cost=${pos.cost_basis_usd} "
                                    f"(not in wallet/positions)"
                                ),
                                payload=payload,
                            )
                        )
                        closed.append(
                            {
                                "id": int(pos.id),
                                "token_id": str(pos.token_id),
                                "condition_id": str(pos.condition_id),
                                "side": str(pos.side),
                                "size": str(pos.size),
                                "cost_basis_usd": str(pos.cost_basis_usd),
                            }
                        )
                    s.commit()

            return {
                "ok": True,
                "bot_id": bot_id,
                "wallet": wallet_address,
                "checked": len(local),
                "kept_open": len(kept),
                "closed_count": len(closed),
                "closed_positions": closed,
                "dry_run": dry_run,
            }
        finally:
            if owns_client:
                http_client.close()
