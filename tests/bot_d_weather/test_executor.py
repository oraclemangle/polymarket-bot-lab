"""Tests for Bot D weather executor — sizing, caps, dedupe, exit logic."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from bots.bot_d_weather.discovery import WeatherMarket
from bots.bot_d_weather.strategy import WeatherEdgeDecision
from core import pyth_models  # noqa: F401
from core.clob import OrderBook, OrderResponse
from core.db import Base, Book, Event, HaltFlag, Order, Position, Trade


@pytest.fixture
def main_sf():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def mock_clob():
    clob = MagicMock()
    counter = {"n": 0}

    def _fake(**kwargs):
        counter["n"] += 1
        return OrderResponse(
            f"paper-d-{counter['n']:04x}",
            "PAPER_OPEN",
            {k: str(v) for k, v in kwargs.items()},
        )

    clob.place_limit.side_effect = _fake
    clob.cancel_order.return_value = True
    clob.paper_override = True
    clob.get_book.return_value = OrderBook(
        token_id="book-token",
        bids=[(Decimal("0.40"), Decimal("100"))],
        asks=[(Decimal("0.05"), Decimal("1000"))],
        timestamp=datetime.now(UTC).timestamp(),
    )
    return clob


def _dec(city="NYC", date="2026-04-16", direction="between", lo=74, hi=76,
         yes_price=0.05, gfs=0.26, gamma_id="g1", side="BUY_YES",
         end_date=None, forecast_source=None):
    if end_date is None:
        end_date = datetime.now(UTC) + timedelta(hours=24)
    m = WeatherMarket(
        gamma_id=gamma_id, slug="s", question="q", city=city, date=date,
        temp_type="high", direction=direction,
        range_low_f=float(lo), range_high_f=float(hi), unit="F",
        yes_token_id="ytok-" + gamma_id, no_token_id="ntok-" + gamma_id,
        yes_price=Decimal(str(yes_price)), volume_24h_usd=Decimal("1000"),
        end_date=end_date,
    )
    net = gfs - yes_price
    return WeatherEdgeDecision(
        market=m, gfs_probability=gfs, market_probability=yes_price,
        gross_edge=net, net_edge=net, edge=net,
        side=side, reason="test",
        forecast_mean_f=75.0, forecast_std_f=3.5, ensemble_count=31,
        decided_at=datetime.now(UTC), forecast_source=forecast_source,
    )


def test_placement_creates_order_only(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod
    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = _dec(gfs=0.50, yes_price=0.05, gamma_id="g1")
    r = ex.try_enter(d)
    assert r.placed, f"expected placed, got {r.reason}"
    with main_sf() as s:
        orders = list(s.execute(select(Order)).scalars())
        positions = list(s.execute(select(Position)).scalars())
    assert len(orders) == 1
    assert orders[0].bot_id == "bot_d"
    # U-06 (audit 2026-04-18): Position rows are NOT created at placement.
    # The Portfolio layer creates them on fill. Before this change, the
    # dual-write caused _apply_to_position to find the pre-existing OPEN
    # Position and add the filled size a second time, doubling exposure.
    assert len(positions) == 0


def test_placement_persists_book_snapshot(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    d = _dec(gfs=0.50, yes_price=0.05, gamma_id="book-capture")
    mock_clob.get_book.return_value = OrderBook(
        token_id=d.market.yes_token_id,
        bids=[(Decimal("0.04"), Decimal("200"))],
        asks=[(Decimal("0.05"), Decimal("1000"))],
        timestamp=datetime.now(UTC).timestamp(),
    )
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(d)

    assert r.placed, r.reason
    mock_clob.get_book.assert_called_with(d.market.yes_token_id)
    with main_sf() as s:
        book = s.scalars(select(Book).where(Book.token_id == d.market.yes_token_id)).one()
        assert book.asks == [["0.05", "1000"]]


def test_depth_gate_rejects_thin_entry_book(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_DEPTH_GATE_ENABLED", "true")
    monkeypatch.setenv("BOT_D_MIN_ENTRY_DEPTH_USD", "25")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    d = _dec(gfs=0.50, yes_price=0.05, gamma_id="thin-book")
    mock_clob.get_book.return_value = OrderBook(
        token_id=d.market.yes_token_id,
        bids=[(Decimal("0.04"), Decimal("200"))],
        asks=[(Decimal("0.05"), Decimal("100"))],
        timestamp=datetime.now(UTC).timestamp(),
    )
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "depth_too_low"
    assert r.depth_usd == Decimal("5.0000")
    assert r.required_depth_usd == Decimal("30.00")
    mock_clob.place_limit.assert_not_called()


def test_dedupe_blocks_second_entry(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod
    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = _dec(gamma_id="dup1")
    r1 = ex.try_enter(d)
    assert r1.placed
    r2 = ex.try_enter(d)
    assert not r2.placed
    assert r2.reason == "dedupe"


def test_live_order_sync_clears_stale_local_open_rows(main_sf, mock_clob, monkeypatch):
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    mock_clob.get_user_orders.return_value = [SimpleNamespace(order_id="still-open")]
    with main_sf() as s:
        s.add_all([
            Order(
                order_id="filled-in-two-parts",
                bot_id="bot_d",
                condition_id="c1",
                token_id="t1",
                side="BUY",
                price=Decimal("0.67"),
                size=Decimal("5"),
                status="PARTIAL",
            ),
            Trade(
                trade_id="f1",
                bot_id="bot_d",
                order_id="filled-in-two-parts",
                condition_id="c1",
                token_id="t1",
                side="BUY",
                price=Decimal("0.67"),
                size=Decimal("2.5"),
                fee_usd=Decimal("0"),
                filled_at=datetime.now(UTC),
                usd_gbp_rate=Decimal("0.8"),
                gbp_notional=Decimal("1.34"),
            ),
            Trade(
                trade_id="f2",
                bot_id="bot_d",
                order_id="filled-in-two-parts",
                condition_id="c1",
                token_id="t1",
                side="BUY",
                price=Decimal("0.67"),
                size=Decimal("2.5"),
                fee_usd=Decimal("0"),
                filled_at=datetime.now(UTC),
                usd_gbp_rate=Decimal("0.8"),
                gbp_notional=Decimal("1.34"),
            ),
            Order(
                order_id="vanished-unfilled",
                bot_id="bot_d",
                condition_id="c2",
                token_id="t2",
                side="BUY",
                price=Decimal("0.72"),
                size=Decimal("5"),
                status="live",
            ),
            Order(
                order_id="still-open",
                bot_id="bot_d",
                condition_id="c3",
                token_id="t3",
                side="BUY",
                price=Decimal("0.80"),
                size=Decimal("5"),
                status="live",
            ),
        ])
        s.commit()
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    updated = ex._sync_live_open_order_statuses()

    assert updated == 2
    with main_sf() as s:
        statuses = {o.order_id: o.status for o in s.scalars(select(Order)).all()}
        assert statuses["filled-in-two-parts"] == "FILLED"
        assert statuses["vanished-unfilled"] == "CANCELLED"
        assert statuses["still-open"] == "live"


def test_isolated_wave_size_multiplier_reduces_order_size(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod
    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(gfs=0.50, yes_price=0.05, gamma_id="wave-size"),
        regime="isolated",
        wave_count=1,
        size_multiplier=Decimal("0.50"),
    )
    r = ex.try_enter(d)
    assert r.placed, f"expected placed, got {r.reason}"
    assert r.size_usd == Decimal("15.00")
    assert r.size_shares == Decimal("300.00")


def test_concurrency_cap(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_MAX_CONCURRENT_POSITIONS", "1")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod
    importlib.reload(cfgmod)  # constants live in config.py
    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    r1 = ex.try_enter(_dec(gamma_id="a1"))
    assert r1.placed
    r2 = ex.try_enter(_dec(gamma_id="a2"))
    assert not r2.placed
    assert r2.reason == "max_concurrent"


def test_long_lockup_market_is_rejected(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_MAX_LOCKUP_HOURS", "48")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = _dec(gamma_id="long-lock", end_date=datetime.now(UTC) + timedelta(hours=72))

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "lockup_too_long"


def test_ended_market_is_rejected(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = _dec(gamma_id="ended", end_date=datetime.now(UTC) - timedelta(minutes=1))

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "market_ended"


def test_nearly_ended_market_is_rejected(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_MIN_ENTRY_HOURS_TO_END", "2")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = _dec(gamma_id="nearly-ended", end_date=datetime.now(UTC) + timedelta(minutes=30))

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "too_close_to_end"


def test_missing_end_date_market_is_rejected(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_REQUIRE_KNOWN_END_DATE", "true")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = _dec(gamma_id="missing-end", end_date=datetime.now(UTC) + timedelta(hours=24))
    d = replace(d, market=replace(d.market, end_date=None))

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "missing_end_date"


def test_unverified_settlement_market_is_rejected(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_REQUIRE_VERIFIED_SETTLEMENT", "true")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = _dec(city="Houston", gamma_id="unverified-city")

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "unverified_settlement"


def test_entry_halt_blocks_entry(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_ENTRY_HALT", "true")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec())

    assert not r.placed
    assert r.reason == "entry_halt"


def test_halted_blocks_entry(main_sf, mock_clob, monkeypatch):
    monkeypatch.delenv("BOT_D_ENTRY_HALT", raising=False)
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    with main_sf() as s:
        s.add(HaltFlag(bot_id="bot_d", halted=1, reason="test", set_at=datetime.now(UTC)))
        s.commit()
    r = ex.try_enter(_dec())
    assert not r.placed and r.reason == "halted"


def test_live_mode_requires_explicit_authorization(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "false")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="live-block"))

    assert not r.placed
    assert r.reason == "live_not_authorized"
    mock_clob.place_limit.assert_not_called()


def test_live_probe_uses_fixed_shares_and_small_notional(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-03")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "4")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "50")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "50")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="bot-d-live-fixed", gfs=0.50, yes_price=0.25))

    assert r.placed, r.reason
    assert r.size_shares == Decimal("5.00")
    assert r.size_usd == Decimal("1.25")
    with main_sf() as s:
        order = s.execute(select(Order)).scalars().one()
    assert order.bot_id == "bot_d_live_probe"
    assert order.size == Decimal("5.00000000")


def test_live_probe_evidence_gated_sizes_expensive_winner_to_ten_shares(
    main_sf, mock_clob, monkeypatch
):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-10")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_LIVE_SIZING_MODE", "evidence_gated")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "10")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "100")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "150")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(
        _dec(
            gamma_id="bot-d-live-ladder-high",
            gfs=0.96,
            yes_price=0.85,
            forecast_source="noaa_nbm",
        )
    )

    assert r.placed, r.reason
    assert r.size_shares == Decimal("10.00")
    assert r.size_usd == Decimal("8.50")


def test_live_probe_evidence_gated_sizes_cheap_b_tier_to_thirty_shares(
    main_sf, mock_clob, monkeypatch
):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-10")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_LIVE_SIZING_MODE", "evidence_gated")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "10")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "100")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "150")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(
        _dec(
            gamma_id="bot-d-live-ladder-cheap",
            gfs=0.20,
            yes_price=0.077,
            forecast_source="noaa_nbm",
        )
    )

    assert r.placed, r.reason
    assert r.size_shares == Decimal("30.00")
    assert r.size_usd == Decimal("2.31")


def test_live_probe_evidence_gated_does_not_scale_weak_slices(
    main_sf, mock_clob, monkeypatch
):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-10")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_LIVE_SIZING_MODE", "evidence_gated")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "10")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "100")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "150")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_LIMIT_OFFSET", "0.012")
    monkeypatch.setenv("BOT_D_DEPTH_GATE_ENABLED", "false")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    grib = ex.try_enter(
        _dec(
            gamma_id="bot-d-live-ladder-grib",
            gfs=0.95,
            yes_price=0.85,
            forecast_source="gribstream_nbm",
        )
    )
    seattle = ex.try_enter(
        _dec(
            gamma_id="bot-d-live-ladder-seattle",
            city="Seattle",
            gfs=0.95,
            yes_price=0.85,
            forecast_source="noaa_nbm",
        )
    )
    mid = ex.try_enter(
        _dec(
            gamma_id="bot-d-live-ladder-mid",
            gfs=0.60,
            yes_price=0.30,
            forecast_source="noaa_nbm",
        )
    )

    assert grib.placed, grib.reason
    assert grib.size_shares == Decimal("5.00")
    assert seattle.placed, seattle.reason
    assert seattle.size_shares == Decimal("5.00")
    assert mid.placed, mid.reason
    assert mid.size_shares == Decimal("5.00")


def test_live_probe_evidence_gated_collects_cheap_yes_with_source_agreement(
    main_sf, mock_clob, monkeypatch
):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-10")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_LIVE_SIZING_MODE", "evidence_gated")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "10")
    monkeypatch.setenv("BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD", "0")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "100")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "150")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_LIMIT_OFFSET", "0.012")
    monkeypatch.setenv("BOT_D_DEPTH_GATE_ENABLED", "false")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    d = _dec(
        gamma_id="bot-d-live-ladder-seattle-cheap-yes",
        city="Seattle",
        gfs=0.129,
        yes_price=0.031,
        forecast_source="noaa_nbm",
    )
    d = replace(d, api_agreement_count=2, api_agreement_max_gap_f=1.43)

    r = ex.try_enter(d)

    assert r.placed, r.reason
    assert r.size_shares == Decimal("23.26")
    assert r.size_usd == Decimal("1.00")


def test_live_probe_blocks_invalid_forecast_numeric_before_order(
    main_sf, mock_clob, monkeypatch
):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-10")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "10")
    monkeypatch.setenv("BOT_D_LIVE_SIZING_MODE", "evidence_gated")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "10")
    monkeypatch.setenv("BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD", "0")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "100")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "150")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(
            gamma_id="bot-d-live-invalid-forecast",
            gfs=0.95,
            yes_price=0.031,
            forecast_source="gribstream_nbm",
        ),
        forecast_mean_f=float("nan"),
    )

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "invalid_numeric:forecast_mean_f"
    mock_clob.place_limit.assert_not_called()


def test_live_probe_blocks_exchange_sub_dollar_when_min_guard_disabled(
    main_sf, mock_clob, monkeypatch
):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-10")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "10")
    monkeypatch.setenv("BOT_D_LIVE_SIZING_MODE", "evidence_gated")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "10")
    monkeypatch.setenv("BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD", "0")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "100")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "150")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_LIMIT_OFFSET", "0.012")
    monkeypatch.setenv("BOT_D_DEPTH_GATE_ENABLED", "false")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = _dec(
        gamma_id="bot-d-live-exchange-floor",
        gfs=0.95,
        yes_price=0.031,
        forecast_source="gribstream_nbm",
    )

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "live_below_exchange_min_notional"
    assert r.size_shares == Decimal("10.00")
    assert r.size_usd == Decimal("0.43")
    mock_clob.place_limit.assert_not_called()


def test_live_probe_blocks_below_exchange_min_notional(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-03")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_LIVE_MIN_ORDER_NOTIONAL_USD", "1.00")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "4")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "50")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "50")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="bot-d-live-sub-dollar", gfs=0.50, yes_price=0.05))

    assert not r.placed
    assert r.reason == "live_below_min_notional"
    assert r.size_shares == Decimal("5.00")
    assert r.size_usd == Decimal("0.25")
    mock_clob.place_limit.assert_not_called()


def test_live_probe_daily_gross_cap_blocks_entry(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-03")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "4")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "0.20")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "50")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="bot-d-live-cap", gfs=0.50, yes_price=0.25))

    assert not r.placed
    assert r.reason == "live_daily_gross_cap"
    mock_clob.place_limit.assert_not_called()


def test_live_probe_daily_gross_cap_counts_sell_orders(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-03")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "4")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "1.00")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "50")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    now = datetime.now(UTC)
    with main_sf() as s:
        s.add(Order(
            order_id="sell-today",
            bot_id="bot_d_live_probe",
            condition_id="old",
            token_id="tok",
            side="SELL",
            price=Decimal("0.80"),
            size=Decimal("1"),
            status="MATCHED",
            order_type="FOK",
            placed_at=now,
            last_updated=now,
        ))
        s.commit()
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="bot-d-live-sell-gross", gfs=0.50, yes_price=0.25))

    assert not r.placed
    assert r.reason == "live_daily_gross_cap"
    mock_clob.place_limit.assert_not_called()


def test_live_probe_requires_separate_bot_id(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-03")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="bot-d-live-wrong-id"))

    assert not r.placed
    assert r.reason == "live_probe_requires_separate_bot_id"
    mock_clob.place_limit.assert_not_called()


def test_live_probe_requires_approved_at(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="bot-d-live-no-date"))

    assert not r.placed
    assert r.reason == "live_probe_missing_approved_at"
    mock_clob.place_limit.assert_not_called()


def test_live_probe_blocks_when_probe_mode_unset(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.delenv("BOT_D_LIVE_PROBE_MODE", raising=False)
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod
    import scripts.bot_d_readiness_report as report_mod

    monkeypatch.setattr(
        report_mod,
        "build_report",
        lambda _db_path: {"readiness": {"live_ready": False, "blockers": ["test_blocker"]}},
    )
    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="bot-d-live-no-probe-mode"))

    assert not r.placed
    assert r.reason == "live_readiness_blocked:test_blocker"
    mock_clob.place_limit.assert_not_called()


def test_live_probe_order_notional_cap_blocks_entry(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-03")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "4")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "50")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "50")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="bot-d-live-order-cap", gfs=0.95, yes_price=0.85))

    assert not r.placed
    assert r.reason == "live_order_notional_cap"
    mock_clob.place_limit.assert_not_called()


def test_live_probe_open_exposure_cap_blocks_entry(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-03")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_LIVE_MAX_ORDER_USD", "4")
    monkeypatch.setenv("BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD", "50")
    monkeypatch.setenv("BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD", "50")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    now = datetime.now(UTC)
    with main_sf() as s:
        s.add(Order(
            order_id="existing-live-probe-order",
            bot_id="bot_d_live_probe",
            condition_id="existing-live-probe",
            token_id="existing-token",
            side="BUY",
            price=Decimal("0.49"),
            size=Decimal("102"),
            status="OPEN",
            placed_at=now,
            last_updated=now,
        ))
        s.commit()
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="bot-d-live-exposure-cap", gfs=0.50, yes_price=0.25))

    assert not r.placed
    assert r.reason == "live_open_exposure_cap"
    mock_clob.place_limit.assert_not_called()


def test_live_probe_blocks_recent_skewnorm_fallback(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_ID_OVERRIDE", "bot_d_live_probe")
    monkeypatch.setenv("BOT_D_LIVE_AUTHORIZED", "true")
    monkeypatch.setenv("BOT_D_LIVE_APPROVED_AT", "2026-05-03")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "5")
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    with main_sf() as s:
        s.add(Event(
            bot_id="bot_d_live_probe",
            event_type="bot_d.skewnorm_fallback",
            severity="warn",
            message="test fallback",
            payload={},
            created_at=datetime.now(UTC),
        ))
        s.commit()
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    r = ex.try_enter(_dec(gamma_id="bot-d-live-skew-block", gfs=0.50, yes_price=0.05))

    assert not r.placed
    assert r.reason == "skewnorm_fallback_recent"
    mock_clob.place_limit.assert_not_called()


def test_live_probe_fixed_shares_required_in_live_plumbing_mode(monkeypatch):
    monkeypatch.setenv("BOT_D_ENV", "live")
    monkeypatch.setenv("BOT_D_LIVE_PROBE_MODE", "plumbing")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "0")
    import importlib

    import bots.bot_d_weather.config as cfgmod

    with pytest.raises(RuntimeError, match="BOT_D_LIVE_FIXED_SHARES"):
        importlib.reload(cfgmod)


def test_nws_fallback_entries_are_blocked_by_default(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_ALLOW_NWS_FALLBACK_ENTRY", "false")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(_dec(gamma_id="nws-only"), forecast_source="nws_fallback")

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "nws_fallback_entry_blocked"
    mock_clob.place_limit.assert_not_called()


def test_expensive_no_guard_blocks_single_source_high_no(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(
            gamma_id="expensive-no-single-source",
            lo=62,
            hi=63,
            yes_price=0.09,
            gfs=0.005,
            side="BUY_NO",
        ),
        forecast_source="gribstream_nbm",
        forecast_mean_f=67.55,
        forecast_std_f=3.36,
        api_agreement_count=1,
        api_agreement_max_gap_f=None,
    )

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "expensive_no_guard:source_agreement"
    assert r.limit_price == Decimal("0.910")
    mock_clob.place_limit.assert_not_called()


def test_expensive_no_guard_blocks_near_bucket_even_with_source_agreement(
    main_sf,
    mock_clob,
    monkeypatch,
):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(
            gamma_id="expensive-no-near-bucket",
            lo=62,
            hi=63,
            yes_price=0.09,
            gfs=0.005,
            side="BUY_NO",
        ),
        forecast_source="multi_model",
        forecast_mean_f=64.0,
        forecast_std_f=3.0,
        api_agreement_count=2,
        api_agreement_max_gap_f=1.0,
    )

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "expensive_no_guard:distance"
    mock_clob.place_limit.assert_not_called()


def test_expensive_no_guard_blocks_weak_c_tier_high_no(
    main_sf,
    mock_clob,
    monkeypatch,
):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    # ADR-160: the distance gate is now `max(4.0F, 2.0*sigma)`. The test
    # setup uses a forecast mean well clear of the bucket so distance passes
    # cleanly, and a small absolute net edge so the C-tier edge gate is the
    # load-bearing block.
    d = replace(
        _dec(
            gamma_id="expensive-no-weak-c-tier",
            lo=58,
            hi=59,
            yes_price=0.125,
            gfs=0.048,
            side="BUY_NO",
        ),
        forecast_source="noaa_nbm",
        forecast_mean_f=72.0,
        forecast_std_f=2.0,
        api_agreement_count=2,
        api_agreement_max_gap_f=0.6,
    )

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "expensive_no_guard:tier_c_edge"
    assert r.limit_price == Decimal("0.875")
    mock_clob.place_limit.assert_not_called()


def test_buy_no_blocks_when_forecast_mean_inside_yes_bucket(
    main_sf,
    mock_clob,
    monkeypatch,
):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(
            gamma_id="buy-no-mean-inside",
            lo=60,
            hi=61,
            yes_price=0.12,
            gfs=0.01,
            side="BUY_NO",
        ),
        forecast_source="noaa_nbm",
        forecast_mean_f=60.0,
        forecast_std_f=3.3,
        api_agreement_count=3,
        api_agreement_max_gap_f=0.9,
    )

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "buy_no_mean_inside_yes_bucket"
    assert r.limit_price == Decimal("0.880")
    mock_clob.place_limit.assert_not_called()


def test_expensive_no_guard_allows_far_bucket_with_source_agreement(
    main_sf,
    mock_clob,
    monkeypatch,
):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(
            gamma_id="expensive-no-far-bucket",
            lo=62,
            hi=63,
            yes_price=0.35,
            gfs=0.02,
            side="BUY_NO",
        ),
        forecast_source="multi_model",
        forecast_mean_f=75.0,
        forecast_std_f=2.5,
        api_agreement_count=2,
        api_agreement_max_gap_f=1.0,
    )

    r = ex.try_enter(d)

    assert r.placed, r.reason
    assert r.limit_price == Decimal("0.650")


# ADR-160 premium-tier NO sizing ladder tests. Each band exercises
# `_live_size_shares` directly so the assertions read the ladder output
# without entangling other guards. The `_no_premium_hard_skip` test uses
# `try_enter` because the guard fires before sizing.

def _reload_with_env(monkeypatch, **env):
    """Set env vars and reload config + executor modules so the new values
    are picked up by module-level Decimals."""
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    monkeypatch.setenv("BOT_D_LIVE_FIXED_SHARES", "15")
    monkeypatch.setenv("BOT_D_LIVE_SIZING_MODE", "evidence_gated")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    return cfgmod, exmod


def test_no_ladder_low_price_uses_fixed_shares(main_sf, mock_clob, monkeypatch):
    _cfgmod, exmod = _reload_with_env(monkeypatch)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(gamma_id="no-ladder-low", lo=58, hi=59, yes_price=0.50, side="BUY_NO"),
        forecast_source="multi_model",
    )
    target = ex._live_size_shares(d, limit_price=Decimal("0.50"))
    assert target == Decimal("15.00"), f"expected 15 shares for <0.60 NO, got {target}"


def test_no_ladder_mid_price_uses_mid_shares(main_sf, mock_clob, monkeypatch):
    _cfgmod, exmod = _reload_with_env(monkeypatch)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(gamma_id="no-ladder-mid", lo=58, hi=59, yes_price=0.30, side="BUY_NO"),
        forecast_source="multi_model",
    )
    target = ex._live_size_shares(d, limit_price=Decimal("0.70"))
    assert target == Decimal("10.00"), f"expected 10 shares for 0.60-0.75 NO, got {target}"


def test_no_ladder_high_price_uses_high_shares(main_sf, mock_clob, monkeypatch):
    _cfgmod, exmod = _reload_with_env(monkeypatch)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(gamma_id="no-ladder-high", lo=58, hi=59, yes_price=0.20, side="BUY_NO"),
        forecast_source="multi_model",
    )
    target = ex._live_size_shares(d, limit_price=Decimal("0.80"))
    assert target == Decimal("6.00"), f"expected 6 shares for 0.75-0.85 NO, got {target}"


def test_no_ladder_very_high_price_clamps_to_exchange_floor(
    main_sf, mock_clob, monkeypatch
):
    """`BOT_D_LIVE_NO_SHARES_VERY_HIGH=3` records operator intent for the
    0.85-0.95 band, but `MIN_POLYMARKET_SHARES=5` is the exchange-side
    floor and clamps upward. Future loosening of the floor would let the
    ladder reach 3 without further code changes."""
    _cfgmod, exmod = _reload_with_env(monkeypatch)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(gamma_id="no-ladder-very-high", lo=58, hi=59, yes_price=0.10, side="BUY_NO"),
        forecast_source="multi_model",
    )
    target = ex._live_size_shares(d, limit_price=Decimal("0.90"))
    assert target == Decimal("5.00"), (
        f"expected 5 shares (exchange floor) for 0.85-0.95 NO with cfg=3, got {target}"
    )


def test_no_premium_hard_skip_blocks_above_95c(main_sf, mock_clob, monkeypatch):
    """A `BUY_NO` priced at or above `BOT_D_LIVE_NO_PREMIUM_HARD_SKIP`
    (default `0.95`) is rejected with `no_premium_hard_skip` before
    sizing. Expensive-NO guard is disabled in this test so the hard-skip
    is the load-bearing block, not the upstream guard."""
    _cfgmod, exmod = _reload_with_env(
        monkeypatch,
        BOT_D_EXPENSIVE_NO_GUARD_ENABLED="false",
    )
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = replace(
        _dec(
            gamma_id="no-premium-hard-skip",
            lo=58,
            hi=59,
            yes_price=0.04,
            gfs=0.02,
            side="BUY_NO",
        ),
        forecast_source="multi_model",
        forecast_mean_f=72.0,
        forecast_std_f=2.0,
        api_agreement_count=2,
        api_agreement_max_gap_f=0.5,
    )

    r = ex.try_enter(d)

    assert not r.placed
    assert r.reason == "no_premium_hard_skip"
    # limit price at 1 - 0.04 = 0.96, above the 0.95 hard-skip threshold.
    assert r.limit_price == Decimal("0.960")
    mock_clob.place_limit.assert_not_called()


def test_review_cancels_on_edge_collapse(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod
    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    # Place an order.
    d = _dec(gamma_id="cancel1", gfs=0.50, yes_price=0.10, side="BUY_YES")
    r = ex.try_enter(d)
    assert r.placed
    # Now the edge has collapsed (market moved to model fair value).
    d_collapsed = _dec(gamma_id="cancel1", gfs=0.11, yes_price=0.10, side="SKIP")
    cancelled = ex.review_open_orders([d_collapsed], edge_collapse_threshold=0.03)
    assert cancelled == 1
    # Order status should be CANCELLED. No Position existed (U-06:
    # Position is only created on fill), so review_open_orders has
    # nothing to close on that side.
    with main_sf() as s:
        order = s.execute(select(Order).where(Order.condition_id == "cancel1")).scalars().first()
        pos = s.execute(select(Position).where(Position.condition_id == "cancel1")).scalars().first()
    assert order.status == "CANCELLED"
    assert pos is None


def test_review_cancels_on_edge_flip(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod
    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    # Bought YES because model > market.
    d = _dec(gamma_id="flip1", gfs=0.50, yes_price=0.10, side="BUY_YES")
    r = ex.try_enter(d)
    assert r.placed
    # Forecast shifted: model now says probability is LOW → edge flips to BUY_NO.
    d_flipped = _dec(gamma_id="flip1", gfs=0.05, yes_price=0.10, side="BUY_NO")
    cancelled = ex.review_open_orders([d_flipped])
    assert cancelled == 1


def test_review_cancels_live_status_order(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_MIN_VOLUME_24H_USD", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod
    importlib.reload(cfgmod)
    importlib.reload(exmod)
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)
    d = _dec(gamma_id="live-status", gfs=0.50, yes_price=0.10, side="BUY_YES")
    r = ex.try_enter(d)
    assert r.placed
    with main_sf() as s:
        order = s.execute(select(Order).where(Order.condition_id == "live-status")).scalars().first()
        order.status = "live"
        s.commit()
    d_collapsed = _dec(gamma_id="live-status", gfs=0.11, yes_price=0.10, side="SKIP")
    cancelled = ex.review_open_orders([d_collapsed], edge_collapse_threshold=0.03)
    assert cancelled == 1


def test_paper_position_exit_uses_bid_slippage_and_fee(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_PAPER_EXIT_SLIPPAGE_BPS", "50")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod
    import core.portfolio as portfolio

    monkeypatch.setattr(portfolio, "get_usd_to_gbp_rate", lambda _date=None: Decimal("0.80"))
    importlib.reload(cfgmod)
    importlib.reload(exmod)
    d = _dec(gamma_id="paper-exit", gfs=0.05, yes_price=0.40, side="BUY_NO")
    mock_clob.get_book.return_value = OrderBook(
        token_id=d.market.yes_token_id,
        bids=[(Decimal("0.40"), Decimal("100"))],
        asks=[(Decimal("0.42"), Decimal("100"))],
        timestamp=datetime.now(UTC).timestamp(),
    )
    with main_sf() as s:
        s.add(Position(
            bot_id="bot_d",
            condition_id=d.market.gamma_id,
            token_id=d.market.yes_token_id,
            side="YES",
            size=Decimal("10"),
            avg_price=Decimal("0.30"),
            cost_basis_usd=Decimal("3.00"),
            status="OPEN",
            opened_at=datetime.now(UTC) - timedelta(hours=1),
        ))
        s.commit()
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    exited = ex.review_open_positions([d])

    assert exited == 1
    with main_sf() as s:
        sell = s.execute(select(Trade).where(Trade.side == "SELL")).scalars().one()
        pos = s.execute(select(Position).where(Position.condition_id == "paper-exit")).scalars().one()
        books = list(s.execute(select(Book).where(Book.token_id == d.market.yes_token_id)).scalars())
    assert sell.price == Decimal("0.39800000")
    assert sell.fee_usd > Decimal("0")
    assert pos.status == "CLOSED"
    assert books


def test_stale_live_sell_order_is_cancelled(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_EXIT_STALE_MIN", "10")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    with main_sf() as s:
        s.add(Order(
            order_id="sell-stale",
            bot_id="bot_d",
            condition_id="stale-cid",
            token_id="yes-token",
            side="SELL",
            price=Decimal("0.40"),
            size=Decimal("10"),
            status="OPEN",
            order_type="GTC",
            placed_at=datetime.now(UTC) - timedelta(minutes=30),
        ))
        s.commit()
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    cancelled = ex.review_open_orders([])

    assert cancelled == 1
    mock_clob.cancel_order.assert_called_with("sell-stale")
    with main_sf() as s:
        order = s.get(Order, "sell-stale")
        event = s.execute(
            select(Event).where(Event.event_type == "bot_d.live_exit.stale")
        ).scalars().one()
    assert order.status == "CANCELLED"
    assert event.severity == "warn"


def test_live_take_profit_places_sell_at_best_bid_threshold(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_TAKE_PROFIT_ENABLED", "true")
    monkeypatch.setenv("BOT_D_TAKE_PROFIT_MIN_BID", "0.99")
    monkeypatch.setenv("BOT_D_TAKE_PROFIT_LIMIT_OFFSET", "0.001")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    d = _dec(gamma_id="take-profit", gfs=0.60, yes_price=0.50, side="BUY_YES")
    mock_clob._effective_paper.return_value = False
    mock_clob.get_book.return_value = OrderBook(
        token_id=d.market.yes_token_id,
        bids=[(Decimal("0.994"), Decimal("25"))],
        asks=[(Decimal("0.999"), Decimal("25"))],
        timestamp=datetime.now(UTC).timestamp(),
    )
    with main_sf() as s:
        s.add(Position(
            bot_id="bot_d",
            condition_id=d.market.gamma_id,
            token_id=d.market.yes_token_id,
            side="YES",
            size=Decimal("5"),
            avg_price=Decimal("0.68"),
            cost_basis_usd=Decimal("3.40"),
            status="OPEN",
            opened_at=datetime.now(UTC) - timedelta(hours=1),
        ))
        s.commit()
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    exited = ex.review_open_positions([d])

    assert exited == 1
    mock_clob.place_limit.assert_called_once()
    kwargs = mock_clob.place_limit.call_args.kwargs
    assert kwargs["side"].value == "SELL"
    assert kwargs["price"] == Decimal("0.993")
    with main_sf() as s:
        sell_order = s.execute(select(Order).where(Order.side == "SELL")).scalars().one()
        event = s.execute(
            select(Event).where(Event.event_type == "bot_d.take_profit_exit")
        ).scalars().one()
        trade = s.execute(select(Trade).where(Trade.side == "SELL")).scalars().first()
    assert sell_order.price == Decimal("0.993")
    assert event.payload["best_bid"] == "0.994"
    assert trade is None


def test_live_take_profit_reviews_position_without_fresh_decision(main_sf, mock_clob, monkeypatch):
    monkeypatch.setenv("BOT_D_TAKE_PROFIT_ENABLED", "true")
    monkeypatch.setenv("BOT_D_TAKE_PROFIT_MIN_BID", "0.99")
    monkeypatch.setenv("BOT_D_TAKE_PROFIT_LIMIT_OFFSET", "0.001")
    import importlib

    import bots.bot_d_weather.config as cfgmod
    import bots.bot_d_weather.executor as exmod

    importlib.reload(cfgmod)
    importlib.reload(exmod)
    mock_clob._effective_paper.return_value = False
    mock_clob.get_book.return_value = OrderBook(
        token_id="take-profit-token",
        bids=[(Decimal("0.991"), Decimal("25"))],
        asks=[(Decimal("0.997"), Decimal("25"))],
        timestamp=datetime.now(UTC).timestamp(),
    )
    with main_sf() as s:
        s.add(Position(
            bot_id="bot_d",
            condition_id="stale-scan-cid",
            token_id="take-profit-token",
            side="NO",
            size=Decimal("5"),
            avg_price=Decimal("0.68"),
            cost_basis_usd=Decimal("3.40"),
            status="OPEN",
            opened_at=datetime.now(UTC) - timedelta(hours=1),
        ))
        s.commit()
    ex = exmod.BotDExecutor(clob=mock_clob, main_session_factory=main_sf)

    exited = ex.review_open_positions([])

    assert exited == 1
    kwargs = mock_clob.place_limit.call_args.kwargs
    assert kwargs["side"].value == "SELL"
    assert kwargs["price"] == Decimal("0.990")
    with main_sf() as s:
        event = s.execute(
            select(Event).where(Event.event_type == "bot_d.take_profit_exit")
        ).scalars().one()
    assert event.payload["has_fresh_decision"] is False
