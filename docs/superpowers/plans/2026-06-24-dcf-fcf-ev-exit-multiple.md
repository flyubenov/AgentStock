# DCF Real-FCF + EV Exit-Multiple Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make composite fair values realistic for high-quality mega-caps by sourcing the DCF base from real free cash flow, compressing the EV exit multiple toward a fundamentally-justified mature level, and lowering the optimistic growth ceiling — bringing MSFT from +129% down to ~−10%.

**Architecture:** Three independent, suite-green tasks against the existing `backend/valuation/` package and `backend/services/yahoo.py`. Task 1 adds EV exit-multiple compression in `models.py`. Task 2 simplifies the DCF base (always real FCF), deletes the capex→CFO rule, and lowers the optimistic growth cap. Task 3 wires real FCF from the cashflow statement into `engine.run`. The pure `evaluate(fin)` pipeline and model functions stay testable with static fixtures.

**Tech Stack:** Python 3 / FastAPI / pytest (backend), yfinance (free data).

## Global Constraints

These apply to every task. Values copied verbatim from the spec.

- **Constants (unchanged):** discount rate `0.10`, terminal growth `0.03`, horizon `10`, MoS `0.90`, `EV_EBITDA_CAP = 20.0`, `EV_SALES_CAP = 8.0`.
- **Mature-multiple factor:** `MATURE_MULTIPLE_FACTOR = (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE - TERMINAL_GROWTH)` (= 14.714…), computed from existing constants, never hard-coded.
- **EV/EBITDA exit compression:** `conversion = real_FCF / EBITDA`, clamped to `[EBITDA_CONV_FLOOR = 0.40, EBITDA_CONV_CAP = 0.65]`; `exit_multiple = min(current_multiple, EV_EBITDA_CAP, conversion × MATURE_MULTIPLE_FACTOR)`. Only compresses when FCF present and EBITDA > 0; else falls back to `min(current, EV_EBITDA_CAP)`.
- **EV/Sales exit compression:** `exit_multiple = min(current_multiple, EV_SALES_CAP, MATURE_EV_SALES = 2.0)` (fixed mature multiple — no conversion).
- **`min(current, …)` never inflates** a cheap stock — compression only ever lowers a premium multiple.
- **DCF base = `fin["fcf_ttm"]` always.** No capex-conditional logic; the capex→CFO rule is removed.
- **Real FCF priority:** (1) cashflow statement "Free Cash Flow" row, else (2) "Operating Cash Flow" + "Capital Expenditure" (capex is **negative** in the statement, so this is OCF − |capex|), else (3) the `info`-dict `freeCashflow` fallback.
- **Optimistic growth ceiling:** `min(base + 0.05, 0.20)` (was `0.25`). Base band `[0.02, 0.20]`, pessimistic floor `0.02`, offsets `+0.05 / −0.04` unchanged.
- **Growth stays constant per scenario** for all 10 explicit years; 3% only at terminal. No growth fade.
- **SOTP unchanged** — exit compression applies only to the 10-year-projected EV models (`calc_ev_ebitda`, `calc_ev_sales`).
- **Tests use static fixtures — no live yfinance calls.** Python interpreter in this environment: `C:/Users/f_lub/AppData/Local/Python/bin/python3.exe` (bare `python` is not on PATH). Run tests from the `backend/` directory.

## File Structure

- `backend/valuation/models.py` — Tasks 1 & 2: new constants + `_compressed_exit_multiple` helper; `calc_ev_ebitda` / `calc_ev_sales` compression; `calc_dcf` parameter removal.
- `backend/valuation/engine.py` — Task 2 & 3: delete `dcf_cashflow_base` + `CAPEX_CFO_GATE`; lower optimistic cap in `build_scenarios`; `evaluate` DCF call; `run` wires real FCF.
- `backend/services/yahoo.py` — Task 3: `fetch_ticker_cashflow`, `_fetch_cashflow_sync`, `real_fcf`.
- `backend/tests/test_models.py`, `test_engine.py`, `test_engine_run.py`, `test_yahoo_block.py` — updated/added tests per task.

