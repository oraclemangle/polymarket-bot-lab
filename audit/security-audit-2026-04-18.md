# Security Audit — next-build Polymarket Trading Bot System

**Date:** 2026-04-18  
**Pinned commit:** `4d4c1be` (head of main at 2026-04-17)  
**Audit type:** Production system review (correctness, safety, failure modes)

---

## Executive Summary

**Read order:** MEMORY.md (sessions 17f-17g) → CHANGELOG.md → docs/architecture-decision.md → docs/decisions-log.md (ADR-022 through ADR-028) → docs/kill-dates.md → docs/restart-playbook.md → docs/open-questions.md → docs/audit/bots-a-d-e-audit-responses/README.md → docs/audit/bots-a-d-e-trading-audit-prompt.md → per-bot CLAUDE.md files → codebase.

**Time spent:** ~2.5 hours of focused reading + cross-referencing.

The repository is a production Polymarket trading system with 6 bots (A-F). As of commit `4d4c1be` (2026-04-17), all bots are in **paper mode** after a recent emergency halt/unhalt cycle. The security audit remediation from 2026-04-16 has been applied (8/8 services active on the bot LXC container).

**Single biggest risk:** `core/sd_notify.py` heartbeat mechanism may not catch all async hang vectors — Bot E recorder had 4 systemd restarts today due to 9h40m zombie hang.

**Operable in current state?** Yes — paper only, with significant caveats. Bot B's watchdog is looping every 60s due to stale HTTP scorer; Bot E recorder's writer task may hang without alerting.

**Top 3 fixes for risk reduction:**
1. Fix Bot E recorder's async hang detection (heartbeat should run in writer task, not just discovery task)
2. Verify `POLYMARKET_ENV=live` fallback doesn't override per-bot `BOT_X_ENV=paper` in critical paths
3. Audit `core/clob.py` paper simulator for impossible fills that distort calibration

---

## Findings

### F-001
**Severity:** P0  
**Category:** safety  
**Files:** `core/emergency_halt.py:88-102`, `core/clob.py:245-260`  
**Symptom:** Emergency halt's cancel-all may hit live CLOB even in paper mode.  
**Root cause:** `EmergencyHalter.cancel_all_orders()` at line 95 calls `self.client.cancel_all_orders()` without checking `self.env == "live"`. The paper-mode check exists at line 248 but is bypassed during emergency flows.  
**Evidence:** Line 95-99 iterates markets and cancels without env check; line 248-250 only guards order placement, not cancellation.  
**Suggested fix:** Add `if self.env != "live": return` at line 93 in `emergency_halt.py`.  
**Blast radius:** Could cancel live orders if emergency halt is triggered in live mode or misconfigured.  
**Confidence:** high  
**Depends on:** F-002

### F-002
**Severity:** P1  
**Category:** safety  
**Files:** `core/clob.py:160-165`, `bots/bot_*/__main__.py`  
**Symptom:** Global `POLYMARKET_ENV=live` default could override per-bot `BOT_X_ENV=paper` in non-local paths.  
**Root cause:** `ClobClient.__init__` at line 160 reads `os.getenv("POLYMARKET_ENV", "live")` which defaults to live; per-bot env var `BOT_X_ENV=paper` is only checked in executor.py at line 42. The CLOB client construction in `__main__.py` does not pass bot-specific env.  
**Evidence:** Line 162: `env = os.getenv("POLYMARKET_ENV", "live")` — global default overrides bot-specific config.  
**Suggested fix:** In `__main__.py` per-bot startup, explicitly pass `env=os.getenv(f"BOT_{bot_id}_ENV", "paper")` to ClobClient.  
**Blast radius:** Accidental live trading if global env var set incorrectly.  
**Confidence:** medium  
**Depends on:** None

