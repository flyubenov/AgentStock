---
name: cloud-deploy-validating-skill
description: Plan + progress for running the validating-agent-stock skill in the cloud (Claude Platform Managed Agents), the project-canonical in-repo memory setup, and the verified deploy recipe (Console-UI + PowerShell/curl hybrid).
metadata:
  type: project
---

**Goal:** run `/validating-agent-stock` on Claude Platform **Managed Agents** so it works like local. User has Claude Platform + Google Cloud Run; chose Managed Agents (least plumbing) over Cloud Run.

**Key fact — the skill is NOT a deployable service.** Agent *instructions* (`SKILL.md` + `risk-reward-validation.md`) + harness (`validate_ticker.py`) that imports the real backend engine. Cloud needs: the repo, deps (`backend/requirements.txt`), yfinance egress, a Claude runtime + Anthropic **API key** (Managed Agents is an API product — the subscription alone isn't the key).

**MEMORY MADE PROJECT-CANONICAL (Option B-clean) — DONE 2026-08-09, STILL NOT COMMITTED:**
1. Migrated live external auto-memory → in-repo `.claude/memory/` (41 files, byte-identical). **37 modified + 2 new are staged but NOT committed. NEXT: commit + push to `origin/main` BEFORE any cloud run** (cloud clones from GitHub; local `master` tracks `origin/main`).
2. `autoMemoryDirectory` = abs `C:/Users/f_lub/proj/Agent Stock/.claude/memory` in gitignored `.claude/settings.local.json` (machine-local). Verified in official docs: read from any settings scope; MUST be absolute or `~/`. Also exists: `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`, per-project `autoMemoryEnabled:false`. Activates next session after workspace-trust prompt → then local reads (MEMORY.md injection) + writes both hit the in-repo dir.
3. SKILL.md repointed: line-25 memory → `.claude/memory/`; run block → `python3` (verified works locally + Linux; deps import OK).

**CLOUD MEMORY MODEL / divergence answer:** In Managed Agents, treat `.claude/memory/` as plain repo files (settings.local.json is gitignored → doesn't reach cloud; don't rely on the auto-memory feature there). Agent READS them (skill step 1) and WRITES findings as file edits → commit + push / PR. **NO auto-sync — git is the only sync bus; local & cloud diverge unless reconciled.** Recommend: cloud writes → branch + PR (GitHub MCP `create_pull_request`) → user reviews/merges → local `git pull`. Ephemeral sandboxes → unpushed cloud memory is lost. (Alt not chosen: platform **managed memory store**, beta `agent-memory-2026-07-22`, mounts `/mnt/memory/`, server-side persistence — user deliberately picked repo+git for reviewable/versioned knowledge.)

**VERIFIED Managed Agents API (official docs platform.claude.com, beta header `managed-agents-2026-04-01`; the community `anthropics/skills` doc's `/v1/beta/...` paths were WRONG):**
- Endpoints: `POST /v1/environments`, `/v1/agents`, `/v1/sessions`, `/v1/sessions/{id}/events`, `/v1/sessions/{id}/resources`. Header `anthropic-beta: managed-agents-2026-04-01` + `x-api-key` + `anthropic-version: 2023-06-01`.
- Environment: `{name, config:{type:"cloud", networking:{type:"unrestricted"}, packages:{pip:[...]}}}`. `packages.pip` PRE-INSTALLS + CACHES across sessions (skip per-session pip). `limited` needs `allow_package_managers:true`+`allowed_hosts`.
- Agent: `{name, model:"claude-opus-5", system, tools:[{type:"agent_toolset_20260401"}], mcp_servers:[{type:"url",name:"github",url:"https://api.githubcopilot.com/mcp/"}], tools+{type:"mcp_toolset",mcp_server_name:"github"}}`. GitHub MCP only needed for auto-PRs.
- **Repo mount (session)**: `resources:[{type:"github_repository", url, mount_path (default /workspace/<repo>), checkout (default def branch), authorization_token (PAT repo-scope; authenticates clone, never echoed)}]`. **Skills in the mounted repo's root `.claude/skills` AUTO-LOAD at session start** — so DON'T attach the skill from the org library; the mount delivers it. Repos cached.
- Session create can seed+start with `initial_events:[{type:"user.message",content:[{type:"text",text:...}]}]`. Send more via `/events`. Budget via `budget:{type:"limit",max_list_cost:{amount:"2500",currency:"USD"}}`.

**RECOMMENDED HYBRID FLOW:** (1) Build agent in Console UI at `platform.claude.com/workspaces/default/agent-quickstart` (model, validator system prompt, agent toolset, optional GitHub MCP; UI test-chat can't run harness — no repo mounted there); copy `agent_id`. (2) Create environment + session (with repo mount) via CLI/curl/PowerShell. (3) Open `platform.claude.com/workspaces/default/sessions/{id}`, send `cd /workspace/AgentStock && pip install -r backend/requirements.txt` then `python3 .claude/skills/validating-agent-stock/validate_ticker.py PLTR --inputs`.

**`ant` CLI GOTCHA (2026-08-09):** NOT on npm — `npm i -g @anthropic-ai/ant` = 404. Only `brew install anthropics/tap/ant` or `go install github.com/anthropics/anthropic-cli/cmd/ant@latest` (needs Go 1.22+). Auth `ant auth login` or `ANTHROPIC_API_KEY`. In `ant`, session `resources` pass via **stdin YAML** (verified), not a confirmed `--resources` flag. User's Windows box: has curl + python3, LACKS jq + go + ant. **RESOLUTION: use PowerShell `Invoke-RestMethod`** (native JSON→objects, no jq/ant/install). PowerShell Step-2 snippet delivered (env create + session create w/ github_repository resource via `@"..."@` here-string). Git-Bash+curl+python3 (`python3 -c "import sys,json;print(json.load(sys.stdin)['id'])"`, no jq) is the bash alt.

**CAVEATS:** (a) yfinance from Anthropic datacenter IP may be throttled by Yahoo — real reliability risk (engine has pacing/retry: [[yfinance-dedicated-pool]], [[recalculate-all-flow-control]]). (b) per-session `pip install` unless `packages.pip` pre-cached in env. (c) full deploy script (curl, deps pre-baked) saved to session scratchpad `deploy_managed_agent.sh` (ephemeral — regenerate if needed).

**NEXT when resumed:** commit + push the memory migration + SKILL.md edits to `origin/main`; user builds the agent in Console UI (get agent_id), runs the PowerShell Step-2 (needs API key + PAT), drives validations in the browser. Offered but pending: (a) I commit+push the pending changes; (b) Git-Bash/curl variant of Step 2.
