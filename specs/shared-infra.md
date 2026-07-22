# Shared Infrastructure Spec

**Status:** Specified, not built
**Last updated:** 2026-04-14
**Role:** Modules both Bot A and Bot B depend on. Built once in Week 1 before any bot code. Total build estimate: **6.25 working days** over ~10 calendar days in a single rotation home window.

This spec is self-contained.

---

## Top-level directory layout

```
polymarket-bot/                  # (eventual — currently at ~/Code/next-build)
├── core/
│   ├── __init__.py
│   ├── clob.py                  # CLOB client wrapper (auth, signing, retry)
│   ├── keystore.py              # Age-encrypted private key management
│   ├── ingest.py                # Market scraper + book snapshotter + WSS
│   ├── db.py                    # SQLAlchemy models + session
│   ├── portfolio.py             # Position tracking + PnL + HMRC log
│   ├── watchdog.py              # Kill-switches + health checks
│   ├── notify.py                # Telegram alerts
│   ├── backtest.py              # Replay harness
│   └── config.py                # Environment loading + global constants
├── migrations/                   # Alembic
├── scripts/
│   ├── dry_run_order.py         # $5 place-and-cancel sanity check
│   └── unlock_keystore.py       # Boot-time passphrase loader
├── systemd/
│   ├── polymarket-bot-a.service
│   ├── polymarket-bot-b.service
│   └── polymarket-watchdog.service
├── infra/
│   └── vpn/
│       └── vpn-wg-split.conf.example
└── .env.example
```

Bots live at `bots/bot_a/` and `bots/bot_b/`. They import from `core/` only.

---

## 1. `core/clob.py` — CLOB client wrapper (1 day)

### Purpose
Thin wrapper around `py-clob-client` exposing only what the bots need. Adds retry, rate-limit awareness, and structured error types.

### Public API
```python
class ClobWrapper:
    def __init__(self, keystore: Keystore, chain_id: int = 137)

    # Market data (public)
    def get_book(token_id: str) -> OrderBook
    def get_tick_size(token_id: str) -> Decimal
    def get_midpoint(token_id: str) -> Decimal
    def get_fee_rate(token_id: str) -> Decimal

    # Orders (authenticated)
    def place_limit(token_id, price, size, side, order_type=GTC) -> OrderResponse
    def cancel_order(order_id: str) -> bool
    def cancel_all(market_id: str | None = None) -> int

    # Lifecycle
    def get_user_orders(market_id=None) -> list[Order]
    def get_user_trades(since=None) -> list[Trade]

    # WSS
    async def subscribe_user_channel(callback) -> None
    async def subscribe_market_channel(token_ids: list[str], callback) -> None
```

### Implementation notes
- Retry via `tenacity`: `wait_exponential(multiplier=0.5, min=0.5, max=8)`, `retry=retry_if_exception_type((PolyApiException, httpx.ConnectTimeout, httpx.ReadTimeout))`, `stop_after_attempt(5)`, `reraise=True`
- Local token-bucket at 80% of published CLOB rate limits (see `research/clob-spec.md` §3.4)
- **Never logs the private key or API secret.** Structured logging redacts.
- HMAC canonical string must be verified against `py_clob_client/signing/hmac.py` source before first live request (`docs/open-questions.md` OQ-006)

### Blocked by
- OQ-006: HMAC canonical string verified
- OQ-007: verifyingContract addresses verified
- OQ-008: USDC.e vs native USDC confirmed

---

## 2. `core/keystore.py` — Key management (1 day)

### Purpose
Hold the hot wallet's private key securely, decrypt on daemon start, never persist decrypted bytes to disk.

### Design
- Encrypted keystore: `~/.config/polymarket-bot/keystore.age`
- Encryption: `age` (preferred over gpg for simplicity + modern crypto)
- Passphrase: populated into tmpfs path (e.g. `/run/user/$UID/polymarket/passphrase`) via SSH on boot, read by systemd `ExecStartPre`, zeroed after `ExecStart` reads it
- Decrypted key held in a `SecureBytes` wrapper inside the running process; never written back to disk

### Public API
```python
class Keystore:
    @classmethod
    def load(cls, keystore_path: Path, passphrase_path: Path) -> 'Keystore'
    def signer(self) -> EthereumSigner   # handed to py-clob-client
    def address(self) -> ChecksumAddress
    # No method returns the raw key bytes.
```

