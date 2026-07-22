"""Preflight check regression tests (OQ-006/007/008)."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from scripts.preflight_check import (
    check_addresses,
    check_collateral_live,
    check_hmac,
    main,
)


def test_hmac_check_passes():
    ok, msg = check_hmac()
    assert ok, msg


def test_addresses_check_passes():
    ok, msg = check_addresses()
    assert ok, msg


def test_collateral_static_passes():
    ok, msg = check_collateral_live(do_fetch=False)
    assert ok
    assert "0x2791bca1f2de4661ed88a30c99a7a9449aa84174" in msg.lower()


class _Resp:
    def __init__(self, status: int, payload=None):
        self.status_code = status
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)

    def json(self):
        return self._payload


class _Client:
    def __init__(self, resp):
        self._resp = resp

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, *a, **kw):
        return self._resp


def test_collateral_live_passes_on_markets_probe():
    """Live probe hits /markets and accepts a list payload."""
    payload = [{"condition_id": "0xabc123def4", "question": "t"}]
    with patch("httpx.Client", return_value=_Client(_Resp(200, payload))):
        ok, msg = check_collateral_live(do_fetch=True)
    assert ok, msg
    assert "reachable" in msg


def test_collateral_live_passes_on_wrapped_payload():
    payload = {"data": [{"condition_id": "0xabc123def4"}]}
    with patch("httpx.Client", return_value=_Client(_Resp(200, payload))):
        ok, msg = check_collateral_live(do_fetch=True)
    assert ok, msg


def test_collateral_live_fails_on_empty_markets():
    with patch("httpx.Client", return_value=_Client(_Resp(200, {"data": []}))):
        ok, msg = check_collateral_live(do_fetch=True)
    assert not ok
    assert "schema unexpected" in msg


def test_collateral_live_fails_on_network_error():
    class _Boom:
        def __enter__(self):
            raise httpx.ConnectError("dead")

        def __exit__(self, *a):
            return False

    with patch("httpx.Client", return_value=_Boom()):
        ok, msg = check_collateral_live(do_fetch=True)
    assert not ok
    assert "probe failed" in msg


def test_main_commit_writes_event(tmp_db):
    """--commit writes a preflight.verified event and returns 0 on all-green."""
    from core.db import Event, get_session_factory

    payload = [{"condition_id": "0xabc123def4"}]
    with patch("httpx.Client", return_value=_Client(_Resp(200, payload))):
        rc = main(["--commit", "--live"])
    assert rc == 0

    Session = get_session_factory()
    with Session() as s:
        events = list(s.query(Event).all())
    kinds = [e.event_type for e in events]
    assert "preflight.verified" in kinds


def test_main_no_commit_is_readonly(tmp_db):
    from core.db import Event, get_session_factory

    rc = main([])
    assert rc == 0

    Session = get_session_factory()
    with Session() as s:
        events = list(s.query(Event).all())
    assert events == []


class TestV2Addresses:
    """V2 cutover-gate check — pure constant comparison against the
    canonical addresses transcribed from docs.polymarket.com/v2-migration."""

    def test_v2_addresses_match_canonical(self):
        from scripts.preflight_check import check_addresses_v2
        ok, msg = check_addresses_v2()
        assert ok, msg
        assert "match canonical" in msg

    def test_v2_address_drift_caught(self, monkeypatch):
        """If anyone alters core/polymarket_v2.CTF_EXCHANGE_V2 in the future,
        this check must fail loudly."""
        from scripts.preflight_check import check_addresses_v2
        from core import polymarket_v2 as v2
        monkeypatch.setattr(
            v2, "CTF_EXCHANGE_V2",
            "0x0000000000000000000000000000000000000000",
        )
        ok, msg = check_addresses_v2()
        assert not ok
        assert "V2 mainnet exchange" in msg

    def test_v1_check_returns_marker_when_sdk_uninstalled(self, monkeypatch):
        """Post-cutover py_clob_client is gone. The V1 check returns a
        structured marker that main() recognises."""
        from scripts import preflight_check as pf
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **kw):
            if name.startswith("py_clob_client"):
                raise ImportError("simulated post-cutover state")
            return real_import(name, *a, **kw)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        ok, msg = pf.check_addresses()
        assert not ok
        assert msg == "V1_SDK_UNINSTALLED"


class TestCutoverPhase:
    def test_is_post_cutover_returns_bool(self):
        from scripts.preflight_check import is_post_cutover
        # Today is 2026-04-27; cutover is 2026-04-28T11:00Z. The exact
        # phase depends on when this test runs, but the function must
        # return a bool either way.
        assert isinstance(is_post_cutover(), bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
