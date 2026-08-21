# FV Quality Cluster — Quality-Adjusted Discount Rate & Margin of Safety — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Fair Value pipeline's discount rate and margin of safety quality-sensitive — the discount rate keyed to market risk (beta/WACC), the MOS keyed to business durability (ROIC−WACC spread) — and fix the captive-finance WACC distortion at its source in `screener.metrics.wacc()`.

**Architecture:** The FV legs today read two flat module globals (`DISCOUNT_RATE = 0.10`, `MOS = 0.90`). We thread per-company `discount_rate` / `ddm_rate` / `mos` through the `fin` dict (the exact precedent already used for `cost_of_equity` in the FINANCIAL book legs), inject them in `engine.evaluate()`, and source their inputs (WACC, ROIC−WACC spread, 5-year ROIC) in `engine.run()` by reusing `screener.metrics` as a library. Every leg falls back to the flat global when its `fin` key is absent, so the neutral case is byte-for-byte identical to today's model — the whole change is backward-compatible by construction. The captive-finance fix is a standalone correction inside the shared `wacc()`.

**Tech Stack:** Python 3.14, pytest, asyncio; existing modules `valuation/models.py`, `valuation/engine.py`, `screener/metrics.py`, `screener/data.py`.

**Spec:** `docs/superpowers/specs/2026-08-17-fv-quality-discount-mos-design.md` (read it alongside this plan — the plan argues from it).

## Global Constraints

- **Concurrency-safety (hard requirement):** the batch pipeline evaluates tickers in a thread pool (`services/yf_pool.py`). Per-company rate/MOS MUST travel through the `fin` dict (or explicit function params) — **never** by mutating the module globals `models.DISCOUNT_RATE` / `models.MOS`. The sweep harness patched those globals; that is a sweep-only shortcut and a production concurrency bug. Do not replicate it.
- **Backward-compatible identity:** when a `fin` dict carries no `wacc` (and therefore no injected rate/mos), `blended_discount_rate(None)` MUST return `DISCOUNT_RATE` (0.10), `ddm_discount_rate(0.10)` MUST return 0.10, and `quality_margin_of_safety(None, None, None)` MUST return `MOS` (0.90). This makes every existing test (498 collected) pass unchanged. Verify the full suite stays green after each task.
- **`MATURE_MULTIPLE_FACTOR` stays flat.** It is import-bound to the flat 0.10 and is used only for the EV/EBITDA compression ceiling (`_compressed_exit_multiple`), a terminal mature-multiple ceiling. It is deliberately NOT recomputed per-company — the sweep validated the FV deltas with it flat. Leave it alone.
- **Units:** WACC, ROIC−WACC spread, and 5-year ROIC are carried in the same units `screener.metrics` produces — WACC and ROIC as **percent** (e.g. 8.6 not 0.086), spread in **percentage points**. The calibration functions convert internally (`wacc_pct / 100`).
- **Settled calibration values (copy verbatim):** blend weight `0.30`; rate clamp `[0.085, 0.13]`; DDM perpetuity floor `0.09`; MOS band `[0.85, 0.95]`; MOS spot-spread pivot `15.0` pp; MOS durability pivot `5.0` pp; Option A debt-weight cap `0.50`; Option A cost-of-debt floor `risk_free × (1 − tax)`; Option A excludes `sector == "Financial Services"`.
- **Review:** inline Opus subagent review only — never `/code-review ultra` or any billed feature without explicit approval (`no-paid-features-without-approval.md`).

---

### Task 1: Option A — captive-finance WACC fix at source in `screener.metrics.wacc()`

Standalone correction to the shared WACC. Keys on the distortion **signature** (implausibly cheap implied cost of debt + debt dominating the capital structure), not the industry string, so TSLA (also "Auto Manufacturers", debt-weight 0.01) never triggers and no non-auto captive lender is missed. Excludes financials (legitimately debt-funded; also keeps their Quality `roic_wacc_spread` untouched).

**Files:**
- Modify: `backend/screener/metrics.py:85-102` (the `wacc()` function)
- Test: `backend/tests/test_screener_metrics.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `wacc(inp: ScreenerInputs, tax_rate: float) -> float | None` — unchanged signature; corrected value for captive-finance non-financials.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_screener_metrics.py` (reuses the existing `_mk_inputs` helper):

