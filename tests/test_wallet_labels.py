"""Tests for core/wallet_labels.py — PolyVerify CSV lookup."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from core.wallet_labels import WalletLabel, WalletLabels, load_default


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    p = tmp_path / "wallets.csv"
    rows = [
        ["rank", "proxyWallet", "userName", "vol", "pnl",
         "botScore", "botConfidence", "likelyAutomated", "tags"],
        ["1", "0xAA00000000000000000000000000000000000001", "TopProf",
         "10000000", "5000000", "30", "low", "False", ""],
        ["2", "0xBB00000000000000000000000000000000000002", "Botty",
         "8000000", "1000000", "85", "high", "True", "scalper"],
        ["3", "0xCC00000000000000000000000000000000000003", "MidPlayer",
         "5000000", "200000", "67", "medium", "True", ""],
        ["4", "0xDD00000000000000000000000000000000000004", "LossPlayer",
         "1000000", "-300000", "30", "low", "False", ""],
    ]
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)
    return p


def test_load_parses_all_columns(sample_csv: Path) -> None:
    labels = WalletLabels.load(sample_csv)
    assert len(labels) == 4
    botty = labels.lookup("0xBB00000000000000000000000000000000000002")
    assert botty is not None
    assert botty.user_name == "Botty"
    assert botty.bot_score == 85
    assert botty.bot_confidence == "high"
    assert botty.likely_automated is True
    assert botty.pnl_usd == 1_000_000
    assert botty.rank == 2
    assert botty.tags == "scalper"


def test_lookup_is_case_insensitive(sample_csv: Path) -> None:
    labels = WalletLabels.load(sample_csv)
    upper = labels.lookup("0xAA00000000000000000000000000000000000001")
    lower = labels.lookup("0xaa00000000000000000000000000000000000001")
    mixed = labels.lookup("0xAa00000000000000000000000000000000000001")
    assert upper is not None
    assert upper == lower == mixed


def test_lookup_returns_none_for_unknown(sample_csv: Path) -> None:
    labels = WalletLabels.load(sample_csv)
    assert labels.lookup("0xdeadbeef") is None
    assert labels.lookup("") is None
    assert labels.is_likely_automated("0xdeadbeef") is False
    assert labels.is_known("0xdeadbeef") is False
    assert labels.bot_score("0xdeadbeef") is None


def test_helper_methods(sample_csv: Path) -> None:
    labels = WalletLabels.load(sample_csv)
    assert labels.is_likely_automated("0xBB00000000000000000000000000000000000002") is True
    assert labels.is_likely_automated("0xAA00000000000000000000000000000000000001") is False
    assert labels.is_high_confidence_bot("0xBB00000000000000000000000000000000000002") is True
    assert labels.is_high_confidence_bot("0xCC00000000000000000000000000000000000003") is False
    assert labels.is_top_100("0xAA00000000000000000000000000000000000001") is True
    assert labels.bot_score("0xCC00000000000000000000000000000000000003") == 67


def test_filter(sample_csv: Path) -> None:
    labels = WalletLabels.load(sample_csv)

    automated = labels.filter(likely_automated=True)
    assert len(automated) == 2
    assert {w.user_name for w in automated} == {"Botty", "MidPlayer"}

    profitable = labels.filter(min_pnl_usd=100_000)
    assert len(profitable) == 3  # excludes LossPlayer

    high_conf = labels.filter(bot_confidence="high")
    assert len(high_conf) == 1
    assert high_conf[0].user_name == "Botty"


def test_stats(sample_csv: Path) -> None:
    labels = WalletLabels.load(sample_csv)
    s = labels.stats()
    assert s["total"] == 4
    assert s["likely_automated"] == 2
    assert s["high_confidence_bots"] == 1
    assert s["positive_pnl_wallets"] == 3


def test_load_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        WalletLabels.load(tmp_path / "missing.csv")


def test_skips_malformed_rows(tmp_path: Path) -> None:
    p = tmp_path / "wallets.csv"
    rows = [
        ["rank", "proxyWallet", "userName", "vol", "pnl",
         "botScore", "botConfidence", "likelyAutomated", "tags"],
        ["1", "0xAA00", "GoodWallet", "100", "50", "30", "low", "False", ""],
        ["2", "", "Empty", "0", "0", "0", "low", "False", ""],
        ["3", "not-a-hex-address", "Bad", "0", "0", "0", "low", "False", ""],
        ["4", "0xBB00", "GoodWallet2", "abc", "xyz", "?", "low", "?", ""],
    ]
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)
    labels = WalletLabels.load(p)
    # rows 1 and 4 should load (4 with coerced 0 values for malformed numeric fields);
    # row 2 (empty wallet) and row 3 (non-0x prefix) should be skipped
    assert len(labels) == 2
    bad = labels.lookup("0xBB00")
    assert bad is not None
    assert bad.volume_usd == 0
    assert bad.pnl_usd == 0
    assert bad.bot_score == 0
    assert bad.likely_automated is False  # "?" coerced to False


def test_load_default_uses_repo_csv() -> None:
    """Smoke test against the actual checked-in PolyVerify CSV.

    The source CSV has 1000 rows but contains one duplicate wallet
    (`0x130dfd2b...` appears at both an earlier rank and rank 976), so
    the loaded set has 999 unique wallets — last-write-wins by design.
    """
    labels = load_default()
    assert len(labels) == 999
    s = labels.stats()
    # 194 flagged in source; could be 193 or 194 in the deduped set
    # depending on which version of the duplicate row wins.
    assert 193 <= s["likely_automated"] <= 194
    assert s["total"] == 999


def test_load_default_caches() -> None:
    """Repeated calls return the same instance."""
    a = load_default()
    b = load_default()
    assert a is b


def test_known_wallet_smoke() -> None:
    """Verify a known top-rank wallet from the actual CSV."""
    labels = load_default()
    theo = labels.lookup("0xF00D000000000000000000000000000000000009")
    assert theo is not None
    assert theo.user_name == "Theo4"
    assert theo.rank == 1
    assert theo.likely_automated is False
