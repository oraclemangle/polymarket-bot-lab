"""Build Bot A `Candidate` objects from the shared DB.

Joins the latest book snapshot per market against the markets table and
packages the minimum info filters.py needs. No network.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from bots.bot_a.config import DEPTH_WIDTH_CENTS
from bots.bot_a.filters import Candidate
from core.db import Book, Market, get_session_factory


def _best_ask(book_side: list) -> Decimal:
    if not book_side:
        return Decimal("1")
    return min(Decimal(str(row[0])) for row in book_side)


def _best_bid(book_side: list) -> Decimal:
    if not book_side:
        return Decimal("0")
    return max(Decimal(str(row[0])) for row in book_side)


def _depth_within(book_side: list, anchor: Decimal, width: Decimal) -> Decimal:
    """Sum USD notional (price * size) of levels within `width` of `anchor`."""
    total = Decimal("0")
    for row in book_side:
        px = Decimal(str(row[0]))
        sz = Decimal(str(row[1]))
        if abs(px - anchor) <= width:
            total += px * sz
    return total


def latest_book_for(s: Session, token_id: str) -> Book | None:
    return s.scalars(
        select(Book).where(Book.token_id == token_id).order_by(Book.snapshot_at.desc())
    ).first()


def build_candidates(
    session_factory=None, volume_map: dict[str, Decimal] | None = None
) -> list[Candidate]:
    """Pull every market with both YES and NO token ids and assemble a Candidate.

    Volume is now read from `markets.volume_24h_usd` (populated by the Gamma
    scraper).  The legacy `volume_map` kwarg still overrides per-market for
    tests and ad-hoc injection.
    """
    factory = session_factory or get_session_factory()
    out: list[Candidate] = []
    with factory() as s:
        markets = list(
            s.scalars(
                select(Market).where(
                    Market.yes_token_id.is_not(None), Market.no_token_id.is_not(None)
                )
            )
        )
        for m in markets:
            yes_book = latest_book_for(s, m.yes_token_id)
            no_book = latest_book_for(s, m.no_token_id)
            if yes_book is None or no_book is None:
                continue

            best_yes_ask = _best_ask(yes_book.asks or [])
            best_no_ask = _best_ask(no_book.asks or [])

            # Depth at NO-ask within 2¢ of its mid.
            no_mid = (
                (best_no_ask + _best_bid(no_book.bids or [])) / 2
                if no_book.bids
                else best_no_ask
            )
            depth = _depth_within(no_book.asks or [], no_mid, DEPTH_WIDTH_CENTS)

            out.append(
                Candidate(
                    condition_id=m.condition_id,
                    category=m.category,
                    question=m.question,
                    yes_token_id=m.yes_token_id,
                    no_token_id=m.no_token_id,
                    best_yes_ask=best_yes_ask,
                    best_no_ask=best_no_ask,
                    no_ask_depth_within_2c_usd=depth,
                    volume_24h_usd=(
                        Decimal(str((volume_map or {}).get(m.condition_id)))
                        if volume_map and m.condition_id in volume_map
                        else (m.volume_24h_usd or Decimal("0"))
                    ),
                    end_date=m.end_date,
                    is_neg_risk=bool(m.is_neg_risk),
                )
            )
    return out
