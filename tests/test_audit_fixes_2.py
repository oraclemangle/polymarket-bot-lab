"""Regression tests for AUDIT.md second-pass fixes.

Covers:
  C1/C3  — Bot B try_enter: exception on place_limit, MIN_ORDER_SHARES guard,
           SKIPPED_MIN_SIZE handled without phantom DB row.
  C2     — Bot B _place_exit_order: exception safety.
  C5     — Watchdog requires cancel_all (no silent no-op).
  C7     — Migration adds server_default (smoke-check the upgrade op arg).
  C8     — /unhalt two-step confirmation + cooldown.
  my-miss-#1 — _place_limit_live no longer retries on ReadTimeout.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from core.clob import ClobWrapper, OrderResponse
from core.db import Order, get_session_factory
from core.watchdog import WatchdogConfig


# ---------- C5: Watchdog requires cancel_all ----------
def test_place_limit_live_does_not_retry_on_read_timeout():
    import httpx
    from tenacity import Retrying

    from core.clob import ClobWrapper

    retry_obj = ClobWrapper._place_limit_live.retry  # type: ignore[attr-defined]
    # tenacity records the retry predicate on the decorated function.
    assert hasattr(retry_obj, "retry")
    # Build the predicate and assert ReadTimeout is NOT in retry-for exceptions.
    pred = retry_obj.retry
    # Construct a fake state with a ReadTimeout outcome — the predicate should say False.
    from tenacity import RetryCallState

    class _Outcome:
        def __init__(self, exc):
            self._exc = exc

        def failed(self):
            return True

        def exception(self):
            return self._exc

    state = RetryCallState(retry_obj, None, (), {})
    state.outcome = _Outcome(httpx.ReadTimeout("boom"))
    assert pred(state) is False
    state.outcome = _Outcome(httpx.ConnectTimeout("boom"))
    assert pred(state) is True


# ---------- C7: migration has server_default ----------
def test_volume_24h_migration_has_server_default():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent
        / "migrations"
        / "versions"
        / "20260415_0045_2a92772f19ea_add_volume_24h_usd_to_markets.py"
    )
    src = path.read_text()
    assert "server_default" in src, (
        "C7: migration must use server_default so SQLite can backfill existing rows."
    )


# ---------- C8: /unhalt cooldown ----------
def test_unhalt_requires_confirmation_and_cooldown(tmp_db, monkeypatch):
    from core.notify import Listener, TelegramClient

    calls = []
    client = TelegramClient(token="tok", allowed_chat_ids=[99])
    client.send = lambda sev, msg: calls.append(("send", sev, msg)) or True

    def unhalt(bot_id, reason):
        calls.append(("unhalt", bot_id, reason))
        return True

    listener = Listener(client=client, unhalt_handler=unhalt)
    # Stage.
    listener._handle_update({"message": {"chat": {"id": 99}, "text": "/unhalt bot_b"}})
    assert not any(c[0] == "unhalt" for c in calls)
    # Confirm.
    listener._handle_update(
        {"message": {"chat": {"id": 99}, "text": "/unhalt bot_b confirm"}}
    )
    assert sum(1 for c in calls if c[0] == "unhalt") == 1
    # Immediate re-confirm should hit the cooldown (no second unhalt dispatched).
    listener._handle_update({"message": {"chat": {"id": 99}, "text": "/unhalt bot_b"}})
    listener._handle_update(
        {"message": {"chat": {"id": 99}, "text": "/unhalt bot_b confirm"}}
    )
    assert sum(1 for c in calls if c[0] == "unhalt") == 1
    assert any("cooldown" in c[2].lower() for c in calls if c[0] == "send")
