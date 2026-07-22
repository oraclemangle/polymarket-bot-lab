"""Read-only dashboard query layer used by the new dashboard server."""

from __future__ import annotations

import json
import os
import shlex
import sqlite3
import subprocess
import threading
import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from bots.bot_d_weather.config import BOT_D_PAPER_EPOCH_ID, BOT_D_PAPER_EPOCH_START
from core.bot_g_live_probe import bot_g_tiny_live_probe_plan
from core.bot_registry import (
    REGISTRY,
    active_systemd_units,
    archived_dashboard_bot_ids,
    dashboard_bot_ids,
)
from core.bot_registry import (
    meta as bot_meta,
)
from core.db import (
    Book,
    Event,
    HaltFlag,
    Market,
    Order,
    PnlSnapshot,
    Position,
    Trade,
    get_session_factory,
)
from scripts.bot_d_readiness_report import build_report as build_bot_d_readiness_report
from scripts.crypto_fair_value_paper_report import build_report as build_crypto_fv_report

USDCE_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
PYTH_PRO_TRIAL_EXPIRY = datetime(2026, 4, 22, tzinfo=timezone.utc)
SERVICES = [unit.removesuffix(".service") for unit in active_systemd_units()]

# Timer-driven units: their `systemctl is-active` reports 'inactive' between
# runs, which is the EXPECTED state. For these, we check the timer itself
# and treat an active timer as healthy.
TIMER_SERVICES = {
    "polymarket-fast-roi-report": "polymarket-fast-roi-report.timer",
    "polymarket-bot-g-lead-bucket-roi-report": "polymarket-bot-g-lead-bucket-roi-report.timer",
    "polymarket-bot-h-maker-v2-quote-paper": "polymarket-bot-h-maker-v2-quote-paper.timer",
    "polymarket-bot-h-maker-v2-resolution-backfill": "polymarket-bot-h-maker-v2-resolution-backfill.timer",
    "polymarket-bot-h-maker-v2-daily-replay": "polymarket-bot-h-maker-v2-daily-replay.timer",
    "polymarket-wallet-observer-daily-report": "polymarket-wallet-observer-daily-report.timer",
    "polymarket-bot-f-momentum-paper": "polymarket-bot-f-momentum-paper.timer",
    "polymarket-wallet-tag-feature-shadow": "polymarket-wallet-tag-feature-shadow.timer",
    "polymarket-wc-negrisk-basket-paper": "polymarket-wc-negrisk-basket-paper.timer",
    # Bot I Persistence (ADR-128) is a daily-timer oneshot — the .service
    # is `inactive` between runs by design. Healthy = timer active.
    "polymarket-persistence-paper": "polymarket-persistence-paper.timer",
    # Bot D wallet-position reconciler (2026-05-15): hourly oneshot that
    # closes locally-OPEN rows the wallet no longer holds. Decoupled
    # from polymarket-bot-d-live.service so dashboard truth is preserved
    # even when the live bot is not restarted.
    "polymarket-bot-d-wallet-reconcile": "polymarket-bot-d-wallet-reconcile.timer",
}

FLEET_EPOCH_START = "2026-04-30T00:00:00+00:00"
FLEET_EPOCH_ID = "fleet_epoch_2026_04_30"
BOT_G_PRIME_LIVE_EPOCH_START = "2026-05-10T16:28:10+00:00"
BOT_G_PRIME_LIVE_EPOCH_ID = "bot_g_prime_live_adr149_2026_05_10"
ARCHIVED_DASHBOARD_BOT_IDS = set(archived_dashboard_bot_ids())
CRYPTO_FAIR_VALUE_BOT_IDS = (
    "crypto_probability_gap_paper",
    "crypto_brownian_fv_paper",
    "crypto_probability_gap_paper_maker",
    "crypto_brownian_fv_paper_maker",
)


def _freshness_for_live_row(last_fill_at: str | None, registry_status: str) -> str:
    """Reusable freshness classifier for live registry rows (OQ-123 / phase 4).
    Returns one of: 'fresh' | 'stale_7d' | 'stale_30d' | 'unknown' | 'n/a'.
    Extracted from inline logic so it is used consistently in inventory, alerts, and services_summary.
    """
    if registry_status not in {"live", "paused"}:
        return "n/a"
    if not last_fill_at:
        return "unknown"
    try:
        lf = str(last_fill_at).replace("Z", "+00:00")
        last = datetime.fromisoformat(lf)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - last).days
        if age_days > 30:
            return "stale_30d"
        if age_days > 7:
            return "stale_7d"
        return "fresh"
    except Exception:
        return "unknown"


def _dashboard_specs_from_registry() -> tuple[dict[str, Any], ...]:
    specs: list[dict[str, Any]] = []
    for bot_id in dashboard_bot_ids():
        bot = bot_meta(bot_id)
        if bot is None:
            continue
        if bot_id == "bot_d":
            epoch_id = BOT_D_PAPER_EPOCH_ID
            epoch_start = BOT_D_PAPER_EPOCH_START
        elif bot_id == "bot_g_prime_live":
            epoch_id = BOT_G_PRIME_LIVE_EPOCH_ID
            epoch_start = BOT_G_PRIME_LIVE_EPOCH_START
        else:
            epoch_id = FLEET_EPOCH_ID
            epoch_start = FLEET_EPOCH_START
        specs.append(
            {
                "bot_id": bot.bot_id,
                "label": bot.display_name or bot.bot_id,
                "services": bot.dashboard_services,
                "registry_status": bot.status,
                "epoch_id": epoch_id,
                "epoch_start": epoch_start,
            }
        )
    return tuple(specs)


BOT_DASHBOARD_SPECS: tuple[dict[str, Any], ...] = _dashboard_specs_from_registry()

_balance_cache: dict[str, Any] = {"ts": 0.0, "value": None}
_balance_lock = threading.Lock()
_systemd_env_cache: dict[str, Any] = {"ts": 0.0, "units": {}}
_systemd_env_lock = threading.Lock()


def main_db_path() -> str:
    return os.environ.get("POLYMARKET_DB_PATH", "data/main.db")


def bot_c_db_path() -> str:
    return os.environ.get("BOT_C_DB_PATH", "data/bot_c_pyth.db")


def wallet_address() -> str:
    # Audit C23: no hardcoded default. If the operator hasn't set
    # POLYMARKET_WALLET, return empty and let the dashboard surface that
    # as "not configured" rather than querying somebody else's chain state.
    return os.environ.get("POLYMARKET_WALLET", "")


def rpc_url() -> str:
    return os.environ.get("POLYGON_RPC", "https://polygon-bor.publicnode.com")


def current_mode() -> str:
    return os.environ.get("POLYMARKET_ENV", "paper")


def _systemd_unit_env(unit: str) -> dict[str, str]:
    """Best-effort unit environment reader for live cap display.

    The dashboard service has its own environment, while live probes often set
    risk caps directly in their systemd unit. Reading the unit keeps the UI
    aligned with the bot that is actually trading; failures fall back to the
    dashboard process env.
    """
    now = time.time()
    with _systemd_env_lock:
        cached = (_systemd_env_cache.get("units") or {}).get(unit)
        if cached and now - float(cached.get("ts", 0.0)) < 15:
            return dict(cached.get("env") or {})
    try:
        result = subprocess.run(
            ["systemctl", "show", unit, "-p", "Environment", "--value"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        env: dict[str, str] = {}
        if result.returncode == 0 and result.stdout.strip():
            for item in shlex.split(result.stdout.strip()):
                if "=" not in item:
                    continue
                key, value = item.split("=", 1)
                env[key] = value
    except Exception:
        env = {}
    with _systemd_env_lock:
        units = dict(_systemd_env_cache.get("units") or {})
        units[unit] = {"ts": now, "env": env}
        _systemd_env_cache["ts"] = now
        _systemd_env_cache["units"] = units
    return env


def _env_from_unit(unit: str, key: str, default: str) -> str:
    return _systemd_unit_env(unit).get(key) or os.environ.get(key, default)


def initial_usd() -> dict[str, Decimal]:
    """Per-bot paper bankroll baseline used for dashboard return %.

    Reads `BOT_X_INITIAL_USD` first (explicit override), then the runtime
    bankroll env vars, then schema defaults. Keeps dashboard return % aligned
    with current active strategy surfaces.
    """
    return {
        "bot_c": Decimal(
            os.environ.get("BOT_C_INITIAL_USD", os.environ.get("BOT_C_BANKROLL_USD", "50"))
        ),
        "bot_d": Decimal(
            os.environ.get("BOT_D_INITIAL_USD", os.environ.get("BOT_D_BANKROLL_USD", "500"))
        ),
        "bot_d_live_probe": Decimal(
            os.environ.get(
                "BOT_D_LIVE_PROBE_INITIAL_USD",
                os.environ.get("BOT_D_LIVE_WALLET_USD", "200"),
            )
        ),
        "bot_d_maker_live_probe": Decimal(
            os.environ.get(
                "BOT_D_MAKER_LIVE_INITIAL_USD",
                os.environ.get("BOT_D_MAKER_LIVE_WALLET_USD", "200"),
            )
        ),
        "bot_e": Decimal(
            os.environ.get("BOT_E_INITIAL_USD", os.environ.get("BOT_E_BANKROLL_USD", "0"))
        ),
        "bot_g_prime": Decimal(
            os.environ.get("BOT_G_PRIME_INITIAL_USD", os.environ.get("BOT_G_BANKROLL_USD", "2000"))
        ),
        "bot_g_prime_maker": Decimal(
            os.environ.get(
                "BOT_G_PRIME_MAKER_INITIAL_USD", os.environ.get("BOT_G_BANKROLL_USD", "2000")
            )
        ),
        "bot_g_prime_live": Decimal(
            os.environ.get(
                "BOT_G_PRIME_LIVE_INITIAL_USD", os.environ.get("BOT_G_LIVE_WALLET_USD", "200")
            )
        ),
        "bot_g_prime_live_maker": Decimal(
            os.environ.get(
                "BOT_G_PRIME_LIVE_MAKER_INITIAL_USD", os.environ.get("BOT_G_LIVE_WALLET_USD", "200")
            )
        ),
        "bot_g_prime_shadow": Decimal(
            os.environ.get(
                "BOT_G_PRIME_SHADOW_INITIAL_USD", os.environ.get("BOT_G_LIVE_WALLET_USD", "200")
            )
        ),
        "bot_g_prime_high_tail": Decimal(
            os.environ.get(
                "BOT_G_PRIME_HIGH_TAIL_INITIAL_USD", os.environ.get("BOT_G_BANKROLL_USD", "2000")
            )
        ),
        "bot_g_prime_late_cheap": Decimal(
            os.environ.get(
                "BOT_G_PRIME_LATE_CHEAP_INITIAL_USD", os.environ.get("BOT_G_BANKROLL_USD", "2000")
            )
        ),
    }


def bot_e_recorder_db_path() -> str:
    return os.environ.get(
        "BOT_E_RECORDER_DB_PATH",
        str(Path(__file__).resolve().parents[1] / "data" / "bot_e_recorder.db"),
    )


def persistence_paper_db_path() -> str:
    return os.environ.get(
        "PERSISTENCE_PAPER_DB_PATH",
        "data/persistence_paper.db",
    )


def bot_f_momentum_paper_db_path() -> str:
    return os.environ.get(
        "BOT_F_MOMENTUM_PAPER_DB_PATH",
        "data/bot_f_momentum_paper.db",
    )


def wallet_tag_feature_shadow_db_path() -> str:
    return os.environ.get(
        "WALLET_TAG_FEATURE_SHADOW_DB_PATH",
        "data/wallet_tag_feature_shadow.db",
    )


def wallet_tag_elite_cap_paper_db_path() -> str:
    return os.environ.get(
        "WALLET_TAG_ELITE_CAP_PAPER_DB_PATH",
        "data/wallet_tag_elite_cap_paper.db",
    )


def wc_negrisk_basket_paper_db_path() -> str:
    return os.environ.get(
        "WC_NEGRISK_BASKET_PAPER_DB_PATH",
        "data/wc_negrisk_basket_paper.db",
    )


def maker_recorder_db_path() -> str:
    return os.environ.get(
        "BOT_H_MAKER_V2_RECORDER_DB_PATH",
        "data/maker_recorder.db",
    )


def wallet_observer_db_path() -> str:
    return os.environ.get(
        "WALLET_OBSERVER_DB",
        "data/wallet_observer.db",
    )


def persistence_halt_flag_path() -> str:
    return os.environ.get(
        "PERSISTENCE_HALT_FLAG_PATH",
        "data/persistence_paper.halt",
    )


def _persistence_paper_summary() -> dict[str, Any]:
    """Compact summary for the Active Recorders row + Overview surface.

    Returns total entry count, last-run age, halt flag, gates progress, and
    DB size. Empty dict on missing DB. Read-only.
    """
    db_path = Path(persistence_paper_db_path())
    halt_path = Path(persistence_halt_flag_path())
    out: dict[str, Any] = {
        "halt_flag_present": halt_path.exists(),
    }
    if not db_path.exists():
        return out
    try:
        out["size_bytes"] = db_path.stat().st_size
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS n, SUM(won) AS wins, "
                "SUM(pnl_usd) AS pnl, SUM(fee_usd) AS fees, "
                "SUM(ask_high) AS cost FROM paper_entries"
            ).fetchone()
            n = int(row[0] or 0)
            wins = int(row[1] or 0)
            pnl = float(row[2] or 0)
            fees = float(row[3] or 0)
            cost = float(row[4] or 0)
            out["n_entries"] = n
            out["wins"] = wins
            out["wr"] = round(wins / n, 4) if n else 0.0
            out["post_fee_roi"] = round((pnl - fees) / cost, 4) if cost else 0.0
            out["pnl_usd_net"] = round(pnl - fees, 4)
            out["cost_usd"] = round(cost, 4)

            per_cell: dict[str, int] = {}
            for r in conn.execute(
                "SELECT cell_label, COUNT(*) FROM paper_entries GROUP BY cell_label"
            ):
                per_cell[r[0]] = int(r[1] or 0)
            out["per_cell_n"] = per_cell

            r2 = conn.execute(
                "SELECT started_at_ms, n_added_total, halted "
                "FROM run_log ORDER BY started_at_ms DESC LIMIT 1"
            ).fetchone()
            if r2:
                out["last_run_ms"] = int(r2[0] or 0)
                out["last_run_added"] = int(r2[1] or 0)
                out["last_run_halted"] = bool(r2[2])
                age_sec = (datetime.now(timezone.utc).timestamp() * 1000 - int(r2[0] or 0)) / 1000.0
                out["heartbeat_age_sec"] = round(max(0, age_sec), 1)
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return out


def _bot_f_momentum_paper_summary() -> dict[str, Any]:
    """Compact read-only summary for Crowd Momentum Paper (F)."""
    db_path = Path(bot_f_momentum_paper_db_path())
    out: dict[str, Any] = {}
    if not db_path.exists():
        return out
    try:
        out["size_bytes"] = db_path.stat().st_size
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        try:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS n_entries,
                    SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END) AS closed,
                    SUM(CASE WHEN status='CLOSED' AND pnl_usd > 0 THEN 1 ELSE 0 END) AS wins,
                    COALESCE(SUM(CASE WHEN status='CLOSED' THEN pnl_usd ELSE 0 END), 0) AS pnl,
                    COALESCE(SUM(CASE WHEN status='CLOSED' THEN size_usd ELSE 0 END), 0) AS cost,
                    SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS open_entries
                FROM paper_entries
                """
            ).fetchone()
            n_entries = int(row[0] or 0)
            closed = int(row[1] or 0)
            wins = int(row[2] or 0)
            pnl = float(row[3] or 0)
            cost = float(row[4] or 0)
            open_cost_row = conn.execute(
                "SELECT COALESCE(SUM(size_usd), 0) FROM paper_entries WHERE status='OPEN'"
            ).fetchone()
            out.update(
                {
                    "n_entries": n_entries,
                    "closed": closed,
                    "wins": wins,
                    "open_entries": int(row[5] or 0),
                    "pnl_usd": round(pnl, 2),
                    "post_fee_roi": round(pnl / cost, 4) if cost else 0.0,
                    "open_cost_usd": round(float(open_cost_row[0] or 0), 2),
                }
            )
            r2 = conn.execute(
                "SELECT started_at, candidates, inserted, closed "
                "FROM run_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if r2:
                out["last_run"] = r2[0]
                out["last_run_candidates"] = int(r2[1] or 0)
                out["last_run_inserted"] = int(r2[2] or 0)
                out["last_run_closed"] = int(r2[3] or 0)
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return out


def _wallet_tag_feature_shadow_summary(path: str | Path | None = None) -> dict[str, Any]:
    db_path = Path(path or wallet_tag_feature_shadow_db_path())
    out: dict[str, Any] = {}
    if not db_path.exists():
        return out
    try:
        out["size_bytes"] = db_path.stat().st_size
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END) AS closed,
                       SUM(CASE WHEN status='CLOSED' AND pnl_usd > 0 THEN 1 ELSE 0 END) AS wins,
                       COALESCE(SUM(CASE WHEN status='CLOSED' THEN pnl_usd ELSE 0 END), 0) AS pnl,
                       COALESCE(SUM(CASE WHEN status='CLOSED' THEN entry_cost_usd ELSE 0 END), 0) AS cost,
                       SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS open_entries
                FROM paper_entries
                """
            ).fetchone()
            n = int(row[0] or 0)
            closed = int(row[1] or 0)
            wins = int(row[2] or 0)
            pnl = float(row[3] or 0)
            cost = float(row[4] or 0)
            # Open-position cost basis: sum of entry_cost on OPEN rows.
            open_cost_row = conn.execute(
                "SELECT COALESCE(SUM(entry_cost_usd), 0) FROM paper_entries WHERE status='OPEN'"
            ).fetchone()
            out.update(
                {
                    "n_entries": n,
                    "closed": closed,
                    "wins": wins,
                    "open_entries": int(row[5] or 0),
                    "pnl_usd": round(pnl, 2),
                    "post_fee_roi": round(pnl / cost, 4) if cost else 0.0,
                    "open_cost_usd": round(float(open_cost_row[0] or 0), 2),
                }
            )
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return out


def _wallet_tag_elite_cap_paper_summary() -> dict[str, Any]:
    return _wallet_tag_feature_shadow_summary(wallet_tag_elite_cap_paper_db_path())


