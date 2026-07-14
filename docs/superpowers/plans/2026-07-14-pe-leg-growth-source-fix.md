# TDD Task: Fix the P/E-leg growth source when yfinance `earningsGrowth` is unreliable

**Date:** 2026-07-14
**Scope:** `backend/valuation/models.py` — `_forward_target_pe()` only. One variable (`g`).
**Motivating case:** HOOD FV came out at **$19.47** vs a $109.86 price; the P/E leg was
crushed to **$10.01** by a target multiple of **5.4×** built on a bogus 2.7%
`earningsGrowth` field, while HOOD grows revenue ~49%/yr at 47% operating margins.

Related: [[iren-opmargin-capex-reroute]] (same class — a broken yfinance `info` field
mis-driving a downstream number), [[avgo-forward-eps-pe]] (the *EPS-base* half of this
leg, which we are NOT touching).

---

## 1. Problem

`calc_pe(forward=True)` (used by GROWTH / LARGE_CAP / MID_CAP) is:

```
FV = EPS × target_P/E × 0.90(MOS)
```

`target_P/E` comes from `_forward_target_pe()`:

```python
g = fin["earnings_growth"]          # yfinance info['earningsGrowth']
if g is None or g <= 0:
    g = fin["revenue_growth"] or 0  # fallback ONLY when g is None or ≤ 0
if g <= 0:
    return None
return min(forward_pe, g * 100 * PEG_CEILING)   # PEG_CEILING = 2.0
```

The fallback to revenue growth only fires when `earnings_growth <= 0`. When yfinance
returns a **small-but-positive** noise value (HOOD: `earningsGrowth = 0.027`), it is
used verbatim and the target P/E collapses:

```
target = min(36, 0.027 × 100 × 2.0) = min(36, 5.4) = 5.4×
FV     = 2.06 × 5.4 × 0.90 = $10.01
```

## 2. Fix (decision already made)