```python
def test_wacc_floors_implausibly_cheap_captive_debt():
    from screener.metrics import wacc as wacc_fn
    # Ford-shaped: huge finance-arm debt at a ~0.5% implied cost (interest booked against
    # finance revenue, not the Interest Expense line) dominating a small equity base.
    inp = _mk_inputs(info={"beta": 1.85, "totalDebt": 163_000.0, "marketCap": 57_000.0})
    inp.income.rows["Interest Expense"] = [1_000.0, 1_000.0, 1_000.0, 1_000.0]  # ~0.6% of debt
    w = wacc_fn(inp, 0.21)
    # Without the fix this collapses to ~4%; the cost-of-debt floor + 0.50 debt-weight cap
    # keep it a defensible industrial hurdle well above the risk-free rate.
    assert w > 0.08


def test_wacc_debt_weight_capped_at_half():
    from screener.metrics import wacc as wacc_fn
    # Debt-weight would be 0.74; capped to 0.50 so match-funded debt can't dominate the hurdle.
    heavy = _mk_inputs(info={"beta": 1.85, "totalDebt": 163_000.0, "marketCap": 57_000.0})
    heavy.income.rows["Interest Expense"] = [1_000.0] * 4
    # Same company but with the debt weight already <= 0.50 (double the equity): the cap
    # doesn't bind, so the only lift comes from the cost-of-debt floor.
    lighter = _mk_inputs(info={"beta": 1.85, "totalDebt": 163_000.0, "marketCap": 200_000.0})
    lighter.income.rows["Interest Expense"] = [1_000.0] * 4
    assert wacc_fn(heavy, 0.21) is not None and wacc_fn(lighter, 0.21) is not None


def test_wacc_low_debt_name_untouched_by_captive_fix():
    from screener.metrics import wacc as wacc_fn
    # TSLA-shaped: also an automaker but debt-weight ~0.01 -> neither guard binds -> identical
    # to the pre-fix value. Compare against a hand-computed equity-dominated WACC.
    inp = _mk_inputs(info={"beta": 1.0, "totalDebt": 100.0, "marketCap": 5000.0,
                           "sector": "Consumer Cyclical"})
    w = wacc_fn(inp, 0.21)
    # equity weight ~0.98 * cost_equity(0.045+1.0*0.05=0.095) dominates -> ~0.093-0.095
    assert w == pytest.approx(0.0937, abs=0.002)


def test_wacc_financials_excluded_from_captive_fix():
    from screener.metrics import wacc as wacc_fn
    # A bank legitimately carries a high debt weight and low implied cost of debt; the fix
    # must NOT touch it (keeps Quality's roic_wacc_spread for banks unchanged).
    bank = _mk_inputs(info={"beta": 1.0, "totalDebt": 100_000.0, "marketCap": 90_000.0,
                            "sector": "Financial Services"})
    bank.income.rows["Interest Expense"] = [200.0] * 4  # low implied cost
    no_fix = _mk_inputs(info={"beta": 1.0, "totalDebt": 100_000.0, "marketCap": 90_000.0,
                              "sector": "Financial Services"})
    no_fix.income.rows["Interest Expense"] = [200.0] * 4
    # Recompute the pre-fix formula by hand to prove no floor/cap was applied:
    rf, erp = 0.045, 0.05
    ce = rf + 1.0 * erp
    cd = (200.0 / 100_000.0) * (1 - 0.21)
    total = 100_000.0 + 90_000.0
    expected = (90_000.0 / total) * ce + (100_000.0 / total) * cd
    assert wacc_fn(bank, 0.21) == pytest.approx(expected, abs=1e-9)


def test_wacc_normal_name_unchanged_regression():
    from screener.metrics import wacc as wacc_fn
    # The default _mk_inputs (Technology, debt-weight ~0.02, cost_debt ~0.079*(1-tax)) is a
    # normal name: cost-of-debt floor may nudge but the debt weight is tiny, so WACC stays
    # in its established band (guards the existing test_roic_and_wacc expectation).
    w = wacc_fn(_mk_inputs(), 0.21)
    assert 0.05 < w < 0.12
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_screener_metrics.py -k "captive or debt_weight or low_debt or financials_excluded or normal_name_unchanged" -v`
Expected: the captive/debt-weight/financials tests FAIL (current WACC ~4% for Ford-shaped; no exclusion), the untouched/regression ones may already pass.

- [ ] **Step 3: Implement the fix**

Replace `wacc()` in `backend/screener/metrics.py` (lines 85-102) with:

```python
# Option A — captive-finance WACC correction (spec §4.4). A captive-finance arm
# (Ford Credit, GM Financial) inflates info['totalDebt'] with match-funded lending
# debt whose interest is booked against finance revenue, not the "Interest Expense"
# line — so interest/totalDebt collapses to ~0.5% and drags WACC toward the risk-free
# floor. Classifier-free: we key on the distortion signature (cheap implied cost of
# debt + debt dominance), not the industry string, so a low-debt automaker (TSLA,
# debt-weight ~0.01) never triggers. Excluded for financials (legitimately debt-funded;
# also keeps Quality's roic_wacc_spread for banks unchanged).
CAPTIVE_DEBT_WEIGHT_CAP = 0.50


def wacc(inp: ScreenerInputs, tax_rate: float) -> float | None:
    info = inp.info
    beta = info.get("beta")
    if beta is None:
        return None
    beta = min(beta, BETA_CEILING)
    rf = inp.risk_free if inp.risk_free is not None else DEFAULT_RISK_FREE
    cost_equity = rf + beta * ERP
    debt = info.get("totalDebt") or 0.0
    equity = info.get("marketCap") or 0.0
    total = debt + equity
    if total <= 0:
        return cost_equity
    interest = None
    if inp.income is not None:
        interest = inp.income.latest("Interest Expense")
    cost_debt = (abs(interest) / debt) * (1 - tax_rate) if (interest and debt > 0) else 0.0
    w_debt = debt / total
    if info.get("sector") != "Financial Services":
        # (1) No large borrower funds at ~0.5% after tax; floor the implied cost of debt
        #     at the after-tax risk-free rate to reject the finance-arm artifact.
        cost_debt = max(cost_debt, rf * (1 - tax_rate))
        # (2) Match-funded finance debt must not dominate the equity hurdle.
        w_debt = min(w_debt, CAPTIVE_DEBT_WEIGHT_CAP)
    return (1 - w_debt) * cost_equity + w_debt * cost_debt
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_screener_metrics.py -v`
Expected: all PASS (including the pre-existing `test_roic_and_wacc`, `test_wacc_caps_inflated_beta`).

