from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from bots.bot_d_weather.discovery import WeatherMarket
from bots.bot_d_weather.source_monitor import (
    FinalSourceSnapshot,
    TomorrowShadowSnapshot,
    classify_bucket_state,
    fetch_station_day_snapshot,
    fetch_tomorrow_shadow_snapshot,
    record_completed_forecast_resolutions,
    record_source_snapshots,
)
from core.db import Event, get_session_factory


def _mkt(
    *,
    temp_type: str = "high",
    direction: str = "between",
    lo: float | None = 74.0,
    hi: float | None = 76.0,
    yes_price: str = "0.22",
) -> WeatherMarket:
    return WeatherMarket(
        gamma_id="gamma-nyc",
        slug="nyc-high",
        question="Will the highest temperature in New York City be between 74-76°F on May 5?",
        city="NYC",
        date="2026-05-05",
        temp_type=temp_type,
        direction=direction,
        range_low_f=lo,
        range_high_f=hi,
        unit="F",
        yes_token_id="yes",
        no_token_id="no",
        yes_price=Decimal(yes_price),
        volume_24h_usd=Decimal("1000"),
    )


def test_station_snapshot_uses_settlement_day_extrema(monkeypatch):
    records = [
        {"reportTime": "2026-05-05T10:00:00Z", "temp": 20.0},  # 68F
        {"reportTime": "2026-05-05T14:00:00Z", "temp": 24.4},  # 75.92F -> 76F settled
        {"reportTime": "2026-05-04T23:00:00Z", "temp": 5.0},
    ]
    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor._fetch_aviationweather_metars",
        lambda *a, **k: records,
    )

    snap = fetch_station_day_snapshot(
        "NYC",
        "2026-05-05",
        now=datetime(2026, 5, 5, 15, tzinfo=UTC),
    )

    assert snap.station == "KLGA"
    assert snap.sample_count == 2
    assert snap.raw_max_settlement_f == 76.0
    assert snap.raw_min_settlement_f == 68.0
    assert snap.raw_max_observed_at == datetime(2026, 5, 5, 14, tzinfo=UTC)


def test_classify_high_bucket_already_impossible(monkeypatch):
    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor._fetch_aviationweather_metars",
        lambda *a, **k: [{"reportTime": "2026-05-05T14:00:00Z", "temp": 25.0}],
    )
    snap = fetch_station_day_snapshot(
        "NYC",
        "2026-05-05",
        now=datetime(2026, 5, 5, 15, tzinfo=UTC),
    )

    state = classify_bucket_state(_mkt(hi=76.0), snap)

    assert state["bucket_state"] == "already_no"
    assert state["bucket_impossible"] is True
    assert state["bucket_locked"] is False


def test_classify_low_bucket_already_yes(monkeypatch):
    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor._fetch_aviationweather_metars",
        lambda *a, **k: [{"reportTime": "2026-05-05T09:00:00Z", "temp": 10.0}],
    )
    snap = fetch_station_day_snapshot(
        "NYC",
        "2026-05-05",
        now=datetime(2026, 5, 5, 15, tzinfo=UTC),
    )

    state = classify_bucket_state(
        _mkt(temp_type="low", direction="below", lo=None, hi=52.0),
        snap,
    )

    assert state["bucket_state"] == "already_yes"
    assert state["bucket_locked"] is True
    assert state["bucket_impossible"] is False


def test_record_source_snapshots_writes_event(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor._fetch_aviationweather_metars",
        lambda *a, **k: [{"reportTime": "2026-05-05T14:00:00Z", "temp": 24.4}],
    )

    written = record_source_snapshots(
        get_session_factory(),
        [_mkt()],
        bot_id="bot_d",
        now=datetime(2026, 5, 5, 15, tzinfo=UTC),
    )

    assert written == 1
    with get_session_factory()() as session:
        event = session.query(Event).filter_by(event_type="bot_d.source_snapshot").one()
    payload = event.payload if isinstance(event.payload, dict) else json.loads(event.payload)
    assert payload["settlement_station"] == "KLGA"
    assert payload["market_yes_price"] == "0.22"
    assert payload["bucket_state"] == "pending"
    assert payload["observed_temperature_f"] is None
    assert payload["source_snapshot"]["raw_max_settlement_f"] == 76.0
    counterfactuals = payload["settlement_rounding_counterfactuals"]
    assert counterfactuals["nearest_int"]["raw_max_settlement_f"] == 76.0
    assert counterfactuals["floor"]["raw_max_settlement_f"] == 75.0
    assert counterfactuals["nearest_vs_floor_disagree"] is False


