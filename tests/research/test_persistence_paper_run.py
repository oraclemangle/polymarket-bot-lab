from __future__ import annotations

import contextlib
from pathlib import Path

from scripts.research.persistence_paper_run import selected_cells


def test_selected_cells_default_preserves_existing_persistence_cells():
    cells = selected_cells()

    assert set(cells) == {"A_borderline_5m_15m", "B_tail_15m"}


def test_selected_cells_can_isolate_cell_c():
    cells = selected_cells(only_cell_c=True)

    assert set(cells) == {"C_tail_5m_15m_95_99"}
    cell = cells["C_tail_5m_15m_95_99"]
    assert cell["min_mid_high"] == 0.95
    assert cell["max_mid_high"] == 0.99
    assert cell["durations"] == [5, 15]


def test_live_maker_shadow_uses_distinct_report_suffix():
    root = Path(__file__).resolve().parents[2]
    unit = (
        root / "systemd/polymarket-bot-i-persistence-live-maker-paper.service"
    ).read_text()

    assert "--paper-db data/persistence_live_maker_paper.db" in unit
    assert "--execution-style maker --report-suffix maker-live" in unit


def test_live_bot_i_report_flag_triggers_guard_when_paused(monkeypatch):
    """Regression test for Codex audit finding: the guard must be narrow.

    When --live-bot-i-report is passed and live Bot I is paused in the registry,
    main() must exit early (0).

    When the flag is *not* passed (normal paper runs), main() must proceed even
    if live Bot I is paused.
    """
    import sys
    from unittest.mock import MagicMock, patch

    import pytest

    from scripts.research import persistence_paper_run as mod

    # Force registry to report live Bot I as paused
    def fake_meta(bid):
        if bid in ("bot_i_persistence_live", "bot_i_persistence_live_maker"):
            m = MagicMock()
            m.status = "paused"
            return m
        return None

    monkeypatch.setattr(mod, "bot_meta", fake_meta, raising=False)

    # Case 1: flag present → should exit(0)
    with patch.object(sys, "exit") as mock_exit, \
         patch("sys.argv", ["prog", "--live-bot-i-report", "--recorder-db", "/tmp/x", "--paper-db", "/tmp/y", "--report-dir", "/tmp/z"]):
        with contextlib.suppress(SystemExit):
            mod.main()
    mock_exit.assert_called_with(0)

    # Case 2: flag absent → must *not* call exit early (would proceed to parser)
    # Patch DB openers and heavy init so the no-flag path does not require real files in this unit test.
    with patch.object(sys, "exit") as mock_exit, \
         patch("sys.argv", ["prog", "--recorder-db", "/tmp/x", "--paper-db", "/tmp/y", "--report-dir", "/tmp/z"]), \
         patch.object(mod, "connect_ro", return_value=MagicMock()), \
         patch.object(mod, "init_paper_db", return_value=MagicMock()), \
         patch.object(mod, "load_markets", return_value=[]):
        with contextlib.suppress(SystemExit, Exception):
            mod.main()
    # The guard should not have triggered
    for call in mock_exit.call_args_list:
        if call[0] == (0,):
            pytest.fail("Guard triggered on a normal paper-style invocation (no --live-bot-i-report flag)")
