# Moat Validation Extension — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the `validating-agent-stock` skill so it can validate a ticker's Moat Score — a qualitative-primary "is the moat real and what is its source" analysis, corroborated by the pipeline's number.

**Architecture:** Docs + one read-only harness projection. No backend engine change. The harness (`validate_ticker.py`) already runs the screener pipeline (`sc_run`), which computes the Moat Score; we project the already-present `sc.moat_score` / `sc.moat_breakdown` / `sc.metrics` into a new `MOAT` block (zero extra live calls). A new reference doc `moat-validation.md` carries the qualitative method + quant reconciliation + divergence matrix; `SKILL.md` gets lean trigger/routing edits. The qualitative half uses web research (the one place this skill reaches outside the harness).

**Tech Stack:** Python 3 (harness, stdlib only — `asyncio`/`json`), Markdown (skill docs). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-27-moat-validation-design.md`

## Global Constraints

- **No backend engine change.** `backend/moat/scoring.py` and all pipeline code are untouched; `pytest` is unaffected and is not part of this plan's verification.
- **Harness stays read-only.** `validate_ticker.py` only reads existing engine outputs; it writes nothing and touches no Sheets. No new `asyncio.gather` pipeline call — the Moat data already rides the `sc` result.
- **Per-ticker only.** No screener/batch mode. Hidden-gems is a byproduct, never a focus.
- **Qualitative is PRIMARY; the number corroborates.** The verdict band is set from graded web evidence before the number is read; the number can only agree or diverge, never promote/demote the band. "No durable moat found" is a valid, expected outcome.
- **Verbatim constants** (from `backend/moat/scoring.py`, quote exactly): `MOAT_GATE_CEIL = 35.0`, `MOAT_MIN_YEARS = 3`, `MOAT_MIN_PILLARS = 3`, `FINANCIAL_COE_PCT = 8.5`, `B1_THIN_SPREAD_PP = 2.0`, `B1_THIN_SPREAD_CAP = 15.0`. Pillar maxima: A1 20 / A2 20 / B1 25 / B2 10 / B3 15 / C1 10. Headline: `moat = 100 * earned / available` where `available = Σ maxima` (renormalized, not fixed 100).
- **Branch:** `feat/validate-moat` (already checked out, from `master` @ `88fcf48`).

---

### Task 1: Harness MOAT block

Project the Moat data already on the `sc` (ScreenerResult) into a new top-level `MOAT` block. Verified on `screener/engine.py:24,31` — `metrics=metrics.model_dump()`, `moat_score`, and `moat_breakdown` are set on both return paths, so this is a pure projection with zero extra live calls.

**Files:**
- Modify: `.claude/skills/validating-agent-stock/validate_ticker.py` (the `main` function, ~line 72-94, and add a module-level field list near `_RR_INFO_FIELDS`, ~line 45)

**Interfaces:**
- Consumes: `sc.moat_score: float | None`, `sc.moat_breakdown: dict` (keys `variant`/`pillars`/`maxima`/`earned`/`available`/`gated`/`excluded`), `sc.metrics: dict` (full `ScreenerMetrics.model_dump()`) — all already produced by `sc_run` in the existing `asyncio.gather`.
- Produces: a top-level `MOAT` key in the harness JSON, consumed by `moat-validation.md` (Task 2) and the self-test (Task 4).

- [ ] **Step 1: Add the moat metric-field allowlist**

After the `_RR_INFO_FIELDS` list (ends ~line 54), add:

```python
# The moat-relevant slice of ScreenerMetrics (sc.metrics), dumped in the MOAT
# block so every moat pillar is cross-checkable without a second fetch. Series
# are latest-first; percents/pp per ScreenerMetrics. See moat-validation.md.
_MOAT_METRIC_FIELDS = [
    # A1/A2/B1/B2 return axis + spread
    "roic_series", "roic_5y_avg", "roic_ttm", "wacc", "roic_wacc_spread",
    "roic_series_ex_goodwill", "roic_5y_ex_goodwill", "goodwill_intangible_share",
    "rote_series", "rote_5y_avg", "rote",
    # B3 margin durability
    "gross_margin_series", "op_margin_series",
    "gross_margin_trajectory", "op_margin_trajectory",
    # C1 cash backing
    "fcf", "ebitda",
    "sector",
]
```

- [ ] **Step 2: Emit the MOAT block in `main`**

In `main`, insert a `"MOAT"` entry into the `out` dict between `"QUALITY"` and `"RISK_REWARD"` (Moat rides the screener, so it sits with Quality). The `out` dict currently is:

```python
    out = {
        "FV": fv.model_dump(),
        "QUALITY": {
            "quality_score": sc.quality_score,
            "sector": sc.sector,
            "sector_profile": sc.sector_profile,
            "section_scores": sc.section_scores,
            "score_breakdown": sc.score_breakdown,
            "status": sc.status,
            "errors": sc.errors,
        },
        # Third pipeline. The full result: ratio, tier, reward_score, risk_score,
        # actionable_insight, per-slot metric_scores (raw/source/score/weight/dropped),
        # raw_snapshot, status, errors. See risk-reward-validation.md for the recipe.
        "RISK_REWARD": rr.model_dump(),
    }
