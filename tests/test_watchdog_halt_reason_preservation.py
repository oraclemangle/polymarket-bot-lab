"""Test watchdog halt-reason preservation (2026-04-17).

When a bot is already halted by an operator with a human-readable reason
(e.g. "Session 17 operator decision..."), subsequent watchdog-triggered
halts for the same bot MUST NOT overwrite the operator's text. Instead,
only the `set_at` timestamp advances.

Context: bot_b was halted manually with a Session 17 operator reason.
After oracle-mangle had an outage, the scorer.liveness watchdog check
started firing every minute, overwriting the reason field to
"scorer stale: last score Xm ago" on every tick. The misleading display
made it look like the scorer was the reason bot_b wasn't trading, when
in fact the operator had already halted it for a different (and still
current) reason.

Fix: watchdog prefixes its own reasons with "watchdog: " and only
overwrites prior reasons that (a) are empty, or (b) already start with
"watchdog: ". Operator-set text (anything else) is preserved across
subsequent watchdog trips.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.db import Base, HaltFlag
from core.watchdog import Watchdog, WatchdogConfig


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def wd(session_factory):
    cfg = WatchdogConfig(
        bot_a_initial_usd=Decimal("100"),
        bot_b_initial_usd=Decimal("100"),
    )
    return Watchdog(
        cfg,
        cancel_all=lambda bot_id: 0,
        session_factory=session_factory,
    )


def _get_flag(sf, bot_id):
    with sf() as s:
        return s.get(HaltFlag, bot_id)


def test_halt_prefixes_watchdog_reason(wd, session_factory):
    wd._halt("bot_a", "aggregate exposure $500 > cap $400")
    flag = _get_flag(session_factory, "bot_a")
    assert flag.halted == 1
    assert flag.reason.startswith("watchdog: ")
    assert "aggregate exposure" in flag.reason


def test_operator_reason_is_preserved_on_watchdog_retrigger(wd, session_factory):
    """The scenario that motivated this fix."""
    # Operator manually halts with a human reason.
    operator_reason = (
        "Session 17 operator decision: live trading halted; existing 7 "
        "positions to resolve naturally; future B activity is paper-only "
        "via bot_b_shadow"
    )
    with session_factory() as s:
        s.add(HaltFlag(
            bot_id="bot_b",
            halted=1,
            reason=operator_reason,
            set_at=datetime.now(UTC),
        ))
        s.commit()

    # Watchdog then halts bot_b because scorer went stale.
    wd._halt("bot_b", "scorer stale: last score 632.0m ago")

    flag = _get_flag(session_factory, "bot_b")
    # Still halted (halted=1 reaffirmed).
    assert flag.halted == 1
    # But the operator's reason is preserved.
    assert flag.reason == operator_reason
    assert "scorer stale" not in flag.reason
    # set_at should still advance so monitoring knows the halt was reaffirmed.
    # (hard to assert exact time; just ensure it's recent)
    now = datetime.now(UTC)
    set_at = flag.set_at
    if set_at.tzinfo is None:
        set_at = set_at.replace(tzinfo=UTC)
    assert (now - set_at).total_seconds() < 5


def test_prior_watchdog_reason_can_be_overwritten(wd, session_factory):
    """A bot halted by an earlier watchdog check should have its reason
    updated when a different check fires later — e.g. drawdown → now
    scorer-stale is the primary concern."""
    wd._halt("bot_a", "drawdown 16% > kill 15%")
    flag = _get_flag(session_factory, "bot_a")
    assert flag.reason == "watchdog: drawdown 16% > kill 15%"

    wd._halt("bot_a", "aggregate exposure $500 > cap $400")
    flag = _get_flag(session_factory, "bot_a")
    # Newer watchdog reason wins.
    assert "aggregate exposure" in flag.reason
    assert "drawdown" not in flag.reason


def test_empty_prior_reason_is_overwritten(wd, session_factory):
    """If somehow a HaltFlag exists with null/empty reason, watchdog fills it."""
    with session_factory() as s:
        s.add(HaltFlag(
            bot_id="bot_a",
            halted=1,
            reason="",
            set_at=datetime.now(UTC),
        ))
        s.commit()

    wd._halt("bot_a", "drawdown 20% > kill 15%")
    flag = _get_flag(session_factory, "bot_a")
    assert flag.reason.startswith("watchdog: ")
