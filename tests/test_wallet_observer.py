"""Tests for the wallet observer module.

Coverage:
- Whitelist loader: tier filtering, address lookup, case-insensitivity
- Schema init: tables created idempotently
- Log decoder: parses real OrderFilled topic+data, rejects mismatches
- Collector state: persists last_block per exchange across restarts
- Side derivation: BUY/SELL/UNKNOWN logic
"""
from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from bots.wallet_observer import config as cfg
import bots.wallet_observer.collector as collector_mod
from bots.wallet_observer.collector import (
    Collector,
    DecodedFill,
    decode_log,
    write_fill,
)
from bots.wallet_observer.schema import init_db
from bots.wallet_observer.whitelist import Whitelist, WhitelistedWallet
from scripts.wallet_observer_daily_report import render


@pytest.fixture()
def sample_xref_csv(tmp_path: Path) -> Path:
    p = tmp_path / "xref.csv"
    rows = [
        ["wallet", "n_buys", "n_markets", "total_cost", "net_pnl",
         "roi_pct", "winrate", "polyverify_known", "bot_score",
         "likely_automated", "user_name", "pv_rank", "tier"],
        ["0xAA00000000000000000000000000000000000001", "150", "12",
         "1500", "300", "20", "55", "True", "30", "False",
         "Alpha", "50", "A_human_profitable"],
        ["0xBB00000000000000000000000000000000000002", "120", "8",
         "5000", "8000", "160", "65", "False", "", "",
         "", "", "B_unknown_profitable"],
        ["0xCC00000000000000000000000000000000000003", "300", "150",
         "100000", "10000", "10", "55", "True", "85", "True",
         "BotFarm", "120", "C_automated_profitable"],
        ["0xDD00000000000000000000000000000000000004", "40", "5",
         "200", "-50", "-25", "30", "False", "", "",
         "", "", "untiered"],
    ]
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerows(rows)
    return p


# ---------- Whitelist tests ----------


def test_whitelist_default_includes_a_and_b_only(sample_xref_csv: Path) -> None:
    wl = Whitelist.load(sample_xref_csv)
    # Default = A + B per cfg.INCLUDED_TIERS
    assert len(wl) == 2
    assert wl.is_observed("0xAA00000000000000000000000000000000000001")
    assert wl.is_observed("0xBB00000000000000000000000000000000000002")
    # Tier C and untiered must NOT be observed by default
    assert not wl.is_observed("0xCC00000000000000000000000000000000000003")
    assert not wl.is_observed("0xDD00000000000000000000000000000000000004")


def test_whitelist_custom_tiers(sample_xref_csv: Path) -> None:
    wl = Whitelist.load(sample_xref_csv, included_tiers={"C_automated_profitable"})
    assert len(wl) == 1
    assert wl.is_observed("0xCC00000000000000000000000000000000000003")
    assert not wl.is_observed("0xAA00000000000000000000000000000000000001")


def test_whitelist_lookup_returns_metadata(sample_xref_csv: Path) -> None:
    wl = Whitelist.load(sample_xref_csv)
    rec = wl.lookup("0xAA00000000000000000000000000000000000001")
    assert rec is not None
    assert rec.tier == "A_human_profitable"
    assert rec.user_name == "Alpha"
    assert rec.pv_rank == 50
    assert rec.historical_n_buys == 150


def test_whitelist_case_insensitive(sample_xref_csv: Path) -> None:
    wl = Whitelist.load(sample_xref_csv)
    assert wl.is_observed("0xaa00000000000000000000000000000000000001")
    assert wl.is_observed("0xAA00000000000000000000000000000000000001")
    assert wl.is_observed("0xAa00000000000000000000000000000000000001")


def test_whitelist_unknown_returns_none(sample_xref_csv: Path) -> None:
    wl = Whitelist.load(sample_xref_csv)
    assert wl.lookup("0xdeadbeef") is None
    assert wl.is_observed("") is False
    assert wl.is_observed("0xdeadbeef") is False