### F-003
**Severity:** P0  
**Category:** performance  
**Files:** `bots/bot_e_btc_scalp/recorder/capture.py:180-220`, `core/sd_notify.py:45-60`  
**Symptom:** Recorder async hang (NRestarts=4 today) not caught by heartbeat.  
**Root cause:** The `notify_watchdog()` at line 195 runs in the discovery task, but the writer task (line 215) which actually writes to SQLite can hang independently. sd_notify heartbeat only fires when discovery completes, not during writer stalls.  
**Evidence:** Line 195: `self.notify_watchdog()` in `_discover_new_events()`; line 215: `writer.write_batch(self.batch)` in `_write_pending()` — no heartbeat between batch writes.  
**Suggested fix:** Move `notify_watchdog()` to line 218 (after each batch write) and add a timer-based fallback: if >30s since last heartbeat, emit alert.  
**Blast radius:** 9+ hour silent hangs like today; data loss if recorder dies mid-write.  
**Confidence:** high  
**Depends on:** None

### F-004
**Severity:** P1  
**Category:** data  
**Files:** `core/portfolio.py:280-320`, `core/db.py:580-600`  
**Symptom:** Orphan SELL detection may create phantom losses in Bot C's realized P&L.  
**Root cause:** `get_realised_pnl` at line 295 uses `detect_orphan_sells()` which calls `find_candidates_for_filo()` at line 308. The FIFO match at line 312 assumes BUY lot cost basis equals SELL proceeds, but Bot C's Position rows have `cost_basis_usd=0` for some fills (180 rows with $0 realized).  
**Evidence:** `bots/bot_c_pyth/executor.py:125` shows `cost_basis_usd=0` for paper-mode fills passed to Portfolio.on_fill; `portfolio.py:298` calculates `gain_loss = proceeds - cost_basis` which becomes `proceeds - 0 = proceeds` for these orphan cases.  
**Suggested fix:** In `Portfolio.on_fill` for Bot C, set `cost_basis_usd=min(fill_price * size, actual_cost)` not zero.  
**Blast radius:** 180 Bot C fills report $0 realized but $40 open cost basis — P&L queries are inconsistent.  
**Confidence:** high  
**Depends on:** None

### F-005
**Severity:** P2  
**Category:** correctness  
**Files:** `bots/bot_e_btc_scalp/signal.py:95-120`, `bots/bot_e_btc_scalp/recorder/capture.py:155-165`  
**Symptom:** Recorder cursor may not advance past restart if same event ID reappears.  
**Root cause:** Cursor fix at line 105-108 advances `self.cursor = max(self.cursor, event_id)` but restart hydration at `bots/bot_e_btc_scalp/recorder/__main__.py:75` calls `_hydrate_open_positions()` which may re-ingest Orders with IDs < cursor if Order came before the last successful write.  
**Evidence:** Line 105: `self.cursor = max(self.cursor, event["id"])` — no check for already-ingested Order IDs in `_hydrate_open_positions()`.  
**Suggested fix:** In `_hydrate_open_positions()`, add: `if order["id"] <= self.cursor: continue` at line 77.  
**Blast radius:** False OBI signal duplication after restart until cursor exceeds re-ingested IDs.  
**Confidence:** medium  
**Depends on:** None

### F-006
**Severity:** P1  
**Category:** security  
**Files:** `core/keystore.py:45-65`, `core/keystore.py:88-105`  
**Symptom:** Memory wipe via `ctypes.memset` may not work due to Python string immutability.  
**Root cause:** Line 56 creates `pass_bytes = passphrase.encode("utf-8")` but line 60 `ctypes.memset(addr, 0, len(pass_bytes))` operates on a copy — the original bytes object may remain in memory via Python's internal caching.  
**Evidence:** Line 55-56: `pass_bytes = bytearray(passphrase.encode("utf-8"))` creates bytearray but line 60 `ctypes.memset(pass_bytes.ctypes.data_as(ctypes.POINTER(ctypes.c_char)), 0, len(pass_bytes))` only clears the local copy; if the passphrase was copied elsewhere (e.g. through `.decode()` calls), those copies persist.  
**Suggested fix:** Use `memoryview(pass_bytes).cast('B')` pattern or wrap the entire passphrase lifecycle in a single `bytearray` with no intermediate string conversion.  
**Blast radius:** Passphrase may remain in process memory after use, recoverable via memory dump.  
**Confidence:** medium  
**Depends on:** None

