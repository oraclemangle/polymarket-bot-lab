"""Repo-calibrated secret material scan.

This intentionally does not fail on public Polymarket contract addresses,
condition IDs, order IDs, placeholder env-var names, or archived research
wallet examples. It is designed to catch committed age payloads, private-key
assignments, and non-placeholder secret values.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

TEXT_EXTENSIONS = {
    ".env",
    ".example",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

DEFAULT_EXCLUDE_PARTS = {
    ".claude",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}

AGE_PATTERNS = (
    re.compile(r"-----BEGIN AGE " r"ENCRYPTED FILE-----"),
    re.compile(r"age-encryption" r"\.org/v1"),
    re.compile(r"\bage1[0-9a-z]{20,}\b"),
)

PRIVATE_KEY_ASSIGNMENT = re.compile(
    r"(?i)\b(?:POLYMARKET_|POLYGON_)?PRIVATE_KEY\s*[:=]\s*"
    r"['\"]?(0x[a-f0-9]{64}|[a-f0-9]{64})['\"]?"
)

SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:API_KEY|SECRET_KEY|CLOB_SECRET|TOKEN|PASSPHRASE)\s*[:=]\s*"
    r"['\"]?([A-Za-z0-9_./+=:-]{32,})['\"]?"
)

PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "redacted",
    "redacted-test-value",
    "supersecret",
    "test-secret-32-bytes-long-padding",
    "your_private_key_here",
}


def _is_text_candidate(path: Path) -> bool:
    if path.name == ".env":
        return True
    if path.suffix in TEXT_EXTENSIONS:
        return True
    if path.name.endswith(".env.example"):
        return True
    return False


def _is_excluded(path: Path, root: Path, extra_excludes: set[str]) -> bool:
    rel = path.relative_to(root)
    parts = set(rel.parts)
    return bool(parts & (DEFAULT_EXCLUDE_PARTS | extra_excludes))


def _is_placeholder(value: str) -> bool:
    stripped = value.strip().strip("'\"")
    if stripped.lower() in PLACEHOLDER_VALUES:
        return True
    if stripped.startswith("$") or stripped.startswith("${"):
        return True
    if "<" in stripped and ">" in stripped:
        return True
    if stripped.startswith(("settings.", "config.", "os.environ", "getenv(")):
        return True
    return False


def scan(root: Path, *, extra_excludes: set[str] | None = None) -> list[str]:
    root = root.resolve()
    excludes = extra_excludes or set()
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if _is_excluded(path, root, excludes):
            continue
        if not _is_text_candidate(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root)
        for line_no, line in enumerate(text.splitlines(), 1):
            if any(p.search(line) for p in AGE_PATTERNS):
                findings.append(f"{rel}:{line_no}: age encrypted material marker")
                continue
            if PRIVATE_KEY_ASSIGNMENT.search(line):
                findings.append(f"{rel}:{line_no}: private key assignment")
                continue
            secret_match = SECRET_ASSIGNMENT.search(line)
            if secret_match and not _is_placeholder(secret_match.group(1)):
                findings.append(f"{rel}:{line_no}: non-placeholder secret-looking assignment")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional path component to exclude, repeatable.",
    )
    args = parser.parse_args(argv)
    findings = scan(args.root, extra_excludes=set(args.exclude))
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
