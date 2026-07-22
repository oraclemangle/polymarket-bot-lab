"""Bot E daily calibration-gate runner.

Phase 4 audit 2026-04-17. Cron-friendly wrapper around
`bot_e_calibration_spike.py` that:
1. Runs the full calibration pipeline against the recorder DB.
2. Writes `data/bot_e_calibration.json` with realistic fill-rate + adverse
   stats (per Phase 4 spike enhancements).
3. Exits 0 if GO, 2 if NO-GO (so systemd timers can react).
4. Optionally posts a Telegram summary via the notify daemon's webhook
   if `BOT_E_CALIBRATION_NOTIFY=true`.

Intended cron schedule: daily at 04:00 UTC after the recorder has accumulated
24h of fresh data. On the bot host:

    [Unit]
    Description=Bot E calibration gate

    [Service]
    Type=oneshot
    WorkingDirectory=/home/bot/polymarket-bot
    ExecStart=.venv/bin/python -m scripts.bot_e_calibration_gate

    [Timer]
    OnCalendar=daily
    Persistent=true
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("bot_e_calibration_gate")

LOCK_PATH = Path("data/.bot_e_calibration.lock")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )

    # Concurrency guard: the spike loads ~1.4M cex_trades + ~250k pm_events
    # into memory (see scripts/bot_e_calibration_spike.py load_cex_prices +
    # simulate_maker_fills). Two concurrent runs blew the bot host past its 8G
    # limit on 2026-04-24 and pushed the the homelab hypervisor into swap-thrashing
    # at load 24. flock skip-on-collision avoids that without crashing the
    # systemd timer or alarming.
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_fh = LOCK_PATH.open("w")
    try:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.warning("calibration_gate.already_running path=%s — skipping this run", LOCK_PATH)
        return 0

    # Run the calibration spike. It writes data/bot_e_calibration.json
    # and docs/bot-e-calibration-report.md as side effects.
    try:
        from scripts import bot_e_calibration_spike
        bot_e_calibration_spike.main()
    except SystemExit as e:
        # Spike calls sys.exit(1) when the DB is missing; propagate.
        return int(e.code or 0)
    except Exception as exc:
        log.error("calibration_gate.spike_failed err=%s", exc, exc_info=True)
        return 1

    # Read the calibration JSON the spike just wrote and extract the verdict.
    out_json = Path("data/bot_e_calibration.json")
    if not out_json.exists():
        log.error("calibration_gate.json_missing path=%s", out_json)
        return 1
    try:
        doc = json.loads(out_json.read_text())
    except Exception as exc:
        log.error("calibration_gate.json_parse_failed err=%s", exc)
        return 1

    ready = bool(doc.get("ready"))
    reasons = doc.get("no_go_reasons") or []
    cal = doc.get("calibration") or {}
    fill = doc.get("fill_realism") or {}

    summary = (
        f"ready={ready} "
        f"n_signals={cal.get('n_signals', 0)} "
        f"wr={cal.get('overall_realised_winrate', 0):.3f} "
        f"ece={cal.get('overall_ece', 0):.3f} "
        f"fill_rate={fill.get('fill_rate', 0):.3f} "
        f"adverse_rate={fill.get('adverse_rate', 0):.3f}"
    )
    if ready:
        log.info("calibration_gate.GO %s", summary)
    else:
        log.warning(
            "calibration_gate.NO_GO %s reasons=%s",
            summary, "; ".join(reasons),
        )

    # Optional: notify via Telegram. Import lazily so tests don't touch it.
    if os.environ.get("BOT_E_CALIBRATION_NOTIFY", "").lower() in ("true", "1", "yes"):
        try:
            from core.notify import send_telegram_alert  # type: ignore[attr-defined]
            verdict = "GO" if ready else "NO-GO"
            msg = f"Bot E calibration: {verdict}\n{summary}"
            if reasons:
                msg += "\nreasons: " + "; ".join(reasons[:3])
            send_telegram_alert(msg)
        except Exception as exc:
            log.warning("calibration_gate.notify_failed err=%s", exc)

    return 0 if ready else 2


if __name__ == "__main__":
    sys.exit(main())
