from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select


def _meta_and_signal():
    from bots.crypto_fair_value.model import MarketMeta, Signal

    meta = MarketMeta(
        condition_id="cond-report",
        question="Bitcoin Up or Down - May 6, 1:00PM-1:05PM ET",
        end_ms=1_779_999_900_000,
        start_ms=1_779_999_600_000,
        symbol="BTC",
        duration_minutes=5,
        yes_token_id="yes-report",
        no_token_id="no-report",
    )
    signal = Signal(
        strategy="probability_gap",
        condition_id=meta.condition_id,
        symbol="BTC",
        duration_minutes=5,
        side="UP",
        token_id=meta.yes_token_id,
        ask_price=Decimal("0.40"),
        model_probability_up=0.53,
        model_edge=Decimal("0.13"),
        pm_mid_up=Decimal("0.39"),
        effective_spread=Decimal("0.02"),
        top_depth_usd=Decimal("80"),
        seconds_left=60,
        decision_ms=1_779_999_840_000,
        cex_move_60s=0.001,
    )
    return meta, signal


def test_execute_signal_writes_main_1c_ledger_and_blocks_duplicate(tmp_db, monkeypatch):
    from bots.crypto_fair_value.config import load_config
    from bots.crypto_fair_value.paper_executor import execute_signal
    from core import portfolio as portfolio_mod
    from core.db import Event, Order, Position, Trade, get_session_factory

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda _date=None: Decimal("0.75"))
    cfg = load_config("probability_gap")
    meta, signal = _meta_and_signal()

    assert execute_signal(config=cfg, meta=meta, signal=signal) is True
    assert execute_signal(config=cfg, meta=meta, signal=signal) is False

    sf = get_session_factory()
    with sf() as session:
        order = session.scalars(select(Order).where(Order.bot_id == cfg.bot_id)).one()
        trade = session.scalars(select(Trade).where(Trade.bot_id == cfg.bot_id)).one()
        position = session.scalars(select(Position).where(Position.bot_id == cfg.bot_id)).one()
        event = session.scalars(
            select(Event).where(Event.event_type == "crypto_fair_value.signal")
        ).one()

    assert order.price == Decimal("0.41000000")
    assert trade.price == Decimal("0.41000000")
    assert position.status == "OPEN"
    assert event.payload["main_fill_track"] == "paper_taker_stressed_1c"
    assert {t["fill_track"] for t in event.payload["fill_tracks"]} == {
        "paper_taker_top",
        "paper_taker_stressed_1c",
        "paper_taker_stressed_2c",
    }


def test_execute_signal_maker_shadow_uses_bid_zero_fee(tmp_db, monkeypatch):
    from bots.crypto_fair_value.config import load_config
    from bots.crypto_fair_value.paper_executor import execute_signal
    from core import portfolio as portfolio_mod
    from core.db import Event, Order, Trade, get_session_factory

    monkeypatch.setenv("CRYPTO_PROB_GAP_EXECUTION_STYLE", "maker")
    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda _date=None: Decimal("0.75"))
    cfg = load_config("probability_gap")
    meta, signal = _meta_and_signal()

    assert cfg.bot_id == "crypto_probability_gap_paper_maker"
    assert execute_signal(config=cfg, meta=meta, signal=signal) is True

    sf = get_session_factory()
    with sf() as session:
        order = session.scalars(select(Order).where(Order.bot_id == cfg.bot_id)).one()
        trade = session.scalars(select(Trade).where(Trade.bot_id == cfg.bot_id)).one()
        event = session.scalars(
            select(Event).where(Event.event_type == "crypto_fair_value.signal")
        ).one()

    assert order.price == Decimal("0.38000000")
    assert order.order_type == "PAPER_MAKER_BID"
    assert trade.fee_usd == Decimal("0E-8")
    assert event.payload["main_fill_track"] == "paper_maker_bid"
    assert event.payload["execution_style"] == "maker"


