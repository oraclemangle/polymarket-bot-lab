"""Shared CEX (Binance) WSS client for reference BTC/ETH/SOL prices.

Used by:
- `bots/bot_e_recorder/` — captures trade ticks alongside Polymarket WSS so
  replay can bucket OBI signals by concurrent CEX price movement.
- `bots/bot_e_btc_scalp/` — eventually as a secondary price source; primary
  for Phase 1 is Chainlink (see `core/chainlink_source.py`).

Binance public stream endpoint: `wss://stream.binance.com:9443/ws/<symbol>@trade`
Example for BTC/USDT: `wss://stream.binance.com:9443/ws/btcusdt@trade`

Combined stream endpoint supports multiple symbols in one connection:
`wss://stream.binance.com:9443/stream?streams=btcusdt@trade/ethusdt@trade/solusdt@trade`

Trade message schema (per Binance docs):
{
  "e": "trade",           // event type
  "E": 1729000000000,     // event time (ms)
  "s": "BTCUSDT",         // symbol
  "t": 12345,             // trade id
  "p": "68500.00",        // price
  "q": "0.001",           // qty
  "T": 1729000000000,     // trade time (ms)
  "m": true               // buyer is market maker (true = sell side took)
}

Resilience: same exponential backoff as `core/polymarket_ws.py` (1s→2s→…→60s).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

log = logging.getLogger(__name__)

BINANCE_WS_URL = "wss://stream.binance.com:9443"

# Keep same exponential-backoff constants as polymarket_ws for consistency.
BACKOFF_INITIAL_SEC = 1.0
BACKOFF_MAX_SEC = 60.0
BACKOFF_MULTIPLIER = 2.0

WSS_PING_INTERVAL = 20.0
WSS_PING_TIMEOUT = 15.0


@dataclass
class CexTrade:
    """One trade tick from a CEX, with local receipt timestamp."""
    symbol: str                 # "BTCUSDT", "ETHUSDT", "SOLUSDT"
    price: float                # last trade price
    size: float                 # quantity in base asset
    trade_time_ms: int          # exchange trade timestamp
    received_at_ms: int         # local UTC ms at receipt
    is_buyer_maker: bool        # True if the market-taker was a seller
    raw: dict = field(default_factory=dict)


@dataclass
class BinanceWSSClient:
    """Async WSS client for Binance combined trade streams.

    Usage:
        client = BinanceWSSClient(
            symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            on_trade=my_async_handler,
        )
        await client.run()

    The client never raises from `run()`. Cancel to stop.
    """
    symbols: list[str]
    on_trade: Callable[[CexTrade], Awaitable[None]]
    url: str = BINANCE_WS_URL

    _last_message_ms: int = field(default=0, init=False)
    _closed: bool = field(default=False, init=False)

    def last_message_age_sec(self) -> float:
        if self._last_message_ms == 0:
            return 0.0
        return (time.time() * 1000 - self._last_message_ms) / 1000.0

    async def close(self) -> None:
        self._closed = True

    def _stream_url(self) -> str:
        streams = "/".join(f"{s.lower()}@trade" for s in self.symbols)
        return f"{self.url}/stream?streams={streams}"

    async def run(self) -> None:
        backoff = BACKOFF_INITIAL_SEC
        while not self._closed:
            try:
                await self._run_once()
                backoff = BACKOFF_INITIAL_SEC
            except asyncio.CancelledError:
                log.info("cex_ws.cancelled symbols=%s", self.symbols)
                raise
            except (ConnectionClosed, WebSocketException) as exc:
                log.warning(
                    "cex_ws.reconnect symbols=%s reason=%s backoff=%.1fs",
                    self.symbols, type(exc).__name__, backoff,
                )
            except Exception as exc:
                log.error(
                    "cex_ws.unexpected symbols=%s error=%s backoff=%.1fs",
                    self.symbols, exc, backoff, exc_info=True,
                )
            if self._closed:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * BACKOFF_MULTIPLIER, BACKOFF_MAX_SEC)

    async def _run_once(self) -> None:
        async with websockets.connect(
            self._stream_url(),
            ping_interval=WSS_PING_INTERVAL,
            ping_timeout=WSS_PING_TIMEOUT,
        ) as ws:
            self._last_message_ms = int(time.time() * 1000)
            log.info("cex_ws.connected symbols=%s", self.symbols)
            async for raw in ws:
                await self._dispatch_raw(raw)

    async def _dispatch_raw(self, raw: str | bytes) -> None:
        """Parse combined-stream envelope and emit CexTrade events.

        Combined stream wraps each event as {"stream": "...", "data": {...}}.
        Single-stream mode sends the raw event.
        """
        now_ms = int(time.time() * 1000)
        self._last_message_ms = now_ms
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("cex_ws.bad_json symbols=%s", self.symbols)
            return

        # Normalize single vs combined stream format
        data = body.get("data") if isinstance(body, dict) and "data" in body else body
        if not isinstance(data, dict):
            return
        if data.get("e") != "trade":
            # Ignore non-trade events (subscription acks, etc.)
            return
        try:
            trade = CexTrade(
                symbol=str(data["s"]),
                price=float(data["p"]),
                size=float(data["q"]),
                trade_time_ms=int(data["T"]),
                received_at_ms=now_ms,
                is_buyer_maker=bool(data.get("m", False)),
                raw=data,
            )
        except (KeyError, ValueError, TypeError) as exc:
            log.warning("cex_ws.bad_trade_shape symbols=%s error=%s", self.symbols, exc)
            return

        try:
            await self.on_trade(trade)
        except Exception as exc:
            log.error(
                "cex_ws.handler_error symbol=%s error=%s",
                trade.symbol, exc, exc_info=True,
            )
