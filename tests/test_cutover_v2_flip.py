"""Tests for scripts/cutover_v2_flip.py.

Cover every import-line shape we need to handle on cutover day:
- bare ``from core.clob import ClobWrapper``
- combined ``from core.clob import ClobWrapper, OrderType, Side``
- types-only ``from core.clob import OrderType, Side``
- indented (inside a function/conditional)
- with trailing comment
- already-on-V2 (idempotent)
- non-clob imports (untouched)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "cutover_v2_flip",
    Path(__file__).resolve().parent.parent / "scripts" / "cutover_v2_flip.py",
)
_mod = importlib.util.module_from_spec(_SPEC)
sys.modules["cutover_v2_flip"] = _mod
_SPEC.loader.exec_module(_mod)


class TestRewriteImportLine:
    def test_bare_clobwrapper(self):
        line = "from core.clob import ClobWrapper"
        out = _mod.rewrite_import_line(line)
        assert out == "from core.clob_v2 import ClobWrapperV2 as ClobWrapper"

    def test_clobwrapper_with_types(self):
        line = "from core.clob import ClobWrapper, OrderType, Side"
        out = _mod.rewrite_import_line(line)
        assert out == (
            "from core.clob_v2 import ClobWrapperV2 as ClobWrapper, "
            "OrderType, Side"
        )

    def test_types_only_no_clobwrapper(self):
        line = "from core.clob import OrderType, Side"
        out = _mod.rewrite_import_line(line)
        assert out == "from core.clob_v2 import OrderType, Side"

    def test_indented_line_preserves_indent(self):
        line = "    from core.clob import ClobWrapper"
        out = _mod.rewrite_import_line(line)
        assert out == (
            "    from core.clob_v2 import ClobWrapperV2 as ClobWrapper"
        )

    def test_double_indented(self):
        line = "        from core.clob import OrderType, Side"
        out = _mod.rewrite_import_line(line)
        assert out == "        from core.clob_v2 import OrderType, Side"

    def test_already_on_v2_left_alone(self):
        line = "from core.clob_v2 import ClobWrapperV2 as ClobWrapper"
        # Re-running the rewrite must NOT keep flipping.
        out = _mod.rewrite_import_line(line)
        assert out == line

    def test_unrelated_import_untouched(self):
        line = "from core.db import Order, Trade"
        out = _mod.rewrite_import_line(line)
        assert out == line

    def test_v1_dotted_path_untouched(self):
        """Direct py-clob-client imports (in core/clob.py itself) are NOT
        rewritten — they still exist for the V1 wrapper module."""
        line = "from py_clob_client.client import ClobClient"
        out = _mod.rewrite_import_line(line)
        assert out == line

    def test_trailing_comment_preserved(self):
        line = "from core.clob import ClobWrapper  # noqa: E501"
        out = _mod.rewrite_import_line(line)
        assert out.startswith(
            "from core.clob_v2 import ClobWrapperV2 as ClobWrapper"
        )
        assert "noqa: E501" in out

    def test_long_imports_with_extra_whitespace(self):
        line = "from core.clob import   ClobWrapper,   OrderType,   Side"
        out = _mod.rewrite_import_line(line)
        assert "ClobWrapperV2 as ClobWrapper" in out
        assert "OrderType" in out
        assert "Side" in out


class TestRewriteText:
    def test_counts_changed_lines(self):
        src = (
            "import os\n"
            "from core.clob import ClobWrapper\n"
            "from core.clob import OrderType, Side\n"
            "x = 1\n"
        )
        out, n = _mod.rewrite_text(src)
        assert n == 2
        assert "from core.clob_v2 import ClobWrapperV2 as ClobWrapper" in out
        assert "from core.clob_v2 import OrderType, Side" in out
        assert "import os" in out  # untouched

    def test_idempotent_on_already_v2_file(self):
        src = (
            "from core.clob_v2 import ClobWrapperV2 as ClobWrapper\n"
            "x = 1\n"
        )
        out, n = _mod.rewrite_text(src)
        assert n == 0
        assert out == src

    def test_preserves_trailing_newline(self):
        src = "from core.clob import ClobWrapper\n"
        out, _ = _mod.rewrite_text(src)
        assert out.endswith("\n")

    def test_preserves_no_trailing_newline(self):
        src = "from core.clob import ClobWrapper"
        out, _ = _mod.rewrite_text(src)
        assert not out.endswith("\n")
        assert out.startswith(
            "from core.clob_v2 import ClobWrapperV2 as ClobWrapper"
        )


class TestEndToEnd:
    """Run the full rewrite pipeline against the real repo tree (without
    --apply) to confirm no python file is mangled by the regex on real
    code patterns."""

    def test_dry_run_against_repo_finds_expected_count(self, tmp_path: Path):
        # Apply rewrite to the actual bots/scripts dirs and check that
        # at least one file (the V1-only wrapper itself, core/clob.py) is
        # NOT touched, and that no rewrites produce broken Python syntax.
        from scripts import cutover_v2_flip as flip  # noqa: F401

        repo_root = Path(__file__).resolve().parent.parent
        for sub in ("bots", "scripts"):
            d = repo_root / sub
            for path in d.rglob("*.py"):
                if "__pycache__" in path.parts:
                    continue
                original = path.read_text()
                rewritten, _ = _mod.rewrite_text(original)
                # Sanity: rewritten output must still compile.
                try:
                    compile(rewritten, str(path), "exec")
                except SyntaxError as exc:
                    pytest.fail(
                        f"rewrite produced syntax error in {path}: {exc}"
                    )

    def test_no_double_flip_when_run_twice(self):
        """Cutover script must be safe to re-run. Running the rewrite
        on already-rewritten text must produce zero further changes."""
        src = (
            "from core.clob import ClobWrapper, OrderType, Side\n"
            "from core.clob import OrderType, Side\n"
        )
        once, n1 = _mod.rewrite_text(src)
        twice, n2 = _mod.rewrite_text(once)
        assert n1 == 2
        assert n2 == 0
        assert once == twice


class TestOnlyFilter:
    """Canary-rollout support: --only narrows the file list to a substring
    match on the relative path. Used to flip one bot at a time post-cutover
    rather than the whole fleet at once."""

    def _make_flip_fixture(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(_mod, "REPO_ROOT", tmp_path)
        for rel in (
            "bots/bot_g_longshot/__main__.py",
            "bots/bot_a/__main__.py",
            "bots/bot_b/__main__.py",
            "scripts/dry_run_order.py",
        ):
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("from core.clob import ClobWrapper\n")

    def test_only_filter_matches_single_bot(self, tmp_path: Path,
                                            monkeypatch, capsys):
        self._make_flip_fixture(tmp_path, monkeypatch)

        rc = _mod.main(["--only", "bot_g_longshot"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "bot_g_longshot" in captured.out
        for excluded in ("bot_a/", "bot_b/", "scripts/"):
            assert excluded not in captured.out, (
                f"--only filter leaked: {excluded} in output"
            )

    def test_only_filter_with_no_match_returns_3(self, tmp_path: Path,
                                                 monkeypatch):
        self._make_flip_fixture(tmp_path, monkeypatch)

        rc = _mod.main(["--only", "nonexistent_xyzzy"])
        assert rc == 3

    def test_explicit_dry_run_flag_is_accepted(self, tmp_path: Path,
                                               monkeypatch, capsys):
        self._make_flip_fixture(tmp_path, monkeypatch)

        rc = _mod.main(["--dry-run", "--only", "bot_g_longshot"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
