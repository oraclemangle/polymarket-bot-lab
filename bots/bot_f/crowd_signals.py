"""Bot F crowd-signal detector — daily cron over `mirror_signals`.

Per ADR-032, this module is the second half of Bot F's rehabilitation from
cancelled trader to sensor-supplier. It scans the Mirror-captured trade
stream for windows in which multiple ranked copy-bot wallets piled into the
same market on the same side within a tight window, and records each such
"cascade" event to the `crowd_signals` table for downstream consumption by:

  - Bot B ensemble E4 estimator (reads aggregated wallet flow as a
    probability prior; stale-OK because it is NOT a timing signal).
  - Bot A / Bot D candidate filters (skip or halve size if a same-direction
    cascade fired recently — front-run-fade avoidance).

Design decisions:

- **Pure function over a session.** `detect_cascades` takes a session factory
  and a time range, returns a list of CrowdCascade instances. Caller persists
  (or not). This makes the detection logic independently testable without
  committing to DB state.
- **Rolling window, not bucketed.** A 60s rolling window on timestamps is
  cheap at the Bot F data volume (hundreds to low thousands of signals per
  day) and avoids the bucket-boundary artefact where two wallets entering
  at t=59 and t=61 would be split across buckets.
- **Dominance check.** A cascade must have a dominant side (default >= 2x
  the other side by notional). This filters out two-way flow ("signal" and
  "noise" cancelling out) which isn't a herding trail, just activity.
- **No in-module side-effects.** If you want persistence, call
  `persist_cascades`. The daily-cron script calls both.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from bots.bot_f.db import CrowdCascade, MirrorSignal

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CascadeDetection:
    """In-memory detection; becomes CrowdCascade on persist."""
    market_id: str
    cascade_start_ts: int
    cascade_end_ts: int
    n_wallets: int
    dominant_side: str          # "BUY_YES" | "BUY_NO" | "SELL_YES" | "SELL_NO"
    gross_usd: float
    dominant_ratio: float


def _token_side_key(side: str, token_outcome_hint: str | None = None) -> str:
    """Map MirrorSignal (side, outcome) to a canonical {BUY,SELL}_{YES,NO} key.

    MirrorSignal.side is "BUY" or "SELL" — whether the whale bought or sold
    the token. We need both the trade direction AND the YES/NO token. The
    Mirror raw_payload has `outcome` ("Yes"/"No") but we avoid parsing it
    here; callers that care can join against `markets.yes_token_id` to
    resolve. For cascade detection, we collapse to a 4-value key assuming
    the outcome hint is passed in.
    """
    outcome = (token_outcome_hint or "").strip().upper()
    direction = side.upper().strip()
    if outcome == "YES":
        return f"{direction}_YES"
    if outcome == "NO":
        return f"{direction}_NO"
    # Fallback — treat the token as an unknown side; cascades will still be
    # grouped by (market_id, BUY/SELL) which is a coarser but safe grouping.
    return direction


def detect_cascades(
    session_factory,
    *,
    lookback_hours: int = 24,
    window_s: int = 60,
    min_wallets: int = 6,
    min_gross_usd: float = 500.0,
    dominance_ratio: float = 2.0,
    now: datetime | None = None,
) -> list[CascadeDetection]:
    """Scan mirror_signals over `lookback_hours`, return detected cascades.

    A cascade on (market_id, side) is a rolling-`window_s` window containing:
      - >= `min_wallets` distinct wallets trading that side
      - total notional >= `min_gross_usd`
      - that side's notional >= `dominance_ratio` * other-side notional
        for the same market in the same window

    Returns at most ONE cascade per (market_id, dominant_side) over the lookback
    window — the one with the largest notional. This prevents reporting
    overlapping windows on the same cascade.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=lookback_hours)

    with session_factory() as s:
        rows = list(s.scalars(
            select(MirrorSignal)
            .where(MirrorSignal.detected_at >= cutoff)
            .order_by(MirrorSignal.whale_tx_ts)
        ))

    if not rows:
        return []

    # Group by market_id
    by_market: dict[str, list[MirrorSignal]] = {}
    for r in rows:
        by_market.setdefault(r.condition_id, []).append(r)

    results: list[CascadeDetection] = []

    for market_id, market_rows in by_market.items():
        # Sort by whale_tx_ts (unix seconds). Rows with missing whale_tx_ts
        # fall back to detected_at converted to unix.
        def _ts(r: MirrorSignal) -> int:
            if r.whale_tx_ts is not None:
                return int(r.whale_tx_ts)
            return int(r.detected_at.timestamp())

        market_rows_sorted = sorted(market_rows, key=_ts)

        # For each signal, open a forward window and check for cascade
        # conditions. Track per-side aggregates.
        # Rolling window via two pointers.
        best_by_side: dict[str, CascadeDetection] = {}
        n = len(market_rows_sorted)
        i = 0
        while i < n:
            w_start = _ts(market_rows_sorted[i])
            w_end = w_start + window_s
            j = i
            # Collect everything in window
            window_rows: list[MirrorSignal] = []
            while j < n and _ts(market_rows_sorted[j]) <= w_end:
                window_rows.append(market_rows_sorted[j])
                j += 1
            if len(window_rows) < min_wallets:
                i += 1
                continue
            # Aggregate per side within this window
            per_side: dict[str, dict] = {}
            for r in window_rows:
                # Recover outcome from raw_payload if present
                outcome = _peek_outcome(r.raw_payload)
                key = _token_side_key(r.side, outcome)
                bucket = per_side.setdefault(key, {"wallets": set(), "notional": 0.0})
                bucket["wallets"].add(r.wallet)
                try:
                    bucket["notional"] += float(r.price) * float(r.size_shares)
                except Exception:
                    pass
            total_notional = sum(b["notional"] for b in per_side.values())
            if total_notional < min_gross_usd:
                i += 1
                continue
            # Find dominant side
            dominant_side, dominant_bucket = max(
                per_side.items(), key=lambda kv: kv[1]["notional"],
            )
            dom_notional = dominant_bucket["notional"]
            other_notional = total_notional - dom_notional
            if other_notional > 0 and dom_notional < dominance_ratio * other_notional:
                i += 1
                continue
            if len(dominant_bucket["wallets"]) < min_wallets:
                i += 1
                continue
            if dom_notional < min_gross_usd:
                i += 1
                continue
            ratio = dom_notional / total_notional if total_notional else 0.0
            cd = CascadeDetection(
                market_id=market_id,
                cascade_start_ts=w_start,
                cascade_end_ts=_ts(window_rows[-1]),
                n_wallets=len(dominant_bucket["wallets"]),
                dominant_side=dominant_side,
                gross_usd=dom_notional,
                dominant_ratio=ratio,
            )
            # Keep the largest cascade per dominant_side for this market
            existing = best_by_side.get(dominant_side)
            if existing is None or cd.gross_usd > existing.gross_usd:
                best_by_side[dominant_side] = cd
            i += 1
        results.extend(best_by_side.values())

    return results


