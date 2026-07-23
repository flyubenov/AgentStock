# Dual-Class Share-Count Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop per-share fair value being inflated for multi-class companies by sourcing the share-count denominator from `market_cap / price` when yfinance's `sharesOutstanding` under-reports it.

**Architecture:** Add one pure helper `_effective_shares(info, price)` in `backend/services/yahoo.py` that returns a fully-diluted count — adopting `market_cap / price` only when it exceeds the reported count by >3% (upward-only, gated), else keeping `sharesOutstanding`. Wire it into `extract_financials`. No valuation-leg or constant changes: this is a clean terminal rescale.

**Tech Stack:** Python 3.14, pytest (`asyncio_mode=auto`), yfinance. Run tests from `backend/`.

## Global Constraints

- Branch: `dual-class-share-count-fix` (off master `4d09516`). All work lands here.
- Correction is **upward-only**: never adopt a denominator smaller than the reported `sharesOutstanding`.
- Gate threshold is **3%** (`_SHARE_GATE_RATIO = 1.03`) — copied verbatim from the spec.
- **No changes** to any valuation leg, cap, fade, tier, or scenario constant. FV pipeline only; Quality/screener untouched.
- Spec: `docs/superpowers/specs/2026-07-23-dual-class-share-count-design.md`.

---

### Task 1: `_effective_shares` gated helper

**Files:**
- Modify: `backend/services/yahoo.py` (add module constant + helper above `extract_financials` at line 290)
- Test: `backend/tests/test_yahoo_block.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `_effective_shares(info: dict, price: float | None) -> float | None` — returns the fully-diluted share count. Task 2 imports and calls it inside `extract_financials`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_yahoo_block.py` (import `_effective_shares` alongside the existing `services.yahoo` imports at the top of the file):

```python
from services.yahoo import _effective_shares


def test_effective_shares_corrects_multi_class_upward():
    # KVYO-shape: sharesOutstanding is Class A only; marketCap capitalizes all classes.
    info = {"sharesOutstanding": 140_897_018, "marketCap": 4_821_398_016}
    result = _effective_shares(info, price=16.11)
    assert result == pytest.approx(4_821_398_016 / 16.11)  # ~299.3M, not 140.9M


def test_effective_shares_keeps_reported_within_tolerance():
    # Single-class: implied (1.02x) is inside the 3% gate -> keep reported.
    info = {"sharesOutstanding": 100_000_000, "marketCap": 102_000_000 * 100}
    result = _effective_shares(info, price=100.0)
    assert result == 100_000_000


def test_effective_shares_keeps_reported_when_marketcap_missing():
    info = {"sharesOutstanding": 100_000_000}
    assert _effective_shares(info, price=100.0) == 100_000_000


def test_effective_shares_keeps_reported_when_price_missing():
    info = {"sharesOutstanding": 100_000_000, "marketCap": 5_000_000_000}
    assert _effective_shares(info, price=None) == 100_000_000


def test_effective_shares_adopts_implied_when_reported_missing():
    info = {"sharesOutstanding": None, "marketCap": 5_000_000_000}
    assert _effective_shares(info, price=50.0) == pytest.approx(100_000_000)


def test_effective_shares_never_corrects_downward():
    # implied < reported -> keep reported (never introduce inflation).
    info = {"sharesOutstanding": 200_000_000, "marketCap": 5_000_000_000}
    assert _effective_shares(info, price=50.0) == 200_000_000  # implied 100M < 200M
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `pytest tests/test_yahoo_block.py -k effective_shares -v`
Expected: FAIL — `ImportError: cannot import name '_effective_shares'`.

- [ ] **Step 3: Write the helper and constant**

In `backend/services/yahoo.py`, immediately above `def extract_financials(info: dict) -> dict:` (currently line 290), add:

```python
# Below this divergence, market_cap/price and sharesOutstanding agree to rounding
# (single-class names <=0.1%); above it a hidden share class is present (PLTR ~4.2%;
# KVYO/GOOGL ~2.1x, where sharesOutstanding is the Class A float only). 3% clears
# intraday market_cap/price staleness and sits below the smallest real multi-class gap.
_SHARE_GATE_RATIO = 1.03


def _effective_shares(info: dict, price: float | None) -> float | None:
    """Fully-diluted share count for the per-share fair-value divide.

    yfinance's sharesOutstanding returns only one class for multi-class companies
    (typically the Class A float), while marketCap capitalizes every class. Dividing
    an absolute equity value by the single-class count inflates per-share FV by
    true_shares / reported_shares. Correct UPWARD ONLY and gated at _SHARE_GATE_RATIO:
    adopt market_cap/price when it exceeds the reported count beyond the gate; else
    keep the reported count (single-class names stay byte-identical). Falls back to
    the reported count whenever market_cap or price is unavailable.
    """
    reported = info.get("sharesOutstanding")
    market_cap = info.get("marketCap")
    if not market_cap or not price:
        return reported
    implied = market_cap / price
    if not reported or reported <= 0:
        return implied
    if implied > reported * _SHARE_GATE_RATIO:
        return implied
    return reported
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `backend/`): `pytest tests/test_yahoo_block.py -k effective_shares -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/services/yahoo.py backend/tests/test_yahoo_block.py
git commit -m "feat(valuation): gated upward-only dual-class share-count helper"
```

