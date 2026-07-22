"""Tests for Bot H Maker V2 (paper-only per ADR-134) — Phase 1 recorder.

Covers:

- The cell filter mirrors ADR-134 (politics 0-10c + sports 10-20c only).
- The category classifier matches the maker-flow simulator's CASE
  expression (`m_v2.category` in `/tmp/track1_maker_sim.py`).
- The recorder filter accepts in-band markets and rejects out-of-band /
  out-of-category / under-volume markets.
- The recorder DB schema initialises cleanly and the writer's task
  shapes round-trip through SQLite.
- The discovery dataclass round-trips through `markets`-table upsert
  semantics.
"""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal

import pytest

from bots.bot_h_maker_v2 import config as cfg
from bots.bot_h_maker_v2.capture import WriteTask, _execute_task
from bots.bot_h_maker_v2.config import (
    ACTIVE_QUOTE_CELLS,
    is_active_quote_cell,
    question_to_category,
)
from bots.bot_h_maker_v2.discovery import _market_in_filter
from bots.bot_h_maker_v2.schema import init_db

# ---------------------------------------------------------------------------
# Cell filter (ADR-134 narrow scope)
# ---------------------------------------------------------------------------


def test_active_quote_cells_match_adr_134():
    labels = {c.label for c in ACTIVE_QUOTE_CELLS}
    assert labels == {"politics_0_10c", "sports_10_20c"}, (
        "ADR-134 restricts active quotes to politics 0-10c and sports 10-20c only. "
        "Adding more cells requires a new ADR."
    )


def test_is_active_quote_cell_matches_top_2_passing_cells():
    assert is_active_quote_cell("politics", Decimal("0.05")) is True
    assert is_active_quote_cell("sports", Decimal("0.15")) is True
    # politics 30-40c was the killed mirage cell; must NOT be in active scope
    assert is_active_quote_cell("politics", Decimal("0.35")) is False
    # awards 0-10c was killed by robustness check
    assert is_active_quote_cell("awards", Decimal("0.05")) is False
    # weather is excluded entirely (no rebate, Strategy E2 covers taker side)
    assert is_active_quote_cell("weather", Decimal("0.05")) is False
    # Below politics range
    assert is_active_quote_cell("politics", Decimal("0.10")) is False  # exclusive upper
    # Below sports range
    assert is_active_quote_cell("sports", Decimal("0.09")) is False
    # At sports lower bound
    assert is_active_quote_cell("sports", Decimal("0.10")) is True


# ---------------------------------------------------------------------------
# Category classifier (mirrors WANGZJ simulator)
# ---------------------------------------------------------------------------


def test_question_to_category_matches_maker_sim_classifier():
    """Classifier mirrors `m_v2.category` CASE in `/tmp/track1_maker_sim.py`
    on the bot host. Awards keys are oscar/nobel/grammy only — bare "Best
    Picture" does NOT classify as awards in the simulator, so it must
    not classify here either, otherwise the recorder's category
    distribution will diverge from the historical analysis."""
    assert question_to_category("Will the temperature in NYC be above 80F?") == "weather"
    assert question_to_category("Will Bitcoin hit $200,000?") == "crypto"
    assert question_to_category("Will ETH cross $5000 by year-end?") == "crypto"
    assert question_to_category("Will Sanchez win the 2026 primary?") == "politics"
    assert question_to_category("Will Spain win the World Cup?") == "sports"
    assert question_to_category("Will the Lakers reach the NBA finals?") == "sports"
    assert question_to_category("Will Oppenheimer win Best Picture Oscar?") == "awards"
    assert question_to_category("Will the Nobel committee award X?") == "awards"
    # Bare "Best Picture" without "oscar" matches the simulator's _other,
    # not awards — keep parity with WANGZJ historical analysis.
    assert question_to_category("Will Oppenheimer win Best Picture?") == "_other"
    assert question_to_category("Random meta question?") == "_other"


# ---------------------------------------------------------------------------
# Recorder filter
# ---------------------------------------------------------------------------


def test_recorder_filter_accepts_in_band_market():
    assert _market_in_filter(
        category="politics",
        yes_price=Decimal("0.05"),
        volume_24h_usd=Decimal("5000"),
    ) is True


