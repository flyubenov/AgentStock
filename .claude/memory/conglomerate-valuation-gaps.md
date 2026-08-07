---
name: conglomerate-valuation-gaps
description: CONGLOMERATE tier DELETED (HON->DIVIDEND, MMM->MID_CAP) + calc_nav leverage double-count fixed + sotp dead code removed. DONE, branch ready to merge.
metadata:
  node_type: memory
  type: project
  originSessionId: aaed5efa-0ffb-43c8-a1a6-751cfac3da1d
  modified: 2026-07-22T14:04:00.481Z
---

DONE + MERGED to master (2026-07-22, no-ff merge `6af9971`) — branch `conglomerate-removal-nav-fix`, whole-branch opus review **Ready to merge** (0 Critical / 0 Important), 338 tests pass on merged master. Supersedes the earlier DEFERRED note. Brainstorm + spec + plan + subagent-driven TDD; see `docs/superpowers/specs/2026-07-22-conglomerate-removal-nav-fix-design.md` and the sibling plan.

**Three independent changes (they don't interact — post-deletion HON/MMM use no nav/sotp leg):**

1. **Deleted the CONGLOMERATE tier** (classifier rule 3, `CONGLOMERATE_KEYWORDS`, the `_TYPE_WEIGHTS` entry). It was a **2-name tier** (only HON/MMM, via `industry == "Conglomerates"`) and its value came entirely from two broken legs (see below), not a real conglomerate model. Reclassification (live): **HON -> DIVIDEND** $91 -> $174.79 (px -26%; feed shows yield 4.14% / payout 74%), **MMM -> MID_CAP** $79 -> $131.98 (px -24%; yield 1.83% < 2.5% skips DIVIDEND, $88B < $100B). Blast radius = exactly those two. Key finding from the sweep: with `real_fcf` the DCF is HEALTHY (HON DCF ~$169), so the memory's old "DCF collapses" claim was STALE (it used the low info-FCF $2.94B, not real_fcf $5.42B) — there was no genuine conglomerate valuation problem left, only the two legs the tier uniquely leaned on.

2. **Fixed the `calc_nav` leverage double-count** (`bvps - net_debt/share` -> `bvps`, x MOS 0.90). book_value_per_share already nets ALL liabilities, so subtracting net debt double-debited it, driving NAV negative for levered REITs (SPG -$66, AMT -$77) and crushing every ASSET_HEAVY composite at 0.45 weight. Blast radius = ASSET_HEAVY (nav 0.45) + CYCLICAL (nav 0.15) ONLY (the two tiers that weight nav; net-debt names UP, net-cash names slightly DOWN). Measured REIT re-rating: O +32% ($40.9->$53.9), VICI +21%, PLD +20%, SPG +43%, AMT +72%. **DEFERRED (still open):** the fix does NOT make REIT NAV correct — for high-P/B REITs (AMT P/B 21.6, SPG P/B 15.3) *book* value is a poor NAV proxy (towers/malls carry real estate far below market / are intangible-annuity businesses), so even fixed nav at 0.45 weight leaves AMT reading -44%. Real fix (cap/temper nav by P/B, reweight ASSET_HEAVY, or a market/cap-rate NAV) is a separate future session.

3. **Removed orphaned `sotp` dead code** (`calc_sotp`, its `_SINGLE_VALUE_FN` dispatch, `ALL_METHODS`/`APPROX_METHODS` membership, the `"sotp": 0.00` key in every tier). SOTP was a misnomer (whole-company EV/EBITDA x 0.85 on the flat 20x cap, not a real parts sum) and CONGLOMERATE was its only weighted home. **Kept the blank SOTP Sheets column** (`services/sheets.py` `_MODEL_COLS`/`_DB_HEADERS` UNCHANGED) — removing it would shift the quality-score column index and, because `_ensure_database_sheet` only writes headers on tab creation and existing rows keep the old layout, the reader would mis-map persisted rows (reading the old blank SOTP cell as quality score). The blank column is benign; only executable dead code was removed. GOTCHA that gates this: `ALL_METHODS` and every `_TYPE_WEIGHTS` tier MUST carry the same key set (engine does `method_weights[mid]` for every mid in ALL_METHODS) — remove sotp from BOTH in one commit or KeyError.

**Canaries verified byte-identical** (none uses a nav/sotp leg): IREN (MID_CAP, capex-reroute ev_ebitda/pe), NBIS (EARLY_GROWTH, ev_sales), KLAC (GROWTH, dcf/ev_ebitda/pe).
