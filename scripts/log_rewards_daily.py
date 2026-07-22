#!/usr/bin/env python3
"""Daily runner for the passive maker-rewards snapshot.

Intended to be called once per day after UTC midnight, recording
yesterday's maker notional per bot and any rewards credited to the
hot wallet. Designed to be scheduled by a systemd timer on the bot host.
No live trading, no wallet writes, no order placement. Read-only
against local DB and public Polymarket endpoints.

Usage:
    python -m scripts.log_rewards_daily [--wallet 0x...] [--date YYYY-MM-DD]

Env:
    HOT_WALLET_ADDRESS — fallback if --wallet is omitted.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from core.rewards_monitor import DEFAULT_SNAPSHOT_PATH, snapshot_daily  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser(description="Daily maker-rewards snapshot.")
    ap.add_argument("--wallet", default=os.environ.get("HOT_WALLET_ADDRESS"))
    ap.add_argument("--out", default=str(DEFAULT_SNAPSHOT_PATH))
    ap.add_argument("--date", help="YYYY-MM-DD UTC; default = yesterday UTC")
    args = ap.parse_args()

    d = date.fromisoformat(args.date) if args.date else None
    snap = snapshot_daily(args.wallet, Path(args.out), snapshot_date=d)
    print(snap.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
