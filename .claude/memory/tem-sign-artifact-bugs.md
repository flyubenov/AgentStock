---
name: tem-sign-artifact-bugs
description: TEM validation exposed a class of sign-artifact bugs — ratios with negative denominators scored as favorable; plus magnitude-based pre-profit guard let negative DCFs into the blend
metadata: 
  node_type: memory
  type: project
  originSessionId: aeef9c29-8bb7-4fc5-8aea-4e7a5c8d7f4d
---

TEM (Tempus AI) validation, 2026-07-16. DONE + MERGED to master (no-ff `26856c0`).
TEM read Quality 6.2 / no fair value. Both verdicts were reached through faulty machinery.

**Bug class: ratios whose denominator goes negative score as if favorable.** A ratio can
go negative for two opposite reasons, and the scorers only ever assumed the good one:
- `leverage_score` (screener/scoring.py) returns 10.0 on `r <= 0` — the "net cash" rule.
  Correct only when the NUMERATOR (net debt) is negative. TEM had +$635M net debt over
  -$185M EBITDA = -3.43 → scored 10/10 (pristine) when it's the worst case. Same for
  Net Debt / FCF. Fixed by gating in `_section_iii` on `m.ebitda > 0` / `m.fcf > 0`
  (NOT inside leverage_score — it only sees the ratio, and `leverage_score(-1, 4.5) == 10`
  must stay for genuine net cash). A None denominator = unknown, keep old behaviour.
- `earnings_quality` = OCF/NI (screener/metrics.py) is doubly inverted for loss-makers:
  two negatives → flattering positive (TEM -218/-245 = +0.89 → 6/10 "healthy"), while an
  OCF-positive loss-maker (the genuinely BETTER case) → negative → worst score. Now gated
  on `ni > 1e-6`.
→ TEM Quality 6.1 → **5.3** (Section III 6.67 → 0.0).

