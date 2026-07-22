"""Kill-switches and health checks.

Runs every 60s (systemd timer).  Checks:
- Per-bot drawdown vs threshold
- Per-bot open exposure vs cap
- Scraper liveness (markets.last_updated max)
- Scorer liveness (scores.scored_at max) — Bot B only
- WSS liveness (trades / heartbeat row recency)
- USDC.e peg (>1% deviation for >2h → halt)
- VPN liveness (resolve CLOB host through tunnel)

On trigger: cancel_all on offending bot, set halt_flag, emit events row,
notify via Telegram.

Fails closed: any uncaught exception halts and alerts rather than silently
skipping the check.
"""

from __future__ import annotations

import logging
import os
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from core.bot_registry import REGISTRY
from core.config import settings
from core.db import Event, HaltFlag, Market, Score, Trade, get_session_factory
from core.portfolio import Portfolio

log = logging.getLogger(__name__)

# Bots that run on the VPS (vps-host) rather than the bot container.
# the bot container watchdog must not halt these — its CLOB-reachability and
# market-catalog liveness checks reflect the bot container's egress and DB state, not
# the VPS path. The VPS bots have their own local kill-switch logic and
# read their own DBs. See ADR-115 (Session 179, 2026-05-06) and the
# Session 170 paper-lane migration.
VPS_HOSTED_BOTS = frozenset(
    {
        "bot_g_prime",
        "bot_g_prime_live",
        "bot_g_prime_shadow",
        "bot_g_prime_high_tail",
        "bot_g_prime_late_cheap",
        "bot_g_prime_take_profit",
        "bot_d_spike",
        "crypto_probability_gap_paper",
        "crypto_brownian_fv_paper",
    }
)

def watchdog_host_role() -> str:
    """Return the host role for watchdog scoping.

    the bot container owns the bot container-local bots; the VPS owns the latency-hosted Bot G/Bot D
    spike lanes. Keeping scope explicit prevents a the bot container watchdog from judging
    VPS health while allowing a VPS watchdog to cancel its own live orders.
    """
    role = os.environ.get("LONGSHOT_WATCHDOG_HOST_ROLE", "local").strip().lower()
    return "vps" if role in {"vps", "vps-host"} else "local"


def local_watchdog_excluded_bots() -> frozenset[str]:
    """Return bot ids this host's watchdog must not manage."""
    if watchdog_host_role() == "vps":
        return frozenset(b.bot_id for b in REGISTRY if b.bot_id not in VPS_HOSTED_BOTS)
    return VPS_HOSTED_BOTS


LOCAL_WATCHDOG_EXCLUDED_BOTS = local_watchdog_excluded_bots()


LIVE_CAP_BOTS = tuple(
    bid for bid in ("bot_b", "bot_d_live_probe", "bot_g_prime_live")
    if bid not in LOCAL_WATCHDOG_EXCLUDED_BOTS
)
PAPER_CAP_BOTS = tuple(
    b.bot_id
    for b in REGISTRY
    if b.include_in_cap
    and b.bot_id not in LIVE_CAP_BOTS
    and b.bot_id not in LOCAL_WATCHDOG_EXCLUDED_BOTS
)
MARKET_CATALOG_BOTS = tuple(
    bid for bid in (
        "bot_b",
        "bot_c",
        "bot_d",
        "bot_d_live_probe",
        "bot_g_prime",
        "bot_g_prime_live",
    )
    if bid not in LOCAL_WATCHDOG_EXCLUDED_BOTS
)


def _active_trading_bot_ids() -> list[str]:
    """Return active bot ids that can place orders and therefore can be halted.

    Excludes bots outside this host's watchdog scope.
    """
    try:
        from core.bot_registry import REGISTRY

        return [
            b.bot_id
            for b in REGISTRY
            if b.status not in ("archived", "sensor", "shadow")
            and b.bot_id not in LOCAL_WATCHDOG_EXCLUDED_BOTS
        ]
    except Exception:
        return [
            bid
            for bid in (
                "bot_b",
                "bot_c",
                "bot_d",
                "bot_e",
                "bot_f_mirror",
                "bot_g_prime",
                "bot_g_prime_live",
            )
            if bid not in LOCAL_WATCHDOG_EXCLUDED_BOTS
        ]


