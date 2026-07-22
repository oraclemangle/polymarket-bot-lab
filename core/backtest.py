"""Replay harness.

Feeds historical book snapshots (and for Bot B, historical scores) to the
bot's decision function.  Simulates fills using the "take the touch" model:
a BUY at limit ≥ best_ask fills at best_ask; SELL at limit ≤ best_bid fills
at best_bid.

Minimal v1 (per specs/shared-infra.md §8):
- Deterministic replay
- No slippage modelling beyond take-the-touch
- No partial-fill modelling (CLOB markets are thin enough that we either
  clear the whole touch or don't; good enough for Bot A; Bot B sizes small)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.db import Book, Market, Score, get_session_factory

log = logging.getLogger(__name__)


@dataclass
class SimTrade:
    token_id: str
    side: str  # BUY | SELL
    price: Decimal
    size: Decimal
    timestamp: datetime


@dataclass
class SimResult:
    run_id: str
    trades: list[SimTrade] = field(default_factory=list)
    pnl_curve: list[tuple[datetime, Decimal]] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "trades": [
                {
                    "token_id": t.token_id,
                    "side": t.side,
                    "price": str(t.price),
                    "size": str(t.size),
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in self.trades
            ],
            "pnl_curve": [(ts.isoformat(), str(v)) for ts, v in self.pnl_curve],
            "summary": self.summary,
        }


def _best_ask(book: Book) -> Decimal | None:
    asks = book.asks or []
    if not asks:
        return None
    return min(Decimal(str(a[0])) for a in asks)


def _best_bid(book: Book) -> Decimal | None:
    bids = book.bids or []
    if not bids:
        return None
    return max(Decimal(str(b[0])) for b in bids)


DecisionFn = Callable[[Session, Book, Market], list[tuple[str, str, Decimal, Decimal]]]
"""Decision function signature.

Args:
    session: active DB session (read-only usage expected)
    book: current book snapshot being replayed
    market: the parent market

Returns: list of (token_id, side, limit_price, size) tuples.
"""


class Backtest:
    def __init__(self, session_factory=None, outdir: Path | None = None):
        self._sessions = session_factory or get_session_factory()
        self.outdir = outdir or Path("./data/backtests")

    def run(
        self,
        decision_fn: DecisionFn,
        start: datetime,
        end: datetime,
        run_id: str | None = None,
    ) -> SimResult:
        rid = run_id or f"backtest_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        result = SimResult(run_id=rid)

        with self._sessions() as s:
            books = list(
                s.scalars(
                    select(Book)
                    .where(Book.snapshot_at >= start, Book.snapshot_at <= end)
                    .order_by(Book.snapshot_at)
                )
            )
            # SECURITY_AUDIT.md H-1 fix: map BOTH yes and no token IDs to
            # the parent Market. Bot A (and any other NO-side strategy) was
            # being silently skipped because the previous YES-only map
            # returned None on every NO book snapshot.
            markets: dict[str, Market] = {}
            for m in s.scalars(select(Market)):
                if m.yes_token_id:
                    markets[m.yes_token_id] = m
                if m.no_token_id:
                    markets[m.no_token_id] = m

            realised = Decimal("0")
            position_cost: dict[str, Decimal] = {}  # token → cost basis
            position_size: dict[str, Decimal] = {}  # token → size

            for book in books:
                market = markets.get(book.token_id)
                if market is None:
                    continue
                decisions = decision_fn(s, book, market) or []
                for token_id, side, limit_price, size in decisions:
                    fill_price = self._simulate_fill(book, side, limit_price)
                    if fill_price is None:
                        continue
                    result.trades.append(
                        SimTrade(
                            token_id=token_id,
                            side=side,
                            price=fill_price,
                            size=size,
                            timestamp=book.snapshot_at,
                        )
                    )
                    notional = fill_price * size
                    if side == "BUY":
                        position_cost[token_id] = position_cost.get(
                            token_id, Decimal("0")
                        ) + notional
                        position_size[token_id] = position_size.get(
                            token_id, Decimal("0")
                        ) + size
                    else:
                        avg = (
                            position_cost.get(token_id, Decimal("0"))
                            / position_size.get(token_id, Decimal("1"))
                            if position_size.get(token_id, Decimal("0")) > 0
                            else Decimal("0")
                        )
                        realised += (fill_price - avg) * size
                        position_size[token_id] = position_size.get(
                            token_id, Decimal("0")
                        ) - size
                        position_cost[token_id] = avg * position_size.get(
                            token_id, Decimal("0")
                        )
                    result.pnl_curve.append((book.snapshot_at, realised))

        result.summary = {
            "n_trades": len(result.trades),
            "realised_pnl": str(realised),
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        self._write(result)
        return result

    @staticmethod
    def _simulate_fill(book: Book, side: str, limit_price: Decimal) -> Decimal | None:
        if side == "BUY":
            ask = _best_ask(book)
            if ask is None or limit_price < ask:
                return None
            return ask
        if side == "SELL":
            bid = _best_bid(book)
            if bid is None or limit_price > bid:
                return None
            return bid
        return None

    def _write(self, result: SimResult) -> None:
        self.outdir.mkdir(parents=True, exist_ok=True)
        path = self.outdir / f"{result.run_id}.json"
        path.write_text(json.dumps(result.to_dict(), indent=2))
        log.info("backtest.written", extra={"path": str(path), "n_trades": len(result.trades)})
