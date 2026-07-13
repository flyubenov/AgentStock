# IREN-class fixes: screener op-margin data quality + valuation capex reroute

**Date:** 2026-07-12
**Branch:** `iren-opmargin-capex-reroute` (off `master`)
**Status:** Design approved; ready for implementation plan.

## Problem

Running **IREN** (IREN Limited — bitcoin miner / AI data-centre operator) through Stock Agent
produced a **Quality Score of 4.0** and **no Fair Value**. Investigation showed both outputs are
distorted by the same root cause: the screener and the valuation trust yfinance `info` fields that
are **broken for IREN**, while the actual financial statements are correct.

IREN's real numbers (FY2025 income statement, ended 2025-06-30):

| Signal | yfinance `info` field | Actual statement |
|---|---|---|
| Operating margin | `operatingMargins` = **−64.5%** | Operating Income +$22.1M / Rev $501M = **+4.4%** |
| Revenue growth | `revenueGrowth` = **−0.0%** | 501/187 − 1 = **+167.7% YoY** |
| EBITDA | `ebitda` = $147M | statement EBITDA = **$286M** (~2× — the known NFLX-class mismatch) |

Other signals are all positive and consistent: gross margin 68%, net income +$87–158M,
EPS +$0.77, operating cash flow +$246M. IREN is **operationally profitable and hyper-growing**;
its FCF is deeply negative (−$1.13B, −149% of revenue) **only** because capex ($1.37B) vastly
exceeds operating cash flow — a data-centre build-out, i.e. investing, not burning.

### Why 4.0 (screener)

The screener profile is correctly **BALANCED** (the FINANCIALS→BALANCED nudge fires), so IREN is
*not* mis-scored as a bank. The 4.0 is driven down by the bogus `operatingMargins = −64.5%`, which
does double damage:

1. Zeroes the Section I operating-margin sub-score.
2. Trips the `operating_loss` gate (`scoring.py`), routing IREN through the pre-profit
   Rule-of-40 blend. Rule of 40 = growth (broken 0%) + margin (broken −64.5%) = **−64.5** →
   blends the ~4.07 fundamentals composite down to 4.0.

Section II (capital efficiency) is a legitimate **0.75** — ROIC(ttm) ≈ 3.5%, 5y-avg ROIC ≈ −11%
(real 2022–23 losses), ROIC−WACC spread ≈ −8pp, ROTE ≈ 4.8%. IREN only just crossed into
profitability and still earns below its ~11.5% cost of capital, so a low capital-efficiency score
is *correct* and is not touched by this work.

### Why no FV (valuation)

IREN classifies as **MID_CAP** (crypto-miner keyword override de-financializes it; "Capital
Markets" is not a core-financial industry). MID_CAP is DCF-anchored. Its real trailing FCF is
−149% of revenue, far below the `FCF_MARGIN_FLOOR` (−25%), so the **pre-profit guard** declines
it (`engine.py`). The guard's refusal to run a trailing-FCF DCF is defensible — but IREN is
GAAP-profitable with positive EBITDA, so the engine's existing **capex-distortion reroute** (onto
EV/EBITDA + P/E, built for AMZN-style capex-eaten FCF) *should* apply. It doesn't, only because
that reroute is gated to `fcf_ttm >= 0` and IREN's capex pushed FCF past zero.

## Goals

- Screener: stop a single broken `info` field from unilaterally tanking the score and misrouting a
  profitable company into the pre-profit branch. → IREN **4.0 → 4.7**.
- Valuation: let a GAAP-profitable, cash-generative name with capex-driven negative FCF receive an
  EV/EBITDA + P/E fair value instead of a decline, and make that number trustworthy (not
  understated by the same broken growth field). → IREN **no FV → ~$15 (−63% vs $41)**.

## Non-goals

- Not changing Section II capital-efficiency scoring — IREN's 0.75 there is correct.
- Not making IREN look "cheap." The correct output is *valued and expensive* (~−63%), a
  disciplined "priced far above fundamentals" signal for a momentum stock.
