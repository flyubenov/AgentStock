---
name: pltr-fade-band-relief
description: $150B-$1T fade band had no growth-relief valve; PLTR faded harder than smaller AND larger peers at the same growth rate
metadata: 
  node_type: memory
  type: project
  originSessionId: fac349e0-afbe-42d7-8561-0e5f5b1489ca
  modified: 2026-07-21T20:43:37.312Z
---

`_fade_hold_years` (models.py) was non-monotonic in size. The mega band (>= $1T) had a
growth-relief valve (`revenue_growth >= MEGA_CAP_GROWTH_RELIEF` 0.40 → `FADE_HOLD_MID` 5)
but the $150B-$1T band did NOT, so a fast grower there got only a 3y hold
(`FADE_HOLD_LARGE`) while both a <$150B and a >$1T peer growing at the same rate got 5y.
PLTR ($317B, ~85% growth) sat in the trough. Fixed by mirroring the mega valve into the
$150B-$1T branch (step shape, reuses the same constants — no new knob). Restores
monotonicity: at any fixed growth rate a larger company never holds LONGER than a smaller
one.

Live (committed code, branch `fade-band-relief` @`dee3994`): PLTR $49.12 → **$53.26
(+8.4%)**, verdict −62.9% → −59.8% — still deeply overvalued (an internal-consistency fix,
NOT a re-rating; the −60% is the capped-growth model correctly reading 153x EV/EBITDA /
59x sales). Pre-commit probe agreed ($48.42 → $52.42, +8.3%). Quality Score unaffected
(fade is FV-only, no shared code). Blast radius verified PLTR-only across the 27-ticker
test universe; canaries NBIS ($48.51) and VRT ($199.74) byte-identical pre/post, KLAC
($278B, 12%) unchanged — in-band but below the 0.40 gate (the real-data proof the gate
holds). 330 backend tests pass.

Nearest near-miss: AMD ($808B, 38%) — in-band but just below the 0.40 cliff (the residual
step discontinuity, identical in kind to the mega band's; accepted by choosing the "mirror
the mega valve" step shape over a graduated one). See [[size-coupled-growth-fade]].

DEFERRED separate gap — NOW RESOLVED by [[scenario-growth-band]] (merged to master
`8d74e14`, 2026-07-21): for a capped hyper-grower the three FV scenarios collapsed
(optimistic == realistic, the growth cap pinning both). Fixed with a growth/size/quality/
leverage-coupled ramp-and-saturate band. (The exit-multiples-are-a-single-point half of the
gap remains open — the band covers the growth scenarios, not the exit multiple.) Original
spec: docs/superpowers/specs/2026-07-19-fade-band-relief-design.md; plan:
docs/superpowers/plans/2026-07-19-fade-band-relief.md.
