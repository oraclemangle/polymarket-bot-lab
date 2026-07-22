"""Market / book / trade ingestion.

Three independent jobs, all driven off the same DB:

- `Scraper.run_once()`             — upserts active markets from Gamma API
- `BookSnapshotter.run_once(ids)`  — pulls order books for the active set
- `TradeStream.run()` (async)      — WSS user-channel, writes fills + emits to portfolio

Systemd timers run Scraper every 15m and BookSnapshotter every 5m.  TradeStream
is always-on.  Spec: specs/shared-infra.md §3.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import websockets
from sqlalchemy import select

from core.config import FEE_RATE_BY_CATEGORY_BPS, get_settings
from core.db import Book, Market, Position, get_session_factory
from core.portfolio import Portfolio

log = logging.getLogger(__name__)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


# --- Category derivation from Gamma event tags ---
# Gamma's /markets endpoint stopped populating `category`. Tags live on
# /events (each event owns >=1 market). We fetch /events once per scrape,
# build event_id -> tag_labels, and derive our taxonomy priority-first.
# Priority order matters: a market tagged both "Politics" and "Middle East"
# is geopolitics, not politics.
_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("geopolitics", (
        "geopolitics", "middle east", "iran", "israel", "ukraine", "russia",
        "military strikes", "war", "conflict", "hamas", "gaza", "taiwan",
    )),
    ("politics", (
        "politics", "elections", "primaries", "us election", "global elections",
        "world elections", "president", "congress", "senate",
    )),
    ("economics", (
        "economy", "economic policy", "fed", "fed rates", "fomc", "cpi",
        "recession", "jobs", "inflation", "jerome powell",
    )),
    ("finance", (
        "finance", "commodities", "markets", "stocks", "oil",
    )),
    ("crypto", (
        "crypto", "bitcoin", "ethereum", "solana",
    )),
    ("sports", (
        "sports", "nba", "nfl", "mlb", "soccer", "tennis", "fifa", "games",
    )),
)


def _derive_category(tag_labels: Iterable[str]) -> str:
    labels_lower = {(l or "").strip().lower() for l in tag_labels if l}
    for cat, keywords in _CATEGORY_KEYWORDS:
        if any(k in labels_lower for k in keywords):
            return cat
    return "other"


# --- Scraper ---
class Scraper:
    """Pulls active markets from Gamma API, upserts into `markets` table."""

    def __init__(
        self,
        session_factory=None,
        gamma_host: str | None = None,
        page_size: int = 500,
    ):
        self._sessions = session_factory or get_session_factory()
        self.host = gamma_host or get_settings().polymarket_gamma_host
        self.page_size = page_size

    def _fetch_page(self, offset: int) -> list[dict]:
        url = f"{self.host}/markets"
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                url,
                params={
                    "active": "true",
                    "closed": "false",
                    "offset": offset,
                    "limit": self.page_size,
                },
            )
            r.raise_for_status()
            return r.json() or []

    def _fetch_event_categories(self, max_events: int = 2000) -> dict[str, str]:
        """Fetch active events and build event_id -> derived category map.

        Gamma's /markets payload no longer populates `category` or `tags`.
        /events still carries tag metadata; each event owns one or more
        markets. We dereference each market's `events[0].id` against this
        map inside `_upsert_batch`.

        Returns an empty dict (and logs a warning) on network error so
        ingest degrades to "other" categorisation instead of crashing.
        """
        url = f"{self.host}/events"
        out: dict[str, str] = {}
        offset = 0
        page_size = 500
        try:
            with httpx.Client(timeout=15.0) as client:
                while offset < max_events:
                    r = client.get(
                        url,
                        params={
                            "active": "true",
                            "closed": "false",
                            "offset": offset,
                            "limit": page_size,
                        },
                    )
                    r.raise_for_status()
                    batch = r.json() or []
                    if not batch:
                        break
                    for ev in batch:
                        eid = str(ev.get("id") or "")
                        if not eid:
                            continue
                        tags = ev.get("tags") or []
                        labels = [
                            (t.get("label") or t.get("slug") or "")
                            for t in tags
                            if isinstance(t, dict)
                        ]
                        out[eid] = _derive_category(labels)
                    if len(batch) < page_size:
                        break
                    offset += page_size
        except Exception as e:
            log.warning("ingest.events.fetch_failed", extra={"error": str(e)})
            return {}
        log.info("ingest.events.indexed", extra={"event_count": len(out)})
        return out

    def run_once(self, max_pages: int = 20) -> int:
        """Return count of markets upserted."""
        event_categories = self._fetch_event_categories()
        total = 0
        for page in range(max_pages):
            batch = self._fetch_page(page * self.page_size)
            if not batch:
                break
            total += self._upsert_batch(batch, event_categories=event_categories)
            if len(batch) < self.page_size:
                break
        log.info("ingest.scraper.done", extra={"markets_upserted": total})
        return total

    def _upsert_batch(
        self,
        batch: Iterable[dict],
        event_categories: dict[str, str] | None = None,
    ) -> int:
        event_categories = event_categories or {}
        count = 0
        with self._sessions() as s:
            for m in batch:
                cid = m.get("conditionId") or m.get("condition_id")
                if not cid:
                    continue
                # Prefer event-derived category (Gamma dropped per-market category
                # field). Fall back to the legacy field, then to "other".
                ev_id = ""
                ev_list = m.get("events") or []
                if ev_list and isinstance(ev_list[0], dict):
                    ev_id = str(ev_list[0].get("id") or "")
                category = event_categories.get(ev_id) or (m.get("category") or "other")
                category = category.lower()
                fee_bps = FEE_RATE_BY_CATEGORY_BPS.get(category, 50)
                # Gamma exposes tokens in several shapes:
                #  - legacy: list of {token_id, outcome} dicts
                #  - legacy: list of token_id strings
                #  - current: `clobTokenIds` as a JSON-encoded string, with a
                #    parallel `outcomes` JSON-encoded string of labels
                tokens_raw = m.get("tokens") or m.get("clobTokenIds") or []
                outcomes_raw = m.get("outcomes") or []
                if isinstance(tokens_raw, str):
                    try:
                        tokens_raw = json.loads(tokens_raw) or []
                    except (ValueError, TypeError):
                        tokens_raw = []
                if isinstance(outcomes_raw, str):
                    try:
                        outcomes_raw = json.loads(outcomes_raw) or []
                    except (ValueError, TypeError):
                        outcomes_raw = []
                yes_id = no_id = None
                if isinstance(tokens_raw, list) and tokens_raw:
                    if isinstance(tokens_raw[0], dict):
                        for t in tokens_raw:
                            if (t.get("outcome") or "").lower() == "yes":
                                yes_id = t.get("token_id")
                            elif (t.get("outcome") or "").lower() == "no":
                                no_id = t.get("token_id")
                    else:
                        # Parallel arrays of token_id + outcome label.
                        toks = [str(t) for t in tokens_raw]
                        outs = [str(o).lower() for o in outcomes_raw]
                        for idx, tok in enumerate(toks):
                            out = outs[idx] if idx < len(outs) else ""
                            if out == "yes":
                                yes_id = tok
                            elif out == "no":
                                no_id = tok
                        # Fallback: if outcomes weren't paired, assume position.
                        if yes_id is None and no_id is None and len(toks) >= 2:
                            yes_id, no_id = toks[0], toks[1]

                end_date = _parse_iso(m.get("endDate") or m.get("end_date"))
                vol_raw = (
                    m.get("volume24hr") or m.get("volume_24h") or m.get("volumeNum") or 0
                )
                try:
                    from decimal import Decimal

                    vol = Decimal(str(vol_raw)).quantize(Decimal("0.01"))
                except Exception:
                    vol = Decimal("0")

                # YES outcome price from Gamma. `outcomePrices` is a JSON string
                # like '["0.05","0.95"]'; we pair with the outcomes list.
                yes_price_dec: Decimal | None = None
                prices_raw = m.get("outcomePrices")
                if isinstance(prices_raw, str):
                    try:
                        prices_raw = json.loads(prices_raw)
                    except (ValueError, TypeError):
                        prices_raw = None
                if isinstance(prices_raw, list) and prices_raw:
                    try:
                        if isinstance(outcomes_raw, list) and outcomes_raw:
                            outs_lower = [str(o).lower() for o in outcomes_raw]
                            if "yes" in outs_lower:
                                yes_price_dec = Decimal(str(prices_raw[outs_lower.index("yes")]))
                            else:
                                yes_price_dec = Decimal(str(prices_raw[0]))
                        else:
                            yes_price_dec = Decimal(str(prices_raw[0]))
                    except (ValueError, TypeError, IndexError):
                        yes_price_dec = None

                existing = s.get(Market, cid)
                if existing is None:
                    s.add(
                        Market(
                            condition_id=cid,
                            category=category,
                            question=m.get("question") or "",
                            end_date=end_date,
                            fee_rate_bps=fee_bps,
                            yes_token_id=yes_id,
                            no_token_id=no_id,
                            is_neg_risk=1 if m.get("negRisk") else 0,
                            volume_24h_usd=vol,
                            yes_price=yes_price_dec,
                            last_updated=datetime.now(UTC),
                        )
                    )
                else:
                    existing.category = category
                    existing.question = m.get("question") or existing.question
                    existing.end_date = end_date or existing.end_date
                    existing.fee_rate_bps = fee_bps
                    existing.yes_token_id = yes_id or existing.yes_token_id
                    existing.no_token_id = no_id or existing.no_token_id
                    existing.is_neg_risk = 1 if m.get("negRisk") else existing.is_neg_risk
                    existing.volume_24h_usd = vol
                    if yes_price_dec is not None:
                        existing.yes_price = yes_price_dec
                    existing.last_updated = datetime.now(UTC)
                count += 1
            s.commit()
        return count


# --- Book snapshotter ---
class BookSnapshotter:
    def __init__(self, session_factory=None, host: str | None = None):
        self._sessions = session_factory or get_session_factory()
        self.host = host or get_settings().polymarket_host

    def active_token_ids(self) -> list[str]:
        """Return token IDs we care about — both YES and NO per market.

        Candidate assembly (Bot B especially) requires both sides of the book,
        so we must snapshot both. Bots narrow the set via a watchlist helper.
        """
        with self._sessions() as s:
            rows = list(
                s.execute(
                    select(Market.yes_token_id, Market.no_token_id).where(
                        Market.yes_token_id.is_not(None)
                    )
                )
            )
        out: list[str] = []
        for yes_id, no_id in rows:
            if yes_id:
                out.append(yes_id)
            if no_id:
                out.append(no_id)
        return out

    def tokens_for_bot_a(
        self,
        max_yes_price: Decimal,
        min_volume_usd: Decimal,
        categories: Iterable[str],
    ) -> list[str]:
        """Narrow scan targets to markets that could pass Bot A's filters.

        Bot A fades tail-priced YES (≤ MAX_YES_ENTRY_PRICE). Snapshotting
        books for ~1,200 target-category non-neg-risk markets per tick
        would chew through the CLOB rate budget; filtering by the
        Gamma-reported yes_price first drops that to dozens of candidates.

        We snapshot the NO token (Bot A sells NO) plus the YES token
        (needed for mid-price sanity in `build_candidates`).
        """
        cats = [c.lower() for c in categories]
        with self._sessions() as s:
            rows = list(
                s.execute(
                    select(Market.yes_token_id, Market.no_token_id).where(
                        Market.yes_token_id.is_not(None),
                        Market.no_token_id.is_not(None),
                        Market.is_neg_risk == 0,
                        Market.category.in_(cats),
                        Market.volume_24h_usd >= min_volume_usd,
                        Market.yes_price.is_not(None),
                        Market.yes_price <= max_yes_price,
                    )
                )
            )
        out: list[str] = []
        for yes_id, no_id in rows:
            if yes_id: out.append(yes_id)
            if no_id: out.append(no_id)
        return out

    def tokens_for_bot_b(
        self,
        categories: Iterable[str],
    ) -> list[str]:
        """Narrow scan targets to markets that could pass Bot B's filters.

        Bot B is a directional trader on scored markets. Unlike the
        full-scan `active_token_ids()` which returns ~20,000 tokens,
        this filters to non-neg-risk markets in Bot B's target categories.
        """
        cats = [c.lower() for c in categories]
        with self._sessions() as s:
            rows = list(
                s.execute(
                    select(Market.yes_token_id, Market.no_token_id).where(
                        Market.yes_token_id.is_not(None),
                        Market.no_token_id.is_not(None),
                        Market.is_neg_risk == 0,
                        Market.category.in_(cats),
                    )
                )
            )
        out: list[str] = []
        for yes_id, no_id in rows:
            if yes_id:
                out.append(yes_id)
            if no_id:
                out.append(no_id)
        return out

    def snapshot(self, token_id: str) -> bool:
        url = f"{self.host}/book"
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(url, params={"token_id": token_id})
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            log.warning("ingest.book.fetch_failed", extra={"token": token_id, "error": str(e)})
            return False

        bids = [
            [str(b.get("price")), str(b.get("size"))] for b in (data.get("bids") or [])
        ]
        asks = [
            [str(a.get("price")), str(a.get("size"))] for a in (data.get("asks") or [])
        ]
        with self._sessions() as s:
            s.add(
                Book(
                    token_id=token_id,
                    snapshot_at=datetime.now(UTC),
                    bids=bids,
                    asks=asks,
                )
            )
            s.commit()
        return True

    def run_once(self, token_ids: Iterable[str] | None = None) -> int:
        ids = list(token_ids) if token_ids is not None else self.active_token_ids()
        count = 0
        for tid in ids:
            if self.snapshot(tid):
                count += 1
        log.info("ingest.books.done", extra={"snapshots": count, "total": len(ids)})
        return count


# --- Price helpers (latest-book derived mark prices) ---
def latest_yes_mid_prices(
    condition_ids: Iterable[str] | None = None,
    session_factory=None,
) -> dict[str, Decimal]:
    """Return `{yes_token_id: mid_price}` from the most recent Book rows.

    Used by daemons to supply a `current_yes_price_fn` for exit checks and to
    build the `mark_prices` dict for drawdown / PnL snapshotting. If no
    `condition_ids` is supplied, scans every market with a yes_token_id.

    Mid is `(best_bid + best_ask) / 2`; if one side is empty we fall back to
    the other, and skip markets with no book data at all.
    """
    sf = session_factory or get_session_factory()
    out: dict[str, Decimal] = {}
    with sf() as s:
        stmt = select(Market.yes_token_id)
        if condition_ids is not None:
            ids = [c for c in condition_ids if c]
            if not ids:
                return out
            stmt = stmt.where(Market.condition_id.in_(ids))
        yes_tokens = [y for y in s.scalars(stmt) if y]
        for yes_tok in yes_tokens:
            book = s.scalars(
                select(Book).where(Book.token_id == yes_tok).order_by(Book.snapshot_at.desc())
            ).first()
            if book is None:
                continue
            bids = book.bids or []
            asks = book.asks or []
            best_bid = max((Decimal(str(r[0])) for r in bids), default=None)
            best_ask = min((Decimal(str(r[0])) for r in asks), default=None)
            if best_bid is not None and best_ask is not None:
                out[yes_tok] = (best_bid + best_ask) / 2
            elif best_bid is not None:
                out[yes_tok] = best_bid
            elif best_ask is not None:
                out[yes_tok] = best_ask
    return out


def build_mark_prices(
    bot_id: str, session_factory=None
) -> dict[str, Decimal]:
    """Return `{token_id: mark}` for every OPEN position of `bot_id`.

    Mark for a YES-side position is the mid of its own token's latest book.
    Mark for a NO-side position is `1 − mid(yes_book)` (canonical equivalent).
    Positions with no fresh book are omitted (portfolio handles missing marks
    by skipping — i.e. conservative: unrealised PnL = 0 for that position).
    """
    sf = session_factory or get_session_factory()
    out: dict[str, Decimal] = {}
    with sf() as s:
        positions = list(
            s.scalars(
                select(Position).where(Position.bot_id == bot_id, Position.status == "OPEN")
            )
        )
        market_map = {
            m.condition_id: m
            for m in s.scalars(select(Market))
        }
        for pos in positions:
            market = market_map.get(pos.condition_id)
            if market is None:
                continue
            # Mark the token directly (works for both YES and NO sides).
            book = s.scalars(
                select(Book)
                .where(Book.token_id == pos.token_id)
                .order_by(Book.snapshot_at.desc())
            ).first()
            mid: Decimal | None = None
            if book is not None:
                bids = book.bids or []
                asks = book.asks or []
                best_bid = max((Decimal(str(r[0])) for r in bids), default=None)
                best_ask = min((Decimal(str(r[0])) for r in asks), default=None)
                if best_bid is not None and best_ask is not None:
                    mid = (best_bid + best_ask) / 2
                elif best_bid is not None:
                    mid = best_bid
                elif best_ask is not None:
                    mid = best_ask
            if mid is None and market.yes_token_id:
                # Fall back via YES book for NO-side positions.
                yes_book = s.scalars(
                    select(Book)
                    .where(Book.token_id == market.yes_token_id)
                    .order_by(Book.snapshot_at.desc())
                ).first()
                if yes_book is not None:
                    bids = yes_book.bids or []
                    asks = yes_book.asks or []
                    best_bid = max((Decimal(str(r[0])) for r in bids), default=None)
                    best_ask = min((Decimal(str(r[0])) for r in asks), default=None)
                    if best_bid is not None and best_ask is not None:
                        yes_mid = (best_bid + best_ask) / 2
                        mid = (Decimal("1") - yes_mid) if pos.side == "NO" else yes_mid
            if mid is not None:
                out[pos.token_id] = mid
    return out


def latest_yes_price_fn(
    session_factory=None,
) -> Callable[[str], Decimal | None]:
    """Return a callable `(yes_token_id) -> Decimal|None` that reads the
    latest Book row per token. Used by daemons for exit-price lookups.
    """
    sf = session_factory or get_session_factory()

    def _lookup(yes_token_id: str) -> Decimal | None:
        with sf() as s:
            book = s.scalars(
                select(Book)
                .where(Book.token_id == yes_token_id)
                .order_by(Book.snapshot_at.desc())
            ).first()
        if book is None:
            return None
        bids = book.bids or []
        asks = book.asks or []
        best_bid = max((Decimal(str(r[0])) for r in bids), default=None)
        best_ask = min((Decimal(str(r[0])) for r in asks), default=None)
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2
        return best_bid or best_ask


    return _lookup


# --- Trade stream (WSS user channel) ---
class TradeStream:
    """Async WSS consumer that writes fills to DB and invokes portfolio.on_fill.

    `auth_payload` is constructed externally (HMAC signed) and passed in —
    keeping this class agnostic of the signing path.  The bot daemon builds it.
    """

    def __init__(
        self,
        auth_payload: dict,
        portfolio: Portfolio | None = None,
        bot_id: str = "bot_a",
        wss_host: str | None = None,
        on_event: Callable[[dict], Awaitable[None]] | None = None,
    ):
        self.auth_payload = auth_payload
        self.portfolio = portfolio or Portfolio()
        self.bot_id = bot_id
        self.host = wss_host or get_settings().polymarket_wss_host
        self._on_event = on_event

    async def _handle_event(self, event: dict) -> None:
        etype = event.get("event_type") or event.get("type")
        if etype in ("trade", "match", "TRADE"):
            ts = _parse_iso(event.get("timestamp")) or datetime.now(UTC)
            try:
                self.portfolio.on_fill(
                    bot_id=self.bot_id,
                    trade_id=str(event["id"]),
                    order_id=str(event.get("order_id")) if event.get("order_id") else None,
                    condition_id=str(event.get("condition_id") or ""),
                    token_id=str(event["asset_id"]),
                    side=str(event["side"]),
                    price=Decimal(str(event["price"])),
                    size=Decimal(str(event["size"])),
                    fee_usd=Decimal(str(event.get("fee_usd", "0"))),
                    filled_at=ts,
                )
            except KeyError as e:
                log.warning("ingest.wss.missing_field", extra={"field": str(e), "event": event})
        if self._on_event:
            await self._on_event(event)

    async def run(self, reconnect: bool = True) -> None:
        url = f"{self.host}/user"
        backoff = 1.0
        while True:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    await ws.send(json.dumps(self.auth_payload))
                    backoff = 1.0
                    async for raw in ws:
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            log.warning("ingest.wss.bad_json", extra={"raw": raw[:200]})
                            continue
                        await self._handle_event(event)
            except Exception as e:
                log.warning("ingest.wss.disconnect", extra={"error": str(e)})
                if not reconnect:
                    raise
                await asyncio.sleep(min(backoff, 30.0))
                backoff = min(backoff * 2, 30.0)