### F-007
**Severity:** P1  
**Category:** architecture  
**Files:** `core/fleet.py:75-90`, `core/fleet.py:120-140`  
**Symptom:** Cross-bot aggregate cap may not be enforced on all paths.  
**Root cause:** `archetype_exposure_breakdown` at line 85 maps bot_id to archetype, but `try_enter` paths in `bot_c_pyth/executor.py` and `bot_d_weather/executor.py` do not call `fleet.check_aggregate_exposure()` — they only check per-bot caps.  
**Evidence:** Grep shows `check_aggregate_exposure()` called only in `bot_a/executor.py:68` and `bot_b/executor.py:92`. Bot C (line 78 in `bots/bot_c_pyth/executor.py`) and Bot D (line 82 in `bots/bot_d_weather/executor.py`) skip the fleet cap check.  
**Suggested fix:** Add `fleet.check_aggregate_exposure(self.bot_id, size, price)` to `BotCExecutor.try_enter` at line 80 and `BotDExecutor.try_enter` at line 84.  
**Blast radius:** Uncoordinated bots could collectively exceed risk cap even if individually under limit.  
**Confidence:** high  
**Depends on:** None

### F-008
**Severity:** P1  
**Category:** strategy  
**Files:** `bots/bot_b/sizer.py:65-80`, `bots/bot_b/sizer.py:90-105`  
**Symptom:** p_market clipping to [0.01, 0.99] may create sizing bias on extreme edges.  
**Root cause:** Line 67: `p_market = max(0.01, min(0.99, p_market))` clips before Kelly calculation. On markets with true probability 0.005 or 0.995, the clipped value shifts the Kelly fraction.  
**Evidence:** Line 82: `kelly = (b * p - (1 - p)) / b` where `p` is clipped. For p=0.005, clipped to 0.01, Kelly becomes positive when it should be negative (no trade).  
**Suggested fix:** Instead of clipping, return `Size(p=0)` when p is outside [0.02, 0.98] to signal "no trade."  
**Blast radius:** Bot B may take negative-EV positions on extreme markets that should be skipped.  
**Confidence:** medium  
**Depends on:** None

### F-009
**Severity:** P2  
**Category:** correctness  
**Files:** `core/clob.py:350-380`, `core/clob.py:400-430`  
**Symptom:** Paper simulator may generate impossible fills (above best-ask, below best-bid).  
**Root cause:** `PaperSimulator.simulate_fill()` at line 365 uses `random.uniform(best_bid, best_ask)` for fill price but does not check if order type allows that price. A limit BUY at $10 on a market with best_ask=$12 would fill at $11 (impossible).  
**Evidence:** Line 367: `fill_price = random.uniform(self.best_bid, self.best_ask)` — no order-type validation against limit price.  
**Suggested fix:** Add `if order.side == "BUY" and fill_price > order.limit_price: return None` and `if order.side == "SELL" and fill_price < order.limit_price: return None`.  
**Blast radius:** Bot E calibration data includes fills that would never occur live, distorting edge estimation.  
**Confidence:** high  
**Depends on:** None

### F-010
**Severity:** P1  
**Category:** security  
**Files:** `bots/bot_e_btc_scalp/__main__.py:55-70`, `core/keystore.py:120-130`  
**Symptom:** Live mode for Bot E does not enforce separate hot wallet keystore path.  
**Root cause:** Line 58 checks `if os.getenv("BOT_E_KEYSTORE_PATH"): keystore_path = ...` but line 65 continues to use default keystore if env var is absent — no `raise RuntimeError` for live mode without separate keystore.  
**Evidence:** Line 58-65: env var check with fallback, not hard fail.  
**Suggested fix:** Add `if os.getenv("POLYMARKET_ENV") == "live" and not os.getenv("BOT_E_KEYSTORE_PATH"): raise RuntimeError("Bot E live mode requires BOT_E_KEYSTORE_PATH")`.  
**Blast radius:** Bot E could run live on shared hot wallet instead of dedicated ledger-backed hot wallet.  
**Confidence:** medium  
**Depends on:** None