- [ ] **Step 5: Run the screener + engine suites for blast radius, then commit**

Run: `python -m pytest tests/test_screener_metrics.py tests/test_screener_engine.py tests/test_screener_scoring.py -q`
Expected: PASS (the fix changes only captive-finance non-financials; the near-nil Quality blast radius was measured — only GM moves).

```bash
git add backend/screener/metrics.py backend/tests/test_screener_metrics.py
git commit -m "fix(wacc): correct captive-finance debt distortion at source (Option A)"
```

---

### Task 2: Pure calibration functions in `models.py`

The math for the quality-adjusted rate and MOS, as pure functions with the settled constants and neutral fallbacks. No threading yet — unit-tested in isolation.

**Files:**
- Modify: `backend/valuation/models.py` (add constants after line 6 `MOS = 0.90`, and functions near the other helpers ~line 139)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `DISCOUNT_RATE`, `MOS` (existing module constants).
- Produces:
  - `blended_discount_rate(wacc_pct: float | None) -> float`
  - `ddm_discount_rate(rate: float) -> float`
  - `quality_margin_of_safety(spread_pp: float | None, roic5_pct: float | None, wacc_pct: float | None) -> float`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_models.py`:

```python
def test_blended_discount_rate_neutral_fallback():
    # No WACC signal -> exactly the flat prior (backward-compatible identity).
    assert m.blended_discount_rate(None) == pytest.approx(m.DISCOUNT_RATE)


def test_blended_discount_rate_blends_and_clamps():
    # 0.7*0.10 + 0.3*(wacc/100), clamped to [0.085, 0.13].
    assert m.blended_discount_rate(8.6) == pytest.approx(0.7 * 0.10 + 0.3 * 0.086)   # ~0.0958
    assert m.blended_discount_rate(4.0) == pytest.approx(0.085)   # low WACC hits the floor
    assert m.blended_discount_rate(20.0) == pytest.approx(0.13)   # high WACC hits the ceiling


def test_ddm_discount_rate_floors_at_9pct():
    assert m.ddm_discount_rate(0.085) == pytest.approx(0.09)   # perpetuity floor binds
    assert m.ddm_discount_rate(0.12) == pytest.approx(0.12)    # above the floor, unchanged


def test_quality_mos_neutral_fallback():
    # Both durability signals missing -> exactly the flat 0.90 (backward-compatible identity).
    assert m.quality_margin_of_safety(None, None, None) == pytest.approx(m.MOS)


def test_quality_mos_ramps_within_band():
    # Full spot spread (>=15pp) -> ceiling 0.95; zero/negative durability -> floor 0.85.
    assert m.quality_margin_of_safety(15.0, None, None) == pytest.approx(0.95)
    assert m.quality_margin_of_safety(0.0, None, None) == pytest.approx(0.85)
    # Takes the GREATER of the spot-spread ramp and the (roic5 - wacc) durability ramp.
    # spread 0 but roic5 25 vs wacc 20 -> durability ramp = 5/5 = 1.0 -> ceiling.
    assert m.quality_margin_of_safety(0.0, 25.0, 20.0) == pytest.approx(0.95)
    # Half of the spot pivot -> midpoint 0.90.
    assert m.quality_margin_of_safety(7.5, None, None) == pytest.approx(0.90)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -k "blended or ddm_discount or quality_mos" -v`
Expected: FAIL with `AttributeError: module 'valuation.models' has no attribute 'blended_discount_rate'`.

- [ ] **Step 3: Implement the constants and functions**

Add the constants immediately after `MOS = 0.90` (line 6) in `backend/valuation/models.py`:

```python
# Quality-adjusted discount rate (spec §4.1): nudge the flat prior partway toward the
# company's beta-driven WACC, then clamp to a tight band. Gentler 0.30 blend + 8.5%
# floor were chosen because aggressive settings over-inflated low-WACC DDM-heavy names.
RATE_BLEND_W = 0.30
RATE_FLOOR = 0.085
RATE_CEIL = 0.13
# DDM perpetuity guard: (rate - g) in the Gordon denominator is hypersensitive at low
# rates, so the DDM leg floors its discount rate higher than the DCF/EV legs.
DDM_RATE_FLOOR = 0.09
# Quality-adjusted margin of safety (spec §4.2, Variant A): nudge the flat 0.90 within a
# tight band by business durability (ROIC-WACC spot spread, or 5y-ROIC-vs-WACC ramp).
MOS_FLOOR = 0.85
MOS_CEIL = 0.95
MOS_SPREAD_PIVOT = 15.0       # pp of ROIC-WACC spot spread for the full nudge
MOS_DURABILITY_PIVOT = 5.0    # pp of (roic_5y_avg - wacc) for the full nudge
```

Add the functions near `_apply_mos` (after line 145, `_avg`):

```python
def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def blended_discount_rate(wacc_pct: float | None) -> float:
    """Per-company DCF/EV discount rate: blend the flat prior toward the company WACC,
    clamped to [RATE_FLOOR, RATE_CEIL]. Neutral flat prior when WACC is unavailable
    (spec §4.3) — this makes the no-signal case byte-identical to today's model."""
    if wacc_pct is None:
        return DISCOUNT_RATE
    return _clamp((1 - RATE_BLEND_W) * DISCOUNT_RATE + RATE_BLEND_W * (wacc_pct / 100.0),
                  RATE_FLOOR, RATE_CEIL)