```

Add, immediately after the `"QUALITY"` block's closing `},`:

```python
        # Moat Score — durability of realized economic profit (rides the screener;
        # no extra fetch). moat_breakdown carries variant/pillars/maxima/earned/
        # available/gated/excluded; the metrics slice makes every pillar checkable.
        # Qualitative-primary: the number corroborates. See moat-validation.md.
        "MOAT": {
            "moat_score": sc.moat_score,
            "moat_breakdown": sc.moat_breakdown,
            "metrics": {k: sc.metrics.get(k) for k in _MOAT_METRIC_FIELDS},
        },
```

- [ ] **Step 3: Update the harness docstring**

In the module docstring (top of file), the sentence listing what's dumped ("the full FV breakdown … the Quality sections, and the Risk-Reward breakdown") — add Moat. Change:

```
the full FV breakdown (per-leg weight + scenarios), the Quality sections, and the
Risk-Reward breakdown (ratio/tier/reward/risk + per-metric scoring).
```

to:

```
the full FV breakdown (per-leg weight + scenarios), the Quality sections, the Moat
block (score + breakdown + pillar metrics; rides the screener, no extra fetch), and
the Risk-Reward breakdown (ratio/tier/reward/risk + per-metric scoring).
```

- [ ] **Step 4: Run the harness live and verify the MOAT block reconciles**

Run (from repo root):

```bash
python ".claude/skills/validating-agent-stock/validate_ticker.py" MCO
```

Expected: the JSON contains a top-level `MOAT` block with a non-null `moat_score` (≈ 79.5), `moat_breakdown.variant == "ROIC"`, `moat_breakdown.gated == false`, and a `metrics` sub-dict with populated `roic_series` / `roic_5y_avg` / `wacc`. Confirm by hand from the dump that `round(100 * moat_breakdown.earned / moat_breakdown.available, 1) == moat_score` (the headline reconciles). If `moat_score` is null, read which of the three coverage-floor conditions tripped — that is itself a valid outcome, but MCO should score.

- [ ] **Step 5: Commit**

```bash
git add ".claude/skills/validating-agent-stock/validate_ticker.py"
git commit -m "feat(validate): dump MOAT block in validate_ticker harness"
```

---

### Task 2: The `moat-validation.md` reference doc

The self-contained companion, read only when the question is about the moat. Mirrors the structure and depth of the existing `risk-reward-validation.md`, but inverts the priority order (qualitative primary, number as witness).

**Files:**
- Create: `.claude/skills/validating-agent-stock/moat-validation.md`

**Interfaces:**
- Consumes: the `MOAT` block from Task 1 (`moat_score`, `moat_breakdown.{variant,pillars,maxima,earned,available,gated,excluded}`, `metrics.{roic_series,...}`).
- Produces: the recipe the self-test (Task 4) dry-runs; referenced by `SKILL.md` (Task 3).

- [ ] **Step 1: Write the reference doc**

Create `.claude/skills/validating-agent-stock/moat-validation.md` with exactly this content:

```markdown
# Validating a Moat Score

