# CONGLOMERATE Removal + NAV Double-Count Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the two-name CONGLOMERATE valuation tier, remove the orphaned `sotp` dead code, and fix `calc_nav`'s leverage double-count.

**Architecture:** Three independent changes in the pure valuation core. Change 1 deletes a classifier tier so HON→DIVIDEND and MMM→MID_CAP. Change 2 removes the now-unreachable `sotp` computation (keeping the blank Sheets column to avoid a schema migration). Change 3 corrects `calc_nav` from `bvps − net_debt/share` to `bvps`, which re-rates ASSET_HEAVY/CYCLICAL names but never touches HON/MMM.

**Tech Stack:** Python 3.14, pytest (`asyncio_mode=auto`). All commands run from `backend/`.

## Global Constraints

- Run all `pytest` commands from the `backend/` directory.
- Python interpreter: `C:/Users/f_lub/AppData/Local/Python/bin/python3.exe` (or `python3` if on PATH from `backend/`).
- MOS factor is 0.90 (`_apply_mos(x) == x * 0.90`) — used verbatim in NAV test expectations.
- `ALL_METHODS` and every `_TYPE_WEIGHTS` tier dict MUST carry the same method-id key set: `engine.evaluate` does `classification["method_weights"][mid]` for every `mid in ALL_METHODS`, so a key in one but not the other is a `KeyError`. When removing `"sotp"`, remove it from BOTH in the same commit.
- Do NOT modify `services/sheets.py` or `tests/test_sheets_row.py` — the blank SOTP column stays (chosen in the spec to avoid a persisted-schema migration).
- Do NOT change any method weights beyond dropping the dead `"sotp"` key.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `backend/valuation/classifier.py` | stock-type tiers + method weights | Remove CONGLOMERATE rule, keywords, weights entry; drop `"sotp"` key from all tiers |
| `backend/valuation/models.py` | leg math | Remove `calc_sotp`; drop `"sotp"` from `ALL_METHODS`/`APPROX_METHODS`; fix `calc_nav` |
| `backend/valuation/engine.py` | pipeline dispatch | Remove `"sotp"` from `_SINGLE_VALUE_FN` |
| `backend/tests/test_classifier.py` | classifier tests | Remove 2 CONGLOMERATE tests; add HON/MMM/keyword reclassification tests; fix `sotp`-weight asserts |
| `backend/tests/test_models.py` | leg tests | Remove 3 `calc_sotp` tests; add non-zero-net-debt NAV test |
| `backend/tests/test_engine.py` | pipeline tests | Remove `test_evaluate_sotp_flagged_approx` |

---

## Task 1: Establish green baseline

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite and confirm it passes**

Run: `python3 -m pytest -q`
Expected: all tests PASS (the pre-change baseline). Record the count (e.g. "339 passed"). If anything fails, STOP — the baseline must be green before proceeding.

---

## Task 2: Delete the CONGLOMERATE tier

**Files:**
- Modify: `backend/valuation/classifier.py` (remove rule 3 block ~lines 117–121, `CONGLOMERATE_KEYWORDS` ~lines 3–10, `_TYPE_WEIGHTS["CONGLOMERATE"]` ~line 66)
- Test: `backend/tests/test_classifier.py`

**Interfaces:**
- Consumes: `classify(fin: dict) -> {"stock_type": str, "method_weights": dict}` (unchanged signature).
- Produces: `classify` no longer ever returns `"CONGLOMERATE"`; a `Conglomerates`-industry name now falls through to the normal rules.

- [ ] **Step 1: Replace the two positive CONGLOMERATE tests with reclassification tests**

In `backend/tests/test_classifier.py`, DELETE `test_conglomerate_industry` (lines ~21–23) and `test_conglomerate_keyword_in_summary` (lines ~26–28). Leave `test_subsidiaries_boilerplate_is_not_conglomerate` (it already asserts `GROWTH`). In their place add:

```python
def test_conglomerates_industry_no_longer_conglomerate_dividend():
    # HON-like: the old rule-3 "Conglomerates" industry no longer captures. A
    # mature payer falls through to DIVIDEND (yield > 2.5%, payout > 40%).
    fin = {
        "sector": "Industrials", "industry": "Conglomerates",
        "dividend_yield": 0.0414, "payout_ratio": 0.741,
        "revenue_growth": 0.024, "eps_ttm": 12.53,
    }
    assert classify(fin)["stock_type"] == "DIVIDEND"


def test_conglomerates_industry_no_longer_conglomerate_midcap():
    # MMM-like: yield 1.83% < 2.5% skips DIVIDEND, not cyclical, $88B < $100B -> MID_CAP.
    fin = {
        "sector": "Industrials", "industry": "Conglomerates",
        "dividend_yield": 0.0183, "payout_ratio": 0.572,
        "revenue_growth": 0.025, "eps_ttm": 5.19,
        "trailing_pe": 32.9, "market_cap": 88_000_000_000,
    }
    assert classify(fin)["stock_type"] == "MID_CAP"


def test_diversified_holding_keyword_no_longer_conglomerate():
    # The old summary keyword ("diversified holding company") no longer triggers
    # CONGLOMERATE; the name falls through to the size default.
    fin = {
        "sector": "Industrials",
        "long_business_summary": "A diversified holding company.",
        "eps_ttm": 5.0, "market_cap": 20_000_000_000,
    }
    assert classify(fin)["stock_type"] == "MID_CAP"
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m pytest tests/test_classifier.py::test_conglomerates_industry_no_longer_conglomerate_dividend tests/test_classifier.py::test_conglomerates_industry_no_longer_conglomerate_midcap tests/test_classifier.py::test_diversified_holding_keyword_no_longer_conglomerate -v`
Expected: all three FAIL — `classify` currently returns `"CONGLOMERATE"` (via `industry == "Conglomerates"` or the summary keyword) instead of `DIVIDEND`/`MID_CAP`.

- [ ] **Step 3: Delete the CONGLOMERATE rule, keywords, and weights**

In `backend/valuation/classifier.py`:

a. Remove the `CONGLOMERATE_KEYWORDS` list (the whole block, currently lines ~3–10 including its leading comment).

b. Remove the classifier rule-3 block:

```python
    # 3. Conglomerate
    is_conglomerate_industry = "conglomerate" in industry or "diversified" in industry
    has_conglomerate_keywords = any(kw in summary for kw in CONGLOMERATE_KEYWORDS)
    if is_conglomerate_industry or has_conglomerate_keywords:
        return "CONGLOMERATE"
```