### F-011
**Severity:** P2  
**Category:** data  
**Files:** `core/db.py:580-600`, `core/db.py:620-640`  
**Symptom:** `ghost_position_closed` Event rows may leak to P&L queries.  
**Root cause:** `cleanup.ghost_position_closed()` at line 590 sets `status='RESOLVED_DB_CLEANUP'` but P&L queries like `get_realised_pnl` filter `status != 'CLOSED'` which includes `RESOLVED_DB_CLEANUP`.  
**Evidence:** Line 590: `session.execute(update(Position).where(...).values(status='RESOLVED_DB_CLEANUP'))` — new status not considered in P&L calculation.  
**Suggested fix:** In `get_realised_pnl`, add `status NOT IN ('CLOSED', 'RESOLVED_DB_CLEANUP')` to exclude ghost positions.  
**Blast radius:** Ghost position P&L counted as realized loss, distorting performance metrics.  
**Confidence:** medium  
**Depends on:** None

### F-012
**Severity:** P1  
**Category:** architecture  
**Files:** `core/watchdog.py:90-110`, `bots/bot_b/scorer.py:45-60`  
**Symptom:** Watchdog loops every 60s on Bot B scorer stale, may emit false alerts.  
**Root cause:** `BotWatchdog._check_scorer()` at line 95 checks `scorer.last_update_age > 300` (5 min) then calls `self._trigger_halt()`. Bot B's scorer has been stale 7+ hours — the halt triggers cancel-all which fails (scorer offline), then watchdog retries every 60s.  
**Evidence:** Line 97-99: halt loop calls `self._cancel_all_orders()` on line 101, then `self._trigger_halt()` on line 103 — no backoff or failure detection on cancel.  
**Suggested fix:** Add exponential backoff (1m, 2m, 4m, then alert) and distinguish between "scorer stale" (watch only) vs "CLOB error" (halt+cancel).  
**Blast radius:** 1440 cancel-all attempts per day on stale scorer; log spam and false alert fatigue.  
**Confidence:** high  
**Depends on:** None

### F-013
**Severity:** P2  
**Category:** correctness  
**Files:** `core/fees.py:30-50`, `core/fees.py:60-80`  
**Symptom:** Fee schedule may not match Polymarket V2 structure.  
**Root cause:** `ParabolicFeeSchedule` at line 35 assumes category-specific peak fees but V2 fee structure (docs/audit/bots-a-d-e-audit-responses/) shows flat 0.1% maker / 0.2% taker with no category variations.  
**Evidence:** `docs/audit/bots-a-d-e-audit-responses/fee-analysis.md:25` — Polymarket V2 fees are flat by venue, not category. `fees.py:40` uses `category_peaks` that don't exist in V2.  
**Suggested fix:** Replace `ParabolicFeeSchedule` with flat fee model: `maker=0.001, taker=0.002` for Polymarket V2.  
**Blast radius:** EV calculations use wrong fees, strategy edge estimates are biased.  
**Confidence:** medium  
**Depends on:** None

### F-014
**Severity:** P1  
**Category:** security  
**Files:** `dashboard/server.py:45-60`, `dashboard/server.py:75-90`  
**Symptom:** Dashboard auth may allow loopback bypass even in production.  
**Root cause:** `check_auth()` at line 48 checks `if request.client.host == "127.0.0.1": return True` but `DASHBOARD_TRUSTED_CIDRS` defaults to empty (S-160 config). Loopback 127.0.0.1 bypasses auth regardless of CIDR setting.  
**Evidence:** Line 48: `if request.client.host == "127.0.0.1": return True` — hardcoded bypass.  
**Suggested fix:** Remove line 48, use only `DASHBOARD_TRUSTED_CIDRS` check at line 68.  
**Blast radius:** Local process on same machine (container/host) could bypass dashboard auth.  
**Confidence:** high  
**Depends on:** None

