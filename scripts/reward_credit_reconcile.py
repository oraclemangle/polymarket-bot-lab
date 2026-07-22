#!/usr/bin/env python3
"""Read-only Polymarket reward and maker-rebate credit reconciliation."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import get_settings  # noqa: E402
from core.db import Order, Trade, get_session_factory  # noqa: E402
from core.keystore import Keystore  # noqa: E402

HOST = "https://clob.polymarket.com"
REBATES_CURRENT_URL = f"{HOST}/rebates/current"
DEFAULT_OUT = Path("docs/reports/reward-credit-reconcile-2026-05-16.md")
MAKER_ORDER_TYPES = {"GTC", "GTD"}


@dataclass(frozen=True)
class LocalMakerFill:
    bot_id: str
    condition_id: str
    notional: Decimal
    fill_count: int


def _decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value if value is not None else default))
    except Exception:
        return Decimal(default)


def _money(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:.6f}".rstrip("0").rstrip(".")


def _mask(address: str) -> str:
    if not address:
        return "n/a"
    return f"{address[:8]}...{address[-6:]}"


def _dates(days: int, end_date: date | None = None) -> list[date]:
    end = end_date or datetime.now(UTC).date()
    start = end - timedelta(days=max(days - 1, 0))
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _live_bot_ids() -> set[str]:
    from core.bot_registry import REGISTRY

    return {meta.bot_id for meta in REGISTRY if str(meta.status) == "live"}


def _load_local_maker_fills(bot_ids: set[str], start: datetime, end: datetime) -> list[LocalMakerFill]:
    with get_session_factory()() as session:
        rows = (
            session.query(
                Trade.bot_id,
                Trade.condition_id,
                Trade.price,
                Trade.size,
            )
            .join(Order, Order.order_id == Trade.order_id)
            .filter(Trade.bot_id.in_(sorted(bot_ids)))
            .filter(Trade.filled_at >= start)
            .filter(Trade.filled_at < end)
            .filter(Order.order_type.in_(sorted(MAKER_ORDER_TYPES)))
            .all()
        )

    totals: dict[tuple[str, str], tuple[Decimal, int]] = {}
    for bot_id, condition_id, price, size in rows:
        key = (str(bot_id), str(condition_id))
        prev_notional, prev_count = totals.get(key, (Decimal("0"), 0))
        totals[key] = (
            prev_notional + (_decimal(price) * _decimal(size)),
            prev_count + 1,
        )
    return [
        LocalMakerFill(bot_id=bot_id, condition_id=condition_id, notional=notional, fill_count=count)
        for (bot_id, condition_id), (notional, count) in sorted(totals.items())
    ]


def _build_clob_client():
    from py_clob_client_v2 import ClobClient

    settings = get_settings()
    keystore = Keystore.load_from_settings(settings)
    signer = keystore.signer()
    kwargs: dict[str, Any] = {
        "host": settings.polymarket_host or HOST,
        "chain_id": settings.chain_id,
        "key": signer.key.hex(),
    }
    if settings.polymarket_signature_type is not None:
        kwargs["signature_type"] = settings.polymarket_signature_type
    if settings.polymarket_funder_address:
        kwargs["funder"] = settings.polymarket_funder_address
    client = ClobClient(**kwargs)
    client.set_api_creds(client.derive_api_key())
    return client, keystore.address, settings.polymarket_funder_address or ""


def _call_l2(client: Any, fn_name: str, *args: Any) -> tuple[Any, str | None]:
    try:
        return getattr(client, fn_name)(*args), None
    except Exception as exc:
        return None, str(exc)[:240]


def _fetch_rebates(maker_addresses: list[str], days: list[date]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    with httpx.Client(headers={"User-Agent": "longshot-reward-credit-reconcile/1.0"}) as http:
        for maker in maker_addresses:
            if not maker:
                continue
            for d in days:
                try:
                    response = http.get(
                        REBATES_CURRENT_URL,
                        params={"date": d.isoformat(), "maker_address": maker},
                        timeout=20,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if isinstance(payload, list):
                        rows.extend(payload)
                except Exception as exc:
                    errors.append(f"{d.isoformat()} {_mask(maker)} {str(exc)[:160]}")
    return rows, errors


def _sum_field(rows: list[dict[str, Any]], field: str) -> Decimal:
    return sum((_decimal(row.get(field)) for row in rows), Decimal("0"))


def _render_report(
    *,
    run_at: datetime,
    days: list[date],
    signer_address: str,
    maker_address: str,
    totals_by_day: dict[str, Any],
    totals_errors: dict[str, str | None],
    user_market_rows: list[dict[str, Any]],
    user_market_error: str | None,
    reward_percentages: dict[str, Any] | None,
    reward_percentages_error: str | None,
    rebate_rows: list[dict[str, Any]],
    rebate_errors: list[str],
    local_fills: list[LocalMakerFill],
) -> str:
    local_by_condition: dict[str, Decimal] = defaultdict(Decimal)
    local_by_bot: dict[str, Decimal] = defaultdict(Decimal)
    local_fill_counts: dict[str, int] = defaultdict(int)
    local_by_condition_bot: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for fill in local_fills:
        local_by_condition[fill.condition_id] += fill.notional
        local_by_bot[fill.bot_id] += fill.notional
        local_fill_counts[fill.bot_id] += fill.fill_count
        local_by_condition_bot[fill.condition_id][fill.bot_id] += fill.notional

    rebate_total = _sum_field(rebate_rows, "rebated_fees_usdc")
    rebate_by_condition: dict[str, Decimal] = defaultdict(Decimal)
    for row in rebate_rows:
        rebate_by_condition[str(row.get("condition_id") or "")] += _decimal(
            row.get("rebated_fees_usdc")
        )
    attributed_rebate_by_bot: dict[str, Decimal] = defaultdict(Decimal)
    unattributed_rebate = Decimal("0")
    for condition_id, rebate in rebate_by_condition.items():
        bot_notional = local_by_condition_bot.get(condition_id) or {}
        condition_notional = sum(bot_notional.values(), Decimal("0"))
        if condition_notional <= 0:
            unattributed_rebate += rebate
            continue
        for bot_id, notional in bot_notional.items():
            attributed_rebate_by_bot[bot_id] += rebate * notional / condition_notional
    earnings_total = sum(
        (_decimal(row.get("total") or row.get("earnings") or row.get("amount")) for row in totals_by_day.values() if isinstance(row, dict)),
        Decimal("0"),
    )

    market_earnings_total = sum(
        (_decimal(row.get("earnings") or row.get("earning") or row.get("rewards")) for row in user_market_rows),
        Decimal("0"),
    )

    lines = [
        "# Reward Credit Reconciliation - 2026-05-16",
        "",
        "**Status:** read-only. No orders, cancellations, transfers, wraps, or redemptions were submitted.",
        "",
        f"Generated: `{run_at.isoformat()}`",
        f"Date window: `{days[0].isoformat()}` to `{days[-1].isoformat()}`",
        f"Signer address: `{_mask(signer_address)}`",
        f"Maker/funder address: `{_mask(maker_address)}`" if maker_address else "Maker/funder address: `n/a`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Authenticated reward total from `/rewards/user/total` | {_money(earnings_total)} |",
        f"| Market-row earnings from `/rewards/user/markets` | {_money(market_earnings_total)} |",
        f"| Public maker rebates from `/rebates/current` | {_money(rebate_total)} |",
        f"| Public rebates attributed to local live bots | {_money(sum(attributed_rebate_by_bot.values(), Decimal('0')))} |",
        f"| Public rebates not matched to local live fills | {_money(unattributed_rebate)} |",
        f"| Current reward percentage markets | {len(reward_percentages or {})} |",
        f"| Local live-maker notional in window | {_money(sum(local_by_bot.values(), Decimal('0')))} |",
        "",
        "## Local Live Maker Fills",
        "",
        "| Bot | Maker fills | Maker notional |",
        "|---|---:|---:|",
    ]
    if local_by_bot:
        for bot_id in sorted(local_by_bot):
            lines.append(
                f"| `{bot_id}` | {local_fill_counts[bot_id]} | {_money(local_by_bot[bot_id])} |"
            )
    else:
        lines.append("| n/a | 0 | $0 |")

    lines.extend(
        [
            "",
            "## Rebate Attribution",
            "",
            "| Bot | Attributed rebate | Rebate / maker notional |",
            "|---|---:|---:|",
        ]
    )
    if attributed_rebate_by_bot:
        for bot_id in sorted(attributed_rebate_by_bot):
            notional = local_by_bot.get(bot_id, Decimal("0"))
            ratio = (
                attributed_rebate_by_bot[bot_id] / notional
                if notional > 0
                else Decimal("0")
            )
            lines.append(
                f"| `{bot_id}` | {_money(attributed_rebate_by_bot[bot_id])} | {ratio:.4%} |"
            )
    else:
        lines.append("| n/a | $0 | 0.0000% |")

    lines.extend(
        [
            "",
            "## Daily Authenticated Reward Totals",
            "",
            "| Date | Total | Error |",
            "|---|---:|---|",
        ]
    )
    for d in days:
        key = d.isoformat()
        payload = totals_by_day.get(key)
        amount = Decimal("0")
        if isinstance(payload, dict):
            amount = _decimal(payload.get("total") or payload.get("earnings") or payload.get("amount"))
        lines.append(f"| `{key}` | {_money(amount)} | {totals_errors.get(key) or ''} |")

    lines.extend(
        [
            "",
            "## Public Maker Rebates",
            "",
            "| Date | Condition | Rebate |",
            "|---|---|---:|",
        ]
    )
    if rebate_rows:
        for row in sorted(rebate_rows, key=lambda r: (str(r.get("date")), str(r.get("condition_id")))):
            cid = str(row.get("condition_id") or "")
            lines.append(
                f"| `{row.get('date')}` | `{cid[:12]}...` | {_money(_decimal(row.get('rebated_fees_usdc')))} |"
            )
    else:
        lines.append("| n/a | n/a | $0 |")

    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            f"- `/rewards/user/markets` rows: `{len(user_market_rows)}`"
            + (f"; error: `{user_market_error}`" if user_market_error else ""),
            f"- `/rewards/user/percentages` error: `{reward_percentages_error}`" if reward_percentages_error else "- `/rewards/user/percentages` returned successfully.",
            f"- `/rebates/current` errors: `{len(rebate_errors)}`",
            "",
            "## Interpretation",
            "",
            "- Reward and rebate credits remain excluded from realised bot ROI unless a non-zero credited amount appears here.",
            "- If totals remain below the payout floor, rebates may be real economically but should not be promoted into dashboard P&L yet.",
            "- Maker execution is still the better execution posture, but reward chasing should remain separate from strategy EV until credits are observed.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--end-date", type=lambda s: date.fromisoformat(s), default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    days = _dates(args.days, args.end_date)
    start = datetime.combine(days[0], datetime.min.time(), tzinfo=UTC)
    end = datetime.combine(days[-1] + timedelta(days=1), datetime.min.time(), tzinfo=UTC)

    client, signer_address, funder_address = _build_clob_client()
    maker_address = funder_address or signer_address

    totals_by_day: dict[str, Any] = {}
    totals_errors: dict[str, str | None] = {}
    for d in days:
        payload, err = _call_l2(client, "get_total_earnings_for_user_for_day", d.isoformat())
        totals_by_day[d.isoformat()] = payload or {}
        totals_errors[d.isoformat()] = err

    user_market_rows: list[dict[str, Any]] = []
    user_market_error: str | None = None
    payload, user_market_error = _call_l2(
        client,
        "get_user_earnings_and_markets_config",
        days[-1].isoformat(),
    )
    if isinstance(payload, list):
        user_market_rows = payload

    reward_percentages_payload, reward_percentages_error = _call_l2(
        client,
        "get_reward_percentages",
    )
    reward_percentages = reward_percentages_payload if isinstance(reward_percentages_payload, dict) else None

    maker_addresses = list(dict.fromkeys([maker_address, signer_address]))
    rebate_rows, rebate_errors = _fetch_rebates(maker_addresses, days)
    local_fills = _load_local_maker_fills(_live_bot_ids(), start, end)

    report = _render_report(
        run_at=datetime.now(UTC),
        days=days,
        signer_address=signer_address,
        maker_address=maker_address,
        totals_by_day=totals_by_day,
        totals_errors=totals_errors,
        user_market_rows=user_market_rows,
        user_market_error=user_market_error,
        reward_percentages=reward_percentages,
        reward_percentages_error=reward_percentages_error,
        rebate_rows=rebate_rows,
        rebate_errors=rebate_errors,
        local_fills=local_fills,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
