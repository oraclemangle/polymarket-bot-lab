"""Unit tests for core.pyth_ingest. Zero network IO."""
from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.db import Base
from core import pyth_models  # noqa: F401 — register models
from core.pyth_feeds import FEEDS, active_feeds
from core.pyth_ingest import (
    BACKOFF_INITIAL_S,
    PythIngestor,
    _decode_parsed_tick,
    decode_price,
    run_ingest,
    run_pro,
    _wrap_pro,
)
from core.pyth_models import PythBarPro, PythBarHermes, PythTickRecent


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_decode_negative_exponent():
    assert decode_price(4726139, -3) == Decimal("4726.139")


def test_decode_positive_exponent():
    assert decode_price(5, 2) == Decimal("500")


def test_decode_string_inputs():
    assert decode_price("100", "-2") == Decimal("1.00")


def test_parsed_tick_skips_malformed():
    assert _decode_parsed_tick({"priceFeedId": 346}) is None


def test_parsed_tick_happy_path():
    tick = _decode_parsed_tick({
        "priceFeedId": 346,
        "price": 4726139,
        "exponent": -3,
        "bestBidPrice": 4726000,
        "bestAskPrice": 4726200,
        "confidence": 100,
        "publisherCount": 17,
        "marketSession": "regular",
    }, ts_ms=1_700_000_000_000)
    assert tick is not None
    assert tick["feed_id"] == 346
    assert tick["price"] == Decimal("4726.139")
    assert tick["bid"] == Decimal("4726.000")
    assert tick["publisher_count"] == 17
    assert tick["market_session"] == "regular"
    assert tick["ts_ms"] == 1_700_000_000_000


def test_bar_aggregation_same_second(session_factory):
    ing = PythIngestor("pro", session_factory, PythBarPro)
    base_ms = 1_700_000_000_000  # exact second boundary
    for px in (Decimal("100"), Decimal("101"), Decimal("99")):
        ing.handle_tick(
            feed_id=346, symbol="GOLD", price=px,
            bid=None, ask=None, confidence=None,
            publisher_count=None, market_session=None,
            ts_ms=base_ms + 100,
        )
    # Force bar flush by moving to next second
    ing.handle_tick(
        feed_id=346, symbol="GOLD", price=Decimal("102"),
        bid=None, ask=None, confidence=None,
        publisher_count=None, market_session=None,
        ts_ms=base_ms + 1500,
    )
    with session_factory() as s:
        bars = list(s.execute(select(PythBarPro)).scalars())
    assert len(bars) >= 1
    first = [b for b in bars if b.feed_id == 346 and b.tick_count == 3]
    assert first, f"expected a bar with tick_count=3, got {[(b.tick_count) for b in bars]}"
    bar = first[0]
    assert bar.open == Decimal("100")
    assert bar.high == Decimal("101")
    assert bar.low == Decimal("99")
    assert bar.close == Decimal("99")


def test_bar_rollover(session_factory):
    ing = PythIngestor("pro", session_factory, PythBarPro)
    base_ms = 1_700_000_000_000
    ing.handle_tick(346, "GOLD", Decimal("100"), None, None, None, None, None, base_ms)
    ing.handle_tick(346, "GOLD", Decimal("200"), None, None, None, None, None, base_ms + 1100)
    ing.handle_tick(346, "GOLD", Decimal("300"), None, None, None, None, None, base_ms + 2100)
    with session_factory() as s:
        bars = sorted(s.execute(select(PythBarPro)).scalars(), key=lambda b: b.ts)
    assert len(bars) == 2, f"expected 2 flushed bars (3rd still in memory), got {len(bars)}"
    assert bars[0].close == Decimal("100")
    assert bars[1].close == Decimal("200")


def test_prune_ticks(session_factory):
    ing = PythIngestor("pro", session_factory, PythBarPro)
    now_ms = int(time.time() * 1000)
    ing.handle_tick(346, "GOLD", Decimal("100"), None, None, None, None, None, now_ms - 3 * 3600 * 1000)
    ing.handle_tick(346, "GOLD", Decimal("101"), None, None, None, None, None, now_ms)
    with session_factory() as s:
        before = s.scalar(select(PythTickRecent).limit(1))
    assert before is not None
    deleted = ing.prune_ticks()
    assert deleted >= 1
    with session_factory() as s:
        remaining = list(s.execute(select(PythTickRecent)).scalars())
    assert all(r.ts_ms >= now_ms - 7200 * 1000 for r in remaining)


