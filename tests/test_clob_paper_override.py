"""Tests for ClobWrapper.paper_override — Bot C can paper while global is live."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from core.clob import ClobWrapper, OrderType, Side


@pytest.fixture
def live_settings(monkeypatch):
    """Force get_settings().is_live() to return True without touching .env."""
    from core.config import RunMode, get_settings

    s = get_settings()
    monkeypatch.setattr(s, "polymarket_env", RunMode.LIVE)
    yield s


def test_paper_override_forces_paper_fill_even_when_global_live(live_settings):
    assert live_settings.is_live() is True
    clob = ClobWrapper(keystore=None, paper_override=True)
    resp = clob.place_limit(
        token_id="t1",
        price=Decimal("0.5"),
        size=Decimal("20"),
        side=Side.BUY,
        order_type=OrderType.GTC,
    )
    assert resp.order_id.startswith("paper-")
    assert resp.status == "PAPER_OPEN"


def test_paper_override_false_respects_global_live(live_settings):
    assert live_settings.is_live() is True
    clob = ClobWrapper(keystore=None, paper_override=False)
    # preflight NOT set → live path blocked at _guard_live before network call
    from core.clob import ClobNotReadyError

    with pytest.raises(ClobNotReadyError):
        clob.place_limit(
            token_id="t1",
            price=Decimal("0.5"),
            size=Decimal("20"),
            side=Side.BUY,
            order_type=OrderType.GTC,
        )


def test_paper_override_cancel_short_circuits(live_settings):
    clob = ClobWrapper(keystore=None, paper_override=True)
    # Any cancel in effective-paper mode is a no-op returning True.
    assert clob.cancel_order("paper-deadbeef") is True
    assert clob.cancel_all() == 0


def test_default_constructor_unchanged():
    """Without paper_override, behaviour is identical to the pre-flag constructor."""
    clob = ClobWrapper(keystore=None)
    assert clob.paper_override is False
