# Bot naming reference

**Last updated:** 2026-05-03 (Session 119 Bot E dashboard decommission)

Each bot has a stable internal identifier (`bot_a`, `bot_b`, ...) used throughout code, databases, env-var prefixes, and historical documents. In 2026-04-20 we added descriptive display names for operators. The internal identifiers DID NOT change — every SQL query, env var, and historical log still uses `bot_a` etc.

## Current fleet

| Internal ID | Display name | Strategy | Status (2026-04-20) |
|---|---|---|---|
| `bot_a` | **Bot Tail Fade (A)** | General binary-market NO-side tail fades (Starmer out, Trump China, etc.) | Archived (ADR-033) |
| `bot_b` | **Bot LLM Kelly (B)** | LLM+RAG directional scorer with Kelly sizing via oraclemangle | Halted (awaiting E2 estimator + ECE validation) |
| `bot_c` | **Bot GBM Directional (C)** | Traditional-asset price GBM directional on crypto + indices | Archived (ADR-034, data-hoover only) |
| `bot_d` | **Bot Weather Fade (D)** | Fade mispriced temperature-tail markets | Paper-trading live |
| `bot_e` | **Bot Maker Flow Recorder (E retired)** | Retired 15-min crypto maker-flow trader; recorder/replay retained | Trading retired by ADR-092; recorder remains shared data infrastructure |
| `bot_f` | **Bot Whale Sensor (F)** | Whale wallet tracking + cascade detection (signals for other bots) | Mirror active, hunter daily |
| `bot_g` | **Bot Longshot Fade (G)** | Near-resolution cheap-side entries on crypto Up/Down (≤2¢ in final 60s) | Paper-trading live (ADR-036) |

Bot E service posture:
- `polymarket-bot-e-recorder.service` — WSS + CEX capture daemon retained as shared data infrastructure
- `polymarket-bot-e-trader.service` — retired from active dashboard/fleet surfaces by ADR-092
- `polymarket-bot-e-calibration.service` — historical ECE analysis service, not part of active trading promotion

Bot F has multiple services:
- `polymarket-bot-f-mirror.service` — read-only whale signal logger
- `polymarket-bot-f-hunter.service` — nightly wallet ranker (timer-triggered)
- `polymarket-bot-f-cascades.service` — daily cascade-detection scan (timer-triggered)

## What this naming change touched

- `systemd/*.service` — all `Description=` lines rewritten to the new display names
- `dashboard/static/index.html` — tab button labels
- `dashboard/static/app.js` — panel titles (per-tab `botXPanels()` functions)
- `tests/dashboard/test_dashboard.py` — tab-label assertions
- Bot G added across dashboard, `runtime_queries.py::query_bot_g`, service unit, tests

## What this change did NOT touch (intentionally)

- `bot_a`, `bot_b`, ..., `bot_g` identifier strings in code, logs, DB tables, env-var prefixes
- Historical entries in `CHANGELOG.md`, `MEMORY.md`, `docs/*.md`, `AUDIT.md` — these are immutable history and would be misleading if rewritten
- Python module names (`bots/bot_a`, `bots/bot_b`, etc.)
- ADR titles referring to "Bot A archived", "Bot C archived" — those are the historic decisions; renaming would obscure them
- Database bot_id foreign keys — rewriting would break every reconcile and P&L query

## When writing new code or docs

Use the display name for human-facing text (dashboard labels, operator messages, Telegram alerts, README):

> "Bot Longshot Fade (G) entered BUY_NO at 0.01 × 250 shares"

Use the internal identifier for code, logs, bot_id columns, env vars:

```python
BOT_ID = "bot_g"
log.info("bot_g.entry_placed cid=%s ...", cid[:16])
config = os.environ.get("BOT_G_FIXED_TRADE_USD", "5")
```

## Naming conventions for future bots

- Internal ID: `bot_X` where X is the next unused letter (after G: H).
- Display name format: `Bot <Descriptive Strategy Name> (<Letter>)`.
- Prefer 2-word strategy names; longer if needed for disambiguation (e.g. "OBI Scalp" vs "Longshot Fade").
- Retire letters are reusable only after archive + a ≥6-month gap to avoid confusion with historical logs.
