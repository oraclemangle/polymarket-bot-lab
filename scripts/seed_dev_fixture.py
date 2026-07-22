#!/usr/bin/env python3
"""Seed a development fixture into the DB — Market, Books, and a Score row
for Bot B — so the paper-mode pipelines can be smoke-tested without any
network call (no Gamma, no CLOB, no oracle-mangle).

Useful for:
  - First-time local smoke after `alembic upgrade head`
  - CI-style end-to-end "does a tick actually place a paper order" check
  - Verifying the daemons boot cleanly

Usage:
  python scripts/seed_dev_fixture.py --reset
  python -m bots.bot_a          # should place a paper order on the seeded market
  (Bot B excluded from public export; see docs/bot-b-reference.md)
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select

from core.db import Book, Market, Score, get_session_factory


FIXTURE_CID = "dev-fixture-0001"


def seed(reset: bool = False) -> int:
    Session = get_session_factory()
    with Session() as s:
        if reset:
            s.execute(delete(Book).where(Book.token_id.in_(["yes_fix", "no_fix"])))
            s.execute(delete(Score).where(Score.condition_id == FIXTURE_CID))
            s.execute(delete(Market).where(Market.condition_id == FIXTURE_CID))
            s.commit()

        existing = s.get(Market, FIXTURE_CID)
        if existing:
            print(f"Fixture {FIXTURE_CID} already present; re-run with --reset to rebuild.")
            return 0

        # Bot A wants yes_ask ≤ 0.05.  Bot B wants divergence between
        # claude_implied_prob and yes_price ≥ 0.08, confidence ≥ 0.70,
        # DR ≤ 0.25.  A single market can satisfy both.
        s.add(
            Market(
                condition_id=FIXTURE_CID,
                category="geopolitics",
                question="DEV FIXTURE — will the rate be cut in June?",
                fee_rate_bps=0,
                yes_token_id="yes_fix",
                no_token_id="no_fix",
                is_neg_risk=0,
                volume_24h_usd=Decimal("50000"),
                end_date=datetime.now(UTC) + timedelta(days=45),
            )
        )
        # Books: wide bid-ask, deep enough for the depth filter.
        s.add(
            Book(
                token_id="yes_fix",
                snapshot_at=datetime.now(UTC),
                bids=[["0.03", "50000"], ["0.02", "60000"]],
                asks=[["0.04", "80000"], ["0.05", "50000"]],
            )
        )
        s.add(
            Book(
                token_id="no_fix",
                snapshot_at=datetime.now(UTC),
                bids=[["0.95", "1000"], ["0.94", "2000"]],
                asks=[["0.96", "5000"], ["0.97", "3000"]],
            )
        )
        # Score: model thinks YES probability is 0.18 vs market 0.04 → Bot B picks YES.
        s.add(
            Score(
                condition_id=FIXTURE_CID,
                scored_at=datetime.now(UTC),
                dispute_risk=Decimal("0.10"),
                claude_pick="YES",
                claude_confidence=Decimal("0.80"),
                claude_implied_prob=Decimal("0.18"),
                resolution_prediction="DEV fixture: resolution likely YES per fake rationale.",
                model_version="dev-fixture-v1",
            )
        )
        s.commit()
    print(f"Seeded dev fixture: {FIXTURE_CID}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="remove fixture first")
    args = parser.parse_args(argv)
    return seed(reset=args.reset)


if __name__ == "__main__":
    sys.exit(main())
