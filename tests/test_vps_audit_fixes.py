from __future__ import annotations

from pathlib import Path

from scripts.repo_secret_scan import scan


def test_watchdog_unit_does_not_hard_require_vpn() -> None:
    root = Path(__file__).resolve().parents[1]
    unit = (root / "systemd/polymarket-watchdog.service").read_text()

    assert "Requires=polymarket-wg-vpn.service" not in unit
    assert "After=polymarket-wg-vpn.service" not in unit
    assert "After=network-online.target" in unit
    assert "Wants=network-online.target" in unit


def test_vps_live_unit_uses_vps_paths_and_reduced_size() -> None:
    root = Path(__file__).resolve().parents[1]
    unit = (root / "systemd/polymarket-bot-g-prime-live-vps.service").read_text()

    assert "User=operator" in unit
    assert "WorkingDirectory=/home/operator/longshot-research" in unit
    assert 'Environment="POLYMARKET_DB_PATH=/home/operator/longshot-research/data/bot_g_vps_main.db"' in unit
    assert 'Environment="BOT_G_FIXED_TRADE_USD=1"' in unit
    assert 'Environment="BOT_G_MIN_ENTRY_PRICE=0.06"' in unit
    assert 'Environment="BOT_G_MAX_ENTRY_PRICE=0.08"' in unit
    assert 'Environment="BOT_G_ALLOWED_SYMBOLS=ETH,SOL"' in unit


def test_vps_watchdog_unit_can_manage_vps_live_bot_g() -> None:
    root = Path(__file__).resolve().parents[1]
    unit = (root / "systemd/polymarket-watchdog-vps.service").read_text()

    assert "User=operator" in unit
    assert "WorkingDirectory=/home/operator/longshot-research" in unit
    assert 'Environment="LONGSHOT_WATCHDOG_HOST_ROLE=vps"' in unit
    assert 'Environment="POLYMARKET_DB_PATH=/home/operator/longshot-research/data/bot_g_vps_main.db"' in unit
    assert 'Environment="BOT_G_PRIME_LIVE_ENV=live"' in unit
    assert "ExecStart=/home/operator/longshot-research/.venv/bin/python -m bots.watchdog_daemon" in unit


def test_watchdog_scope_is_host_aware(monkeypatch) -> None:
    import importlib

    from core import watchdog

    monkeypatch.setenv("LONGSHOT_WATCHDOG_HOST_ROLE", "the bot container")
    importlib.reload(watchdog)
    assert "bot_g_prime_live" in watchdog.LOCAL_WATCHDOG_EXCLUDED_BOTS
    assert "bot_g_prime_live" not in watchdog.LIVE_CAP_BOTS

    monkeypatch.setenv("LONGSHOT_WATCHDOG_HOST_ROLE", "vps")
    importlib.reload(watchdog)
    assert "bot_g_prime_live" not in watchdog.LOCAL_WATCHDOG_EXCLUDED_BOTS
    assert "bot_g_prime_live" in watchdog.LIVE_CAP_BOTS
    assert "bot_b" in watchdog.LOCAL_WATCHDOG_EXCLUDED_BOTS
    assert "bot_d_live_probe" in watchdog.LOCAL_WATCHDOG_EXCLUDED_BOTS

    monkeypatch.delenv("LONGSHOT_WATCHDOG_HOST_ROLE", raising=False)
    importlib.reload(watchdog)


def test_active_bot_g_live_surfaces_are_six_to_eight_cent() -> None:
    root = Path(__file__).resolve().parents[1]
    active_paths = [
        root / "systemd/polymarket-bot-g-prime-live.service",
        root / "systemd/polymarket-bot-g-prime-live-vps.service",
        root / "systemd/polymarket-bot-g-prime-high-tail.service",
        root / "systemd/polymarket-bot-g-prime-high-tail-vps.service",
        root / "bots/bot_g_longshot/CLAUDE.md",
        root / "dashboard/static/app.js",
        root / "dashboard/runtime_queries.py",
    ]

    combined = "\n".join(path.read_text() for path in active_paths)
    assert "0.065" not in combined
    assert "6.5-8c" not in combined
    assert "6.5c-8c" not in combined
    assert 'Environment="BOT_G_MIN_ENTRY_PRICE=0.06"' in combined


def test_repo_secret_scan_ignores_public_address_and_flags_private_key(tmp_path) -> None:
    public_doc = tmp_path / "public.md"
    public_doc.write_text(
        "Wallet 0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA is public.\n"
        "POLYMARKET_PRIVATE_KEY=<redacted>\n",
        encoding="utf-8",
    )
    assert scan(tmp_path) == []

    leak = tmp_path / "leak.env"
    leak.write_text(
        "POLYMARKET_PRIVATE_KEY="
        "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
        encoding="utf-8",
    )
    findings = scan(tmp_path)
    assert len(findings) == 1
    assert "private key assignment" in findings[0]
