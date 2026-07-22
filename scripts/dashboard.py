#!/usr/bin/env python3
"""Compatibility wrapper for the dashboard backend entrypoint."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.server import ROUTES as API_ROUTES
from dashboard.server import DashboardHandler, ThreadingHTTPServer, main


if __name__ == "__main__":
    raise SystemExit(main())
