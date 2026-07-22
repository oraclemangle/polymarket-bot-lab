"""Bot E — OBI signal engine.

Maintains per-market rolling trade logs and computes order-book imbalance:

    obi(window) = (yes_volume - no_volume) / (yes_volume + no_volume)

OBI > threshold → candidate BUY_YES (market buying UP)
OBI < -threshold → candidate BUY_NO (market buying DOWN)

Thresholds from `config.py` (starting value 0.20 per v96; re-tuned by
Phase 0d calibration).

No executor coupling — this module outputs `ObiSignal` objects; the executor
applies fees/sizing/halts and decides whether to place an order.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal

log = logging.getLogger(__name__)


@dataclass
class ObiSignal:
    """Proposed entry based on OBI."""
    subscription_id: str
    side: str                           # "BUY_YES" | "BUY_NO"
    obi: float                          # observed imbalance [-1, 1]
    abs_obi: float
    window_sec: float
    n_trades: int
    total_volume: Decimal
    yes_price: Decimal | None           # for limit-price calc
    no_price: Decimal | None
    ts_ms: int


@dataclass
class SubscriptionTrades:
    """Rolling trade log for one market subscription."""
    subscription_id: str
    yes_token_id: str | None = None
    no_token_id: str | None = None
    trades: list[tuple[int, str, Decimal]] = field(default_factory=list)
    last_yes_price: Decimal | None = None
    last_no_price: Decimal | None = None
    # 2026-04-17 Audit Finding 1 fix: per-subscription recorder cursor.
    # The main loop reads trades from the recorder DB on every 5s scan. If
    # the caller passes `since_ms = now - window` naively, every trade in
    # the rolling 120s window is re-ingested ~24 times across its lifetime,
    # inflating n_trades and corrupting OBI volume. Callers should pass
    # `since_ms = max(window_floor, sub.last_ingested_ts_ms + 1)` and
    # update this cursor via `record_trade` (which advances it automatically).
    last_ingested_ts_ms: int = 0

    def record_trade(self, ts_ms: int, asset_id: str, size: Decimal) -> None:
        self.trades.append((ts_ms, asset_id, size))
        if ts_ms > self.last_ingested_ts_ms:
            self.last_ingested_ts_ms = ts_ms

    def set_tokens(self, yes_token_id: str, no_token_id: str) -> None:
        self.yes_token_id = yes_token_id
        self.no_token_id = no_token_id

    def prune(self, now_ms: int, window_ms: int) -> None:
        cutoff = now_ms - window_ms
        self.trades = [t for t in self.trades if t[0] >= cutoff]

    def compute_obi(
        self,
        now_ms: int,
        window_sec: float,
        min_trades: int,
        min_volume: Decimal,
        *,
        decay_half_life_sec: float = 0.0,
    ) -> tuple[float | None, int, Decimal]:
        """Return (obi_or_none, n_trades, total_volume).

        `decay_half_life_sec`: 0 = rectangular window (equal weight to all
        trades in `window_sec`). >0 = exponential decay, so a trade aged
        `decay_half_life_sec` ago is weighted 0.5. Audit 2026-04-17
        (GLM-5.1 Q15 / Gemini / Codex P1): rectangular window gives equal
        weight to a trade 119s ago and 1s ago; EWMA preserves the
        information asymmetry.

        Both raw and effective volumes are tracked: the rectangular
        counterparts are still used for `min_volume` / `min_trades` gates
        so the decay change doesn't silently reduce signal frequency.
        """
        window_ms = int(window_sec * 1000)
        self.prune(now_ms, window_ms)
        if len(self.trades) < min_trades or not self.yes_token_id:
            return None, len(self.trades), Decimal("0")
        yes_vol_raw = sum((sz for _, a, sz in self.trades if a == self.yes_token_id), Decimal("0"))
        no_vol_raw = sum((sz for _, a, sz in self.trades if a == self.no_token_id), Decimal("0"))
        total_raw = yes_vol_raw + no_vol_raw
        if total_raw < min_volume:
            return None, len(self.trades), total_raw

        if decay_half_life_sec <= 0:
            imbalance = float(yes_vol_raw - no_vol_raw) / float(total_raw)
            return imbalance, len(self.trades), total_raw

        # EWMA: weight = 0.5 ** (age_sec / half_life_sec).
        half_life_ms = decay_half_life_sec * 1000.0
        yes_w = 0.0
        no_w = 0.0
        for ts, asset_id, size in self.trades:
            age_ms = max(0, now_ms - ts)
            weight = 0.5 ** (age_ms / half_life_ms)
            if asset_id == self.yes_token_id:
                yes_w += float(size) * weight
            elif asset_id == self.no_token_id:
                no_w += float(size) * weight
        total_w = yes_w + no_w
        if total_w <= 0:
            return None, len(self.trades), total_raw
        imbalance = (yes_w - no_w) / total_w
        return imbalance, len(self.trades), total_raw


def maybe_fire(
    state: SubscriptionTrades,
    now_ms: int,
    *,
    window_sec: float,
    threshold: Decimal,
    min_trades: int,
    min_volume: Decimal,
    decay_half_life_sec: float = 0.0,
) -> ObiSignal | None:
    """Return a signal if OBI crosses threshold in either direction.

    `decay_half_life_sec`: 0 = rectangular window; >0 = EWMA (audit 2026-04-17).

    The caller is responsible for gating on regime, time-to-resolution,
    risk caps, and halts. This function only decides "is there an OBI
    reading strong enough to consider".
    """
    obi, n, vol = state.compute_obi(
        now_ms, window_sec, min_trades, min_volume,
        decay_half_life_sec=decay_half_life_sec,
    )
    if obi is None:
        return None
    thr = float(threshold)
    if abs(obi) < thr:
        return None
    side = "BUY_YES" if obi > 0 else "BUY_NO"
    return ObiSignal(
        subscription_id=state.subscription_id,
        side=side,
        obi=obi,
        abs_obi=abs(obi),
        window_sec=window_sec,
        n_trades=n,
        total_volume=vol,
        yes_price=state.last_yes_price,
        no_price=state.last_no_price,
        ts_ms=now_ms,
    )
