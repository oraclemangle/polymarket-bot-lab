"""Bot A state machine — one `tick()` per scheduling interval.

Stateless; reads current DB + live book snapshots, decides what to do, writes
back.  Can be called by a systemd timer every N minutes, or by tests directly.

Flow:
  1. If halted — no-op.
  2. Build candidates from DB (markets × latest books).
  3. Filter them.
  4. For each survivor: `try_enter()` (respects aggregate cap + position-exists).
  5. For each open position: check abnormal-exit threshold on current YES price.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from sqlalchemy import select

from bots.bot_a.candidates import build_candidates
from bots.bot_a.config import BOT_ID
from bots.bot_a.executor import BotAExecutor, EntryDecision
from bots.bot_a.filters import Candidate, qualifies
from core.clob_v2 import ClobWrapperV2 as ClobWrapper
from core.db import Market, Position, get_session_factory

log = logging.getLogger(__name__)


@dataclass
class TickResult:
    entries_placed: int = 0
    entries_skipped: int = 0
    exits_placed: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)
    placed_order_ids: list[str] = field(default_factory=list)

    def record_skip(self, reason: str) -> None:
        self.skip_reasons[reason] = self.skip_reasons.get(reason, 0) + 1


def tick(
    executor: BotAExecutor,
    bankroll_usd: Decimal,
    volume_map: dict[str, Decimal] | None = None,
    current_yes_price_fn: Callable[[str], Decimal | None] | None = None,
) -> TickResult:
    result = TickResult()

    if executor.is_halted():
        log.info("bot_a.tick.halted")
        return result

    # --- Entries ---
    cands = build_candidates(volume_map=volume_map)
    for cand in cands:
        if not qualifies(cand):
            result.record_skip("filter_reject")
            result.entries_skipped += 1
            continue
        decision = executor.try_enter(
            cand,
            bankroll_usd=bankroll_usd,
            depth_usd=cand.no_ask_depth_within_2c_usd,
        )
        if decision.placed:
            result.entries_placed += 1
            if decision.order_id:
                result.placed_order_ids.append(decision.order_id)
        else:
            result.entries_skipped += 1
            result.record_skip(decision.reason or "unknown")

    # --- Exits (abnormal regime break) ---
    if current_yes_price_fn is not None:
        with get_session_factory()() as s:
            open_positions = list(
                s.scalars(
                    select(Position).where(
                        Position.bot_id == BOT_ID, Position.status == "OPEN"
                    )
                )
            )
            # Map condition_id → YES token id so we can quote the right price.
            market_map = {
                m.condition_id: m.yes_token_id
                for m in s.scalars(select(Market))
                if m.yes_token_id
            }

        for pos in open_positions:
            yes_token = market_map.get(pos.condition_id)
            if yes_token is None:
                continue
            yes_px = current_yes_price_fn(yes_token)
            if yes_px is None:
                continue
            if executor.try_cut_loss(pos, yes_px):
                result.exits_placed += 1

    log.info("bot_a.tick.done", extra={
        "entries_placed": result.entries_placed,
        "entries_skipped": result.entries_skipped,
        "exits_placed": result.exits_placed,
        "skip_reasons": result.skip_reasons,
    })
    return result