c. Remove the `"CONGLOMERATE": {...}` line from `_TYPE_WEIGHTS` (line ~66) and the two-line explanatory comment above `EARLY_GROWTH` that references SOTP re-admission only if it pertains to CONGLOMERATE — leave the EARLY_GROWTH comment intact (it explains that tier's own zeroing).

d. Renumber the downstream rule comments: `# 4. Early growth` → `# 3. Early growth`, `# 5. Growth` → `# 4. Growth`, `# 6. Dividend` → `# 5. Dividend`, `# 7. Cyclical` → `# 6. Cyclical`, `# 8. Size-based default` → `# 7. Size-based default`.

- [ ] **Step 4: Run the classifier suite to verify green**

Run: `python3 -m pytest tests/test_classifier.py -v`
Expected: PASS, including the three new tests. No test references `"CONGLOMERATE"` anymore.

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/classifier.py backend/tests/test_classifier.py
git commit -m "$(cat <<'EOF'
refactor(classifier): delete CONGLOMERATE tier

HON->DIVIDEND, MMM->MID_CAP. The 2-name tier's value came from a
broken NAV leg and a whole-company-EV/EBITDA SOTP misnomer; the
names value defensibly on their natural tiers' DCF+EV/EBITDA+P/E.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01X5y2E5fcfQn5dpsEa7SzUV
EOF
)"
```

---

## Task 3: Remove orphaned `sotp` dead code

**Files:**
- Modify: `backend/valuation/models.py` (remove `calc_sotp` ~lines 561–576; `"sotp"` from `ALL_METHODS` line ~128 and `APPROX_METHODS` line ~130)
- Modify: `backend/valuation/engine.py` (`_SINGLE_VALUE_FN` line ~113)
- Modify: `backend/valuation/classifier.py` (`"sotp": 0.00` key in every remaining `_TYPE_WEIGHTS` dict)
- Test: `backend/tests/test_models.py`, `backend/tests/test_engine.py`, `backend/tests/test_classifier.py`

**Interfaces:**
- Consumes: `ALL_METHODS: list[str]`, `_TYPE_WEIGHTS: dict[str, dict[str, float]]`.
- Produces: neither `ALL_METHODS` nor any tier dict contains `"sotp"`; `calc_sotp` no longer exists. `services/sheets.py` still lists `"sotp"` in `_MODEL_COLS` (blank column) — leave it.

- [ ] **Step 1: Remove the sotp tests that pin the deleted function/behavior**

In `backend/tests/test_models.py`, DELETE `test_sotp_null_on_nonpositive_ebitda`, `test_sotp_null_on_nonpositive_multiple`, and `test_sotp_positive_ebitda_still_values` (lines ~82–103).

In `backend/tests/test_engine.py`, DELETE `test_evaluate_sotp_flagged_approx` (lines ~188–193).

- [ ] **Step 2: Update the `sotp`-weight assertions to expect the key is absent**

In `backend/tests/test_classifier.py`, `test_early_growth_weights_no_sotp` — replace its two `w["sotp"]` assertions so the test asserts the key is gone (keep the dcf/ev_sales checks):

```python
def test_early_growth_weights_no_sotp():
    # SOTP was removed entirely (dead code). EARLY_GROWTH's dcf/ev_sales still carry
    # the tier at the redistributed ratio.
    res = classify({"sector": "Technology", "revenue_growth": 0.35, "eps_ttm": -1.2,
                    "ebitda_ttm": 10})
    w = res["method_weights"]
    assert "sotp" not in w
    assert w["dcf"]["weight"] == pytest.approx(0.4667, abs=1e-4)
    assert w["ev_sales"]["weight"] == pytest.approx(0.5333, abs=1e-4)
```

In the same file, `test_mid_cap_weights_shape` — replace line ~123 `assert res["method_weights"]["sotp"]["weight"] == 0.0` with:

```python
    assert "sotp" not in res["method_weights"]
```

- [ ] **Step 3: Run the edited tests to verify they fail**

Run: `python3 -m pytest tests/test_classifier.py::test_early_growth_weights_no_sotp tests/test_classifier.py::test_mid_cap_weights_shape -v`
Expected: both FAIL — `classify` still emits a `"sotp"` key (every `_TYPE_WEIGHTS` tier still has `"sotp": 0.00`), so `"sotp" not in w` is False.

- [ ] **Step 4: Remove the `sotp` code**

a. In `backend/valuation/models.py`, delete the entire `calc_sotp` function and its `# -- SOTP ...` header comment (lines ~561–577).

b. In `backend/valuation/models.py`, remove `"sotp"` from `ALL_METHODS`:

```python
ALL_METHODS = ["dcf", "fcfe", "ev_ebitda", "pe", "ev_sales", "ddm", "pb", "rim", "nav"]
```

c. In `backend/valuation/models.py`, remove `"sotp"` from `APPROX_METHODS`:

```python
APPROX_METHODS = {"nav"}
```

d. In `backend/valuation/engine.py`, remove the `"sotp"` entry from `_SINGLE_VALUE_FN`:

```python
_SINGLE_VALUE_FN = {"pb": m.calc_pb, "nav": m.calc_nav}
```

