# V2 Migration Plan — Polymarket Exchange Cutover 2026-04-22

**Date:** 2026-04-17.
**Cutover:** 2026-04-22 ~11:00 UTC, ~1 hour maintenance downtime.
**Effect:** V1 exchange stops matching orders permanently. Open orders wiped during the window. Positions (ERC-1155 CTF shares) persist — same contract in V2.

This plan documents everything committed this session and the work remaining for Option A (liquidate V1 positions + clean paper posture across migration).

## Supersedes / extends

- **Supersedes ADR-017** ("wait until py-clob-client-v2 >= 0.1.0"). V2 is now mandatory, not optional.
- **Extends OQ-016.** The open question is closed with outcome: V2 migration executes pre-cutover.

## Strategic stance

Fleet is paper-only since Session 17f (2026-04-17 AM). Option A selected: sell all V1 positions before the cutover, accept realized loss on book-crossing slippage, hold wallet in USDC.e post-cutover, wrap to pUSD only when a live V2 session is imminent. Rationale:
- Zero ambiguity at the cutover moment (no stranded V1 orders).
- Paper-only posture already in place — no live-trading continuity cost.
- Clean audit trail: V1 activity closes as a chapter; V2 is a separate future decision.

## Shipped this session (Session 17g PM)

### `core/polymarket_v2.py` (NEW)