def ddm_discount_rate(rate: float) -> float:
    """DDM perpetuity-leg rate: the DCF/EV rate floored at DDM_RATE_FLOOR (Gordon guard)."""
    return max(rate, DDM_RATE_FLOOR)


def quality_margin_of_safety(spread_pp: float | None, roic5_pct: float | None,
                             wacc_pct: float | None) -> float:
    """Variant-A MOS: nudge the flat MOS within [MOS_FLOOR, MOS_CEIL] on the GREATER of the
    ROIC-WACC spot-spread ramp and the 5y-ROIC-vs-WACC durability ramp. Neutral flat MOS
    when both signals are missing (spec §4.3) — byte-identical to today's model."""
    ramps = []
    if spread_pp is not None:
        ramps.append(_clamp(spread_pp / MOS_SPREAD_PIVOT, 0.0, 1.0))
    if roic5_pct is not None and wacc_pct is not None:
        ramps.append(_clamp((roic5_pct - wacc_pct) / MOS_DURABILITY_PIVOT, 0.0, 1.0))
    if not ramps:
        return MOS
    return MOS_FLOOR + max(ramps) * (MOS_CEIL - MOS_FLOOR)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -k "blended or ddm_discount or quality_mos" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "feat(valuation): pure quality-adjusted discount-rate and MOS functions"
```

---

### Task 3: Thread the discount rate and MOS through the DCF / EV legs

Give the two scenario helpers explicit `rate` / `mos` params (defaulting to the module globals for backward-compat), and have `calc_dcf` / `calc_fcfe` / `calc_ev_ebitda` / `calc_ev_sales` read them from `fin`. `_apply_mos` gains a defaulted `mos` param. The compression ceiling (`MATURE_MULTIPLE_FACTOR`) stays flat per the Global Constraints.

**Files:**
- Modify: `backend/valuation/models.py` — `_apply_mos` (139-140), `_scenario_dcf_equity` (215-224), `_scenario_ev_multiple` (227-233), `calc_dcf` (300-315), `calc_fcfe` (319-329), `calc_ev_ebitda` (333-383), `calc_ev_sales` (424-443)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `fin["discount_rate"]`, `fin["mos"]` (optional; default to `DISCOUNT_RATE` / `MOS`).
- Produces (updated signatures):
  - `_apply_mos(value: float, mos: float = MOS) -> float`
  - `_scenario_dcf_equity(cf, growth, net_debt, shares, hold=HORIZON, rate=DISCOUNT_RATE, mos=MOS) -> float`
  - `_scenario_ev_multiple(base, growth, multiple, net_debt, shares, hold=HORIZON, rate=DISCOUNT_RATE, mos=MOS) -> float`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_models.py`:

```python
def test_dcf_uses_fin_discount_rate_and_mos():
    fin = {"fcf_ttm": 1_000.0, "shares_outstanding": 100.0, "net_debt": 0}
    base = m.calc_dcf(fin, GROWTH)["fair_value"]
    # A LOWER discount rate raises the DCF; a HIGHER mos (less haircut) raises it too.
    tuned = m.calc_dcf({**fin, "discount_rate": 0.085, "mos": 0.95}, GROWTH)["fair_value"]
    assert tuned > base


def test_dcf_absent_keys_are_identical_to_today():
    # Backward-compatible identity: no discount_rate/mos in fin -> the flat-10%/0.90 result.
    fin = {"fcf_ttm": 1_000.0, "shares_outstanding": 100.0, "net_debt": 0}
    explicit = m.calc_dcf({**fin, "discount_rate": m.DISCOUNT_RATE, "mos": m.MOS}, GROWTH)
    assert m.calc_dcf(fin, GROWTH)["fair_value"] == pytest.approx(explicit["fair_value"])


def test_ev_ebitda_uses_fin_discount_rate():
    fin = {"ebitda_ttm": 500.0, "shares_outstanding": 100.0, "net_debt": 0,
           "ev_ebitda": 12.0, "fcf_ttm": 300.0}
    base = m.calc_ev_ebitda(fin, GROWTH)["fair_value"]
    lower_rate = m.calc_ev_ebitda({**fin, "discount_rate": 0.085}, GROWTH)["fair_value"]
    # The future EV is discounted back 10 years at the per-company rate: a lower rate -> higher PV.
    assert lower_rate > base
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -k "dcf_uses_fin or dcf_absent or ev_ebitda_uses_fin" -v`
Expected: FAIL (tuned == base — the legs currently ignore the fin keys).

