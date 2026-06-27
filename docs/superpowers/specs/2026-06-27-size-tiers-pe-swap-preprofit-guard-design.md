# Size Tiers, Market-P/E Swap, and Pre-Profit Guard — Design

**Date:** 2026-06-27
**Status:** Approved (design phase)

## Problem

Three coupled defects surfaced while validating individual tickers (IREN as the
driving case):

1. **yfinance mis-sectors crypto/data-center companies as "Financial Services."**
   IREN (builds data centers, converting bitcoin-mining capacity to AI compute)
   is tagged Financial Services and routed to the FINANCIAL type, which values it
   on book-value models (P/B, RIM) and returns ~$5 — nonsense for the business.

2. **`LARGE_CAP` is the unconditioned catch-all default**, not a size class. The
   only market-cap test anywhere in the classifier is `ASSET_HEAVY`'s
   `0 < market_cap < 2_000_000_000`. So a $16.9B mid-cap like IREN would display
   "LARGE_CAP" purely because it matched no earlier rule — the label asserts a
   size that isn't checked. Real large caps (Mag7) are $1–4T; the top-100 US
   floor is ~$100B.

3. **The P/E model is dividend-payout-dependent.** `calc_pe` uses the justified
   (Gordon) form `P/E = payout / (r − g)`, which collapses to the `max(pe, 1)`
   floor (≈ `0.9 × EPS`, a P/E of ~1) for non-dividend payers — exactly the
   mature, buyback-driven large caps the model is meant to serve. Left in a
   blend, it drags the composite down hard.

A fourth issue is structural: a company in a heavy-investment / pre-profit phase
(deeply negative trailing FCF, e.g. IREN at ~−149% FCF margin) cannot be valued
reliably from trailing financials by a DCF-anchored type. The engine should
decline to value it rather than emit a misleading number.

## Goals

- Stop crypto/data-center names from being classified FINANCIAL on yfinance's
  bad sector tag.
- Give `LARGE_CAP` a real market-cap definition (> $100B) and introduce a
  size-neutral `MID_CAP` default for everything else that matches no specialized
  rule.
- Replace the payout-dependent justified P/E with a capped **market** P/E that
  works for dividend and non-dividend companies alike.
- Add a pre-profit guard that returns a `failed` result (type `PRE_PROFIT`,
  `fair_value = None`) when a DCF-anchored company is deeply FCF-negative on a
  trailing basis.

## Non-Goals

- Renaming or re-weighting any type other than the changes specified here.
- Adding new data sources or peer/sector P/E baselines.
- Changing the growth-scenario logic (`build_scenarios`) or any other model.
- Handling buybacks explicitly in earnings-power valuation.

---

## Design

### 1. Classifier (`backend/valuation/classifier.py`)

#### 1a. De-financialize override

Add a module-level keyword list and gate the FINANCIAL rule on it:

```python
# Phrases that mark a yfinance "Financial Services" tag as a mis-classification:
# crypto miners and data-center operators are tagged Financial Services but are
# not balance-sheet/book-value businesses.
NON_FINANCIAL_KEYWORDS = [
    "bitcoin", "cryptocurrency", "crypto", "digital asset",
    "data center", "data centre", "mining", "miner",
]
```

Rule #1 in `_detect_type` becomes:

```python
    # 1. Financial
    if sector == "Financial Services" and not any(kw in summary for kw in NON_FINANCIAL_KEYWORDS):
        return "FINANCIAL"
```

`summary` is already `(fin.get("long_business_summary") or "").lower()`, so the
keyword match is case-insensitive against the lowercased summary.

#### 1b. Size-gated default

Rule #8 replaces the bare `return "LARGE_CAP"`:

```python
    # 8. Size-based default
    if market_cap > 100_000_000_000:
        return "LARGE_CAP"
    return "MID_CAP"
```

`market_cap` is already `fin.get("market_cap") or 0`, so a missing/zero cap
falls to `MID_CAP` (the conservative default).

#### 1c. Weights

`LARGE_CAP` is redefined — drop EV/Sales (a GROWTH tell) and SOTP (a
CONGLOMERATE tell); concentrate on cash + earnings. `MID_CAP` is new and sits
between LARGE_CAP and GROWTH (retains a small EV/Sales weight for faster
mid-cap growth). Both sum to 1.00.

