"""Tests for Portfolio.reconcile_live_positions_against_wallet.

Bot D live-probe accumulated 17 stale OPEN positions on the bot container that the
hot wallet no longer holds (sold/redeemed but the on_fill/on_redeem path
missed them). The dashboard exposure card summed all OPEN rows and
overstated real exposure ~3.3× ($100.35 vs ~$30.80 wallet value).

This module exercises the local-ledger-truth reconciler. The reconciler
never touches the wallet, CLOB, or keys — it only compares local
``Position(status='OPEN')`` rows against the wallet's current Data API
``/positions`` response and closes rows the wallet no longer holds.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from core.db import Event, Position, get_session_factory
from core.portfolio import Portfolio


BOT_ID = "bot_d_live_probe"
WALLET = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


@pytest.fixture
def pfo(tmp_db, monkeypatch):
    from core import portfolio
    monkeypatch.setattr(portfolio, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))
    return Portfolio()


class _StubResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> Any:
        return self._payload


class _StubClient:
    """Subset of httpx.Client used by reconcile_live_positions_against_wallet."""

    def __init__(self, positions_payload: Any, *, fail: Exception | None = None) -> None:
        self._payload = positions_payload
        self._fail = fail
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, params: dict | None = None) -> _StubResponse:
        self.calls.append({"url": url, "params": dict(params or {})})
        if self._fail is not None:
            raise self._fail
        return _StubResponse(self._payload)

    def close(self) -> None:
        pass


def _seed_open_position(token_id: str, *, size: str = "10", cost: str = "5.00") -> int:
    sf = get_session_factory()
    with sf() as s:
        pos = Position(
            bot_id=BOT_ID,
            condition_id=f"cond-{token_id}",
            token_id=token_id,
            side="YES",
            size=Decimal(size),
            avg_price=Decimal("0.50"),
            cost_basis_usd=Decimal(cost),
            status="OPEN",
            opened_at=datetime.now(UTC) - timedelta(days=2),
        )
        s.add(pos)
        s.commit()
        return int(pos.id)


def _open_positions(bot_id: str = BOT_ID) -> list[Position]:
    sf = get_session_factory()
    with sf() as s:
        return list(
            s.scalars(
                select(Position).where(
                    Position.bot_id == bot_id, Position.status == "OPEN"
                )
            )
        )


def _positions_by_status(status: str, bot_id: str = BOT_ID) -> list[Position]:
    sf = get_session_factory()
    with sf() as s:
        return list(
            s.scalars(
                select(Position).where(
                    Position.bot_id == bot_id, Position.status == status
                )
            )
        )


# ------------------------------------------------------------------ #
# Core happy path
# ------------------------------------------------------------------ #


def test_present_positions_remain_open(pfo):
    _seed_open_position("tok-a")
    _seed_open_position("tok-b")
    client = _StubClient([
        {"asset": "tok-a", "size": "10", "currentValue": "5.0"},
        {"asset": "tok-b", "size": "5", "currentValue": "2.5"},
    ])

    result = pfo.reconcile_live_positions_against_wallet(
        BOT_ID, WALLET, http_client=client,
    )

    assert result["ok"] is True
    assert result["checked"] == 2
    assert result["kept_open"] == 2
    assert result["closed_count"] == 0
    assert len(_open_positions()) == 2


def test_absent_positions_get_closed(pfo):
    """Five present, seventeen absent — mirrors the production state."""
    present_token_ids = [f"tok-present-{i}" for i in range(5)]
    absent_token_ids = [f"tok-stale-{i}" for i in range(17)]
    for tid in present_token_ids + absent_token_ids:
        _seed_open_position(tid, cost="5.91")  # ~$100.47 total cost basis

    client = _StubClient([
        {"asset": tid, "size": "10", "currentValue": "5.0"}
        for tid in present_token_ids
    ])

    result = pfo.reconcile_live_positions_against_wallet(
        BOT_ID, WALLET, http_client=client,
    )

    assert result["ok"] is True
    assert result["checked"] == 22
    assert result["kept_open"] == 5
    assert result["closed_count"] == 17

    # Wallet-confirmed positions still OPEN; stale rows are
    # CLOSED_EXTERNAL_SYNC, not vanilla CLOSED.
    open_now = _open_positions()
    assert {p.token_id for p in open_now} == set(present_token_ids)
    closed_now = _positions_by_status("CLOSED_EXTERNAL_SYNC")
    assert {p.token_id for p in closed_now} == set(absent_token_ids)
    for pos in closed_now:
        assert pos.closed_at is not None


def test_event_emitted_per_closed_row(pfo):
    _seed_open_position("tok-present")
    _seed_open_position("tok-stale", size="100", cost="50.0")
    client = _StubClient([{"asset": "tok-present", "size": "10"}])

    pfo.reconcile_live_positions_against_wallet(BOT_ID, WALLET, http_client=client)

    sf = get_session_factory()
    with sf() as s:
        events = list(
            s.scalars(
                select(Event).where(
                    Event.bot_id == BOT_ID,
                    Event.event_type == "bot_d.live_position_reconciled",
                )
            )
        )
    assert len(events) == 1
    payload = events[0].payload
    assert payload["token_id"] == "tok-stale"
    assert payload["reason"] == "not_in_wallet_positions"
    # Decimal columns persist with full Numeric(18,8) precision.
    assert Decimal(payload["size"]) == Decimal("100")
    assert Decimal(payload["cost_basis_usd"]) == Decimal("50.0")


# ------------------------------------------------------------------ #
# Idempotency
# ------------------------------------------------------------------ #


def test_idempotent_second_run_changes_nothing(pfo):
    _seed_open_position("tok-present")
    _seed_open_position("tok-stale")
    client = _StubClient([{"asset": "tok-present"}])

    first = pfo.reconcile_live_positions_against_wallet(BOT_ID, WALLET, http_client=client)
    assert first["closed_count"] == 1

    second = pfo.reconcile_live_positions_against_wallet(BOT_ID, WALLET, http_client=client)
    # Only one OPEN row remains and the wallet still holds it → zero changes.
    assert second["ok"] is True
    assert second["checked"] == 1
    assert second["kept_open"] == 1
    assert second["closed_count"] == 0

    # One Event, not two.
    sf = get_session_factory()
    with sf() as s:
        events = list(
            s.scalars(
                select(Event).where(
                    Event.bot_id == BOT_ID,
                    Event.event_type == "bot_d.live_position_reconciled",
                )
            )
        )
    assert len(events) == 1


# ------------------------------------------------------------------ #
# Failure modes
# ------------------------------------------------------------------ #


def test_data_api_failure_leaves_rows_unchanged(pfo):
    _seed_open_position("tok-a")
    _seed_open_position("tok-b")
    client = _StubClient(None, fail=RuntimeError("connection refused"))

    result = pfo.reconcile_live_positions_against_wallet(
        BOT_ID, WALLET, http_client=client,
    )

    assert result["ok"] is False
    assert "data_api_error" in result["reason"]
    assert result["closed_count"] == 0
    assert result["kept_open"] == 2
    # Both rows still OPEN — no destructive change on API failure.
    assert len(_open_positions()) == 2
    # No events emitted on failure.
    sf = get_session_factory()
    with sf() as s:
        events = list(
            s.scalars(
                select(Event).where(
                    Event.event_type == "bot_d.live_position_reconciled"
                )
            )
        )
    assert events == []


def test_empty_local_ledger_returns_zero(pfo):
    client = _StubClient([{"asset": "tok-from-wallet"}])
    result = pfo.reconcile_live_positions_against_wallet(
        BOT_ID, WALLET, http_client=client,
    )
    assert result["ok"] is True
    assert result["checked"] == 0
    assert result["closed_count"] == 0


# ------------------------------------------------------------------ #
# Dry run
# ------------------------------------------------------------------ #


def test_dry_run_does_not_mutate(pfo):
    _seed_open_position("tok-present")
    stale_id = _seed_open_position("tok-stale")
    client = _StubClient([{"asset": "tok-present"}])

    result = pfo.reconcile_live_positions_against_wallet(
        BOT_ID, WALLET, http_client=client, dry_run=True,
    )

    assert result["ok"] is True
    assert result["closed_count"] == 1
    assert result["dry_run"] is True
    assert result["closed_positions"][0]["id"] == stale_id

    # No DB mutation.
    open_now = _open_positions()
    assert {p.token_id for p in open_now} == {"tok-present", "tok-stale"}
    assert _positions_by_status("CLOSED_EXTERNAL_SYNC") == []
    # No events emitted in dry run.
    sf = get_session_factory()
    with sf() as s:
        events = list(
            s.scalars(
                select(Event).where(
                    Event.event_type == "bot_d.live_position_reconciled"
                )
            )
        )
    assert events == []


# ------------------------------------------------------------------ #
# Safety surface — no order/cancel/redeem methods touched
# ------------------------------------------------------------------ #


def test_reconcile_does_not_touch_clob_or_wallet(pfo):
    """The reconciler accepts only an http_client and never imports the
    CLOB/keystore. We assert that by exercising a stub client with no
    CLOB methods at all — if the reconciler ever tried to place/cancel
    orders or redeem positions, it would AttributeError on the stub.
    """
    _seed_open_position("tok-stale")

    class _MinimalClient:
        def __init__(self):
            self.calls = 0

        def get(self, _url, params=None):
            self.calls += 1
            return _StubResponse([])  # wallet empty → close the row

        def close(self):
            pass

    client = _MinimalClient()
    result = pfo.reconcile_live_positions_against_wallet(
        BOT_ID, WALLET, http_client=client,
    )
    assert result["ok"] is True
    assert result["closed_count"] == 1
    assert client.calls == 1


def test_only_specified_bot_id_is_touched(pfo):
    """A reconcile for bot_d_live_probe must not affect other bots' rows."""
    _seed_open_position("tok-bot-d-stale")
    # Other-bot OPEN row at the same token id (different bot_id).
    sf = get_session_factory()
    with sf() as s:
        s.add(
            Position(
                bot_id="bot_g_prime_live",
                condition_id="cond-g",
                token_id="tok-bot-d-stale",
                side="YES",
                size=Decimal("1"),
                avg_price=Decimal("0.5"),
                cost_basis_usd=Decimal("0.5"),
                status="OPEN",
                opened_at=datetime.now(UTC),
            )
        )
        s.commit()

    client = _StubClient([])  # wallet "empty"
    result = pfo.reconcile_live_positions_against_wallet(
        BOT_ID, WALLET, http_client=client,
    )
    assert result["closed_count"] == 1

    g_open = _open_positions(bot_id="bot_g_prime_live")
    assert len(g_open) == 1  # untouched


