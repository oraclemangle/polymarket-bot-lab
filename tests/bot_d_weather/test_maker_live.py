"""Tests for Bot D maker live probe."""
from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bots.bot_d_weather.discovery import WeatherMarket
from bots.bot_d_weather.strategy import WeatherEdgeDecision
from core.clob import OrderBook, OrderResponse
from core.db import Base, Event, Order


@pytest.fixture
def sf():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


class FakeClob:
    paper_override = False

    def __init__(self, *, bid="0.700", ask="0.780"):
        self.book = OrderBook(
            token_id="tok-no",
            bids=[(Decimal(bid), Decimal("100"))],
            asks=[(Decimal(ask), Decimal("100"))],
            timestamp=datetime.now(UTC).timestamp(),
        )
        self.placed = []
        self.cancelled = []

    def _effective_paper(self):
        return False

    def get_tick_size(self, _token_id):
        return Decimal("0.001")

    def get_book(self, _token_id):
        return self.book

    def get_user_orders(self):
        return []

    def get_user_trades(self, since=None):
        return []

    def cancel_order(self, order_id):
        self.cancelled.append(order_id)
        return True

    def place_limit(self, token_id, price, size, side, order_type):
        self.placed.append((token_id, price, size, side, order_type))
        return OrderResponse("maker-order-1", "OPEN", {"ok": True})


def _reload(monkeypatch):
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    monkeypatch.setenv("BOT_D_MAKER_ENV", "live")
    monkeypatch.setenv("BOT_D_MAKER_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_MAKER_LIVE_APPROVED_AT", "2026-05-15")
    monkeypatch.setenv("BOT_D_MAKER_MAX_ORDER_USD", "10")
    monkeypatch.setenv("BOT_D_MAKER_MIN_NOTIONAL_USD", "5")
    monkeypatch.setenv("BOT_D_MAKER_MAX_DAILY_GROSS_USD", "100")
    monkeypatch.setenv("BOT_D_MAKER_MAX_OPEN_EXPOSURE_USD", "100")
    monkeypatch.setenv("BOT_D_MAKER_MIN_EDGE", "0.02")
    import bots.bot_d_weather.maker_live as maker_live
    return importlib.reload(maker_live)


def _decision(gamma_id="maker-c1", side="BUY_NO", yes_price="0.20", gfs=0.10, end_date=None):
    if end_date is None:
        end_date = datetime.now(UTC) + timedelta(hours=8)
    market = WeatherMarket(
        gamma_id=gamma_id,
        slug="slug",
        question="Will the highest temperature in NYC be between 80-81°F on May 15?",
        city="NYC",
        date="2026-05-15",
        temp_type="high",
        direction="between",
        range_low_f=80.0,
        range_high_f=81.0,
        unit="F",
        yes_token_id="tok-yes",
        no_token_id="tok-no",
        yes_price=Decimal(yes_price),
        volume_24h_usd=Decimal("1000"),
        end_date=end_date,
    )
    net = gfs - float(Decimal(yes_price))
    return WeatherEdgeDecision(
        market=market,
        gfs_probability=gfs,
        market_probability=float(Decimal(yes_price)),
        gross_edge=net,
        net_edge=net,
        edge=net,
        side=side,
        reason="test",
        forecast_mean_f=70.0,
        forecast_std_f=2.0,
        ensemble_count=31,
        decided_at=datetime.now(UTC),
        forecast_source="multi_model",
        forecast_fetched_at=datetime.now(UTC),
        api_agreement_count=2,
        api_agreement_max_gap_f=1.0,
    )


def test_quote_is_non_crossing_and_notional_sized(sf, monkeypatch):
    maker_live = _reload(monkeypatch)
    runner = maker_live.BotDMakerLive(clob=FakeClob(bid="0.700", ask="0.780"), session_factory=sf)

    quote = runner.quote_for_decision(_decision())

    assert not isinstance(quote, str), quote
    assert quote.quote_price < Decimal("0.780")
    assert quote.notional_usd >= Decimal("5")
    assert quote.notional_usd <= Decimal("10")


def test_ended_market_blocks_quote(sf, monkeypatch):
    maker_live = _reload(monkeypatch)
    runner = maker_live.BotDMakerLive(clob=FakeClob(bid="0.010", ask="0.040"), session_factory=sf)
    decision = _decision(
        "ended-c",
        side="BUY_YES",
        yes_price="0.03",
        gfs=0.20,
        end_date=datetime.now(UTC) - timedelta(minutes=1),
    )

    assert runner.quote_for_decision(decision) == "market_ended"


def test_too_close_market_blocks_quote(sf, monkeypatch):
    maker_live = _reload(monkeypatch)
    monkeypatch.setenv("BOT_D_MAKER_MIN_ENTRY_HOURS_TO_END", "3")
    maker_live = importlib.reload(maker_live)
    runner = maker_live.BotDMakerLive(clob=FakeClob(bid="0.010", ask="0.040"), session_factory=sf)
    decision = _decision(
        "late-c",
        side="BUY_YES",
        yes_price="0.03",
        gfs=0.20,
        end_date=datetime.now(UTC) + timedelta(minutes=90),
    )

    assert runner.quote_for_decision(decision) == "too_close_to_end"


