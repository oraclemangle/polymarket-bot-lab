"""Pyth feed-id registry. Source-of-truth for symbol→id mappings.

Two identifier spaces:
  - Pyth Lazer Pro: numeric ``id`` (int) used on wss://pyth-lazer-0.dourolabs.app
  - Pyth Hermes (free): 64-char hex ``hermes_id`` used on hermes.pyth.network

Both were resolved against the live catalogues on 2026-04-15 via:
  https://pyth.dourolabs.app/v1/symbols       (Lazer numeric IDs)
  https://hermes.pyth.network/v2/price_feeds  (Hermes hex IDs)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Feed:
    id: int | None
    symbol: str
    category: str  # 'equity' | 'commodity' | 'etf' | 'crypto'
    hermes_id: str | None = None  # 64-char hex, no 0x prefix


FEEDS: dict[str, Feed] = {
    # Metals / commodities
    "GOLD":   Feed(346,  "GOLD",   "commodity",
                   hermes_id="765d2ba906dbc32ca17cc11f5310a89e9ee1f6420508c63861f2f8ba4ee34bb2"),
    "SILVER": Feed(345,  "SILVER", "commodity",
                   hermes_id="f2fb02c32b055c805e7238d628e5e9dadef274376114eb1f012337cabe93871e"),
    "WTI":    Feed(344,  "WTI",    "commodity",
                   hermes_id=None),  # Hermes has only month-coded futures; revisit per Polymarket reference
    # TODO: Pyth has only natural-gas futures (id=3005..3029 NGD[J|K|M|N|Q|U|H]6/USD).
    # Decide which contract Polymarket references once market discovery lands.
    "NATGAS": Feed(None, "NATGAS", "commodity", hermes_id=None),
    # US equities
    "AAPL":   Feed(922,  "AAPL",   "equity",
                   hermes_id="49f6b65cb1de6b10eaf75e7c03ca029c306d0357e91b5311b175084a5ad55688"),
    "TSLA":   Feed(1435, "TSLA",   "equity",
                   hermes_id="16dad506d7db8da01c87581c87ca897a012a153557d4d578c3b9c9e1bc0632f1"),
    "NVDA":   Feed(1314, "NVDA",   "equity",
                   hermes_id="b1073854ed24cbc755dc527418f52b7d271f6cc967bbf8d8129112b18860a593"),
    "COIN":   Feed(1042, "COIN",   "equity",
                   hermes_id="fee33f2a978bf32dd6b662b65ba8083c6773b494f8401194ec1870c640860245"),
    "PLTR":   Feed(1346, "PLTR",   "equity",
                   hermes_id="11a70634863ddffb71f2b11f2cff29f73f3db8f6d0b78c49f2b5f4ad36e885f0"),
    # ETFs
    "SPY":    Feed(1398, "SPY",    "etf",
                   hermes_id="19e09bb805456ada3979a7d1cbb4b6d63babc3a0f8e8a9509f68afa5c4c11cd5"),
    "QQQ":    Feed(1363, "QQQ",    "etf",
                   hermes_id="9695e2b96ea7b3859da9ed25b7a46a920a776e2fdae19a7bcfdf2b219230452d"),
    "EWY":    Feed(2944, "EWY",    "etf",
                   hermes_id="7be2b3f9f9d02b1ffcf61fc26ad5cc6aff4dd02044f9abc22ee57f37b3b5d2e5"),
    # Crypto
    "BTC":    Feed(1,    "BTC",    "crypto",
                   hermes_id="e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43"),
    "ETH":    Feed(2,    "ETH",    "crypto",
                   hermes_id="ff61491a931112ddf1bd8147cd1b641375f79f5825126d665480874634fd0ace"),
    "SOL":    Feed(6,    "SOL",    "crypto",
                   hermes_id="ef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d"),
}


def active_feeds() -> list[Feed]:
    """Return only feeds with a verified (non-None) Pyth Lazer id."""
    return [f for f in FEEDS.values() if f.id is not None]


def hermes_feeds() -> list[Feed]:
    """Return only feeds with a verified (non-None) Hermes hex id."""
    return [f for f in FEEDS.values() if f.hermes_id is not None]


def feed_by_id(fid: int) -> Feed | None:
    """Look up a feed by its Pyth Lazer feed id."""
    for f in FEEDS.values():
        if f.id == fid:
            return f
    return None


def feed_by_hermes_id(hid: str) -> Feed | None:
    """Look up a feed by its Hermes hex feed id (case-insensitive)."""
    hid_lower = hid.lower()
    for f in FEEDS.values():
        if f.hermes_id and f.hermes_id.lower() == hid_lower:
            return f
    return None


def feed_by_symbol(sym: str) -> Feed | None:
    """Look up a feed by symbol (case-sensitive)."""
    return FEEDS.get(sym)
