"""Tests for core.rewards_monitor.

Covers the two pieces of logic that aren't just HTTP passthroughs:
eligibility filtering by date window and the condition_id intersection
inside compute_maker_notional.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from core.db import Order, Trade, get_session_factory
from core.rewards_monitor import (
    compute_maker_notional,
    eligible_condition_ids,
    fetch_eligible_markets,
    snapshot_daily,
    sum_daily_reward_pool,
)


class _StubResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _StubClient:
    """Minimal httpx.Client stand-in that serves a fixed page of markets."""

    def __init__(self, pages):
        self._pages = list(pages)
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        if not self._pages:
            return _StubResponse([])
        return _StubResponse(self._pages.pop(0))

    def close(self):
        pass


def _market(cid: str, rate: float, start: str, end: str) -> dict:
    return {
        "conditionId": cid,
        "clobRewards": [
            {"rewardsDailyRate": rate, "startDate": start, "endDate": end}
        ],
    }


def test_eligibility_filter_respects_date_window():
    today = date(2026, 4, 24)
    markets = [
        _market("active", 5.0, "2026-01-01", "2026-12-31"),
        _market("expired", 5.0, "2025-01-01", "2025-12-31"),
        _market("future", 5.0, "2026-06-01", "2026-12-31"),
        _market("zero_rate", 0, "2026-01-01", "2026-12-31"),
    ]
    client = _StubClient([markets])
    eligible = fetch_eligible_markets(client, today=today)
    assert eligible_condition_ids(eligible) == {"active"}
    assert sum_daily_reward_pool(eligible) == Decimal("5.0")


def test_compute_maker_notional_splits_eligible(tmp_db: Path):
    sf = get_session_factory()
    with sf() as s:
        s.add_all(
            [
                Order(
                    order_id="o_maker_elig",
                    bot_id="bot_e",
                    condition_id="cid_elig",
                    token_id="t1",
                    side="BUY",
                    price=Decimal("0.45"),
                    size=Decimal("10"),
                    status="FILLED",
                    order_type="GTC",
                ),
                Order(
                    order_id="o_maker_ineligible",
                    bot_id="bot_e",
                    condition_id="cid_none",
                    token_id="t2",
                    side="BUY",
                    price=Decimal("0.30"),
                    size=Decimal("20"),
                    status="FILLED",
                    order_type="GTC",
                ),
                Order(
                    order_id="o_taker_elig",
                    bot_id="bot_g",
                    condition_id="cid_elig",
                    token_id="t3",
                    side="BUY",
                    price=Decimal("0.02"),
                    size=Decimal("100"),
                    status="FILLED",
                    order_type="FOK",
                ),
            ]
        )
        filled_at = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
        s.add_all(
            [
                Trade(
                    trade_id="t1",
                    bot_id="bot_e",
                    order_id="o_maker_elig",
                    condition_id="cid_elig",
                    token_id="t1",
                    side="BUY",
                    price=Decimal("0.45"),
                    size=Decimal("10"),
                    filled_at=filled_at,
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("3.6"),
                ),
                Trade(
                    trade_id="t2",
                    bot_id="bot_e",
                    order_id="o_maker_ineligible",
                    condition_id="cid_none",
                    token_id="t2",
                    side="BUY",
                    price=Decimal("0.30"),
                    size=Decimal("20"),
                    filled_at=filled_at,
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("4.8"),
                ),
                Trade(
                    trade_id="t3",
                    bot_id="bot_g",
                    order_id="o_taker_elig",
                    condition_id="cid_elig",
                    token_id="t3",
                    side="BUY",
                    price=Decimal("0.02"),
                    size=Decimal("100"),
                    filled_at=filled_at,
                    usd_gbp_rate=Decimal("0.80"),
                    gbp_notional=Decimal("1.6"),
                ),
            ]
        )
        s.commit()

    start = datetime(2026, 4, 24, 0, 0, tzinfo=UTC)
    end = start + timedelta(days=1)
    totals, eligible_totals = compute_maker_notional(sf, start, end, {"cid_elig"})

    # bot_e made two maker fills (4.5 + 6.0 = 10.5); bot_g's taker fill is ignored.
    assert totals == {"bot_e": Decimal("10.5")}
    # Only the cid_elig maker fill counts toward eligible notional.
    assert eligible_totals == {"bot_e": Decimal("4.5")}


def test_snapshot_daily_appends_jsonl(tmp_db: Path, tmp_path: Path, monkeypatch):
    out = tmp_path / "snap.jsonl"
    client = _StubClient([[_market("cid_x", 3.0, "2026-01-01", "2026-12-31")]])

    snap = snapshot_daily(
        wallet=None,
        out_path=out,
        snapshot_date=date(2026, 4, 24),
        http_client=client,
    )
    assert snap.eligible_markets == 1
    assert snap.eligible_daily_pool_usd == "3.0"
    assert snap.rewards_source == "skipped"
    assert out.read_text().count("\n") == 1

    # Second call on the same date appends rather than replacing.
    client2 = _StubClient([[]])
    snapshot_daily(
        wallet=None,
        out_path=out,
        snapshot_date=date(2026, 4, 24),
        http_client=client2,
    )
    assert out.read_text().count("\n") == 2
