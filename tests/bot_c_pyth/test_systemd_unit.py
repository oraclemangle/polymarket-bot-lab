from pathlib import Path


def test_bot_c_systemd_unit_is_archived_by_default():
    root = Path(__file__).resolve().parents[2]
    unit = (root / "systemd/archived/polymarket-bot-c.service").read_text()

    assert 'Environment="BOT_C_ARCHIVED=true"' in unit
    assert 'Environment="BOT_C_ENDPOINT=hermes"' in unit
    assert 'Environment="BOT_C_ENV=paper"' in unit
    assert 'Environment="BOT_C_MAX_HOURS_TO_RESOLUTION=2160"' in unit
    assert "--enable-executor" not in unit
    assert "Restart=no" in unit
