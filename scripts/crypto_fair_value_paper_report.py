#!/usr/bin/env python3
"""Daily report for crypto fair-value paper bots."""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.config import get_settings  # noqa: E402

DEFAULT_OUT_MD = REPO_ROOT / "data" / "reports" / "crypto_fair_value_paper" / "latest.md"
DEFAULT_OUT_JSON = REPO_ROOT / "data" / "reports" / "crypto_fair_value_paper" / "latest.json"
DEFAULT_BOT_IDS = ("crypto_probability_gap_paper", "crypto_brownian_fv_paper")


@dataclass
class GroupStats:
    signals: int = 0
    fills: int = 0
    no_fills: int = 0
    closed: int = 0
    wins: int = 0
    gross_pnl: Decimal = Decimal("0")
    fee_stressed_pnl: Decimal = Decimal("0")
    rois: list[float] = field(default_factory=list)
    edges: list[Decimal] = field(default_factory=list)
    spreads: list[Decimal] = field(default_factory=list)
    depths: list[Decimal] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        avg_roi = statistics.fmean(self.rois) if self.rois else 0.0
        median_roi = statistics.median(self.rois) if self.rois else 0.0
        return {
            "signals": self.signals,
            "simulated_fills": self.fills,
            "no_fills": self.no_fills,
            "fill_rate": self.fills / self.signals if self.signals else 0.0,
            "closed_positions": self.closed,
            "wins": self.wins,
            "hit_rate": self.wins / self.closed if self.closed else 0.0,
            "gross_pnl": float(self.gross_pnl),
            "fee_stressed_pnl": float(self.fee_stressed_pnl),
            "raw_roi": avg_roi,
            "median_roi": median_roi,
            "ex_largest_win_roi": _trimmed_mean(self.rois, 1),
            "ex_largest_two_roi": _trimmed_mean(self.rois, 2),
            "average_model_edge": float(_avg_decimal(self.edges)),
            "average_spread": float(_avg_decimal(self.spreads)),
            "average_top_depth": float(_avg_decimal(self.depths)),
        }


def _trimmed_mean(values: list[float], n_largest: int) -> float:
    if not values or len(values) <= n_largest:
        return 0.0
    return statistics.fmean(sorted(values)[:-n_largest])


