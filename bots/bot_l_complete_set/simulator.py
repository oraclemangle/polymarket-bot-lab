"""Complete-set convergence simulator for BTC 5-minute Polymarket markets."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bots.bot_l_complete_set.schema import init_db

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORDER_DB = REPO_ROOT / "data" / "bot_e_recorder_vps_canary.db"
DEFAULT_PAPER_DB = REPO_ROOT / "data" / "bot_l_complete_set_paper.db"


@dataclass(frozen=True)
class Quote:
    event_id: int
    received_at_ms: int
    event_type: str
    asset_id: str
    condition_id: str
    bid: float | None
    ask: float | None
    bid_size: float | None
    ask_size: float | None
    diagnostics: dict[str, Any]
    payload_json: str


@dataclass(frozen=True)
class Market:
    condition_id: str
    question: str
    end_date_ms: int | None
    yes_token_id: str
    no_token_id: str
    symbol: str
    duration_minutes: int


def _parse_iso_ms(value: Any) -> int | None:
    if not value:
        return None
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)


def _connect_ro(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _float_with_reason(value: Any) -> tuple[float | None, str]:
    if value is None:
        return None, "missing"
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None, "invalid"
    if out <= 0:
        return None, "zero_or_negative"
    return out, "ok"


def _float(value: Any) -> float | None:
    return _float_with_reason(value)[0]


def _best_price_and_size(
    levels: Any,
    *,
    best: str,
) -> tuple[float | None, float | None, dict[str, Any]]:
    if not isinstance(levels, list):
        return None, None, {"levels": "missing_or_not_list"}
    parsed: list[tuple[float, float | None, str]] = []
    skipped = 0
    for level in levels:
        if not isinstance(level, dict):
            skipped += 1
            continue
        price, _price_reason = _float_with_reason(level.get("price"))
        if price is None:
            skipped += 1
            continue
        size, size_reason = _float_with_reason(level.get("size"))
        parsed.append((price, size, size_reason))
    if not parsed:
        return None, None, {"levels": "no_valid_price", "skipped_levels": skipped}
    price, size, size_reason = (max(parsed) if best == "bid" else min(parsed))
    return price, size, {
        "levels": "ok",
        "valid_levels": len(parsed),
        "skipped_levels": skipped,
        "selected_size": size_reason,
    }


def parse_quote(row: sqlite3.Row) -> Quote | None:
    """Extract a top-of-book quote from `best_bid_ask` or `book` payloads."""
    asset_id = row["asset_id"]
    if not asset_id:
        return None
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError):
        return None
    condition_id = row["condition_id"] or payload.get("market")
    if not condition_id:
        return None
    bid, bid_reason = _float_with_reason(payload.get("best_bid"))
    ask, ask_reason = _float_with_reason(payload.get("best_ask"))
    bid_size, bid_size_reason = _float_with_reason(payload.get("best_bid_size"))
    ask_size, ask_size_reason = _float_with_reason(payload.get("best_ask_size"))
    diagnostics: dict[str, Any] = {
        "best_bid": bid_reason,
        "best_ask": ask_reason,
        "best_bid_size": bid_size_reason,
        "best_ask_size": ask_size_reason,
        "bid_source": "direct" if bid is not None else None,
        "ask_source": "direct" if ask is not None else None,
    }
    if bid is None or ask is None or bid_size is None or ask_size is None:
        book_bid, book_bid_size, book_bid_diag = _best_price_and_size(payload.get("bids"), best="bid")
        book_ask, book_ask_size, book_ask_diag = _best_price_and_size(payload.get("asks"), best="ask")
        diagnostics["book_bid"] = book_bid_diag
        diagnostics["book_ask"] = book_ask_diag
        if bid is None:
            bid = book_bid
            diagnostics["bid_source"] = "book" if bid is not None else None
        if ask is None:
            ask = book_ask
            diagnostics["ask_source"] = "book" if ask is not None else None
        if bid_size is None:
            bid_size = book_bid_size
            diagnostics["bid_size_source"] = "book" if bid_size is not None else "none"
        else:
            diagnostics["bid_size_source"] = "direct"
        if ask_size is None:
            ask_size = book_ask_size
            diagnostics["ask_size_source"] = "book" if ask_size is not None else "none"
        else:
            diagnostics["ask_size_source"] = "direct"
    else:
        diagnostics["bid_size_source"] = "direct" if bid_size is not None else "none"
        diagnostics["ask_size_source"] = "direct" if ask_size is not None else "none"
    if bid is None and ask is None:
        return None
    if bid is not None and ask is not None and bid > ask:
        return None
    return Quote(
        event_id=int(row["id"]),
        received_at_ms=int(row["received_at_ms"]),
        event_type=str(row["event_type"] or ""),
        asset_id=str(asset_id),
        condition_id=str(condition_id),
        bid=bid,
        ask=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        diagnostics=diagnostics,
        payload_json=str(row["payload_json"]),
    )


def _join_book_depth(
    quote: Quote,
    book_quote: Quote | None,
    *,
    max_depth_age_ms: int,
) -> Quote:
    diagnostics = dict(quote.diagnostics)
    if book_quote is None:
        diagnostics["depth_join"] = "missing_book"
        return replace(quote, diagnostics=diagnostics)
    depth_age_ms = quote.received_at_ms - book_quote.received_at_ms
    diagnostics["depth_age_ms"] = depth_age_ms
    diagnostics["depth_source_event_id"] = book_quote.event_id
    if depth_age_ms < 0:
        diagnostics["depth_join"] = "future_book_rejected"
        return replace(quote, diagnostics=diagnostics)
    if depth_age_ms > max_depth_age_ms:
        diagnostics["depth_join"] = "stale_book"
        return replace(quote, diagnostics=diagnostics)
    diagnostics["depth_join"] = "book"
    return replace(
        quote,
        bid_size=book_quote.bid_size,
        ask_size=book_quote.ask_size,
        diagnostics=diagnostics,
    )


def _latest_btc_5m_markets(con: sqlite3.Connection) -> dict[str, Market]:
    rows = con.execute(
        """
        SELECT condition_id, question, end_date_iso, yes_token_id, no_token_id, symbol, duration_minutes,
               MAX(scan_at_ms) AS last_scan_ms
        FROM markets
        WHERE symbol='BTC'
          AND duration_minutes=5
          AND yes_token_id IS NOT NULL
          AND no_token_id IS NOT NULL
        GROUP BY condition_id
        """
    ).fetchall()
    return {
        str(row["condition_id"]): Market(
            condition_id=str(row["condition_id"]),
            question=str(row["question"] or ""),
            end_date_ms=_parse_iso_ms(row["end_date_iso"]),
            yes_token_id=str(row["yes_token_id"]),
            no_token_id=str(row["no_token_id"]),
            symbol="BTC",
            duration_minutes=5,
        )
        for row in rows
    }


def _last_processed_event_id(con: sqlite3.Connection) -> int:
    row = con.execute(
        "SELECT COALESCE(MAX(last_recorder_event_id), 0) FROM bot_l_complete_set_run_log"
    ).fetchone()
    return int(row[0] or 0)


def _write_signal(
    con: sqlite3.Connection,
    *,
    event_id: int,
    detected_at_ms: int,
    market: Market,
    signal_type: str,
    yes_price: float,
    no_price: float,
    raw_sum: float,
    adjusted_sum: float,
    yes_size: float | None,
    no_size: float | None,
    simulated_cost_usd: float,
    simulated_return_usd: float,
    executable: bool,
    reason: str,
    payload: dict[str, Any],
) -> int:
    pnl = simulated_return_usd - simulated_cost_usd
    roi = pnl / simulated_cost_usd if simulated_cost_usd else 0.0
    cur = con.execute(
        """
        INSERT OR IGNORE INTO bot_l_complete_set_signals (
            recorder_event_id, detected_at_ms, condition_id, question, symbol,
            duration_minutes, signal_type, yes_token_id, no_token_id,
            yes_price, no_price, raw_sum, adjusted_sum, yes_size, no_size,
            simulated_cost_usd, simulated_return_usd, simulated_pnl_usd,
            simulated_roi, executable, reason, payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            detected_at_ms,
            market.condition_id,
            market.question,
            market.symbol,
            market.duration_minutes,
            signal_type,
            market.yes_token_id,
            market.no_token_id,
            yes_price,
            no_price,
            raw_sum,
            adjusted_sum,
            yes_size,
            no_size,
            simulated_cost_usd,
            simulated_return_usd,
            pnl,
            roi,
            1 if executable else 0,
            reason,
            json.dumps(payload, sort_keys=True),
        ),
    )
    return int(cur.rowcount or 0)


