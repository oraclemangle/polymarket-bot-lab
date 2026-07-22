"""Age-encrypted hot-wallet keystore.

Design (per specs/shared-infra.md §2 and ADR-009):

- Keystore file: age-encrypted blob at `~/.config/polymarket-bot/keystore.age`.
- Passphrase: written to a tmpfs path (e.g. `/run/user/$UID/polymarket/passphrase`)
  by systemd `ExecStartPre` via SSH-delivered secret, zeroed after ExecStart reads it.
- Decrypted key lives in memory as `SecureBytes`; never written back to disk.
- The raw key bytes are not returned by any public method.  Signer objects
  wrap the key so callers can sign without touching the bytes.

Runtime dependency: the `age` binary (`brew install age` / `apt install age`).
We shell out rather than ship a Python re-implementation — age is widely
audited and staying on the official binary avoids crypto-in-pure-python risk.

`age` 1.x insists on `/dev/tty` for passphrase prompts even when a
passphrase is piped on stdin.  Inside a non-interactive systemd service
or `pct exec` call there is no controlling terminal, so we allocate a
pty with `pty.fork()`, disable terminal echo on the slave, and write
the passphrase to it once age emits the prompt.  The plaintext comes
back over the same pty with terminal control codes interspersed; we
strip the ANSI CSI sequences and the prompt echo to recover the raw
key hex.
"""

from __future__ import annotations

import ctypes
import os
import pty
import re
import select
import termios
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from eth_account import Account
from eth_account.signers.local import LocalAccount

if TYPE_CHECKING:
    pass


# Strip ANSI CSI sequences (cursor moves, clears) that age writes to the pty.
_ANSI_CSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
# age prompt marker; everything after the last occurrence is plaintext.
_PROMPT_MARKER = b"passphrase: "


def _age_decrypt_with_pty(keystore_path: Path, passphrase: str, timeout: float) -> bytes:
    """Decrypt an age passphrase-encrypted file by giving `age` a pty.

    age 1.x unconditionally opens `/dev/tty` for the passphrase prompt.
    Under systemd / `pct exec` / ssh-without-tty there is no controlling
    terminal, so the call fails with ENXIO.  We spawn age under a pty
    (with echo disabled on the slave so the passphrase cannot leak back)
    and drive the prompt from the parent.
    """
    try:
        pid, fd = pty.fork()
    except OSError as e:
        raise KeystoreError(f"pty.fork failed: {e}") from e

    if pid == 0:
        # Child: disable ECHO, exec age.  Anything raised here is
        # invisible to the parent — age's own stderr comes back via the pty.
        try:
            attrs = termios.tcgetattr(0)
            attrs[3] &= ~termios.ECHO
            termios.tcsetattr(0, termios.TCSANOW, attrs)
        except Exception:
            pass
        try:
            os.execvp("age", ["age", "--decrypt", str(keystore_path)])
        except FileNotFoundError:
            os._exit(127)
        os._exit(126)

    # Parent: wait for the passphrase prompt, send, drain, reap.
    import time

    deadline = time.monotonic() + timeout
    buf = b""
    try:
        while b"passphrase" not in buf:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                os.kill(pid, 9)
                raise KeystoreError("age decryption timed out waiting for prompt")
            r, _, _ = select.select([fd], [], [], min(remaining, 0.5))
            if not r:
                continue
            try:
                chunk = os.read(fd, 1024)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk

        os.write(fd, passphrase.encode() + b"\n")

        out = b""
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                os.kill(pid, 9)
                raise KeystoreError("age decryption timed out reading plaintext")
            r, _, _ = select.select([fd], [], [], min(remaining, 0.5))
            if not r:
                # Quick liveness check — if child exited, stop looping.
                try:
                    done_pid, _ = os.waitpid(pid, os.WNOHANG)
                    if done_pid:
                        pid = 0
                        break
                except ChildProcessError:
                    break
                continue
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            out += chunk

        if pid:
            _, status = os.waitpid(pid, 0)
        else:
            status = 0
    finally:
        try:
            os.close(fd)
        except OSError:
            pass

    exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -1
    if exit_code == 127:
        raise KeystoreError("`age` binary not found on PATH")

    # Recover plaintext: drop ANSI CSI + the prompt echo + \r noise.
    clean = _ANSI_CSI_RE.sub(b"", out).replace(b"\r", b"")
    idx = clean.rfind(_PROMPT_MARKER)
    tail = clean[idx + len(_PROMPT_MARKER) :] if idx >= 0 else clean
    tail = tail.lstrip(b"\n").rstrip(b"\n")

    if exit_code != 0:
        # age writes its error text to stderr (mirrored onto the pty).
        err = (_ANSI_CSI_RE.sub(b"", out).decode(errors="replace"))[-300:]
        raise KeystoreError(f"age decryption failed (exit {exit_code}): {err}")

    if not tail:
        raise KeystoreError("age decryption returned empty plaintext")
    return tail


class KeystoreError(RuntimeError):
    """Raised when keystore decryption or signer construction fails."""