def _wc_negrisk_basket_paper_summary() -> dict[str, Any]:
    db_path = Path(wc_negrisk_basket_paper_db_path())
    out: dict[str, Any] = {}
    if not db_path.exists():
        return out
    try:
        out["size_bytes"] = db_path.stat().st_size
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n,
                       SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END) AS open_baskets,
                       COALESCE(AVG(ask_sum_entry), 0) AS avg_ask_sum,
                       COALESCE(MIN(ask_sum_entry), 0) AS best_ask_sum,
                       COALESCE(AVG(net_edge_after_fee), 0) AS avg_net_edge,
                       COALESCE(MAX(net_edge_after_fee), 0) AS best_net_edge,
                       COALESCE(SUM(realised_pnl_usd), 0) AS pnl
                FROM paper_baskets
                """
            ).fetchone()
            obs = conn.execute("SELECT COUNT(*) FROM basket_observations").fetchone()[0]
            open_cost_row = conn.execute(
                "SELECT COALESCE(SUM(ask_sum_entry), 0) FROM paper_baskets WHERE status='OPEN'"
            ).fetchone()
            out.update(
                {
                    "n_baskets": int(row[0] or 0),
                    "open_baskets": int(row[1] or 0),
                    "avg_ask_sum": round(float(row[2] or 0), 4),
                    "best_ask_sum": round(float(row[3] or 0), 4),
                    "avg_net_edge": round(float(row[4] or 0), 4),
                    "best_net_edge": round(float(row[5] or 0), 4),
                    "pnl_usd": round(float(row[6] or 0), 2),
                    "observations": int(obs or 0),
                    "open_cost_usd": round(float(open_cost_row[0] or 0), 2),
                }
            )
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return out


def bot_e_calibration_go_path() -> str:
    return os.environ.get(
        "BOT_E_CALIBRATION_GO_PATH",
        str(Path(__file__).resolve().parents[1] / "data" / "bot_e_calibration.json"),
    )


def bot_g_lead_bucket_report_path() -> Path:
    return Path(
        os.environ.get(
            "BOT_G_LEAD_BUCKET_REPORT_JSON",
            str(Path(main_db_path()).parent / "reports" / "bot_g_lead_bucket" / "latest.json"),
        )
    )


def _read_json_path(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _load_vps_node_status() -> dict[str, Any]:
    """Load the optional split-hosting VPS status artifact.

    Disabled unless `VPS_NODE_STATUS_URL` or `VPS_NODE_STATUS_PATH` is set, so
    local dashboard tests and single-host deployments do not make network
    calls. In production, the bot container should read this over Tailscale.
    """
    url = os.environ.get("VPS_NODE_STATUS_URL", "").strip()
    path_raw = os.environ.get("VPS_NODE_STATUS_PATH", "").strip()
    if not url and not path_raw:
        return {"configured": False, "ok": False, "status": "not_configured"}

    source = url or path_raw
    try:
        if url:
            with urlopen(
                url, timeout=float(os.environ.get("VPS_NODE_STATUS_TIMEOUT", "1.5"))
            ) as response:
                report = json.loads(response.read().decode("utf-8"))
        else:
            report = _read_json_path(Path(path_raw))
    except (OSError, TimeoutError, ValueError, HTTPError, URLError, json.JSONDecodeError) as exc:
        return {
            "configured": True,
            "ok": False,
            "status": "unreachable",
            "source": source,
            "error": str(exc),
        }

    generated_at = str(report.get("generated_at") or "")
    age_seconds: float | None = None
    try:
        generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=UTC)
        age_seconds = max(0.0, (datetime.now(UTC) - generated.astimezone(UTC)).total_seconds())
    except ValueError:
        pass

    services = report.get("services") if isinstance(report.get("services"), dict) else {}
    tailscale = report.get("tailscale") if isinstance(report.get("tailscale"), dict) else {}
    tailscale_status = tailscale.get("status") if isinstance(tailscale.get("status"), dict) else {}
    disk = report.get("disk") if isinstance(report.get("disk"), dict) else {}
    databases = report.get("databases") if isinstance(report.get("databases"), dict) else {}

    service_states = {
        name: {
            "active": state.get("active") if isinstance(state, dict) else "unknown",
            "enabled": state.get("enabled") if isinstance(state, dict) else "unknown",
        }
        for name, state in services.items()
    }
    required_services = (
        "ssh.service",
        "ssh.socket",
        "tailscaled.service",
        "longshot-vps-node-status.timer",
    )
    required_ok = all(
        service_states.get(name, {}).get("active") == "active" for name in required_services
    )
    fresh = age_seconds is not None and age_seconds < int(
        os.environ.get("VPS_NODE_STATUS_STALE_SECONDS", "180")
    )
    running = tailscale_status.get("BackendState") == "Running"
    ok = bool(fresh and running and required_ok)
    if ok:
        status = "healthy"
    elif age_seconds is not None and not fresh:
        status = "stale"
    else:
        status = "degraded"

    return {
        "configured": True,
        "ok": ok,
        "status": status,
        "source": source,
        "generated_at": generated_at,
        "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "node": report.get("node") if isinstance(report.get("node"), dict) else {},
        "disk": {
            "used_pct": disk.get("used_pct"),
            "free_bytes": disk.get("free_bytes"),
        },
        "tailscale": {
            "state": tailscale_status.get("BackendState"),
            "ipv4": tailscale.get("ipv4"),
        },
        "services": service_states,
        "databases": databases,
        "recorder": (report.get("recorder") if isinstance(report.get("recorder"), dict) else {}),
        "bot_g": (report.get("bot_g") if isinstance(report.get("bot_g"), dict) else {}),
        "bot_d_spike": (
            report.get("bot_d_spike") if isinstance(report.get("bot_d_spike"), dict) else {}
        ),
        "bot_d_spike_short": (
            report.get("bot_d_spike_short")
            if isinstance(report.get("bot_d_spike_short"), dict)
            else {}
        ),
        "bot_h_maker_v2": (
            report.get("bot_h_maker_v2") if isinstance(report.get("bot_h_maker_v2"), dict) else {}
        ),
        "bot_h_quote_paper": (
            report.get("bot_h_quote_paper")
            if isinstance(report.get("bot_h_quote_paper"), dict)
            else {}
        ),
        "wallet_observer": (
            report.get("wallet_observer") if isinstance(report.get("wallet_observer"), dict) else {}
        ),
    }


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{main_db_path()}?mode=ro", uri=True, timeout=5)
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.row_factory = sqlite3.Row
    return conn


def _bot_c_db() -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{bot_c_db_path()}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _fmt_decimal(value: Decimal | None, places: int = 2) -> str:
    amount = Decimal("0") if value is None else Decimal(str(value))
    return f"{amount:.{places}f}"


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    return value.isoformat()


def _mask_wallet(address: str) -> str:
    if len(address) < 12:
        return address
    return f"{address[:6]}…{address[-4:]}"


def _parse_epoch_start(raw: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime(2026, 4, 29, 19, 10, tzinfo=UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _sqlite_dt(value: datetime) -> str:
    return value.astimezone(UTC).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")


def _bot_d_epoch() -> dict[str, Any]:
    start = _parse_epoch_start(BOT_D_PAPER_EPOCH_START)
    return {
        "id": BOT_D_PAPER_EPOCH_ID,
        "start": start.isoformat(),
        "label": "Bot D station-fix paper epoch",
    }


def _bot_d_source_edge_summary(hours: int = 6, bot_id: str = "bot_d_live_probe") -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out: dict[str, Any] = {
        "lookback_hours": hours,
        "bot_id": bot_id,
        "snapshots": 0,
        "late_certain": 0,
        "bucket_locked": 0,
        "bucket_impossible": 0,
        "by_bucket_state": {},
        "latest": [],
    }
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT payload, created_at FROM events "
                "WHERE bot_id=? AND event_type='bot_d.source_snapshot' AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT 500",
                (bot_id, _sqlite_dt(cutoff)),
            ).fetchall()
        states: dict[str, int] = defaultdict(int)
        latest: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = (
                    json.loads(row["payload"])
                    if isinstance(row["payload"], str)
                    else row["payload"]
                )
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            state = str(payload.get("bucket_state") or "unknown")
            states[state] += 1
            if state in {"already_yes", "already_no", "locked_yes", "locked_no"}:
                out["late_certain"] += 1
            if payload.get("bucket_locked"):
                out["bucket_locked"] += 1
            if payload.get("bucket_impossible"):
                out["bucket_impossible"] += 1
            if len(latest) < 10:
                latest.append(
                    {
                        "created_at": row["created_at"],
                        "city": payload.get("city"),
                        "station": payload.get("settlement_station"),
                        "date": payload.get("date"),
                        "temp_type": payload.get("temp_type"),
                        "bucket_state": state,
                        "yes_price": payload.get("market_yes_price"),
                        "station_metric_f": payload.get("station_metric_f"),
                        "lock_age_seconds": payload.get("lock_age_seconds"),
                    }
                )
        out["snapshots"] = len(rows)
        out["by_bucket_state"] = dict(sorted(states.items()))
        out["latest"] = latest
    except Exception as exc:
        out["error"] = str(exc)[:200]
    return out


def _bot_d_gribstream_summary(hours: int = 24, bot_id: str = "bot_d_live_probe") -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out: dict[str, Any] = {
        "lookback_hours": hours,
        "bot_id": bot_id,
        "events": 0,
        "http_calls": 0,
        "cache_hits": 0,
        "ok_calls": 0,
        "error_calls": 0,
        "empty_calls": 0,
        "response_rows": 0,
        "result_dates": 0,
        "response_bytes": 0,
        "avg_duration_ms": None,
        "by_status": {},
        "by_city": {},
        "latest": [],
    }
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT payload, created_at FROM events "
                "WHERE bot_id=? AND event_type='bot_d.gribstream_call' AND created_at >= ? "
                "ORDER BY created_at DESC LIMIT 2000",
                (bot_id, _sqlite_dt(cutoff)),
            ).fetchall()
        statuses: dict[str, int] = defaultdict(int)
        cities: dict[str, int] = defaultdict(int)
        durations: list[float] = []
        latest: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = (
                    json.loads(row["payload"])
                    if isinstance(row["payload"], str)
                    else row["payload"]
                )
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            status = str(payload.get("status") or "unknown")
            city = str(payload.get("city") or "unknown")
            from_cache = bool(payload.get("from_cache"))
            statuses[status] += 1
            cities[city] += 1
            out["events"] += 1
            if from_cache:
                out["cache_hits"] += 1
            else:
                out["http_calls"] += 1
            if status == "ok":
                out["ok_calls"] += 1
            elif status == "empty":
                out["empty_calls"] += 1
            elif status not in {"cache_hit", "disabled"}:
                out["error_calls"] += 1
            try:
                out["response_rows"] += int(payload.get("response_rows") or 0)
                out["result_dates"] += int(payload.get("results_count") or 0)
                out["response_bytes"] += int(payload.get("response_bytes") or 0)
            except (TypeError, ValueError):
                pass
            try:
                if payload.get("duration_ms") is not None:
                    durations.append(float(payload.get("duration_ms")))
            except (TypeError, ValueError):
                pass
            if len(latest) < 8:
                latest.append(
                    {
                        "created_at": row["created_at"],
                        "city": payload.get("city"),
                        "model": payload.get("model"),
                        "status": status,
                        "from_cache": from_cache,
                        "http_status": payload.get("http_status"),
                        "response_rows": payload.get("response_rows"),
                        "results_count": payload.get("results_count"),
                        "duration_ms": payload.get("duration_ms"),
                    }
                )
        out["by_status"] = dict(sorted(statuses.items()))
        out["by_city"] = dict(sorted(cities.items()))
        out["avg_duration_ms"] = round(sum(durations) / len(durations), 1) if durations else None
        out["latest"] = latest
    except Exception as exc:
        out["error"] = str(exc)[:200]
    return out


def _event_payload(row: sqlite3.Row) -> dict[str, Any]:
    try:
        payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _bot_d_station_lock_summary(hours: int = 24) -> dict[str, Any]:
    """Compact dashboard summary for Bot D Station Lock paper lane.

    Station Lock writes synthetic evidence to Event rows only. This helper is
    intentionally read-only and does not infer real Order/Position state.
    """
    bot_id = "bot_d_station_lock"
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out: dict[str, Any] = {
        "bot_id": bot_id,
        "lookback_hours": hours,
        "candidates": 0,
        "entries": 0,
        "fills": 0,
        "skips": 0,
        "resolutions": 0,
        "open_fills": 0,
        "paper_notional_usd": 0.0,
        "open_notional_usd": 0.0,
        "realised_pnl_usd": 0.0,
        "win_count": 0,
        "loss_count": 0,
        "rounding_disagreements": 0,
        "wu_station_mutations": 0,
        "by_city": {},
        "by_state": {},
        "skip_reasons": {},
        "latest": [],
    }
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT event_type, payload, created_at FROM events "
                "WHERE bot_id=? AND event_type LIKE 'bot_d.station_lock.%' "
                "AND created_at >= ? ORDER BY created_at DESC LIMIT 3000",
                (bot_id, _sqlite_dt(cutoff)),
            ).fetchall()
        cities: dict[str, int] = defaultdict(int)
        states: dict[str, int] = defaultdict(int)
        skips: dict[str, int] = defaultdict(int)
        open_by_key: dict[str, float] = {}
        latest: list[dict[str, Any]] = []
        for row in rows:
            event_type = str(row["event_type"] or "")
            payload = _event_payload(row)
            city = str(payload.get("city") or "unknown")
            state = str(payload.get("state") or payload.get("station_state") or "unknown")
            condition_id = str(payload.get("condition_id") or "")
            side = str(payload.get("side") or payload.get("certain_side") or "")
            token_id = str(payload.get("token_id") or "")
            key = "|".join(part for part in (condition_id, side, token_id) if part)
            if event_type == "bot_d.station_lock.candidate":
                out["candidates"] += 1
                cities[city] += 1
                states[state] += 1
                if payload.get("rounding_disagreement"):
                    out["rounding_disagreements"] += 1
                if payload.get("wu_station_mutation"):
                    out["wu_station_mutations"] += 1
            elif event_type == "bot_d.station_lock.entry_attempt":
                out["entries"] += 1
                try:
                    out["paper_notional_usd"] += float(payload.get("paper_notional_usd") or 0)
                except (TypeError, ValueError):
                    pass
            elif event_type == "bot_d.station_lock.paper_fill":
                out["fills"] += 1
                try:
                    notional = float(payload.get("paper_notional_usd") or 0)
                except (TypeError, ValueError):
                    notional = 0.0
                if key:
                    open_by_key[key] = notional
            elif event_type == "bot_d.station_lock.resolution":
                out["resolutions"] += 1
                if bool(payload.get("resolved_correct")):
                    out["win_count"] += 1
                else:
                    out["loss_count"] += 1
                try:
                    out["realised_pnl_usd"] += float(payload.get("paper_realised_pnl_usd") or 0)
                except (TypeError, ValueError):
                    pass
                if key and key in open_by_key:
                    open_by_key.pop(key, None)
            elif event_type == "bot_d.station_lock.skip":
                out["skips"] += 1
                reason = str(payload.get("reason") or payload.get("skip_reason") or "unknown")
                skips[reason] += 1
            if len(latest) < 12:
                latest.append(
                    {
                        "created_at": row["created_at"],
                        "event_type": event_type.removeprefix("bot_d.station_lock."),
                        "city": payload.get("city"),
                        "date": payload.get("date"),
                        "state": state,
                        "side": side or None,
                        "price": payload.get("yes_price") or payload.get("market_yes_price"),
                        "reason": payload.get("reason") or payload.get("skip_reason"),
                        "pnl_usd": payload.get("paper_realised_pnl_usd"),
                    }
                )
        out["open_fills"] = len(open_by_key)
        out["open_notional_usd"] = round(sum(open_by_key.values()), 2)
        out["paper_notional_usd"] = round(float(out["paper_notional_usd"]), 2)
        out["realised_pnl_usd"] = round(float(out["realised_pnl_usd"]), 2)
        out["by_city"] = dict(sorted(cities.items(), key=lambda kv: (-kv[1], kv[0]))[:12])
        out["by_state"] = dict(sorted(states.items()))
        out["skip_reasons"] = dict(sorted(skips.items(), key=lambda kv: (-kv[1], kv[0]))[:12])
        out["latest"] = latest
    except Exception as exc:
        out["error"] = str(exc)[:200]
    return out


def _env_epoch_value(bot_id: str, field: str, default: str) -> str:
    env_name = f"{bot_id.upper()}_PAPER_EPOCH_{field}"
    return os.environ.get(env_name, default)


_LIVE_EPOCH_BOT_IDS: tuple[str, ...] = (
    "bot_g_prime_live",
    "bot_d_live_probe",
    "bot_d_maker_live_probe",
)


def _bot_epoch(spec: dict[str, Any]) -> dict[str, Any]:
    epoch_id = _env_epoch_value(spec["bot_id"], "ID", str(spec["epoch_id"]))
    raw_start = _env_epoch_value(spec["bot_id"], "START", str(spec["epoch_start"]))
    start = _parse_epoch_start(raw_start)
    suffix = "live epoch" if spec["bot_id"] in _LIVE_EPOCH_BOT_IDS else "paper epoch"
    return {
        "id": epoch_id,
        "start": start.isoformat(),
        "label": f"{spec['label']} {suffix}",
    }


def _service_is_active(state: str | None) -> bool:
    return state in {"active", "timer:active", "vps:active"}


def _halted_bot_ids() -> set[str]:
    session_factory = get_session_factory()
    with session_factory() as session:
        rows = session.query(HaltFlag.bot_id, HaltFlag.reason).filter(HaltFlag.halted == 1).all()
    return {row[0] for row in rows if row[0] and "unhalt" not in (row[1] or "").lower()}


def _spec_for(bot_id: str) -> dict[str, Any]:
    for spec in BOT_DASHBOARD_SPECS:
        if spec["bot_id"] == bot_id:
            return spec
    bot = bot_meta(bot_id)
    if bot is not None and bot.dashboard_services:
        return {
            "bot_id": bot.bot_id,
            "label": bot.display_name or bot.bot_id,
            "services": bot.dashboard_services,
            "registry_status": bot.status,
            "epoch_id": FLEET_EPOCH_ID,
            "epoch_start": FLEET_EPOCH_START,
        }
    return {
        "bot_id": bot_id,
        "label": bot_id,
        "services": (),
        "epoch_id": FLEET_EPOCH_ID,
        "epoch_start": FLEET_EPOCH_START,
    }


def _bot_active_status(
    spec: dict[str, Any],
    services: dict[str, str],
    halted_ids: set[str],
) -> dict[str, Any]:
    service_names = tuple(spec.get("services") or ())
    service_states_for_bot = {name: services.get(name, "unknown") for name in service_names}
    healthy = [_service_is_active(state) for state in service_states_for_bot.values()]
    halted = spec["bot_id"] in halted_ids
    registry_status = str(spec.get("registry_status") or spec.get("status") or "")
    if halted:
        label = "halted"
    elif registry_status == "paused" and any(healthy):
        label = "active_policy_conflict"
    elif registry_status == "paused":
        label = "paused"
    elif healthy and all(healthy):
        label = "active"
    elif any(healthy):
        label = "degraded"
    elif service_states_for_bot:
        label = "inactive"
    else:
        label = "unknown"
    return {
        "status": label,
        "active": label in {"active", "active_policy_conflict"},
        "halted": halted,
        "services": service_states_for_bot,
    }


def _bot_simple_summary(
    spec: dict[str, Any],
    *,
    services: dict[str, str] | None = None,
    halted_ids: set[str] | None = None,
) -> dict[str, Any]:
    services = service_states() if services is None else services
    halted_ids = _halted_bot_ids() if halted_ids is None else halted_ids
    epoch = _bot_epoch(spec)
    epoch_start = _parse_epoch_start(epoch["start"])
    metrics = _bot_epoch_fast_metrics(spec["bot_id"], epoch_start)
    if spec["bot_id"] in {"bot_d_live_probe", "bot_d_maker_live_probe"}:
        trade_metrics = _trade_metrics(spec["bot_id"], since=epoch_start)
        metrics["cash_pnl_usd"] = metrics["pnl_usd"]
        metrics["pnl_usd"] = trade_metrics["realised_pnl_usd"]
        metrics["realised_pnl_usd"] = trade_metrics["realised_pnl_usd"]
        metrics["pnl_note"] = "realised live P&L"
    status = _bot_active_status(spec, services, halted_ids)
    return {
        "bot_id": spec["bot_id"],
        "label": spec["label"],
        "epoch": epoch,
        "status": status["status"],
        "active": status["active"],
        "halted": status["halted"],
        "services": status["services"],
        "pnl_usd": metrics["pnl_usd"],
        "paper_amount_usd": metrics["paper_amount_usd"],
        "trades": metrics["trades"],
        "fills": metrics["fills"],
        "settlement_fills": metrics["settlement_fills"],
        "trade_rows": metrics["trade_rows"],
        "open_orders": metrics["open_orders"],
        "paper_open_orders": metrics["paper_open_orders"],
        "open_positions": metrics["open_positions"],
        "open_position_cost_usd": metrics["open_position_cost_usd"],
        **(
            {"realised_pnl_usd": metrics["realised_pnl_usd"]}
            if "realised_pnl_usd" in metrics
            else {}
        ),
        **({"cash_pnl_usd": metrics["cash_pnl_usd"]} if "cash_pnl_usd" in metrics else {}),
        **({"pnl_note": metrics["pnl_note"]} if "pnl_note" in metrics else {}),
    }


def _bot_d_spike_vps_simple(
    simple: dict[str, Any],
    vps: dict[str, Any],
    order_metrics: dict[str, Any],
    trade_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Return a simple summary whose headline counts come from the VPS lane."""
    updated = dict(simple)
    updated.update(
        {
            "pnl_usd": float(trade_metrics.get("realised_pnl_usd") or 0.0),
            "paper_amount_usd": float(order_metrics.get("reserved_notional_usd") or 0.0),
            "trades": int(order_metrics.get("total_orders") or 0),
            "fills": int(trade_metrics.get("filled_trades_count") or 0),
            "settlement_fills": int(trade_metrics.get("settlement_fills_count") or 0),
            "trade_rows": int(trade_metrics.get("trade_rows_count") or 0),
            "open_orders": int(order_metrics.get("open_orders") or 0),
            "paper_open_orders": int(order_metrics.get("paper_open_orders") or 0),
            "open_positions": int(vps.get("open_positions") or 0),
            "open_position_cost_usd": float(vps.get("open_cost_basis_usd") or 0.0),
            "pnl_note": "VPS paper realised P&L",
        }
    )
    return updated


def _vps_bot_g_is_remote(bot_id: str, services: dict[str, str], vps_bot_g: dict[str, Any]) -> bool:
    spec = _spec_for(bot_id)
    return any(
        services.get(str(service)) == "vps:active" for service in spec.get("services", ())
    ) and bot_id in (vps_bot_g.get("bot_ids") or [])


def _vps_bot_g_open_cost(bot_id: str, vps_bot_g: dict[str, Any]) -> float:
    positions_open = (
        vps_bot_g.get("positions_open") if isinstance(vps_bot_g.get("positions_open"), dict) else {}
    )
    total = 0.0
    for position in positions_open.get(bot_id, []):
        if isinstance(position, dict):
            try:
                total += float(position.get("cost_basis_usd") or 0)
            except (TypeError, ValueError):
                continue
    return round(total, 2)


def _vps_bot_g_fast_metrics(bot_id: str, vps_bot_g: dict[str, Any]) -> dict[str, Any] | None:
    live_epoch = (
        vps_bot_g.get("live_epoch") if isinstance(vps_bot_g.get("live_epoch"), dict) else {}
    )
    if bot_id == "bot_g_prime_live" and live_epoch:
        order_metrics = {"bot_g_prime_live": live_epoch.get("order_metrics") or {}}
        trade_metrics = {"bot_g_prime_live": live_epoch.get("trade_metrics") or {}}
        positions_open = {"bot_g_prime_live": live_epoch.get("positions_open") or []}
        paper_pnl = {}
        metric_note = f"VPS realised P&L since {live_epoch.get('start')}"
    else:
        order_metrics = (
            vps_bot_g.get("order_metrics")
            if isinstance(vps_bot_g.get("order_metrics"), dict)
            else {}
        )
        trade_metrics = (
            vps_bot_g.get("trade_metrics")
            if isinstance(vps_bot_g.get("trade_metrics"), dict)
            else {}
        )
        paper_pnl = (
            vps_bot_g.get("paper_pnl") if isinstance(vps_bot_g.get("paper_pnl"), dict) else {}
        )
        positions_open = (
            vps_bot_g.get("positions_open")
            if isinstance(vps_bot_g.get("positions_open"), dict)
            else {}
        )
        metric_note = "VPS realised P&L"
    orders = order_metrics.get(bot_id)
    trades = trade_metrics.get(bot_id)
    if not isinstance(orders, dict) or not isinstance(trades, dict):
        return None
    open_cost = 0.0
    for position in positions_open.get(bot_id, []):
        if isinstance(position, dict):
            try:
                open_cost += float(position.get("cost_basis_usd") or 0)
            except (TypeError, ValueError):
                continue
    open_cost = round(open_cost, 2)
    paper = paper_pnl.get(bot_id) if isinstance(paper_pnl.get(bot_id), dict) else {}
    return {
        "pnl_usd": round(float(trades.get("realised_pnl_usd") or 0), 2),
        "paper_amount_usd": round(
            float(orders.get("reserved_notional_usd") or paper.get("capital_deployed") or 0), 2
        ),
        "trades": int(orders.get("total_orders") or 0),
        "fills": int(trades.get("filled_trades_count") or 0),
        "settlement_fills": int(trades.get("settlement_fills_count") or 0),
        "trade_rows": int(trades.get("trade_rows_count") or 0),
        "open_orders": int(orders.get("open_orders") or 0),
        "paper_open_orders": int(orders.get("paper_open_orders") or 0),
        "open_positions": len(positions_open.get(bot_id, [])),
        "open_position_cost_usd": open_cost,
        "realised_pnl_usd": round(float(trades.get("realised_pnl_usd") or 0), 2),
        "cash_pnl_usd": round(float(trades.get("realised_pnl_usd") or 0), 2),
        "pnl_note": metric_note,
    }


def _summary_needs_vps_bot_g_metrics(summary: dict[str, Any], vps_bot_g: dict[str, Any]) -> bool:
    metrics = _vps_bot_g_fast_metrics(str(summary.get("bot_id") or ""), vps_bot_g)
    if metrics is None:
        return False
    return int(metrics["trades"]) > int(summary.get("trades") or 0)


def _apply_vps_bot_g_simple_metrics(
    summary: dict[str, Any], vps_bot_g: dict[str, Any]
) -> dict[str, Any]:
    metrics = _vps_bot_g_fast_metrics(str(summary.get("bot_id") or ""), vps_bot_g)
    if metrics is None:
        return summary
    summary.update(metrics)
    summary["data_source"] = "vps"
    summary["pnl_breakdown"] = {
        "closed_realised_usd": metrics["realised_pnl_usd"],
        "open_cost_usd": metrics["open_position_cost_usd"],
    }
    summary["pnl_note"] = (
        f"VPS realised ${metrics['realised_pnl_usd']:.2f} "
        f"- open ${metrics['open_position_cost_usd']:.2f}"
    )
    return summary


def _bot_epoch_fast_metrics(bot_id: str, since: datetime) -> dict[str, Any]:
    """Fast dashboard-only epoch metrics.

    This intentionally avoids full FIFO/portfolio scans. Historical records
    remain queryable through the detailed endpoints and DB; the dashboard
    cards need fast, stable headline numbers.
    """
    empty = {
        "pnl_usd": 0.0,
        "paper_amount_usd": 0.0,
        "trades": 0,
        "fills": 0,
        "settlement_fills": 0,
        "trade_rows": 0,
        "open_orders": 0,
        "paper_open_orders": 0,
        "open_positions": 0,
        "open_position_cost_usd": 0.0,
    }
    try:
        since_sql = _sqlite_dt(since)
        with _db() as conn:
            order_row = conn.execute(
                """
                SELECT
                  COUNT(*) AS trades,
                  SUM(CASE WHEN status IN ('PAPER_OPEN', 'OPEN', 'PARTIAL', 'live') THEN 1 ELSE 0 END) AS open_orders,
                  SUM(CASE WHEN status = 'PAPER_OPEN' THEN 1 ELSE 0 END) AS paper_open_orders,
                  SUM(
                    CASE
                      WHEN status IN ('PAPER_OPEN', 'OPEN', 'PARTIAL', 'live')
                      THEN COALESCE(price, 0) * COALESCE(size, 0)
                      ELSE 0
                    END
                  ) AS paper_amount
                FROM orders
                WHERE bot_id=? AND placed_at >= ?
                """,
                (bot_id, since_sql),
            ).fetchone()
            trade_row = conn.execute(
                """
                SELECT
                  SUM(CASE WHEN trade_id NOT LIKE 'paper-resolve-%' THEN 1 ELSE 0 END) AS fills,
                  SUM(CASE WHEN trade_id LIKE 'paper-resolve-%' THEN 1 ELSE 0 END) AS settlement_fills,
                  COUNT(*) AS trade_rows,
                  SUM(
                    CASE
                      WHEN side LIKE 'SELL%' THEN (COALESCE(price, 0) * COALESCE(size, 0)) - COALESCE(fee_usd, 0)
                      ELSE -((COALESCE(price, 0) * COALESCE(size, 0)) + COALESCE(fee_usd, 0))
                    END
                  ) AS cash_pnl
                FROM trades
                WHERE bot_id=? AND filled_at >= ?
                """,
                (bot_id, since_sql),
            ).fetchone()
            position_row = conn.execute(
                """
                SELECT
                  COUNT(*) AS open_positions,
                  COALESCE(SUM(COALESCE(cost_basis_usd, 0)), 0) AS open_position_cost
                FROM positions
                WHERE bot_id=?
                  AND status='OPEN'
                  AND opened_at >= ?
                """,
                (bot_id, since_sql),
            ).fetchone()
        return {
            "pnl_usd": round(float(trade_row["cash_pnl"] or 0.0), 2),
            "paper_amount_usd": round(float(order_row["paper_amount"] or 0.0), 2),
            "trades": int(order_row["trades"] or 0),
            "fills": int(trade_row["fills"] or 0),
            "settlement_fills": int(trade_row["settlement_fills"] or 0),
            "trade_rows": int(trade_row["trade_rows"] or 0),
            "open_orders": int(order_row["open_orders"] or 0),
            "paper_open_orders": int(order_row["paper_open_orders"] or 0),
            "open_positions": int(position_row["open_positions"] or 0),
            "open_position_cost_usd": round(float(position_row["open_position_cost"] or 0.0), 2),
        }
    except Exception:
        return empty