def test_record_source_snapshots_records_wu_current_lag(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor._fetch_aviationweather_metars",
        lambda *a, **k: [{"reportTime": "2026-05-05T14:00:00Z", "temp": 24.4}],
    )

    def fake_final_source(*args, **kwargs):
        return FinalSourceSnapshot(
            city="NYC",
            date="2026-05-05",
            station="KLGA",
            source="wunderground",
            fetched_at=datetime(2026, 5, 5, 15, tzinfo=UTC),
            status="ok",
            valid_time=datetime(2026, 5, 5, 14, 7, tzinfo=UTC),
            temperature_f=76.0,
            temperature_max_24h_f=76.0,
            temperature_max_since_7am_f=76.0,
            temperature_min_24h_f=68.0,
            source_url="https://api.weather.com/v3/wx/observations/current",
        )

    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor.fetch_final_source_snapshot",
        fake_final_source,
    )

    written = record_source_snapshots(
        get_session_factory(),
        [_mkt()],
        bot_id="bot_d",
        now=datetime(2026, 5, 5, 15, tzinfo=UTC),
    )

    assert written == 1
    with get_session_factory()() as session:
        event = session.query(Event).filter_by(event_type="bot_d.source_snapshot").one()
    payload = event.payload if isinstance(event.payload, dict) else json.loads(event.payload)
    assert payload["source_station_status"] == "ok"
    assert payload["source_value_f"] == 76.0
    assert payload["source_value_field"] == "temperatureMax24Hour"
    assert payload["source_visible_timestamp"] == "2026-05-05T14:07:00+00:00"
    assert payload["source_lag_seconds"] == 420.0
    assert payload["source_matches_station_metric"] is True


def test_fetch_tomorrow_shadow_snapshot_builds_daily_high_low(monkeypatch):
    monkeypatch.setattr("bots.bot_d_weather.source_monitor.TOMORROW_API_KEY", "test-key")
    monkeypatch.setattr("bots.bot_d_weather.source_monitor.BOT_D_TOMORROW_SHADOW_ENABLED", True)
    monkeypatch.setattr("bots.bot_d_weather.source_monitor._TOMORROW_CACHE", {})

    class Client:
        def get(self, url, params=None, timeout=None):
            request = __import__("httpx").Request("GET", url)
            return __import__("httpx").Response(
                200,
                request=request,
                json={
                    "timelines": {
                        "hourly": [
                            {"time": "2026-05-05T04:00:00Z", "values": {"temperature": 62.0}},
                            {"time": "2026-05-05T14:00:00Z", "values": {"temperature": 74.0}},
                            {"time": "2026-05-05T18:00:00Z", "values": {"temperature": 77.0}},
                        ]
                    }
                },
            )

    snap = fetch_tomorrow_shadow_snapshot(
        "NYC",
        "2026-05-05",
        client=Client(),
        now=datetime(2026, 5, 5, 12, tzinfo=UTC),
    )

    assert snap.status == "ok"
    assert snap.high_f == 77.0
    assert snap.low_f == 62.0
    assert snap.source_url is not None
    assert "test-key" not in snap.source_url


def test_record_source_snapshots_records_tomorrow_shadow(tmp_db, monkeypatch):
    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor._fetch_aviationweather_metars",
        lambda *a, **k: [{"reportTime": "2026-05-05T14:00:00Z", "temp": 24.4}],
    )

    def fake_tomorrow(*args, **kwargs):
        return TomorrowShadowSnapshot(
            city="NYC",
            date="2026-05-05",
            fetched_at=datetime(2026, 5, 5, 15, tzinfo=UTC),
            status="ok",
            high_f=78.0,
            low_f=63.0,
            first_time=datetime(2026, 5, 5, 4, tzinfo=UTC),
            last_time=datetime(2026, 5, 6, 3, tzinfo=UTC),
            source_url="https://api.tomorrow.io/v4/weather/forecast?location=40.7772,-73.8726",
        )

    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor.fetch_tomorrow_shadow_snapshot",
        fake_tomorrow,
    )

    written = record_source_snapshots(
        get_session_factory(),
        [_mkt()],
        bot_id="bot_d",
        now=datetime(2026, 5, 5, 15, tzinfo=UTC),
    )

    assert written == 1
    with get_session_factory()() as session:
        event = session.query(Event).filter_by(event_type="bot_d.source_snapshot").one()
    payload = event.payload if isinstance(event.payload, dict) else json.loads(event.payload)
    assert payload["tomorrow_io_snapshot"]["status"] == "ok"
    assert payload["tomorrow_io_value_f"] == 78.0
    assert payload["tomorrow_io_gap_to_station_f"] == 2.0


