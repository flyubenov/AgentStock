---
name: cloud-deploy-validating-skill
description: "Running the validating-agent-stock skill in the cloud on Claude Platform Managed Agents - DEPLOYED + WORKING, plus the reusable PowerShell scripts, cost optimizations, and the gotchas hit along the way."
metadata: 
  node_type: memory
  type: project
  originSessionId: 3fad56d0-a91a-4ccf-9e7c-77bb90773527
  modified: 2026-08-10T10:16:33.929Z
---

**STATUS: DEPLOYED + WORKING (2026-08-10).** `/validating-agent-stock` runs on Claude Platform **Managed Agents**; PLTR validated live in the cloud (verdict returned). Chose Managed Agents over Google Cloud Run.

**The skill is NOT a service** - agent *instructions* (`SKILL.md` + `risk-reward-validation.md`) + harness (`validate_ticker.py`) importing the real backend engine. Cloud needs: repo mounted, deps, yfinance egress, Anthropic **API key** (Managed Agents is an API product, billed on API credits - not covered by a subscription).

**MEMORY IS PROJECT-CANONICAL (Option B-clean), COMMITTED + PUSHED to `origin/main`:** in-repo `.claude/memory/` (41 files) is the source of truth; `autoMemoryDirectory` = abs repo path in gitignored `.claude/settings.local.json` (local reads+writes hit the in-repo dir); SKILL.md line-25 memory ref -> `.claude/memory/`, run block -> `python3`. Cloud memory = plain repo files, synced ONLY via git (NO auto-sync; local+cloud diverge unless reconciled; cloud writes -> branch/PR -> review -> local pull). See [[validating-skill-rr-extension]].

**LIVE DEPLOYMENT (workspace = the one the API key belongs to, NOT necessarily "default"):**
- Environment `agentstock-env`: cloud, `networking.unrestricted`, `packages.pip` pre-caches all of `backend/requirements.txt` (no per-session pip).
- Agent `agentstock-validator`: created `claude-opus-5` + `agent_toolset_20260401`. **Updated to v2** with a lean system prompt (see cost section). GitHub MCP NOT added (memory-writeback PRs would need `mcp_servers:[{type:url,name:github,url:https://api.githubcopilot.com/mcp/}]` + `mcp_toolset`).
- Session mounts the repo via `resources:[{type:github_repository,url,mount_path:/workspace/AgentStock,authorization_token:PAT}]`; **skills auto-load from the mounted repo's `.claude/skills`**. Drive in browser at `platform.claude.com/workspaces/<SLUG>/sessions/<id>` or via API.

**REUSABLE SCRIPTS at repo root (NEW, untracked, NO secrets - safe to commit; secrets read from `$env:ANTHROPIC_API_KEY` + `$env:GITHUB_TOKEN`):**
- `SetupClaudePlatform.ps1` - one-time full setup (env + agent + first session). (User's earlier runs were SetupClaudePlatform.ps1 / SetupClaudePlatform2.ps1.)
- `new_session.ps1` - reusable: `-Ticker` (def PLTR), `-Model` (def `claude-sonnet-5`; pass `claude-opus-5` for deep analysis, via per-session `agent_with_overrides`), `-BudgetUSD` (def 2; 0=none), `-Workspace`. Looks up env+agent by name, mounts repo, seeds a concise validation.
- `update_agent.ps1` - `POST /v1/agents/{id}` to patch the system prompt (creates a new version).

**COST + OPTIMIZATION:** PLTR cost **$1.85 on Opus** - too high. Drivers: (1) Opus model, (2) `--inputs` mega-dump re-sent every turn, (3) heavy upfront memory/code reading, (4) loop length. Done (**B+C, agent-only**): `new_session.ps1` defaults to **Sonnet 5** (~4-5x cheaper, per-session override so Opus agent intact); agent **v2 lean prompt** = run harness WITHOUT `--inputs` by default, read ONLY the driver's memory entry + code comment, concise verdict, single run, no re-reads, escalate only if the number looks wrong; `new_session.ps1` seeded message no longer forces `--inputs` (would override the agent). **Residual (D, NOT done):** `SKILL.md` still says "use `--inputs` every time" + read memory/comments - the agent prompt overrides but if it still over-reads, edit SKILL.md to make the default lean (that edit changes LOCAL behavior too + needs commit+push to reach cloud).

**VERIFIED API FACTS (official platform.claude.com docs; the community `anthropics/skills` `/v1/beta/...` paths were WRONG):** endpoints are `/v1/environments|agents|sessions|sessions/{id}/events|resources` + header `anthropic-beta: managed-agents-2026-04-01` (+`x-api-key`+`anthropic-version:2023-06-01`). Agent update = POST `/v1/agents/{id}`, omitted fields preserved, creates a new **version** (starts at 1); sessions referencing the agent id **string** use the LATEST version, running sessions keep theirs. Per-session model override = `agent:{type:agent_with_overrides,id,model:{id}}` (an `effort` inside a per-session model override is IGNORED - set effort on the agent). Budget only settable at **creation**: `budget:{type:limit,max_list_cost:{amount:"2500"(=whole CENTS string),currency:"USD"}}`; on hit -> idle, stop_reason `budget_reached`. Also: managed **memory store** alt exists (beta `agent-memory-2026-07-22`, mounts `/mnt/memory/`) - NOT chosen (repo+git preferred).

**GOTCHAS HIT + FIXES:** (a) `npm i -g @anthropic-ai/ant` = **404** - `ant` is Go/brew only (`go install github.com/anthropics/anthropic-cli/cmd/ant@latest`); box lacks go+jq+ant -> **use PowerShell `Invoke-RestMethod`** (native JSON, no deps). (b) `github_repository` **`checkout` field -> 400** Bad Request; OMIT it (mount uses repo default branch = `main`). (c) PowerShell `$MountPath:` -> parser error (`:` after a var = scope/drive) -> use `${MountPath}`. (d) Console URL "session not found" = the hardcoded `/workspaces/default/` slug is wrong; use the API key's actual workspace slug (from the browser address bar) or the Console session list. (e) PS 5.1 needs `[Net.ServicePointManager]::SecurityProtocol = Tls12`; `.ps1` vars don't persist after the script aborts.

**CAVEAT:** yfinance from Anthropic's datacenter IP may be Yahoo-throttled (engine has retry/pacing: [[yfinance-dedicated-pool]], [[recalculate-all-flow-control]]).

**NEXT / open:** re-run PLTR on Sonnet+v2 to measure new cost; optionally do the D SKILL.md lean edit; optionally add GitHub MCP for memory-writeback PRs; optionally commit the 3 `.ps1` helpers to the repo.