def test_execute_signal_blocks_same_condition_with_new_decision_timestamp(tmp_db, monkeypatch):
    from bots.crypto_fair_value.config import load_config
    from bots.crypto_fair_value.paper_executor import execute_signal
    from core import portfolio as portfolio_mod
    from core.db import Order, Position, get_session_factory

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda _date=None: Decimal("0.75"))
    cfg = load_config("probability_gap")
    meta, signal = _meta_and_signal()
    later_signal = replace(signal, decision_ms=signal.decision_ms + 1)

    assert execute_signal(config=cfg, meta=meta, signal=signal) is True
    assert execute_signal(config=cfg, meta=meta, signal=later_signal) is False

    sf = get_session_factory()
    with sf() as session:
        assert len(list(session.scalars(select(Order).where(Order.bot_id == cfg.bot_id)))) == 1
        assert len(list(session.scalars(select(Position).where(Position.bot_id == cfg.bot_id)))) == 1


def test_execute_signal_records_out_of_bounds_stress_without_order(tmp_db, monkeypatch):
    from bots.crypto_fair_value.config import load_config
    from bots.crypto_fair_value.paper_executor import execute_signal
    from core import portfolio as portfolio_mod
    from core.db import Event, Order, Position, get_session_factory

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda _date=None: Decimal("0.75"))
    cfg = load_config("probability_gap")
    meta, signal = _meta_and_signal()
    expensive_signal = replace(signal, ask_price=Decimal("0.995"))

    assert execute_signal(config=cfg, meta=meta, signal=expensive_signal) is False

    sf = get_session_factory()
    with sf() as session:
        event = session.scalars(
            select(Event).where(Event.event_type == "crypto_fair_value.signal")
        ).one()
        assert list(session.scalars(select(Order).where(Order.bot_id == cfg.bot_id))) == []
        assert list(session.scalars(select(Position).where(Position.bot_id == cfg.bot_id))) == []

    tracks = {row["fill_track"]: row for row in event.payload["fill_tracks"]}
    assert tracks["paper_taker_top"]["filled"] is True
    assert tracks["paper_taker_stressed_1c"]["filled"] is False
    assert tracks["paper_taker_stressed_2c"]["filled"] is False
    assert tracks["paper_taker_stressed_1c"]["reason"] == "stressed_price_out_of_bounds"


def test_report_reconstructs_three_fill_tracks_after_settlement(tmp_db, monkeypatch):
    from bots.crypto_fair_value.config import load_config
    from bots.crypto_fair_value.paper_executor import execute_signal
    from core import portfolio as portfolio_mod
    from core.db import Event, get_session_factory
    from scripts.crypto_fair_value_paper_report import build_report

    monkeypatch.setattr(portfolio_mod, "get_usd_to_gbp_rate", lambda _date=None: Decimal("0.75"))
    cfg = load_config("probability_gap")
    meta, signal = _meta_and_signal()
    assert execute_signal(config=cfg, meta=meta, signal=signal) is True

    sf = get_session_factory()
    with sf() as session:
        session.add(
            Event(
                bot_id=cfg.bot_id,
                event_type="portfolio.paper_resolve",
                severity="info",
                message="settled",
                payload={
                    "condition_id": meta.condition_id,
                    "token_id": meta.yes_token_id,
                    "settle_price": "1",
                },
                created_at=datetime.now(UTC),
            )
        )
        session.commit()

    report = build_report(db_path=tmp_db, bot_ids=(cfg.bot_id,), since=None)
    tracks = {row["fill_track"]: row for row in report["rows"]}
    assert set(tracks) == {
        "paper_taker_top",
        "paper_taker_stressed_1c",
        "paper_taker_stressed_2c",
    }
    assert tracks["paper_taker_stressed_1c"]["closed_positions"] == 1
    assert tracks["paper_taker_stressed_1c"]["wins"] == 1
    assert tracks["paper_taker_stressed_2c"]["raw_roi"] < tracks["paper_taker_top"]["raw_roi"]
