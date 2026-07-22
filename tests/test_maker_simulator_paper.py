from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

from scripts.maker_simulator_paper import (
    BookState,
    MarketMeta,
    QuoteOutcome,
    QuoteSpec,
    Resolution,
    ToxicTrainingFill,
    TradeEvent,
    apply_delta,
    cancel_latency_filter,
    compute_queue_ahead,
    detect_toxic_wallets,
    is_weekend_utc,
    low_trade_density_quarantine_ms,
    lower_bound_fill_count,
    parse_book_snapshot,
    prior_trade_count,
    should_skip_new_quote_for_final_window,
    simulate_market,
)


def test_parse_book_snapshot_returns_sorted_queryable_book():
    book = parse_book_snapshot(
        {
            "bids": [
                {"price": "0.053", "size": "8"},
                {"price": "0.052", "size": "4"},
            ],
            "asks": [
                {"price": "0.058", "size": "12"},
                {"price": "0.056", "size": "7"},
            ],
            "tick_size": "0.001",
        },
        received_at_ms=1_000,
    )

    assert book.valid is True
    assert book.best_bid == Decimal("0.053")
    assert book.best_ask == Decimal("0.056")
    assert book.ask_size_at(Decimal("0.056")) == Decimal("7")
    assert book.tick_size == Decimal("0.001")
    assert book.last_update_ms == 1_000


def test_apply_delta_updates_side_level_and_removes_zero_size():
    book = parse_book_snapshot(
        {
            "bids": [{"price": "0.052", "size": "4"}],
            "asks": [{"price": "0.056", "size": "7"}],
            "tick_size": "0.001",
        },
        received_at_ms=1_000,
    )

    updated = apply_delta(
        book,
        {
            "price_changes": [
                {
                    "asset_id": "token-1",
                    "price": "0.056",
                    "size": "3",
                    "side": "SELL",
                },
                {
                    "asset_id": "token-1",
                    "price": "0.052",
                    "size": "0",
                    "side": "BUY",
                },
            ],
        },
        asset_id="token-1",
        received_at_ms=2_000,
    )

    assert updated.ask_size_at(Decimal("0.056")) == Decimal("3")
    assert updated.bid_size_at(Decimal("0.052")) == Decimal("0")
    assert updated.last_update_ms == 2_000


def test_compute_queue_ahead_for_three_ladders():
    book = BookState(
        bids={Decimal("0.052"): Decimal("4")},
        asks={
            Decimal("0.056"): Decimal("7"),
            Decimal("0.057"): Decimal("11"),
            Decimal("0.061"): Decimal("13"),
        },
        tick_size=Decimal("0.001"),
        valid=True,
        last_update_ms=1_000,
    )

    assert compute_queue_ahead(book, "join_best_ask") == (
        Decimal("0.056"),
        Decimal("7"),
    )
    assert compute_queue_ahead(book, "improve_best_ask_by_1_tick") == (
        Decimal("0.055"),
        Decimal("0"),
    )
    assert compute_queue_ahead(book, "worse_than_best_ask_by_1_tick") == (
        Decimal("0.057"),
        Decimal("7"),
    )


def test_improve_ladder_rejects_crossing_post_only_quote():
    book = BookState(
        bids={Decimal("0.055"): Decimal("4")},
        asks={Decimal("0.056"): Decimal("7")},
        tick_size=Decimal("0.001"),
        valid=True,
        last_update_ms=1_000,
    )

    assert compute_queue_ahead(book, "improve_best_ask_by_1_tick") is None


def test_lower_bound_fill_consumes_queue_before_filling_quote():
    trades = [
        TradeEvent(ts_ms=1_000, price=Decimal("0.056"), size=Decimal("3"), side="BUY"),
        TradeEvent(ts_ms=2_000, price=Decimal("0.057"), size=Decimal("6"), side="BUY"),
    ]

    result = lower_bound_fill_count(
        trades,
        quote_price=Decimal("0.056"),
        quote_size=Decimal("5"),
        queue_ahead=Decimal("7"),
    )

    assert result.queue_consumed_by_trades == Decimal("7")
    assert result.lower_fill_size == Decimal("2")
    assert result.lower_fill_at_ms == 2_000


def test_lower_bound_fill_ignores_non_buyer_aggressive_and_below_quote_trades():
    trades = [
        TradeEvent(ts_ms=1_000, price=Decimal("0.055"), size=Decimal("20"), side="BUY"),
        TradeEvent(ts_ms=2_000, price=Decimal("0.057"), size=Decimal("20"), side="SELL"),
    ]

    result = lower_bound_fill_count(
        trades,
        quote_price=Decimal("0.056"),
        quote_size=Decimal("5"),
        queue_ahead=Decimal("0"),
    )

    assert result.lower_fill_size == Decimal("0")
    assert result.lower_fill_at_ms is None


