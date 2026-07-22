"""Tests for Bot D audit logging — NWS vetoes + forecast-entry snapshots.

K2.6 audit follow-up 2026-04-21.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from bots.bot_d_weather.audit import (
    _parse_nws_reason,
    log_entry_attempt_snapshot,
    log_forecast_entry_snapshot,
    log_nws_vetoes,
    log_scan_summary,
)
from core.db import Base, Event

# ----- Fake decision/market shapes (avoid real strategy dependency) -----

@dataclass
class _M:
    gamma_id: str = "cid-1"
    yes_token_id: str = "yes1"
    no_token_id: str = "no1"
    city: str = "Dallas"
    date: str = "2026-04-22"
    temp_type: str = "high"
    range_low_f: float | None = 72.0
    range_high_f: float | None = 73.0


@dataclass
class _D:
    market: _M
    gfs_probability: float
    market_probability: float
    gross_edge: float
    net_edge: float
    edge: float
    side: str
    reason: str
    forecast_mean_f: float
    forecast_std_f: float
    ensemble_count: int
    decided_at: datetime


def _make_decision(side: str, reason: str) -> _D:
    return _D(
        market=_M(),
        gfs_probability=0.40, market_probability=0.20,
        gross_edge=0.20, net_edge=0.18, edge=0.18,
        side=side, reason=reason,
        forecast_mean_f=72.5, forecast_std_f=1.8, ensemble_count=82,
        decided_at=datetime.now(UTC),
    )


@pytest.fixture
def sf(tmp_path):
    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


# ----- _parse_nws_reason regex -----

class TestParseNwsReason:
    def test_extracts_all_fields(self):
        out = _parse_nws_reason("nws_disagrees (mean=72.3 vs nws=68.1, threshold=2.5)")
        assert out["nws_temp_f"] == 68.1
        assert abs(out["nws_disagreement_f"] - 4.2) < 1e-6
        assert out["veto_threshold_f"] == 2.5

    def test_handles_negative_numbers(self):
        out = _parse_nws_reason("nws_disagrees (mean=-5.2 vs nws=-8.9, threshold=3.0)")
        assert out["nws_temp_f"] == -8.9
        assert abs(out["nws_disagreement_f"] - 3.7) < 1e-6

    def test_returns_none_on_malformed(self):
        out = _parse_nws_reason("nws_disagrees malformed text")
        assert out["nws_temp_f"] is None
        assert out["nws_disagreement_f"] is None


# ----- log_nws_vetoes -----

class TestLogNwsVetoes:
    def test_writes_event_for_veto(self, sf):
        decs = [
            _make_decision("SKIP", "nws_disagrees (mean=72.3 vs nws=68.1, threshold=2.5)"),
            _make_decision("BUY_YES", "model 0.40 > market 0.20"),  # not a veto
        ]
        n = log_nws_vetoes(sf, decs)
        assert n == 1
        with sf() as s:
            events = list(s.scalars(select(Event).where(Event.event_type == "bot_d.nws_veto")).all())
            assert len(events) == 1
            assert events[0].payload["nws_temp_f"] == 68.1
            assert events[0].payload["city"] == "Dallas"
            assert events[0].payload["net_edge"] == 0.18
            assert events[0].payload["skip_reason_code"] == "nws_disagrees"
            assert events[0].payload["setup_tier"] in {"A", "B", "C"}
            assert "distance_from_threshold_f" in events[0].payload

    def test_skips_non_nws_skips(self, sf):
        decs = [_make_decision("SKIP", "net_edge |0.020| below threshold 0.1")]
        assert log_nws_vetoes(sf, decs) == 0

    def test_empty_list(self, sf):
        assert log_nws_vetoes(sf, []) == 0

    def test_no_commit_overhead_when_nothing_to_write(self, sf):
        # Should return early without opening a session
        assert log_nws_vetoes(sf, [_make_decision("BUY_YES", "normal")]) == 0


# ----- log_forecast_entry_snapshot -----

class TestLogForecastEntrySnapshot:
    def test_writes_event_with_order_context(self, sf):
        dec = _make_decision("BUY_YES", "model 0.40 > market 0.20")
        log_forecast_entry_snapshot(
            sf, dec,
            order_id="ord-abc",
            size_usd=Decimal("15.00"),
            limit_price=Decimal("0.21"),
        )
        with sf() as s:
            events = list(s.scalars(select(Event).where(Event.event_type == "bot_d.forecast_entry")).all())
            assert len(events) == 1
            p = events[0].payload
            assert p["order_id"] == "ord-abc"
            assert p["size_usd"] == "15.00"
            assert p["limit_price"] == "0.21"
            assert p["forecast_mean_f"] == 72.5
            assert p["side"] == "BUY_YES"
            assert p["city"] == "Dallas"
            assert p["paper_epoch_id"] == "station_v1_2026_04_29"
            assert p["paper_epoch_start"].startswith("2026-04-29T19:10:00")
            assert p["skip_reason_code"] == "entry_signal"
            assert p["nws_lane"] == "entry"

    def test_writes_entry_attempt_snapshot(self, sf):
        dec = _make_decision("BUY_YES", "model 0.40 > market 0.20")
        log_entry_attempt_snapshot(
            sf,
            dec,
            placed=False,
            reason="live_order_notional_cap",
            size_usd=Decimal("4.25"),
            size_shares=Decimal("5"),
            limit_price=Decimal("0.85"),
            depth_usd=Decimal("60.00"),
            required_depth_usd=Decimal("25.00"),
        )
        with sf() as s:
            ev = s.scalars(select(Event).where(Event.event_type == "bot_d.entry_attempt")).one()
            assert ev.payload["placed"] is False
            assert ev.payload["entry_attempt_reason"] == "live_order_notional_cap"
            assert ev.payload["depth_lane"] == "depth_gte_50"
            assert ev.payload["size_shares"] == "5"

    def test_message_is_bounded(self, sf):
        """Very long reasons shouldn't blow up the message column."""
        dec = _make_decision("BUY_YES", "x" * 1000)
        log_forecast_entry_snapshot(sf, dec, order_id="o")
        with sf() as s:
            ev = s.scalars(select(Event)).first()
            assert len(ev.message) <= 500


class TestLogScanSummary:
    def test_writes_scan_summary_event(self, sf):
        payload = {
            "raw_markets": 16,
            "kept_markets": 11,
            "evaluated": 11,
            "missing_forecasts": 0,
            "non_skip": 0,
            "after_one_bet_per_event": 0,
            "tradeable": 0,
            "wave": 0,
            "isolated": 0,
            "forecast_sources": {"nws_fallback": 11},
            "skip_reasons": {"below_threshold": 9, "observed_constraint": 2},
            "top_abs_net_edge": 0.035,
            "top_positive_net_edge": 0.035,
            "top_negative_net_edge": -0.007,
        }
        log_scan_summary(sf, payload)
        with sf() as s:
            ev = s.scalars(select(Event).where(Event.event_type == "bot_d.scan_summary")).one()
            assert ev.payload["evaluated"] == 11
            assert ev.payload["skip_reasons"]["below_threshold"] == 9
            assert "top_pos=+0.035" in ev.message