def _fleet_bot_summaries(
    services: dict[str, str] | None = None,
    halted_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    services = service_states() if services is None else services
    halted_ids = _halted_bot_ids() if halted_ids is None else halted_ids
    return [
        _bot_simple_summary(spec, services=services, halted_ids=halted_ids)
        for spec in BOT_DASHBOARD_SPECS
    ]


def _inventory_group(registry_status: str, bot_id: str) -> str:
    if registry_status == "archived":
        return "Archived"
    if registry_status in {"live", "paused"}:
        return "Live"
    if registry_status == "sensor":
        return "Recorder"
    if bot_id.startswith("bot_b"):
        return "Parked"
    if registry_status in {"paper", "paper_tuning", "shadow"}:
        return "Paper"
    if registry_status == "paused":
        return "Paused"
    return "Other"


def _inventory_mode(registry_status: str, group: str) -> str:
    if group == "Recorder":
        return "read-only"
    if group == "Parked":
        return "parked"
    if group == "Archived":
        return "off"
    if registry_status == "paper_tuning":
        return "paper tuning"
    return registry_status.replace("_", " ")


def _inventory_time_to_decision(bot_id: str) -> str | None:
    """Operator-facing proof horizon for active lanes."""
    horizons = {
        "bot_g_prime_live": "operator decision pending",
        "bot_d_live_probe": "continuous (OQ-067)",
        "bot_d": "OQ-093/096 cycle",
        "bot_d_source_shadow": "50-60 closed source-sliced groups",
        "bot_d_spike": "200 closes / ~95d",
        "bot_d_spike_short": "200 closes / ~95d",
        "bot_d_station_lock": "30 resolved paper fills or 14d",
        "bot_f_momentum_paper": "100 closed paper entries",
        "wallet_tag_feature_shadow": ">=200 settled/scored BUYs + positive CI",
        "wallet_tag_elite_cap_paper": ">=100 closed capped entries + ex-largest ROI > 5%",
        "wc_negrisk_basket_paper": "tournament window starts 2026-06-11",
        "wallet_observer": "6 days (2026-05-15)",
        "bot_h_maker_v2": "~24h to OQ-100 trip",
        "bot_h_maker_v2_quote_paper": "100 replayable trips + target-cell pass",
        # ADR-128 first gate: n=50 per cell at observed ~1.45 + 1.68
        # entries/day → roughly 12-14 days from deployment.
        "bot_i_persistence": "~12-14 days to first gate (n=50/cell)",
        "bot_i_persistence_live": "n>=100 closed live entries or 2026-06-13 kill",
        "bot_j_nr_wallet": ">=100 closed near-res wallet entries",
        "bot_k_sports_taker": ">=100 resolved sports entries / ~60-90d",
    }
    return horizons.get(bot_id)


def _live_accounting_metrics(bot_id: str) -> dict[str, Any]:
    """Per-bot live accounting surface for the operator cockpit.

    Realised P&L comes from the portfolio ledger, including normal FIFO SELL
    closes and `portfolio.redeem` events. Exposure is kept separate: open
    position cost basis plus reserved live BUY notional. This prevents open
    maker cost from appearing as realised loss.
    """
    try:
        from core.portfolio import Portfolio

        sessions = get_session_factory()
        realised = Portfolio(sessions).get_realised_pnl(bot_id)
        orders = _order_metrics(bot_id)
        trades = _trade_metrics(bot_id)
        with sessions() as session:
            position_rows = (
                session.query(
                    Position.status,
                    Position.cost_basis_usd,
                )
                .filter(Position.bot_id == bot_id)
                .all()
            )
            redeem_rows = (
                session.query(Event.payload)
                .filter(
                    Event.bot_id == bot_id,
                    Event.event_type == "portfolio.redeem",
                )
                .all()
            )
        status_counts: dict[str, int] = defaultdict(int)
        status_costs: dict[str, Decimal] = defaultdict(Decimal)
        for status, cost in position_rows:
            status_key = str(status or "UNKNOWN")
            status_counts[status_key] += 1
            status_costs[status_key] += Decimal(str(cost or 0))

        redeemed_cost = Decimal("0")
        redeemed_payout = Decimal("0")
        for (payload_raw,) in redeem_rows:
            try:
                payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            redeemed_cost += Decimal(str(payload.get("cost_basis") or 0))
            redeemed_payout += Decimal(str(payload.get("usdc_received") or 0))

        open_position_cost = status_costs.get("OPEN", Decimal("0"))
        open_order_notional = Decimal(str(orders.get("reserved_notional_usd") or 0))
        exposure = open_position_cost + open_order_notional
        realised_cost = redeemed_cost + Decimal(str(trades.get("closed_entry_cost_usd") or 0))
        realised_float = float(realised)
        redeemed_cost_float = float(redeemed_cost)
        realised_cost_float = float(realised_cost)
        return {
            "realised_pnl_usd": round(realised_float, 2),
            "roi_pct": (
                round((realised_float / realised_cost_float) * 100, 2)
                if realised_cost_float > 0
                else None
            ),
            "realised_cost_usd": round(realised_cost_float, 2),
            "redeemed_cost_usd": round(redeemed_cost_float, 2),
            "redeemed_payout_usd": round(float(redeemed_payout), 2),
            "redeemed_positions": int(status_counts.get("REDEEMED", 0)),
            "closed_positions": int(
                status_counts.get("CLOSED", 0)
                + status_counts.get("CLOSED_EXTERNAL_SYNC", 0)
                + status_counts.get("REDEEMED", 0)
            ),
            "open_positions": int(status_counts.get("OPEN", 0)),
            "open_position_cost_usd": round(float(open_position_cost), 2),
            "open_order_notional_usd": round(float(open_order_notional), 2),
            "exposure_usd": round(float(exposure), 2),
            "orders": int(orders.get("total_orders") or 0),
            "fills": int(trades.get("filled_trades_count") or 0),
            "last_fill_at": (
                trades.get("recent_trades", [{}])[0].get("filled_at")
                if trades.get("recent_trades")
                else None
            ),
        }
    except Exception as exc:
        return {
            "accounting_error": str(exc)[:200],
            "realised_pnl_usd": 0.0,
            "roi_pct": None,
            "realised_cost_usd": 0.0,
            "redeemed_cost_usd": 0.0,
            "redeemed_payout_usd": 0.0,
            "redeemed_positions": 0,
            "closed_positions": 0,
            "open_positions": 0,
            "open_position_cost_usd": 0.0,
            "open_order_notional_usd": 0.0,
            "exposure_usd": 0.0,
            "orders": 0,
            "fills": 0,
            "last_fill_at": None,
        }


def _inventory_row_is_visible(row: dict[str, Any]) -> bool:
    """Return whether a row belongs on the operator dashboard.

    Archived, parked, paused, unknown, and fully inactive rows stay out of
    the cockpit. Halted trading lanes are hidden too. Recorder lanes are
    evaluated by service freshness rather than legacy halt rows: e.g. the
    Bot E recorder has a stale trading-bot halt from 2026-05-05 that does
    not apply to the recorder service.
    """
    group = row.get("group")
    if group not in {"Live", "Paper", "Recorder"}:
        return False
    if group == "Recorder":
        service_text = str(row.get("service") or "")
        return "active" in service_text.lower()
    if row.get("halted"):
        return False
    if row.get("registry_status") == "paused":
        return any(
            float(row.get(key) or 0) != 0
            for key in (
                "realised_pnl_usd",
                "exposure_usd",
                "orders",
                "fills",
                "open_positions",
            )
        )
    return str(row.get("status") or "") in {
        "active",
        "timer:active",
        "active_policy_conflict",
        "degraded",
    }


def _bot_inventory(
    *,
    services: dict[str, str],
    halted_ids: set[str],
    vps_node: dict[str, Any],
) -> list[dict[str, Any]]:
    """Operator-facing inventory for active registered bot-like lanes.

    `fleet_bots` intentionally stays small for backwards-compatible headline
    trading cards. This table is the current truth surface: active live probes,
    active paper lanes, and active recorder-only services. Archived/inactive
    evidence belongs in reports, not the default dashboard.
    """
    vps_bot_g = vps_node.get("bot_g") if isinstance(vps_node.get("bot_g"), dict) else {}
    d_spike = vps_node.get("bot_d_spike") if isinstance(vps_node.get("bot_d_spike"), dict) else {}
    d_spike_short = (
        vps_node.get("bot_d_spike_short")
        if isinstance(vps_node.get("bot_d_spike_short"), dict)
        else {}
    )
    bot_h = (
        vps_node.get("bot_h_maker_v2") if isinstance(vps_node.get("bot_h_maker_v2"), dict) else {}
    )
    local_bot_h = _local_bot_h_maker_v2_summary()
    if local_bot_h.get("exists"):
        bot_h = local_bot_h
    bot_h_quote = (
        vps_node.get("bot_h_quote_paper")
        if isinstance(vps_node.get("bot_h_quote_paper"), dict)
        else {}
    )
    local_bot_h_quote = _local_bot_h_quote_paper_summary()
    if local_bot_h_quote.get("exists"):
        bot_h_quote = local_bot_h_quote
    wallet = (
        vps_node.get("wallet_observer") if isinstance(vps_node.get("wallet_observer"), dict) else {}
    )
    local_wallet = _local_wallet_observer_summary()
    if local_wallet.get("exists"):
        wallet = local_wallet

    rows: list[dict[str, Any]] = []
    for bot in REGISTRY:
        service_names = tuple(bot.dashboard_services)
        if not service_names and bot.systemd_unit:
            service_names = (bot.systemd_unit.removesuffix(".service"),)
        registry_status = str(bot.status)
        group = _inventory_group(registry_status, bot.bot_id)
        spec = {
            "bot_id": bot.bot_id,
            "label": bot.display_name or bot.bot_id,
            "services": service_names,
            "registry_status": registry_status,
            "epoch_id": BOT_D_PAPER_EPOCH_ID if bot.bot_id == "bot_d" else FLEET_EPOCH_ID,
            "epoch_start": BOT_D_PAPER_EPOCH_START if bot.bot_id == "bot_d" else FLEET_EPOCH_START,
        }
        simple = _bot_simple_summary(spec, services=services, halted_ids=halted_ids)
        if bot.bot_id in (vps_bot_g.get("bot_ids") or []):
            _apply_vps_bot_g_simple_metrics(simple, vps_bot_g)

        row = {
            "bot_id": bot.bot_id,
            "label": bot.display_name or bot.bot_id,
            "group": group,
            "mode": _inventory_mode(registry_status, group),
            "registry_status": registry_status,
            "status": simple.get("status", "unknown"),
            "active": bool(simple.get("active")),
            "halted": bool(simple.get("halted")),
            "service": " / ".join(
                f"{name}:{state}" for name, state in (simple.get("services") or {}).items()
            )
            or "no service",
            "pnl_usd": simple.get("pnl_usd"),
            # Realised P&L is the FIFO-matched closed-position number for
            # trading lanes (paper or live). Shadow lanes overwrite this
            # below from their own DB summaries. `pnl_kind` documents the
            # source so the renderer can show "synthetic" tags.
            "realised_pnl_usd": simple.get("realised_pnl_usd")
            if simple.get("realised_pnl_usd") is not None
            else simple.get("pnl_usd"),
            "pnl_kind": (
                "realised_clob" if registry_status in {"live", "paused"} else "realised_paper"
            ),
            # Operator-facing exposure = open-position cost basis +
            # reserved-order notional. Shadow lanes overwrite below.
            "exposure_usd": round(
                float(simple.get("open_position_cost_usd") or 0)
                + float(simple.get("paper_amount_usd") or 0),
                2,
            ),
            "orders": simple.get("trades", 0),
            "fills": simple.get("fills", 0),
            "open_orders": simple.get("open_orders", 0),
            "open_positions": simple.get("open_positions", 0),
            "headline": bot.description,
            "data_source": simple.get("data_source", "the bot container"),
            "time_to_decision": _inventory_time_to_decision(bot.bot_id),
        }

        if registry_status in {"live", "paused"}:
            live_accounting = _live_accounting_metrics(bot.bot_id)
            pnl_note = "realised live P&L; exposure shown separately"
            if registry_status == "paused":
                pnl_note = (
                    "paused live lane; realised live P&L retained for "
                    "postmortem; exposure shown separately"
                )
            row.update(
                {
                    "pnl_usd": live_accounting["realised_pnl_usd"],
                    "realised_pnl_usd": live_accounting["realised_pnl_usd"],
                    "roi_pct": live_accounting["roi_pct"],
                    "pnl_kind": "realised_clob",
                    "realised_cost_usd": live_accounting["realised_cost_usd"],
                    "redeemed_cost_usd": live_accounting["redeemed_cost_usd"],
                    "redeemed_payout_usd": live_accounting["redeemed_payout_usd"],
                    "redeemed_positions": live_accounting["redeemed_positions"],
                    "closed_positions": live_accounting["closed_positions"],
                    "exposure_usd": live_accounting["exposure_usd"],
                    "open_position_cost_usd": live_accounting["open_position_cost_usd"],
                    "open_order_notional_usd": live_accounting["open_order_notional_usd"],
                    "open_positions": live_accounting["open_positions"],
                    "orders": live_accounting["orders"],
                    "fills": live_accounting["fills"],
                    "last_fill_at": live_accounting["last_fill_at"],
                    "pnl_note": pnl_note,
                    **(
                        {"accounting_error": live_accounting["accounting_error"]}
                        if live_accounting.get("accounting_error")
                        else {}
                    ),
                }
            )
            # P0 freshness for stale live rows (e.g. bot_g_prime_live last_fill 2026-05-10)
            # while still marked live in registry. Now uses the reusable helper (phase 4).
            freshness = _freshness_for_live_row(
                live_accounting.get("last_fill_at"), registry_status
            )
            row["freshness"] = freshness
            if freshness in ("stale_7d", "stale_30d"):
                age = "7d+" if freshness == "stale_7d" else "30d+"
                row["pnl_note"] = (
                    (row.get("pnl_note") or "")
                    + f" (WARNING: last fill {age} old — investigate blocked data collection / OQ-123)"
                )

            # Reconciliation surface (OQ-123 phase 2) — local DB only until backfill table is written.
            # Explicit labels prevent mistaking ledger for whole-wallet truth.
            row.update(
                {
                    "reconciliation_status": "local_only",
                    "wallet_realised_pnl_usd": None,
                    "unresolved_exposure_usd": round(
                        float(live_accounting.get("exposure_usd") or 0), 2
                    ),
                    "reconciliation_note": "local bot-ledger; run wallet_data_api_backfill.py for wallet-reconciled view",
                }
            )

        if bot.bot_id == "bot_d_spike" and d_spike:
            orders = d_spike.get("orders") if isinstance(d_spike.get("orders"), dict) else {}
            trades = d_spike.get("trades") if isinstance(d_spike.get("trades"), dict) else {}
            row.update(
                {
                    "orders": int(orders.get("total_orders") or 0),
                    "fills": int(trades.get("filled_trades_count") or 0),
                    "open_positions": int(d_spike.get("open_positions") or 0),
                    "pnl_usd": round(float(trades.get("realised_pnl_usd") or 0), 2),
                    "headline": "Strategy E, 6h-12h weather cheap-YES, tiny live probe",
                    "data_source": "vps",
                }
            )
        elif bot.bot_id == "bot_d_spike_short" and d_spike_short:
            orders = (
                d_spike_short.get("orders") if isinstance(d_spike_short.get("orders"), dict) else {}
            )
            trades = (
                d_spike_short.get("trades") if isinstance(d_spike_short.get("trades"), dict) else {}
            )
            row.update(
                {
                    "orders": int(orders.get("total_orders") or 0),
                    "fills": int(trades.get("filled_trades_count") or 0),
                    "open_positions": int(d_spike_short.get("open_positions") or 0),
                    "pnl_usd": round(float(trades.get("realised_pnl_usd") or 0), 2),
                    "headline": "Strategy E2, 0h-6h weather cheap-YES, paper-only",
                    "data_source": "vps",
                }
            )
        elif bot.bot_id == "bot_d_station_lock":
            station_lock = _bot_d_station_lock_summary(hours=24)
            pnl = round(float(station_lock.get("realised_pnl_usd") or 0), 2)
            row.update(
                {
                    "orders": int(station_lock.get("entries") or 0),
                    "fills": int(station_lock.get("fills") or 0),
                    "open_positions": int(station_lock.get("open_fills") or 0),
                    "pnl_usd": pnl,
                    "realised_pnl_usd": pnl,
                    "pnl_kind": "synthetic_shadow",
                    "exposure_usd": round(float(station_lock.get("open_notional_usd") or 0), 2),
                    "headline": (
                        f"{int(station_lock.get('candidates') or 0)} candidates/24h; "
                        f"{int(station_lock.get('resolutions') or 0)} resolved; "
                        f"{int(station_lock.get('skips') or 0)} skips"
                    ),
                    "data_source": "the bot container",
                }
            )
        elif bot.bot_id == "bot_h_maker_v2" and bot_h:
            row.update(
                {
                    "orders": int((bot_h.get("counts") or {}).get("markets") or 0),
                    "fills": int(bot_h.get("events_24h_total") or 0),
                    "open_positions": int(bot_h.get("active_markets") or 0),
                    "pnl_usd": None,
                    "headline": (
                        f"{int(bot_h.get('events_24h_total') or 0)} events/24h; "
                        f"{int(bot_h.get('active_markets') or 0)} active markets; recorder-only"
                    ),
                    "data_source": "the bot container" if local_bot_h.get("exists") else "vps",
                }
            )
        elif bot.bot_id == "bot_h_maker_v2_quote_paper" and bot_h_quote:
            services_block = (
                vps_node.get("services") if isinstance(vps_node.get("services"), dict) else {}
            )
            if local_bot_h_quote.get("exists"):
                effective_state = services.get("polymarket-bot-h-maker-v2-quote-paper", "unknown")
                service_name = "polymarket-bot-h-maker-v2-quote-paper"
                data_source = "the bot container"
            else:
                svc = services_block.get("polymarket-bot-h-maker-v2-quote-paper-vps.service") or {}
                timer = services_block.get("polymarket-bot-h-maker-v2-quote-paper-vps.timer") or {}
                svc_state = svc.get("active") if isinstance(svc, dict) else None
                timer_state = timer.get("active") if isinstance(timer, dict) else None
                effective_state = (
                    "active"
                    if timer_state == "active" or svc_state == "active"
                    else (svc_state or "unknown")
                )
                service_name = "polymarket-bot-h-maker-v2-quote-paper-vps"
                data_source = "vps"
            roi_pct = float(bot_h_quote.get("roi") or 0) * 100
            row.update(
                {
                    "status": effective_state,
                    "active": effective_state in {"active", "timer:active"},
                    "service": f"{service_name}:{effective_state}",
                    "orders": int(bot_h_quote.get("quotes") or 0),
                    "fills": int(bot_h_quote.get("fills") or 0),
                    "open_positions": int(bot_h_quote.get("active_quotes") or 0),
                    "pnl_usd": round(float(bot_h_quote.get("net_pnl_usd") or 0), 2),
                    "headline": (
                        f"{int(bot_h_quote.get('active_quotes') or 0)} active quotes; "
                        f"{int(bot_h_quote.get('settled_fills') or 0)} settled fills; ROI {roi_pct:.2f}%"
                    ),
                    "data_source": data_source,
                }
            )
        elif bot.bot_id == "wallet_observer" and wallet:
            headline = wallet.get("headline") if isinstance(wallet.get("headline"), dict) else {}
            row.update(
                {
                    "orders": int(headline.get("total_fills") or 0),
                    "fills": int(headline.get("fills_24h") or 0),
                    "open_positions": int(headline.get("distinct_wallets_24h") or 0),
                    "pnl_usd": None,
                    "headline": (
                        f"{int(headline.get('fills_24h') or 0)} fills/24h; "
                        f"{int(headline.get('distinct_wallets_24h') or 0)} wallets; passive observer"
                    ),
                    "data_source": "the bot container" if local_wallet.get("exists") else "vps",
                }
            )
        elif bot.bot_id == "bot_f_momentum_paper":
            momentum = _bot_f_momentum_paper_summary()
            if momentum:
                closed = int(momentum.get("closed") or 0)
                roi_pct = float(momentum.get("post_fee_roi") or 0) * 100
                pnl = round(float(momentum.get("pnl_usd") or 0), 2)
                row.update(
                    {
                        "orders": int(momentum.get("n_entries") or 0),
                        "fills": closed,
                        "open_positions": int(momentum.get("open_entries") or 0),
                        "pnl_usd": pnl,
                        "realised_pnl_usd": pnl,
                        "pnl_kind": "synthetic_shadow",
                        "exposure_usd": round(float(momentum.get("open_cost_usd") or 0), 2),
                        "headline": f"BUY-only 1800s PASS cells; {closed}/100 closed; ROI {roi_pct:.2f}%",
                        "data_source": "the bot container",
                    }
                )
        elif bot.bot_id == "wallet_tag_feature_shadow":
            shadow = _wallet_tag_feature_shadow_summary()
            if shadow:
                roi_pct = float(shadow.get("post_fee_roi") or 0) * 100
                pnl = round(float(shadow.get("pnl_usd") or 0), 2)
                row.update(
                    {
                        "orders": int(shadow.get("n_entries") or 0),
                        "fills": int(shadow.get("closed") or 0),
                        "open_positions": int(shadow.get("open_entries") or 0),
                        "pnl_usd": pnl,
                        # Shadow lane mirrors watched-wallet stake sizes
                        # (entries up to $54k!), so the dollar P&L is NOT
                        # operator capital — surface it as synthetic.
                        "realised_pnl_usd": pnl,
                        "pnl_kind": "synthetic_shadow",
                        "exposure_usd": round(float(shadow.get("open_cost_usd") or 0), 2),
                        "headline": (
                            f"{int(shadow.get('closed') or 0)} settled/scored BUYs; "
                            f"{int(shadow.get('wins') or 0)} wins; ROI {roi_pct:.2f}%"
                        ),
                        "data_source": "the bot container",
                    }
                )
        elif bot.bot_id == "wallet_tag_elite_cap_paper":
            shadow = _wallet_tag_elite_cap_paper_summary()
            if shadow:
                roi_pct = float(shadow.get("post_fee_roi") or 0) * 100
                pnl = round(float(shadow.get("pnl_usd") or 0), 2)
                row.update(
                    {
                        "orders": int(shadow.get("n_entries") or 0),
                        "fills": int(shadow.get("closed") or 0),
                        "open_positions": int(shadow.get("open_entries") or 0),
                        "pnl_usd": pnl,
                        "realised_pnl_usd": pnl,
                        "pnl_kind": "capped_synthetic_shadow",
                        "exposure_usd": round(float(shadow.get("open_cost_usd") or 0), 2),
                        "headline": (
                            f"elite capped wallet copy-test; "
                            f"{int(shadow.get('closed') or 0)} closed; "
                            f"ROI {roi_pct:.2f}%"
                        ),
                        "data_source": "the bot container",
                    }
                )
        elif bot.bot_id == "wc_negrisk_basket_paper":
            wc = _wc_negrisk_basket_paper_summary()
            if wc:
                best_edge_pct = float(wc.get("best_net_edge") or 0) * 100
                row.update(
                    {
                        "orders": int(wc.get("n_baskets") or 0),
                        "fills": 0,
                        "open_positions": int(wc.get("open_baskets") or 0),
                        "pnl_usd": None,
                        "realised_pnl_usd": None,  # settlement-pending; no realised yet
                        "pnl_kind": "settlement_pending",
                        "exposure_usd": round(float(wc.get("open_cost_usd") or 0), 2),
                        "headline": (
                            f"{int(wc.get('observations') or 0)} scans; "
                            f"best fee-stressed edge {best_edge_pct:+.2f}%; settlement pending"
                        ),
                        "data_source": "the bot container",
                    }
                )
        elif bot.bot_id == "bot_i_persistence":
            persistence = _persistence_paper_summary()
            if persistence:
                per_cell = persistence.get("per_cell_n") or {}
                cell_a = int(per_cell.get("A_borderline_5m_15m") or 0)
                cell_b = int(per_cell.get("B_tail_15m") or 0)
                n_entries = int(persistence.get("n_entries") or 0)
                wins = int(persistence.get("wins") or 0)
                roi_pct = float(persistence.get("post_fee_roi") or 0) * 100
                # Persistence stores ask_high/pnl_usd/fee_usd per entry
                # in persistence_paper.db. Net = SUM(pnl) - SUM(fees).
                pnl_net = round(float(persistence.get("pnl_usd_net") or 0), 2)
                row.update(
                    {
                        "orders": n_entries,
                        "fills": wins,
                        "open_positions": 0,
                        "pnl_usd": pnl_net if persistence.get("pnl_usd_net") is not None else None,
                        "realised_pnl_usd": pnl_net
                        if persistence.get("pnl_usd_net") is not None
                        else None,
                        "pnl_kind": "synthetic_shadow",
                        "exposure_usd": 0,  # daily replay; no carrying exposure
                        "headline": (
                            f"Cell A {cell_a}/50, Cell B {cell_b}/50; "
                            f"wins {wins}/{n_entries}; ROI {roi_pct:.2f}%"
                        ),
                        "data_source": "the bot container",
                    }
                )
        elif bot.bot_id == "bot_e":
            tile = _overview_bot_e_tile()
            row.update(
                {
                    "orders": int(tile.get("markets") or 0),
                    "fills": int(tile.get("pm_events") or 0),
                    "open_positions": int(tile.get("n_active_subscriptions") or 0),
                    "pnl_usd": None,
                    "headline": (
                        f"{int(tile.get('pm_events') or 0)} PM events; "
                        f"{int(tile.get('cex_trades') or 0)} CEX trades; shared recorder"
                    ),
                }
            )

        if _inventory_row_is_visible(row):
            rows.append(row)

    order = {"Live": 0, "Paper": 1, "Recorder": 2, "Other": 6}
    return sorted(rows, key=lambda row: (order.get(str(row["group"]), 99), str(row["label"])))


def _paper_pnl(bot_id: str, *, since: datetime | None = None) -> dict[str, Any]:
    """Compute theoretical paper P&L from open orders for a bot.

    Since paper orders never fill on the CLOB, we estimate:
    - capital_deployed: sum(price × size) — what we'd pay if filled
    - max_profit: sum(size × (1 − price)) — if every bet wins ($1 payout per share)
    - max_loss: capital_deployed — if every bet loses (shares go to $0)
    - expected_pnl: sum(edge × notional) — probability-weighted expected value
      (requires matching orders to decisions by condition_id)
    """
    try:
        with _db() as conn:
            params: list[Any] = [bot_id]
            since_clause = ""
            if since is not None:
                since_clause = " AND placed_at >= ?"
                params.append(_sqlite_dt(since))
            rows = conn.execute(
                "SELECT order_id, condition_id, price, size, status, placed_at "
                "FROM orders WHERE bot_id=? AND status IN ('PAPER_OPEN', 'OPEN')"
                f"{since_clause}",
                params,
            ).fetchall()
        if not rows:
            return {
                "capital_deployed": 0.0,
                "max_profit": 0.0,
                "max_loss": 0.0,
                "open_count": 0,
                "avg_entry": 0.0,
            }
        capital = sum(float(r["price"]) * float(r["size"]) for r in rows)
        max_profit = sum(float(r["size"]) * (1.0 - float(r["price"])) for r in rows)
        avg_entry = capital / sum(float(r["size"]) for r in rows) if rows else 0
        return {
            "capital_deployed": round(capital, 2),
            "max_profit": round(max_profit, 2),
            "max_loss": round(capital, 2),
            "open_count": len(rows),
            "avg_entry": round(avg_entry, 4),
            "best_case_return_pct": round((max_profit / capital) * 100, 1) if capital > 0 else 0,
        }
    except Exception:
        return {
            "capital_deployed": 0.0,
            "max_profit": 0.0,
            "max_loss": 0.0,
            "open_count": 0,
            "avg_entry": 0.0,
        }


def _live_probe_open_orders_pnl(bot_id: str, *, since: datetime | None = None) -> dict[str, Any]:
    """Compute open-order notional for live probe rows without paper labeling."""
    statuses = ("OPEN", "PARTIAL", "live", "MATCHED")
    try:
        with _db() as conn:
            params: list[Any] = [bot_id, *statuses]
            since_clause = ""
            if since is not None:
                since_clause = " AND placed_at >= ?"
                params.append(_sqlite_dt(since))
            rows = conn.execute(
                "SELECT order_id, condition_id, price, size, status, placed_at "
                "FROM orders WHERE bot_id=? AND status IN (?, ?, ?, ?)"
                f"{since_clause}",
                params,
            ).fetchall()
        if not rows:
            return {
                "capital_deployed": 0.0,
                "max_profit": 0.0,
                "max_loss": 0.0,
                "open_count": 0,
                "avg_entry": 0.0,
            }
        capital = sum(float(r["price"]) * float(r["size"]) for r in rows)
        max_profit = sum(float(r["size"]) * (1.0 - float(r["price"])) for r in rows)
        avg_entry = capital / sum(float(r["size"]) for r in rows) if rows else 0
        return {
            "capital_deployed": round(capital, 2),
            "max_profit": round(max_profit, 2),
            "max_loss": round(capital, 2),
            "open_count": len(rows),
            "avg_entry": round(avg_entry, 4),
            "best_case_return_pct": round((max_profit / capital) * 100, 1) if capital > 0 else 0,
            "statuses": list(statuses),
        }
    except Exception:
        return {
            "capital_deployed": 0.0,
            "max_profit": 0.0,
            "max_loss": 0.0,
            "open_count": 0,
            "avg_entry": 0.0,
        }


def _bot_d_live_probe_caps(bot_id: str = "bot_d_live_probe") -> dict[str, Any]:
    """Return live-probe cap usage from the trade/order ledger.

    Important: the dollar values here are **cost basis** drawn from the
    local ``positions`` ledger, NOT the wallet's current value. The local
    ledger is kept truthful to the wallet by the hourly wallet-position
    reconciler (``Portfolio.reconcile_live_positions_against_wallet``);
    stale rows the wallet no longer holds are marked
    ``status='CLOSED_EXTERNAL_SYNC'`` and excluded from the OPEN count
    below. If the operator wants live wallet value, they must use the
    wallet UI or query Polymarket /positions directly — that's outside
    the cap envelope which is sized in cost-basis terms.
    """
    open_statuses = ("OPEN", "PARTIAL", "live", "MATCHED")
    if bot_id == "bot_d_maker_live_probe":
        unit_env = "polymarket-bot-d-maker-live.service"
        daily_limit_env = "BOT_D_MAKER_MAX_DAILY_GROSS_USD"
        exposure_limit_env = "BOT_D_MAKER_MAX_OPEN_EXPOSURE_USD"
        max_positions_env = "BOT_D_MAKER_MAX_CONCURRENT_POSITIONS"
        default_daily = "100"
        default_exposure = "100"
        default_positions = "20"
    else:
        unit_env = "polymarket-bot-d-live.service"
        daily_limit_env = "BOT_D_LIVE_MAX_DAILY_GROSS_NOTIONAL_USD"
        exposure_limit_env = "BOT_D_LIVE_MAX_OPEN_EXPOSURE_USD"
        max_positions_env = "BOT_D_LIVE_MAX_CONCURRENT_POSITIONS"
        default_daily = "100"
        default_exposure = "150"
        default_positions = "50"
    daily_limit = float(_env_from_unit(unit_env, daily_limit_env, default_daily))
    exposure_limit = float(_env_from_unit(unit_env, exposure_limit_env, default_exposure))
    max_positions = int(_env_from_unit(unit_env, max_positions_env, default_positions))
    try:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        with _db() as conn:
            daily_rows = conn.execute(
                "SELECT side, price, size FROM orders WHERE bot_id=? AND placed_at >= ?",
                (bot_id, _sqlite_dt(today)),
            ).fetchall()
            position_rows = conn.execute(
                "SELECT cost_basis_usd FROM positions WHERE bot_id=? AND status='OPEN'",
                (bot_id,),
            ).fetchall()
            open_order_rows = conn.execute(
                "SELECT side, price, size FROM orders WHERE bot_id=? AND status IN (?, ?, ?, ?)",
                (bot_id, *open_statuses),
            ).fetchall()
        daily_buy = sum(
            float(r["price"] or 0) * float(r["size"] or 0) for r in daily_rows if r["side"] == "BUY"
        )
        daily_sell = sum(
            float(r["price"] or 0) * float(r["size"] or 0)
            for r in daily_rows
            if r["side"] == "SELL"
        )
        daily_gross = daily_buy + daily_sell
        open_cost = sum(float(r["cost_basis_usd"] or 0) for r in position_rows)
        resting_buy = sum(
            float(r["price"] or 0) * float(r["size"] or 0)
            for r in open_order_rows
            if r["side"] == "BUY"
        )
        exposure = open_cost + resting_buy
        return {
            "daily_gross_usd": round(daily_gross, 2),
            "daily_buy_usd": round(daily_buy, 2),
            "daily_sell_usd": round(daily_sell, 2),
            "daily_limit_usd": round(daily_limit, 2),
            "daily_remaining_usd": round(max(0.0, daily_limit - daily_gross), 2),
            "daily_used_pct": round((daily_gross / daily_limit) * 100, 1)
            if daily_limit > 0
            else 0.0,
            "open_positions": len(position_rows),
            "max_open_positions": max_positions,
            "open_positions_remaining": max(0, max_positions - len(position_rows)),
            "open_cost_usd": round(open_cost, 2),
            "resting_buy_usd": round(resting_buy, 2),
            "filled_plus_resting_exposure_usd": round(exposure, 2),
            "open_exposure_limit_usd": round(exposure_limit, 2),
            "open_exposure_remaining_usd": round(max(0.0, exposure_limit - exposure), 2),
            "open_exposure_used_pct": round((exposure / exposure_limit) * 100, 1)
            if exposure_limit > 0
            else 0.0,
            # Self-documenting contract for the dashboard JS + future
            # operators: dollar values are cost basis, NOT current wallet
            # value. Reconciler keeps the OPEN row set consistent with
            # the wallet's actual holdings (see Portfolio.reconcile_live_
            # positions_against_wallet, hourly cadence inside Bot D's
            # live run_loop).
            "basis": "cost_basis_local_ledger",
            "reconciler": {
                "name": "reconcile_live_positions_against_wallet",
                "event_type": "bot_d.live_position_reconciled",
                "interval_s": int(os.environ.get("BOT_D_WALLET_RESOLVE_INTERVAL_S", "3600")),
                "stale_row_status": "CLOSED_EXTERNAL_SYNC",
            },
        }
    except Exception as exc:
        return {
            "error": str(exc)[:200],
            "daily_gross_usd": 0.0,
            "daily_limit_usd": round(daily_limit, 2),
            "daily_remaining_usd": round(daily_limit, 2),
            "open_positions": 0,
            "max_open_positions": max_positions,
            "filled_plus_resting_exposure_usd": 0.0,
            "open_exposure_limit_usd": round(exposure_limit, 2),
        }


def _is_active(unit: str) -> str:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return result.stdout.strip() or result.stderr.strip() or "unknown"
    except Exception as exc:  # pragma: no cover
        return f"error: {exc}"


def service_states() -> dict[str, str]:
    """Return {unit_name: state} for all monitored services.

    For timer-driven services (see TIMER_SERVICES) we report the TIMER's
    state under the service name — an active timer means the oneshot is
    scheduled and will fire on cadence. This avoids treating "oneshot between
    runs" as degraded.
    """
    out: dict[str, str] = {}
    for service in SERVICES:
        out[service] = _is_active(service)
    for service, timer in TIMER_SERVICES.items():
        state = _is_active(timer)
        # Prefix with "timer:" so the UI can render intent clearly.
        out[service] = f"timer:{state}"
    vps = _load_vps_node_status()
    if vps.get("ok"):
        for service, state in (vps.get("services") or {}).items():
            if service.removesuffix(".service") in out and state.get("active") == "active":
                out[service.removesuffix(".service")] = "vps:active"
    return out


def portfolio_pnl() -> dict[str, Any]:
    try:
        from core.portfolio import Portfolio
    except Exception as exc:
        return {"error": f"portfolio import: {exc}"}

    portfolio = Portfolio()
    out: dict[str, Any] = {"bots": {}, "project": {}}
    total_realised = Decimal("0")
    total_unrealised = Decimal("0")
    total_initial = Decimal("0")
    total_exposure = Decimal("0")

    # 2026-04-18: pull latest marks for every open-position token across the
    # fleet once, then pass the shared dict into each get_unrealised_pnl
    # call. Without this, unrealised was always 0 because the function
    # returns 0 when no mark is supplied — the dashboard displayed zero
    # unrealised P&L even when Bot E had +$1,810 from reconstructed
    # positions.
    _all_open_token_ids: set[str] = set()
    try:
        with _db() as conn:
            for r in conn.execute(
                "SELECT DISTINCT token_id FROM positions WHERE status='OPEN'"
            ).fetchall():
                tid = r["token_id"]
                if tid:
                    _all_open_token_ids.add(str(tid))
    except Exception:
        pass
    _marks = _latest_marks(_all_open_token_ids)
    from decimal import Decimal as _Dec

    _marks_decimal = {k: _Dec(str(v)) for k, v in _marks.items()}

    for bot_id, base in initial_usd().items():
        try:
            realised = portfolio.get_realised_pnl(bot_id)
            unrealised = portfolio.get_unrealised_pnl(bot_id, _marks_decimal)
            exposure = portfolio.get_total_exposure(bot_id)
        except Exception as exc:
            out["bots"][bot_id] = {"error": str(exc)[:200]}
            continue
        equity = base + realised + unrealised
        out["bots"][bot_id] = {
            "initial_usd": _fmt_decimal(base),
            "realised_usd": _fmt_decimal(realised),
            "unrealised_usd": _fmt_decimal(unrealised),
            "equity_usd": _fmt_decimal(equity),
            "exposure_usd": _fmt_decimal(exposure),
            "return_pct": _fmt_decimal(((equity - base) / base) * Decimal("100"))
            if base
            else "0.00",
        }
        total_realised += realised
        total_unrealised += unrealised
        total_initial += base
        total_exposure += exposure
    equity = total_initial + total_realised + total_unrealised
    out["project"] = {
        "initial_usd": _fmt_decimal(total_initial),
        "realised_usd": _fmt_decimal(total_realised),
        "unrealised_usd": _fmt_decimal(total_unrealised),
        "equity_usd": _fmt_decimal(equity),
        "exposure_usd": _fmt_decimal(total_exposure),
        "return_pct": _fmt_decimal(((equity - total_initial) / total_initial) * Decimal("100"))
        if total_initial
        else "0.00",
    }
    return out


def _fetch_balances_uncached() -> dict[str, Any]:
    try:
        from web3 import Web3

        web3 = Web3(Web3.HTTPProvider(rpc_url(), request_kwargs={"timeout": 8}))
        addr = Web3.to_checksum_address(wallet_address())
        pol_wei = web3.eth.get_balance(addr)
        contract = web3.eth.contract(
            address=Web3.to_checksum_address(USDCE_ADDRESS),
            abi=[
                {
                    "inputs": [{"name": "a", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function",
                }
            ],
        )
        usdce_raw = contract.functions.balanceOf(addr).call()
        return {
            "pol": f"{pol_wei / 10**18:.4f}",
            "usdce": f"{usdce_raw / 10**6:.2f}",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:  # pragma: no cover
        return {"error": str(exc)[:200]}


def balances() -> dict[str, Any]:
    now = time.time()
    with _balance_lock:
        if _balance_cache["value"] is not None and now - _balance_cache["ts"] < 60:
            return _balance_cache["value"]
        value = _fetch_balances_uncached()
        _balance_cache["ts"] = now
        _balance_cache["value"] = value
        return value


def _event_severity_counts() -> dict[str, int]:
    counts = {"info": 0, "warn": 0, "kill": 0}
    cutoff = _sqlite_dt(datetime.now(UTC) - timedelta(days=7))
    try:
        with _db() as conn:
            rows = conn.execute(
                "SELECT severity, COUNT(*) n FROM events WHERE created_at >= ? GROUP BY severity",
                (cutoff,),
            ).fetchall()
    except sqlite3.Error as exc:
        print(f"dashboard.event_severity_counts_unavailable: {exc}")
        return counts
    for row in rows:
        key = row["severity"] if row["severity"] in counts else "info"
        counts[key] += row["n"]
    return counts


def _daily_project_history(days: int = 14) -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    rows: dict[str, dict[str, Decimal]] = {}
    with session_factory() as session:
        snaps = (
            session.query(PnlSnapshot)
            .filter(~PnlSnapshot.bot_id.in_(ARCHIVED_DASHBOARD_BOT_IDS))
            .order_by(PnlSnapshot.snapshot_date.asc(), PnlSnapshot.bot_id.asc())
            .all()
        )
    for snap in snaps:
        key = snap.snapshot_date.isoformat()
        bucket = rows.setdefault(
            key, {"realised": Decimal("0"), "unrealised": Decimal("0"), "exposure": Decimal("0")}
        )
        bucket["realised"] += snap.realised_usd
        bucket["unrealised"] += snap.unrealised_usd
        bucket["exposure"] += snap.open_exposure_usd
    ordered = sorted(rows.items())[-days:]
    baseline = sum(initial_usd().values())
    return [
        {
            "date": day_key,
            "equity_usd": float(baseline + values["realised"] + values["unrealised"]),
            "realised_usd": float(values["realised"]),
            "unrealised_usd": float(values["unrealised"]),
            "exposure_usd": float(values["exposure"]),
        }
        for day_key, values in ordered
    ]


def _bot_pnl_history(bot_id: str, days: int = 14) -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    with session_factory() as session:
        snaps = (
            session.query(PnlSnapshot)
            .filter(PnlSnapshot.bot_id == bot_id)
            .order_by(PnlSnapshot.snapshot_date.asc())
            .all()
        )
    base = initial_usd().get(bot_id, Decimal("0"))
    return [
        {
            "date": snap.snapshot_date.isoformat(),
            "equity_usd": float(base + snap.realised_usd + snap.unrealised_usd),
            "realised_usd": float(snap.realised_usd),
            "unrealised_usd": float(snap.unrealised_usd),
            "drawdown_pct": float(snap.drawdown_pct),
            "exposure_usd": float(snap.open_exposure_usd),
        }
        for snap in snaps[-days:]
    ]


def _orders_for(bot_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    with session_factory() as session:
        query = session.query(Order).order_by(Order.placed_at.desc())
        if bot_id:
            query = query.filter(Order.bot_id == bot_id)
        else:
            query = query.filter(~Order.bot_id.in_(ARCHIVED_DASHBOARD_BOT_IDS))
        rows = query.limit(limit).all()
    return [
        {
            "order_id": row.order_id,
            "bot_id": row.bot_id,
            "condition_id": row.condition_id,
            "token_id": row.token_id,
            "side": row.side,
            "price": _fmt_decimal(row.price, 4) if row.price is not None else None,
            "size": _fmt_decimal(row.size, 2) if row.size is not None else None,
            "status": row.status,
            "placed_at": _iso(row.placed_at),
            "last_updated": _iso(row.last_updated),
        }
        for row in rows
    ]


def _positions_for(bot_id: str | None = None) -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    with session_factory() as session:
        query = (
            session.query(Position)
            .filter(Position.status == "OPEN")
            .order_by(Position.bot_id.asc())
        )
        if bot_id:
            query = query.filter(Position.bot_id == bot_id)
        else:
            query = query.filter(~Position.bot_id.in_(ARCHIVED_DASHBOARD_BOT_IDS))
        rows = query.all()
    return [
        {
            "bot_id": row.bot_id,
            "condition_id": row.condition_id,
            "token_id": row.token_id,
            "side": row.side,
            "size": _fmt_decimal(row.size, 2),
            "avg_price": _fmt_decimal(row.avg_price, 4),
            "cost_basis_usd": _fmt_decimal(row.cost_basis_usd, 2),
            "status": row.status,
            "opened_at": _iso(row.opened_at),
        }
        for row in rows
    ]


def _question_map(condition_ids: set[str]) -> dict[str, str]:
    if not condition_ids:
        return {}
    session_factory = get_session_factory()
    with session_factory() as session:
        rows = session.query(Market).filter(Market.condition_id.in_(sorted(condition_ids))).all()
    return {row.condition_id: row.question for row in rows}


def _latest_marks(token_ids: set[str]) -> dict[str, float]:
    """Fetch the latest mark per token_id.

    Priority order:
      1. `books` table in main.db (Bot A/B watch-list markets)
      2. Bot E recorder DB's `pm_events.last_trade_price` (for Bot E's
         discovered crypto markets which aren't in BookSnapshotter)

    2026-04-18 rewrite:
      - Per-token LIMIT 1 query (was: unbounded fetch for all tokens).
      - Added recorder fallback (was: returned {} for Bot E tokens and
        dashboard displayed $0 unrealised P&L despite +$1,810 in open
        positions).
    """
    if not token_ids:
        return {}
    session_factory = get_session_factory()
    marks: dict[str, float] = {}
    with session_factory() as session:
        for token_id in sorted(token_ids):
            row = (
                session.query(Book)
                .filter(Book.token_id == token_id)
                .order_by(Book.snapshot_at.desc())
                .limit(1)
                .first()
            )
            if row is None:
                continue
            bids = row.bids or []
            asks = row.asks or []
            best_bid = float(bids[0][0]) if bids else None
            best_ask = float(asks[0][0]) if asks else None
            if best_bid is not None and best_ask is not None:
                marks[token_id] = round((best_bid + best_ask) / 2.0, 4)
            elif best_bid is not None:
                marks[token_id] = round(best_bid, 4)
            elif best_ask is not None:
                marks[token_id] = round(best_ask, 4)

    # Recorder fallback for tokens not covered by BookSnapshotter.
    missing = token_ids - set(marks.keys())
    if missing:
        import json as _json
        import sqlite3 as _sq3
        from pathlib import Path as _Path

        rec_path = _Path(bot_e_recorder_db_path())
        if rec_path.exists():
            try:
                conn = _sq3.connect(f"file:{rec_path}?mode=ro", uri=True, timeout=2.0)
                for tok in sorted(missing):
                    row = conn.execute(
                        "SELECT payload_json FROM pm_events "
                        "WHERE event_type='last_trade_price' AND asset_id=? "
                        "ORDER BY received_at_ms DESC LIMIT 1",
                        (tok,),
                    ).fetchone()
                    if not row:
                        continue
                    try:
                        payload = _json.loads(row[0])
                        price = payload.get("price")
                        if price is not None:
                            marks[tok] = round(float(price), 4)
                    except (ValueError, _json.JSONDecodeError, TypeError):
                        continue
                conn.close()
            except Exception:
                pass
    return marks


def _recent_trades(
    limit: int = 20,
    bot_id: str | None = None,
    *,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    with session_factory() as session:
        query = session.query(Trade).order_by(Trade.filled_at.desc())
        if bot_id:
            query = query.filter(Trade.bot_id == bot_id)
        else:
            query = query.filter(~Trade.bot_id.in_(ARCHIVED_DASHBOARD_BOT_IDS))
        if since is not None:
            query = query.filter(Trade.filled_at >= since)
        rows = query.limit(limit).all()
    questions = _question_map({row.condition_id for row in rows})
    order_ids = {row.order_id for row in rows if row.order_id}
    order_status_by_id: dict[str, str] = {}
    if order_ids:
        with session_factory() as session:
            order_status_by_id = {
                order_id: status
                for order_id, status in session.query(Order.order_id, Order.status).filter(
                    Order.order_id.in_(sorted(order_ids))
                )
            }
    return [
        {
            "trade_id": row.trade_id,
            "bot_id": row.bot_id,
            "market": questions.get(row.condition_id, row.condition_id),
            "condition_id": row.condition_id,
            "side": row.side,
            "price": _fmt_decimal(row.price, 4),
            "size": _fmt_decimal(row.size, 2),
            "notional_usd": _fmt_decimal(row.price * row.size, 2),
            # Session 17s 2026-04-20: Bot E SELL trades come through as
            # plain "SELL" (from paper-resolve) but BUY_YES / BUY_NO need
            # treating as cash outflow (-1). Default to -1 (BUY) unless
            # the side is definitely a SELL variant.
            "cash_flow_usd": _fmt_decimal(
                (row.price * row.size)
                * (Decimal("1") if (row.side or "").startswith("SELL") else Decimal("-1")),
                2,
            ),
            "fee_usd": _fmt_decimal(row.fee_usd, 2),
            "filled_at": _iso(row.filled_at),
            "execution_mode": (
                "settlement"
                if (row.trade_id or "").startswith("paper-resolve-")
                else "paper"
                if (row.order_id or "").startswith("paper-")
                or (row.trade_id or "").startswith("paper-")
                or str(order_status_by_id.get(row.order_id or "", "")).startswith("PAPER")
                else "live"
            ),
        }
        for row in rows
    ]


def _trade_metrics(bot_id: str | None = None, *, since: datetime | None = None) -> dict[str, Any]:
    session_factory = get_session_factory()
    with session_factory() as session:
        query = session.query(Trade).order_by(Trade.filled_at.asc())
        if bot_id:
            query = query.filter(Trade.bot_id == bot_id)
        else:
            query = query.filter(~Trade.bot_id.in_(ARCHIVED_DASHBOARD_BOT_IDS))
        if since is not None:
            query = query.filter(Trade.filled_at >= since)
        rows = query.all()
        order_ids = {row.order_id for row in rows if row.order_id}
        order_status_by_id = {}
        if order_ids:
            order_status_by_id = {
                order_id: status
                for order_id, status in session.query(Order.order_id, Order.status).filter(
                    Order.order_id.in_(sorted(order_ids))
                )
            }
    total_volume = Decimal("0")
    paper_fills = 0
    live_fills = 0
    settlement_fills = 0
    buy_fills = 0
    sell_fills = 0
    matched_positions: dict[tuple[str, str, str], dict[str, Decimal]] = {}
    for row in rows:
        notional = row.price * row.size
        total_volume += notional
        is_settlement = (row.trade_id or "").startswith("paper-resolve-")
        is_paper = (
            (row.order_id or "").startswith("paper-")
            or (row.trade_id or "").startswith("paper-")
            or str(order_status_by_id.get(row.order_id or "", "")).startswith("PAPER")
        )
        if is_settlement:
            settlement_fills += 1
        elif is_paper:
            paper_fills += 1
        else:
            live_fills += 1
        # Session 17s 2026-04-20: Bot E records BUYs as BUY_YES / BUY_NO
        # (signal-side convention). _apply_to_position and get_realised_pnl
        # normalize these to BUY/SELL; dashboard's own FIFO did not, so
        # every Bot E trade was silently dropped from closed_trades / wins
        # / realised_pnl_usd. Normalize here the same way.
        raw_side = row.side
        side = raw_side
        if side and (side.startswith("BUY_") or side.startswith("BUY-")):
            side = "BUY"
        elif side and (side.startswith("SELL_") or side.startswith("SELL-")):
            side = "SELL"
        if side == "BUY":
            buy_fills += 1
        elif side == "SELL":
            sell_fills += 1
        key = (row.bot_id, row.condition_id, row.token_id)
        bucket = matched_positions.setdefault(
            key,
            {
                "open_size": Decimal("0"),
                "open_cost": Decimal("0"),
            },
        )
        if side == "BUY":
            # Entry fees are part of cost basis.
            bucket["open_size"] += row.size
            bucket["open_cost"] += notional + row.fee_usd
        elif side == "SELL":
            if bucket["open_size"] <= 0:
                continue
            matched_size = min(row.size, bucket["open_size"])
            if matched_size <= 0:
                continue
            avg_cost = bucket["open_cost"] / bucket["open_size"]
            matched_cost = avg_cost * matched_size
            fee_share = row.fee_usd * (matched_size / row.size) if row.size > 0 else Decimal("0")
            proceeds = (row.price * matched_size) - fee_share
            bucket.setdefault("closed_pnls", [])
            bucket.setdefault("closed_entry_costs", [])
            bucket["closed_pnls"].append(proceeds - matched_cost)
            bucket["closed_entry_costs"].append(matched_cost)
            bucket["open_size"] -= matched_size
            bucket["open_cost"] -= matched_cost
            if bucket["open_size"] <= 0:
                bucket["open_size"] = Decimal("0")
                bucket["open_cost"] = Decimal("0")
    closed_pnls: list[Decimal] = []
    closed_entry_costs: list[Decimal] = []
    for bucket in matched_positions.values():
        closed_pnls.extend(bucket.get("closed_pnls", []))
        closed_entry_costs.extend(bucket.get("closed_entry_costs", []))
    wins = sum(1 for pnl in closed_pnls if pnl > 0)
    return {
        "recent_trades": _recent_trades(limit=20, bot_id=bot_id, since=since),
        "closed_trades": len(closed_pnls),
        "wins": wins,
        "win_rate_pct": round((wins / len(closed_pnls)) * 100, 1) if closed_pnls else None,
        "closed_entry_cost_usd": round(float(sum(closed_entry_costs, Decimal("0"))), 2),
        "total_volume_usd": round(float(total_volume), 2),
        "realised_pnl_usd": round(float(sum(closed_pnls, Decimal("0"))), 2),
        "filled_trades_count": paper_fills + live_fills,
        "trade_rows_count": len(rows),
        "paper_fills_count": paper_fills,
        "live_fills_count": live_fills,
        "settlement_fills_count": settlement_fills,
        "buy_fills_count": buy_fills,
        "sell_fills_count": sell_fills,
        "volume_source": "trades" if rows else "orders",
    }


def _order_metrics(bot_id: str | None = None, *, since: datetime | None = None) -> dict[str, Any]:
    open_statuses = {"OPEN", "PARTIAL", "PAPER_OPEN", "live"}
    session_factory = get_session_factory()
    with session_factory() as session:
        query = session.query(Order)
        if bot_id:
            query = query.filter(Order.bot_id == bot_id)
        else:
            query = query.filter(~Order.bot_id.in_(ARCHIVED_DASHBOARD_BOT_IDS))
        if since is not None:
            query = query.filter(Order.placed_at >= since)
        rows = query.order_by(Order.placed_at.desc()).all()
    total_orders = len(rows)
    open_orders = [row for row in rows if row.status in open_statuses]
    paper_open_orders = [
        row
        for row in open_orders
        if row.status.startswith("PAPER") or row.order_id.startswith("paper-")
    ]
    live_open_orders = len(open_orders) - len(paper_open_orders)
    # Session 17s 2026-04-20: handle Bot E's BUY_YES / BUY_NO convention.
    buy_orders = sum(1 for row in rows if (row.side or "").startswith("BUY"))
    sell_orders = sum(1 for row in rows if (row.side or "").startswith("SELL"))
    reserved_notional = Decimal("0")
    for row in open_orders:
        if not (row.side or "").startswith("BUY") or row.price is None or row.size is None:
            continue
        reserved_notional += row.price * row.size
    return {
        "total_orders": total_orders,
        "open_orders": len(open_orders),
        "paper_open_orders": len(paper_open_orders),
        "live_open_orders": live_open_orders,
        "buy_orders": buy_orders,
        "sell_orders": sell_orders,
        "reserved_notional_usd": round(float(reserved_notional), 2),
    }


def _order_volume_usd() -> float:
    session_factory = get_session_factory()
    with session_factory() as session:
        rows = session.query(Order.price, Order.size).all()
    total = Decimal("0")
    for price, size in rows:
        if price is not None and size is not None:
            total += price * size
    return round(float(total), 2)


def _enriched_open_positions(bot_id: str | None = None) -> list[dict[str, Any]]:
    positions = _positions_for(bot_id)
    questions = _question_map({row["condition_id"] for row in positions})
    marks = _latest_marks({row["token_id"] for row in positions})
    enriched: list[dict[str, Any]] = []
    for row in positions:
        size = float(row["size"])
        cost_basis = float(row["cost_basis_usd"])
        current_price = marks.get(row["token_id"])
        current_value = round(current_price * size, 2) if current_price is not None else None
        pnl_usd = round(current_value - cost_basis, 2) if current_value is not None else None
        enriched.append(
            {
                **row,
                "market": questions.get(row["condition_id"], row["condition_id"]),
                "entry_price": row["avg_price"],
                "current_price": f"{current_price:.4f}" if current_price is not None else None,
                "current_value_usd": f"{current_value:.2f}" if current_value is not None else None,
                "pnl_usd": f"{pnl_usd:.2f}" if pnl_usd is not None else None,
            }
        )
    return enriched


def _risk_summary(
    open_positions: list[dict[str, Any]], pnl_project: dict[str, Any]
) -> dict[str, Any]:
    """Risk view with internally consistent exposure decomposition.

    Audit fix (Session 14): the headline `current_exposure_usd` came from
    `Portfolio.get_total_exposure()` which sums **positions + open orders**,
    while the breakdown panels (`largest_position`, `exposure_by_bot`) only
    iterated open positions. That made the dashboard look inconsistent
    whenever bots had many resting orders.

    Now we explicitly split:
      total_exposure_usd  = positions_exposure_usd + reserved_orders_usd
      positions_exposure_usd = sum of open position cost_basis_usd
      reserved_orders_usd    = total_exposure_usd − positions_exposure_usd
                                (orders that have committed bankroll but not yet filled)
    """
    exposure_by_bot: dict[str, float] = {}
    largest: dict[str, Any] | None = None
    positions_exposure = 0.0
    for row in open_positions:
        exposure = float(row["cost_basis_usd"])
        positions_exposure += exposure
        exposure_by_bot[row["bot_id"]] = exposure_by_bot.get(row["bot_id"], 0.0) + exposure
        if largest is None or exposure > float(largest["cost_basis_usd"]):
            largest = row

    largest_payload = None
    if largest is not None:
        largest_payload = {
            "bot_id": largest["bot_id"],
            "market": largest["market"],
            "side": largest["side"],
            "size": largest["size"],
            "entry_price": largest["entry_price"],
            "current_price": largest["current_price"],
            "exposure_usd": largest["cost_basis_usd"],
            "pnl_usd": largest["pnl_usd"],
        }

    total_exposure = float(pnl_project.get("exposure_usd", 0) or 0)
    reserved_orders = max(0.0, round(total_exposure - positions_exposure, 2))
    return {
        # Backwards-compatible field — same value as before, now explicitly
        # documented as positions + reserved orders.
        "current_exposure_usd": pnl_project.get("exposure_usd", "0.00"),
        # New: split out so the breakdown matches the headline.
        "positions_exposure_usd": round(positions_exposure, 2),
        "reserved_orders_usd": reserved_orders,
        "largest_position": largest_payload,
        "exposure_by_bot": [
            {"bot_id": bot_id, "exposure_usd": round(value, 2)}
            for bot_id, value in sorted(exposure_by_bot.items())
        ],
    }


def _events(limit: int = 20) -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    with session_factory() as session:
        rows = session.query(Event).order_by(Event.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id,
            "created_at": _iso(row.created_at),
            "event_type": row.event_type,
            "bot_id": row.bot_id,
            "severity": row.severity,
            "message": row.message,
            "payload": row.payload,
        }
        for row in rows
    ]


def _halts() -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    with session_factory() as session:
        rows = session.query(HaltFlag).order_by(HaltFlag.bot_id.asc()).all()
    return [
        {
            "bot_id": row.bot_id,
            "halted": bool(row.halted),
            "reason": row.reason,
            "set_at": _iso(row.set_at),
        }
        for row in rows
    ]


def _counts() -> dict[str, int]:
    with _db() as conn:
        return {
            "markets": conn.execute("SELECT COUNT(*) FROM markets").fetchone()[0],
            "books": conn.execute("SELECT COUNT(*) FROM books").fetchone()[0],
            "scores": conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0],
            "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
        }


def query_overview() -> dict[str, Any]:
    services = service_states()
    halted_ids = _halted_bot_ids()
    halts = _halts()
    fleet_bots = _fleet_bot_summaries(services=services, halted_ids=halted_ids)
    vps_node = _load_vps_node_status()
    epoch_pnl = round(sum(float(bot["pnl_usd"]) for bot in fleet_bots), 2)
    epoch_paper = round(sum(float(bot["paper_amount_usd"]) for bot in fleet_bots), 2)
    epoch_trades = sum(int(bot["trades"]) for bot in fleet_bots)
    bot_inventory = _bot_inventory(
        services=services,
        halted_ids=halted_ids,
        vps_node=vps_node,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": current_mode(),
        "wallet": {
            "display": _mask_wallet(wallet_address()),
            "full": wallet_address()
            if os.environ.get("DASHBOARD_SHOW_FULL_WALLET") == "1"
            else None,
        },
        "services": services,
        "services_summary": {
            "active": sum(1 for v in services.values() if _service_is_active(v)),
            "degraded": sum(1 for v in services.values() if not _service_is_active(v)),
        },
        "halts": halts,
        "counts": {},
        "pnl": {},
        "balances": {},
        "event_severity_7d": _event_severity_counts(),
        "project_history": [],
        "performance": {
            "total_pnl_usd": epoch_pnl,
            "paper_amount_usd": epoch_paper,
            "trades": epoch_trades,
        },
        "risk": _cockpit_risk_summary(services=services, halts=halts, inventory=bot_inventory),
        "priority_alerts": _cockpit_priority_alerts(),
        "strategy_pnl": [],
        "open_positions": [],
        "recent_trades": [],
        "fleet_bots": fleet_bots,
        "bot_inventory": bot_inventory,
        "fleet_epoch": {
            "id": FLEET_EPOCH_ID,
            "start": _parse_epoch_start(FLEET_EPOCH_START).isoformat(),
            "note": "Default current cohort for non-Bot-D paper metrics.",
        },
        "vps_node": vps_node,
        "recorder_comparison": _recorder_comparison_summary(),
        "persistence_paper": _persistence_paper_summary(),
        "bot_f_momentum_paper": _bot_f_momentum_paper_summary(),
        "wallet_tag_feature_shadow": _wallet_tag_feature_shadow_summary(),
        "wallet_tag_elite_cap_paper": _wallet_tag_elite_cap_paper_summary(),
        # P0 accounting clarity (OQ-123 / ADR-181) — extended per overnight spec phase 2
        "accounting": {
            "wallet_reconciliation_run_at": None,
            "wallet_reconciliation_status": "OQ-123 pending — local DB(s) only until wallet_data_api_backfill.py dry-run is reviewed and backfill table populated. "
            "Run scripts/wallet_data_api_backfill.py --dry-run (read-only) for authoritative gap report.",
            "persistence_live_db_separate": True,
            "main_db_is_not_whole_wallet": True,
            "total_unresolved_usd": 0.0,
            "fully_reconciled_bots": 0,
            "reconciliation_note": "per-row fields now include reconciliation_status / wallet_realised_pnl_usd / freshness (local_only until OQ-123 write path approved)",
        },
        "wc_negrisk_basket_paper": _wc_negrisk_basket_paper_summary(),
        "notes": [],
    }


def _cockpit_risk_summary(
    *,
    services: dict[str, str],
    halts: list[dict[str, Any]],
    inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compact risk strip for the cockpit Overview.

    Only surfaces signals worth an operator's eyes: degraded services that
    belong to active dashboard rows, halts on rows still considered active,
    and a stale-feed marker when an active recorder's heartbeat is too old.
    Archived/parked/halted-by-design rows do not contribute.
    """
    active_services = set()
    for row in inventory:
        for entry in (row.get("service") or "").split(" / "):
            name = entry.split(":", 1)[0]
            if name and name != "no service":
                active_services.add(name)
    degraded = [
        {"service": name, "state": state}
        for name, state in services.items()
        if name in active_services and not _service_is_active(state)
    ]
    # Halts on Recorder-class lanes are legacy trading-bot rows that do not
    # apply to the recorder service (e.g. the 2026-05-05 `bot_e` halt). Only
    # halts on currently-active trading lanes belong on the Risk strip.
    trading_active_ids = {
        row.get("bot_id") for row in inventory if row.get("group") in {"Live", "Paper"}
    }
    active_halts = [h for h in halts if h.get("halted") and h.get("bot_id") in trading_active_ids]
    return {
        "degraded_services": degraded,
        "active_halts": active_halts,
        "active_count": len(inventory),
    }


def _cockpit_priority_alerts() -> list[dict[str, Any]]:
    """Priority edge alerts for the cockpit Overview.

    Empty by default. A future ADR (or wallet-tag forward gate clearing the
    OQ-099 bar on 2026-05-15) appends rows here. Keeping the surface
    explicit and empty ensures absence is visible, not implied.
    """
    return []


def _recorder_comparison_summary() -> dict[str, Any]:
    local = _bot_e_recorder_summary()
    vps = _load_vps_node_status()
    vps_rec = vps.get("recorder") if isinstance(vps.get("recorder"), dict) else {}
    local_capture = local.get("capture") if isinstance(local.get("capture"), dict) else {}
    local_counts = local.get("counts") if isinstance(local.get("counts"), dict) else {}
    vps_counts = vps_rec.get("counts") if isinstance(vps_rec.get("counts"), dict) else {}
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "local": {
            "host": "the bot container",
            "db_exists": local.get("db_exists", False),
            "db_size_bytes": local.get("db_size_bytes", 0),
            "counts": local_counts,
            "heartbeat_age_sec": local_capture.get("seconds_since_last_event"),
            "pm_events_per_min": local_capture.get("pm_events_per_min"),
            "cex_trades_per_min": local_capture.get("cex_trades_per_min"),
            "active_subscriptions": len(local.get("active_subscriptions") or []),
            "gaps": local_counts.get("gaps", 0),
        },
        "vps": {
            "host": "vps-host",
            "ok": bool(vps.get("ok")),
            "db_exists": vps_rec.get("exists", False),
            "db_size_bytes": vps_rec.get("size_bytes", 0),
            "counts": vps_counts,
            "heartbeat_age_sec": vps_rec.get("heartbeat_age_sec"),
            "pm_events_per_min": vps_rec.get("pm_events_per_min_5m"),
            "cex_trades_per_min": vps_rec.get("cex_trades_per_min_5m"),
            "active_subscriptions": vps_rec.get("active_subscriptions_5m"),
            "gaps": vps_counts.get("gaps", 0),
        },
    }


def _overview_bot_e_tile() -> dict[str, Any]:
    """Compact Bot E tile for overview grid — no heavy queries, just headline state."""
    rec = _bot_e_recorder_summary()
    if not rec.get("db_exists"):
        return {"phase": "not_deployed", "status": "no_db"}
    capture = rec.get("capture") or {}
    counts = rec.get("counts") or {}
    last_age = capture.get("seconds_since_last_event")
    fresh = last_age is not None and last_age < 120  # considered fresh if event in last 2min
    return {
        "phase": rec["phase"],
        "calibration_ready": rec.get("calibration_ready", False),
        "trader_activated": rec.get("trader_activated", False),
        "pm_events": counts.get("pm_events", 0),
        "cex_trades": counts.get("cex_trades", 0),
        "markets": counts.get("markets", 0),
        "n_active_subscriptions": len(rec.get("active_subscriptions") or []),
        "duration_hours": capture.get("duration_hours"),
        "events_per_min": capture.get("pm_events_per_min"),
        "last_event_age_sec": last_age,
        "fresh": fresh,
        "db_size_mb": round((rec.get("db_size_bytes") or 0) / 1024 / 1024, 1),
    }


def query_bot_c() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    spec = _spec_for("bot_c")
    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bot_id": "bot_c",
        "simple": _bot_simple_summary(spec),
        "trial_expiry": PYTH_PRO_TRIAL_EXPIRY.date().isoformat(),
        "trial_days_left": (PYTH_PRO_TRIAL_EXPIRY - now).days,
    }
    if os.environ.get("DASHBOARD_DETAILED_BOT_TABS", "false").lower() != "true":
        return payload
    if not os.path.exists(bot_c_db_path()):
        payload["error"] = "db not found (bot-c not yet run)"
        return payload
    try:
        with _bot_c_db() as conn:
            cutoff_ms = int(now.timestamp() * 1000) - 3600_000
            tick_rows = conn.execute(
                "SELECT endpoint, COUNT(*) n, MAX(ts_ms) last_ts FROM pyth_ticks_recent WHERE ts_ms >= ? GROUP BY endpoint",
                (cutoff_ms,),
            ).fetchall()
            payload["ticks"] = {
                row["endpoint"]: {
                    "count_1h": row["n"],
                    "last_age_s": int((now.timestamp() * 1000 - row["last_ts"]) / 1000),
                }
                for row in tick_rows
            }

            _ALLOWED_BAR_TABLES = {"pyth_bars_pro", "pyth_bars_hermes"}

            def bars_from(table: str) -> dict[str, Any]:
                # Whitelist the table name — f-string interpolation into SQL
                # is a latent injection pattern even when every caller is
                # currently benign (audit C18).
                if table not in _ALLOWED_BAR_TABLES:
                    raise ValueError(f"bars_from: disallowed table {table!r}")
                try:
                    row = conn.execute(
                        f"SELECT COUNT(*) n, COUNT(DISTINCT symbol) syms, MAX(ts) last_ts FROM {table} WHERE ts >= datetime(?, 'unixepoch')",
                        (int(now.timestamp()) - 3600,),
                    ).fetchone()
                    return {"count_1h": row["n"], "symbols": row["syms"], "last_ts": row["last_ts"]}
                except sqlite3.OperationalError:
                    return {"count_1h": 0, "symbols": 0, "last_ts": None}

            payload["bars_pro"] = bars_from("pyth_bars_pro")
            payload["bars_hermes"] = bars_from("pyth_bars_hermes")
            payload["spots"] = [
                {"symbol": row["symbol"], "price": float(row["close"]), "ts": row["ts"]}
                for row in conn.execute(
                    "SELECT symbol, close, ts FROM pyth_bars_pro WHERE ts = "
                    "(SELECT MAX(ts) FROM pyth_bars_pro AS b WHERE b.symbol = pyth_bars_pro.symbol) ORDER BY symbol"
                ).fetchall()
            ]
            decision_rows = conn.execute(
                "SELECT decided_at, symbol, side, direction, strike_low, strike_high, model_p_yes, market_p_yes, edge, hours_to_resolution, slug "
                "FROM bot_c_decisions ORDER BY id DESC LIMIT 20"
            ).fetchall()
            payload["decisions"] = [dict(row) for row in decision_rows]
            counts = conn.execute(
                "SELECT side, COUNT(*) n FROM bot_c_decisions WHERE decided_at >= datetime(?, 'unixepoch') GROUP BY side",
                (int(now.timestamp()) - 3600,),
            ).fetchall()
            payload["decision_counts_1h"] = {row["side"]: row["n"] for row in counts}
            series_rows = conn.execute(
                "SELECT symbol, ts, close FROM pyth_bars_pro WHERE ts >= datetime(?, 'unixepoch') ORDER BY ts ASC",
                (int(now.timestamp()) - 3600,),
            ).fetchall()
            series: dict[str, list[dict[str, Any]]] = {}
            for row in series_rows:
                series.setdefault(row["symbol"], []).append(
                    {"ts": row["ts"], "close": float(row["close"])}
                )
            payload["series"] = series
    except Exception as exc:
        payload["error"] = str(exc)[:200]
    payload["paper_pnl"] = _paper_pnl("bot_c")
    return payload


def query_bot_d() -> dict[str, Any]:
    """Bot D (weather) — paper/live orders + edge summary from main.db."""
    now = datetime.now(timezone.utc)
    services = service_states()
    halted_ids = _halted_bot_ids()
    spec = _spec_for("bot_d")
    live_spec = _spec_for("bot_d_live_probe")
    maker_spec = _spec_for("bot_d_maker_live_probe")
    spike_spec = _spec_for("bot_d_spike")
    spike_short_spec = _spec_for("bot_d_spike_short")
    station_lock_spec = _spec_for("bot_d_station_lock")
    epoch = _bot_d_epoch()
    epoch_start = _parse_epoch_start(BOT_D_PAPER_EPOCH_START)
    simple = _bot_simple_summary(spec, services=services, halted_ids=halted_ids)
    live_simple = _bot_simple_summary(live_spec, services=services, halted_ids=halted_ids)
    maker_simple = _bot_simple_summary(maker_spec, services=services, halted_ids=halted_ids)
    spike_simple = _bot_simple_summary(spike_spec, services=services, halted_ids=halted_ids)
    spike_short_simple = _bot_simple_summary(
        spike_short_spec, services=services, halted_ids=halted_ids
    )
    station_lock_simple = _bot_simple_summary(
        station_lock_spec, services=services, halted_ids=halted_ids
    )
    station_lock_summary = _bot_d_station_lock_summary(hours=24)
    vps_spike = _vps_bot_d_spike_summary()
    vps_spike_short = _vps_bot_d_spike_short_summary()
    spike_service_active = any(
        services.get(str(service)) == "vps:active" for service in spike_spec.get("services", ())
    )
    spike_short_service_active = any(
        services.get(str(service)) == "vps:active"
        for service in spike_short_spec.get("services", ())
    )
    spike_uses_vps = bool(spike_service_active and vps_spike)
    spike_short_uses_vps = bool(spike_short_service_active and vps_spike_short)
    spike_orders = (
        vps_spike.get("orders")
        if spike_uses_vps and isinstance(vps_spike.get("orders"), dict)
        else _order_metrics("bot_d_spike")
    )
    spike_trades = (
        vps_spike.get("trades")
        if spike_uses_vps and isinstance(vps_spike.get("trades"), dict)
        else _trade_metrics("bot_d_spike")
    )
    spike_short_orders = (
        vps_spike_short.get("orders")
        if spike_short_uses_vps and isinstance(vps_spike_short.get("orders"), dict)
        else _order_metrics("bot_d_spike_short")
    )
    spike_short_trades = (
        vps_spike_short.get("trades")
        if spike_short_uses_vps and isinstance(vps_spike_short.get("trades"), dict)
        else _trade_metrics("bot_d_spike_short")
    )
    if spike_uses_vps:
        spike_simple = _bot_d_spike_vps_simple(spike_simple, vps_spike, spike_orders, spike_trades)
    if spike_short_uses_vps:
        spike_short_simple = _bot_d_spike_vps_simple(
            spike_short_simple,
            vps_spike_short,
            spike_short_orders,
            spike_short_trades,
        )
    source_edge = _bot_d_source_edge_summary(hours=6, bot_id="bot_d_live_probe")
    gribstream_live = _bot_d_gribstream_summary(hours=24, bot_id="bot_d_live_probe")
    gribstream_paper = _bot_d_gribstream_summary(hours=24, bot_id="bot_d")
    payload: dict[str, Any] = {
        "generated_at": now.isoformat(),
        "bot_id": "bot_d",
        "simple": simple,
        "readiness": build_bot_d_readiness_report(Path(main_db_path()), now=now),
        "source_edge": source_edge,
        "gribstream": gribstream_paper,
        "live_probe": {
            "bot_id": "bot_d_live_probe",
            "simple": live_simple,
            "recent_trades": _recent_trades(limit=10, bot_id="bot_d_live_probe"),
            "trade_metrics": _trade_metrics("bot_d_live_probe"),
            "order_metrics": _order_metrics("bot_d_live_probe"),
            "open_orders_pnl": _live_probe_open_orders_pnl("bot_d_live_probe"),
            "caps": _bot_d_live_probe_caps("bot_d_live_probe"),
            "source_edge": source_edge,
            "gribstream": gribstream_live,
        },
        "maker_live": {
            "bot_id": "bot_d_maker_live_probe",
            "label": maker_spec.get("label") or "Weather Maker Live Probe (D)",
            "simple": maker_simple,
            "mode": "live",
            "strategy": "maker quote weather fade",
            "quote_policy": {
                "min_notional_usd": 5,
                "max_order_usd": 10,
                "quote_max_age_sec": 180,
                "maker_only": True,
                "activation_adr": "ADR-174",
            },
            "recent_trades": _recent_trades(limit=10, bot_id="bot_d_maker_live_probe"),
            "trade_metrics": _trade_metrics("bot_d_maker_live_probe"),
            "order_metrics": _order_metrics("bot_d_maker_live_probe"),
            "open_orders_pnl": _live_probe_open_orders_pnl("bot_d_maker_live_probe"),
            "caps": _bot_d_live_probe_caps("bot_d_maker_live_probe"),
        },
        "spike": {
            "bot_id": "bot_d_spike",
            "label": spike_spec.get("label") or "Weather Spike Live Probe (D)",
            "simple": spike_simple,
            "data_source": "vps" if spike_uses_vps else "the bot container",
            "mode": "live",
            "strategy": "Strategy E",
            "entry_band": "1c-15c",
            "ttr_window": "6h-12h",
            "hold_to": "resolution",
            "position_size_usd": 2,
            "deployed_cap_usd": 20,
            "daily_gross_cap_usd": 10,
            "daily_entry_cap": 5,
            "validation": {
                "closed_target": 200,
                "days_target": 90,
                "roi_gate_pct": 5,
                "hit_rate_baseline_pct": 3.6,
                "paper_only": False,
                "tiny_live_probe": True,
                "activation_adr": "ADR-165",
            },
            "order_metrics": spike_orders,
            "trade_metrics": spike_trades,
            "open_positions": (
                vps_spike.get("open_positions")
                if spike_uses_vps
                else spike_simple.get("open_positions", 0)
            ),
            "open_cost_basis_usd": (
                vps_spike.get("open_cost_basis_usd")
                if spike_uses_vps
                else spike_simple.get("open_position_cost_usd", 0)
            ),
            "recent_entries": (
                vps_spike.get("recent_entries", [])
                if spike_uses_vps and isinstance(vps_spike.get("recent_entries"), list)
                else []
            ),
        },
        "spike_short": {
            "bot_id": "bot_d_spike_short",
            "label": spike_short_spec.get("label") or "Weather Spike Short Paper (D)",
            "simple": spike_short_simple,
            "data_source": "vps" if spike_short_uses_vps else "the bot container",
            "mode": "paper",
            "strategy": "Strategy E2",
            "entry_band": "1c-15c",
            "ttr_window": "0h-6h",
            "hold_to": "resolution",
            "position_size_usd": 2,
            "deployed_cap_usd": 200,
            "daily_entry_cap": 30,
            "validation": {
                "closed_target": 200,
                "days_target": 90,
                "roi_gate_pct": 5,
                "hit_rate_baseline_pct": 3.6,
                "paper_only": True,
            },
            "order_metrics": spike_short_orders,
            "trade_metrics": spike_short_trades,
            "open_positions": (
                vps_spike_short.get("open_positions")
                if spike_short_uses_vps
                else spike_short_simple.get("open_positions", 0)
            ),
            "open_cost_basis_usd": (
                vps_spike_short.get("open_cost_basis_usd")
                if spike_short_uses_vps
                else spike_short_simple.get("open_position_cost_usd", 0)
            ),
            "recent_entries": (
                vps_spike_short.get("recent_entries", [])
                if spike_short_uses_vps and isinstance(vps_spike_short.get("recent_entries"), list)
                else []
            ),
        },
        "station_lock": {
            "bot_id": "bot_d_station_lock",
            "label": station_lock_spec.get("label") or "Weather Station Lock Live Probe (D)",
            "simple": station_lock_simple,
            "mode": "live",
            "strategy": "Late station-certainty",
            "validation": {
                "resolved_target": 30,
                "days_target": 14,
                "paper_only": False,
                "tiny_live_probe": True,
                "activation_adr": "ADR-165",
                "oq": "OQ-112",
            },
            "metrics": station_lock_summary,
        },
        "paper_epoch": {
            **epoch,
            "paper_pnl": {
                "capital_deployed": simple["paper_amount_usd"],
                "open_count": simple["open_orders"],
            },
            "order_metrics": {
                "total_orders": simple["trades"],
                "open_orders": simple["open_orders"],
                "paper_open_orders": simple["paper_open_orders"],
            },
            "trade_metrics": {
                "filled_trades_count": simple["fills"],
                "recent_trades": [],
                "realised_pnl_usd": simple["pnl_usd"],
            },
            "status_counts": {},
        },
    }
    payload["recent_trades"] = _recent_trades(limit=15, bot_id="bot_d")
    if os.environ.get("DASHBOARD_DETAILED_BOT_TABS", "false").lower() != "true":
        return payload
    try:
        with _db() as conn:
            # Recent bot_d orders (last 25)
            orders = conn.execute(
                "SELECT order_id, condition_id, token_id, side, price, size, status, placed_at "
                "FROM orders WHERE bot_id='bot_d' ORDER BY placed_at DESC LIMIT 25"
            ).fetchall()
            payload["orders"] = [dict(r) for r in orders]

            # Open positions
            positions = conn.execute(
                "SELECT condition_id, token_id, side, size, avg_price, cost_basis_usd, status "
                "FROM positions WHERE bot_id='bot_d' AND status='OPEN'"
            ).fetchall()
            payload["positions"] = [dict(r) for r in positions]

            # Counts
            total_orders = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE bot_id='bot_d'"
            ).fetchone()[0]
            paper_orders = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE bot_id='bot_d' AND status='PAPER_OPEN'"
            ).fetchone()[0]
            payload["total_orders"] = total_orders
            payload["paper_orders"] = paper_orders
            payload["open_positions"] = len(positions)

            # Order status breakdown
            status_rows = conn.execute(
                "SELECT status, COUNT(*) n FROM orders WHERE bot_id='bot_d' GROUP BY status"
            ).fetchall()
            payload["status_counts"] = {r["status"]: r["n"] for r in status_rows}

            epoch_status_rows = conn.execute(
                "SELECT status, COUNT(*) n FROM orders "
                "WHERE bot_id='bot_d' AND placed_at >= ? GROUP BY status",
                (_sqlite_dt(epoch_start),),
            ).fetchall()
            payload["epoch_status_counts"] = {r["status"]: r["n"] for r in epoch_status_rows}
    except Exception as exc:
        payload["error"] = str(exc)[:200]
    payload["trade_metrics"] = _trade_metrics("bot_d")
    payload["order_metrics"] = _order_metrics("bot_d")
    payload["paper_pnl"] = _paper_pnl("bot_d")
    payload["paper_epoch"]["trade_metrics"] = _trade_metrics("bot_d", since=epoch_start)
    payload["paper_epoch"]["order_metrics"] = _order_metrics("bot_d", since=epoch_start)
    payload["paper_epoch"]["paper_pnl"] = _paper_pnl("bot_d", since=epoch_start)
    payload["paper_epoch"]["status_counts"] = payload.get("epoch_status_counts", {})
    return payload


def _bot_e_recorder_summary() -> dict[str, Any]:
    """Crypto recorder health + capture stats. Returns empty shape if DB absent."""
    db_path = Path(bot_e_recorder_db_path())
    cal_path = Path(bot_e_calibration_go_path())

    out: dict[str, Any] = {
        "phase": "0b_recorder",
        "display_name": "Crypto Recorder",
        "purpose": "Bot G crypto market telemetry and replay data",
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "calibration_ready": cal_path.exists(),
        "trader_activated": False,  # Phase 1 trader is gated on calibration_ready + BOT_E_DRY_RUN=false
    }
    if not db_path.exists():
        out["status"] = "no_db"
        return out

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        try:

            def _fast_count(table: str) -> int:
                """Approximate append-only recorder counts without full DB scans."""
                if table in {"pm_events", "cex_trades"}:
                    row = conn.execute(f"SELECT MAX(id) FROM {table}").fetchone()
                    return int(row[0] or 0)
                return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

            counts = {
                t: _fast_count(t)
                for t in ("pm_events", "cex_trades", "markets", "heartbeats", "gaps")
            }
            out["counts"] = counts

            # Capture window + throughput
            row = conn.execute(
                "SELECT "
                "(SELECT received_at_ms FROM pm_events ORDER BY id ASC LIMIT 1), "
                "(SELECT received_at_ms FROM pm_events ORDER BY id DESC LIMIT 1)"
            ).fetchone()
            if row and row[0] and row[1]:
                dur_sec = (row[1] - row[0]) / 1000.0
                dur_min = max(dur_sec / 60.0, 1e-9)
                now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                out["capture"] = {
                    "first_event_ms": row[0],
                    "last_event_ms": row[1],
                    "duration_sec": round(dur_sec, 1),
                    "duration_hours": round(dur_sec / 3600, 2),
                    "seconds_since_last_event": round((now_ms - row[1]) / 1000.0, 1),
                    "pm_events_per_min": round(counts["pm_events"] / dur_min, 1),
                    "cex_trades_per_min": round(counts["cex_trades"] / dur_min, 1),
                }
            else:
                out["capture"] = {"duration_sec": 0, "seconds_since_last_event": None}

            # Active subscriptions in last 5 minutes
            cutoff_ms = int(datetime.now(timezone.utc).timestamp() * 1000) - 5 * 60 * 1000
            latest_pm_id = counts.get("pm_events", 0)
            recent_floor_id = max(0, latest_pm_id - 50000)
            active = conn.execute(
                "SELECT subscription_id, MAX(received_at_ms) last_event_ms, COUNT(*) n "
                "FROM pm_events WHERE id >= ? AND received_at_ms >= ? "
                "GROUP BY subscription_id ORDER BY last_event_ms DESC",
                (recent_floor_id, cutoff_ms),
            ).fetchall()
            out["active_subscriptions"] = [dict(r) for r in active]

            # Latest markets snapshot — show what's currently being watched.
            # Older recorder DBs may not have the Bot-G-oriented metadata columns
            # until the recorder process has run the migration.
            market_cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(markets)").fetchall()}
            symbol_expr = "symbol" if "symbol" in market_cols else "NULL AS symbol"
            duration_expr = (
                "duration_minutes"
                if "duration_minutes" in market_cols
                else "NULL AS duration_minutes"
            )
            markets = conn.execute(
                "SELECT condition_id, question, end_date_iso, "
                f"{symbol_expr}, {duration_expr}, "
                "yes_price, volume_24h_usd "
                "FROM markets WHERE scan_at_ms = (SELECT MAX(scan_at_ms) FROM markets) "
                "LIMIT 15"
            ).fetchall()
            out["latest_markets"] = [dict(r) for r in markets]

            # Recent gaps (populated by audit.py; may be empty)
            gaps = conn.execute(
                "SELECT source, subscription_id, gap_start_ms, gap_end_ms, duration_sec "
                "FROM gaps ORDER BY gap_start_ms DESC LIMIT 10"
            ).fetchall()
            out["recent_gaps"] = [dict(r) for r in gaps]
        finally:
            conn.close()
    except Exception as exc:
        out["error"] = str(exc)[:200]
    return out


def query_bot_e() -> dict[str, Any]:
    """Bot E full status: Phase 0b recorder + paper-collection trader activity."""
    spec = _spec_for("bot_e")
    simple = _bot_simple_summary(spec)
    if os.environ.get("DASHBOARD_DETAILED_BOT_TABS", "false").lower() != "true":
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "bot_id": "bot_e",
            "simple": simple,
        }
    summary = _bot_e_recorder_summary()
    trade_metrics = _trade_metrics("bot_e")
    order_metrics = _order_metrics("bot_e")
    trader: dict[str, Any] = {
        "bankroll_usd": str(initial_usd().get("bot_e", Decimal("0"))),
        "dry_run": os.environ.get("BOT_E_DRY_RUN", "true").lower() == "true",
        "env": os.environ.get("BOT_E_ENV", "paper"),
        "activation_gated_on": str(Path(bot_e_calibration_go_path())),
        "go_file_exists": Path(bot_e_calibration_go_path()).exists(),
        "trade_metrics": trade_metrics,
        "order_metrics": order_metrics,
        "recent_trades": trade_metrics["recent_trades"],
    }

    # Paper-collection mode orders + positions (ADR-022.1).
    try:
        with _db() as db:
            orders = [
                dict(row)
                for row in db.execute(
                    "SELECT order_id, condition_id, token_id, side, price, size, status, placed_at "
                    "FROM orders WHERE bot_id='bot_e' ORDER BY placed_at DESC LIMIT 25"
                )
            ]
            positions = [
                dict(row)
                for row in db.execute(
                    "SELECT condition_id, token_id, side, size, avg_price, cost_basis_usd "
                    "FROM positions WHERE bot_id='bot_e' AND status='OPEN'"
                )
            ]
            total_orders = db.execute(
                "SELECT COUNT(*) FROM orders WHERE bot_id='bot_e'"
            ).fetchone()[0]
            paper_open = db.execute(
                "SELECT COUNT(*) FROM orders WHERE bot_id='bot_e' AND status='PAPER_OPEN'"
            ).fetchone()[0]
            status_counts = dict(
                db.execute(
                    "SELECT status, COUNT(*) n FROM orders WHERE bot_id='bot_e' GROUP BY status"
                ).fetchall()
            )
        trader["orders_recent"] = orders
        trader["positions_open"] = positions
        trader["order_total"] = total_orders
        trader["paper_open_count"] = paper_open
        trader["status_counts"] = status_counts
        trader["paper_pnl"] = _paper_pnl("bot_e")
    except Exception as exc:
        trader["db_error"] = str(exc)[:200]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bot_id": "bot_e",
        "simple": simple,
        "recorder": summary,
        "trader": trader,
    }


def query_bot_g() -> dict[str, Any]:
    """Bot G Prime live probe plus paper research shadows."""
    services = service_states()
    halted_ids = _halted_bot_ids()
    vps_bot_g = _vps_bot_g_summary()
    g_specs = [_spec_for("bot_g_prime_live"), _spec_for("bot_g_prime")]
    research_specs = [
        _spec_for("bot_g_prime_live_maker"),
        _spec_for("bot_g_prime_maker"),
        _spec_for("bot_g_prime_shadow"),
        _spec_for("bot_g_prime_high_tail"),
        _spec_for("bot_g_prime_late_cheap"),
        _spec_for("bot_g_prime_take_profit"),
    ]
    fleet_bots = [
        _bot_simple_summary(spec, services=services, halted_ids=halted_ids) for spec in g_specs
    ]
    for bot in fleet_bots:
        bot_id = str(bot["bot_id"])
        if _vps_bot_g_is_remote(bot_id, services, vps_bot_g) and _summary_needs_vps_bot_g_metrics(
            bot, vps_bot_g
        ):
            _apply_vps_bot_g_simple_metrics(bot, vps_bot_g)
        else:
            pnl_breakdown = _bot_g_prime_pnl_breakdown(
                _parse_epoch_start(bot["epoch"]["start"]),
                bot_id=bot_id,
            )
            if pnl_breakdown:
                bot["pnl_breakdown"] = pnl_breakdown
                bot["pnl_note"] = (
                    f"cash: realised ${pnl_breakdown['closed_realised_usd']:.2f} "
                    f"- open ${pnl_breakdown['open_cost_usd']:.2f}"
                )

    def _trader_for(bot_id: str, *, validation: dict[str, Any] | None = None) -> dict[str, Any]:
        bot_services = _spec_for(bot_id).get("services", ())
        use_vps = any(
            services.get(str(service)) == "vps:active" for service in bot_services
        ) and bot_id in (vps_bot_g.get("bot_ids") or [])
        vps_trade_metrics = (
            vps_bot_g.get("trade_metrics")
            if isinstance(vps_bot_g.get("trade_metrics"), dict)
            else {}
        )
        vps_order_metrics = (
            vps_bot_g.get("order_metrics")
            if isinstance(vps_bot_g.get("order_metrics"), dict)
            else {}
        )
        vps_recent_orders = (
            vps_bot_g.get("recent_orders")
            if isinstance(vps_bot_g.get("recent_orders"), dict)
            else {}
        )
        vps_positions_open = (
            vps_bot_g.get("positions_open")
            if isinstance(vps_bot_g.get("positions_open"), dict)
            else {}
        )
        vps_paper_pnl = (
            vps_bot_g.get("paper_pnl") if isinstance(vps_bot_g.get("paper_pnl"), dict) else {}
        )
        vps_live_epoch = (
            vps_bot_g.get("live_epoch") if isinstance(vps_bot_g.get("live_epoch"), dict) else {}
        )
        if use_vps and bot_id == "bot_g_prime_live" and vps_live_epoch:
            vps_trade_metrics = {bot_id: vps_live_epoch.get("trade_metrics") or {}}
            vps_order_metrics = {bot_id: vps_live_epoch.get("order_metrics") or {}}
            vps_recent_orders = {bot_id: vps_live_epoch.get("recent_orders") or []}
            vps_positions_open = {bot_id: vps_live_epoch.get("positions_open") or []}
            vps_paper_pnl = {bot_id: {}}
        vps_runtime_state = (
            vps_bot_g.get("runtime_state")
            if isinstance(vps_bot_g.get("runtime_state"), dict)
            else {}
        )
        trade_metrics = (
            vps_trade_metrics.get(bot_id, _trade_metrics(bot_id))
            if use_vps
            else _trade_metrics(bot_id)
        )
        order_metrics = (
            vps_order_metrics.get(bot_id, _order_metrics(bot_id))
            if use_vps
            else _order_metrics(bot_id)
        )
        runtime_state = (
            {**_bot_g_runtime_state_summary(bot_id), **vps_runtime_state.get(bot_id, {})}
            if use_vps
            else _bot_g_runtime_state_summary(bot_id)
        )
        trader: dict[str, Any] = {
            "bot_id": bot_id,
            "bankroll_usd": str(initial_usd().get(bot_id, Decimal("200"))),
            "dry_run": bool(runtime_state.get("bot_dry_run", True)),
            "env": str(runtime_state.get("bot_env", "paper")),
            "archived": os.environ.get("BOT_G_ARCHIVED", "false").lower() in ("true", "1", "yes"),
            "data_source": "vps" if use_vps else "the bot container",
            "trade_metrics": trade_metrics,
            "order_metrics": order_metrics,
            "runtime_state": runtime_state,
        }
        if use_vps:
            trader["orders_recent"] = vps_recent_orders.get(bot_id, [])
            trader["positions_open"] = vps_positions_open.get(bot_id, [])
            trader["paper_pnl"] = vps_paper_pnl.get(bot_id, _paper_pnl(bot_id))
            trader["per_mode"] = {}
        else:
            try:
                with _db() as db:
                    orders = [
                        dict(row)
                        for row in db.execute(
                            """
                            SELECT order_id, condition_id, token_id, side, price, size, status, placed_at
                            FROM orders
                            WHERE bot_id=?
                            ORDER BY placed_at DESC
                            LIMIT 25
                            """,
                            (bot_id,),
                        )
                    ]
                    positions = [
                        dict(row)
                        for row in db.execute(
                            """
                            SELECT condition_id, token_id, side, size, avg_price, cost_basis_usd
                            FROM positions
                            WHERE bot_id=?
                              AND status='OPEN'
                            """,
                            (bot_id,),
                        )
                    ]
                trader["orders_recent"] = orders
                trader["positions_open"] = positions
                trader["paper_pnl"] = _paper_pnl(bot_id)
                trader["per_mode"] = _bot_g_per_mode_breakdown(bot_id)
            except Exception as exc:
                trader["db_error"] = str(exc)[:200]
        trader["live_probe"] = bot_g_tiny_live_probe_plan(
            dry_run=bool(trader["dry_run"]),
            env=str(trader["env"]),
            global_env=str(runtime_state.get("global_polymarket_env", current_mode())),
            effective_paper=runtime_state.get("effective_paper"),
            runtime_source=str(runtime_state.get("source", "dashboard_env")),
            live_approved_at=str(runtime_state.get("live_approved_at", "")),
            live_wallet_usd=runtime_state.get("live_wallet_usd"),
            trade_metrics=trade_metrics,
            order_metrics=order_metrics,
            validation=validation or {},
        )
        return trader

    paper_validation = _bot_g_paper_validation_summary()
    trader = _trader_for("bot_g_prime", validation=paper_validation)
    trader["paper_validation"] = paper_validation
    live_trader = _trader_for("bot_g_prime_live", validation=paper_validation)
    live_archive = {}
    live_epoch = (
        vps_bot_g.get("live_epoch") if isinstance(vps_bot_g.get("live_epoch"), dict) else {}
    )
    if live_epoch:
        live_archive = {
            "epoch_id": live_epoch.get("epoch_id"),
            "start": live_epoch.get("start"),
            "profile": live_epoch.get("profile"),
            "current_trade_metrics": live_epoch.get("trade_metrics") or {},
            "current_order_metrics": live_epoch.get("order_metrics") or {},
            "legacy": live_epoch.get("legacy") or {},
        }
    live_spec = _spec_for("bot_g_prime_live")
    live_services = live_spec.get("services", ())
    live_service_active = any(
        services.get(str(service)) in {"active", "vps:active"} for service in live_services
    )
    live_status_paused = (
        live_spec.get("registry_status") == "paused" or live_spec.get("status") == "paused"
    )
    if live_status_paused and live_service_active:
        live_probe = dict(live_trader.get("live_probe") or {})
        live_probe.update(
            {
                "status": "active_despite_adr_135_pause",
                "live_probe_active": bool(live_probe.get("live_probe_active")),
                "activation_blocked": False,
                "does_not_authorize_live": True,
                "policy_conflict": True,
                "restart_requires_adr": True,
                "pause_reason": (
                    "Policy conflict: registry says ADR-135 paused, "
                    "but the monitored live service is active."
                ),
            }
        )
        live_trader["live_probe"] = live_probe
    elif live_status_paused or not live_service_active:
        live_probe = dict(live_trader.get("live_probe") or {})
        live_probe.update(
            {
                "status": "paused_by_adr_135",
                "live_probe_active": False,
                "activation_blocked": True,
                "does_not_authorize_live": True,
                "restart_requires_adr": True,
                "pause_reason": (
                    "ADR-135 emergency pause: live-shaped cohorts failed; "
                    "restart requires a separate operator-approved ADR."
                ),
            }
        )
        live_trader["live_probe"] = live_probe
    recent_events = _bot_g_recent_event_counts()
    lead_bucket_report = _bot_g_lead_bucket_report_summary()
    _merge_vps_bot_g_report_rows(lead_bucket_report, services=services, vps_bot_g=vps_bot_g)
    research_shadows = [
        _bot_g_research_shadow_summary(
            spec,
            services=services,
            halted_ids=halted_ids,
            lead_bucket_report=lead_bucket_report,
        )
        for spec in research_specs
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bot_id": "bot_g_prime_live",
        "fleet_bots": fleet_bots,
        "simple": fleet_bots[0],
        "trader": trader,
        "paper_trader": trader,
        "live_trader": live_trader,
        "live_archive": live_archive,
        "research_shadows": research_shadows,
        "lead_bucket_report": lead_bucket_report,
        "paper_validation": paper_validation,
        "live_probe": live_trader.get("live_probe"),
        "archived_variants": _bot_g_archived_variant_summaries(),
        "recent_events": recent_events,
    }


def _bot_g_recent_event_counts(hours: int = 24) -> dict[str, int]:
    """Count notable Bot G research event_types in the last N hours.

    Surfaces Session 243 telemetry (`bot_g.take_profit_shadow_signal`) so the
    operator can see whether the TP@50c shadow path is actually firing without
    needing to grep journals.
    """
    import contextlib

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out: dict[str, int] = {
        "bot_g.take_profit_shadow_signal": 0,
        "bot_g.entry_placed": 0,
    }
    with contextlib.suppress(Exception):
        with _db() as conn:
            rows = conn.execute(
                "SELECT event_type, COUNT(*) AS n FROM events "
                "WHERE created_at >= ? AND event_type IN "
                "('bot_g.take_profit_shadow_signal', 'bot_g.entry_placed') "
                "GROUP BY event_type",
                (_sqlite_dt(cutoff),),
            ).fetchall()
            for row in rows:
                out[str(row["event_type"])] = int(row["n"] or 0)
    return out


def _bot_g_lead_bucket_report_summary() -> dict[str, Any]:
    path = bot_g_lead_bucket_report_path()
    labels = {
        "bot_g_prime_live": "Live",
        "bot_g_prime_live_maker": "Maker live shadow",
        "bot_g_prime": "Paper 4c-8c",
        "bot_g_prime_maker": "Maker paper 4c-8c",
        "bot_g_prime_shadow": "Paper live mirror",
        "bot_g_prime_high_tail": "Paper high tail",
        "bot_g_prime_late_cheap": "Paper late cheap",
        "bot_g_prime_take_profit": "Paper take profit",
    }
    try:
        raw = json.loads(path.read_text())
        overall = raw.get("overall") or {}
        rows = []
        for bot_id, label in labels.items():
            row = overall.get(bot_id) or {}
            rows.append(
                {
                    "bot_id": bot_id,
                    "label": label,
                    "orders": int(row.get("n_orders") or 0),
                    "fills": int(row.get("n_fills") or 0),
                    "resolved": int(row.get("n_resolved") or 0),
                    "won": int(row.get("won") or 0),
                    "lost": int(row.get("lost") or 0),
                    "pnl_usd": row.get("realized_pnl_usd"),
                    "roi_pct": row.get("roi_pct"),
                    "roi_ex_largest_two_pct": row.get("roi_ex_largest_two_pct"),
                    "win_rate_pct": row.get("win_rate_pct"),
                }
            )
        return {
            "available": True,
            "path": str(path),
            "generated_at": raw.get("generated_at"),
            "cutoff": raw.get("cutoff"),
            "rows": rows,
            "overall": overall,
        }
    except FileNotFoundError:
        return {
            "available": False,
            "path": str(path),
            "error": "lead-bucket report has not run yet",
            "rows": [
                {
                    "bot_id": bot_id,
                    "label": label,
                    "orders": 0,
                    "fills": 0,
                    "resolved": 0,
                    "won": 0,
                    "lost": 0,
                    "pnl_usd": None,
                    "roi_pct": None,
                    "roi_ex_largest_two_pct": None,
                    "win_rate_pct": None,
                }
                for bot_id, label in labels.items()
            ],
        }
    except Exception as exc:
        return {"available": False, "path": str(path), "error": str(exc)[:200], "rows": []}


def _merge_vps_bot_g_report_rows(
    report: dict[str, Any],
    *,
    services: dict[str, str],
    vps_bot_g: dict[str, Any],
) -> None:
    """Refresh migrated Bot G rows with the minute-level VPS status counts."""
    if report.get("available"):
        return
    rows = report.get("rows")
    if not isinstance(rows, list):
        return
    trade_metrics = (
        vps_bot_g.get("trade_metrics") if isinstance(vps_bot_g.get("trade_metrics"), dict) else {}
    )
    order_metrics = (
        vps_bot_g.get("order_metrics") if isinstance(vps_bot_g.get("order_metrics"), dict) else {}
    )
    if not trade_metrics or not order_metrics:
        return
    touched = False
    for row in rows:
        if not isinstance(row, dict):
            continue
        bot_id = str(row.get("bot_id") or "")
        if not _vps_bot_g_is_remote(bot_id, services, vps_bot_g):
            continue
        trades = trade_metrics.get(bot_id)
        orders = order_metrics.get(bot_id)
        if not isinstance(trades, dict) or not isinstance(orders, dict):
            continue
        if int(row.get("orders") or 0) >= int(orders.get("total_orders") or 0):
            continue
        closed = int(trades.get("closed_trades") or 0)
        wins = int(trades.get("wins") or 0)
        entry_cost = float(trades.get("entry_cost_usd") or 0)
        pnl = round(float(trades.get("realised_pnl_usd") or 0), 2)
        row.update(
            {
                "orders": int(orders.get("total_orders") or 0),
                "fills": int(trades.get("filled_trades_count") or 0),
                "resolved": closed,
                "won": wins,
                "lost": max(0, closed - wins),
                "pnl_usd": pnl,
                "roi_pct": round((pnl / entry_cost) * 100, 2) if entry_cost else None,
                "data_source": "vps_status",
            }
        )
        touched = True
    if touched:
        report["available"] = True
        report["data_source"] = "vps_status"


def _bot_g_research_shadow_summary(
    spec: dict[str, Any],
    *,
    services: dict[str, str],
    halted_ids: set[str],
    lead_bucket_report: dict[str, Any],
) -> dict[str, Any]:
    bot_id = str(spec["bot_id"])
    purpose = {
        "bot_g_prime_shadow": "Paper mirror of the current live lane.",
        "bot_g_prime_live_maker": "Maker paper mirror of the current live lane.",
        "bot_g_prime_maker": "Maker paper mirror of Bot G Prime.",
        "bot_g_prime_high_tail": "Paper 6c-8c high-tail benchmark across BTC/ETH/SOL/XRP/DOGE.",
        "bot_g_prime_late_cheap": "Paper test of the replay-favoured 1c-3c near-close lane.",
        "bot_g_prime_take_profit": "Paper test of selling spikes before resolution.",
    }.get(bot_id, "Paper parameter research lane.")
    band = {
        "bot_g_prime_shadow": "3.5c-5.5c",
        "bot_g_prime_live_maker": "6c-8c",
        "bot_g_prime_maker": "4c-8c",
        "bot_g_prime_high_tail": "6c-8c",
        "bot_g_prime_late_cheap": "1c-3c",
        "bot_g_prime_take_profit": "3.5c-5.5c",
    }.get(bot_id, "unknown")
    window = {
        "bot_g_prime_shadow": "60s",
        "bot_g_prime_live_maker": "45s",
        "bot_g_prime_maker": "60s",
        "bot_g_prime_high_tail": "45s",
        "bot_g_prime_late_cheap": "30s",
        "bot_g_prime_take_profit": "60s entry, 25s-8s exit",
    }.get(bot_id, "unknown")
    simple = _bot_simple_summary(spec, services=services, halted_ids=halted_ids)
    vps_bot_g = _vps_bot_g_summary()
    vps_runtime_state = (
        vps_bot_g.get("runtime_state") if isinstance(vps_bot_g.get("runtime_state"), dict) else {}
    )
    use_vps = any(
        services.get(str(service)) == "vps:active" for service in spec.get("services", ())
    ) and bot_id in (vps_bot_g.get("bot_ids") or [])
    runtime_state = (
        {**_bot_g_runtime_state_summary(bot_id), **vps_runtime_state.get(bot_id, {})}
        if use_vps
        else _bot_g_runtime_state_summary(bot_id)
    )
    if use_vps and _summary_needs_vps_bot_g_metrics(simple, vps_bot_g):
        _apply_vps_bot_g_simple_metrics(simple, vps_bot_g)
    vps_trade_metrics = (
        vps_bot_g.get("trade_metrics") if isinstance(vps_bot_g.get("trade_metrics"), dict) else {}
    )
    vps_order_metrics = (
        vps_bot_g.get("order_metrics") if isinstance(vps_bot_g.get("order_metrics"), dict) else {}
    )
    vps_recent_orders = (
        vps_bot_g.get("recent_orders") if isinstance(vps_bot_g.get("recent_orders"), dict) else {}
    )
    vps_positions_open = (
        vps_bot_g.get("positions_open") if isinstance(vps_bot_g.get("positions_open"), dict) else {}
    )
    vps_paper_pnl = (
        vps_bot_g.get("paper_pnl") if isinstance(vps_bot_g.get("paper_pnl"), dict) else {}
    )
    report_row = next(
        (row for row in lead_bucket_report.get("rows", []) if row.get("bot_id") == bot_id),
        {},
    )
    return {
        "bot_id": bot_id,
        "label": spec.get("label") or bot_id,
        "purpose": purpose,
        "band": band,
        "window": window,
        "symbols": "BTC,ETH,SOL,XRP,DOGE" if bot_id == "bot_g_prime_high_tail" else "BTC,ETH,SOL",
        "simple": simple,
        "runtime_state": runtime_state,
        "data_source": "vps" if use_vps else "the bot container",
        "trade_metrics": vps_trade_metrics.get(bot_id, {}) if use_vps else _trade_metrics(bot_id),
        "order_metrics": vps_order_metrics.get(bot_id, {}) if use_vps else _order_metrics(bot_id),
        "orders_recent": vps_recent_orders.get(bot_id, []) if use_vps else [],
        "positions_open": vps_positions_open.get(bot_id, []) if use_vps else [],
        "paper_pnl": vps_paper_pnl.get(bot_id, _paper_pnl(bot_id))
        if use_vps
        else _paper_pnl(bot_id),
        "report": report_row,
    }


def _vps_bot_g_summary() -> dict[str, Any]:
    vps = _load_vps_node_status()
    if not vps.get("ok"):
        return {}
    bot_g = vps.get("bot_g")
    return bot_g if isinstance(bot_g, dict) else {}


def _vps_bot_d_spike_summary() -> dict[str, Any]:
    vps = _load_vps_node_status()
    if not vps.get("ok"):
        return {}
    bot_d_spike = vps.get("bot_d_spike")
    return bot_d_spike if isinstance(bot_d_spike, dict) else {}


def _vps_bot_d_spike_short_summary() -> dict[str, Any]:
    vps = _load_vps_node_status()
    if not vps.get("ok"):
        return {}
    spike_short = vps.get("bot_d_spike_short")
    return spike_short if isinstance(spike_short, dict) else {}


def _vps_bot_h_maker_v2_summary() -> dict[str, Any]:
    vps = _load_vps_node_status()
    if not vps.get("ok"):
        return {}
    bot_h = vps.get("bot_h_maker_v2")
    return bot_h if isinstance(bot_h, dict) else {}


def _vps_wallet_observer_summary() -> dict[str, Any]:
    vps = _load_vps_node_status()
    if not vps.get("ok"):
        return {}
    wo = vps.get("wallet_observer")
    return wo if isinstance(wo, dict) else {}


def _local_bot_h_maker_v2_summary() -> dict[str, Any]:
    db_path = Path(maker_recorder_db_path())
    if not db_path.exists():
        return {}
    out: dict[str, Any] = {
        "exists": True,
        "size_bytes": db_path.stat().st_size,
        "counts": {},
        "events_24h_total": 0,
        "active_markets": 0,
    }
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=0.2)
        try:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA busy_timeout=200")
            try:
                out["counts"]["markets"] = int(
                    conn.execute("SELECT COUNT(*) FROM markets").fetchone()[0]
                )
            except sqlite3.Error:
                pass
            try:
                row = conn.execute("SELECT COUNT(*) FROM markets WHERE status='ACTIVE'").fetchone()
                out["active_markets"] = int(row[0] or 0) if row else 0
            except sqlite3.Error:
                pass
        finally:
            conn.close()
    except sqlite3.Error as exc:
        out["error"] = str(exc)[:200]
    return out


def _local_bot_h_quote_paper_summary() -> dict[str, Any]:
    try:
        from scripts.vps_node_status import _bot_h_quote_paper_summary
    except Exception as exc:
        return {"error": str(exc)[:200]}
    return _bot_h_quote_paper_summary(Path(maker_recorder_db_path()))


def _local_wallet_observer_summary() -> dict[str, Any]:
    try:
        from scripts.vps_node_status import _wallet_observer_summary
    except Exception as exc:
        return {"error": str(exc)[:200]}
    return _wallet_observer_summary(Path(wallet_observer_db_path()))


def _bot_host_local_db_warning(
    *,
    bot_label: str,
    db_path: Path,
    services: dict[str, str],
    bot_host_service: str,
    use_local: bool,
) -> str | None:
    """Return a warning string if a the bot container unit is active but the local DB
    does not exist. After the ADR-145 migration the dashboard expects the
    local the bot container DB to back the active unit; if the DB is missing the
    `data_source` label silently flips to `vps` (or to `the bot container` with empty
    data) without erroring. Surface that mismatch as `data_source_warning`.
    """
    if use_local:
        return None
    state = str(services.get(bot_host_service, "")).lower()
    # Only fire when the unit is locally active on the bot container. VPS-bridge-active
    # states (`vps:active`) and inactive/unknown states are not a misconfig.
    if state != "active" and state != "timer:active":
        return None
    return (
        f"{bot_label}: the bot container unit '{bot_host_service}' is {state}, but local DB "
        f"at {db_path} is missing. Dashboard fell back to the VPS bridge — "
        "verify the the bot container DB path and env overrides."
    )


def query_bot_h() -> dict[str, Any]:
    """Bot H Maker V2 Phase 1 recorder dashboard payload (paper-only,
    ADR-134). Reads the bot container after the Session 304 migration and falls back to
    the VPS status bridge while the old VPS service is still active.
    """
    services = service_states()
    halted_ids = _halted_bot_ids()
    spec = _spec_for("bot_h_maker_v2")
    simple = _bot_simple_summary(spec, services=services, halted_ids=halted_ids)
    local_summary = _local_bot_h_maker_v2_summary()
    vps_summary = _vps_bot_h_maker_v2_summary()
    use_local = bool(local_summary.get("exists"))
    summary = local_summary if use_local else vps_summary
    warning = _bot_host_local_db_warning(
        bot_label="bot_h_maker_v2",
        db_path=Path(maker_recorder_db_path()),
        services=services,
        bot_host_service="polymarket-bot-h-maker-v2-recorder",
        use_local=use_local,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bot_id": "bot_h_maker_v2",
        "label": spec.get("label") or "Maker Flow Recorder (H paper)",
        "simple": simple,
        "data_source": "the bot container" if use_local else ("vps" if vps_summary else "the bot container"),
        "data_source_warning": warning,
        "phase": "1_recorder",
        "mode": "paper",
        "active_quote_cells": [
            {
                "label": "politics_0_10c",
                "category": "politics",
                "price_min": 0.00,
                "price_max": 0.10,
            },
            {"label": "sports_10_20c", "category": "sports", "price_min": 0.10, "price_max": 0.20},
        ],
        "recorder_filter": {
            "categories": ["politics", "sports", "awards", "crypto"],
            "price_min": 0.01,
            "price_max": 0.50,
            "volume_floor_usd": 1000,
        },
        "recorder": summary,
        "vps_configured": bool(vps_summary),
    }


def query_wallet_observer() -> dict[str, Any]:
    """Wallet Observer dashboard payload (passive Polygon CTF Exchange
    recorder for the 245 retail-tier wallets, ADR-137). Reads the bot container after
    the Session 304 migration and falls back to the VPS status bridge while
    the old VPS service is still active.
    """
    services = service_states()
    halted_ids = _halted_bot_ids()
    spec = _spec_for("wallet_observer")
    simple = _bot_simple_summary(spec, services=services, halted_ids=halted_ids)
    local_summary = _local_wallet_observer_summary()
    vps_summary = _vps_wallet_observer_summary()
    use_local = bool(local_summary.get("exists"))
    summary = local_summary if use_local else vps_summary
    warning = _bot_host_local_db_warning(
        bot_label="wallet_observer",
        db_path=Path(wallet_observer_db_path()),
        services=services,
        bot_host_service="polymarket-wallet-observer",
        use_local=use_local,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bot_id": "wallet_observer",
        "label": spec.get("label") or "Wallet Observer",
        "simple": simple,
        "data_source": "the bot container" if use_local else ("vps" if vps_summary else "the bot container"),
        "data_source_warning": warning,
        "mode": "passive",
        "wallet_count": 245,
        "tiers": ["A_human_profitable", "B_unknown_profitable"],
        "summary": summary,
        "vps_configured": bool(vps_summary),
    }


def _bot_g_paper_validation_summary() -> dict[str, Any]:
    """Dashboard-facing Bot G Prime validation read."""
    try:
        from scripts.bot_g_feature_analysis import (
            fetch_entry_events,
            fetch_trades,
            fifo_match,
            live_candidate_gate,
            live_transfer_summary,
            validation_splits,
        )

        with _db() as db:
            trades = fetch_trades(db, bot_ids=("bot_g_prime",))
            entry_events = fetch_entry_events(db)
            closed = fifo_match(trades, entry_events=entry_events, con=db)
            latest_entry = _latest_bot_g_entry_telemetry(db)
            live_transfer = live_transfer_summary(db, closed)
        splits = validation_splits(closed)
        gate = live_candidate_gate(splits)
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc)[:200],
            "posture": "paper_only",
            "collection_band": "4c-8c",
            "positive_signal_band": "4c-5c",
            "live_ready": False,
        }
    return {
        "available": True,
        "posture": "paper_only",
        "collection_band": "4c-8c",
        "positive_signal_band": "4c-5c",
        "live_candidate_gate": gate,
        "live_ready": gate["live_ready"],
        "read": (
            "4c-8c stays open for paper data collection. Only 4c-5c has "
            "positive signal; 5c-8c is not a live-promotion cohort."
        ),
        "live_transfer": live_transfer,
        "latest_entry_telemetry": latest_entry,
        "splits": splits,
    }


def _bot_g_runtime_state_summary(bot_id: str = "bot_g_prime") -> dict[str, Any]:
    fallback = {
        "available": False,
        "source": "dashboard_env",
        "bot_env": os.environ.get("BOT_G_ENV", "paper"),
        "bot_dry_run": os.environ.get("BOT_G_DRY_RUN", "true").lower() == "true",
        "global_polymarket_env": current_mode(),
        "paper_override": os.environ.get("BOT_G_ENV", "paper") != "live"
        or os.environ.get("BOT_G_DRY_RUN", "true").lower() == "true",
        "effective_paper": True,
        "live_intent": False,
        "live_approved_at": os.environ.get("BOT_G_LIVE_APPROVED_AT", ""),
        "live_wallet_usd": os.environ.get("BOT_G_LIVE_WALLET_USD", "200"),
    }
    fallback["live_intent"] = str(fallback["bot_env"]).lower() == "live" and not bool(
        fallback["bot_dry_run"]
    )
    fallback["effective_paper"] = (
        bool(fallback["paper_override"]) or str(fallback["global_polymarket_env"]).lower() != "live"
    )
    try:
        with _db() as db:
            row = db.execute(
                """
                SELECT created_at, payload
                FROM events
                WHERE bot_id = ?
                  AND event_type = 'bot_g.runtime_state'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (bot_id,),
            ).fetchone()
        if row is None:
            return fallback
        payload = json.loads(row["payload"] or "{}")
        return {
            **fallback,
            "available": True,
            "source": "trader_event",
            "created_at": row["created_at"],
            "bot_env": payload.get("bot_env", fallback["bot_env"]),
            "bot_dry_run": bool(payload.get("bot_dry_run", fallback["bot_dry_run"])),
            "global_polymarket_env": payload.get(
                "global_polymarket_env",
                fallback["global_polymarket_env"],
            ),
            "paper_override": bool(payload.get("paper_override", fallback["paper_override"])),
            "effective_paper": bool(payload.get("effective_paper", fallback["effective_paper"])),
            "live_intent": bool(payload.get("live_intent", fallback["live_intent"])),
            "live_approved_at": payload.get(
                "live_approved_at",
                fallback["live_approved_at"],
            ),
            "fixed_trade_usd": payload.get("fixed_trade_usd"),
            "live_max_daily_entries": payload.get("live_max_daily_entries"),
            "live_max_concurrent_positions": payload.get("live_max_concurrent_positions"),
            "live_max_daily_gross_notional_usd": payload.get("live_max_daily_gross_notional_usd"),
            "live_wallet_usd": payload.get("live_wallet_usd", fallback["live_wallet_usd"]),
        }
    except Exception as exc:
        return {**fallback, "error": str(exc)[:200]}


def _latest_bot_g_entry_telemetry(db: sqlite3.Connection) -> dict[str, Any]:
    try:
        cols = {str(row[1]) for row in db.execute("PRAGMA table_info(events)")}
        if "payload" not in cols:
            return {"available": False, "has_capacity_depth": False}
        row = db.execute(
            """
            SELECT created_at, payload
            FROM events
            WHERE bot_id='bot_g_prime'
              AND event_type='bot_g.entry_placed'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
    except Exception:
        return {"available": False, "has_capacity_depth": False}
    if row is None:
        return {"available": False, "has_capacity_depth": False}
    try:
        payload = json.loads(row["payload"] or "{}")
    except Exception:
        payload = {}
    cap = payload.get("capacity_depth")
    return {
        "available": True,
        "created_at": row["created_at"],
        "has_capacity_depth": isinstance(cap, dict),
        "depth_ticks": sorted(cap.keys()) if isinstance(cap, dict) else [],
    }


def _bot_g_prime_pnl_breakdown(
    since: datetime,
    *,
    bot_id: str = "bot_g_prime",
) -> dict[str, float] | None:
    """Explain the Bot G card P&L as cash P&L vs closed FIFO P&L."""
    try:
        trade_metrics = _trade_metrics(bot_id, since=since)
        with _db() as db:
            row = db.execute(
                """
                SELECT COALESCE(SUM(COALESCE(cost_basis_usd, 0)), 0) AS open_cost
                FROM positions
                WHERE bot_id=?
                  AND status='OPEN'
                  AND opened_at >= ?
                """,
                (bot_id, _sqlite_dt(since)),
            ).fetchone()
        return {
            "closed_realised_usd": round(float(trade_metrics["realised_pnl_usd"] or 0), 2),
            "open_cost_usd": round(float(row["open_cost"] or 0), 2),
        }
    except Exception:
        return None


def _bot_g_archived_variant_summaries() -> list[dict[str, Any]]:
    """Historical Bot G evidence, recomputed from trades when available.

    The old G variants are archived, but some paper positions can settle after
    archive time. Recompute the round-trip snapshot from the DB so the dashboard
    does not freeze stale kill-switch evidence.
    """
    meta = {
        "bot_g": {
            "label": "Archived raw G",
            "reason": "rolling ROI kill-switch fired",
            "fallback": {"closed": 100, "wins": 3, "pnl_usd": -205.34, "roi_pct": -51.08},
        },
        "bot_g_jackpot": {
            "label": "Archived jackpot",
            "reason": "0 wins in <=3c cohort",
            "fallback": {"closed": 80, "wins": 0, "pnl_usd": -334.56, "roi_pct": -100.0},
        },
        "bot_g_scalp": {
            "label": "Archived scalp",
            "reason": "raw 30s scalp negative; evidence retained for Prime",
            "fallback": {"closed": 83, "wins": 1, "pnl_usd": -250.51, "roi_pct": -71.47},
        },
    }

    metrics: dict[str, dict[str, Decimal | int]] = {
        bot_id: {"closed": 0, "wins": 0, "pnl": Decimal("0"), "cost": Decimal("0")}
        for bot_id in meta
    }
    try:
        with _db() as db:
            rows = db.execute(
                f"""
                SELECT bot_id, token_id, side, price, size
                FROM trades
                WHERE bot_id IN ({",".join("?" for _ in meta)})
                ORDER BY filled_at, trade_id
                """,
                tuple(meta),
            ).fetchall()
    except Exception:
        rows = []

    buys: dict[tuple[str, str], list[dict[str, Decimal]]] = defaultdict(list)
    for row in rows:
        bot_id = str(row["bot_id"])
        side = str(row["side"] or "").upper()
        key = (bot_id, str(row["token_id"]))
        price = Decimal(str(row["price"] or 0))
        size = Decimal(str(row["size"] or 0))
        if side.startswith("BUY"):
            buys[key].append({"price": price, "remaining": size})
            continue
        if not side.startswith("SELL"):
            continue
        remaining = size
        lots = buys.get(key, [])
        while remaining > 0 and lots:
            lot = lots[0]
            match_size = min(remaining, lot["remaining"])
            bot_metrics = metrics[bot_id]
            pnl = (price - lot["price"]) * match_size
            bot_metrics["closed"] = int(bot_metrics["closed"]) + 1
            bot_metrics["wins"] = int(bot_metrics["wins"]) + (1 if price > lot["price"] else 0)
            bot_metrics["pnl"] = Decimal(str(bot_metrics["pnl"])) + pnl
            bot_metrics["cost"] = Decimal(str(bot_metrics["cost"])) + (lot["price"] * match_size)
            lot["remaining"] -= match_size
            remaining -= match_size
            if lot["remaining"] <= 0:
                lots.pop(0)

    out: list[dict[str, Any]] = []
    for bot_id, details in meta.items():
        bot_metrics = metrics[bot_id]
        closed = int(bot_metrics["closed"])
        if closed == 0:
            summary = details["fallback"]
            out.append(
                {
                    "bot_id": bot_id,
                    "label": details["label"],
                    "closed": summary["closed"],
                    "wins": summary["wins"],
                    "pnl_usd": summary["pnl_usd"],
                    "roi_pct": summary["roi_pct"],
                    "reason": details["reason"],
                }
            )
            continue
        pnl = Decimal(str(bot_metrics["pnl"]))
        cost = Decimal(str(bot_metrics["cost"]))
        roi = (pnl / cost * Decimal("100")) if cost else Decimal("0")
        out.append(
            {
                "bot_id": bot_id,
                "label": details["label"],
                "closed": closed,
                "wins": int(bot_metrics["wins"]),
                "pnl_usd": round(float(pnl), 2),
                "roi_pct": round(float(roi), 2),
                "reason": details["reason"],
            }
        )
    return out


def _bot_g_per_mode_breakdown(bot_id: str = "bot_g") -> dict[str, Any]:
    """Aggregate Bot G fills by mode using Event rows.

    bot_g/__main__.py emits Event(type='bot_g.entry_placed', payload.mode=...)
    on every order placement. We join that to Trades to split realised P&L.
    """
    from sqlalchemy import select

    from core.db import Event, Trade, get_session_factory

    sf = get_session_factory()
    out: dict[str, Any] = {
        "prime": {"entries": 0, "closed": 0, "wins": 0, "realised_usd": 0.0},
        "jackpot": {"entries": 0, "closed": 0, "wins": 0, "realised_usd": 0.0},
        "scalp": {"entries": 0, "closed": 0, "wins": 0, "realised_usd": 0.0},
        "unknown": {"entries": 0, "closed": 0, "wins": 0, "realised_usd": 0.0},
    }
    try:
        with sf() as s:
            # order_id → mode from entry events
            events = s.scalars(
                select(Event).where(
                    Event.bot_id == bot_id,
                    Event.event_type == "bot_g.entry_placed",
                )
            ).all()
            order_mode: dict[str, str] = {}
            for ev in events:
                p = ev.payload or {}
                oid = p.get("order_id")
                mode = p.get("mode")
                if oid and mode:
                    order_mode[oid] = mode
                    out.get(mode, out["unknown"])["entries"] += 1
            # Each OPEN position has one BUY trade + maybe a paper-resolve SELL.
            # For per-mode realised, pair BUY.order_id → mode, then look for
            # a matching paper-resolve SELL for the same token_id.
            buys = s.scalars(
                select(Trade).where(
                    Trade.bot_id == bot_id,
                    Trade.side.in_(("BUY", "BUY_YES", "BUY_NO")),
                )
            ).all()
            sells = list(
                s.scalars(
                    select(Trade).where(
                        Trade.bot_id == bot_id,
                        Trade.side == "SELL",
                    )
                ).all()
            )
            for buy in buys:
                mode = order_mode.get(buy.order_id, "unknown")
                bucket = out.get(mode, out["unknown"])
                # Find a SELL for the same token that's after the BUY.
                matching = [
                    t for t in sells if t.token_id == buy.token_id and t.filled_at >= buy.filled_at
                ]
                if not matching:
                    continue
                sell = matching[0]
                cost = float(buy.price) * float(buy.size)
                proceeds = float(sell.price) * float(sell.size)
                pnl = proceeds - cost
                bucket["closed"] += 1
                if pnl > 0:
                    bucket["wins"] += 1
                bucket["realised_usd"] = round(bucket["realised_usd"] + pnl, 2)
            # Derive win rate per mode.
            for mode in out:
                c = out[mode]["closed"]
                c and out[mode].update({"win_rate_pct": round(100 * out[mode]["wins"] / c, 1)})
    except Exception:
        pass
    return out


def _crypto_fair_value_recent_signals(limit: int = 30) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in CRYPTO_FAIR_VALUE_BOT_IDS)
    try:
        with _db() as db:
            rows = db.execute(
                f"""
                SELECT bot_id, created_at, payload
                FROM events
                WHERE bot_id IN ({placeholders})
                  AND event_type='crypto_fair_value.signal'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*CRYPTO_FAIR_VALUE_BOT_IDS, limit),
            ).fetchall()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload"] or "{}")
        except Exception:
            payload = {}
        fill_tracks = payload.get("fill_tracks") or []
        main = next(
            (
                track
                for track in fill_tracks
                if isinstance(track, dict) and track.get("fill_track") == "paper_taker_stressed_1c"
            ),
            {},
        )
        out.append(
            {
                "bot_id": row["bot_id"],
                "created_at": row["created_at"],
                "strategy": payload.get("strategy"),
                "symbol": payload.get("symbol"),
                "duration_minutes": payload.get("duration_minutes"),
                "side": payload.get("side"),
                "ask_price": payload.get("ask_price"),
                "entry_price_1c": main.get("entry_price"),
                "model_edge": payload.get("model_edge"),
                "model_probability_up": payload.get("model_probability_up"),
                "lead_bucket": payload.get("lead_bucket"),
                "question": payload.get("question"),
                "condition_id": payload.get("condition_id"),
            }
        )
    return out


def _crypto_fair_value_event_counts(bot_id: str) -> dict[str, Any]:
    empty = {"signals": 0, "latest_signal_at": None}
    try:
        with _db() as db:
            row = db.execute(
                """
                SELECT COUNT(*) AS n, MAX(created_at) AS latest
                FROM events
                WHERE bot_id=?
                  AND event_type='crypto_fair_value.signal'
                """,
                (bot_id,),
            ).fetchone()
        return {
            "signals": int(row["n"] or 0),
            "latest_signal_at": row["latest"],
        }
    except Exception:
        return empty


def _crypto_fair_value_track_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("bot_id") or ""), str(row.get("fill_track") or ""))
        bucket = buckets.setdefault(
            key,
            {
                "bot_id": key[0],
                "fill_track": key[1],
                "signals": 0,
                "simulated_fills": 0,
                "closed_positions": 0,
                "wins": 0,
                "fee_stressed_pnl": 0.0,
                "weighted_roi": 0.0,
            },
        )
        signals = int(row.get("signals") or 0)
        closed = int(row.get("closed_positions") or 0)
        bucket["signals"] += signals
        bucket["simulated_fills"] += int(row.get("simulated_fills") or 0)
        bucket["closed_positions"] += closed
        bucket["wins"] += int(row.get("wins") or 0)
        bucket["fee_stressed_pnl"] += float(row.get("fee_stressed_pnl") or 0.0)
        bucket["weighted_roi"] += float(row.get("raw_roi") or 0.0) * closed
    out: list[dict[str, Any]] = []
    for bucket in buckets.values():
        closed = int(bucket["closed_positions"] or 0)
        signals = int(bucket["signals"] or 0)
        fills = int(bucket["simulated_fills"] or 0)
        bucket["raw_roi"] = bucket["weighted_roi"] / closed if closed else 0.0
        bucket["hit_rate"] = int(bucket["wins"] or 0) / closed if closed else 0.0
        bucket["fill_rate"] = fills / signals if signals else 0.0
        bucket["fee_stressed_pnl"] = round(float(bucket["fee_stressed_pnl"]), 2)
        del bucket["weighted_roi"]
        out.append(bucket)
    return sorted(out, key=lambda item: (item["bot_id"], item["fill_track"]))


def _vps_crypto_fair_value_summary() -> dict[str, Any]:
    vps = _load_vps_node_status()
    if not vps.get("ok"):
        return {}
    crypto = vps.get("crypto_fair_value")
    return crypto if isinstance(crypto, dict) else {}


def _vps_bot_g_summary() -> dict[str, Any]:
    vps = _load_vps_node_status()
    if not vps.get("ok"):
        return {}
    bot_g = vps.get("bot_g")
    return bot_g if isinstance(bot_g, dict) else {}


def _vps_bot_d_spike_summary() -> dict[str, Any]:
    vps = _load_vps_node_status()
    if not vps.get("ok"):
        return {}
    bot_d_spike = vps.get("bot_d_spike")
    return bot_d_spike if isinstance(bot_d_spike, dict) else {}


def query_crypto_fair_value() -> dict[str, Any]:
    """Crypto fair-value paper-live lanes over the shared recorder tape."""
    services = service_states()
    halted_ids = _halted_bot_ids()
    vps_crypto = _vps_crypto_fair_value_summary()
    specs = [_spec_for(bot_id) for bot_id in CRYPTO_FAIR_VALUE_BOT_IDS]
    fleet_bots = [
        _bot_simple_summary(spec, services=services, halted_ids=halted_ids) for spec in specs
    ]
    report_error = None
    try:
        report = build_crypto_fv_report(
            db_path=Path(main_db_path()),
            bot_ids=CRYPTO_FAIR_VALUE_BOT_IDS,
            since=datetime.now(UTC) - timedelta(days=7),
        )
    except Exception as exc:
        report_error = str(exc)[:200]
        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "scan_counts": {},
            "rows": [],
        }

    lanes: list[dict[str, Any]] = []
    vps_scan_counts = (
        vps_crypto.get("scan_counts") if isinstance(vps_crypto.get("scan_counts"), dict) else {}
    )
    vps_event_counts = (
        vps_crypto.get("event_counts") if isinstance(vps_crypto.get("event_counts"), dict) else {}
    )
    vps_trade_metrics = (
        vps_crypto.get("trade_metrics") if isinstance(vps_crypto.get("trade_metrics"), dict) else {}
    )
    vps_order_metrics = (
        vps_crypto.get("order_metrics") if isinstance(vps_crypto.get("order_metrics"), dict) else {}
    )
    vps_open_positions = (
        vps_crypto.get("open_positions")
        if isinstance(vps_crypto.get("open_positions"), dict)
        else {}
    )
    for bot in fleet_bots:
        bot_id = str(bot["bot_id"])
        local_counts = _crypto_fair_value_event_counts(bot_id)
        use_vps = (
            any(str(state) == "vps:active" for state in (bot.get("services") or {}).values())
            and bot_id in vps_event_counts
        )
        counts = vps_event_counts.get(bot_id, local_counts) if use_vps else local_counts
        scan_counts = (
            vps_scan_counts.get(bot_id, {})
            if use_vps
            else report.get("scan_counts", {}).get(bot_id, {})
        )
        trade_metrics = (
            vps_trade_metrics.get(bot_id, _trade_metrics(bot_id))
            if use_vps
            else _trade_metrics(bot_id)
        )
        order_metrics = (
            vps_order_metrics.get(bot_id, _order_metrics(bot_id))
            if use_vps
            else _order_metrics(bot_id)
        )
        lanes.append(
            {
                **bot,
                "mode": "paper-live",
                "posture": "live data, paper ledger only",
                "signals": counts["signals"],
                "latest_signal_at": counts["latest_signal_at"],
                "latest_scan_at": counts.get("latest_scan_at"),
                "scan_summaries": counts.get("scan_summaries"),
                "scan_counts": scan_counts,
                "trade_metrics": trade_metrics,
                "order_metrics": order_metrics,
                "orders": [] if use_vps else _orders_for(bot_id, limit=15),
                "positions": [] if use_vps else _positions_for(bot_id),
                "recent_trades": trade_metrics.get("recent_trades", [])
                if use_vps
                else _recent_trades(limit=15, bot_id=bot_id),
                "open_positions": int(vps_open_positions.get(bot_id, 0))
                if use_vps
                else bot.get("open_positions", 0),
                "data_source": "vps" if use_vps else "the bot container",
            }
        )

    rows = list(report.get("rows") or [])
    rows.sort(
        key=lambda row: (
            int(row.get("closed_positions") or 0),
            int(row.get("signals") or 0),
        ),
        reverse=True,
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "posture": {
            "label": "paper-live",
            "reads_live_data": True,
            "writes_live_orders": False,
            "uses_wallet": False,
            "main_ledger_track": "paper_taker_stressed_1c",
            "note": (
                "Watches live recorder/book/CEX data and writes simulated "
                "paper orders, fills, and positions only."
            ),
        },
        "bot_ids": list(CRYPTO_FAIR_VALUE_BOT_IDS),
        "fleet_bots": fleet_bots,
        "lanes": lanes,
        "track_summary": _crypto_fair_value_track_summary(rows),
        "report": {
            "available": report_error is None,
            "error": report_error,
            "generated_at": report.get("generated_at"),
            "scan_counts": vps_scan_counts if vps_scan_counts else report.get("scan_counts", {}),
            "rows": rows[:80],
        },
        "recent_signals": (
            vps_crypto.get("recent_signals", [])
            if isinstance(vps_crypto.get("recent_signals"), list)
            and vps_crypto.get("recent_signals")
            else _crypto_fair_value_recent_signals(limit=30)
        ),
    }