def test_recorder_filter_rejects_out_of_category():
    assert _market_in_filter(
        category="weather",
        yes_price=Decimal("0.05"),
        volume_24h_usd=Decimal("5000"),
    ) is False
    assert _market_in_filter(
        category="_other",
        yes_price=Decimal("0.05"),
        volume_24h_usd=Decimal("5000"),
    ) is False


def test_recorder_filter_rejects_above_50_cents():
    assert _market_in_filter(
        category="politics",
        yes_price=Decimal("0.51"),
        volume_24h_usd=Decimal("5000"),
    ) is False


def test_recorder_filter_rejects_below_volume_floor():
    assert _market_in_filter(
        category="politics",
        yes_price=Decimal("0.05"),
        volume_24h_usd=Decimal("500"),  # below 1000 floor
    ) is False


def test_recorder_filter_rejects_unknown_yes_price():
    assert _market_in_filter(
        category="politics",
        yes_price=None,
        volume_24h_usd=Decimal("5000"),
    ) is False


# ---------------------------------------------------------------------------
# Recorder DB schema + writer task round-trip
# ---------------------------------------------------------------------------


@pytest.fixture()
def recorder_db(tmp_path) -> sqlite3.Connection:
    path = tmp_path / "test_maker_recorder.db"
    conn = init_db(path)
    yield conn
    conn.close()


def test_schema_creates_all_tables(recorder_db: sqlite3.Connection):
    rows = recorder_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {r[0] for r in rows}
    assert "markets" in table_names
    assert "pm_events" in table_names
    assert "heartbeats" in table_names


def test_schema_pragma_journal_mode_is_wal(recorder_db: sqlite3.Connection):
    mode = recorder_db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_writer_persists_pm_event(recorder_db: sqlite3.Connection):
    payload = {"asset_id": "tok-yes", "price": "0.05", "size": "100"}
    task = WriteTask(
        kind="pm_event",
        row={
            "received_at_ms": 1714262400000,
            "subscription_id": "test-sub",
            "event_type": "last_trade_price",
            "asset_id": "tok-yes",
            "condition_id": "cond-1",
            "payload_json": json.dumps(payload),
        },
    )
    _execute_task(recorder_db, task)
    recorder_db.commit()
    row = recorder_db.execute(
        "SELECT received_at_ms, subscription_id, event_type, asset_id, condition_id "
        "FROM pm_events WHERE asset_id=?",
        ("tok-yes",),
    ).fetchone()
    assert row == (1714262400000, "test-sub", "last_trade_price", "tok-yes", "cond-1")


def test_writer_upserts_market_on_repeated_discovery(recorder_db: sqlite3.Connection):
    base_row = {
        "condition_id": "cond-A",
        "yes_token_id": "yes-tok",
        "no_token_id": "no-tok",
        "category": "politics",
        "question": "Will X win?",
        "end_date_ts": 1714262400,
        "discovered_at_ms": 100,
        "last_seen_at_ms": 100,
        "initial_yes_price": 0.05,
        "volume_24h_usd": 5000.0,
        "status": "ACTIVE",
    }
    _execute_task(recorder_db, WriteTask(kind="market", row=base_row))
    update_row = dict(base_row)
    update_row["last_seen_at_ms"] = 200
    update_row["volume_24h_usd"] = 7500.0
    _execute_task(recorder_db, WriteTask(kind="market", row=update_row))
    recorder_db.commit()
    rows = recorder_db.execute(
        "SELECT condition_id, last_seen_at_ms, volume_24h_usd FROM markets"
    ).fetchall()
    assert len(rows) == 1, "Discovery refresh must UPSERT, not INSERT"
    assert rows[0] == ("cond-A", 200, 7500.0)


def test_writer_persists_heartbeat(recorder_db: sqlite3.Connection):
    task = WriteTask(
        kind="heartbeat",
        row={
            "received_at_ms": 1714262500000,
            "subscription_id": "bot_h_maker_v2/all",
            "asset_id_count": 200,
            "note": "events=book=10,price_change=5",
        },
    )
    _execute_task(recorder_db, task)
    recorder_db.commit()
    row = recorder_db.execute("SELECT asset_id_count, note FROM heartbeats").fetchone()
    assert row == (200, "events=book=10,price_change=5")


# ---------------------------------------------------------------------------
# Config sanity
# ---------------------------------------------------------------------------


