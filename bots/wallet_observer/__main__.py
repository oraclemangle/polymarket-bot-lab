"""Entrypoint for the wallet observer service.

Polls Polygon RPC every `WALLET_OBSERVER_POLL_INTERVAL_S` seconds for
OrderFilled events on the CTF + NegRiskCTF exchanges; writes any fill
where the maker or taker matches our 245-wallet whitelist.

Read-only: no signing, no orders, no operator wallet access.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from datetime import UTC, datetime

from bots.wallet_observer import config as cfg
from bots.wallet_observer.collector import Collector
from bots.wallet_observer.whitelist import Whitelist

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Wallet observer — passive Polygon CTF Exchange recorder")
    p.add_argument("--once", action="store_true",
                   help="run one polling cycle and exit (smoke test)")
    p.add_argument("--poll-interval-s", type=float, default=cfg.POLL_INTERVAL_S)
    p.add_argument("--lookback-blocks", type=int, default=cfg.INITIAL_LOOKBACK_BLOCKS)
    p.add_argument("--max-range", type=int, default=cfg.MAX_BLOCK_RANGE_PER_POLL)
    p.add_argument("--finality-lag-blocks", type=int, default=cfg.FINALITY_LAG_BLOCKS)
    p.add_argument("--rpc-url", default=cfg.POLYGON_RPC_URL)
    p.add_argument("--whitelist-csv", default=str(cfg.WHITELIST_CSV))
    p.add_argument("--db-path", default=str(cfg.WALLET_OBSERVER_DB))
    p.add_argument("--log-level", default="INFO")
    return p


_should_stop = False


def _install_signal_handlers() -> None:
    def handler(signum, frame):
        global _should_stop
        log.info("wallet_observer.signal received=%d shutting_down", signum)
        _should_stop = True
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, handler)


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    whitelist = Whitelist.load(args.whitelist_csv)
    log.info(
        "wallet_observer.startup tiers=%s n_wallets=%d rpc=%s db=%s",
        sorted(cfg.INCLUDED_TIERS), len(whitelist), args.rpc_url, args.db_path,
    )
    log.info("wallet_observer.tier_breakdown %s", whitelist.tier_counts())

    collector = Collector(
        whitelist=whitelist,
        rpc_url=args.rpc_url,
        db_path=args.db_path,
    )
    if not collector.is_connected():
        log.error("wallet_observer.rpc_unreachable url=%s", args.rpc_url)
        return 2

    # Open run record
    run_started = int(time.time())
    cur = collector.con.execute(
        "INSERT INTO observer_runs (started_at, n_fills, n_polls) VALUES (?, 0, 0)",
        (run_started,),
    )
    run_id = cur.lastrowid

    _install_signal_handlers()
    n_polls = 0
    n_fills_total = 0
    last_block_per_ex: dict[str, int] = {}
    try:
        while not _should_stop:
            try:
                fills, state = collector.poll_once(
                    max_range=args.max_range,
                    initial_lookback=args.lookback_blocks,
                    finality_lag=args.finality_lag_blocks,
                    run_id=run_id,
                )
                n_polls += 1
                n_fills_total += fills
                last_block_per_ex = state
                max_block = max(last_block_per_ex.values()) if last_block_per_ex else None
                collector.con.execute(
                    """
                    UPDATE observer_runs
                    SET n_fills=?, n_polls=?, last_block=?
                    WHERE run_id=?
                    """,
                    (n_fills_total, n_polls, max_block, run_id),
                )
                log.info(
                    "wallet_observer.cycle_done fills=%d total=%d state=%s at=%s",
                    fills, n_fills_total, state, datetime.now(UTC).isoformat(),
                )
            except Exception as e:
                log.exception("wallet_observer.cycle_error err=%s", e)
            if args.once:
                break
            # Sleep with periodic check for shutdown signal.
            sleep_left = args.poll_interval_s
            while sleep_left > 0 and not _should_stop:
                step = min(1.0, sleep_left)
                time.sleep(step)
                sleep_left -= step
    finally:
        max_block = max(last_block_per_ex.values()) if last_block_per_ex else None
        collector.con.execute(
            "UPDATE observer_runs SET stopped_at=?, n_fills=?, n_polls=?, last_block=? WHERE run_id=?",
            (int(time.time()), n_fills_total, n_polls, max_block, run_id),
        )
        log.info(
            "wallet_observer.shutdown run_id=%s polls=%d fills=%d last_block=%s",
            run_id, n_polls, n_fills_total, max_block,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
