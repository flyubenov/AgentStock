# Size Tiers, Market-P/E Swap, and Pre-Profit Guard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop crypto/data-center names being mis-classified FINANCIAL, give LARGE_CAP a real >$100B definition with a new MID_CAP default, swap the payout-based justified P/E for a capped market P/E, and add a pre-profit guard that declines deeply FCF-negative DCF-anchored companies.

**Architecture:** Four localized changes across three files. `classifier.py` gains a de-financialize keyword gate and a market-cap size split. `models.py` replaces `calc_pe` with a single-value capped-market-P/E model. `engine.py` re-wires P/E from the scenario map to the single-value map and adds a pre-profit early-return guard inside `evaluate`. No new files, no schema changes — `TickerResult` already carries `stock_type`, `status="failed"`, and `errors`.

**Tech Stack:** Python 3.14, pytest. FastAPI backend (untouched here). yfinance-sourced `extract_financials` dicts as model input.

## Global Constraints

- Python interpreter: `C:/Users/f_lub/AppData/Local/Python/bin/python3.exe` (bare `python` is not on PATH).
- Run all tests from the `backend/` directory. Canonical test command (steps abbreviate this as `pytest …`):
  `cd "C:/Users/f_lub/proj/Agent Stock/backend" && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest <args>`
- For live ticker scripts only: prefix `PYTHONPATH="C:/Users/f_lub/proj/Agent Stock/backend"` and `PYTHONIOENCODING=utf-8` (the console is cp1251 and chokes on non-ASCII).
- **Security:** never run `git add -A`/`git add .`; stage only the exact paths listed in each commit step. Never edit, stage, or commit `backend/.env` or `backend/credentials/`.
- End every commit message with: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Exact parameter values (copy verbatim): `MATURE_PE_CAP = 21.0`; LARGE_CAP cap threshold `> 100_000_000_000`; `FCF_MARGIN_FLOOR = -0.25`; `NON_FINANCIAL_KEYWORDS = ["bitcoin", "cryptocurrency", "crypto", "digital asset", "data center", "data centre", "mining", "miner"]`.

---

### Task 1: Capped market-P/E model + engine wiring

Replace the payout-dependent justified P/E with a capped market P/E (single-value, no growth term). Re-wire it from the scenario map to the single-value map.

**Files:**
- Modify: `backend/valuation/models.py` (add `MATURE_PE_CAP`; rewrite `calc_pe`; drop `"pe"` from `SCENARIO_MODELS`)
- Modify: `backend/valuation/engine.py` (move `"pe"` from `_SCENARIO_FN` to `_SINGLE_VALUE_FN`)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `m._apply_mos`, `m.MOS`, `m.SCENARIO_KEYS`, `m._null_result` (existing in `models.py`).
- Produces: `calc_pe(fin: dict) -> dict` — **new signature, no `growth` arg**. Returns the standard model dict: `{"scenarios": {opt/real/pess: fv}, "fair_value": fv, "weight": 0.0, "has_scenarios": False}`, or `_null_result(False)` when `eps_ttm <= 0`/missing or `trailing_pe <= 0`/missing. Module constant `MATURE_PE_CAP = 21.0`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_models.py`:

```python
def test_pe_caps_at_mature_multiple():
    # trailing P/E above the cap -> reverts to MATURE_PE_CAP
    fv = m.calc_pe({"eps_ttm": 10.0, "trailing_pe": 35.0})["fair_value"]
    assert fv == pytest.approx(10.0 * m.MATURE_PE_CAP * m.MOS)


def test_pe_keeps_trailing_below_cap():
    # trailing P/E below the cap -> never inflates, keep trailing
    fv = m.calc_pe({"eps_ttm": 10.0, "trailing_pe": 12.0})["fair_value"]
    assert fv == pytest.approx(10.0 * 12.0 * m.MOS)


def test_pe_null_on_nonpositive_eps():
    assert m.calc_pe({"eps_ttm": 0, "trailing_pe": 20.0})["fair_value"] is None
    assert m.calc_pe({"eps_ttm": -2.0, "trailing_pe": 20.0})["fair_value"] is None


