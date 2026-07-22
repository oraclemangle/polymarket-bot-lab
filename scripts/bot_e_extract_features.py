#!/usr/bin/env python3
"""Wire signal-reconstruction (from bot_e_calibration_spike) with the
feature extractor (in bots.bot_e_btc_scalp.features) and emit a CSV
the E-2 fit pipeline can consume.

Per `docs/bot-e-model-replacement-plan.md`:

  E-1 calibration spike already proved the formula
  ``predicted_wr = 0.5 + |OBI|/2`` is overconfident. E-2 replaces it
  with a fit model. Step 1 of E-2 is "extract a clean feature dataset
  from recorder tape so the fit step has something to train on." This
  script is that extractor.

What it does
------------

  1. Open the recorder DB (default ``data/bot_e_recorder.db``).
  2. Reuse the spike's signal-reconstruction (``replay_signals``,
     ``detect_resolutions_via_cex``, ``attach_outcomes``).
  3. For each labelled signal, build a ``SignalContext`` from data
     available STRICTLY at or before signal time ``t0_ms``.
  4. Call ``bots.bot_e_btc_scalp.features.extract_features``.
  5. Emit a CSV row per signal: signal_id, *features..., label, side,
     symbol, ts_ms, sub_id, condition_id.

Out of scope (do not invent features here):
  - The polymarket_mid / bid_notional / ask_notional reconstruction
    from book/price_change events is approximate. We use the most
    recent ``last_trade_price`` on the target asset as a proxy mid,
    and zero-out depth notional. ``depth_log_ratio`` and
    ``mid_distance_from_50c`` will be slightly degraded; every other
    feature (OBI windows, CEX CVD, realised vol, TTE bucket, regime
    trend, symbol one-hot) is computed exactly.
  - The actual model fit. That's Step 2; this script's job ends at
    the CSV.

Usage
-----

    .venv/bin/python scripts/bot_e_extract_features.py \\
        --db data/bot_e_recorder.db \\
        --out /tmp/bot_e_features.csv \\
        --since '2026-04-25 00:00:00' --until '2026-04-25 21:00:00'

WARNING — do NOT run on the live recorder DB during normal operations.
``load_cex_prices`` walks the full CEX-trades timeline (1+ M rows on a
production-aged DB), and the SQLite reader pressure starves the
recorder's writer under WAL/lz4 ZFS contention. Observed during
Session 39 dev: a long-running extract caused
``polymarket-bot-e-recorder.service`` heartbeats to fall ~28 min
behind, triggering the external ``recorder.freshness`` watchdog and
halting bot_e. Recover with ``systemctl restart``.

Safe options before invoking this script:
  - Stop the recorder first (``systemctl stop
    polymarket-bot-e-recorder.service``), run extract, restart.
  - OR copy the DB elsewhere first (``sqlite3 src.db
    ".backup target.db"``) and pass --db target.db.
  - OR run during a known idle window.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Reuse the spike's signal reconstruction wholesale — single source of truth.
from scripts.bot_e_calibration_spike import (  # noqa: E402
    SignalObs,
    attach_outcomes,
    build_sub_to_market,
    build_token_to_market,
    detect_resolutions_via_cex,
    load_cex_prices,
    load_markets,
    replay_signals,
)
from bots.bot_e_btc_scalp.features import (  # noqa: E402
    FEATURE_NAMES,
    FeatureVector,
    SignalContext,
    TradeTick,
    extract_features,
)

log = logging.getLogger("bot_e_extract_features")

CSV_HEADER: tuple[str, ...] = (
    "signal_id",
    "ts_ms",
    "sub_id",
    "symbol",
    "side",
    "tte_minutes",
    *FEATURE_NAMES,
    "label",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--db", default="data/bot_e_recorder.db",
                   help="Recorder DB path")
    p.add_argument("--out", required=True,
                   help="Output CSV path")
    p.add_argument("--since", default=None,
                   help="Earliest signal t0 to include (UTC, "
                        "'YYYY-MM-DD HH:MM:SS'); default: no lower bound")
    p.add_argument("--until", default=None,
                   help="Latest signal t0 to include; default: no upper bound")
    p.add_argument("--limit", type=int, default=None,
                   help="Cap signal count (debug)")
    return p.parse_args(argv)


def _parse_ts(s: str | None) -> int | None:
    if s is None:
        return None
    return int(datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
               .replace(tzinfo=timezone.utc).timestamp() * 1000)


def _symbol_from_sub_id(sub_id: str) -> str:
    """Subscription ids are formatted 'btc-20260425T2300', etc.
    The spike code uses ``meta.symbol``; we mirror that here for the
    feature-extractor's symbol_onehot which expects 'BTC' / 'ETH' / 'SOL'."""
    head = sub_id.split("-", 1)[0].upper()
    if head in ("BTC", "ETH", "SOL"):
        return head
    return ""