---

## Task 1: EV exit-multiple compression (D3 + D4)

Self-contained in `models.py`. `calc_dcf`, `engine.py`, and the data layer are untouched, so the suite stays green. EV/EBITDA compresses using `fin["fcf_ttm"]` (the `info`-dict value until Task 3 wires in real FCF — interim behavior is fine).

**Files:**
- Modify: `backend/valuation/models.py` (constants block lines 3-8; add helper near line 37; `calc_ev_ebitda` lines 82-91; `calc_ev_sales` lines 95-104)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Produces: constants `MATURE_MULTIPLE_FACTOR`, `EBITDA_CONV_FLOOR = 0.40`, `EBITDA_CONV_CAP = 0.65`, `MATURE_EV_SALES = 2.0`; helper `_compressed_exit_multiple(current_mult, conversion, conv_lo, conv_hi) -> float`. `calc_ev_ebitda(fin, growth)` and `calc_ev_sales(fin, growth)` keep their signatures and return shape `{"scenarios","fair_value","weight","has_scenarios"}`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_models.py`:

```python
def test_ev_ebitda_exit_compressed_by_conversion():
    base = {"ebitda_ttm": 1_000_000, "ev_ebitda": 15.0, "net_debt": 0, "shares_outstanding": 100_000}
    uncompressed = m.calc_ev_ebitda(base, GROWTH)["fair_value"]                      # no fcf -> cap path, 15x
    compressed = m.calc_ev_ebitda({**base, "fcf_ttm": 400_000}, GROWTH)["fair_value"]  # conv 0.40 -> ~5.89x
    assert compressed < uncompressed


def test_ev_ebitda_compression_floors_conversion():
    base = {"ebitda_ttm": 1_000_000, "ev_ebitda": 15.0, "net_debt": 0, "shares_outstanding": 100_000}
    very_low = m.calc_ev_ebitda({**base, "fcf_ttm": 10_000}, GROWTH)["fair_value"]   # conv 0.01 -> floor 0.40
    at_floor = m.calc_ev_ebitda({**base, "fcf_ttm": 400_000}, GROWTH)["fair_value"]  # conv 0.40
    assert very_low == pytest.approx(at_floor)


def test_ev_ebitda_compression_never_inflates_cheap():
    base = {"ebitda_ttm": 1_000_000, "ev_ebitda": 5.0, "net_debt": 0, "shares_outstanding": 100_000}
    cheap = m.calc_ev_ebitda({**base, "fcf_ttm": 650_000}, GROWTH)["fair_value"]  # conv 0.65 -> 9.56x, min keeps 5x
    no_fcf = m.calc_ev_ebitda(base, GROWTH)["fair_value"]                          # cap path -> 5x
    assert cheap == pytest.approx(no_fcf)


