"""Shared pytest fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Force paper mode and isolate DB before any core module is imported.
os.environ.setdefault("POLYMARKET_ENV", "paper")


@pytest.fixture
def tmp_db(tmp_path, monkeypatch) -> Path:
    """Use a fresh SQLite DB for each test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("POLYMARKET_DB_PATH", str(db_path))

    # Reset the lazy singletons so they pick up the new env.
    from core import config, db

    config.reset_settings()
    db.reset_engine()
    # Re-read settings and initialise the schema.
    config.settings = config.get_settings()
    db.init_db()
    yield db_path
    db.reset_engine()
    config.reset_settings()
