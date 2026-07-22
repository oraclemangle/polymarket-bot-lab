"""Ingestion tests — stub HTTP."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from core import config
from core.db import Book, Market, get_session_factory
from core.ingest import BookSnapshotter, Scraper, TradeStream


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, route: dict):
        self._route = route

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None):
        for key, payload in self._route.items():
            if key in url:
                return _FakeResp(payload)
        return _FakeResp([])


def test_scraper_upserts_markets(tmp_db, monkeypatch):
    markets = [
        {
            "conditionId": "0xaaa",
            "category": "politics",
            "question": "Will X?",
            "endDate": "2026-05-01T00:00:00Z",
            "volume24hr": 12345.67,
            "tokens": [
                {"token_id": "yes_a", "outcome": "Yes"},
                {"token_id": "no_a", "outcome": "No"},
            ],
        },
    ]
    monkeypatch.setattr(
        "httpx.Client",
        lambda *a, **k: _FakeClient({"/markets": markets}),
    )
    s = Scraper(page_size=500)
    count = s.run_once(max_pages=1)
    assert count == 1

    session_factory = get_session_factory()
    with session_factory() as sess:
        m = sess.get(Market, "0xaaa")
        assert m is not None
        assert m.category == "politics"
        assert m.yes_token_id == "yes_a"
        assert m.no_token_id == "no_a"
        # Politics baseRate 0.04 × 10000 = 400 (canonical scale per
        # ADR-038 / GLM-5.1 A8). Old value 40 was 10× off.
        assert m.fee_rate_bps == 400  # politics
        assert m.volume_24h_usd == Decimal("12345.67")


def test_scraper_updates_existing(tmp_db, monkeypatch):
    session_factory = get_session_factory()
    with session_factory() as sess:
        sess.add(
            Market(
                condition_id="0xbbb",
                category="other",
                question="old",
                fee_rate_bps=50,
                last_updated=datetime.now(UTC),
            )
        )
        sess.commit()

    markets = [{"conditionId": "0xbbb", "category": "geopolitics", "question": "new"}]
    monkeypatch.setattr(
        "httpx.Client",
        lambda *a, **k: _FakeClient({"/markets": markets}),
    )
    s = Scraper(page_size=500)
    s.run_once(max_pages=1)

    with session_factory() as sess:
        m = sess.get(Market, "0xbbb")
        assert m.category == "geopolitics"
        assert m.fee_rate_bps == 0
        assert m.question == "new"


def test_book_snapshotter(tmp_db, monkeypatch):
    session_factory = get_session_factory()
    with session_factory() as sess:
        sess.add(
            Market(
                condition_id="c1",
                category="geopolitics",
                question="?",
                fee_rate_bps=0,
                yes_token_id="yes_c1",
            )
        )
        sess.commit()

    payload = {"bids": [{"price": "0.04", "size": "100"}], "asks": [{"price": "0.06", "size": "50"}]}
    monkeypatch.setattr(
        "httpx.Client",
        lambda *a, **k: _FakeClient({"/book": payload}),
    )
    snap = BookSnapshotter()
    count = snap.run_once()
    assert count == 1

    with session_factory() as sess:
        books = list(sess.scalars(select(Book)))
        assert len(books) == 1
        assert books[0].bids == [["0.04", "100"]]
        assert books[0].asks == [["0.06", "50"]]


def test_ingest_constructors_re_read_settings_after_reset(tmp_db, monkeypatch):
    monkeypatch.setenv("POLYMARKET_GAMMA_HOST", "https://gamma.example")
    monkeypatch.setenv("POLYMARKET_HOST", "https://clob.example")
    monkeypatch.setenv("POLYMARKET_WSS_HOST", "wss://ws.example")
    config.reset_settings()

    scraper = Scraper()
    snapshotter = BookSnapshotter()
    stream = TradeStream(auth_payload={"auth": "ok"})

    assert scraper.host == "https://gamma.example"
    assert snapshotter.host == "https://clob.example"
    assert stream.host == "wss://ws.example"


# --- Category derivation from /events tags ---

def test_derive_category_priority():
    from core.ingest import _derive_category

    # Iran should be geopolitics even when Politics tag is also present
    assert _derive_category(["Politics", "Middle East", "Iran"]) == "geopolitics"
    # Plain politics
    assert _derive_category(["Politics", "US Election", "Elections"]) == "politics"
    # Economics wins over finance when both present
    assert _derive_category(["Finance", "Economy", "Fed Rates"]) == "economics"
    # Finance fallback
    assert _derive_category(["Finance", "Commodities"]) == "finance"
    # Unknown -> other
    assert _derive_category(["Hide From New", "Monthly"]) == "other"
    assert _derive_category([]) == "other"


def test_scraper_uses_event_tags_for_category(tmp_db, monkeypatch):
    """Scraper must join /events tags because /markets dropped `category`."""
    events = [
        {
            "id": "100",
            "tags": [{"label": "Politics"}, {"label": "Middle East"}, {"label": "Iran"}],
        },
        {
            "id": "200",
            "tags": [{"label": "Sports"}, {"label": "NBA"}],
        },
    ]
    markets = [
        {
            "conditionId": "0xgeo",
            "question": "Iran strike next month?",
            "events": [{"id": "100"}],
            "tokens": [
                {"token_id": "yes_g", "outcome": "Yes"},
                {"token_id": "no_g", "outcome": "No"},
            ],
        },
        {
            "conditionId": "0xnba",
            "question": "Lakers win tonight?",
            "events": [{"id": "200"}],
            "tokens": [
                {"token_id": "yes_n", "outcome": "Yes"},
                {"token_id": "no_n", "outcome": "No"},
            ],
        },
    ]
    monkeypatch.setattr(
        "httpx.Client",
        lambda *a, **k: _FakeClient({"/events": events, "/markets": markets}),
    )
    s = Scraper(page_size=500)
    count = s.run_once(max_pages=1)
    assert count == 2

    session_factory = get_session_factory()
    with session_factory() as sess:
        geo = sess.get(Market, "0xgeo")
        nba = sess.get(Market, "0xnba")
        assert geo.category == "geopolitics"
        assert nba.category == "sports"


def test_scraper_falls_back_to_other_when_events_fetch_fails(tmp_db, monkeypatch):
    """If /events is unreachable, ingest degrades gracefully, doesn't crash."""
    class _FailingEventsClient:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, params=None):
            if "/events" in url:
                raise RuntimeError("gamma events down")
            return _FakeResp([
                {
                    "conditionId": "0xaaa",
                    "question": "Q?",
                    "events": [{"id": "999"}],
                    "tokens": [{"token_id": "y", "outcome": "Yes"}, {"token_id": "n", "outcome": "No"}],
                }
            ])

    monkeypatch.setattr("httpx.Client", _FailingEventsClient)
    s = Scraper(page_size=500)
    count = s.run_once(max_pages=1)
    assert count == 1

    session_factory = get_session_factory()
    with session_factory() as sess:
        m = sess.get(Market, "0xaaa")
        assert m.category == "other"


