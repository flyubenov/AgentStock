# FINANCIAL Cost-of-Equity + Growth-Adjusted P/B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The FINANCIAL bucket reads systematically ~30% overvalued (JPM −30%, BAC −30%, WFC −26%, C −36% vs price) because both book-value legs — P/B (0.35 weight) and RIM (0.45 weight), 80% of the FINANCIAL blend — discount at the flat `DISCOUNT_RATE = 0.10`, and the P/B leg uses a zero-growth `ROE/r` multiple. Fix by (a) discounting banks' book-value legs at a lower `FINANCIAL_COE = 0.085`, and (b) replacing `calc_pb`'s zero-growth multiple with the growth-adjusted justified P/B `(ROE−g)/(COE−g)`, guarded against distorted (unsustainably high) ROE.

**Architecture:** Three changes, no new cross-module data:
1. `backend/valuation/models.py` — `calc_pb` rewritten to read `cost_of_equity` (default `DISCOUNT_RATE`), use the growth-adjusted form, and cap the ROE input at `ROE_PB_CAP_MULT × COE`. Two new constants.
2. `backend/valuation/engine.py` — `evaluate` sets `fin["cost_of_equity"] = FINANCIAL_COE` for FINANCIAL names (on a copy; never mutates the caller's dict; respects an upstream-supplied COE). RIM already reads `cost_of_equity` — no change there.
3. Tests only.

**Tech Stack:** Python 3.14, pytest. No new dependencies. Run all tests from `backend/` with `python -m pytest`.

## Global Constraints

- `FINANCIAL_COE = 0.085`. Applies **only** to `stock_type == "FINANCIAL"` (banks / lenders / insurers). DIVIDEND, MEGA_CAP, GROWTH, etc. keep the flat `DISCOUNT_RATE = 0.10`.
- The growth-adjusted P/B uses `g = min(TERMINAL_GROWTH, COE − 0.01)` so `g` is always strictly below the discount rate (no division blow-up, no negative denominator).
- `justified_pb = (roe − g) / (coe − g)`, then floored at `0.1` (existing floor, unchanged), then `_apply_mos` (0.90, unchanged).
- Distorted-ROE guard: `roe` used in `calc_pb` is capped at `ROE_PB_CAP_MULT × coe` **(3.0 — a decision, see below)**. At `COE = 0.085` this caps ROE at 25.5%. This is the P/B leg only; RIM's `roe = eps/bvps` is **out of scope** for this change.
- `calc_pb` reads `coe = fin.get("cost_of_equity") or DISCOUNT_RATE`. When a caller supplies `cost_of_equity`, respect it; when absent, default to `DISCOUNT_RATE`.
- `evaluate` must **not** mutate the caller's `fin` dict — set the COE on a shallow copy (`fin = {**fin, ...}`). **Gate condition:** `extract_financials` hardcodes `cost_of_equity = DISCOUNT_RATE (0.10)` as the flat default, so the live pipeline never sends `None`. Override when the value is `None` **or** equals the flat `DISCOUNT_RATE` default; a genuine per-name COE (anything other than the flat default) is respected. (An `is None`-only gate is a latent bug — it leaves the RIM leg stuck at 0.10 live.)
- Do not touch DDM (still discounts at `DISCOUNT_RATE`), DCF, EV legs, the classifier's type rules, or the screener. RIM is affected only transitively (it already reads `cost_of_equity`).

### Decision: `ROE_PB_CAP_MULT = 3.0`

The guard exists because growth-adjusted P/B with a low COE amplifies an unsustainable ROE (Allstate prints a 45% ROE off a thin post-buyback book → an un-guarded P/B of ~7.7× and a fair value +139% above price). `3.0 × 0.085 = 25.5%` is the recommended cap:
- **Clips** the artifacts: ALL 45.2% → 25.5% (combined FV overshoot +139% → +85% vs price), AXP 34.4% → 25.5%.
- **Leaves untouched** every healthy bank (all ROE < 25.5%): JPM 17.8%, GS 17.0%, MS 16.4%, SYF 21.8%, BAC/WFC/USB/PNC/MET/C/AIG.

If the reviewer prefers a tighter guard (e.g. `2.5` → 21.25%, which would also clip SYF) or looser (`3.5`), change only the constant; the tests below pin the mechanism, not a specific bank's live number.

---

### Task 1: Rewrite `calc_pb` — COE-aware, growth-adjusted, ROE-guarded

**Files:**
- Modify: `backend/valuation/models.py` (add two constants near the top constant block ~line 13; rewrite `calc_pb` ~line 269)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: `models.FINANCIAL_COE = 0.085`, `models.ROE_PB_CAP_MULT = 3.0`, and a rewritten `calc_pb(fin: dict) -> dict` with the same return shape.
- Consumes: existing `DISCOUNT_RATE`, `TERMINAL_GROWTH`, `_apply_mos`, `_null_result`, `SCENARIO_KEYS`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_models.py` (keep the two existing `test_pb_*` tests — they stay green):

```python
def test_pb_roe_equals_coe_is_one_times_book():
    # Invariant: at ROE == COE the growth-adjusted P/B is exactly 1.0, for any COE.
    fin = {"book_value_per_share": 100.0, "return_on_equity": 0.085,
           "cost_of_equity": 0.085}
    assert m.calc_pb(fin)["fair_value"] == pytest.approx(90.0)   # 100 * 1.0 * 0.90


def test_pb_growth_adjusted_at_bank_coe():
    # roe 0.178, coe 0.085, g 0.03 -> (0.178-0.03)/(0.085-0.03) = 2.69090909
    fin = {"book_value_per_share": 100.0, "return_on_equity": 0.178,
           "cost_of_equity": 0.085}
    assert m.calc_pb(fin)["fair_value"] == pytest.approx(242.1818, abs=1e-3)


def test_pb_defaults_to_discount_rate_when_coe_absent():
    # No cost_of_equity -> COE = DISCOUNT_RATE (0.10): (0.178-0.03)/(0.10-0.03)=2.11428
    fin = {"book_value_per_share": 100.0, "return_on_equity": 0.178}
    assert m.calc_pb(fin)["fair_value"] == pytest.approx(190.2857, abs=1e-3)


def test_pb_lower_coe_lifts_value_for_roe_above_coe():
    hi = m.calc_pb({"book_value_per_share": 100.0, "return_on_equity": 0.178,
                    "cost_of_equity": 0.10})["fair_value"]
    lo = m.calc_pb({"book_value_per_share": 100.0, "return_on_equity": 0.178,
                    "cost_of_equity": 0.085})["fair_value"]
    assert lo > hi


def test_pb_distorted_roe_is_capped():
    # roe 0.452 (ALL-like), coe 0.085, cap 3x -> ROE clipped to 0.255
    # justified = (0.255-0.03)/(0.085-0.03) = 4.09090909 -> 100 * 4.0909 * 0.90
    fin = {"book_value_per_share": 100.0, "return_on_equity": 0.452,
           "cost_of_equity": 0.085}
    capped = m.calc_pb(fin)["fair_value"]
    assert capped == pytest.approx(368.1818, abs=1e-3)
    # strictly below what the uncapped ROE would have produced
    uncapped_pb = (0.452 - 0.03) / (0.085 - 0.03)
    assert capped < 100.0 * uncapped_pb * 0.90


def test_pb_floor_holds_at_bank_coe_for_subgrowth_roe():
    # roe 0.02 < g -> justified negative -> floored at 0.1 -> 100 * 0.1 * 0.90
    fin = {"book_value_per_share": 100.0, "return_on_equity": 0.02,
           "cost_of_equity": 0.085}
    assert m.calc_pb(fin)["fair_value"] == pytest.approx(9.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_models.py -k pb -v`
Expected: the six new tests FAIL (current `calc_pb` uses `roe/DISCOUNT_RATE`, ignores `cost_of_equity`, has no growth term and no ROE cap); the two existing `test_pb_justified_is_exact` / `test_pb_floor_justified_pb_at_0_1` still PASS.

- [ ] **Step 3: Add constants and rewrite `calc_pb`**

In `backend/valuation/models.py`, add near the top constant block (after `MATURE_PE_CAP = 21.0`, ~line 13):

```python
# Banks / lenders / insurers are financed at a lower cost of equity than the flat
# DISCOUNT_RATE default; the FINANCIAL bucket discounts its book-value legs (P/B, RIM)
# at FINANCIAL_COE. Gated to stock_type == "FINANCIAL" in engine.evaluate.
FINANCIAL_COE = 0.085
# Distorted-ROE guard for the justified P/B leg: a growth-adjusted multiple with a low
# COE amplifies an unsustainable ROE (e.g. ALL's ~45% off a thin post-buyback book).
# Cap the ROE used in calc_pb at this multiple of the COE (3.0 x 0.085 = 25.5%).
ROE_PB_CAP_MULT = 3.0
```

Replace `calc_pb` (currently ~lines 269-276) with:

```python
# -- P/B (justified, growth-adjusted) ------------------------------------------
def calc_pb(fin: dict) -> dict:
    """Justified P/B = (ROE - g) / (COE - g), the growth-adjusted Gordon form.

    COE is the leg's discount rate: fin['cost_of_equity'] when supplied (the
    FINANCIAL bucket sets FINANCIAL_COE in engine.evaluate), else DISCOUNT_RATE.
    g is bounded strictly below COE. At ROE == COE the multiple is exactly 1.0.
    The ROE input is capped at ROE_PB_CAP_MULT x COE so a distorted, unsustainable
    ROE (thin-book insurer artifact) can't run the multiple away."""
    bvps = fin.get("book_value_per_share")
    roe = fin.get("return_on_equity")
    if bvps is None or roe is None:
        return _null_result(False)
    coe = fin.get("cost_of_equity") or DISCOUNT_RATE
    roe = min(roe, ROE_PB_CAP_MULT * coe)
    g = min(TERMINAL_GROWTH, coe - 0.01)
    justified_pb = (roe - g) / (coe - g)
    fv = _apply_mos(bvps * max(justified_pb, 0.1))
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv,
            "weight": 0.0, "has_scenarios": False}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_models.py -k pb -v`
Expected: PASS (six new + two existing).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "feat(valuation): growth-adjusted, COE-aware justified P/B with ROE guard"
```

---

### Task 2: Gate `FINANCIAL_COE` into the book-value legs in `evaluate`

**Files:**
- Modify: `backend/valuation/engine.py` — `evaluate` (the top of the function, ~lines 137-140)
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `m.FINANCIAL_COE` (Task 1), `m.calc_pb`, `m.calc_rim`, `engine.build_scenarios`, `engine.classify` (all existing).
- Produces: `evaluate` sets `cost_of_equity = FINANCIAL_COE` on a copy of `fin` for FINANCIAL names, feeding both the P/B and RIM legs. Public signature unchanged.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_engine.py` (imports `engine` and `models as m` are already present in that file; add `import pytest` only if missing):

```python
def _bank_fin(**over):
    fin = {"ticker": "BNK", "company_name": "Test Bank",
           "sector": "Financial Services", "industry": "Banks - Diversified",
           "current_price": 100.0, "book_value_per_share": 100.0,
           "return_on_equity": 0.15, "eps_ttm": 15.0, "trailing_pe": 10.0}
    fin.update(over)
    return fin


def _dividend_fin(**over):
    fin = {"ticker": "DIV", "company_name": "Div Co",
           "sector": "Consumer Defensive", "industry": "Beverages - Non-Alcoholic",
           "current_price": 50.0, "book_value_per_share": 10.0,
           "return_on_equity": 0.30, "eps_ttm": 2.5, "trailing_pe": 20.0,
           "dividend_rate": 1.5, "dividend_yield": 0.03, "payout_ratio": 0.6,
           "fcf_ttm": 3.0e9, "shares_outstanding": 1e9, "net_debt": 0}
    fin.update(over)
    return fin


def test_evaluate_financial_discounts_book_legs_at_financial_coe():
    fin = _bank_fin()
    growth = engine.build_scenarios(fin)
    exp_pb = m.calc_pb({**fin, "cost_of_equity": m.FINANCIAL_COE})["fair_value"]
    exp_rim = m.calc_rim({**fin, "cost_of_equity": m.FINANCIAL_COE}, growth)["fair_value"]
    out = engine.evaluate(fin)
    assert out["stock_type"] == "FINANCIAL"
    bd = out["fair_value_breakdown"]
    assert bd["pb"]["fair_value"] == pytest.approx(round(exp_pb, 2))
    assert bd["rim"]["fair_value"] == pytest.approx(round(exp_rim, 2))


def test_evaluate_financial_lifts_book_legs_vs_flat_coe():
    # ROE 0.15 > COE -> the lower FINANCIAL_COE raises both book legs vs the flat 0.10.
    fin = _bank_fin()
    growth = engine.build_scenarios(fin)
    base_pb = m.calc_pb({**fin, "cost_of_equity": m.DISCOUNT_RATE})["fair_value"]
    base_rim = m.calc_rim({**fin, "cost_of_equity": m.DISCOUNT_RATE}, growth)["fair_value"]
    bd = engine.evaluate(fin)["fair_value_breakdown"]
    assert bd["pb"]["fair_value"] > round(base_pb, 2)
    assert bd["rim"]["fair_value"] > round(base_rim, 2)


def test_evaluate_does_not_mutate_caller_fin():
    fin = _bank_fin()
    engine.evaluate(fin)
    assert fin.get("cost_of_equity") is None


def test_evaluate_respects_preset_cost_of_equity():
    fin = _bank_fin(cost_of_equity=0.09)
    exp_pb = m.calc_pb({**fin})["fair_value"]   # uses the pre-set 0.09, not 0.085
    bd = engine.evaluate(fin)["fair_value_breakdown"]
    assert bd["pb"]["fair_value"] == pytest.approx(round(exp_pb, 2))


def test_evaluate_non_financial_pb_keeps_flat_coe():
    # A DIVIDEND name has a P/B leg (0.10 weight) but must NOT get FINANCIAL_COE.
    fin = _dividend_fin()
    out = engine.evaluate(fin)
    assert out["stock_type"] == "DIVIDEND"
    exp_pb = m.calc_pb({**fin})["fair_value"]   # default DISCOUNT_RATE
    assert out["fair_value_breakdown"]["pb"]["fair_value"] == pytest.approx(round(exp_pb, 2))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "financial or preset or mutate or non_financial" -v`
Expected: `test_evaluate_financial_discounts_book_legs_at_financial_coe` and `test_evaluate_financial_lifts_book_legs_vs_flat_coe` FAIL (legs still computed at flat 0.10). The mutate / preset / non-financial tests may already pass (they assert behavior the gate must preserve) — that is fine.

- [ ] **Step 3: Add the gate**

In `backend/valuation/engine.py`, inside `evaluate`, immediately after `stock_type = classification["stock_type"]` (~line 138) and before the `weights = {...}` line:

```python
    # Banks / lenders / insurers are financed below the flat 10% default; discount
    # their book-value legs (P/B + RIM) at FINANCIAL_COE. Copy so the caller's dict is
    # never mutated. extract_financials hardcodes cost_of_equity = DISCOUNT_RATE (0.10)
    # as the flat default, so treat None *or* that default as "unset" and override; a
    # genuine per-name COE (anything other than the flat default) is respected.
    if stock_type == "FINANCIAL":
        coe = fin.get("cost_of_equity")
        if coe is None or coe == m.DISCOUNT_RATE:
            fin = {**fin, "cost_of_equity": m.FINANCIAL_COE}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k "financial or preset or mutate or non_financial" -v`
Expected: PASS (all five).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(valuation): discount FINANCIAL book-value legs at FINANCIAL_COE"
```

---

### Task 3: End-to-end anchor + full-suite regression

**Files:**
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `engine.evaluate`, `m.FINANCIAL_COE`, `m.ROE_PB_CAP_MULT`, the `_bank_fin` fixture from Task 2.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_engine.py`:

```python
def test_evaluate_distorted_roe_bank_pb_leg_is_guarded():
    # ROE 0.45 (thin-book artifact, ALL-like): the P/B leg is clipped to the
    # ROE_PB_CAP_MULT x FINANCIAL_COE cap, strictly below the un-guarded value.
    fin = _bank_fin(return_on_equity=0.45, eps_ttm=45.0)
    guarded = engine.evaluate(fin)["fair_value_breakdown"]["pb"]["fair_value"]
    g = min(m.TERMINAL_GROWTH, m.FINANCIAL_COE - 0.01)
    bvps = fin["book_value_per_share"]
    capped_pb = (m.ROE_PB_CAP_MULT * m.FINANCIAL_COE - g) / (m.FINANCIAL_COE - g)
    unguarded_pb = (0.45 - g) / (m.FINANCIAL_COE - g)
    assert guarded == pytest.approx(round(bvps * capped_pb * m.MOS, 2))
    assert guarded < round(bvps * unguarded_pb * m.MOS, 2)
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/test_engine.py::test_evaluate_distorted_roe_bank_pb_leg_is_guarded -v`
Expected: PASS (Tasks 1-2 already implement the guard end to end). If it fails, the guard or the gate is wired wrong — fix before continuing.

- [ ] **Step 3: Run the full backend test suite**

Run: `python -m pytest -q`
Expected: all tests PASS — no regressions in `test_models.py`, `test_engine.py`, `test_engine_run.py`, `test_classifier.py`, or the screener suites. The two pre-existing `test_pb_*` tests must stay green (the growth form gives exactly P/B = 1.0 at ROE = COE, and the 0.1 floor is unchanged). If any previously-green test now fails, stop and reconcile.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_engine.py
git commit -m "test(valuation): e2e guard for FINANCIAL COE + distorted-ROE P/B cap"
```

---

## Notes for the implementer

- **Why the two existing `calc_pb` tests stay green:** `test_pb_justified_is_exact` (ROE 0.10, no COE → COE 0.10) gives `(0.10−0.03)/(0.10−0.03) = 1.0 → 9.0`; `test_pb_floor_justified_pb_at_0_1` (ROE 0.0) gives a negative multiple that the unchanged `max(…, 0.1)` floor clamps to `0.9`. Do not edit those fixtures.
- **RIM needs no code change** — it already reads `fin.get("cost_of_equity") or 0.10` (models.py line 285). The Task 2 gate is what feeds it 0.085. RIM's internal `roe = eps/bvps` is deliberately **not** ROE-guarded here; if a thin-book name later overshoots via RIM, that's a separate follow-up.
- **DIVIDEND names** keep the flat 0.10 (the gate is FINANCIAL-only) but do pick up the growth-adjusted P/B *form* at that 0.10 — a negligible move on their 0.10-weight P/B leg (KO ≈ flat, VZ ≈ +2%). This is expected and acceptable.
- **Live-data expectations (context, NOT asserted — the unit/e2e tests encode the mechanism deterministically without the network):** combined COE-0.085 + growth-P/B + ROE guard re-rates the FINANCIAL bucket:
  - JPM $242 → **$294** (−30% → −15% vs price); healthy banks lift ~+13–20%: BAC −17%, WFC −12%, USB −13%, PNC −19%, GS −27%, MS −34%, MET −27%.
  - Sub-10%-ROE names rise *modestly* (the COE lift outweighs the growth-P/B markdown): C +13.5%, AIG +14.7%, SOFI +11.1% — none flip sign or drop to "declined".
  - The ROE guard tames the artifacts: **ALL +139% → +85%** vs price, AXP clipped to −42%. SYF (21.8% ROE) is under the cap and keeps its +54% (a real high-ROE lender, correctly flagged rich).
  - **COF stays broken** (−97%): its 3.3% ROE is a bad *input* (Discover-acquisition book inflation), which no discount-rate change fixes — out of scope.
  - No name that was "undervalued vs price" at baseline flips to "overvalued" or vice-versa in a way that isn't already directionally present.
- **Ordering safety:** Task 1 is self-contained. Task 2 depends on Task 1 (`FINANCIAL_COE`). Task 3 depends on both.
- **Residual, out of scope:** even fully re-rated, GS/MS/AXP still read −27% to −42% — that gap lives in the P/E leg (capped at trailing, 0.20 weight) and RIM's ROE input, not in COE/P/B. A separate investigation if those names matter.
