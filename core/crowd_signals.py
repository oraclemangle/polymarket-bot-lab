"""Shared read-only accessors for Bot F crowd/cascade signals.

Bot F is no longer treated as a preferred standalone trader. Its useful
surface is the sensor data it already records: mirror signals and detected
copy-bot cascades. This module gives other bots a small dependency-free way
to query that data without importing Bot F's SQLAlchemy schema or executor.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

DEFAULT_BOT_F_DB = Path(os.environ.get("BOT_F_DB_PATH", "./data/bot_f.db")).resolve()


@dataclass(frozen=True)
class CrowdSignal:
    market_id: str
    detected_at: datetime | None
    cascade_start_ts: int
    cascade_end_ts: int
    n_wallets: int
    dominant_side: str
    gross_usd: float
    dominant_ratio: float


@dataclass(frozen=True)
class CrowdPressure:
    market_id: str
    has_recent_cascade: bool
    cascade_count: int
    top_side: str | None = None
    top_gross_usd: float = 0.0
    top_wallets: int = 0
    newest_detected_at: datetime | None = None


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _connect(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def recent_cascades_for_market(
    market_id: str,
    *,
    bot_f_db: Path | str | None = None,
    within_hours: int = 6,
    now: datetime | None = None,
) -> list[CrowdSignal]:
    """Return recent Bot F cascade rows for one market.

    Missing DB/table is treated as no signal. That keeps Bot F optional:
    downstream bots can use this as an input without becoming unavailable
    when the sensor is paused.
    """
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(hours=within_hours)
    path = Path(bot_f_db).resolve() if bot_f_db is not None else DEFAULT_BOT_F_DB
    conn = _connect(path)
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT detected_at, market_id, cascade_start_ts, cascade_end_ts,
                   n_wallets, dominant_side, gross_usd, dominant_ratio
            FROM crowd_signals
            WHERE market_id = ?
              AND detected_at >= ?
            ORDER BY detected_at DESC
            """,
            (market_id, cutoff.strftime("%Y-%m-%d %H:%M:%S")),
        ).fetchall()
    except sqlite3.Error:
        return []
    finally:
        conn.close()

    out: list[CrowdSignal] = []
    for row in rows:
        out.append(
            CrowdSignal(
                market_id=str(row["market_id"]),
                detected_at=_parse_dt(row["detected_at"]),
                cascade_start_ts=int(row["cascade_start_ts"]),
                cascade_end_ts=int(row["cascade_end_ts"]),
                n_wallets=int(row["n_wallets"]),
                dominant_side=str(row["dominant_side"]),
                gross_usd=float(row["gross_usd"]),
                dominant_ratio=float(row["dominant_ratio"]),
            )
        )
    return out


def crowd_pressure_for_market(
    market_id: str,
    *,
    bot_f_db: Path | str | None = None,
    within_hours: int = 6,
    now: datetime | None = None,
) -> CrowdPressure:
    cascades = recent_cascades_for_market(
        market_id,
        bot_f_db=bot_f_db,
        within_hours=within_hours,
        now=now,
    )
    if not cascades:
        return CrowdPressure(
            market_id=market_id,
            has_recent_cascade=False,
            cascade_count=0,
        )
    top = max(cascades, key=lambda c: c.gross_usd)
    newest = max(
        (c.detected_at for c in cascades if c.detected_at is not None),
        default=None,
    )
    return CrowdPressure(
        market_id=market_id,
        has_recent_cascade=True,
        cascade_count=len(cascades),
        top_side=top.dominant_side,
        top_gross_usd=top.gross_usd,
        top_wallets=top.n_wallets,
        newest_detected_at=newest,
    )

