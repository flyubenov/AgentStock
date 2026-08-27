# Validating-Agent-Stock Skill — Moat Validation Extension — Design Spec

**Date:** 2026-08-27
**Branch:** `feat/validate-moat` (from `master` @ `88fcf48`, `master == origin/main`)
**Status:** Approved design; ready for implementation planning.

## 1. Objective

Extend the existing `validating-agent-stock` skill so it can validate a ticker's **Moat
Score** — the durability-of-economic-profit pillar shipped by the Moat Score work (merged +
pushed to `origin/main`; see `docs/superpowers/specs/2026-08-24-moat-score-design.md`).
Today the skill and its harness know three pipelines (Fair Value, Quality, Risk-Reward). This
adds Moat as a first-class, but **on-demand**, validation target.

The deliverable is documentation + a small read-only harness change, **not** any change to
the Moat scorer (`backend/moat/scoring.py`), which is done. Known scorer traps (the
acquirer tangible-ROIC inflation — see the memory note `moat-acquirer-tangible-roic-inflation`)
are *documented as traps*, not fixed here; fixing one would be a separate, validation-driven
task this extended skill would then drive.

## 2. What makes Moat different (the framing that drives the design)

The three existing validators judge a *number* against a reference: FV against market/DCF
reality, Quality against fundamentals, R-R's internal correctness against its own config. For
Moat, the object being validated is **not the number** — it is the real-world claim *"does
this company have a durable economic moat, and what is its source?"** The pipeline's Moat
Score is a backward-looking financial fingerprint of *realized* economic profit; it can
**suggest** a moat but cannot prove one, cannot see a moat's *source*, cannot see an
un-monetized moat, and can be faked by a cyclical peak or an accounting routing. So the
priority order **inverts** relative to the R-R extension:

1. **Qualitative moat analysis (PRIMARY).** From internet research, determine whether a real
   moat exists, name its **source(s)** against an exhaustive taxonomy, grade the evidence, and
   test durability. This sets the verdict.
2. **Quantitative reconciliation (corroboration).** Recompute the Moat Score *from the
   breakdown the pipeline already emitted* to confirm it is internally sound and to understand
   what drove it (which variant, which pillars, gated or not). The number is a **witness**,
   never the verdict.
3. **Divergence read (the payoff).** Cross the qualitative verdict against the number; each
   quadrant has a distinct meaning and a required action (§6.5).

Two cross-cutting facts the skill must state, because they change how a validator reasons:

- **The Moat Score rides the Screener pipeline** (same `sc_run`, zero extra yfinance I/O) and
  is **numeric only, 0–100, with no Wide/Narrow bands**. The verbal bands in *this analyst
  artifact* are a separate thing from the engine, which deliberately avoids bands for the
  number.
- **Quality ≠ Moat.** Both come off the screener. Quality is broad business fundamentals;
  Moat is narrowly durability-of-economic-profit. A cross-reference keeps the two from being
  conflated.

## 3. Trigger and flow (on-demand + light cross-reference)

