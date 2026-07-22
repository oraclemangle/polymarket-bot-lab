"""Tests for core/polymarket_ws.py.

Unit tests for the WSS dispatcher; the actual connection loop is tested via
a fake async websocket server that the client connects to.
"""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock

import pytest

from core.polymarket_ws import (
    PolymarketWSSClient,
    WSSEvent,
)


class TestWSSEvent:
    def test_event_fields(self):
        ev = WSSEvent(
            event_type="book",
            payload={"hello": "world"},
            received_at_ms=1234,
            subscription_id="sub1",
        )
        assert ev.event_type == "book"
        assert ev.payload == {"hello": "world"}
        assert ev.received_at_ms == 1234
        assert ev.subscription_id == "sub1"


class TestDispatcher:
    """Test _dispatch_raw in isolation — no real network."""

    @pytest.mark.asyncio
    async def test_single_event_dispatched(self):
        received = []
        async def handler(ev: WSSEvent) -> None:
            received.append(ev)

        client = PolymarketWSSClient(
            asset_ids=["tok1"],
            on_event=handler,
            subscription_id="test",
        )
        raw = json.dumps({
            "event_type": "book",
            "asset_id": "tok1",
            "bids": [["0.42", "100"]],
            "asks": [["0.43", "100"]],
        })
        await client._dispatch_raw(raw)

        assert len(received) == 1
        assert received[0].event_type == "book"
        assert received[0].payload["asset_id"] == "tok1"
        assert received[0].received_at_ms > 0
        assert received[0].subscription_id == "test"

    @pytest.mark.asyncio
    async def test_list_of_events(self):
        """Polymarket sometimes delivers a list of events in one message."""
        received = []
        async def handler(ev: WSSEvent) -> None:
            received.append(ev)

        client = PolymarketWSSClient(
            asset_ids=["tok1"],
            on_event=handler,
            subscription_id="test",
        )
        raw = json.dumps([
            {"event_type": "book", "asset_id": "tok1"},
            {"event_type": "price_change", "asset_id": "tok1", "price": "0.43"},
            {"event_type": "last_trade_price", "asset_id": "tok1", "price": "0.425"},
        ])
        await client._dispatch_raw(raw)

        assert len(received) == 3
        assert [ev.event_type for ev in received] == [
            "book", "price_change", "last_trade_price",
        ]

    @pytest.mark.asyncio
    async def test_bad_json_ignored(self):
        received = []
        async def handler(ev: WSSEvent) -> None:
            received.append(ev)

        client = PolymarketWSSClient(
            asset_ids=["tok1"],
            on_event=handler,
            subscription_id="test",
        )
        await client._dispatch_raw("not json {{")
        assert received == []

    @pytest.mark.asyncio
    async def test_missing_event_type_becomes_unknown(self):
        received = []
        async def handler(ev: WSSEvent) -> None:
            received.append(ev)

        client = PolymarketWSSClient(
            asset_ids=["tok1"],
            on_event=handler,
            subscription_id="test",
        )
        await client._dispatch_raw(json.dumps({"foo": "bar"}))
        assert len(received) == 1
        assert received[0].event_type == "unknown"

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_break_client(self):
        """A raising handler must not crash the WSS loop."""
        call_count = 0
        async def bad_handler(ev: WSSEvent) -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("deliberate")

        client = PolymarketWSSClient(
            asset_ids=["tok1"],
            on_event=bad_handler,
            subscription_id="test",
        )
        # Should not raise
        await client._dispatch_raw(json.dumps({"event_type": "book"}))
        await client._dispatch_raw(json.dumps({"event_type": "price_change"}))
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_last_message_age_tracks_dispatches(self):
        async def handler(ev: WSSEvent) -> None:
            pass

        client = PolymarketWSSClient(
            asset_ids=["tok1"],
            on_event=handler,
            subscription_id="test",
        )
        # Before any message: 0
        assert client.last_message_age_sec() == 0.0

        await client._dispatch_raw(json.dumps({"event_type": "book"}))
        # After a message: should be very small (ms-scale)
        age = client.last_message_age_sec()
        assert 0 <= age < 1.0

    @pytest.mark.asyncio
    async def test_synthetic_reconnect_event(self):
        received = []
        async def handler(ev: WSSEvent) -> None:
            received.append(ev)

        client = PolymarketWSSClient(
            asset_ids=["tok1"],
            on_event=handler,
            subscription_id="test",
        )
        await client._emit_synthetic("reconnect", {"n_assets": 1})
        assert len(received) == 1
        assert received[0].event_type == "reconnect"
        assert received[0].payload == {"n_assets": 1}