def test_record_source_snapshots_flags_rounding_counterfactual_disagreement(
    tmp_db,
    monkeypatch,
):
    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor._fetch_aviationweather_metars",
        lambda *a, **k: [{"reportTime": "2026-05-05T21:00:00Z", "temp": 24.4}],
    )

    written = record_source_snapshots(
        get_session_factory(),
        [_mkt(lo=76.0, hi=76.0)],
        bot_id="bot_d",
        now=datetime(2026, 5, 6, 5, tzinfo=UTC),
    )

    assert written == 1
    with get_session_factory()() as session:
        event = session.query(Event).filter_by(event_type="bot_d.source_snapshot").one()
    payload = event.payload if isinstance(event.payload, dict) else json.loads(event.payload)
    counterfactuals = payload["settlement_rounding_counterfactuals"]
    assert counterfactuals["nearest_int"]["yes_resolved"] is True
    assert counterfactuals["floor"]["yes_resolved"] is False
    assert counterfactuals["nearest_vs_floor_disagree"] is True


def test_record_source_snapshots_writes_resolution_once_after_complete_day(
    tmp_db,
    monkeypatch,
):
    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor._fetch_aviationweather_metars",
        lambda *a, **k: [{"reportTime": "2026-05-05T21:00:00Z", "temp": 24.4}],
    )

    written = record_source_snapshots(
        get_session_factory(),
        [_mkt()],
        bot_id="bot_d",
        now=datetime(2026, 5, 6, 5, tzinfo=UTC),
    )
    written_again = record_source_snapshots(
        get_session_factory(),
        [_mkt()],
        bot_id="bot_d",
        now=datetime(2026, 5, 6, 5, 1, tzinfo=UTC),
    )

    assert written == 1
    assert written_again == 1
    with get_session_factory()() as session:
        snapshots = session.query(Event).filter_by(event_type="bot_d.source_snapshot").all()
        resolutions = session.query(Event).filter_by(
            event_type="bot_d.forecast_resolution"
        ).all()

    assert len(snapshots) == 2
    assert len(resolutions) == 1
    payload = (
        resolutions[0].payload
        if isinstance(resolutions[0].payload, dict)
        else json.loads(resolutions[0].payload)
    )
    assert payload["condition_id"] == "gamma-nyc"
    assert payload["observed_temperature_f"] == 76.0
    assert payload["observed_temperature_complete"] is True
    assert payload["yes_resolved"] is True
    assert payload["settlement_label_source"] == "station_observation"


def test_record_completed_forecast_resolutions_labels_old_source_snapshot(
    tmp_db,
    monkeypatch,
):
    monkeypatch.setattr(
        "bots.bot_d_weather.source_monitor._fetch_aviationweather_metars",
        lambda *a, **k: [{"reportTime": "2026-05-05T21:00:00Z", "temp": 24.4}],
    )

    written = record_source_snapshots(
        get_session_factory(),
        [_mkt()],
        bot_id="bot_d",
        now=datetime(2026, 5, 5, 15, tzinfo=UTC),
    )
    labelled = record_completed_forecast_resolutions(
        get_session_factory(),
        bot_id="bot_d",
        now=datetime(2026, 5, 6, 5, tzinfo=UTC),
    )
    labelled_again = record_completed_forecast_resolutions(
        get_session_factory(),
        bot_id="bot_d",
        now=datetime(2026, 5, 6, 5, 1, tzinfo=UTC),
    )

    assert written == 1
    assert labelled == 1
    assert labelled_again == 0
    with get_session_factory()() as session:
        resolutions = session.query(Event).filter_by(
            event_type="bot_d.forecast_resolution"
        ).all()

    assert len(resolutions) == 1
    payload = (
        resolutions[0].payload
        if isinstance(resolutions[0].payload, dict)
        else json.loads(resolutions[0].payload)
    )
    assert payload["condition_id"] == "gamma-nyc"
    assert payload["observed_temperature_f"] == 76.0
    assert payload["observed_temperature_complete"] is True
    assert payload["yes_resolved"] is True