e. In `backend/valuation/classifier.py`, remove the `"sotp": 0.00,` key from EVERY remaining `_TYPE_WEIGHTS` dict (MEGA_CAP, LARGE_CAP, MID_CAP, DIVIDEND, GROWTH, EARLY_GROWTH, CYCLICAL, FINANCIAL, ASSET_HEAVY). Update the key-list comment on line ~51 to drop `sotp`.

- [ ] **Step 5: Run the full suite to verify green**

Run: `python3 -m pytest -q`
Expected: PASS. Confirm the count dropped by exactly the 4 removed tests plus any added (net vs Task 1 baseline). No `KeyError` from the `ALL_METHODS`/`method_weights` mismatch (both now lack `"sotp"`).

- [ ] **Step 6: Verify the blank SOTP Sheets column still round-trips**

Run: `python3 -m pytest tests/test_sheets_row.py -v`
Expected: PASS unchanged — `_MODEL_COLS` still contains `"sotp"`, so `model_value("sotp")` returns `""` and `len(_DB_HEADERS) == 16` holds.

- [ ] **Step 7: Commit**

```bash
git add backend/valuation/models.py backend/valuation/engine.py backend/valuation/classifier.py backend/tests/test_models.py backend/tests/test_engine.py backend/tests/test_classifier.py
git commit -m "$(cat <<'EOF'
refactor(valuation): remove orphaned sotp dead code

calc_sotp is unreachable now that CONGLOMERATE (its only 0.4-weight
home) is gone. Drop the function, its dispatch, and its ALL_METHODS /
_TYPE_WEIGHTS membership. The blank SOTP Sheets column is intentionally
kept to avoid a persisted-schema migration.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01X5y2E5fcfQn5dpsEa7SzUV
EOF
)"
```

---

## Task 4: Fix the `calc_nav` leverage double-count

**Files:**
- Modify: `backend/valuation/models.py` (`calc_nav`, line ~586)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `calc_nav(fin: dict) -> dict` (unchanged signature).
- Produces: `calc_nav` returns `_apply_mos(bvps)` — independent of `net_debt`.

- [ ] **Step 1: Add a non-zero-net-debt NAV test**

The existing `test_nav_is_exact` uses `net_debt=0`, so it can't detect the double-count. Add, in `backend/tests/test_models.py`, right after `test_nav_is_exact`:

```python
def test_nav_ignores_net_debt():
    # NAV = bvps * MOS. book_value_per_share is already equity (assets - all
    # liabilities, debt included), so net debt must NOT be subtracted again.
    # A net-debt name and a net-cash name with the same bvps get the same NAV.
    net_debt = {"book_value_per_share": 10.0, "net_debt": 5_000, "shares_outstanding": 1_000}
    net_cash = {"book_value_per_share": 10.0, "net_debt": -2_000, "shares_outstanding": 1_000}
    assert m.calc_nav(net_debt)["fair_value"] == pytest.approx(9.0)
    assert m.calc_nav(net_cash)["fair_value"] == pytest.approx(9.0)
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `python3 -m pytest tests/test_models.py::test_nav_ignores_net_debt -v`
Expected: FAIL — with the double-count, the net-debt case is `(10 − 5)*0.9 = 4.5` and the net-cash case is `(10 − (−2))*0.9 = 10.8`, neither equal to 9.0.

- [ ] **Step 3: Remove the net-debt term from `calc_nav`**

In `backend/valuation/models.py`, in `calc_nav`, delete the `net_debt = fin.get("net_debt") or 0` line and change the `fv` line:

```python
def calc_nav(fin: dict) -> dict:
    bvps = fin.get("book_value_per_share")
    shares = fin.get("shares_outstanding")
    if bvps is None or not shares:
        return _null_result(False)
    # book_value_per_share already nets all liabilities (equity = assets - liabilities),
    # so subtracting net debt again double-debits it (drove NAV negative for levered REITs).
    fv = _apply_mos(bvps)
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv, "weight": 0.0, "has_scenarios": False}
```

Note: `shares` is still read for the None/zero guard; keep it.

- [ ] **Step 4: Run the NAV tests to verify green**

Run: `python3 -m pytest tests/test_models.py::test_nav_is_exact tests/test_models.py::test_nav_ignores_net_debt -v`
Expected: both PASS (`test_nav_is_exact` still passes — its `net_debt=0` made the old and new formulas identical).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "$(cat <<'EOF'
fix(valuation): drop net-debt double-count in calc_nav

book_value_per_share already nets all liabilities, so bvps - net_debt/share
debited debt twice, driving NAV negative for levered REITs (SPG -$66, AMT
-$77) and crushing every ASSET_HEAVY composite at 0.45 weight. NAV = bvps * MOS.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01X5y2E5fcfQn5dpsEa7SzUV
EOF
)"
```