def _bot_g_paper_validation_summary() -> dict[str, Any]:
    """Dashboard-facing Bot G Prime validation read."""
    try:
        from scripts.bot_g_feature_analysis import (
            fetch_entry_events,
            fetch_trades,
            fifo_match,
            live_candidate_gate,
            live_transfer_summary,
            validation_splits,
        )

        with _db() as db:
            trades = fetch_trades(db, bot_ids=("bot_g_prime",))
            entry_events = fetch_entry_events(db)
            closed = fifo_match(trades, entry_events=entry_events, con=db)
            latest_entry = _latest_bot_g_entry_telemetry(db)
            live_transfer = live_transfer_summary(db, closed)
        splits = validation_splits(closed)
        gate = live_candidate_gate(splits)
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc)[:200],
            "posture": "paper_only",
            "collection_band": "4c-8c",
            "positive_signal_band": "4c-5c",
            "live_ready": False,
        }
    return {
        "available": True,
        "posture": "paper_only",
        "collection_band": "4c-8c",
        "positive_signal_band": "4c-5c",
        "live_candidate_gate": gate,
        "live_ready": gate["live_ready"],
        "read": (
            "4c-8c stays open for paper data collection. Only 4c-5c has "
            "positive signal; 5c-8c is not a live-promotion cohort."
        ),
        "live_transfer": live_transfer,
        "latest_entry_telemetry": latest_entry,
        "splits": splits,
    }