def _cex_symbol(short: str) -> str:
    """The recorder stores Binance symbols as 'BTCUSDT' / 'ETHUSDT' /
    'SOLUSDT'. SignalContext.symbol expects the short form 'BTC' / 'ETH'
    / 'SOL' (drives symbol_onehot). Translate when querying CEX trades."""
    if short in ("BTC", "ETH", "SOL"):
        return f"{short}USDT"
    return short


def _last_trade_price_at_or_before(
    conn: sqlite3.Connection, *, sub_id: str, asset_id: str | None, t0_ms: int,
) -> float | None:
    """Most recent ``last_trade_price`` event for this asset on this sub
    at or before ``t0_ms``. Used as a proxy for the polymarket mid when we
    can't cheaply rebuild the full L2 book."""
    if asset_id is None:
        return None
    row = conn.execute(
        """
        SELECT payload_json
        FROM pm_events
        WHERE subscription_id = ?
          AND asset_id = ?
          AND event_type = 'last_trade_price'
          AND received_at_ms <= ?
        ORDER BY received_at_ms DESC
        LIMIT 1
        """,
        (sub_id, asset_id, t0_ms),
    ).fetchone()
    if not row:
        return None
    import json
    try:
        p = json.loads(row[0])
    except Exception:
        return None
    raw = p.get("price")
    try:
        v = float(raw) if raw is not None else None
        return v if v is not None and v > 0 else None
    except (TypeError, ValueError):
        return None


def _load_cex_trades_up_to(
    conn: sqlite3.Connection, symbol: str, t0_ms: int,
    *, lookback_ms: int = 600_000,
) -> list[TradeTick]:
    """All CEX trades for this symbol in [t0 - lookback_ms, t0_ms]."""
    rows = conn.execute(
        """
        SELECT received_at_ms, price, size, is_buyer_maker
        FROM cex_trades
        WHERE symbol = ?
          AND received_at_ms BETWEEN ? AND ?
        ORDER BY received_at_ms
        """,
        (symbol, t0_ms - lookback_ms, t0_ms),
    ).fetchall()
    return [
        TradeTick(
            ts_ms=int(ts), price=float(p), size=float(sz),
            is_buyer_maker=bool(m),
        )
        for ts, p, sz, m in rows
    ]


def _cex_price_at_or_before(
    conn: sqlite3.Connection, symbol: str, t_ms: int,
) -> float | None:
    """Last CEX trade price for ``symbol`` at or before ``t_ms``."""
    row = conn.execute(
        """
        SELECT price FROM cex_trades
        WHERE symbol = ? AND received_at_ms <= ?
        ORDER BY received_at_ms DESC
        LIMIT 1
        """,
        (symbol, t_ms),
    ).fetchone()
    return float(row[0]) if row else None


def build_context(
    conn: sqlite3.Connection,
    sig: SignalObs,
    *,
    cex_lookback_ms: int = 600_000,
) -> SignalContext:
    """Build a SignalContext for one signal using strictly-pre-t0 data."""
    symbol = _symbol_from_sub_id(sig.sub_id)

    proxy_mid = _last_trade_price_at_or_before(
        conn, sub_id=sig.sub_id, asset_id=sig.asset_id_at_signal,
        t0_ms=sig.ts_ms,
    )

    cex_sym = _cex_symbol(symbol)
    cex_trades = _load_cex_trades_up_to(
        conn, cex_sym, sig.ts_ms, lookback_ms=cex_lookback_ms,
    )
    cex_price_at_t0 = _cex_price_at_or_before(conn, cex_sym, sig.ts_ms)
    cex_price_10m_ago = _cex_price_at_or_before(
        conn, cex_sym, sig.ts_ms - 10 * 60 * 1000,
    )

    return SignalContext(
        t0_ms=sig.ts_ms,
        tte_minutes=sig.min_to_expiry,
        symbol=symbol,
        polymarket_mid=proxy_mid,
        # Depth notional is unavailable without book reconstruction. Set to
        # zero on both sides so depth_log_ratio returns 0.0; documented as
        # a known limitation in the script docstring.
        bid_notional=0.0,
        ask_notional=0.0,
        cex_trades_up_to_t0=cex_trades,
        cex_price_at_t0=cex_price_at_t0,
        cex_price_10m_ago=cex_price_10m_ago,
    )