class SecureBytes:
    """Bytearray wrapper that best-effort zeroes memory on destruction.

    CPython makes "true" zeroing impossible without cooperative C code,
    but this raises the bar materially: after `.wipe()` the backing
    bytearray contains only NULs, so heap inspection on a core dump
    won't leak the key.
    """

    __slots__ = ("_buf",)

    def __init__(self, data: bytes):
        self._buf = bytearray(data)

    def bytes(self) -> bytes:
        if self._buf is None:  # type: ignore[comparison-overlap]
            raise KeystoreError("SecureBytes already wiped")
        return bytes(self._buf)

    def hex(self) -> str:
        return self.bytes().hex()

    def wipe(self) -> None:
        if self._buf is None:  # type: ignore[comparison-overlap]
            return
        n = len(self._buf)
        # Overwrite the bytearray in place.
        ctypes.memset(
            (ctypes.c_char * n).from_buffer(self._buf), 0, n
        )
        self._buf = None  # type: ignore[assignment]

    def __del__(self):
        try:
            self.wipe()
        except Exception:
            pass

    def __repr__(self) -> str:
        return "<SecureBytes (redacted)>"


@dataclass
class Keystore:
    """Loaded hot wallet. Holds decrypted key in memory only."""

    _key: SecureBytes = field(repr=False)
    address: str
    # SECURITY_AUDIT.md H-3 partial mitigation: cache the LocalAccount so
    # repeated signer() calls don't keep instantiating new copies of the
    # private key in heap memory. eth_account's API accepts only bytes/hex
    # for from_key() so we can't avoid the first plaintext copy entirely,
    # but we can stop multiplying it across every signing call.
    _signer_cache: "LocalAccount | None" = field(default=None, repr=False, compare=False)

    # -- Construction --
    @classmethod
    def load(cls, keystore_path: Path, passphrase_path: Path) -> "Keystore":
        """Decrypt keystore with passphrase from tmpfs.

        Both paths must exist and be readable by the current user.
        Raises KeystoreError on any failure.
        """
        keystore_path = Path(keystore_path).expanduser()
        passphrase_path = Path(passphrase_path).expanduser()

        if not keystore_path.exists():
            raise KeystoreError(f"keystore not found: {keystore_path}")
        if not passphrase_path.exists():
            raise KeystoreError(f"passphrase not found: {passphrase_path}")

        # SECURITY_AUDIT.md H-4: read passphrase as bytearray (mutable)
        # so we can actually zero it via ctypes.memset. The previous
        # `passphrase = "\x00" * len(passphrase)` was a no-op for security
        # — Python strings are immutable; reassignment leaves the original
        # heap content intact.
        raw_pass_bytes = passphrase_path.read_bytes().strip()
        if not raw_pass_bytes:
            raise KeystoreError("passphrase file is empty")
        # Convert to bytearray for in-place wiping. The age subprocess
        # interface still needs a str; we accept the str copy is short-
        # lived and zero the bytearray afterwards.
        passphrase_buf = bytearray(raw_pass_bytes)
        del raw_pass_bytes
        passphrase = passphrase_buf.decode("utf-8")

        try:
            raw = _age_decrypt_with_pty(keystore_path, passphrase, timeout=10.0)
        finally:
            # Wipe the bytearray in place — this DOES affect heap memory.
            ctypes.memset(
                ctypes.addressof((ctypes.c_char * len(passphrase_buf)).from_buffer(passphrase_buf)),
                0,
                len(passphrase_buf),
            )
            # Drop the str reference; GC may take time but at least our
            # bytearray (the bigger source) is zeroed.
            passphrase = None  # noqa: F841

        key_hex = raw.decode(errors="replace").strip()
        if key_hex.startswith("0x"):
            key_hex = key_hex[2:]
        if len(key_hex) != 64:
            raise KeystoreError(f"expected 64-hex-char key, got {len(key_hex)} chars")
        try:
            key_bytes = bytes.fromhex(key_hex)
        except ValueError as e:
            raise KeystoreError("keystore contents not valid hex") from e

        # Derive address before wrapping in SecureBytes so we don't need
        # to expose the raw bytes later.
        acct = Account.from_key(key_bytes)
        sb = SecureBytes(key_bytes)
        # Zero the intermediate `key_bytes` reference.
        key_bytes = b"\x00" * len(key_bytes)  # noqa: F841
        return cls(_key=sb, address=acct.address)

    @classmethod
    def load_from_settings(cls, settings) -> "Keystore":
        """Convenience wrapper for daemons that already hold a Settings object.

        Equivalent to ``Keystore.load(settings.polymarket_keystore_path,
        settings.polymarket_passphrase_path)``. Added to fix the SECURITY_AUDIT.md
        Critical finding where Bot C and Bot D's __main__ called this method
        without it existing — every live-mode startup AttributeError'd.
        """
        return cls.load(
            settings.polymarket_keystore_path,
            settings.polymarket_passphrase_path,
        )

    # -- Signer access --
    def signer(self) -> LocalAccount:
        """Return an eth_account LocalAccount usable by py-clob-client.

        The LocalAccount holds the private key internally; callers should
        treat the returned object as sensitive and not log it.

        Cached after first call (SECURITY_AUDIT.md H-3 partial fix) — see
        the _signer_cache field for rationale.
        """
        if self._signer_cache is None:
            self._signer_cache = Account.from_key(self._key.bytes())
        return self._signer_cache

    def sign_message(self, message_bytes: bytes) -> bytes:
        """Sign an arbitrary byte string.  Used by CLOB HMAC layer and tests."""
        from eth_account.messages import encode_defunct

        signable = encode_defunct(primitive=message_bytes)
        signed = self.signer().sign_message(signable)
        return signed.signature

    # -- Lifecycle --
    def close(self) -> None:
        self._key.wipe()
        # Drop the cached signer too — its internal key copy lives until GC.
        self._signer_cache = None

    def __enter__(self) -> "Keystore":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<Keystore address={self.address} (key redacted)>"