def test_recorder_categories_excludes_weather():
    """Weather has no builder-code rebate (0% per fee schedule) so the
    maker bot has no upside there. Strategy E + E2 already cover the
    weather category at the taker side."""
    assert "weather" not in cfg.RECORDER_CATEGORIES


def test_paper_only_flag_is_true():
    """Phase 1 is recorder-only; Phase 2 will still be paper-only until
    a separate ADR. ADR-134 forbids live mode without future ADR."""
    assert cfg.PAPER_ONLY is True


def test_max_tokens_subscribed_protects_wss_resource_use():
    """Defensive cap to prevent runaway subscription on election-day
    politics market surges. 600 tokens = 300 markets."""
    assert cfg.MAX_TOKENS_SUBSCRIBED <= 1000


# ---------------------------------------------------------------------------
# Event-key extraction (covers the three observed Polymarket WSS payload shapes)
# ---------------------------------------------------------------------------


def test_extract_event_keys_handles_book_payload():
    """`book` events have top-level asset_id (decimal) AND market (hex).
    Both should be captured: asset_id used for token-to-market lookup,
    condition_id taken from `market` directly so non-subscribed markets
    are still groupable at analysis time."""
    from bots.bot_h_maker_v2.capture import _extract_event_keys

    payload = {
        "market": "0xF00D000000000000000000000000000000000019ca8d8c265c84d24755399cf5",
        "asset_id": "103845791232328975452762372781150730610824357544180691092497335946993481308222",
        "bids": [{"price": "0.04", "size": "100"}],
        "asks": [{"price": "0.05", "size": "100"}],
        "event_type": "book",
    }
    asset_id, condition_id = _extract_event_keys(payload)
    assert asset_id == "103845791232328975452762372781150730610824357544180691092497335946993481308222"
    assert condition_id == "0xF00D000000000000000000000000000000000019ca8d8c265c84d24755399cf5"


def test_extract_event_keys_handles_price_change_payload():
    """`price_change` events nest asset_id inside a price_changes array
    and put condition_id at top-level under `market`. Pre-fix, my handler
    walked top-level keys only and stored the hex condition_id as
    asset_id, leaving condition_id null. This test pins the fixed
    behaviour."""
    from bots.bot_h_maker_v2.capture import _extract_event_keys

    payload = {
        "market": "0xF00D00000000000000000000000000000000001acba988679f30d19ce4a8d3c5",
        "price_changes": [
            {"asset_id": "113710393279527763530378008437597279835126076957440571149632824827852634668972", "price": "0.961"},
            {"asset_id": "29494240399215886054557010650682484978723635190716893569856542948072305979460", "price": "0.039"},
        ],
        "event_type": "price_change",
    }
    asset_id, condition_id = _extract_event_keys(payload)
    assert asset_id == "113710393279527763530378008437597279835126076957440571149632824827852634668972"
    assert condition_id == "0xF00D00000000000000000000000000000000001acba988679f30d19ce4a8d3c5"


def test_extract_event_keys_handles_new_market_payload():
    """`new_market` events have explicit `condition_id` (not `market`)
    and `clob_token_ids` (not `asset_id`)."""
    from bots.bot_h_maker_v2.capture import _extract_event_keys

    payload = {
        "id": "2197779",
        "condition_id": "0xF00D00000000000000000000000000000000001b92d7e432012cebd88a729212",
        "clob_token_ids": [
            "98949720998774655014131769748936022035183942209748894002498217709002263752422",
            "35006843403404454268571082212313371387891958682206442462442907671846491672383",
        ],
        "event_type": "new_market",
    }
    asset_id, condition_id = _extract_event_keys(payload)
    assert asset_id == "98949720998774655014131769748936022035183942209748894002498217709002263752422"
    assert condition_id == "0xF00D00000000000000000000000000000000001b92d7e432012cebd88a729212"


def test_extract_event_keys_handles_empty_payload():
    """Heartbeat / reconnect events may have no useful keys. Both should
    be None — the recorder still persists them with NULL ids."""
    from bots.bot_h_maker_v2.capture import _extract_event_keys

    asset_id, condition_id = _extract_event_keys({})
    assert asset_id is None
    assert condition_id is None


# ---------------------------------------------------------------------------
# Write-time broadcast filter (ADR-134 Session 256 amendment)
# ---------------------------------------------------------------------------


