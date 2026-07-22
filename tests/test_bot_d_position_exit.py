"""Tests for Bot D's review_open_positions (bot-driven exit logic).

K2.6 audit fix 2026-04-21 — closes the "fatal flaw" of hold-to-resolution
on filled positions.
"""

import importlib
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.clob import OrderBook, OrderResponse
from core.db import Base, Event, Order, Position, Trade


# Minimal fake WeatherMarket / WeatherEdgeDecision shapes so we don't pull
# in the full strategy module.
@dataclass
class _FakeMarket:
    gamma_id: str
    yes_token_id: str
    no_token_id: str
    yes_price: float | None = 0.30
    city: str = "TestCity"


@dataclass
class _FakeDecision:
    market: _FakeMarket
    net_edge: float
    side: str = "BUY_YES"
    gfs_probability: float = 0.5


@pytest.fixture
def sf(tmp_path):
    """Session factory backed by a fresh SQLite DB."""
    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}", future=True)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _seed_position(sf, *, token_id: str, side: str, size: Decimal,
                   cost_basis: Decimal, yes_token_id: str, no_token_id: str,
                   condition_id: str = "cid-1"):
    with sf() as s:
        s.add(Position(
            bot_id="bot_d",
            condition_id=condition_id,
            token_id=token_id,
            side=side,
            size=size,
            avg_price=cost_basis / size,
            cost_basis_usd=cost_basis,
            status="OPEN",
            opened_at=datetime.now(UTC),
        ))
        s.commit()


def _seed_source_snapshot(
    sf,
    *,
    condition_id: str = "cid-1",
    bucket_state: str = "pending",
    station_metric_f: float = 75.0,
    distance_to_bucket_f: float | None = None,
):
    with sf() as s:
        s.add(Event(
            bot_id="bot_d",
            event_type="bot_d.source_snapshot",
            severity="info",
            message="source snapshot",
            payload={
                "condition_id": condition_id,
                "bucket_state": bucket_state,
                "station_metric_f": station_metric_f,
                "distance_to_bucket_f": distance_to_bucket_f,
                "end_date": "2026-05-14T23:00:00+00:00",
            },
        ))
        s.commit()


