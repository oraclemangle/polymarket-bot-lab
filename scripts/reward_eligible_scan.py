#!/usr/bin/env python3
"""Report-only Polymarket reward eligibility scan.

This script does not place, cancel, or modify orders. It reads the local
orders/trades DB, fetches public Polymarket rewards configuration, and writes a
markdown report describing whether current maker activity is eligible for
liquidity rewards or maker rebates.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.bot_registry import REGISTRY  # noqa: E402
from core.db import Order, Trade, get_session_factory  # noqa: E402

REWARDS_URL = "https://clob.polymarket.com/rewards/markets/multi"
CLOB_MARKET_URL = "https://clob.polymarket.com/clob-markets/{condition_id}"
DEFAULT_REPORT_DIR = Path("docs/reports")
MAKER_ORDER_TYPES = {"GTC", "GTD"}
OPEN_STATUSES = {"OPEN", "PARTIAL", "live"}


@dataclass(frozen=True)
class RewardMarket:
    condition_id: str
    question: str
    market_slug: str
    event_slug: str
    reward_per_day: Decimal
    rewards_min_size: Decimal
    rewards_max_spread_cents: Decimal
    spread: Decimal | None
    volume_24hr: Decimal | None
    tokens: tuple[dict[str, Any], ...]


def _decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except Exception:
        return Decimal(default)


def _fetch_reward_markets(
    client: httpx.Client,
    *,
    max_pages: int,
    page_limit: int = 25,
) -> list[RewardMarket]:
    markets: list[RewardMarket] = []
    cursor: str | None = None
    for _ in range(max_pages):
        params: dict[str, Any] = {"limit": page_limit}
        if cursor:
            params["next_cursor"] = cursor
        page_failed = False
        for attempt in range(3):
            response = client.get(REWARDS_URL, params=params, timeout=20)
            if response.status_code < 500:
                response.raise_for_status()
                break
            if attempt == 2:
                if markets:
                    page_failed = True
                    break
                response.raise_for_status()
        if page_failed:
            break
        payload = response.json()
        for raw in payload.get("data") or []:
            configs = raw.get("rewards_config") or []
            reward_per_day = sum(
                (_decimal(config.get("rate_per_day")) for config in configs),
                Decimal("0"),
            )
            condition_id = str(raw.get("condition_id") or "")
            if not condition_id:
                continue
            markets.append(
                RewardMarket(
                    condition_id=condition_id,
                    question=str(raw.get("question") or ""),
                    market_slug=str(raw.get("market_slug") or ""),
                    event_slug=str(raw.get("event_slug") or ""),
                    reward_per_day=reward_per_day,
                    rewards_min_size=_decimal(raw.get("rewards_min_size")),
                    rewards_max_spread_cents=_decimal(raw.get("rewards_max_spread")),
                    spread=(
                        _decimal(raw.get("spread"))
                        if raw.get("spread") is not None
                        else None
                    ),
                    volume_24hr=(
                        _decimal(raw.get("volume_24hr"))
                        if raw.get("volume_24hr") is not None
                        else None
                    ),
                    tokens=tuple(raw.get("tokens") or ()),
                )
            )
        cursor = payload.get("next_cursor")
        if not cursor or cursor == "LTE=":
            break
    return markets


def _live_bot_ids() -> list[str]:
    return [meta.bot_id for meta in REGISTRY if str(meta.status) == "live"]


def _load_orders_and_trades(bot_ids: set[str], lookback_hours: int) -> tuple[list[Order], list[Trade]]:
    cutoff = datetime.now(UTC) - timedelta(hours=lookback_hours)
    with get_session_factory()() as session:
        orders = (
            session.query(Order)
            .filter(Order.bot_id.in_(sorted(bot_ids)))
            .filter(Order.placed_at >= cutoff)
            .order_by(Order.placed_at.desc())
            .all()
        )
        trades = (
            session.query(Trade)
            .join(Order, Order.order_id == Trade.order_id)
            .filter(Trade.bot_id.in_(sorted(bot_ids)))
            .filter(Trade.filled_at >= cutoff)
            .filter(Order.order_type.in_(sorted(MAKER_ORDER_TYPES)))
            .order_by(Trade.filled_at.desc())
            .all()
        )
    return orders, trades


def _token_price(market: RewardMarket, token_id: str) -> Decimal | None:
    for token in market.tokens:
        if str(token.get("token_id") or "") == str(token_id):
            return _decimal(token.get("price"))
    return None


def _order_reward_check(order: Order, market: RewardMarket) -> tuple[bool, str]:
    if str(order.order_type or "") not in MAKER_ORDER_TYPES:
        return False, "not maker order type"
    if order.price is None or order.size is None:
        return False, "missing price or size"
    if Decimal(order.size) < market.rewards_min_size:
        return False, f"size {Decimal(order.size)} < min {market.rewards_min_size}"
    token_price = _token_price(market, str(order.token_id))
    if token_price is None:
        return False, "token not found in reward market response"
    distance_cents = abs(Decimal(order.price) - token_price) * Decimal("100")
    if distance_cents > market.rewards_max_spread_cents:
        return False, (
            f"distance {distance_cents:.2f}c > max "
            f"{market.rewards_max_spread_cents}c"
        )
    return True, "inside reward band"


def _fetch_fee_info(client: httpx.Client, condition_ids: set[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for condition_id in sorted(condition_ids):
        try:
            response = client.get(
                CLOB_MARKET_URL.format(condition_id=condition_id),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            out[condition_id] = data if isinstance(data, dict) else {}
        except Exception as exc:
            out[condition_id] = {"error": str(exc)[:160]}
    return out


def _format_money(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:.2f}"


def _fmt(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}".rstrip("0").rstrip(".")


def build_report(
    *,
    markets: list[RewardMarket],
    orders: list[Order],
    trades: list[Trade],
    fee_info: dict[str, dict[str, Any]],
    lookback_hours: int,
) -> str:
    now = datetime.now(UTC)
    reward_by_condition = {market.condition_id: market for market in markets}
    reward_conditions = set(reward_by_condition)
    daily_pool = sum((market.reward_per_day for market in markets), Decimal("0"))

    orders_by_bot: dict[str, list[Order]] = defaultdict(list)
    for order in orders:
        orders_by_bot[str(order.bot_id)].append(order)

    trades_by_bot: dict[str, list[Trade]] = defaultdict(list)
    for trade in trades:
        trades_by_bot[str(trade.bot_id)].append(trade)

    lines = [
        "# Reward Eligibility Scan - 2026-05-16",
        "",
        "**Status:** report-only. No orders were placed, cancelled, or modified.",
        "",
        f"Generated: `{now.isoformat()}`",
        f"Lookback: `{lookback_hours}` hours",
        f"Reward markets fetched: `{len(markets)}`",
        f"Published daily reward pool fetched: `{_format_money(daily_pool)}`",
        "",
        "## Current Bot Overlap",
        "",
        "| Bot | Orders | Reward-market orders | Qualifying open orders | Maker fills | Reward-market maker fill notional | Rebate fee-enabled fills | Read |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]

    all_bots = sorted(set(orders_by_bot) | set(trades_by_bot))
    for bot_id in all_bots:
        bot_orders = orders_by_bot.get(bot_id, [])
        bot_trades = trades_by_bot.get(bot_id, [])
        reward_orders = [o for o in bot_orders if str(o.condition_id) in reward_conditions]
        qualifying_open = 0
        disqualifiers = Counter()
        for order in reward_orders:
            if str(order.status) not in OPEN_STATUSES:
                continue
            ok, reason = _order_reward_check(order, reward_by_condition[str(order.condition_id)])
            if ok:
                qualifying_open += 1
            else:
                disqualifiers[reason] += 1
        reward_trade_notional = sum(
            (
                Decimal(trade.price) * Decimal(trade.size)
                for trade in bot_trades
                if str(trade.condition_id) in reward_conditions
            ),
            Decimal("0"),
        )
        fee_enabled_fills = 0
        for trade in bot_trades:
            info = fee_info.get(str(trade.condition_id)) or {}
            tbf = _decimal(info.get("tbf")) if "tbf" in info else Decimal("0")
            fd = info.get("fd") if isinstance(info.get("fd"), dict) else {}
            fd_rate = _decimal(fd.get("r")) if fd else Decimal("0")
            if tbf > 0 or fd_rate > 0:
                fee_enabled_fills += 1
        if qualifying_open:
            read = "currently reward-scoring candidate"
        elif reward_orders:
            common = disqualifiers.most_common(1)
            read = common[0][0] if common else "reward market but no open scoring order"
        elif reward_trade_notional > 0:
            read = "had maker fills on reward market"
        elif fee_enabled_fills:
            read = "maker rebate candidate only"
        else:
            read = "no reward overlap in lookback"
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{bot_id}`",
                    str(len(bot_orders)),
                    str(len(reward_orders)),
                    str(qualifying_open),
                    str(len(bot_trades)),
                    _format_money(reward_trade_notional),
                    str(fee_enabled_fills),
                    read,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Top Reward Markets",
            "",
            "| Daily reward | Min size | Max spread | Spread | Volume 24h | Market |",
            "|---:|---:|---:|---:|---:|---|",
        ]
    )
    for market in sorted(markets, key=lambda m: m.reward_per_day, reverse=True)[:20]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _format_money(market.reward_per_day),
                    _fmt(market.rewards_min_size),
                    f"{_fmt(market.rewards_max_spread_cents)}c",
                    _fmt(market.spread),
                    _format_money(market.volume_24hr),
                    market.question.replace("|", "\\|")[:120],
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Maker execution is still the right default direction for ROI, but this scan does not justify converting every live bot blindly.",
            "- Liquidity rewards require active reward markets, sufficient order size, and quotes inside the published spread band.",
            "- Maker rebates are separate from liquidity rewards: they require maker fills in fee-enabled markets and should be reconciled as realised USDC credits before being counted as strategy edge.",
            "- Current FV and Bot D maker caps are intentionally tiny; many reward markets require much larger share size than our safety caps allow.",
            "- Do not increase order size just to chase rewards until the expected reward can beat adverse-selection and inventory risk.",
            "",
            "## Next Gates",
            "",
            "1. Add daily read-only reward snapshots for current live maker bots.",
            "2. Reconcile actual reward/rebate credits from `/rewards/user/markets` with L2 auth on the bot container.",
            "3. Only include rewards in ROI after observed USDC credits clear the `$1` payout floor.",
            "4. If reward overlap remains low, keep rewards as a reporting tag rather than a trading objective.",
            "5. If reward overlap is high and observed credits are material, propose a separate reward-aware paper maker lane with explicit caps.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--page-limit", type=int, default=25)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--bot", action="append", help="bot_id to include; repeatable")
    args = parser.parse_args()

    bot_ids = set(args.bot or _live_bot_ids())
    with httpx.Client(headers={"User-Agent": "longshot-reward-eligible-scan/1.0"}) as client:
        markets = _fetch_reward_markets(
            client,
            max_pages=args.max_pages,
            page_limit=args.page_limit,
        )
        orders, trades = _load_orders_and_trades(bot_ids, args.lookback_hours)
        condition_ids = {str(order.condition_id) for order in orders} | {
            str(trade.condition_id) for trade in trades
        }
        fee_info = _fetch_fee_info(client, condition_ids)

    report = build_report(
        markets=markets,
        orders=orders,
        trades=trades,
        fee_info=fee_info,
        lookback_hours=args.lookback_hours,
    )
    out = args.out or args.report_dir / "reward-eligible-scan-2026-05-16.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
