---
name: validating-agent-stock
description: Use when the user questions, sanity-checks, or asks you to validate Agent Stock's fair value or quality score for a specific ticker ("is PLTR's FV right?", "why is X rated so low?", "does −63% look fair?", "cross-check this number"), or suspects the valuation/scoring pipeline unfairly mis-rated a company.
---

# Validating Agent Stock

## Overview

You are an expert financial analyst validating a result that Agent Stock — a two-pipeline Python app — produced for one ticker. **Your default deliverable is a verdict + evidence, not a code change.** Agent Stock has been through many tuning passes (see the memory dir); most numbers are sound. Confirm or fault the number honestly; only cross into fixing the engine when a *real* gap is proven and the user is in the loop.

**Core principle:** a fair value is a *range*, not a point. Agent Stock reports a single number; your job is to judge whether that number is a defensible center of a reasonable range, and if not, *why* — data problem, or logic problem.

## When to use

- User asks whether a ticker's FV or Quality score is right / fair / trustworthy.
- User says a company looks mis-rated (too cheap/expensive, quality too low/high).
- You suspect a classifier tier, method weight, guard, or cap distorted a result.

**When NOT to use:** building new features, screener work unrelated to a specific verdict, or generic finance questions with no Agent Stock result in play.

## Do these first (the RED gaps this skill exists to close)

1. **Read the relevant memory before analyzing.** `C:\Users\f_lub\.claude\projects\C--Users-f-lub-proj-Agent-Stock\memory\` (index: `MEMORY.md`). Many tickers and mechanisms are already documented — NBIS's real 684% growth, the size-coupled fade saga, winner-take-all `pick_ev_multiple`, split-aware history. Grep it for the ticker AND the mechanism. **Do not re-derive settled decisions or re-open a fix the memory already records.**
2. **Separate "the number the engine computes now" from "the number the app shows."** The grid/UI serves **persisted Google Sheets rows**; they can be stale (a code fix does *not* change what's shown until a recompute). Always recompute live before trusting or faulting a number. See [[app-serves-persisted-rows-not-live-compute]].
3. **Read the ticker-tagged code comments around whatever leg/cap/guard drives this ticker.** Agent Stock is in active optimization, and nearly every constant, cap, and guard carries an inline comment naming the ticker(s) it was tuned against and *why* (`grep` the driver in `valuation/{engine,models}.py`, `classifier.py`, `screener/{metrics,scoring}.py` — e.g. `# NVDA's peak-era median reads ~fairly valued at 25x but flips to undervalued at 30x`, `# TEM: +$635M net debt over -$185M EBITDA … scored 10/10`). These comments are the design intent: they tell you whether the behavior you're seeing is deliberate calibration or an unforeseen case. **Never propose changing a constant without first reading the comment that set it** — you will otherwise re-break a documented neighbor.

## Run one ticker (the harness — don't reinvent it)

`validate_ticker.py` (shipped beside this skill) runs BOTH pipelines live and dumps everything you need. It locates `backend/` itself and is read-only (no Sheets writes):

```
"C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" \
  ".claude/skills/validating-agent-stock/validate_ticker.py" PLTR --inputs
```

`--inputs` also dumps the raw `extract_financials` dict, cashflow, EV/EBITDA history, and quarterly revenue — the inputs you cross-check against. Use it every time; input-dumping is what turns hand-waving into evidence.

To test **logic on synthetic inputs** (no network), call the pure cores directly:
`valuation.engine.evaluate(fin)`, `valuation.classifier.classify(fin)`, `screener.scoring.score(metrics, sector)`.

## Codebase map

