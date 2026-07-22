"""Telegram alerting + control channel.

Two roles:

1. `send(severity, msg)` — fire-and-forget alerts.  Used by watchdog and bots.
2. `Listener.run()` — async coroutine that polls Telegram for `/status` and
   `/unhalt <bot_id>` from allowlisted chat IDs.

Keeps zero state locally — all state lives in DB.
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy import select

from core.bot_registry import REGISTRY
from core.config import settings
from core.db import HaltFlag, PnlSnapshot, get_session_factory

# Audit C8: two-step /unhalt timing.
UNHALT_CONFIRM_WINDOW_S = 60
UNHALT_COOLDOWN_S = 60

log = logging.getLogger(__name__)

# httpx logs full request URLs at INFO, which exposes Telegram bot tokens in
# journald because Telegram embeds the token in the URL path.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def _status_bot_ids() -> tuple[str, ...]:
    return tuple(b.bot_id for b in REGISTRY if b.status != "archived")


def _unhaltable_bot_ids() -> tuple[str, ...]:
    return tuple(
        b.bot_id
        for b in REGISTRY
        if b.status not in ("archived", "sensor", "live")
    )


def _bot_g_report_path() -> Path:
    return Path(
        os.environ.get(
            "BOT_G_LEAD_BUCKET_REPORT_JSON",
            "data/reports/bot_g_lead_bucket/latest.json",
        )
    )


def _fmt_money(value: object) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"${amount:+.2f}"


def _fmt_pct(value: object) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{amount:.1f}%"


def bot_g_report_text(path: Path | None = None) -> str:
    """Small Telegram-safe summary of the latest Bot G lead-bucket report."""
    report_path = path or _bot_g_report_path()
    try:
        report = json.loads(report_path.read_text())
    except FileNotFoundError:
        return (
            "Bot G report unavailable: daily lead-bucket report has not run yet.\n"
            f"Expected: {report_path}"
        )
    except Exception as exc:
        return f"Bot G report unavailable: {str(exc)[:180]}"

    labels = (
        ("bot_g_prime_live", "Live"),
        ("bot_g_prime", "Paper 4-8c"),
        ("bot_g_prime_shadow", "Mirror"),
        ("bot_g_prime_high_tail", "High tail"),
        ("bot_g_prime_late_cheap", "Late cheap"),
    )
    overall = report.get("overall") or {}
    lines = [
        "Bot G lead-bucket report",
        f"Generated: {report.get('generated_at', 'unknown')}",
        f"Window start: {report.get('cutoff', 'unknown')}",
    ]
    for bot_id, label in labels:
        row = overall.get(bot_id) or {}
        lines.append(
            f"{label}: orders={int(row.get('n_orders') or 0)} "
            f"fills={int(row.get('n_fills') or 0)} "
            f"resolved={int(row.get('n_resolved') or 0)} "
            f"wins={int(row.get('won') or 0)} "
            f"PnL={_fmt_money(row.get('realized_pnl_usd'))} "
            f"ROI={_fmt_pct(row.get('roi_pct'))} "
            f"ex2={_fmt_pct(row.get('roi_ex_largest_two_pct'))}"
        )
    lines.append("Read-only summary. No live parameter changes are automated.")
    return "\n".join(lines)


@dataclass
class TelegramClient:
    token: str
    allowed_chat_ids: list[int]

    @property
    def _base(self) -> str:
        return f"https://api.telegram.org/bot{self.token}"

    def send(self, severity: str, message: str) -> bool:
        """Send an alert to every allowlisted chat.  Returns True if any send succeeded."""
        if not self.token or not self.allowed_chat_ids:
            log.debug("notify.send.skipped.no_config")
            return False
        prefix = {"info": "[info]", "warn": "[warn]", "kill": "[kill]"}.get(
            severity,
            "[notice]",
        )
        text = f"{prefix} {message}"
        any_ok = False
        for chat_id in self.allowed_chat_ids:
            try:
                with httpx.Client(timeout=5.0) as client:
                    r = client.post(
                        f"{self._base}/sendMessage",
                        json={"chat_id": chat_id, "text": text},
                    )
                    r.raise_for_status()
                any_ok = True
            except Exception as e:
                log.warning("notify.send.failed", extra={"chat_id": chat_id, "error": str(e)})
        return any_ok


def default_client() -> TelegramClient:
    return TelegramClient(
        token=settings.telegram_bot_token.get_secret_value(),
        allowed_chat_ids=settings.allowed_chat_ids(),
    )


def send(severity: str, message: str) -> bool:
    """Module-level convenience for callers that don't want to construct a client."""
    return default_client().send(severity, message)


