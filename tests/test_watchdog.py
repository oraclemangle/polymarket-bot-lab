"""Watchdog tests."""

from __future__ import annotations

import inspect
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from core.db import Market, Score, Trade, get_session_factory
from core.portfolio import Portfolio
from core.watchdog import CheckResult, Watchdog, WatchdogConfig


@pytest.fixture
def pfo(tmp_db, monkeypatch):
    from core import portfolio

    monkeypatch.setattr(portfolio, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))
    return Portfolio()


@pytest.fixture
def cancelled(monkeypatch):
    calls: list[str] = []
    return calls


@pytest.fixture
def wd(pfo, cancelled):
    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("1000"),
        bot_b_initial_usd=Decimal("1000"),
        bot_a_dd_kill_pct=Decimal("15"),
        bot_b_dd_kill_pct=Decimal("15"),
    )

    def cancel(bot_id: str) -> int:
        cancelled.append(bot_id)
        return 0

    return Watchdog(cfg, portfolio=pfo, cancel_all=cancel)


def test_scraper_stale_triggers_kill(wd, monkeypatch):
    monkeypatch.setenv("MARKET_CATALOG_WATCHDOG_ENABLED", "true")
    # No markets ingested → warn.
    session_factory = get_session_factory()
    results = wd.run_once()
    scraper = next(r for r in results if r.name == "scraper.liveness")
    assert not scraper.ok

    # Old market → kill.
    with session_factory() as s:
        s.add(
            Market(
                condition_id="c1",
                category="politics",
                question="?",
                fee_rate_bps=40,
                last_updated=datetime.now(UTC) - timedelta(hours=2),
            )
        )
        s.commit()
    results = wd.run_once()
    scraper = next(r for r in results if r.name == "scraper.liveness")
    assert not scraper.ok
    assert scraper.severity == "kill"


def test_recorder_freshness_uses_append_only_latest_row_lookup(wd):
    """The recorder DB can be hundreds of GB; freshness must not scan it."""
    src = inspect.getsource(Watchdog._check_recorder_freshness)
    assert "MAX(received_at_ms)" not in src
    assert "MAX(emitted_at_ms)" not in src
    assert "ORDER BY id DESC LIMIT 1" in src