| Concern | Where | Entry point |
|---|---|---|
| Fair value — live | `backend/valuation/engine.py` | `run(ticker)` → `TickerResult` |
| Fair value — pure logic | `backend/valuation/engine.py` | `evaluate(fin)` (no IO) |
| Method math, caps, fade | `backend/valuation/models.py` | `build_scenarios`, `calc_*`, `_fade_hold_years`, `_ev_ebitda_ceiling` |
| Stock-type tiers + method weights | `backend/valuation/classifier.py` | `classify(fin)`, `_TYPE_WEIGHTS` |
| Quality — live | `backend/screener/engine.py` | `run(ticker)` → `ScreenerResult` |
| Quality — metrics / scoring | `backend/screener/{metrics,scoring}.py` | `compute_metrics`, `score` |
| Both pipelines + Sheets persist | `backend/orchestrator/batch.py` | `_run_one(ticker)` |
| Live recompute API | `backend/routers/analysis.py` | `POST /ticker/{t}/recalculate` |
| yfinance data layer | `backend/services/yahoo.py`, `yf_pool.py` | `extract_financials`, `fetch_*` |
| Tests | `backend/tests/` | `pytest` from `backend/` (`asyncio_mode=auto`) |

**FV tiers** (`classify`): FINANCIAL, ASSET_HEAVY, CONGLOMERATE, EARLY_GROWTH, GROWTH, DIVIDEND, CYCLICAL, then size default MEGA_CAP (>$1T) / LARGE_CAP (>$100B) / MID_CAP. Each has fixed method weights.

**Quality sections** (`section_scores`): **I** growth & margins, **II** capital efficiency (ROIC / ROIC−WACC / ROTE), **III** balance sheet & leverage, **IV** capital allocation. Weighted by sector profile (`PROFILES`).

## The validation recipe

1. **Memory + live recompute** (see "Do these first"). Read `score_breakdown` / `fair_value_breakdown`.
2. **Reconcile the composite.** Confirm `fair_value == Σ weight·leg_fv`. Note which legs survived — `pick_ev_multiple` is **winner-take-all** (ev_sales folds into ev_ebitda or vice-versa), and guards can zero a leg (EARLY_GROWTH DCF, pre-profit decline, capex reroute).
3. **Cross-check inputs vs logic.** Compare the dumped `fin` inputs to reality. Classic input traps: quarterly-YoY growth read as annual, statement-vs-`info` EBITDA basis (~2×), split-distorted history, sign-artifact ratios (negative denominators), stale TTM base.
4. **Localize the driver.** Which leg/cap/guard/tier moved the number? Call the leg function with the live `fin` to isolate it. Distinguish **data problem** (bad input) from **logic problem** (a cap/fade/tier that mis-fits this company).
5. **Verdict.** State it as a range: is the reported number a defensible center? Name the single biggest swing factor. **It is a valid, common outcome to conclude the number is sound** — say so plainly; don't manufacture a gap. **If — and only if — you propose a change, the verdict MUST carry a worked numeric example** (see below); a proposal without before→after numbers is not finished.

### The worked-example rule (required whenever a change is proposed)

Any proposed change — in the verdict, the levers section, or a brainstorm — must be pinned to concrete numbers, never described in the abstract. Show, in this shape:

- **What changes:** the exact input / metric / constant / cap / branch (name the symbol and file), its **current value → proposed value**.
- **Which outcome it targets and by how much:** FV and/or Quality Score, **before → after**, with direction and rough magnitude. State explicitly if one pipeline is unaffected (a fade/cap/weight change usually moves **FV only**; a metric/section change usually moves **Quality only** — they share almost no code).
- **Measure it, don't estimate it:** get the after-number by re-running the pure core on the live `fin` with the value swapped (a read-only probe: monkey-patch the constant, call `evaluate` / `score` again, diff). Guessing the magnitude is not acceptable.
- **Blast radius, quantified:** which other tickers move, in which direction, by roughly how much (see the cross-classification rule below).

Example (PLTR fade band): *change `_fade_hold_years` `$150B–$1T` branch from `FADE_HOLD_LARGE (3)` → `FADE_HOLD_MID (5)` for `revenue_growth > 0.40`; FV $48.42 → $52.42 (+8.3%, −63.4% → −60.4%); Quality unaffected (fade is FV-only); blast radius = only $150B–$1T names growing >40%, canaries unmoved.*

