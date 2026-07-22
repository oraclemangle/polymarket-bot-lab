# Decision Ledger — longshot-research

Append-only ledger of concrete portfolio, design, and research-strategy decisions. One entry per finalized decision. Date + short title + status + cross-refs. Update on material changes only. Not advice.

---

## 2026-06-07 — ADR-189: Grok Build S466 verify/harden recorder storage guard (OQ-053 P0) + OQ-123 P1 backfill tooling + hygiene + doc updates

**Status:** accepted (logged in docs/decisions-log.md)

**Decision summary:** Accept S465/ADR-188 storage recovery state as verified (guard code + VPS empirical + the bot container code/sims/subagent match spec). Stage 3 untracked recovery files (guard.py + service/timer). No new logic harden (tests cover, surgical). P1: tooling + dry runs confirmed; dashboard accounting surface doc inaccuracy corrected ("present" at runtime_queries.py:2972-2982 with verbatim + pins). P2/P3: artifacts + 31/17 ghosts noted. New ADR-189 + updates to MEMORY/CHANGELOG/open-questions. All hygiene (tests 15/15, secret 0, ruff, git) passed. Posture: no live/wallet/funds.

**Key cross-refs:** ADR-188 (recovery), 183/187 (pause), OQ-053/123/124/125/109/100/067/122, /tmp/storage-verify... and oq123... reports, S466 close-off in HANDOFF.md.

**Rationale / evidence:** Empirical (VPS 93% active 0 failed fresh; the bot container via code audit) + subagent + re-review 0 issues. Pre-mut snapshots explicit.

---

## 2026-06-07 — ADR-190: Handoff to Claude Fable-5 for creative MAX profitability research (current bots DEAD / weather intermittent)

**Status:** accepted (logged in docs/decisions-log.md)

**Decision summary:** Create and deliver self-contained handoff prompt (docs/prompts/claude-fable5-max-profitability-creative-edges-2026-06-07.md) backed by >20 tool calls (canonicals, reports, bot_d code, DB stats, historical numbers). Instruct Fable-5 (via router/model_call; note: direct CLIs per discovery, no fable yaml) to get creative on new edges/ideas (hybrids, mid-band, co-sign, synthetic robustness, data moat expansion) with strict empirical validation on existing assets, solo scale, OQ unblock first (esp 123/124), paper/research only, safety (no live without new ADR + approval). Update MEMORY/CHANGELOG with S466 close-off. No code beyond hygiene.

**Key cross-refs:** ADR-189, 188/187/183, OQ-123/124/053/067/122/100/109/125, the prompt file, S466/467 entries in MEMORY/CHANGELOG/HANDOFF.md, active-operating-model, bot_d reports + recorder stats.

**Rationale / evidence:** Current lanes DEAD/archived per 187 or intermittent (small samples, outlier dependence, forward failures per S462/audits/strategy-e2). Data moat rich but under-utilized for new ideas. Fable-5 suited for synthesis + creative while respecting constraints (AGENTS/Claude.md, no scope creep).

---

## 2026-06-09 — S467 creative edge mining (Claude Fable-5 execution of 2026-06-07 handoff prompt): surface sports mid-band NO fade + elite-human cheap-tail co-sign as primary new candidates (KEEP pending validation); add OQ-127/128/129; calibration confirms structural dead-lanes thesis

**Status:** research output accepted (detailed in docs/reports/creative-edge-mining-2026-06-09.md; OQs added to open-questions.md; proposed ADR-191 text in report, NOT yet logged in decisions-log — strategy adoption is the operator decision per rules)

**Decision summary / verdicts (per report + close-off template):** 
- Sports mid-band NO fade (Idea 1, top rank): KEEP (universe calibration backtest.db 5,695 markets: sports YES 55-75c hit 58.5% vs 63.6c implied n=557; NO-fade sim +9.22% post-fee +8.50% ex-top-2, day-bootstrap CI [-5.78%,+23.27%]; corroborated by wallet-tag human cohort +10.1pp n=13,418; high velocity, no outlier dependence; mechanism favorite-longshot bias). 
- Elite-human cheap-tail co-sign filter (Idea 2): KEEP (+63.1% local n=78 replicating historical +40.5% CI-lower; filter on proven 0-15c corner, not full copy; advances OQ-099/128).
- Other 3 ideas (weather favorite maker inversion, etc.): KEEP for rotation or further mining per report signals.
- Structural thesis confirmed: dead lanes (Bot A/G, E/E2, etc.) bought overpriced 0-15c tails (+0.41pp gross 0-5c n=1,823 this tape); surviving positives sell the side.
- New OQs 127 (WANGZJ sports validation on the bot container), 128 (co-sign filter + prod join), 129 (daily calibration-tape harvester) added.
- Proposed ADR-191 draft in report (not logged).

**Key cross-refs:** 2026-06-07 handoff prompt, S466/467 in MEMORY/CHANGELOG/HANDOFF.md, creative-edge-mining report, OQ-123/124 still blocking live, ADR-190, all bot_d / wallet-tag / backtest reports, backtest.db / wallet_observer.db joins.

**Rationale / evidence:** Read-only 20+ tool calls + fresh local dev DB runs (backtest.db 5,695 matched pre-close prices; wallet_observer settlement join); every number run-specific 2026-06-09, re-execute cmds in report; dated sources; empirical gates (Murphy/bootstrap like prior reports); no live touches; reusable template followed.

**Next (operator/Claude):** OQ-127/128 prod validation on the bot container; if PASS, paper lane proposals with $1 sizing per ADR-163 pattern; log ADR-191 only on the operator adoption; continue rotation on other signals.

---

## 2026-06-11 — ADR-185: Complete fleet-wide audit and unprofitable lanes shutdown plan

**Status:** accepted (logged in docs/decisions-log.md)

**Decision summary:** Formally retire and shut down five unprofitable or falsified paper/research lanes (`bot_f_momentum_paper`, `bot_g_prime_late_cheap`, `bot_g_prime_take_profit`, `wc_negrisk_basket_paper`, and `bot_d_spike_short`). Stop and disable the corresponding systemd services/timers on the bot container and the VPS. All live trading remains paused under ADR-183. Weather Fade D (`bot_d_live_probe`) remains the only approved live candidate under a $137 USD starting wallet, strictly gated by the resolution of OQ-123.

**Key cross-refs:** ADR-183 (live pause), ADR-181 (loss pause), OQ-067 (weather scale), OQ-086 (spike), OQ-097 (FV), OQ-119 (set L), OQ-123 (backfill blocker), HANDOFF.md, MEMORY.md, CHANGELOG.md.

**Rationale / evidence:** Empirical performance data: Weather Fade D taker is the only positive realized live lane (`+$31.06` realized, `11.07%` ROI, robust to top-2 wins trimming). Other live lanes are deeply negative or suffer from adverse fill selection. Dead paper lanes have failed their sample gates or are fee-gated.

---

*Ledger initialized 2026-06-09 from S466/467 close-off. Append new material decisions only. Cross-check against decisions-log.md for full ADR text.*