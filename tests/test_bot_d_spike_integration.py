"""Integration tests for Bot D-Spike gate composition + scan pipeline.

Covers gaps identified in docs/reports/bot-d-spike-deployment-audit-2026-05-07.md:
- Gate ordering: when multiple blockers apply, the highest-priority one fires.
- Cap enforcement: max_concurrent (positions), max_deployed (USD), dedupe.
- ENTRY_HALT respected.
- Full scan_once() end-to-end with multiple eligible candidates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from bots.bot_d_spike import config as cfg
from bots.bot_d_spike.discovery import (
    SpikeMarket,
    candidate_from_market,
)
from bots.bot_d_spike.executor import SpikeExecutor
from bots.bot_d_spike.strategy import decide_entry
from core.clob import OrderBook, OrderResponse
from core.config import reset_settings
from core.db import (
    Base,
    Order,
    Position,
    Trade,
    get_session_factory,
    init_db,
    reset_engine,
)


@dataclass
class FakeClob:
    book: OrderBook
    paper: bool = True
    placed: list[dict] | None = None

    def _effective_paper(self) -> bool:
        return self.paper

    def get_book(self, token_id: str) -> OrderBook:
        # Allow multiple tokens by returning the same book (good enough for these tests)
        return OrderBook(
            token_id=token_id,
            bids=self.book.bids,
            asks=self.book.asks,
            timestamp=self.book.timestamp,
        )

    def place_limit(self, **kwargs) -> OrderResponse:
        if self.placed is None:
            self.placed = []
        self.placed.append(kwargs)
        return OrderResponse(
            order_id=f"paper-test-{len(self.placed)}",
            status="PAPER_OPEN",
            raw=kwargs,
        )


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


def _book(*, bid: str = "0.04", ask: str = "0.05", ask_size: str = "100") -> OrderBook:
    return OrderBook(
        token_id="yes-token",
        bids=[(Decimal(bid), Decimal("200"))],
        asks=[(Decimal(ask), Decimal(ask_size))],
        timestamp=datetime(2026, 5, 7, 0, 0, tzinfo=UTC).timestamp(),
    )


def _market(
    *,
    city: str = "Hong Kong",
    condition_id: str = "c1",
    token_suffix: str = "1",
) -> SpikeMarket:
    return SpikeMarket(
        gamma_id=condition_id,
        condition_id=condition_id,
        slug=f"weather-market-{condition_id}",
        question=f"Will the highest temperature in {city} be 19°C on May 7?",
        city=city,
        date="May 7",
        temp_type="high",
        direction="exact",
        bucket="19C",
        yes_token_id=f"yes-token-{token_suffix}",
        no_token_id=f"no-token-{token_suffix}",
        end_date=datetime.now(UTC) + timedelta(hours=8),
        yes_price_hint=Decimal("0.05"),
        volume_24h_usd=Decimal("1000"),
    )


# ---------- Gate-coverage tests ----------


def test_executor_blocks_dedupe_same_bot_open_order(temp_db):
    """Re-entering same (condition, token) when an open paper order exists must
    return reason='dedupe', not silently double-up."""
    candidate = candidate_from_market(_market(condition_id="dedup"), clob=FakeClob(_book()))
    assert candidate is not None
    with get_session_factory()() as s:
        s.add(
            Order(
                order_id="paper-existing",
                bot_id="bot_d_spike",
                condition_id="dedup",
                token_id="yes-token-1",
                side="BUY",
                price=Decimal("0.05"),
                size=Decimal("40"),
                status="PAPER_OPEN",
            )
        )
        s.commit()
    result = SpikeExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))
    assert result.placed is False
    assert result.reason == "dedupe"


def test_executor_blocks_dedupe_same_bot_open_position(temp_db):
    """Re-entering same (condition, token) when an open position exists must
    return reason='dedupe' even if no orders are pending."""
    candidate = candidate_from_market(_market(condition_id="dedup-pos"), clob=FakeClob(_book()))
    assert candidate is not None
    with get_session_factory()() as s:
        s.add(
            Position(
                bot_id="bot_d_spike",
                condition_id="dedup-pos",
                token_id="yes-token-1",
                side="YES",
                size=Decimal("40"),
                avg_price=Decimal("0.05"),
                cost_basis_usd=Decimal("2"),
                status="OPEN",
            )
        )
        s.commit()
    result = SpikeExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))
    assert result.placed is False
    assert result.reason == "dedupe"


def test_executor_enforces_max_concurrent(temp_db, monkeypatch):
    """When at max_concurrent, the next entry must reject with reason='max_concurrent'."""
    monkeypatch.setattr(cfg, "MAX_CONCURRENT_POSITIONS", 3)
    monkeypatch.setattr(cfg, "MAX_DAILY_ENTRIES", 100)  # don't trip daily cap first
    monkeypatch.setattr(cfg, "MAX_DEPLOYED_USD", Decimal("1000"))  # don't trip USD cap
    with get_session_factory()() as s:
        for i in range(3):
            s.add(
                Position(
                    bot_id="bot_d_spike",
                    condition_id=f"existing-{i}",
                    token_id=f"existing-token-{i}",
                    side="YES",
                    size=Decimal("40"),
                    avg_price=Decimal("0.05"),
                    cost_basis_usd=Decimal("2"),
                    status="OPEN",
                )
            )
        s.commit()
    candidate = candidate_from_market(_market(condition_id="new"), clob=FakeClob(_book()))
    assert candidate is not None
    result = SpikeExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))
    assert result.placed is False
    assert result.reason == "max_concurrent"


def test_executor_enforces_max_deployed(temp_db, monkeypatch):
    """When deployed cost basis is at cap, next entry must reject with reason='max_deployed'."""
    monkeypatch.setattr(cfg, "MAX_DEPLOYED_USD", Decimal("5"))
    monkeypatch.setattr(cfg, "MAX_CONCURRENT_POSITIONS", 100)  # don't trip concurrent first
    monkeypatch.setattr(cfg, "MAX_DAILY_ENTRIES", 100)
    monkeypatch.setattr(cfg, "PER_POSITION_SIZE_USD", Decimal("2"))
    with get_session_factory()() as s:
        # 4 USD already deployed (need 2 more, cap is 5 → 4+2 > 5 → blocked)
        s.add(
            Position(
                bot_id="bot_d_spike",
                condition_id="existing",
                token_id="existing-token",
                side="YES",
                size=Decimal("80"),
                avg_price=Decimal("0.05"),
                cost_basis_usd=Decimal("4"),
                status="OPEN",
            )
        )
        s.commit()
    candidate = candidate_from_market(_market(condition_id="new"), clob=FakeClob(_book()))
    assert candidate is not None
    result = SpikeExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))
    assert result.placed is False
    assert result.reason == "max_deployed"


def test_executor_respects_entry_halt_env_flag(temp_db, monkeypatch):
    """If BOT_D_SPIKE_ENTRY_HALT is set, no entries are placed."""
    monkeypatch.setattr(cfg, "ENTRY_HALT", True)
    candidate = candidate_from_market(_market(), clob=FakeClob(_book()))
    assert candidate is not None
    result = SpikeExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))
    assert result.placed is False
    assert result.reason == "entry_halt"


# ---------- Gate-priority test ----------


def test_gate_priority_paper_guard_fires_before_dedupe(temp_db):
    """If both paper-mode-violation AND dedupe could fire, paper guard wins
    (paper_only_guard appears earlier in _blocker())."""
    # Insert a duplicate order to also trigger dedupe
    candidate = candidate_from_market(_market(condition_id="both"), clob=FakeClob(_book()))
    assert candidate is not None
    with get_session_factory()() as s:
        s.add(
            Order(
                order_id="paper-existing",
                bot_id="bot_d_spike",
                condition_id="both",
                token_id="yes-token-1",
                side="BUY",
                price=Decimal("0.05"),
                size=Decimal("40"),
                status="PAPER_OPEN",
            )
        )
        s.commit()
    # Live mode + dedupe both true; expect paper_only_guard wins
    clob = FakeClob(_book(), paper=False)
    result = SpikeExecutor(clob).try_enter(decide_entry(candidate))
    assert result.placed is False
    assert result.reason == "paper_only_guard"
    assert clob.placed is None  # never even attempted


# ---------- Entry-point scan pipeline tests ----------


def test_scan_once_places_multiple_eligible_and_caps_correctly(temp_db, monkeypatch):
    """Given 5 candidates and MAX_DAILY_ENTRIES=3, scan_once places exactly 3.

    This exercises the real entrypoint wiring: forced paper ClobWrapperV2,
    find_eligible_candidates(), SpikeExecutor, the loop's daily-cap break,
    and the resolution reconciliation call.
    """
    import bots.bot_d_spike.__main__ as spike_main

    monkeypatch.setattr(cfg, "MAX_DAILY_ENTRIES", 3)
    monkeypatch.setattr(cfg, "MAX_CONCURRENT_POSITIONS", 100)
    monkeypatch.setattr(cfg, "MAX_DEPLOYED_USD", Decimal("1000"))

    cities = ["Hong Kong", "Tokyo", "Wellington", "Shenzhen", "Madrid"]
    source_clob = FakeClob(_book())
    candidates = [
        candidate_from_market(
            _market(city=city, condition_id=f"cond-{i}", token_suffix=str(i)),
            clob=source_clob,
        )
        for i, city in enumerate(cities)
    ]
    assert all(c is not None for c in candidates)
    candidates.sort(key=lambda c: (c.market.end_date, c.best_ask, c.city))

    runtime_clob = FakeClob(_book())
    wrappers: list[dict] = []
    reconciled: list[bool] = []

    def fake_wrapper(*, keystore=None, paper_override=False):
        wrappers.append({"keystore": keystore, "paper_override": paper_override})
        return runtime_clob

    def fake_candidates(*, clob, limit):
        assert clob is runtime_clob
        assert limit == 123
        return candidates

    monkeypatch.setattr(spike_main, "ClobWrapperV2", fake_wrapper)
    monkeypatch.setattr(spike_main, "find_eligible_candidates", fake_candidates)
    monkeypatch.setattr(
        SpikeExecutor,
        "reconcile_resolutions",
        lambda self: reconciled.append(True) or 0,
    )

    placed = spike_main.scan_once(dry_run=False, gamma_limit=123)

    assert placed == 3
    assert wrappers == [{"keystore": None, "paper_override": True}]
    assert reconciled == [True]
    with get_session_factory()() as s:
        assert s.query(Order).filter_by(bot_id="bot_d_spike").count() == 3
        assert s.query(Trade).filter_by(bot_id="bot_d_spike", side="BUY").count() == 3
        assert s.query(Position).filter_by(bot_id="bot_d_spike", status="OPEN").count() == 3


def test_scan_once_dry_run_does_not_write_or_reconcile(temp_db, monkeypatch):
    """Dry-run scan logs candidates but never writes orders or resolves positions."""
    import bots.bot_d_spike.__main__ as spike_main

    candidate = candidate_from_market(_market(), clob=FakeClob(_book()))
    assert candidate is not None
    runtime_clob = FakeClob(_book())

    monkeypatch.setattr(
        spike_main,
        "ClobWrapperV2",
        lambda *, keystore=None, paper_override=False: runtime_clob,
    )
    monkeypatch.setattr(
        spike_main,
        "find_eligible_candidates",
        lambda *, clob, limit: [candidate],
    )
    monkeypatch.setattr(
        SpikeExecutor,
        "reconcile_resolutions",
        lambda self: pytest.fail("dry-run should not reconcile"),
    )

    placed = spike_main.scan_once(dry_run=True, gamma_limit=500)

    assert placed == 0
    assert runtime_clob.placed is None
    with get_session_factory()() as s:
        assert s.query(Order).filter_by(bot_id="bot_d_spike").count() == 0
        assert s.query(Trade).filter_by(bot_id="bot_d_spike").count() == 0
        assert s.query(Position).filter_by(bot_id="bot_d_spike").count() == 0


# ---------- Cross-bot isolation test ----------


def test_executor_does_not_modify_other_bot_rows(temp_db):
    """After bot_d_spike places its entry, no rows owned by other bot_ids are
    touched. This guards against accidental cross-bot writes."""
    candidate = candidate_from_market(_market(), clob=FakeClob(_book()))
    assert candidate is not None
    with get_session_factory()() as s:
        s.add(
            Position(
                bot_id="bot_d_live_probe",
                condition_id="other-bot",  # different condition so no overlap
                token_id="other-token",
                side="NO",
                size=Decimal("5"),
                avg_price=Decimal("0.8"),
                cost_basis_usd=Decimal("4"),
                status="OPEN",
            )
        )
        s.add(
            Position(
                bot_id="bot_g",
                condition_id="bot-g-cond",
                token_id="bot-g-token",
                side="YES",
                size=Decimal("100"),
                avg_price=Decimal("0.04"),
                cost_basis_usd=Decimal("4"),
                status="OPEN",
            )
        )
        s.commit()
    SpikeExecutor(FakeClob(_book())).try_enter(decide_entry(candidate))

    # Verify other bots' rows untouched
    with get_session_factory()() as s:
        live_probe_pos = s.query(Position).filter_by(bot_id="bot_d_live_probe").one()
        assert live_probe_pos.size == Decimal("5")
        assert live_probe_pos.avg_price == Decimal("0.8")
        assert live_probe_pos.status == "OPEN"

        bot_g_pos = s.query(Position).filter_by(bot_id="bot_g").one()
        assert bot_g_pos.size == Decimal("100")
        assert bot_g_pos.avg_price == Decimal("0.04")
        assert bot_g_pos.status == "OPEN"

        # Spike got its own position
        spike_pos = s.query(Position).filter_by(bot_id="bot_d_spike", status="OPEN").one()
        assert spike_pos.condition_id == candidate.market.condition_id
