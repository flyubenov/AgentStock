# Remove CONGLOMERATE tier + fix NAV double-count

**Date:** 2026-07-22
**Status:** Approved (design), pending implementation plan
**Related memory:** `conglomerate-valuation-gaps.md` (this supersedes the DEFERRED note), `early-growth-sotp-removal.md`

## Problem

The `CONGLOMERATE` stock-type tier holds exactly two live names — **HON** and **MMM** — both via
`industry == "Conglomerates"` (classifier rule 3). It produces indefensible fair values:

| | FV now | price vs FV | driving legs (weight) |
|---|---|---|---|
| HON $229.86 | **$91.00** | +153% (reads wildly overvalued) | ev_ebitda $98.85 (0.30), sotp $178 (0.40), nav −$33 (0.30) |
| MMM $170.76 | **$78.66** | +117% | ev_ebitda $98.48 (0.30), sotp $131 (0.40), nav −$10 (0.30) |

Two artifacts drive the breakage, together 70% of the tier's weight:

1. **`nav` double-counts leverage.** `calc_nav` computes `bvps − net_debt/share`. Book value per share is
   *already* equity (assets − all liabilities, debt included), so subtracting net debt again debits the debt a
   second time — driving NAV negative whenever net-debt/share > book (HON −$33, MMM −$10; SPG −$66, AMT −$77).
2. **`sotp` is a misnomer.** `calc_sotp` is whole-company EV/EBITDA × 0.85 on the stale flat 20× cap — not a real
   sum-of-parts. Proper segment SOTP is infeasible with the current data layer (yfinance exposes no reliable
   per-segment revenue/EBIT).

With `real_fcf`, the DCF leg for these names is actually healthy (HON DCF $169), contradicting the memory's stale
"$58" finding — so **there is no genuine conglomerate valuation problem left to solve**. The only breakage is the
two legs the CONGLOMERATE tier uniquely leans on. When HON/MMM fall to their natural tiers, those legs disappear
and the values become defensible.

## Decision

Delete the CONGLOMERATE tier entirely, remove the dead `sotp` code it orphans, and fix the `calc_nav`
double-count bug. The deeper "book value understates high-P/B REIT NAV" problem is **explicitly out of scope**
(deferred to a future session).

The three changes are independent and do not interact: once CONGLOMERATE is deleted, HON/MMM use no `nav` leg, so
the NAV fix never touches them.

## Change 1 — Delete the CONGLOMERATE tier (`valuation/classifier.py`)

- Remove classifier rule 3 (the `is_conglomerate_industry` / `has_conglomerate_keywords` block that returns
  `"CONGLOMERATE"`).
- Remove the `CONGLOMERATE_KEYWORDS` list.
- Remove the `_TYPE_WEIGHTS["CONGLOMERATE"]` entry.
- Renumber the downstream rule comments (current rules 4–8 become 3–7).

### Reclassification (measured live, by bypassing rule 3 on the live feed)

| Ticker | now | after removal | FV before → after | notes |
|---|---|---|---|---|
| HON | CONGLOMERATE | **DIVIDEND** | $91.00 → **$174.79** (+153% → +31%) | feed shows yield 4.14% / payout 74% |
| MMM | CONGLOMERATE | **MID_CAP** | $78.66 → **$131.13** (+117% → +30%) | yield 1.83% < 2.5% skips DIVIDEND; $88B < $100B |

**Blast radius: exactly HON and MMM.** The tier is keyword-isolated and check #3, so removal cannot touch any name
that does not already carry conglomerate/diversified/breakup language. Every other classic candidate already routes
elsewhere (BRK-B/Loews→FINANCIAL, GE/Howmet→GROWTH, DHR/Siemens→LARGE_CAP, MDLZ→DIVIDEND, Icahn→PRE_PROFIT). A
future name with those keywords now falls through to the normal size/growth/dividend rules instead of this tier.

### Known data caveats (feed bugs, orthogonal to the tier — do NOT fix here)

- HON market cap reads **$72.8B** (316M shares — yfinance under-counts; true HON ≈ $150B). Immaterial to the
  destination: DIVIDEND fires before the size default regardless.
- HON `dividend_rate` reads **$9.52** (≈ double the real ~$4.50). This is what pushes HON into DIVIDEND and inflates
  its DDM leg. On clean data HON's yield is ~2% and it would fall to LARGE_CAP instead. Accepted as-is for this change.

## Change 2 — Remove orphaned `sotp` dead code

After Change 1, `sotp` has weight 0.00 in every remaining tier, so `calc_sotp` is unreachable. Remove:

- `calc_sotp` in `valuation/models.py`.
- The `"sotp": m.calc_sotp` entry in `_SINGLE_VALUE_FN` (`valuation/engine.py`).
- `"sotp"` from `ALL_METHODS` and `APPROX_METHODS` (`valuation/models.py`).
- The `"sotp": 0.00` key from every `_TYPE_WEIGHTS` dict (`valuation/classifier.py`).

### Sheets schema — keep the blank SOTP column (chosen)

`services/sheets.py` lists `"sotp"` in `_MODEL_COLS` and `"SOTP"` in `_DB_HEADERS`, and `_row_to_database_row` reads
the quality score by fixed position (col Q, index 16). `_MODEL_COLS` maps breakdowns to columns positionally, so once
`calc_sotp` is gone the SOTP cell is simply always blank — exactly how any unweighted model already behaves.