def _bot_g_runtime_state_summary(bot_id: str = "bot_g_prime") -> dict[str, Any]:
    fallback = {
        "available": False,
        "source": "dashboard_env",
        "bot_env": os.environ.get("BOT_G_ENV", "paper"),
        "bot_dry_run": os.environ.get("BOT_G_DRY_RUN", "true").lower() == "true",
        "global_polymarket_env": current_mode(),
        "paper_override": os.environ.get("BOT_G_ENV", "paper") != "live"
        or os.environ.get("BOT_G_DRY_RUN", "true").lower() == "true",
        "effective_paper": True,
        "live_intent": False,
        "live_approved_at": os.environ.get("BOT_G_LIVE_APPROVED_AT", ""),
        "live_wallet_usd": os.environ.get("BOT_G_LIVE_WALLET_USD", "200"),
    }
    fallback["live_intent"] = str(fallback["bot_env"]).lower() == "live" and not bool(
        fallback["bot_dry_run"]
    )
    fallback["effective_paper"] = (
        bool(fallback["paper_override"]) or str(fallback["global_polymarket_env"]).lower() != "live"
    )
    try:
        with _db() as db:
            row = db.execute(
                """
                SELECT created_at, payload
                FROM events
                WHERE bot_id = ?
                  AND event_type = 'bot_g.runtime_state'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (bot_id,),
            ).fetchone()
        if row is None:
            return fallback
        payload = json.loads(row["payload"] or "{}")
        return {
            **fallback,
            "available": True,
            "source": "trader_event",
            "created_at": row["created_at"],
            "bot_env": payload.get("bot_env", fallback["bot_env"]),
            "bot_dry_run": bool(payload.get("bot_dry_run", fallback["bot_dry_run"])),
            "global_polymarket_env": payload.get(
                "global_polymarket_env",
                fallback["global_polymarket_env"],
            ),
            "paper_override": bool(payload.get("paper_override", fallback["paper_override"])),
            "effective_paper": bool(payload.get("effective_paper", fallback["effective_paper"])),
            "live_intent": bool(payload.get("live_intent", fallback["live_intent"])),
            "live_approved_at": payload.get(
                "live_approved_at",
                fallback["live_approved_at"],
            ),
            "fixed_trade_usd": payload.get("fixed_trade_usd"),
            "live_max_daily_entries": payload.get("live_max_daily_entries"),
            "live_max_concurrent_positions": payload.get("live_max_concurrent_positions"),
            "live_max_daily_gross_notional_usd": payload.get("live_max_daily_gross_notional_usd"),
            "live_wallet_usd": payload.get("live_wallet_usd", fallback["live_wallet_usd"]),
        }
    except Exception as exc:
        return {**fallback, "error": str(exc)[:200]}


def _latest_bot_g_entry_telemetry(db: sqlite3.Connection) -> dict[str, Any]:
    try:
        cols = {str(row[1]) for row in db.execute("PRAGMA table_info(events)")}
        if "payload" not in cols:
            return {"available": False, "has_capacity_depth": False}
        row = db.execute(
            """
            SELECT created_at, payload
            FROM events
            WHERE bot_id='bot_g_prime'
              AND event_type='bot_g.entry_placed'
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).fetchone()
    except Exception:
        return {"available": False, "has_capacity_depth": False}
    if row is None:
        return {"available": False, "has_capacity_depth": False}
    try:
        payload = json.loads(row["payload"] or "{}")
    except Exception:
        payload = {}
    cap = payload.get("capacity_depth")
    return {
        "available": True,
        "created_at": row["created_at"],
        "has_capacity_depth": isinstance(cap, dict),
        "depth_ticks": sorted(cap.keys()) if isinstance(cap, dict) else [],
    }


