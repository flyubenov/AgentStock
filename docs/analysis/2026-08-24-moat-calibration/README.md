# Moat Score calibration sweep (Task 10)

Exploratory, non-TDD pass over a stratified 25-ticker subset of the DB universe,
run against the live pipeline (`fetch_screener_inputs` -> `compute_metrics` ->
`apply_nudge(base_profile(...))` -> `moat.scoring.score`), strictly sequential
(no concurrency — the yfinance fetch layer uses a shared monkeypatch/lru_cache
that races otherwise). Script: scratchpad `moat_sweep.py` (not committed, per
brief). **No scoring constants were changed.** This is a report for the user to
approve or reject tuning — see the proposals at the bottom.

Of the 25 requested tickers, 5 (AXP, F, GM, VZ, T) are not currently in the
136-row DB universe; they were scored anyway per the task brief. All 25 fetched
without error (0 `err:` rows).

## Ranked table

| Ticker | Score | Variant | Gated | Excluded | A1 | A2 | B1 | B2 | B3 | C1 |
|---|---|---|---|---|---|---|---|---|---|---|
| AXP | 100.0 | FINANCIAL_ROTE | no | C1 | 20 | 20 | 25.0 | 10 | — | — |
| MA | 96.5 | ROIC | no | — | 20 | 20 | 25.0 | 10 | 13.5 | 8 |
| AAPL | 95.0 | ROIC | no | — | 20 | 20 | 25.0 | 10 | 14.0 | 6 |
| ADBE | 93.5 | TANGIBLE_ROIC | no | — | 20 | 20 | 25.0 | 5 | 13.5 | 10 |
| ANET | 92.5 | ROIC | no | — | 20 | 16 | 25.0 | 10 | 11.5 | 10 |
| JPM | 90.7 | FINANCIAL_ROTE | no | C1 | 17 | 16 | 25.0 | 10 | — | — |
| MSFT | 89.0 | ROIC | no | — | 20 | 20 | 25.0 | 10 | 11.0 | 3 |
| GOOGL | 87.5 | ROIC | no | — | 20 | 20 | 25.0 | 8 | 11.5 | 3 |
| CDNS | 87.0 | TANGIBLE_ROIC | no | — | 20 | 20 | 25.0 | 5 | 9.0 | 8 |
| SNPS | 81.5 | TANGIBLE_ROIC | no | — | 20 | 20 | 25.0 | 3 | 5.5 | 8 |
| OPFI | 66.9 | FINANCIAL_ROTE | no | C1 | 13 | 20 | 16.7 | 0 | 10.5 | — |
| VZ | 59.0 | ROIC | no | — | 4 | 5 | 25.0 | 8 | 14.0 | 3 |
| T | 40.2 | ROIC | no | — | 0 | 5 | 18.75 | 0 | 13.5 | 3 |
| LYFT | 20.6 | ROIC | **yes** | — | 0 | 0 | 0 | — | 8.5 | 10 |
| F | 15.0 | ROIC | **yes** | — | 0 | 0 | 0 | 0 | 5.0 | 10 |
| CRWV | 11.1 | ROIC | no* | — | 0 | — | — | — | 5.0 | 0 |
| SOFI | 9.6 | FINANCIAL_ROTE | **yes** | C1 | 0 | 0 | 6.25 | — | — | — |
| GM | 8.9 | ROIC | **yes** | C1 | 0 | 0 | 0 | 3 | 5.0 | — |
| NBIS | 5.6 | ROIC | **yes** | — | 0 | 0 | 0 | — | 5.0 | 0 |
| IREN | 0.0 | ROIC | **yes** | C1 | 0 | 0 | 0 | — | 0.0 | — |
| V | **blank** | ROIC | — | — | — | — | — | — | 12.0 | 6 |
| TEM | **blank** | ROIC | — | — | 0 | 0 | 0 | — | 5.0 | — |

`*` CRWV: `wacc` is `None` (no beta from yfinance) so the level<=hurdle gate
check never fires even though the business is clearly value-destroying
(level ≈ −19.9). It still lands low (11.1) because only 3 pillars clear the
coverage floor (A1=0, B3=5, C1=0, available=45). Not one of the two flagged
observations below, but worth a note — a `None`-hurdle name can dodge the gate
purely by lacking a beta, rather than by clearing WACC.