- The skill's **triggers expand** so it *fires* on moat questions — either flavor:
  qualitative-led ("does MCO have a real moat / what is it?") or quant-led ("why is PANW's
  moat 77.8?").
- The **full moat recipe** (reading `moat-validation.md`, doing the qualitative research
  first, then reconciling the number) runs **only when the question is about the moat**.
  FV / Quality / R-R questions are answered as they are today — the agent does not run the
  moat recipe unprompted.
- **Light cross-reference:** because the harness now always dumps the Moat block cheaply (§4),
  a Quality answer *may* add a **one-line** moat cross-reference (score + one-word read) when
  relevant — especially when it contrasts with the Quality verdict. This is a sanity flag,
  never a full moat validation, and it is explicitly *not* the same axis as Quality.

## 4. Harness change — `validate_ticker.py`

The harness (`.claude/skills/validating-agent-stock/validate_ticker.py`) already runs
`fv_run` + `sc_run` + `rr_run` via `asyncio.gather` and dumps FV + QUALITY + RISK_REWARD
(+ raw inputs under `--inputs`). It stays a **read-only** live probe. The Moat data already
rides the `sc` result (`ScreenerResult.moat_score` / `.moat_breakdown` / `.metrics` —
`screener/models.py:105-116`), so **no new pipeline call is added**. Changes:

- Emit a new top-level **`MOAT`** block, always present, sourced from the existing `sc`
  result:
  - `moat_score` and the full **`moat_breakdown`** — `variant` (`ROIC` / `TANGIBLE_ROIC` /
    `FINANCIAL_ROTE`), `pillars` (earned per A1/A2/B1/B2/B3/C1), `maxima`, `earned`,
    `available`, `gated`, `excluded`.
  - The **moat-relevant slice of `sc.metrics`**, so every pillar is cross-checkable without a
    second fetch: `roic_series`, `roic_5y_avg`, `roic_series_ex_goodwill`,
    `roic_5y_ex_goodwill`, `rote_series`, `rote_5y_avg`, `wacc`, `roic_wacc_spread`,
    `goodwill_intangible_share`, `gross_margin_series`, `op_margin_series`,
    `gross_margin_trajectory`, `op_margin_trajectory`, `fcf`, `ebitda`, `sector`.
- **No `--inputs` change is required** — the moat inputs are the screener metrics, already
  fully present in the block above. (The qualitative half needs **no** harness data at all;
  its inputs are the web.)
- Cost: **zero extra live calls** — the screener already ran. The block is a projection of
  data the harness already holds.

The harness docstring gets one line noting the MOAT block; the "ALL THREE pipelines" wording
stays (Moat is not a fourth pipeline, it rides the screener).

## 5. `SKILL.md` spine edits (kept lean)

Only short, cross-cutting changes go in `SKILL.md`; the depth lives in the new reference
(§6). Specifically:

- **Frontmatter `description`:** add moat triggers so the skill fires on moat questions —
  "validate/sanity-check a ticker's fair value, quality score, risk-reward, **or moat score /
  whether a company has a real economic moat**."
- **Overview:** name Moat alongside FV / Quality / R-R, with the one-line framing that Moat
  validation is **qualitative-primary** (the inversion) — the number corroborates.
- **Core principle companion line:** the object validated is the *real-world moat claim*, not
  the number; "no durable moat found" is a valid, expected outcome (analog of "a sound number
  is a valid outcome").
- **"When to use":** add the moat triggers; keep "When NOT to use" intact.
- **Routing bullet:** "**Moat** (is the moat real / what is its source / why is the score what
  it is) → read `moat-validation.md`, run the harness, do the qualitative analysis **first**,
  then reconcile the number."
- **Codebase map:** add Moat rows — `moat/scoring.py` `score(m, profile)`, the moat metric
  series on `ScreenerMetrics`, and that the Moat Score rides `screener/engine.py` `run`.
- **Quality↔Moat cross-ref:** a one-line note in the Quality section — "Quality ≠ Moat; for
  durability-of-economic-profit see `moat-validation.md`."
- **Harness section:** note it now dumps the `MOAT` block.

The FV / Quality / R-R reasoning in `SKILL.md` is otherwise unchanged.

## 6. New reference — `moat-validation.md`

A self-contained companion, read only when the question is about the moat. Sections:

### 6.1 What the Moat Score is / what "validate" means
Durability of *realized* economic profit — a 40/50/10 model (Magnitude A1+A2 / Durability
B1+B2+B3 / Cash C1) over series the screener already carries; numeric 0–100, no bands. Restate
the inversion: it is a **witness, not the verdict**; the qualitative "is there a real moat and
what is its source" is the thing being validated; the number can only corroborate or diverge.

### 6.2 Run the harness
`python validate_ticker.py TICKER`; read the `MOAT` block. No `--inputs` needed for moat.

### 6.3 Qualitative analysis (PRIMARY) — runs BEFORE looking at the number
The five-step method:
1. **Frame the business** from the web (not marketing) — what it sells, to whom, how it earns.
2. **Enumerate ALL candidate moat sources** against the exhaustive taxonomy: **Network
   effects · Intangible assets** (brands / patents / licenses / regulatory IP) **· Switching
   costs · Cost advantage · Efficient scale · Regulatory-legal · Other/emergent**. The
   Other/emergent bucket is real but carries a **higher** evidentiary bar — name the concrete
   mechanism, never use it as a catch-all.
3. **Grade each claim** — `DATA` (verifiable + web citation) / `JUDGMENT` (analyst inference)
   / `COMPANY-CLAIM` (self-serving IR/marketing — DISCOUNTED, never counted as moat evidence).
4. **Durability tests (4 required):** (a) could a well-funded entrant replicate it, and how
   fast; (b) pricing power — above-inflation price rises without volume loss; (c) 5–10y margin
   & share stability (the moat's financial fingerprint); (d) **what would break it** — an
   explicit kill-case with probability and time-horizon.
5. **Research rigor:** prefer 10-Ks / competitor filings / antitrust & industry analyses /
   long-form third-party; distrust company IR (→ COMPANY-CLAIM); citations required for DATA;
   **resist priors** (famous ≠ moated) and state "no durable moat found" when that's honest.

**Set the verdict band here** (before the number):
- **Wide** — ≥1 source graded DATA, all 4 durability tests pass, replication >5–10y or
  structurally blocked, pricing power shown.
- **Narrow** — a real but contestable source (replicable in a few years, or partial pricing
  power, or only one durability test fully passes).
- **None** — no source survives grading, or the kill-case is live/near-term. "Sounds strong"
  without evidence lands here.

### 6.4 Quantitative reconciliation (corroboration)
Recompute-from-breakdown (do **not** re-fetch or re-derive from raw statements — that only
reproduces upstream flaws):
1. **Recompute the headline:** `moat = 100 × earned / available` (`available` = Σ maxima, the
   renormalized denominator — not a fixed 100). Confirm it matches `moat_score`.
2. **Two structural overrides:** the **economic-profit gate** (`level ≤ hurdle` → cap at
   **35**, `gated: true`) and the **coverage floor** (`series_len < 3` MOAT_MIN_YEARS OR
   `pillars < 3` MOAT_MIN_PILLARS OR `available ≤ 0` → `moat_score = None`; a **blank is not a
   low score** — say which of the three tripped).
3. **Confirm the variant** (`ROIC` / `TANGIBLE_ROIC` / `FINANCIAL_ROTE`) — the #1 source of a
   misleading number; it decides what "return" and "hurdle" mean.
4. **Per-pillar checks** (input sane · band maps right · right signal):

   | Pillar | Max | Recompute | Trap |
   |--------|-----|-----------|------|
   | A1 level | 20 | `score_high(level, A1_ROIC_BANDS)` | ex-goodwill inflation; 1y vs 5y basis |
   | A2 spread | 20 | `score_high(0.5·spot+0.5·five, A2_SPREAD_BANDS)`, missing leg drops+renorms | WACC/beta quality; ex-goodwill spread |
   | B1 persistence | 25 | `25 × persistence_fraction(series, hurdle)`, then thin-spread cap: spread < 2.0pp → cap 15 | "clears by a hair every year" faking a wide moat |
   | B2 consistency | 10 | `score_low(coef_of_variation(series), B2_COV_BANDS)` | cyclical smoothing; too-short series |
   | B3 margin durability | 15 | mean(gross-stdev, op-stdev, trajectory)·15/10 | **excluded if financial**; stability not level |
   | C1 FCF conversion | 10 | `score_high(fcf/ebitda, C1_FCF_BANDS)` | **excluded if financial or heavy-capex**; needs ebitda>0 |

5. **State what the number measures** — durability of *realized* economic profit; blind to
   source, blind to un-monetized moats, fakeable by cyclical peaks / accounting routing.

### 6.5 The divergence matrix (the payoff)
Cross qualitative verdict × number; name the quadrant explicitly, and on any off-diagonal name
the concrete mechanism (which variant / pillar / durability test):

| | Number HIGH (≳50, ungated) | Number LOW / GATED / BLANK |
|---|---|---|
| **Qual = real moat** | **CORROBORATED** — profit confirms the source; report both + horizon. | **EMERGING or DISTORTED** — moat real but not yet in the financials (reinvestment/early-growth) *or* an accounting distortion (goodwill, heavy capex, gate/coverage). Say which. |
| **Qual = no moat** | **SCORE ARTIFACT** — the dangerous cell. Suspect (i) TANGIBLE_ROIC inflation on a serial acquirer, (ii) cyclical peak in the 5y window, (iii) thin-spread persistence dodging the B1 cap. Trust the qual; name the mechanism. | **AGREEMENT** — both say no moat; verify the low number isn't a *data* problem masking a real graded source. |

### 6.6 Write the verdict
Structured header — `Moat: None/Narrow/Wide · Source(s) · Trend Widening/Stable/Eroding ·
Durability horizon` — set from the graded qualitative work; **Source(s)** named concretely
(the mechanism, not just the taxonomy label). Then: graded evidence prose, the reconciliation,
the divergence-matrix cell, and the honest horizon + kill-case. Include the instruction that
"no durable moat found" is a valid, expected outcome.

### 6.7 Worked examples
- **MCO (corroborated):** qual Wide (intangible/regulatory NRSRO incumbency + efficient-scale
  duopoly with S&P), number ≈ 79.5, `variant: ROIC` (tpe/fpe 1.18 < 1.5 → *not*
  acquisition-routed despite 74.5% goodwill), ROIC ~19.8% vs WACC ~10.7% (+9pp), ungated →
  CORROBORATED.
- **PANW (score artifact):** qual real-but-contestable (likely Narrow), number ≈ 77.8,
  `variant: TANGIBLE_ROIC` (`_acquisition_distorted` fired), full-capital `roic_5y` ~8.4% <
  WACC ~9.1% (would gate to ~35 on plain ROIC), gate bypassed by ex-goodwill routing →
  SCORE ARTIFACT; name the mechanism.

## 7. Verification (skill self-test)

No backend engine change, so `pytest` is unaffected; the harness is a read-only probe.
Verification is:

- Run the extended `validate_ticker.py` live on MCO and PANW and confirm the `MOAT` block is
  correct: `100 × earned / available` matches `moat_score`, the `variant` / `gated` /
  `excluded` fields are right, and the pillar series are present.
- **Self-test pass criterion:** an analyst following `moat-validation.md`, given only the
  ticker, reaches **MCO → Wide / CORROBORATED** and **PANW → Narrow-or-None / SCORE ARTIFACT
  with the tangible-ROIC mechanism cited**. If PANW reads as "Wide, 77.8, corroborated," the
  doc has failed and needs a sharper variant-check step.
- Confirm an FV-only / Quality-only / R-R-only question still reads and behaves exactly as
  before, with at most the optional one-line moat cross-reference.

## 8. Non-goals

- **Not** a screener/batch mode — per-ticker only; hidden-gems is a byproduct, never a focus.
- **Not** changing the Moat scorer, its constants, or any FV / Quality / R-R behavior.
- **Not** fixing the acquirer tangible-ROIC inflation (documented as a trap only; PANW is the
  standing counter-example).
- **Not** always-on four-way validation — Moat deep-validates on demand.
- **Note (deliberate contrast with the R-R extension):** the qualitative half **does** use
  external web research — it is the primary input. This is the one place the validating skill
  reaches outside the harness, and it is bounded to the moat-source analysis.