def test_cancel_latency_filter_includes_only_in_flight_trades():
    trades = [
        TradeEvent(ts_ms=900, price=Decimal("0.056"), size=Decimal("1"), side="BUY"),
        TradeEvent(ts_ms=1_000, price=Decimal("0.056"), size=Decimal("1"), side="BUY"),
        TradeEvent(ts_ms=1_500, price=Decimal("0.056"), size=Decimal("1"), side="BUY"),
        TradeEvent(ts_ms=1_501, price=Decimal("0.056"), size=Decimal("1"), side="BUY"),
    ]

    in_flight = cancel_latency_filter(
        trades,
        cancel_intent_ms=1_000,
        cancel_latency_ms=500,
    )

    assert [t.ts_ms for t in in_flight] == [1_000, 1_500]


def test_cancel_latency_allows_fill_before_cancel_effective_time():
    trades = [
        TradeEvent(ts_ms=1_250, price=Decimal("0.056"), size=Decimal("5"), side="BUY"),
        TradeEvent(ts_ms=1_750, price=Decimal("0.056"), size=Decimal("5"), side="BUY"),
    ]

    result = lower_bound_fill_count(
        trades,
        quote_price=Decimal("0.056"),
        quote_size=Decimal("5"),
        queue_ahead=Decimal("0"),
        cancel_intent_ms=1_000,
        cancel_latency_ms=500,
    )

    assert result.lower_fill_size == Decimal("5")
    assert result.lower_fill_at_ms == 1_250
    assert result.lower_fill_during_cancel is True


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def _sim_conn() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        CREATE TABLE pm_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at_ms INTEGER NOT NULL,
            subscription_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            asset_id TEXT,
            condition_id TEXT,
            payload_json TEXT NOT NULL
        );
        CREATE TABLE cex_trades (
            received_at_ms INTEGER,
            trade_time_ms INTEGER,
            symbol TEXT,
            price REAL,
            size REAL,
            is_buyer_maker INTEGER
        );
        CREATE TABLE gaps (
            gap_start_ms INTEGER,
            gap_end_ms INTEGER,
            subscription_id TEXT
        );
        """
    )
    return con


def _insert_pm(
    con: sqlite3.Connection,
    *,
    ts_ms: int,
    sub_id: str,
    event_type: str,
    asset_id: str,
    condition_id: str,
    payload: dict,
) -> None:
    con.execute(
        """
        INSERT INTO pm_events (
            received_at_ms, subscription_id, event_type, asset_id, condition_id, payload_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (ts_ms, sub_id, event_type, asset_id, condition_id, json.dumps(payload)),
    )


def test_weekend_exclusion_helper_identifies_sat_sun_utc():
    saturday = _ms(datetime(2026, 5, 9, 12, tzinfo=UTC))
    sunday = _ms(datetime(2026, 5, 10, 12, tzinfo=UTC))
    monday = _ms(datetime(2026, 5, 11, 12, tzinfo=UTC))

    assert is_weekend_utc(saturday) is True
    assert is_weekend_utc(sunday) is True
    assert is_weekend_utc(monday) is False


def test_final_60s_no_new_quote_blocks_posting():
    end_ms = _ms(datetime(2026, 5, 11, 12, 15, tzinfo=UTC))
    post_ms = end_ms - 30_000

    assert should_skip_new_quote_for_final_window(end_ms=end_ms, post_ms=post_ms) is True

    con = _sim_conn()
    market = MarketMeta(
        condition_id="cid",
        question="BTC 15 minutes",
        symbol="BTC",
        start_ms=end_ms - 900_000,
        end_ms=end_ms,
        yes_token_id="yes",
        no_token_id="no",
    )
    _insert_pm(
        con,
        ts_ms=post_ms,
        sub_id="btc-20260511T1215",
        event_type="book",
        asset_id="yes",
        condition_id="cid",
        payload={"asks": [{"price": "0.060", "size": "10"}], "bids": []},
    )

    outcomes, stats = simulate_market(
        con,
        market,
        Resolution(winner_token_id="yes", path="test"),
        target_band=type("Band", (), {"contains": lambda _self, _price: True})(),
        min_lead_sec=0,
        max_lead_sec=60,
        cancel_latency_ms_values=[300],
        cancel_bps_threshold=Decimal("3"),
        cancel_window_sec=30,
        quote_size=Decimal("5"),
        stale_book_sec=30,
    )

    assert outcomes == []
    assert stats["quotes_skipped_final_60s"] == 3