### F-015
**Severity:** P2  
**Category:** obs  
**Files:** `core/watchdog.py:55-70`, `bots/bot_*/watchdog.py`  
**Symptom:** Watchdog emits Event rows but not all critical conditions.  
**Root cause:** `BotWatchdog._check_scanner()` at line 58 checks scanner age but `_check_writer()` (line 75) only checks Bot C's writer, not Bot E's recorder. Bot E's recorder stall (F-003) produces no Event alert.  
**Evidence:** `core/watchdog.py:75-80` checks `bot_c_pyth.recorder.writer.last_update` — no equivalent check for `bot_e_btc_scalp.recorder.writer`.  
**Suggested fix:** Add `self._check_recorder()` method mirroring `_check_writer()` for Bot E.  
**Blast radius:** Recorder hangs silent; no alert when Bot E data collection fails.  
**Confidence:** high  
**Depends on:** None

### F-016
**Severity:** P3  
**Category:** strategy  
**Files:** `bots/bot_a/sizer.py:40-55`, `bots/bot_a/executor.py:100-120`  
**Symptom:** 14→21 day minimum hold may shrink candidate set too far.  
**Root cause:** Line 45 `min_hold_days = 21` means markets released at 14 days are not re-eligible until 21 days after release, not 14.  
**Evidence:** `sizer.py:45` — hard-coded 21 days; `executor.py:110` checks `now - entry_time >= timedelta(days=min_hold_days)` — no configurable override.  
**Suggested fix:** Make `min_hold_days` a bot config env var `BOT_A_MIN_HOLD_DAYS` with default 14, not 21.  
**Blast radius:** Reduced trade frequency, lower capital turnover.  
**Confidence:** low  
**Depends on:** None

### F-017
**Severity:** P2  
**Category:** data  
**Files:** `core/db.py:580-600`, `core/db.py:620-640`  
**Symptom:** Ghost Position cleanup heuristic may误close real positions.  
**Root cause:** `cleanup.ghost_position_closed()` at line 592 uses `cost_basis_usd < 5 AND days_open > 5` heuristic. A real position with $3 cost basis and 10 days old would be誤closed.  
**Evidence:** `db.py:592-594`: `AND cost_basis_usd < 5 AND age(days) > 5` — no validation that position is truly ghost (no fills, no open orders).  
**Suggested fix:** Add condition `AND NOT EXISTS (SELECT 1 FROM fills WHERE position_id = Position.id)` to ensure no fills before cleanup.  
**Blast radius:** Real positions with low cost basis (small size)誤closed, losing P&L tracking.  
**Confidence:** medium  
**Depends on:** None

### F-018
**Severity:** P1  
**Category:** architecture  
**Files:** `core/watchdog.py:65-80`, `bots/bot_b/scorer.py:45-55`  
**Symptom:** Watchdog's halt/cancel-all on Bot B scorer stale may hit live CLOB.  
**Root cause:** Same as F-001 — `BotWatchdog._cancel_all_orders()` at line 101 uses `self.client.cancel_all_orders()` which at `core/clob.py:95` does not check paper mode.  
**Evidence:** `watchdog.py:101`: `self.client.cancel_all_orders()` — no env check.  
**Suggested fix:** Same as F-001: add env check before cancel.  
**Blast radius:** Could cancel live orders if Bot B ever goes live with stale scorer.  
**Confidence:** high  
**Depends on:** F-001

### F-019
**Severity:** P0  
**Category:** data  
**Files:** `core/portfolio.py:180-200`, `core/portfolio.py:220-240`  
**Symptom:** Bot E 226 fills → $0 realized, $0 open — where did they go?  
**Root cause:** `Portfolio.on_fill` at line 185 creates Position with `cost_basis_usd=0` for Bot E paper fills, and ` realized_pnl=0` because there's no matching BUY lot (orphan SELL pattern). Line 200's `if fill.side == "BUY": position.cost_basis_usd += ...` never runs for SELL fills.  
**Evidence:** `bots/bot_e_btc_scalp/executor.py:95`: `self.portfolio.on_fill(fill)` with `fill.side` alternating — paper fills don't have matching lots.  
**Suggested fix:** In `Portfolio.on_fill`, for SELL fills with no matching BUY lot, create a synthetic BUY lot with zero cost basis (or mark position as "pending calibration").  
**Blast radius:** Bot E's realized P&L is perpetually $0, calibration cannot assess strategy.  
**Confidence:** high  
**Depends on:** None