def _peek_outcome(raw_payload: str | None) -> str | None:
    """Return 'Yes'/'No' from the raw JSON payload if parseable, else None.

    Cheap, tolerant parse — we do not want to fail detection because of
    malformed JSON on one signal.
    """
    if not raw_payload:
        return None
    try:
        import json
        d = json.loads(raw_payload)
        out = d.get("outcome")
        if out:
            return str(out)
    except Exception:
        return None
    return None


def persist_cascades(
    session_factory,
    cascades: list[CascadeDetection],
    *,
    now: datetime | None = None,
) -> int:
    """Insert detected cascades into `crowd_signals`. Returns count written.

    Idempotency: uses a lightweight existence check on (market_id,
    cascade_start_ts, dominant_side). If a row with the same key already
    exists, skip — the daily cron can be safely re-run.
    """
    now = now or datetime.now(UTC)
    written = 0
    with session_factory() as s:
        for cd in cascades:
            existing = s.scalar(
                select(CrowdCascade).where(
                    CrowdCascade.market_id == cd.market_id,
                    CrowdCascade.cascade_start_ts == cd.cascade_start_ts,
                    CrowdCascade.dominant_side == cd.dominant_side,
                )
            )
            if existing is not None:
                continue
            s.add(CrowdCascade(
                detected_at=now,
                market_id=cd.market_id,
                cascade_start_ts=cd.cascade_start_ts,
                cascade_end_ts=cd.cascade_end_ts,
                n_wallets=cd.n_wallets,
                dominant_side=cd.dominant_side,
                gross_usd=cd.gross_usd,
                dominant_ratio=cd.dominant_ratio,
            ))
            written += 1
        s.commit()
    return written


def recent_cascade_for_market(
    session_factory,
    market_id: str,
    *,
    within_hours: int = 6,
    now: datetime | None = None,
) -> CrowdCascade | None:
    """Utility for Bot A / Bot D filters: has this market had a cascade recently?

    Returns the most recent CrowdCascade row for `market_id` detected within
    `within_hours`, or None.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=within_hours)
    with session_factory() as s:
        return s.scalars(
            select(CrowdCascade)
            .where(
                CrowdCascade.market_id == market_id,
                CrowdCascade.detected_at >= cutoff,
            )
            .order_by(CrowdCascade.detected_at.desc())
        ).first()
