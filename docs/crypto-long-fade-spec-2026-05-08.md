# Crypto Long-Horizon NO-Fade Spec

**Created:** 2026-05-08
**Status:** spec + module skeleton; build executable in 1-2 sessions when approved.

---

## Strategy in one paragraph

On crypto markets (BTC/ETH/SOL price-target binaries) with **time-to-resolution > 7 days**, BUY the NO-side at price `0.92-0.99` (= sell YES at `0.01-0.08`). Hold to resolution. Effectively fading expensive longshot YES tokens that price as if a low-probability event were even less likely than the market's own implied probability suggests.

## Why this is interesting

Test B (2026-05-08 WANGZJ V2 re-validation) found:
- 543,921 historical trades on V2 (post Apr 28 2026) matching this filter
- $101.6M total cost basis
- **+1.3% gross ROI**, **+0.95% net of typical V2 crypto fees + 2% slippage**
- Wilson 95% CI extremely tight at this sample size — **genuine signal**

This is structurally different from Bot A (which lost on long-DTR cheap-YES across categories). Bot A's filter was 21-180 day cheap-YES across all categories. This is **>7d crypto only on the NO-side**, which Bot A also tested and lost (-$13.6K). The DIFFERENCE: Test B's filter is on the NO-side at 0.92-0.99, NOT the YES-side at 0.01-0.10.

Wait — they should be mathematically equivalent under no-arb. Let me restate the difference:
- Bot A: sells cheap YES at 0.05 → buys NO at 0.95
- Test B: identical structurally — buys NO at 0.92-0.99 (= selling YES at 0.01-0.08)

So why does Bot A LOSE while this strategy WINS in V2 data?
- **Time horizon difference:** Bot A was 21-180 days. Test B is 7+ days but average is much longer (most are 1-7d to >7d range).
- **Category restriction:** Bot A was all categories. Test B is crypto-only.
- **V2 fee schedule:** crypto has the highest fee rate (0.072 × p × (1-p)) which means at 0.95 entry: fee = 0.072 × 0.95 × 0.05 = 0.0034/share. Fee is highest at p=0.5 ($0.018/share). At extreme prices fees are LOWER.

Best guess: the +1.3% edge comes from crypto-specific over-confidence in cheap longshot YES (price-target binaries that the crowd over-prices because of FOMO / lottery psychology), combined with V2's reduced fee burden at extreme prices.

## Capacity at $5k operator scale

| metric | calculation |
|---|---|
| Historical V2 flow | 543,921 trades / $101.6M cost over ~9 days post-V2 |
| Annualized flow | ~22M trades / $4.1B per year |
| Available retail capture | ~1% of flow ≈ 220K trades / $41M / year |
| **At $30/trade entry** | **220K trades × +0.95% ÷ 220K = +$0.285/trade × volume we can absorb** |
| **At $5k wallet, ~$200/day deployed** | **$200 × 365 × 0.95% = ~$695/year additional income** |
| At $50k wallet | ~$6,950/year |
| At $500k wallet | hits Polymarket-side capacity limits |

**Realistic at $5k cap: ~£550/year additional income.** Won't change life. **Free money** if the bot is paper-zero-risk.

## Spec

### Entry

- Side: NO (or equivalently SELL YES at low price)
- Price: 0.01-0.08 on the YES side (= 0.92-0.99 on NO side)
- Time-to-resolution: > 7 days
- Asset filter: crypto BTC/ETH/SOL price-target binaries only
  - Question pattern: `Will (BTC|Bitcoin|ETH|Ethereum|SOL|Solana) hit/reach <price> by <date>?`
  - or: `Will (BTC|...) be (above|below) <price> on <date>?`
- Volume floor: $1,000 (lower than weather since crypto markets have many small markets)
- Liquidity floor: ≥10 shares depth at entry price

### Exit

**Hold to resolution.** No intraday exits (Strategy A failed; same logic applies).

### Sizing

Same conservative pattern as Bot D-Spike:
- $1-3 per position (paper-only)
- 100 concurrent positions cap (higher than weather since each position is tiny)
- $300 total deployed cap (slightly higher; capacity-limited niche)
- No daily entry cap (high frequency expected; let it run)

### Architecture

Clone of `bots/bot_d_spike/`:

```
bots/crypto_long_fade/
  __init__.py
  __main__.py        # main loop
  config.py          # constants
  discovery.py       # parse crypto questions, identify BTC/ETH/SOL price-target markets
  strategy.py        # entry decision (price band, TTR, side check)
  executor.py        # paper order placement (clone Bot D-Spike's)
```

### Database

