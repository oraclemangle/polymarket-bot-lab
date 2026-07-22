"""Bot A market-selection filter tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from bots.bot_a.filters import Candidate, qualifies, reasons


def _base(**overrides) -> Candidate:
    now = datetime.now(UTC)
    d = dict(
        condition_id="c1",
        category="politics",
        question="Will X happen by year end?",
        yes_token_id="yes1",
        no_token_id="no1",
        best_yes_ask=Decimal("0.04"),
        best_no_ask=Decimal("0.96"),
        no_ask_depth_within_2c_usd=Decimal("1000"),
        volume_24h_usd=Decimal("10000"),
        end_date=now + timedelta(days=60),
        is_neg_risk=False,
    )
    d.update(overrides)
    return Candidate(**d)


def test_golden_passes():
    assert qualifies(_base())


def test_category_reject():
    assert not qualifies(_base(category="sports"))
    assert "category_ok" in reasons(_base(category="sports"))


def test_yes_price_reject():
    assert not qualifies(_base(best_yes_ask=Decimal("0.06")))


def test_volume_reject():
    assert not qualifies(_base(volume_24h_usd=Decimal("100")))


def test_too_short_window():
    c = _base(end_date=datetime.now(UTC) + timedelta(days=10))
    assert not qualifies(c)


def test_too_long_window():
    c = _base(end_date=datetime.now(UTC) + timedelta(days=400))
    assert not qualifies(c)


def test_no_end_date():
    c = _base(end_date=None)
    assert not qualifies(c)


def test_depth_reject():
    assert not qualifies(_base(no_ask_depth_within_2c_usd=Decimal("100")))


def test_neg_risk_reject():
    assert not qualifies(_base(is_neg_risk=True))


def test_blacklist_reject():
    c = _base(question="Will Putin be assassinated this year?")
    assert not qualifies(c)
    assert "question_not_blacklisted" in reasons(c)


def test_case_insensitive_category():
    c = _base(category="Politics")
    assert qualifies(c)


def test_reasons_lists_all_failures():
    c = _base(category="sports", best_yes_ask=Decimal("0.10"))
    fails = reasons(c)
    assert "category_ok" in fails
    assert "yes_price_below_threshold" in fails
