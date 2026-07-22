"""Repo-wide emergency halt flag.

Audit 2026-04-17 Phase 3 (meta-review M-2). A single flag every bot reads
pre-trade. When set, no bot places new entries regardless of per-bot halts,
fleet cap, or keystore state.

Persistence: uses a DB-backed singleton row in `halt_flags` with
`bot_id="__ALL__"`. Fall-back: if DB unreachable, checks an env var
`EMERGENCY_HALT=true` so an operator can halt even without DB access.

Trigger scenarios:
- UMA mass-dispute event (entire category frozen)
- Polymarket venue outage / suspected manipulation
- Fee-schedule change detected by the scraper (see
  `scripts/check_polymarket_fees.py`)
- Wallet-balance anomaly
- Operator-initiated panic halt via Telegram

Write path: `set_emergency_halt(reason)` / `clear_emergency_halt()`.
Read path: `is_emergency_halted()` — called at the top of every bot's
`try_enter` path. Failure-open under DB errors: if the DB read fails, we
log loudly and ALLOW trading to continue. Rationale: a DB outage should
not silently wedge a live bot that's holding positions needing exits.
Operators can force-halt via the env var fallback if they want fail-closed
behavior.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import select

from core.db import HaltFlag, get_session_factory

log = logging.getLogger(__name__)

EMERGENCY_BOT_ID = "__ALL__"


@dataclass(frozen=True)
class EmergencyHaltState:
    halted: bool
    reason: str | None
    set_at: datetime | None


def _env_halt() -> bool:
    raw = os.environ.get("EMERGENCY_HALT", "").strip().lower()
    return raw in ("true", "1", "yes", "on")


def is_emergency_halted() -> bool:
    """True if the repo-wide halt is active.

    Env var takes precedence (operator override without DB). DB read
    failures fail OPEN (log + allow) — see module docstring for why.
    """
    if _env_halt():
        return True
    try:
        with get_session_factory()() as s:
            flag = s.scalars(
                select(HaltFlag).where(HaltFlag.bot_id == EMERGENCY_BOT_ID)
            ).first()
            return bool(flag and flag.halted)
    except Exception as exc:
        log.warning(
            "emergency_halt.db_check_failed err=%s — failing OPEN (trading allowed)",
            exc,
        )
        return False


def get_emergency_halt_state() -> EmergencyHaltState:
    """Full state for dashboard / logs."""
    if _env_halt():
        return EmergencyHaltState(
            halted=True,
            reason=f"env:EMERGENCY_HALT={os.environ.get('EMERGENCY_HALT')}",
            set_at=None,
        )
    try:
        with get_session_factory()() as s:
            flag = s.scalars(
                select(HaltFlag).where(HaltFlag.bot_id == EMERGENCY_BOT_ID)
            ).first()
            if flag and flag.halted:
                return EmergencyHaltState(
                    halted=True,
                    reason=getattr(flag, "reason", None),
                    set_at=getattr(flag, "updated_at", None) or getattr(flag, "set_at", None),
                )
    except Exception as exc:
        log.warning("emergency_halt.state_read_failed err=%s", exc)
    return EmergencyHaltState(halted=False, reason=None, set_at=None)


def set_emergency_halt(reason: str) -> None:
    """Set the repo-wide halt. Idempotent — repeated calls update the reason."""
    try:
        with get_session_factory()() as s:
            flag = s.scalars(
                select(HaltFlag).where(HaltFlag.bot_id == EMERGENCY_BOT_ID)
            ).first()
            if flag is None:
                flag = HaltFlag(bot_id=EMERGENCY_BOT_ID, halted=True)
                s.add(flag)
            else:
                flag.halted = True
            # HaltFlag has a `reason` column in most installs; set defensively.
            if hasattr(flag, "reason"):
                try:
                    flag.reason = reason
                except Exception:
                    pass
            s.commit()
        log.warning("emergency_halt.set reason=%s", reason)
    except Exception as exc:
        log.error("emergency_halt.set_failed err=%s reason=%s", exc, reason)
        raise


def clear_emergency_halt() -> None:
    """Clear the repo-wide halt. Leaves the row in place (audit trail)."""
    try:
        with get_session_factory()() as s:
            flag = s.scalars(
                select(HaltFlag).where(HaltFlag.bot_id == EMERGENCY_BOT_ID)
            ).first()
            if flag is not None:
                flag.halted = False
                s.commit()
        log.warning("emergency_halt.cleared")
    except Exception as exc:
        log.error("emergency_halt.clear_failed err=%s", exc)
        raise
