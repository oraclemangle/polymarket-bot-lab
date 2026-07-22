from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fast_roi_report_unit_is_read_only_except_report_dir():
    unit = (ROOT / "systemd/polymarket-fast-roi-report.service").read_text()

    assert "scripts/fast_roi_report.py" in unit
    assert "ExecStartPre=/usr/bin/mkdir -p data/reports/fast_roi" in unit
    assert "--db data/main.db" in unit
    assert "--bot-f-db data/bot_f.db" in unit
    assert "ProtectSystem=strict" in unit
    assert "ReadWritePaths=data/reports" in unit
    assert "keystore" not in unit.lower()
    assert "BOT_D_ENV=live" not in unit
    assert "place" not in unit.lower()


def test_fast_roi_report_timer_runs_hourly():
    timer = (ROOT / "systemd/polymarket-fast-roi-report.timer").read_text()

    assert "OnCalendar=hourly" in timer
    assert "Persistent=true" in timer
    assert "Unit=polymarket-fast-roi-report.service" in timer
