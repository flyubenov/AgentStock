# Growth-coupled, ramp-and-saturate scenario bands

**Date:** 2026-07-21
**Status:** Approved design, ready for implementation plan
**Scope:** Fair Value pipeline only — `build_scenarios` in `backend/valuation/engine.py`. No Quality Score change; no change to any per-leg valuation model.

## Problem

`build_scenarios` produces the three growth rates `[optimistic, realistic, pessimistic]`
that every valuation leg (DCF, EV/EBITDA, EV/Sales, P/E, …) is run at; fair value is
the plain average of the three composites. Today the two outer legs are **constant
offsets** off the realistic base:

```python
optimistic  = min(base + 0.05, opt_ceiling)      # opt_ceiling collapses to `cap` for
realistic   = base                               #   uncorroborated hyper-growers
pessimistic = max(base - 0.04, 0.02)
```

Two structural defects:

1. **`optimistic == realistic` for the names we care about.** The optimistic leg shares
   the realistic leg's growth cap: when raw growth is high and the name is not
   "corroborated," `opt_ceiling` falls back to `cap`, which equals `base`. The bull case
   is erased. For PLTR this yields `[0.25, 0.25, 0.21]` — dcf 37.03/37.03, ev_ebitda
   29.82/29.82 — so the three-scenario average carries false precision (only the
   pessimistic leg has any room to move, biasing FV strictly *below* realistic).

2. **The offsets are arbitrary constants**, not tied to the company. A mature dividend
   name and a 60%-grower get the identical ±0.05/−0.04 band, which is neither
   asymmetric nor performance-related.

The prior attempt (throwaway sim, historical-percentile bands) failed instructively:
letting the optimistic *growth* track a history percentile produced absurd valuations
for any recently-accelerating name — **NBIS → $1.02 billion/share, NVDA → $3,894, IREN
→ $1,536** — because an above-cap growth rate compounds over the 10-year horizon. That
is exactly the failure mode the engine's growth cap exists to prevent. The lesson: an
optimistic leg **must be bounded by a saturating ceiling**, not an open percentile.

## Goal

Every stock gets three **distinct**, **asymmetric**, **performance-coupled** growth
scenarios, bounded so no leg can explode. Reuse the shape the engine already trusts
for this exact job.

Non-goals (explicitly out of scope):
- **Re-anchoring any realistic (central) estimate.** The band is *dispersion around*
  the realistic leg, which is unchanged. In particular, NBIS's central FV (~$48, set by
  the EARLY_GROWTH EV/Sales pipeline) is far below its ~$180 price; the band lifts it to
  ~$69 via a legitimate bull leg, but closing the rest of that gap — if warranted — is a
  separate question about the EV/Sales multiple / burn assumptions, not this change.
  (Also noted for separate follow-up: baseline NBIS reads ~$48 here vs the ~$92 that
  `tem-sign-artifact-bugs` last landed — a data-shift sanity check is worth doing
  regardless of this work.)
- Scenario-**banded exit multiples** (a separate lever; the growth band alone resolves
  the collapse).

## Design

### The shape (already in the codebase, twice)

`_growth_cap` (engine) and `_ev_ebitda_ceiling` (models) both compute: a **flat floor →
a linear ramp coupled to revenue growth → a hard saturating ceiling**. The scenario band
reuses it. Note the growth window below (0.10 → 0.30) is the same one
`_ev_ebitda_ceiling` already uses (`EV_EBITDA_CAP_G_LO`/`_G_HI`).

### Construction

The band applies **only to the bounded-horizon main call** (`distorted_cap >=
GROWTH_CAP_BASE`). The perpetuity-based **DDM call passes `distorted_cap =
SUSTAINABLE_CEIL` (0.039)** so Gordon growth can't overshoot the discount rate; the band
must be skipped there and that call keeps today's construction untouched — the same guard
the existing cap-selection already uses (`if distorted_cap >= GROWTH_CAP_BASE`).

