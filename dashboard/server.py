"""Dashboard HTTP entrypoint with static assets and focused JSON endpoints."""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .runtime_queries import (
    main_db_path,
    query_bot_c,
    query_bot_d,
    query_bot_e,
    query_bot_g,
    query_bot_h,
    query_events,
    query_orders,
    query_overview,
    query_state,
    query_wallet_observer,
)

STATIC_ROOT = Path(__file__).resolve().parent / "static"
CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}

ROUTES: dict[str, Callable[[], dict[str, Any]]] = {
    "/api/state": query_state,
    "/api/overview": query_overview,
    "/api/bot-c": query_bot_c,
    "/api/bot-d": query_bot_d,
    "/api/bot-e": query_bot_e,
    "/api/bot-g": query_bot_g,
    "/api/bot-h": query_bot_h,
    "/api/wallet-observer": query_wallet_observer,
    "/api/orders": query_orders,
    "/api/events": query_events,
}
API_ROUTES = ROUTES


def _safe_static_path(path: str) -> Path | None:
    candidate = (STATIC_ROOT / path.lstrip("/")).resolve()
    try:
        candidate.relative_to(STATIC_ROOT.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


_EMPTY_KEY_WARNED = False


def _require_api_key() -> str | None:
    """Return the configured API key or None (loopback-only mode).

    Distinguishes unset (None) from empty-string (""). Empty string was
    silently treated as "auth disabled" prior to the 2026-04-22 GLM-5.1
    review (A5) — any deploy script that exported DASHBOARD_API_KEY=""
    disabled the whole auth path. Now we emit a one-time WARNING so the
    operator sees it; auth still disables (backwards-compat for the
    existing deploys) but loudly.
    """
    raw = os.environ.get("DASHBOARD_API_KEY")
    if raw is None:
        return None
    if raw == "":
        global _EMPTY_KEY_WARNED
        if not _EMPTY_KEY_WARNED:
            import logging
            logging.getLogger("dashboard").warning(
                "DASHBOARD_API_KEY is empty string — auth is DISABLED. "
                "Unset the var to silence this warning.",
            )
            _EMPTY_KEY_WARNED = True
        return None
    return raw


def _sanitize_for_json(value: Any) -> Any:
    """Recursively replace non-finite floats (NaN/Inf) with None so the
    response body is strict-JSON-parseable. Browsers' `response.json()`
    rejects bare `NaN` tokens, which previously broke the Events tab
    when Bot D weather payloads contained `forecast_mean_f: NaN`."""
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_for_json(item) for item in value]
    return value


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, *args, **kwargs) -> None:  # pragma: no cover
        return

    def _check_auth(self) -> bool:
        """Enforce API key on non-loopback, non-trusted clients when DASHBOARD_API_KEY set.

        Pass conditions (any one is sufficient):
          - DASHBOARD_API_KEY is not set (loopback-only mode)
          - Peer is loopback (127.0.0.1 / ::1)
          - Peer IP matches a CIDR in DASHBOARD_TRUSTED_CIDRS
            (comma-separated; default "192.0.2.1/16,192.0.2.1/8,192.0.2.1/12"
             — RFC1918 private space, i.e. your home LAN)
          - Request carries X-API-Key equal to $DASHBOARD_API_KEY
        """
        key = _require_api_key()
        if key is None:
            return True
        peer = self.client_address[0] if self.client_address else ""
        # SECURITY_AUDIT.md L-1: peer is always an IP string from
        # BaseHTTPRequestHandler.client_address, never the literal
        # "localhost". The string match was dead code.
        if peer in ("127.0.0.1", "::1"):
            return True
        # Trusted-CIDR bypass.
        # SECURITY_AUDIT.md M-2 compromise: default is now empty (loopback-
        # only) per the audit recommendation. Set DASHBOARD_TRUSTED_CIDRS
        # explicitly (e.g. "192.0.2.1/24") to opt-in to LAN access without
        # an API key. Previous default permitted all RFC1918 private space,
        # which is too broad for fresh deploys, but the env override
        # preserves the "browse from another machine on home LAN" workflow.
        import ipaddress

        trusted_cidrs = os.environ.get("DASHBOARD_TRUSTED_CIDRS", "")
        try:
            ip = ipaddress.ip_address(peer)
            for cidr in (c.strip() for c in trusted_cidrs.split(",") if c.strip()):
                if ip in ipaddress.ip_network(cidr, strict=False):
                    return True
        except ValueError:
            pass
        supplied = self.headers.get("X-API-Key", "")
        # Timing-safe comparison per 2026-04-22 GLM-5.1 review (A5).
        # Direct `supplied == key` leaked the key character-by-character to
        # a remote attacker via response-time side-channel.
        import hmac
        return hmac.compare_digest(supplied.encode("utf-8"), key.encode("utf-8"))

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        # `allow_nan=False` would raise on NaN/Infinity in event payloads
        # (e.g. `forecast_mean_f: NaN` from Bot D weather rows). Coerce
        # those to JSON null up-front so the browser's strict JSON parser
        # does not blow up the Events tab.
        body = json.dumps(_sanitize_for_json(payload), default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if not self._check_auth():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "missing or invalid X-API-Key"})
            return
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ROUTES:
            try:
                self._send_json(HTTPStatus.OK, ROUTES[path]())
            except Exception as exc:
                # 2026-04-18: log full traceback so disk I/O / engine errors
                # are diagnosable from journalctl. Previously the wrapper
                # rendered str(exc) to the client and ate the stack.
                import traceback as _tb
                _tb.print_exc()
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        if path in ("/", "/index.html"):
            self._send_file(STATIC_ROOT / "index.html")
            return
        if path in ("/app.js", "/styles.css"):
            asset = _safe_static_path(path)
            if asset is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_file(asset)
            return
        if path == "/healthz":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        self.send_error(HTTPStatus.NOT_FOUND)


def make_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), DashboardHandler)


def main() -> int:
    # Default to loopback (audit C16) — financial data shouldn't be readable
    # by every host on the LAN. To expose on LAN, set DASHBOARD_HOST=0.0.0.0
    # AND DASHBOARD_API_KEY (enforced inside DashboardHandler via X-API-Key).
    host = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
    port = int(os.environ.get("DASHBOARD_PORT", "8090"))
    if host != "127.0.0.1" and not os.environ.get("DASHBOARD_API_KEY"):
        print(
            f"dashboard REFUSING to bind {host}:{port} without DASHBOARD_API_KEY set. "
            "Set DASHBOARD_HOST=127.0.0.1 or provide DASHBOARD_API_KEY.",
            flush=True,
        )
        return 2
    server = make_server(host, port)
    print(f"dashboard listening on http://{host}:{port} (db={main_db_path()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        pass
    return 0
