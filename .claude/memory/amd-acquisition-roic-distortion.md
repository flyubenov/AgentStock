---
name: amd-acquisition-roic-distortion
description: AMD scored a low 6.6 because Xilinx goodwill/amortization crushed Section II ROIC; fixed with tangible-capital ROIC substitution + WACC beta cap
metadata: 
  node_type: memory
  type: project
  originSessionId: ea25e0a9-65a1-45de-bc36-6155c47ebbed
---

AMD's Screener Quality Score was an understated **6.6**, driven entirely by **Section II
(Returns on Capital) = 3.6** (30% weight). Root cause: the **Xilinx acquisition** (~$49B,
all-stock, Feb 2022) loads ~$42B of goodwill & intangibles onto the books — **63% of
invested capital**. That inflates the ROIC *denominator* while its amortization depresses
the EBIT *numerator*, so reported ROIC read **5.1%** vs. a tangible-capital ROIC of
**~13.8%**. The tell: **ROTE (already tangible-based) read a healthy 20.5%** — the two
return twins disagreed only on whether the deal price tag is counted.

Two fixes (commit on branch `screener-fixes`, 2026-07-12):
1. **Tangible-capital ROIC substitution** — new `_acquisition_distorted(m)` gate in
   `scoring.py` (goodwill+intangibles ≥ 30% of invested capital, trailing P/E >> forward
   P/E via existing `DEPRESSED_PE_RATIO`, tangible ROIC strictly > reported). When it
   fires, Section II scores `roic_ex_goodwill` / `roic_5y_ex_goodwill` / a recomputed
   spread instead of the reported ROIC trio. Deliberately **not** gated on `eps_cagr<=0`
   (that gate is what makes [[avgo-forward-eps-pe]] / the earnings adjustment skip a
   fast-grower like AMD). New metrics computed in `metrics.py::compute_metrics`.
2. **WACC beta cap** — `BETA_CEILING = 2.0` in `metrics.py::wacc`. yfinance reported
   AMD's beta at 2.47 (stale 2022-crash window), inflating WACC to 16.9% and pinning the
   spread sub-score at 0. Global input fix; only bites betas > 2.0, can only lower the
   hurdle.

Result: **AMD 6.6 → 7.2** (Section II 3.6 → 5.4). Tightly gated — MSFT (goodwill 37% but
no amortization-depression signal) and NVDA (goodwill 15%) are unaffected. Same family as
[[distorted-earnings-dual-cap]] and the capex-distortion reroute; spec at
`docs/superpowers/specs/2026-07-12-acquisition-roic-distortion-design.md`.
