from scripts.polymarket_api_endpoint_probe import (
    CLOB_WS,
    ProbeResult,
    _render_text,
    run_probes,
)


class _Resp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = "{}"
        self.url = "https://example.test/path"

    def json(self):
        return self._payload


class _Client:
    def __init__(self, *args, **kwargs):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, url, params=None):
        self.calls.append((url, params or {}))
        if url.endswith("/markets/keyset"):
            return _Resp({"data": [], "next_cursor": ""})
        if url.endswith("/public-search"):
            assert "q" in (params or {})
            assert "term" not in (params or {})
            return _Resp({"events": [], "markets": []})
        if "/events/slug/" in url:
            return _Resp({"markets": []})
        if url.endswith("/tags"):
            return _Resp([])
        if url.endswith("/time"):
            return _Resp({"serverTime": 1})
        if url.endswith("/markets"):
            return _Resp([])
        raise AssertionError(f"unexpected URL {url}")


def test_public_probe_uses_q_search_and_skips_wallet_specific(monkeypatch):
    monkeypatch.setattr("scripts.polymarket_api_endpoint_probe.httpx.Client", _Client)

    results = run_probes()

    by_name = {r.name: r for r in results}
    assert by_name["gamma.public_search_q"].status == "ok"
    assert by_name["data.activity"].status == "skip"
    assert by_name["ws.market_url"].url == f"{CLOB_WS}/market"


def test_render_text_summarises_statuses():
    text = _render_text([
        ProbeResult("a", "u", "ok", 200, "fine"),
        ProbeResult("b", "u", "fail", 500, "bad"),
        ProbeResult("c", "u", "skip", detail="needs input"),
    ])

    assert "OK   a HTTP 200" in text
    assert "FAIL b HTTP 500" in text
    assert "Summary: ok=1 fail=1 skip=1" in text
