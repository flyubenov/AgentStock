---
name: agent-stock-monetization-smoke-test
description: PAUSED brainstorm (branch MonetizationPlan-brainstorm) — commercialization pressure-test + smoke-test spec in progress; resume at 2 open questions
metadata: 
  node_type: memory
  type: project
  originSessionId: 3373c6b8-32ea-462e-8efb-934404560923
  modified: 2026-09-14T20:53:53.099Z
---

Brainstorm session on commercializing Agent Stock. **PAUSED 2026-09-14, will continue.** Branch `MonetizationPlan-brainstorm`.

**What happened, in order:**
1. **Pressure-tested** the `MonetizationPlan/` PRD set (10 Gemini-drafted docs). Key conclusions: data-licensing + guard-recalibration is the load-bearing risk (engines are calibrated to yfinance field semantics; a feed swap re-validates every distortion guard + 500 tests; redistribution rights are a separate pricier license); drop Next.js/Redis/Celery/LLM-agent for launch; Sheets→Postgres is the one required migration; ticker-count vs SEO tension; AI-drafted legal copy has errors.
2. **Decomposition roadmap WRITTEN + COMMITTED** `2918df5`: `docs/superpowers/specs/2026-09-13-agent-stock-commercialization-roadmap.md` — 8 sub-projects (SP0 fork → SP1 data spike → SP2 Postgres → SP3 auth → SP4 Stripe → SP5 paywall → SP6 SEO pages; SP7 expansion, SP8 PWA; SP-Legal parallel). Decisions baked in: **Option 1 (two repos / fork for commercial, personal repo untouched); NO shared-engine extraction (divergence accepted); B2B excluded entirely.**
3. User questioned **whether it's worth it**. Goal = **income**. Honest joint conclusion: paid SaaS vs Morningstar/Bloomberg/SimplyWallSt is **low-EV** — scores are commodity, Moat/R-R 0–100 is false-precision vs Morningstar's narrow/wide, incumbents entrenched. Higher-EV income path noted = convert the *skill* to a job/contract (not pursued now). User chose to **run a cheap smoke test** to validate willingness-to-pay before building.
4. **KEY REFRAME by user** (changes the whole positioning): the product's value is NOT the 130-ticker DB — it's **real-time compute of ANY ticker in seconds, no manual modeling**. DB = free SEO funnel only. New tier ladder: **Free** = Quality score on crawlable DB pages; **Mid** = +Fair Value; **Premium** = +Moat +R/R +on-demand any-ticker compute +watchlists.

**Smoke-test design settled so far (spec NOT yet written):**
- Signal = **fake-door email capture** (not real payment; note: email door barely tests price).
- Hero = **interactive "type any ticker → live Quality score, blurred FV/Moat/R-R" demo** + email gate "unlock on every ticker + watchlists → early access." Needs public rate-limited compute endpoint (cache, US-listed cap).
- Pricing: I recommended **$25 mid / $35 premium** for positioning (user floated $20/$30 or $25/$35).
- Tech defaults: reuse React/Vite + FastAPI, public landing route + compute endpoint, emails → Google Sheet (creds already exist), Plausible/GA4 events, throwaway marketing URL, personal instance untouched, no fork until test passes.
- Go/no-go draft (user owns): ~2–3 wks, ≥300–500 visitors; **green** ≥8% email + some "when can I pay"; **yellow** 3–8%; **red** <3%.
- Established: **SEO can't be smoke-test traffic** (too slow, 6–12mo) — validation needs active traffic (ads and/or forum posts). SEO/publishing the 130 is later growth only.

**RESUME HERE — 2 open questions the user must answer, then write+commit the smoke-test spec to `docs/superpowers/specs/`:**
1. Traffic source for the test: **A) ~$100 paid ads (I recommended — cleanest, no self-promo hassle; user was put off by hand-marketing), B) organic forum/X, C) both.**
2. Publish the existing 130 as public browse pages during the test (cheap depth + starts SEO clock) — yes/no?

Then: write the spec (fake-door smoke test), then optionally invoke writing-plans. Related: [[wacc-mos-moat-margin-design]], [[moat-score-design]] (the engines being productized).