def _maybe_write_buy_signal(
    con: sqlite3.Connection,
    *,
    market: Market,
    event_id: int,
    detected_at_ms: int,
    yes: Quote,
    no: Quote,
    raw_threshold: float,
    adjusted_threshold: float,
    slippage_per_leg: float,
    gross_cost_usd: float,
    min_depth_shares: float,
    require_depth: bool,
    pair_age_ms: int,
    blocked_reason: str | None,
) -> int:
    if yes.ask is None or no.ask is None:
        return 0
    raw_sum = yes.ask + no.ask
    adjusted_sum = raw_sum + (2 * slippage_per_leg)
    if raw_sum > raw_threshold:
        return 0
    dynamic_depth_shares = gross_cost_usd / adjusted_sum if require_depth and adjusted_sum > 0 else 0.0
    required_depth_shares = max(min_depth_shares, dynamic_depth_shares)
    depth_ok = (
        required_depth_shares <= 0
        or (
            yes.ask_size is not None
            and no.ask_size is not None
            and yes.ask_size >= required_depth_shares
            and no.ask_size >= required_depth_shares
        )
    )
    haircut_ok = adjusted_sum <= adjusted_threshold
    executable = depth_ok and haircut_ok and blocked_reason is None
    shares = gross_cost_usd / adjusted_sum if adjusted_sum > 0 else 0.0
    reason = "passes_haircut"
    if not executable:
        if blocked_reason:
            reason = blocked_reason
        elif not haircut_ok:
            reason = "raw_only"
        elif not depth_ok:
            reason = "depth_missing_or_insufficient"
    return _write_signal(
        con,
        event_id=event_id,
        detected_at_ms=detected_at_ms,
        market=market,
        signal_type="BUY_COMPLETE_SET",
        yes_price=yes.ask,
        no_price=no.ask,
        raw_sum=raw_sum,
        adjusted_sum=adjusted_sum,
        yes_size=yes.ask_size,
        no_size=no.ask_size,
        simulated_cost_usd=gross_cost_usd,
        simulated_return_usd=shares,
        executable=executable,
        reason=reason,
        payload={
            "yes_event_id": yes.event_id,
            "no_event_id": no.event_id,
            "yes_quote_diagnostics": yes.diagnostics,
            "no_quote_diagnostics": no.diagnostics,
            "slippage_per_leg": slippage_per_leg,
            "min_depth_shares": min_depth_shares,
            "require_depth": require_depth,
            "required_depth_shares": required_depth_shares,
            "pair_age_ms": pair_age_ms,
            "blocked_reason": blocked_reason,
        },
    )