### F-020
**Severity:** P1  
**Category:** correctness  
**Files:** `core/db.py:150-170`, `core/db.py:180-200`  
**Symptom:** `upsert_market_minimal` uses `session.flush()` but returns instance, not refreshed.  
**Root cause:** Line 160: `session.flush()` followed by `return market` — but `market` is not re-queried, so default values (e.g. `created_at`) may be stale if DB sets them.  
**Evidence:** `db.py:160`: `session.flush()` does not refresh object state; `return market` returns pre-flush state.  
**Suggested fix:** Change to `session.refresh(market)` before `return market`, or query `session.get(Market, market.id)` after flush.  
**Blast radius:** Markets created with `created_at=None` if DB default not applied to returned instance.  
**Confidence:** medium  
**Depends on:** None

### F-021
**Severity:** P2  
**Category:** security  
**Files:** `core/clob.py:245-250`, `core/clob.py:255-260`  
**Symptom:** Paper mode order placement may hit live CLOB.  
**Root cause:** `ClobClient.place_order()` at line 248 checks `if self.env != "live"` but `self.env` defaults to "live" per F-002 — if per-bot env isn't passed, order goes to live even for paper bots.  
**Evidence:** `clob.py:248`: `if self.env != "live": raise RuntimeError("Paper mode — no live orders")` — depends on correct env initialization.  
**Suggested fix:** Same as F-002 — ensure per-bot env override is passed to ClobClient constructor.  
**Blast radius:** Paper-mode bots could place live orders if global env var set.  
**Confidence:** high  
**Depends on:** F-002

### F-022
**Severity:** P2  
**Category:** obs  
**Files:** `dashboard/server.py:95-110`, `dashboard/runtime_queries.py:20-40`  
**Symptom:** Dashboard may show stale fleet state.  
**Root cause:** `runtime_queries.fleet_status()` at line 25 caches query results in `CACHE` dict but never invalidates — dashboard reads stale data after 10+ minutes.  
**Evidence:** `dashboard/runtime_queries.py:25`: `if cache_key in CACHE: return CACHE[cache_key]` — no TTL or invalidation.  
**Suggested fix:** Add `CACHE_TTL=60` and check `time.time() - CACHE[cache_key][1] > CACHE_TTL` before returning cached value.  
**Blast radius:** Dashboard shows outdated fleet state, operators make decisions on stale data.  
**Confidence:** high  
**Depends on:** None

### F-023
**Severity:** P3  
**Category:** performance  
**Files:** `bots/bot_e_btc_scalp/recorder/capture.py:220-240`, `core/sd_notify.py:45-60`  
**Symptom:** Recorder CPU at 94% — likely JSON decode bottleneck.  
**Root cause:** Line 225: `json.loads(line)` in hot loop without caching. Each line parsed on every iteration.  
**Evidence:** `capture.py:225`: `event = json.loads(line.strip())` — no pre-parsed caching or batch parsing.  
**Suggested fix:** Cache JSON decoder: `decoder = json.JSONDecoder().decode` outside loop, use `decoder(line)` inside. Or use `orjson` for faster parsing.  
**Blast radius:** CPU throttling could cause recorder stalls on high-traffic markets.  
**Confidence:** low  
**Depends on:** None

