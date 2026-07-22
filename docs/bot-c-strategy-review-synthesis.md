# Bot C strategy review — synthesis

**Reviewers:** Gemini 2.5 Flash (Vertex AI) + GLM-5.1 (Ollama Cloud)
**Date:** 2026-04-15
**Raw outputs:** `docs/bot-c-review-gemini-flash.md`, `docs/bot-c-review-glm-5.1.md`

Both reviewers independently concluded **the strategy should not trade
live in its current form.** Paper trading is fine and will produce
useful calibration data, but several corrections must land before real
capital is at risk.

The findings below are ordered by blast radius. Items marked **[BOTH]**
were flagged independently by each reviewer; **[GLM]** or **[GEM]** was
flagged by one.

## Critical (guaranteed money loss)

### 1. Barrier vs terminal probability for "hit" markets **[GLM]**

**The single biggest flaw.** Polymarket question patterns include:

- `"Will TSLA hit (LOW) $337 Week of April 13"` — resolves YES if the
  price *ever touches* the strike during the week.
- `"Will Gold (GC) hit (HIGH) $9,000 by end of June"` — same "ever
  touches" semantic.

The current model computes **terminal probability** `P(S_T > K)` for all
of these. The true semantic is **barrier probability** `P(max S_t ≥ K)`
which under zero-drift GBM is *~2× the terminal probability* for
strikes not too far from spot (reflection principle).

Consequence: on "hit" markets the model **systematically understates**
the true probability and produces spurious negative edges, routing the
bot into BUY_NO trades on markets that are actually fairly priced.

**Evidence in the live decisions log:** the AAPL "hit (LOW) $252"
market shows model=0.000 vs market=0.105 → edge -0.105 → would trigger
BUY_NO at threshold 0.10. The market is almost certainly pricing the
touch probability correctly; our model is pricing the terminal
probability and losing the 5–10 bp gap.

The "finish above/below" and "settle over/under" patterns are correct
(terminal resolution).

**Fix:** add a `question_kind ∈ {terminal, barrier}` field to
`ParsedMarket`, populated by `discovery.py`. In `strategy.py` replace
`gbm_prob_above / gbm_prob_below` for barrier markets with:

    P(max S_t ≥ K) = 1 − Φ(d1) + (K/S)^{2μ/σ² − 1} · Φ(d2)
    [drift 0 degenerates to 2 · P(S_T ≥ K) for K > S]

### 2. No fee-adjusted edge **[BOTH]**

Polymarket's taker fee curve peaks near 3% at 50% probability and falls
to near-zero at the tails. The current `edge = model_p_yes − yes_price`
does not subtract the fee. A 0.15 gross edge at 0.50 mid is roughly
0.12 net.

**Fix:** `net_edge = gross_edge − fee_usd / trade_notional_usd`, and
only route to executor if `net_edge ≥ threshold`.

### 3. No exit logic / no stop loss **[BOTH]**

Positions hold to resolution regardless of whether the model still
believes in them. If the underlying moves such that model and market
converge (edge goes to 0 or reverses), the bot has no mechanism to
cut. For a 90-day horizon on a $10 ticket this isn't catastrophic per
trade, but aggregated across many trades it gives up a lot of variance
reduction.

**Fix:** two exits to add:

- **Edge-collapse exit:** if the *re-scored* model edge on an open
  position drops below 0.03 (or flips sign), cancel any unfilled
  portion + close at market.
- **Time-stop:** if we're within the last 10% of horizon with
  |current_model_p − filled_price| < 0.05, exit. No point holding
  through resolution variance for a consumed edge.

### 4. Zero-drift GBM for equities **[GEM]**

Equities have documented positive drift (7–10%/yr ex-dividend). Over a
weekly horizon drift is small but over a 90-day horizon it moves the
terminal distribution's mean by ~2σ. A model that ignores drift will
systematically:

- **Under-price** "finish above" markets on trending equities → spurious
  BUY_NO signals.
- **Over-price** "finish below" markets → spurious BUY_NO on fade.

**Fix:** incorporate a simple drift estimate per symbol. Two cheap
options: (a) risk-free + equity premium proxy (~0.05/yr), (b) trailing
6-month realized drift per feed. Log-return drift μ enters the d1
formula as `d = (ln(S/K) + (μ − σ²/2)T) / (σ√T)`.

### 5. Annualisation factor wrong for non-equity feeds **[BOTH]**

`bars_per_year = 5,896,800` is the equity-session constant (252d × 6.5h
× 3600s). Applied to crypto (24/7), this **understates σ** by a factor
of ~2.5 (crypto actual bars_per_year ≈ 365 × 24 × 3600 = 31.5M).
Applied to commodities/FX it's also wrong in the other direction.

**Fix:** `bars_per_year` must be a function of the feed's category
(equity / etf / commodity / crypto). Store per-category annualisation
in `core.pyth_feeds`.

## High severity

### 6. Adverse selection via `mid + 0.01` limit **[GEM]**

Posting 1¢ above the apparent mid is fill-seeking in a book where we
can't see depth. If a more-informed counterparty takes our offer, it's
because they believe fair is < our price. The sizer doesn't account
for this.