def _bot_g_prime_pnl_breakdown(
    since: datetime,
    *,
    bot_id: str = "bot_g_prime",
) -> dict[str, float] | None:
    """Explain the Bot G card P&L as cash P&L vs closed FIFO P&L."""
    try:
        trade_metrics = _trade_metrics(bot_id, since=since)
        with _db() as db:
            row = db.execute(
                """
                SELECT COALESCE(SUM(COALESCE(cost_basis_usd, 0)), 0) AS open_cost
                FROM positions
                WHERE bot_id=?
                  AND status='OPEN'
                  AND opened_at >= ?
                """,
                (bot_id, _sqlite_dt(since)),
            ).fetchone()
        return {
            "closed_realised_usd": round(float(trade_metrics["realised_pnl_usd"] or 0), 2),
            "open_cost_usd": round(float(row["open_cost"] or 0), 2),
        }
    except Exception:
        return None


def _bot_g_archived_variant_summaries() -> list[dict[str, Any]]:
    """Historical Bot G evidence, recomputed from trades when available.

    The old G variants are archived, but some paper positions can settle after
    archive time. Recompute the round-trip snapshot from the DB so the dashboard
    does not freeze stale kill-switch evidence.
    """
    meta = {
        "bot_g": {
            "label": "Archived raw G",
            "reason": "rolling ROI kill-switch fired",
            "fallback": {"closed": 100, "wins": 3, "pnl_usd": -205.34, "roi_pct": -51.08},
        },
        "bot_g_jackpot": {
            "label": "Archived jackpot",
            "reason": "0 wins in <=3c cohort",
            "fallback": {"closed": 80, "wins": 0, "pnl_usd": -334.56, "roi_pct": -100.0},
        },
        "bot_g_scalp": {
            "label": "Archived scalp",
            "reason": "raw 30s scalp negative; evidence retained for Prime",
            "fallback": {"closed": 83, "wins": 1, "pnl_usd": -250.51, "roi_pct": -71.47},
        },
    }

    metrics: dict[str, dict[str, Decimal | int]] = {
        bot_id: {"closed": 0, "wins": 0, "pnl": Decimal("0"), "cost": Decimal("0")}
        for bot_id in meta
    }
    try:
        with _db() as db:
            rows = db.execute(
                f"""
                SELECT bot_id, token_id, side, price, size
                FROM trades
                WHERE bot_id IN ({",".join("?" for _ in meta)})
                ORDER BY filled_at, trade_id
                """,
                tuple(meta),
            ).fetchall()
    except Exception:
        rows = []

    buys: dict[tuple[str, str], list[dict[str, Decimal]]] = defaultdict(list)
    for row in rows:
        bot_id = str(row["bot_id"])
        side = str(row["side"] or "").upper()
        key = (bot_id, str(row["token_id"]))
        price = Decimal(str(row["price"] or 0))
        size = Decimal(str(row["size"] or 0))
        if side.startswith("BUY"):
            buys[key].append({"price": price, "remaining": size})
            continue
        if not side.startswith("SELL"):
            continue
        remaining = size
        lots = buys.get(key, [])
        while remaining > 0 and lots:
            lot = lots[0]
            match_size = min(remaining, lot["remaining"])
            bot_metrics = metrics[bot_id]
            pnl = (price - lot["price"]) * match_size
            bot_metrics["closed"] = int(bot_metrics["closed"]) + 1
            bot_metrics["wins"] = int(bot_metrics["wins"]) + (1 if price > lot["price"] else 0)
            bot_metrics["pnl"] = Decimal(str(bot_metrics["pnl"])) + pnl
            bot_metrics["cost"] = Decimal(str(bot_metrics["cost"])) + (lot["price"] * match_size)
            lot["remaining"] -= match_size
            remaining -= match_size
            if lot["remaining"] <= 0:
                lots.pop(0)

    out: list[dict[str, Any]] = []
    for bot_id, details in meta.items():
        bot_metrics = metrics[bot_id]
        closed = int(bot_metrics["closed"])
        if closed == 0:
            summary = details["fallback"]
            out.append(
                {
                    "bot_id": bot_id,
                    "label": details["label"],
                    "closed": summary["closed"],
                    "wins": summary["wins"],
                    "pnl_usd": summary["pnl_usd"],
                    "roi_pct": summary["roi_pct"],
                    "reason": details["reason"],
                }
            )
            continue
        pnl = Decimal(str(bot_metrics["pnl"]))
        cost = Decimal(str(bot_metrics["cost"]))
        roi = (pnl / cost * Decimal("100")) if cost else Decimal("0")
        out.append(
            {
                "bot_id": bot_id,
                "label": details["label"],
                "closed": closed,
                "wins": int(bot_metrics["wins"]),
                "pnl_usd": round(float(pnl), 2),
                "roi_pct": round(float(roi), 2),
                "reason": details["reason"],
            }
        )
    return out