def _avg_decimal(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def _payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    if value.endswith("d"):
        return datetime.now(UTC) - timedelta(days=int(value[:-1]))
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _dt_filter(since: datetime | None) -> tuple[str, list[str]]:
    if since is None:
        return "", []
    since_utc = since.astimezone(UTC) if since.tzinfo else since.replace(tzinfo=UTC)
    # SQLAlchemy stores SQLite DateTime values as "YYYY-MM-DD HH:MM:SS.ffffff".
    # Use the same shape so lexical filtering works on same-day reports.
    return " AND created_at >= ?", [since_utc.strftime("%Y-%m-%d %H:%M:%S.%f")]


def build_report(
    *,
    db_path: Path,
    bot_ids: tuple[str, ...] = DEFAULT_BOT_IDS,
    since: datetime | None = None,
) -> dict[str, Any]:
    bot_set = set(bot_ids)
    groups: dict[tuple[str, ...], GroupStats] = defaultdict(GroupStats)
    scan_counts: dict[str, dict[str, int]] = {
        bot_id: defaultdict(int) for bot_id in bot_ids
    }
    settlements: dict[tuple[str, str, str], Decimal] = {}
    where_since, since_params = _dt_filter(since)

    with _connect(db_path) as con:
        placeholders = ",".join("?" for _ in bot_ids)
        for row in con.execute(
            f"""
            SELECT bot_id, payload
            FROM events
            WHERE event_type = 'portfolio.paper_resolve'
              AND bot_id IN ({placeholders})
            """,
            bot_ids,
        ):
            payload = _payload(row["payload"])
            cid = str(payload.get("condition_id") or "")
            token_id = str(payload.get("token_id") or "")
            if cid and token_id:
                settlements[(str(row["bot_id"]), cid, token_id)] = Decimal(
                    str(payload.get("settle_price", "0"))
                )

        for row in con.execute(
            f"""
            SELECT bot_id, payload
            FROM events
            WHERE event_type = 'crypto_fair_value.scan_summary'
              AND bot_id IN ({placeholders})
              {where_since}
            """,
            [*bot_ids, *since_params],
        ):
            payload = _payload(row["payload"])
            if str(row["bot_id"]) not in bot_set:
                continue
            for key, value in payload.items():
                try:
                    scan_counts[str(row["bot_id"])][str(key)] += int(value)
                except (TypeError, ValueError):
                    continue

        signal_rows = con.execute(
            f"""
            SELECT bot_id, created_at, payload
            FROM events
            WHERE event_type = 'crypto_fair_value.signal'
              AND bot_id IN ({placeholders})
              {where_since}
            ORDER BY created_at
            """,
            [*bot_ids, *since_params],
        ).fetchall()

    for row in signal_rows:
        bot_id = str(row["bot_id"])
        payload = _payload(row["payload"])
        strategy = str(payload.get("strategy") or "")
        symbol = str(payload.get("symbol") or "")
        duration = f"{int(payload.get('duration_minutes') or 0)}m"
        lead = str(payload.get("lead_bucket") or "")
        side = str(payload.get("side") or "")
        prob_bucket = str(payload.get("probability_bucket") or "")
        ask_bucket = str(payload.get("ask_bucket") or "")
        cid = str(payload.get("condition_id") or "")
        token_id = str(payload.get("token_id") or "")
        settle = settlements.get((bot_id, cid, token_id))

        for track in payload.get("fill_tracks") or []:
            if not isinstance(track, dict):
                continue
            fill_track = str(track.get("fill_track") or "")
            key = (
                bot_id,
                strategy,
                symbol,
                duration,
                lead,
                side,
                prob_bucket,
                ask_bucket,
                fill_track,
            )
            stat = groups[key]
            stat.signals += 1
            stat.edges.append(Decimal(str(payload.get("model_edge", "0"))))
            stat.spreads.append(Decimal(str(payload.get("effective_spread", "0"))))
            stat.depths.append(Decimal(str(payload.get("top_depth_usd", "0"))))
            if not track.get("filled"):
                stat.no_fills += 1
                continue
            stat.fills += 1
            if settle is None:
                continue
            size = Decimal(str(track.get("size", "0")))
            stake = Decimal(str(track.get("stake_usd", "0")))
            fee = Decimal(str(track.get("fee_usd", "0")))
            gross = (settle * size) - stake
            net = gross - fee
            stat.closed += 1
            if settle >= Decimal("1"):
                stat.wins += 1
            stat.gross_pnl += gross
            stat.fee_stressed_pnl += net
            if stake > 0:
                stat.rois.append(float(net / stake))

    rows: list[dict[str, Any]] = []
    for key, stat in sorted(groups.items()):
        (
            bot_id,
            strategy,
            symbol,
            duration,
            lead,
            side,
            prob_bucket,
            ask_bucket,
            fill_track,
        ) = key
        rows.append(
            {
                "bot_id": bot_id,
                "strategy": strategy,
                "symbol": symbol,
                "duration": duration,
                "lead_bucket": lead,
                "side": side,
                "model_probability_bucket": prob_bucket,
                "entry_ask_bucket": ask_bucket,
                "fill_track": fill_track,
                **stat.summary(),
            }
        )

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "db_path": str(db_path),
        "since": since.isoformat() if since else None,
        "bot_ids": list(bot_ids),
        "scan_counts": {
            bot_id: dict(sorted(counts.items()))
            for bot_id, counts in scan_counts.items()
        },
        "rows": rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Crypto Fair-Value Paper Report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"DB: `{report['db_path']}`",
        "",
        "## Scan Counts",
        "",
    ]
    for bot_id, counts in report["scan_counts"].items():
        if not counts:
            lines.append(f"- `{bot_id}`: no scan summaries")
            continue
        count_text = ", ".join(f"{k}={v}" for k, v in counts.items())
        lines.append(f"- `{bot_id}`: {count_text}")
    lines.extend([
        "",
        "## Results",
        "",
        "| Bot | Strategy | Symbol | Dur | Lead | Side | Prob | Ask | Track | Signals | Fills | Closed | Hit | ROI | Ex-2 ROI | P&L |",
        "|---|---|---:|---:|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in report["rows"]:
        lines.append(
            "| {bot_id} | {strategy} | {symbol} | {duration} | {lead_bucket} | "
            "{side} | {model_probability_bucket} | {entry_ask_bucket} | "
            "{fill_track} | {signals} | {simulated_fills} | {closed_positions} | "
            "{hit_rate:.1%} | {raw_roi:.1%} | {ex_largest_two_roi:.1%} | "
            "${fee_stressed_pnl:+.2f} |".format(**row)
        )
    if not report["rows"]:
        lines.append("| _No rows yet_ |  |  |  |  |  |  |  |  | 0 | 0 | 0 |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], *, out_md: Path, out_json: Path) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    out_md.write_text(render_markdown(report), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--db", default=str(get_settings().polymarket_db_path))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--bot-id", action="append", dest="bot_ids")
    parser.add_argument("--since", default="7d", help="ISO datetime or Nd lookback; default 7d")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    since = _parse_since(args.since)
    bot_ids = tuple(args.bot_ids or DEFAULT_BOT_IDS)
    report = build_report(db_path=Path(args.db), bot_ids=bot_ids, since=since)
    write_outputs(report, out_md=Path(args.out_md), out_json=Path(args.out_json))
    print(f"wrote {args.out_md}")
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