## Counts

- **Scored:** 20/22 fetched (V and TEM blank on the coverage floor)
- **Gated (≤35):** 6 — LYFT, F, SOFI, GM, NBIS, IREN
- **Blank:** 2 — V (data gap, see below), TEM (series_len=2 < `MOAT_MIN_YEARS`=3)
- **Variant split:** ROIC 15 (incl. the 2 blanks), TANGIBLE_ROIC 3 (ADBE, CDNS, SNPS), FINANCIAL_ROTE 4 (AXP, JPM, OPFI, SOFI)

## Golden-name landings vs. expectation

| Expectation | Result |
|---|---|
| Wide-moat compounders land ≈70+ | MA 96.5, AAPL 95.0, ADBE 93.5, ANET 92.5, MSFT 89.0, GOOGL 87.5, CDNS 87.0, SNPS 81.5 — **all match**. **V is blank** — does not match, investigated below. |
| Commodity/cyclical/no-excess land gated (≤35) or low | F 15.0 (gated) ✓, GM 8.9 (gated) ✓. VZ 59.0 and T 40.2 land **moderate**, not gated/low — see Observation 1. |
| Pre-profit burners land low or blank | IREN 0.0 (gated) ✓, NBIS 5.6 (gated) ✓, LYFT 20.6 (gated) ✓, CRWV 11.1 (low) ✓, TEM blank ✓ — **all match**. |
| JPM sane non-blank ROTE score | JPM 90.7, FINANCIAL_ROTE ✓ — **matches**. |

## V (Visa) blank — root-cause finding

**Verdict: genuine yfinance data gap, cascading through pre-existing shared code — not a new Task-1 bug.**

Evidence, pulled directly from the fetch layer for V:

- V's balance sheet **does** carry `Invested Capital` (`[62.34B, 58.94B, 57.50B, 55.71B, None]`, 2025-2021) and `Goodwill And Other Intangible Assets` — those parts of the pipeline are fine.
- V's income statement rows are: `['Basic Average Shares', 'Basic EPS', 'Cost Of Revenue', ..., 'EBITDA', ..., 'Operating Income', 'Operating Revenue', ..., 'Total Operating Income As Reported', ...]` — **there is no `EBIT` key at all.** yfinance never populates a computed `EBIT` line for V (only `EBITDA`, `Operating Income`, and `Total Operating Income As Reported`).
- `screener.metrics.roic()` requires `ebit` and always reads it via `inc.value("EBIT", i)` / `inc.latest("EBIT")`. For V that is `None` at every year, so:
  - `m.roic_ttm = None`, `m.roic_5y_avg = None`, `m.roic_ex_goodwill = None`
  - `m.roic_series = []`, `m.roic_series_ex_goodwill = []`
- Confirmed live: `compute_metrics(V)` → `roic_ttm=None, roic_5y_avg=None, roic_series=[]` (`series_len=0`).
- In `moat.scoring._return_axis`, V is not routed FINANCIAL (de-financialized payment network, profile resolves `BALANCED` — the payment-network de-financialization fix already in place is working correctly), and `_acquisition_distorted` needs `roic_ex_goodwill`/`roic_ttm`, both `None`, so it can't even reach the TANGIBLE_ROIC rescue. V ends up on the plain ROIC axis with an empty series.
- In `moat.scoring.score`, `series_len (0) < MOAT_MIN_YEARS (3)` → the coverage floor returns `None`. (Separately, only 2 pillars — B3=12.0, C1=6 — clear at all, also under `MOAT_MIN_PILLARS`=3, so either floor alone would have blanked it.)

This is **not** something Task 1's new series-population code introduced: the moat `roic_series` loop reuses the exact same `roic()` helper and the exact same `"EBIT"` statement key that `roic_ttm`/`roic_5y_avg` (pre-existing Quality-engine metrics) have always used. V's Quality-side `roic_wacc_spread` sub-score has presumably been `None` for the same reason all along — Moat just inherits the gap because it deliberately shares the fetch/metrics layer (spec §7, zero extra I/O). Category: **(c) genuinely-missing yfinance data**, with a caveat: a real fix exists (fall back to `Operating Income` or `Total Operating Income As Reported` when `EBIT` is absent, mirroring the statement-primary op-margin fallback already used elsewhere in `compute_metrics`), but that is a Quality/Section-II-level change outside Moat's Task 10 scope — flagged for the controller, not fixed here.

