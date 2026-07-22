"""Shared Polymarket WSS client.

Subscribes to the public market channel on the CLOB WSS endpoint and emits
typed events via a pluggable callback. Used by:

- `bots/bot_e_recorder/` — captures every event with local receipt timestamps
  for later replay (ADR-022 Phase 0b).
- `bots/bot_e_btc_scalp/` — consumes events live for signal generation
  (ADR-022 Phase 1).

Endpoint (verified 2026-04-16): `wss://ws-subscriptions-clob.polymarket.com/ws/market`
Subscribe message: `{"type": "market", "assets_ids": [...], "custom_feature_enabled": true}`
Event types: `book`, `price_change`, `last_trade_price`, `best_bid_ask`,
             `new_market`, `market_resolved`, `tick_size_change`

Resilience (per Grok S5 / Codex C-S5):
- Exponential backoff on reconnect (1s → 2s → 4s → … → 60s cap)
- Per-connection heartbeat tracking so callers can detect silent stalls
- Ping interval via `websockets` built-in keepalive
- On reconnect, re-subscribe and emit a synthetic `reconnect` event so
  downstream state machines can invalidate stale data

No order placement here. This module is read-only.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Iterable

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

log = logging.getLogger(__name__)

POLYMARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Exponential backoff: start at 1s, cap at 60s.
BACKOFF_INITIAL_SEC = 1.0
BACKOFF_MAX_SEC = 60.0
BACKOFF_MULTIPLIER = 2.0

# Heartbeat: if no message in this long, caller will typically treat the feed
# as stale. We don't halt here — just expose it. Matches spec's 500ms stale
# threshold * ~600 to convert to "definitely dead" vs "briefly quiet".
SILENT_SECONDS_WARN = 30.0

# Ping via websockets library (keeps TCP alive through proxies).
WSS_PING_INTERVAL = 20.0
WSS_PING_TIMEOUT = 15.0


@dataclass
class WSSEvent:
    """One message from the Polymarket WSS, with local receipt timestamp."""
    event_type: str                    # e.g. "book", "price_change", "last_trade_price"
    payload: dict                      # raw JSON body
    received_at_ms: int                # local UTC ms at receipt
    subscription_id: str               # which subscription this event belongs to
    # For reconnects and health events, a synthetic event type is used:
    #   "reconnect"   — we just reconnected, re-subscribed; downstream should invalidate state
    #   "disconnect"  — connection dropped, about to reconnect
    #   "heartbeat"   — emitted periodically so callers see liveness even during quiet markets


@dataclass
class PolymarketWSSClient:
    """Async WSS client for Polymarket's market channel.

    Usage:
        client = PolymarketWSSClient(
            asset_ids=["tok1", "tok2"],
            on_event=my_async_handler,
            subscription_id="bot_e_recorder/BTC-2026-04-17-12:00",
        )
        await client.run()  # blocks; handles reconnects internally

    The client never raises from `run()`; all errors are logged and trigger
    an internal reconnect. Cancel the task to shut down cleanly.
    """
    asset_ids: list[str]
    on_event: Callable[[WSSEvent], Awaitable[None]]
    subscription_id: str
    custom_feature_enabled: bool = True
    url: str = POLYMARKET_WS_URL

    # State (not constructor args; set during run)
    _last_message_ms: int = field(default=0, init=False)
    _connection_started_ms: int = field(default=0, init=False)
    _closed: bool = field(default=False, init=False)

    def last_message_age_sec(self) -> float:
        """Seconds since last message (any event). Caller uses for stale-feed halts."""
        if self._last_message_ms == 0:
            return 0.0
        return (time.time() * 1000 - self._last_message_ms) / 1000.0

    async def close(self) -> None:
        """Request the run loop to stop on next iteration."""
        self._closed = True

    async def run(self) -> None:
        """Main loop. Blocks; reconnects forever until close() is called."""
        backoff = BACKOFF_INITIAL_SEC
        while not self._closed:
            try:
                await self._run_once()
                # Normal disconnect — reset backoff for next attempt
                backoff = BACKOFF_INITIAL_SEC
            except asyncio.CancelledError:
                log.info("polymarket_ws.cancelled subscription_id=%s", self.subscription_id)
                raise
            except (ConnectionClosed, WebSocketException) as exc:
                log.warning(
                    "polymarket_ws.reconnect subscription_id=%s reason=%s backoff=%.1fs",
                    self.subscription_id, type(exc).__name__, backoff,
                )
            except Exception as exc:
                log.error(
                    "polymarket_ws.unexpected subscription_id=%s error=%s backoff=%.1fs",
                    self.subscription_id, exc, backoff, exc_info=True,
                )

            if self._closed:
                break
            await self._emit_synthetic("disconnect", {"next_backoff_sec": backoff})
            await asyncio.sleep(backoff)
            backoff = min(backoff * BACKOFF_MULTIPLIER, BACKOFF_MAX_SEC)

    async def _run_once(self) -> None:
        """Single connection lifecycle: connect → subscribe → receive loop."""
        async with websockets.connect(
            self.url,
            ping_interval=WSS_PING_INTERVAL,
            ping_timeout=WSS_PING_TIMEOUT,
        ) as ws:
            self._connection_started_ms = int(time.time() * 1000)
            self._last_message_ms = self._connection_started_ms

            # Subscribe
            sub = {
                "type": "market",
                "assets_ids": self.asset_ids,
                "custom_feature_enabled": self.custom_feature_enabled,
            }
            await ws.send(json.dumps(sub))
            log.info(
                "polymarket_ws.subscribed subscription_id=%s n_assets=%d",
                self.subscription_id, len(self.asset_ids),
            )

            # Synthetic reconnect event — downstream state machines invalidate here.
            await self._emit_synthetic("reconnect", {
                "n_assets": len(self.asset_ids),
                "connection_started_ms": self._connection_started_ms,
            })

            async for raw in ws:
                await self._dispatch_raw(raw)

    async def _dispatch_raw(self, raw: str | bytes) -> None:
        """Parse a raw message and emit typed events."""
        now_ms = int(time.time() * 1000)
        self._last_message_ms = now_ms
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            log.warning("polymarket_ws.bad_json subscription_id=%s", self.subscription_id)
            return

        # The market channel sends either a list of events or a single event.
        # Normalize to a list.
        events = body if isinstance(body, list) else [body]
        for ev in events:
            if not isinstance(ev, dict):
                continue
            event_type = str(ev.get("event_type") or "unknown")
            try:
                await self.on_event(WSSEvent(
                    event_type=event_type,
                    payload=ev,
                    received_at_ms=now_ms,
                    subscription_id=self.subscription_id,
                ))
            except Exception as exc:
                log.error(
                    "polymarket_ws.handler_error subscription_id=%s event_type=%s: %s",
                    self.subscription_id, event_type, exc,
                    exc_info=True,
                )

    async def _emit_synthetic(self, event_type: str, payload: dict) -> None:
        """Emit a synthetic event (reconnect / disconnect / heartbeat) to the handler."""
        now_ms = int(time.time() * 1000)
        try:
            await self.on_event(WSSEvent(
                event_type=event_type,
                payload=payload,
                received_at_ms=now_ms,
                subscription_id=self.subscription_id,
            ))
        except Exception as exc:
            log.error(
                "polymarket_ws.synthetic_error subscription_id=%s event_type=%s: %s",
                self.subscription_id, event_type, exc,
            )


async def run_multi(
    asset_groups: Iterable[tuple[str, list[str]]],
    on_event: Callable[[WSSEvent], Awaitable[None]],
) -> None:
    """Run multiple independent WSS clients concurrently.

    Useful when subscribing to separate asset groups (e.g. one group per
    expiring 15-min market). Polymarket docs recommend keeping subscription
    size modest per connection.
    """
    clients = [
        PolymarketWSSClient(
            asset_ids=ids, on_event=on_event, subscription_id=name,
        )
        for name, ids in asset_groups
    ]
    tasks = [asyncio.create_task(c.run()) for c in clients]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