Moat is Agent Stock's durability-of-economic-profit score — a 40/50/10 model
(`backend/moat/scoring.py`) over series the **screener** already carries (it rides
`screener/engine.py`'s `run`, no extra fetch). Magnitude 40 (A1 ROIC/ROTE level 20 +
A2 economic-spread blend 20) / Durability 50 (B1 persistence 25 + B2 consistency 10 +
B3 margin durability 15) / Cash-backing 10 (C1 FCF/EBITDA). It is **numeric only, 0–100,
with no Wide/Narrow bands** — the verbal bands in *this analyst artifact* are a separate
thing from the engine, which deliberately avoids bands for the number.

**What "validate a moat" means — and why it inverts the other three validators.** For
Fair Value, Quality, and Risk-Reward, the object validated is the *number*. For Moat, the
object validated is the real-world claim: **does this company have a durable economic moat,
and what is its source?** The Moat Score is a backward-looking financial fingerprint of
*realized* economic profit — it can **suggest** a moat but cannot prove one, cannot see a
moat's *source*, cannot see an un-monetized moat, and can be faked by a cyclical peak or an
accounting routing. So the priority order flips:

1. **Qualitative moat analysis (PRIMARY).** From internet research, decide whether a real
   moat exists, name its source(s) against an exhaustive taxonomy, grade the evidence, and
   test durability. This sets the verdict band.
2. **Quantitative reconciliation (corroboration).** Recompute the score *from the breakdown
   the harness already dumped* to confirm it is internally sound and understand what drove it.
   The number is a **witness, never the verdict.**
3. **Divergence read (the payoff).** Cross the qualitative verdict against the number.

Two facts govern every moat validation:

- **Moat rides the screener** — same `sc_run`, zero extra I/O; a moat question does not add a
  pipeline. Its inputs are the `ScreenerMetrics` series (`roic_series`, `rote_series`, margin
  series, `wacc`, `fcf`/`ebitda`).
- **Quality ≠ Moat.** Both come off the screener. Quality is broad business fundamentals; Moat
  is narrowly durability-of-economic-profit. Do not conflate them or read one from the other.

## Run the harness

```
python ".claude/skills/validating-agent-stock/validate_ticker.py" <TICKER>
```

Read the top-level `MOAT` block: `moat_score`, `moat_breakdown`
(`variant` / `pillars` / `maxima` / `earned` / `available` / `gated` / `excluded`), and the
`metrics` slice (`roic_series`, `roic_5y_avg`, `wacc`, `roic_wacc_spread`,
`roic_series_ex_goodwill`, `roic_5y_ex_goodwill`, `goodwill_intangible_share`, `rote_series`,
`rote_5y_avg`, margin series + trajectories, `fcf`, `ebitda`). No `--inputs` flag is needed
for moat — the moat inputs *are* the screener metrics, already in the block. **The qualitative
half needs no harness data at all — its inputs are the web.**

## The qualitative analysis (PRIMARY) — do this BEFORE looking at the number

Five steps. Run them from research, not from the score, so the number cannot anchor you.