## Flagged observation 1 — binary B1 + level-only gate on a thin spread

`B1 = 25 * persistence_fraction` is all-or-nothing per year (`series > hurdle`,
`moat/metrics.py:persistence_fraction`) — a name that clears its hurdle by
0.01pp every year gets exactly the same B1 credit as one that clears it by
20pp. The only ROIC-*level*-sensitive pillars are A1 (max 20) and A2 (max 20,
bands starting at 0pp for the lowest tier), and the gate itself is a single
level<=hurdle check, not a spread-magnitude check.

Low-spread tail from this sweep:

| Ticker | Blended spread (pp) | A1 | A2 | B1 | Score |
|---|---|---|---|---|---|
| VZ | 4.00 | 4 | 5 | 25.0 (full) | 59.0 |
| T | 4.40 | 0 | 5 | 18.75 | 40.2 |
| F | −10.36 | 0 | 0 | 0 | 15.0 (gated) |
| GM | −4.66 | 0 | 0 | 0 | 8.9 (gated) |

None of these four cleared ~70 in this sample — VZ (the closest) is held back
by weak B2 (8/10) and C1 (3/10). But the arithmetic ceiling the review flagged
is real: plug in a hypothetical thin-spread name that just clears its hurdle
every year (B1=25) while otherwise having stable, well-covered margins
(B2=10, B3=15, C1=10) and a modest ROIC level sitting at the A1/A2 band edges
(A1=8 for level≈12%, A2=5 for spread≈0-5pp) — that's `8+5+25+10+15+10 = 73`.
A name with almost no economic moat (barely-positive spread) but very stable,
capital-light margins can reach the "high-moat" range on stability alone. VZ
is the closest real illustration in this subset: B1's full 25/25 is nearly
half its total 59, despite A1+A2 (the actual level/spread signal) contributing
only 9/40.

**This does look like a genuine calibration gap worth the user's attention.**

## Flagged observation 2 — B3 margin-durability for FINANCIALS

Per spec, only C1 (FCF conversion) is explicitly excluded for the FINANCIALS
profile; B3 is not. In practice B3's inclusion for banks turns out to be an
**accident of data availability**, not a principled decision:

| Ticker | `gross_margin_series` | `op_margin_series` | B3 |
|---|---|---|---|
| JPM | `[]` | `[]` | excluded (no data) |
| AXP | `[]` | `[]` | excluded (no data) |
| SOFI | `[]` | `[]` | excluded (no data) |
| OPFI | `[83.2, 80.0, 78.9, 79.0]` | `[64.1, 56.8, 54.6, 51.1]` | **included**, 10.5/15 |

For JPM/AXP/SOFI, yfinance simply doesn't report a `Gross Profit` line for a
bank income statement, so `_margin_durability` naturally falls through to
`None` and B3 self-excludes (same effective outcome as an explicit exclusion,
by luck rather than intent). For OPFI — a specialty lender that yfinance
happens to statement in a goods-like `Cost Of Revenue`/`Gross Profit` shape —
B3 fires and contributes real points (10.5/15, roughly a quarter of OPFI's
total 66.9 score) off gross/op margins of 78-83%/51-64%. Those numbers aren't
a "gross margin" in the normal sense for a lender (no COGS concept applies);
they're closer to a net-interest-margin proxy that happens to land in the
`Gross Profit` row. The B3 stability/trajectory read on that series isn't
obviously wrong, but it isn't validated as a moat signal for a lender the way
it is for a product company, and its presence/absence for a given bank is
purely a function of whether yfinance happened to populate those rows — not
a deliberate scoring choice. This matches the review's concern:
**B3 for FINANCIALS is inconsistent by construction.**

## Proposed band adjustments (NOT YET APPLIED)

Both proposals are mechanical, small, and additive-only (they only ever
*remove* a source of potential score inflation) — but per Task 10 instructions
**no constant was changed**; these need explicit user approval before a
follow-up TDD edit.