def _bot_b_watchdog_enabled() -> bool:
    """Return whether parked Bot B should still receive scorer liveness checks."""
    return os.environ.get("BOT_B_WATCHDOG_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _market_catalog_watchdog_enabled() -> bool:
    """Return whether the legacy shared market-catalog liveness check is required."""
    return os.environ.get("MARKET_CATALOG_WATCHDOG_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _same_reason_family(existing: str, new: str) -> bool:
    """Decide whether two watchdog halt reasons describe the same failure.

    U-12 (audit 2026-04-18): `_halt` uses this to suppress repeat
    `cancel_all` calls. Reasons are human-readable strings like
    "scorer stale: last score 118.2m ago" or "bot_a drawdown 19.3% ≥ 15%".
    We extract a coarse family signature (the leading phrase before any
    number or colon) and compare. This is intentionally liberal — two
    different kinds of halt (scorer vs drawdown) differ in the family
    string and will both fire cancel; same check firing on every tick
    maps to the same family and the cancel is suppressed.
    """
    def _family(s: str) -> str:
        # Take everything up to the first colon or digit.
        head = []
        for ch in s:
            if ch in (":", ",") or ch.isdigit():
                break
            head.append(ch)
        return "".join(head).strip().lower()
    return _family(existing) == _family(new) and _family(existing) != ""


@dataclass
class CheckResult:
    name: str
    ok: bool
    severity: str = "info"  # info | warn | kill
    message: str = ""
    bot_id: str | None = None
    # 2026-04-17: scope_bots lets a fleet-level kill (e.g. live aggregate
    # exposure) halt only the affected mode-group instead of every bot.
    # If bot_id is set, that bot alone halts. Else if scope_bots is set,
    # those bots halt. Else only active trading bots halt; this fallback is
    # retained for fail-closed infrastructure checks, but new kill checks
    # should set an explicit scope.
    scope_bots: list[str] | None = None


@dataclass
class WatchdogConfig:
    bot_b_initial_usd: Decimal
    # Audit 2026-05-10: bot_a archived per ADR-033. Field retained as optional
    # default so legacy test call-sites don't break; value is ignored.
    bot_a_initial_usd: Decimal = Decimal("0")
    bot_a_dd_kill_pct: Decimal = Decimal("0")
    bot_b_dd_kill_pct: Decimal = field(default_factory=lambda: settings.bot_b_drawdown_kill_pct)
    aggregate_dd_kill_pct: Decimal = field(
        default_factory=lambda: settings.aggregate_drawdown_kill_pct
    )
    max_aggregate_exposure_usd: Decimal = field(
        default_factory=lambda: settings.max_aggregate_exposure_usd
    )
    # 2026-04-17: see core/config.py — split caps by mode.
    max_aggregate_exposure_usd_live: Decimal = field(
        default_factory=lambda: settings.max_aggregate_exposure_usd_live
    )
    max_aggregate_exposure_usd_paper: Decimal = field(
        default_factory=lambda: settings.max_aggregate_exposure_usd_paper
    )
    scraper_stale_minutes: int = 30
    # Bot B scoring sweep runs on a 300s tick and is bounded by `budget`
    # (default 20 markets/tick). A backfill of a few hundred scoreable
    # markets takes an hour even on the institutional external-scorer tier,
    # and network jitter against the upstream can leave us briefly stale.
    # 120 min gives enough headroom that we only halt on real outages.
    scorer_stale_minutes: int = 120
    wss_stale_minutes: int = 15
    vpn_host: str = "clob.polymarket.com"
    # Alert deduplication: re-notify on the same (check, severity) only
    # after this many seconds. Prevents the Telegram spam that happens
    # when a check fails every tick but the condition hasn't transitioned.
    alert_dedupe_seconds: int = 1800  # 30 minutes
    # Checks whose failures should never page the operator via Telegram.
    # Failures are still persisted as Event rows and still halt the bot;
    # only the Telegram push is suppressed.
    #
    # scorer.liveness — silenced because stale scorer is a known paper-phase
    #   condition (Gemini quota exhaustion resets at UTC midnight) with no
    #   operator action available.
    # wss.liveness — silenced because "no fills for Nm" fires every minute
    #   for slow-firing strategies (Bot A's longshot fade places 1-3 trades
    #   per day on average). The warning is noise, not actionable — no-fill
    #   streaks of hours are expected and healthy.
    silenced_notify_checks: frozenset[str] = frozenset(
        {"scorer.liveness", "wss.liveness"}
    )


class Watchdog:
    def __init__(
        self,
        cfg: WatchdogConfig,
        cancel_all: Callable[[str], int],
        session_factory=None,
        portfolio: Portfolio | None = None,
        notify: Callable[[str, str], None] | None = None,
    ):
        # cancel_all is REQUIRED (audit C5). A silent no-op kill-switch
        # leaves real-money orders live on the CLOB after a halt trigger.
        # If a caller genuinely needs to construct a Watchdog without
        # cancellation, they must pass an explicit lambda and accept the
        # risk — we no longer auto-inject one.
        if cancel_all is None:
            raise ValueError(
                "Watchdog: cancel_all is required. Pass a Callable[[str], int]."
            )
        self.cfg = cfg
        self._sessions = session_factory or get_session_factory()
        self.portfolio = portfolio or Portfolio(self._sessions)
        # cancel_all(bot_id) → count of orders cancelled
        self._cancel_all = cancel_all
        self._notify = notify or (lambda sev, msg: None)
        # Track when we last alerted on each (check_name, severity) key so
        # we suppress identical repeat alerts within the dedupe window.
        self._last_alert_at: dict[tuple[str, str], datetime] = {}

    # --- Individual checks ---
    def _mark_prices_for(self, bot_id: str) -> dict[str, Decimal]:
        """Build token_id → mid mapping from latest Book rows for this bot's
        open positions. Lazy-imported to avoid a core.ingest <-> watchdog
        import cycle at module load.
        """
        try:
            from core.ingest import build_mark_prices
            return build_mark_prices(bot_id, session_factory=self._sessions)
        except Exception as e:
            log.warning("watchdog.marks_fail", extra={"error": str(e)})
            return {}

    def _check_drawdown(self, bot_id: str, initial: Decimal, kill_pct: Decimal) -> CheckResult:
        dd = self.portfolio.get_drawdown_pct(bot_id, initial, self._mark_prices_for(bot_id))
        if dd >= kill_pct:
            return CheckResult(
                name=f"drawdown.{bot_id}",
                ok=False,
                severity="kill",
                bot_id=bot_id,
                message=f"{bot_id} drawdown {dd}% ≥ {kill_pct}%",
            )
        return CheckResult(name=f"drawdown.{bot_id}", ok=True, bot_id=bot_id)

    def _check_aggregate_exposure_live(self) -> CheckResult:
        # 2026-04-17: live-only aggregate cap. Halts only live bots when
        # tripped, so paper trading cannot ever interfere with real money.
        total = sum(
            (self.portfolio.get_total_exposure(bot_id) for bot_id in LIVE_CAP_BOTS),
            Decimal("0"),
        )
        cap = self.cfg.max_aggregate_exposure_usd_live
        if total > cap:
            return CheckResult(
                name="exposure.aggregate.live",
                ok=False,
                severity="kill",
                scope_bots=list(LIVE_CAP_BOTS),
                message=f"live aggregate exposure ${total} > cap ${cap}",
            )
        return CheckResult(name="exposure.aggregate.live", ok=True)

    def _check_aggregate_exposure_paper(self) -> CheckResult:
        # 2026-04-17: paper-only aggregate cap. Tripping halts only the
        # paper fleet — live bots untouched. Default cap is large because
        # paper losses are informational; the per-bot bankroll caps still
        # apply individually.
        exposures = {bot_id: self.portfolio.get_total_exposure(bot_id) for bot_id in PAPER_CAP_BOTS}
        total = sum(exposures.values(), Decimal("0"))
        cap = self.cfg.max_aggregate_exposure_usd_paper
        if total > cap:
            return CheckResult(
                name="exposure.aggregate.paper",
                ok=False,
                severity="kill",
                scope_bots=list(PAPER_CAP_BOTS),
                message=f"paper aggregate exposure ${total} > cap ${cap}",
            )
        return CheckResult(name="exposure.aggregate.paper", ok=True)

    def _check_recorder_freshness(self) -> CheckResult:
        """2026-04-17 Audit Finding 5: recorder silent-failure detection.

        Scenario seen 2026-04-16: the Bot E recorder process stayed
        `active (running)` in systemd while its WSS subscription stalled
        for 11h producing zero events. Bot E trader kept reading the same
        stale pm_events window, firing (now-debounced, but still
        degraded) OBI signals on data that was hours old.

        Checks two tables:
          1. `heartbeats` — recorder's own liveness loop writes one every
             30s unconditionally. Stale heartbeats = recorder process
             itself stalled (this is the real failure mode we halt on).
          2. `pm_events` — Polymarket WSS traffic. Can legitimately go
             quiet when `market_discovery` finds zero matching markets
             (between Up/Down window cohorts). If heartbeats are fresh
             but pm_events are stale, that's a *quiet market* state, not
             a recorder failure — do NOT halt in that case.

        Session 17n 2026-04-19: the prior logic halted on 5 min of pm
        silence alone, which tripped every time discovery returned 0
        markets. Now pm-stale + heartbeats-fresh = ok; only both-stale
        counts as a failure.

        Degrades gracefully if the recorder DB isn't present (e.g. on dev
        machines where the recorder isn't deployed).
        """
        import sqlite3
        import time
        from pathlib import Path
        db_path = os.environ.get(
            "BOT_E_RECORDER_DB_PATH",
            "data/bot_e_recorder.db",
        )
        if not Path(db_path).exists():
            return CheckResult(name="recorder.freshness", ok=True)
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
            pm_row = conn.execute(
                "SELECT received_at_ms FROM pm_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            # Heartbeats table may not exist on dev/test fixtures; tolerate
            # its absence (falls back to pm-only stale detection = pre-fix
            # behaviour).
            try:
                hb_row = conn.execute(
                    "SELECT emitted_at_ms FROM heartbeats ORDER BY id DESC LIMIT 1"
                ).fetchone()
            except sqlite3.OperationalError:
                hb_row = None
            conn.close()
        except Exception as exc:
            log.warning("watchdog.recorder_freshness.query_failed err=%s", exc)
            return CheckResult(name="recorder.freshness", ok=True)
        if not pm_row or pm_row[0] is None:
            # Empty DB — recorder may be brand-new; don't halt on this.
            return CheckResult(name="recorder.freshness", ok=True)
        now_ms = time.time() * 1000
        pm_age_sec = (now_ms - int(pm_row[0])) / 1000
        hb_present = hb_row is not None and hb_row[0] is not None
        hb_age_sec = (now_ms - int(hb_row[0])) / 1000 if hb_present else None
        # Heartbeat threshold is tighter because the heartbeat loop is
        # unconditional — if it stops, the recorder process itself is
        # hung or crashed. Only enforced when heartbeats table exists
        # AND has been populated (production recorder).
        hb_threshold_sec = 120
        pm_threshold_sec = 300
        if hb_present and hb_age_sec > hb_threshold_sec:
            # 2026-04-23: additionally probe systemd state so the alert is
            # actionable. The 2026-04-21 incident had the recorder sitting
            # in systemd `failed` state for 31 hours (crashed 23 times,
            # hit restart burst limit, systemd gave up). The staleness
            # check correctly flagged the DB was stale, but the alert
            # didn't say "PERMANENT FAILED — reset-failed + restart".
            permanent_failed = False
            try:
                import subprocess
                r = subprocess.run(
                    ["systemctl", "is-failed", "polymarket-bot-e-recorder.service"],
                    capture_output=True, timeout=3, text=True,
                )
                permanent_failed = (r.stdout.strip() == "failed")
            except Exception:
                pass
            actionable = (
                " RECORDER PERMANENTLY FAILED (systemd state=failed). "
                "Recover: `systemctl reset-failed polymarket-bot-e-recorder "
                "&& systemctl restart polymarket-bot-e-recorder`."
            ) if permanent_failed else ""
            return CheckResult(
                name="recorder.freshness",
                ok=False,
                severity="kill",
                scope_bots=["bot_e"],
                bot_id="bot_e",
                message=(
                    f"recorder heartbeat stale {hb_age_sec:.0f}s "
                    f"(pm_events age {pm_age_sec:.0f}s); "
                    f"bot_e halting until recorder recovers.{actionable}"
                ),
            )
        # Quiet-market carve-out: only applies when heartbeats are present
        # AND fresh. If the heartbeats table doesn't exist (dev fixtures)
        # we fall through to the pm-stale check below, preserving the
        # pre-Session-17n behaviour.
        if pm_age_sec > pm_threshold_sec and hb_present and hb_age_sec <= hb_threshold_sec:
            # pm stale but recorder alive (heartbeats fresh) — quiet market.
            # Not a failure; Bot E trader will also see no events and skip.
            log.debug(
                "recorder.freshness.quiet_market pm_age=%.0fs hb_age=%.0fs",
                pm_age_sec, hb_age_sec,
            )
            return CheckResult(name="recorder.freshness", ok=True)
        if pm_age_sec > pm_threshold_sec:
            return CheckResult(
                name="recorder.freshness",
                ok=False,
                severity="kill",
                scope_bots=["bot_e"],
                bot_id="bot_e",
                message=(
                    f"recorder stale {pm_age_sec:.0f}s "
                    f"(last event {datetime.fromtimestamp(int(pm_row[0])/1000, UTC).isoformat()}); "
                    f"bot_e halting until recorder recovers"
                ),
            )
        return CheckResult(name="recorder.freshness", ok=True)

    def _check_scraper_liveness(self) -> CheckResult:
        if not _market_catalog_watchdog_enabled():
            return CheckResult(
                name="scraper.liveness",
                ok=True,
                severity="info",
                message="shared market-catalog liveness skipped; active bots use bot-specific discovery",
            )
        with self._sessions() as s:
            latest = s.scalars(select(Market.last_updated).order_by(Market.last_updated.desc())
            ).first()
        if latest is None:
            return CheckResult(
                name="scraper.liveness",
                ok=False,
                severity="warn",
                message="no markets ingested yet",
            )
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=UTC)
        age = datetime.now(UTC) - latest
        if age > timedelta(minutes=self.cfg.scraper_stale_minutes):
            return CheckResult(
                name="scraper.liveness",
                ok=False,
                severity="kill",
                scope_bots=list(MARKET_CATALOG_BOTS),
                message=f"scraper stale: last ingest {age.total_seconds() / 60:.1f}m ago",
            )
        return CheckResult(name="scraper.liveness", ok=True)

    def _check_scorer_liveness(self) -> CheckResult:
        if not _bot_b_watchdog_enabled():
            return CheckResult(
                name="scorer.liveness",
                ok=True,
                severity="info",
                message="Bot B scorer liveness skipped because Bot B is parked",
            )
        with self._sessions() as s:
            latest = s.scalars(select(Score.scored_at).order_by(Score.scored_at.desc())).first()
        if latest is None:
            return CheckResult(
                name="scorer.liveness",
                ok=True,
                severity="info",
                message="no scores yet (Bot B idle)",
            )
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=UTC)
        age = datetime.now(UTC) - latest
        if age > timedelta(minutes=self.cfg.scorer_stale_minutes):
            return CheckResult(
                name="scorer.liveness",
                ok=False,
                severity="kill",
                bot_id="bot_b",
                message=f"scorer stale: last score {age.total_seconds() / 60:.1f}m ago",
            )
        return CheckResult(name="scorer.liveness", ok=True)

    def _check_wss_liveness(self) -> CheckResult:
        with self._sessions() as s:
            latest = s.scalars(select(Trade.filled_at).order_by(Trade.filled_at.desc())).first()
        # If we have no trades, we don't know the WSS is alive — but also can't trigger kill.
        if latest is None:
            return CheckResult(
                name="wss.liveness",
                ok=True,
                severity="info",
                message="no trades recorded yet",
            )
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=UTC)
        age = datetime.now(UTC) - latest
        if age > timedelta(minutes=self.cfg.wss_stale_minutes):
            return CheckResult(
                name="wss.liveness",
                ok=False,
                severity="warn",
                message=f"no fills for {age.total_seconds() / 60:.1f}m (may be normal)",
            )
        return CheckResult(name="wss.liveness", ok=True)

    # External-scorer liveness probe removed with Bot B
    # (excluded from public export; see docs/bot-b-reference.md).


    def _check_vpn(self) -> CheckResult:
        """Verify the CLOB host is reachable over HTTPS via the split-tunnel.

        DNS alone is not enough: normal ISP DNS still resolves
        `clob.polymarket.com` even after the the VPN provider route is torn down, so
        a DNS-only probe gives false green. We therefore:
          1. Resolve DNS (fast early-exit if that fails).
          2. Issue a tiny HTTPS GET to the host and require 2xx/4xx (any
             valid TCP+TLS round-trip through the tunnel).
        A 5xx or connection error is still a kill — the live order path
        cannot function with that egress state.
        """
        try:
            socket.gethostbyname(self.cfg.vpn_host)
        except OSError as e:
            return CheckResult(
                name="vpn.liveness",
                ok=False,
                severity="kill",
                scope_bots=_active_trading_bot_ids(),
                message=f"cannot resolve {self.cfg.vpn_host}: {e}",
            )
        import httpx

        last_error: Exception | None = None
        last_status: int | None = None
        paths = ("/time", "/")
        for attempt in range(3):
            with httpx.Client(timeout=5.0) as c:
                for path in paths:
                    try:
                        r = c.get(f"https://{self.cfg.vpn_host}{path}")
                    except Exception as e:
                        last_error = e
                        continue
                    last_status = r.status_code
                    if 200 <= r.status_code < 500:
                        return CheckResult(name="vpn.liveness", ok=True)
            if attempt < 2:
                time.sleep(1)
        if last_status is not None:
            return CheckResult(
                name="vpn.liveness",
                ok=False,
                severity="kill",
                scope_bots=_active_trading_bot_ids(),
                message=f"CLOB host returned {last_status} after retry",
            )
        return CheckResult(
            name="vpn.liveness",
            ok=False,
            severity="kill",
            scope_bots=_active_trading_bot_ids(),
            message=f"CLOB host unreachable after retry: {last_error}",
        )

    # --- Orchestration ---
    def run_once(self) -> list[CheckResult]:
        # Bot C/D/E initial USD read from env (default 0 = no drawdown check if unset).
        bot_c_initial = Decimal(os.environ.get("BOT_C_INITIAL_USD", "0"))
        bot_d_initial = Decimal(os.environ.get("BOT_D_INITIAL_USD", "0"))
        bot_e_initial = Decimal(os.environ.get("BOT_E_INITIAL_USD", "0"))
        bot_b_shadow_initial = Decimal(os.environ.get("BOT_B_SHADOW_INITIAL_USD", "25"))
        bot_c_dd = Decimal(os.environ.get("BOT_C_DRAWDOWN_KILL_PCT", "20"))
        bot_d_dd = Decimal(os.environ.get("BOT_D_DRAWDOWN_KILL_PCT", "20"))
        bot_e_dd = Decimal(os.environ.get("BOT_E_DRAWDOWN_KILL_PCT", "20"))
        shadow_dd = Decimal(os.environ.get("BOT_SHADOW_DRAWDOWN_KILL_PCT", "50"))

        checks = [
            *(
                [self._check_drawdown("bot_b", self.cfg.bot_b_initial_usd, self.cfg.bot_b_dd_kill_pct)]
                if "bot_b" not in LOCAL_WATCHDOG_EXCLUDED_BOTS else []
            ),
            # Audit fix #4: Bot C + D drawdown checks. Only meaningful if
            # initial USD > 0 (i.e. operator has funded them).
            # Bot E added 2026-04-16 — same pattern.
            *(
                [self._check_drawdown("bot_c", bot_c_initial, bot_c_dd)]
                if bot_c_initial > 0 else []
            ),
            *(
                [self._check_drawdown("bot_d", bot_d_initial, bot_d_dd)]
                if bot_d_initial > 0 else []
            ),
            *(
                [self._check_drawdown("bot_e", bot_e_initial, bot_e_dd)]
                if bot_e_initial > 0 else []
            ),
            # Shadow bots: paper-only, so drawdown kill just halts the shadow.
            # Default 50% threshold (generous — paper losses are informational).
            *(
                [self._check_drawdown("bot_b_shadow", bot_b_shadow_initial, shadow_dd)]
                if bot_b_shadow_initial > 0 and "bot_b_shadow" not in LOCAL_WATCHDOG_EXCLUDED_BOTS else []
            ),
            self._check_aggregate_exposure_live(),
            self._check_aggregate_exposure_paper(),
            self._check_recorder_freshness(),
            self._check_scraper_liveness(),
            *(
                [self._check_scorer_liveness()]
                if "bot_b" not in LOCAL_WATCHDOG_EXCLUDED_BOTS else []
            ),
            self._check_wss_liveness(),
            self._check_vpn(),
            *(
                []
                if "bot_b" not in LOCAL_WATCHDOG_EXCLUDED_BOTS else []
            ),
        ]

        # Apply side effects for any failing check.
        for c in checks:
            if c.ok:
                continue
            self._record(c)
            if c.severity == "kill":
                if c.bot_id:
                    self._halt(c.bot_id, c.message)
                elif c.scope_bots:
                    # 2026-04-17: scope_bots restricts a fleet-level halt to
                    # the affected mode-group (live vs paper).
                    for bot in c.scope_bots:
                        self._halt(bot, c.message)
                else:
                    # Fail closed, but only for currently active trading
                    # bots. Historical legacy fallback halted archived and
                    # shadow rows while missing newer bots such as G Prime.
                    for bot in _active_trading_bot_ids():
                        self._halt(bot, c.message)
        return checks

    def _record(self, c: CheckResult) -> None:
        with self._sessions() as s:
            s.add(
                Event(
                    bot_id=c.bot_id,
                    event_type=f"watchdog.{c.name}",
                    severity=c.severity,
                    message=c.message,
                    payload={"check": c.name, "ok": c.ok},
                )
            )
            s.commit()
        log.warning(
            "watchdog.check.failed",
            extra={"check": c.name, "bot_id": c.bot_id, "severity": c.severity},
        )
        # Dedupe notifications: only emit if the (check, severity) has not
        # been alerted within cfg.alert_dedupe_seconds. Every failure is
        # still persisted as an Event row; only the Telegram push is
        # throttled so the operator isn't spammed once a minute.
        now = datetime.now(UTC)
        key = (c.name, c.severity)
        last = self._last_alert_at.get(key)
        if last is None or (now - last).total_seconds() >= self.cfg.alert_dedupe_seconds:
            if c.name not in self.cfg.silenced_notify_checks:
                self._notify(c.severity, f"[{c.name}] {c.message}")
            self._last_alert_at[key] = now

    def _halt(self, bot_id: str, reason: str) -> None:
        # U-12 (audit 2026-04-18): skip cancel_all if the bot is already
        # halted with a watchdog reason of the same family. Prior code
        # fired cancel_all on every 60-second tick while a check was
        # continuously failing (e.g. Bot B scorer stale for hours),
        # burning CLOB rate-limit budget and log volume. We still update
        # the HaltFlag.set_at timestamp so the "last halt tick" remains
        # accurate for dashboard + alert dedup.
        prefixed = f"watchdog: {reason}"
        skip_cancel = False
        skip_reason = ""
        with self._sessions() as s:
            existing_flag = s.get(HaltFlag, bot_id)
            if existing_flag is not None and existing_flag.halted:
                existing_reason = existing_flag.reason or ""
                # Skip condition A: same-family watchdog repeat.
                if existing_reason.startswith("watchdog: ") and _same_reason_family(
                    existing_reason[len("watchdog: "):], reason
                ):
                    skip_cancel = True
                    skip_reason = "same_watchdog_family"
                # Skip condition B (U-12 revised 2026-04-19): operator-set
                # halt that's older than 60s. If an operator halted the bot
                # manually, subsequent watchdog ticks should NOT keep
                # re-cancelling — the initial cancel_all at operator-halt
                # time (done via /halt handler or manual) already handled
                # live orders. Without this, a bot halted by operator for
                # 46h (e.g. Bot B scorer-stale 2026-04-17 → 2026-04-19)
                # generates ~2,700 DELETE /cancel-all calls against the
                # live CLOB — pure noise, and real API-budget burn.
                elif (
                    existing_flag.set_at is not None
                    and (datetime.now(UTC) - (
                        existing_flag.set_at if existing_flag.set_at.tzinfo
                        else existing_flag.set_at.replace(tzinfo=UTC)
                    )).total_seconds() > 60
                ):
                    skip_cancel = True
                    set_at = (
                        existing_flag.set_at
                        if existing_flag.set_at.tzinfo
                        else existing_flag.set_at.replace(tzinfo=UTC)
                    )
                    age_s = int((datetime.now(UTC) - set_at).total_seconds())
                    skip_reason = f"halt_older_than_60s_{age_s}s"
        cancelled = 0 if skip_cancel else self._cancel_all(bot_id)
        # 2026-04-17: prefix all watchdog-set reasons so they're
        # distinguishable from operator-set reasons. When a bot is already
        # halted by an operator with a human-readable reason (e.g.
        # "Session 17 operator decision..."), subsequent watchdog halts
        # for the same bot should NOT overwrite that text — otherwise the
        # UI surface misleads future operators about why the bot is halted.
        with self._sessions() as s:
            flag = s.get(HaltFlag, bot_id)
            was_already_halted = bool(flag and flag.halted)
            if flag is None:
                flag = HaltFlag(bot_id=bot_id, halted=1, reason=prefixed)
                s.add(flag)
            else:
                flag.halted = 1
                # Preserve operator-set text; only overwrite prior watchdog
                # entries or empty reasons.
                existing = flag.reason or ""
                if not existing.strip() or existing.startswith("watchdog: "):
                    flag.reason = prefixed
                # U-12 revised 2026-04-19: only advance set_at on the
                # unhalted→halted transition. Previously it always advanced,
                # which defeated the skip_cancel age check one layer up —
                # each watchdog tick refreshed set_at, so set_at was always
                # <60s old and skip_cancel never fired.
                if not was_already_halted:
                    flag.set_at = datetime.now(UTC)
            if not was_already_halted:
                s.add(
                    Event(
                        bot_id=bot_id,
                        event_type="watchdog.halt",
                        severity="kill",
                        message=prefixed,
                        payload={
                            "cancelled": cancelled,
                            "skip_cancel": skip_cancel,
                            "skip_reason": skip_reason,
                            "transition": "halted",
                        },
                    )
                )
            s.commit()
        if not was_already_halted:
            self._notify(
                "kill",
                (
                    f"[halt] {bot_id} halted by watchdog: {reason} "
                    f"(cancelled={cancelled})"
                ),
            )
        log.error(
            "watchdog.halt",
            extra={
                "bot_id": bot_id,
                "cancelled": cancelled,
                "reason": reason,
                "skip_cancel": skip_cancel,
                "skip_reason": skip_reason,
            },
        )

    def unhalt(self, bot_id: str, reason: str = "manual unhalt") -> bool:
        with self._sessions() as s:
            flag = s.get(HaltFlag, bot_id)
            if flag is None:
                return False
            flag.halted = 0
            flag.reason = reason
            flag.set_at = datetime.now(UTC)
            s.add(
                Event(
                    bot_id=bot_id,
                    event_type="watchdog.unhalt",
                    severity="info",
                    message=reason,
                )
            )
            s.commit()
        return True

    def is_halted(self, bot_id: str) -> bool:
        with self._sessions() as s:
            flag = s.get(HaltFlag, bot_id)
            return bool(flag and flag.halted)
