<#
  new_session.ps1 — start a fresh Managed Agents session that mounts the
  Agent Stock repo and validates one ticker.

  Reuses the persistent environment + agent created by the full setup script
  (looked up by name), so this only creates a new session.

  Prereqs (once per PowerShell window):
    $env:ANTHROPIC_API_KEY = "sk-ant-..."     # Anthropic API key
    $env:GITHUB_TOKEN      = "github_pat_..."  # fine-grained PAT, repo scope

  Examples:
    .\new_session.ps1                                  # PLTR, $25 cap
    .\new_session.ps1 -Ticker NVDA                     # different ticker
    .\new_session.ps1 -Ticker TEM -BudgetUSD 10        # $10 cap
    .\new_session.ps1 -Ticker AMD -BudgetUSD 0         # no cap
    .\new_session.ps1 -Ticker MU  -Workspace wrksp_xxx # clickable Console URL
#>
param(
  [string]$Ticker    = "PLTR",
  [int]   $BudgetUSD = 2,          # hard spend cap in whole USD; 0 = no cap
  [string]$Model     = "claude-sonnet-5",  # cheap default; use claude-opus-5 for deep engine analysis
  [string]$Workspace = "default"    # set to your real workspace slug for a clickable URL
)

$ErrorActionPreference = "Stop"

# ── Fixed config ─────────────────────────────────────────────────────────────
$RepoUrl   = "https://github.com/flyubenov/AgentStock"
$MountPath = "/workspace/AgentStock"
$EnvName   = "agentstock-env"
$AgentName = "agentstock-validator"
$Base      = "https://api.anthropic.com/v1"

# ── Secrets from environment ─────────────────────────────────────────────────
$ApiKey      = $env:ANTHROPIC_API_KEY
$GitHubToken = $env:GITHUB_TOKEN
if (-not $ApiKey)      { throw "Set `$env:ANTHROPIC_API_KEY first." }
if (-not $GitHubToken) { throw "Set `$env:GITHUB_TOKEN first (GitHub PAT, repo scope)." }

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Headers = @{
  "x-api-key"         = $ApiKey
  "anthropic-version" = "2023-06-01"
  "anthropic-beta"    = "managed-agents-2026-04-01"
}

# ── Reuse the existing environment + agent (created once by the full setup) ──
$EnvId = ((Invoke-RestMethod -Uri "$Base/environments" -Headers $Headers).data |
          Where-Object { $_.name -eq $EnvName } | Select-Object -First 1).id
$AgentId = ((Invoke-RestMethod -Uri "$Base/agents" -Headers $Headers).data |
          Where-Object { $_.name -eq $AgentName } | Select-Object -First 1).id
if (-not $EnvId)   { throw "Environment '$EnvName' not found run the full setup script first." }
if (-not $AgentId) { throw "Agent '$AgentName' not found run the full setup script first." }

# ── Agent field: plain id, or an agent_with_overrides to swap the model ──────
if ($Model) {
  $agentField = "{ ""type"": ""agent_with_overrides"", ""id"": ""$AgentId"", ""model"": { ""id"": ""$Model"" } }"
} else {
  $agentField = """$AgentId"""
}

# ── Optional budget fragment (amount is WHOLE CENTS as a string) ─────────────
$budgetJson = ""
if ($BudgetUSD -gt 0) {
  $cents = [string]([int]($BudgetUSD * 100))
  $budgetJson = ",`n  ""budget"": { ""type"": ""limit"", ""max_list_cost"": { ""amount"": ""$cents"", ""currency"": ""USD"" } }"
}

# ── Create the session: mount the repo + seed the first validation ───────────
$body = @"
{
  "agent": $agentField,
  "environment_id": "$EnvId",
  "resources": [
    { "type": "github_repository", "url": "$RepoUrl", "mount_path": "$MountPath",
      "authorization_token": "$GitHubToken" }
  ],
  "initial_events": [
    { "type": "user.message", "content": [ { "type": "text",
      "text": "Validate $Ticker. Give a concise verdict; follow your default lean flow (run the harness without --inputs unless the number looks off)." } ] }
  ]$budgetJson
}
"@

try {
  $s = Invoke-RestMethod -Method Post -Uri "$Base/sessions" -Headers $Headers -ContentType "application/json" -Body $body
  Write-Host ""
  Write-Host "Session:  $($s.id)"
  Write-Host "Ticker:   $Ticker"
  Write-Host "Model:    $(if ($Model) { $Model } else { 'agent default (claude-opus-5)' })"
  if ($BudgetUSD -gt 0) { Write-Host "Budget:   `$$BudgetUSD USD cap" } else { Write-Host "Budget:   none" }
  Write-Host "Open:     https://platform.claude.com/workspaces/$Workspace/sessions/$($s.id)"
}
catch {
  Write-Host "HTTP $($_.Exception.Response.StatusCode.value__)"
  if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message }
  else { (New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() }
}
