"""Pyth price-feed ingest.

Runs two concurrent subscribers:
  - Pro: wss://pyth-lazer-0.dourolabs.app/v1/stream (Bearer PYTH_TOKEN)
  - Hermes: wss://hermes.pyth.network/ws (no auth; stub until feed-id map known)

Each subscriber aggregates 200ms ticks into 1-second OHLC bars keyed
(ts, feed_id) and writes to its per-endpoint table. Raw recent ticks
(last 2h) go to pyth_ticks_recent for later analysis.

Reconnects with capped exponential backoff. Logs heartbeat every 30s.
Warns loudly after 2026-04-22 if still on the Pro endpoint.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import websockets
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from core.pyth_feeds import Feed, active_feeds, feed_by_hermes_id, feed_by_id, hermes_feeds
from core.pyth_models import PythBarHermes, PythBarPro, PythTickRecent

log = logging.getLogger(__name__)


PRO_URI = "wss://pyth-lazer-0.dourolabs.app/v1/stream"
HERMES_URI = "wss://hermes.pyth.network/ws"
BACKOFF_INITIAL_S = 1.0
BACKOFF_MAX_S = 60.0
HEARTBEAT_EVERY_S = 30.0
TICK_PRUNE_EVERY_S = 60.0
TICK_RETENTION_S = 7200
TRIAL_EXPIRY = datetime(2026, 4, 22, 0, 0, tzinfo=UTC)


def decode_price(raw: int | str, exponent: int | str) -> Decimal:
    """price = raw * 10**exponent, using Decimal to preserve precision."""
    return Decimal(int(raw)) * (Decimal(10) ** int(exponent))


@dataclass
class _BarBuilder:
    feed_id: int
    symbol: str
    ts_second: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    bid: Decimal | None = None
    ask: Decimal | None = None
    confidence: Decimal | None = None
    publisher_count: int | None = None
    market_session: str | None = None
    tick_count: int = 1

    def update(
        self,
        price: Decimal,
        bid: Decimal | None,
        ask: Decimal | None,
        confidence: Decimal | None,
        publisher_count: int | None,
        market_session: str | None,
    ) -> None:
        self.close = price
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        if bid is not None:
            self.bid = bid
        if ask is not None:
            self.ask = ask
        if confidence is not None:
            self.confidence = confidence
        if publisher_count is not None:
            self.publisher_count = publisher_count
        if market_session is not None:
            self.market_session = market_session
        self.tick_count += 1

    def to_row(self) -> dict[str, Any]:
        return dict(
            ts=datetime.fromtimestamp(self.ts_second, tz=UTC),
            feed_id=self.feed_id,
            symbol=self.symbol,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            bid=self.bid,
            ask=self.ask,
            confidence=self.confidence,
            publisher_count=self.publisher_count,
            market_session=self.market_session,
            tick_count=self.tick_count,
        )


class PythIngestor:
    """Per-endpoint bar aggregator + tick persister."""

    def __init__(
        self,
        endpoint_name: str,
        session_factory: sessionmaker,
        bar_model: type[PythBarPro] | type[PythBarHermes],
    ) -> None:
        if endpoint_name not in ("pro", "hermes"):
            raise ValueError(f"endpoint_name must be 'pro' or 'hermes', got {endpoint_name!r}")
        self.endpoint_name = endpoint_name
        self.session_factory = session_factory
        self.bar_model = bar_model
        self._bars: dict[int, _BarBuilder] = {}
        self.last_tick_at: float | None = None

    def handle_tick(
        self,
        feed_id: int,
        symbol: str,
        price: Decimal,
        bid: Decimal | None,
        ask: Decimal | None,
        confidence: Decimal | None,
        publisher_count: int | None,
        market_session: str | None,
        ts_ms: int,
        *,
        autocommit: bool = True,
        session: Any = None,
    ) -> None:
        """Absorb one tick.

        Default behaviour opens a session and commits immediately (one commit
        per tick). High-throughput callers should instead open a session once,
        pass it via ``session=``, and set ``autocommit=False``; the caller is
        then responsible for committing once per frame-batch. See C19 in
        AUDIT.md.
        """
        self.last_tick_at = time.monotonic()
        ts_second = ts_ms // 1000

        if session is None:
            session_ctx = self.session_factory()
        else:
            session_ctx = _NullCtx(session)

        with session_ctx as sess:
            sess.add(
                PythTickRecent(
                    endpoint=self.endpoint_name,
                    ts_ms=ts_ms,
                    feed_id=feed_id,
                    price=price,
                    bid=bid,
                    ask=ask,
                )
            )

            current = self._bars.get(feed_id)
            if current is None or current.ts_second != ts_second:
                if current is not None:
                    self._flush_bar(sess, current)
                self._bars[feed_id] = _BarBuilder(
                    feed_id=feed_id,
                    symbol=symbol,
                    ts_second=ts_second,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    bid=bid,
                    ask=ask,
                    confidence=confidence,
                    publisher_count=publisher_count,
                    market_session=market_session,
                    tick_count=1,
                )
            else:
                current.update(price, bid, ask, confidence, publisher_count, market_session)

            if autocommit:
                sess.commit()

    def _flush_bar(self, session: Any, bar: _BarBuilder) -> None:
        row = self.bar_model(**bar.to_row())
        session.merge(row)

    def flush_open_bars(self) -> int:
        if not self._bars:
            return 0
        with self.session_factory() as session:
            for bar in self._bars.values():
                self._flush_bar(session, bar)
            session.commit()
        flushed = len(self._bars)
        self._bars.clear()
        return flushed

    def prune_ticks(self) -> int:
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - TICK_RETENTION_S * 1000
        with self.session_factory() as session:
            res = session.execute(
                delete(PythTickRecent).where(
                    PythTickRecent.endpoint == self.endpoint_name,
                    PythTickRecent.ts_ms < cutoff_ms,
                )
            )
            session.commit()
            return res.rowcount or 0


class _NullCtx:
    """Pass-through context manager for reusing an externally-owned session."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def __enter__(self) -> Any:
        return self._value

    def __exit__(self, *exc: Any) -> None:
        pass