**Decision: leave the SOTP column in place.** Removing it would shift every later column (quality score index 16 → 15)
and, because `_ensure_database_sheet` only writes headers when the tab is first created and existing rows keep the old
16-index layout, the reader would mis-map persisted rows (reading the old blank SOTP cell as the quality score) until
every ticker is re-upserted — the Sheets round-trip regression the memory guards against. Keeping the blank column
preserves the exact schema at zero migration risk. `services/sheets.py` and `tests/test_sheets_row.py` are therefore
**unchanged**. Only the executable `sotp` dead code is removed.

## Change 3 — Fix the `calc_nav` double-count (`valuation/models.py`)

Change the leg from `bvps − net_debt/share` to `bvps` (× MOS unchanged):

```python
# before
fv = _apply_mos(bvps - net_debt / shares)
# after
fv = _apply_mos(bvps)
```

The `net_debt` read is no longer needed and is removed.

### Blast radius (measured live)

The NAV fix does **not** touch HON/MMM (post-reclassification they use no `nav` leg). Its entire reach is the two
tiers that still weight `nav`: ASSET_HEAVY (0.45) and CYCLICAL (0.15).

| Ticker | Tier | navW | nav old→new | FV old→new | Δ | context |
|---|---|---|---|---|---|---|
| O | ASSET_HEAVY | 0.45 | $8.9→$37.8 | $40.9→$53.9 | +32% | P/B 1.55, px $65 (−17%) — defensible |
| VICI | ASSET_HEAVY | 0.45 | $9.7→$23.7 | $29.8→$36.1 | +21% | P/B 1.01, px $26.6 |
| PLD | ASSET_HEAVY | 0.45 | $18→$51.6 | $75→$90.1 | +20% | P/B 2.62, px $150 |
| SPG | ASSET_HEAVY | 0.45 | −$65.6→$13.4 | $83→$118.6 | +43% | P/B 15.3, px $227 |
| AMT | ASSET_HEAVY | 0.45 | −$77.3→$6.8 | $52.9→$90.8 | +72% | P/B 21.6, px $163 |
| LIN | CYCLICAL | 0.15 | — | $184→$190.6 | +3.5% | small (0.15 weight) |
| DVN | CYCLICAL | 0.15 | — | $26.3→$27.1 | +3.1% | |
| NEM | CYCLICAL | 0.15 | net-cash | $188.2→$187.8 | −0.2% | fix correctly *lowers* net-cash |

Direction is correct and matches the memory ("raises net-debt names, lowers net-cash names" — NEM confirms). The
old formula drove SPG/AMT NAV to −$66/−$77 and, at 0.45 weight, was crushing every REIT.

### Explicitly deferred (NOT in this change)

The fix removes the double-count but does **not** make REIT NAV correct. For high-P/B REITs (AMT P/B 21.6, SPG P/B
15.3), *book* value is a poor NAV proxy — towers/malls carry real estate far below market or are intangible-annuity
businesses — so even the fixed leg at 0.45 weight still drags them to implausible −44%/−48% reads. Fixing that
(cap/temper the NAV leg by P/B, reweight ASSET_HEAVY, or source a market/cap-rate NAV) is a separate design question
for a dedicated session.

## Testing

Establish green (`pytest` from `backend/`) before touching anything, then TDD each change.

### New tests (failing first)

- A `Conglomerates`-industry name no longer classifies `CONGLOMERATE`: HON → `DIVIDEND`, MMM → `MID_CAP`
  (synthetic `fin` fixtures mirroring their live inputs).
- `calc_nav` returns `bvps × MOS` with no net-debt term: a net-debt fixture values *higher* than the old formula, a
  net-cash fixture values *lower*; both equal `_apply_mos(bvps)` exactly.

### Update / remove existing tests

- `test_classifier.py`: remove the two positive CONGLOMERATE classification tests (lines ~19–28); the KLAC
  "not CONGLOMERATE" regression (line ~33) stays valid but its comment is updated. Update the `sotp`-weight
  assertions (`test_early_growth_weights_no_sotp` and line ~123) — `sotp` is gone from the weight set entirely.
- `test_models.py`: remove the three `calc_sotp` tests (lines ~82–102).
- `test_engine.py`: remove `test_evaluate_sotp_flagged_approx` (CONGLOMERATE, lines ~188–193). The EARLY_GROWTH
  `"sotp" not in breakdown` assertions (~1003, ~1033) still pass; refresh their comments.
- `test_sheets_row.py`: update if it pins the SOTP column (full-removal path).

### Re-validation canaries (after green)

- **Moved, must land as measured:** HON ($175, DIVIDEND), MMM ($131, MID_CAP), O ($53.9), SPG ($118.6), AMT ($90.8).
- **Must stay byte-identical** (use no `nav`/`sotp` leg): IREN, NBIS, KLAC.

## Out of scope

- HON's doubled `dividend_rate` and under-counted share count (feed bugs).
- The deeper REIT book-NAV problem (Change 3 "deferred" section).
- Any change to DIVIDEND / MID_CAP / ASSET_HEAVY / CYCLICAL method weights beyond dropping the dead `sotp` key.