- [ ] **Step 3: Implement the threading**

In `backend/valuation/models.py`:

Change `_apply_mos` (lines 139-140):

```python
def _apply_mos(value: float, mos: float = MOS) -> float:
    return value * mos
```

Change `_scenario_dcf_equity` (lines 215-224):

```python
def _scenario_dcf_equity(cf: float, growth: float, net_debt: float, shares: float,
                         hold: int = HORIZON, rate: float = DISCOUNT_RATE,
                         mos: float = MOS) -> float:
    total = 0.0
    cf_t = cf
    for t in range(1, HORIZON + 1):
        cf_t *= (1 + _faded_rate(growth, hold, t))
        total += _pv(cf_t, rate, t)
    tv = cf_t * (1 + TERMINAL_GROWTH) / (rate - TERMINAL_GROWTH)
    total += _pv(tv, rate, HORIZON)
    return _apply_mos((total - net_debt) / shares, mos)
```

Change `_scenario_ev_multiple` (lines 227-233):

```python
def _scenario_ev_multiple(base: float, growth: float, multiple: float, net_debt: float,
                          shares: float, hold: int = HORIZON, rate: float = DISCOUNT_RATE,
                          mos: float = MOS) -> float:
    projected = base
    for t in range(1, HORIZON + 1):
        projected *= (1 + _faded_rate(growth, hold, t))
    future_ev = projected * multiple
    return _apply_mos((future_ev - net_debt) / shares / (1 + rate) ** HORIZON, mos)
```

In `calc_dcf`, after `hold = _fade_hold_years(...)` (line 311), read the fin values and pass them:

```python
    hold = _fade_hold_years(fin.get("market_cap"), fin.get("revenue_growth"))
    rate = fin.get("discount_rate") or DISCOUNT_RATE
    mos = fin.get("mos") or MOS
    scenarios = {k: _scenario_dcf_equity(base, growth[k], net_debt, shares, hold,
                                         rate=rate, mos=mos) for k in SCENARIO_KEYS}
```

In `calc_fcfe`, change the scenarios line (line 328) to:

```python
    mos = fin.get("mos") or MOS
    rate = fin.get("discount_rate") or DISCOUNT_RATE
    scenarios = {k: _scenario_dcf_equity(fcfe, growth[k], 0, shares, rate=rate, mos=mos)
                 for k in SCENARIO_KEYS}
```

In `calc_ev_ebitda`, change the scenarios line (line 382) to:

```python
    rate = fin.get("discount_rate") or DISCOUNT_RATE
    mos = fin.get("mos") or MOS
    scenarios = {k: _scenario_ev_multiple(ebitda, growth[k], multiple, net_debt, shares, hold,
                                          rate=rate, mos=mos) for k in SCENARIO_KEYS}
```

(Leave the `_compressed_exit_multiple` / `MATURE_MULTIPLE_FACTOR` block untouched — the compression ceiling stays flat per the Global Constraints.)

In `calc_ev_sales`, change the scenarios block (lines 439-442) to:

```python
    rate = fin.get("discount_rate") or DISCOUNT_RATE
    mos = fin.get("mos") or MOS
    scenarios = {k: _scenario_ev_multiple(
                    revenue, growth[k], multiple,
                    exit_net_debt(fin, revenue, growth[k], HORIZON, net_debt), shares,
                    rate=rate, mos=mos)
                 for k in SCENARIO_KEYS}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (new threading tests pass; every pre-existing `test_models` assertion still passes because absent keys default to the globals).

- [ ] **Step 5: Run the engine suite for blast radius, then commit**

Run: `python -m pytest tests/test_engine.py tests/test_models.py -q`
Expected: PASS.

```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "feat(valuation): thread per-company rate/MOS through DCF and EV legs"
```

---

### Task 4: Thread the DDM-guard rate and MOS through `calc_ddm`

The DDM perpetuity leg reads its own floored `ddm_rate` (separate from the DCF/EV `discount_rate`) plus `mos`.

**Files:**
- Modify: `backend/valuation/models.py` — `calc_ddm` (502-514)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `fin["ddm_rate"]`, `fin["mos"]` (optional; default `DISCOUNT_RATE` / `MOS`).
- Produces: `calc_ddm(fin, growth) -> dict` — unchanged signature.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_models.py`:

```python
def test_ddm_uses_fin_ddm_rate_and_mos():
    fin = {"dividend_rate": 2.0}
    base = m.calc_ddm(fin, GROWTH)["fair_value"]
    # A HIGHER ddm_rate widens the Gordon denominator -> LOWER value (the guard's whole point).
    higher_rate = m.calc_ddm({**fin, "ddm_rate": 0.12}, GROWTH)["fair_value"]
    assert higher_rate < base


def test_ddm_absent_keys_are_identical_to_today():
    fin = {"dividend_rate": 2.0}
    explicit = m.calc_ddm({**fin, "ddm_rate": m.DISCOUNT_RATE, "mos": m.MOS}, GROWTH)
    assert m.calc_ddm(fin, GROWTH)["fair_value"] == pytest.approx(explicit["fair_value"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -k "ddm_uses_fin or ddm_absent" -v`
