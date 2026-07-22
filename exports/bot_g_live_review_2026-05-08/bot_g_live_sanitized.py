#!/usr/bin/env python3
"""PII-stripped Bot G Prime Live strategy logic.

Generated: 2026-05-08

This file is safe to share for external review. It contains the entry
decision logic and public strategy parameters only. It deliberately excludes:

- wallet addresses, private keys, keystore paths, passphrase paths, API keys;
- hostnames, usernames, IP addresses, deployment paths, systemd units;
- raw orders, raw fills, market ids from the live ledger, and database rows;
- any code that can place a real order.

Purpose:
    Review the current Bot G Prime Live idea as a pure decision function:
    should a near-resolution crypto Up/Down market be bought, and at what
    limit price/size, given a sanitized market snapshot?

Usage:
    python bot_g_live_sanitized.py --example
    python bot_g_live_sanitized.py example_snapshot.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from typing import Any


def dec(value: Any, default: str = "0") -> Decimal:
    """Convert JSON-ish values to Decimal without going through binary float."""
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def quant(value: Decimal, places: str = "0.0001") -> str:
    return str(value.quantize(Decimal(places), rounding=ROUND_DOWN))


@dataclass(frozen=True)
class Quote:
    best_bid: Decimal
    best_ask: Decimal
    best_ask_size: Decimal

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Quote | None":
        if not data:
            return None
        return cls(
            best_bid=dec(data.get("best_bid")),
            best_ask=dec(data.get("best_ask")),
            best_ask_size=dec(data.get("best_ask_size")),
        )


@dataclass(frozen=True)
class CexWindow:
    old_price: Decimal
    new_price: Decimal
    window_sec: int = 45

    @property
    def move_bps(self) -> Decimal:
        if self.old_price <= 0:
            return Decimal("0")
        return ((self.new_price - self.old_price) / self.old_price) * Decimal("10000")

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CexWindow | None":
        if not data:
            return None
        return cls(
            old_price=dec(data.get("old_price")),
            new_price=dec(data.get("new_price")),
            window_sec=int(data.get("window_sec", 45)),
        )


@dataclass(frozen=True)
class DepletionSignal:
    depletion_ratio: Decimal | None = None
    n_trailing: int = 0
    n_recent: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DepletionSignal | None":
        if not data:
            return None
        ratio = data.get("depletion_ratio")
        return cls(
            depletion_ratio=None if ratio is None else dec(ratio),
            n_trailing=int(data.get("n_trailing", 0)),
            n_recent=int(data.get("n_recent", 0)),
        )


@dataclass(frozen=True)
class MarketSnapshot:
    condition_id: str
    question: str
    seconds_to_close: int
    yes: Quote | None
    no: Quote | None
    cex: CexWindow | None = None
    depletion: dict[str, DepletionSignal] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MarketSnapshot":
        depletion_raw = data.get("depletion") or {}
        return cls(
            condition_id=str(data.get("condition_id") or "sanitized-market"),
            question=str(data.get("question") or ""),
            seconds_to_close=int(data.get("seconds_to_close", 0)),
            yes=Quote.from_dict(data.get("yes")),
            no=Quote.from_dict(data.get("no")),
            cex=CexWindow.from_dict(data.get("cex")),
            depletion={
                str(side).upper(): signal
                for side, value in depletion_raw.items()
                if (signal := DepletionSignal.from_dict(value)) is not None
            },
        )


@dataclass(frozen=True)
class BotGPrimeLiveConfig:
    allowed_symbols: tuple[str, ...] = ("BTC", "ETH", "SOL")
    entry_window_sec: int = 60
    min_fresh_lead_sec: int = 5
    min_entry_price: Decimal = Decimal("0.035")
    max_entry_price: Decimal = Decimal("0.055")
    min_counterparty_price: Decimal = Decimal("0.91")
    fixed_trade_usd: Decimal = Decimal("1")
    min_book_size_shares: Decimal = Decimal("20")
    min_actual_notional_usd: Decimal = Decimal("1")
    tick_size: Decimal = Decimal("0.01")
    live_price_improvement_ticks: int = 1
    max_open_positions: int = 10
    max_daily_entries: int = 20
    max_daily_gross_notional_usd: Decimal = Decimal("100")
    require_cex_confirm: bool = False
    cex_window_sec: int = 45
    min_cex_move_bps: Decimal = Decimal("1.5")
    require_depletion: bool = False
    max_depletion_ratio: Decimal = Decimal("0.75")


@dataclass(frozen=True)
class Decision:
    enter: bool
    reason: str
    side: str | None = None
    limit_price: Decimal | None = None
    size_shares: Decimal | None = None
    notional_usd: Decimal | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "enter": self.enter,
            "reason": self.reason,
            "side": self.side,
            "limit_price": None if self.limit_price is None else quant(self.limit_price),
            "size_shares": None if self.size_shares is None else quant(self.size_shares, "0.000001"),
            "notional_usd": None if self.notional_usd is None else quant(self.notional_usd),
            "diagnostics": _jsonable(self.diagnostics),
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return quant(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def extract_symbol(question: str) -> str | None:
    q = question.upper()
    symbol_needles = {
        "BTC": ("BTC", "BITCOIN"),
        "ETH": ("ETH", "ETHEREUM"),
        "SOL": ("SOL", "SOLANA"),
        "XRP": ("XRP", "RIPPLE"),
        "DOGE": ("DOGE", "DOGECOIN"),
    }
    for symbol, needles in symbol_needles.items():
        if any(needle in q for needle in needles):
            return symbol
    return None


def _quote_for_side(snapshot: MarketSnapshot, side: str) -> Quote | None:
    return snapshot.yes if side == "YES" else snapshot.no


def _cex_confirms_side(side: str, cex: CexWindow, min_move_bps: Decimal) -> bool:
    if side == "YES":
        return cex.move_bps >= min_move_bps
    return cex.move_bps <= -min_move_bps


def break_even_win_rate(entry_price: Decimal, exit_price: Decimal = Decimal("1")) -> Decimal:
    """Break-even hit rate before fees.

    Holding a binary token bought at p to a full 1.00 payout breaks even at
    p. Exiting early at 0.50 breaks even at p / 0.50.
    """
    if exit_price <= 0:
        raise ValueError("exit_price must be positive")
    return entry_price / exit_price


def choose_entry(
    snapshot: MarketSnapshot,
    cfg: BotGPrimeLiveConfig = BotGPrimeLiveConfig(),
    *,
    already_entered_condition_ids: set[str] | None = None,
    open_positions: int = 0,
    daily_entries: int = 0,
    daily_gross_notional_usd: Decimal = Decimal("0"),
) -> Decision:
    """Return the sanitized Bot G Prime Live entry decision.

    This mirrors the live production strategy shape:

    1. only BTC/ETH/SOL crypto Up/Down markets;
    2. only the final 60s, with at least 5s left at pre-submit time;
    3. buy the cheapest side if its ask is 3.5c to 5.5c;
    4. require the other side to look near-certain, currently at least 91c;
    5. use one tick of limit-price improvement for live transfer, capped at 5.5c;
    6. cap position count, daily entry count, and daily gross notional.
    """
    entered = already_entered_condition_ids or set()
    diagnostics: dict[str, Any] = {
        "condition_id": snapshot.condition_id,
        "seconds_to_close": snapshot.seconds_to_close,
        "configured_entry_window_sec": cfg.entry_window_sec,
        "price_band": [cfg.min_entry_price, cfg.max_entry_price],
    }

    if snapshot.condition_id in entered:
        return Decision(False, "already_entered_market", diagnostics=diagnostics)

    symbol = extract_symbol(snapshot.question)
    diagnostics["symbol"] = symbol
    if symbol not in cfg.allowed_symbols:
        return Decision(False, "symbol_not_allowed", diagnostics=diagnostics)

    if snapshot.seconds_to_close > cfg.entry_window_sec:
        return Decision(False, "too_early", diagnostics=diagnostics)
    if snapshot.seconds_to_close < cfg.min_fresh_lead_sec:
        return Decision(False, "too_late_fresh_clock_guard", diagnostics=diagnostics)

    if open_positions >= cfg.max_open_positions:
        return Decision(False, "open_position_cap", diagnostics=diagnostics)
    if daily_entries >= cfg.max_daily_entries:
        return Decision(False, "daily_entry_cap", diagnostics=diagnostics)
    if daily_gross_notional_usd + cfg.fixed_trade_usd > cfg.max_daily_gross_notional_usd:
        return Decision(False, "daily_gross_notional_cap", diagnostics=diagnostics)

    candidates: list[tuple[str, Quote]] = []
    quote_diagnostics: dict[str, Any] = {}
    for side in ("YES", "NO"):
        quote = _quote_for_side(snapshot, side)
        if quote is None:
            quote_diagnostics[side] = {"available": False}
            continue
        eligible = (
            quote.best_ask > 0
            and cfg.min_entry_price <= quote.best_ask <= cfg.max_entry_price
            and quote.best_ask_size >= cfg.min_book_size_shares
        )
        quote_diagnostics[side] = {
            "available": True,
            "best_bid": quote.best_bid,
            "best_ask": quote.best_ask,
            "best_ask_size": quote.best_ask_size,
            "eligible": eligible,
        }
        if eligible:
            candidates.append((side, quote))
    diagnostics["quotes"] = quote_diagnostics

    if not candidates:
        return Decision(False, "no_side_in_price_band_with_depth", diagnostics=diagnostics)

    available_asks = [
        q.best_ask for q in (snapshot.yes, snapshot.no) if q is not None and q.best_ask > 0
    ]
    max_ask = max(available_asks) if available_asks else Decimal("0")
    diagnostics["max_counterparty_ask"] = max_ask
    if max_ask < cfg.min_counterparty_price:
        return Decision(False, "counterparty_not_near_certain", diagnostics=diagnostics)

    candidates.sort(key=lambda item: item[1].best_ask)
    side, quote = candidates[0]
    diagnostics["chosen_observed_ask"] = quote.best_ask

    if cfg.require_cex_confirm:
        if snapshot.cex is None:
            return Decision(False, "cex_confirmation_missing", diagnostics=diagnostics)
        diagnostics["cex_move_bps"] = snapshot.cex.move_bps
        if not _cex_confirms_side(side, snapshot.cex, cfg.min_cex_move_bps):
            return Decision(False, "cex_not_confirming_side", side=side, diagnostics=diagnostics)

    if cfg.require_depletion:
        depletion = snapshot.depletion.get(side)
        diagnostics["depletion"] = depletion.depletion_ratio if depletion else None
        if (
            depletion is None
            or depletion.depletion_ratio is None
            or depletion.depletion_ratio > cfg.max_depletion_ratio
        ):
            return Decision(False, "book_not_depleting", side=side, diagnostics=diagnostics)

    improved_price = quote.best_ask + (cfg.tick_size * cfg.live_price_improvement_ticks)
    limit_price = min(cfg.max_entry_price, improved_price)
    size_by_budget = cfg.fixed_trade_usd / limit_price
    size = min(size_by_budget, quote.best_ask_size)
    notional = size * limit_price

    diagnostics["limit_price_before_cap"] = improved_price
    diagnostics["size_by_budget"] = size_by_budget

    if size <= 0:
        return Decision(False, "zero_size", side=side, diagnostics=diagnostics)
    if notional + Decimal("0.000001") < cfg.min_actual_notional_usd:
        return Decision(False, "below_min_notional", side=side, diagnostics=diagnostics)
    if daily_gross_notional_usd + notional > cfg.max_daily_gross_notional_usd:
        return Decision(False, "daily_gross_notional_cap_after_sizing", side=side, diagnostics=diagnostics)

    diagnostics["break_even_hold_to_one"] = break_even_win_rate(limit_price)
    diagnostics["break_even_exit_at_50c"] = break_even_win_rate(limit_price, Decimal("0.50"))

    return Decision(
        True,
        "enter_longshot_tail",
        side=side,
        limit_price=limit_price,
        size_shares=size,
        notional_usd=notional,
        diagnostics=diagnostics,
    )


EXAMPLE_SNAPSHOT = {
    "condition_id": "example-btc-updown-2026-05-08T12-00Z",
    "question": "Bitcoin Up or Down - example sanitized market",
    "seconds_to_close": 42,
    "yes": {"best_bid": "0.035", "best_ask": "0.040", "best_ask_size": "44"},
    "no": {"best_bid": "0.925", "best_ask": "0.940", "best_ask_size": "120"},
    "cex": {"old_price": "100000", "new_price": "100020", "window_sec": 45},
}


def _load_snapshots(raw: Any) -> list[MarketSnapshot]:
    if isinstance(raw, dict) and "markets" in raw:
        raw = raw["markets"]
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        raise TypeError("JSON must be one market object or a list under 'markets'")
    return [MarketSnapshot.from_dict(item) for item in raw]


def _read_json(path: str | None) -> Any:
    if path is None:
        return EXAMPLE_SNAPSHOT
    if path == "-":
        return json.load(sys.stdin)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "json_path",
        nargs="?",
        help="Market snapshot JSON file. Use '-' for stdin. Omit with --example.",
    )
    parser.add_argument(
        "--example",
        action="store_true",
        help="Run the built-in synthetic example.",
    )
    args = parser.parse_args(argv)

    raw = EXAMPLE_SNAPSHOT if args.example else _read_json(args.json_path)
    snapshots = _load_snapshots(raw)
    decisions = [choose_entry(snapshot).to_jsonable() for snapshot in snapshots]
    json.dump(decisions, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
