# ============================================================
# C3 — StructuredDocs
# - C2의 파일 + docs/adr/* + 루트 AGENTS.md (전역 지침).
# - continual-learning 플러그인은 비활성 (C4 와의 차이가 자동유지 여부).
# ============================================================
param(
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$TaskId
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\runner\lib\common.ps1"

$docsRoot = Get-DocsRoot -ScriptDir $PSScriptRoot
Write-Log "C3.setup Workspace=$Workspace TaskId=$TaskId"

Initialize-Workspace -Workspace $Workspace
Copy-Requirements -DocsRoot $docsRoot -TaskId $TaskId -Workspace $Workspace
Copy-DesignDocs   -DocsRoot $docsRoot -Workspace $Workspace
Copy-AdrAndAgents -DocsRoot $docsRoot -Workspace $Workspace

Write-ConditionManifest -Workspace $Workspace -Condition 'C3' -TaskId $TaskId `
    -PlacedFiles @(
        'REQUIREMENTS.md',
        'AGENTS.md',
        'docs/architecture.md',
        'docs/api.md',
        'docs/db.md',
        'docs/adr/*'
    )
Write-Log "C3.setup done"