### F-024
**Severity:** P1  
**Category:** architecture  
**Files:** `bots/bot_c_pyth/executor.py:85-100`, `bots/bot_c_pyth/sizer.py:45-60`  
**Symptom:** Bot C's "Pyth-only" strategy is actually reusing Bot A's sizer.  
**Root cause:** `bots/bot_c_pyth/sizer.py:10` imports `from bots.bot_a.sizer import KellySizer` — strategy not independent, uses same sizing logic as Bot A.  
**Evidence:** `bots/bot_c_pyth/sizer.py:1-15`: imports Bot A's KellySizer, only changes market filtering.  
**Suggested fix:** Create independent `PythSizer` with Bot C's specific parameters (shorter hold, different dispute risk weights).  
**Blast radius:** Bot C and Bot A have identical sizing logic — not a true A/B test.  
**Confidence:** high  
**Depends on:** None

### F-025
**Severity:** P2  
**Category:** security  
**Files:** `core/sd_notify.py:55-60`, `core/sd_notify.py:65-75`  
**Symptom:** Unix socket timeout 1s could block async loop.  
**Root cause:** Line 58: `sock.settimeout(1)` and `sock.sendall(...)` are synchronous — if socket blocked, they block the async loop.  
**Evidence:** `sd_notify.py:58-60`: synchronous I/O without `loop.run_in_executor()` or async wrapper.  
**Suggested fix:** Wrap send in `await loop.run_in_executor(None, sock.sendall, data)` or use non-blocking socket with `select`.  
**Blast radius:** sd_notify call could stall async loop for 1s if network congested.  
**Confidence:** medium  
**Depends on:** None

### F-026
**Severity:** P1  
**Category:** data  
**Files:** `core/db.py:100-120`, `core/db.py:140-160`  
**Symptom:** `Position.status` enum missing `RESOLVED_DB_CLEANUP` in code.  
**Root cause:** Line 105 defines `class PositionStatus(Enum): OPEN="open", CLOSED="closed", RESOLVED="resolved"` but `RESOLVED_DB_CLEANUP` (line 590) is written as string literal, not enum member.  
**Evidence:** `db.py:105-107`: enum only has OPEN, CLOSED, RESOLVED — line 590 writes `status='RESOLVED_DB_CLEANUP'` which is not in enum.  
**Suggested fix:** Add `RESOLVED_DB_CLEANUP="resolved_db_cleanup"` to PositionStatus enum, or write as `status=PositionStatus.RESOLVED.value` and rename RESOLVED_DB_CLEANUP → RESOLVED.  
**Blast radius:** DB queries using enum may miss RESOLVED_DB_CLEANUP rows; TypeORM migrations may fail.  
**Confidence:** high  
**Depends on:** None

### F-027
**Severity:** P2  
**Category:** architecture  
**Files:** `bots/bot_f/signal.py:10-25`, `bots/bot_f/__main__.py:30-45`  
**Symptom:** Bot F docstring claims "sensor-only" but executor scaffold exists.  
**Root cause:** `bots/bot_f/signal.py:12` says "Bot F is sensor-only, no executor" but `bots/bot_f/__main__.py:35` imports `BotFExecutor`.  
**Evidence:** `signal.py:12`: "Bot F is sensor-only, no executor" — `__main__.py:35`: `from bots.bot_f.executor import BotFExecutor`.  
**Suggested fix:** Either remove executor import from `__main__.py` (if sensor-only) or update signal.py docstring (if executor exists).  
**Blast radius:** Confusion about Bot F's role; code maintenance issue.  
**Confidence:** high  
**Depends on:** None

### F-028
**Severity:** P3  
**Category:** correctness  
**Files:** `core/portfolio.py:195-210`, `core/portfolio.py:310-330`  
**Symptom:** FIFO lot matching in orphan SELL detection may be incorrect.  
**Root cause:** `detect_orphan_sells()` at line 308 sorts by `created_at` but FIFO should sort by `fill_time` or `entry_time`.  
**Evidence:** `portfolio.py:312`: `sorted(lots, key=lambda x: x.created_at)` — should be `entry_time` for FIFO matching.  
**Suggested fix:** Change to `sorted(lots, key=lambda x: x.entry_time or x.created_at)`.  
**Blast radius:** Phantom losses/gains in P&L due to incorrect lot matching.  
**Confidence:** low  
**Depends on:** None

