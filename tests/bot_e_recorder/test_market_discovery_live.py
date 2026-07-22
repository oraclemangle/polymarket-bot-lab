"""Regression test for the runtime path of fetch_live_crypto_markets().

Audit 2026-04-16 found a NameError on `vol` — undefined variable referenced
on every market with populated volume24hr. The bug was not caught because
existing tests only covered helper functions in isolation. This test
exercises the full live-discovery code path with a mocked httpx response.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import httpx

from bots.bot_e_recorder.market_discovery import (
    CryptoMarket,
    fetch_live_crypto_markets,
)


def _make_mock_client(payload: list[dict]) -> MagicMock:
    """Mock httpx.Client returning the same payload for every page."""
    client = MagicMock(spec=httpx.Client)
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    client.get.return_value = response
    return client


def _response(payload, *, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_fetch_live_crypto_markets_with_volume_does_not_namerror():
    """The bug: line 199 referenced undefined `vol` instead of `vol_raw`.

    Trigger condition: any market that (a) parses as a crypto Up/Down market,
    (b) has volume24hr above the floor (so the volume-filter doesn't continue),
    AND (c) has tokens parsed successfully — the code reaches the buggy line.
    """
    now = datetime.now(UTC)
    end = now + timedelta(minutes=10)
    payload = [{
        "conditionId": "0xabc123",
        "question": "Bitcoin Up or Down — April 16, 11:30am-11:35am ET",
        "endDate": end.isoformat().replace("+00:00", "Z"),
        "active": True,
        "closed": False,
        "volume24hr": 12345.67,  # populated → trips the previously-broken branch
        "clobTokenIds": json.dumps(["yes_tok_id", "no_tok_id"]),
        "outcomes": json.dumps(["Up", "Down"]),
        "outcomePrices": json.dumps(["0.51", "0.49"]),
    }]
    client = _make_mock_client(payload)
    # Pre-fix this raised NameError on `vol`. Post-fix it returns markets.
    markets = fetch_live_crypto_markets(
        max_minutes_to_res=20.0,
        min_volume_usd=50.0,
        client=client,
        now=now,
    )
    assert isinstance(markets, list)
    # If the symbol-classifier rejected the question we'll get []; that's fine.
    # The critical assertion is "no exception raised" + "function returned".
    if markets:
        m = markets[0]
        assert isinstance(m, CryptoMarket)
        assert m.condition_id == "0xabc123"


def test_fetch_live_crypto_markets_volume_none_does_not_namerror():
    """Same path with volume24hr missing — also previously hit the bug."""
    now = datetime.now(UTC)
    end = now + timedelta(minutes=10)
    payload = [{
        "conditionId": "0xdef456",
        "question": "Bitcoin Up or Down — April 16, 11:30am-11:35am ET",
        "endDate": end.isoformat().replace("+00:00", "Z"),
        "active": True,
        "closed": False,
        # volume24hr deliberately omitted
        "clobTokenIds": json.dumps(["yes_tok_id", "no_tok_id"]),
        "outcomes": json.dumps(["Up", "Down"]),
        "outcomePrices": json.dumps(["0.51", "0.49"]),
    }]
    client = _make_mock_client(payload)
    # Should not raise.
    markets = fetch_live_crypto_markets(
        max_minutes_to_res=20.0,
        min_volume_usd=50.0,
        client=client,
        now=now,
    )
    assert isinstance(markets, list)


def test_fetch_live_crypto_markets_uses_slug_fallback_when_pages_miss_market():
    now = datetime.fromtimestamp(1778847601, UTC)
    end = datetime.fromtimestamp(1778847900, UTC)
    slug_payload = {
        "conditionId": "0xslug",
        "question": "Bitcoin Up or Down - May 15, 8:25AM-8:30AM ET",
        "endDate": end.isoformat().replace("+00:00", "Z"),
        "active": True,
        "closed": False,
        "volume24hr": 403.14,
        "clobTokenIds": json.dumps(["yes_tok_id", "no_tok_id"]),
        "outcomes": json.dumps(["Up", "Down"]),
        "outcomePrices": json.dumps(["0.51", "0.49"]),
    }
    client = MagicMock(spec=httpx.Client)

    def fake_get(url, **kwargs):
        if str(url).endswith("/btc-updown-5m-1778847900"):
            return _response(slug_payload)
        if "/markets/slug/" in str(url):
            return _response({}, status_code=404)
        return _response([])

    client.get.side_effect = fake_get

    markets = fetch_live_crypto_markets(
        max_minutes_to_res=20.0,
        min_volume_usd=50.0,
        client=client,
        now=now,
    )

    assert [market.condition_id for market in markets] == ["0xslug"]
