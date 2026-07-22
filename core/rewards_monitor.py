"""Passive maker-rewards logger.

Produces one JSONL row per UTC day with the quantities needed to decide
whether Polymarket's Liquidity Rewards Program (LRP) materially shifts
any bot's unit economics. Scope: measurement only. No trading decisions
or strategy changes are made from this data.

Columns per row:
  date            — UTC date (YYYY-MM-DD)
  run_at          — UTC timestamp of this snapshot run
  eligible_markets — count of LRP-eligible markets pulled from gamma
  maker_notional_by_bot — {bot_id: usd_notional_filled_as_maker}
  rewards_received_usd — best-effort rewards credited to wallet on this date
  rewards_source  — which endpoint produced the rewards figure (or "unknown")
  notes           — free-text diagnostics

Report (14-day yield per $1 of maker notional) is intentionally a
separate script; keep this one append-only and side-effect-light.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select

from core.db import Order, Trade, get_session_factory

log = logging.getLogger(__name__)

GAMMA_BASE = "https://gamma-api.polymarket.com"
DEFAULT_SNAPSHOT_PATH = Path("data/rewards_snapshot.jsonl")
GAMMA_PAGE_SIZE = 500
GAMMA_MAX_PAGES = 20  # hard cap so a broken API never spins forever

# Polymarket uses "GTC" limit orders as the maker path in this repo; taker
# orders are "FOK" or "IOC". See docs/decisions-log.md ADR-022.
MAKER_ORDER_TYPES = ("GTC",)


@dataclass
class DailySnapshot:
    date: str
    run_at: str
    eligible_markets: int
    eligible_daily_pool_usd: str  # sum of rewardsDailyRate across eligible markets
    maker_notional_by_bot: dict[str, str]  # all markets
    maker_notional_on_eligible_by_bot: dict[str, str]  # eligible markets only
    rewards_received_usd: str
    rewards_source: str
    notes: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))


def fetch_eligible_markets(
    client: httpx.Client, today: date | None = None
) -> list[dict[str, Any]]:
    """Return markets with an active liquidity-rewards pool.

    Gamma's /markets endpoint embeds reward config per market under
    `clobRewards`. A market is eligible if any entry in that list has
    `rewardsDailyRate > 0` and a date window that spans today.
    """
    today_s = (today or datetime.now(UTC).date()).isoformat()
    eligible: list[dict[str, Any]] = []
    offset = 0
    for _ in range(GAMMA_MAX_PAGES):
        try:
            r = client.get(
                f"{GAMMA_BASE}/markets",
                params={
                    "limit": GAMMA_PAGE_SIZE,
                    "offset": offset,
                    "active": "true",
                    "closed": "false",
                },
                timeout=20.0,
            )
            r.raise_for_status()
            batch = r.json() or []
        except Exception as e:
            log.warning("rewards_monitor.eligible.fetch_failed: %s", e)
            break
        if not batch:
            break
        for m in batch:
            for rw in m.get("clobRewards") or []:
                rate = rw.get("rewardsDailyRate") or 0
                if rate <= 0:
                    continue
                start_s = rw.get("startDate") or ""
                end_s = rw.get("endDate") or ""
                if (not start_s or start_s <= today_s) and (not end_s or today_s <= end_s):
                    eligible.append(m)
                    break
        if len(batch) < GAMMA_PAGE_SIZE:
            break
        offset += GAMMA_PAGE_SIZE
    return eligible


def eligible_condition_ids(markets: list[dict[str, Any]]) -> set[str]:
    """Extract condition_ids from a list of market dicts.

    Gamma embeds the condition under `conditionId` on the market and
    again inside each `clobRewards` entry; we take the market-level one
    since that's what Trade rows join on.
    """
    out: set[str] = set()
    for m in markets:
        cid = m.get("conditionId")
        if cid:
            out.add(cid)
    return out


def sum_daily_reward_pool(markets: list[dict[str, Any]]) -> Decimal:
    """Total daily USDC paid across all eligible markets today.

    Context only — not attributable to any bot without quote-quality
    scoring. Useful for judging whether the pool is worth chasing.
    """
    total = Decimal(0)
    for m in markets:
        for rw in m.get("clobRewards") or []:
            rate = rw.get("rewardsDailyRate") or 0
            if rate > 0:
                total += Decimal(str(rate))
    return total


def compute_maker_notional(
    session_factory,
    start: datetime,
    end: datetime,
    eligible_ids: set[str] | None = None,
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """Sum maker-fill USD notional per bot for [start, end).

    Returns (all_markets, eligible_only). Notional = sum(price * size)
    over trades whose parent order was GTC. Paper fills count; fees
    and rebates are ignored — we only want the quote-surface volume
    that *could* have earned rewards.
    """
    Session = session_factory()
    with Session as s:
        stmt = (
            select(
                Trade.bot_id,
                Trade.condition_id,
                func.sum(Trade.price * Trade.size).label("notional"),
            )
            .join(Order, Order.order_id == Trade.order_id)
            .where(
                Trade.filled_at >= start,
                Trade.filled_at < end,
                Order.order_type.in_(MAKER_ORDER_TYPES),
            )
            .group_by(Trade.bot_id, Trade.condition_id)
        )
        rows = s.execute(stmt).all()

    totals: dict[str, Decimal] = {}
    eligible_totals: dict[str, Decimal] = {}
    for bot_id, cid, notional in rows:
        n = Decimal(notional or 0)
        totals[bot_id] = totals.get(bot_id, Decimal(0)) + n
        if eligible_ids and cid in eligible_ids:
            eligible_totals[bot_id] = eligible_totals.get(bot_id, Decimal(0)) + n
    return totals, eligible_totals


def fetch_rewards_for_wallet(
    client: httpx.Client, wallet: str
) -> tuple[Decimal, str, str]:
    """Best-effort fetch of rewards credited to this wallet.

    Polymarket's per-user rewards endpoints require L2-signed CLOB
    auth; the unauthenticated surfaces all return 404/405. This stub
    returns (0, "needs_auth", ...) so the snapshot still records
    notional correctly. Replace with a py-clob-client call once run
    from the bot host with keystore access.
    """
    _ = client, wallet
    return (
        Decimal(0),
        "needs_auth",
        "per-user rewards endpoint requires L2-signed CLOB auth; "
        "run on the bot host with py-clob-client to populate",
    )


def _utc_day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


def snapshot_daily(
    wallet: str | None,
    out_path: Path = DEFAULT_SNAPSHOT_PATH,
    snapshot_date: date | None = None,
    session_factory=None,
    http_client: httpx.Client | None = None,
) -> DailySnapshot:
    """Compute one day's snapshot and append it to the JSONL log.

    Idempotent in the sense that re-running overwrites nothing — the
    report script dedupes by (date, run_at). We keep the full history
    so any late-arriving reward credits can be reconciled.
    """
    d = snapshot_date or (datetime.now(UTC).date() - timedelta(days=1))
    start, end = _utc_day_bounds(d)
    sf = session_factory or get_session_factory()
    owns_client = http_client is None
    client = http_client or httpx.Client(
        headers={"User-Agent": "bot-rewards-monitor/1.0"}
    )
    try:
        eligible = fetch_eligible_markets(client, today=d)
        elig_ids = eligible_condition_ids(eligible)
        pool_usd = sum_daily_reward_pool(eligible)
        notional_all, notional_eligible = compute_maker_notional(
            sf, start, end, elig_ids
        )
        if wallet:
            rewards_usd, source, notes = fetch_rewards_for_wallet(client, wallet)
        else:
            rewards_usd, source, notes = Decimal(0), "skipped", "no wallet provided"
    finally:
        if owns_client:
            client.close()

    snap = DailySnapshot(
        date=d.isoformat(),
        run_at=datetime.now(UTC).isoformat(),
        eligible_markets=len(eligible),
        eligible_daily_pool_usd=str(pool_usd),
        maker_notional_by_bot={k: str(v) for k, v in notional_all.items()},
        maker_notional_on_eligible_by_bot={k: str(v) for k, v in notional_eligible.items()},
        rewards_received_usd=str(rewards_usd),
        rewards_source=source,
        notes=notes,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a") as f:
        f.write(snap.to_json() + "\n")
    log.info(
        "rewards_monitor.snapshot date=%s eligible=%d pool_usd=%s bots=%d rewards=%s source=%s",
        snap.date,
        snap.eligible_markets,
        pool_usd,
        len(notional_all),
        rewards_usd,
        source,
    )
    return snap


if __name__ == "__main__":
    import argparse
    import os

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser(description="Daily maker-rewards snapshot.")
    ap.add_argument("--wallet", default=os.environ.get("HOT_WALLET_ADDRESS"))
    ap.add_argument("--out", default=str(DEFAULT_SNAPSHOT_PATH))
    ap.add_argument("--date", help="YYYY-MM-DD UTC; default = yesterday UTC")
    args = ap.parse_args()

    d = date.fromisoformat(args.date) if args.date else None
    snapshot_daily(args.wallet, Path(args.out), snapshot_date=d)