### Operational
- `scripts/unlock_keystore.py` — interactive helper for first-time setup and emergency unlock
- Backup: keystore file is age-encrypted; safe to back up to Backblaze B2 daily (the passphrase is never stored)
- **No hardware wallet path in v1** (see ADR-009)

### Ledger treasury
Treasury wallet is a separate EOA on a Ledger device. Hot-wallet top-ups are manual: user signs a treasury → hot transfer via Ledger Live or similar. This project never touches the Ledger private key.

---

## 3. `core/ingest.py` — Market data ingestion (1.5 days)

### Purpose
Keep the local DB up to date on markets, books, and trades. Feeds both bots.

### Components

**Scraper (cron: every 15 min)**
- Fetches active markets via Gamma API (`/markets` paginated)
- Upserts to `markets` table: condition_id, outcome tokens, category, question, end_date, volume_24h, fee_rate

**Book snapshotter (cron: every 5 min)**
- For each market in the active set (positions + candidates), fetches `/book?token_id=...`
- Writes to `books` snapshot table with timestamp
- Also used by backtest harness

**Trade stream (always-on async)**
- WSS `user` channel subscription
- On every fill event, writes to `trades` table and emits to portfolio + notify

**Settlement watcher (cron: every 1h)**
- Polls UMA subgraph for resolution events on markets we hold
- On resolution: triggers redeem flow via CLOB + on-chain tx
- Updates `positions.status = 'redeemed'`

### Failure handling
- Scraper crash: systemd restart; if 3× in 1h, halt + alert
- WSS drop: auto-reconnect with exponential backoff; if disconnected >5 min, halt entries
- All external calls via VPN (see §9 below)

---

## 4. `core/db.py` + `migrations/` — Storage (0.5 days)

### Schema (SQLite v1; Postgres-compatible SQL)

```sql
-- Market catalogue (shared)
CREATE TABLE markets (
    condition_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    question TEXT NOT NULL,
    end_date TIMESTAMP,
    fee_rate_bps INTEGER,
    yes_token_id TEXT,
    no_token_id TEXT,
    is_neg_risk INTEGER DEFAULT 0,
    last_updated TIMESTAMP NOT NULL
);

-- Book snapshots
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id TEXT NOT NULL,
    snapshot_at TIMESTAMP NOT NULL,
    bids JSON,  -- [[price, size], ...]
    asks JSON,
    UNIQUE(token_id, snapshot_at)
);

-- Orders (per-bot)
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,  -- 'bot_a' | 'bot_b'
    condition_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    side TEXT NOT NULL,  -- 'BUY' | 'SELL'
    price DECIMAL,
    size DECIMAL,
    status TEXT,  -- 'OPEN' | 'FILLED' | 'CANCELLED' | 'PARTIAL'
    order_type TEXT,  -- 'GTC' | 'GTD' | 'FOK' | 'FAK'
    placed_at TIMESTAMP,
    last_updated TIMESTAMP
);

-- Fills
CREATE TABLE trades (
    trade_id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    order_id TEXT,
    condition_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    side TEXT NOT NULL,
    price DECIMAL,
    size DECIMAL,
    fee_usd DECIMAL,
    filled_at TIMESTAMP NOT NULL,
    -- HMRC-ready fields
    usd_gbp_rate DECIMAL NOT NULL,  -- at fill time
    gbp_notional DECIMAL NOT NULL
);

-- Positions (per-bot)
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id TEXT NOT NULL,
    condition_id TEXT NOT NULL,
    token_id TEXT NOT NULL,  -- which outcome we hold
    side TEXT NOT NULL,  -- 'YES' | 'NO'
    size DECIMAL NOT NULL,
    avg_price DECIMAL NOT NULL,
    cost_basis_usd DECIMAL NOT NULL,
    status TEXT,  -- 'OPEN' | 'CLOSED' | 'REDEEMED' | 'DISPUTED'
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP
);

-- Daily PnL snapshots
CREATE TABLE pnl_snapshots (
    bot_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    realised_usd DECIMAL,
    unrealised_usd DECIMAL,
    open_exposure_usd DECIMAL,
    drawdown_pct DECIMAL,
    PRIMARY KEY (bot_id, snapshot_date)
);

-- Events (kill-switches, halts, alerts)
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id TEXT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,  -- 'info' | 'warn' | 'kill'
    message TEXT NOT NULL,
    payload JSON,
    created_at TIMESTAMP NOT NULL
);

-- Bot B only: scores
CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    condition_id TEXT NOT NULL,
    scored_at TIMESTAMP NOT NULL,
    dispute_risk DECIMAL,
    claude_pick TEXT,          -- 'YES' | 'NO' | 'SKIP' -- FIXED persistence
    claude_confidence DECIMAL, -- FIXED persistence
    claude_implied_prob DECIMAL,
    resolution_prediction TEXT,
    model_version TEXT NOT NULL
);

-- Bot B only: RAG corpus passthrough (from upstream price_requests)
CREATE TABLE price_requests (
    id INTEGER PRIMARY KEY,
    ancillary_decoded TEXT,
    resolved_price DECIMAL,
    is_resolved INTEGER,
    dispute_count INTEGER,
    final_outcome TEXT,
    imported_at TIMESTAMP NOT NULL
);
```