- Not globally switching valuation growth to statements — only supplying a statement fallback for
  the specific broken-field case.

## Guiding principle

**Prefer the financial statement; fall back to `info`.** This is the pattern the codebase already
uses for FCF (`real_fcf`) and for the EV/EBITDA base (the NFLX statement-consistent-base fix). Both
fixes extend that same principle to operating margin and revenue growth.

---

## Fix #1 — Screener op-margin data quality

Files: `backend/screener/metrics.py`, `backend/screener/scoring.py`, `backend/screener/models.py`.

### 1a. Operating margin: statement-primary, info fallback

In `compute_metrics` (`metrics.py`), replace:

```python
m.op_margin = pct(info.get("operatingMargins"))
```

with a statement-first computation using the income statement (which is already loaded and already
used two lines below for `op_margin_trajectory`):

```python
oi = inc.latest("Operating Income") if inc is not None else None
stmt_rev = inc.latest("Total Revenue") if inc is not None else None
if oi is not None and stmt_rev:
    m.op_margin = oi / stmt_rev * 100.0
else:
    m.op_margin = pct(info.get("operatingMargins"))
```

- Uses the statement's own revenue as the denominator (consistent basis with the numerator).
- IREN: −64.5% → **+4.4%**.

### 1b. Rule-of-40 growth: statement YoY primary

Add a statement-derived year-over-year revenue growth metric and prefer it in the Rule of 40.

**`models.py`** — add one field to `ScreenerMetrics` in the "raw inputs" block (near
`revenue_growth`):

```python
revenue_growth_yoy: float | None = None   # statement latest-FY vs prior-FY (percent)
```

**`metrics.py`** — compute it from the income statement revenue series (most-recent-first):

```python
rev_series = inc.series("Total Revenue")
if len(rev_series) >= 2 and rev_series[0] is not None and rev_series[1]:
    m.revenue_growth_yoy = (rev_series[0] / rev_series[1] - 1) * 100.0
```

**`scoring.py` `_rule_of_40`** — change the growth source line from:

```python
g = m.revenue_growth if m.revenue_growth is not None else m.revenue_cagr_3y
```

to a statement-first chain (explicit `is not None` checks so a legitimate 0% is respected):

```python
if m.revenue_growth_yoy is not None:
    g = m.revenue_growth_yoy
elif m.revenue_growth is not None:
    g = m.revenue_growth
else:
    g = m.revenue_cagr_3y
```

- IREN: broken 0% → **+167.7%** (then capped at `RULE_OF_40_GROWTH_CAP` = 100).
- Note: with 1a fixed, IREN no longer enters the operating-loss branch at all, so this term is not
  used *for IREN* — it hardens the Rule of 40 for other genuinely operating-loss names whose `info`
  growth is broken.

### Fix #1 result (verified against live IREN data)

- op_margin: −64.5% → **+4.4%**; statement YoY: **+167.7%**.
- **Quality Score 4.0 → 4.7.** Section I 6.0 → 8.25; pre-profit branch no longer applied.
- Side effect (intended): the correct positive op-margin now lets `_heavy_capex_distortion` fire,
  so IREN's capex-eaten FCF metrics (FCF margin/CAGR, OCF/CapEx, Net Debt/FCF) are excluded as
  deliberate reinvestment rather than scored as weakness — the same treatment AMZN already gets.
- Section II stays **0.75** (unchanged, correct).

### Fix #1 conflict check

The recently merged `b28d0bb` (dynamic goodwill floor) touches only the
`_acquisition_distorted` / goodwill-floor region of `scoring.py` — disjoint from `_rule_of_40` and
from `metrics.py` op-margin. No overlap.

---

## Fix #2 — Valuation capex reroute for profitable negative-FCF names

Files: `backend/valuation/engine.py`, `backend/services/yahoo.py`.

### 2a. Reroute gate (EBITDA > 0 AND OCF > 0)