def test_flush_open_bars_persists_current_second(session_factory):
    ing = PythIngestor("pro", session_factory, PythBarPro)
    ing.handle_tick(346, "GOLD", Decimal("100"), None, None, None, None, None, 1_700_000_000_000)
    flushed = ing.flush_open_bars()
    assert flushed == 1
    with session_factory() as s:
        bars = list(s.execute(select(PythBarPro)).scalars())
    assert len(bars) == 1
    assert bars[0].close == Decimal("100")


# --- reconnect / websocket mocking -------------------------------------------


class _FakeWS:
    """Async iterable that yields frames then optionally raises."""

    def __init__(self, frames: list[str], after: Exception | None = None):
        self._frames = list(frames)
        self._after = after
        self.sent: list[str] = []

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._frames:
            return self._frames.pop(0)
        if self._after is not None:
            exc = self._after
            self._after = None
            raise exc
        raise StopAsyncIteration


def _make_connect_factory(*ws_instances: _FakeWS):
    """Returns a context-manager-like connect factory feeding ws_instances in order."""
    queue = list(ws_instances)

    @asynccontextmanager
    async def connect(uri, **_kwargs):
        if not queue:
            raise AssertionError("connect called more times than fake WSes provided")
        ws = queue.pop(0)
        yield ws

    return connect


def _tick_frame(feed_id: int, price_raw: int, exponent: int, ts_us: int) -> str:
    return json.dumps({
        "type": "streamUpdated",
        "subscriptionId": 1,
        "parsed": {
            "timestampUs": str(ts_us),
            "priceFeeds": [{
                "priceFeedId": feed_id,
                "price": str(price_raw),
                "exponent": exponent,
                "bestBidPrice": str(price_raw - 10),
                "bestAskPrice": str(price_raw + 10),
                "confidence": 5,
                "publisherCount": 12,
                "marketSession": "regular",
            }],
        },
    })


async def test_pro_reconnect_backoff_sequence(session_factory, monkeypatch):
    """run_pro should retry with backoff 1,2,4s after connection errors."""
    from core import pyth_ingest as pi
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)
        # third failure: stop loop
        if len(sleeps) >= 3:
            raise asyncio.CancelledError()

    monkeypatch.setattr(pi.asyncio, "sleep", fake_sleep)

    ws1 = _FakeWS([], after=ConnectionError("boom"))
    ws2 = _FakeWS([], after=ConnectionError("boom"))
    ws3 = _FakeWS([], after=ConnectionError("boom"))
    connect_factory = _make_connect_factory(ws1, ws2, ws3)

    with pytest.raises(asyncio.CancelledError):
        await run_pro(
            token="t",
            session_factory=session_factory,
            feeds=active_feeds(),
            connect_factory=connect_factory,
        )
    # first sleep is after first failure: 1s, then 2s, then 4s
    assert sleeps[:3] == [1.0, 2.0, 4.0]


async def test_pro_decodes_and_writes(session_factory):
    """Feed one tick through a fake WS and check it lands in the DB."""
    frame = _tick_frame(feed_id=346, price_raw=4726139, exponent=-3, ts_us=1_700_000_000_000_000)
    ws = _FakeWS([frame])
    connect_factory = _make_connect_factory(ws)

    # Use _run_pro_once directly to avoid reconnect loop.
    from core.pyth_ingest import _run_pro_once
    ing = PythIngestor("pro", session_factory, PythBarPro)

    await _run_pro_once(
        token="t",
        ingestor=ing,
        feeds=[f for f in active_feeds() if f.id == 346],
        connect_factory=connect_factory,
    )

    sent_json = json.loads(ws.sent[0])
    assert sent_json["type"] == "subscribe"
    assert sent_json["channel"] == "fixed_rate@200ms"
    assert 346 in sent_json["priceFeedIds"]

    with session_factory() as s:
        ticks = list(s.execute(select(PythTickRecent)).scalars())
    assert len(ticks) == 1
    assert ticks[0].price == Decimal("4726.139")


async def test_hermes_idles_when_no_hermes_ids(session_factory):
    """run_hermes should idle (not connect) when no feeds have hermes_id."""
    from core.pyth_ingest import run_hermes
    from core.pyth_feeds import Feed
    stop = asyncio.Event()
    feeds = [Feed(id=999, symbol="FAKE", category="crypto", hermes_id=None)]
    task = asyncio.create_task(run_hermes(session_factory, feeds, stop_event=stop))
    await asyncio.sleep(0.05)
    assert not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_decode_hermes_frame_happy_path():
    from core.pyth_ingest import _decode_hermes_frame
    frame = {
        "type": "price_update",
        "price_feed": {
            "id": "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43",
            "price": {
                "price": "7494541000000",
                "conf": "2362000000",
                "expo": -8,
                "publish_time": 1776283284,
            },
            "ema_price": {"price": "0", "conf": "0", "expo": -8, "publish_time": 0},
        },
    }
    tick = _decode_hermes_frame(frame)
    assert tick is not None
    assert tick["feed_id_hex"].startswith("e62df6c8")
    # 7494541000000 * 10^-8 = 74945.41
    assert tick["price"] == Decimal("74945.41000000")
    assert tick["ts_ms"] == 1776283284 * 1000


