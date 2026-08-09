---
name: cloud-deploy-validating-skill
description: Plan + progress for running the validating-agent-stock skill in the cloud (Claude Platform Managed Agents), and the project-canonical in-repo memory setup that makes it portable.
metadata:
  type: project
---

**Goal:** run `/validating-agent-stock` on a cloud provider so it works like local. User has Claude Platform + Google Cloud Run. Chose **Claude Platform → Managed Agents** (least plumbing) over Cloud Run.

**Key fact — the skill is NOT a deployable service.** It's Claude-agent *instructions* (`SKILL.md` + `risk-reward-validation.md`) + a harness (`validate_ticker.py`) that imports the real backend engine (`valuation`/`screener`/`risk_reward` + `services.yahoo`). Cloud needs: the repo, `pip install -r backend/requirements.txt`, network egress for yfinance, a Claude runtime + Anthropic key.

**MEMORY MADE PROJECT-CANONICAL (Option B-clean) — DONE 2026-08-09:**
1. **Migrated** the live external auto-memory (`~/.claude/projects/C--Users-f-lub-proj-Agent-Stock/memory/`, which was NEWER than the Aug-7 repo snapshot — nearly all files differed + 2 files were external-only) INTO the in-repo `.claude/memory/`. Now byte-identical (41 files). NOT yet committed — 37 modified + 2 new staged. **NEXT: commit them.**
2. **`autoMemoryDirectory`** set to abs path `C:/Users/f_lub/proj/Agent Stock/.claude/memory` in `.claude/settings.local.json` (gitignored/untracked — machine-local, correct). Confirmed via official docs it's read from any settings scope; value MUST be absolute or `~/`-prefixed (can't be repo-relative). Takes effect next session after the workspace-trust prompt → then BOTH session-start MEMORY.md injection (reads) AND auto-memory saves (writes) target the in-repo dir. Local ergonomics solved.
3. **SKILL.md repointed**: line-25 memory ref → `.claude/memory/` (repo-relative); run block → `python3` (verified works locally AND is Linux default; deps import OK). No other Windows-abs refs remain in the skill.

**CLOUD MEMORY MODEL (answers the divergence question):** In Managed Agents, do NOT rely on the Claude-Code auto-memory *feature* (settings.local.json is gitignored so it won't reach the cloud checkout; auto-memory-write behavior in Managed Agents is not guaranteed same as CLI). Instead treat `.claude/memory/` as plain repo files: the agent READS them (skill step 1 already says so) and WRITES new findings as explicit file edits, then **commits + pushes / opens a PR**. **There is NO automatic sync** — `.claude/memory/` is synced ONLY via git. Local and cloud each write their own checkout → they WILL diverge unless reconciled by git. Recommended: cloud writes memory → PR (via GitHub MCP `create_pull_request`) → user reviews/merges → local `git pull`; local writes → push → cloud mounts fresh next session. Managed-agent sandboxes are ephemeral — unpushed cloud memory is lost at session end.

**MANAGED AGENTS RECIPE (beta header `managed-agents-2026-04-01`, auth = Anthropic API key; sources: github.com/anthropics/skills claude-api/shared/managed-agents-*):**
- `POST /v1/beta/environments` → `{type:"cloud", networking:{type:"unrestricted"}}` (unrestricted lets pip + yfinance out; else limited needs `allow_package_managers:true` + Yahoo hosts in `allowed_hosts`).
- `POST /v1/beta/agents` → model `claude-opus-5`, `tools:{agent_toolset_20260401:true}`, system prompt = validator role + "canonical memory is `.claude/memory/`; commit/PR memory changes", optional GitHub MCP server for PRs. Skills in the mounted repo's `.claude/skills/` **auto-load** (no explicit load step).
- Repo mount = `resources:[{type:"github_repository", url:"https://github.com/flyubenov/AgentStock", authorization_token:<PAT>, checkout:<branch>, mount_path defaults /workspace/AgentStock}]` (token via Anthropic git proxy, never in container). PRs need BOTH the repo resource AND a GitHub MCP server (vault-stored creds).
- `POST /v1/beta/sessions` {agent_id, environment_id, vault_ids, resources}. Then `POST /v1/beta/sessions/{id}/messages`. First action in sandbox: `pip install -r backend/requirements.txt`, then `python3 .claude/skills/validating-agent-stock/validate_ticker.py TICKER --inputs`.

**CAVEATS:** (a) yfinance from a datacenter IP (Anthropic cloud) may be throttled/blocked by Yahoo — engine already has pacing/retry ([[yfinance-dedicated-pool]], [[recalculate-all-flow-control]]) but cloud reliability is a real risk. (b) `pip install` is a per-session cost unless a self-hosted/cached sandbox is used. (c) settings.local.json is gitignored → cloud sets memory behavior via skill instructions, not the setting.

**NEXT:** commit the memory migration + SKILL.md edits; then (optionally) stand up the Managed Agents environment/agent/session per the recipe.
