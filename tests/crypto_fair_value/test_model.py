from __future__ import annotations

from decimal import Decimal

from bots.crypto_fair_value.model import (
    BookSide,
    BookState,
    CexState,
    MarketMeta,
    brownian_fair_value_signal,
    probability_gap_signal,
    probability_up,
)


def _meta() -> MarketMeta:
    return MarketMeta(
        condition_id="cond-1",
        question="Bitcoin Up or Down - May 6, 1:00PM-1:05PM ET",
        end_ms=1_000_000,
        start_ms=700_000,
        symbol="BTC",
        duration_minutes=5,
        yes_token_id="yes",
        no_token_id="no",
    )


def _book(yes_ask: str = "0.45", no_ask: str = "0.58") -> BookState:
    return BookState(
        yes=BookSide("yes", Decimal("0.43"), Decimal(yes_ask), Decimal("100"), 999_000),
        no=BookSide("no", Decimal("0.56"), Decimal(no_ask), Decimal("100"), 999_000),
    )


def test_probability_up_clamps_and_moves_with_spot():
    assert probability_up(current=100, start=100, seconds_left=60, realized_vol_tick=0.001) == 0.5
    assert probability_up(current=101, start=100, seconds_left=60, realized_vol_tick=0.001) > 0.99
    assert probability_up(current=99, start=100, seconds_left=60, realized_vol_tick=0.001) < 0.01


def test_probability_gap_signal_buys_side_with_model_edge():
    sig = probability_gap_signal(
        meta=_meta(),
        book=_book(yes_ask="0.70", no_ask="0.15"),
        cex=CexState("BTCUSDT", 100.0, 99.0, 999_000, 0.001, -0.002),
        decision_ms=970_000,
        min_edge=Decimal("0.07"),
        min_price=Decimal("0.03"),
        max_price=Decimal("0.85"),
    )
    assert sig is not None
    assert sig.side == "DOWN"
    assert sig.model_edge >= Decimal("0.07")


def test_brownian_signal_requires_mid_gap_and_entry_edge():
    no_gap = brownian_fair_value_signal(
        meta=_meta(),
        book=_book(yes_ask="0.50", no_ask="0.50"),
        cex=CexState("BTCUSDT", 100.0, 100.0, 999_000, 0.001, 0.0),
        decision_ms=970_000,
        min_model_mid_gap=Decimal("0.04"),
        min_entry_edge=Decimal("0.03"),
        min_price=Decimal("0.03"),
        max_price=Decimal("0.85"),
    )
    assert no_gap is None

    sig = brownian_fair_value_signal(
        meta=_meta(),
        book=_book(yes_ask="0.35", no_ask="0.68"),
        cex=CexState("BTCUSDT", 100.0, 100.5, 999_000, 0.002, 0.001),
        decision_ms=970_000,
        min_model_mid_gap=Decimal("0.04"),
        min_entry_edge=Decimal("0.03"),
        min_price=Decimal("0.03"),
        max_price=Decimal("0.85"),
    )
    assert sig is not None
    assert sig.side == "UP"
