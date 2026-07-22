# Bot A (Longshot) — Longshot Fade

**Status:** Specified, not built
**Last updated:** 2026-04-14
**Role:** Mechanical baseline bot. No LLM. No oraclemangle dependency. Exists to isolate whether model-driven edge (Bot B) adds value over rule-driven edge.

This spec is self-contained. If `docs/architecture-decision.md` disappeared, this file alone should be enough to start building.

---

## Thesis

Polymarket's binary UMA-resolved markets systematically over-price tail outcomes in the sub-$0.05 region. Two forces create this:
1. **Retail "lottery ticket" buyers** who pay above fair value for upside optionality
2. **Thin liquidity at the far tail** — MM YES inventory sits wider than fair because filling 100+ shares of 2¢ optionality is a small-ticket trade for them

A disciplined fader who buys NO at $0.95+, waits out resolution, and stays in fee-favourable categories captures the over-round.

**Edge persists because** the hold is 30–180 days. Bot-builders chasing short-horizon flash-strategies won't tolerate this timescale — the competitor pool self-selects out.

---

## Mechanics

### Market selection filters

All must hold:

| Filter | Value | Rationale |
|---|---|---|
| Category | ∈ {geopolitics, politics, finance, economics} | Zero to 5-bp fee drag; UMA-resolved |
| Structure | binary YES/NO | Single contract type; avoids neg-risk complexity |
| `yes_price` | ≤ 0.05 | Only fade the far tail |
| `volume_24h` | ≥ $5,000 | Ensures exit optionality if thesis breaks |
| `days_to_resolution` | ∈ [30, 180] | Short enough to compound; long enough to avoid event variance |
| `book_depth_at_no_ask` | ≥ $500 within 2¢ of mid | Can fill at the touch without slippage |
| `question` text | not on manual blacklist | Sanctions, assassination, violence markets excluded |

Expected candidate universe: **40–120 active markets** at any time (estimate — verify on fresh data).

### Signal generation

**None.** The rule IS the signal. Pseudocode:

```python
if (market matches all filters)
   and (no existing position in market)
   and (available_capital >= position_size):
    place_no_limit_order(
        token_id=market.no_token_id,
        price=1 - market.best_yes_ask,
        size=position_size,
        order_type=GTC,
    )
```

Deliberately mechanical. Reviewable by a human. Reproducible across dates.

### Execution

- **Order type:** GTC limit at `(1 − best_yes_ask)`. No market orders at entry.
- **Sizing:** `position_size = min($30, 1% of bot_bankroll, 2% of book_depth)`. Starts at $30 fixed.
- **Entry:** one order per qualifying market. No pyramiding.
- **Exit (normal):** hold to resolution → redeem NO shares for USDC.e.
- **Exit (abnormal):** if `yes_price` rises above $0.25, cut at market. Rationale: the thesis was regime-conditional; a 5× move invalidates the regime.
- **Exit (dispute):** if market enters UMA dispute, hold. Do not panic-sell into thinned liquidity.
- **Exit (kill-switch):** cancel all open orders; close open positions at best available market price; alert.

### Risk controls

| Control | Value | Trigger |
|---|---|---|
| Per-market notional cap | $30 | Hard cap |
| Aggregate open exposure cap | $1,000 | Hard cap |
| Drawdown kill | −£150 (−15% of £1k bot bankroll) | Cancel all orders, halt new entries, alert |
| Staleness halt | market data >5 min stale | Halt new entries |
| Dispute-streak halt | 3 consecutive closes via dispute | Halt, human review |

### Capital allocation

| Phase | Capital |
|---|---|
| Paper (30 days) | £1,000 simulated |
| Live graduation | £250 |
| Scale-up 1 (at +30 live days positive, <10% drawdown) | £500 |
| Scale-up 2 (at +60 live days positive, <12% drawdown) | £1,000 |
| Scaling ceiling | £1,000 (no further without re-decision) |

---

## Expected performance (estimates, not promises)