def _decode_parsed_tick(parsed: dict[str, Any], *, ts_ms: int | None = None) -> dict[str, Any] | None:
    """Extract one tick from a Pyth Lazer per-feed parsed dict. Returns None if malformed.

    `parsed` is ONE element of the `priceFeeds` list inside a streamUpdated frame.
    `ts_ms` is the frame-level timestamp; if None, now() is substituted.
    """
    try:
        feed_id = int(parsed["priceFeedId"])
        exponent = int(parsed["exponent"])
        price = decode_price(parsed["price"], exponent)
        bid = decode_price(parsed["bestBidPrice"], exponent) if parsed.get("bestBidPrice") else None
        ask = decode_price(parsed["bestAskPrice"], exponent) if parsed.get("bestAskPrice") else None
        confidence = (
            decode_price(parsed["confidence"], exponent) if parsed.get("confidence") else None
        )
        publisher_count = (
            int(parsed["publisherCount"]) if parsed.get("publisherCount") is not None else None
        )
        market_session = parsed.get("marketSession")
        # Back-compat: some callers still pass timestampNs in the per-tick dict.
        if ts_ms is None:
            ts_ns = parsed.get("timestampNs")
            ts_ms_effective = (
                int(int(ts_ns) // 1_000_000) if ts_ns is not None else int(time.time() * 1000)
            )
        else:
            ts_ms_effective = ts_ms
    except (KeyError, ValueError, TypeError) as exc:
        log.debug("skipped malformed parsed tick: %s (parsed=%r)", exc, parsed)
        return None
    return {
        "feed_id": feed_id,
        "price": price,
        "bid": bid,
        "ask": ask,
        "confidence": confidence,
        "publisher_count": publisher_count,
        "market_session": market_session,
        "ts_ms": ts_ms_effective,
    }


async def _run_pro_once(
    token: str,
    ingestor: PythIngestor,
    feeds: list[Feed],
    *,
    connect_factory: Any = websockets.connect,
) -> None:
    """One Pro connection lifecycle. Returns on disconnect; caller retries."""
    subscribe_frame = {
        "type": "subscribe",
        "subscriptionId": 1,
        "priceFeedIds": [f.id for f in feeds if f.id is not None],
        "properties": [
            "price",
            "exponent",
            "bestBidPrice",
            "bestAskPrice",
            "confidence",
            "publisherCount",
            "marketSession",
        ],
        "chains": ["solana"],
        "channel": "fixed_rate@200ms",
        "parsed": True,
    }
    headers = [("Authorization", f"Bearer {token}")]
    log.info("pro: connecting to %s with %d feeds", PRO_URI, len(subscribe_frame["priceFeedIds"]))
    async with connect_factory(PRO_URI, additional_headers=headers) as ws:
        await ws.send(json.dumps(subscribe_frame))
        log.info("pro: subscribe sent")
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as exc:
                log.warning("pro: bad JSON: %s", exc)
                continue
            if msg.get("type") != "streamUpdated":
                log.debug("pro: ignoring frame type=%s", msg.get("type"))
                continue
            parsed = msg.get("parsed") or {}
            price_feeds = parsed.get("priceFeeds") or []
            ts_us = parsed.get("timestampUs")
            frame_ts_ms = (
                int(int(ts_us) // 1000) if ts_us is not None else int(time.time() * 1000)
            )
            # C19 fix: commit ONCE per frame (which has up to ~14 ticks) rather than
            # once per tick. At 5 frames/sec * 14 feeds we used to do 70 commits/sec;
            # now 5 commits/sec.
            with ingestor.session_factory() as batch_session:
                for feed_entry in price_feeds:
                    tick = _decode_parsed_tick(feed_entry, ts_ms=frame_ts_ms)
                    if tick is None:
                        continue
                    feed = feed_by_id(tick["feed_id"])
                    if feed is None:
                        log.warning("pro: untracked feed_id %s", tick["feed_id"])
                        continue
                    ingestor.handle_tick(
                        feed_id=tick["feed_id"],
                        symbol=feed.symbol,
                        price=tick["price"],
                        bid=tick["bid"],
                        ask=tick["ask"],
                        confidence=tick["confidence"],
                        publisher_count=tick["publisher_count"],
                        market_session=tick["market_session"],
                        ts_ms=tick["ts_ms"],
                        autocommit=False,
                        session=batch_session,
                    )
                batch_session.commit()


async def run_pro(
    token: str,
    session_factory: sessionmaker,
    feeds: Iterable[Feed],
    *,
    connect_factory: Any = websockets.connect,
    stop_event: asyncio.Event | None = None,
) -> PythIngestor:
    """Run the Pro subscriber with reconnect loop. Returns the ingestor (for tests)."""
    ingestor = PythIngestor("pro", session_factory, PythBarPro)
    feed_list = [f for f in feeds if f.id is not None]
    backoff = BACKOFF_INITIAL_S
    last_expiry_warn = 0.0
    try:
        while stop_event is None or not stop_event.is_set():
            now = datetime.now(UTC)
            if now > TRIAL_EXPIRY and (time.monotonic() - last_expiry_warn) > 60:
                log.warning(
                    "PYTH PRO TRIAL EXPIRED — restart Bot C with "
                    "--endpoint hermes or BOT_C_ENDPOINT=hermes"
                )
                last_expiry_warn = time.monotonic()
            try:
                await _run_pro_once(token, ingestor, feed_list, connect_factory=connect_factory)
                log.info("pro: connection closed cleanly")
                backoff = BACKOFF_INITIAL_S
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("pro: connection error: %s; backoff=%.1fs", exc, backoff)
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    raise
                backoff = min(backoff * 2, BACKOFF_MAX_S)
                continue
            # Clean disconnect — short sleep then reconnect
            try:
                await asyncio.sleep(BACKOFF_INITIAL_S)
            except asyncio.CancelledError:
                raise
    finally:
        ingestor.flush_open_bars()
    return ingestor


def _decode_hermes_frame(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Extract one tick from a Hermes price_update frame. Returns None if malformed.

    Schema (verified 2026-04-15 at wss://hermes.pyth.network/ws):
    {"type":"price_update","price_feed":{"id":"<64-hex>",
      "price":{"price":"<int>","conf":"<int>","expo":<int>,"publish_time":<secs>},
      "ema_price":{...}}}
    """
    try:
        feed = payload.get("price_feed") or {}
        fid_hex = str(feed["id"])
        p = feed["price"]
        expo = int(p["expo"])
        price = decode_price(p["price"], expo)
        confidence = decode_price(p["conf"], expo) if p.get("conf") else None
        publish_time_s = int(p.get("publish_time") or time.time())
        ts_ms = publish_time_s * 1000
    except (KeyError, ValueError, TypeError) as exc:
        log.debug("hermes: skipped malformed frame: %s (payload=%r)", exc, payload)
        return None
    # Hermes publishes price=0 during closed market sessions for equities/ETFs.
    # Drop those so they don't poison bars or downstream vol/edge calculations.
    if price <= 0:
        return None
    return {
        "feed_id_hex": fid_hex,
        "price": price,
        "confidence": confidence,
        "ts_ms": ts_ms,
    }


async def _run_hermes_once(
    ingestor: PythIngestor,
    feeds: list[Feed],
    *,
    connect_factory: Any = websockets.connect,
) -> None:
    """One Hermes connection lifecycle. Returns on disconnect; caller retries.

    Hermes frames are per-feed (not batched like Lazer), so we commit once per
    frame rather than once per tick (still much better than original autocommit
    which was the same — but keeps the code path consistent).
    """
    ids = [f.hermes_id for f in feeds if f.hermes_id is not None]
    if not ids:
        raise RuntimeError("hermes: no feeds with hermes_id configured")
    subscribe_frame = {"type": "subscribe", "ids": ids}
    log.info("hermes: connecting to %s with %d feeds", HERMES_URI, len(ids))
    async with connect_factory(HERMES_URI) as ws:
        await ws.send(json.dumps(subscribe_frame))
        log.info("hermes: subscribe sent")
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as exc:
                log.warning("hermes: bad JSON: %s", exc)
                continue
            mtype = msg.get("type")
            if mtype == "response":
                status = msg.get("status")
                if status != "success":
                    log.warning("hermes: subscribe response status=%s msg=%s",
                                status, msg.get("error") or msg)
                else:
                    log.debug("hermes: subscribe acknowledged")
                continue
            if mtype != "price_update":
                log.debug("hermes: ignoring frame type=%s", mtype)
                continue
            tick = _decode_hermes_frame(msg)
            if tick is None:
                continue
            feed = feed_by_hermes_id(tick["feed_id_hex"])
            if feed is None or feed.id is None:
                log.warning("hermes: untracked feed_id %s", tick["feed_id_hex"])
                continue
            # Persist using the Lazer numeric id as feed_id for cross-endpoint joins.
            with ingestor.session_factory() as batch_session:
                ingestor.handle_tick(
                    feed_id=feed.id,
                    symbol=feed.symbol,
                    price=tick["price"],
                    bid=None,
                    ask=None,
                    confidence=tick["confidence"],
                    publisher_count=None,
                    market_session=None,
                    ts_ms=tick["ts_ms"],
                    autocommit=False,
                    session=batch_session,
                )
                batch_session.commit()


async def run_hermes(
    session_factory: sessionmaker,
    feeds: Iterable[Feed],
    *,
    connect_factory: Any = websockets.connect,
    stop_event: asyncio.Event | None = None,
) -> PythIngestor:
    """Hermes subscriber reconnect loop. Returns the ingestor (for tests)."""
    ingestor = PythIngestor("hermes", session_factory, PythBarHermes)
    feed_list = [f for f in feeds if f.hermes_id is not None]
    if not feed_list:
        log.warning(
            "hermes: no feeds have hermes_id set; subscriber would idle. "
            "Sleeping until cancelled instead of opening a pointless connection."
        )
        try:
            if stop_event is not None:
                await stop_event.wait()
            else:
                await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise
        finally:
            ingestor.flush_open_bars()
        return ingestor

    backoff = BACKOFF_INITIAL_S
    try:
        while stop_event is None or not stop_event.is_set():
            try:
                await _run_hermes_once(ingestor, feed_list, connect_factory=connect_factory)
                log.info("hermes: connection closed cleanly")
                backoff = BACKOFF_INITIAL_S
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("hermes: connection error: %s; backoff=%.1fs", exc, backoff)
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    raise
                backoff = min(backoff * 2, BACKOFF_MAX_S)
                continue
            try:
                await asyncio.sleep(BACKOFF_INITIAL_S)
            except asyncio.CancelledError:
                raise
    finally:
        ingestor.flush_open_bars()
    return ingestor


async def _wrap_hermes(
    ingestor: PythIngestor,
    feeds: list[Feed],
) -> None:
    """Hermes reconnect loop using a shared ingestor (so heartbeat can see it)."""
    if not feeds:
        log.warning("hermes: no feeds configured; idle loop until cancelled")
        try:
            await asyncio.Event().wait()
        finally:
            ingestor.flush_open_bars()
        return

    backoff = BACKOFF_INITIAL_S
    try:
        while True:
            try:
                await _run_hermes_once(ingestor, feeds)
                log.info("hermes: connection closed cleanly; reconnecting")
                backoff = BACKOFF_INITIAL_S
                await asyncio.sleep(BACKOFF_INITIAL_S)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("hermes: connection error: %s; backoff=%.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX_S)
    finally:
        ingestor.flush_open_bars()


def _age(ing: PythIngestor | None) -> str:
    if ing is None:
        return "disabled"
    if ing.last_tick_at is None:
        return "no-ticks"
    return f"{time.monotonic() - ing.last_tick_at:.1f}s"


async def heartbeat(
    pro_ing: PythIngestor | None,
    hermes_ing: PythIngestor | None,
    *,
    stop_event: asyncio.Event | None = None,
    interval_s: float = HEARTBEAT_EVERY_S,
) -> None:
    while stop_event is None or not stop_event.is_set():
        log.info("HB pro=%s hermes=%s", _age(pro_ing), _age(hermes_ing))
        try:
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            raise


async def pruner(
    ingestors: list[PythIngestor],
    *,
    stop_event: asyncio.Event | None = None,
    interval_s: float = TICK_PRUNE_EVERY_S,
) -> None:
    while stop_event is None or not stop_event.is_set():
        try:
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            raise
        for ing in ingestors:
            try:
                deleted = ing.prune_ticks()
                if deleted:
                    log.debug("pruned %d ticks from endpoint=%s", deleted, ing.endpoint_name)
            except Exception as exc:
                log.warning("prune failed for %s: %s", ing.endpoint_name, exc)


async def run_ingest(
    session_factory: sessionmaker,
    token: str | None,
    feeds: Iterable[Feed] | None = None,
    *,
    include_pro: bool = True,
    include_hermes: bool = True,
) -> None:
    feed_list = list(feeds) if feeds is not None else active_feeds()
    if not feed_list:
        raise RuntimeError("no active feeds configured; check core/pyth_feeds.py")

    stop_event = asyncio.Event()
    pro_ing: PythIngestor | None = None
    hermes_ing: PythIngestor | None = None
    tasks: list[asyncio.Task] = []

    if include_pro:
        if not token:
            log.warning("PYTH_TOKEN unset or empty; skipping Pro subscriber")
        else:
            pro_ing = PythIngestor("pro", session_factory, PythBarPro)
            tasks.append(asyncio.create_task(_wrap_pro(token, pro_ing, feed_list), name="pro"))

    if include_hermes:
        hermes_feed_list = [f for f in feed_list if f.hermes_id is not None]
        if not hermes_feed_list:
            log.warning(
                "hermes: no feeds in feed_list have hermes_id set; skipping Hermes subscriber"
            )
        else:
            hermes_ing = PythIngestor("hermes", session_factory, PythBarHermes)
            tasks.append(
                asyncio.create_task(
                    _wrap_hermes(hermes_ing, hermes_feed_list), name="hermes"
                )
            )

    ingestors = [ing for ing in (pro_ing, hermes_ing) if ing is not None]
    if not ingestors:
        raise RuntimeError(
            "no Pyth subscribers started; provide PYTH_TOKEN for Pro or enable Hermes"
        )
    tasks.append(
        asyncio.create_task(heartbeat(pro_ing, hermes_ing, stop_event=stop_event), name="hb")
    )
    tasks.append(
        asyncio.create_task(pruner(ingestors, stop_event=stop_event), name="pruner")
    )

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        log.info("ingest: cancellation received, stopping tasks")
        stop_event.set()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


async def _wrap_pro(token: str, ingestor: PythIngestor, feeds: list[Feed]) -> None:
    """Pro reconnect loop using a shared ingestor (so heartbeat can see it)."""
    backoff = BACKOFF_INITIAL_S
    last_expiry_warn = 0.0
    try:
        while True:
            now = datetime.now(UTC)
            if now > TRIAL_EXPIRY and (time.monotonic() - last_expiry_warn) > 60:
                log.warning(
                    "PYTH PRO TRIAL EXPIRED — restart Bot C with "
                    "--endpoint hermes or BOT_C_ENDPOINT=hermes"
                )
                last_expiry_warn = time.monotonic()
            try:
                await _run_pro_once(token, ingestor, feeds)
                log.info("pro: connection closed cleanly; reconnecting")
                backoff = BACKOFF_INITIAL_S
                await asyncio.sleep(BACKOFF_INITIAL_S)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("pro: connection error: %s; backoff=%.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX_S)
    finally:
        ingestor.flush_open_bars()
