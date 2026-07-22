#!/usr/bin/env python3
"""Run one Bot L BUY/MERGE tiny-live probe pass.

The current implemented live action is the BUY-both-legs bundle attempt. Merge
execution is intentionally gated behind actual live fills and a later explicit
on-chain transaction path; this runner refuses to exceed the approved bundle
cap or daily/open exposure caps.
"""

from __future__ import annotations

import argparse
import json
import logging
from decimal import Decimal
from pathlib import Path

from bots.bot_l_complete_set.live_executor import (
    current_open_exposure_usd,
    daily_gross_used_usd,
    latest_executable_signal,
    place_buy_bundle,
    reconcile_live,
)
from core.clob_v2 import ClobWrapperV2
from core.config import get_settings
from core.db import init_db
from core.keystore import Keystore

log = logging.getLogger("bot_l_complete_set_live_probe")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--paper-db-path", type=Path, default=Path("data/bot_l_complete_set_paper.db"))
    p.add_argument("--max-bundle-usd", type=Decimal, default=Decimal("1"))
    p.add_argument("--daily-gross-cap-usd", type=Decimal, default=Decimal("10"))
    p.add_argument("--open-exposure-cap-usd", type=Decimal, default=Decimal("20"))
    p.add_argument("--max-signal-age-ms", type=int, default=120_000)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--log-level", default="INFO")
    return p


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    init_db()
    settings = get_settings()
    if not settings.is_live() and not args.dry_run:
        raise SystemExit("Bot L live probe requires POLYMARKET_ENV=live or --dry-run")

    signal = latest_executable_signal(args.paper_db_path, max_signal_age_ms=args.max_signal_age_ms)
    if signal is None:
        print(json.dumps({"placed": False, "reason": "no_executable_signal"}, sort_keys=True))
        return 0

    if args.dry_run:
        clob = ClobWrapperV2(keystore=None, paper_override=True)
    else:
        keystore = Keystore.load(settings.polymarket_keystore_path, settings.polymarket_passphrase_path)
        clob = ClobWrapperV2(keystore=keystore, paper_override=False)
        clob.load_preflight_from_db()
        reconcile_live(clob)

    daily_used = Decimal("0") if args.dry_run else daily_gross_used_usd()
    open_exposure = Decimal("0") if args.dry_run else current_open_exposure_usd()
    result = place_buy_bundle(
        clob,
        signal,
        max_bundle_usd=args.max_bundle_usd,
        daily_gross_used_usd=daily_used,
        daily_gross_cap_usd=args.daily_gross_cap_usd,
        open_exposure_usd=open_exposure,
        open_exposure_cap_usd=args.open_exposure_cap_usd,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.__dict__, default=str, sort_keys=True))
    ok_reasons = {
        "placed",
        "dry_run",
        "no_executable_signal",
        "below_exchange_min_shares",
        "dedupe",
    }
    if result.reason.startswith("live_book_unavailable:"):
        return 0
    return 0 if result.reason in ok_reasons else 1


if __name__ == "__main__":
    raise SystemExit(main())