In `evaluate` (`engine.py`), the pre-profit guard currently declines any DCF-anchored name with
`fcf_ttm / revenue_ttm < FCF_MARGIN_FLOOR`. Before declining, check whether the name is a
cash-generative capex investor and, if so, reroute instead of declining:

```python
ocf_ttm = fin.get("ocf_ttm")
if ocf_ttm is None:
    ocf_ttm = fin.get("operating_cashflow")   # info fallback
ebitda_ttm = fin.get("ebitda_ttm") or 0

if (weights.get("dcf", 0) > 0 and fcf_ttm is not None and revenue_ttm
        and fcf_ttm / revenue_ttm < FCF_MARGIN_FLOOR):
    if ebitda_ttm > 0 and ocf_ttm is not None and ocf_ttm > 0:
        # Capex-distorted, negative-FCF variant: operations generate cash (OCF > 0) and
        # EBITDA is valuable, so deeply negative FCF is a capex/investment choice, not a
        # burn. Value on EV/EBITDA + P/E, but lean harder on the multiple than the
        # positive-FCF case does (0.85/0.15, not 0.70/0.30) — see rationale below.
        weights = {mid: 0.0 for mid in m.ALL_METHODS}
        weights["ev_ebitda"], weights["pe"] = 0.85, 0.15
    else:
        return { ... existing PRE_PROFIT decline ... }
```

- **Rationale for the gate** (from brainstorming): `FCF = OCF − capex`, so `OCF > 0` is the one
  condition that actually distinguishes *investing* (operations self-fund; capex exceeds them)
  from *burning* (operations consume cash). `EBITDA > 0` is required for EV/EBITDA to be
  computable. EPS is deliberately **not** in the gate — it is accrual (IREN's net income is
  inflated by non-cash bitcoin fair-value gains) and would wrongly exclude legitimate
  heavy-depreciation investors; the P/E leg self-drops when EPS ≤ 0 anyway.