On the main call, the **realistic leg is unchanged**. The optimistic and pessimistic legs
become growth-coupled, asymmetric offsets off realistic, with the optimistic leg clipped
by a type/size/quality-coupled saturating ceiling:

```python
def _ramp(g, lo, hi, at_lo, at_hi):          # flat floor -> ramp -> saturate
    if g <= lo:
        return at_lo
    return at_lo + min(1.0, (g - lo) / (hi - lo)) * (at_hi - at_lo)

g   = _band_growth_signal(fin)               # SAME rate the realistic leg is derived from
up  = _ramp(g, SCEN_BAND_G_LO, SCEN_BAND_G_HI, SCEN_UP_FLOOR,   SCEN_UP_CEIL)
dn  = _ramp(g, SCEN_BAND_G_LO, SCEN_BAND_G_HI, SCEN_DOWN_FLOOR, SCEN_DOWN_CEIL)
optimistic  = max(realistic, min(realistic + up, _opt_ceil(fin, stock_type)))
pessimistic = max(0.02, realistic - dn)
```

**Constants** (new, in engine):

| Constant | Value | Role |
|---|---|---|
| `SCEN_BAND_G_LO`, `SCEN_BAND_G_HI` | 0.10, 0.30 | growth window the offsets ramp over |
| `SCEN_UP_FLOOR`, `SCEN_UP_CEIL` | 0.05, 0.10 | bull offset: floor = today's +0.05 |
| `SCEN_DOWN_FLOOR`, `SCEN_DOWN_CEIL` | 0.04, 0.12 | bear offset: floor = today's −0.04 |
| `SCEN_OPT_CEIL_EARLY` | 0.50 | early-growth bull ceiling |
| `SCEN_OPT_CEIL_MEGA` | 0.28 | mega (≥$1T) bull ceiling — hard |
| `SCEN_OPT_CEIL_LARGE` | 0.32 | large ($150B–$1T) bull ceiling — quality carve-out |
| `SCEN_OPT_CEIL_DEFAULT` | 0.35 | everything else |

The **floors match today's constants**, so the band is *inert* for a low-growth name
(`g <= 0.10` → up 0.05 / down 0.04 = today's ±0.05/−0.04) and only *widens* as growth
rises. This is what keeps mature names byte-identical.

### The optimistic ceiling — type/size-coupled with a quality carve-out

```python
def _opt_ceil(fin, stock_type):
    if stock_type == "EARLY_GROWTH":
        return SCEN_OPT_CEIL_EARLY                       # bull leg = "the hyper-growth is real"
    mc = fin.get("market_cap") or 0
    if mc >= m.MEGA_CAP_FLOOR:                            # >= $1T: HARD cap, quality cannot lift
        return SCEN_OPT_CEIL_MEGA
    if mc >= m.LARGE_CAP_FADE_FLOOR:                      # $150B–$1T: quality earns it back
        return SCEN_OPT_CEIL_LARGE + _quality_frac(fin) * (SCEN_OPT_CEIL_DEFAULT - SCEN_OPT_CEIL_LARGE)
    return SCEN_OPT_CEIL_DEFAULT

def _quality_frac(fin):                                  # same signal as _ev_ebitda_ceiling
    fcf, ebitda = fin.get("fcf_ttm"), fin.get("ebitda_ttm")
    if fcf is None or not ebitda or ebitda <= 0:
        return 0.0
    conv = fcf / ebitda
    return max(0.0, min(1.0, (conv - m.QUALITY_CONV_LO) / (m.QUALITY_CONV_HI - m.QUALITY_CONV_LO)))
```

Rationale, and how each maps to existing engine philosophy:

- **EARLY_GROWTH → 0.50 (above its realistic cap).** The realistic leg for a hyper-grower
  is deliberately *noise-suppressed* to `EG_CAP_CEIL` (0.35) — we won't bet the base case
  on a 684% feed reading. But the optimistic scenario *is* the "what if the growth is
  real" case; that is precisely where a higher (still bounded) rate belongs. Pinning it at
  the noise cap defeats the purpose of an optimistic leg and produces the paradox that a
  higher-growth name gets a *lower* FV. 0.50 is a generous-but-bounded rate; it cannot
  explode because it is a hard ceiling on the exact same horizon.
- **MEGA (≥$1T) → 0.28, hard.** A $3T franchise cannot sustain a 35% bull case regardless
  of margin quality — a TAM/arithmetic ceiling, not a quality one. This mirrors
  `_ev_ebitda_ceiling`, where a mega-cap's ceiling is the *mega* top (25×) and quality
  ramps a name only *toward* that top, never above it.
- **LARGE ($150B–$1T) → 0.32 + quality×0.03.** Size tempers the bull leg, but a
  high-FCF/EBITDA-conversion compounder earns it back to the 0.35 default — directly
  mirroring `_ev_ebitda_ceiling`'s `max(growth, quality)` lift (CDNS/ANET keep their
  premium). Without this, ANET (~$170B, quality 9.5) would be tempered to 0.32 and lose
  its bull case; with it, `q=1.00 → 0.35`.