class Listener:
    """Long-poll loop for Telegram updates.

    Commands understood:
      /status            → summary of halt flags + today's PnL per bot
      /botg              → latest Bot G lead-bucket report summary
      /unhalt <bot_id>   → clear halt flag (allowlisted chat only)
    """

    def __init__(
        self,
        client: TelegramClient | None = None,
        unhalt_handler: Callable[[str, str], bool] | None = None,
        session_factory=None,
        bot_g_report_path: Path | None = None,
    ):
        self.client = client or default_client()
        self._sessions = session_factory or get_session_factory()
        self._unhalt = unhalt_handler or (lambda *_a, **_k: False)
        self._bot_g_report_path = bot_g_report_path
        self._offset = 0
        # Audit C8: two-step /unhalt to prevent single-factor remote control.
        # Track pending confirmations keyed by (chat_id, bot_id). Entries
        # expire after UNHALT_CONFIRM_WINDOW_S.
        self._pending_unhalt: dict[tuple[int, str], float] = {}
        # Audit C8: per-chat cooldown between successful unhalts.
        self._last_unhalt_at: dict[tuple[int, str], float] = {}

    def _status_text(self) -> str:
        with self._sessions() as s:
            flags = {f.bot_id: f for f in s.scalars(select(HaltFlag))}
            snaps = list(
                s.scalars(
                    select(PnlSnapshot).order_by(PnlSnapshot.snapshot_date.desc())
                )
            )

        lines = ["Status:"]
        for bot in _status_bot_ids():
            flag = flags.get(bot)
            halted = "HALTED" if flag and flag.halted else "OK"
            latest = next((x for x in snaps if x.bot_id == bot), None)
            if latest:
                suffix = f" reason={flag.reason}" if flag and flag.halted and flag.reason else ""
                lines.append(
                    f"  {bot}: {halted}  dd={latest.drawdown_pct}%  "
                    f"realised=${latest.realised_usd}  exposure=${latest.open_exposure_usd}"
                    f"{suffix}"
                )
            else:
                suffix = f" reason={flag.reason}" if flag and flag.halted and flag.reason else ""
                lines.append(f"  {bot}: {halted}  (no snapshot yet){suffix}")
        return "\n".join(lines)

    def _handle_update(self, update: dict) -> None:
        msg = update.get("message") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        if chat_id not in self.client.allowed_chat_ids:
            return
        text = (msg.get("text") or "").strip()
        if text == "/status":
            self.client.send("info", self._status_text())
        elif text in ("/botg", "/bot_g", "/g"):
            self.client.send("info", bot_g_report_text(self._bot_g_report_path))
        elif text == "/help":
            self.client.send(
                "info",
                "Commands: /status, /botg, /unhalt <bot_id>, /unhalt <bot_id> confirm",
            )
        elif text.startswith("/unhalt"):
            parts = text.split()
            allowed_bots = _unhaltable_bot_ids()
            if len(parts) < 2 or parts[1] not in allowed_bots:
                self.client.send(
                    "info",
                    "usage: /unhalt <bot_id> [confirm]\n"
                    f"allowed: {', '.join(allowed_bots)}",
                )
                return
            bot_id = parts[1]
            is_confirm = len(parts) >= 3 and parts[2] == "confirm"
            now = time.time()
            # Enforce cooldown on confirmed attempts.
            last = self._last_unhalt_at.get((chat_id, bot_id), 0.0)
            if is_confirm and (now - last) < UNHALT_COOLDOWN_S:
                wait = int(UNHALT_COOLDOWN_S - (now - last))
                log.info(
                    "notify.unhalt.cooldown",
                    extra={"chat_id": chat_id, "bot_id": bot_id, "wait_s": wait},
                )
                self.client.send("info", f"unhalt cooldown — retry in {wait}s.")
                return
            key = (chat_id, bot_id)
            # SECURITY_AUDIT.md L-2: prune expired entries on every access
            # so a flood of `/unhalt` without follow-up `confirm` doesn't
            # leak memory in long-running notify_daemon processes.
            self._pending_unhalt = {
                k: v for k, v in self._pending_unhalt.items() if v > now
            }
            if not is_confirm:
                # Stage a pending confirmation.
                self._pending_unhalt[key] = now + UNHALT_CONFIRM_WINDOW_S
                log.info(
                    "notify.unhalt.pending",
                    extra={"chat_id": chat_id, "bot_id": bot_id},
                )
                self.client.send(
                    "info",
                    f"To confirm, reply `/unhalt {bot_id} confirm` within "
                    f"{UNHALT_CONFIRM_WINDOW_S}s.",
                )
                return
            # Confirmation path. Require a matching pending entry.
            expiry = self._pending_unhalt.pop(key, 0.0)
            if expiry <= now:
                self.client.send(
                    "info",
                    f"No pending unhalt for {bot_id} (or it expired). "
                    f"Send `/unhalt {bot_id}` first.",
                )
                return
            ok = self._unhalt(bot_id, "telegram unhalt")
            if ok:
                self._last_unhalt_at[key] = now
            log.info(
                "notify.unhalt.confirmed",
                extra={"chat_id": chat_id, "bot_id": bot_id, "ok": ok},
            )
            self.client.send("info", f"unhalt {bot_id}: {'OK' if ok else 'not halted'}")

    def poll_once(self, timeout: int = 25) -> int:
        """One long-poll round.  Returns number of updates handled."""
        try:
            with httpx.Client(timeout=timeout + 5) as client:
                r = client.get(
                    f"{self.client._base}/getUpdates",
                    params={"offset": self._offset, "timeout": timeout},
                )
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            log.warning("notify.poll.failed", extra={"error": str(e)})
            return 0

        count = 0
        for update in data.get("result", []):
            self._offset = update["update_id"] + 1
            try:
                self._handle_update(update)
                count += 1
            except Exception as e:
                log.warning("notify.handle.failed", extra={"error": str(e)})
        return count
