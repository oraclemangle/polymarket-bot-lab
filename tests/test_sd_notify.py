"""Tests for core/sd_notify.py — systemd watchdog helpers."""
from __future__ import annotations

import os
import socket
import tempfile
from pathlib import Path

import pytest

from core import sd_notify


class TestSdNotify:
    def test_no_op_when_notify_socket_unset(self, monkeypatch):
        monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
        assert sd_notify._send("READY=1") is False
        assert sd_notify._send("WATCHDOG=1") is False
        # Public helpers must not raise either.
        sd_notify.notify_ready()
        sd_notify.notify_watchdog()
        sd_notify.notify_status("hello")
        sd_notify.notify_stopping()

    def test_sends_to_unix_socket(self, monkeypatch):
        # AF_UNIX path limit is 104 on macOS; use short /tmp path.
        import uuid
        sock_path = Path(f"/tmp/sdn_{uuid.uuid4().hex[:8]}.sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        srv.bind(str(sock_path))
        srv.settimeout(2.0)
        try:
            monkeypatch.setenv("NOTIFY_SOCKET", str(sock_path))
            assert sd_notify._send("READY=1") is True
            data, _ = srv.recvfrom(4096)
            assert data == b"READY=1"
        finally:
            srv.close()
            try:
                sock_path.unlink()
            except Exception:
                pass

    def test_watchdog_message_format(self, monkeypatch):
        import uuid
        sock_path = Path(f"/tmp/sdn_{uuid.uuid4().hex[:8]}.sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        srv.bind(str(sock_path))
        srv.settimeout(2.0)
        try:
            monkeypatch.setenv("NOTIFY_SOCKET", str(sock_path))
            sd_notify.notify_watchdog()
            data, _ = srv.recvfrom(4096)
            assert data == b"WATCHDOG=1"
        finally:
            srv.close()
            try:
                sock_path.unlink()
            except Exception:
                pass

    def test_status_truncates_long_strings(self, monkeypatch):
        import uuid
        sock_path = Path(f"/tmp/sdn_{uuid.uuid4().hex[:8]}.sock")
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        srv.bind(str(sock_path))
        srv.settimeout(2.0)
        try:
            monkeypatch.setenv("NOTIFY_SOCKET", str(sock_path))
            sd_notify.notify_status("x" * 500)
            data, _ = srv.recvfrom(4096)
            # STATUS= prefix (7 chars) + 256 char cap.
            assert data.startswith(b"STATUS=")
            assert len(data) == 7 + 256
        finally:
            srv.close()
            try:
                sock_path.unlink()
            except Exception:
                pass

    def test_fails_silently_on_bad_socket(self, monkeypatch):
        monkeypatch.setenv("NOTIFY_SOCKET", "/nonexistent/path/that/does/not/exist")
        # Must not raise.
        assert sd_notify._send("READY=1") is False
        sd_notify.notify_watchdog()
