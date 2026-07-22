"""Fleet-wide execution policy — dynamic limit-ladder + toxicity filter.

Per ADR-031 (docs/decisions-log.md) and docs/session-2026-04-17-edges-review.md
Section 3.3, this module adds two primitives on top of the existing
place-and-hold passive-limit pattern:

1. Toxicity filter — scores the top-of-book aggressive flow for our intended
   side. Blocks new placements when flow is hostile (aggressive sellers
   hitting bids we're about to join); freezes existing limits when flow
   flips hostile mid-life.

2. Limit ladder — state machine that steps a resting limit closer to mid
   after T1 seconds unfilled, steps again after T2, cancels after T3. Also
   cancels on large book moves against us (|delta| > k * ATR).

Both primitives are pure functions over snapshotted inputs; no network calls,
no DB access. The owning bot supplies BookSnapshot and FlowWindow objects and
decides whether to act on the returned recommendations.

Rollout is strictly opt-in per bot via BOT_X_EXEC_POLICY_ENABLED.
Default off. Risk guardrails (cancel-storm breaker, per-bot timing priors)
are the operator's to tune.

Security note: this module does NOT touch keys, signers, or CLOB wrappers.
It operates on plain dataclasses. Integration code in each bot's executor
calls into here, then places / cancels through the existing CLOB path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Side / state primitives
# ---------------------------------------------------------------------------


Side = Literal["YES_BUY", "NO_BUY", "YES_SELL", "NO_SELL"]


class LadderState(str, Enum):
    PLACED = "placed"
    STEP_1 = "step_1"
    STEP_2 = "step_2"
    FROZEN = "frozen"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Input dataclasses — populated by the caller from WSS / portfolio state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BookSnapshot:
    """Top-of-book view at a moment in time."""
    best_yes_bid: float
    best_yes_ask: float
    best_no_bid: float
    best_no_ask: float
    yes_bid_depth_usd: float
    yes_ask_depth_usd: float
    no_bid_depth_usd: float
    no_ask_depth_usd: float
    ts: float


@dataclass(frozen=True)
class FlowWindow:
    """Aggregated aggressive flow over a recent lookback (usually 60s).

    Aggressive = trade that crossed the spread to execute immediately.
    On Polymarket CLOB, aggressive BUY lifts an ask; aggressive SELL hits a bid.
    Per-side (YES/NO token) so toxicity can be computed for either side.
    """
    ts_start: float
    ts_end: float
    aggressive_buy_yes_usd: float
    aggressive_sell_yes_usd: float
    aggressive_buy_no_usd: float
    aggressive_sell_no_usd: float


@dataclass
class ActiveLimit:
    """Book-keeping for a live resting limit order.

    Owned by the caller (usually a per-bot LadderManager). This module
    provides pure functions over this dataclass; it does not persist it.
    """
    order_id: str
    bot_name: str
    side: Side
    original_price: float
    current_price: float
    placed_ts: float
    state: LadderState = LadderState.PLACED
    step_count: int = 0


# ---------------------------------------------------------------------------
# Policy configuration (per-bot; see bots/bot_x/config.py for env binding)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LadderPolicy:
    """Ladder-step thresholds and cancel rules. All durations in seconds."""
    step_1_age_s: int = 300
    step_2_age_s: int = 900
    cancel_age_s: int = 1800
    tick_step: float = 0.01
    max_step_count: int = 2
    book_move_cancel_atr: float = 2.0
    toxicity_freeze_threshold: float = 0.70
    toxicity_place_block_threshold: float = 0.80


# ---------------------------------------------------------------------------
# Pure policy functions
# ---------------------------------------------------------------------------


def compute_toxicity(flow: FlowWindow, intended_side: Side) -> float:
    """Score aggressive flow against our side on [0, 1].

    Higher = more hostile. "Against our side" means: if we intend to BUY YES
    at bid, aggressive SELL YES (side="SELL" trade on YES token) is against us
    because it's someone dumping into bids.
    """
    if intended_side == "YES_BUY":
        against = flow.aggressive_sell_yes_usd
        with_us = flow.aggressive_buy_yes_usd
    elif intended_side == "NO_BUY":
        against = flow.aggressive_sell_no_usd
        with_us = flow.aggressive_buy_no_usd
    elif intended_side == "YES_SELL":
        against = flow.aggressive_buy_yes_usd
        with_us = flow.aggressive_sell_yes_usd
    elif intended_side == "NO_SELL":
        against = flow.aggressive_buy_no_usd
        with_us = flow.aggressive_sell_no_usd
    else:
        raise ValueError(f"unknown side: {intended_side}")
    gross = against + with_us
    if gross < 1e-6:
        return 0.0
    return against / gross


def should_place(
    policy: LadderPolicy,
    intended_side: Side,
    flow: FlowWindow,
) -> tuple[bool, str]:
    """Decide whether to place a new passive limit given current flow.

    Returns (ok, reason). `reason` is a short token suitable for logging / telemetry
    counters ("ok", "toxicity_block:0.82", etc.).
    """
    tox = compute_toxicity(flow, intended_side)
    if tox >= policy.toxicity_place_block_threshold:
        return False, f"toxicity_block:{tox:.2f}"
    return True, "ok"


def book_ref_price(book: BookSnapshot, side: Side) -> float:
    """Return the book-side reference price relevant to the given side.

    For YES_BUY we care about best_yes_bid (where our limit rests).
    For NO_BUY we care about best_no_bid, etc.
    """
    if side == "YES_BUY":
        return book.best_yes_bid
    if side == "NO_BUY":
        return book.best_no_bid
    if side == "YES_SELL":
        return book.best_yes_ask
    if side == "NO_SELL":
        return book.best_no_ask
    raise ValueError(f"unknown side: {side}")


def _step_direction(side: Side) -> int:
    """+1 for BUY (step up toward ask); -1 for SELL (step down toward bid)."""
    if side in ("YES_BUY", "NO_BUY"):
        return 1
    return -1


def next_ladder_action(
    limit: ActiveLimit,
    book: BookSnapshot,
    flow: FlowWindow,
    atr: float,
    policy: LadderPolicy,
    now_ts: float,
) -> tuple[LadderState, float | None]:
    """Decide the next action for an active resting limit.

    Returns (next_state, new_price_or_None). `new_price=None` means: stay where
    you are or move to `next_state` without repricing (e.g. FREEZE / CANCEL).

    Priority order:
      1. Toxicity freeze (hostile flow) — overrides stepping.
      2. Book moved against us by > k*ATR — cancel.
      3. Age >= cancel_age_s — cancel.
      4. Age >= step_2 threshold and not yet STEP_2 — step.
      5. Age >= step_1 threshold and still PLACED — step.
      6. Otherwise stay.
    """
    if atr < 0:
        raise ValueError("atr must be non-negative")

    age = now_ts - limit.placed_ts
    tox = compute_toxicity(flow, limit.side)

    # 1) Freeze on hostile flow
    if tox >= policy.toxicity_freeze_threshold:
        return LadderState.FROZEN, None

    # 2) Cancel on book moves against us
    ref = book_ref_price(book, limit.side)
    # Adverse move: for BUY sides, book_ref_price moving away (further from ask)
    # isn't adverse — we care about the mid moving AWAY from our limit.
    # Simple proxy: if the absolute move from original exceeds k * ATR, cancel.
    if atr > 0 and abs(ref - limit.original_price) > policy.book_move_cancel_atr * atr:
        return LadderState.CANCELLED, None

    # 3) Age-based cancel
    if age >= policy.cancel_age_s:
        return LadderState.CANCELLED, None

    # Ladder stepping (respects max_step_count)
    if limit.step_count >= policy.max_step_count:
        return limit.state, None

    direction = _step_direction(limit.side)
    new_price_step1 = limit.current_price + direction * policy.tick_step
    new_price_step2 = limit.current_price + direction * 2 * policy.tick_step

    if age >= policy.step_2_age_s and limit.state != LadderState.STEP_2:
        return LadderState.STEP_2, new_price_step2
    if age >= policy.step_1_age_s and limit.state == LadderState.PLACED:
        return LadderState.STEP_1, new_price_step1

    return limit.state, None


# ---------------------------------------------------------------------------
# Per-bot helper — simple in-memory ladder manager
# ---------------------------------------------------------------------------


@dataclass
class LadderManager:
    """Tracks active limits for one bot and drives the step/cancel loop.

    Integration:
    - On place_limit success, call register(order_id, ...).
    - On every book/flow tick (or on a 30s heartbeat), call tick() which
      returns a list of (order_id, action, new_price) for the bot executor
      to apply via CLOB.
    - On fill/cancel confirmation from CLOB, call forget(order_id).

    Cancel-storm breaker:
    - If cancel count exceeds cancels_per_window_limit within window_s,
      tick() returns [] and sets `self.tripped=True`. Operator must
      `reset_breaker()` to resume.
    """
    policy: LadderPolicy
    bot_name: str
    cancels_per_window_limit: int = 30
    window_s: int = 300
    _active: dict[str, ActiveLimit] = field(default_factory=dict)
    _recent_cancels: list[float] = field(default_factory=list)
    tripped: bool = False

    def register(self, limit: ActiveLimit) -> None:
        self._active[limit.order_id] = limit

    def forget(self, order_id: str) -> None:
        self._active.pop(order_id, None)

    def reset_breaker(self) -> None:
        self.tripped = False
        self._recent_cancels = []

    def _prune_cancels(self, now_ts: float) -> None:
        cutoff = now_ts - self.window_s
        self._recent_cancels = [t for t in self._recent_cancels if t >= cutoff]

    def tick(
        self,
        book: BookSnapshot,
        flow: FlowWindow,
        atr: float,
        now_ts: float,
    ) -> list[tuple[str, LadderState, float | None]]:
        """Evaluate all active limits and return the actions to apply."""
        if self.tripped:
            return []
        self._prune_cancels(now_ts)
        actions: list[tuple[str, LadderState, float | None]] = []
        for oid, limit in list(self._active.items()):
            next_state, new_price = next_ladder_action(
                limit, book, flow, atr, self.policy, now_ts,
            )
            if next_state == limit.state and new_price is None:
                continue
            # State transition detected — update local copy
            if new_price is not None:
                limit.current_price = new_price
                limit.step_count += 1
            limit.state = next_state
            actions.append((oid, next_state, new_price))
            if next_state == LadderState.CANCELLED:
                self._recent_cancels.append(now_ts)
                if len(self._recent_cancels) >= self.cancels_per_window_limit:
                    self.tripped = True
                    log.warning(
                        "exec_policy.cancel_storm_breaker bot=%s cancels=%d window_s=%d",
                        self.bot_name, len(self._recent_cancels), self.window_s,
                    )
        return actions