**The pre-profit guard was magnitude-based, not sign-based.** It triggered on
FCF/revenue < -25% (`FCF_MARGIN_FLOOR`, now deleted). TEM at -18% slipped under it, so a
DCF built on -$245M FCF ran anyway → -$47.47/share, poisoning the composite → declined by
the negative-composite clamp (NOT the pre-profit guard, despite the "pre-profit" reading).
A DCF of negative cash flows is negative by construction at ANY burn depth, so a magnitude
floor perversely only let the near-breakeven names through with a meaningless negative leg
(at -1% FCF margin TEM would have emitted a *completed* FV of $12.70 vs its own EV/Sales
leg's $29). Guard now triggers on `fcf_ttm < 0`.

**EARLY_GROWTH carried a 0.35 DCF weight** despite the tier being DEFINED by
unprofitability (classifier rule 4: revenue growth > 20% AND eps/ebitda <= 0) — guaranteed
negative for every name it exists to value. Now zeroed when `fcf_ttm <= 0`, before the
guard; the guard then skips the tier via `weights.get("dcf", 0) > 0`, the same mechanism
that skips FINANCIAL. Elegant composition — reuse it for any future tier-level DCF drop.

**Blast radius** (269 → 277 tests, all pass; live basket of 20 names, only 3 moved):
- TEM: DECLINED → **$29.02 (-45%)**, Q 6.1 → 5.3
- INTC: DECLINED → **$20.38 (-79%)** — FCF -$4.9B but EBITDA +$14.2B → IREN-style
  0.85/0.15 reroute, P/E leg self-drops (EPS -0.6) → EV/EBITDA at weight 1.0. Sound; the
  negative-composite clamp (see [[mega-cap-tier-and-valuation-guards]]) was a band-aid
  over exactly this bug and remains as a backstop.
- NBIS: DECLINED[PRE_PROFIT] → **$15.13 (-91%)** — EARLY_GROWTH, EBITDA -$39M → EV/Sales
  at weight 1.0. **CAVEAT/open issue:** NBIS revenue growth is 6.839 (684%) but
  `build_scenarios` caps growth at 0.20-0.25 (see [[revenue-coupled-growth-cap]]), so the
  sole surviving leg values a 684% grower at 20% off a 58x EV/Sales → -91% is mechanically
  consistent but the growth input is an order of magnitude off. The cap is pre-existing but
  my fix made it LOAD-BEARING for cash-burning EARLY_GROWTH names (EV/Sales now carries
  weight 1.0 instead of being declined). TEM is milder (36% actual → 20% capped) so $29.02
  is somewhat conservative too. Revisit before trusting EARLY_GROWTH FVs.

**FOLLOW-UP DONE** (commit `95cebec`): the NBIS caveat above is resolved.
EARLY_GROWTH now runs its own growth-coupled ceiling `EG_CAP_CEIL` (0.45 at first, **lowered to
0.35** @`3ef06c9` — see CAUTION) on the SAME
shallow slope, gated on `EG_REVENUE_FLOOR = $500M` (scale, not rate — a tiny base prints
hyper-growth on arithmetic). TEM $29.02 -> $34.57 (-35%); NBIS $15.13 -> $103.99 (-39%).
283 tests pass; only the 2 EARLY_GROWTH names in a 20-name basket move.

Facts worth keeping from that investigation:
- **NBIS's 684% is REAL** — reconciles with Q1 YoY (+683.9%) and annual (+479%),
  accelerating +75% QoQ. My "noisy yfinance" suspicion was WRONG; check statements before
  blaming the feed.
- **yfinance `revenueGrowth` IS the latest-quarter YoY figure** (verified on both names).
  So it's already the most current organic read. `revenue_growth_stmt` (ANNUAL) is worse
  for TEM — it reads 83.4%, inflated by the Feb-2025 Ambry deal, vs the 36.1% organic
  run-rate. Don't "harden" growth by switching to the annual figure.
- `revenue_growth_stmt` is **dead code for the whole EARLY_GROWTH tier**: returned only
  inside `fetch_ev_ebitda_history`'s dict, which bails to None when the EV/EBITDA median
  is uncomputable — always, for negative EBITDA. `_statement_revenue_yoy` computes it fine
  and it's then discarded.
- **`EV_SALES_CAP = 8.0` is dead**: `min(m, EV_SALES_CAP, MATURE_EV_SALES=2.0)` always
  reduces to `min(m, 2.0)`. Vestigial from the port (c77e1f9); MATURE_EV_SALES was layered
  on later (e8a9517) and shadowed it. Still unremoved.
- **A magnitude threshold needs a real cliff to sit on.** I proposed declining EARLY_GROWTH
  when growth outran the cap — the user caught that this repeats the exact error the
  pre-profit guard made (arbitrary threshold, declines the extreme, passes the middling).
  Sign is a cliff (a DCF on negative FCF is wrong by construction); high growth is not (the
  EV/Sales model just degrades smoothly into a conservative lower bound). Couple to the
  variable instead.

**BOTH REMAINING ITEMS DONE** (commit `64ca8df`):
- **Stale TTM base FIXED.** TTM is the SUM of 4 quarters = revenue centred ~6mo back, so
  it lags today on a fast grower (NBIS $873M vs a $1.596B run-rate). `models.run_rate_revenue`
  annualises the latest quarter (x4), gated on `RUN_RATE_GROWTH_FLOOR = 0.50` + only-help;
  `calc_ev_sales` prefers `revenue_run_rate` over `revenue_ttm`. The growth gate is what
  separates "TTM is stale" from "Q4 is seasonally big" — a retailer's Q4 annualises above TTM
  but at single-digit growth TTM does NOT lag. Verified live: COST/WMT/AAPL/AMZN untouched;
  only NBIS/NVDA/APP clear it (and NVDA/APP are unaffected anyway — pick_ev_multiple folds
  their EV/Sales leg away at healthy EBITDA margins). `engine.run` pre-gates on `info` growth
  so the extra quarterly fetch is only paid by names that could qualify (rate limits).
  **My earlier "double-count" worry was WRONG**: revenue_growth is trailing and only selects
  the base and the cap; the projection runs FORWARD from t=0, so a more accurate t=0 is a
  correction, not extra growth.
- **`EV_SALES_CAP` removed** (was dead behind MATURE_EV_SALES=2.0), along with
  `test_ev_sales_multiple_is_capped` — it compared 20.0 vs 8.0, both clamped to 2.0, so it
  passed regardless of the constant. 288 tests pass.

**CEILING RECALIBRATED 0.45 → 0.35** @`3ef06c9`; NBIS settled at **$91.95 (-46%)**.
The user caught this: 0.45 had been calibrated against the STALE base (it showed $103.99/-39%
at the time it was picked), so when `run_rate_revenue` lifted the base 1.83x the same ceiling
gave $189.32 (+10%). **The cap had been doing double duty** — half growth, half silently
compensating for a base lagging 83% — and once the base was fixed that job vanished, but I
left the ceiling up, double-counting the compensation. I had even WRITTEN this warning
("raising the ceiling partly compensates for a stale base... the wrong mechanism") and then
walked into it. **Lesson: when you correct an input, re-derive every constant that was tuned
against the old one.**

Choose the ceiling by the SHAPE of the curve, not by a target number. Swept on the corrected
base: the whole 0.35–0.40 band leaves NBIS robustly overvalued (-46% → -23%) and moves ~$4 per
0.01 — the verdict is invariant across it. FV crosses price at **0.4361**, so 0.45 sat just PAST
the crossover on a knife edge (0.01 flips buy/sell) with the curve going convex above. The real
distinction is "inside the stable zone" vs "on the crossover", not 0.35 vs 0.40.

**Still treat EARLY_GROWTH FV as a wide range, not a point.** NBIS ran $15.13 → $103.99 →
$189.32 → $91.95 across four commits. EV/Sales is hyper-sensitive (growth AND exit multiple
enter exponentially over 10y) and carries weight 1.0 for this tier, so the value rests almost
entirely on two CHOSEN constants (EG_CAP_CEIL 0.35, MATURE_EV_SALES 2.0) over a run-rate base.
The ceiling is set on a thin sample — only >140% growers reach it, so NBIS is currently the only
observation. Prefer round defensible assumptions over values reverse-engineered from one name.

**REGRESSION FROM THIS WORK, FOUND + FIXED @`cdb72a2`** (ASTS validation, 2026-07-17).
The EARLY_GROWTH DCF drop above says the pre-profit guard skipping the tier is fine —
"a zero DCF weight, nothing left to protect". **WRONG.** The guard had a SECOND, unstated
job: refusing to value a cash-burning company whose trailing financials support NO model.
ASTS emitted $1.15 (-97.9%) off $84.9M of lumpy contract revenue (one $54.3M milestone
quarter) vs a $21.4B mcap, ev_sales weight 1.00 — proved by worktree at `aa5c165` that it
DECLINED before `507f5bd`. Only ASTS fell through: it alone is both hyper-growth
(→EARLY_GROWTH) and pre-commercial; ACHR/USAR/OKLO/NXE have ~0 growth → size tiers →
DCF weight > 0 → original guard still fires. **Lesson: when you disable a guard for a
tier, enumerate every case it was catching, not just the one you're reasoning about.**
Fix: decline when `set(results) == {"ev_sales"} and not _eg_cap_eligible(fin)` — the model
can't call a revenue base uninformative about GROWTH and authoritative about VALUE at once.
Reuses the existing floor, no new constant. Narrow on purpose (SOLE anchor AND sub-floor):
AMBA/IDR are sub-floor but corroborated by a DCF/PE leg; NBIS is sole-ev_sales but clears
the floor. **Rejected an EBITDA-margin < -100% gate** — looks scale-free, but wrongly
catches FIG ($1.16B real recurring revenue, -124.7% margin from IPO stock-comp only).

**EG_REVENUE_FLOOR swept 500M/250M/100M/50M/0 — LEAVE AT 500M.** Totally INERT 500M→100M
(every valued name clears it anyway; every sub-floor name declines or has another leg), and
at ~85M it reverts the ASTS fix ($3.67/-93%). So the floor is in practice a pure ASTS
decline switch — its cap-gating job has ZERO live effect. It's a cliff, not a ramp: you
can't tune it by nudging and watching, nothing moves until it snaps. Keep it high on
asymmetry: too high = a bounded, mildly conservative FV; too low = confident false precision
about a business the statements can't see. Set on zero live observations — same posture as
EG_CAP_CEIL (sample of one): prefer the round defensible number until a real name lands in
the $100M-$500M band. **Design note: the floor now carries TWO jobs behind one constant**
(elevated cap gate + sole-anchor decline). Deliberately not split — two constants each tuned
on zero observations is worse than one, and both encode the same belief — but tuning one job
moves the other.

Related: [[iren-opmargin-capex-reroute]] (the 0.85/0.15 reroute this composes with),
[[sofi-lender-crypto-misclassification]] (the other pre-profit-guard misfire),
[[revenue-coupled-growth-cap]] (the 0.20->0.25 ramp EG_CAP_CEIL extends).
