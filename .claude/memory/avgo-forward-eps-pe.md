---
name: avgo-forward-eps-pe
description: Why the P/E leg uses forward EPS when trailing earnings are amortization-depressed (trailing P/E >> forward P/E)
metadata: 
  node_type: memory
  type: project
  originSessionId: ffa1ddc2-d81f-4c11-a231-33666ae7a851
---

The forward-tier P/E leg multiplied **trailing** GAAP EPS by the forward multiple.
For names whose trailing earnings are depressed by acquisition amortization (AVGO
post-VMware: trailing EPS $6.02, trailing P/E 62x vs forward P/E 19x), this read a
spuriously low P/E leg ($104) and dragged the blended FV down.

Fix (commit fe75959): `_normalized_forward_eps` in `models.py` substitutes
`forward_eps` for the depressed trailing EPS in `calc_pe(forward=True)` when
`trailing_pe / forward_pe > DEPRESSED_PE_RATIO` (1.5) **and** forward EPS > trailing
(never lowers EPS). `forward_eps` was added to `extract_financials` (yahoo
`forwardEps`).

**Why:** trailing P/E far above forward P/E means the market expects an earnings
jump — usually a one-off charge / amortization masking real earnings power.

**How to apply:** healthy names (ratio < 1.5: META 1.3x, MSFT 1.2x, GOOGL/AAPL ~1.1x)
are untouched. It fires for AVGO and NVDA (1.96x), and incidentally ETN (1.54x —
ETN's trailing was also charge-depressed, consistent with [[distorted-earnings-dual-cap]]).
Paired with the mega-cap growth relief in [[size-coupled-growth-fade]].
