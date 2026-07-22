#!/usr/bin/env python3
"""Cutover-day import flip from V1 ClobWrapper to V2 ClobWrapperV2.

Apply this on **2026-04-28 post-11:00 UTC** after Polymarket's V2 cutover
completes and ``pip install py-clob-client-v2>=1.0.0`` has run on the bot host.
Pre-cutover use is unsafe: V2 SDK calls against the V1 endpoint will fail
with auth/EIP-712 mismatches.

What it does
------------
Walks ``bots/`` and ``scripts/`` and rewrites three V1 import patterns to
their V2 equivalents:

  from core.clob import ClobWrapper
    → from core.clob_v2 import ClobWrapperV2 as ClobWrapper

  from core.clob import ClobWrapper, OrderType, Side
    → from core.clob_v2 import ClobWrapperV2 as ClobWrapper, OrderType, Side

  from core.clob import OrderType, Side
    → from core.clob_v2 import OrderType, Side

The script is idempotent — files already on V2 (importing from
``core.clob_v2``) are skipped. ``--dry-run`` (default) prints a diff;
``--apply`` writes the changes in place.

Usage
-----
    # Preview every file that would change (no writes):
    .venv/bin/python scripts/cutover_v2_flip.py

    # Apply the flips:
    .venv/bin/python scripts/cutover_v2_flip.py --apply

Exit codes
----------
    0 = success (or no changes needed)
    2 = unexpected exception
    3 = invalid args / no files found
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SEARCH_DIRS = ("bots", "scripts")

log = logging.getLogger("cutover_v2_flip")

# Regex matches ``from core.clob import <names>`` where <names> is a
# comma-separated list. Group 1 captures the names list verbatim.
_IMPORT_RE = re.compile(
    r"^(?P<indent>\s*)from\s+core\.clob\s+import\s+(?P<names>[^\n#]+?)(?P<trail>\s*(?:#.*)?)$",
    re.MULTILINE,
)


def rewrite_import_line(line: str) -> str:
    """Rewrite a single ``from core.clob import …`` line to its V2 form.

    Returns the line unchanged if it isn't a matching import. The four
    expected shapes (with optional trailing comments) are all handled by
    a single regex over the names tuple.
    """
    m = _IMPORT_RE.match(line)
    if m is None:
        return line
    indent = m.group("indent")
    names = m.group("names").strip()
    trail = m.group("trail")
    parts = [p.strip() for p in names.split(",") if p.strip()]

    # Translate ClobWrapper → 'ClobWrapperV2 as ClobWrapper'. Other names
    # (OrderType, Side, exceptions) are re-exported by clob_v2 unchanged.
    new_parts = []
    for p in parts:
        if p == "ClobWrapper":
            new_parts.append("ClobWrapperV2 as ClobWrapper")
        else:
            new_parts.append(p)

    return f"{indent}from core.clob_v2 import {', '.join(new_parts)}{trail}"


def rewrite_text(text: str) -> tuple[str, int]:
    """Apply ``rewrite_import_line`` to every line of ``text``.

    Returns ``(new_text, n_lines_changed)``.
    """
    out_lines: list[str] = []
    changed = 0
    for line in text.splitlines(keepends=True):
        # splitlines(True) preserves the trailing \n; strip it for regex,
        # then add it back.
        suffix = ""
        body = line
        for term in ("\r\n", "\n", "\r"):
            if body.endswith(term):
                suffix = term
                body = body[: -len(term)]
                break
        rewritten = rewrite_import_line(body)
        if rewritten != body:
            changed += 1
        out_lines.append(rewritten + suffix)
    return "".join(out_lines), changed


def _list_python_files(roots: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    self_path = Path(__file__).resolve()
    for root in roots:
        d = REPO_ROOT / root
        if not d.exists():
            continue
        for p in d.rglob("*.py"):
            if "__pycache__" in p.parts or not p.is_file():
                continue
            # Skip this script itself — its docstring contains literal
            # "from core.clob import …" examples which match the regex.
            if p.resolve() == self_path:
                continue
            files.append(p)
    return sorted(files)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true",
                      help="Write changes in place. Default: dry-run only.")
    mode.add_argument("--dry-run", action="store_false", dest="apply",
                      help="Preview changes without writing. This is the default.")
    p.add_argument("--root", action="append", default=None,
                   help="Subtree to search (relative to repo root). "
                        f"Repeatable. Default: {list(SEARCH_DIRS)}")
    p.add_argument("--only", default=None,
                   help="Substring filter on file paths (relative to repo root). "
                        "Use to canary-flip a single bot or directory before "
                        "applying fleet-wide. Example: --only bot_g_longshot")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args(argv)

    roots = tuple(args.root) if args.root else SEARCH_DIRS
    files = _list_python_files(roots)
    if args.only:
        files = [
            p for p in files
            if args.only in str(p.relative_to(REPO_ROOT))
        ]
    if not files:
        print("no python files found under", roots, file=sys.stderr)
        return 3

    total_changed_files = 0
    total_changed_lines = 0
    for path in files:
        try:
            original = path.read_text()
        except Exception as exc:
            log.warning("skip %s: %s", path, exc)
            continue
        rewritten, n = rewrite_text(original)
        if n == 0:
            continue
        total_changed_files += 1
        total_changed_lines += n
        rel = path.relative_to(REPO_ROOT)
        print(f"-- {rel}: {n} import line(s) flipped --")
        # Show only the changed lines for review.
        for orig_line, new_line in zip(
            original.splitlines(), rewritten.splitlines(),
            strict=False,
        ):
            if orig_line != new_line:
                print(f"  - {orig_line}")
                print(f"  + {new_line}")
        if args.apply:
            path.write_text(rewritten)

    print()
    if total_changed_files == 0:
        print("=== Already on V2: nothing to flip. ===")
    elif args.apply:
        print(
            f"=== APPLIED: {total_changed_lines} line(s) across "
            f"{total_changed_files} file(s) flipped to V2. ==="
        )
    else:
        print(
            f"=== DRY RUN: {total_changed_lines} line(s) across "
            f"{total_changed_files} file(s) would flip. "
            f"Re-run with --apply to write. ==="
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
