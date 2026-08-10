<#
  update_agent.ps1 — patch the agentstock-validator agent's system prompt to a
  lean, cost-efficient flow:
    B) run the harness WITHOUT --inputs by default; add --inputs only on demand
    C) concise verdict, single harness run, targeted memory/comment lookup, no re-reads

  Creates a new agent version. New sessions (via new_session.ps1) pick it up
  automatically; already-running sessions keep the version they started with.

  Prereq:  $env:ANTHROPIC_API_KEY = "sk-ant-..."
#>
$ErrorActionPreference = "Stop"
$AgentName = "agentstock-validator"
$Base      = "https://api.anthropic.com/v1"

$ApiKey = $env:ANTHROPIC_API_KEY
if (-not $ApiKey) { throw "Set `$env:ANTHROPIC_API_KEY first." }

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Headers = @{
  "x-api-key"         = $ApiKey
  "anthropic-version" = "2023-06-01"
  "anthropic-beta"    = "managed-agents-2026-04-01"
}

$AgentId = ((Invoke-RestMethod -Uri "$Base/agents" -Headers $Headers).data |
            Where-Object { $_.name -eq $AgentName } | Select-Object -First 1).id
if (-not $AgentId) { throw "Agent '$AgentName' not found run the full setup script first." }

# One-line JSON string value (no raw newlines, no double quotes inside).
$body = @"
{
  "system": "You validate Agent Stock Fair Value, Quality, and Risk-Reward results for one ticker using the validating-agent-stock skill mounted at /workspace/AgentStock/.claude/skills. Always work from /workspace/AgentStock. Be concise and cost-efficient. Default flow: (1) run python3 .claude/skills/validating-agent-stock/validate_ticker.py TICKER WITHOUT the --inputs flag; (2) read only the MEMORY.md entry and the ticker-tagged code comment for the specific driver behind the number - do not read the whole memory dir and do not grep broadly; (3) give a short verdict of a few sentences with the key evidence. Escalate only when the number looks wrong or the user asks for a deep dive - then re-run with --inputs, grep the relevant engine code, and read more memory. Never re-read a file you have already read. If you prove a real gap worth remembering, write a markdown file into .claude/memory/, update MEMORY.md, commit to a NEW branch (never the default branch), push, and open a PR."
}
"@

try {
  $r = Invoke-RestMethod -Method Post -Uri "$Base/agents/$AgentId" -Headers $Headers -ContentType "application/json" -Body $body
  Write-Host "Updated agent $AgentId  ->  version $($r.version)"
}
catch {
  Write-Host "HTTP $($_.Exception.Response.StatusCode.value__)"
  if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message }
  else { (New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() }
}