Expected: FAIL (higher_rate == base — the leg ignores `ddm_rate`).

- [ ] **Step 3: Implement the threading**

Replace `calc_ddm` (lines 502-514) in `backend/valuation/models.py`:

```python
def calc_ddm(fin: dict, growth: dict) -> dict:
    div = fin.get("dividend_rate")
    if div is None or div <= 0:
        return _null_result(True)
    rate = fin.get("ddm_rate") or DISCOUNT_RATE
    mos = fin.get("mos") or MOS

    def scenario_ddm(g: float) -> float | None:
        capped_g = min(g, rate - 0.01)
        if rate <= capped_g:
            return None
        return _apply_mos(div * (1 + capped_g) / (rate - capped_g), mos)

    scenarios = {k: scenario_ddm(growth[k]) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -k "ddm" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "feat(valuation): thread floored DDM-guard rate and MOS through calc_ddm"
```

---

### Task 5: Thread MOS through the P/E and book-value legs

`calc_pe`, `calc_pb`, `calc_rim`, `calc_nav` read `mos` from `fin`. These have no discount-rate change (P/E uses a market multiple; P/B and RIM already read `cost_of_equity` from `fin`).

**Files:**
- Modify: `backend/valuation/models.py` — `calc_pe` (484-498), `calc_pb` (518-536), `calc_rim` (540-571), `calc_nav` (576-584)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `fin["mos"]` (optional; default `MOS`).
- Produces: `calc_pe`, `calc_pb`, `calc_rim`, `calc_nav` — unchanged signatures.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_models.py`:

```python
def test_book_and_pe_legs_use_fin_mos():
    nav = {"book_value_per_share": 10.0, "net_debt": 0, "shares_outstanding": 1_000}
    assert m.calc_nav({**nav, "mos": 0.95})["fair_value"] == pytest.approx(10.0 * 0.95)
    pb = {"book_value_per_share": 10.0, "return_on_equity": 0.10}
    assert m.calc_pb({**pb, "mos": 0.95})["fair_value"] == pytest.approx(10.0 * 1.0 * 0.95)
    pe = {"eps_ttm": 1.0, "trailing_pe": 10.0}
    assert m.calc_pe({**pe, "mos": 0.95})["fair_value"] == pytest.approx(1.0 * 10.0 * 0.95)


