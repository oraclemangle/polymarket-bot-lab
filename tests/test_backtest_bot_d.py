from __future__ import annotations

from core.backtest_bot_d import BotDTrade, _parse_weather_question, _select_backtest_trades


def _trade(
    condition_id: str,
    *,
    city: str = "NYC",
    date_iso: str = "2026-04-16",
    side: str = "BUY_NO",
    net_edge: float = -0.20,
    pnl_usd: float = 190.0,
) -> BotDTrade:
    return BotDTrade(
        condition_id=condition_id,
        question="q",
        city=city,
        date_iso=date_iso,
        temp_type="high",
        entry_ts=0,
        side=side,
        entry_price=0.05,
        size_usd=10.0,
        exit_price=1.0,
        pnl_usd=pnl_usd,
        model_prob=0.01,
        market_prob=0.95,
        net_edge=net_edge,
        exit_reason="resolution",
    )


def test_backtest_parser_uses_reference_year_not_current_rollover():
    parsed = _parse_weather_question(
        "Will the highest temperature in New York City be between 86-87°F on April 15?",
        reference_year=2026,
    )
    assert parsed is not None
    assert parsed.city == "NYC"
    assert parsed.date_iso == "2026-04-15"
    assert parsed.range_low_f == 86.0
    assert parsed.range_high_f == 87.0


def test_backtest_parser_supports_or_below():
    parsed = _parse_weather_question(
        "Will the highest temperature in Houston be 79°F or below on April 17?",
        reference_year=2026,
    )
    assert parsed is not None
    assert parsed.city == "Houston"
    assert parsed.range_low_f is None
    assert parsed.range_high_f == 79.0


def test_backtest_wave_selector_keeps_full_size_cluster_and_halves_isolated():
    trades = [
        _trade("a", city="NYC"),
        _trade("b", city="Chicago"),
        _trade("c", city="Dallas"),
        _trade("d", city="Tokyo", date_iso="2026-04-17", pnl_usd=-10.0),
    ]
    selected = _select_backtest_trades(
        trades,
        one_bet_per_event=True,
        wave_filter=True,
        wave_min_markets=3,
        isolated_size_factor=0.5,
        require_wave=False,
    )
    by_id = {t.condition_id: t for t in selected}
    assert {by_id[k].regime for k in ("a", "b", "c")} == {"wave"}
    assert by_id["a"].size_usd == 10.0
    assert by_id["d"].regime == "isolated"
    assert by_id["d"].size_usd == 5.0
    assert by_id["d"].pnl_usd == -5.0


def test_backtest_wave_selector_can_drop_isolated():
    selected = _select_backtest_trades(
        [_trade("a")],
        one_bet_per_event=True,
        wave_filter=True,
        wave_min_markets=3,
        isolated_size_factor=0.5,
        require_wave=True,
    )
    assert selected == []
