"""Tests for core/fleet.py — cross-bot pre-trade aggregate cap."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from core.db import Order, Position, get_session_factory
from core.fleet import (
    check_fleet_exposure,
    snapshot_fleet_exposure,
)


def _add_open_position(bot_id: str, cost_basis_usd: Decimal, cid: str):
    with get_session_factory()() as s:
        p = Position(
            bot_id=bot_id,
            condition_id=cid,
            token_id=f"tok_{cid}",
            side="YES",
            size=Decimal("10"),
            avg_price=Decimal("0.50"),
            cost_basis_usd=cost_basis_usd,
            status="OPEN",
            opened_at=datetime.now(UTC),
        )
        s.add(p)
        s.commit()


def _add_open_order(bot_id: str, price: Decimal, size: Decimal, oid: str):
    with get_session_factory()() as s:
        o = Order(
            order_id=oid,
            bot_id=bot_id,
            condition_id="cid_x",
            token_id="tok_x",
            side="BUY",
            price=price,
            size=size,
            status="OPEN",
            order_type="GTC",
            placed_at=datetime.now(UTC),
            last_updated=datetime.now(UTC),
        )
        s.add(o)
        s.commit()


class TestSnapshotFleetExposure:
    def test_empty_db(self, tmp_db, monkeypatch):
        monkeypatch.setenv("FLEET_WALLET_USD", "500")
        monkeypatch.setenv("FLEET_DEPLOYABLE_FRAC", "0.80")
        # Force re-import to pick up env.
        import importlib
        import core.fleet as fleet
        importlib.reload(fleet)
        snap = fleet.snapshot_fleet_exposure()
        assert snap.positions_usd == Decimal("0")
        assert snap.open_orders_usd == Decimal("0")
        assert snap.total_usd == Decimal("0")
        assert snap.wallet_usd == Decimal("500")
        assert snap.deployable_cap_usd == Decimal("400.00")

    def test_sums_positions_and_orders_across_bots(self, tmp_db, monkeypatch):
        monkeypatch.setenv("FLEET_WALLET_USD", "1000")
        monkeypatch.setenv("FLEET_DEPLOYABLE_FRAC", "0.80")
        import importlib
        import core.fleet as fleet
        importlib.reload(fleet)
        _add_open_position("bot_a", Decimal("100"), "cid_a")
        _add_open_position("bot_b", Decimal("200"), "cid_b")
        _add_open_order("bot_e", Decimal("0.50"), Decimal("60"), "paper-1")  # 30 USD
        snap = fleet.snapshot_fleet_exposure()
        assert snap.positions_usd == Decimal("300")
        assert snap.open_orders_usd == Decimal("30.00")
        assert snap.total_usd == Decimal("330.00")
        assert snap.deployable_cap_usd == Decimal("800.00")


class TestCheckFleetExposure:
    def test_allow_when_under_cap(self, tmp_db, monkeypatch):
        monkeypatch.setenv("FLEET_WALLET_USD", "500")
        monkeypatch.setenv("FLEET_DEPLOYABLE_FRAC", "0.80")
        import importlib
        import core.fleet as fleet
        importlib.reload(fleet)
        _add_open_position("bot_b", Decimal("100"), "cid_b")
        r = fleet.check_fleet_exposure("bot_d", Decimal("50"))
        assert r.ok is True
        assert r.reason == "fleet_ok"
        assert r.projected_total_usd == Decimal("150")
        assert r.deployable_cap_usd == Decimal("400.00")

    def test_block_when_over_cap(self, tmp_db, monkeypatch):
        monkeypatch.setenv("FLEET_WALLET_USD", "500")
        monkeypatch.setenv("FLEET_DEPLOYABLE_FRAC", "0.80")
        import importlib
        import core.fleet as fleet
        importlib.reload(fleet)
        _add_open_position("bot_b", Decimal("350"), "cid_b")
        r = fleet.check_fleet_exposure("bot_d", Decimal("100"))
        assert r.ok is False
        assert r.reason == "fleet_cap_breach"

    def test_allow_when_cap_nonpositive(self, tmp_db, monkeypatch):
        monkeypatch.setenv("FLEET_WALLET_USD", "0")
        monkeypatch.setenv("FLEET_DEPLOYABLE_FRAC", "0.80")
        import importlib
        import core.fleet as fleet
        importlib.reload(fleet)
        r = fleet.check_fleet_exposure("bot_a", Decimal("50"))
        # Misconfig should not wedge trading.
        assert r.ok is True
        assert r.reason == "fleet_cap_nonpositive"

    def test_live_blocks_when_cap_nonpositive(self, tmp_db, monkeypatch):
        monkeypatch.setenv("POLYMARKET_ENV", "live")
        monkeypatch.setenv("BOT_D_ENV", "live")
        monkeypatch.setenv("FLEET_WALLET_USD", "0")
        monkeypatch.setenv("FLEET_DEPLOYABLE_FRAC", "0.80")
        import importlib
        from core import config
        config.reset_settings()
        import core.fleet as fleet
        importlib.reload(fleet)
        r = fleet.check_fleet_exposure("bot_d_live_probe", Decimal("50"))
        assert r.ok is False
        assert r.reason == "fleet_cap_nonpositive"

    def test_live_blocks_on_snapshot_failure(self, tmp_db, monkeypatch):
        monkeypatch.setenv("POLYMARKET_ENV", "live")
        monkeypatch.setenv("BOT_D_ENV", "live")
        monkeypatch.setenv("FLEET_WALLET_USD", "500")
        import importlib
        from core import config
        config.reset_settings()
        import core.fleet as fleet
        importlib.reload(fleet)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(fleet, "snapshot_fleet_exposure", _boom)
        r = fleet.check_fleet_exposure("bot_d_live_probe", Decimal("50"))
        assert r.ok is False
        assert r.reason == "fleet_snapshot_failed"

    def test_live_mode_uses_registry_status_not_shared_bot_env(self, tmp_db, monkeypatch):
        monkeypatch.setenv("POLYMARKET_ENV", "live")
        monkeypatch.setenv("BOT_D_ENV", "live")
        monkeypatch.setenv("FLEET_WALLET_USD", "250")
        monkeypatch.setenv("FLEET_DEPLOYABLE_FRAC", "0.80")
        import importlib
        from core import config
        config.reset_settings()
        import core.fleet as fleet
        importlib.reload(fleet)

        _add_open_position("bot_d", Decimal("500"), "paper_weather")
        _add_open_position("bot_d_live_probe", Decimal("100"), "live_weather")

        live_snap = fleet.snapshot_fleet_exposure(mode="live")
        assert live_snap.positions_usd == Decimal("100")

        result = fleet.check_fleet_exposure("bot_d_live_probe", Decimal("50"))
        assert result.ok is True
        assert result.projected_total_usd == Decimal("150")

    def test_boundary_exact_equal_allowed(self, tmp_db, monkeypatch):
        monkeypatch.setenv("FLEET_WALLET_USD", "500")
        monkeypatch.setenv("FLEET_DEPLOYABLE_FRAC", "0.80")
        import importlib
        import core.fleet as fleet
        importlib.reload(fleet)
        _add_open_position("bot_b", Decimal("300"), "cid_b")
        # Intended 100 brings total to 400 == cap; allowed.
        r = fleet.check_fleet_exposure("bot_d", Decimal("100"))
        assert r.ok is True
        # Intended 101 would exceed; blocked.
        r2 = fleet.check_fleet_exposure("bot_d", Decimal("101"))
        assert r2.ok is False
