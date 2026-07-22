"""Market selection predicates for Bot A.

One function per predicate; `qualifies()` composes them. Pure functions —
no DB, no HTTP — so they're trivially unit-testable on synthetic data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Iterable

from bots.bot_a.config import (
    DEPTH_WIDTH_CENTS,
    MAX_DAYS_TO_RESOLUTION,
    MAX_YES_ENTRY_PRICE,
    MIN_24H_VOLUME_USD,
    MIN_DAYS_TO_RESOLUTION,
    MIN_NO_ASK_DEPTH_USD,
    QUESTION_BLACKLIST,
    TARGET_CATEGORIES,
)


@dataclass(frozen=True)
class Candidate:
    """Minimal market snapshot needed by Bot A's filters."""

    condition_id: str
    category: str
    question: str
    yes_token_id: str | None
    no_token_id: str | None
    best_yes_ask: Decimal  # from YES book asks
    best_no_ask: Decimal   # from NO book asks
    no_ask_depth_within_2c_usd: Decimal
    volume_24h_usd: Decimal
    end_date: datetime | None
    is_neg_risk: bool = False


def category_ok(c: Candidate) -> bool:
    return c.category.lower() in TARGET_CATEGORIES


def structure_ok(c: Candidate) -> bool:
    return (not c.is_neg_risk) and bool(c.yes_token_id) and bool(c.no_token_id)


def yes_price_below_threshold(c: Candidate) -> bool:
    return c.best_yes_ask <= MAX_YES_ENTRY_PRICE


def volume_above_threshold(c: Candidate) -> bool:
    return c.volume_24h_usd >= MIN_24H_VOLUME_USD


def days_to_resolution_in_window(c: Candidate, now: datetime | None = None) -> bool:
    if c.end_date is None:
        return False
    now = now or datetime.now(UTC)
    # Normalise tz if SQLite stripped it.
    end = c.end_date if c.end_date.tzinfo else c.end_date.replace(tzinfo=UTC)
    days = (end - now).total_seconds() / 86400
    return MIN_DAYS_TO_RESOLUTION <= days <= MAX_DAYS_TO_RESOLUTION


def depth_ok(c: Candidate) -> bool:
    return c.no_ask_depth_within_2c_usd >= MIN_NO_ASK_DEPTH_USD


def question_not_blacklisted(c: Candidate) -> bool:
    q = c.question.lower()
    return not any(term in q for term in QUESTION_BLACKLIST)


_ALL_PREDICATES = (
    category_ok,
    structure_ok,
    yes_price_below_threshold,
    volume_above_threshold,
    days_to_resolution_in_window,
    depth_ok,
    question_not_blacklisted,
)


def qualifies(c: Candidate, now: datetime | None = None) -> bool:
    """All predicates must pass."""
    for pred in _ALL_PREDICATES:
        if pred is days_to_resolution_in_window:
            if not pred(c, now):
                return False
        else:
            if not pred(c):
                return False
    return True


def reasons(c: Candidate, now: datetime | None = None) -> list[str]:
    """Explainability — returns the names of failing predicates, empty on pass."""
    failing: list[str] = []
    for pred in _ALL_PREDICATES:
        ok = pred(c, now) if pred is days_to_resolution_in_window else pred(c)
        if not ok:
            failing.append(pred.__name__)
    return failing


def filter_candidates(
    candidates: Iterable[Candidate], now: datetime | None = None
) -> list[Candidate]:
    return [c for c in candidates if qualifies(c, now)]
