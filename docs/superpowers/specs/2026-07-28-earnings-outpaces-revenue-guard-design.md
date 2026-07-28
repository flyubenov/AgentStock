# Growth-source guard: earnings outpacing revenue (acquisition consolidation)

**Date:** 2026-07-28
**Status:** Approved design, ready for implementation plan
**Scope:** Fair Value pipeline only — a new growth-source guard in `build_scenarios`,
`backend/valuation/engine.py`. No Quality Score change; no change to any per-leg
valuation model; no new fetch, no new tunable constant.

## Problem

`build_scenarios` derives the realistic growth rate that the DCF, EV/EBITDA and DDM
legs compound over the horizon. Its `else`-branch trusts `fin["earnings_growth"]` —
yfinance `info['earningsGrowth']`, a single-quarter YoY figure — as the primary source:

```python
else:
    raw = (fin.get("earnings_growth") or fin.get("revenue_growth")
           or fin.get("revenue_growth_stmt") or 0.07)
base = max(0.02, min(float(raw), cap))   # cap ~= 0.20
```

When a company closes a large acquisition, the acquired revenue and earnings consolidate
into the trailing quarter, so the quarterly YoY **earnings** growth prints far above the
organic rate — but it is a one-time step change in the size of the business, not a rate
the business will compound for a decade. The cap (~0.20) hides most of the damage, but
whenever the true organic rate is **below** the cap, the guard-less path pins growth at
the full 0.20 instead of the real ~10–13%, and every horizon leg over-compounds.

**CRM (Salesforce), post-Informatica:** `earnings_growth` 0.522 vs `revenue_growth`
0.133. The else-branch caps 0.522 → 0.20 and projects a decade of 20% growth off a
top line growing 13%. Live FV **$497.78 / +204%** — the "enormously undervalued /
suspicious" read that triggered this validation.

The three existing growth-source guards do not cover this shape:

- `_earnings_distorted` — fires only when earnings growth is **negative** (eg < 0).
- `_earnings_non_operating` — needs a **statement** operating-income reading that is
  flat/declining; CRM's operating line is genuinely growing, so it does not fire.
- `_earnings_inflated` — needs `forward_pe/trailing_pe > 1.5` **and** `feps < teps`
  (a one-time trailing gain the market prices below forward). CRM's earnings are real
  and recurring — forward EPS is above trailing — so it does not fire.

## Goal

Detect the "quarterly earnings growth runs far ahead of revenue growth" signature and
re-source the realistic growth rate from **revenue**, exactly as `_earnings_distorted`
and `_earnings_inflated` already do — bounded by `distorted_cap`, one-way (only ever
lowers the projected rate), reusing the constants already defined for the mirror-image
case in `_forward_target_pe`. No new fetch, no new knob.

## Design

### New guard — `_earnings_outpaces_revenue(fin)`

Added to `backend/valuation/engine.py` alongside the other three guards:

```python
def _earnings_outpaces_revenue(fin: dict) -> bool:
    """GAAP earnings growth runs far ahead of revenue growth — the signature of a
    just-consolidated acquisition, where acquired revenue/earnings land in the trailing
    quarter and inflate the quarterly-YoY earnings figure into a one-time step change,
    not a rate the business compounds. Growth is re-sourced from revenue, like
    _earnings_distorted / _earnings_inflated.

    The exact mirror of models._forward_target_pe's divergence re-sourcing: THERE revenue
    outpaces earnings 3x (a tiny noisy quarterly earnings print on a fast grower, HOOD) and
    the PEG target sources growth from revenue; HERE earnings outpace revenue 3x and the
    realistic leg sources growth from revenue. Both operands are the quarterly-YoY info
    figures, so the comparison is like-with-like, and both reused thresholds
    (GROWTH_TRUST_FLOOR, GROWTH_REVENUE_RATIO) carry over unchanged — no second knob.

    The revenue floor (>= GROWTH_TRUST_FLOOR) is what keeps this off flat-revenue recovery
    names, whose earnings spike is a depressed-base effect, not consolidation on a growing
    business: HON (rev 4.3%), MMM (2.5%), UNH (0.4%) all fail the floor and keep the normal
    path. The guard also self-limits above the cap: when revenue growth already exceeds the
    ~0.20 growth cap (DDOG, PLTR, GOOGL, MU), sourcing from capped-revenue equals sourcing
    from capped-earnings, so firing changes nothing. It bites only in the 0.10 <= rev < ~0.20
    band — a healthy double-digit grower whose quarterly earnings run 3x+ its revenue."""
    eg = fin.get("earnings_growth")
    rg = fin.get("revenue_growth")
    return (eg is not None and eg > 0
            and rg is not None and rg >= m.GROWTH_TRUST_FLOOR
            and eg > rg * m.GROWTH_REVENUE_RATIO)
```

### Placement in `build_scenarios`

Added as the **4th `elif`**, after all three existing guards, so existing precedence is
untouched:

```python
if _earnings_distorted(fin):
    raw = min(fin.get("revenue_growth") or 0, distorted_cap)
elif _earnings_non_operating(fin):
    raw = fin["op_income_growth_stmt"]
elif _earnings_inflated(fin):
    raw = min(fin.get("revenue_growth") or 0, distorted_cap)
elif _earnings_outpaces_revenue(fin):                       # NEW
    raw = min(fin.get("revenue_growth") or 0, distorted_cap)
else:
    raw = (fin.get("earnings_growth") or fin.get("revenue_growth")
           or fin.get("revenue_growth_stmt") or 0.07)
```

Placing it **last** means:

- `_earnings_inflated` still wins for LYFT (one-time deferred-tax release), keeping that
  fix intact — LYFT never reaches the new guard.
- The `_earnings_non_operating` operating-line signal still wins when a statement reading
  is present.

The sourcing expression is byte-identical to `_earnings_distorted` / `_earnings_inflated`
(`min(revenue_growth, distorted_cap)`), so the DDM path (which passes
`distorted_cap = SUSTAINABLE_CEIL`) stays bounded exactly as those guards already are.

The optimistic leg is unaffected by construction: `_band_growth_signal` keys off
`revenue_growth_stmt`/`revenue_growth`, never `earnings_growth`, so no change is needed
there. The P/E leg (`_forward_target_pe`) is a separate call and is likewise untouched —
this guard lives entirely inside `build_scenarios`.

### Constants — reused, none added

Both thresholds already exist in `backend/valuation/models.py` for the mirror-image
`_forward_target_pe` case:

- `GROWTH_TRUST_FLOOR = 0.10`
- `GROWTH_REVENUE_RATIO = 3.0`

## Fingerprint (why it fires on exactly the right shape)

The guard moves a valuation only when **all** hold:

1. `earnings_growth` present and `> 0`,
2. `revenue_growth` present and `>= 0.10` (floor),
3. `earnings_growth > revenue_growth * 3.0`.

The two-sided band is the whole point:

- **Lower bound (floor 0.10):** excludes flat-revenue *recovery* names (HON/MMM/UNH),
  whose earnings jump is a depressed-base artifact, not consolidation on a growing top
  line. Sourcing those from ~0% revenue would wrongly crush them to the 0.02 floor.
- **Upper bound (emergent from the ~0.20 cap):** genuine hyper-growers (DDOG, PLTR, MU,
  GOOGL) have revenue growth above the cap, so revenue-sourced == earnings-sourced ==
  cap. The guard is inert for them.

So it bites precisely on healthy-but-mature double-digit growers whose quarterly earnings
run 3×+ their revenue — the acquisition-consolidation signature.

## Measured blast radius

Measured by monkey-patching the guard as a real `elif` inside `build_scenarios` (so only
the scenario legs are perturbed, exactly as the real change will be — the P/E leg is left
untouched) and diffing live FV across a representative basket:

| Ticker | Baseline FV | With guard | Δ | Reads |
|--------|------------:|-----------:|----:|-------|
| **CRM** | $497.78 (+204%) | $342.36 (+109%) | **−31.2%** | Informatica consolidation |
| **CSCO** | $84.12 | $61.45 | **−27.0%** | Splunk consolidation |
| DDOG, GOOGL, PLTR, MU | — | — | 0.0% | self-limiting (rev ≥ cap) |
| HON, MMM, UNH | — | — | 0.0% | floor excludes (rev < 0.10) |
| LYFT | — | — | 0.0% | `_earnings_inflated` wins (precedence) |
| KLAC, NBIS, IREN, AAPL, NVDA, ANET, V | — | — | 0.0% | byte-identical |

Exactly **two** names move — both recent large acquirers — and both move *down* (reading
less undervalued / more overvalued), which is the correct direction. CSCO is an accepted
correct second catch: the guard treats Splunk consolidation identically to CRM's
Informatica, on the divergence signal itself, not on any acquisition-specific input.

## Tests (for the implementation plan / TDD phase)

Pure-guard unit tests on synthetic `fin` dicts + `build_scenarios`/`evaluate`:

1. **fires + re-sources** — CRM-shape (eg 0.52, rev 0.13): guard `True`; realistic growth
   sourced from revenue, not the capped 0.52.
2. **floor excludes** — HON-shape (eg 2.6, rev 0.04): guard `False`; normal path.
3. **self-limiting inert** — DDOG-shape (eg 1.04, rev 0.32): `evaluate` FV byte-identical
   with and without the guard.
4. **precedence** — LYFT-shape (`_earnings_inflated` conditions met): `_earnings_inflated`
   wins; the new guard is never reached.
5. **canary** — KLAC-shape (eg ≈ rev): guard `False`; unchanged.

Plus the full `pytest` suite green, and a live re-validation of CRM/CSCO (move as
measured) and canaries IREN/NBIS/KLAC (byte-identical).

## Non-goals / explicitly out of scope

- No change to the growth **cap** itself (still ~0.20 / GROWTH_CAP_CEIL path).
- No new fetch and no dependence on the screener's goodwill signal — the rejected
  alternative added +1 fetch/ticker or broke pipeline isolation, raising freeze risk on
  batch runs; this design uses only fields already present in `fin`.
- No new tunable constant.
- The residual CRM overshoot after the guard (+109%) is not a target of this change; the
  guard corrects the growth-source artifact only.
