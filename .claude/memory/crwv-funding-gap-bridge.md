---
name: crwv-funding-gap-bridge
description: "CRWV's +55% \"undervalued\" was a frozen-capital-structure artifact — forward EV/Sales bridged a year-10 EV against today's net debt; fixed with a self-gating cumulative funding-gap accretion"
metadata: 
  node_type: memory
  type: project
  originSessionId: 58a380bf-d8b3-4ab5-8440-695ac5046dea
  modified: 2026-07-19T09:31:57.114Z
---

DONE + MERGED to master (no-ff `85881e3`, impl `ec450d0`, spec `7dc9807`): CRWV (CoreWeave) printed a composite **$113.79 (+55% "undervalued")** off a frozen-capital-structure artifact. The forward EV-multiple legs price a **year-10 enterprise value** but bridge to equity with **today's** net debt and share count (`equity = future_EV − net_debt_today`). For a deeply FCF-negative, already-levered name (CRWV: net debt $32.9B = 82% of market cap, 10.9× EBITDA, FCF −$7.25B/yr, revenue growing 111.6%) that manufactures phantom upside — the projected growth is funded by external capital that becomes a claim ahead of today's owners, so by year 10 neither net debt nor the share count resembles today's.

**Fix (Approach A — cumulative funding-gap):** new pure helper `exit_net_debt(fin, rev0, growth, hold, net_debt, …)` in `backend/valuation/models.py` accretes onto today's net debt the **cumulative external funding the burn requires** over HORIZON. Burn is the company's own FCF margin (`m0 = fcf_ttm/rev0`) faded toward a mature terminal margin; only negative-FCF years accrue (no paydown credit). Constants: `FUNDING_TERMINAL_FCF_MARGIN = 0.10`, `FUNDING_FADE_HOLD = 2`, `FUNDING_BURN_MARGIN_FLOOR = -1.0`.

**Self-gating is the primary safety property:** `fcf_ttm >= 0` (or missing inputs) → gap 0 → leg byte-for-byte unchanged, so every FCF-positive name (KLAC/ANET/NVDA/KO/JPM/V/AVGO/SNPS) is provably untouched. Only trailing-FCF-negative names on a forward EV-multiple leg move.

**Two over-corrections surfaced and resolved the design's open gates (both from the SAME extreme-transient-margin pathology — a capex spike on a lagging revenue base extrapolated as a sustained burn larger than the whole EV):**
1. **IREN → scoped out of `calc_ev_ebitda`.** On the EV/EBITDA capex-reroute, IREN's −226% FCF margin on $501M revenue accreted a ~$12B gap against a ~$4.8B EV. Per the spec's decision gate the correction was **confined to `calc_ev_sales` only** (the reroute regime already carries bespoke weighting); NOTE comment left in `calc_ev_ebitda`. IREN restored to $20.27 (regression canary).
2. **NBIS → added `FUNDING_BURN_MARGIN_FLOOR = -1.0`.** −230% on a $1.6B run-rate → $73B gap vs $64B EV drove the sole ev_sales leg negative → declined. Floor caps assumed sustained burn at 100% of revenue; sits at/below CRWV's −87% anchor so CRWV/moderate burners are untouched. NBIS returns valued $48.51.

**Final live results:** CRWV $62.46 (−14.68%, the intended flip from +55%), NBIS $48.51 (−72.7%), IREN $20.27 (unchanged), TEM $31.04, ASTS declines, ANET/KLAC/KO unchanged. 324 tests pass. SOTP deliberately out of scope (spot breakup value, freezing today's net debt there is internally consistent). Spec: `docs/superpowers/specs/2026-07-18-eg-capital-structure-bridge-design.md`.

**Gotcha discovered at merge (code review):** the branch initially committed 3 FTNT `CORROBORATED_GROWTH_CEIL` corroboration tests that depended on a **foreign, uncommitted `engine.py` change** (separate FTNT growth-corroboration work, not part of this fix) — a clean checkout failed 2 tests with `AttributeError`. Cause: a prior git-recovery amend swept the whole working-tree `test_engine.py` into the commit. Fixed by amending those 3 tests out; they + the engine.py change remain **uncommitted** in the working tree for that separate branch. LESSON: after a git-recovery amend, diff the commit against the branch's actual scope — a `git grep` for foreign symbols catches tests that silently depend on uncommitted work. Relates to [[app-serves-persisted-rows-not-live-compute]] (verify in a fresh/clean state, not the dirty working tree).

CAUTION: like NBIS in [[tem-sign-artifact-bugs]], EARLY_GROWTH burner FVs are a wide range, not a point — the calibration (terminal margin / fade hold / floor) is centralized for one-line recalibration. KLAC's live −68.79% is a **pre-existing** split-data artifact ([[klac-growth-undervaluation]]), untouchable here (KLAC is FCF-positive, no ev_sales leg).
