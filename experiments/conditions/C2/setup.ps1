# ============================================================
# C2 — Split
# - REQUIREMENTS.md + docs/architecture.md + docs/api.md + docs/db.md
# - AGENTS.md / ADR 는 아직 없음. "설계 문서 분할이 도움 되는가" 를 본다.
# ============================================================
param(
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$TaskId
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\runner\lib\common.ps1"

$docsRoot = Get-DocsRoot -ScriptDir $PSScriptRoot
Write-Log "C2.setup Workspace=$Workspace TaskId=$TaskId"

Initialize-Workspace -Workspace $Workspace
Copy-Requirements -DocsRoot $docsRoot -TaskId $TaskId -Workspace $Workspace
Copy-DesignDocs -DocsRoot $docsRoot -Workspace $Workspace

Write-ConditionManifest -Workspace $Workspace -Condition 'C2' -TaskId $TaskId `
    -PlacedFiles @('REQUIREMENTS.md', 'docs/architecture.md', 'docs/api.md', 'docs/db.md')
Write-Log "C2.setup done"
