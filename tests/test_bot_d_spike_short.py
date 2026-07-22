"""Tests for the Bot D-Spike-Short paper lane (Strategy E2 short-TTR variant).

Mirrors `test_bot_d_spike.py` with the TTR window adjusted to `[0, 6)` hours
and the daily-entry cap raised to 30. Verifies:

- the short lane uses its own bot_id (`bot_d_spike_short`) so DB attribution
  stays clean from the 6-12h `bot_d_spike` lane;
- the TTR gate rejects 6-12h candidates and accepts 0-6h candidates;
- the daily-entry cap blocks at 30, not 20;
- cross-bot overlap is detected against `bot_d_spike` positions on the same
  condition_id (the two lanes must NOT both hold a position in the same
  market simultaneously);
- live mode is blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from bots.bot_d_spike_short import config as cfg_short
from bots.bot_d_spike_short.discovery import (
    SpikeMarket,
    candidate_from_market,
    parse_spike_weather_question,
)
from bots.bot_d_spike_short.executor import SpikeShortExecutor
from bots.bot_d_spike_short.strategy import decide_entry
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


def _market(
    *,
    city: str = "Hong Kong",
    condition_id: str = "123",
    hours_to_close: float = 3.0,
) -> SpikeMarket:
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
        end_date=datetime.now(UTC) + timedelta(hours=hours_to_close),
        yes_price_hint=Decimal("0.05"),
        volume_24h_usd=Decimal("1000"),
    )


def test_short_lane_has_distinct_bot_id_and_short_ttr_window():
    assert cfg_short.BOT_D_SPIKE_SHORT_BOT_ID == "bot_d_spike_short"
    assert Decimal("0") == cfg_short.TTR_MIN_HOURS
    assert Decimal("6") == cfg_short.TTR_MAX_HOURS
    assert cfg_short.MAX_DAILY_ENTRIES == 30


def test_parse_spike_question_uses_shared_parser():
    """Short lane re-exports the parent parser; identical behaviour."""
    assert parse_spike_weather_question(
        "Will the highest temperature in Shenzhen be exactly 22°C on May 7?"
    )["city"] == "Shenzhen"


def test_short_ttr_window_accepts_zero_to_six_hours_only():
    """0-6h accepted; 6-12h rejected; >12h rejected."""
    accept = candidate_from_market(_market(hours_to_close=3.0), clob=FakeClob(_book()))
    assert accept is not None
    assert decide_entry(accept).enter is True

    long_ttr = candidate_from_market(_market(hours_to_close=8.0), clob=FakeClob(_book()))
    assert long_ttr is None

    far_ttr = candidate_from_market(_market(hours_to_close=24.0), clob=FakeClob(_book()))
    assert far_ttr is None


def test_short_ttr_rejects_negative_hours_after_resolution():
    """Past-resolution markets fail the TTR_MIN_HOURS=0 lower bound."""
    past = candidate_from_market(_market(hours_to_close=-0.5), clob=FakeClob(_book()))
    assert past is None


def test_short_ttr_boundary_is_strict_at_six_hours():
    """TTR_MAX_HOURS=6 is exclusive; exactly-6h is rejected."""
    on_boundary = candidate_from_market(_market(hours_to_close=6.0), clob=FakeClob(_book()))
    assert on_boundary is None

    just_under = candidate_from_market(_market(hours_to_close=5.99), clob=FakeClob(_book()))
    assert just_under is not None


def test_short_executor_uses_correct_bot_id_in_db(temp_db):
    candidate = candidate_from_market(_market(hours_to_close=3.0), clob=FakeClob(_book()))
    assert candidate is not None
    clob = FakeClob(_book())
    executor = SpikeShortExecutor(clob)

    result = executor.try_enter(decide_entry(candidate))

    assert result.placed is True
    with get_session_factory()() as s:
        assert s.query(Order).filter_by(bot_id="bot_d_spike_short").count() == 1
        assert s.query(Order).filter_by(bot_id="bot_d_spike").count() == 0
        assert s.query(Trade).filter_by(bot_id="bot_d_spike_short", side="BUY").count() == 1
        pos = s.query(Position).filter_by(bot_id="bot_d_spike_short", status="OPEN").one()
        assert pos.side == "YES"


def test_short_executor_blocks_live_mode(temp_db):
    candidate = candidate_from_market(_market(hours_to_close=3.0), clob=FakeClob(_book()))
    assert candidate is not None
    clob = FakeClob(_book(), paper=False)
    executor = SpikeShortExecutor(clob)

    result = executor.try_enter(decide_entry(candidate))

    assert result.placed is False
    assert result.reason == "paper_only_guard"
    assert clob.placed is None


def test_short_executor_daily_cap_is_thirty_not_twenty(temp_db):
    """Short lane has higher daily cap (30) because positions resolve within hours."""
    candidate = candidate_from_market(
        _market(condition_id="overlap", hours_to_close=3.0),
        clob=FakeClob(_book()),
    )
    assert candidate is not None
    now = datetime.now(UTC)
    with get_session_factory()() as s:
        for i in range(20):
            s.add(
                Order(
                    order_id=f"paper-existing-{i}",
                    bot_id="bot_d_spike_short",
                    condition_id=f"c{i}",
                    token_id=f"t{i}",
                    side="BUY",
                    price=Decimal("0.05"),
                    size=Decimal("40"),
                    status="FILLED",
                    placed_at=now,
                )
            )
        s.commit()

    twenty_first = SpikeShortExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))
    assert twenty_first.placed is True

    with get_session_factory()() as s:
        for i in range(20, 30):
            s.add(
                Order(
                    order_id=f"paper-existing-{i}",
                    bot_id="bot_d_spike_short",
                    condition_id=f"c{i}",
                    token_id=f"t{i}",
                    side="BUY",
                    price=Decimal("0.05"),
                    size=Decimal("40"),
                    status="FILLED",
                    placed_at=now,
                )
            )
        s.commit()
    candidate_again = candidate_from_market(
        _market(condition_id="overlap-after-cap", hours_to_close=3.0),
        clob=FakeClob(_book()),
    )
    assert candidate_again is not None
    capped = SpikeShortExecutor(FakeClob(_book())).try_enter(decide_entry(candidate_again))
    assert capped.placed is False
    assert capped.reason == "daily_entry_cap"


def test_short_executor_detects_overlap_with_bot_d_spike_lane(temp_db):
    """If the 6-12h lane already holds the condition, the short lane must not enter."""
    candidate = candidate_from_market(
        _market(condition_id="shared-condition", hours_to_close=3.0),
        clob=FakeClob(_book()),
    )
    assert candidate is not None
    with get_session_factory()() as s:
        s.add(
            Position(
                bot_id="bot_d_spike",
                condition_id="shared-condition",
                token_id="other-token",
                side="YES",
                size=Decimal("5"),
                avg_price=Decimal("0.05"),
                cost_basis_usd=Decimal("0.25"),
                status="OPEN",
            )
        )
        s.commit()
    result = SpikeShortExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))
    assert result.placed is False
    assert result.reason == "other_bot_overlap"


def test_short_lane_rejects_blacklisted_city():
    """City whitelist is identical to the 6-12h lane."""
    blacklisted = candidate_from_market(
        _market(city="Dallas", hours_to_close=3.0),
        clob=FakeClob(_book()),
    )
    assert blacklisted is None
