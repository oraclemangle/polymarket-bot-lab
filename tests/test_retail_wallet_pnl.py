"""Tests for core/retail_wallet_pnl.py — WANGZJ-derived retail-tier PnL."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from core.retail_wallet_pnl import (
    ALL_TIERS,
    TIER_A,
    TIER_B,
    TIER_C,
    TIER_UNTIERED,
    RetailWalletPnL,
    load_default,
)


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    p = tmp_path / "xref.csv"
    rows = [
        ["wallet", "n_buys", "n_markets", "total_cost", "net_pnl",
         "roi_pct", "winrate", "polyverify_known", "bot_score",
         "likely_automated", "user_name", "pv_rank", "tier"],
        # Tier A: human + profitable
        ["0xAA00000000000000000000000000000000000001", "150", "12",
         "1500", "300", "20", "55", "True", "30", "False",
         "SmartHuman", "50", TIER_A],
        # Tier B: outside PolyVerify, high ROI
        ["0xBB00000000000000000000000000000000000002", "120", "8",
         "5000", "8000", "160", "65", "False", "", "",
         "", "", TIER_B],
        # Tier C: known bot
        ["0xCC00000000000000000000000000000000000003", "300", "150",
         "100000", "10000", "10", "55", "True", "85", "True",
         "BotFarm", "120", TIER_C],
        # Untiered
        ["0xDD00000000000000000000000000000000000004", "40", "5",
         "200", "-50", "-25", "30", "False", "", "",
         "", "", TIER_UNTIERED],
    ]
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)
    return p


def test_load_parses_all_tiers(sample_csv: Path) -> None:
    pnl = RetailWalletPnL.load(sample_csv)
    assert len(pnl) == 4
    a = pnl.lookup("0xAA00000000000000000000000000000000000001")
    assert a is not None
    assert a.user_name == "SmartHuman"
    assert a.tier == TIER_A
    assert a.is_human_profitable is True
    assert a.is_smart_money is True
    assert a.bot_score == 30
    assert a.likely_automated is False


def test_tier_helpers(sample_csv: Path) -> None:
    pnl = RetailWalletPnL.load(sample_csv)
    assert pnl.tier("0xAA00000000000000000000000000000000000001") == TIER_A
    assert pnl.tier("0xBB00000000000000000000000000000000000002") == TIER_B
    assert pnl.tier("0xCC00000000000000000000000000000000000003") == TIER_C
    assert pnl.tier("0xDD00000000000000000000000000000000000004") == TIER_UNTIERED
    assert pnl.tier("0xnotfound") is None


def test_smart_money_combines_a_and_b(sample_csv: Path) -> None:
    pnl = RetailWalletPnL.load(sample_csv)
    assert pnl.is_smart_money("0xAA00000000000000000000000000000000000001") is True
    assert pnl.is_smart_money("0xBB00000000000000000000000000000000000002") is True
    assert pnl.is_smart_money("0xCC00000000000000000000000000000000000003") is False
    assert pnl.is_smart_money("0xDD00000000000000000000000000000000000004") is False


def test_known_bot_only_tier_c(sample_csv: Path) -> None:
    pnl = RetailWalletPnL.load(sample_csv)
    assert pnl.is_known_bot("0xCC00000000000000000000000000000000000003") is True
    for w in [
        "0xAA00000000000000000000000000000000000001",
        "0xBB00000000000000000000000000000000000002",
        "0xDD00000000000000000000000000000000000004",
    ]:
        assert pnl.is_known_bot(w) is False


def test_by_tier_returns_correct_subsets(sample_csv: Path) -> None:
    pnl = RetailWalletPnL.load(sample_csv)
    a = pnl.by_tier(TIER_A)
    b = pnl.by_tier(TIER_B)
    c = pnl.by_tier(TIER_C)
    untiered = pnl.by_tier(TIER_UNTIERED)
    assert len(a) == 1
    assert len(b) == 1
    assert len(c) == 1
    assert len(untiered) == 1


def test_tier_count(sample_csv: Path) -> None:
    pnl = RetailWalletPnL.load(sample_csv)
    counts = pnl.tier_count()
    assert counts == {
        TIER_A: 1,
        TIER_B: 1,
        TIER_C: 1,
        TIER_UNTIERED: 1,
    }


def test_filter_combines_criteria(sample_csv: Path) -> None:
    pnl = RetailWalletPnL.load(sample_csv)
    smart_high_roi = pnl.filter(min_roi_pct=100)
    # Only Tier B has ROI > 100%
    assert len(smart_high_roi) == 1
    assert smart_high_roi[0].tier == TIER_B

    a_only = pnl.filter(tier=TIER_A)
    assert len(a_only) == 1
    assert a_only[0].user_name == "SmartHuman"


def test_lookup_case_insensitive(sample_csv: Path) -> None:
    pnl = RetailWalletPnL.load(sample_csv)
    upper = pnl.lookup("0xAA00000000000000000000000000000000000001")
    lower = pnl.lookup("0xaa00000000000000000000000000000000000001")
    assert upper == lower


def test_invalid_tier_falls_back_to_untiered(tmp_path: Path) -> None:
    p = tmp_path / "xref.csv"
    rows = [
        ["wallet", "n_buys", "n_markets", "total_cost", "net_pnl",
         "roi_pct", "winrate", "polyverify_known", "bot_score",
         "likely_automated", "user_name", "pv_rank", "tier"],
        ["0xAA00", "10", "1", "100", "0", "0", "50", "False", "", "",
         "", "", "BOGUS_TIER"],
    ]
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)
    pnl = RetailWalletPnL.load(p)
    r = pnl.lookup("0xAA00")
    assert r is not None
    assert r.tier == TIER_UNTIERED


def test_load_default_smoke() -> None:
    """Smoke test against the actual checked-in CSV."""
    pnl = load_default()
    assert len(pnl) == 500  # 500 retail-tier wallets in xref CSV
    counts = pnl.tier_count()
    assert counts[TIER_A] >= 80   # ~97 in the actual data
    assert counts[TIER_B] >= 100  # ~148
    assert counts[TIER_C] >= 20   # ~29
    assert counts[TIER_A] + counts[TIER_B] + counts[TIER_C] + counts[TIER_UNTIERED] == 500


def test_load_default_caches() -> None:
    a = load_default()
    b = load_default()
    assert a is b


def test_known_smart_money_smoke() -> None:
    """Verify a known Tier A wallet from the actual CSV."""
    pnl = load_default()
    # swisstony — top retail by absolute PnL, PolyVerify rank 7
    swisstony = pnl.lookup("0xF00D00000000000000000000000000000000000e")
    assert swisstony is not None
    assert swisstony.tier == TIER_A
    assert swisstony.user_name == "swisstony"
    assert swisstony.net_pnl > 1_000_000