- **TO source:** bounded **revenue growth** (`fin["revenue_growth"]`, the info field —
  same one the existing `≤0` fallback already trusts). NOT forward-EPS-implied growth
  (that blows up names with a sky-high forward P/E — TSLA's 134% × forward_pe 153 → $355).
- **Trigger:** **surgical** — override only when trailing earnings growth is a small
  positive number *materially contradicted* by much stronger revenue growth. A healthy
  earnings-growth signal is never touched.

New constants (near the other multiple constants at the top of `models.py`):

```python
GROWTH_TRUST_FLOOR   = 0.10   # earnings_growth at/above this is trusted as-is
GROWTH_REVENUE_RATIO = 3.0    # revenue must exceed earnings growth by this factor to override
```

New `_forward_target_pe()`:

```python
def _forward_target_pe(fin: dict) -> float | None:
    fpe = fin.get("forward_pe")
    if not fpe or fpe <= 0:
        return None
    g = fin.get("earnings_growth")
    rev_g = fin.get("revenue_growth") or 0
    # A small-but-positive trailing earnings-growth figure that is badly contradicted
    # by much stronger revenue growth is treated as an unreliable single-quarter
    # yfinance artifact (e.g. HOOD's earningsGrowth=2.7% against ~49% revenue growth):
    # source growth from the bounded revenue figure instead. Guarded so a genuinely
    # healthy signal is never overridden — QCOM (173%) is above the floor; TSLA (8.3%)
    # is below the floor but its revenue growth (15.8%) does not clear the ratio.
    if g is not None and 0 < g < GROWTH_TRUST_FLOOR and rev_g > g * GROWTH_REVENUE_RATIO:
        g = rev_g
    if g is None or g <= 0:
        g = rev_g
    if g <= 0:
        return None
    return min(fpe, g * 100 * PEG_CEILING)
```

### Why the thresholds separate the three names

| Ticker | earnings_growth | < FLOOR 0.10? | revenue_growth | > earn×3? | Override? | target P/E | P/E-leg FV |
|---|---|---|---|---|---|---|---|
| **HOOD** | 0.027 | yes | 0.151 | 0.151 > 0.081 ✓ | **fires** | 5.4 → **30.2** | $10.01 → **$56.0** |
| **TSLA** | 0.083 | yes | 0.158 | 0.158 > 0.249 ✗ | no | 16.6 | $38.54 (unchanged) |
| **QCOM** | 1.73 | no | −0.035 | — | no | 16.7 | $140.04 (unchanged) |

## 3. RED — failing tests first (`backend/tests/test_models.py`)

Add alongside the existing `test_pe_forward_*` block:

```python
def test_pe_forward_overrides_noise_earnings_growth_with_revenue():
    # HOOD shape: tiny-positive earnings growth badly contradicted by strong revenue
    # growth -> source growth from revenue (bounded), not the 2.7% noise value.
    fin = {"eps_ttm": 2.06, "trailing_pe": 53.3, "forward_pe": 36.0,
           "earnings_growth": 0.027, "revenue_growth": 0.151}
    target = min(36.0, 0.151 * 100 * m.PEG_CEILING)   # = 30.2x
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(2.06 * target * m.MOS)


def test_pe_forward_keeps_healthy_earnings_growth_below_floor():
    # TSLA shape: earnings growth is below the floor but revenue growth does NOT
    # clear the ratio (0.158 !> 0.083*3) -> earnings growth is kept, leg unchanged.
    fin = {"eps_ttm": 2.58, "trailing_pe": 358.9, "forward_pe": 153.0,
           "earnings_growth": 0.083, "revenue_growth": 0.158}
    target = min(153.0, 0.083 * 100 * m.PEG_CEILING)  # = 16.6x
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(2.58 * target * m.MOS)


def test_pe_forward_keeps_high_earnings_growth_above_floor():
    # QCOM shape: earnings growth well above the floor is always trusted, even when
    # revenue growth is negative -> no override, forward_pe binds.
    fin = {"eps_ttm": 9.31, "trailing_pe": 19.76, "forward_pe": 16.71,
           "earnings_growth": 1.73, "revenue_growth": -0.035}
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(9.31 * 16.71 * m.MOS)


def test_pe_forward_override_needs_material_ratio():
    # Guard the ratio: revenue only modestly above earnings growth must NOT override.
    fin = {"eps_ttm": 10.0, "trailing_pe": 40.0, "forward_pe": 30.0,
           "earnings_growth": 0.05, "revenue_growth": 0.10}   # 0.10 !> 0.05*3
    target = min(30.0, 0.05 * 100 * m.PEG_CEILING)   # = 10x, off earnings growth
    fv = m.calc_pe(fin, forward=True)["fair_value"]
    assert fv == pytest.approx(10.0 * target * m.MOS)
```

Confirm the first test FAILS against current code (it will compute off 5.4×, not 30.2×)
and the other three PASS (they already hold under current behavior — they are the
regression guardrails proving the change is surgical).

## 4. GREEN — implement

1. Add `GROWTH_TRUST_FLOOR` and `GROWTH_REVENUE_RATIO` constants.
2. Replace `_forward_target_pe()` body as in §2.
3. Keep the existing `≤0` fallback and the `min(fpe, …)` cap intact.

## 5. Verification

- `python3 -m pytest tests/test_models.py -q` — all four new tests pass; existing
  `test_pe_forward_*` unchanged.
- `python3 -m pytest -q` — full suite still green (was 208).
- End-to-end spot check (throwaway script, delete after):
  - **HOOD** — P/E leg `$10.01 → ~$56`; blended FV `$19.47 → ~$34` (DCF $34.96 now
    corroborated rather than outvoted). Still a conservative discount to $109.86, which
    is the intended posture — we are un-breaking the leg, not chasing the market price.
  - **TSLA** — P/E leg stays `$38.54`; blended FV `$36.93` unchanged.
  - **QCOM** — P/E leg stays `$140.04`; blended FV `$257.77` unchanged.

## 6. Out of scope (explicitly NOT changing)

- The EV/Sales `MATURE_EV_SALES = 2.0` cap (0.40 weight on HOOD). That is a deliberate
  mean-reversion design choice, not a data defect — separate decision if revisited.
- The EPS-base selection (`_normalized_forward_eps`, the AVGO forward-EPS logic).
- Any screener / Quality-Score code (HOOD's 6.3 validated as correct).

## 7. Memory

On completion, add a `project`-type memory note (`hood-pe-growth-source-fix.md`) +
MEMORY.md index line, linking [[iren-opmargin-capex-reroute]] and [[avgo-forward-eps-pe]].