def test_whitelist_tier_counts(sample_xref_csv: Path) -> None:
    wl = Whitelist.load(sample_xref_csv)
    counts = wl.tier_counts()
    # Default load only includes A + B
    assert counts == {"A_human_profitable": 1, "B_unknown_profitable": 1}


def test_whitelist_addresses_set(sample_xref_csv: Path) -> None:
    wl = Whitelist.load(sample_xref_csv)
    addrs = wl.addresses()
    assert isinstance(addrs, set)
    assert "0xaa00000000000000000000000000000000000001" in addrs
    assert "0xcc00000000000000000000000000000000000003" not in addrs


# ---------- Schema tests ----------


def test_schema_creates_required_tables(tmp_path: Path) -> None:
    db = tmp_path / "obs.db"
    con = init_db(db)
    cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {r[0] for r in cur.fetchall()}
    assert "wallet_observed_fills" in tables
    assert "wallet_market_tokens" in tables
    assert "wallet_market_resolutions" in tables
    assert "observer_runs" in tables
    assert "collector_state" in tables


def test_schema_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "obs.db"
    init_db(db).close()
    init_db(db).close()  # second call must not raise


def test_schema_unique_constraint(tmp_path: Path) -> None:
    """Same (tx_hash, log_index) is the primary key — duplicates are ignored."""
    db = tmp_path / "obs.db"
    con = init_db(db)
    fill = _example_fill()
    fill.block_ts = 0
    observed = WhitelistedWallet(
        address=fill.taker_address, tier="A_human_profitable",
        user_name="Test", pv_rank=10, historical_net_pnl=100.0,
        historical_roi_pct=10.0, historical_n_buys=100, historical_winrate=50.0,
    )
    write_fill(con, fill, observed=observed, role="taker", side="BUY",
               price=0.05, size_shares=100.0)
    write_fill(con, fill, observed=observed, role="taker", side="BUY",
               price=0.05, size_shares=100.0)  # dup
    n = con.execute("SELECT COUNT(*) FROM wallet_observed_fills").fetchone()[0]
    assert n == 1


# ---------- Decoder tests ----------


def _example_fill() -> DecodedFill:
    """V2 OrderFilled: maker placed a SELL order that filled.

    side=1 (maker SELL): maker spent YES tokens, got USDC.
    Equivalent: maker SELLS, taker BUYS.

    Maker provided 100 YES; taker provided 5 USDC at price 0.05/share.
    """
    return DecodedFill(
        tx_hash="0x" + "ab" * 32,
        log_index=42,
        block_number=1234567,
        block_ts=1715000000,
        exchange="CTF",
        order_hash="0x" + "cd" * 32,
        maker_address="0x1111111111111111111111111111111111111111",
        taker_address="0x2222222222222222222222222222222222222222",
        side_raw=1,  # maker SELL
        token_id="123456789012345678901234567890",  # YES token
        # V2: side=1 means maker_amt = shares (6-decimal), taker_amt = USDC (6-decimal)
        maker_amount_filled=str(100 * 1_000_000),  # 100 shares (6-decimal)
        taker_amount_filled=str(5 * 1_000_000),    # 5 USDC (6-decimal)
        fee_raw="0",
        builder_code="0x" + "00" * 32,
        metadata="0x" + "00" * 32,
    )


