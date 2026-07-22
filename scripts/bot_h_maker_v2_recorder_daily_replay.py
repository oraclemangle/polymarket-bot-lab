"""Daily wrapper around maker_flow_recorder_replay.

Runs the replay simulator on `data/maker_recorder.db` and writes:

  - `data/reports/maker_flow_replay/YYYY-MM-DD.{md,json}` (dated archive)
  - `data/reports/maker_flow_replay/latest.{md,json}` (always up-to-date,
    used by the dashboard)

Optionally prunes archive files older than `--retain-days` (default 90)
so the report directory stays bounded.

Designed for a daily systemd timer. Read-only against the recorder DB
(opened in `?mode=ro`); writes only to `data/reports/`.

Usage:

    python -m scripts.bot_h_maker_v2_recorder_daily_replay \\
        [--db-path data/maker_recorder.db] \\
        [--reports-dir data/reports/maker_flow_replay] \\
        [--retain-days 90] \\
        [--min-events 1000]
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "maker_recorder.db"
DEFAULT_REPORTS_DIR = REPO_ROOT / "data" / "reports" / "maker_flow_replay"

log = logging.getLogger(__name__)


def _prune_old_reports(reports_dir: Path, retain_days: int) -> int:
    """Delete dated archive files (`YYYY-MM-DD.{md,json}`) older than
    `retain_days`. Returns the number of files removed.

    `latest.md` / `latest.json` are NEVER pruned regardless of mtime.
    """
    if not reports_dir.exists():
        return 0
    cutoff = time.time() - retain_days * 86400
    n = 0
    for p in reports_dir.iterdir():
        if not p.is_file():
            continue
        if p.name.startswith("latest."):
            continue
        if p.suffix not in (".md", ".json"):
            continue
        # Only prune files matching the YYYY-MM-DD prefix shape so we
        # don't accidentally nuke unrelated content.
        stem = p.stem
        if len(stem) != 10 or stem[4] != "-" or stem[7] != "-":
            continue
        if p.stat().st_mtime < cutoff:
            try:
                p.unlink()
                n += 1
            except OSError as exc:
                log.warning("daily_replay.prune.failed path=%s err=%s", p, exc)
    return n


def _run_replay(db_path: Path, dated_out: Path, min_events: int) -> int:
    """Invoke the replay script in-process. Returns the exit code from
    `run_replay`."""
    from scripts.research.maker_flow_recorder_replay import (
        render_markdown,
        run_replay,
    )

    report = run_replay(db_path=db_path, min_events=min_events)
    md = render_markdown(report)
    dated_out.parent.mkdir(parents=True, exist_ok=True)
    dated_out.write_text(md)
    json_out = dated_out.with_suffix(".json")
    import json as json_module

    json_out.write_text(json_module.dumps(report, indent=2, default=str))
    log.info(
        "daily_replay.dated_written md=%s json=%s ok=%s",
        dated_out,
        json_out,
        report.get("ok"),
    )
    if not report.get("ok"):
        return 0  # Insufficient data is not a failure for cron
    if not report["phase_2_gate"]["build_authorised"]:
        if report["phase_2_gate"]["spec_amendment_needed"]:
            return 2
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--retain-days", type=int, default=90)
    parser.add_argument("--min-events", type=int, default=1000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not args.db_path.exists():
        log.warning(
            "daily_replay.db_missing path=%s — recorder hasn't deployed; nothing to do",
            args.db_path,
        )
        return 0

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    dated_out = args.reports_dir / f"{today}.md"
    rc = _run_replay(args.db_path, dated_out, args.min_events)

    # Update latest.{md,json} as a copy (not symlink — Polymarket VPS
    # is single-host and copies are simpler for the dashboard's static
    # file fetch).
    latest_md = args.reports_dir / "latest.md"
    latest_json = args.reports_dir / "latest.json"
    try:
        shutil.copyfile(dated_out, latest_md)
        shutil.copyfile(dated_out.with_suffix(".json"), latest_json)
        log.info("daily_replay.latest_updated md=%s json=%s", latest_md, latest_json)
    except FileNotFoundError as exc:
        log.warning("daily_replay.latest_copy_failed err=%s", exc)

    pruned = _prune_old_reports(args.reports_dir, args.retain_days)
    if pruned:
        log.info("daily_replay.pruned files=%d retain_days=%d", pruned, args.retain_days)

    return rc


if __name__ == "__main__":
    sys.exit(main())
