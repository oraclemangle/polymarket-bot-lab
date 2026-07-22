"""Cross-bot pre-trade aggregate exposure cap.

Audit 2026-04-17 fix for Session-14 repeat risk. All three reviewers
(Gemini, GLM-5.1, Codex) flagged the absence of a cross-bot aggregate cap;
Codex additionally flagged that the existing watchdog check is once-per-loop,
not pre-trade atomic (`core/watchdog.py` L141 — AF-3).

This module provides a single function, `check_fleet_exposure`, that every
bot MUST call inside its `try_enter` path, immediately before submitting an
order. The check reads all bots' open positions + open orders from the
shared DB in a single atomic transaction and rejects any trade whose
addition would push the fleet above the deployable cap.

Deployable cap:
  FLEET_DEPLOYABLE_CAP_USD = FLEET_WALLET_USD * FLEET_DEPLOYABLE_FRAC

Default `FLEET_DEPLOYABLE_FRAC = 0.80` (20% reserve for slippage, exit fees,
FX spread, and drawdown buffer). Env-overridable via:
  FLEET_DEPLOYABLE_FRAC  (decimal, e.g. "0.80")
  FLEET_WALLET_USD       (absolute USD, overrides automatic derivation)

Automatic wallet derivation:
  If FLEET_WALLET_USD is unset, the cap falls back to the sum of per-bot
  bankroll settings (bot_a + bot_b in USD + bot_e in USD, etc.). This keeps
  behaviour compatible with the Session-14 "cap = bankroll" fix while
  applying an 80% deployable fraction on top.

Enforcement is advisory (returns ok/not-ok); callers must honour the
refusal. Pre-trade call cadence makes the check atomic under normal burst
patterns — two concurrent bots can race, but SQLite's single-writer model
serializes their commit paths and so the last submitter sees the other's
order already in the DB.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import select

from core.db import Order, Position, get_session_factory

log = logging.getLogger(__name__)


def _env_decimal(key: str, default: str) -> Decimal:
    raw = os.environ.get(key, default)
    try:
        return Decimal(str(raw))
    except Exception:
        return Decimal(default)


FLEET_DEPLOYABLE_FRAC: Decimal = _env_decimal("FLEET_DEPLOYABLE_FRAC", "0.80")


def _wallet_usd_from_env() -> Decimal | None:
    raw = os.environ.get("FLEET_WALLET_USD", "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except Exception:
        return None


def _derive_wallet_usd_from_bankrolls() -> Decimal:
    """Fallback: sum per-bot bankroll configs in USD.

    Uses the bot configs directly (lazy import to avoid circular deps).
    GBP bankrolls converted via the current USD/GBP rate.

    Audit 2026-05-10: bot_a removed (archived ADR-033). bot_e retired as
    trading strategy ADR-092; recorder-only posture means it no longer
    contributes to the deployable trading cap. Only bot_b remains as an
    active bankroll contributor in this fallback path.
    """
    total = Decimal("0")
    # Bot B excluded from public export; its bankroll contribution was
    # removed with it. See docs/bot-b-reference.md.
    return total


def get_fleet_wallet_usd() -> Decimal:
    """Return the current fleet wallet size in USD (env or derived)."""
    from_env = _wallet_usd_from_env()
    if from_env is not None:
        return from_env
    return _derive_wallet_usd_from_bankrolls()


def get_fleet_deployable_cap_usd() -> Decimal:
    """Deployable cap = wallet * FLEET_DEPLOYABLE_FRAC."""
    return get_fleet_wallet_usd() * FLEET_DEPLOYABLE_FRAC


# M-01 (audit 2026-04-18): live/paper mode split. Previously the fleet
# cap summed ALL bots' open exposure — paper positions counted against a
# cap that should only apply to real capital. In mixed-mode operation
# (Bot A/B live, Bot C/D/E paper), paper exposure effectively starved
# the live bots. The check now infers mode from each bot's BOT_X_ENV
# setting and only compares a caller's intended trade against the total
# exposure of bots in the *same* mode.
def _bot_is_paper(bot_id: str) -> bool:
    """Return True if this bot is currently in paper mode.

    Reads `BOT_<ID>_ENV` env var first (matching watchdog_daemon); falls
    back to global `POLYMARKET_ENV` via `settings.is_live()`. Shadow bots
    (`bot_a_shadow`, `bot_b_shadow`) are paper by definition.

    Audit 2026-04-19 (Gemini 3.1 Pro fragility note): previously used
    `bot_id.split("_")[-1]` which worked for canonical `bot_X` names but
    would mis-key any bot_id with >1 underscore (e.g. a hypothetical
    "bot_e_btc_scalp" would yield env_key="BOT_SCALP_ENV" instead of
    "BOT_E_ENV"). Fix: strip the "bot_" prefix explicitly and take the
    first remaining segment.
    """
    if bot_id.endswith("_shadow"):
        return True
    try:
        from core.bot_registry import REGISTRY
        meta = next((b for b in REGISTRY if b.bot_id == bot_id), None)
        if meta is not None:
            if meta.status == "live":
                return False
            if meta.status in {"archived", "paper", "paper_tuning", "paused", "shadow", "sensor"}:
                return True
    except Exception:
        pass
    _prefix = "bot_"
    if bot_id.startswith(_prefix):
        short = bot_id[len(_prefix):].split("_")[0].upper()
    else:
        short = bot_id.upper()
    env_key = f"BOT_{short}_ENV"
    raw = os.environ.get(env_key, "").lower()
    if raw:
        return raw == "paper"
    try:
        from core.config import get_settings
        return not get_settings().is_live()
    except Exception:
        return True  # fail-closed: treat unknown-mode as paper


@dataclass(frozen=True)
class FleetExposureSnapshot:
    positions_usd: Decimal    # sum of cost_basis_usd across all OPEN positions
    open_orders_usd: Decimal  # sum of price*size for all OPEN orders
    total_usd: Decimal        # positions + open_orders
    wallet_usd: Decimal
    deployable_cap_usd: Decimal


def snapshot_fleet_exposure(
    mode: "Literal['live', 'paper', 'combined'] | None" = None,
    *,
    raise_on_error: bool = False,
) -> FleetExposureSnapshot:
    """Read the fleet's current exposure atomically from DB.

    M-01 (audit 2026-04-18): when `mode` is "live" or "paper", filter to
    only bots currently operating in that mode (per `BOT_X_ENV`). When
    `mode` is "combined" or None, sum every bot — preserves pre-M-01
    behaviour for callers that explicitly want the whole fleet.
    """
    # Compute the set of bot_ids that match the requested mode (or all
    # bots when combined). If a mode is requested, any bot whose mode
    # cannot be determined is conservatively excluded to keep live and
    # paper accounting strictly separate.
    # Audit 2026-04-19 (GLM-5.1 F-004): bot_f was omitted from this tuple,
    # so any Position/Order it ever creates would be invisible to the
    # mode-filtered fleet cap. Bot F is sensor-only today per ADR-032, but
    # Phase 2 Trigger could change that; add it now to close the contract gap.
    # 2026-04-22: derived from canonical registry so new bots (G,
    # F_mirror) are automatically included. Previously hand-maintained
    # and drifted — Codex Section C / GLM A7.
    # Use all_bot_ids, not active_bot_ids: archived bots may still hold
    # residual open positions that count toward current exposure.
    from core.bot_registry import all_bot_ids, cap_member_bot_ids
    known_bots = all_bot_ids()
    cap_bots = set(cap_member_bot_ids())
    if mode in ("live", "paper"):
        want_paper = mode == "paper"
        allowed_bots: set[str] | None = {
            b for b in cap_bots if _bot_is_paper(b) == want_paper
        }
    else:
        allowed_bots = None  # combined

    positions_usd = Decimal("0")
    open_orders_usd = Decimal("0")
    try:
        with get_session_factory()() as s:
            pos_rows = s.scalars(
                select(Position).where(Position.status == "OPEN")
            ).all()
            for p in pos_rows:
                if allowed_bots is not None and p.bot_id not in allowed_bots:
                    continue
                try:
                    positions_usd += Decimal(p.cost_basis_usd or 0)
                except Exception:
                    continue
            # U-05 (audit 2026-04-18): align fleet-cap order-status set
            # with `Portfolio.get_open_orders_notional`. OPEN-only missed
            # PARTIAL/PAPER_OPEN/live orders that still reserve bankroll;
            # this allowed fleet cap to green-light additional trades
            # while other orders were pending.
            order_rows = s.scalars(
                select(Order).where(
                    Order.status.in_(("OPEN", "PARTIAL", "PAPER_OPEN", "live", "MATCHED"))
                )
            ).all()
            for o in order_rows:
                if allowed_bots is not None and o.bot_id not in allowed_bots:
                    continue
                try:
                    if o.price is None or o.size is None:
                        continue
                    open_orders_usd += Decimal(o.price) * Decimal(o.size)
                except Exception:
                    continue
    except Exception as exc:
        log.warning("fleet.snapshot_failed err=%s — returning zero exposure", exc)
        if raise_on_error:
            raise
    wallet_usd = get_fleet_wallet_usd()
    cap_usd = wallet_usd * FLEET_DEPLOYABLE_FRAC
    return FleetExposureSnapshot(
        positions_usd=positions_usd,
        open_orders_usd=open_orders_usd,
        total_usd=positions_usd + open_orders_usd,
        wallet_usd=wallet_usd,
        deployable_cap_usd=cap_usd,
    )


@dataclass(frozen=True)
class FleetCheckResult:
    ok: bool
    reason: str                         # "fleet_ok" | "fleet_cap_breach" | "fleet_snapshot_failed"
    severity: Literal["info", "warn", "error"]
    current_total_usd: Decimal
    intended_usd: Decimal
    projected_total_usd: Decimal
    deployable_cap_usd: Decimal


def check_fleet_exposure(
    bot_id: str,
    intended_notional_usd: Decimal | float | int,
) -> FleetCheckResult:
    """Return whether placing `intended_notional_usd` would breach the fleet cap.

    Call this immediately before submitting an order to the CLOB. Callers
    MUST refuse the order when `ok=False`; the result carries enough
    diagnostic for a structured log line.

    In paper mode, snapshot/cap misconfiguration remains fail-open so data
    collection does not wedge. In live mode, snapshot failure or a nonpositive
    deployable cap is a hard block.
    """
    intended = Decimal(str(intended_notional_usd))
    caller_mode = "paper" if _bot_is_paper(bot_id) else "live"
    try:
        # M-01 (audit 2026-04-18): restrict the snapshot to bots in the
        # same mode as the caller. A live caller is only checked against
        # the live-fleet cap; a paper caller only against paper.
        snap = snapshot_fleet_exposure(mode=caller_mode, raise_on_error=True)
    except Exception as exc:
        log.error("fleet.check_failed bot=%s err=%s", bot_id, exc)
        return FleetCheckResult(
            ok=(caller_mode == "paper"),
            reason="fleet_snapshot_failed",
            severity="error",
            current_total_usd=Decimal("0"),
            intended_usd=intended,
            projected_total_usd=intended,
            deployable_cap_usd=Decimal("0"),
        )

    cap = snap.deployable_cap_usd
    projected = snap.total_usd + intended

    if cap <= 0:
        log.warning(
            "fleet.cap_nonpositive bot=%s mode=%s cap_usd=%s",
            bot_id, caller_mode, cap,
        )
        return FleetCheckResult(
            ok=(caller_mode == "paper"),
            reason="fleet_cap_nonpositive",
            severity="warn",
            current_total_usd=snap.total_usd,
            intended_usd=intended,
            projected_total_usd=projected,
            deployable_cap_usd=cap,
        )

    if projected > cap:
        log.warning(
            "fleet.cap_breach bot=%s current=%s intended=%s projected=%s cap=%s",
            bot_id, snap.total_usd, intended, projected, cap,
        )
        return FleetCheckResult(
            ok=False,
            reason="fleet_cap_breach",
            severity="warn",
            current_total_usd=snap.total_usd,
            intended_usd=intended,
            projected_total_usd=projected,
            deployable_cap_usd=cap,
        )

    return FleetCheckResult(
        ok=True,
        reason="fleet_ok",
        severity="info",
        current_total_usd=snap.total_usd,
        intended_usd=intended,
        projected_total_usd=projected,
        deployable_cap_usd=cap,
    )


# ---------------------------------------------------------------------------
# Cross-bot condition_id overlap detector (Phase 3, audit 2026-04-17)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConditionOverlap:
    """A condition_id held open by more than one bot."""
    condition_id: str
    bot_ids: list[str]
    total_notional_usd: Decimal


def detect_cross_bot_overlap() -> list[ConditionOverlap]:
    """Find condition_ids held open by more than one bot.

    Two bots on the same market is 2× concentration, not 2× diversification.
    This detector surfaces that for dashboard + watchdog alerts.
    """
    try:
        with get_session_factory()() as s:
            rows = s.scalars(
                select(Position).where(Position.status == "OPEN")
            ).all()
    except Exception as exc:
        log.warning("fleet.overlap_scan_failed err=%s", exc)
        return []
    by_cid: dict[str, list[tuple[str, Decimal]]] = {}
    for p in rows:
        cid = str(p.condition_id)
        notional = Decimal(p.cost_basis_usd or 0)
        by_cid.setdefault(cid, []).append((p.bot_id, notional))
    overlaps: list[ConditionOverlap] = []
    for cid, entries in by_cid.items():
        bot_ids = sorted({b for b, _n in entries})
        if len(bot_ids) > 1:
            total = sum((n for _b, n in entries), Decimal("0"))
            overlaps.append(ConditionOverlap(
                condition_id=cid, bot_ids=bot_ids, total_notional_usd=total,
            ))
    return overlaps


# ---------------------------------------------------------------------------
# Strategy-archetype concentration monitor (meta-review M-1, Phase 3)
# ---------------------------------------------------------------------------


# Factor-archetype mapping. Every bot's exposure collapses into one of
# these buckets for single-factor-risk measurement. All four of our live
# bots currently map to `short_surprise` — the meta-review called this
# out as the most likely portfolio-breaking assumption. Adding a non-fade
# bot (e.g. Bot C Pyth repricing as `momentum`) is the operational fix.
# 2026-04-22 per GLM-5.1 A7 / Codex Section C: the legacy hand-maintained
# dict missed bot_g and bot_f_mirror. Now derived from the canonical
# registry. Add archetype to `core/bot_registry.py::REGISTRY` to extend.
def _build_archetype() -> dict[str, str]:
    from core.bot_registry import archetype_map
    return archetype_map()


BOT_ARCHETYPE: dict[str, str] = _build_archetype()


@dataclass(frozen=True)
class ArchetypeExposure:
    archetype: str
    notional_usd: Decimal
    fraction_of_total: Decimal


def archetype_exposure_breakdown() -> list[ArchetypeExposure]:
    """Sum open-position notionals grouped by strategy archetype.

    Intended for dashboard display and a Telegram alert when any archetype
    exceeds 70% of fleet exposure (i.e. "we're one factor").
    """
    try:
        with get_session_factory()() as s:
            rows = s.scalars(
                select(Position).where(Position.status == "OPEN")
            ).all()
    except Exception as exc:
        log.warning("fleet.archetype_scan_failed err=%s", exc)
        return []
    totals: dict[str, Decimal] = {}
    for p in rows:
        arch = BOT_ARCHETYPE.get(p.bot_id, "unknown")
        totals[arch] = totals.get(arch, Decimal("0")) + Decimal(p.cost_basis_usd or 0)
    grand = sum(totals.values(), Decimal("0"))
    if grand <= 0:
        return [ArchetypeExposure(a, v, Decimal("0")) for a, v in totals.items()]
    return [
        ArchetypeExposure(a, v, (v / grand).quantize(Decimal("0.0001")))
        for a, v in sorted(totals.items(), key=lambda x: -x[1])
    ]


def single_factor_alert_needed(threshold_frac: Decimal = Decimal("0.70")) -> tuple[bool, str]:
    """Return (alert_needed, message).

    True when any archetype holds >= threshold_frac of total fleet exposure.
    """
    breakdown = archetype_exposure_breakdown()
    for e in breakdown:
        if e.fraction_of_total >= threshold_frac:
            return (
                True,
                f"single-factor risk: {e.archetype}={e.fraction_of_total*100:.0f}% "
                f"of fleet exposure ({e.notional_usd} USD)",
            )
    return (False, "ok")