def test_book_legs_absent_mos_identical_to_today():
    nav = {"book_value_per_share": 10.0, "net_debt": 0, "shares_outstanding": 1_000}
    assert m.calc_nav(nav)["fair_value"] == pytest.approx(9.0)   # 10 * 0.90, unchanged
    rim = {"book_value_per_share": 10.0, "eps_ttm": 1.0}
    assert m.calc_rim(rim, GROWTH)["fair_value"] == pytest.approx(
        m.calc_rim({**rim, "mos": m.MOS}, GROWTH)["fair_value"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -k "use_fin_mos or absent_mos_identical" -v`
Expected: FAIL for the `mos: 0.95` assertions (legs currently apply the flat 0.90).

- [ ] **Step 3: Implement the threading**

In `backend/valuation/models.py`, in `calc_pe` change the final value line (line 496):

```python
    fv = _apply_mos(eps * target_pe, fin.get("mos") or MOS)
```

In `calc_pb` change the final value line (line 534):

```python
    fv = _apply_mos(bvps * max(justified_pb, 0.1), fin.get("mos") or MOS)
```

In `calc_rim`, read mos before the inner function (after line 559 `roe = min(...)`) and use it:

```python
    roe = min(roe, ROE_PB_CAP_MULT * coe)
    mos = fin.get("mos") or MOS

    def scenario_rim(g: float) -> float:
        total = 0.0
        bv = bvps
        for t in range(1, HORIZON + 1):
            bv_prev = bv
            bv = bv * (1 + g)
            total += _pv(bv_prev * (roe - coe), coe, t)
        return _apply_mos(bvps + total, mos)
```

In `calc_nav` change the value line (line 583):

```python
    fv = _apply_mos(bvps, fin.get("mos") or MOS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (including `test_engine.py:744-766`-style expectations that read `m.MOS`, since absent-key legs still use `MOS`).

- [ ] **Step 5: Run the engine suite, then commit**

Run: `python -m pytest tests/test_engine.py tests/test_models.py -q`
Expected: PASS.

```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "feat(valuation): thread per-company MOS through P/E and book-value legs"
```

---

### Task 6: Inject `discount_rate` / `ddm_rate` / `mos` in `engine.evaluate()`

Derive the per-company rate and MOS from the WACC / spread / 5y-ROIC that `run()` will attach to `fin` (Task 7), and inject them into the copied `fin`. FINANCIAL stays rate-invariant (only MOS applied). Missing WACC → neutral flat prior (the injected values equal today's globals, so the identity holds).

**Files:**
- Modify: `backend/valuation/engine.py:487-499` (inside `evaluate`, right after the FINANCIAL COE block)
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `fin["wacc"]`, `fin["roic_wacc_spread"]`, `fin["roic_5y_avg"]` (optional, percent units); `m.blended_discount_rate`, `m.ddm_discount_rate`, `m.quality_margin_of_safety` (Task 2).
- Produces: injects `fin["discount_rate"]`, `fin["ddm_rate"]`, `fin["mos"]` (consumed by Tasks 3-5).

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_engine.py`:

```python
def test_evaluate_applies_low_wacc_discount_rate():
    # A non-financial DCF-anchored name: a low per-company WACC -> lower discount rate + a
    # wide durability spread -> higher MOS -> a HIGHER fair value than the neutral baseline.
    base_fin = {
        "ticker": "T", "current_price": 100.0, "fcf_ttm": 1_000.0,
        "shares_outstanding": 100.0, "net_debt": 0, "market_cap": 50_000_000_000,
        "revenue_growth": 0.05, "eps_ttm": 5.0, "trailing_pe": 20.0,
    }
    baseline = engine.evaluate(dict(base_fin))["fair_value"]
    tuned = engine.evaluate({**base_fin, "wacc": 5.0, "roic_wacc_spread": 20.0,
                             "roic_5y_avg": 25.0})["fair_value"]
    assert tuned > baseline


def test_evaluate_missing_wacc_is_identity():
    # No WACC signal -> injected rate/mos equal the flat globals -> byte-identical FV.
    base_fin = {
        "ticker": "T", "current_price": 100.0, "fcf_ttm": 1_000.0,
        "shares_outstanding": 100.0, "net_debt": 0, "market_cap": 50_000_000_000,
        "revenue_growth": 0.05, "eps_ttm": 5.0, "trailing_pe": 20.0,
    }
    a = engine.evaluate(dict(base_fin))["fair_value"]
    b = engine.evaluate({**base_fin, "wacc": None, "roic_wacc_spread": None,
                         "roic_5y_avg": None})["fair_value"]
    assert a == pytest.approx(b)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "low_wacc_discount_rate or missing_wacc_is_identity" -v`
Expected: `test_evaluate_applies_low_wacc_discount_rate` FAILs (tuned == baseline — evaluate does not yet inject); the identity test may already pass.

- [ ] **Step 3: Implement the injection**

In `backend/valuation/engine.py`, immediately after the FINANCIAL COE block (after line 499, before `weights = ...` on line 500), insert:

```python
    # Quality-adjusted discount rate and margin of safety (spec §4.1/§4.2). Inputs are the
    # per-company WACC / ROIC-WACC spread / 5y ROIC that run() attaches to fin by reusing
    # screener.metrics (percent units). Missing signals -> neutral flat prior (§4.3), which
    # makes the injected values equal the flat globals, so a no-signal fin is byte-identical
    # to today's model. FINANCIAL stays rate-invariant: its book legs discount at
    # FINANCIAL_COE and its DCF/EV/DDM weights are 0, so only the durability MOS is applied.
    wacc_pct = fin.get("wacc")
    inject = {"mos": m.quality_margin_of_safety(
        fin.get("roic_wacc_spread"), fin.get("roic_5y_avg"), wacc_pct)}
    if stock_type != "FINANCIAL":
        rate = m.blended_discount_rate(wacc_pct)
        inject["discount_rate"] = rate
        inject["ddm_rate"] = m.ddm_discount_rate(rate)
    fin = {**fin, **inject}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -v`
Expected: PASS. In particular every pre-existing `test_engine` assertion passes because those `fin` dicts carry no `wacc`, so the injected rate/mos equal `DISCOUNT_RATE` / `MOS`.

- [ ] **Step 5: Run the full valuation suite, then commit**

Run: `python -m pytest tests/test_engine.py tests/test_engine_run.py tests/test_models.py tests/test_classifier.py -q`
Expected: PASS.

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(valuation): inject quality-adjusted rate/MOS in evaluate()"
```

---

### Task 7: Source WACC / spread / 5y-ROIC in `engine.run()` (reuse `screener.metrics`)

Populate the three `fin` keys from a live screener-inputs fetch + `compute_metrics`, failure-isolated so any screener-data error leaves them absent and FV falls back to the neutral prior. This is the IO wiring that makes the feature live.

**Files:**
- Modify: `backend/valuation/engine.py` — imports (after line 9) and `run()` (before `data = evaluate(fin)` on line 774)
- Test: `backend/tests/test_engine_run.py`

**Interfaces:**
- Consumes: `screener.data.fetch_screener_inputs`, `screener.metrics.compute_metrics` (the Option A fix from Task 1 lives inside the `wacc()` these call).
- Produces: `fin["wacc"]`, `fin["roic_wacc_spread"]`, `fin["roic_5y_avg"]` (consumed by Task 6).

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_engine_run.py`:

```python
from screener.models import ScreenerMetrics


@pytest.mark.asyncio
async def test_run_low_wacc_lifts_fair_value():
    # A low per-company WACC (5%) + wide durability spread lifts FV above the neutral run.
    stub = ScreenerMetrics(wacc=5.0, roic_wacc_spread=20.0, roic_5y_avg=25.0)
    with patch("valuation.engine.fetch_ticker_info", return_value=_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=None), \
         patch("valuation.engine.fetch_screener_inputs", return_value=None):
        neutral = (await engine.run("AAPL")).fair_value
    with patch("valuation.engine.fetch_ticker_info", return_value=_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=None), \
         patch("valuation.engine.fetch_screener_inputs", return_value=object()), \
         patch("valuation.engine.compute_metrics", return_value=stub):
        lifted = (await engine.run("AAPL")).fair_value
    assert lifted > neutral


@pytest.mark.asyncio
async def test_run_screener_failure_is_isolated():
    # A screener-data failure must not fail the FV run — it falls back to the neutral prior.
    with patch("valuation.engine.fetch_ticker_info", return_value=_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=None), \
         patch("valuation.engine.fetch_screener_inputs", side_effect=RuntimeError("boom")):
        result = await engine.run("AAPL")
    assert result.status == "completed" and result.fair_value is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine_run.py -k "low_wacc_lifts or screener_failure_is_isolated" -v`
Expected: FAIL with `AttributeError`/`ImportError` — `fetch_screener_inputs` / `compute_metrics` are not yet imported into `valuation.engine`.

- [ ] **Step 3: Implement the sourcing**

In `backend/valuation/engine.py`, add imports after line 9 (`from models import TickerResult`):

```python
from screener.data import fetch_screener_inputs
from screener.metrics import compute_metrics
```

In `run()`, immediately before `data = evaluate(fin)` (line 774), insert:

```python
    # Attach the per-company WACC / ROIC-WACC durability signal for the quality-adjusted
    # discount rate + MOS (spec §4.1/§4.2), reusing screener.metrics as a library (the
    # Option A captive-finance fix lives inside its wacc()). Failure-isolated: any screener
    # error leaves the keys absent, so evaluate() falls back to the neutral flat prior
    # (rate 0.10 / MOS 0.90) and FV still computes — preserving pipeline independence.
    try:
        sinp = await fetch_screener_inputs(ticker)
        if sinp is not None:
            met = compute_metrics(sinp)
            fin["wacc"] = met.wacc
            fin["roic_wacc_spread"] = met.roic_wacc_spread
            fin["roic_5y_avg"] = met.roic_5y_avg
    except Exception:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine_run.py -v`
Expected: PASS (including the pre-existing run tests — they patch `fetch_screener_inputs` to nothing, so it uses the real one; add `patch("valuation.engine.fetch_screener_inputs", return_value=None)` to any pre-existing test that would otherwise attempt a network call — check each and update if needed).

- [ ] **Step 5: Run the FULL suite for the blast-radius gate**

Run: `python -m pytest -q`
Expected: PASS — all ~500+ tests. If any pre-existing `run()` test now attempts a live screener fetch, patch `valuation.engine.fetch_screener_inputs` to `return_value=None` in that test (neutral, matches its prior behavior).

- [ ] **Step 6: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine_run.py
git commit -m "feat(valuation): source per-company WACC/spread for quality-adjusted FV"
```

---

## Self-Review

**1. Spec coverage.**
- §4.1 quality-adjusted discount rate (blend 0.7/0.3, clamp 8.5–13%) → Task 2 (`blended_discount_rate`) + Tasks 3/6.
- §4.1 DDM 9% perpetuity floor → Task 2 (`ddm_discount_rate`) + Task 4.
- §4.1 no beta floor (VZ path i) → nothing to build; the rate function has no beta-floor term. ✓ (correctly absent.)
- §4.1 FINANCIAL rate-invariant → Task 6 (`if stock_type != "FINANCIAL"`).
- §4.2 Variant A MOS → Task 2 (`quality_margin_of_safety`) + Tasks 3/4/5/6.
- §4.3 neutral fallback → Task 2 (None-guards) + Task 6 identity test + Task 7 failure-isolation.
- §4.4 Option A captive-finance fix → Task 1.
- §4.5 architecture: reuse screener.metrics as a library, no live Quality-result call, concurrency-safe threading via `fin`, failure-isolation → Tasks 7 + 6 + Global Constraints.
- §7 testing discipline (rate blend, DDM floor, neutral fallback, Variant A, Option A, Quality blast radius) → covered across Tasks 1–7 with the full-suite gate in Task 7.
- No gaps found.

**2. Placeholder scan.** No TBD/TODO/"handle edge cases"/"similar to Task N" — every code and test step contains concrete content. ✓

**3. Type consistency.** `fin` keys `discount_rate` / `ddm_rate` / `mos` / `wacc` / `roic_wacc_spread` / `roic_5y_avg` are named identically in the producing task (6/7) and every consuming task (3/4/5). Function names `blended_discount_rate` / `ddm_discount_rate` / `quality_margin_of_safety` match between Task 2 (definition) and Task 6 (call). Units (percent for WACC/ROIC, pp for spread) are consistent between `screener.metrics` output, Task 7 attachment, and Task 2 conversion (`wacc_pct / 100`). Signature extensions (`_apply_mos`, `_scenario_dcf_equity`, `_scenario_ev_multiple`) use defaulted params so partial application across tasks never breaks the module. ✓

---

## Execution Handoff

After the final task, run a spot-check against the sweep (optional, non-blocking): confirm a captive-finance name (F) and a blue-chip (PG) move in the direction the Option-A sweep recorded, and that FINANCIAL names' Quality scores are unchanged except GM. Then write the landing note to `.claude/memory/`.