**Fix options:** (a) post at mid (or mid − 0.005), accept slower fills;
(b) reduce edge threshold bump by the expected adverse-selection cost
(~0.02 per fill based on Grok/Polymarket MM notes); (c) make-side only
— post on the passive side of the book.

### 7. Limit price computation uses `1 − yes_price` as "NO price" **[GLM]**

For BUY_NO the code computes `mid_no = 1 − yes_price`. That's only
accurate if the book has a tight spread and YES + NO sums to ~1. In
thin books the NO side can have its own bid/ask that deviates.

**Fix:** fetch both YES and NO prices from Gamma (`outcomePrices[0/1]`),
use the actual NO price rather than synthesising from YES.

### 8. Edge threshold mismatch between analyst and executor **[GLM]**

`DEFAULT_EDGE_THRESHOLD = 0.10` in analyst; `BOT_C_MIN_EDGE_FOR_ORDER =
0.15` in executor. The analyst persists decisions at the looser
threshold but the executor's stricter threshold silently filters half
of them. Workable but confusing; document or unify.

### 9. No dedupe on symbol+direction+strike collisions **[GLM]**

Dedupe is only on `gamma_id`. If Polymarket publishes two markets on
the same underlying with the same strike (e.g. duplicated on Binance
vs Coinbase rails), we could double-size the same economic exposure.

**Fix:** dedupe by `(symbol, direction, round(strike, 2),
resolution_date.date())` tuple in addition to gamma_id.

### 10. Volatility from 30-minute window is too noisy for multi-day
horizons **[BOTH]**

30 minutes of 1s bars (1,800 obs) is fine for measurement but picks up
intraday spikes, news-minute moves, and microstructure noise. Using
that σ to extrapolate over weeks or months inflates or deflates the
estimate arbitrarily.

**Fix:** blend near-term σ with a longer-lookback σ (e.g., 5-day or
20-day, annualised). For the short-horizon markets (< 48h) near-term
σ is appropriate; for >7d markets use a term-structure blend.

### 11. No awareness of market schedule / overnight gaps **[GEM]**

Equities have overnight + weekend gaps that violate GBM's
continuous-time assumption. A Friday-close Polymarket market on
`AAPL finish above X next week` prices in the full weekend gap risk,
but our model extrapolates an intraday σ over continuous time.

**Fix:** mark `market_closed_hours` out of `t_years` when the
underlying is equity; add a jump term for earnings-day markets.

## Medium severity

### 12. Question regex defaults to current year on ambiguous dates **[GEM]**

`"Will X hit HIGH $K by end of June"` with no year will resolve to
2026; in December that becomes 2026 (a *past* date) → t_years ≤ 0 →
P → 1 or 0 → huge false edge.

**Fix:** when no year is present, pick the *next* occurrence of that
month.

### 13. GTC order staleness **[GLM]**

Unfilled GTC orders linger. If the model edge disappears 10 minutes
later but the order is still on the book, it may get filled at a price
that's no longer +EV.

**Fix:** periodically re-score open orders; cancel any where the
current model edge is < 0.05 absolute.

### 14. Pyth feed subscription vs use mismatch **[GLM]**

We subscribe to 14 feeds via Lazer Pro but only 5 consistently make it
into the 30-min volatility window (the warmup gate). Low-traffic feeds
(e.g., EWY) may never warm up.

**Fix:** emit a warning when a market matches a symbol whose feed has
< 30 bars in the last hour; skip those decisions.

### 15. "Between L and H" uses terminal probability **[BOTH]**

Already acknowledged in the prompt. Same fix path as finding #1 —
barrier-pricing for `P(L ≤ min S_t ≤ max S_t ≤ H)`.

## Hygiene

### 16. `PYTH_TOKEN` not centralised in Settings

Already fixed in audit-fixes commit.

### 17. Bankroll math at $50 × 3 positions

Three concurrent $10 positions use 60% of the $50 cap — leaves no
headroom for a fourth high-edge signal. Either raise bankroll or
reduce per-trade.

## Priority-ordered remediation list (before live)

If you decide to flip Bot C to live on a $2k bankroll, these must land
in this order:

1. **Barrier probability for "hit" markets** (finding #1). The biggest
   single improvement. ~2 hours of work.
2. **Fee-adjusted net edge** (finding #2). ~30 minutes.
3. **Annualisation per asset class** (finding #5). ~30 minutes.
4. **Drift term for equity feeds** (finding #4). ~1 hour.
5. **Edge-collapse exit + time-stop** (finding #3). ~2 hours.
6. **Lower limit-price offset + make-side routing** (finding #6).
   ~1 hour.
7. **Year-rollover date parsing** (finding #12). 15 minutes.
8. **Volatility term-structure blend** (finding #10). ~2 hours.

Total: ~10 hours of focused work before live is responsible.

## Paper-mode implication

**Paper trading now is fine and informative** — even a biased model
generates useful data on the *slippage, fill, and resolution-variance*
side of the execution stack. The paper trades will also expose the
"hit vs terminal" bias quickly (barrier markets will produce a steady
stream of losing BUY_NO signals whose resolutions go the other way).
Let it run for 5–7 days, then the first live-ready version of the
model can use that dataset for calibration.