def _reload_executor(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    return importlib.reload(exmod)


class TestReviewOpenPositions:

    def test_exits_when_edge_flips_on_yes_position(self, sf):
        from bots.bot_d_weather.executor import BotDExecutor
        # Seed: YES position bought for $10 (200 shares at $0.05)
        _seed_position(
            sf, condition_id="cid-1",
            token_id="yes1", side="YES",
            size=Decimal("200"), cost_basis=Decimal("10"),
            yes_token_id="yes1", no_token_id="no1",
        )
        executor = BotDExecutor(clob=object(), main_session_factory=sf)
        # Decision: net_edge NEGATIVE (thesis reversed on YES side)
        mkt = _FakeMarket(gamma_id="cid-1", yes_token_id="yes1", no_token_id="no1", yes_price=0.08)
        dec = _FakeDecision(market=mkt, net_edge=-0.15)
        n = executor.review_open_positions([dec])
        assert n == 1
        # Position closed, SELL trade written at yes_price=0.08
        with sf() as s:
            pos = s.execute(select(Position).where(Position.condition_id == "cid-1")).scalars().first()
            assert pos.status == "CLOSED"
            sell = s.execute(select(Trade).where(Trade.side == "SELL")).scalars().first()
            assert sell is not None
            assert sell.price == Decimal("0.08")
            assert sell.size == Decimal("200")

    def test_live_exit_places_sell_order_without_synthetic_close(self, sf):
        from bots.bot_d_weather.executor import BotDExecutor

        class _LiveClob:
            paper_override = False

            def __init__(self):
                self.calls = []

            def _effective_paper(self):
                return False

            def place_limit(self, **kwargs):
                self.calls.append(kwargs)
                return OrderResponse("live-exit-1", "OPEN", {"ok": True})

        _seed_position(
            sf, condition_id="cid-1",
            token_id="yes1", side="YES",
            size=Decimal("200"), cost_basis=Decimal("10"),
            yes_token_id="yes1", no_token_id="no1",
        )
        clob = _LiveClob()
        executor = BotDExecutor(clob=clob, main_session_factory=sf)
        mkt = _FakeMarket(gamma_id="cid-1", yes_token_id="yes1", no_token_id="no1", yes_price=0.08)
        dec = _FakeDecision(market=mkt, net_edge=-0.15)

        n = executor.review_open_positions([dec])

        assert n == 1
        assert clob.calls
        assert clob.calls[0]["side"].value == "SELL"
        with sf() as s:
            pos = s.execute(select(Position).where(Position.condition_id == "cid-1")).scalars().first()
            sell_trade = s.execute(select(Trade).where(Trade.side == "SELL")).scalars().first()
            sell_order = s.execute(select(Order).where(Order.side == "SELL")).scalars().first()
        assert pos.status == "OPEN"
        assert sell_trade is None
        assert sell_order is not None
        assert sell_order.order_id == "live-exit-1"
        assert sell_order.status == "OPEN"
        assert sell_order.price == Decimal("0.07500000")

    def test_review_open_orders_does_not_cancel_live_exit_sell(self, sf):
        from bots.bot_d_weather.executor import BotDExecutor

        class _LiveClob:
            paper_override = False

            def __init__(self):
                self.cancel_calls = []

            def _effective_paper(self):
                return False

            def cancel_order(self, order_id):
                self.cancel_calls.append(order_id)
                return True

        with sf() as s:
            s.add(Order(
                order_id="live-exit-sell",
                bot_id="bot_d",
                condition_id="cid-1",
                token_id="yes1",
                side="SELL",
                price=Decimal("0.08"),
                size=Decimal("200"),
                status="OPEN",
                order_type="GTC",
            ))
            s.commit()
        clob = _LiveClob()
        executor = BotDExecutor(clob=clob, main_session_factory=sf)
        mkt = _FakeMarket(gamma_id="cid-1", yes_token_id="yes1", no_token_id="no1", yes_price=0.08)
        dec = _FakeDecision(market=mkt, net_edge=-0.15)

        assert executor.review_open_orders([dec]) == 0
        assert clob.cancel_calls == []

    def test_exits_no_position_when_edge_collapses_below_floor(self, sf):
        from bots.bot_d_weather.executor import BotDExecutor
        _seed_position(
            sf, condition_id="cid-1",
            token_id="no1", side="NO",
            size=Decimal("100"), cost_basis=Decimal("20"),
            yes_token_id="yes1", no_token_id="no1",
        )
        executor = BotDExecutor(clob=object(), main_session_factory=sf)
        mkt = _FakeMarket(gamma_id="cid-1", yes_token_id="yes1", no_token_id="no1", yes_price=0.50)
        # net_edge=+0.01 → for NO side, edge_for_side=-0.01; |edge| < 0.02 floor
        dec = _FakeDecision(market=mkt, net_edge=0.01)
        n = executor.review_open_positions([dec])
        assert n == 1
        with sf() as s:
            sell = s.execute(select(Trade).where(Trade.side == "SELL")).scalars().first()
            assert sell is not None
            assert sell.price == Decimal("0.49800000")  # 1 - yes_price for NO, after paper exit slippage
            assert sell.size == Decimal("100")

    def test_keeps_position_when_edge_still_strong(self, sf):
        from bots.bot_d_weather.executor import BotDExecutor
        _seed_position(
            sf, condition_id="cid-1",
            token_id="yes1", side="YES",
            size=Decimal("100"), cost_basis=Decimal("5"),
            yes_token_id="yes1", no_token_id="no1",
        )
        executor = BotDExecutor(clob=object(), main_session_factory=sf)
        mkt = _FakeMarket(gamma_id="cid-1", yes_token_id="yes1", no_token_id="no1", yes_price=0.05)
        dec = _FakeDecision(market=mkt, net_edge=+0.15)  # Strong positive edge on YES
        n = executor.review_open_positions([dec])
        assert n == 0
        with sf() as s:
            pos = s.execute(select(Position)).scalars().first()
            assert pos.status == "OPEN"

    def test_no_exit_when_no_fresh_decision(self, sf):
        """Don't force-exit on no-signal: decision missing = keep holding."""
        from bots.bot_d_weather.executor import BotDExecutor
        _seed_position(
            sf, condition_id="cid-1",
            token_id="yes1", side="YES",
            size=Decimal("100"), cost_basis=Decimal("5"),
            yes_token_id="yes1", no_token_id="no1",
        )
        executor = BotDExecutor(clob=object(), main_session_factory=sf)
        n = executor.review_open_positions([])  # no decisions at all
        assert n == 0
        with sf() as s:
            pos = s.execute(select(Position)).scalars().first()
            assert pos.status == "OPEN"

    def test_returns_zero_when_no_open_positions(self, sf):
        from bots.bot_d_weather.executor import BotDExecutor
        executor = BotDExecutor(clob=object(), main_session_factory=sf)
        mkt = _FakeMarket(gamma_id="cid-1", yes_token_id="yes1", no_token_id="no1", yes_price=0.5)
        dec = _FakeDecision(market=mkt, net_edge=-0.20)
        assert executor.review_open_positions([dec]) == 0

    def test_position_validation_stop_loss_plus_worsening_data_recommends_sell(self, sf, monkeypatch):
        exmod = _reload_executor(
            monkeypatch,
            BOT_D_POSITION_AUTO_SELL_ENABLED="false",
            BOT_D_POSITION_STOP_LOSS_PCT="0.25",
        )
        _seed_position(
            sf, condition_id="cid-raw",
            token_id="no1", side="NO",
            size=Decimal("10"), cost_basis=Decimal("8.00"),
            yes_token_id="yes1", no_token_id="no1",
        )
        _seed_source_snapshot(
            sf,
            condition_id="cid-raw",
            bucket_state="pending",
            station_metric_f=75.0,
            distance_to_bucket_f=0.0,
        )

        class _LiveClob:
            paper_override = False

            def _effective_paper(self):
                return False

            def get_book(self, token_id):
                return OrderBook(
                    token_id=token_id,
                    bids=[(Decimal("0.40"), Decimal("20"))],
                    asks=[(Decimal("0.45"), Decimal("20"))],
                    timestamp=datetime.now(UTC).timestamp(),
                )

            def place_limit(self, **_kwargs):
                raise AssertionError("report-only validation must not place orders")

        executor = exmod.BotDExecutor(clob=_LiveClob(), main_session_factory=sf)

        assert executor.review_open_positions([]) == 0
        with sf() as s:
            event = s.execute(
                select(Event).where(Event.event_type == "bot_d.position_validation")
            ).scalars().one()
            assert event.payload["action"] == "SELL_RECOMMENDED"
            assert "stop_loss_with_invalidating_data" in event.payload["reason"]
            assert s.execute(select(Order).where(Order.side == "SELL")).scalars().first() is None

    def test_position_validation_raw_temperature_invalidation_recommends_sell(self, sf, monkeypatch):
        exmod = _reload_executor(monkeypatch, BOT_D_POSITION_AUTO_SELL_ENABLED="false")
        _seed_position(
            sf, condition_id="cid-lock",
            token_id="no1", side="NO",
            size=Decimal("10"), cost_basis=Decimal("8.00"),
            yes_token_id="yes1", no_token_id="no1",
        )
        _seed_source_snapshot(
            sf,
            condition_id="cid-lock",
            bucket_state="already_yes",
            station_metric_f=75.0,
            distance_to_bucket_f=0.0,
        )

        class _LiveClob:
            paper_override = False

            def _effective_paper(self):
                return False

            def get_book(self, token_id):
                return OrderBook(
                    token_id=token_id,
                    bids=[(Decimal("0.55"), Decimal("20"))],
                    asks=[(Decimal("0.60"), Decimal("20"))],
                    timestamp=datetime.now(UTC).timestamp(),
                )

            def place_limit(self, **_kwargs):
                raise AssertionError("report-only validation must not place orders")

        executor = exmod.BotDExecutor(clob=_LiveClob(), main_session_factory=sf)

        assert executor.review_open_positions([]) == 0
        with sf() as s:
            event = s.execute(
                select(Event).where(Event.event_type == "bot_d.position_validation")
            ).scalars().one()
        assert event.payload["action"] == "SELL_NOW"
        assert "raw_station_against_no" in event.payload["reason"]

    def test_position_validation_auto_sell_requires_explicit_enable(self, sf, monkeypatch):
        exmod = _reload_executor(monkeypatch, BOT_D_POSITION_AUTO_SELL_ENABLED="true")
        _seed_position(
            sf, condition_id="cid-auto",
            token_id="no1", side="NO",
            size=Decimal("5"), cost_basis=Decimal("4.00"),
            yes_token_id="yes1", no_token_id="no1",
        )
        _seed_source_snapshot(
            sf,
            condition_id="cid-auto",
            bucket_state="already_yes",
            station_metric_f=75.0,
            distance_to_bucket_f=0.0,
        )

        class _LiveClob:
            paper_override = False

            def __init__(self):
                self.calls = []

            def _effective_paper(self):
                return False

            def get_book(self, token_id):
                return OrderBook(
                    token_id=token_id,
                    bids=[(Decimal("0.30"), Decimal("20"))],
                    asks=[(Decimal("0.35"), Decimal("20"))],
                    timestamp=datetime.now(UTC).timestamp(),
                )

            def place_limit(self, **kwargs):
                self.calls.append(kwargs)
                return OrderResponse("auto-sell-1", "OPEN", {"ok": True})

        clob = _LiveClob()
        executor = exmod.BotDExecutor(clob=clob, main_session_factory=sf)

        assert executor.review_open_positions([]) == 1
        assert len(clob.calls) == 1
        assert clob.calls[0]["side"].value == "SELL"
        with sf() as s:
            order = s.execute(select(Order).where(Order.side == "SELL")).scalars().one()
            event = s.execute(
                select(Event).where(Event.event_type == "bot_d.live_exit.order_placed")
            ).scalars().one()
        assert order.order_id == "auto-sell-1"
        assert event.payload["source"] == "position_validation"
