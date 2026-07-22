"""Tests for core/cex_ws.py."""
from __future__ import annotations

import json

import pytest

from core.cex_ws import BinanceWSSClient, CexTrade


class TestStreamURL:
    def test_single_symbol(self):
        c = BinanceWSSClient(symbols=["BTCUSDT"], on_trade=None)  # type: ignore
        assert "btcusdt@trade" in c._stream_url()
        assert c._stream_url().startswith("wss://stream.binance.com:9443/stream")

    def test_multi_symbol(self):
        c = BinanceWSSClient(
            symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            on_trade=None,  # type: ignore
        )
        url = c._stream_url()
        assert "btcusdt@trade" in url
        assert "ethusdt@trade" in url
        assert "solusdt@trade" in url
        # All three joined by "/"
        assert url.count("@trade") == 3


class TestDispatcher:
    @pytest.mark.asyncio
    async def test_combined_stream_trade_event(self):
        received = []
        async def handler(t: CexTrade) -> None:
            received.append(t)

        c = BinanceWSSClient(symbols=["BTCUSDT"], on_trade=handler)
        # Combined-stream envelope
        raw = json.dumps({
            "stream": "btcusdt@trade",
            "data": {
                "e": "trade",
                "E": 1729000000000,
                "s": "BTCUSDT",
                "t": 123,
                "p": "68500.50",
                "q": "0.0012",
                "T": 1729000000000,
                "m": True,
            },
        })
        await c._dispatch_raw(raw)

        assert len(received) == 1
        t = received[0]
        assert t.symbol == "BTCUSDT"
        assert t.price == 68500.5
        assert t.size == 0.0012
        assert t.trade_time_ms == 1729000000000
        assert t.is_buyer_maker is True
        assert t.received_at_ms > 0

    @pytest.mark.asyncio
    async def test_single_stream_trade_event(self):
        received = []
        async def handler(t: CexTrade) -> None:
            received.append(t)

        c = BinanceWSSClient(symbols=["BTCUSDT"], on_trade=handler)
        # Single-stream format (no envelope)
        raw = json.dumps({
            "e": "trade",
            "s": "BTCUSDT",
            "p": "68000",
            "q": "0.5",
            "T": 1700000000000,
            "m": False,
        })
        await c._dispatch_raw(raw)

        assert len(received) == 1
        assert received[0].price == 68000.0
        assert received[0].size == 0.5
        assert received[0].is_buyer_maker is False

    @pytest.mark.asyncio
    async def test_non_trade_event_ignored(self):
        received = []
        async def handler(t: CexTrade) -> None:
            received.append(t)

        c = BinanceWSSClient(symbols=["BTCUSDT"], on_trade=handler)
        # Subscription ack or other non-trade event
        raw = json.dumps({"result": None, "id": 1})
        await c._dispatch_raw(raw)
        assert received == []

        # Wrong event type
        raw2 = json.dumps({"e": "kline", "s": "BTCUSDT"})
        await c._dispatch_raw(raw2)
        assert received == []

    @pytest.mark.asyncio
    async def test_bad_json_ignored(self):
        received = []
        async def handler(t: CexTrade) -> None:
            received.append(t)

        c = BinanceWSSClient(symbols=["BTCUSDT"], on_trade=handler)
        await c._dispatch_raw("not json {{")
        assert received == []

    @pytest.mark.asyncio
    async def test_malformed_trade_ignored(self):
        received = []
        async def handler(t: CexTrade) -> None:
            received.append(t)

        c = BinanceWSSClient(symbols=["BTCUSDT"], on_trade=handler)
        # Missing required field `s` (symbol)
        raw = json.dumps({"e": "trade", "p": "68000", "q": "0.5", "T": 1700000000000})
        await c._dispatch_raw(raw)
        assert received == []

    @pytest.mark.asyncio
    async def test_handler_exception_does_not_break_client(self):
        call_count = 0
        async def bad_handler(t: CexTrade) -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("deliberate")

        c = BinanceWSSClient(symbols=["BTCUSDT"], on_trade=bad_handler)
        raw = json.dumps({
            "e": "trade", "s": "BTCUSDT", "p": "1", "q": "1", "T": 1,
        })
        # Should not raise
        await c._dispatch_raw(raw)
        await c._dispatch_raw(raw)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_last_message_age(self):
        async def handler(t: CexTrade) -> None:
            pass

        c = BinanceWSSClient(symbols=["BTCUSDT"], on_trade=handler)
        assert c.last_message_age_sec() == 0.0

        raw = json.dumps({
            "e": "trade", "s": "BTCUSDT", "p": "1", "q": "1", "T": 1,
        })
        await c._dispatch_raw(raw)
        assert 0 <= c.last_message_age_sec() < 1.0