def test_pe_null_on_missing_trailing_pe():
    assert m.calc_pe({"eps_ttm": 5.0, "trailing_pe": None})["fair_value"] is None
    assert m.calc_pe({"eps_ttm": 5.0, "trailing_pe": 0})["fair_value"] is None


def test_pe_is_single_value():
    r = m.calc_pe({"eps_ttm": 10.0, "trailing_pe": 18.0})
    assert r["has_scenarios"] is False
    assert r["scenarios"]["optimistic"] == r["scenarios"]["pessimistic"] == r["fair_value"]
```

Also fix the existing `test_missing_inputs_return_null` — its P/E line passes the now-removed `growth` arg and a `payout_ratio`. Replace that one line:

```python
    assert m.calc_pe({"eps_ttm": 0, "payout_ratio": 0.5}, GROWTH)["fair_value"] is None
```

with:

```python
    assert m.calc_pe({"eps_ttm": 0, "trailing_pe": 20})["fair_value"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: the five new tests FAIL (old `calc_pe` requires a `growth` positional arg → `TypeError`, and there is no `MATURE_PE_CAP`).

- [ ] **Step 3: Add `MATURE_PE_CAP` and rewrite `calc_pe` in `models.py`**

After `MATURE_EV_SALES = 2.0` (currently line 12) add:

```python
MATURE_PE_CAP = 21.0
```

Change `SCENARIO_MODELS` (currently line 15) — remove `"pe"`:

```python
SCENARIO_MODELS = {"dcf", "fcfe", "ev_ebitda", "ev_sales", "ddm", "rim"}
```

Replace the entire `calc_pe` function (currently lines 124-136, the `# -- P/E (justified)` block) with:

```python
# -- P/E (capped market multiple) ----------------------------------------------
def calc_pe(fin: dict) -> dict:
    eps = fin.get("eps_ttm")
    trailing_pe = fin.get("trailing_pe")
    if eps is None or eps <= 0 or trailing_pe is None or trailing_pe <= 0:
        return _null_result(False)
    target_pe = min(trailing_pe, MATURE_PE_CAP)
    fv = _apply_mos(eps * target_pe)
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv,
            "weight": 0.0, "has_scenarios": False}
```

- [ ] **Step 4: Re-wire `"pe"` in `engine.py`**

Change `_SINGLE_VALUE_FN` and `_SCENARIO_FN` (currently lines 11-19) to move `"pe"`:

```python
_SINGLE_VALUE_FN = {"pe": m.calc_pe, "pb": m.calc_pb, "sotp": m.calc_sotp, "nav": m.calc_nav}
_SCENARIO_FN = {
    "fcfe": m.calc_fcfe,
    "ev_ebitda": m.calc_ev_ebitda,
    "ev_sales": m.calc_ev_sales,
    "ddm": m.calc_ddm,
    "rim": m.calc_rim,
}
```

- [ ] **Step 5: Run the full suite to verify green**

Run: `pytest -v`
Expected: PASS. The new P/E tests pass; `test_evaluate_large_cap_blend` and `test_evaluate_price_vs_fair_value_pct` still pass (they assert `fair_value > 0` and the breakdown-consistency blend, both preserved since P/E remains in the breakdown as a single value).

- [ ] **Step 6: Commit**

```bash
git add backend/valuation/models.py backend/valuation/engine.py backend/tests/test_models.py
git commit -m "feat: replace justified P/E with capped market P/E (cap 21x)"
```

---

### Task 2: De-financialize classifier override

Stop a yfinance "Financial Services" tag from forcing FINANCIAL when the business summary marks it as a crypto-miner / data-center operator.

**Files:**
- Modify: `backend/valuation/classifier.py` (add `NON_FINANCIAL_KEYWORDS`; gate rule #1)
- Test: `backend/tests/test_classifier.py`

**Interfaces:**
- Consumes: `_detect_type`'s existing `sector` and `summary` locals (`summary` is the lowercased `long_business_summary`).
- Produces: module-level `NON_FINANCIAL_KEYWORDS: list[str]`. No signature changes; `classify`'s contract is unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_classifier.py`:

```python
def test_crypto_miner_not_financial():
    # yfinance tags bitcoin miners / data-center operators "Financial Services";
    # the de-financialize override must skip FINANCIAL for them.
    fin = {
        "sector": "Financial Services",
        "long_business_summary": (
            "The company operates data centers and bitcoin mining facilities, "
            "converting capacity to AI compute."
        ),
        "market_cap": 16_000_000_000,
    }
    assert classify(fin)["stock_type"] != "FINANCIAL"


def test_real_bank_still_financial():
    fin = {
        "sector": "Financial Services",
        "long_business_summary": "A regional bank providing deposit and loan services.",
    }
    assert classify(fin)["stock_type"] == "FINANCIAL"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_classifier.py::test_crypto_miner_not_financial -v`
Expected: FAIL — currently returns `"FINANCIAL"` (the bare sector check matches).

- [ ] **Step 3: Add the keyword list and gate rule #1**

In `backend/valuation/classifier.py`, after the `CYCLICAL_SECTORS` definition (currently line 12) add:

```python
# Phrases that mark a yfinance "Financial Services" tag as a mis-classification:
# crypto miners and data-center operators are tagged Financial Services but are
# not balance-sheet / book-value businesses.
NON_FINANCIAL_KEYWORDS = [
    "bitcoin", "cryptocurrency", "crypto", "digital asset",
    "data center", "data centre", "mining", "miner",
]
```

Replace rule #1 in `_detect_type` (currently lines 51-53):

```python
    # 1. Financial
    if sector == "Financial Services" and not any(kw in summary for kw in NON_FINANCIAL_KEYWORDS):
        return "FINANCIAL"
```

- [ ] **Step 4: Run the suite to verify green**

Run: `pytest tests/test_classifier.py -v`
Expected: PASS — `test_crypto_miner_not_financial`, `test_real_bank_still_financial`, and all existing classifier tests (the existing `test_financial_sector_is_financial` fixture has no summary, so the keyword check is vacuously false → still FINANCIAL).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/classifier.py backend/tests/test_classifier.py
git commit -m "feat: de-financialize crypto/data-center names mis-tagged by yfinance"
```

---

### Task 3: Size-gated default (LARGE_CAP >$100B) + MID_CAP

Give LARGE_CAP a real market-cap definition and introduce the MID_CAP default. Redefine LARGE_CAP weights (drop EV/Sales + SOTP) and add MID_CAP weights.

**Files:**
- Modify: `backend/valuation/classifier.py` (`_TYPE_WEIGHTS` LARGE_CAP + new MID_CAP; rule #8)
- Test: `backend/tests/test_classifier.py`, `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `_detect_type`'s existing `market_cap` local (`fin.get("market_cap") or 0`).
- Produces: stock type `"MID_CAP"` with weights `dcf 0.45 / ev_ebitda 0.25 / pe 0.15 / ev_sales 0.15`; redefined `"LARGE_CAP"` weights `dcf 0.50 / ev_ebitda 0.35 / pe 0.15`. Both sum to 1.00.

- [ ] **Step 1: Write/adjust the failing tests**

In `backend/tests/test_classifier.py`, replace the existing `test_large_cap_default` (its fixture has no `market_cap`, which now resolves to MID_CAP) with these tests:

```python
def test_large_cap_default():
    fin = {"sector": "Technology", "revenue_growth": 0.05, "eps_ttm": 5.0,
           "dividend_yield": 0.005, "market_cap": 500_000_000_000}
    assert classify(fin)["stock_type"] == "LARGE_CAP"


def test_mid_cap_below_threshold():
    fin = {"sector": "Technology", "revenue_growth": 0.05, "eps_ttm": 5.0,
           "dividend_yield": 0.005, "market_cap": 20_000_000_000}
    assert classify(fin)["stock_type"] == "MID_CAP"


def test_missing_market_cap_defaults_mid_cap():
    fin = {"sector": "Technology", "revenue_growth": 0.05, "eps_ttm": 5.0,
           "dividend_yield": 0.005}
    assert classify(fin)["stock_type"] == "MID_CAP"


def test_mid_cap_weights_shape():
    res = classify({"sector": "Technology", "eps_ttm": 5.0, "market_cap": 20_000_000_000})
    assert res["method_weights"]["dcf"]["weight"] == 0.45
    assert res["method_weights"]["ev_sales"]["weight"] == 0.15
    assert res["method_weights"]["sotp"]["weight"] == 0.0
```

In `backend/tests/test_engine.py`, update the stale tail of `test_evaluate_large_cap_blend` — replace its last two lines (the `# LARGE_CAP weights both EV multiples` comment and the `assert not (...)`) with:

```python
    # LARGE_CAP weights only EV/EBITDA among the EV multiples (no EV/Sales)
    bd = result["fair_value_breakdown"]
    assert "ev_sales" not in bd
    assert "ev_ebitda" in bd
```

And add a MID_CAP blend test to `backend/tests/test_engine.py`:

```python
def test_evaluate_mid_cap_blend():
    # Same profile as the large-cap fixture but a $20B cap -> MID_CAP default.
    fin = _large_cap_fin(market_cap=20_000_000_000)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "MID_CAP"
    assert result["status"] == "completed"
    total_w = sum(b["weight"] for b in result["fair_value_breakdown"].values())
    assert total_w == pytest.approx(1.0)
    # MID_CAP keeps a small EV/Sales weight (distinct from LARGE_CAP)
    assert "ev_sales" in result["fair_value_breakdown"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_classifier.py::test_mid_cap_below_threshold tests/test_engine.py::test_evaluate_mid_cap_blend -v`
Expected: FAIL — `MID_CAP` is not a known type yet (`_TYPE_WEIGHTS[stock_type]` would `KeyError` once rule #8 returns it; before the rule change the classifier returns `LARGE_CAP`, so the assertions fail).

- [ ] **Step 3: Redefine LARGE_CAP and add MID_CAP weights**

In `backend/valuation/classifier.py`, replace the `"LARGE_CAP"` line in `_TYPE_WEIGHTS` (currently line 17) and add a `"MID_CAP"` line directly after it:

```python
    "LARGE_CAP":    {"dcf": 0.50, "fcfe": 0.00, "ev_ebitda": 0.35, "pe": 0.15, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.00},
    "MID_CAP":      {"dcf": 0.45, "fcfe": 0.00, "ev_ebitda": 0.25, "pe": 0.15, "ev_sales": 0.15, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.00},
```

- [ ] **Step 4: Replace rule #8 with the size gate**

Replace the final block of `_detect_type` (currently lines 81-82):

```python
    # 8. Size-based default
    if market_cap > 100_000_000_000:
        return "LARGE_CAP"
    return "MID_CAP"
```

- [ ] **Step 5: Run the full suite to verify green**

Run: `pytest -v`
Expected: PASS. New classifier and MID_CAP engine tests pass; `test_evaluate_large_cap_blend` passes with the updated EV-multiple assertions (the fixture's $3T cap keeps it LARGE_CAP).

- [ ] **Step 6: Commit**

```bash
git add backend/valuation/classifier.py backend/tests/test_classifier.py backend/tests/test_engine.py
git commit -m "feat: gate LARGE_CAP at \$100B, add MID_CAP default tier"
```

---

### Task 4: Pre-profit guard

Decline to value a DCF-anchored company that is deeply FCF-negative on a trailing basis; return a `failed` result typed `PRE_PROFIT`.

**Files:**
- Modify: `backend/valuation/engine.py` (add `FCF_MARGIN_FLOOR`; early-return guard in `evaluate`)
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `weights` (post-`pick_ev_multiple`), `fin.get("fcf_ttm")`, `fin.get("revenue_ttm")`, and the same result-dict shape `evaluate` already returns on its `"insufficient data"` failed path.
- Produces: module constant `FCF_MARGIN_FLOOR = -0.25`. On fire, `evaluate` returns `status="failed"`, `stock_type="PRE_PROFIT"`, `fair_value=None`, `price_vs_fair_value_pct=None`, `fair_value_breakdown={}`, `errors=["Negative free cash flow (pre-profit / heavy investment phase) — trailing financials don't support a reliable valuation"]`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_engine.py`:

```python
def test_evaluate_pre_profit_guard_fires():
    # Deeply FCF-negative, DCF-anchored (MID_CAP) -> declined as PRE_PROFIT.
    fin = _large_cap_fin(market_cap=16_000_000_000,
                         fcf_ttm=-1_130_000_000, revenue_ttm=757_000_000)
    result = engine.evaluate(fin)
    assert result["status"] == "failed"
    assert result["stock_type"] == "PRE_PROFIT"
    assert result["fair_value"] is None
    assert result["price_vs_fair_value_pct"] is None
    assert "Negative free cash flow" in result["errors"][0]


def test_evaluate_pre_profit_guard_not_fired_when_fcf_positive():
    fin = _large_cap_fin(market_cap=16_000_000_000)  # positive fcf_ttm
    result = engine.evaluate(fin)
    assert result["status"] == "completed"
    assert result["stock_type"] == "MID_CAP"


def test_evaluate_pre_profit_guard_skips_financial():
    # FINANCIAL has dcf weight 0, so the guard must not fire even when FCF<0.
    fin = _large_cap_fin(sector="Financial Services",
                         fcf_ttm=-1_000_000_000, revenue_ttm=500_000_000)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "FINANCIAL"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_engine.py::test_evaluate_pre_profit_guard_fires -v`
Expected: FAIL — with no guard, MID_CAP with negative FCF still runs models (DCF on negative FCF yields a value) and returns `status="completed"`, `stock_type="MID_CAP"`.

- [ ] **Step 3: Add the constant**

In `backend/valuation/engine.py`, after `SUSTAINABLE_CEIL = 0.039` (currently line 9) add:

```python
FCF_MARGIN_FLOOR = -0.25
```

- [ ] **Step 4: Insert the guard in `evaluate`**

In `evaluate`, immediately after `weights = pick_ev_multiple(weights, fin)` (currently line 72) and before `growth = build_scenarios(fin)`:

```python
    # Pre-profit guard: a DCF-anchored company burning cash on a trailing basis
    # cannot be valued reliably from trailing financials. Decline rather than
    # emit a misleading number.
    fcf_ttm = fin.get("fcf_ttm")
    revenue_ttm = fin.get("revenue_ttm")
    if (weights.get("dcf", 0) > 0 and fcf_ttm is not None and revenue_ttm
            and fcf_ttm / revenue_ttm < FCF_MARGIN_FLOOR):
        return {
            "ticker": fin.get("ticker") or "",
            "company_name": fin.get("company_name"),
            "current_price": fin.get("current_price"),
            "last_evaluated": None, "stock_type": "PRE_PROFIT",
            "fair_value": None, "price_vs_fair_value_pct": None,
            "fair_value_breakdown": {},
            "status": "failed",
            "errors": ["Negative free cash flow (pre-profit / heavy investment "
                       "phase) — trailing financials don't support a reliable valuation"],
        }
```

- [ ] **Step 5: Run the full suite to verify green**

Run: `pytest -v`
Expected: PASS — all three guard tests pass; the FINANCIAL case (dcf weight 0) bypasses the guard and completes on book-value models.

- [ ] **Step 6: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat: pre-profit guard returns PRE_PROFIT for deeply FCF-negative names"
```

---

### Task 5: Live re-validation (anchors + IREN)

Verify the global P/E swap didn't regress the spec-anchor tickers and that IREN now returns PRE_PROFIT. This task hits the network (yfinance); it has no unit-test deliverable but a concrete pass/fail script.

**Files:**
- Create (temporary, do not commit): `scratchpad/revalidate.py` under the session scratchpad directory.

**Interfaces:**
- Consumes: `valuation.engine.run` (async; fetches yfinance info + cashflow, returns a `TickerResult`).

- [ ] **Step 1: Write the validation script**

Create `C:/Users/f_lub/AppData/Local/Temp/claude/C--Users-f-lub-proj-Agent-Stock/cfe0d507-a709-4d95-b8c6-c0e9325cfa18/scratchpad/revalidate.py`:

```python
import asyncio
from valuation.engine import run

TICKERS = ["MSFT", "AMAT", "KLAC", "ABBV", "IREN"]


async def main():
    for t in TICKERS:
        r = await run(t)
        fv = "-" if r.fair_value is None else f"{r.fair_value:.2f}"
        print(f"{t:6} type={r.stock_type:12} status={r.status:9} fair={fv}")


asyncio.run(main())
```

- [ ] **Step 2: Run it**

Run:
```bash
cd "C:/Users/f_lub/proj/Agent Stock/backend" && \
PYTHONPATH="C:/Users/f_lub/proj/Agent Stock/backend" PYTHONIOENCODING=utf-8 \
"C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" \
"C:/Users/f_lub/AppData/Local/Temp/claude/C--Users-f-lub-proj-Agent-Stock/cfe0d507-a709-4d95-b8c6-c0e9325cfa18/scratchpad/revalidate.py"
```

Expected (qualitative — exact fair values move with live data):
- `IREN` → `type=PRE_PROFIT status=failed fair=-`.
- `MSFT`, `AMAT`, `KLAC` → `status=completed`, a positive fair value in the same broad range as before the change (the P/E leg now mean-reverts toward 21× but is only 15-ish% of the blend, so the composite should not swing wildly). MSFT stays a LARGE_CAP (>$100B); KLAC/AMAT classify as before.
- `ABBV` → `status=completed`, fair value near the ~$220 established when `SUSTAINABLE_CEIL` was locked (its growth-normalization path is untouched here).

If any anchor swings by more than ~15% from its pre-change value, stop and investigate the P/E leg before proceeding — do not "fix" by tuning `MATURE_PE_CAP` without confirming with the maintainer.

- [ ] **Step 3: Record the outcome**

No commit (the script lives in scratchpad and is not part of the repo). Report the printed table back to the maintainer as the validation result.

---

## Self-Review

**1. Spec coverage:**
- De-financialize override → Task 2. ✓
- Size-gated default (LARGE_CAP >$100B) + MID_CAP weights → Task 3. ✓
- Capped market-P/E swap + wiring (`SCENARIO_MODELS`, `_SCENARIO_FN`→`_SINGLE_VALUE_FN`) → Task 1. ✓
- Pre-profit guard (`FCF_MARGIN_FLOOR`, `PRE_PROFIT`) → Task 4. ✓
- IREN end-to-end + anchor re-validation → Task 5. ✓
- Test-impact items (P/E signature change, stale `test_evaluate_large_cap_blend` fold assertion, `test_large_cap_default` cap) → Tasks 1 and 3. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows full code and exact commands. ✓

**3. Type consistency:** `calc_pe(fin)` (1-arg) is defined in Task 1 and consumed by the Task 1 engine wiring; `MID_CAP`/`PRE_PROFIT` string types and the `FCF_MARGIN_FLOOR`/`MATURE_PE_CAP` constants are used consistently across tasks; the guard's returned dict matches `evaluate`'s existing failed-path shape and `TickerResult` fields. ✓

**Ordering note:** Task 1 must precede Task 4's full-suite run (the `_large_cap_fin` fixture's `trailing_pe=28` flows through the new single-value P/E). Tasks 2 and 3 both edit `classifier.py` but in disjoint regions (rule #1 / keyword list vs. `_TYPE_WEIGHTS` + rule #8); apply in listed order to avoid merge friction.
