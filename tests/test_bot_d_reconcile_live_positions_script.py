"""CLI smoke test for scripts.bot_d_reconcile_live_positions.

Verifies:
- Dry-run is the default; --execute is required to mutate.
- --json prints a parseable summary with the expected keys.
- Exit code 0 on ok=True, 2 on Data API failure.
- Wallet resolution falls back through --wallet → POLYMARKET_WALLET.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from core.db import Position, get_session_factory
from scripts import bot_d_reconcile_live_positions as repair


BOT_ID = "bot_d_live_probe"


class _StubResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> Any:
        return self._payload


@pytest.fixture
def _seed(tmp_db):
    sf = get_session_factory()
    with sf() as s:
        for tid in ["tok-present", "tok-stale-1", "tok-stale-2"]:
            s.add(
                Position(
                    bot_id=BOT_ID,
                    condition_id=f"cond-{tid}",
                    token_id=tid,
                    side="YES",
                    size=Decimal("10"),
                    avg_price=Decimal("0.5"),
                    cost_basis_usd=Decimal("5"),
                    status="OPEN",
                    opened_at=datetime.now(UTC) - timedelta(days=1),
                )
            )
        s.commit()
    yield


def _patch_data_api(monkeypatch, payload, *, fail=False):
    """Patch httpx.Client so the reconciler sees a deterministic wallet response."""
    import httpx

    class _Client:
        def __init__(self, *a, **kw):
            pass

        def get(self, _url, params=None):
            if fail:
                raise RuntimeError("network down")
            return _StubResponse(payload)

        def close(self):
            pass

    monkeypatch.setattr(httpx, "Client", _Client)


def test_dry_run_is_default(_seed, monkeypatch, capsys):
    _patch_data_api(monkeypatch, [{"asset": "tok-present"}])
    rc = repair.run([
        "--wallet", "0xABCDEFabcdef0000000000000000000000000001",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DRY-RUN" in out
    assert "WOULD CLOSE" in out
    assert "No changes were written" in out
    # DB unchanged.
    sf = get_session_factory()
    with sf() as s:
        open_count = s.scalar(
            __import__("sqlalchemy").text(
                f"SELECT COUNT(*) FROM positions WHERE bot_id='{BOT_ID}' AND status='OPEN'"
            )
        )
    assert open_count == 3


def test_execute_mutates(_seed, monkeypatch, capsys):
    _patch_data_api(monkeypatch, [{"asset": "tok-present"}])
    rc = repair.run([
        "--wallet", "0xABCDEFabcdef0000000000000000000000000001",
        "--execute",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DRY-RUN" not in out
    assert "CLOSED:" in out
    sf = get_session_factory()
    with sf() as s:
        open_count = s.scalar(
            __import__("sqlalchemy").text(
                f"SELECT COUNT(*) FROM positions WHERE bot_id='{BOT_ID}' AND status='OPEN'"
            )
        )
        closed_count = s.scalar(
            __import__("sqlalchemy").text(
                f"SELECT COUNT(*) FROM positions WHERE bot_id='{BOT_ID}' AND status='CLOSED_EXTERNAL_SYNC'"
            )
        )
    assert open_count == 1
    assert closed_count == 2


def test_json_output(_seed, monkeypatch, capsys):
    _patch_data_api(monkeypatch, [{"asset": "tok-present"}])
    rc = repair.run([
        "--wallet", "0xABCDEFabcdef0000000000000000000000000001",
        "--json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    summary = json.loads(out)
    assert summary["bot_id"] == BOT_ID
    assert summary["dry_run"] is True
    assert summary["before"]["open_count"] == 3
    assert summary["closed_count"] == 2
    assert summary["kept_open"] == 1


def test_data_api_failure_returns_exit_code_2(_seed, monkeypatch, capsys):
    _patch_data_api(monkeypatch, None, fail=True)
    rc = repair.run([
        "--wallet", "0xABCDEFabcdef0000000000000000000000000001",
    ])
    out = capsys.readouterr().out
    assert rc == 2
    # No mutation.
    sf = get_session_factory()
    with sf() as s:
        open_count = s.scalar(
            __import__("sqlalchemy").text(
                f"SELECT COUNT(*) FROM positions WHERE bot_id='{BOT_ID}' AND status='OPEN'"
            )
        )
    assert open_count == 3


def test_wallet_from_env(_seed, monkeypatch, capsys):
    _patch_data_api(monkeypatch, [{"asset": "tok-present"}])
    monkeypatch.setenv("POLYMARKET_WALLET", "0xenvenvenvenvenvenvenvenvenvenvenvenv0001")
    rc = repair.run([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0xenvenvenv" in out  # truncated wallet display