- **else → 0.35.** GROWTH/MID/small — the sustainable-compounder regime top
  (`CORROBORATED_GROWTH_CEIL` = 0.35).

### The offset growth signal respects the earnings guards

`_band_growth_signal(fin)` must return the **same rate the realistic leg is derived
from**, so the distorted / non-operating guards govern the bull leg too:

```python
def _band_growth_signal(fin):
    if _earnings_distorted(fin):
        return float(fin.get("revenue_growth") or 0.0)          # matches realistic's source
    if _earnings_non_operating(fin):
        return float(fin.get("op_income_growth_stmt") or 0.0)   # matches realistic's source
    g = fin.get("revenue_growth_stmt")
    return float(g if g is not None else (fin.get("revenue_growth") or 0.0))
```

Without this, BWXT's non-operating revenue growth (18% *while operating income fell* — the
`bwxt-non-operating-growth-source` fix) sneaks back into the optimistic leg (opt 0.02 →
0.091). Sourcing the offset from operating income (−1.4%) keeps BWXT's band identical to
its pinned baseline. Symmetrically, a distorted name (SNPS post-Ansys) keys the band off
the revenue growth its realistic leg already uses — consistent by construction.

### What this replaces

The `opt_ceiling` / `corroborated` block in `build_scenarios` is **removed** and replaced
by the construction above. Consequently:
- `GROWTH_OPT_HEADROOM` (0.05) is subsumed by `SCEN_UP_FLOOR`.
- `CORROBORATED_GROWTH_CEIL` (0.35) survives as the value of `SCEN_OPT_CEIL_DEFAULT` but its
  *corroboration-gating role* is gone. Check `test_engine.py` for assertions on the old
  path; delete the constant only if no longer referenced (it may read cleaner to keep it
  named and reuse it as the default ceiling).

## Effect (measured, read-only sim)

Method: reconstruct each ticker's live `fin` via the production fetch path, monkeypatch
`build_scenarios` with the proposed construction, run `engine.evaluate(fin)` baseline vs
band, diff the composite `fair_value`. Basket of 12:

| Ticker | type | BAND triple | FV base → band | Δ% |
|---|---|---|---|---|
| PLTR | GROWTH | [.350,.250,.130] | 53.70 → 57.68 | +7.4 |
| NBIS | EARLY | [.450,.350,.230] | 48.51 → 68.66 | +41.5 |
| IREN | MID | [.350,.250,.130] | 20.27 → 23.31 | +15.0 |
| NVDA | MEGA | [.280,.250,.130] | 197.77 → 190.27 | −3.8 |
| ANET | GROWTH | [.346,.250,.136] | 140.80 → 142.30 | +1.1 |
| JPM | FIN | [.300,.200,.080] | 297.31 → 305.33 | +2.7 |
| MSFT | MEGA | [.262,.200,.140] | 315.00 → 314.34 | −0.2 |
| SNPS | GROWTH | [.300,.200,.080] | 390.87 → 388.05 | −0.7 |
| KLAC | GROWTH | [.172,.118,.072] | 66.83 → 66.81 | −0.0 |
| AAPL | MEGA | [.250,.200,.160] | 183.28 → 183.28 | +0.0 |
| KO | DIV | [.232,.182,.142] | 107.95 → 107.95 | +0.0 |
| BWXT | GROWTH | [.070,.020,.020] | 54.43 → 54.43 | +0.0 |