def test_recorder_freshness_ok_with_fresh_pm_and_heartbeat(tmp_path, wd, monkeypatch):
    db_path = tmp_path / "recorder.db"
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE pm_events (id INTEGER PRIMARY KEY AUTOINCREMENT, received_at_ms INTEGER NOT NULL);
        CREATE TABLE heartbeats (id INTEGER PRIMARY KEY AUTOINCREMENT, emitted_at_ms INTEGER NOT NULL);
        """
    )
    con.execute("INSERT INTO pm_events (received_at_ms) VALUES (?)", (now_ms,))
    con.execute("INSERT INTO heartbeats (emitted_at_ms) VALUES (?)", (now_ms,))
    con.commit()
    con.close()

    monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(db_path))
    result = wd._check_recorder_freshness()
    assert result.ok is True


def test_halt_flag_set_and_unhalt(wd):
    session_factory = get_session_factory()
    # Force a kill by triggering aggregate exposure cap.
    from core.db import Position

    with session_factory() as s:
        s.add(
            Position(
                bot_id="bot_b",
                condition_id="c1",
                token_id="t1",
                side="YES",
                size=Decimal("1"),
                avg_price=Decimal("1"),
                cost_basis_usd=Decimal("5000"),
                status="OPEN",
            )
        )
        s.commit()
    wd.run_once()
    assert wd.is_halted("bot_b")

    ok = wd.unhalt("bot_b", "test unhalt")
    assert ok
    assert not wd.is_halted("bot_b")


def test_healthy_state_no_halt(wd, monkeypatch):
    # Fresh market ingest + a recent trade → vpn check is the only remaining hazard
    # (resolution may still fail in CI). Stub vpn check.
    monkeypatch.setattr(wd, "_check_vpn", lambda: __import__(
        "core.watchdog", fromlist=["CheckResult"]
    ).CheckResult(name="vpn.liveness", ok=True))
    session_factory = get_session_factory()
    now = datetime.now(UTC)
    with session_factory() as s:
        s.add(
            Market(
                condition_id="c1",
                category="politics",
                question="?",
                fee_rate_bps=40,
                last_updated=now,
            )
        )
        s.add(
            Trade(
                trade_id="t1",
                bot_id="bot_a",
                order_id=None,
                condition_id="c1",
                token_id="y1",
                side="BUY",
                price=Decimal("0.04"),
                size=Decimal("10"),
                fee_usd=Decimal("0"),
                filled_at=now,
                usd_gbp_rate=Decimal("0.80"),
                gbp_notional=Decimal("0.32"),
            )
        )
        s.commit()
    results = wd.run_once()
    kills = [r for r in results if not r.ok and r.severity == "kill"]
    assert kills == []
    assert not wd.is_halted("bot_a")
    assert not wd.is_halted("bot_b")


def test_alert_dedupe_suppresses_repeat_notifications(pfo, cancelled, tmp_db, monkeypatch):
    """Same failing check must notify once, then be throttled."""
    monkeypatch.setenv("MARKET_CATALOG_WATCHDOG_ENABLED", "true")
    sent: list[tuple[str, str]] = []
    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("1000"),
        bot_b_initial_usd=Decimal("1000"),
        alert_dedupe_seconds=1800,
    )
    w = Watchdog(
        cfg,
        portfolio=pfo,
        cancel_all=lambda _b: 0,
        notify=lambda s, m: sent.append((s, m)),
    )

    # Two back-to-back run_once() on a cold DB: scraper.liveness fires KILL both times
    # because no markets ingested, but we should notify only once.
    w.run_once()
    w.run_once()
    # Could be 1 or 2 depending on how many kill-class checks fire; the key invariant
    # is that the same (check, severity) key doesn't fire twice.
    # Each failing check must have been notified exactly once in the window.
    assert len([m for _s, m in sent if "scraper.liveness" in m]) == 1
    # scorer may or may not fire depending on fixture; if it did, only once.
    assert len([m for _s, m in sent if "scorer.liveness" in m]) <= 1


def test_alert_dedupe_allows_notification_after_window(pfo, cancelled, tmp_db, monkeypatch):
    monkeypatch.setenv("MARKET_CATALOG_WATCHDOG_ENABLED", "true")
    sent: list[tuple[str, str]] = []
    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("1000"),
        bot_b_initial_usd=Decimal("1000"),
        alert_dedupe_seconds=0,  # no throttling
    )
    w = Watchdog(
        cfg,
        portfolio=pfo,
        cancel_all=lambda _b: 0,
        notify=lambda s, m: sent.append((s, m)),
    )

    w.run_once()
    w.run_once()
    # With zero dedupe window, both runs should notify.
    assert len([m for _s, m in sent if "scraper.liveness" in m]) == 2


def test_scorer_liveness_only_halts_bot_b_and_still_alerts(pfo, tmp_db, monkeypatch):
    sent: list[tuple[str, str]] = []
    cancelled: list[str] = []
    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("1000"),
        bot_b_initial_usd=Decimal("1000"),
        scorer_stale_minutes=120,
    )
    monkeypatch.setenv("BOT_B_WATCHDOG_ENABLED", "true")
    w = Watchdog(
        cfg,
        portfolio=pfo,
        cancel_all=lambda bot_id: cancelled.append(bot_id) or 0,
        notify=lambda sev, msg: sent.append((sev, msg)),
    )
    monkeypatch.setattr(w, "_check_vpn", lambda: CheckResult(name="vpn.liveness", ok=True))
    session_factory = get_session_factory()
    now = datetime.now(UTC)
    with session_factory() as s:
        s.add(
            Market(
                condition_id="c1",
                category="politics",
                question="?",
                fee_rate_bps=40,
                last_updated=now,
            )
        )
        s.add(
            Trade(
                trade_id="t1",
                bot_id="bot_e",
                order_id=None,
                condition_id="c1",
                token_id="y1",
                side="BUY",
                price=Decimal("0.04"),
                size=Decimal("10"),
                fee_usd=Decimal("0"),
                filled_at=now,
                usd_gbp_rate=Decimal("0.80"),
                gbp_notional=Decimal("0.32"),
            )
        )
        s.add(
            Score(
                condition_id="c1",
                scored_at=now - timedelta(hours=3),
                model_version="test",
            )
        )
        s.commit()

    w.run_once()

    assert cancelled == ["bot_b"]
    assert w.is_halted("bot_b")
    assert not w.is_halted("bot_c")
    assert not w.is_halted("bot_d")
    assert not w.is_halted("bot_e")
    assert any("[halt] bot_b halted" in msg for _sev, msg in sent)
    assert not any("[scorer.liveness]" in msg for _sev, msg in sent)


def test_scorer_liveness_skips_when_bot_b_parked(pfo, tmp_db, monkeypatch):
    sent: list[tuple[str, str]] = []
    cancelled: list[str] = []
    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("1000"),
        bot_b_initial_usd=Decimal("1000"),
        scorer_stale_minutes=120,
    )
    w = Watchdog(
        cfg,
        portfolio=pfo,
        cancel_all=lambda bot_id: cancelled.append(bot_id) or 0,
        notify=lambda sev, msg: sent.append((sev, msg)),
    )
    monkeypatch.delenv("BOT_B_WATCHDOG_ENABLED", raising=False)
    monkeypatch.setattr(w, "_check_vpn", lambda: CheckResult(name="vpn.liveness", ok=True))
    session_factory = get_session_factory()
    now = datetime.now(UTC)
    with session_factory() as s:
        s.add(
            Market(
                condition_id="c1",
                category="politics",
                question="?",
                fee_rate_bps=40,
                last_updated=now,
            )
        )
        s.add(
            Trade(
                trade_id="t1",
                bot_id="bot_e",
                order_id=None,
                condition_id="c1",
                token_id="y1",
                side="BUY",
                price=Decimal("0.04"),
                size=Decimal("10"),
                fee_usd=Decimal("0"),
                filled_at=now,
                usd_gbp_rate=Decimal("0.80"),
                gbp_notional=Decimal("0.32"),
            )
        )
        s.add(
            Score(
                condition_id="c1",
                scored_at=now - timedelta(hours=3),
                model_version="test",
            )
        )
        s.commit()

    results = w.run_once()
    scorer = next(r for r in results if r.name == "scorer.liveness")

    assert scorer.ok
    assert "parked" in scorer.message
    assert cancelled == []
    assert not w.is_halted("bot_b")
    assert sent == []


def test_scraper_liveness_skips_when_catalog_watchdog_disabled(wd, monkeypatch):
    monkeypatch.delenv("MARKET_CATALOG_WATCHDOG_ENABLED", raising=False)

    results = wd.run_once()
    scraper = next(r for r in results if r.name == "scraper.liveness")

    assert scraper.ok
    assert "skipped" in scraper.message


def test_scraper_liveness_uses_explicit_market_catalog_scope(pfo, tmp_db, monkeypatch):
    monkeypatch.setenv("MARKET_CATALOG_WATCHDOG_ENABLED", "true")
    cancelled: list[str] = []
    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("1000"),
        bot_b_initial_usd=Decimal("1000"),
    )
    w = Watchdog(cfg, portfolio=pfo, cancel_all=lambda bot_id: cancelled.append(bot_id) or 0)
    monkeypatch.setattr(w, "_check_vpn", lambda: CheckResult(name="vpn.liveness", ok=True))
    session_factory = get_session_factory()
    old = datetime.now(UTC) - timedelta(hours=2)
    with session_factory() as s:
        s.add(
            Market(
                condition_id="c1",
                category="politics",
                question="?",
                fee_rate_bps=40,
                last_updated=old,
            )
        )
        s.add(
            Trade(
                trade_id="t1",
                bot_id="bot_e",
                order_id=None,
                condition_id="c1",
                token_id="y1",
                side="BUY",
                price=Decimal("0.04"),
                size=Decimal("10"),
                fee_usd=Decimal("0"),
                filled_at=datetime.now(UTC),
                usd_gbp_rate=Decimal("0.80"),
                gbp_notional=Decimal("0.32"),
            )
        )
        s.commit()

    w.run_once()

    assert set(cancelled) == {
        "bot_b",
        "bot_c",
        "bot_d",
        "bot_d_live_probe",
    }
    assert not w.is_halted("bot_e")
    assert not w.is_halted("bot_f_mirror")
