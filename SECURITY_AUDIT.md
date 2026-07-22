# Security and Correctness Audit Report

**Remediation status (2026-04-17 post-mortem):**

All Critical + High + Medium + Low findings below were remediated and deployed in commit `875787e` on 2026-04-16. Regression tests live in `tests/test_audit_fixes.py` and `tests/test_audit_fixes_2.py`. This file is retained as a historical audit trail; it does NOT reflect live code state.

If you are an agent reading this: **do not re-apply any fix listed here without first grepping for the referenced symbol or file location and confirming the current state.** The remediation notes at each finding are informational markers; they mean "this was the finding", not "this still exists in code."

Spot-check performed 2026-04-17:
- C-2 (Bot C position double-counting): verified absent — `grep -n "Position(" bots/bot_c_pyth/executor.py` returns no construction calls. Tripwire comment at the insertion point retains the fix rationale for future review.
- L-2 (pending_unhalt memory leak): closed Session 17 per CHANGELOG.
- S-2 (Bot B Kelly singularity at p_market=1): closed — `bots/bot_b/sizer.py:size_position` clips p_market to [0.01, 0.99] before Kelly.

---


## Critical

### Missing `load_from_settings` causing startup crash in Live mode
- File: `bots/bot_c_pyth/__main__.py:97`, `bots/bot_d_weather/__main__.py:127`
- Category: correctness
- Symptom: Bot C and Bot D crash on startup with `AttributeError` when `enable_executor` is set and mode is `live`.
- Root cause: The bots call `Keystore.load_from_settings(settings)`, but this method is not defined in `core/keystore.py`.
- Trigger: Starting Bot C or Bot D in live mode with executor enabled.
- Fix: Implement `load_from_settings` in `Keystore` class or use `Keystore.load(settings.polymarket_keystore_path, settings.polymarket_passphrase_path)`.

### Bot C position double-counting
- File: `bots/bot_c_pyth/executor.py:168-185`
- Category: data
- Symptom: Bot C open positions are recorded with double the actual size, leading to incorrect PnL and exposure cap violations.
- Root cause: `BotCExecutor.try_enter` manually adds a `Position` row to the database. However, `Portfolio.on_fill` (called during reconciliation) also creates or updates `Position` rows for the same `token_id`. `Portfolio` finds the existing row and adds the fill size to it, doubling the state.
- Trigger: Any successful fill for a Bot C order.
- Fix: Remove the `s.add(Position(...))` block in `BotCExecutor.try_enter`. Use `Order` rows only; the `Position` will be created by the reconciliation layer.

## High

### Backtest ignores NO-token trades
- File: `core/backtest.py:97-101`
- Category: test
- Symptom: Backtests for strategies trading NO tokens (like Bot A) show zero fills and zero PnL despite profitable opportunities.
- Root cause: The `Backtest.run` method builds a `markets` map using only `yes_token_id` as the key. When replaying a `Book` snapshot for a `no_token_id`, the lookup `markets.get(book.token_id)` returns `None`, causing the snapshot to be skipped.
- Trigger: Running a backtest on a bot that places orders for NO tokens.
- Fix: Map both `yes_token_id` and `no_token_id` to the `Market` object in the `markets` dictionary.

### Bot C Analyst hardcoded to Pro endpoint
- File: `bots/bot_c_pyth/strategy.py:91-95`
- Category: correctness
- Symptom: Bot C analyst returns no spot/vol data and fails to trade if the operator switches to the Hermes (free) endpoint.
- Root cause: `get_spot_and_vol` is hardcoded to query the `PythBarPro` table. It does not check the configuration to see if it should query `PythBarHermes` instead.
- Trigger: Running Bot C with `--endpoint hermes`.
- Fix: Pass the configured bar model or endpoint name to `get_spot_and_vol` and query the appropriate table.

### O(N) Database queries in performance-critical paths
- File: `core/ingest.py:465-470`, `core/ingest.py:516-521`, `bots/bot_c_pyth/strategy.py:91-96`
- Category: performance
- Symptom: High CPU/DB load and eventual timeouts as the number of active markets or positions grows. Bot C scans become prohibitively slow.
- Root cause: `latest_yes_mid_prices`, `build_mark_prices`, and `get_spot_and_vol` all perform a separate SQL query inside a loop for every token/market. `get_spot_and_vol` is particularly severe as it fetches 18,000 rows *per market*.
- Trigger: Having 500+ active markets or positions.
- Fix: Use a single query with an `IN` clause and `row_number() OVER (PARTITION BY ...)` to fetch latest rows for all tokens at once.

### Private key leak to heap
- File: `core/keystore.py:270`, `core/clob.py:73`
- Category: security
- Symptom: Plaintext private key remains in process memory in multiple locations, making it retrievable via core dumps or heap inspection.
- Root cause: `Keystore.signer()` returns `Account.from_key(self._key.bytes())`, where `self._key.bytes()` creates a new immutable `bytes` copy. `ClobWrapper` then calls `signer.key.hex()`, creating another immutable `str` copy.
- Trigger: Initializing the CLOB client or signing any message.
- Fix: Use `eth_account` functions that accept `memoryview` or `bytearray` if possible, and ensure intermediate `hex()` strings are avoided by passing keys directly to the client constructor if supported.

