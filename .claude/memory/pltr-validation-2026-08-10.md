---
name: pltr-validation-2026-08-10
description: PLTR re-validated live at $172 — FV $62.11 (−63.9%) and Quality 8.1 both SOUND, left as-is; logs that the P/E leg is the FV's most permissive leg and its PEG ceiling rides the uncapped quarterly earnings-growth figure
metadata:
  node_type: memory
  type: project
---

# PLTR validation — 2026-08-10 (verdict: SOUND, no change)

Live harness run (`validate_ticker.py PLTR --inputs`), price **$172.01**, market cap $413B.

| Pipeline | Result |
|---|---|
| Fair Value | **$62.11 / −63.89%** (GROWTH tier) |
| Quality | **8.1** (I 10.0 / II 7.25 / III 10.0 / IV 4.5, TECH_GROWTH) |
| Risk-Reward | **1.52 "Reward-Favored"** (reward 3.27 / risk 2.15) |

## Composite reconciles exactly

`0.40·42.37 (dcf) + 0.40·35.49 (ev_ebitda) + 0.20·154.81 (pe) = 62.106` ✓.
`pick_ev_multiple` folded ev_sales (0.20) into ev_ebitda (EBITDA margin 43% clears the
floor), so the GROWTH weights land 0.40 / 0.40 / 0.20.

## Prior tuning verified live (do not re-derive)

- **[[pltr-fade-band-relief]] is firing:** `_fade_hold_years($413B, 0.928)` → **5** (the
  $150B–$1T growth-relief valve), not `FADE_HOLD_LARGE` 3. Worth +$4.93 (hold 3 → $57.18).
- **[[scenario-growth-band]] is firing:** scenarios are `opt 0.3367 / real 0.25 / pess 0.13`
  — no opt==real collapse. `_opt_ceil` = 0.3367 (LARGE 0.32 + `_quality_frac` on 0.789
  FCF/EBITDA conversion → toward 0.35).
- **Growth cap** = 0.25 (`_growth_cap` at ceiling, statement g 0.562).
- **EV/EBITDA:** hist median **231.7x** trimmed to the **30x** terminal ceiling
  (`_ev_ebitda_ceiling`, durable + full growth/quality frac), projected off the *statement*
  base $1.44B — not `info['ebitda']` $2.66B (the [[nflx-ebitda-basis-mismatch]] contract).
- `_earnings_understated` fires (ni 2.52 / op 3.56 both above earnings_growth 2.154) but is
  **inert** — raw 2.516 is capped to 0.25 either way.

## Inputs cross-checked clean

Quarterly revenue 1935.5/1632.6/1406.8/1181.1 sums to TTM $6.156B ✓; 1935.5 vs 1003.7 =
**+92.8%**, exactly the `revenue_growth` field (confirming again it is *quarterly* YoY —
the model uses the annual statement 56.2% where the basis matters). Shares 2.403B ≈ balance
sheet 2.391B (single-class, dual-class fold-in inert). Net cash −$9.2B. FCF $2.10B statement.

## Why −63.9% is a defensible range center

Reverse-engineering the price, not the model: to justify **$172** the DCF leg alone needs
**56.1%** growth held 5 years then faded (or **40.2%** flat for a full decade) at a 10%
discount with the 0.9 MOS; the EV/EBITDA leg needs a **155x terminal** multiple — i.e. the
market's spot 152x paid *forever*. Bracketing (FV vs price −63.9%):

| Stress | FV |
|---|---|
| growth cap 0.20 / 0.25 (live) / 0.30 / 0.35 / 0.45 | $56.00 / **$62.11** / $66.60 / $73.39 / $100.09 |
| fade hold 3y / 5y (live) / 7y / 10y (no fade) | $57.18 / **$62.11** / $68.02 / $84.03 |
| terminal EV/EBITDA 20x / 30x (live) / 40x / 60x | $57.55 / **$62.11** / $66.66 / $75.77 |
| bull combo (35% growth + 40x exit + 7y hold) | $91.44 (−46.8%) |
| MOS removed (0.9 → 1.0) | $69.01 |

Every defensible corner still reads deeply overvalued; you only reach today's price by
assuming ~56% growth for a decade AND a permanent 150x EBITDA multiple. The −63.9% is the
capped-growth model working, not failing.

## Logged observation (no change made)

**The P/E leg is the single most permissive leg in PLTR's FV, and it is what holds the number
up.** `calc_pe(forward=True)` = forward EPS $2.309 × target P/E **74.5x** × MOS = $154.81 —
a flat single point (no scenarios), ~2.5x the two modelled legs. Drop it and FV would be
**$38.93** (−77%); it is worth **+$23** of the $62.11.

Its target multiple is *today's spot forward P/E*, because `_forward_target_pe`'s PEG ceiling
is sourced from the **uncapped** `earnings_growth` (2.154 → 215% × PEG_CEILING 2 = 430x),
which never binds against 74.5x. If the ceiling instead rode the *sustainable capped* rate
(0.25 → 50x), the leg would be $103.89 and **FV $51.92 (−69.8%)** (measured, not estimated).

**Recommendation: leave as-is.** It errs toward the market (conservative in the SELL
direction — correcting it would only make PLTR look *more* overvalued), the verdict is
unchanged either way, and the ceiling constant is a forward-tier-wide path (blast radius =
every FORWARD_TIERS name with a hot quarterly earnings print), so it is a brainstorm-class
recalibration, not a one-ticker fix. Related open gap already logged in
[[pltr-fade-band-relief]]: "exit multiples still un-banded".

## Quality 8.1 and R-R 1.52 both consistent

Quality: Section IV 4.5 is the only drag and it is real — shares CAGR **+7.6%** dilution and
SBC **15.3% of revenue**; Sections I/III max out on 33% revenue CAGR, 47% FCF margin, 85%
gross margin, net cash −3.45x EBITDA; Section II 7.25 on ROIC 18.9% vs WACC 12.5% (+6.4
spread). Defensible.

R-R **does not contradict** the FV: R-R's `discount` metric is distance from the 52-week high
(17.1%), a *technical* input — there is no fair-value term anywhere in the R-R axis set, so
"Reward-Favored" and "−63.9% overvalued" are measuring different things by design.