def _bot_g_per_mode_breakdown(bot_id: str = "bot_g") -> dict[str, Any]:
    """Aggregate Bot G fills by mode using Event rows.

    bot_g/__main__.py emits Event(type='bot_g.entry_placed', payload.mode=...)
    on every order placement. We join that to Trades to split realised P&L.
    """
    from sqlalchemy import select

    from core.db import Event, Trade, get_session_factory

    sf = get_session_factory()
    out: dict[str, Any] = {
        "prime": {"entries": 0, "closed": 0, "wins": 0, "realised_usd": 0.0},
        "jackpot": {"entries": 0, "closed": 0, "wins": 0, "realised_usd": 0.0},
        "scalp": {"entries": 0, "closed": 0, "wins": 0, "realised_usd": 0.0},
        "unknown": {"entries": 0, "closed": 0, "wins": 0, "realised_usd": 0.0},
    }
    try:
        with sf() as s:
            # order_id → mode from entry events
            events = s.scalars(
                select(Event).where(
                    Event.bot_id == bot_id,
                    Event.event_type == "bot_g.entry_placed",
                )
            ).all()
            order_mode: dict[str, str] = {}
            for ev in events:
                p = ev.payload or {}
                oid = p.get("order_id")
                mode = p.get("mode")
                if oid and mode:
                    order_mode[oid] = mode
                    out.get(mode, out["unknown"])["entries"] += 1
            # Each OPEN position has one BUY trade + maybe a paper-resolve SELL.
            # For per-mode realised, pair BUY.order_id → mode, then look for
            # a matching paper-resolve SELL for the same token_id.
            buys = s.scalars(
                select(Trade).where(
                    Trade.bot_id == bot_id,
                    Trade.side.in_(("BUY", "BUY_YES", "BUY_NO")),
                )
            ).all()
            sells = list(
                s.scalars(
                    select(Trade).where(
                        Trade.bot_id == bot_id,
                        Trade.side == "SELL",
                    )
                ).all()
            )
            for buy in buys:
                mode = order_mode.get(buy.order_id, "unknown")
                bucket = out.get(mode, out["unknown"])
                # Find a SELL for the same token that's after the BUY.
                matching = [
                    t for t in sells if t.token_id == buy.token_id and t.filled_at >= buy.filled_at
                ]
                if not matching:
                    continue
                sell = matching[0]
                cost = float(buy.price) * float(buy.size)
                proceeds = float(sell.price) * float(sell.size)
                pnl = proceeds - cost
                bucket["closed"] += 1
                if pnl > 0:
                    bucket["wins"] += 1
                bucket["realised_usd"] = round(bucket["realised_usd"] + pnl, 2)
            # Derive win rate per mode.
            for mode in out:
                c = out[mode]["closed"]
                c and out[mode].update({"win_rate_pct": round(100 * out[mode]["wins"] / c, 1)})
    except Exception:
        pass
    return out


