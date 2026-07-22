"""Tests for discovery parsing and strategy evaluation."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from bots.bot_c_pyth.discovery import (
    ParsedMarket,
    _extract_yes_no_tokens,
    _extract_yes_price,
    parse_question,
)
from bots.bot_c_pyth.strategy import evaluate_market, gbm_prob_above


def _market(symbol, direction, lo, hi, hours, yes_price=0.5):
    return ParsedMarket(
        gamma_id="g1", slug="s", question="q", symbol=symbol,
        direction=direction, strike_low=Decimal(str(lo)),
        strike_high=Decimal(str(hi)) if hi is not None else None,
        resolution_date=datetime.now(UTC) + timedelta(hours=hours),
        yes_token_id="y", no_token_id="n",
        yes_price=Decimal(str(yes_price)), volume_24h_usd=Decimal("1000"),
    )


def test_parse_weekly_hit_low():
    r = parse_question("Will Tesla, Inc. (TSLA) hit (LOW) $337.50 Week of April 13 2026?")
    assert r is not None
    assert r["symbol"] == "TSLA"
    assert r["direction"] == "below"
    assert r["strike_low"] == Decimal("337.50")


def test_parse_weekly_hit_high():
    r = parse_question("Will Apple (AAPL) hit (HIGH) $252 Week of April 13 2026?")
    assert r is not None
    assert r["symbol"] == "AAPL"
    assert r["direction"] == "above"
    assert r["strike_low"] == Decimal("252")


def test_parse_weekly_finish():
    r = parse_question("Will NVIDIA (NVDA) finish week of April 13 above $175?")
    assert r is not None
    assert r["symbol"] == "NVDA" and r["direction"] == "above"
    assert r["strike_low"] == Decimal("175")


def test_parse_eom_hit():
    r = parse_question("Will Gold (GC) hit (HIGH) $9,000 by end of June?")
    assert r is not None and r["symbol"] == "GOLD" and r["direction"] == "above"
    assert r["strike_low"] == Decimal("9000")


def test_parse_month_settle():
    r = parse_question(
        "Will Silver (SI) settle over $60 on the final trading day of June 2026?"
    )
    assert r is not None and r["symbol"] == "SILVER" and r["direction"] == "above"


def test_parse_crypto_between_month():
    r = parse_question("Will the price of Bitcoin be between $95,000 and $100,000 in April?")
    assert r is not None
    assert r["symbol"] == "BTC" and r["direction"] == "between"
    assert r["strike_low"] == Decimal("95000")
    assert r["strike_high"] == Decimal("100000")


def test_parse_crypto_between_date():
    r = parse_question("Will the price of Solana be between $70 and $80 on April 15?")
    assert r is not None and r["symbol"] == "SOL" and r["direction"] == "between"


def test_parse_unrelated_returns_none():
    assert parse_question("Will Trump win the 2028 primary?") is None
    assert parse_question("Random nonsense about nothing") is None


def test_extract_yes_no_tokens_from_json_strings():
    m = {"clobTokenIds": '["111","222"]', "outcomes": '["Yes","No"]'}
    assert _extract_yes_no_tokens(m) == ("111", "222")


def test_extract_yes_no_tokens_from_lists():
    m = {"clobTokenIds": ["aaa", "bbb"], "outcomes": ["No", "Yes"]}
    # Yes is index 1 -> token "bbb"
    assert _extract_yes_no_tokens(m) == ("bbb", "aaa")


def test_extract_yes_price_outcome_prices():
    m = {"outcomes": '["Yes","No"]', "outcomePrices": '["0.42","0.58"]'}
    assert _extract_yes_price(m) == Decimal("0.42")


def test_gbm_sanity_near_50pct():
    p = gbm_prob_above(100.0, 100.0, 0.25, 1.0)
    assert 0.3 < p < 0.7


def test_gbm_far_in_money_near_1():
    p = gbm_prob_above(200.0, 100.0, 0.20, 0.01)  # 3.6 days
    assert p > 0.95


def test_gbm_far_out_money_near_0():
    p = gbm_prob_above(50.0, 100.0, 0.20, 0.01)
    assert p < 0.05


def test_evaluate_skip_when_edge_small():
    m = _market("NVDA", "above", 100, None, 24, yes_price=0.55)
    dec = evaluate_market(m, spot=Decimal("100"), sigma_ann=0.25, edge_threshold=0.10)
    assert dec.side == "SKIP"


def test_evaluate_buy_yes_when_model_higher():
    m = _market("NVDA", "above", 100, None, 24 * 30, yes_price=0.20)
    dec = evaluate_market(m, spot=Decimal("150"), sigma_ann=0.20, edge_threshold=0.10)
    assert dec.side == "BUY_YES"
    assert dec.edge > 0.1


def test_evaluate_buy_no_when_model_lower():
    m = _market("NVDA", "above", 200, None, 24 * 30, yes_price=0.80)
    dec = evaluate_market(m, spot=Decimal("100"), sigma_ann=0.20, edge_threshold=0.10)
    assert dec.side == "BUY_NO"
    assert dec.edge < -0.1


def test_evaluate_handles_between():
    m = _market("BTC", "between", 90000, 100000, 24 * 7, yes_price=0.30)
    dec = evaluate_market(m, spot=Decimal("95000"), sigma_ann=0.60, edge_threshold=0.05)
    # spot sits mid-range; short horizon; high vol → should be above 30% model p_yes
    assert dec.side in ("BUY_YES", "SKIP")
