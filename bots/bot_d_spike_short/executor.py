"""Paper-only executor for Bot D-Spike-Short.

Mirror of `bots/bot_d_spike/executor.py` with the bot_id and config module
swapped to the short-TTR lane. Both lanes share `core.db` schema, `core.clob`,
and `core.portfolio`; attribution is via `bot_id` in every row.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from bots.bot_d_spike_short import config as cfg
from bots.bot_d_spike_short.strategy import EntryDecision
from core.clob import OrderBook
from core.clob_v2 import OrderType, Side
from core.config import FEE_RATE_BY_CATEGORY_BPS
from core.db import Book, Event, Order, Position, get_session_factory, upsert_market_minimal
from core.emergency_halt import is_emergency_halted
from core.portfolio import Portfolio

log = logging.getLogger(__name__)

OPEN_ORDER_STATUSES = ("OPEN", "PARTIAL", "PAPER_OPEN", "live", "MATCHED")


@dataclass(frozen=True)
class SpikeShortEntryResult:
    placed: bool
    reason: str
    order_id: str | None = None
    condition_id: str | None = None
    token_id: str | None = None
    limit_price: Decimal | None = None
    size_shares: Decimal | None = None
    size_usd: Decimal | None = None
    fills_simulated: int = 0


class SpikeShortExecutor:
    def __init__(
        self,
        clob: object,
        main_session_factory: sessionmaker | None = None,
        *,
        auto_fill_paper: bool = True,
    ) -> None:
        self.clob = clob
        self._sessions = main_session_factory or get_session_factory()
        self.auto_fill_paper = auto_fill_paper

    def _effective_paper(self) -> bool:
        effective = getattr(self.clob, "_effective_paper", None)
        if callable(effective):
            return bool(effective())
        return bool(getattr(self.clob, "paper_override", False))

    def _capture_book_snapshot(self, token_id: str, book: OrderBook) -> None:
        snapshot_at = datetime.fromtimestamp(float(book.timestamp), tz=UTC)

        def rows(levels: list[tuple[Decimal, Decimal]]) -> list[list[str]]:
            return [[str(price), str(size)] for price, size in levels]

        with self._sessions() as s:
            s.add(Book(token_id=token_id, snapshot_at=snapshot_at, bids=rows(book.bids), asks=rows(book.asks)))
            s.commit()

    def has_position_or_order(self, condition_id: str, token_id: str) -> bool:
        with self._sessions() as s:
            orders = s.scalar(
                select(func.count()).select_from(Order).where(
                    Order.bot_id == cfg.BOT_D_SPIKE_SHORT_BOT_ID,
                    Order.condition_id == condition_id,
                    Order.token_id == token_id,
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            )
            positions = s.scalar(
                select(func.count()).select_from(Position).where(
                    Position.bot_id == cfg.BOT_D_SPIKE_SHORT_BOT_ID,
                    Position.condition_id == condition_id,
                    Position.token_id == token_id,
                    Position.status == "OPEN",
                )
            )
        return bool((orders or 0) + (positions or 0))

    def other_bot_active_on_condition(self, condition_id: str) -> bool:
        with self._sessions() as s:
            orders = s.scalar(
                select(func.count()).select_from(Order).where(
                    Order.bot_id != cfg.BOT_D_SPIKE_SHORT_BOT_ID,
                    Order.condition_id == condition_id,
                    Order.status.in_(OPEN_ORDER_STATUSES),
                )
            )
            positions = s.scalar(
                select(func.count()).select_from(Position).where(
                    Position.bot_id != cfg.BOT_D_SPIKE_SHORT_BOT_ID,
                    Position.condition_id == condition_id,
                    Position.status == "OPEN",
                )
            )
        return bool((orders or 0) + (positions or 0))

    def count_open(self) -> int:
        with self._sessions() as s:
            pos_cids = set(
                s.scalars(
                    select(Position.condition_id).where(
                        Position.bot_id == cfg.BOT_D_SPIKE_SHORT_BOT_ID,
                        Position.status == "OPEN",
                    )
                )
            )
            order_cids = set(
                s.scalars(
                    select(Order.condition_id).where(
                        Order.bot_id == cfg.BOT_D_SPIKE_SHORT_BOT_ID,
                        Order.status.in_(OPEN_ORDER_STATUSES),
                    )
                )
            )
        return len(pos_cids | order_cids)

    def deployed_usd(self) -> Decimal:
        return Portfolio(self._sessions).get_total_exposure(cfg.BOT_D_SPIKE_SHORT_BOT_ID)

    def todays_entries(self, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        with self._sessions() as s:
            return int(
                s.scalar(
                    select(func.count()).select_from(Order).where(
                        Order.bot_id == cfg.BOT_D_SPIKE_SHORT_BOT_ID,
                        Order.side == "BUY",
                        Order.placed_at >= start,
                    )
                )
                or 0
            )

    def _blocker(self, decision: EntryDecision, size_usd: Decimal) -> str | None:
        if not decision.enter:
            return decision.reason
        if not self._effective_paper():
            return "paper_only_guard"
        if cfg.ENTRY_HALT:
            return "entry_halt"
        if is_emergency_halted():
            return "emergency_halt"
        candidate = decision.candidate
        if self.has_position_or_order(candidate.market.condition_id, candidate.yes_token_id):
            return "dedupe"
        if self.other_bot_active_on_condition(candidate.market.condition_id):
            return "other_bot_overlap"
        if self.count_open() >= cfg.MAX_CONCURRENT_POSITIONS:
            return "max_concurrent"
        if self.deployed_usd() + size_usd > cfg.MAX_DEPLOYED_USD:
            return "max_deployed"
        if self.todays_entries() >= cfg.MAX_DAILY_ENTRIES:
            return "daily_entry_cap"
        return None

    def try_enter(self, decision: EntryDecision) -> SpikeShortEntryResult:
        size_usd = decision.size_usd or cfg.PER_POSITION_SIZE_USD
        blocker = self._blocker(decision, size_usd)
        candidate = decision.candidate
        if blocker is not None:
            return SpikeShortEntryResult(
                False,
                blocker,
                condition_id=candidate.market.condition_id,
                token_id=candidate.yes_token_id,
                size_usd=size_usd,
            )

        limit = candidate.best_ask.quantize(Decimal("0.001"))
        size_shares = (size_usd / limit).quantize(Decimal("0.01"))
        book = self.clob.get_book(candidate.yes_token_id)
        self._capture_book_snapshot(candidate.yes_token_id, book)

        resp = self.clob.place_limit(
            token_id=candidate.yes_token_id,
            price=limit,
            size=size_shares,
            side=Side.BUY,
            order_type=OrderType.GTC,
        )
        if not resp.order_id or not str(resp.order_id).startswith("paper-"):
            log.error("bot_d_spike_short.paper_guard_failed response=%s", resp)
            return SpikeShortEntryResult(False, "paper_order_guard_failed")

        with self._sessions() as s:
            upsert_market_minimal(
                s,
                condition_id=candidate.market.condition_id,
                category="weather",
                question=candidate.market.question,
                yes_token_id=candidate.market.yes_token_id,
                no_token_id=candidate.market.no_token_id,
                end_date=candidate.market.end_date,
                yes_price=limit,
                volume_24h_usd=candidate.market.volume_24h_usd,
                fee_rate_bps=FEE_RATE_BY_CATEGORY_BPS.get("weather"),
            )
            s.add(
                Order(
                    order_id=resp.order_id,
                    bot_id=cfg.BOT_D_SPIKE_SHORT_BOT_ID,
                    condition_id=candidate.market.condition_id,
                    token_id=candidate.yes_token_id,
                    side="BUY",
                    price=limit,
                    size=size_shares,
                    status=resp.status or "PAPER_OPEN",
                    order_type="GTC",
                )
            )
            s.add(
                Event(
                    bot_id=cfg.BOT_D_SPIKE_SHORT_BOT_ID,
                    event_type="bot_d_spike_short.entry_placed",
                    severity="info",
                    message=f"paper BUY placed {candidate.city} {candidate.market.bucket}",
                    payload={
                        "condition_id": candidate.market.condition_id,
                        "gamma_id": candidate.market.gamma_id,
                        "token_id": candidate.yes_token_id,
                        "city": candidate.city,
                        "city_tier": candidate.city_tier,
                        "date": candidate.market.date,
                        "bucket": candidate.market.bucket,
                        "best_ask": str(candidate.best_ask),
                        "best_bid": str(candidate.best_bid),
                        "spread": str(candidate.spread),
                        "depth_at_ask_shares": str(candidate.depth_at_ask_shares),
                        "hours_to_resolution": str(candidate.hours_to_resolution),
                        "size_usd": str(size_usd),
                        "size_shares": str(size_shares),
                    },
                )
            )
            s.commit()

        fills = 0
        if self.auto_fill_paper:
            fills = Portfolio(self._sessions).simulate_paper_fills(cfg.BOT_D_SPIKE_SHORT_BOT_ID)
        return SpikeShortEntryResult(
            True,
            "placed",
            order_id=resp.order_id,
            condition_id=candidate.market.condition_id,
            token_id=candidate.yes_token_id,
            limit_price=limit,
            size_shares=size_shares,
            size_usd=size_usd,
            fills_simulated=fills,
        )

    def reconcile_resolutions(self) -> int:
        return Portfolio(self._sessions).reconcile_paper_resolutions(cfg.BOT_D_SPIKE_SHORT_BOT_ID)