All V2-relevant Polygon mainnet addresses extracted from [docs.polymarket.com/resources/contracts](https://docs.polymarket.com/resources/contracts):

| Role | Address |
|---|---|
| CTF Exchange V2 | `0xE111180000d2663C0091e4f400237545B87B996B` |
| Neg-Risk CTF Exchange V2 | `0xe2222d279d744050d28e00520010520000310F59` |
| Conditional Tokens (**unchanged V1→V2**) | `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` |
| pUSD proxy | `0xF00D000000000000000000000000000000000014` |
| pUSD implementation | `0xF00D000000000000000000000000000000000015` |
| CollateralOnramp | `0xF00D000000000000000000000000000000000016` |
| CollateralOfframp | `0xF00D000000000000000000000000000000000017` |
| CTF Collateral Adapter | `0xADa100874d00e3331D00F2007a9c336a65009718` |
| Neg-Risk CTF Collateral Adapter | `0xAdA200001000ef00D07553cEE7006808F895c6F1` |
| USDC.e (unchanged) | `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174` |
| CTF Exchange V1 (reference) | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` |
| Neg-Risk CTF Exchange V1 (reference) | `0xC5d563A36AE78145C45a50134d48A1215220f80a` |

EIP-712 order-struct delta (per migration guide):
- **Removed:** `taker`, `expiration`, `nonce`, `feeRateBps`
- **Added:** `timestamp` (ms), `metadata` (bytes32), `builder` (bytes32)
- **Exchange domain version** bumps `"1"` → `"2"`. L1/L2 auth domain stays `"1"`.

Tests: `tests/test_polymarket_v2_constants.py` (25 cases) — hex-format validation, V1/V2 distinctness, proxy/impl distinctness, onramp/offramp distinctness, CTF stability, order-field disjointness, domain-version regression.

### `scripts/wrap_usdce_to_pusd.py` + `unwrap_pusd_to_usdce.py` (NEW)

Raw web3.py scripts modeled on the existing live-tested `scripts/approve_polymarket.py`. Two-transaction flow (approve + wrap/unwrap), dynamic EIP-1559 gas, `--execute --yes` gated. Uses `core.keystore.Keystore.load_from_settings()` for signing — no private key touches disk.

### `scripts/liquidate_positions.py` (NEW)

Generalises the Session 14 `/tmp/_sell_bolsonaro.py` pattern to bulk-close all open Bot A + Bot B positions:
- Builds a plan per position (best_bid − 1¢ slippage, quantize 0.01).
- Dry run by default. `--execute --yes` required for real submission.
- Per-position filters: `--only-cid`, `--skip-cid`.
- Idempotent: skips positions already marked `CLOSED_V2_MIGRATION`.
- Emits `liquidate.v2_migration` Event rows for every plan decision + every fill/stall outcome.
- Poll-for-fill loop with `--fill-timeout-sec` default 120s.

Tests: `tests/test_liquidate_positions.py` (12 cases) covering plan-build, filters, clamps, idempotency, place-fail handling.

## Remaining work (operator on the bot LXC container)

### Before 2026-04-22 ~10:30 UTC

1. **Plan dry run.** Operator runs:
   ```
   POLYMARKET_ENV=live .venv/bin/python scripts/liquidate_positions.py
   ```
   Expected output: table of open Bot A / Bot B positions with best_bid, exit_limit, notional. Review.

2. **Execute liquidation.**
   ```
   POLYMARKET_ENV=live .venv/bin/python scripts/liquidate_positions.py --execute --yes
   ```
   Expect: SELL orders placed at best_bid−1¢, polled for 120s each. Positions transitioning to `status='CLOSED_V2_MIGRATION'`. Audit rows in `events` table.

3. **If any positions stall** (timeout waiting for fill):
   - Cancel the stale SELL with `py-clob-client` cancel (or via Polymarket UI).
   - Re-run with wider slippage: `--slippage-cents 0.02` or `0.03`.
   - Or exclude them with `--skip-cid` and accept holding those through the cutover.

4. **Verify wallet state post-liquidation:**
   - Polygonscan on `0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA`:
     - USDC.e balance reflects proceeds.
     - POL balance still covers ~20 more txs of gas.
     - CTF ERC-1155 balances zero for liquidated markets.

### During the cutover window (2026-04-22 11:00-12:00 UTC)

No action. Watch `status.polymarket.com` and the operator's Telegram.

### After cutover (Apr 22 afternoon — separate session)

5. **V2 code migration PR** (not landed this session; requires `pip install py-clob-client-v2==1.0.0` on Mac + LXC):
   - Update `pyproject.toml`: remove `py-clob-client`, add `py-clob-client-v2==1.0.0`.
   - Update `core/clob.py`: import from `py_clob_client_v2`; V2 exchange addresses from `core.polymarket_v2`; new order-struct fields; new EIP-712 domain version.
   - Update `core/keystore.py`: re-verify L1/L2 derivation (unchanged per migration guide; add a regression test).
   - Update `research/clob-preflight-verified.md`: V1→V2 address delta.
   - Update `STATE.md`: new addresses + pUSD notation.
   - Update `scripts/preflight_check.py`: re-run against V2; write new `preflight.verified` event.
   - Update `scripts/approve_polymarket.py`: approvals now target V2 exchanges + pUSD.

6. **V2 preflight** (operator on LXC):
   ```
   POLYMARKET_ENV=live .venv/bin/python scripts/preflight_check.py --commit --live
   ```
   Expect: all V2 exchange addresses reachable, L1/L2 creds valid, new order-struct fields accepted, preflight event written.

### Only when a live V2 session is imminent

7. **Wrap USDC.e → pUSD:**
   ```
   POLYMARKET_ENV=live .venv/bin/python scripts/wrap_usdce_to_pusd.py --all
   # Review dry-run output, then:
   POLYMARKET_ENV=live .venv/bin/python scripts/wrap_usdce_to_pusd.py --all --execute --yes
   ```

8. **Set V2 approvals** (updated `scripts/approve_polymarket.py`):
   ```
   POLYMARKET_ENV=live .venv/bin/python scripts/approve_polymarket.py --execute --yes
   ```

Do not wrap USDC.e preemptively — it's not required until there's active V2 trading. USDC.e in the wallet is fully liquid and unlocked.

## Risk table

| Risk | Mitigation |
|---|---|
| Wide spreads at liquidation → larger than expected realized loss | `--slippage-cents` tunable; fallback: hold and redeem on resolution |
| A position's book has zero bids | Script skips and reports; operator holds through cutover and redeems on resolution |
| V2 py-clob-client has a breaking API change vs V1 | Addressed in step 5 (separate session); tests before deploy |
| CollateralOnramp reverts on wrap (edge case) | Script dry-runs via eth_call first; no wrap until operator verifies |
| USDC.e depegs during migration | Out-of-scope — same risk applies whether or not wrapped to pUSD |
| Cutover extends beyond ~1 hour | No action required — paper-only fleet has no time-sensitive orders |

## Follow-ups (not blocking migration)

- Post-cutover, confirm Bot E recorder WSS still works (URL should be unchanged per guide; verify the `fee_rate_bps` field still appears on `last_trade_price` events).
- Post-cutover, confirm Bot F Mirror's `data-api.polymarket.com/trades` still works.
- Write an ADR superseding ADR-017 once V2 code migration lands.
- Pyth Pro expiry same day — operator follows the existing free-pyth test posture per `docs/kill-dates.md` C-2.
