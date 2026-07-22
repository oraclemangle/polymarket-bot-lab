"""Tests for Bot F Mirror — signal extraction + dedup + filter eval.

Does NOT test network calls; those are exercised by the CLI.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from bots.bot_f.db import (
    HunterRanking,
    MirrorSignal,
    get_bot_f_session_factory,
)
from bots.bot_f.signal import (
    SignalCandidate,
    extract_candidate,
    hypothetical_trigger_eval,
    latest_ranked_wallets,
    mirror_summary,
    record_signal,
    signal_exists,
)


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "bot_f.db"


def _seed_hunter_run(sf, run_id: str, wallets: list[tuple[str, str]]) -> None:
    with sf() as s:
        for rank, (w, name) in enumerate(wallets, start=1):
            s.add(
                HunterRanking(
                    run_id=run_id,
                    rank=rank,
                    wallet=w,
                    pseudonym=name,
                    trade_count=100,
                    win_rate=0.7,
                    profit_factor=2.0,
                    sharpe=1.0,
                    realised_pnl_usd=1000.0,
                    total_notional_usd=5000.0,
                    recent_edge_ratio=1.1,
                    p7d_share=0.6,
                    top_categories="sports",
                    created_at=datetime.now(UTC),
                )
            )
        s.commit()


def test_latest_ranked_wallets_returns_latest_run(tmp_db):
    sf = get_bot_f_session_factory(tmp_db)
    _seed_hunter_run(sf, "old", [("0xa", "alice"), ("0xb", "bob")])
    # New run with different wallets overrides.
    _seed_hunter_run(sf, "new", [("0xc", "carol"), ("0xd", "dave"), ("0xe", "eve")])
    result = latest_ranked_wallets(sf, top_n=10)
    assert [w for w, _ in result] == ["0xc", "0xd", "0xe"]


def test_extract_candidate_valid_trade():
    trade = {
        "transactionHash": "0xabc123",
        "conditionId": "0xcid",
        "asset": "token_1",
        "timestamp": 1700000000,
        "side": "BUY",
        "proxyWallet": "0xwallet",
        "size": 10.5,
        "price": 0.42,
        "title": "Will X happen?",
        "slug": "x-happen",
        "eventSlug": "event-slug",
        "outcome": "Yes",
    }
    sig = extract_candidate(trade, pseudonym="whale1")
    assert sig is not None
    assert sig.transaction_hash == "0xabc123"
    assert sig.side == "BUY"
    assert sig.size == 10.5
    assert sig.price == 0.42
    assert sig.pseudonym == "whale1"


def test_extract_candidate_rejects_missing_fields():
    # Missing proxyWallet
    trade = {"transactionHash": "0x1", "conditionId": "c", "asset": "a",
             "timestamp": 1, "side": "BUY"}
    assert extract_candidate(trade, None) is None
    # Zero size
    trade2 = {"transactionHash": "0x1", "conditionId": "c", "asset": "a",
              "timestamp": 1, "side": "BUY", "proxyWallet": "w", "size": 0, "price": 0.5}
    assert extract_candidate(trade2, None) is None


def test_hypothetical_trigger_accepts_fresh_signal():
    sig = SignalCandidate(
        transaction_hash="0x1", wallet="0xw", pseudonym=None,
        condition_id="c", token_id="t", side="BUY",
        price=0.5, size=10.0, whale_tx_ts=1700000000,
        title="q", slug="s", event_slug="e", outcome=None, raw={},
    )
    now = sig.whale_tx_ts + 30  # 30s old
    ok, reason = hypothetical_trigger_eval(sig, now)
    assert ok is True
    assert reason is None


def test_hypothetical_trigger_rejects_stale_signal():
    sig = SignalCandidate(
        transaction_hash="0x1", wallet="0xw", pseudonym=None,
        condition_id="c", token_id="t", side="BUY",
        price=0.5, size=10.0, whale_tx_ts=1700000000,
        title="q", slug="s", event_slug="e", outcome=None, raw={},
    )
    now = sig.whale_tx_ts + 200  # way past MIRROR_SIGNAL_MAX_AGE_S=90
    ok, reason = hypothetical_trigger_eval(sig, now)
    assert ok is False
    assert "age" in reason


def test_record_signal_and_dedup(tmp_db):
    sf = get_bot_f_session_factory(tmp_db)
    sig = SignalCandidate(
        transaction_hash="0xtx1", wallet="0xw", pseudonym="test",
        condition_id="cid1", token_id="tok1", side="BUY",
        price=0.42, size=100.0, whale_tx_ts=int(datetime.now(UTC).timestamp()) - 5,
        title="q", slug="s", event_slug="e", outcome="Yes", raw={},
    )
    now = int(datetime.now(UTC).timestamp())
    record_signal(sf, sig, now)
    # Second call (dedup on tx hash) should NOT create a duplicate.
    assert signal_exists(sf, "0xtx1", "tok1") is True
    # Different token — not a dup.
    assert signal_exists(sf, "0xtx1", "tok_other") is False


def test_mirror_summary_empty(tmp_db):
    sf = get_bot_f_session_factory(tmp_db)
    assert mirror_summary(sf) == {"total_signals": 0}


def test_mirror_summary_aggregates(tmp_db):
    sf = get_bot_f_session_factory(tmp_db)
    now = int(datetime.now(UTC).timestamp())
    # Record 3 signals from 2 wallets.
    for i, (w, name) in enumerate([("0xa", "alice"), ("0xa", "alice"), ("0xb", "bob")]):
        sig = SignalCandidate(
            transaction_hash=f"0xtx{i}", wallet=w, pseudonym=name,
            condition_id=f"c{i}", token_id=f"t{i}",
            side="BUY" if i < 2 else "SELL",
            price=0.5, size=10.0, whale_tx_ts=now - 20,
            title="q", slug="s", event_slug="e", outcome=None, raw={},
        )
        record_signal(sf, sig, now)
    summary = mirror_summary(sf)
    assert summary["total_signals"] == 3
    assert summary["unique_wallets"] == 2
    assert summary["by_side"]["BUY"] == 2
    assert summary["by_side"]["SELL"] == 1
    assert summary["would_have_traded"] == 3  # all fresh enough
    # Alice has 2/3 = 0.667 of signals
    assert summary["top_wallet_share"] == pytest.approx(0.667, abs=0.01)
