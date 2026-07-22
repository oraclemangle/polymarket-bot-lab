# Round 4 — Oracle validation + honest live update

Copy-paste to Grok. Round 3 ended with "run both variants in parallel, pull the Chainlink subset now, and keep the paper bot live." Here's where we are.

---

```
Three short updates and one honest blocker:

**1. Oracle validation (your round-3 ask #3).** Ran the Chainlink subset
check. Filtered to "Up or Down" markets only (our strategy universe —
threshold markets are noise here). Sample n=80 resolved markets, 65
where both Gamma and our Binance-spot proxy could determine outcome:

    Agreement: 95.4% (62/65)
    Disagreement: 3 (4.6%)
    All 3 disagreements are ≤1.2bps marginal moves — exact-timestamp
    noise between Binance spot and Chainlink snapshot, as predicted.

Backtest conclusion preserved. The 4 jackpot winners were all high-gap
markets (>20bps), well outside the oracle-noise band.

**2. Two-mode Bot G deployed.** Both jackpot (t=60s, ≤2¢) and scalp
(t=30s, ≤2¢) run in parallel on same scan loop. Per-tick logic picks
the tightest-eligible window. Per-mode attribution via Event rows so
dashboard can split realised P&L by mode as data accumulates.

**3. Fractional Kelly documented.** At b≈99, p≈0.08, full Kelly ≈7% of
bankroll. We're at $5/trade on a $500 bankroll = 1% = ~1/7 Kelly. Matches
your 1/8-to-1/10 recommendation, slightly more aggressive. Keeping for
paper; will tighten before any live.

**Now the honest part — n=0 after 14 hours.**

The paper bot has been live since yesterday. Zero entries. Root cause
wasn't strategy — it was infrastructure. Bot G depends on a separate
"recorder" daemon (Bot E's data collector) for its book-depth reads.
That recorder has been in a crash loop: 23 restarts overnight, hitting
systemd's rate limit and stopping altogether for 1h44m.

Dumped the Python stack at one of the crashes via py-spy. Real bug was
subtle: asyncio.gather() without return_exceptions, so any task crash
in the producer graph (PM WSS, CEX WSS, heartbeat, discovery) cancelled
all the others in a cascade. The self-abort safety nets caught the
silent-zombie state but not fast enough to prevent starvation.

Just shipped a supervisor wrapper that catches per-task exceptions,
logs with stack trace, and restarts with exponential backoff. return_
exceptions=True so no cascades. Deployed, recorder's been clean for
~10 min. If this holds, Bot G should start producing data today.

Your n=50 gate stands. Just haven't started the clock yet.

**One follow-up question for you while we wait:**

When a 15-min crypto market has BOTH sides trading above ≤2¢
(say YES=3¢, NO=4¢), the thesis implicitly says the losing side may
still reverse. But empirically, is there a regime where BOTH being
above tail-threshold is actually a NEGATIVE signal — "neither side is
the obvious loser → don't bet"? Should Bot G have a "minimum spread
between sides" filter so we only enter when one side is clearly the
tail and the other is near-certainty? Or is that overfitting?

Will report back on:
* First fills (recorder stability permitting)
* n=10 live paper — per-mode WR breakdown
* Any new stack dumps if the supervisor misses something
```

---

## Operational notes to self

Don't hide the infrastructure story from Grok — they respect honest reporting of failures. The "0 fills because our recorder is a crash-loop" is more valuable signal for the discussion than "here are more numbers."

The "minimum spread between sides" question is genuine research — I don't actually know the answer. Possible hypotheses:
- Tight spread (both near 50¢) = genuine uncertainty → tail-chasing works worse here
- Wide spread (one side <5¢) = market thinks it's clear → tail-chasing may work better
- OR: depends on whether the CEX gap is actually big enough to drive the spread

Worth a backtest filter sweep if the question is interesting.
