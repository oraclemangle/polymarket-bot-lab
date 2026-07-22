"""Bot D daemon safety helpers."""

import inspect
from types import SimpleNamespace


def test_executor_is_paper_uses_wrapper_effective_mode():
    from bots.bot_d_weather.__main__ import _executor_is_paper

    class _PaperClob:
        def _effective_paper(self):
            return True

    class _LiveClob:
        def _effective_paper(self):
            return False

    assert _executor_is_paper(None) is False
    assert _executor_is_paper(SimpleNamespace(clob=_PaperClob())) is True
    assert _executor_is_paper(SimpleNamespace(clob=_LiveClob())) is False


def test_executor_is_paper_live_global_without_override(monkeypatch):
    from core import config
    from bots.bot_d_weather.__main__ import _executor_is_paper

    monkeypatch.setenv("POLYMARKET_ENV", "live")
    config.reset_settings()
    assert _executor_is_paper(SimpleNamespace(clob=SimpleNamespace(paper_override=False))) is False
    config.reset_settings()


def test_live_reconcile_requires_known_bot_d_order():
    """Shared live wallets must not import other bots' CLOB fills as Bot D."""
    from bots.bot_d_weather.__main__ import run_loop

    src = inspect.getsource(run_loop)
    assert "portfolio.reconcile_live_fills(" in src
    assert "require_known_order=True" in src
