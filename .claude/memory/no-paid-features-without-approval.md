---
name: no-paid-features-without-approval
description: Never use paid Claude features (e.g. /code-review ultra / ultrareview) without explicit approval first
metadata: 
  node_type: memory
  type: feedback
  originSessionId: b5a02239-c606-41f1-85c3-1d321ae001c2
  modified: 2026-07-23T07:46:31.281Z
---

Never invoke paid/billed Claude options without asking first. Specifically: do NOT run `/code-review ultra` (a.k.a. ultrareview, the multi-agent cloud review) or any other billed feature on the user's behalf. If a task seems to need one, explicitly ask the user for approval BEFORE using it.

**Why:** the user is cost-conscious about billed features and wants to control when they're spent.

**How to apply:** for code review, default to a lighter INLINE review (spawn an Opus review subagent against the diff) rather than the cloud ultrareview. Only escalate to a paid option after the user explicitly approves it. Note: prior memory entries say "opus review 0 Crit/0 Imp" — that referred to the paid ultrareview; going forward "the review" means the inline subagent review unless the user says otherwise. See [[lyft-earnings-inflated-guard]].