- **Weights (0.85 / 0.15), *not* the positive-FCF reroute's 0.70 / 0.30.** The gate excludes EPS
  precisely because deeply-negative-FCF names in this branch tend to carry accrual-distorted
  earnings (IREN's net income is inflated by non-cash bitcoin fair-value gains). It would be
  inconsistent to distrust net income for *eligibility* and then trust it for 30% of the *value*,
  so the P/E leg is cut to 0.15 and EV/EBITDA carries 0.85. (The positive-FCF reroute keeps
  0.70/0.30 — clean-earnings AMZN-style names — and is left unchanged.)
- The existing positive-FCF reroute block below stays unchanged.
- IREN: EBITDA +$147M, OCF +$246M → reroute.

### 2b. Growth source — statement fallback (required for a trustworthy number)

Without this, `build_scenarios` falls to its 7% default (because `info.revenueGrowth` is the broken
−0.0), the EV/EBITDA leg projects EBITDA at 7%/yr, and the FV is understated (~$9). The fix:

**`services/yahoo.py`** — extend `_fetch_ev_ebitda_history_sync` (which already loads the income
statement) to also return statement revenue YoY, and thread it through
`fetch_ev_ebitda_history`. The returned dict gains one key:

```python
# after building `rows` / computing `median`:
rev_growth = _statement_revenue_yoy(ist)   # latest-FY / prior-FY - 1 from "Total Revenue"
return {"multiple": median, "ebitda": latest_statement_ebitda(rows),
        "revenue_growth": rev_growth}
```

`_statement_revenue_yoy` reads the two most-recent `Total Revenue` columns from the income
statement (`ist`), returning `None` if unavailable. (This lives beside the existing
`latest_statement_ebitda` helper and is unit-testable in isolation.)

**`engine.py` `run`** — plumb it into `fin` (next to the existing `ev_ebitda_hist` plumbing):

```python
if hist is not None:
    fin["ev_ebitda_hist"] = hist["multiple"]
    fin["ev_ebitda_hist_base"] = hist["ebitda"]
    if hist.get("revenue_growth") is not None:
        fin["revenue_growth_stmt"] = hist["revenue_growth"]
```

**`engine.py` `build_scenarios`** — add the statement growth to the fallback chain, *after* the
info fields and *before* the 7% default, so it only ever fires when the info fields are
missing/zero (the broken-field case). Change:

```python
raw = fin.get("earnings_growth") or fin.get("revenue_growth") or 0.07
```

to:

```python
raw = (fin.get("earnings_growth") or fin.get("revenue_growth")
       or fin.get("revenue_growth_stmt") or 0.07)
```

- `or` chaining is intentional: `revenue_growth = −0.0` and `earnings_growth = None` are both
  falsy → statement growth is used. A name with a valid nonzero info growth is unaffected (minimal
  blast radius).
- The engine's existing `min(raw, 0.20)` cap still applies, so IREN's +168% becomes 20%.
- EBITDA base is already the statement figure via the existing `ev_ebitda_hist_base` (NFLX fix).

### Fix #2 result (verified against live IREN data)

- Reroute fires (EBITDA +$147M > 0, OCF +$246M > 0).
- Growth from statement fallback → scenarios {opt 0.20, real 0.20, pess 0.16} (capped).
- EV/EBITDA leg ≈ **$15.4** (statement EBITDA base $286M, hist multiple 16.8, no compression),
  P/E leg ≈ **$14.6** (trailing EPS $0.77 × capped 21× × 0.9 MOS).
- **Composite FV ≈ $15 (−63% vs $41.14 price)** at 0.85/0.15 (0.85·15.4 + 0.15·14.6 ≈ 15.3) —
  was: no FV / declined. The weight shift barely moves the number here (the two legs nearly
  coincide); it matters for names where BTC-inflated EPS pushes the P/E leg far above the multiple.

### Fix #2 conflict check

Last valuation change on `master` was `e20810d` (statement-consistent EV/EBITDA base) — this design
*relies on* it (the hist base). `31b3d97` added the positive-FCF reroute this extends. Both current
in HEAD; edits are additive and do not modify their logic.

## Known limitations (accepted)

- `revenue_growth_stmt` rides on the EV/EBITDA history reconstruction, so a name where that returns
  `None` (recent split, or fewer than 3 positive-EBITDA years) will not get the growth fallback.
  Acceptable: the reroute itself needs EBITDA history, and normal names have valid `info` growth.
- IREN still lands ~−63%, and that is correct — the fixes make it *valued*, not *cheap*.

## Testing

Unit / behavior tests to add (TDD, alongside existing `test_screener_*` and `test_engine*`):

**Fix #1**
- `op_margin` sourced from statement Operating Income / Total Revenue when the statement is present;
  falls back to `info["operatingMargins"]` when absent.
- `revenue_growth_yoy` computed from the two most-recent statement revenue points; `None` with < 2
  points.
- `_rule_of_40` prefers `revenue_growth_yoy`, then `revenue_growth`, then `revenue_cagr_3y`.
- End-to-end IREN-shaped fixture: bogus `operatingMargins`/`revenueGrowth` + healthy statement →
  score ~4.7, no pre-profit branch, `_heavy_capex_distortion` fires.
- Regression: a normal profitable name with no statement (info-only) still scores as before.

**Fix #2**
- `_statement_revenue_yoy` returns latest/prior − 1; `None` when insufficient.
- Reroute fires for deeply-negative-FCF + EBITDA>0 + OCF>0 → weights ev_ebitda 0.85 / pe 0.15, FV
  produced.
- Still declines when OCF ≤ 0 (genuine burn) or EBITDA ≤ 0.
- `build_scenarios` uses `revenue_growth_stmt` only when info growth fields are falsy; unaffected
  when info growth is valid.
- End-to-end IREN-shaped fixture → completed status, FV ≈ $15, stock_type MID_CAP.
- Regression: an existing PRE_PROFIT decline case with OCF ≤ 0 still declines.

Full `pytest` (`backend/`) must stay green.