---

### Task 2: Wire `_effective_shares` into `extract_financials`

**Files:**
- Modify: `backend/services/yahoo.py` (the `shares_outstanding` line in the `extract_financials` return dict, currently line 302)
- Test: `backend/tests/test_yahoo_block.py`

**Interfaces:**
- Consumes: `_effective_shares(info, price)` from Task 1. `price` is already computed at the top of `extract_financials` (`price = info.get("currentPrice") or info.get("regularMarketPrice")`).
- Produces: `extract_financials(info)["shares_outstanding"]` now returns the corrected count for multi-class `info`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_yahoo_block.py`:

```python
def test_extract_financials_corrects_multi_class_shares():
    info = {
        "symbol": "KVYO",
        "currentPrice": 16.11,
        "marketCap": 4_821_398_016,
        "sharesOutstanding": 140_897_018,  # Class A only
    }
    fin = extract_financials(info)
    assert fin["shares_outstanding"] == pytest.approx(4_821_398_016 / 16.11)


def test_extract_financials_keeps_single_class_shares():
    info = {
        "symbol": "AAPL",
        "currentPrice": 200.0,
        "marketCap": 3_000_000_000_000,
        "sharesOutstanding": 15_000_000_000,  # implied == reported
    }
    fin = extract_financials(info)
    assert fin["shares_outstanding"] == 15_000_000_000
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `pytest tests/test_yahoo_block.py -k "corrects_multi_class_shares or keeps_single_class_shares" -v`
Expected: `test_extract_financials_corrects_multi_class_shares` FAILS (returns raw 140_897_018); `test_extract_financials_keeps_single_class_shares` passes incidentally.

- [ ] **Step 3: Wire the helper in**

In `backend/services/yahoo.py`, change the `shares_outstanding` entry in the `extract_financials` return dict (line 302) from:

```python
        "shares_outstanding": info.get("sharesOutstanding"),
```

to:

```python
        "shares_outstanding": _effective_shares(info, price),
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run (from `backend/`): `pytest tests/test_yahoo_block.py -v`
Expected: PASS — all tests in the file, including the pre-existing `test_extract_financials_adds_valuation_fields` (its `info` has no `marketCap`, so the gate no-ops and it is unchanged).

- [ ] **Step 5: Run the full suite to confirm no snapshot moved**

Run (from `backend/`): `pytest -q`
Expected: PASS (all green; new tests added, none broken — engine/models tests build synthetic `fin` dicts and call `evaluate()` directly, bypassing `extract_financials`).

- [ ] **Step 6: Commit**

```bash
git add backend/services/yahoo.py backend/tests/test_yahoo_block.py
git commit -m "feat(valuation): use dual-class-corrected share count in extract_financials"
```

---

### Task 3: Read-only universe sweep verification

**Files:**
- Create (scratchpad, not committed): sweep script under the session scratchpad dir.

**Interfaces:**
- Consumes: the live pipeline via `valuation.engine`. No code under `backend/` changes in this task.

- [ ] **Step 1: Run the live before/after sweep**

Reuse the sweep already written this session (or recreate it): for each ticker, build the live `fin` via `engine.fetch_ticker_info` → `extract_financials` (now corrected) and `engine.evaluate`; compare against the same `fin` with `shares_outstanding` forced back to raw `info["sharesOutstanding"]`. Cover at minimum:

`KVYO GOOGL META CRWV V NBIS HOOD APP DDOG PLTR IREN KLAC AAPL JPM NVDA SNPS ANET TEM BWXT KO NFLX AVGO`

- [ ] **Step 2: Assert the invariants**

Confirm, against the spec's expected-impact table:
- Every **single-class** canary (IREN, KLAC, AAPL, JPM, NVDA, SNPS, ANET, TEM, BWXT, KO, NFLX, AVGO) is **byte-identical** before vs after.
- Every **multi-class** name moved by ~its `reported/true` ratio.
- **No verdict flips toward "cheaper."** CRWV stays SELL (moves further into SELL, never BUY); the only large flip is GOOGL BUY→SELL (intended — it rejoins its mega-cap peers).

Expected: all invariants hold. If a single-class canary moves, or any name flips toward BUY, STOP — that signals a hidden dependency the "clean rescale" stance did not anticipate; investigate before merging.

- [ ] **Step 3: Record the result**

No commit (scratchpad script is throwaway). Note the pass/fail of the invariants in the branch's final summary / memory update.

---

## Post-implementation

- Full `pytest` green + sweep invariants hold → the branch is ready for review (inline Opus subagent review per project norms; **not** the paid ultrareview).
- On merge, record in memory: the fix, the 3% gate, the `market_cap/price` source, and that no valuation constant was re-derived (clean rescale) — plus the verified single-class canary list.
