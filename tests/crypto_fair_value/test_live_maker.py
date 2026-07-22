from __future__ import annotations

import time
from decimal import Decimal

import pytest

from bots.crypto_fair_value.config import load_config
from bots.crypto_fair_value.live_maker import (
    CryptoFVLiveMaker,
    load_live_config,
    startup_authorization_blocker,
)
from bots.crypto_fair_value.model import MarketMeta, Signal
from core.clob import OrderBook, OrderRecord, OrderResponse, Side
from core.db import Event, Order, Position, get_session_factory


class FakeClob:
    paper_override = False

    def __init__(self) -> None:
        self.placed: list[dict] = []

    def _effective_paper(self) -> bool:
        return False

    def get_book(self, token_id: str) -> OrderBook:
        return OrderBook(
            token_id=token_id,
            bids=[(Decimal("0.370"), Decimal("100"))],
            asks=[(Decimal("0.390"), Decimal("100"))],
            timestamp=time.time(),
        )

    def get_tick_size(self, token_id: str) -> Decimal:
        return Decimal("0.001")

    def place_limit(self, *, token_id, price, size, side, order_type, post_only=False) -> OrderResponse:
        self.placed.append(
            {
                "token_id": token_id,
                "price": price,
                "size": size,
                "side": side,
                "order_type": order_type,
                "post_only": post_only,
            }
        )
        return OrderResponse(order_id="fv-live-order-1", status="OPEN", raw={})

    def get_user_orders(self, market_id: str | None = None) -> list[OrderRecord]:
        return []

    def get_user_trades(self):
        return []

    def cancel_order(self, order_id: str) -> bool:
        return True


@pytest.fixture
def live_env(monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    monkeypatch.setenv("CRYPTO_PROB_GAP_LIVE_ENV", "live")
    monkeypatch.setenv("CRYPTO_PROB_GAP_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("CRYPTO_PROB_GAP_LIVE_APPROVED_AT", "2026-05-16")
    monkeypatch.setenv("FLEET_WALLET_USD", "100")


def _meta() -> MarketMeta:
    now_ms = int(time.time() * 1000)
    return MarketMeta(
        condition_id="fv-condition-1",
        question="BTC Up or Down?",
        end_ms=now_ms + 300_000,
        start_ms=now_ms - 60_000,
        symbol="BTC",
        duration_minutes=5,
        yes_token_id="yes-token",
        no_token_id="no-token",
    )


def _signal() -> Signal:
    return Signal(
        strategy="probability_gap",
        condition_id="fv-condition-1",
        symbol="BTC",
        duration_minutes=5,
        side="UP",
        token_id="yes-token",
        ask_price=Decimal("0.390"),
        model_probability_up=0.43,
        model_edge=Decimal("0.040"),
        pm_mid_up=Decimal("0.380"),
        effective_spread=Decimal("0.010"),
        top_depth_usd=Decimal("39"),
        seconds_left=240,
        decision_ms=int(time.time() * 1000),
        cex_move_60s=0.001,
    )


def _runner() -> CryptoFVLiveMaker:
    return CryptoFVLiveMaker(
        clob=FakeClob(),
        signal_config=load_config("probability_gap"),
        live_config=load_live_config("probability_gap"),
    )


def test_startup_blocks_before_wallet_when_not_approved(tmp_db, monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    monkeypatch.setenv("CRYPTO_PROB_GAP_LIVE_ENV", "live")
    monkeypatch.setenv("CRYPTO_PROB_GAP_LIVE_AUTHORIZED", "false")

    live_config = load_live_config("probability_gap")
    assert startup_authorization_blocker(live_config) == "live_not_authorized"

    runner = _runner()
    quote = runner.quote_for_signal(_meta(), _signal())
    assert not isinstance(quote, str)
    with pytest.raises(RuntimeError, match="live_not_authorized"):
        runner.place_quote(quote)
    assert runner.clob.placed == []


def test_live_config_defaults_are_history_sized(monkeypatch):
    prob = load_live_config("probability_gap")
    brownian = load_live_config("brownian_fair_value")

    assert prob.max_order_usd == Decimal("5")
    assert prob.daily_gross_cap_usd == Decimal("250")
    assert prob.open_exposure_cap_usd == Decimal("100")
    assert prob.max_concurrent_positions == 20
    assert brownian.max_order_usd == Decimal("5")
    assert brownian.daily_gross_cap_usd == Decimal("300")
    assert brownian.open_exposure_cap_usd == Decimal("120")
    assert brownian.max_concurrent_positions == 24


def test_places_non_crossing_known_live_order_when_approved(tmp_db, live_env):
    runner = _runner()

    quote = runner.quote_for_signal(_meta(), _signal())

    assert not isinstance(quote, str)
    assert quote.quote_price == Decimal("0.389")
    assert quote.quote_price < quote.best_ask
    assert quote.notional_usd <= Decimal("5")
    response = runner.place_quote(quote)

    assert response.order_id == "fv-live-order-1"
    assert runner.clob.placed == [
        {
            "token_id": "yes-token",
            "price": Decimal("0.389"),
            "size": Decimal("12"),
            "side": Side.BUY,
            "order_type": "GTC",
            "post_only": True,
        }
    ]
    with get_session_factory()() as session:
        order = session.get(Order, "fv-live-order-1")
        assert order is not None
        assert order.bot_id == "crypto_probability_gap_live_maker"
        assert order.status == "OPEN"
        event = session.query(Event).filter_by(
            bot_id="crypto_probability_gap_live_maker",
            event_type="crypto_fv_live_maker.quote_placed",
        ).one()
        assert event.payload["notional_usd"] == "4.67"


def test_open_exposure_cap_blocks_new_quote(tmp_db, live_env, monkeypatch):
    monkeypatch.setenv("CRYPTO_PROB_GAP_LIVE_OPEN_EXPOSURE_CAP_USD", "4")
    with get_session_factory()() as session:
        session.add(
            Position(
                bot_id="crypto_probability_gap_live_maker",
                condition_id="other-condition",
                token_id="other-token",
                side="YES",
                size=Decimal("10"),
                avg_price=Decimal("0.30"),
                cost_basis_usd=Decimal("3.00"),
                status="OPEN",
            )
        )
        session.commit()

    runner = _runner()

    assert runner.quote_for_signal(_meta(), _signal()) == "open_exposure_cap"