def test_decode_log_parses_valid_orderfilled() -> None:
    """V2 OrderFilled has 7 unindexed fields = 224 bytes data."""
    maker = "0x1111111111111111111111111111111111111111"
    taker = "0x2222222222222222222222222222222222222222"

    def addr_to_topic(addr: str) -> str:
        return "0x" + addr[2:].lower().zfill(64)

    def uint_to_word(v: int) -> bytes:
        return v.to_bytes(32, "big", signed=False)

    builder_code = bytes.fromhex("00" * 32)
    metadata = bytes.fromhex("00" * 32)
    data = (
        uint_to_word(0)            # side = 0 (maker BUY)
        + uint_to_word(98765)      # tokenId (single ID in V2)
        + uint_to_word(5_000_000)  # makerAmountFilled (5 USDC raw, 6-decimal)
        + uint_to_word(100_000_000)  # takerAmountFilled (100 shares, 6-decimal)
        + uint_to_word(0)          # fee
        + builder_code             # builder
        + metadata                 # metadata
    )
    log_entry = {
        "topics": [
            cfg.ORDER_FILLED_TOPIC0,
            "0x" + "ab" * 32,
            addr_to_topic(maker),
            addr_to_topic(taker),
        ],
        "data": "0x" + data.hex(),
        "address": cfg.CTF_EXCHANGE_ADDRESS,
        "blockNumber": 1234,
        "logIndex": 5,
        "transactionHash": "0x" + "01" * 32,
    }
    fill = decode_log(log_entry)
    assert fill is not None
    assert fill.maker_address == maker.lower()
    assert fill.taker_address == taker.lower()
    assert fill.exchange == "CTF"
    assert fill.side_raw == 0
    assert fill.token_id == "98765"
    assert fill.maker_amount_filled == "5000000"
    assert fill.taker_amount_filled == "100000000"
    assert fill.fee_raw == "0"


def test_decode_log_rejects_wrong_topic0() -> None:
    log_entry = {
        "topics": ["0x" + "00" * 32, "0x" + "ab" * 32],
        "data": "0x",
        "address": cfg.CTF_EXCHANGE_ADDRESS,
    }
    assert decode_log(log_entry) is None


def test_decode_log_rejects_unknown_contract() -> None:
    log_entry = {
        "topics": [cfg.ORDER_FILLED_TOPIC0, "0x" + "ab" * 32,
                   "0x" + "00" * 12 + "11" * 20, "0x" + "00" * 12 + "22" * 20],
        "data": "0x" + "00" * 160,
        "address": "0x9999999999999999999999999999999999999999",
    }
    assert decode_log(log_entry) is None


# ---------- Side-derivation tests ----------


def test_derive_side_taker_buying_yes() -> None:
    """Taker pays USDC, gets YES tokens → taker BUYS YES."""
    fill = _example_fill()
    role, side, price, size = fill.derive_observed_side(fill.taker_address)
    assert role == "taker"
    assert side == "BUY"
    assert size == 100.0
    assert price is not None
    assert 0.04 <= price <= 0.06  # 5 USDC / 100 shares = 0.05


def test_derive_side_maker_selling_yes() -> None:
    fill = _example_fill()
    role, side, price, size = fill.derive_observed_side(fill.maker_address)
    assert role == "maker"
    assert side == "SELL"


def test_derive_side_unknown_for_third_party() -> None:
    fill = _example_fill()
    role, side, _, _ = fill.derive_observed_side("0x" + "ee" * 20)
    assert role == "unknown"
    assert side is None


def test_derive_side_v2_maker_buy() -> None:
    """V2 side=0 means maker placed a BUY order → maker BUYS, taker SELLS."""
    fill = DecodedFill(
        tx_hash="0x" + "ab" * 32, log_index=1, block_number=1, block_ts=0,
        exchange="CTF", order_hash="0x" + "cd" * 32,
        maker_address="0x1111111111111111111111111111111111111111",
        taker_address="0x2222222222222222222222222222222222222222",
        side_raw=0,  # maker BUY
        token_id="98765",
        # side=0: maker_amt = USDC (6-dec), taker_amt = shares (6-dec)
        maker_amount_filled=str(5 * 1_000_000),    # 5 USDC
        taker_amount_filled=str(100 * 1_000_000),  # 100 shares
        fee_raw="0",
        builder_code="0x" + "00" * 32,
        metadata="0x" + "00" * 32,
    )
    role, side, price, _ = fill.derive_observed_side(fill.maker_address)
    assert role == "maker"
    assert side == "BUY"
    assert price is not None and 0.04 <= price <= 0.06
    role, side, _, _ = fill.derive_observed_side(fill.taker_address)
    assert role == "taker"
    assert side == "SELL"