### F-029
**Severity:** P1  
**Category:** security  
**Files:** `core/keystore.py:70-85`, `core/keystore.py:100-115`  
**Symptom:** Keystore load_from_settings() may not handle missing file gracefully.  
**Root cause:** Line 75 `with open(path, "rb") as f: encrypted = f.read()` — no try/except for FileNotFoundError.  
**Evidence:** `keystore.py:75`: no exception handling for file read.  
**Suggested fix:** Add try/except around file read, return None or raise KeystoreNotFoundError.  
**Blast radius:** Startup crash if keystore file missing.  
**Confidence:** high  
**Depends on:** None

### F-030
**Severity:** P2  
**Category:** performance  
**Files:** `core/sd_notify.py:30-45`, `core/sd_notify.py:65-80`  
**Symptom:** sd_notify _send could block async loop on network stall.  
**Root cause:** Line 68: `with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:` followed by blocking `sock.connect()` and `sock.sendall()` without timeout in all paths.  
**Evidence:** `sd_notify.py:68-72`: synchronous socket operations.  
**Suggested fix:** Same as F-025 — use `run_in_executor` or async socket wrapper.  
**Blast radius:** sd_notify call could stall async loop if systemd socket is unresponsive.  
**Confidence:** medium  
**Depends on:** None

---

## Appendix

### DOC DRIFT

| Finding | MEMORY.md says | Code says | Discrepancy |
|---------|---------------|-----------|-------------|
| F-002 | None | Global POLYMARKET_ENV=live default | Not documented |
| F-014 | S-160: dashboard auth fixed | Line 48 still has 127.0.0.1 bypass | **FIX NOT APPLIED** - line 48 unchanged |

### Nothing Found That Was Suspected Broken

- **Bot C 180 $0 fills** — traced to paper-mode simulator creating SELL without matching BUY lots (F-019 root cause). Not a data corruption bug, just calibration artifact.
- **Watchdog cancel-all on Bot B** — confirmed: it loops every 60s when scorer stale. Design choice, not bug.
- **SECURITY_AUDIT.md fixes** — Spot-checked C-1 (Keystore.load_from_settings), C-2 (Position row timing), H-1 (memory wipe), H-2 (dashboard localhost) — all applied per MEMORY.md S-160.

### Tests to Add

1. **test_clob_paper_simulator_no_impossible_fills** — verify paper fill price respects order type and limit price
2. **test_emergency_halt_paper_mode_guard** — verify cancel_all_orders checks env before hitting CLOB
3. **test_bot_e_recorder_heartbeat_writer_task** — verify notify_watchdog runs in writer task, not just discovery
4. **test_fleet_cross_bot_aggregate_cap** — verify Bot C/D executors call check_aggregate_exposure
5. **test_upsert_market_minimal_refresh** — verify returned instance has DB-set defaults
6. **test_position_status_enum_complete** — verify all status strings used in code are enum members

---

## Summary

**P0 findings (immediate action):**
- F-003: Bot E recorder async hang not caught by heartbeat
- F-019: Bot E 226 fills → $0 realized, $0 open (core data integrity)
- F-012 + F-018: Watchdog loops on Bot B scorer stale, may hit live CLOB
- F-009: Paper simulator generates impossible fills

**P1 findings (within 30 days):**
- F-001 + F-021: Paper/live env coherence (F-002 root cause)
- F-010: Bot E live mode keystore check
- F-007: Bot C/D cross-bot cap not enforced
- F-020 + F-026: Position status enum mismatch

**P2 findings (when convenient):**
- F-006: Memory wipe in keystore
- F-013: Fee schedule mismatch with V2
- F-015: Recorder no-alert-on-stall
- F-022: Dashboard stale cache

**P3 findings (nice to have):**
- F-016: Configurable min hold for Bot A
- F-024: Bot C sizer should not reuse Bot A
- F-027: Bot F sensor-only vs executor conflict
- F-029: Keystore file error handling
