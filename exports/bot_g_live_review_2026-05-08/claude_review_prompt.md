# Paste-Ready Claude Review Prompt

You are reviewing a PII-stripped crypto binary-options trading strategy. The
attached Python file is standalone and safe to inspect. It contains only the
entry decision logic, current parameters, and a synthetic example. It excludes
wallets, keys, hostnames, raw trade logs, order ids, and all live order
placement code.

Strategy summary:

- Market type: near-resolution crypto Up/Down binary markets.
- Thesis: in the final minute, the apparently losing side can be underpriced
  as a longshot tail.
- Current live universe: BTC, ETH, SOL.
- Current live band: buy the cheap side only at 3.5c to 5.5c.
- Current entry window: 60s to 5s before close.
- Current size: fixed $1 notional per entry.
- Current cap: 20 entries/day, $100 daily gross, 10 open positions.
- Current spread-purity rule: the opposite side must have ask >= 91c.
- Current live transfer rule: bid one 1c tick above observed ask, capped at
  5.5c.
- Current CEX confirmation and book-depletion hard gates are disabled, but the
  code includes them for review.
- Current evidence note: this is not proven profitable. Recent internal
  summaries were negative; treat the task as deciding whether to fix, filter,
  or retire the idea.

Please review `bot_g_live_sanitized.py` and answer:

1. What are the top 5 ways this strategy can lose money even if the historical
   thesis looked attractive?
2. Which current parameter is most likely damaging expectancy: entry band,
   entry timing, one-tick improvement, no CEX gate, spread-purity gate,
   symbol mix, or hold-to-resolution exit?
3. What concrete filters or exit rules would you test first, and why?
4. For each proposed change, specify the minimum replay/live sample needed,
   the pass/fail threshold, and the failure mode it addresses.
5. What changes should not be made because they would only overfit?
6. If you had to give a binary recommendation today, would you continue,
   pause, or retire this live strategy?

Please keep the answer practical: prioritize expectancy math, fill realism,
queue/latency effects, and test design over broad trading advice.