def test_scraper_parses_json_encoded_token_ids(tmp_db, monkeypatch):
    """Gamma's current /markets returns clobTokenIds and outcomes as JSON strings."""
    markets = [
        {
            "conditionId": "0xjson",
            "question": "Will X?",
            "events": [{"id": "1"}],
            "clobTokenIds": '["11111", "22222"]',
            "outcomes": '["Yes", "No"]',
            "volume24hr": 1000,
        }
    ]
    monkeypatch.setattr(
        "httpx.Client",
        lambda *a, **k: _FakeClient({"/events": [], "/markets": markets}),
    )
    s = Scraper(page_size=500)
    count = s.run_once(max_pages=1)
    assert count == 1

    session_factory = get_session_factory()
    with session_factory() as sess:
        m = sess.get(Market, "0xjson")
        assert m.yes_token_id == "11111"
        assert m.no_token_id == "22222"


def test_scraper_positional_fallback_when_outcomes_missing(tmp_db, monkeypatch):
    markets = [
        {
            "conditionId": "0xpos",
            "question": "Q?",
            "events": [{"id": "1"}],
            "clobTokenIds": '["aaa", "bbb"]',
            # no outcomes field
        }
    ]
    monkeypatch.setattr(
        "httpx.Client",
        lambda *a, **k: _FakeClient({"/events": [], "/markets": markets}),
    )
    Scraper().run_once(max_pages=1)
    session_factory = get_session_factory()
    with session_factory() as sess:
        m = sess.get(Market, "0xpos")
        assert m.yes_token_id == "aaa"
        assert m.no_token_id == "bbb"


def test_scraper_stores_yes_price(tmp_db, monkeypatch):
    markets = [
        {
            "conditionId": "0xprice",
            "question": "Q?",
            "events": [{"id": "1"}],
            "clobTokenIds": '["aa","bb"]',
            "outcomes": '["Yes","No"]',
            "outcomePrices": '["0.04","0.96"]',
        }
    ]
    monkeypatch.setattr("httpx.Client", lambda *a, **k: _FakeClient({"/events": [], "/markets": markets}))
    Scraper().run_once(max_pages=1)
    with get_session_factory()() as s:
        m = s.get(Market, "0xprice")
        assert m.yes_price == Decimal("0.040000")


def test_book_snapshotter_bot_a_filter(tmp_db):
    from core.ingest import BookSnapshotter

    # Seed three markets: one matches, two don't.
    with get_session_factory()() as s:
        s.add(Market(
            condition_id="m1", category="politics", question="Q1",
            yes_token_id="y1", no_token_id="n1", is_neg_risk=0,
            volume_24h_usd=Decimal("10000"), yes_price=Decimal("0.04"),
        ))
        s.add(Market(  # too expensive
            condition_id="m2", category="politics", question="Q2",
            yes_token_id="y2", no_token_id="n2", is_neg_risk=0,
            volume_24h_usd=Decimal("10000"), yes_price=Decimal("0.50"),
        ))
        s.add(Market(  # wrong category
            condition_id="m3", category="sports", question="Q3",
            yes_token_id="y3", no_token_id="n3", is_neg_risk=0,
            volume_24h_usd=Decimal("10000"), yes_price=Decimal("0.03"),
        ))
        s.commit()

    targets = BookSnapshotter().tokens_for_bot_a(
        max_yes_price=Decimal("0.05"),
        min_volume_usd=Decimal("5000"),
        categories=["politics", "geopolitics"],
    )
    assert set(targets) == {"y1", "n1"}