### Migrations
- Alembic; revision files in `migrations/versions/`
- First migration creates all tables above
- Every schema change ships as a new revision

### Backup
- Daily `restic` snapshot of `data/*.db` to Backblaze B2 (encrypted)
- Cost: ~$0.01/month

---

## 5. `core/portfolio.py` — Position + PnL tracking (1 day)

### Purpose
On every fill, reconcile positions; on every mark-to-market call, compute unrealised PnL; expose per-bot bankroll + exposure + drawdown.

### Public API
```python
class Portfolio:
    def on_fill(trade: Trade) -> None
    def on_resolution(condition_id: str, outcome: str) -> None
    def on_redeem(position_id: int, usdc_received: Decimal) -> None

    def get_bot_bankroll(bot_id: str) -> Decimal   # realised + collateral
    def get_open_exposure(bot_id: str) -> Decimal
    def get_realised_pnl(bot_id: str, since: datetime = None) -> Decimal
    def get_unrealised_pnl(bot_id: str) -> Decimal  # mark = best-bid (conservative)
    def get_drawdown_pct(bot_id: str) -> Decimal   # peak-to-trough over running window
```

### HMRC log
- Every trade row has `usd_gbp_rate` and `gbp_notional` at fill time
- Spot rate source: BoE daily rate, cached in `config.py` (refresh daily)
- Monthly export: `scripts/hmrc_export.py` → CSV suitable for self-assessment

---

## 6. `core/watchdog.py` — Kill-switches + monitoring (0.5 days)

### Purpose
Runs every 60s. Enforces risk controls across both bots. Fails closed.

