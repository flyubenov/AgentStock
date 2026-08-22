# FV & Quality rerating — A/B comparison (2026-08-23)

Per-ticker comparison of the **new** dynamic pipeline (WACC-blended discount rate +
quality-scaled MOS + Option-A `wacc()` fix, branch `wacc-mos-moat-margin-design`)
against the **old** static model (flat `DISCOUNT_RATE = 0.10` / `MOS = 0.90` +
pre-Option-A `wacc()`), across all **136 tickers in the Database sheet**.

Both numbers for each ticker come from a **single fundamentals fetch**, so each
delta isolates the model change (not data drift).

## Files
- `rerating_report.html` — self-contained interactive report (open in a browser).
  Published artifact: https://claude.ai/code/artifact/7a2bd751-69d6-4578-991b-9e5c7acf1866
- `compare_out.csv` — raw data: `fv_old/fv_new/fv_delta_pct`, `q_old/q_new/q_delta`,
  `wacc/spread/roic5`, per ticker.
- `pipeline_compare.py` — the reproducible generator.

## Headline
- **Quality: 132 / 134 unchanged.** Only OKTA and LEU shift (−0.2) — the DB's
  captive-debt-signature names the Option-A fix catches. FINANCIALs identical.
- **FV: 32 up / 74 down / 7 flat** (of 113 valued), median **−3.3%**, range
  −19.3% to +41.6%. Durable low-WACC compounders re-rate up (PFE +42%, CF +23%,
  WM +22%, ABBV/HON +16%, RTX/MA +12%); speculative high-beta names haircut down
  (AMBA −19%, SYM −18%, TSLA/COIN/SHOP −14…−15%).
- **23 names unvaluable by both models** (pre-profit miners, SPACs, foreign
  tickers) → N/A. ZETA hit a quality-metric error; SYM's spread is a known
  ROIC-denominator artifact (FV delta still bounded).

## Reproduce
Read-only; hits live Yahoo + the Sheets `Database` tab. Does **not** touch stored
DB rows or recompute anything in the app.

```bash
cd backend
# .env must have GOOGLE_SHEETS_ID + GOOGLE_SHEETS_CREDS_PATH
PYTHONPATH=. python ../docs/analysis/2026-08-23-fv-rerating-comparison/pipeline_compare.py
```

**Harness note:** `CONCURRENCY` **must stay 1** — the FV capture monkeypatches
shared module globals (`engine.evaluate`, `engine.fetch_screener_inputs`,
`metrics.wacc`), so parallel coroutines corrupt each other's captures (an earlier
concurrency=4 run produced impossible +1788% outliers — a harness bug, not the
pipeline). The script writes `compare_out.csv` next to itself.
