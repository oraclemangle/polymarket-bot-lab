"""Portfolio / PnL tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from core.clob import Side, TradeRecord
from core.db import Event, Order, Position, Trade, get_session_factory
from core.portfolio import Portfolio


@pytest.fixture
def pfo(tmp_db, monkeypatch):
    # Stub FX so tests don't hit the BoE network.
    from core import portfolio

    monkeypatch.setattr(portfolio, "get_usd_to_gbp_rate", lambda *_a, **_k: Decimal("0.80"))
    return Portfolio()


def _fill(pfo, bot, token, side, price, size, ts=None):
    ts = ts or datetime.now(UTC)
    pfo.on_fill(
        bot_id=bot,
        trade_id=f"t{ts.timestamp()}-{token}-{side}",
        order_id=None,
        condition_id=f"cond-{token}",
        token_id=token,
        side=side,
        price=Decimal(str(price)),
        size=Decimal(str(size)),
        fee_usd=Decimal("0"),
        filled_at=ts,
    )


def test_buy_creates_position(pfo):
    _fill(pfo, "bot_a", "tokX", "BUY", "0.04", "100")
    Session = get_session_factory()
    with Session() as s:
        pos = s.scalars(
            select(Position).where(Position.bot_id == "bot_a", Position.status == "OPEN")
        ).one()
        assert pos.size == Decimal("100")
        assert pos.avg_price == Decimal("0.04")


def test_multiple_buys_weighted_avg(pfo):
    _fill(pfo, "bot_a", "tokX", "BUY", "0.04", "100")
    _fill(pfo, "bot_a", "tokX", "BUY", "0.06", "100")
    Session = get_session_factory()
    with Session() as s:
        pos = s.scalars(select(Position).where(Position.status == "OPEN")).one()
        assert pos.size == Decimal("200")
        assert pos.avg_price == Decimal("0.05")


def test_sell_closes_position(pfo):
    _fill(pfo, "bot_a", "tokX", "BUY", "0.04", "100")
    _fill(pfo, "bot_a", "tokX", "SELL", "0.07", "100", ts=datetime.now(UTC) + timedelta(hours=1))
    Session = get_session_factory()
    with Session() as s:
        # One CLOSED position
        closed = list(
            s.scalars(
                select(Position).where(Position.status == "CLOSED", Position.bot_id == "bot_a")
            )
        )
        assert len(closed) == 1
        assert closed[0].size == Decimal("0")


def test_realised_pnl_accounting(pfo):
    _fill(pfo, "bot_a", "tokX", "BUY", "0.04", "100")  # cost 4
    _fill(pfo, "bot_a", "tokX", "SELL", "0.07", "100")  # proceeds 7
    # realised = 7 - 4 = 3
    assert pfo.get_realised_pnl("bot_a") == Decimal("3")


def test_unrealised_pnl_mark_to_market(pfo):
    _fill(pfo, "bot_a", "tokX", "BUY", "0.04", "100")
    # Mark at 0.05 → unrealised (0.05-0.04)*100 = 1.0
    assert pfo.get_unrealised_pnl("bot_a", {"tokX": Decimal("0.05")}) == Decimal("1.00")


def test_drawdown_computation(pfo):
    # Start with 1000; buy 100 at 0.04 (exposure 4); mark drops to 0.01.
    _fill(pfo, "bot_a", "tokX", "BUY", "0.04", "100")
    dd = pfo.get_drawdown_pct("bot_a", Decimal("1000"))
    assert dd >= Decimal("0")


def test_sell_without_position_logs_event(pfo):
    _fill(pfo, "bot_a", "tokX", "SELL", "0.07", "50")
    from core.db import Event

    Session = get_session_factory()
    with Session() as s:
        ev = s.scalars(
            select(Event).where(Event.event_type == "portfolio.sell_without_position")
        ).first()
        assert ev is not None


def test_hmrc_fields_populated(pfo):
    _fill(pfo, "bot_a", "tokX", "BUY", "0.04", "100")
    Session = get_session_factory()
    with Session() as s:
        t = s.scalars(select(Trade)).one()
        assert t.usd_gbp_rate == Decimal("0.80")
        assert t.gbp_notional == Decimal("0.04") * Decimal("100") * Decimal("0.80")


def test_idempotent_fill(pfo):
    ts = datetime.now(UTC)
    pfo.on_fill(
        bot_id="bot_a",
        trade_id="dedupe-1",
        order_id=None,
        condition_id="c1",
        token_id="tok1",
        side="BUY",
        price=Decimal("0.04"),
        size=Decimal("100"),
        fee_usd=Decimal("0"),
        filled_at=ts,
    )
    pfo.on_fill(
        bot_id="bot_a",
        trade_id="dedupe-1",
        order_id=None,
        condition_id="c1",
        token_id="tok1",
        side="BUY",
        price=Decimal("0.04"),
        size=Decimal("100"),
        fee_usd=Decimal("0"),
        filled_at=ts,
    )
    Session = get_session_factory()
    with Session() as s:
        pos = s.scalars(select(Position).where(Position.status == "OPEN")).one()
        assert pos.size == Decimal("100")  # not doubled


def test_live_reconcile_can_require_known_order(pfo):
    class FakeClob:
        def get_user_trades(self, since=0):
            return [
                TradeRecord(
                    trade_id="external-wallet-fill",
                    order_id="unknown-order",
                    token_id="tok-external",
                    side=Side.BUY,
                    price=Decimal("0.04"),
                    size=Decimal("10"),
                    fee_usd=Decimal("0"),
                    filled_at=1000.0,
                    market_id="external-market",
                )
            ]

    count = pfo.reconcile_live_fills(
        FakeClob(),
        "bot_g_prime_live",
        require_known_order=True,
    )

    assert count == 0
    Session = get_session_factory()
    with Session() as s:
        assert s.query(Trade).filter_by(bot_id="bot_g_prime_live").count() == 0
        cursor = s.query(Event).filter_by(
            event_type="portfolio.fill_cursor.bot_g_prime_live"
        ).one()
        assert cursor.payload["fills_reconciled"] == 0


def test_live_reconcile_imports_known_order_and_counts_only_new(pfo):
    class FakeClob:
        def get_user_trades(self, since=0):
            return [
                TradeRecord(
                    trade_id="known-live-fill",
                    order_id="known-order",
                    token_id="tok-live",
                    side=Side.BUY,
                    price=Decimal("0.04"),
                    size=Decimal("10"),
                    fee_usd=Decimal("0"),
                    filled_at=1000.0,
                    market_id="live-market",
                )
            ]

    Session = get_session_factory()
    with Session() as s:
        s.add(
            Order(
                order_id="known-order",
                bot_id="bot_g_prime_live",
                condition_id="live-market",
                token_id="tok-live",
                side="BUY",
                price=Decimal("0.04"),
                size=Decimal("10"),
                status="OPEN",
            )
        )
        s.commit()

    assert pfo.reconcile_live_fills(
        FakeClob(),
        "bot_g_prime_live",
        require_known_order=True,
    ) == 1
    assert pfo.reconcile_live_fills(
        FakeClob(),
        "bot_g_prime_live",
        require_known_order=True,
    ) == 0


def test_snapshot_daily_idempotent(pfo):
    _fill(pfo, "bot_a", "tokX", "BUY", "0.04", "100")
    d = datetime.now(UTC).date()
    pfo.snapshot_daily("bot_a", Decimal("1000"), {"tokX": Decimal("0.05")}, on_date=d)
    pfo.snapshot_daily("bot_a", Decimal("1000"), {"tokX": Decimal("0.06")}, on_date=d)

    from core.db import PnlSnapshot

    Session = get_session_factory()
    with Session() as s:
        snaps = list(s.scalars(select(PnlSnapshot).where(PnlSnapshot.bot_id == "bot_a")))
        assert len(snaps) == 1
        # Second call overwrote (updated unrealised from 0.05 to 0.06).


# --- FX rate fetcher (frankfurter) ---

class _FxResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._payload


def test_fx_fetch_parses_frankfurter_payload(monkeypatch):
    from datetime import date
    from decimal import Decimal
    from unittest.mock import MagicMock
    import core.portfolio as p

    captured = {}
    def fake_get(url, params=None, **kw):
        captured["url"] = url
        captured["params"] = params
        return _FxResp(200, {"amount": 1.0, "base": "USD", "date": "2026-04-15", "rates": {"GBP": 0.7846}})
    monkeypatch.setattr(p.httpx, "get", MagicMock(side_effect=fake_get))
    p._FX_CACHE.clear()

    rate = p.get_usd_to_gbp_rate(date(2026, 4, 15))
    assert rate == Decimal("0.78460000")
    assert "frankfurter.dev/v1/2026-04-15" in captured["url"]
    assert captured["params"] == {"from": "USD", "to": "GBP"}


def test_fx_fetch_missing_rates_field_falls_through(monkeypatch):
    from datetime import date
    from decimal import Decimal
    from unittest.mock import MagicMock
    import core.portfolio as p

    monkeypatch.setattr(p.httpx, "get", MagicMock(return_value=_FxResp(200, {"rates": {}})))
    p._FX_CACHE.clear()
    p._FX_LAST_GOOD = Decimal("0.78")

    rate = p.get_usd_to_gbp_rate(date(2026, 4, 15))
    # 7 walk-back attempts all fail too — falls back to last-good
    assert rate == Decimal("0.78")


def test_fx_fetch_uses_cache(monkeypatch):
    from datetime import date
    from decimal import Decimal
    from unittest.mock import MagicMock
    import core.portfolio as p

    p._FX_CACHE.clear()
    p._FX_CACHE[date(2026, 4, 15)] = Decimal("0.7777")
    boom = MagicMock(side_effect=AssertionError("should not be called"))
    monkeypatch.setattr(p.httpx, "get", boom)

    assert p.get_usd_to_gbp_rate(date(2026, 4, 15)) == Decimal("0.7777")
    boom.assert_not_called()