# ------------------------------------------------------------------ #
# Dashboard surface — caps exclude reconciled stale rows
# ------------------------------------------------------------------ #


def test_dashboard_caps_exclude_reconciled_stale_rows(pfo, monkeypatch):
    """`_bot_d_live_probe_caps` must report counts based on the post-reconcile
    OPEN set (rows still in the wallet), not the raw historical OPEN count.
    """
    # Seed exactly the production pattern: 5 wallet-confirmed, 17 stale.
    present = [f"tok-present-{i}" for i in range(5)]
    stale = [f"tok-stale-{i}" for i in range(17)]
    for tid in present + stale:
        _seed_open_position(tid, cost="5.91")  # cost basis $5.91 each → $130.02 total

    # Mock the keystore/env reads — caps() reads env via _env_from_unit and
    # we just want defaults to apply. No mutation needed.
    from dashboard.runtime_queries import _bot_d_live_probe_caps

    # Before reconcile: all 22 OPEN, exposure ≈ $130
    pre = _bot_d_live_probe_caps(BOT_ID)
    assert pre["open_positions"] == 22
    assert pre["basis"] == "cost_basis_local_ledger"
    assert pre["reconciler"]["stale_row_status"] == "CLOSED_EXTERNAL_SYNC"

    # Reconcile against a wallet that holds only the 5 present rows.
    client = _StubClient([{"asset": tid} for tid in present])
    result = pfo.reconcile_live_positions_against_wallet(
        BOT_ID, WALLET, http_client=client,
    )
    assert result["closed_count"] == 17

    # After reconcile: only the 5 wallet-confirmed rows count.
    post = _bot_d_live_probe_caps(BOT_ID)
    assert post["open_positions"] == 5
    assert abs(post["open_cost_usd"] - 5 * 5.91) < 0.01
    # Sanity: filled_plus_resting_exposure_usd dropped accordingly.
    assert post["filled_plus_resting_exposure_usd"] < pre["filled_plus_resting_exposure_usd"]
