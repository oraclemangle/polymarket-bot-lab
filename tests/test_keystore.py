"""Keystore tests.

The real `age` binary refuses to read a passphrase from a non-tty pipe
on decryption (by design).  `core.keystore` works around this by
running `age` under a pty; for unit tests we mock the pty helper
(`_age_decrypt_with_pty`) so we can exercise the parse + signer path
end-to-end without spawning a real age process.

The full encryption round-trip is exercised manually via
`scripts/unlock_keystore.py` and by the production LXC deployment.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from eth_account import Account

from core.keystore import Keystore, KeystoreError, SecureBytes


@pytest.fixture
def fake_keystore_files(tmp_path: Path) -> tuple[Path, Path, str]:
    """Create placeholder keystore + passphrase files, return paths + expected priv hex."""
    acct = Account.create()
    priv_hex = acct.key.hex()
    keystore_path = tmp_path / "keystore.age"
    keystore_path.write_text("dummy encrypted content")
    passphrase_path = tmp_path / "passphrase"
    passphrase_path.write_text("correct-horse")
    return keystore_path, passphrase_path, priv_hex


def test_load_roundtrip(fake_keystore_files):
    keystore_path, passphrase_path, priv_hex = fake_keystore_files
    acct = Account.from_key(priv_hex)

    def fake_pty(keystore, passphrase, timeout):
        assert Path(keystore) == keystore_path
        assert passphrase == "correct-horse"
        return priv_hex.encode()

    with patch("core.keystore._age_decrypt_with_pty", side_effect=fake_pty):
        ks = Keystore.load(keystore_path, passphrase_path)
        try:
            assert ks.address == acct.address
            sig = ks.sign_message(b"hello polymarket")
            assert len(sig) == 65
        finally:
            ks.close()


def test_bad_passphrase(fake_keystore_files):
    keystore_path, passphrase_path, _ = fake_keystore_files

    def fake_pty(keystore, passphrase, timeout):
        raise KeystoreError("age decryption failed (exit 1): incorrect passphrase")

    with patch("core.keystore._age_decrypt_with_pty", side_effect=fake_pty):
        with pytest.raises(KeystoreError):
            Keystore.load(keystore_path, passphrase_path)


def test_age_binary_missing(fake_keystore_files):
    keystore_path, passphrase_path, _ = fake_keystore_files
    with patch(
        "core.keystore._age_decrypt_with_pty",
        side_effect=KeystoreError("`age` binary not found on PATH"),
    ):
        with pytest.raises(KeystoreError):
            Keystore.load(keystore_path, passphrase_path)


def test_malformed_key(fake_keystore_files):
    keystore_path, passphrase_path, _ = fake_keystore_files

    with patch(
        "core.keystore._age_decrypt_with_pty",
        side_effect=lambda *a, **kw: b"not-hex-too-short",
    ):
        with pytest.raises(KeystoreError):
            Keystore.load(keystore_path, passphrase_path)


def test_missing_files(tmp_path):
    with pytest.raises(KeystoreError):
        Keystore.load(tmp_path / "nope.age", tmp_path / "nope.pass")


def test_missing_keystore_but_pass_present(tmp_path):
    passphrase = tmp_path / "pass"
    passphrase.write_text("x")
    with pytest.raises(KeystoreError):
        Keystore.load(tmp_path / "nope.age", passphrase)


def test_empty_passphrase_refused(tmp_path):
    keystore = tmp_path / "k.age"
    keystore.write_text("x")
    passphrase = tmp_path / "pass"
    passphrase.write_text("")
    with pytest.raises(KeystoreError):
        Keystore.load(keystore, passphrase)


def test_secure_bytes_wipe():
    sb = SecureBytes(b"secret-key-bytes")
    assert sb.hex() == b"secret-key-bytes".hex()
    sb.wipe()
    with pytest.raises(KeystoreError):
        sb.bytes()


def test_secure_bytes_double_wipe_ok():
    sb = SecureBytes(b"secret")
    sb.wipe()
    sb.wipe()  # should not raise


def test_repr_does_not_leak():
    sb = SecureBytes(b"secret-key-bytes")
    assert "secret" not in repr(sb)
    assert "redacted" in repr(sb)


def test_keystore_repr_redacted(fake_keystore_files):
    keystore_path, passphrase_path, priv_hex = fake_keystore_files

    with patch(
        "core.keystore._age_decrypt_with_pty",
        side_effect=lambda *a, **kw: priv_hex.encode(),
    ):
        ks = Keystore.load(keystore_path, passphrase_path)
        try:
            r = repr(ks)
            assert "redacted" in r
            assert priv_hex not in r
        finally:
            ks.close()


def test_pty_helper_strips_ansi_and_prompt():
    """Helper integration: fake age bytes through the clean path."""
    from core.keystore import _ANSI_CSI_RE, _PROMPT_MARKER

    raw = b"Enter passphrase: \r\n\x1b[F\x1b[KDEADBEEF" + b"CAFEBABE" * 7
    clean = _ANSI_CSI_RE.sub(b"", raw).replace(b"\r", b"")
    tail = clean.rsplit(_PROMPT_MARKER, 1)[-1].lstrip(b"\n")
    assert tail == b"DEADBEEF" + b"CAFEBABE" * 7