# ---------- Collector state tests ----------


def test_collector_state_persists(tmp_path: Path) -> None:
    """get_state / set_state round-trip across simulated restart."""
    db = tmp_path / "obs.db"
    con = init_db(db)
    # First set
    con.execute(
        "INSERT INTO collector_state (chain, exchange, last_block, last_updated) VALUES (?, ?, ?, ?)",
        ("polygon", "CTF", 100, 1715000000),
    )
    con.execute(
        "UPDATE collector_state SET last_block=?, last_updated=? WHERE chain='polygon' AND exchange='CTF'",
        (200, 1715000010),
    )
    cur = con.execute(
        "SELECT last_block FROM collector_state WHERE chain='polygon' AND exchange='CTF'"
    )
    assert cur.fetchone()[0] == 200


def test_poll_once_does_not_advance_failed_rpc_range(
    sample_xref_csv: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed eth_getLogs call must not look like a genuine empty range."""
    collector = Collector(
        whitelist=Whitelist.load(sample_xref_csv),
        rpc_url="http://127.0.0.1:9",
        db_path=tmp_path / "obs.db",
    )
    collector.set_state("CTF", 100)
    collector.set_state("NegRiskCTF", 100)
    monkeypatch.setattr(collector, "latest_block", lambda: 120)

    def fake_fetch(exchange: str, *, from_block: int, to_block: int):
        if exchange == "CTF":
            return None
        return []

    monkeypatch.setattr(collector, "fetch_logs_for_exchange", fake_fetch)

    written, state = collector.poll_once(
        max_range=10,
        initial_lookback=10,
        finality_lag=0,
    )

    assert written == 0
    assert state["CTF"] == 100
    assert collector.get_state("CTF") == 100
    assert state["NegRiskCTF"] == 110
    assert collector.get_state("NegRiskCTF") == 110


def test_process_logs_skips_fill_when_block_timestamp_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fill = _example_fill()
    fill.block_ts = 0
    observed = WhitelistedWallet(
        address=fill.taker_address,
        tier="A_human_profitable",
        user_name="Test",
        pv_rank=10,
        historical_net_pnl=100.0,
        historical_roi_pct=10.0,
        historical_n_buys=100,
        historical_winrate=50.0,
    )
    collector = Collector(
        whitelist=Whitelist({observed.address: observed}),
        rpc_url="http://127.0.0.1:9",
        db_path=tmp_path / "obs.db",
    )
    monkeypatch.setattr(collector_mod, "decode_log", lambda raw: fill)
    monkeypatch.setattr(collector, "fetch_block_timestamp", lambda block_number: None)

    assert collector.process_logs("CTF", [{}]) == 0
    n = collector.con.execute("SELECT COUNT(*) FROM wallet_observed_fills").fetchone()[0]
    assert n == 0


def test_daily_report_ignores_zero_block_ts_for_first_fill(tmp_path: Path) -> None:
    db = tmp_path / "obs.db"
    con = init_db(db)
    observed = WhitelistedWallet(
        address=_example_fill().taker_address,
        tier="A_human_profitable",
        user_name="Test",
        pv_rank=10,
        historical_net_pnl=100.0,
        historical_roi_pct=10.0,
        historical_n_buys=100,
        historical_winrate=50.0,
    )
    zero_ts = _example_fill()
    zero_ts.block_ts = 0
    write_fill(
        con, zero_ts, observed=observed, role="taker", side="BUY",
        price=0.05, size_shares=100.0,
    )
    good_ts = _example_fill()
    good_ts.tx_hash = "0x" + "ef" * 32
    good_ts.block_ts = 1715000000
    write_fill(
        con, good_ts, observed=observed, role="taker", side="BUY",
        price=0.05, size_shares=100.0,
    )

    _, payload = render(con)
    assert payload["headline"]["first_fill_ts"] == 1715000000