def test_cheap_yes_quote_is_capped_below_default_min_notional(sf, monkeypatch):
    maker_live = _reload(monkeypatch)
    runner = maker_live.BotDMakerLive(clob=FakeClob(bid="0.015", ask="0.038"), session_factory=sf)
    decision = _decision("cheap-yes-c", side="BUY_YES", yes_price="0.03", gfs=0.20)

    quote = runner.quote_for_decision(decision)

    assert not isinstance(quote, str), quote
    assert quote.quote_price == Decimal("0.037")
    assert quote.notional_usd <= Decimal("2.05")
    assert quote.max_notional_usd == Decimal("2")
    assert quote.shares < Decimal("100")


def test_place_quote_requires_explicit_live_authorization(sf, monkeypatch):
    maker_live = _reload(monkeypatch)
    monkeypatch.setenv("BOT_D_MAKER_LIVE_AUTHORIZED", "false")
    maker_live = importlib.reload(maker_live)
    clob = FakeClob()
    runner = maker_live.BotDMakerLive(clob=clob, session_factory=sf)
    quote = runner.quote_for_decision(_decision())
    assert not isinstance(quote, str), quote

    with pytest.raises(RuntimeError, match="maker_live_not_authorized"):
        runner.place_quote(quote)
    assert clob.placed == []


def test_place_quote_writes_separate_bot_order(sf, monkeypatch):
    maker_live = _reload(monkeypatch)
    clob = FakeClob()
    runner = maker_live.BotDMakerLive(clob=clob, session_factory=sf)
    quote = runner.quote_for_decision(_decision())
    assert not isinstance(quote, str), quote

    runner.place_quote(quote)

    with sf() as s:
        order = s.get(Order, "maker-order-1")
        assert order is not None
        assert order.bot_id == "bot_d_maker_live_probe"
        event = s.query(Event).filter(Event.event_type == "bot_d_maker.quote_placed").one()
        assert event.bot_id == "bot_d_maker_live_probe"


def test_stale_quote_cancel_updates_order(sf, monkeypatch):
    maker_live = _reload(monkeypatch)
    clob = FakeClob()
    runner = maker_live.BotDMakerLive(clob=clob, session_factory=sf)
    old = datetime.now(UTC) - timedelta(minutes=10)
    with sf() as s:
        s.add(Order(
            order_id="stale-1",
            bot_id="bot_d_maker_live_probe",
            condition_id="c1",
            token_id="tok-no",
            side="BUY",
            price=Decimal("0.75"),
            size=Decimal("7"),
            status="OPEN",
            placed_at=old,
            last_updated=old,
        ))
        s.commit()

    assert runner.cancel_stale_quotes() == 1

    with sf() as s:
        assert s.get(Order, "stale-1").status == "CANCELLED"
    assert clob.cancelled == ["stale-1"]


def test_daily_gross_cap_blocks_new_quote(sf, monkeypatch):
    maker_live = _reload(monkeypatch)
    monkeypatch.setenv("BOT_D_MAKER_MAX_DAILY_GROSS_USD", "5")
    maker_live = importlib.reload(maker_live)
    runner = maker_live.BotDMakerLive(clob=FakeClob(), session_factory=sf)
    with sf() as s:
        s.add(Order(
            order_id="today-1",
            bot_id="bot_d_maker_live_probe",
            condition_id="c-old",
            token_id="tok-no",
            side="BUY",
            price=Decimal("0.75"),
            size=Decimal("7"),
            status="CANCELLED",
            placed_at=datetime.now(UTC),
            last_updated=datetime.now(UTC),
        ))
        s.commit()

    assert runner.quote_for_decision(_decision("new-c")) == "maker_daily_gross_cap"


def test_stale_forecast_blocks_quote(sf, monkeypatch):
    maker_live = _reload(monkeypatch)
    monkeypatch.setenv("BOT_D_MAKER_MAX_FORECAST_AGE_SEC", "60")
    maker_live = importlib.reload(maker_live)
    runner = maker_live.BotDMakerLive(clob=FakeClob(), session_factory=sf)
    decision = _decision("stale-c")
    decision = WeatherEdgeDecision(
        **{
            **decision.__dict__,
            "forecast_fetched_at": datetime.now(UTC) - timedelta(minutes=10),
        }
    )

    assert runner.quote_for_decision(decision) == "stale_forecast"


def test_halt_blocks_quote(sf, monkeypatch):
    maker_live = _reload(monkeypatch)
    runner = maker_live.BotDMakerLive(clob=FakeClob(), session_factory=sf)
    with sf() as s:
        from core.db import HaltFlag

        s.add(HaltFlag(bot_id="bot_d_maker_live_probe", halted=1, reason="test"))
        s.commit()

    assert runner.quote_for_decision(_decision("halt-c")) == "bot_halt"