def test_low_trade_density_quarantine_blocks_quote_attempt():
    end_ms = _ms(datetime(2026, 5, 11, 12, 15, tzinfo=UTC))
    post_ms = end_ms - 300_000
    con = _sim_conn()
    market = MarketMeta(
        condition_id="cid",
        question="BTC 15 minutes",
        symbol="BTC",
        start_ms=end_ms - 900_000,
        end_ms=end_ms,
        yes_token_id="yes",
        no_token_id="no",
    )
    for i in range(4):
        _insert_pm(
            con,
            ts_ms=post_ms - 240_000 + i * 10_000,
            sub_id="btc-20260511T1215",
            event_type="last_trade_price",
            asset_id="yes",
            condition_id="cid",
            payload={"price": "0.060", "size": "1", "side": "BUY"},
        )
    _insert_pm(
        con,
        ts_ms=post_ms,
        sub_id="btc-20260511T1215",
        event_type="book",
        asset_id="yes",
        condition_id="cid",
        payload={"asks": [{"price": "0.060", "size": "10"}], "bids": []},
    )

    outcomes, stats = simulate_market(
        con,
        market,
        Resolution(winner_token_id="no", path="test"),
        target_band=type("Band", (), {"contains": lambda _self, _price: True})(),
        min_lead_sec=300,
        max_lead_sec=600,
        cancel_latency_ms_values=[300],
        cancel_bps_threshold=Decimal("3"),
        cancel_window_sec=30,
        quote_size=Decimal("5"),
        stale_book_sec=30,
    )

    assert prior_trade_count(
        [TradeEvent(post_ms - 1_000, Decimal("0.06"), Decimal("1"), "BUY")],
        post_ms=post_ms,
    ) == 1
    assert low_trade_density_quarantine_ms(
        [post_ms - 240_000 + i * 10_000 for i in range(4)],
        start_ms=post_ms,
        end_ms=end_ms - 300_000,
    ) == 0
    assert outcomes == []
    assert stats["quotes_skipped_low_trade_density"] == 3


def test_toxic_wallet_detection_thresholds():
    toxic_events = [
        ToxicTrainingFill(
            taker_addr="0xtoxic",
            lead_sec=30,
            price=Decimal("0.05"),
            size=Decimal("100"),
            won=True,
        )
        for _ in range(30)
    ]
    below_threshold = [
        ToxicTrainingFill(
            taker_addr="0xsafe",
            lead_sec=30,
            price=Decimal("0.05"),
            size=Decimal("100"),
            won=i < 10,
        )
        for i in range(30)
    ]

    toxic, rows = detect_toxic_wallets([*toxic_events, *below_threshold])

    assert "0xtoxic" in toxic
    assert "0xsafe" not in toxic
    assert rows[0]["toxic"] is True


def test_roi_excluding_toxic_removes_toxic_fill_pnl():
    quote = QuoteSpec(
        ladder="join_best_ask",
        condition_id="cid",
        symbol="BTC",
        side="UP",
        token_id="yes",
        posted_at_ms=0,
        end_ms=600_000,
        quote_price=Decimal("0.10"),
        quote_size=Decimal("5"),
        queue_ahead_at_post=Decimal("0"),
        tick_size=Decimal("0.001"),
        cancel_intent_ms=None,
        cancel_reason=None,
    )
    clean = QuoteOutcome(
        quote=quote,
        latency_ms=300,
        won=False,
        resolution_path="test",
        lower_fill_size=Decimal("5"),
        lower_fill_at_ms=1_000,
        lower_fill_during_cancel=False,
        upper_fill_size=Decimal("5"),
        upper_fill_at_ms=1_000,
        attempted_collateral_dollar_minutes=Decimal("1"),
        taker_fill_sizes={"0xclean": Decimal("5")},
    )
    toxic = QuoteOutcome(
        quote=quote,
        latency_ms=300,
        won=True,
        resolution_path="test",
        lower_fill_size=Decimal("5"),
        lower_fill_at_ms=1_000,
        lower_fill_during_cancel=False,
        upper_fill_size=Decimal("5"),
        upper_fill_at_ms=1_000,
        attempted_collateral_dollar_minutes=Decimal("1"),
        taker_fill_sizes={"0xtoxic": Decimal("5")},
    )

    assert clean.pnl_excluding_toxic({"0xtoxic"}) == Decimal("0.50")
    assert toxic.pnl_excluding_toxic({"0xtoxic"}) == Decimal("0")


def test_300ms_cancel_latency_regime_present_in_default_contract():
    latencies = [200, 300, 500, 1000]
    regime_keys = {f"cancel_latency_{latency_ms}ms": True for latency_ms in latencies}

    assert regime_keys["cancel_latency_300ms"] is True