def test_decode_hermes_frame_rejects_missing_price():
    from core.pyth_ingest import _decode_hermes_frame
    assert _decode_hermes_frame({"type": "price_update", "price_feed": {}}) is None


def test_decode_hermes_frame_rejects_zero_price_closed_market():
    from core.pyth_ingest import _decode_hermes_frame
    # Equity/ETF feeds emit 0 during closed market sessions; must drop.
    frame = {
        "type": "price_update",
        "price_feed": {
            "id": "abc",
            "price": {"price": "0", "conf": "0", "expo": -8, "publish_time": 1},
        },
    }
    assert _decode_hermes_frame(frame) is None


async def test_hermes_decodes_and_writes(session_factory):
    """Feed one Hermes price_update through a fake WS and verify the tick is decoded
    and the symbol is looked up via hermes_id→feed mapping, landing in the DB."""
    from core.pyth_ingest import _run_hermes_once
    from core.pyth_feeds import FEEDS
    btc = FEEDS["BTC"]
    # response frame + one price_update
    ack = json.dumps({"type": "response", "status": "success"})
    update = json.dumps({
        "type": "price_update",
        "price_feed": {
            "id": btc.hermes_id,
            "price": {
                "price": "7494541000000",
                "conf": "2362000000",
                "expo": -8,
                "publish_time": 1776283284,
            },
            "ema_price": {"price": "0", "conf": "0", "expo": -8, "publish_time": 0},
        },
    })
    ws = _FakeWS([ack, update])
    connect_factory = _make_connect_factory(ws)
    ing = PythIngestor("hermes", session_factory, PythBarHermes)
    await _run_hermes_once(ing, [btc], connect_factory=connect_factory)

    sent_sub = json.loads(ws.sent[0])
    assert sent_sub == {"type": "subscribe", "ids": [btc.hermes_id]}

    with session_factory() as s:
        ticks = list(s.execute(select(PythTickRecent)).scalars())
    assert len(ticks) == 1
    assert ticks[0].endpoint == "hermes"
    assert ticks[0].feed_id == btc.id  # stored as Lazer numeric for cross-endpoint join
    assert ticks[0].price == Decimal("74945.41000000")


async def test_hermes_skips_untracked_hex_id(session_factory):
    """An unknown hermes_id should be logged+dropped, not crash the subscriber."""
    from core.pyth_ingest import _run_hermes_once
    from core.pyth_feeds import FEEDS
    btc = FEEDS["BTC"]
    bogus = "00" * 32
    ack = json.dumps({"type": "response", "status": "success"})
    good = json.dumps({
        "type": "price_update",
        "price_feed": {
            "id": btc.hermes_id,
            "price": {"price": "100", "conf": "0", "expo": 0, "publish_time": 1},
            "ema_price": {"price": "0", "conf": "0", "expo": 0, "publish_time": 0},
        },
    })
    bogus_frame = json.dumps({
        "type": "price_update",
        "price_feed": {
            "id": bogus,
            "price": {"price": "100", "conf": "0", "expo": 0, "publish_time": 2},
            "ema_price": {"price": "0", "conf": "0", "expo": 0, "publish_time": 0},
        },
    })
    ws = _FakeWS([ack, bogus_frame, good])
    connect_factory = _make_connect_factory(ws)
    ing = PythIngestor("hermes", session_factory, PythBarHermes)
    await _run_hermes_once(ing, [btc], connect_factory=connect_factory)
    with session_factory() as s:
        ticks = list(s.execute(select(PythTickRecent)).scalars())
    # only the good one landed
    assert len(ticks) == 1
    assert ticks[0].feed_id == btc.id


async def test_run_ingest_raises_when_no_subscriber_can_start(session_factory):
    with pytest.raises(RuntimeError, match="no Pyth subscribers started"):
        await run_ingest(
            session_factory=session_factory,
            token=None,
            feeds=active_feeds(),
            include_pro=True,
            include_hermes=False,
        )
