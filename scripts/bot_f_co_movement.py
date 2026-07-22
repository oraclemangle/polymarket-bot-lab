#!/usr/bin/env python3
"""Bot F - Co-movement analysis.

Analyzes the overlap between top 'sharp' wallets to determine if they are
taking the same positions (crowded trades) or acting independently.
"""
from __future__ import annotations

import argparse
import logging
import sys
from itertools import combinations
from typing import Any

import httpx

DATA_API_URL = "https://data-api.polymarket.com"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot_f_co_movement")

def fetch_wallet_trades(client: httpx.Client, wallet: str, limit: int = 500) -> list[dict[str, Any]]:
    try:
        r = client.get(
            f"{DATA_API_URL}/trades",
            params={"user": wallet, "limit": limit},
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        log.debug("Failed to fetch trades for %s: %s", wallet, e)
        return []

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wallets", nargs="+", help="List of 2 or more wallet addresses")
    ap.add_argument("--limit", type=int, default=500, help="Max trades per wallet")
    args = ap.parse_args()

    if len(args.wallets) < 2:
        log.error("Requires at least 2 wallets to compare.")
        return 1

    wallet_conditions: dict[str, set[str]] = {}

    with httpx.Client() as client:
        for w in args.wallets:
            log.info("Fetching trades for %s...", w)
            trades = fetch_wallet_trades(client, w, args.limit)
            conditions = set()
            for t in trades:
                cid = t.get("conditionId")
                if cid:
                    conditions.add(cid)
            wallet_conditions[w] = conditions
            log.info("Wallet %s traded %d unique conditions", w, len(conditions))

    print("\nPairwise Overlap (Jaccard Similarity on traded Condition IDs):")
    print(f"{'Wallet A':<15} | {'Wallet B':<15} | {'Overlap':>8} | {'Jaccard':>7}")
    print("-" * 55)

    for w1, w2 in combinations(args.wallets, 2):
        s1 = wallet_conditions[w1]
        s2 = wallet_conditions[w2]
        if not s1 or not s2:
            continue
        intersection = s1.intersection(s2)
        union = s1.union(s2)
        jaccard = len(intersection) / len(union) * 100 if union else 0.0
        w1_short = w1[:12] + ".." if len(w1) > 12 else w1
        w2_short = w2[:12] + ".." if len(w2) > 12 else w2
        print(f"{w1_short:<15} | {w2_short:<15} | {len(intersection):>8} | {jaccard:>6.1f}%")

    return 0

if __name__ == "__main__":
    sys.exit(main())