1. **Dampen B1 on a thin blended spread.** Cap B1's contribution when the
   `_spread_blend` value is small, independent of persistence fraction, e.g.:
   ```python
   # moat/scoring.py — illustrative, not applied
   B1_THIN_SPREAD_PP = 2.0     # blended spread below this pp caps B1
   B1_THIN_SPREAD_CAP = 15.0   # cap value (was 25 uncapped)
   ...
   frac = persistence_fraction(axis["series"], axis["hurdle"])
   b1 = (25.0 * frac) if frac is not None else None
   spread = _spread_blend(axis["spot"], axis["five"])
   if b1 is not None and spread is not None and spread < B1_THIN_SPREAD_PP:
       b1 = min(b1, B1_THIN_SPREAD_CAP)
   add("B1", b1, 25)
   ```
   Rationale: keeps B1 rewarding genuine multi-year persistence for names with
   real economic profit (VZ's 4pp spread wouldn't even trip this at the
   suggested 2pp threshold — the cap is deliberately conservative), while
   preventing a merely-not-losing-money name from banking near-full B1 credit.
   The exact threshold/cap values are a judgment call for the user; 2.0pp /
   15.0 are a starting proposal, not a fitted constant.

2. **Exclude B3 for the FINANCIALS profile**, mirroring the existing C1
   exclusion:
   ```python
   # moat/scoring.py — illustrative, not applied
   is_fin = profile == "FINANCIALS"
   heavy_capex = _heavy_capex_distortion(m)
   if not is_fin:
       add("B3", _margin_durability(m), 15)
   if is_fin or heavy_capex:
       excluded.append("C1 FCF conversion")
   elif m.fcf is not None and m.ebitda is not None and m.ebitda > 0:
       add("C1", score_high(m.fcf / m.ebitda, C1_FCF_BANDS, 0.0), 10)
   ```
   Rationale: makes bank scoring consistent regardless of whether yfinance
   happens to populate a `Gross Profit`/`Operating Income` row for a given
   lender (OPFI vs. JPM/AXP/SOFI today), and avoids treating a
   lender's cost-of-revenue-shaped line as a genuine "margin stability" moat
   signal. Effect: OPFI's available pillars drop from `{A1,A2,B1,B2,B3}=90`
   to `{A1,A2,B1,B2}=75`; earned points drop from 60.17 (incl. B3's 10.5) to
   49.67, moving its score from 66.9 to `100*49.67/75 = 66.2` — nearly
   unchanged, because renormalization largely offsets the lost points. JPM/
   AXP/SOFI are untouched (B3 was already `None` for them). The main value of
   this change is *consistency* — removing a signal that currently fires or
   not by accident of yfinance's statement shape for a given lender — not a
   large score movement in this sample.

Not proposed here (out of scope / needs its own investigation): the V EBIT
fallback (Quality-engine-level fix, not Moat-specific) and the CRWV
`wacc=None` gate-bypass noted above.

## Resolution (user decision, 2026-08-25)

Both proposals **approved and applied** as follow-up TDD edits to
`moat/scoring.py`; the §3.1 band tables were kept unchanged.

1. **B1 thin-spread cap** — added `B1_THIN_SPREAD_PP = 2.0` /
   `B1_THIN_SPREAD_CAP = 15.0`: when the blended spread is below 2pp, B1 is
   capped at 15 (still out of 25, so renormalization penalizes). Latent in this
   sample — no ticker's spread fell below 2pp (VZ's 4pp stays uncapped, score
   59.0 unchanged). Covered by `test_b1_capped_on_thin_spread_despite_full_persistence`
   and `test_b1_not_capped_on_healthy_spread`.
2. **B3 excluded for FINANCIALS** — mirrors the C1 exclusion; the breakdown now
   records `"B3 margin durability"` in `excluded` for banks. Effect on the
   re-run: **OPFI 66.9 → 66.2**; AXP/JPM/SOFI unchanged (B3 was already absent
   by data). Every non-financial and every wide-moat name is byte-identical to
   the pre-change sweep. Covered by `test_b3_excluded_for_financials_even_with_margin_data`
   and `test_b3_still_scored_for_non_financial_with_margin_data`.

**Deferred** (not addressed in the Moat branch, per the same decision): the V
EBIT-fallback (a Quality/Section-II change with wider blast radius — own task)
and the CRWV `wacc=None` gate-bypass. Full suite after the changes: 542 passing.
