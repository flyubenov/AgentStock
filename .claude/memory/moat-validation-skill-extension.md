---
name: moat-validation-skill-extension
description: "DONE + IMPLEMENTED (feat/validate-moat): extended validating-agent-stock to validate Moat score (quant reconciliation + qualitative internet-research moat-source analysis, Approach A). Self-test PASSED (MCO corroborated, PANW score artifact)."
metadata:
  node_type: memory
  type: project
  originSessionId: cd567975-3d92-49b9-95bc-462fcb83e2cb
  modified: 2026-08-27T20:09:19.251Z
---

**Task:** extend the `validating-agent-stock` skill to also validate a ticker's **Moat
Score** — both the quantitative formula/metrics/method (like the existing FV/Quality/R-R
validation) AND a **qualitative internet-research** analysis of whether a *real* moat
exists and what its source is. Mirrors the [[validating-skill-rr-extension]] pattern
(new reference doc + harness dump + lean SKILL.md wiring). Docs+harness only, **no engine
change** (scorer is DONE — see [[moat-score-design]]).

**STATUS: DONE + IMPLEMENTED on branch `feat/validate-moat`** (cut from master,
master==origin/main @`88fcf48`). Three implementation commits:
- `4457620` feat(validate): dump MOAT block in validate_ticker harness
- `3e48c5b` docs(validate): add moat-validation reference doc
- `350e8c0` docs(validate): wire Moat validation into SKILL.md (triggers, routing, map)

**Self-test (acceptance gate) result — PASSED.** Ran the harness live on MCO and PANW,
followed `moat-validation.md`'s quant-reconciliation + divergence-matrix recipe end to
end:
- **MCO:** `moat_score 79.5`, `variant: ROIC`, `gated: false`, ROIC 5y-avg 19.79% vs WACC
  10.65% (+13.6pp spread), goodwill 74.5% (does NOT trigger tangible-ROIC routing since
  tpe/fpe < 1.5). Reconciles exactly: `round(100*79.5/100,1)==79.5`. Qual = Wide → **cell:
  CORROBORATED.** Matches the worked example in `moat-validation.md` almost exactly — no
  doc drift, no edit needed.
- **PANW:** `moat_score 77.8` (earned 77.75), `variant: TANGIBLE_ROIC`
  (`_acquisition_distorted` fired), full-capital `roic_5y_avg` 8.44% *below* WACC 9.10%
  (confirms the ex-goodwill routing bypassed the economic-profit gate — would have gated
  to 35 on plain ROIC), `gated: false`. Reconciles: `round(100*77.75/100,1)==77.8`. Qual =
  Narrow/real-but-contestable → **cell: SCORE ARTIFACT**, tangible-ROIC mechanism named.
  Matches the worked example almost exactly — no drift.
- **Regression check (NBIS `--inputs`):** FV/QUALITY/RISK_REWARD/INPUTS blocks unchanged
  in shape; new MOAT block additive only (NBIS moat_score 5.6, `gated: true` — correctly
  flagged, no analysis needed for this check).
- Acceptance criterion: analyst following the doc reaches MCO→CORROBORATED and
  PANW→SCORE ARTIFACT with the tangible-ROIC mechanism named. **PASS.**

**Settled decisions (user-approved):**
- **Per-ticker only** (NOT a screener). Primary goal = "is there a real moat and what is
  its source"; hidden-gems is a byproduct, NOT a focus ("do not put focus on finding gems").
- **Qualitative analysis is PRIMARY; the numeric Moat score only CORROBORATES** (inversion
  vs R-R, where quant internal-correctness leads). The number can *suggest* a moat but
  can't prove it.
- **Approach A — evidence-graded structured analysis** (chosen over B narrative-checklist,
  C score-anchored). Grading discipline is what enforces "is it REAL" over "sounds good".
- **Structured verdict** header: `Moat: None/Narrow/Wide · Source(s) · Trend
  Widening/Stable/Eroding · Durability horizon`, then evidence prose + quant reconciliation.
  (Verbal bands OK here — the ENGINE avoids bands for the number, but this analyst artifact
  is separate.)