### Ineffective memory zeroing
- File: `core/keystore.py:246`, `core/keystore.py:261`
- Category: security
- Symptom: Sensitive data (passphrase, private key) is not actually erased from memory despite explicit attempts.
- Root cause: Strings (`str`) and `bytes` in Python are immutable. Reassigning `passphrase = "\x00" * len(passphrase)` only changes the local pointer; the original sensitive string remains in the heap.
- Trigger: Closing the keystore or finishing decryption.
- Fix: Use `bytearray` for all sensitive intermediate buffers and zero them using `ctypes.memset`.

## Medium

### `notify_daemon` cannot cancel orders in Live mode
- File: `bots/notify_daemon.py:48-51`
- Category: correctness
- Symptom: `/unhalt` or manual cancel commands from Telegram fail to actually cancel orders on the CLOB when the bot is in Live mode.
- Root cause: `notify_daemon` initializes `ClobWrapper(keystore=None)`. The `cancel_all` method in `ClobWrapper` requires a keystore to initialize the live client for signing cancellation requests.
- Trigger: Sending a Telegram command that triggers `dispatch_cancel` while `POLYMARKET_ENV=live`.
- Fix: Load the keystore in `notify_daemon.main()` if `is_live()` is true, similar to `watchdog_daemon`.

### Dashboard auth bypass for local network
- File: `dashboard/server.py:74-78`
- Category: security
- Symptom: Anyone on the same LAN as the bot can view PnL, exposure, and wallet addresses without an API key.
- Root cause: `DASHBOARD_TRUSTED_CIDRS` defaults to RFC1918 private space, and `_check_auth` allows any IP in these ranges to bypass the API key check.
- Trigger: Accessing the dashboard from a different device on the same network.
- Fix: Remove RFC1918 from default trusted CIDRs; default to loopback-only or mandatory API key for non-loopback.

### `upsert_market_minimal` returns stale state
- File: `core/db.py:317`
- Category: correctness
- Symptom: Callers of `upsert_market_minimal` receive `None` or an object without an ID when a new market is first created.
- Root cause: The function calls `session.get` before `session.flush()` or `session.commit()`. SQLAlchemy's Identity Map won't find the object if it hasn't been assigned an ID (for autoincrement) or flushed.
- Trigger: Calling `upsert_market_minimal` for a new `condition_id`.
- Fix: Call `session.flush()` before the final `session.get`, or simply return the `new_market` object directly.

### Hardcoded UID 1000 in `config.py`
- File: `core/config.py:73`
- Category: config
- Symptom: Bot fails to find the passphrase file when run as any user other than the primary system user.
- Root cause: `polymarket_passphrase_path` is hardcoded to `/run/user/1000/...`.
- Trigger: Running the bot under a different system user or in certain containerized environments.
- Fix: Use `Path(f"/run/user/{os.getuid()}/polymarket/passphrase")`.

## Low

### `localhost` string match in `_check_auth`
- File: `dashboard/server.py:68`
- Category: correctness
- Symptom: Requests to `localhost` (if they resolve to something other than `127.0.0.1` or `::1` in the `peer` IP) might be incorrectly challenged.
- Root cause: `peer` is an IP address string, but the code checks if it is equal to the string `"localhost"`.
- Trigger: Accessing the dashboard via a hostname that resolves to a non-standard loopback IP.
- Fix: Remove `"localhost"` from the tuple; `ipaddress` check handles the logic.

### Missing cleanup in `_pending_unhalt`
- File: `core/notify.py:108`
- Category: correctness
- Symptom: Small, slow memory leak in `notify_daemon`.
- Root cause: `_pending_unhalt` entries are added but only removed if a confirmation is received. Expired but unconfirmed attempts remain in the dictionary forever.
- Trigger: Repeatedly sending `/unhalt` without the `confirm` follow-up.
- Fix: Periodically prune the `_pending_unhalt` dict for expired timestamps.

## Suspicious but unconfirmed

### Busy-wait in `TokenBucket`
- File: `core/clob.py:126-140`
- Category: concurrency
- Symptom: High CPU usage when rate-limited.
- Reason: `TokenBucket.acquire` uses a `while True` loop with `time.sleep(0.25)` or `wait_seconds`. If `wait_seconds` is very small, it may loop many times. Confirm by profiling under heavy load.

### Bot B Kelly sizing explosion
- File: `bots/bot_b/sizer.py:38`
- Category: correctness
- Symptom: Bot B could place dangerously large orders if `p_market` is extremely close to 1.0.
- Reason: `(p_model - p_market) / (1 - p_market)` has a singularity at `p_market = 1`. While capped by `PER_MARKET_CAP_FRACTION`, the intended Kelly logic is distorted at extremes. Confirm by checking if `p_market` is ever clipped or if `PER_MARKET_CAP_FRACTION` is sufficiently small.
