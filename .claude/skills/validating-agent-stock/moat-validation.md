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
