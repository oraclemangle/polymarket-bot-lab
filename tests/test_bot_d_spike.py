from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import ClassVar

import pytest

from bots.bot_d_spike.discovery import (
    SpikeMarket,
    candidate_from_market,
    fetch_spike_markets,
    parse_spike_weather_question,
)
from bots.bot_d_spike.executor import SpikeExecutor
from bots.bot_d_spike.strategy import decide_entry
from core.clob import OrderBook, OrderResponse
from core.config import reset_settings
from core.db import Base, Order, Position, Trade, get_session_factory, init_db, reset_engine


@dataclass
class FakeClob:
    book: OrderBook
    paper: bool = True
    placed: list[dict] | None = None

    def _effective_paper(self) -> bool:
        return self.paper

    def get_book(self, token_id: str) -> OrderBook:
        assert token_id == self.book.token_id
        return self.book

    def place_limit(self, **kwargs) -> OrderResponse:
        if self.placed is None:
            self.placed = []
        self.placed.append(kwargs)
        return OrderResponse(order_id="paper-test-order", status="PAPER_OPEN", raw=kwargs)


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("POLYMARKET_DB_PATH", str(tmp_path / "main.db"))
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    reset_settings()
    reset_engine()
    engine = init_db()
    yield
    Base.metadata.drop_all(engine)
    reset_engine()
    reset_settings()


@pytest.fixture(autouse=True)
def no_fx_network(monkeypatch):
    import core.portfolio as portfolio

    monkeypatch.setattr(portfolio, "get_usd_to_gbp_rate", lambda _date=None: Decimal("1"))


def _book(token: str = "yes-token", *, bid: str = "0.04", ask: str = "0.05", ask_size: str = "100") -> OrderBook:
    return OrderBook(
        token_id=token,
        bids=[(Decimal(bid), Decimal("200"))],
        asks=[(Decimal(ask), Decimal(ask_size))],
        timestamp=datetime(2026, 5, 7, 0, 0, tzinfo=UTC).timestamp(),
    )


def _market(*, city: str = "Hong Kong", condition_id: str = "123") -> SpikeMarket:
    return SpikeMarket(
        gamma_id=condition_id,
        condition_id=condition_id,
        slug="weather-market",
        question=f"Will the highest temperature in {city} be 19°C on May 7?",
        city=city,
        date="May 7",
        temp_type="high",
        direction="exact",
        bucket="19C",
        yes_token_id="yes-token",
        no_token_id="no-token",
        end_date=datetime.now(UTC) + timedelta(hours=8),
        yes_price_hint=Decimal("0.05"),
        volume_24h_usd=Decimal("1000"),
    )


def test_parse_spike_question_handles_missing_bot_d_cities_and_nyc_alias():
    assert parse_spike_weather_question(
        "Will the highest temperature in Shenzhen be exactly 22°C on May 7?"
    )["city"] == "Shenzhen"
    assert parse_spike_weather_question(
        "Will the lowest temperature in New York City be between 43-44°F on May 7?"
    )["city"] == "New York"
    assert parse_spike_weather_question(
        "Will the highest temperature in Dallas be 82°F or below on May 7?"
    )["city"] == "Dallas"


def test_gamma_timeout_returns_empty_market_scan():
    class TimeoutSession:
        headers: ClassVar[dict[str, str]] = {}

        def get(self, *_args, **_kwargs):
            import requests

            raise requests.ReadTimeout("gamma timed out")

    assert fetch_spike_markets(client=TimeoutSession()) == []


def test_candidate_decision_enforces_book_price_spread_depth_and_city():
    candidate = candidate_from_market(_market(), clob=FakeClob(_book()))
    assert candidate is not None
    assert decide_entry(candidate).enter is True

    wide = candidate_from_market(_market(), clob=FakeClob(_book(bid="0.01", ask="0.05")))
    assert wide is None

    thin = candidate_from_market(_market(), clob=FakeClob(_book(ask_size="24")))
    assert thin is None

    blacklisted = candidate_from_market(_market(city="Dallas"), clob=FakeClob(_book()))
    assert blacklisted is None


def test_executor_places_forced_paper_order_and_simulates_fill(temp_db):
    candidate = candidate_from_market(_market(), clob=FakeClob(_book()))
    assert candidate is not None
    clob = FakeClob(_book())
    executor = SpikeExecutor(clob)

    result = executor.try_enter(decide_entry(candidate))

    assert result.placed is True
    assert result.order_id == "paper-test-order"
    with get_session_factory()() as s:
        assert s.query(Order).filter_by(bot_id="bot_d_spike").count() == 1
        assert s.query(Trade).filter_by(bot_id="bot_d_spike", side="BUY").count() == 1
        pos = s.query(Position).filter_by(bot_id="bot_d_spike", status="OPEN").one()
        assert pos.condition_id == candidate.market.condition_id
        assert pos.side == "YES"


def test_executor_blocks_live_mode_even_when_candidate_valid(temp_db):
    candidate = candidate_from_market(_market(), clob=FakeClob(_book()))
    assert candidate is not None
    clob = FakeClob(_book(), paper=False)
    executor = SpikeExecutor(clob)

    result = executor.try_enter(decide_entry(candidate))

    assert result.placed is False
    assert result.reason == "paper_only_guard"
    assert clob.placed is None


def test_executor_enforces_daily_cap_and_cross_bot_overlap(temp_db):
    candidate = candidate_from_market(_market(condition_id="overlap"), clob=FakeClob(_book()))
    assert candidate is not None
    now = datetime.now(UTC)
    with get_session_factory()() as s:
        for i in range(40):
            s.add(
                Order(
                    order_id=f"paper-existing-{i}",
                    bot_id="bot_d_spike",
                    condition_id=f"c{i}",
                    token_id=f"t{i}",
                    side="BUY",
                    price=Decimal("0.001"),
                    size=Decimal("1"),
                    status="FILLED",
                    placed_at=now,
                )
            )
        s.commit()
    capped = SpikeExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))
    assert capped.reason == "daily_entry_cap"


def test_executor_enforces_daily_gross_cap(temp_db):
    candidate = candidate_from_market(_market(condition_id="daily-gross"), clob=FakeClob(_book()))
    assert candidate is not None
    now = datetime.now(UTC)
    with get_session_factory()() as s:
        s.add(
            Order(
                order_id="paper-existing-gross",
                bot_id="bot_d_spike",
                condition_id="gross-used",
                token_id="gross-token",
                side="BUY",
                price=Decimal("0.05"),
                size=Decimal("180"),
                status="FILLED",
                placed_at=now,
            )
        )
        s.commit()
    capped = SpikeExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))
    assert capped.reason == "daily_gross_cap"


def test_executor_blocks_other_bot_open_position(temp_db):
    candidate = candidate_from_market(_market(condition_id="shared-condition"), clob=FakeClob(_book()))
    assert candidate is not None
    with get_session_factory()() as s:
        s.add(
            Position(
                bot_id="bot_d_live_probe",
                condition_id="shared-condition",
                token_id="other-token",
                side="NO",
                size=Decimal("5"),
                avg_price=Decimal("0.8"),
                cost_basis_usd=Decimal("4"),
                status="OPEN",
            )
        )
        s.commit()
    result = SpikeExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))
    assert result.placed is False
    assert result.reason == "other_bot_overlap"
