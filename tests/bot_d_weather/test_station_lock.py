"""Tests for Bot D Station Lock — classifier, entry gate, and paper-only guard.

Required cases (handoff section 13):
  1.  High bounded 'already_no' when station high exceeds upper bound.
  2.  High bounded stays 'pending' when station high below lower bound
      before local day complete.
  3.  High bounded 'locked_no' when local day complete, station high below lower bound.
  4.  Low bounded 'already_no' when station low drops below lower bound.
  5.  Low bounded stays 'pending' when station low above upper bound before day complete.
  6.  'above' and 'higher' directions parse/behave identically.
  7.  Celsius market evaluates in native (C) unit before F conversion.
  8.  Rounding disagreement produces confidence='unsafe'.
  9.  Missing station spec blocks entry.
  10. WU station mutation blocks entry.
  11. Paper order uses 'bot_d_station_lock', not 'bot_d' or 'bot_d_live_probe'.
  12. Live mode cannot be enabled; _assert_paper_only must raise for live envs.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from bots.bot_d_weather.discovery import WeatherMarket
from bots.bot_d_weather.source_monitor import StationDaySnapshot
from bots.bot_d_weather.station_lock import (
    BOT_ID,
    _assert_paper_only,
    classify_station_lock,
    run_station_lock_scan,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _market(
    *,
    city: str = "Chicago",
    temp_type: str = "high",
    direction: str = "between",
    lo_f: float | None = 58.0,
    hi_f: float | None = 59.0,
    unit: str = "F",
    yes_price: str = "0.72",
    gamma_id: str = "test-cond-id",
    date: str = "2026-05-13",
    end_date: datetime | None = datetime(2026, 5, 13, 23, 59, tzinfo=UTC),
) -> WeatherMarket:
    return WeatherMarket(
        gamma_id=gamma_id,
        slug="test-slug",
        question="Will the highest temperature in Chicago be between 58-59°F on May 13?",
        city=city,
        date=date,
        temp_type=temp_type,
        direction=direction,
        range_low_f=lo_f,
        range_high_f=hi_f,
        unit=unit,
        yes_token_id="yes-token",
        no_token_id="no-token",
        yes_price=Decimal(yes_price),
        volume_24h_usd=Decimal("5000"),
        end_date=end_date,
    )


def _snap(
    *,
    city: str = "Chicago",
    raw_max_f: float | None = None,
    raw_min_f: float | None = None,
    raw_max_settlement_f: float | None = None,
    raw_min_settlement_f: float | None = None,
    local_day_complete: bool = False,
    station: str | None = "KORD",
    source: str | None = "aviationweather_metar",
    observed_at: datetime | None = None,
) -> StationDaySnapshot:
    _at = observed_at or datetime(2026, 5, 13, 17, 45, tzinfo=UTC)  # 15min before _NOW
    return StationDaySnapshot(
        city=city,
        date="2026-05-13",
        station=station,
        source=source,
        fetched_at=datetime(2026, 5, 13, 18, tzinfo=UTC),
        local_day_complete=local_day_complete,
        latest_temp_f=raw_max_f,
        latest_settlement_temp_f=raw_max_settlement_f,
        latest_observed_at=_at,
        raw_max_f=raw_max_f,
        raw_max_settlement_f=raw_max_settlement_f,
        raw_min_f=raw_min_f,
        raw_min_settlement_f=raw_min_settlement_f,
        raw_max_observed_at=_at if raw_max_f is not None else None,
        raw_min_observed_at=_at if raw_min_f is not None else None,
        sample_count=1 if (raw_max_f or raw_min_f) else 0,
    )


_NOW = datetime(2026, 5, 13, 18, tzinfo=UTC)


# ── Test 1: high bounded already_no when station high exceeds upper bound ─────


def test_high_between_already_no_when_exceeds_upper():
    """Station high 63°F > bucket high 59°F → already_no, certain_side=BUY_NO."""
    market = _market(direction="between", lo_f=58.0, hi_f=59.0)
    snap = _snap(raw_max_f=63.0, raw_max_settlement_f=63.0)
    lock = classify_station_lock(market, snap, now=_NOW)
    assert lock.state == "already_no"
    assert lock.certain_side == "BUY_NO"
    assert lock.confidence == "hard"
    assert not lock.rounding_disagreement


# ── Test 2: high bounded pending when station high below lower bound, day incomplete ──


def test_high_between_pending_when_below_lower_intraday():
    """Station high 55°F < bucket low 58°F before day ends → pending (can still rise)."""
    market = _market(direction="between", lo_f=58.0, hi_f=59.0)
    snap = _snap(raw_max_f=55.0, raw_max_settlement_f=55.0, local_day_complete=False)
    lock = classify_station_lock(market, snap, now=_NOW)
    assert lock.state == "pending"
    assert lock.certain_side is None


# ── Test 3: high bounded locked_no when day complete and below lower bound ────


def test_high_between_locked_no_when_day_complete_below_lower():
    """Station high 55°F < bucket low 58°F, day complete → locked_no."""
    market = _market(direction="between", lo_f=58.0, hi_f=59.0)
    snap = _snap(raw_max_f=55.0, raw_max_settlement_f=55.0, local_day_complete=True)
    lock = classify_station_lock(market, snap, now=_NOW)
    assert lock.state == "locked_no"
    assert lock.certain_side == "BUY_NO"
    assert lock.confidence == "hard"


def test_high_between_locked_yes_when_day_complete_inside_bucket():
    """Station high inside bounded bucket after day complete → locked_yes."""
    market = _market(direction="between", lo_f=58.0, hi_f=59.0)
    snap = _snap(raw_max_f=58.0, raw_max_settlement_f=58.0, local_day_complete=True)
    lock = classify_station_lock(market, snap, now=_NOW)
    assert lock.state == "locked_yes"
    assert lock.certain_side == "BUY_YES"
    assert lock.confidence == "hard"


def test_high_below_already_no_and_locked_yes():
    """High 'or below' is NO after crossing threshold and YES when complete below."""
    market = _market(direction="below", lo_f=None, hi_f=60.0)
    crossed = classify_station_lock(
        market,
        _snap(raw_max_f=61.0, raw_max_settlement_f=61.0),
        now=_NOW,
    )
    complete_below = classify_station_lock(
        market,
        _snap(raw_max_f=59.0, raw_max_settlement_f=59.0, local_day_complete=True),
        now=_NOW,
    )
    assert crossed.state == "already_no"
    assert crossed.certain_side == "BUY_NO"
    assert complete_below.state == "locked_yes"
    assert complete_below.certain_side == "BUY_YES"


# ── Test 4: low bounded already_no when station low drops below lower bound ───


def test_low_between_already_no_when_drops_below_lower():
    """Station low 48°F < bucket low 50°F → already_no (bucket impossible)."""
    market = _market(temp_type="low", direction="between", lo_f=50.0, hi_f=55.0)
    snap = _snap(raw_min_f=48.0, raw_min_settlement_f=48.0)
    lock = classify_station_lock(market, snap, now=_NOW)
    assert lock.state == "already_no"
    assert lock.certain_side == "BUY_NO"
    assert lock.confidence == "hard"


# ── Test 5: low bounded pending when station low above upper bound, day incomplete ──


def test_low_between_pending_when_above_upper_intraday():
    """Station low 60°F > bucket high 55°F before day complete → pending (can still fall)."""
    market = _market(temp_type="low", direction="between", lo_f=50.0, hi_f=55.0)
    snap = _snap(raw_min_f=60.0, raw_min_settlement_f=60.0, local_day_complete=False)
    lock = classify_station_lock(market, snap, now=_NOW)
    assert lock.state == "pending"
    assert lock.certain_side is None


# ── Test 6: 'above' and 'higher' parse/behave identically ─────────────────────


def test_above_and_higher_directions_identical():
    """'above' and 'higher' must classify identically for the same inputs."""
    snap = _snap(raw_max_f=65.0, raw_max_settlement_f=65.0)
    market_above = _market(direction="above", lo_f=60.0, hi_f=None)
    market_higher = _market(direction="higher", lo_f=60.0, hi_f=None)
    lock_above = classify_station_lock(market_above, snap, now=_NOW)
    lock_higher = classify_station_lock(market_higher, snap, now=_NOW)
    assert lock_above.state == lock_higher.state
    assert lock_above.certain_side == lock_higher.certain_side
    assert lock_above.confidence == lock_higher.confidence


# ── Test 7: Celsius market evaluates in native C unit ─────────────────────────


def test_celsius_market_rounds_in_celsius():
    """Rounding applied in C to avoid F-rounding errors at bucket boundaries.

    London bucket: between 20-21°C → F range ~68.0-69.8°F.
    Station raw: 69.5°F = 20.833°C.

    C rounding: round(20.833) = 21°C = 69.8°F → at boundary → in bucket.
    The classifier's nearest/floor counterfactuals both run in C, so both
    native paths remain inside the [20, 21] bucket.
    """
    # London has unit='C' in SETTLEMENT_SPECS
    market = _market(
        city="London",
        direction="between",
        lo_f=68.0,   # 20°C
        hi_f=69.8,   # 21°C
        unit="C",
    )
    snap = _snap(city="London", raw_max_f=69.5, raw_max_settlement_f=70.0, station="EGLC")
    lock = classify_station_lock(market, snap, now=_NOW)
    # 69.5°F = 20.833°C. nearest_int in C = 21°C, floor in C = 20°C.
    # The key test is that classification happens in C, not raw F.
    assert lock.station_metric_native is not None
    # For C market, native should be approximately 21°C (rounded from 20.833°C)
    assert abs(lock.station_metric_native - 21.0) < 0.01


def test_celsius_bucket_counterfactuals_stay_in_celsius():
    """Celsius nearest/floor counterfactuals run in native C, not raw F."""
    market = _market(
        city="London",
        direction="between",
        lo_f=68.0,
        hi_f=69.8,
        unit="C",
    )
    snap = _snap(city="London", raw_max_f=69.9, raw_max_settlement_f=70.0, station="EGLC")
    lock = classify_station_lock(market, snap, now=_NOW)
    # 69.9°F = 20.944°C. In native C:
    # nearest_int = 21°C and floor = 20°C; both remain inside [20, 21].
    assert lock.station_metric_native is not None
    assert lock.station_metric_native < 30
    assert lock.nearest_int_state == "pending"
    assert lock.floor_state == "pending"
    assert lock.rounding_disagreement is False


# ── Test 8: rounding disagreement → confidence='unsafe' ───────────────────────


def test_rounding_disagreement_produces_unsafe():
    """When nearest_int and floor give different states, confidence='unsafe'."""
    # Choose a value where nearest_int rounds up across a boundary but floor stays below.
    # high market, between 63-64°F. Station = 63.6°F.
    # nearest_int(63.6) = 64 → at hi boundary 64 ≤ 64 → in bucket → pending
    # floor(63.6) = 63 → at lo boundary 63 ≥ 63 → in bucket → pending
    # These agree. Need a sharper case.
    # high market, between 63-64°F. Station = 64.6°F.
    # nearest_int(64.6) = 65 → 65 > 64 → already_no
    # floor(64.6) = 64 → 64 ≤ 64 → in bucket → pending (or locked)
    market = _market(direction="between", lo_f=63.0, hi_f=64.0)
    snap = _snap(raw_max_f=64.6, raw_max_settlement_f=65.0)
    lock = classify_station_lock(market, snap, now=_NOW)
    assert lock.rounding_disagreement is True
    assert lock.confidence == "unsafe"
    assert lock.certain_side is None
    # Nearest_int state should be already_no, floor state pending
    assert lock.nearest_int_state == "already_no"
    assert lock.floor_state == "pending"


# ── Test 9: missing station spec blocks entry ─────────────────────────────────


def test_missing_station_spec_produces_no_entry(monkeypatch, tmp_path):
    """Market for a city with no settlement spec is always skipped."""
    market = _market(city="NotARealCity", direction="between", lo_f=68.0, hi_f=70.0)

    def _no_markets(*a, **k):
        return [market]

    def _snap_fn(*a, **k):
        return _snap(city="NotARealCity", raw_max_f=75.0, station=None)

    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_weather_markets", _no_markets)
    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_station_day_snapshot", _snap_fn)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.db import Base, Event

    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    sf = sessionmaker(engine)

    counts = run_station_lock_scan(session_factory=sf, now=_NOW)

    from bots.bot_d_weather.config import SETTLEMENT_SPECS
    assert "NotARealCity" not in SETTLEMENT_SPECS
    # Skip event should have been written
    with sf() as s:
        skips = s.query(Event).filter_by(event_type="bot_d.station_lock.skip").all()
    assert len(skips) >= 1
    assert counts["entries"] == 0


# ── Test 10: WU station mutation blocks entry ──────────────────────────────────


def test_wu_station_mutation_blocks_entry():
    """WU data with a different station than expected returns confidence='unsafe'."""
    market = _market(city="Chicago", direction="between", lo_f=58.0, hi_f=59.0)
    snap = _snap(raw_max_f=63.0, raw_max_settlement_f=63.0)
    # data_source='wunderground', wu_station_seen differs from expected 'KORD'
    lock = classify_station_lock(
        market,
        snap,
        now=_NOW,
        data_source="wunderground",
        wu_station_seen="KDFW",  # wrong station
    )
    assert lock.confidence == "unsafe"
    assert "wu_station_mutation" in lock.reason
    assert lock.certain_side is None


def test_wu_station_unknown_blocks_entry():
    """WU data with no station seen returns confidence='unsafe'."""
    market = _market()
    snap = _snap(raw_max_f=63.0)
    lock = classify_station_lock(
        market,
        snap,
        now=_NOW,
        data_source="wunderground",
        wu_station_seen=None,
    )
    assert lock.confidence == "unsafe"
    assert lock.reason == "wu_station_unknown"


# ── Test 11: paper order uses bot_d_station_lock ──────────────────────────────


def test_paper_entry_uses_station_lock_bot_id(monkeypatch, tmp_path):
    """Entry attempt events must carry bot_id='bot_d_station_lock', not 'bot_d'."""
    market = _market(city="Chicago", direction="between", lo_f=58.0, hi_f=59.0)
    # Station high already exceeds upper bound → hard certainty → should enter
    snap = _snap(raw_max_f=63.0, raw_max_settlement_f=63.0)

    def _mock_markets(*a, **k):
        return [market]

    def _mock_snap(*a, **k):
        return snap

    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_weather_markets", _mock_markets)
    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_station_day_snapshot", _mock_snap)

    # Chicago is in SETTLEMENT_SPECS with verified=True
    from bots.bot_d_weather.config import SETTLEMENT_SPECS
    assert SETTLEMENT_SPECS["Chicago"].verified

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.db import Base, Event

    engine = create_engine(f"sqlite:///{tmp_path}/test11.db")
    Base.metadata.create_all(engine)
    sf = sessionmaker(engine)

    counts = run_station_lock_scan(session_factory=sf, now=_NOW)

    with sf() as s:
        all_events = s.query(Event).all()

    bot_ids = {e.bot_id for e in all_events}
    assert "bot_d_station_lock" in bot_ids
    assert "bot_d" not in bot_ids
    assert "bot_d_live_probe" not in bot_ids

    # Verify entry event specifically
    entry_events = [e for e in all_events if e.event_type == "bot_d.station_lock.entry_attempt"]
    assert len(entry_events) >= 1
    assert entry_events[0].bot_id == "bot_d_station_lock"
    assert counts["entries"] >= 1


def test_daily_gross_cap_blocks_second_entry(monkeypatch, tmp_path):
    """Daily gross cap is based on entry date and blocks multiple same-scan fills."""
    markets = [
        _market(gamma_id="cap-1", direction="between", lo_f=58.0, hi_f=59.0),
        _market(gamma_id="cap-2", direction="between", lo_f=58.0, hi_f=59.0),
    ]
    snap = _snap(raw_max_f=63.0, raw_max_settlement_f=63.0)

    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_weather_markets", lambda *a, **k: markets)
    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_station_day_snapshot", lambda *a, **k: snap)
    monkeypatch.setattr("bots.bot_d_weather.station_lock.STATION_LOCK_MAX_DAILY_GROSS_USD", Decimal("5"))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.db import Base, Event

    engine = create_engine(f"sqlite:///{tmp_path}/daily-cap.db")
    Base.metadata.create_all(engine)
    sf = sessionmaker(engine)

    counts = run_station_lock_scan(session_factory=sf, now=_NOW)

    with sf() as s:
        entries = s.query(Event).filter_by(event_type="bot_d.station_lock.entry_attempt").all()
        cap_skips = [
            e for e in s.query(Event).filter_by(event_type="bot_d.station_lock.skip").all()
            if (e.payload or {}).get("skip_reason_code") == "daily_gross_cap"
        ]
    assert counts["entries"] == 1
    assert len(entries) == 1
    assert len(cap_skips) == 1


def test_open_exposure_cap_blocks_entry(monkeypatch, tmp_path):
    """Unresolved paper fills count against station-lock open exposure."""
    market = _market(gamma_id="exposure-new", direction="between", lo_f=58.0, hi_f=59.0)
    snap = _snap(raw_max_f=63.0, raw_max_settlement_f=63.0)

    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_weather_markets", lambda *a, **k: [market])
    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_station_day_snapshot", lambda *a, **k: snap)
    monkeypatch.setattr("bots.bot_d_weather.station_lock.STATION_LOCK_MAX_OPEN_EXPOSURE_USD", Decimal("5"))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.db import Base, Event

    engine = create_engine(f"sqlite:///{tmp_path}/exposure-cap.db")
    Base.metadata.create_all(engine)
    sf = sessionmaker(engine)
    with sf() as s:
        s.add(Event(
            bot_id=BOT_ID,
            event_type="bot_d.station_lock.paper_fill",
            severity="info",
            message="seed fill",
            payload={"condition_id": "existing", "paper_trade_usd": "5"},
        ))
        s.commit()

    counts = run_station_lock_scan(session_factory=sf, now=_NOW)

    with sf() as s:
        entries = s.query(Event).filter_by(event_type="bot_d.station_lock.entry_attempt").all()
        skips = s.query(Event).filter_by(event_type="bot_d.station_lock.skip").all()
    assert counts["entries"] == 0
    assert not entries
    assert any((e.payload or {}).get("skip_reason_code") == "open_exposure_cap" for e in skips)


def test_duplicate_condition_id_does_not_reenter(monkeypatch, tmp_path):
    """A condition id is entered at most once across repeated scans."""
    market = _market(gamma_id="dup-cond")
    snap = _snap(raw_max_f=63.0, raw_max_settlement_f=63.0)

    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_weather_markets", lambda *a, **k: [market])
    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_station_day_snapshot", lambda *a, **k: snap)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.db import Base, Event

    engine = create_engine(f"sqlite:///{tmp_path}/duplicate.db")
    Base.metadata.create_all(engine)
    sf = sessionmaker(engine)

    first = run_station_lock_scan(session_factory=sf, now=_NOW)
    second = run_station_lock_scan(session_factory=sf, now=_NOW)

    with sf() as s:
        entries = s.query(Event).filter_by(event_type="bot_d.station_lock.entry_attempt").all()
    assert first["entries"] == 1
    assert second["entries"] == 0
    assert len(entries) == 1


def test_scan_metar_missing_station_reports_no_station_data(monkeypatch, tmp_path):
    """The scan path uses METAR data semantics, not WU station mutation semantics."""
    market = _market(gamma_id="wu-unknown", direction="between", lo_f=58.0, hi_f=59.0)
    snap = _snap(
        raw_max_f=None,
        raw_max_settlement_f=None,
        station=None,
        source="wunderground",
    )

    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_weather_markets", lambda *a, **k: [market])
    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_station_day_snapshot", lambda *a, **k: snap)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.db import Base, Event

    engine = create_engine(f"sqlite:///{tmp_path}/wu-unknown.db")
    Base.metadata.create_all(engine)
    sf = sessionmaker(engine)

    counts = run_station_lock_scan(session_factory=sf, now=_NOW)

    with sf() as s:
        entries = s.query(Event).filter_by(event_type="bot_d.station_lock.entry_attempt").all()
        skips = s.query(Event).filter_by(event_type="bot_d.station_lock.skip").all()
    assert counts["entries"] == 0
    assert not entries
    assert any("no_station_data" in (e.payload or {}).get("skip_reason_code", "") for e in skips)


def test_too_early_local_day_skip(monkeypatch, tmp_path):
    """Station Lock waits for the configured local-day age before paper entry."""
    early_now = datetime(2026, 5, 13, 6, tzinfo=UTC)  # 01:00 Chicago local
    market = _market(gamma_id="early-local", direction="between", lo_f=58.0, hi_f=59.0)
    snap = _snap(
        raw_max_f=63.0,
        raw_max_settlement_f=63.0,
        source="wunderground",
        observed_at=early_now,
    )

    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_weather_markets", lambda *a, **k: [market])
    monkeypatch.setattr("bots.bot_d_weather.station_lock.fetch_station_day_snapshot", lambda *a, **k: snap)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.db import Base, Event

    engine = create_engine(f"sqlite:///{tmp_path}/too-early.db")
    Base.metadata.create_all(engine)
    sf = sessionmaker(engine)

    counts = run_station_lock_scan(session_factory=sf, now=early_now)

    with sf() as s:
        skips = s.query(Event).filter_by(event_type="bot_d.station_lock.skip").all()
        candidates = s.query(Event).filter_by(event_type="bot_d.station_lock.candidate").all()
    assert counts["entries"] == 0
    assert any("too_early_local_day" in (e.payload or {}).get("skip_reason_code", "") for e in skips)
    assert candidates
    payload = candidates[0].payload or {}
    assert payload["bucket_low_native"] == 58.0
    assert payload["bucket_high_native"] == 59.0
    assert payload["source"] == "aviationweather_metar"
    assert payload["settlement_source"] == "wunderground"


# ── Test 12: live mode cannot be enabled ──────────────────────────────────────


def test_assert_paper_only_raises_on_bot_d_env_live(monkeypatch):
    """_assert_paper_only must raise RuntimeError when BOT_D_ENV=live."""
    monkeypatch.setenv("BOT_D_ENV", "live")
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    with pytest.raises(RuntimeError, match="paper-only"):
        _assert_paper_only()


def test_assert_paper_only_raises_on_polymarket_env_live(monkeypatch):
    """_assert_paper_only must raise RuntimeError when POLYMARKET_ENV=live."""
    monkeypatch.setenv("BOT_D_ENV", "paper")
    monkeypatch.setenv("POLYMARKET_ENV", "live")
    with pytest.raises(RuntimeError, match="paper-only"):
        _assert_paper_only()


def test_assert_paper_only_ok_in_paper_mode(monkeypatch):
    """_assert_paper_only must NOT raise when both envs are paper."""
    monkeypatch.setenv("BOT_D_ENV", "paper")
    monkeypatch.setenv("POLYMARKET_ENV", "paper")
    _assert_paper_only()  # must not raise


def test_run_scan_raises_if_live_env(monkeypatch, tmp_path):
    """run_station_lock_scan must refuse to run if live env is set."""
    monkeypatch.setenv("BOT_D_ENV", "live")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.db import Base

    engine = create_engine(f"sqlite:///{tmp_path}/test12.db")
    Base.metadata.create_all(engine)
    sf = sessionmaker(engine)
    with pytest.raises(RuntimeError, match="paper-only"):
        run_station_lock_scan(session_factory=sf)