def query_orders() -> dict[str, Any]:
    orders = _orders_for(limit=25)
    positions = _positions_for()
    open_positions = _enriched_open_positions()
    trade_metrics = _trade_metrics()
    order_metrics = _order_metrics()
    status_counts: dict[str, int] = {}
    for order in orders:
        status_counts[order["status"]] = status_counts.get(order["status"], 0) + 1
    bot_counts: dict[str, int] = {}
    for position in positions:
        bot_counts[position["bot_id"]] = bot_counts.get(position["bot_id"], 0) + 1
    pnl_project = portfolio_pnl().get("project", {})
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "orders": orders,
        "positions": positions,
        "open_positions": open_positions,
        "recent_trades": trade_metrics["recent_trades"],
        "trade_metrics": trade_metrics,
        "order_metrics": order_metrics,
        "status_counts": status_counts,
        "open_position_counts": bot_counts,
        "risk": _risk_summary(open_positions, pnl_project),
    }


def _persistence_db_path(env_var: str, default_filename: str) -> str:
    return os.environ.get(env_var, f"data/{default_filename}")


def _persistence_cell_breakdown(db_path: str, entries_table: str) -> dict[str, Any]:
    """Aggregate persistence_paper.db or persistence_live.db per cell."""
    import sqlite3 as _sqlite3

    path = Path(db_path)
    if not path.exists():
        return {
            "db_path": str(path),
            "exists": False,
            "cells": {},
            "total": {},
            "halt": {"active": False, "reason": None},
        }

    con = _sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5.0)
    con.row_factory = _sqlite3.Row
    cells: dict[str, Any] = {}
    tot_n = tot_wins = 0
    tot_stake = tot_pnl = tot_fees = 0.0
    realised_total: float | None = None
    n_resolved: int | None = None
    halt_active = False
    halt_reason: str | None = None

    try:
        rows = con.execute(
            f"SELECT cell_label, COUNT(*) AS n, "
            f"       COALESCE(SUM(CASE WHEN won = 1 THEN 1 ELSE 0 END), 0) AS wins, "
            f"       COALESCE(SUM(ask_high), 0) AS sum_ask, "
            f"       COALESCE(SUM(pnl_usd), 0) AS sum_pnl_legacy, "
            f"       COALESCE(SUM(fee_usd), 0) AS sum_fees, "
            f"       COALESCE(SUM(stake_usd), 0) AS sum_stake "
            f"FROM {entries_table} GROUP BY cell_label"
        ).fetchall()
    except _sqlite3.OperationalError:
        rows = []

    for r in rows:
        n = int(r["n"])
        wins = int(r["wins"] or 0)
        stake = float(r["sum_stake"] or 0)
        cells[r["cell_label"]] = {
            "n": n,
            "wins": wins,
            "win_rate": (wins / n) if n > 0 else 0.0,
            "sum_ask": float(r["sum_ask"] or 0),
            "sum_pnl_paper_style": float(r["sum_pnl_legacy"] or 0),
            "sum_fees": float(r["sum_fees"] or 0),
            "sum_stake_usd": stake,
        }
        tot_n += n
        tot_wins += wins
        tot_stake += stake
        tot_pnl += float(r["sum_pnl_legacy"] or 0)
        tot_fees += float(r["sum_fees"] or 0)

    if entries_table == "live_entries":
        try:
            row = con.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(realised_pnl_usd), 0) AS pnl "
                "FROM live_entries WHERE status = 'resolved'"
            ).fetchone()
            n_resolved = int(row["n"])
            realised_total = float(row["pnl"])
        except _sqlite3.OperationalError:
            pass
        try:
            row = con.execute(
                "SELECT reason FROM halt_flags WHERE cleared_at_ms IS NULL "
                "ORDER BY raised_at_ms DESC LIMIT 1"
            ).fetchone()
            if row:
                halt_active = True
                halt_reason = row["reason"]
        except _sqlite3.OperationalError:
            pass

    con.close()
    return {
        "db_path": str(path),
        "exists": True,
        "cells": cells,
        "total": {
            "n": tot_n,
            "wins": tot_wins,
            "win_rate": (tot_wins / tot_n) if tot_n > 0 else 0.0,
            "sum_stake_usd": tot_stake,
            "sum_pnl_paper_style": tot_pnl,
            "sum_fees": tot_fees,
            "n_resolved": n_resolved,
            "realised_pnl_usd": realised_total,
        },
        "halt": {"active": halt_active, "reason": halt_reason},
    }


def _persistence_recent_entries(db_path: str, *, limit: int = 12) -> list[dict[str, Any]]:
    import sqlite3 as _sqlite3

    path = Path(db_path)
    if not path.exists():
        return []
    con = _sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5.0)
    con.row_factory = _sqlite3.Row
    try:
        rows = con.execute(
            "SELECT inserted_at_ms, cell_label, crypto, duration_minutes, "
            "       side, ask_high, mid_high, shares, stake_usd, status, "
            "       resolved_outcome, won, realised_pnl_usd "
            "FROM live_entries ORDER BY inserted_at_ms DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = [dict(r) for r in rows]
    except _sqlite3.OperationalError:
        out = []
    finally:
        con.close()
    return out


def _open_exposure_for_bot(bot_id: str) -> float:
    try:
        from sqlalchemy import select

        from core.db import Position, get_session_factory

        Session = get_session_factory()
        with Session() as s:
            rows = s.execute(
                select(Position.cost_basis_usd).where(
                    Position.bot_id == bot_id,
                    Position.status == "OPEN",
                )
            ).all()
        return float(sum((r[0] or 0) for r in rows))
    except Exception:  # noqa: BLE001
        return 0.0


def query_bot_i() -> dict[str, Any]:
    """Bot I — Persistence Live. ADR-129.

    Surfaces: simple status, paper-vs-live cell comparator, recent
    entries, halt-flag, and live caps. Tolerant of the live DB not
    yet existing (it is created on Bot I's first scan tick).
    """
    now = datetime.now(timezone.utc)
    services = service_states()
    halted_ids = _halted_bot_ids()
    spec = _spec_for("bot_i_persistence_live")
    simple = _bot_simple_summary(spec, services=services, halted_ids=halted_ids)

    live_db = _persistence_db_path("BOT_I_LIVE_DB", "persistence_live.db")
    paper_db = _persistence_db_path("PERSISTENCE_PAPER_DB", "persistence_paper.db")
    paper_breakdown = _persistence_cell_breakdown(paper_db, "paper_entries")
    live_breakdown = _persistence_cell_breakdown(live_db, "live_entries")
    recent = _persistence_recent_entries(live_db, limit=12)

    return {
        "generated_at": now.isoformat(),
        "bot_id": "bot_i_persistence_live",
        "label": spec.get("label") or "Persistence Live (I)",
        "adr": "ADR-129",
        "envelope": {
            "wallet_budget_usd": 100,
            "per_entry_usd": 5,
            "daily_gross_usd": 50,
            "open_exposure_usd": 100,
            "max_concurrent": 20,
            "max_entries_per_day": 20,
            "wallet_shared_with": "bot_d_live_probe",
            "kill_date_iso": "2026-06-13",
        },
        "cells": {
            "A_borderline_5m_15m": {
                "min_mid": 0.50,
                "max_mid": 0.55,
                "durations": [5, 15],
                "side": "buy_favourite_at_ask",
            },
            "B_tail_15m": {
                "min_mid": 0.85,
                "max_mid": 0.95,
                "durations": [15],
                "side": "buy_favourite_at_ask",
            },
        },
        "simple": simple,
        "live": live_breakdown,
        "paper_comparator": paper_breakdown,
        "recent_entries": recent,
        "live_caps": {
            "open_exposure_usd": _open_exposure_for_bot("bot_i_persistence_live"),
            "order_metrics": _order_metrics("bot_i_persistence_live"),
            "trade_metrics": _trade_metrics("bot_i_persistence_live"),
        },
    }


def query_events() -> dict[str, Any]:
    services = service_states()
    halted_ids = _halted_bot_ids()
    halts = _halts()
    inventory = _bot_inventory(
        services=services,
        halted_ids=halted_ids,
        vps_node=_load_vps_node_status(),
    )
    # Only surface halts for currently-active trading lanes. Halts on
    # archived/retired identities (bot_a/b/c/e/f) and on Recorder-class
    # rows (legacy bot_e trading-bot halt) stay out of the cockpit.
    trading_active_ids = {
        row.get("bot_id") for row in inventory if row.get("group") in {"Live", "Paper"}
    }
    filtered_halts = [h for h in halts if h.get("bot_id") in trading_active_ids]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "services": services,
        "halts": filtered_halts,
        "severity_counts": _event_severity_counts(),
        "events": _events(limit=30),
    }


def query_state() -> dict[str, Any]:
    """Legacy aggregate endpoint, retained for compatibility (audit C16/C17 era).

    Audit fix (Session 14): this once included all active bot tabs. It now
    follows the current dashboard surface; archived Bot A/F identities and
    retired Bot E trading rows are retained in code/data archives, not the
    operator dashboard.
    """
    overview = query_overview()
    return {
        "generated_at": overview["generated_at"],
        "mode": overview["mode"],
        "wallet": overview["wallet"]["display"],
        "services": overview["services"],
        "halts": overview["halts"],
        "orders": _orders_for(limit=20),
        "positions": _positions_for(),
        "events": _events(limit=15),
        "counts": overview["counts"],
        "pnl": overview["pnl"],
        "balances": overview["balances"],
        "bot_c": query_bot_c(),
        "bot_d": query_bot_d(),
        "bot_g": query_bot_g(),
    }