```python
    "LARGE_CAP": {"dcf": 0.50, "fcfe": 0.00, "ev_ebitda": 0.35, "pe": 0.15, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.00},
    "MID_CAP":   {"dcf": 0.45, "fcfe": 0.00, "ev_ebitda": 0.25, "pe": 0.15, "ev_sales": 0.15, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.00},
```

All other type weights are unchanged.

### 2. P/E model swap (`backend/valuation/models.py`)

Replace the justified (payout/Gordon) P/E with a **capped market P/E**. The
target multiple is the stock's own trailing P/E capped at a mature level, so it
mean-reverts a richly-valued name toward maturity and never inflates a cheap one
(symmetric with how EV/EBITDA and EV/Sales already compress toward mature
multiples). It has no payout or growth term, so it becomes a **single-value**
model (fills all three scenarios with the same value, like `calc_pb`).

```python
MATURE_PE_CAP = 21.0  # ~ long-run S&P average; mean-reversion ceiling for P/E
```

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

Wiring changes:

- `models.py`: remove `"pe"` from `SCENARIO_MODELS`.
- `engine.py`: move `"pe": m.calc_pe` from `_SCENARIO_FN` to `_SINGLE_VALUE_FN`
  (it is now called as `calc_pe(fin)`, no `growth` argument).

Blast radius: this changes fair values for **every** type that weights `pe`
(LARGE_CAP, MID_CAP, GROWTH, DIVIDEND, CYCLICAL, FINANCIAL). This is intended and
consistent.

### 3. Pre-profit guard (`backend/valuation/engine.py`, in `evaluate`)

```python
FCF_MARGIN_FLOOR = -0.25
```

Inside `evaluate`, after `weights = pick_ev_multiple(weights, fin)` and before
`growth = build_scenarios(fin)`:

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

The guard fires only when DCF carries weight (it is the anchor for the
trailing-cash thesis); FINANCIAL (dcf weight 0) is unaffected. The returned
`stock_type` is `"PRE_PROFIT"` — the detected bucket (e.g. transient MID_CAP) is
not leaked.

---

## End-to-end: IREN

1. Sector "Financial Services" **and** summary contains "data center"/"bitcoin"/
   "mining" → de-fin override skips FINANCIAL.
2. Falls through rules 2–7: positive EBITDA and $16.9B cap dodge ASSET_HEAVY; no
   conglomerate signal; Yahoo's `revenue_growth = 0` dodges EARLY_GROWTH and
   GROWTH; not a dividend payer; negative/zero trailing P/E dodges CYCLICAL.
3. `market_cap` $16.9B < $100B → **MID_CAP** (dcf weight 0.45).
4. Pre-profit guard: FCF margin ≈ −1.13B / 757M ≈ −149% < −0.25 → **fires**.
5. Result: `stock_type = "PRE_PROFIT"`, `fair_value = None`, `status = "failed"`,
   the pre-profit error message. Frontend renders the failed badge and an em-dash
   (existing infra).

## Parameters

| Name | Value | Location | Rationale |
|---|---|---|---|
| `NON_FINANCIAL_KEYWORDS` | crypto/data-center terms | classifier.py | de-tag yfinance mis-sector |
| LARGE_CAP cap threshold | `> 100_000_000_000` | classifier.py rule #8 | ~top-100 US floor |
| `MATURE_PE_CAP` | `21.0` | models.py | ~long-run S&P average |
| `FCF_MARGIN_FLOOR` | `-0.25` | engine.py | lenient enough to spare mildly-negative mature names; catches deep burn |

## Test impact

- **classifier tests:** add de-fin override case (Financial Services + crypto
  summary → not FINANCIAL); add size-gate cases (> $100B → LARGE_CAP, ≤ $100B →
  MID_CAP); add MID_CAP weight presence.
- **models tests:** `calc_pe` loses the `growth` arg — update
  `test_missing_inputs_return_null` and any P/E call sites; add capped-market-P/E
  cases (cap applied above 21×, trailing kept below 21×, null on eps ≤ 0 or
  missing trailing_pe).
- **engine tests:** `test_evaluate_large_cap_blend` — LARGE_CAP no longer weights
  ev_sales/sotp, so the "both EV multiples fold" assertion/comment is stale and
  must be updated (only ev_ebitda survives by construction). Add a MID_CAP blend
  test and a pre-profit-guard test (deep-negative FCF margin → failed/PRE_PROFIT).
- Re-validate spec-anchor tickers (MSFT, AMAT, KLAC, ABBV) for regressions from
  the global P/E swap; confirm IREN returns PRE_PROFIT.
