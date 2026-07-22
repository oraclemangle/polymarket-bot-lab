"""Tests for Portfolio.reconcile_paper_resolutions (Session 17r-ext Bot D fix).

Paper mode never triggers on_redeem, so OPEN positions accumulated past
end_date until Session 17n's one-off manual SQL. This is the loop-level
replacement — verified here against a stubbed Gamma response.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from core.db import Event, Market, Position, Trade, get_session_factory
from core.portfolio import Portfolio


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
    """Matches the subset of httpx.Client used by reconcile_paper_resolutions."""

    def __init__(self, payloads_by_cid: dict[str, Any]) -> None:
        self._by_cid = payloads_by_cid
        self.calls: list[str] = []

    def get(self, _url: str, params: dict | None = None) -> _StubResponse:
        params = params or {}
        # The helper uses either `condition_ids=` (hex) or `id=` (Gamma numeric id).
        cid = params.get("condition_ids") or params.get("id") or ""
        self.calls.append(cid)
        return _StubResponse(self._by_cid.get(cid, []))

    def close(self) -> None:
        pass


def _seed_market(end_date: datetime | None, cid: str, yes: str, no: str) -> None:
    sf = get_session_factory()
    with sf() as s:
        s.add(
            Market(
                condition_id=cid,
                category="weather",
                question="Will it rain?",
                end_date=end_date,
                yes_token_id=yes,
                no_token_id=no,
            )
        )
        s.commit()


def _seed_buy(pfo: Portfolio, bot: str, token: str, cid: str, price: str, size: str) -> None:
    pfo.on_fill(
        bot_id=bot,
        trade_id=f"buy-{token}-{cid}",
        order_id=None,
        condition_id=cid,
        token_id=token,
        side="BUY",
        price=Decimal(price),
        size=Decimal(size),
        fee_usd=Decimal("0"),
        filled_at=datetime.now(UTC) - timedelta(days=2),
    )


def _gamma_closed(yes_price: str, no_price: str, yes_token: str, no_token: str, cid: str) -> list[dict]:
    # Populate both `id` (numeric) and `conditionId` (hex) so the helper
    # matches whichever field it queried.
    return [
        {
            "id": cid,
            "conditionId": cid,
            "closed": True,
            "outcomePrices": f'["{yes_price}", "{no_price}"]',
            "clobTokenIds": f'["{yes_token}", "{no_token}"]',
        }
    ]


def test_yes_winner_settles_at_one(pfo):
    _seed_market(datetime.now(UTC) - timedelta(hours=5), "c1", "yes1", "no1")
    _seed_buy(pfo, "bot_d", "yes1", "c1", "0.20", "100")  # cost basis 20
    client = _StubClient({"c1": _gamma_closed("1.0", "0.0", "yes1", "no1", "c1")})

    n = pfo.reconcile_paper_resolutions("bot_d", http_client=client)

    assert n == 1
    sf = get_session_factory()
    with sf() as s:
        pos = s.scalars(select(Position).where(Position.bot_id == "bot_d")).one()
        assert pos.status == "CLOSED"
        assert pos.size == Decimal("0")
    # Realised P&L = sell_price(1.0) * 100 - cost_basis(20) = 80
    assert pfo.get_realised_pnl("bot_d") == Decimal("80")


def test_yes_loser_settles_at_zero(pfo):
    _seed_market(datetime.now(UTC) - timedelta(hours=5), "c2", "yes2", "no2")
    _seed_buy(pfo, "bot_d", "yes2", "c2", "0.20", "100")
    client = _StubClient({"c2": _gamma_closed("0.0", "1.0", "yes2", "no2", "c2")})

    n = pfo.reconcile_paper_resolutions("bot_d", http_client=client)

    assert n == 1
    # Realised = 0 * 100 - 20 = -20
    assert pfo.get_realised_pnl("bot_d") == Decimal("-20")


def test_no_token_settles_at_one(pfo):
    _seed_market(datetime.now(UTC) - timedelta(hours=5), "c3", "yes3", "no3")
    _seed_buy(pfo, "bot_d", "no3", "c3", "0.30", "50")  # cost 15
    client = _StubClient({"c3": _gamma_closed("0.0", "1.0", "yes3", "no3", "c3")})

    n = pfo.reconcile_paper_resolutions("bot_d", http_client=client)

    assert n == 1
    assert pfo.get_realised_pnl("bot_d") == Decimal("35")  # 1.0 * 50 - 15


def test_future_end_date_is_skipped(pfo):
    _seed_market(datetime.now(UTC) + timedelta(days=3), "c4", "yes4", "no4")
    _seed_buy(pfo, "bot_d", "yes4", "c4", "0.10", "10")
    client = _StubClient({})  # would blow up if called

    n = pfo.reconcile_paper_resolutions("bot_d", http_client=client)

    assert n == 0
    assert client.calls == []  # short-circuited before Gamma


def test_unresolved_on_gamma_leaves_position_open(pfo):
    _seed_market(datetime.now(UTC) - timedelta(hours=5), "c5", "yes5", "no5")
    _seed_buy(pfo, "bot_d", "yes5", "c5", "0.10", "10")
    # Gamma returns an open market (not closed yet — e.g. UMA dispute window).
    client = _StubClient({
        "c5": [{"conditionId": "c5", "closed": False, "outcomePrices": '["0.5","0.5"]'}]
    })

    n = pfo.reconcile_paper_resolutions("bot_d", http_client=client)

    assert n == 0
    sf = get_session_factory()
    with sf() as s:
        pos = s.scalars(select(Position).where(Position.bot_id == "bot_d")).one()
        assert pos.status == "OPEN"


def test_idempotent_resettle(pfo):
    _seed_market(datetime.now(UTC) - timedelta(hours=5), "c6", "yes6", "no6")
    _seed_buy(pfo, "bot_d", "yes6", "c6", "0.20", "100")
    client = _StubClient({"c6": _gamma_closed("1.0", "0.0", "yes6", "no6", "c6")})

    pfo.reconcile_paper_resolutions("bot_d", http_client=client)
    # Re-run — must be a no-op (no new Position to settle).
    n2 = pfo.reconcile_paper_resolutions("bot_d", http_client=client)

    assert n2 == 0
    sf = get_session_factory()
    with sf() as s:
        # Exactly one SELL Trade with the paper-resolve prefix.
        sells = list(
            s.scalars(select(Trade).where(Trade.bot_id == "bot_d", Trade.side == "SELL"))
        )
        assert len(sells) == 1
        assert sells[0].trade_id.startswith("paper-resolve-")


def test_orphan_position_no_market_row_emits_event(pfo):
    # No _seed_market: position has a condition_id that never hit the markets table.
    _seed_buy(pfo, "bot_d", "orphan_tok", "c_orphan", "0.10", "10")
    # Gamma returns nothing (empty list).
    client = _StubClient({"c_orphan": []})

    n = pfo.reconcile_paper_resolutions("bot_d", http_client=client)

    assert n == 0
    sf = get_session_factory()
    with sf() as s:
        pos = s.scalars(select(Position).where(Position.bot_id == "bot_d")).one()
        assert pos.status == "OPEN"  # Left alone — upstream ingest bug.
        ev = s.scalars(
            select(Event).where(Event.event_type == "portfolio.paper_resolve.orphan")
        ).first()
        assert ev is not None
        assert ev.payload["condition_id"] == "c_orphan"


def test_settlement_emits_audit_event(pfo):
    _seed_market(datetime.now(UTC) - timedelta(hours=5), "c7", "yes7", "no7")
    _seed_buy(pfo, "bot_d", "yes7", "c7", "0.20", "100")
    client = _StubClient({"c7": _gamma_closed("1.0", "0.0", "yes7", "no7", "c7")})

    pfo.reconcile_paper_resolutions("bot_d", http_client=client)

    sf = get_session_factory()
    with sf() as s:
        ev = s.scalars(
            select(Event).where(Event.event_type == "portfolio.paper_resolve")
        ).one()
        assert ev.payload["settle_price"] == "1.0"
        assert ev.payload["cost_basis_usd"] == "20.00000000"


def test_numeric_id_uses_id_param(pfo):
    """Bot D stores Gamma's numeric `id` in Position.condition_id. Helper
    must query with `id=...` rather than `condition_ids=...` (which expects
    a 0x-prefixed hex string)."""
    _seed_market(datetime.now(UTC) - timedelta(hours=5), "1996525", "yes_num", "no_num")
    _seed_buy(pfo, "bot_d", "yes_num", "1996525", "0.20", "100")

    class _ParamCapture(_StubClient):
        def __init__(self, payloads):
            super().__init__(payloads)
            self.param_names_seen: list[str] = []

        def get(self, url, params=None):
            params = params or {}
            self.param_names_seen.append(
                "condition_ids" if "condition_ids" in params else ("id" if "id" in params else "none")
            )
            return super().get(url, params)

    client = _ParamCapture({"1996525": _gamma_closed("1.0", "0.0", "yes_num", "no_num", "1996525")})
    n = pfo.reconcile_paper_resolutions("bot_d", http_client=client)

    assert n == 1
    assert client.param_names_seen == ["id"]  # numeric → id=


def test_hex_condition_id_uses_condition_ids_param(pfo):
    hex_cid = "0x" + "a" * 64
    _seed_market(datetime.now(UTC) - timedelta(hours=5), hex_cid, "yes_hex", "no_hex")
    _seed_buy(pfo, "bot_d", "yes_hex", hex_cid, "0.20", "100")

    class _ParamCapture(_StubClient):
        def __init__(self, payloads):
            super().__init__(payloads)
            self.param_names_seen: list[str] = []

        def get(self, url, params=None):
            params = params or {}
            self.param_names_seen.append(
                "condition_ids" if "condition_ids" in params else ("id" if "id" in params else "none")
            )
            return super().get(url, params)

    client = _ParamCapture({hex_cid: _gamma_closed("1.0", "0.0", "yes_hex", "no_hex", hex_cid)})
    n = pfo.reconcile_paper_resolutions("bot_d", http_client=client)

    assert n == 1
    assert client.param_names_seen == ["condition_ids"]


def test_gamma_network_failure_is_graceful(pfo):
    class _Blowup:
        def get(self, *_a, **_kw):
            raise RuntimeError("connection refused")

        def close(self):
            pass

    _seed_market(datetime.now(UTC) - timedelta(hours=5), "c8", "yes8", "no8")
    _seed_buy(pfo, "bot_d", "yes8", "c8", "0.20", "100")

    # Should swallow the network error and return 0, not raise.
    n = pfo.reconcile_paper_resolutions("bot_d", http_client=_Blowup())
    assert n == 0