1. **Frame the business** from the web (not the company's own marketing) — what it sells, to
   whom, and how it actually earns money.
2. **Enumerate ALL candidate moat sources** against this **exhaustive taxonomy**:
   - **Network effects** — value rises with users on the same/other side (marketplaces,
     exchanges, standards).
   - **Intangible assets** — brands, patents, licenses, regulatory approvals/designations,
     proprietary data, IP.
   - **Switching costs** — cost/risk/effort of leaving (integration, workflow lock-in,
     retraining, data gravity, certification).
   - **Cost advantage** — durably lower unit cost (process, location, scale economies,
     privileged input access).
   - **Efficient scale** — a market profitably served by one/few incumbents; new entry
     destroys the economics for everyone.
   - **Regulatory / legal** — statutory monopoly, license scarcity, mandated standard,
     government-granted exclusivity.
   - **Other / emergent** — a real, durable advantage that fits none of the above. This bucket
     is legitimate but carries a **higher evidentiary bar**: name the concrete mechanism and
     why it is durable; never use it as a catch-all for "seems strong."
3. **Grade each claimed source:**
   - `DATA` — verifiable, with a web citation (a filing, a regulator, a third-party analysis).
   - `JUDGMENT` — a defensible analyst inference not directly cited.
   - `COMPANY-CLAIM` — self-serving IR / marketing language. **Discounted — never counted as
     moat evidence on its own.**
   A source only supports the verdict on `DATA`, or on strong, explicitly-reasoned `JUDGMENT`.
4. **Durability tests (all four required):**
   a. **Replication** — could a well-funded, competent entrant reproduce this, and how fast?
      >5–10 years or structurally blocked ⇒ strong; a few years ⇒ contestable.
   b. **Pricing power** — has the company raised prices above inflation without losing volume?
   c. **Financial fingerprint** — are margins and market share stable/rising over 5–10 years?
      (This is where the number becomes relevant, but only as corroboration.)
   d. **Kill-case** — what would break this moat? Name the concrete threat (substitute tech,
      regulation, a platform shift, a deep-pocketed entrant), its probability, and its
      time-horizon. A moat with a live near-term kill-case is not durable.
5. **Research rigor.** Prefer 10-Ks, competitor filings, antitrust/industry analyses, and
   long-form third-party research; distrust company IR (→ `COMPANY-CLAIM`); require citations
   for `DATA`. **Resist your priors** — a famous company is not automatically moated, and an
   obscure one may hold a real moat. State "no durable moat found" plainly when that is the
   honest read; it is a valid, expected outcome, not a failure of the analysis.

**Set the verdict band here, from the graded evidence, before reading the number:**

- **Wide** — at least one source graded `DATA`, all four durability tests pass, replication is
  >5–10 years or structurally blocked, and pricing power is demonstrated.
- **Narrow** — a real but contestable source: replicable in a few years, or pricing power is
  partial, or only one durability test fully passes. Source may be `DATA` or strong `JUDGMENT`.
- **None** — no source survives grading (all `COMPANY-CLAIM` / no durability), or a source
  exists but the kill-case is live/near-term. "Sounds strong" without evidence lands here.

## Quantitative reconciliation (corroboration only)

Recompute the score **from the `moat_breakdown` the harness already dumped** — do *not*
re-fetch or re-derive ROIC/WACC from raw statements; that only reproduces any upstream flaw
instead of catching it (this mirrors how `risk-reward-validation.md` recomputes from
`metric_scores`, not from raw feeds).

1. **Recompute the headline.** `moat = 100 * earned / available`, where `earned = Σ pillars`
   and `available = Σ maxima` (the renormalized denominator — **not** a fixed 100; excluded
   pillars are removed from it). Confirm it matches `moat_score` (rounded to 1 dp).

2. **Check the two structural overrides.**
   - **Economic-profit gate:** if `level ≤ hurdle`, the score is capped at **35.0**
     (`MOAT_GATE_CEIL`) and `moat_breakdown.gated == true`. A gated score is the engine saying
     "no durable excess return" — it should line up with a None/Narrow qualitative verdict; a
     Wide-qual + gated number is a flagged divergence.
   - **Coverage floor → None:** the score is `None` when the return series has fewer than
     `MOAT_MIN_YEARS = 3` observations, OR fewer than `MOAT_MIN_PILLARS = 3` pillars scored, OR
     `available ≤ 0`. A **blank is not a low score** — say which of the three tripped.

3. **Confirm the variant** (`moat_breakdown.variant`) — the #1 source of a misleading number.
   It decides what "return" and "hurdle" mean:
   - `ROIC` — plain, full-capital ROIC vs WACC.
   - `TANGIBLE_ROIC` — `_acquisition_distorted` fired: level is **ex-goodwill** ROIC, which
     *maxes magnitude AND bypasses the economic-profit gate on full-capital ROIC*. This is the
     acquirer trap (see memory `moat-acquirer-tangible-roic-inflation`). Verify the ex-goodwill
     routing is warranted, not merely inflating a serial acquirer whose full-capital ROIC sits
     below WACC.
   - `FINANCIAL_ROTE` — level is ROTE, hurdle is fixed **8.5%** (`FINANCIAL_COE_PCT`); B3 and
     C1 are excluded (see `moat_breakdown.excluded`).

4. **Per-pillar checks** (for each: is the input sane · does the band map right · is it the
   right signal). Recompute against `moat_breakdown.pillars` + the `metrics` slice:

   | Pillar | Max | Recompute | Trap to check |
   |---|---|---|---|
   | **A1** level | 20 | `score_high(level, A1_ROIC_BANDS)` | ex-goodwill inflation; single-year vs 5y-avg basis |
   | **A2** spread | 20 | `score_high(0.5·spot + 0.5·five, A2_SPREAD_BANDS)`; a missing leg drops and renormalizes | WACC/beta quality; ex-goodwill spread |
   | **B1** persistence | 25 | `25 · persistence_fraction(series, hurdle)`, then **thin-spread cap**: if blended spread `< 2.0`pp (`B1_THIN_SPREAD_PP`) → cap at `15.0` (`B1_THIN_SPREAD_CAP`) | a name clearing its hurdle "by a hair every year" masquerading as a wide moat |
   | **B2** consistency | 10 | `score_low(coef_of_variation(series), B2_COV_BANDS)` | cyclical smoothing; too-short series |
   | **B3** margin durability | 15 | mean(gross-stdev, op-stdev, trajectory comps) · 15/10 | **excluded if financial**; measures stability, not level |
   | **C1** FCF conversion | 10 | `score_high(fcf/ebitda, C1_FCF_BANDS)` | **excluded if financial or heavy-capex**; needs `ebitda > 0` |

   To recompute a band by hand on synthetic inputs (no network), the pure scorer is callable:
   `from moat.scoring import score` and `from screener.scoring import score_high, score_low`;
   the band tables (`A1_ROIC_BANDS`, `A2_SPREAD_BANDS`, `B2_COV_BANDS`, `C1_FCF_BANDS`, …) live
   in `moat/scoring.py`.

5. **State what the number measures.** The Moat Score is *durability of realized economic
   profit* — backward-looking. It cannot see a moat's *source*, cannot see an un-monetized
   moat, and can be faked by a cyclical peak or an accounting routing. That is exactly why the
   qualitative half leads.

## The divergence matrix (the payoff)

Cross the qualitative verdict against the number. Name the quadrant explicitly, and on any
off-diagonal case name the concrete mechanism (which variant / pillar / durability test) —
never "the numbers disagree, moving on."

| | Number HIGH (≳50, ungated) | Number LOW / GATED / BLANK |
|---|---|---|
| **Qual = real moat** (Wide/Narrow) | **CORROBORATED** — the strongest outcome. Realized economic profit confirms the source you identified. Report both; note the durability horizon. *(MCO.)* | **EMERGING or DISTORTED** — the moat is real but not yet in the financials (early-growth, reinvestment suppressing FCF/ROIC), *or* an accounting distortion (goodwill, heavy capex, gate/coverage). Say which. This is where an un-materialized moat legitimately shows up — but the bar is the graded `DATA` source, not the low number. |
| **Qual = no moat** (None) | **SCORE ARTIFACT** — the dangerous quadrant. High number, no durable source ⇒ suspect (i) `TANGIBLE_ROIC` inflation on a serial acquirer, (ii) a cyclical peak in the 5y window, (iii) thin-spread persistence that dodged the B1 cap. Trust the qualitative read; name the mechanism. *(PANW.)* | **AGREEMENT** — both say no moat. Fast and clean. Verify the low number is not a *data* problem masking a real graded source (if it is, this is really the EMERGING/DISTORTED cell). |

## Write the verdict

Lead with the structured header, set from the graded qualitative work:

```
Moat: None / Narrow / Wide · Source(s) · Trend Widening/Stable/Eroding · Durability horizon
```

- **Source(s)** named **concretely** — the mechanism, not just the taxonomy label
  (e.g. "Intangible/regulatory: NRSRO designation + issuer-pays ratings incumbency," not just
  "Intangible").
- **Trend** from durability test (c) plus any structural shift found in research.
- **Horizon** — the honest estimate of how many years the moat holds before the kill-case
  bites. A Wide moat with a 3-year horizon is a real and important finding.

Then: the graded evidence prose (every claim tagged `DATA` / `JUDGMENT` / `COMPANY-CLAIM`), the
quant reconciliation, the divergence-matrix cell you landed in, and the kill-case. **"No
durable moat found" is a valid, expected verdict** — state it plainly when honest; do not
manufacture a moat to seem responsive, and do not let a high number talk you into one.

## Worked examples

- **MCO (Moody's) — corroborated.** Qualitative: **Wide** · Intangible/regulatory (NRSRO
  designation, issuer-pays incumbency) + efficient-scale duopoly with S&P · Stable · long
  horizon. Harness: `moat_score ≈ 79.5`, `variant: ROIC` (trailing/forward P/E ≈ 1.18 < 1.5 ⇒
  **not** acquisition-routed, despite ~74.5% goodwill), ROIC ~19.8% vs WACC ~10.7% (+9pp),
  `gated: false`. Divergence cell: **CORROBORATED** (real moat + high number). The trap avoided:
  the ~74.5% goodwill does *not* trigger `TANGIBLE_ROIC` here, so don't expect the ex-goodwill
  variant.
- **PANW (Palo Alto Networks) — score artifact.** Qualitative: a real but contestable
  platform/switching-cost moat ⇒ likely **Narrow**, not Wide. Harness: `moat_score ≈ 77.8`,
  `variant: TANGIBLE_ROIC` (`_acquisition_distorted` fired — serial acquirer), full-capital
  `roic_5y` ~8.4% *below* WACC ~9.1% (would gate to ~35 on plain ROIC), gate bypassed by the
  ex-goodwill routing. Divergence cell: **SCORE ARTIFACT** — name the mechanism: tangible-ROIC
  routing maxed magnitude and dodged the economic-profit gate (memory
  `moat-acquirer-tangible-roic-inflation`). The number is high; trust the qualitative Narrow.

## Proposing a moat change (rare — the scorer is done)

The Moat Score is shipped and calibrated. A moat *validation* almost always ends at a verdict,
not a code change. If reconciliation does surface a genuine scorer gap (e.g. the acquirer
tangible-ROIC inflation), it is a separate, validation-driven task under the main `SKILL.md`
optimize discipline — measure the blast radius across the DB tickers first (the tangible-ROIC
gate change touches ADBE/CDNS/SNPS/AMD, not just PANW), reuse an existing pattern before
inventing one, TDD it, and record it in memory. Do **not** quick-edit `moat/scoring.py` from a
single-ticker finding.
```

- [ ] **Step 2: Verify the doc renders and cross-links resolve**

Confirm the file exists and its internal references are correct:

```bash
grep -n "moat_breakdown\|TANGIBLE_ROIC\|MOAT_GATE_CEIL\|moat-acquirer-tangible-roic-inflation" ".claude/skills/validating-agent-stock/moat-validation.md"
```

Expected: matches for the breakdown keys, the variant name, the constant, and the memory cross-reference — confirming the doc names the same symbols the harness dumps and the scorer uses.

- [ ] **Step 3: Commit**

```bash
git add ".claude/skills/validating-agent-stock/moat-validation.md"
git commit -m "docs(validate): add moat-validation reference doc"
```

---

### Task 3: `SKILL.md` wiring

Lean, cross-cutting edits so the skill fires on moat questions and routes to the new doc only when the question is about the moat. Mirrors the R-R extension's wiring pattern.

**Files:**
- Modify: `.claude/skills/validating-agent-stock/SKILL.md` (frontmatter description; Overview; Core principle; When to use; the harness routing section; Codebase map)

**Interfaces:**
- Consumes: `moat-validation.md` (Task 2), the `MOAT` block (Task 1).
- Produces: nothing downstream — this is the final wiring.

- [ ] **Step 1: Extend the frontmatter `description` to fire on moat questions**

Replace the `description:` line (line 3) — append the moat trigger clause to the existing string:

Current ending: `...or the newly added Risk-Reward (R-R) ratio ("is X's R-R right?", "why is this a Value Trap?", "does this R-R look fair?").`

Change to end with: `...or the newly added Risk-Reward (R-R) ratio ("is X's R-R right?", "why is this a Value Trap?", "does this R-R look fair?"), or the Moat score / whether a company has a real economic moat ("does X have a real moat?", "what is X's moat?", "why is X's moat score so high/low?").`

- [ ] **Step 2: Name Moat in the Overview**

In the Overview (line 10), the app is described as "a three-pipeline Python app (Fair Value, Quality Score, Risk-Reward)". Moat rides the screener, so it is not a fourth pipeline — add it as a rider. Change that parenthetical to:

`a three-pipeline Python app (Fair Value, Quality Score, Risk-Reward) plus a Moat score that rides the Quality/Screener pipeline`

- [ ] **Step 3: Add a Moat companion line to the Core principle**

After the Core-principle paragraph (ends line 12, "...not its distance from a market price."), append one sentence:

`Moat is different again, and inverted: validating a moat is **qualitative-primary** — the real question is *whether a durable economic moat exists and what its source is*, answered from research; the pipeline's numeric Moat score only **corroborates** it (it can suggest a moat but cannot prove one). "No durable moat found" is a valid, expected verdict.`

- [ ] **Step 4: Add the Moat trigger to "When to use"**

After the R-R bullet (line 19, "User asks whether a ticker's Risk-Reward ratio or tier..."), add:

`- User asks whether a ticker has a real economic moat, what its source is, or why its Moat score is what it is.`

- [ ] **Step 5: Add the Moat routing pointer to the harness section**

After the R-R routing paragraph (ends line 41, "...it does not run the full R-R recipe unprompted."), add a parallel Moat paragraph:

`**Validating a Moat score — or "does this company have a real moat"? Read `moat-validation.md`** (in this skill dir). It carries the qualitative-primary method (frame the business from research → enumerate sources against an exhaustive taxonomy → grade DATA/JUDGMENT/COMPANY-CLAIM → four durability tests), the quant reconciliation (recompute from the harness `MOAT` block; the gate, coverage floor, and three variants), and the divergence matrix. The harness now always dumps a `MOAT` block (score + breakdown + pillar metrics; it rides the screener, so **no extra fetch**). Run that recipe **only when the question is about the moat.** A Quality validation may add a **one-line** moat cross-reference (score + one-word read) when relevant — Quality ≠ Moat, so never read one from the other.`

- [ ] **Step 6: Add Moat rows to the Codebase map**

In the Codebase-map table, after the Quality rows (after `Quality — metrics / scoring` row, ~line 55), add:

```
| Moat — score (rides screener) | `backend/moat/scoring.py` | `score(metrics, profile)` → `(float│None, breakdown)` |
| Moat — pillar inputs | `backend/screener/models.py` | `ScreenerMetrics` moat series (roic/rote/margin series, wacc) |
```

Then, after the "Quality sections" explanatory line (line 69), add one line:

`**Moat** rides the screener (same `sc_run`, no extra I/O) and is **numeric only, 0–100, no bands** — pure durability of realized economic profit (Magnitude 40 / Durability 50 / Cash 10 + an economic-profit gate). Quality ≠ Moat: broad fundamentals vs narrow durability-of-excess-return.`

- [ ] **Step 7: Verify the edits are consistent and commit**

Confirm the six edits landed and nothing references a wrong filename:

```bash
grep -n "moat-validation.md\|Moat\|MOAT" ".claude/skills/validating-agent-stock/SKILL.md"
```

Expected: the description trigger, Overview rider, Core-principle line, When-to-use bullet, the routing pointer to `moat-validation.md`, and the two codebase-map rows all present.

```bash
git add ".claude/skills/validating-agent-stock/SKILL.md"
git commit -m "docs(validate): wire Moat validation into SKILL.md (triggers, routing, map)"
```

---

### Task 4: Skill self-test (acceptance gate)

Dry-run the full recipe end-to-end against the two known cases, validating Tasks 1–3 together. This is the design's acceptance check; both tickers are read-only.

**Files:**
- None modified. This is a verification task. (Any doc gap it surfaces is fixed back in Task 2/3 and re-committed.)

**Interfaces:**
- Consumes: the harness `MOAT` block (Task 1), `moat-validation.md` (Task 2), `SKILL.md` routing (Task 3).
- Produces: the go/no-go signal for the whole extension.

- [ ] **Step 1: Run the harness on both cases**

```bash
python ".claude/skills/validating-agent-stock/validate_ticker.py" MCO
python ".claude/skills/validating-agent-stock/validate_ticker.py" PANW
```

Confirm each prints a `MOAT` block whose headline reconciles (`round(100*earned/available,1) == moat_score`).

- [ ] **Step 2: Dry-run the reconciliation on MCO (corroboration case)**

Following `moat-validation.md` §"Quantitative reconciliation", confirm from the MCO dump:
`moat_score ≈ 79.5`, `variant == "ROIC"`, `gated == false`, ROIC level clears WACC by a wide margin. Expected qualitative band (from research): **Wide** (intangible/regulatory + efficient-scale duopoly). Expected divergence cell: **CORROBORATED**. Pass = the analyst is *not* misled by the ~74.5% goodwill into expecting `TANGIBLE_ROIC`.

- [ ] **Step 3: Dry-run the reconciliation on PANW (score-artifact case)**

Following the same recipe, confirm from the PANW dump: `moat_score ≈ 77.8`, `variant == "TANGIBLE_ROIC"` (`_acquisition_distorted` fired), and that full-capital ROIC would sit below WACC (the ex-goodwill routing bypassed the gate). Expected qualitative band: **Narrow** (real but contestable). Expected divergence cell: **SCORE ARTIFACT**, with the tangible-ROIC mechanism cited.

- [ ] **Step 4: Confirm the acceptance criterion**

**Pass:** an analyst following `moat-validation.md`, given only the ticker, reaches
**MCO → Wide / CORROBORATED** and **PANW → Narrow(-or-None) / SCORE ARTIFACT with the
tangible-ROIC mechanism named**. **Fail** (needs a sharper variant-check step in Task 2): PANW
reads as "Wide, 77.8, corroborated." If the variant on either ticker differs materially from
the expected (`ROIC` for MCO, `TANGIBLE_ROIC` for PANW) — live data drift since the design —
note the actual variant and adjust the worked example in `moat-validation.md` to match, then
re-commit Task 2.

- [ ] **Step 5: Confirm the other validators are unaffected**

Run one FV/Quality/R-R validation and confirm it reads exactly as before, with at most the optional one-line moat cross-reference:

```bash
python ".claude/skills/validating-agent-stock/validate_ticker.py" NBIS --inputs
```

Expected: FV / QUALITY / RISK_REWARD blocks unchanged in shape; the new MOAT block is additive. No routing change fires for a non-moat question.

- [ ] **Step 6: Record the completed extension in memory**

Update `.claude/memory/moat-validation-skill-extension.md`: mark the design **DONE + IMPLEMENTED** on `feat/validate-moat`, note the three commits (harness / reference doc / SKILL.md) and the self-test result (MCO corroborated, PANW artifact), and update the `MEMORY.md` index line. Then commit the memory files (per the standing instruction, they were held uncommitted "until the design's done" — it now is):

```bash
git add ".claude/memory/moat-validation-skill-extension.md" ".claude/memory/MEMORY.md"
git commit -m "docs(memory): mark moat-validation skill extension done"
```
```
