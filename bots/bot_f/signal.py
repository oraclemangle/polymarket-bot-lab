"""Mirror — read-only whale trade subscriber (sensor-role permanent).

Consumes the latest Hunter rankings and polls data-api.polymarket.com/trades
per ranked wallet for new positions. Writes every detected signal to
bot_f.db::mirror_signals with latency telemetry. ZERO EXECUTION — permanently.

**Phase 2 Trigger cancelled 2026-04-17.** See `bots/bot_f/__init__.py` for
reasoning. The `would_have_traded` label + `rejection_reason` produced by
`hypothetical_trigger_eval` are MEASUREMENT data only. They are never
consumed by an executor. If a future session proposes re-introducing
copy-trade execution, that requires a new ADR and peer review — do NOT
silently wire the label into an order path.

Design decision (2026-04-16):
  Polymarket has CLOB WSS channels, but whale tracking via WSS requires
  per-wallet auth we don't have. Market-channel WSS + filter-by-taker
  is an alternative but noisy (thousands of events/minute). Polling
  /trades?user=<addr>&limit=N per ranked wallet every 5-10s is simpler
  and adequate for measurement. Detection latency of 5-10s is fine for
  a MEASUREMENT bot (locked in as the permanent role).

Signal lifecycle:
  1. Each poll cycle fetches last N trades per ranked wallet.
  2. Dedup by transactionHash (primary key on Polymarket traders).
  3. For each NEW trade: compute signal_age_ms (now - whale_tx_ts),
     apply hypothetical Trigger filters, mark would_have_traded + reason.
  4. Persist to mirror_signals.

Downstream consumption is OPTIONAL (F-2 crowd_signals):
  Future daily rollup may populate `crowd_signals` as an opt-in
  down-weighter for Bot A/B candidate filters. Default-disabled.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from sqlalchemy import desc, select

from bots.bot_f.config import (
    DATA_API_URL,
    MIRROR_DEDUP_WINDOW_S,
    MIRROR_SIGNAL_MAX_AGE_S,
    TRIGGER_MAX_SPREAD_CENTS,
    TRIGGER_MIN_TTR_HOURS,
)
from bots.bot_f.db import (
    HunterRanking,
    MirrorSignal,
    get_bot_f_session_factory,
)

log = logging.getLogger(__name__)


# --- Load ranked wallets from latest Hunter run ---

def latest_ranked_wallets(
    session_factory,
    top_n: int = 40,
) -> list[tuple[str, str | None]]:
    """Return [(wallet, pseudonym)] from the most recent Hunter run."""
    with session_factory() as s:
        latest_run_id = s.scalar(
            select(HunterRanking.run_id)
            .order_by(desc(HunterRanking.created_at))
            .limit(1)
        )
        if latest_run_id is None:
            return []
        rows = list(
            s.scalars(
                select(HunterRanking)
                .where(HunterRanking.run_id == latest_run_id)
                .order_by(HunterRanking.rank)
                .limit(top_n)
            )
        )
    return [(r.wallet, r.pseudonym) for r in rows]


# --- Trade fetcher + signal extraction ---

@dataclass
class SignalCandidate:
    transaction_hash: str
    wallet: str
    pseudonym: str | None
    condition_id: str
    token_id: str
    side: str            # BUY | SELL
    price: float
    size: float
    whale_tx_ts: int     # unix seconds
    title: str
    slug: str
    event_slug: str
    outcome: str | None
    raw: dict


def fetch_recent_trades(
    client: httpx.Client,
    wallet: str,
    limit: int = 20,
) -> list[dict]:
    """Shallow /trades fetch per wallet — most recent N trades."""
    try:
        r = client.get(
            f"{DATA_API_URL}/trades",
            params={"user": wallet, "limit": limit},
            timeout=10.0,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        log.debug("mirror.fetch_failed wallet=%s err=%s", wallet[:12], e)
        return []


def extract_candidate(trade: dict, pseudonym: str | None) -> SignalCandidate | None:
    tx = trade.get("transactionHash")
    cid = trade.get("conditionId")
    asset = trade.get("asset")
    ts = trade.get("timestamp")
    side = (trade.get("side") or "").upper()
    wallet = trade.get("proxyWallet")
    if not all([tx, cid, asset, ts, side, wallet]):
        return None
    try:
        size = float(trade.get("size") or 0)
        price = float(trade.get("price") or 0)
        whale_ts = int(ts)
    except (TypeError, ValueError):
        return None
    if size <= 0 or price <= 0:
        return None
    return SignalCandidate(
        transaction_hash=tx,
        wallet=wallet,
        pseudonym=pseudonym,
        condition_id=cid,
        token_id=asset,
        side=side,
        price=price,
        size=size,
        whale_tx_ts=whale_ts,
        title=str(trade.get("title") or "")[:300],
        slug=str(trade.get("slug") or "")[:300],
        event_slug=str(trade.get("eventSlug") or "")[:300],
        outcome=trade.get("outcome"),
        raw=trade,
    )


# --- Hypothetical Trigger filters (measurement-only flagging) ---

def hypothetical_trigger_eval(
    sig: SignalCandidate,
    now_ts: int,
) -> tuple[bool, str | None]:
    """Would Phase-2 Trigger have placed an order on this signal?

    Measurement-only — does NOT actually trade. Records which signals would
    have been tradeable (useful metric for the 2-week go/no-go).
    Mirrors the Phase-2 filters that don't require live book depth.
    """
    signal_age_s = now_ts - sig.whale_tx_ts
    if signal_age_s > MIRROR_SIGNAL_MAX_AGE_S:
        return False, f"age {signal_age_s}s > {MIRROR_SIGNAL_MAX_AGE_S}s"
    # TTR unknown here — would need Gamma lookup. Phase 1 skips this check.
    # Spread check would require book snapshot — Phase 1 skips.
    # Only the clock-based checks are feasible for Mirror without adding
    # per-signal Gamma calls; we accept the approximation.
    return True, None


# --- Persistence ---

def signal_exists(session_factory, transaction_hash: str, token_id: str) -> bool:
    with session_factory() as s:
        existing = s.scalar(
            select(MirrorSignal.id).where(
                MirrorSignal.condition_id != "",
                MirrorSignal.raw_payload.like(f'%"{transaction_hash}"%'),
                MirrorSignal.token_id == token_id,
            ).limit(1)
        )
        return existing is not None


def record_signal(
    session_factory,
    sig: SignalCandidate,
    now_ts: int,
) -> None:
    would_trade, reject = hypothetical_trigger_eval(sig, now_ts)
    signal_age_ms = (now_ts - sig.whale_tx_ts) * 1000
    with session_factory() as s:
        s.add(
            MirrorSignal(
                detected_at=datetime.now(UTC),
                wallet=sig.wallet,
                condition_id=sig.condition_id,
                token_id=sig.token_id,
                side=sig.side,
                price=Decimal(str(sig.price)),
                size_shares=Decimal(str(sig.size)),
                whale_tx_ts=sig.whale_tx_ts,
                signal_age_ms=signal_age_ms,
                would_have_traded=1 if would_trade else 0,
                rejection_reason=reject,
                raw_payload=json.dumps({
                    "transactionHash": sig.transaction_hash,
                    "pseudonym": sig.pseudonym,
                    "title": sig.title,
                    "slug": sig.slug,
                    "event_slug": sig.event_slug,
                    "outcome": sig.outcome,
                }),
            )
        )
        s.commit()


# --- Daemon loop ---

@dataclass
class MirrorStats:
    cycles: int = 0
    polls: int = 0
    new_signals: int = 0
    duplicate_skips: int = 0
    errors: int = 0
    started_at: datetime | None = None


def run_mirror(
    poll_interval_s: int = 7,
    top_n: int = 40,
    trades_per_poll: int = 20,
    db_path: Path | None = None,
    max_cycles: int | None = None,
) -> MirrorStats:
    """Long-running daemon: poll ranked wallets, log new signals.

    Exit cleanly on KeyboardInterrupt / SIGTERM. Tracks stats returned on
    shutdown (useful in tests with max_cycles).
    """
    sf = get_bot_f_session_factory(db_path)
    stats = MirrorStats(started_at=datetime.now(UTC))
    wallets = latest_ranked_wallets(sf, top_n=top_n)
    if not wallets:
        log.error("mirror.no_hunter_run — run scripts/bot_f_hunter.py first")
        return stats
    log.info("mirror.start tracking_wallets=%d interval=%ds", len(wallets), poll_interval_s)

    # Per-wallet last-seen trade hash (in-memory cache — short-lived bot).
    seen_cache: dict[str, set[str]] = {w: set() for w, _ in wallets}

    with httpx.Client(timeout=15.0, headers={"User-Agent": "bot-f-mirror/0.1"}) as client:
        try:
            while True:
                stats.cycles += 1
                cycle_new = 0
                for wallet, pseudonym in wallets:
                    stats.polls += 1
                    trades = fetch_recent_trades(client, wallet, limit=trades_per_poll)
                    if not trades:
                        continue
                    now_ts = int(datetime.now(UTC).timestamp())
                    for t in trades:
                        sig = extract_candidate(t, pseudonym)
                        if sig is None:
                            continue
                        # In-memory dedup (fast path).
                        dedup_key = f"{sig.transaction_hash}:{sig.token_id}"
                        if dedup_key in seen_cache.get(wallet, set()):
                            stats.duplicate_skips += 1
                            continue
                        # Persistent dedup (survives restarts).
                        if signal_exists(sf, sig.transaction_hash, sig.token_id):
                            seen_cache.setdefault(wallet, set()).add(dedup_key)
                            stats.duplicate_skips += 1
                            continue
                        record_signal(sf, sig, now_ts)
                        seen_cache.setdefault(wallet, set()).add(dedup_key)
                        cycle_new += 1
                        stats.new_signals += 1
                    # Pacing between wallets.
                    time.sleep(0.05)

                if cycle_new:
                    log.info(
                        "mirror.cycle %d: %d new signals (total=%d)",
                        stats.cycles, cycle_new, stats.new_signals,
                    )
                elif stats.cycles % 10 == 0:
                    log.info(
                        "mirror.cycle %d: no new signals (dupes skipped=%d)",
                        stats.cycles, stats.duplicate_skips,
                    )
                if max_cycles and stats.cycles >= max_cycles:
                    break
                time.sleep(poll_interval_s)
        except KeyboardInterrupt:
            log.info("mirror.interrupt new_signals=%d cycles=%d", stats.new_signals, stats.cycles)
    return stats


# --- Reporting (for the 2-week go/no-go evaluation) ---

def mirror_summary(session_factory, since_hours: int | None = None) -> dict:
    """Aggregate metrics for the 2-week gate decision."""
    with session_factory() as s:
        stmt = select(MirrorSignal)
        if since_hours:
            from datetime import timedelta
            cutoff = datetime.now(UTC) - timedelta(hours=since_hours)
            stmt = stmt.where(MirrorSignal.detected_at >= cutoff)
        signals = list(s.scalars(stmt))

    if not signals:
        return {"total_signals": 0}

    ages = [s.signal_age_ms for s in signals if s.signal_age_ms is not None]
    by_wallet: dict[str, int] = {}
    by_side: dict[str, int] = {}
    would_trade_count = 0
    for s in signals:
        by_wallet[s.wallet] = by_wallet.get(s.wallet, 0) + 1
        by_side[s.side] = by_side.get(s.side, 0) + 1
        would_trade_count += int(s.would_have_traded or 0)

    # Latency percentiles.
    ages_sorted = sorted(ages) if ages else [0]
    p50 = ages_sorted[len(ages_sorted) // 2] if ages_sorted else 0
    p95 = ages_sorted[int(len(ages_sorted) * 0.95)] if ages_sorted else 0
    p99 = ages_sorted[int(len(ages_sorted) * 0.99)] if ages_sorted else 0

    # Diversification — top-wallet share.
    top_wallet_count = max(by_wallet.values()) if by_wallet else 0
    top_wallet_share = top_wallet_count / len(signals)

    return {
        "total_signals": len(signals),
        "unique_wallets": len(by_wallet),
        "by_side": by_side,
        "would_have_traded": would_trade_count,
        "would_trade_pct": round(100 * would_trade_count / len(signals), 2),
        "top_wallet_share": round(top_wallet_share, 3),
        "signal_age_ms": {
            "p50": p50, "p95": p95, "p99": p99,
            "min": min(ages) if ages else 0,
            "max": max(ages) if ages else 0,
        },
    }
