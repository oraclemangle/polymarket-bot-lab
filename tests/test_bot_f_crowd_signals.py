"""Tests for bots/bot_f/crowd_signals — cascade detection + persistence.

Covers ADR-032 contract:
- Detects same-side flooding when >= min_wallets + min_notional within window_s
- Dominance filter rejects two-way flow
- Lookback window and order don't matter
- Persist is idempotent
- recent_cascade_for_market returns None outside lookback
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import sessionmaker

from bots.bot_f.crowd_signals import (
    CascadeDetection,
    detect_cascades,
    persist_cascades,
    recent_cascade_for_market,
)
from bots.bot_f.db import (
    BotFBase,
    CrowdCascade,
    MirrorSignal,
    get_bot_f_engine,
)


@pytest.fixture
def bot_f_sf(tmp_path):
    """Fresh Bot F SQLite DB per test."""
    db_path = tmp_path / "bot_f_test.db"
    engine = get_bot_f_engine(db_path)
    sf = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    yield sf
    engine.dispose()


def _insert_signal(
    sf,
    *,
    wallet: str,
    condition_id: str,
    side: str,
    price: float,
    size: float,
    whale_tx_ts: int,
    outcome: str = "Yes",
):
    with sf() as s:
        s.add(MirrorSignal(
            detected_at=datetime.fromtimestamp(whale_tx_ts, tz=UTC),
            wallet=wallet,
            condition_id=condition_id,
            token_id=f"tok_{condition_id}_{outcome}",
            side=side,
            price=Decimal(str(price)),
            size_shares=Decimal(str(size)),
            whale_tx_ts=whale_tx_ts,
            signal_age_ms=0,
            would_have_traded=0,
            rejection_reason=None,
            raw_payload=json.dumps({"outcome": outcome}),
        ))
        s.commit()


# --- Detection ---------------------------------------------------------


def test_empty_db_returns_no_cascades(bot_f_sf):
    assert detect_cascades(bot_f_sf) == []


def test_single_wallet_does_not_trigger_cascade(bot_f_sf):
    now_ts = int(datetime.now(UTC).timestamp())
    for i in range(10):
        _insert_signal(
            bot_f_sf, wallet="0xA", condition_id="M1", side="BUY",
            price=0.50, size=100.0, whale_tx_ts=now_ts - 120,
        )
    cascades = detect_cascades(bot_f_sf, min_wallets=6)
    assert cascades == []


def test_cascade_detected_when_thresholds_met(bot_f_sf):
    now_ts = int(datetime.now(UTC).timestamp())
    # 6 wallets, all BUY YES, same market, within 30s
    for i in range(6):
        _insert_signal(
            bot_f_sf,
            wallet=f"0x{i:040x}", condition_id="M1", side="BUY",
            price=0.20, size=200.0, whale_tx_ts=now_ts - 3600 + i * 5,
            outcome="Yes",
        )
    cascades = detect_cascades(
        bot_f_sf, min_wallets=6, min_gross_usd=200.0, dominance_ratio=2.0,
    )
    assert len(cascades) == 1
    c = cascades[0]
    assert c.market_id == "M1"
    assert c.dominant_side == "BUY_YES"
    assert c.n_wallets == 6
    assert c.gross_usd == pytest.approx(6 * 0.20 * 200.0)
    assert c.dominant_ratio == pytest.approx(1.0)


def test_two_way_flow_fails_dominance(bot_f_sf):
    """3 BUY and 3 SELL on same market — not dominant in either direction."""
    now_ts = int(datetime.now(UTC).timestamp())
    for i in range(3):
        _insert_signal(
            bot_f_sf, wallet=f"0xA{i:040x}", condition_id="M1", side="BUY",
            price=0.30, size=300.0, whale_tx_ts=now_ts - 1800 + i,
            outcome="Yes",
        )
    for i in range(3):
        _insert_signal(
            bot_f_sf, wallet=f"0xB{i:040x}", condition_id="M1", side="SELL",
            price=0.30, size=300.0, whale_tx_ts=now_ts - 1800 + i + 3,
            outcome="Yes",
        )
    cascades = detect_cascades(bot_f_sf, min_wallets=6, dominance_ratio=2.0)
    # 6 wallets total but two-sided — no dominant side
    assert cascades == []


def test_cascade_notional_below_threshold_rejected(bot_f_sf):
    now_ts = int(datetime.now(UTC).timestamp())
    # 6 wallets but tiny notional each
    for i in range(6):
        _insert_signal(
            bot_f_sf, wallet=f"0x{i:040x}", condition_id="M1", side="BUY",
            price=0.10, size=10.0, whale_tx_ts=now_ts - 1000 + i,
            outcome="Yes",
        )
    cascades = detect_cascades(bot_f_sf, min_wallets=6, min_gross_usd=500.0)
    # 6 * 0.10 * 10 = $6 total — below $500
    assert cascades == []


def test_cascades_outside_window_not_merged(bot_f_sf):
    """Two separate clusters > window_s apart — each can be its own cascade,
    but per-side deduplication keeps only the largest per market+side."""
    now_ts = int(datetime.now(UTC).timestamp())
    # Cluster A: 6 BUY_YES wallets
    for i in range(6):
        _insert_signal(
            bot_f_sf, wallet=f"0xA{i:040x}", condition_id="M1", side="BUY",
            price=0.20, size=200.0, whale_tx_ts=now_ts - 3000 + i,
            outcome="Yes",
        )
    # Cluster B: 6 BUY_YES wallets 600s later, smaller notional
    for i in range(6):
        _insert_signal(
            bot_f_sf, wallet=f"0xB{i:040x}", condition_id="M1", side="BUY",
            price=0.10, size=100.0, whale_tx_ts=now_ts - 2400 + i,
            outcome="Yes",
        )
    cascades = detect_cascades(
        bot_f_sf, min_wallets=6, min_gross_usd=100.0, dominance_ratio=1.5,
    )
    # Per-side dedup — we keep only the larger cluster A (notional 6*0.20*200=240)
    assert len(cascades) == 1
    assert cascades[0].gross_usd == pytest.approx(240.0)


def test_lookback_hours_respected(bot_f_sf):
    """Signals older than `lookback_hours` are ignored."""
    now = datetime.now(UTC)
    now_ts = int(now.timestamp())
    # 6 signals 48h old
    for i in range(6):
        _insert_signal(
            bot_f_sf, wallet=f"0x{i:040x}", condition_id="M1", side="BUY",
            price=0.20, size=200.0, whale_tx_ts=now_ts - 48 * 3600 + i,
            outcome="Yes",
        )
    cascades = detect_cascades(
        bot_f_sf, lookback_hours=24, min_wallets=6, min_gross_usd=100.0,
        now=now,
    )
    # Also need to backfill the detected_at — we set detected_at from
    # whale_tx_ts in _insert_signal, so these rows are also 48h old
    assert cascades == []


def test_cascade_across_two_markets(bot_f_sf):
    now_ts = int(datetime.now(UTC).timestamp())
    # Market 1: 6 BUY_YES
    for i in range(6):
        _insert_signal(
            bot_f_sf, wallet=f"0xM1{i:038x}", condition_id="M1", side="BUY",
            price=0.20, size=200.0, whale_tx_ts=now_ts - 3000 + i,
            outcome="Yes",
        )
    # Market 2: 6 SELL_NO
    for i in range(6):
        _insert_signal(
            bot_f_sf, wallet=f"0xM2{i:038x}", condition_id="M2", side="SELL",
            price=0.30, size=150.0, whale_tx_ts=now_ts - 2500 + i,
            outcome="No",
        )
    cascades = detect_cascades(
        bot_f_sf, min_wallets=6, min_gross_usd=100.0, dominance_ratio=1.5,
    )
    assert len(cascades) == 2
    by_market = {c.market_id: c for c in cascades}
    assert by_market["M1"].dominant_side == "BUY_YES"
    assert by_market["M2"].dominant_side == "SELL_NO"


# --- Persistence -------------------------------------------------------


def test_persist_cascades_writes_rows(bot_f_sf):
    now = datetime.now(UTC)
    cascades = [
        CascadeDetection(
            market_id="M1",
            cascade_start_ts=int(now.timestamp()) - 100,
            cascade_end_ts=int(now.timestamp()) - 40,
            n_wallets=6,
            dominant_side="BUY_YES",
            gross_usd=500.0,
            dominant_ratio=0.9,
        ),
    ]
    n = persist_cascades(bot_f_sf, cascades, now=now)
    assert n == 1
    with bot_f_sf() as s:
        rows = list(s.scalars(__import__("sqlalchemy").select(CrowdCascade)))
    assert len(rows) == 1
    assert rows[0].market_id == "M1"
    assert rows[0].dominant_side == "BUY_YES"


def test_persist_cascades_is_idempotent(bot_f_sf):
    now = datetime.now(UTC)
    cascades = [
        CascadeDetection(
            market_id="M1",
            cascade_start_ts=int(now.timestamp()) - 100,
            cascade_end_ts=int(now.timestamp()) - 40,
            n_wallets=6,
            dominant_side="BUY_YES",
            gross_usd=500.0,
            dominant_ratio=0.9,
        ),
    ]
    # Write twice; second call should be a no-op
    n1 = persist_cascades(bot_f_sf, cascades, now=now)
    n2 = persist_cascades(bot_f_sf, cascades, now=now)
    assert n1 == 1
    assert n2 == 0
    with bot_f_sf() as s:
        rows = list(s.scalars(__import__("sqlalchemy").select(CrowdCascade)))
    assert len(rows) == 1


# --- recent_cascade_for_market --------------------------------------


def test_recent_cascade_returns_none_when_empty(bot_f_sf):
    assert recent_cascade_for_market(bot_f_sf, "M1", within_hours=6) is None


def test_recent_cascade_returns_recent(bot_f_sf):
    now = datetime.now(UTC)
    # Insert a cascade detected 1 hour ago
    recent_detected = now - timedelta(hours=1)
    with bot_f_sf() as s:
        s.add(CrowdCascade(
            detected_at=recent_detected,
            market_id="M1",
            cascade_start_ts=int(recent_detected.timestamp()) - 60,
            cascade_end_ts=int(recent_detected.timestamp()),
            n_wallets=6,
            dominant_side="BUY_YES",
            gross_usd=500.0,
            dominant_ratio=0.9,
        ))
        s.commit()
    result = recent_cascade_for_market(bot_f_sf, "M1", within_hours=6, now=now)
    assert result is not None
    assert result.market_id == "M1"
    assert result.dominant_side == "BUY_YES"


def test_recent_cascade_ignores_old_cascades(bot_f_sf):
    now = datetime.now(UTC)
    # Insert cascade detected 12h ago
    old_detected = now - timedelta(hours=12)
    with bot_f_sf() as s:
        s.add(CrowdCascade(
            detected_at=old_detected,
            market_id="M1",
            cascade_start_ts=int(old_detected.timestamp()) - 60,
            cascade_end_ts=int(old_detected.timestamp()),
            n_wallets=6,
            dominant_side="BUY_YES",
            gross_usd=500.0,
            dominant_ratio=0.9,
        ))
        s.commit()
    result = recent_cascade_for_market(bot_f_sf, "M1", within_hours=6, now=now)
    assert result is None
