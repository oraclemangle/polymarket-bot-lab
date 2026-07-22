"""Tests for bot_e_recorder/market_discovery.py (pure-function parsers)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from bots.bot_e_recorder.market_discovery import (
    _classify_symbol,
    _extract_tokens,
    _extract_yes_price,
    _infer_duration_minutes,
    _is_crypto_updown,
    _parse_end_date,
    _slug_candidates,
)


class TestClassifySymbol:
    def test_btc(self):
        assert _classify_symbol("Up or down on BTC for the period ending...") == "BTC"
        assert _classify_symbol("bitcoin up or down?") == "BTC"

    def test_eth(self):
        assert _classify_symbol("ETH up or down") == "ETH"
        assert _classify_symbol("will ethereum go up") == "ETH"

    def test_sol(self):
        assert _classify_symbol("SOL up or down") == "SOL"
        assert _classify_symbol("solana price") == "SOL"

    def test_xrp(self):
        assert _classify_symbol("XRP up or down") == "XRP"
        assert _classify_symbol("Ripple Up or Down - May 2") == "XRP"

    def test_doge(self):
        assert _classify_symbol("DOGE up or down") == "DOGE"
        assert _classify_symbol("Dogecoin Up or Down - May 2") == "DOGE"

    def test_no_symbol(self):
        assert _classify_symbol("Will Taylor Swift announce a new album?") is None
        assert _classify_symbol("weather in NYC") is None


class TestIsCryptoUpdown:
    def test_matches_btc_updown(self):
        assert _is_crypto_updown("Up or down on BTC for the period ending Apr 17 3pm?") is True

    def test_matches_will_eth_go_up(self):
        assert _is_crypto_updown("Will ETH go up in the next 15 minutes?") is True

    def test_matches_xrp_doge_updown(self):
        assert _is_crypto_updown("XRP Up or Down - May 2, 4:45PM-5:00PM ET") is True
        assert _is_crypto_updown("Dogecoin Up or Down - May 2, 4:45PM-5:00PM ET") is True

    def test_rejects_non_crypto(self):
        assert _is_crypto_updown("Will USD/JPY be above 150 today?") is False

    def test_rejects_no_updown(self):
        assert _is_crypto_updown("BTC price at 3pm EST") is False


class TestExtractTokens:
    def test_list_tokens(self):
        m = {"clobTokenIds": ["tok_yes", "tok_no"]}
        assert _extract_tokens(m) == ("tok_yes", "tok_no")

    def test_json_string_tokens(self):
        m = {"clobTokenIds": json.dumps(["tok_yes", "tok_no"])}
        assert _extract_tokens(m) == ("tok_yes", "tok_no")

    def test_bad_shape(self):
        assert _extract_tokens({"clobTokenIds": "notalist"}) is None
        assert _extract_tokens({}) is None
        assert _extract_tokens({"clobTokenIds": ["only_one"]}) is None


class TestParseEndDate:
    def test_z_suffix(self):
        m = {"endDate": "2026-04-17T15:15:00Z"}
        dt = _parse_end_date(m)
        assert dt is not None
        assert dt.tzinfo is not None
        assert dt.year == 2026 and dt.month == 4 and dt.day == 17

    def test_offset(self):
        m = {"endDate": "2026-04-17T15:15:00+00:00"}
        assert _parse_end_date(m) is not None

    def test_snake_case_key(self):
        m = {"end_date": "2026-04-17T15:15:00Z"}
        assert _parse_end_date(m) is not None

    def test_missing(self):
        assert _parse_end_date({}) is None

    def test_bad_format(self):
        assert _parse_end_date({"endDate": "not a date"}) is None


class TestExtractYesPrice:
    def test_list_of_strings(self):
        from decimal import Decimal
        m = {"outcomePrices": ["0.45", "0.55"]}
        assert _extract_yes_price(m) == Decimal("0.45")

    def test_json_string(self):
        from decimal import Decimal
        m = {"outcomePrices": json.dumps(["0.45", "0.55"])}
        assert _extract_yes_price(m) == Decimal("0.45")

    def test_missing(self):
        assert _extract_yes_price({}) is None

    def test_empty(self):
        assert _extract_yes_price({"outcomePrices": []}) is None


class TestInferDurationMinutes:
    def test_5_min_range(self):
        assert _infer_duration_minutes("Bitcoin Up or Down - May 3, 2:25PM-2:30PM ET") == 5

    def test_15_min_range(self):
        assert _infer_duration_minutes("Ethereum Up or Down - May 4, 4:45PM-5:00PM ET") == 15

    def test_explicit_minute_label(self):
        assert _infer_duration_minutes("Bitcoin Up or Down 15 Min") == 15
        assert _infer_duration_minutes("Bitcoin Up or Down 5 minute") == 5

    def test_unknown_duration(self):
        assert _infer_duration_minutes("Bitcoin Up or Down today?") is None


class TestSlugCandidates:
    def test_near_term_btc_eth_sol_5m_and_15m_slugs(self):
        now = datetime.fromtimestamp(1778847601, UTC)

        slugs = _slug_candidates(now, max_minutes_to_res=20)

        assert "btc-updown-5m-1778847900" in slugs
        assert "eth-updown-5m-1778847900" in slugs
        assert "sol-updown-5m-1778847900" in slugs
        assert "btc-updown-15m-1778848200" in slugs
        assert all("xrp" not in slug and "doge" not in slug for slug in slugs)