def test_ev_sales_exit_compressed_to_mature():
    base = {"revenue_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    high = m.calc_ev_sales({**base, "ev_sales": 6.0}, GROWTH)["fair_value"]       # -> mature 2x
    at_mature = m.calc_ev_sales({**base, "ev_sales": 2.0}, GROWTH)["fair_value"]
    assert high == pytest.approx(at_mature)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest tests/test_models.py -k "compress or mature or floor or inflate" -v`
Expected: FAIL — `test_ev_ebitda_exit_compressed_by_conversion` fails (no compression yet, compressed == uncompressed), `test_ev_sales_exit_compressed_to_mature` fails (6× not yet compressed to 2×).

- [ ] **Step 3: Add the constants**

In `backend/valuation/models.py`, replace the constants block (lines 3-8):

```python
DISCOUNT_RATE = 0.10
TERMINAL_GROWTH = 0.03
HORIZON = 10
MOS = 0.90
EV_EBITDA_CAP = 20.0
EV_SALES_CAP = 8.0
```

with:

```python
DISCOUNT_RATE = 0.10
TERMINAL_GROWTH = 0.03
HORIZON = 10
MOS = 0.90
EV_EBITDA_CAP = 20.0
EV_SALES_CAP = 8.0
MATURE_MULTIPLE_FACTOR = (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE - TERMINAL_GROWTH)  # = 14.714...
EBITDA_CONV_FLOOR = 0.40
EBITDA_CONV_CAP = 0.65
MATURE_EV_SALES = 2.0
```

- [ ] **Step 4: Add the `_compressed_exit_multiple` helper**

In `backend/valuation/models.py`, after `_null_result` (after line 36), add:

```python
def _compressed_exit_multiple(current_mult: float, conversion: float, conv_lo: float, conv_hi: float) -> float:
    """Compress the exit multiple toward a fundamentally-justified mature level:
    justified = clamp(conversion, lo, hi) * MATURE_MULTIPLE_FACTOR. Never inflates —
    returns min(current_mult, justified)."""
    conv = max(conv_lo, min(conversion, conv_hi))
    return min(current_mult, conv * MATURE_MULTIPLE_FACTOR)
```

- [ ] **Step 5: Compress the EV/EBITDA exit multiple**

In `backend/valuation/models.py`, replace `calc_ev_ebitda` (lines 82-91):

```python
def calc_ev_ebitda(fin: dict, growth: dict) -> dict:
    ebitda = fin.get("ebitda_ttm")
    multiple = fin.get("ev_ebitda")
    shares = fin.get("shares_outstanding")
    if ebitda is None or multiple is None or not shares:
        return _null_result(True)
    multiple = min(multiple, EV_EBITDA_CAP)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_ev_multiple(ebitda, growth[k], multiple, net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}
```

with:

```python
def calc_ev_ebitda(fin: dict, growth: dict) -> dict:
    ebitda = fin.get("ebitda_ttm")
    multiple = fin.get("ev_ebitda")
    shares = fin.get("shares_outstanding")
    if ebitda is None or multiple is None or not shares:
        return _null_result(True)
    multiple = min(multiple, EV_EBITDA_CAP)
    fcf = fin.get("fcf_ttm")
    if fcf is not None and ebitda > 0:
        conversion = fcf / ebitda
        multiple = _compressed_exit_multiple(multiple, conversion, EBITDA_CONV_FLOOR, EBITDA_CONV_CAP)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_ev_multiple(ebitda, growth[k], multiple, net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}
```

- [ ] **Step 6: Compress the EV/Sales exit multiple to the mature level**

In `backend/valuation/models.py`, in `calc_ev_sales` (line 101), replace:

```python
    multiple = min(multiple, EV_SALES_CAP)
```

with:

```python
    multiple = min(multiple, EV_SALES_CAP, MATURE_EV_SALES)
```

- [ ] **Step 7: Run the new tests and the full models suite**

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest tests/test_models.py -v`
Expected: PASS — the four new tests pass; the existing `test_ev_ebitda_multiple_is_capped` (fixture has no `fcf_ttm` → fallback cap path) and `test_ev_sales_multiple_is_capped` (both 20× and 8× now collapse to mature 2×, so the equality assertion still holds) still pass.

- [ ] **Step 8: Run the full backend suite (no regressions)**

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest -q`
Expected: PASS — `test_engine.py::test_evaluate_large_cap_blend` and friends still pass (they assert structure/positivity, not specific EV values).

- [ ] **Step 9: Commit**

```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "feat: compress EV/EBITDA and EV/Sales exit multiples toward mature levels"
```

---

## Task 2: DCF base simplification + optimistic cap + remove capex rule (D1 + D5)

`calc_dcf` drops its `cashflow_base` parameter, which forces the `engine.evaluate` call-site change in the same task; the capex→CFO rule and its tests are deleted, and the optimistic growth ceiling drops to 20%. All in one task so the suite ends green.

**Files:**
- Modify: `backend/valuation/models.py` (`calc_dcf` lines 57-64)
- Modify: `backend/valuation/engine.py` (`CAPEX_CFO_GATE` line 9; `build_scenarios` line 27; `dcf_cashflow_base` lines 55-63; `evaluate` lines 73 & 81)
- Test: `backend/tests/test_models.py`, `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `calc_ev_ebitda` / `calc_ev_sales` from Task 1 (unchanged here).
- Produces: `calc_dcf(fin, growth) -> dict` (no `cashflow_base` param). `engine.dcf_cashflow_base` and `engine.CAPEX_CFO_GATE` no longer exist. `engine.build_scenarios(fin)` returns optimistic capped at 0.20.

- [ ] **Step 1: Update the failing/changed tests**

In `backend/tests/test_models.py`, **delete** `test_dcf_uses_cashflow_base_override` (lines 55-59).

In `backend/tests/test_engine.py`, **delete** the three capex tests `test_dcf_cashflow_base_swaps_to_cfo_above_gate`, `test_dcf_cashflow_base_keeps_fcf_below_gate`, `test_dcf_cashflow_base_defaults_to_fcf_when_cfo_missing` (lines 59-72), and replace `test_build_scenarios_capped` (lines 22-26) with:

```python
def test_build_scenarios_capped():
    s = engine.build_scenarios({"earnings_growth": 0.56, "revenue_growth": 0.10})
    assert s["realistic"] == 0.20             # base capped at 0.20
    assert s["optimistic"] == pytest.approx(0.20)   # optimistic ceiling now 20%
    assert s["pessimistic"] == pytest.approx(0.16)
```

- [ ] **Step 2: Run the changed tests to verify they fail**

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest tests/test_engine.py::test_build_scenarios_capped -v`
Expected: FAIL — optimistic is currently `0.25`, assertion expects `0.20`.

- [ ] **Step 3: Drop the `cashflow_base` parameter from `calc_dcf`**

In `backend/valuation/models.py`, replace `calc_dcf` (lines 57-64):

```python
def calc_dcf(fin: dict, growth: dict, cashflow_base: float | None = None) -> dict:
    base = cashflow_base if cashflow_base is not None else fin.get("fcf_ttm")
    shares = fin.get("shares_outstanding")
    if base is None or not shares:
        return _null_result(True)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_dcf_equity(base, growth[k], net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}
```

with:

```python
def calc_dcf(fin: dict, growth: dict) -> dict:
    base = fin.get("fcf_ttm")
    shares = fin.get("shares_outstanding")
    if base is None or not shares:
        return _null_result(True)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_dcf_equity(base, growth[k], net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}
```

- [ ] **Step 4: Lower the optimistic growth ceiling**

In `backend/valuation/engine.py`, in `build_scenarios` (line 27), replace:

```python
        "optimistic": min(base + 0.05, 0.25),
```

with:

```python
        "optimistic": min(base + 0.05, 0.20),
```

- [ ] **Step 5: Delete the capex→CFO rule**

In `backend/valuation/engine.py`, delete the `CAPEX_CFO_GATE = 0.50` constant (line 9), and delete the entire `dcf_cashflow_base` function (lines 55-63):

```python
def dcf_cashflow_base(fin: dict) -> float | None:
    """Decision #6: use CFO instead of FCF for the DCF base when capex is huge."""
    fcf = fin.get("fcf_ttm")
    cfo = fin.get("operating_cashflow")
    if cfo is not None and fcf is not None and cfo > 0:
        capex = cfo - fcf
        if capex / cfo > CAPEX_CFO_GATE:
            return cfo
    return fcf
```

(Leave `EBITDA_MARGIN_FLOOR = 0.08` — still used by `pick_ev_multiple`.)

- [ ] **Step 6: Update `evaluate` to call `calc_dcf` without the override**

In `backend/valuation/engine.py`, in `evaluate`, delete the line:

```python
    cf_base = dcf_cashflow_base(fin)
```

and replace the DCF branch:

```python
        if mid == "dcf":
            r = m.calc_dcf(fin, growth, cashflow_base=cf_base)
```

with:

```python
        if mid == "dcf":
            r = m.calc_dcf(fin, growth)
```

- [ ] **Step 7: Run the full backend suite**

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest -q`
Expected: PASS — no references to `dcf_cashflow_base`, `CAPEX_CFO_GATE`, or the `cashflow_base` param remain; `test_build_scenarios_capped` passes with the 0.20 ceiling.

- [ ] **Step 8: Commit**

```bash
git add backend/valuation/models.py backend/valuation/engine.py backend/tests/test_models.py backend/tests/test_engine.py
git commit -m "feat: DCF base = real FCF only; remove capex rule; optimistic cap 20%"
```

---

## Task 3: Real FCF from the cashflow statement (D2)

Wire the real free cash flow into `fin["fcf_ttm"]` before `evaluate` runs, via a second cached yfinance fetch. `evaluate` and the model functions stay pure.

**Files:**
- Modify: `backend/services/yahoo.py` (add `_fetch_cashflow_sync`, `fetch_ticker_cashflow`, `real_fcf` after `_fetch_sync`)
- Modify: `backend/valuation/engine.py` (import line 5; `run` lines 135-146)
- Test: `backend/tests/test_yahoo_block.py`, `backend/tests/test_engine_run.py`

**Interfaces:**
- Consumes: `engine.evaluate` and `engine.run` from prior tasks.
- Produces: `fetch_ticker_cashflow(ticker: str) -> dict | None` (async), `real_fcf(cashflow: dict | None, info_fcf: float | None) -> float | None`. `engine.run` sets `fin["fcf_ttm"]` to the real FCF when available.

- [ ] **Step 1: Write the failing `real_fcf` tests**

Append to `backend/tests/test_yahoo_block.py`:

```python
from services.yahoo import real_fcf


def test_real_fcf_prefers_statement_fcf():
    cf = {"free_cash_flow": 71.0, "operating_cash_flow": 136.0, "capital_expenditure": -65.0}
    assert real_fcf(cf, 37.0) == 71.0


def test_real_fcf_falls_back_to_ocf_plus_capex():
    cf = {"free_cash_flow": None, "operating_cash_flow": 136.0, "capital_expenditure": -65.0}
    assert real_fcf(cf, 37.0) == pytest.approx(71.0)  # 136 + (-65)


def test_real_fcf_falls_back_to_info_when_no_cashflow():
    assert real_fcf(None, 37.0) == 37.0
    empty = {"free_cash_flow": None, "operating_cash_flow": None, "capital_expenditure": None}
    assert real_fcf(empty, 37.0) == 37.0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest tests/test_yahoo_block.py -k real_fcf -v`
Expected: FAIL — `ImportError: cannot import name 'real_fcf'`.

- [ ] **Step 3: Add the cashflow fetch + `real_fcf` to `yahoo.py`**

In `backend/services/yahoo.py`, after `_fetch_sync` (after line 42, before `extract_financials`), add:

```python
@lru_cache(maxsize=256)
def _fetch_cashflow_sync(ticker: str) -> dict | None:
    """Fetch the cashflow statement and extract the rows we need. Cached per ticker.
    Returns None (never raises) when the statement is unavailable."""
    for attempt in range(_RATE_LIMIT_RETRIES):
        try:
            cf = yf.Ticker(ticker).cashflow
            if cf is None or cf.empty:
                return None

            def _row(label: str) -> float | None:
                try:
                    val = cf.loc[label].iloc[0]
                except (KeyError, IndexError):
                    return None
                return float(val) if val == val else None  # NaN -> None

            return {
                "free_cash_flow": _row("Free Cash Flow"),
                "operating_cash_flow": _row("Operating Cash Flow"),
                "capital_expenditure": _row("Capital Expenditure"),
            }
        except Exception as e:
            is_rate_limit = (
                (_YFRateLimitError and isinstance(e, _YFRateLimitError))
                or "rate" in str(e).lower()
                or "too many" in str(e).lower()
            )
            if is_rate_limit and attempt < _RATE_LIMIT_RETRIES - 1:
                time.sleep(_RATE_LIMIT_BACKOFF * (attempt + 1))
                continue
            return None
    return None


async def fetch_ticker_cashflow(ticker: str) -> dict | None:
    """Async wrapper around _fetch_cashflow_sync."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_cashflow_sync, ticker.upper())


def real_fcf(cashflow: dict | None, info_fcf: float | None) -> float | None:
    """Real FCF priority: statement 'Free Cash Flow', else OCF + (negative) capex,
    else the info-dict free cash flow fallback."""
    if cashflow:
        fcf = cashflow.get("free_cash_flow")
        if fcf is not None:
            return fcf
        ocf = cashflow.get("operating_cash_flow")
        capex = cashflow.get("capital_expenditure")
        if ocf is not None and capex is not None:
            return ocf + capex  # capex is negative in the statement
    return info_fcf
```

- [ ] **Step 4: Run the `real_fcf` tests**

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest tests/test_yahoo_block.py -k real_fcf -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Update the `engine.run` integration tests**

The existing two tests in `backend/tests/test_engine_run.py` patch only `fetch_ticker_info`; once `run` also calls `fetch_ticker_cashflow`, that would hit the network. Replace the file body below the `_INFO` fixture (lines 19-35) with:

```python
@pytest.mark.asyncio
async def test_run_returns_completed_ticker_result():
    with patch("valuation.engine.fetch_ticker_info", return_value=_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=None):
        result = await engine.run("AAPL")
    assert isinstance(result, TickerResult)
    assert result.status == "completed"
    assert result.stock_type == "LARGE_CAP"
    assert result.fair_value is not None
    assert result.last_evaluated is not None


@pytest.mark.asyncio
async def test_run_yfinance_failure_is_failed():
    with patch("valuation.engine.fetch_ticker_info", side_effect=ValueError("boom")):
        result = await engine.run("BADX")
    assert result.status == "failed"
    assert result.errors == ["yfinance data unavailable"]


@pytest.mark.asyncio
async def test_run_uses_real_fcf_from_cashflow():
    cf_low = {"free_cash_flow": 20_000_000_000, "operating_cash_flow": None, "capital_expenditure": None}
    with patch("valuation.engine.fetch_ticker_info", return_value=_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=None):
        baseline = (await engine.run("AAPL")).fair_value
    with patch("valuation.engine.fetch_ticker_info", return_value=_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=cf_low):
        lowered = (await engine.run("AAPL")).fair_value
    # real FCF (20B) is below the info-dict FCF (99B), so DCF + EV/EBITDA conversion drop
    assert lowered < baseline
```

- [ ] **Step 6: Run them to verify the new test fails**

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest tests/test_engine_run.py -v`
Expected: FAIL — `test_run_uses_real_fcf_from_cashflow` fails because `engine.run` does not yet consult `fetch_ticker_cashflow` (and the patch target `valuation.engine.fetch_ticker_cashflow` does not exist yet → AttributeError).

- [ ] **Step 7: Wire real FCF into `engine.run`**

In `backend/valuation/engine.py`, replace the import (line 5):

```python
from services.yahoo import fetch_ticker_info, extract_financials
```

with:

```python
from services.yahoo import fetch_ticker_info, extract_financials, fetch_ticker_cashflow, real_fcf
```

Then replace `run` (lines 135-146):

```python
async def run(ticker: str) -> TickerResult:
    """Async IO wrapper: fetch + extract + evaluate -> TickerResult."""
    try:
        info = await fetch_ticker_info(ticker)
    except Exception:
        return TickerResult(ticker=ticker.upper(), status="failed",
                            errors=["yfinance data unavailable"])
    fin = extract_financials(info)
    fin["ticker"] = fin.get("ticker") or ticker.upper()
    data = evaluate(fin)
    data["last_evaluated"] = datetime.now(timezone.utc).isoformat()
    return TickerResult(**data)
```

with:

```python
async def run(ticker: str) -> TickerResult:
    """Async IO wrapper: fetch info + cashflow, source real FCF, evaluate -> TickerResult."""
    try:
        info = await fetch_ticker_info(ticker)
    except Exception:
        return TickerResult(ticker=ticker.upper(), status="failed",
                            errors=["yfinance data unavailable"])
    fin = extract_financials(info)
    fin["ticker"] = fin.get("ticker") or ticker.upper()
    cashflow = await fetch_ticker_cashflow(ticker)
    rf = real_fcf(cashflow, fin.get("fcf_ttm"))
    if rf is not None:
        fin["fcf_ttm"] = rf
    data = evaluate(fin)
    data["last_evaluated"] = datetime.now(timezone.utc).isoformat()
    return TickerResult(**data)
```

- [ ] **Step 8: Run the full backend suite**

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest -q`
Expected: PASS — all tests including the three in `test_engine_run.py`.

- [ ] **Step 9: Confirm the app still imports**

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -c "import main; print('import OK')"`
Expected: prints `import OK`.

- [ ] **Step 10: Commit**

```bash
git add backend/services/yahoo.py backend/valuation/engine.py backend/tests/test_yahoo_block.py backend/tests/test_engine_run.py
git commit -m "feat: source DCF base from real FCF in the cashflow statement"
```

---

## Validation (manual, after Task 3 — not a unit test)

Confirm the end-to-end MSFT number against the spec's target. This makes a live yfinance call, so it is a one-off check, not part of the suite.

- [ ] **Run a live MSFT check**

Write `backend/_tmp_validate.py`:

```python
import asyncio
from valuation import engine


async def main():
    r = await engine.run("MSFT")
    print("MSFT  stock_type=%s  fair_value=$%.2f  price=$%s  gap=%s%%"
          % (r.stock_type, r.fair_value, r.current_price, r.price_vs_fair_value_pct))
    for mid, b in r.fair_value_breakdown.items():
        print("  %-10s w=%.2f fv=$%.2f" % (mid, b["weight"], b["fair_value"]))


asyncio.run(main())
```

Run: `cd backend && "C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" _tmp_validate.py; rm -f _tmp_validate.py`
Expected (approximately, subject to live data): composite fair value in the low-to-mid $300s and `gap` roughly in the −5% to −15% range (vs the old +129%), with DCF ~$400 and the EV/EBITDA leg compressed to a ~6× exit. Delete the temp file after.

---

## Self-Review

**Spec coverage:**
- D1 (delete capex→CFO rule) → Task 2 Steps 5-6.
- D2 (real FCF from cashflow statement) → Task 3 Steps 3, 7.
- D3 (EV/EBITDA company-specific exit compression) → Task 1 Steps 3-5.
- D4 (EV/Sales fixed mature exit) → Task 1 Steps 3, 6.
- D5 (optimistic ceiling 25%→20%) → Task 2 Step 4.
- "Growth stays constant / no fade" → no change made (verified: `_scenario_dcf_equity` already uses constant growth + 3% terminal).
- SOTP unchanged → not touched in any task.
- Edge cases (missing FCF, low/negative conversion floor, EBITDA ≤ 0, capex sign) → Task 1 Step 5 (FCF/EBITDA guards), Task 1 Step 4 (clamp), Task 3 Step 3 (`val == val` NaN guard, `ocf + capex` sign).
- Test plan (remove cashflow_base/ capex tests, update build_scenarios, add compression + real_fcf + integration tests) → Tasks 1-3 test steps.

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to" — every code step shows complete code; every test step has real assertions.

**Type consistency:** `MATURE_MULTIPLE_FACTOR`, `EBITDA_CONV_FLOOR`, `EBITDA_CONV_CAP`, `MATURE_EV_SALES`, and `_compressed_exit_multiple(current_mult, conversion, conv_lo, conv_hi)` are defined in Task 1 and used consistently. `calc_dcf(fin, growth)` (Task 2) matches its only call site `m.calc_dcf(fin, growth)` in `evaluate` (Task 2 Step 6). `fetch_ticker_cashflow` / `real_fcf` (Task 3 Step 3) match their imports and call sites in `engine.run` (Task 3 Step 7) and the patch targets in the tests (Task 3 Step 5).
