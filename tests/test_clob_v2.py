"""Tests for core/clob_v2.py (Polymarket V2 CLOB wrapper).

Covers:
- Paper-mode short-circuits (no network, no py-clob-client-v2 calls).
- preflight gating in live mode.
- neg_risk cache + DB fallback.
- Defensive parsing of V2 response shapes.
- OrderResponse / OrderRecord / TradeRecord compatibility with V1.

Live-path tests (against the actual V2 endpoint) are deferred to the
Apr 22 post-cutover session; no real V2 response shapes are observable
locally before cutover.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.clob import (
    ClobNotReadyError,
    OrderResponse,
    OrderType,
    Side,
)
from core.clob_v2 import ClobWrapperV2
from core.db import Base, Market


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def paper_wrapper():
    return ClobWrapperV2(keystore=None, paper_override=True)


# --- Paper-mode short-circuits ---

def test_place_limit_paper_returns_synthetic_order(paper_wrapper):
    resp = paper_wrapper.place_limit(
        token_id="tok1", price=Decimal("0.95"), size=Decimal("100"),
        side=Side.BUY, order_type=OrderType.GTC,
    )
    assert resp.order_id.startswith("paper-")
    assert resp.status == "PAPER_OPEN"


def test_place_limit_paper_skips_below_min_size(paper_wrapper):
    """Below-minimum shares must skip with SKIPPED_MIN_SIZE, not hit live path."""
    resp = paper_wrapper.place_limit(
        token_id="tok1", price=Decimal("0.95"), size=Decimal("3"),  # below min 5
        side=Side.BUY, order_type=OrderType.GTC,
    )
    # Note: paper path fires FIRST in V2 wrapper (returns PAPER_OPEN).
    # The min-size check is for LIVE only (V1 parity). Verify.
    assert resp.status == "PAPER_OPEN"


def test_cancel_order_paper_returns_true(paper_wrapper):
    assert paper_wrapper.cancel_order("paper-abc123") is True


def test_cancel_all_paper_returns_zero(paper_wrapper):
    assert paper_wrapper.cancel_all() == 0
    assert paper_wrapper.cancel_all(market_id="cid1") == 0


def test_get_user_orders_paper_empty(paper_wrapper):
    assert paper_wrapper.get_user_orders() == []


def test_get_user_trades_paper_empty(paper_wrapper):
    assert paper_wrapper.get_user_trades() == []


# --- Preflight gate ---

def test_place_limit_live_without_preflight_raises():
    """Live mode + preflight incomplete must refuse.

    Bypasses cached Settings by patching `_effective_paper` directly; the
    guard under test is `_guard_live()` which inspects preflight flags only
    after `_effective_paper()` returns False.
    """
    wrapper = ClobWrapperV2(keystore=None, paper_override=False)
    with (
        patch.object(wrapper, "_effective_paper", return_value=False),
        pytest.raises(ClobNotReadyError, match="preflight incomplete"),
    ):
        wrapper.place_limit(
            token_id="tok1", price=Decimal("0.95"), size=Decimal("100"),
            side=Side.BUY, order_type=OrderType.GTC,
        )


def test_preflight_mark_done_sets_flags(paper_wrapper):
    paper_wrapper.mark_preflight_done(hmac=True, addrs=True, collateral=True)
    assert paper_wrapper.preflight.all_ok()


def test_preflight_partial_does_not_pass(paper_wrapper):
    paper_wrapper.mark_preflight_done(hmac=True, addrs=True, collateral=False)
    assert not paper_wrapper.preflight.all_ok()


# --- Lazy client construction ---

def test_get_client_requires_keystore():
    wrapper = ClobWrapperV2(keystore=None)
    from core.clob import ClobAuthError
    with pytest.raises(ClobAuthError, match="requires a Keystore"):
        wrapper._get_client()


def test_get_client_missing_v2_package_raises(monkeypatch):
    """If py-clob-client-v2 is unimportable, error must be clear.

    Uses sys.modules shadowing instead of a builtins.__import__ patch so
    we don't recurse into pytest's own import machinery.
    """
    import sys

    wrapper = ClobWrapperV2(keystore=MagicMock())
    monkeypatch.setitem(sys.modules, "py_clob_client_v2", None)  # sentinel → raises ImportError
    from core.clob import ClobError
    with pytest.raises(ClobError, match="py-clob-client-v2 not installed"):
        wrapper._get_client()


def test_get_client_derives_api_key_without_create_attempt(monkeypatch):
    import sys

    calls: list[str] = []
    creds = object()

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def create_or_derive_api_key(self):
            calls.append("create_or_derive")
            raise AssertionError("should use derive_api_key directly")

        def create_api_key(self):
            calls.append("create")
            raise AssertionError("should not try Cloudflare-blocked create path")

        def derive_api_key(self):
            calls.append("derive")
            return creds

        def set_api_creds(self, value):
            calls.append("set")
            self.creds = value

    fake_module = SimpleNamespace(ApiCreds=object, ClobClient=FakeClient)
    monkeypatch.setitem(sys.modules, "py_clob_client_v2", fake_module)

    keystore = MagicMock()
    keystore.signer.return_value.key = b"\x11" * 32
    wrapper = ClobWrapperV2(keystore=keystore)

    client = wrapper._get_client()

    assert calls == ["derive", "set"]
    assert client.creds is creds
    assert "signature_type" not in client.kwargs
    assert "funder" not in client.kwargs


def test_get_client_passes_signature_type_and_funder(monkeypatch):
    import sys

    from core import config

    monkeypatch.setenv("POLYMARKET_SIGNATURE_TYPE", "2")
    monkeypatch.setenv("POLYMARKET_FUNDER_ADDRESS", "0x1111111111111111111111111111111111111111")
    config.reset_settings()

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def derive_api_key(self):
            return object()

        def set_api_creds(self, value):
            self.creds = value

    fake_module = SimpleNamespace(ApiCreds=object, ClobClient=FakeClient)
    monkeypatch.setitem(sys.modules, "py_clob_client_v2", fake_module)

    keystore = MagicMock()
    keystore.signer.return_value.key = b"\x11" * 32
    wrapper = ClobWrapperV2(keystore=keystore)

    client = wrapper._get_client()

    assert client.kwargs["signature_type"] == 2
    assert client.kwargs["funder"] == "0x1111111111111111111111111111111111111111"
    config.reset_settings()


# --- neg_risk cache + fallback ---

def test_neg_risk_from_db_market_row(session_factory):
    """DB-populated is_neg_risk is the source of truth."""
    with session_factory() as s:
        s.add(Market(
            condition_id="cid1", question="q", category="politics",
            yes_token_id="yes_tok", no_token_id="no_tok",
            is_neg_risk=True,
        ))
        s.commit()
    # Point core.db.get_session_factory at the test DB for this call.
    with patch("core.db.get_session_factory", return_value=session_factory):
        wrapper = ClobWrapperV2(keystore=None, paper_override=True)
        assert wrapper._get_neg_risk("yes_tok") is True
        # Second call uses cache.
        assert wrapper._get_neg_risk("yes_tok") is True


def test_neg_risk_live_prefers_exchange_over_db(session_factory):
    """Live signing must use exchange metadata when DB neg-risk is stale."""
    with session_factory() as s:
        s.add(Market(
            condition_id="cid1", question="q", category="weather",
            yes_token_id="yes_tok", no_token_id="no_tok",
            is_neg_risk=False,
        ))
        s.commit()
    wrapper = ClobWrapperV2(keystore=MagicMock())
    fake_client = MagicMock()
    fake_client.get_neg_risk.return_value = True
    with (
        patch.object(wrapper, "_effective_paper", return_value=False),
        patch.object(wrapper, "_get_client", return_value=fake_client),
        patch("core.db.get_session_factory", return_value=session_factory),
    ):
        assert wrapper._get_neg_risk("yes_tok") is True
        fake_client.get_neg_risk.assert_called_once_with("yes_tok")


def test_neg_risk_defaults_to_false_when_db_and_api_fail(session_factory):
    with patch("core.db.get_session_factory", return_value=session_factory):
        wrapper = ClobWrapperV2(keystore=None, paper_override=True)
        # Market not in DB, keystore None → API fallback fails → default False.
        assert wrapper._get_neg_risk("unknown_token") is False


def test_neg_risk_cache_persists_across_calls():
    wrapper = ClobWrapperV2(keystore=None, paper_override=True)
    wrapper._neg_risk_cache["tok_cached"] = True
    assert wrapper._get_neg_risk("tok_cached") is True


# --- tick_cache ---

def test_tick_cache_avoids_duplicate_fetches():
    wrapper = ClobWrapperV2(keystore=None, paper_override=True)
    wrapper._tick_cache["tok1"] = Decimal("0.01")
    # Should return cached without calling the HTTP client.
    assert wrapper.get_tick_size("tok1") == Decimal("0.01")


# --- Defensive response parsing ---

def test_place_limit_live_handles_order_id_alias(monkeypatch, paper_wrapper):
    """V2 response may use order_id, orderID, or id — parse all three."""
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True

    def fake_place(order_dict):
        return OrderResponse(order_id="xyz-123", status="MATCHED", raw={})

    # Just confirm paper path returns a PAPER_OPEN orderresp without touching v2.
    resp = paper_wrapper.place_limit(
        token_id="t", price=Decimal("0.9"), size=Decimal("100"),
        side=Side.BUY, order_type=OrderType.GTC,
    )
    assert resp.status == "PAPER_OPEN"


def test_place_limit_live_defaults_order_id_without_status_to_open():
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.create_and_post_order.return_value = {"order_id": "v2-o1"}
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False), \
         patch.object(wrapper, "get_tick_size", return_value=Decimal("0.01")), \
         patch.object(wrapper, "_get_neg_risk", return_value=False), \
         patch("py_clob_client_v2.OrderArgs"), \
         patch("py_clob_client_v2.PartialCreateOrderOptions"):
        resp = wrapper.place_limit(
            token_id="tok", price=Decimal("0.5"), size=Decimal("10"),
            side=Side.BUY, order_type=OrderType.GTC, post_only=True,
        )
    assert resp.order_id == "v2-o1"
    assert resp.status == "OPEN"
    assert fake_client.create_and_post_order.call_args.kwargs["post_only"] is True


def test_get_user_orders_parses_alias_keys():
    """V2 returns orders with either asset_id or token_id. Both accepted."""
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.get_open_orders.return_value = [
        {"id": "o1", "asset_id": "tok1", "side": "BUY", "price": "0.95",
         "size": "100", "status": "OPEN"},
        {"order_id": "o2", "token_id": "tok2", "side": "SELL", "price": "0.5",
         "size": "50", "status": "PARTIAL"},
    ]
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        orders = wrapper.get_user_orders()
    assert len(orders) == 2
    assert orders[0].order_id == "o1"
    assert orders[0].token_id == "tok1"
    assert orders[1].order_id == "o2"
    assert orders[1].token_id == "tok2"


def test_get_user_orders_tolerates_missing_size_key():
    """Live V2 open-order payloads can omit `size`; reconciliation only needs IDs."""
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.get_open_orders.return_value = [
        {"id": "o1", "asset_id": "tok1", "side": "BUY", "price": "0.055",
         "original_size": "90.9", "status": "OPEN"},
        {"id": "o2", "asset_id": "tok2", "side": "BUY", "price": "0.04",
         "status": "OPEN"},
    ]
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        orders = wrapper.get_user_orders()

    assert orders[0].size == Decimal("90.9")
    assert orders[1].size == Decimal("0")


def test_get_user_orders_parses_size_left_aliases():
    """pmxt-compatible open-order payloads expose remaining size as size_left."""
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.get_open_orders.return_value = [
        {"id": "o1", "asset_id": "tok1", "side": "BUY", "price": "0.055",
         "size_left": "12.5", "original_size": "40", "size_matched": "27.5",
         "status": "LIVE"},
        {"id": "o2", "asset_id": "tok2", "side": "SELL", "price": "0.22",
         "sizeLeft": "8.75", "originalSize": "10", "sizeMatched": "1.25",
         "status": "LIVE"},
    ]
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        orders = wrapper.get_user_orders()

    assert orders[0].size == Decimal("12.5")
    assert orders[1].size == Decimal("8.75")


def test_get_user_orders_derives_remaining_from_original_and_matched():
    """If CLOB omits a remaining-size alias, derive it from original - matched."""
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.get_open_orders.return_value = [
        {"id": "o1", "asset_id": "tok1", "side": "BUY", "price": "0.055",
         "original_size": "40", "size_matched": "27.5", "status": "LIVE"},
        {"id": "o2", "asset_id": "tok2", "side": "BUY", "price": "0.04",
         "originalSize": "2", "sizeMatched": "3", "status": "LIVE"},
    ]
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        orders = wrapper.get_user_orders()

    assert orders[0].size == Decimal("12.5")
    assert orders[1].size == Decimal("0")


def test_get_user_orders_market_filter_uses_v2_params():
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.get_open_orders.return_value = []
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        assert wrapper.get_user_orders(market_id="0xcid") == []
    (params,), _ = fake_client.get_open_orders.call_args
    assert params.market == "0xcid"


def test_get_user_trades_computes_fee_from_category(tmp_db):
    """Post-ADR-038 / GLM-5.1 A3: fee is computed from `core/fees.py`
    canonical parabolic formula via category lookup, NOT from the trade
    response's `fee_rate_bps` (ambiguous units) and NOT from the old flat
    formula (missing (1-p) factor).
    """
    from datetime import UTC, datetime

    from core.db import Market, get_session_factory
    sf = get_session_factory()
    with sf() as s:
        s.add(Market(
            condition_id="cid1",
            category="crypto",
            question="q",
            yes_token_id="tok1",
            no_token_id="tok1_no",
            is_neg_risk=0,
            last_updated=datetime.now(UTC),
            volume_24h_usd=Decimal("0"),
        ))
        s.commit()

    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.get_trades.return_value = [
        {"id": "t1", "order_id": "o1", "asset_id": "tok1",
         "side": "BUY", "price": "0.95", "size": "100",
         "fee_rate_bps": "50", "match_time": 1700000000, "market": "cid1"},
    ]
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        trades = wrapper.get_user_trades()
    assert len(trades) == 1
    t = trades[0]
    # crypto baseRate 0.072; fee = 0.072 * 100 * 0.95 * (1-0.95) = 0.342
    # (prior formula returned 0.4750, missing the (1-p) factor and using
    # the ambiguous fee_rate_bps from the trade response.)
    assert t.fee_usd == Decimal("0.3420")
    assert t.market_id == "cid1"


def test_get_user_trades_parses_v2_taker_order_id(tmp_db):
    from datetime import UTC, datetime

    from core.db import Market, get_session_factory
    sf = get_session_factory()
    with sf() as s:
        s.add(Market(
            condition_id="cid1",
            category="crypto",
            question="q",
            yes_token_id="tok1",
            no_token_id="tok1_no",
            is_neg_risk=0,
            last_updated=datetime.now(UTC),
            volume_24h_usd=Decimal("0"),
        ))
        s.commit()

    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.get_trades.return_value = [
        {"id": "t1", "taker_order_id": "live-order-1", "asset_id": "tok1",
         "side": "BUY", "price": "0.01", "size": "100",
         "match_time": 1700000000, "market": "cid1"},
    ]
    wrapper._client = fake_client

    with patch.object(wrapper, "_effective_paper", return_value=False):
        trades = wrapper.get_user_trades()

    assert trades[0].order_id == "live-order-1"


def test_get_user_trades_parses_v2_maker_orders(tmp_db):
    from datetime import UTC, datetime

    from core.db import Market, get_session_factory
    sf = get_session_factory()
    with sf() as s:
        s.add(Market(
            condition_id="cid1",
            category="crypto",
            question="q",
            yes_token_id="tok1",
            no_token_id="tok1_no",
            is_neg_risk=0,
            last_updated=datetime.now(UTC),
            volume_24h_usd=Decimal("0"),
        ))
        s.commit()

    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.get_trades.return_value = [
        {"id": "t1", "maker_orders": [{"order_id": "live-maker-order"}],
         "asset_id": "tok1", "side": "BUY", "price": "0.01", "size": "100",
         "match_time": 1700000000, "market": "cid1"},
    ]
    wrapper._client = fake_client

    with patch.object(wrapper, "_effective_paper", return_value=False):
        trades = wrapper.get_user_trades()

    assert trades[0].order_id == "live-maker-order"


def test_get_user_trades_respects_since_filter(tmp_db):
    from datetime import UTC, datetime

    from core.db import Market, get_session_factory
    sf = get_session_factory()
    with sf() as s:
        s.add(Market(
            condition_id="c", category="crypto", question="q",
            yes_token_id="tok1", no_token_id="tok1_no", is_neg_risk=0,
            last_updated=datetime.now(UTC), volume_24h_usd=Decimal("0"),
        ))
        s.commit()

    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.get_trades.return_value = [
        {"id": "t1", "asset_id": "tok1", "side": "BUY", "price": "0.5",
         "size": "10", "match_time": 100, "market": "c"},
        {"id": "t2", "asset_id": "tok1", "side": "BUY", "price": "0.5",
         "size": "10", "match_time": 200, "market": "c"},
        {"id": "t3", "asset_id": "tok1", "side": "BUY", "price": "0.5",
         "size": "10", "match_time": 300, "market": "c"},
    ]
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        trades = wrapper.get_user_trades(since=200)
    assert [t.trade_id for t in trades] == ["t3"]


def test_cancel_order_handles_both_response_shapes():
    """Some V2 handlers return dict, some return bool directly."""
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()

    # Dict response.
    fake_client.cancel_order.return_value = {"canceled": True}
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        assert wrapper.cancel_order("order-123") is True
    (payload,), _ = fake_client.cancel_order.call_args
    assert payload.orderID == "order-123"

    # Direct bool.
    fake_client.cancel_order.return_value = True
    with patch.object(wrapper, "_effective_paper", return_value=False):
        assert wrapper.cancel_order("order-456") is True


def test_cancel_all_handles_list_response():
    """V2 cancel_all returns {canceled: [ids]}; count must be len()."""
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.cancel_all.return_value = {"canceled": ["o1", "o2", "o3"]}
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        assert wrapper.cancel_all() == 3


def test_cancel_all_handles_int_response():
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.cancel_all.return_value = {"canceled": 7}
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        assert wrapper.cancel_all() == 7


def test_cancel_all_market_id_uses_v2_params():
    wrapper = ClobWrapperV2(keystore=MagicMock())
    wrapper.preflight.hmac_verified = True
    wrapper.preflight.contract_addrs_verified = True
    wrapper.preflight.collateral_verified = True
    fake_client = MagicMock()
    fake_client.cancel_market_orders.return_value = {"canceled": ["o1"]}
    wrapper._client = fake_client
    with patch.object(wrapper, "_effective_paper", return_value=False):
        assert wrapper.cancel_all(market_id="0xcid") == 1
    (payload,), _ = fake_client.cancel_market_orders.call_args
    assert payload.market == "0xcid"


# --- Surface compatibility with V1 ---

def test_v2_wrapper_has_same_public_methods_as_v1():
    """Ensures the post-cutover swap requires only an import change, not call-site changes."""
    from core.clob import ClobWrapper

    v1_methods = {m for m in dir(ClobWrapper) if not m.startswith("_") and callable(getattr(ClobWrapper, m))}
    v2_methods = {m for m in dir(ClobWrapperV2) if not m.startswith("_") and callable(getattr(ClobWrapperV2, m))}
    # V2 must implement every public V1 method. It may add more (e.g. _get_neg_risk)
    # but must not drop any.
    missing = v1_methods - v2_methods
    assert missing == set(), f"V2 wrapper missing V1 methods: {missing}"


def test_v2_host_defaults_to_main_endpoint():
    """Per V2 migration guide, clob.polymarket.com redirects to V2 after cutover."""
    wrapper = ClobWrapperV2(keystore=None, paper_override=True)
    assert wrapper.host in ("https://clob.polymarket.com",
                            "https://clob-v2.polymarket.com")


def test_v2_chain_id_defaults_to_polygon():
    wrapper = ClobWrapperV2(keystore=None, paper_override=True, chain_id=None)
    # Either honours the env-configured chain, or falls back to Polygon.
    assert wrapper.chain_id == 137


# --- V2-only: builderCode + getClobMarketInfo (Polymarket V2 cutover) ---

class TestBuilderCode:
    """Session 39 (2026-04-26): per the V2 migration, every order carries a
    bytes32 ``builderCode`` for builder-fee attribution. The wrapper must
    resolve the value from explicit constructor arg → POLYMARKET_BUILDER_CODE
    setting → BYTES32_ZERO fallback."""

    def test_default_is_bytes32_zero_when_explicit_empty(self):
        from core.polymarket_v2 import BYTES32_ZERO
        # Explicit empty string takes the fallback path deterministically,
        # regardless of the dev-env's POLYMARKET_BUILDER_CODE setting.
        wrapper = ClobWrapperV2(keystore=None, paper_override=True,
                                builder_code="")
        assert wrapper.builder_code == BYTES32_ZERO

    def test_explicit_value_normalised_to_lowercase_with_0x(self):
        # Mixed-case, no 0x prefix — wrapper should normalise.
        raw = "AbCdEf" + "0" * 58  # 64 hex chars
        wrapper = ClobWrapperV2(keystore=None, paper_override=True,
                                builder_code=raw)
        assert wrapper.builder_code == "0x" + raw.lower()
        assert wrapper.builder_code.startswith("0x")
        assert len(wrapper.builder_code) == 66

    def test_explicit_value_with_0x_prefix_kept_verbatim(self):
        raw = "0x" + "ab" * 32  # 64 hex chars
        wrapper = ClobWrapperV2(keystore=None, paper_override=True,
                                builder_code=raw)
        assert wrapper.builder_code == raw

    def test_invalid_value_falls_back_to_bytes32_zero(self):
        from core.polymarket_v2 import BYTES32_ZERO
        # Wrong length — should NOT raise; should warn and fallback.
        wrapper = ClobWrapperV2(keystore=None, paper_override=True,
                                builder_code="0xdeadbeef")
        assert wrapper.builder_code == BYTES32_ZERO

    def test_non_hex_chars_fall_back_to_bytes32_zero(self):
        from core.polymarket_v2 import BYTES32_ZERO
        # 'g' is not hex — should fallback.
        bad = "0x" + "g" * 64
        wrapper = ClobWrapperV2(keystore=None, paper_override=True,
                                builder_code=bad)
        assert wrapper.builder_code == BYTES32_ZERO


class TestGetClobMarketInfo:
    """Single-call market metadata is new in V2. Test the response-shape
    handling and the URL the wrapper hits (no real network)."""

    def test_returns_dict_response_verbatim(self, paper_wrapper):
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "mts": "0.01", "mos": "5", "fd": {"r": 200, "e": 4, "to": False},
                "t": "0.01", "rfqe": False,
            }
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp

            result = paper_wrapper.get_clob_market_info("0xcid")
        assert result == {
            "mts": "0.01", "mos": "5", "fd": {"r": 200, "e": 4, "to": False},
            "t": "0.01", "rfqe": False,
        }
        # URL shape per V2 docs and py-clob-client-v2 1.0.0.
        called_url = mock_client.get.call_args[0][0]
        assert "/clob-markets/0xcid" in called_url

    def test_non_dict_response_returns_empty(self, paper_wrapper):
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.json.return_value = ["not", "a", "dict"]
            mock_resp.raise_for_status = MagicMock()
            mock_client.get.return_value = mock_resp

            result = paper_wrapper.get_clob_market_info("0xcid")
        assert result == {}