- **Taxonomy** (must be exhaustive): Network effects · Intangible assets (brands/patents/
  licenses/regulatory IP) · Switching costs · Cost advantage · Efficient scale · Regulatory
  /legal · **Other/emergent** (real bucket, HIGHER evidentiary bar — name the concrete
  mechanism, not a catch-all).
- **Evidence grades:** `DATA` (verifiable + web citation) / `JUDGMENT` (analyst inference)
  / `COMPANY-CLAIM` (self-serving IR/marketing — DISCOUNTED, never counted as moat evidence).

**Shipped architecture:**
- `validate_ticker.py`: MOAT block — `moat_score` + full `moat_breakdown`
  (variant/pillars/maxima/earned/available/gated/excluded) + moat-relevant slice of
  `sc.metrics` (roic_series, roic_5y_avg, roic_series_ex_goodwill, roic_5y_ex_goodwill,
  rote_series, rote_5y_avg, wacc, roic_wacc_spread, goodwill/intangible share, margin
  series + trajectories, fcf, ebitda). No `--inputs` flag needed for moat.
- `moat-validation.md` — reference doc, structured like `risk-reward-validation.md`:
  qualitative methodology (5 steps, run before the number) → verdict bands (None/Narrow/
  Wide) → quant reconciliation recipe (headline, gate, coverage floor, variant, per-pillar
  table) → divergence matrix (4 quadrants: CORROBORATED / EMERGING-OR-DISTORTED / SCORE
  ARTIFACT / AGREEMENT) → worked examples (MCO, PANW).
- `SKILL.md` — description + When-to-use + routing extended for moat questions.
- NO backend/engine change; harness stays read-only.

**Qualitative methodology (5 steps, runs BEFORE looking at the number):**
1. Frame the business (from web, not marketing) — what it sells/to whom/how it earns.
2. Enumerate ALL candidate moat sources vs taxonomy.
3. Grade each claim DATA/JUDGMENT/COMPANY-CLAIM (guardrail vs marketing).
4. Durability tests (4 required): (a) could a well-funded entrant replicate it & how fast;
   (b) pricing power (above-inflation price rises w/o volume loss); (c) 5-10y margin &
   share stability (moat's financial fingerprint); (d) WHAT WOULD BREAK IT (explicit
   kill-case, prob + time-horizon).
5. Research rigor: prefer 10-Ks/competitor filings/antitrust & industry analyses/long-form
   3rd-party; distrust company IR (→COMPANY-CLAIM); citations required for DATA; instruct
   model to RESIST its priors (famous ≠ moated) and to state "no durable moat found" when
   honest (analog of "sound number is a valid outcome").

**Illustrative examples (worked into `moat-validation.md`):**
- **MCO (Moody's)** — Moat 79.5, plain-ROIC variant, ROIC 19.8% vs WACC 10.7% (+9pp),
  goodwill 74.5%, tpe/fpe 1.18 (<1.5, NOT acq-routed). Qual = WIDE (intangibles/
  regulatory NRSRO + efficient scale duopoly w/ S&P). Cell: CORROBORATED.
- **PANW (Palo Alto Networks)** — Moat 77.8, TANGIBLE_ROIC variant
  (`_acquisition_distorted` fired), full-capital roic_5y ~8.4% below WACC ~9.1% (would
  gate to ~35 on plain ROIC). Qual = Narrow/real-but-contestable. Cell: SCORE ARTIFACT —
  tangible-ROIC routing maxed magnitude and dodged the economic-profit gate (see
  [[moat-acquirer-tangible-roic-inflation]]).

**Key refs:** skill dir `.claude/skills/validating-agent-stock/` (SKILL.md,
moat-validation.md, risk-reward-validation.md, validate_ticker.py). Scorer
`backend/moat/scoring.py` (`score(m, profile)->(float|None, dict)`; constants
MOAT_GATE_CEIL 35, MOAT_MIN_YEARS 3, MOAT_MIN_PILLARS 3, FINANCIAL_COE_PCT 8.5,
B1_THIN_SPREAD_PP 2.0/CAP 15).
Related: [[moat-score-design]], [[moat-acquirer-tangible-roic-inflation]],
[[validating-skill-rr-extension]], [[app-serves-persisted-rows-not-live-compute]].
