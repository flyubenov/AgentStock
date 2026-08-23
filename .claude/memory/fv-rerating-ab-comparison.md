---
name: fv-rerating-ab-comparison
description: "A/B comparison (2026-08-23) of the new dynamic WACC-rate+quality-MOS pipeline vs old static 10%/0.90, across all 136 DB tickers. Committed under docs/analysis/. Session paused, will continue later."
metadata: 
  node_type: memory
  type: project
  originSessionId: ab39a665-b1a3-474c-8aff-036288d4b0a8
  modified: 2026-08-22T21:58:11.270Z
---

Post-landing of [[wacc-mos-moat-margin-design]], the user asked for a full new-vs-old
comparison of Fair Value + Quality Score across every ticker in the DB. **DONE + committed**
on branch `wacc-mos-moat-margin-design` (`51e02b8`) under
`docs/analysis/2026-08-23-fv-rerating-comparison/` (README + `rerating_report.html` +
`compare_out.csv` + reproducible `pipeline_compare.py`). Interactive report artifact:
https://claude.ai/code/artifact/7a2bd751-69d6-4578-991b-9e5c7acf1866

**Method:** Database sheet = 136 tickers. Per ticker, ONE fundamentals fetch → four numbers:
FV_old = `engine.evaluate` with the three source keys stripped (neutral 10%/0.90 = master);
FV_new = live `engine.run`; Q_old = `compute_metrics`+`score` with pre-Option-A `wacc()`
(monkeypatched, no non-financial floor/cap); Q_new = current Option-A `wacc()`. **Read-only —
did NOT touch stored DB rows or /recalculate.**

**Results:** Quality **132/134 unchanged** (only OKTA, LEU −0.2 — the DB's captive-debt-signature
names). FV **32 up / 74 down / 7 flat** of 113 valued, median **−3.3%**, range −19.3%..+41.6%
(PFE +41.6, low-WACC DDM-sensitive). 23 names unvaluable by BOTH models (pre-profit/SPAC/foreign
→ N/A). FINANCIALs byte-identical (rate-invariant + no durability signal → neutral MOS). Durable
low-WACC compounders re-rate up, speculative high-beta names down — the intended risk tilt.

**HARNESS LESSON:** `pipeline_compare.py` MUST run `CONCURRENCY=1`. It monkeypatches shared module
globals (`engine.evaluate` / `engine.fetch_screener_inputs` / `metrics.wacc`), so parallel
coroutines corrupt each other's captures — a concurrency=4 run produced impossible +1788% outliers
(harness race, NOT the pipeline). Serial rerun (~330s) is the correct data.

**Pre-existing issues surfaced (unrelated to the feature, candidates if user resumes):** ZETA hits a
quality-metric TypeError (no score); SYM's `roic_5y_avg` is a broken ROIC-denominator artifact
(−67200%) though its FV delta stays bounded.

**SESSION PAUSED 2026-08-23** ("will continue later"). Branch NOT merged (user chose keep-as-is at
finishing-a-development-branch). Branch @ `51e02b8`, 520 tests, base `ab6df3b`. SDD ledger
`.superpowers/sdd/2026-08-21-fv-quality-discount-mos/progress.md` has the full resume map. No pending/
blocking work.
