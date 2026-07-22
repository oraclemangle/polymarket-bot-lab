"""Phase 3 audit remediation tests.

Covers:
- emergency halt flag (set/clear/env override)
- fee-scraper parser
- Bot A config tuning (two-level exit)
- Bot D exact-temp blacklist + UHI offset
- Cross-bot condition_id overlap detector
- Orphan-SELL alert
- Bot E adverse-selection tracker
- Gap-quarantine actually filters events
- Archetype concentration monitor
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import sqlite3


# ---------------------------------------------------------------------------
# 3.1 emergency halt
# ---------------------------------------------------------------------------


class TestEmergencyHalt:
    def test_default_not_halted(self, tmp_db, monkeypatch):
        monkeypatch.delenv("EMERGENCY_HALT", raising=False)
        from core import emergency_halt
        assert emergency_halt.is_emergency_halted() is False

    def test_env_override(self, monkeypatch, tmp_db):
        monkeypatch.setenv("EMERGENCY_HALT", "true")
        from core import emergency_halt
        assert emergency_halt.is_emergency_halted() is True

    def test_env_false_value(self, monkeypatch, tmp_db):
        monkeypatch.setenv("EMERGENCY_HALT", "no")
        from core import emergency_halt
        assert emergency_halt.is_emergency_halted() is False

    def test_set_and_clear_roundtrip(self, tmp_db, monkeypatch):
        monkeypatch.delenv("EMERGENCY_HALT", raising=False)
        from core import emergency_halt
        emergency_halt.set_emergency_halt("test reason")
        assert emergency_halt.is_emergency_halted() is True
        state = emergency_halt.get_emergency_halt_state()
        assert state.halted is True
        assert "test" in (state.reason or "")
        emergency_halt.clear_emergency_halt()
        assert emergency_halt.is_emergency_halted() is False


# ---------------------------------------------------------------------------
# 3.2 fee scraper
# ---------------------------------------------------------------------------


class TestFeeScraperParsing:
    def test_parse_handles_standard_list(self):
        from scripts.check_polymarket_fees import parse_fee_schedule
        html = """
        Crypto: 1.80%
        Economics - 1.25%
        Geopolitics: 0%
        Sports: 0.75%
        """
        out = parse_fee_schedule(html)
        assert out["crypto"] == Decimal("0.018")
        assert out["economics"] == Decimal("0.0125")
        assert out["geopolitics"] == Decimal("0")
        assert out["sports"] == Decimal("0.0075")

    def test_compare_flags_nonzero_geopolitics(self):
        from scripts.check_polymarket_fees import compare_against_baseline
        observed = {"geopolitics": Decimal("0.005")}  # 0.5% — any non-zero halts
        drifts, halt = compare_against_baseline(observed)
        assert halt is True
        assert any("geopolitics" in d.lower() for d in drifts)

    def test_compare_accepts_matching_baseline(self):
        from scripts.check_polymarket_fees import compare_against_baseline
        # Baseline crypto feeRate 0.072 → peak 0.018
        observed = {"crypto": Decimal("0.018"), "geopolitics": Decimal("0")}
        drifts, halt = compare_against_baseline(observed)
        assert halt is False
        assert drifts == []

    def test_compare_flags_drift_beyond_tolerance(self):
        from scripts.check_polymarket_fees import compare_against_baseline
        observed = {"crypto": Decimal("0.030")}  # ~1.2% delta vs baseline 0.018
        drifts, halt = compare_against_baseline(observed)
        assert halt is True


# ---------------------------------------------------------------------------
# 3.3 Bot A config + two-level exit
# ---------------------------------------------------------------------------


class TestBotAExitGate:
    def test_hard_exit_at_25c_always(self):
        from bots.bot_a.executor import BotAExecutor
        # Instantiation isn't required; we test the bound method via a stub.
        executor = BotAExecutor.__new__(BotAExecutor)
        assert executor.should_cut_loss(Decimal("0.25")) is True
        assert executor.should_cut_loss(Decimal("0.30")) is True

    def test_below_reeval_never_exits(self):
        from bots.bot_a.executor import BotAExecutor
        executor = BotAExecutor.__new__(BotAExecutor)
        assert executor.should_cut_loss(Decimal("0.10")) is False

    def test_reeval_band_without_volume_does_not_exit(self):
        from bots.bot_a.executor import BotAExecutor
        executor = BotAExecutor.__new__(BotAExecutor)
        # In [0.15, 0.25) band; no volume data → no exit.
        assert executor.should_cut_loss(Decimal("0.17")) is False

    def test_reeval_band_with_volume_doubling_exits(self):
        from bots.bot_a.executor import BotAExecutor
        executor = BotAExecutor.__new__(BotAExecutor)
        assert executor.should_cut_loss(
            Decimal("0.17"),
            entry_volume_usd=Decimal("5000"),
            current_volume_usd=Decimal("15000"),  # 3x entry
        ) is True

    def test_reeval_band_without_volume_doubling_holds(self):
        from bots.bot_a.executor import BotAExecutor
        executor = BotAExecutor.__new__(BotAExecutor)
        assert executor.should_cut_loss(
            Decimal("0.17"),
            entry_volume_usd=Decimal("5000"),
            current_volume_usd=Decimal("8000"),  # 1.6x entry
        ) is False


class TestBotAConfigTuning:
    def test_min_days_defaults_21(self, monkeypatch):
        monkeypatch.delenv("BOT_A_MIN_DAYS_TO_RESOLUTION", raising=False)
        import importlib
        from bots.bot_a import config
        importlib.reload(config)
        assert config.MIN_DAYS_TO_RESOLUTION == 21

    def test_repost_stale_defaults_2(self, monkeypatch):
        monkeypatch.delenv("BOT_A_REPOST_STALE_HOURS", raising=False)
        import importlib
        from bots.bot_a import config
        importlib.reload(config)
        assert config.REPOST_STALE_HOURS == 2


# ---------------------------------------------------------------------------
# 3.4 Bot D exact-temp blacklist + UHI
# ---------------------------------------------------------------------------


class TestBotDBlacklistAndUhi:
    def test_exact_temp_blacklisted_by_default(self):
        from bots.bot_d_weather.discovery import parse_weather_question
        r = parse_weather_question(
            "Will the highest temperature in NYC be 68°F on April 16?"
        )
        assert r is None

    def test_edge_threshold_default_010(self, monkeypatch):
        monkeypatch.delenv("BOT_D_EDGE_THRESHOLD", raising=False)
        import importlib
        from bots.bot_d_weather import config
        importlib.reload(config)
        assert config.BOT_D_EDGE_THRESHOLD == 0.10

    def test_verified_airport_markets_have_no_uhi_offset(self):
        from bots.bot_d_weather.config import CITIES
        assert CITIES["NYC"].urban_heat_island_f == 0.0
        assert CITIES["Chicago"].urban_heat_island_f == 0.0
        assert CITIES["Miami"].urban_heat_island_f == 0.0


# ---------------------------------------------------------------------------
# 3.5 cross-bot overlap + 3.9 archetype monitor
# ---------------------------------------------------------------------------


def _add_pos(bot_id: str, cid: str, cost: Decimal):
    from core.db import Position, get_session_factory
    with get_session_factory()() as s:
        s.add(Position(
            bot_id=bot_id, condition_id=cid, token_id=f"tk_{bot_id}_{cid}",
            side="YES", size=Decimal("10"), avg_price=Decimal("0.5"),
            cost_basis_usd=cost, status="OPEN",
            opened_at=datetime.now(UTC),
        ))
        s.commit()


class TestCrossBotOverlap:
    def test_no_overlap_empty_db(self, tmp_db):
        from core.fleet import detect_cross_bot_overlap
        assert detect_cross_bot_overlap() == []

    def test_no_overlap_single_bot(self, tmp_db):
        _add_pos("bot_a", "cid_1", Decimal("50"))
        from core.fleet import detect_cross_bot_overlap
        assert detect_cross_bot_overlap() == []

    def test_detects_two_bots_same_condition(self, tmp_db):
        _add_pos("bot_a", "cid_shared", Decimal("30"))
        _add_pos("bot_b", "cid_shared", Decimal("40"))
        from core.fleet import detect_cross_bot_overlap
        overlaps = detect_cross_bot_overlap()
        assert len(overlaps) == 1
        o = overlaps[0]
        assert o.condition_id == "cid_shared"
        assert sorted(o.bot_ids) == ["bot_a", "bot_b"]
        assert o.total_notional_usd == Decimal("70")


class TestArchetypeMonitor:
    def test_empty_fleet_empty_breakdown(self, tmp_db):
        from core.fleet import archetype_exposure_breakdown
        assert archetype_exposure_breakdown() == []

    def test_single_factor_concentration_flagged(self, tmp_db):
        _add_pos("bot_a", "cid1", Decimal("100"))
        _add_pos("bot_b", "cid2", Decimal("100"))
        _add_pos("bot_d", "cid3", Decimal("100"))
        from core.fleet import single_factor_alert_needed
        alert, msg = single_factor_alert_needed(threshold_frac=Decimal("0.70"))
        assert alert is True
        assert "short_surprise" in msg

    def test_mixed_archetype_no_alert(self, tmp_db):
        _add_pos("bot_a", "cid1", Decimal("50"))  # short_surprise
        _add_pos("bot_c", "cid2", Decimal("50"))  # momentum
        from core.fleet import single_factor_alert_needed
        alert, _ = single_factor_alert_needed(threshold_frac=Decimal("0.70"))
        assert alert is False


# ---------------------------------------------------------------------------
# 3.6 orphan-SELL alert
# ---------------------------------------------------------------------------


class TestOrphanSellAlert:
    def test_no_orphan_no_alert(self, tmp_db):
        from core.portfolio import Portfolio
        p = Portfolio()
        assert p.emit_orphan_sell_alert("bot_x") == 0

    def test_orphan_detected_and_alert_emitted(self, tmp_db):
        from core.db import Event, Trade, get_session_factory
        from sqlalchemy import select
        from core.portfolio import Portfolio
        past = datetime.now(UTC) - timedelta(hours=48)
        with get_session_factory()() as s:
            s.add(Trade(
                trade_id="orphan_old", bot_id="bot_x", order_id=None,
                condition_id="c1", token_id="TK", side="SELL",
                price=Decimal("0.90"), size=Decimal("5"),
                fee_usd=Decimal("0"), filled_at=past,
                usd_gbp_rate=Decimal("0.8"), gbp_notional=Decimal("3.6"),
            ))
            s.commit()
        p = Portfolio()
        count = p.emit_orphan_sell_alert("bot_x", max_age_hours=24)
        assert count == 1
        with get_session_factory()() as s:
            evs = list(s.scalars(
                select(Event).where(Event.event_type == "portfolio.orphan_sell_alert")
            ))
            assert len(evs) == 1

    def test_recent_orphan_not_alerted(self, tmp_db):
        from core.db import Trade, get_session_factory
        from core.portfolio import Portfolio
        recent = datetime.now(UTC) - timedelta(hours=2)
        with get_session_factory()() as s:
            s.add(Trade(
                trade_id="orphan_recent", bot_id="bot_x", order_id=None,
                condition_id="c1", token_id="TK", side="SELL",
                price=Decimal("0.90"), size=Decimal("5"),
                fee_usd=Decimal("0"), filled_at=recent,
                usd_gbp_rate=Decimal("0.8"), gbp_notional=Decimal("3.6"),
            ))
            s.commit()
        p = Portfolio()
        # max_age_hours=24, orphan is 2h old → not flagged yet
        assert p.emit_orphan_sell_alert("bot_x", max_age_hours=24) == 0


# ---------------------------------------------------------------------------
# 3.7 adverse-selection tracker
# ---------------------------------------------------------------------------


class TestAdverseSelection:
    def test_register_and_measure(self):
        from bots.bot_e_btc_scalp.adverse_selection import AdverseSelectionTracker
        tr = AdverseSelectionTracker()
        tr.register(
            order_id="o1", fill_price=Decimal("0.50"),
            fill_side="BUY_YES", fill_ts_ms=1000,
        )
        outcome = tr.measure("o1", midpoint_after=Decimal("0.48"))
        assert outcome is not None
        assert outcome.moved_against is True

    def test_not_adverse_when_moved_for(self):
        from bots.bot_e_btc_scalp.adverse_selection import AdverseSelectionTracker
        tr = AdverseSelectionTracker()
        tr.register(
            order_id="o1", fill_price=Decimal("0.50"),
            fill_side="BUY_YES", fill_ts_ms=1000,
        )
        outcome = tr.measure("o1", midpoint_after=Decimal("0.52"))
        assert outcome.moved_against is False

    def test_adverse_rate_and_halt(self):
        from bots.bot_e_btc_scalp.adverse_selection import AdverseSelectionTracker
        tr = AdverseSelectionTracker()
        # 15 adverse + 5 for → 75% adverse rate
        for i in range(15):
            tr.register(order_id=f"bad{i}", fill_price=Decimal("0.50"),
                        fill_side="BUY_YES", fill_ts_ms=i)
            tr.measure(f"bad{i}", midpoint_after=Decimal("0.48"))
        for i in range(5):
            tr.register(order_id=f"good{i}", fill_price=Decimal("0.50"),
                        fill_side="BUY_YES", fill_ts_ms=100 + i)
            tr.measure(f"good{i}", midpoint_after=Decimal("0.52"))
        halt, msg = tr.should_halt(last_n=20, adverse_threshold=0.60)
        assert halt is True
        assert "adverse_rate" in msg

    def test_insufficient_data_does_not_halt(self):
        from bots.bot_e_btc_scalp.adverse_selection import AdverseSelectionTracker
        tr = AdverseSelectionTracker()
        tr.register(order_id="o1", fill_price=Decimal("0.50"),
                    fill_side="BUY_YES", fill_ts_ms=0)
        tr.measure("o1", midpoint_after=Decimal("0.48"))
        halt, _ = tr.should_halt(last_n=20, adverse_threshold=0.60)
        assert halt is False


# ---------------------------------------------------------------------------
# 3.8 gap quarantine actually applied
# ---------------------------------------------------------------------------


def _make_recorder_db_with_events(
    tmp_path: Path,
    pm_events: list[tuple[int, str]],
) -> Path:
    db = tmp_path / "r.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            "CREATE TABLE pm_events (received_at_ms INTEGER, subscription_id TEXT, "
            "event_type TEXT, asset_id TEXT, condition_id TEXT, payload_json TEXT)"
        )
        conn.execute(
            "CREATE TABLE cex_trades (received_at_ms INTEGER, trade_time_ms INTEGER, "
            "symbol TEXT, price REAL, size REAL, is_buyer_maker INTEGER)"
        )
        for ts, etype in pm_events:
            conn.execute(
                "INSERT INTO pm_events VALUES (?, 's1', ?, 'a1', 'c1', '{}')",
                (ts, etype),
            )
        conn.commit()
    finally:
        conn.close()
    return db


class TestIterEventsQuarantine:
    def test_quarantine_filters_events(self, tmp_path):
        from core.backtest_bot_e import iter_events
        # Events at 1000, 2000, 10000, 11000 ms.
        db = _make_recorder_db_with_events(
            tmp_path,
            [(1000, "book"), (2000, "book"), (10000, "book"), (11000, "book")],
        )
        # Quarantine range that covers 1500-3000.
        events = list(iter_events(db, quarantine=[(1500, 3000)]))
        timestamps = [e.ts_ms for e in events]
        assert 1000 in timestamps
        assert 2000 not in timestamps  # quarantined
        assert 10000 in timestamps
        assert 11000 in timestamps

    def test_no_quarantine_returns_all(self, tmp_path):
        from core.backtest_bot_e import iter_events
        db = _make_recorder_db_with_events(
            tmp_path,
            [(1000, "book"), (2000, "book"), (3000, "book")],
        )
        events = list(iter_events(db))
        assert len(events) == 3