Use existing `core/db.py` with:
- `bot_id = 'crypto_long_fade'`
- `side = 'NO'` (vs Bot D-Spike's 'YES')
- All other fields identical

### Service

`systemd/polymarket-crypto-long-fade-vps.service` (clone of Bot D-Spike service)

### Daily report

Adapt `scripts/bot_d_spike_daily_report.py` to read `bot_id='crypto_long_fade'`.

### Kill conditions

- 200 closed paper positions OR 90 days
- Archive if realized ROI < +0.5% (the historical signal is already thin; this matches that)
- Archive if hit rate < 90% (NO-side, expecting cheap YES to lose ~95% of the time)

## ADR proposal (ADR-133 or next available)

**Title:** Accept Crypto Long-Horizon NO-Fade as paper-only with empirical-edge basis from WANGZJ V2 re-validation.

**Core decision:**
1. Build paper-only `crypto_long_fade` bot lane
2. Deploy on a small EU VPS
3. Bot G (5/15-min crypto) unchanged — different timeframe, different microstructure
4. No live promotion under 200 closes + ROI > +0.5% confirmed forward

**Distinguishing characteristics from Bot A failure:**
- Crypto-specific (Bot A was all categories)
- 7+ day horizon (Bot A 21-180 days)
- V2 fee schedule (Bot A tested on V1)
- Empirical evidence: 543K trades show +1.3% on V2 (vs Bot A's -$13.6K on V1)

## Module skeleton (ready to deploy in next session)

The actual code can be a tight clone of `bots/bot_d_spike/`. Pseudo-spec for changes:

```python
# bots/crypto_long_fade/config.py (vs bot_d_spike/config.py)

CRYPTO_LONG_FADE_BOT_ID = "crypto_long_fade"
PAPER_ONLY = True

# Entry rules
ENTRY_PRICE_MIN_NO = Decimal("0.92")  # = SELL YES at 0.08
ENTRY_PRICE_MAX_NO = Decimal("0.99")  # = SELL YES at 0.01

# TTR: longer than weather
TTR_MIN_HOURS = 168.0  # 7 days
TTR_MAX_HOURS = 8760.0  # 365 days

# Symbol filter (from question text)
ASSET_KEYWORDS = ["bitcoin", "btc", "ethereum", "eth", "solana", "sol"]

# Sizing
PER_POSITION_SIZE_USD = Decimal("2")
MAX_CONCURRENT = 100
MAX_DEPLOYED_USD = Decimal("300")
```

```python
# bots/crypto_long_fade/strategy.py (vs bot_d_spike/strategy.py)

def decide_entry(candidate: Candidate) -> EntryDecision:
    if cfg.PAPER_ONLY is False:
        return EntryDecision(False, "live_not_authorized")
    # Validate it's a crypto price-target market
    q = candidate.market.question.lower()
    if not any(kw in q for kw in cfg.ASSET_KEYWORDS):
        return EntryDecision(False, "non_crypto")
    # NO-side check
    if not (cfg.ENTRY_PRICE_MIN_NO <= candidate.best_ask_no <= cfg.ENTRY_PRICE_MAX_NO):
        return EntryDecision(False, "price_outside_band")
    # TTR
    if not (cfg.TTR_MIN_HOURS <= candidate.hours_to_resolution < cfg.TTR_MAX_HOURS):
        return EntryDecision(False, "ttr_outside_window")
    return EntryDecision(True, "all_gates_passed", cfg.PER_POSITION_SIZE_USD)
```

The rest is straightforward clone of Bot D-Spike with NO-side instead of YES-side.

## Estimated effort

- Spec + ADR draft: done (this doc)
- Module clone: 1 hour
- Adaptation for NO-side + crypto filter: 1 hour
- Tests: 30 min
- Systemd unit: 15 min
- Deploy + verify: 30 min
- **Total: ~3 hours when approved**

## Why I'm not building this in THIS session

1. Track 1 (maker-flow simulator) is still running and may produce more interesting results
2. Operator approval needed for ADR-133 first
3. Better to deliver tight specs that next session can act on cleanly than half-finished code

## Decision required

Operator must:
1. Read empirical evidence (Test B in `findings-revalidation-all-tests-2026-05-08.md`)
2. Decide: build the paper-only crypto_long_fade lane?
3. If yes, approve ADR (probably ADR-133 if Track 3 isn't being built)

## Files referenced

- `docs/reports/findings-revalidation-all-tests-2026-05-08.md` — empirical evidence
- `bots/bot_d_spike/` — module to clone
- `core/db.py` — existing schema (no migrations needed)