## When the user asserts a number is too high or too low

The most common ask is directional: *"PLTR's quality is too high"*, *"NBIS's FV is understated"*, *"why is this rated so low?"* Answer it in a fixed shape — never jump straight to "here's the fix":

1. **Explain why the current number was produced.** Trace it to the specific driver(s): which section/leg dominated, which cap or guard fired, which input fed it. Quote the tuning comment that set the constant. This is the bulk of the answer — the user is usually asking *why*, not *change it*.
2. **Judge whether the number is actually wrong** — a defensible verdict the user simply dislikes is *not* a gap. If the number is sound, **say so and recommend leaving it as is**, with the evidence. This is a valid, frequent, and correct outcome; do not manufacture a change to seem responsive.
3. **Only if it's genuinely off, lay out the levers** — separated by *kind*, because they have very different blast radii:
   - **Input levers** (change what feeds the method): fix a broken/stale/wrong-basis input (`info` vs statement, quarterly-vs-annual growth, split distortion, sign artifact). Lower blast radius — usually corrects one ticker.
   - **Logic levers** (change the method/cap/tier/weight itself): widen a cap, adjust a tier's method weights, move a fade band, change a guard threshold. **Higher blast radius** — name which *other* tickers the change moves, **including names in other classifications the same code path serves** (the memory and code comments tell you), and quantify the direction. A logic change that fixes this ticker by breaking a documented one — in *any* category — is not an option, it's a regression.
   For each lever, give the **worked-example** shape (current→proposed value, before→after FV and/or Quality, blast radius — see "The worked-example rule"). Recommend one, with reasoning — don't just enumerate.
4. Then, and only with the user's buy-in, cross into the TDD flow below.

## Only if a real gap is confirmed — then optimize

Cross this line **only** when step 4 proves a genuine logic/data gap, not a legitimate valuation the user simply dislikes.

1. **Establish green first:** `pytest` from `backend/` passes before you touch anything.
2. **Match the engagement to the fix's complexity — decide, don't default:**
   - **Complex / structural change** (new tier or guard, a cap's shape, method weights, anything with cross-classification reach or several viable designs): open a **brainstorming session** (`superpowers:brainstorming`) — surface the mechanism, the options, and the blast radius, and let the design emerge with the user.
   - **Simple / localized change** (a bounded input fix, a one-ticker threshold nudge, an obviously-correct data correction): **just ask in normal conversation** which approach the user prefers before editing — no full brainstorm needed. When unsure which bucket a change is in, treat it as complex.
3. **Blast radius is mandatory, and it is cross-classification.** Before proposing *any* change, evaluate its knock-on effect on *other* tickers — not only ones in the same tier, but names in **other** classifications the shared code path also touches (a cap in `models.py`, a guard in `engine.py`, a scoring helper in `scoring.py` runs for everything that reaches it). State which tickers move, in which direction, by roughly how much, and confirm the documented canaries and neighbors don't regress. A change whose blast radius you can't characterize is not ready to propose. Agent Stock's memory is full of fixes that over-corrected a neighbor in a *different* category.
4. **TDD the change** (`superpowers:test-driven-development`): failing test pinning the desired behavior → minimal engine change → full suite green → re-validate the ticker and the canaries (IREN, NBIS, KLAC are recurring regression canaries).
5. **When a fix lands, record it in memory** and note which constants were tuned against which inputs (re-tuning against a corrected input is a logged past mistake), and which other tickers the change was verified not to move.

## Common mistakes

- Faulting a **live** number when the user meant the **stale Sheets** value (or vice-versa) — clarify which.
- Reading a defensible "expensive/cheap" verdict as a bug. High multiples with a capped-growth model *should* read overvalued; that's the model working, not failing.
- Re-deriving analysis the memory dir already contains, or re-opening a settled tuning decision.
- Proposing an engine edit before proving the mechanism and looping in the user.
- Trusting `info['ebitda']` / quarterly growth without checking the statement basis.