def _maybe_write_sell_signal(
    con: sqlite3.Connection,
    *,
    market: Market,
    event_id: int,
    detected_at_ms: int,
    yes: Quote,
    no: Quote,
    raw_threshold: float,
    adjusted_threshold: float,
    slippage_per_leg: float,
    notional_usd: float,
    min_depth_shares: float,
    require_depth: bool,
    pair_age_ms: int,
    blocked_reason: str | None,
) -> int:
    if yes.bid is None or no.bid is None:
        return 0
    raw_sum = yes.bid + no.bid
    adjusted_sum = raw_sum - (2 * slippage_per_leg)
    if raw_sum < raw_threshold:
        return 0
    dynamic_depth_shares = notional_usd / adjusted_sum if require_depth and adjusted_sum > 0 else 0.0
    required_depth_shares = max(min_depth_shares, dynamic_depth_shares)
    depth_ok = (
        required_depth_shares <= 0
        or (
            yes.bid_size is not None
            and no.bid_size is not None
            and yes.bid_size >= required_depth_shares
            and no.bid_size >= required_depth_shares
        )
    )
    haircut_ok = adjusted_sum >= adjusted_threshold
    executable = depth_ok and haircut_ok and blocked_reason is None
    reason = "passes_haircut"
    if not executable:
        if blocked_reason:
            reason = blocked_reason
        elif not haircut_ok:
            reason = "raw_only"
        elif not depth_ok:
            reason = "depth_missing_or_insufficient"
    return _write_signal(
        con,
        event_id=event_id,
        detected_at_ms=detected_at_ms,
        market=market,
        signal_type="SELL_COMPLETE_SET",
        yes_price=yes.bid,
        no_price=no.bid,
        raw_sum=raw_sum,
        adjusted_sum=adjusted_sum,
        yes_size=yes.bid_size,
        no_size=no.bid_size,
        simulated_cost_usd=notional_usd,
        simulated_return_usd=notional_usd * adjusted_sum,
        executable=executable,
        reason=reason,
        payload={
            "yes_event_id": yes.event_id,
            "no_event_id": no.event_id,
            "yes_quote_diagnostics": yes.diagnostics,
            "no_quote_diagnostics": no.diagnostics,
            "slippage_per_leg": slippage_per_leg,
            "min_depth_shares": min_depth_shares,
            "require_depth": require_depth,
            "required_depth_shares": required_depth_shares,
            "pair_age_ms": pair_age_ms,
            "blocked_reason": blocked_reason,
            "note": "sell signal is inventory/split research only",
        },
    )