def test_always_keep_event_types_includes_operational_and_discovery_events():
    """new_market is the forward-discovery feed; reconnect/disconnect/
    heartbeat are operational metadata. None of these scale with market
    count, so dropping any of them would discard signal we use without
    saving meaningful disk."""
    from bots.bot_h_maker_v2.capture import ALWAYS_KEEP_EVENT_TYPES

    assert "new_market" in ALWAYS_KEEP_EVENT_TYPES
    assert "reconnect" in ALWAYS_KEEP_EVENT_TYPES
    assert "disconnect" in ALWAYS_KEEP_EVENT_TYPES
    assert "heartbeat" in ALWAYS_KEEP_EVENT_TYPES
    # The volume-dominant types must NOT be in the always-keep set —
    # otherwise the filter does nothing.
    for t in ("book", "price_change", "last_trade_price", "best_bid_ask"):
        assert t not in ALWAYS_KEEP_EVENT_TYPES


@pytest.mark.asyncio
async def test_handler_drops_broadcast_event_for_non_subscribed_market():
    """A `book` event whose asset_id isn't in token_to_condition must be
    dropped at write time, not enqueued for SQLite write. This is the
    main lever for ADR-134's 30 GB / 30 days disk budget."""
    from bots.bot_h_maker_v2.capture import RecorderState, _make_pm_handler
    from core.polymarket_ws import WSSEvent

    state = RecorderState()
    state.token_to_condition = {
        "subscribed-decimal-token": "0xcafe",
    }
    handler = _make_pm_handler(state)
    # asset_id is NOT in token_to_condition → must be dropped
    event = WSSEvent(
        event_type="book",
        payload={
            "market": "0xdeadbeef",
            "asset_id": "non-subscribed-decimal-token",
            "bids": [],
            "asks": [],
        },
        received_at_ms=1_000_000_000,
        subscription_id="bot_h_maker_v2/all",
    )
    await handler(event)
    assert state.queue.qsize() == 0
    assert state.event_counts["_dropped_book"] == 1
    assert state.event_counts.get("book", 0) == 0


@pytest.mark.asyncio
async def test_handler_keeps_event_for_subscribed_market():
    """A `book` event whose asset_id IS in token_to_condition must be
    enqueued (not dropped). Resolved condition_id must come from the
    token-to-condition map (gamma-discovered), preferred over the raw
    payload `market` field."""
    from bots.bot_h_maker_v2.capture import RecorderState, _make_pm_handler
    from core.polymarket_ws import WSSEvent

    state = RecorderState()
    state.token_to_condition = {
        "subscribed-decimal-token": "cond-from-gamma",
    }
    handler = _make_pm_handler(state)
    event = WSSEvent(
        event_type="book",
        payload={
            "market": "0xpayload-condition-id",  # different from gamma's
            "asset_id": "subscribed-decimal-token",
            "bids": [],
            "asks": [],
        },
        received_at_ms=1_000_000_000,
        subscription_id="bot_h_maker_v2/all",
    )
    await handler(event)
    assert state.queue.qsize() == 1
    task: WriteTask = state.queue.get_nowait()
    assert task.kind == "pm_event"
    # Gamma-derived condition_id wins over the raw payload field
    assert task.row["condition_id"] == "cond-from-gamma"
    assert task.row["asset_id"] == "subscribed-decimal-token"
    assert state.event_counts["book"] == 1


@pytest.mark.asyncio
async def test_handler_always_keeps_new_market_event_even_if_unsubscribed():
    """`new_market` is the forward-discovery feed; we want to know about
    every newly-created Polymarket market regardless of subscription."""
    from bots.bot_h_maker_v2.capture import RecorderState, _make_pm_handler
    from core.polymarket_ws import WSSEvent

    state = RecorderState()
    state.token_to_condition = {}  # no subscriptions at all
    handler = _make_pm_handler(state)
    event = WSSEvent(
        event_type="new_market",
        payload={
            "condition_id": "0xnew-market",
            "clob_token_ids": ["unknown-token-1", "unknown-token-2"],
            "question": "Will X happen?",
        },
        received_at_ms=1_000_000_000,
        subscription_id="bot_h_maker_v2/all",
    )
    await handler(event)
    assert state.queue.qsize() == 1
    assert state.event_counts["new_market"] == 1
    assert state.event_counts.get("_dropped_new_market", 0) == 0