### Checks
- Per-bot drawdown vs kill threshold (Bot A: −15%, Bot B: −15%, aggregate: −20%)
- Per-bot open exposure vs cap
- Scraper liveness (`ingest.last_run` timestamp)
- Scorer liveness (Bot B's `scores.scored_at` max)
- WSS liveness (last trade event or heartbeat)
- USDC.e peg (via Chainlink / CoinGecko; if >1% deviation for >2h → halt)
- VPN liveness (resolve `clob.polymarket.com` through tunnel; if fails → halt)

### Actions on trigger
1. Call `ClobWrapper.cancel_all()` for the offending bot
2. Set `halt` flag in DB (bots check before every entry)
3. Emit `events` row with severity='kill'
4. `notify.py` sends Telegram alert

### Unhalt
- Only via Telegram command `/unhalt bot_a|bot_b` from allowlisted chat id
- Logged as an event

---

## 7. `core/notify.py` — Telegram alerting (0.25 days)

### Events alerted
- Bot entry placed / filled
- Bot exit triggered / filled
- Position resolved / redeemed
- Kill-switch trigger
- Daily PnL digest (08:00 + 20:00 UTC, regardless of activity)

### Config
- Telegram bot token from env (`TELEGRAM_BOT_TOKEN`)
- Allowed chat id(s) in env (`TELEGRAM_CHAT_ID_ALLOWLIST`)
- `/unhalt bot_a` and `/status` commands listened for

---

## 8. `core/backtest.py` — Replay harness (0.75 days)

### Purpose
Feed historical book snapshots + (for Bot B) historical scores to the bot's decision function. Simulate fills. Compute theoretical PnL.

### Scope (minimum viable)
- Bot A: deterministic replay. Historical `books` + current filters = deterministic entries. Compute P&L at simulated fill price.
- Bot B: replays historical `scores` through sizer + executor. Requires Gemini + ChromaDB access; each run costs ~$2 per 30 simulated days. Cache score outputs.

### Not in scope
- Fancy vectorbt-style harness
- Transaction-cost modelling beyond the fee formula
- Slippage modelling beyond "take the touch"

### Output
- `backtest_run_YYYYMMDD_HHMM.json` — trades, PnL curve, summary stats
- Can diff two runs to check config changes

---

## 9. VPN + network posture (0.25 days)

### WireGuard VPN on the homelab hypervisor
- Config at `/etc/wireguard/vpn.conf` (NOT committed)
- Example at `infra/vpn/vpn-wg-split.conf.example` with variables redacted
- Exit node: Stockholm (se-sto-wg-001) or Amsterdam (nl-ams-wg-001); NOT UK

### Split-tunnel routing
Only these hosts go through VPN:
- `clob.polymarket.com`
- `gamma-api.polymarket.com`
- `ws-subscriptions-clob.polymarket.com`
- `*.thegraph.com` (UMA subgraph)

Everything else (system updates, Telegram, Backblaze B2) goes direct.

### Kill-switch
- `iptables` rules block the above hosts if VPN interface drops
- `wg-quick@vpn.service` ordered before bot services in systemd (`Requires=`, `After=`)
- Watchdog (§6) probes tunneled DNS resolution; halts entries on failure

---

## Systemd unit layout

```
polymarket-wg-vpn.service     (VPN — Required by all below)
polymarket-bot-a.service          (Bot A daemon)
polymarket-bot-b-scraper.service  (Bot B scraper)
polymarket-bot-b-scorer.service   (Bot B scorer)
polymarket-bot-b.service          (Bot B executor, After= scorer)
polymarket-watchdog.service       (Watchdog)
polymarket-notify.service         (Telegram daemon)
```

All with `Restart=on-failure`, `StartLimitBurst=3`, `StartLimitIntervalSec=3600`.

---

## Environment variables (`.env.example`)

```bash
# Secrets — populated at deploy time, never committed
POLYMARKET_KEYSTORE_PATH=/home/operator/.config/polymarket-bot/keystore.age
POLYMARKET_PASSPHRASE_PATH=/run/user/1000/polymarket/passphrase
GOOGLE_API_KEY=           # Bot B Gemini
GROQ_API_KEY=             # Bot B fallback
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID_ALLOWLIST=

# Deploy config
POLYMARKET_ENV=paper      # 'paper' | 'live'
POLYMARKET_DB_PATH=/home/operator/polymarket-bot/data/main.db
BOT_A_BANKROLL_GBP=1000
BOT_B_BANKROLL_GBP=1000
BOT_A_DRAWDOWN_KILL_PCT=15
BOT_B_DRAWDOWN_KILL_PCT=15
AGGREGATE_DRAWDOWN_KILL_PCT=20
MAX_AGGREGATE_EXPOSURE_USD=2000

# Chain
POLYGON_RPC_URL=https://polygon-rpc.com    # override with paid RPC if needed
CHAIN_ID=137
```

---

## Week 1 build order

| Day | Task |
|---|---|
| Mon | `keystore.py` + `clob.py` scaffolds. Amoy testnet order placement. |
| Tue | `clob.py` complete. Retry + rate-limit layer. HMAC verification (OQ-006). |
| Wed | `ingest.py` scraper + book snapshotter. |
| Thu | `db.py` + migrations + `portfolio.py`. |
| Fri | `watchdog.py` + `notify.py` + VPN setup. |
| Sat | `backtest.py` skeleton. |
| Sun | Shared-infra shakedown: $5 Amoy place-cancel, $5 mainnet place-cancel-at-unfillable-price, Telegram alert end-to-end, VPN kill-switch verified. |

### End-of-week gate (all must pass before Week 2)
- [ ] Amoy testnet: one successful $5 order placed + cancelled
- [ ] Mainnet: one successful $5 limit order at deliberately unfillable price, placed + cancelled
- [ ] Encrypted keystore unlocks cleanly on systemd boot
- [ ] Telegram alert fires end-to-end on a simulated drawdown event
- [ ] VPN kill-switch: pulling the WireGuard interface drops CLOB connectivity within 10s
- [ ] All migrations apply clean on a fresh DB
- [ ] Watchdog detects and alerts on a simulated scraper stall

---

## References

- `docs/architecture-decision.md` §6 — original decision
- `docs/decisions-log.md` ADR-007, ADR-009, ADR-013, ADR-014
- `research/clob-spec.md` — all CLOB facts
- `research/order-placement-reference.md` — signed-order reference
- `research/order-example.py` — DO NOT RUN; reference only