def iter_feature_rows(
    db_path: Path,
    *,
    since_ms: int | None = None,
    until_ms: int | None = None,
    limit: int | None = None,
) -> Iterator[tuple[SignalObs, FeatureVector, bool]]:
    """Yield (signal, feature_vector, label) tuples for every labelled
    signal in [since_ms, until_ms] that resolves before db_end_ms."""
    conn = sqlite3.connect(str(db_path))
    try:
        metas = load_markets(conn)
        token_to_market = build_token_to_market(metas)
        sub_to_meta = build_sub_to_market(conn, metas)

        # SQL-level since/until pushes the time-window filter into the
        # pm_events scan so we don't walk the full recorder DB just to
        # get a 24h slice. Critical when the DB is 16+ GB.
        signals, _n_processed = replay_signals(
            conn, token_to_market, sub_to_meta,
            since_ms=since_ms, until_ms=until_ms,
        )
        if limit is not None:
            signals = signals[:limit]

        cex_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        cex_prices = load_cex_prices(conn, cex_symbols)

        # detect_resolutions_via_cex needs the data window so it can
        # exclude markets resolving outside it. Read from cex_trades
        # extremes — same source detect_resolutions uses.
        row = conn.execute(
            "SELECT MIN(trade_time_ms), MAX(trade_time_ms) FROM cex_trades"
        ).fetchone()
        db_start_ms = int(row[0]) if row and row[0] is not None else 0
        db_end_ms = int(row[1]) if row and row[1] is not None else 0

        outcomes = detect_resolutions_via_cex(
            metas, cex_prices, db_start_ms, db_end_ms,
        )
        labelled = attach_outcomes(signals, outcomes, sub_to_meta)

        for sig in labelled:
            if sig.outcome_yes_won is None:
                continue
            ctx = build_context(conn, sig)
            fv = extract_features(
                ctx, signal_id=f"sig-{sig.sub_id}-{sig.ts_ms}",
            )
            yield sig, fv, sig.outcome_yes_won
    finally:
        conn.close()


def write_csv(rows: Iterable[tuple[SignalObs, FeatureVector, bool]],
              out_path: Path) -> int:
    """Write rows to CSV in the order ``CSV_HEADER`` defines.
    Label is encoded as ``BUY_YES_won`` / ``BUY_NO_won`` mapped to
    1 / 0 — i.e. did the signal's BUY side resolve in our favour?"""
    n = 0
    with out_path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_HEADER)
        for sig, fv, yes_won in rows:
            # The signal's "win" condition depends on its side. BUY_YES wins
            # if outcome_yes_won is True; BUY_NO wins if it's False.
            won = yes_won if sig.side == "BUY_YES" else (not yes_won)
            row = (
                f"sig-{sig.sub_id}-{sig.ts_ms}",
                sig.ts_ms,
                sig.sub_id,
                _symbol_from_sub_id(sig.sub_id),
                sig.side,
                f"{sig.min_to_expiry:.3f}",
                *(f"{v:.6f}" for v in fv.as_dict().values()),
                1 if won else 0,
            )
            writer.writerow(row)
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"recorder DB not found: {db_path}", file=sys.stderr)
        return 3

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    since_ms = _parse_ts(args.since)
    until_ms = _parse_ts(args.until)

    log.info(
        "extracting features db=%s out=%s since=%s until=%s limit=%s",
        db_path, out_path, args.since, args.until, args.limit,
    )

    n = write_csv(
        iter_feature_rows(
            db_path, since_ms=since_ms, until_ms=until_ms, limit=args.limit,
        ),
        out_path,
    )
    log.info("wrote %d feature rows to %s", n, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
