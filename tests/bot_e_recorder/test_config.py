"""Tests for bot_e_recorder/config.py validation."""
from __future__ import annotations

from pathlib import Path


class TestValidate:
    def test_default_config_is_valid(self, monkeypatch):
        """Defaults must pass validation (so the bot can start without env)."""
        # Clear any env overrides
        for var in [
            "BOT_E_CEX_SYMBOLS", "BOT_E_MARKET_SCAN_INTERVAL_SEC",
            "BOT_E_HEARTBEAT_INTERVAL_SEC", "BOT_E_MAX_MINUTES_TO_RES",
            "BOT_E_MIN_VOLUME_USD",
        ]:
            monkeypatch.delenv(var, raising=False)

        # Reload module to pick up env state
        import importlib

        from bots.bot_e_recorder import config
        importlib.reload(config)

        errors = config.validate()
        assert errors == [], f"default config invalid: {errors}"
        assert "XRPUSDT" in config.BOT_E_CEX_SYMBOLS
        assert "DOGEUSDT" in config.BOT_E_CEX_SYMBOLS
        assert "xrp" in config.BOT_E_MARKET_TAGS
        assert "dogecoin" in config.BOT_E_MARKET_TAGS

    def test_crypto_recorder_aliases_override_legacy_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(tmp_path / "legacy.db"))
        monkeypatch.setenv("CRYPTO_RECORDER_DB_PATH", str(tmp_path / "crypto.db"))
        monkeypatch.setenv("BOT_E_CEX_SYMBOLS", "BTCUSDT")
        monkeypatch.setenv("CRYPTO_RECORDER_CEX_SYMBOLS", "ETHUSDT,SOLUSDT")
        monkeypatch.setenv("CRYPTO_RECORDER_MARKET_TAGS", "ethereum,solana")
        monkeypatch.setenv("CRYPTO_RECORDER_MARKET_SCAN_INTERVAL_SEC", "30")
        import importlib

        from bots.bot_e_recorder import config
        importlib.reload(config)

        assert config.BOT_E_RECORDER_DB_PATH == tmp_path / "crypto.db"
        assert config.BOT_E_CEX_SYMBOLS == ["ETHUSDT", "SOLUSDT"]
        assert config.BOT_E_MARKET_TAGS == ["ethereum", "solana"]
        assert config.BOT_E_MARKET_SCAN_INTERVAL_SEC == 30

    def test_bad_interval_rejected(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BOT_E_HEARTBEAT_INTERVAL_SEC", "-1")
        monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(tmp_path / "rec.db"))
        import importlib

        from bots.bot_e_recorder import config
        importlib.reload(config)

        errors = config.validate()
        assert any("BOT_E_HEARTBEAT_INTERVAL_SEC" in e for e in errors)

    def test_empty_symbols_rejected(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BOT_E_CEX_SYMBOLS", "")
        monkeypatch.setenv("BOT_E_RECORDER_DB_PATH", str(tmp_path / "rec.db"))
        import importlib

        from bots.bot_e_recorder import config
        importlib.reload(config)

        errors = config.validate()
        assert any("BOT_E_CEX_SYMBOLS" in e for e in errors)

    def test_vps_paper_feed_records_xrp_doge(self):
        root = Path(__file__).resolve().parents[2]
        unit = (root / "systemd" / "longshot-crypto-recorder-vps-paper-feed.service").read_text()

        assert "BOT_E_CEX_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT" in unit
        assert "xrp,ripple,dogecoin,doge" in unit