- **Edge per trade:** 4–8% of notional expected value (estimated; verify in paper)
- **Trade frequency:** 15–40 entries/week
- **Mean hold:** ~90 days (range 30–180)
- **Hit rate:** 88–96% (mechanical consequence of buying at 95¢ when fair is 96–98¢)
- **Sharpe-equivalent:** 1.2–1.8 annualised (high uncertainty, skewed distribution — prefer Calmar)
- **Calmar target:** > 0.8 paper, > 1.2 live
- **Max drawdown (theoretical):** 5–15% over any 90-day window, dominated by correlated YES-resolution events

---

## Failure modes

| Mode | What it looks like | Response |
|---|---|---|
| Base-rate regime shift | Hit rate stays high but edge per trade compresses over weeks | Monitor; kill if avg edge <2% for 2 consecutive weeks |
| Correlated tail event | Basket of longshots resolves YES on the same day | Drawdown kill-switch fires |
| Liquidity drought at exit | Cut-loss order sits at touch for hours | Re-price inward; accept worse exit |
| Oracle dispute on a "won" position | DVM P4 vote refunds position, lose opportunity cost | Log in `disputes` count; if >5/year, re-evaluate |
| **Death pattern** | Hit rate <80% for 2 weeks, OR avg edge <2% | Kill |

---

## Tech stack

- **Language:** Python 3.11
- **Key libraries:** `py-clob-client` (CLOB), `httpx` (Gamma API), `sqlalchemy` + SQLite (state), `tenacity` (retry), `cryptography` (keystore via shared `core/keystore.py`), `python-telegram-bot`
- **Data sources:** Polymarket Gamma API (market metadata), CLOB REST (books, orders), CLOB WSS user channel (fills)
- **Storage:** SQLite at `./data/bot_a.db`; encrypted daily snapshot to Backblaze B2
- **Monitoring:** Telegram bot for alerts; Uptime Kuma on the homelab hypervisor for liveness; systemd journal for structured logs

### Module layout

```
bots/bot_a/
├── __init__.py
├── filters.py          # Market selection predicates
├── executor.py         # Order placement + cancellation
├── lifecycle.py        # Entry, hold, exit state machine per position
├── config.py           # Thresholds, categories, caps (single source of truth)
└── tests/
    ├── test_filters.py
    ├── test_executor.py
    └── test_lifecycle.py
```

All shared infra lives in `core/` — see `specs/shared-infra.md`.

---

## MVP scope

### Week 2 (single rotation-home week after shared infra ships)
- Day 1: `filters.py` + unit tests against real Gamma data
- Day 2: `executor.py` integrated with `core/clob.py`, place + cancel working in Amoy testnet
- Day 3: `lifecycle.py` paper-trading mode — simulated fills at touch, logged to `bot_a_trades`
- Day 4: exit + redemption logic (paper)
- Day 5: end-to-end paper trade cycle; 30-day paper clock starts

**End-of-week gate:** Bot A paper-trading, logging fills, alerting on entries.

---

## What Bot A does NOT do (explicit non-goals)

- Does not score markets with an LLM
- Does not read oraclemangle tables
- Does not attempt outcome prediction — only over-round harvest
- Does not cross the spread on entry
- Does not scale into a position (one entry per market, period)
- Does not trade crypto, sports, culture, mentions, tech, or "other" categories
- Does not trade multi-outcome / neg-risk markets
- Does not copy other wallets' trades
- Does not use sentiment / news / social signals

---

## Open items specific to Bot A

- **Blacklist markets**: initial list is empty. Curate during Week 2 as filters surface questionable markets (assassination, explicit violence, etc.). Update `bots/bot_a/config.py:BLACKLIST`.
- **Position sizing re-tune**: $30 is conservative. Consider raising to $50 if aggregate cap isn't being hit by week 30.

---

## References

- `docs/architecture-decision.md` §2 — original decision context
- `docs/decisions-log.md` ADR-002 — why this thesis
- `specs/shared-infra.md` — dependencies
- `specs/test-protocol.md` — how Bot A is judged
- (internal edge-distribution review, not exported) — baseline data (166 tradeable candidates in fresh sample)
- `research/grok-methods-dump.md` §"Long-Tail Sniping" — Grok's prior-art note ($300→$117k over 31k predictions)