- **Collapse solved generally:** all 12 have three distinct scenarios, including NBIS
  (was `[.35,.35,.31]` opt==real → `[.45,.35,.23]`).
- **No explosions:** NVDA $190 / IREN $23 (vs the percentile approach's $3,894 / $1,536).
- **NVDA cooled** (−3.8%), **NBIS paradox reversed** (high growth now *raises* FV,
  +41.5%), **ANET protected** by the quality carve-out (+1.1%, not −3.2%), **BWXT inert**
  (guard respected).
- **Mature names untouched:** AAPL/KO/BWXT byte-identical, KLAC/MSFT within ±0.2%.

## Blast radius

The construction returns today's values whenever `g <= SCEN_BAND_G_LO` (0.10) **and** the
optimistic ceiling is not more generous than today's `opt_ceiling` — i.e. low-growth
names are unchanged. Names that move are exactly those with `g > 0.10` (wider band) or a
previously-collapsed optimistic leg (hyper-growers). Direction is bounded and explained by
the `stock_type` / size / quality inputs above.

Regression canaries to hold at expected values in the sweep: **IREN** (must not
re-explode — bounded at ~$23), **NBIS/TEM** (EARLY_GROWTH ceiling behaves), **BWXT**
(inert), **AAPL/KO** (inert), **KLAC** (inert).

## Testing (TDD, RED first)

1. **Pure `build_scenarios` unit tests** on synthetic `fin` dicts pinning each regime:
   - low-growth (`g <= 0.10`) name → triple equals today's `[base+0.05, base, base−0.04]`
     (inertness — the RED guard against drift on mature names);
   - a GROWTH hyper-grower (`raw > cap`) → `optimistic > realistic` (the collapse fix);
   - EARLY_GROWTH → optimistic rides toward 0.50, above its 0.35 realistic cap;
   - MEGA → optimistic clipped at 0.28 regardless of a high `_quality_frac`;
   - LARGE + `q=1.0` → ceiling 0.35; LARGE + `q=0.0` → ceiling 0.32;
   - non-operating fixture (BWXT-like) → band identical to pinned baseline;
   - distorted fixture → offset sourced from revenue growth.
   - **DDM path** (`distorted_cap = SUSTAINABLE_CEIL`) → band skipped, triple equals
     today's construction (perpetuity stays bounded).
   Boundary cases at `g = 0.10`, `g = 0.30`, and the `$150B` / `$1T` size edges.
2. **`_ramp` / `_opt_ceil` / `_band_growth_signal`** unit-tested directly (saturation,
   clamps, guard branches).
3. **Regression via `evaluate`:** an EARLY_GROWTH fixture's FV *rises* (bull leg); a MEGA
   fixture's FV does not rise above baseline; a mature fixture is unchanged.
4. **Full suite green:** `pytest` from `backend/` (`asyncio_mode=auto`). Update/retire
   `test_engine.py` assertions that pinned the old `opt_ceiling`/`corroborated` path.
5. **Re-validate live** via the `validating-agent-stock` skill: reproduce the 12-name
   table; confirm canaries (IREN bounded, BWXT/AAPL/KO inert) and the headline movers
   (PLTR +7.4, NVDA −3.8, NBIS +41.5, ANET +1.1).

## Follow-up (record in memory when landed)

- The band shape, the four `SCEN_OPT_CEIL_*` tiers, the quality carve-out mirroring
  `_ev_ebitda_ceiling`, and the guard-respecting offset signal.
- Deferred, out-of-scope gaps flagged above: NBIS's central EV/Sales estimate vs price,
  and the NBIS baseline data-shift ($48 vs prior $92). Link to this spec.
