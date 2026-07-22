"""Minimal systemd sd_notify helpers (no external deps).

Used by long-running daemons to tell systemd "I'm alive" so `Type=notify`
units can declare READY and `WatchdogSec=` units can stay alive. Without
this, `Restart=on-failure` only catches hard crashes — not async zombie
loops where the process stays alive but stops doing work (e.g. the Bot E
recorder hang 2026-04-17 00:38 UTC that went unnoticed for 9h40m).

Usage in a bot's main loop:

    from core.sd_notify import notify_ready, notify_watchdog
    notify_ready()
    while running:
        do_work()
        notify_watchdog()   # tell systemd we're alive; reset the timer

Unit file:

    [Service]
    Type=notify
    WatchdogSec=180
    Restart=always
    RestartSec=10

When running outside systemd (local dev, tests), NOTIFY_SOCKET is unset
and these calls are silent no-ops. Safe to leave in production code paths.
"""
from __future__ import annotations

import logging
import os
import socket

log = logging.getLogger(__name__)


def _send(message: str) -> bool:
    """Send a raw sd_notify message. Returns True if delivered, False otherwise.

    Never raises — sd_notify is a best-effort liveness signal and a bot
    should never crash because systemd's socket is unavailable.
    """
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return False
    # Abstract namespace socket: @foo -> \0foo in linux kernel terms.
    if addr.startswith("@"):
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1.0)
            sock.sendto(message.encode("utf-8"), addr)
        return True
    except OSError as exc:
        log.debug("sd_notify.send_failed msg=%r err=%s", message, exc)
        return False


def notify_ready() -> None:
    """Mark the service as READY (required for Type=notify units)."""
    _send("READY=1")


def notify_watchdog() -> None:
    """Reset the systemd watchdog timer. Call at least every WatchdogSec/2."""
    _send("WATCHDOG=1")


def notify_status(text: str) -> None:
    """Update the service's status line (visible in `systemctl status`)."""
    # STATUS lines must fit in the datagram; truncate long ones.
    _send(f"STATUS={text[:256]}")


def notify_stopping() -> None:
    """Tell systemd we're shutting down (before final exit)."""
    _send("STOPPING=1")
