"""Tests for scripts/bot_e_extract_features.py.

Focused on the bridge logic: SignalContext construction from a synthetic
recorder DB, and CSV serialisation. Signal reconstruction itself is
covered by tests of bot_e_calibration_spike's primitives (separate
module); we don't re-prove that here.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

# Ensure we can import siblings under scripts/.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_SPEC = importlib.util.spec_from_file_location(
    "bot_e_extract_features",
    REPO_ROOT / "scripts" / "bot_e_extract_features.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["bot_e_extract_features"] = _mod
_SPEC.loader.exec_module(_mod)


def _build_db(tmp_path: Path) -> Path:
    db = tmp_path / "rec.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE pm_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at_ms INTEGER NOT NULL,
            subscription_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            asset_id TEXT,
            condition_id TEXT,
            payload_json TEXT NOT NULL
        );
        CREATE TABLE cex_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at_ms INTEGER NOT NULL,
            trade_time_ms INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            price REAL NOT NULL,
            size REAL NOT NULL,
            is_buyer_maker INTEGER NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    return db


def _add_pm_lastprice(db: Path, *, ts: int, sub_id: str, asset_id: str,
                     price: float, size: float = 10.0):
    conn = sqlite3.connect(str(db))
    payload = json.dumps({"asset_id": asset_id, "price": price, "size": size})
    conn.execute(
        "INSERT INTO pm_events "
        "(received_at_ms, subscription_id, event_type, asset_id, payload_json) "
        "VALUES (?, ?, 'last_trade_price', ?, ?)",
        (ts, sub_id, asset_id, payload),
    )
    conn.commit()
    conn.close()


def _add_cex(db: Path, *, ts: int, symbol: str, price: float,
             size: float = 0.01, is_buyer_maker: int = 0):
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO cex_trades "
        "(received_at_ms, trade_time_ms, symbol, price, size, is_buyer_maker) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ts, ts, symbol, price, size, is_buyer_maker),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestSymbolFromSubId:
    @pytest.mark.parametrize("sub_id, expected", [
        ("btc-20260425T2300", "BTC"),
        ("eth-20260425T2300", "ETH"),
        ("sol-20260425T2300", "SOL"),
        ("BTC-20260425T2300", "BTC"),
        ("xrp-20260425T2300", ""),  # unsupported symbol
        ("", ""),
    ])
    def test_extracts_symbol(self, sub_id, expected):
        assert _mod._symbol_from_sub_id(sub_id) == expected


# ---------------------------------------------------------------------------
# DB-backed helpers
# ---------------------------------------------------------------------------

class TestLastTradePrice:
    def test_returns_most_recent_at_or_before(self, tmp_path: Path):
        db = _build_db(tmp_path)
        _add_pm_lastprice(db, ts=1000, sub_id="s", asset_id="a", price=0.45)
        _add_pm_lastprice(db, ts=2000, sub_id="s", asset_id="a", price=0.50)
        _add_pm_lastprice(db, ts=3000, sub_id="s", asset_id="a", price=0.55)

        conn = sqlite3.connect(str(db))
        try:
            assert _mod._last_trade_price_at_or_before(
                conn, sub_id="s", asset_id="a", t0_ms=2500,
            ) == 0.50
            assert _mod._last_trade_price_at_or_before(
                conn, sub_id="s", asset_id="a", t0_ms=4000,
            ) == 0.55
            # Future-leak guard: t0 before any event → None
            assert _mod._last_trade_price_at_or_before(
                conn, sub_id="s", asset_id="a", t0_ms=500,
            ) is None
        finally:
            conn.close()

    def test_isolates_by_asset_id(self, tmp_path: Path):
        db = _build_db(tmp_path)
        _add_pm_lastprice(db, ts=1000, sub_id="s", asset_id="yes", price=0.40)
        _add_pm_lastprice(db, ts=1000, sub_id="s", asset_id="no", price=0.60)
        conn = sqlite3.connect(str(db))
        try:
            assert _mod._last_trade_price_at_or_before(
                conn, sub_id="s", asset_id="yes", t0_ms=2000,
            ) == 0.40
            assert _mod._last_trade_price_at_or_before(
                conn, sub_id="s", asset_id="no", t0_ms=2000,
            ) == 0.60
        finally:
            conn.close()

    def test_returns_none_for_zero_price(self, tmp_path: Path):
        db = _build_db(tmp_path)
        _add_pm_lastprice(db, ts=1000, sub_id="s", asset_id="a", price=0.0)
        conn = sqlite3.connect(str(db))
        try:
            assert _mod._last_trade_price_at_or_before(
                conn, sub_id="s", asset_id="a", t0_ms=2000,
            ) is None
        finally:
            conn.close()

    def test_returns_none_for_missing_asset(self, tmp_path: Path):
        db = _build_db(tmp_path)
        conn = sqlite3.connect(str(db))
        try:
            assert _mod._last_trade_price_at_or_before(
                conn, sub_id="s", asset_id=None, t0_ms=2000,
            ) is None
        finally:
            conn.close()


class TestLoadCexTradesUpTo:
    def test_includes_only_at_or_before_t0(self, tmp_path: Path):
        db = _build_db(tmp_path)
        for ts, p in [(1000, 50000), (2000, 50100), (3000, 50200), (4000, 50300)]:
            _add_cex(db, ts=ts, symbol="BTCUSDT", price=p)
        conn = sqlite3.connect(str(db))
        try:
            ticks = _mod._load_cex_trades_up_to(
                conn, "BTCUSDT", t0_ms=2500, lookback_ms=600_000,
            )
        finally:
            conn.close()
        assert [t.ts_ms for t in ticks] == [1000, 2000]
        assert [t.price for t in ticks] == [50000.0, 50100.0]

    def test_lookback_window_lower_bound(self, tmp_path: Path):
        db = _build_db(tmp_path)
        for ts in [1_000_000, 1_500_000, 2_000_000, 2_500_000]:
            _add_cex(db, ts=ts, symbol="BTCUSDT", price=50000)
        conn = sqlite3.connect(str(db))
        try:
            # 600s lookback from t0=2_500_000 → window [1_900_000, 2_500_000]
            ticks = _mod._load_cex_trades_up_to(
                conn, "BTCUSDT", t0_ms=2_500_000, lookback_ms=600_000,
            )
        finally:
            conn.close()
        assert [t.ts_ms for t in ticks] == [2_000_000, 2_500_000]

    def test_isolates_by_symbol(self, tmp_path: Path):
        db = _build_db(tmp_path)
        _add_cex(db, ts=1000, symbol="BTCUSDT", price=50000)
        _add_cex(db, ts=1000, symbol="ETHUSDT", price=3000)
        conn = sqlite3.connect(str(db))
        try:
            btc = _mod._load_cex_trades_up_to(conn, "BTCUSDT", t0_ms=2000)
            eth = _mod._load_cex_trades_up_to(conn, "ETHUSDT", t0_ms=2000)
        finally:
            conn.close()
        assert len(btc) == 1 and btc[0].price == 50000.0
        assert len(eth) == 1 and eth[0].price == 3000.0


class TestCexPriceAtOrBefore:
    def test_returns_most_recent(self, tmp_path: Path):
        db = _build_db(tmp_path)
        _add_cex(db, ts=1000, symbol="BTCUSDT", price=50000)
        _add_cex(db, ts=2000, symbol="BTCUSDT", price=51000)
        conn = sqlite3.connect(str(db))
        try:
            assert _mod._cex_price_at_or_before(conn, "BTCUSDT", 2500) == 51000.0
            assert _mod._cex_price_at_or_before(conn, "BTCUSDT", 1500) == 50000.0
            assert _mod._cex_price_at_or_before(conn, "BTCUSDT", 500) is None
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# build_context: integrates the helpers
# ---------------------------------------------------------------------------

class TestBuildContext:
    def _signal(self, *, ts_ms: int = 5_000_000, sub_id: str = "btc-2026",
                asset_id: str | None = "yes_tok", side: str = "BUY_YES",
                end_ms: int = 5_900_000, min_to_expiry: float = 15.0):
        from scripts.bot_e_calibration_spike import SignalObs
        return SignalObs(
            sub_id=sub_id, obi=0.4, abs_obi=0.4, side=side,
            ts_ms=ts_ms, end_ms=end_ms, min_to_expiry=min_to_expiry,
            asset_id_at_signal=asset_id,
        )

    def test_populates_full_context(self, tmp_path: Path):
        db = _build_db(tmp_path)
        t0 = 5_000_000
        # Pre-t0 last trade price on the BUY_YES side
        _add_pm_lastprice(db, ts=t0 - 1_000, sub_id="btc-2026",
                          asset_id="yes_tok", price=0.55)
        # Pre-t0 CEX trades
        _add_cex(db, ts=t0 - 60_000, symbol="BTCUSDT", price=50000)
        _add_cex(db, ts=t0 - 30_000, symbol="BTCUSDT", price=50100)
        _add_cex(db, ts=t0 - 5_000, symbol="BTCUSDT", price=50200)
        # CEX price exactly 10 minutes ago
        _add_cex(db, ts=t0 - 10 * 60 * 1000, symbol="BTCUSDT", price=49500)

        sig = self._signal(ts_ms=t0)

        conn = sqlite3.connect(str(db))
        try:
            ctx = _mod.build_context(conn, sig)
        finally:
            conn.close()

        assert ctx.t0_ms == t0
        assert ctx.symbol == "BTC"
        assert ctx.tte_minutes == 15.0
        assert ctx.polymarket_mid == 0.55
        assert ctx.bid_notional == 0.0   # documented degenerate
        assert ctx.ask_notional == 0.0
        assert ctx.cex_price_at_t0 == 50200.0
        assert ctx.cex_price_10m_ago == 49500.0
        assert len(ctx.cex_trades_up_to_t0) == 4

    def test_no_future_leak_in_cex_trades(self, tmp_path: Path):
        db = _build_db(tmp_path)
        t0 = 5_000_000
        _add_cex(db, ts=t0 - 1_000, symbol="BTCUSDT", price=50000)
        _add_cex(db, ts=t0 + 1_000, symbol="BTCUSDT", price=99999)  # future
        sig = self._signal(ts_ms=t0)

        conn = sqlite3.connect(str(db))
        try:
            ctx = _mod.build_context(conn, sig)
        finally:
            conn.close()

        prices = [t.price for t in ctx.cex_trades_up_to_t0]
        assert 99999.0 not in prices
        assert 50000.0 in prices

    def test_handles_missing_data_gracefully(self, tmp_path: Path):
        """Empty DB → context built with all None / empty values, no
        exception. Important: the audit identified blackout windows
        and the extractor has to survive sparse data."""
        db = _build_db(tmp_path)
        sig = self._signal()

        conn = sqlite3.connect(str(db))
        try:
            ctx = _mod.build_context(conn, sig)
        finally:
            conn.close()

        assert ctx.polymarket_mid is None
        assert ctx.cex_price_at_t0 is None
        assert ctx.cex_price_10m_ago is None
        assert ctx.cex_trades_up_to_t0 == []


# ---------------------------------------------------------------------------
# CSV serialisation
# ---------------------------------------------------------------------------

class TestWriteCsv:
    def test_header_matches_schema(self, tmp_path: Path):
        from bots.bot_e_btc_scalp.features import FEATURE_NAMES
        out = tmp_path / "f.csv"
        _mod.write_csv(iter(()), out)
        with out.open() as fh:
            header = next(csv.reader(fh))
        # Header includes the expected envelope plus every feature.
        for col in ("signal_id", "ts_ms", "sub_id", "symbol", "side",
                    "tte_minutes", "label"):
            assert col in header
        for f in FEATURE_NAMES:
            assert f in header

    def test_label_inversion_for_buy_no(self, tmp_path: Path):
        """A BUY_NO signal that resolves YES is a LOSS. A BUY_NO that
        resolves NO is a WIN. The CSV's label column should reflect
        the side's perspective, not the raw market outcome."""
        from bots.bot_e_btc_scalp.features import FeatureVector
        from scripts.bot_e_calibration_spike import SignalObs

        sig_buy_no_market_resolved_yes = SignalObs(
            sub_id="btc-2026", obi=-0.4, abs_obi=0.4, side="BUY_NO",
            ts_ms=1, end_ms=2, min_to_expiry=10.0,
        )
        sig_buy_yes_market_resolved_yes = SignalObs(
            sub_id="btc-2026", obi=0.4, abs_obi=0.4, side="BUY_YES",
            ts_ms=2, end_ms=3, min_to_expiry=10.0,
        )

        fv = FeatureVector(values=tuple(0.0 for _ in
                                        range(len(_mod.FEATURE_NAMES) - 6)))
        # The FEATURE_NAMES list is the source of truth; recreate fv
        # with the right arity by reading FEATURE_NAMES count.
        from bots.bot_e_btc_scalp.features import FEATURE_NAMES
        fv = FeatureVector(values=tuple(0.0 for _ in FEATURE_NAMES))

        rows = [
            (sig_buy_no_market_resolved_yes, fv, True),   # BUY_NO + YES won → LOSS
            (sig_buy_yes_market_resolved_yes, fv, True),  # BUY_YES + YES won → WIN
        ]

        out = tmp_path / "f.csv"
        n = _mod.write_csv(iter(rows), out)
        assert n == 2

        with out.open() as fh:
            r = list(csv.DictReader(fh))
        assert r[0]["side"] == "BUY_NO" and r[0]["label"] == "0"
        assert r[1]["side"] == "BUY_YES" and r[1]["label"] == "1"

    def test_emits_one_row_per_signal(self, tmp_path: Path):
        from bots.bot_e_btc_scalp.features import FEATURE_NAMES, FeatureVector
        from scripts.bot_e_calibration_spike import SignalObs

        sigs = [
            SignalObs(sub_id="btc-2026", obi=0.4, abs_obi=0.4,
                      side="BUY_YES", ts_ms=ts, end_ms=ts + 100,
                      min_to_expiry=15.0)
            for ts in (1_000, 2_000, 3_000)
        ]
        fv = FeatureVector(values=tuple(0.0 for _ in FEATURE_NAMES))
        rows = [(s, fv, True) for s in sigs]

        out = tmp_path / "f.csv"
        n = _mod.write_csv(iter(rows), out)
        assert n == 3

        with out.open() as fh:
            r = list(csv.DictReader(fh))
        assert len(r) == 3
        assert {row["ts_ms"] for row in r} == {"1000", "2000", "3000"}