def run_once(
    *,
    recorder_db_path: Path,
    paper_db_path: Path,
    lookback_hours: float,
    raw_buy_threshold: float,
    adjusted_buy_threshold: float,
    raw_sell_threshold: float,
    adjusted_sell_threshold: float,
    slippage_per_leg: float,
    gross_cost_usd: float,
    min_depth_shares: float,
    max_pair_age_ms: int,
    require_depth: bool = False,
    max_depth_age_ms: int = 1000,
    incremental: bool = True,
    reset_paper: bool = False,
) -> dict[str, Any]:
    started = datetime.now(UTC)
    paper = init_db(paper_db_path)
    recorder = _connect_ro(recorder_db_path)
    try:
        if reset_paper:
            paper.execute("DELETE FROM bot_l_complete_set_signals")
            paper.execute("DELETE FROM bot_l_complete_set_run_log")
            paper.commit()
        markets = _latest_btc_5m_markets(recorder)
        min_event_id = _last_processed_event_id(paper) if incremental else 0
        since_ms = int(started.timestamp() * 1000 - lookback_hours * 3600 * 1000)
        latest_by_asset: dict[str, Quote] = {}
        latest_book_by_asset: dict[str, Quote] = {}
        source_events_seen = 0
        signals_written = 0
        last_event_id = min_event_id
        failure_counts: dict[str, int] = {
            "quote_parse_failed": 0,
            "market_missing": 0,
            "one_leg_missing": 0,
            "pair_age_too_large": 0,
            "paired_quotes": 0,
            "stale_after_end_date": 0,
            "depth_missing_or_insufficient": 0,
        }
        rows = recorder.execute(
            """
            SELECT id, received_at_ms, event_type, asset_id, condition_id, payload_json
            FROM pm_events
            WHERE id > ?
              AND received_at_ms >= ?
              AND event_type IN ('best_bid_ask', 'book')
            ORDER BY id ASC
            """,
            (min_event_id, since_ms),
        )
        for row in rows:
            source_events_seen += 1
            last_event_id = max(last_event_id, int(row["id"]))
            quote = parse_quote(row)
            if quote is None:
                failure_counts["quote_parse_failed"] += 1
                continue
            market = markets.get(quote.condition_id)
            if market is None:
                failure_counts["market_missing"] += 1
                continue
            if quote.event_type == "book" and (quote.bid_size is not None or quote.ask_size is not None):
                latest_book_by_asset[quote.asset_id] = quote
            latest_by_asset[quote.asset_id] = quote
            yes = latest_by_asset.get(market.yes_token_id)
            no = latest_by_asset.get(market.no_token_id)
            if yes is None or no is None:
                failure_counts["one_leg_missing"] += 1
                continue
            pair_age_ms = abs(yes.received_at_ms - no.received_at_ms)
            if pair_age_ms > max_pair_age_ms:
                failure_counts["pair_age_too_large"] += 1
                continue
            failure_counts["paired_quotes"] += 1
            event_id = max(yes.event_id, no.event_id)
            detected_at_ms = max(yes.received_at_ms, no.received_at_ms)
            blocked_reason = None
            if market.end_date_ms is not None and detected_at_ms > market.end_date_ms:
                blocked_reason = "stale_after_end_date"
                failure_counts["stale_after_end_date"] += 1
            yes_depth = _join_book_depth(
                yes,
                latest_book_by_asset.get(yes.asset_id),
                max_depth_age_ms=max_depth_age_ms,
            )
            no_depth = _join_book_depth(
                no,
                latest_book_by_asset.get(no.asset_id),
                max_depth_age_ms=max_depth_age_ms,
            )
            signals_written += _maybe_write_buy_signal(
                paper,
                market=market,
                event_id=event_id,
                detected_at_ms=detected_at_ms,
                yes=yes_depth,
                no=no_depth,
                raw_threshold=raw_buy_threshold,
                adjusted_threshold=adjusted_buy_threshold,
                slippage_per_leg=slippage_per_leg,
                gross_cost_usd=gross_cost_usd,
                min_depth_shares=min_depth_shares,
                require_depth=require_depth,
                pair_age_ms=pair_age_ms,
                blocked_reason=blocked_reason,
            )
            signals_written += _maybe_write_sell_signal(
                paper,
                market=market,
                event_id=event_id,
                detected_at_ms=detected_at_ms,
                yes=yes_depth,
                no=no_depth,
                raw_threshold=raw_sell_threshold,
                adjusted_threshold=adjusted_sell_threshold,
                slippage_per_leg=slippage_per_leg,
                notional_usd=gross_cost_usd,
                min_depth_shares=min_depth_shares,
                require_depth=require_depth,
                pair_age_ms=pair_age_ms,
                blocked_reason=blocked_reason,
            )
        config = {
            "lookback_hours": lookback_hours,
            "raw_buy_threshold": raw_buy_threshold,
            "adjusted_buy_threshold": adjusted_buy_threshold,
            "raw_sell_threshold": raw_sell_threshold,
            "adjusted_sell_threshold": adjusted_sell_threshold,
            "slippage_per_leg": slippage_per_leg,
            "gross_cost_usd": gross_cost_usd,
            "min_depth_shares": min_depth_shares,
            "require_depth": require_depth,
            "max_pair_age_ms": max_pair_age_ms,
            "max_depth_age_ms": max_depth_age_ms,
            "incremental": incremental,
            "reset_paper": reset_paper,
            "failure_counts": failure_counts,
        }
        paper.execute(
            """
            INSERT INTO bot_l_complete_set_run_log (
                started_at, finished_at, recorder_db_path, source_events_seen,
                signals_written, last_recorder_event_id, config_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started.isoformat(),
                datetime.now(UTC).isoformat(),
                str(recorder_db_path),
                source_events_seen,
                signals_written,
                last_event_id,
                json.dumps(config, sort_keys=True),
            ),
        )
        summary = build_summary(paper)
        paper.commit()
    finally:
        recorder.close()
        paper.close()
    summary.update({
        "generated_at": datetime.now(UTC).isoformat(),
        "source_events_seen_this_run": source_events_seen,
        "signals_written_this_run": signals_written,
        "last_recorder_event_id": last_event_id,
        "failure_counts_this_run": failure_counts,
    })
    return summary


def build_summary(con: sqlite3.Connection) -> dict[str, Any]:
    by_type = {
        row["signal_type"]: dict(row)
        for row in con.execute(
            """
            SELECT signal_type,
                   COUNT(*) AS signals,
                   SUM(CASE WHEN executable=1 THEN 1 ELSE 0 END) AS executable,
                   COALESCE(SUM(simulated_pnl_usd), 0) AS pnl,
                   COALESCE(SUM(CASE WHEN executable=1 THEN simulated_pnl_usd ELSE 0 END), 0) AS executable_pnl,
                   COALESCE(SUM(simulated_cost_usd), 0) AS cost,
                   COALESCE(MIN(adjusted_sum), 0) AS min_adjusted_sum,
                   COALESCE(MAX(adjusted_sum), 0) AS max_adjusted_sum
            FROM bot_l_complete_set_signals
            GROUP BY signal_type
            """
        )
    }
    total = con.execute(
        """
        SELECT COUNT(*) AS signals,
               SUM(CASE WHEN executable=1 THEN 1 ELSE 0 END) AS executable,
               COALESCE(SUM(simulated_pnl_usd), 0) AS pnl,
               COALESCE(SUM(CASE WHEN executable=1 THEN simulated_pnl_usd ELSE 0 END), 0) AS executable_pnl,
               COALESCE(SUM(simulated_cost_usd), 0) AS cost,
               COUNT(DISTINCT condition_id) AS markets
        FROM bot_l_complete_set_signals
        """
    ).fetchone()
    recent = [
        dict(row)
        for row in con.execute(
            """
            SELECT detected_at_ms, signal_type, question, raw_sum, adjusted_sum,
                   simulated_pnl_usd, executable, reason
            FROM bot_l_complete_set_signals
            ORDER BY detected_at_ms DESC, id DESC
            LIMIT 10
            """
        )
    ]
    cost = float(total["cost"] or 0)
    typed_summary = {
        key: {
            "signals": int(value["signals"] or 0),
            "executable": int(value["executable"] or 0),
            "pnl_usd": round(float(value["pnl"] or 0), 4),
            "executable_pnl_usd": round(float(value["executable_pnl"] or 0), 4),
            "min_adjusted_sum": round(float(value["min_adjusted_sum"] or 0), 4),
            "max_adjusted_sum": round(float(value["max_adjusted_sum"] or 0), 4),
        }
        for key, value in by_type.items()
    }
    buy_bucket = typed_summary.get("BUY_COMPLETE_SET", {})
    sell_bucket = typed_summary.get("SELL_COMPLETE_SET", {})
    return {
        "signals": int(total["signals"] or 0),
        "executable_signals": int(total["executable"] or 0),
        "markets": int(total["markets"] or 0),
        "pnl_usd": round(float(total["pnl"] or 0), 4),
        "executable_pnl_usd": round(float(total["executable_pnl"] or 0), 4),
        "buy_executable_pnl_usd": float(buy_bucket.get("executable_pnl_usd", 0.0)),
        "sell_executable_pnl_usd": float(sell_bucket.get("executable_pnl_usd", 0.0)),
        "buy_executable_signals": int(buy_bucket.get("executable", 0)),
        "sell_executable_signals": int(sell_bucket.get("executable", 0)),
        "executable_pnl_by_side": {
            "buy": float(buy_bucket.get("executable_pnl_usd", 0.0)),
            "sell": float(sell_bucket.get("executable_pnl_usd", 0.0)),
        },
        "roi": round(float(total["pnl"] or 0) / cost, 6) if cost else 0.0,
        "by_type": typed_summary,
        "recent": recent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recorder-db-path", type=Path, default=DEFAULT_RECORDER_DB)
    parser.add_argument("--paper-db-path", type=Path, default=DEFAULT_PAPER_DB)
    parser.add_argument("--lookback-hours", type=float, default=24.0)
    parser.add_argument("--raw-buy-threshold", type=float, default=0.995)
    parser.add_argument("--adjusted-buy-threshold", type=float, default=0.995)
    parser.add_argument("--raw-sell-threshold", type=float, default=1.005)
    parser.add_argument("--adjusted-sell-threshold", type=float, default=1.005)
    parser.add_argument("--slippage-per-leg", type=float, default=0.0)
    parser.add_argument("--gross-cost-usd", type=float, default=1.0)
    parser.add_argument("--min-depth-shares", type=float, default=0.0)
    parser.add_argument("--require-depth", action="store_true")
    parser.add_argument("--max-pair-age-ms", type=int, default=1000)
    parser.add_argument("--max-depth-age-ms", type=int, default=1000)
    parser.add_argument("--full-refresh", action="store_true")
    parser.add_argument("--reset-paper", action="store_true")
    args = parser.parse_args()
    report = run_once(
        recorder_db_path=args.recorder_db_path,
        paper_db_path=args.paper_db_path,
        lookback_hours=args.lookback_hours,
        raw_buy_threshold=args.raw_buy_threshold,
        adjusted_buy_threshold=args.adjusted_buy_threshold,
        raw_sell_threshold=args.raw_sell_threshold,
        adjusted_sell_threshold=args.adjusted_sell_threshold,
        slippage_per_leg=args.slippage_per_leg,
        gross_cost_usd=args.gross_cost_usd,
        min_depth_shares=args.min_depth_shares,
        require_depth=args.require_depth,
        max_pair_age_ms=args.max_pair_age_ms,
        max_depth_age_ms=args.max_depth_age_ms,
        incremental=not args.full_refresh,
        reset_paper=args.reset_paper,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