---

## Task 5: Full suite + live canary re-validation

**Files:** none (verification only)

- [ ] **Step 1: Run the entire suite**

Run: `python3 -m pytest -q`
Expected: all PASS.

- [ ] **Step 2: Re-validate the moved names live**

Run each and confirm the reclassification and FV land as designed:

```
python3 ".claude/skills/validating-agent-stock/validate_ticker.py" HON
python3 ".claude/skills/validating-agent-stock/validate_ticker.py" MMM
```
Expected: HON `stock_type == "DIVIDEND"`, FV ≈ $175 (was $91). MMM `stock_type == "MID_CAP"`, FV ≈ $131 (was $79). (Live feed drifts; confirm the tier and that FV is no longer the ~$80–91 artifact, not an exact number.)

- [ ] **Step 3: Re-validate the NAV-moved REIT canaries**

```
python3 ".claude/skills/validating-agent-stock/validate_ticker.py" O
python3 ".claude/skills/validating-agent-stock/validate_ticker.py" AMT
```
Expected: `stock_type == "ASSET_HEAVY"`; the `nav` leg in `fair_value_breakdown` is now positive (O nav ≈ $37.8, AMT nav ≈ $6.8), FV up materially from the pre-fix values (O ≈ $54, AMT ≈ $91).

- [ ] **Step 4: Confirm the byte-identical canaries did not move**

```
python3 ".claude/skills/validating-agent-stock/validate_ticker.py" IREN
python3 ".claude/skills/validating-agent-stock/validate_ticker.py" NBIS
python3 ".claude/skills/validating-agent-stock/validate_ticker.py" KLAC
```
Expected: unchanged tiers (IREN capex-reroute, NBIS EARLY_GROWTH, KLAC GROWTH) and FVs consistent with pre-change — none uses a `nav` or `sotp` leg, so the changes must not touch them.

- [ ] **Step 5: Update memory**

Update `C:\Users\f_lub\.claude\projects\C--Users-f-lub-proj-Agent-Stock\memory\conglomerate-valuation-gaps.md` from DEFERRED to DONE: record that the tier was deleted (HON→DIVIDEND, MMM→MID_CAP), `sotp` dead code removed (blank Sheets column kept), and the `calc_nav` double-count fixed (REITs +20–72%, high-P/B-REIT book-NAV problem still deferred). Add the one-line pointer update in `MEMORY.md`. Note which canaries were verified unmoved (IREN/NBIS/KLAC).

---

## Self-Review Notes

- **Spec coverage:** Change 1 → Task 2; Change 2 (code + kept-column) → Task 3 (+ Step 6 guards the blank column); Change 3 → Task 4; canary/deferred-scope validation → Task 5. All spec sections mapped.
- **ALL_METHODS/_TYPE_WEIGHTS sync:** Task 3 Step 4 removes `"sotp"` from both in one commit (global constraint), preventing the `engine.evaluate` `KeyError`.
- **Type consistency:** `calc_nav` / `classify` / `ALL_METHODS` names match across tasks. No new symbols introduced.
