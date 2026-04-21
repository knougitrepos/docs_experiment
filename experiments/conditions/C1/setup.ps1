# ============================================================
# C1 — SingleReq
# - workspace 루트에 REQUIREMENTS.md 1개만 제공한다.
# - 해당 task 의 요구사항 파일을 그대로 복사.
# ============================================================
param(
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$TaskId
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\runner\lib\common.ps1"

$docsRoot = Get-DocsRoot -ScriptDir $PSScriptRoot
Write-Log "C1.setup Workspace=$Workspace TaskId=$TaskId"

Initialize-Workspace -Workspace $Workspace
Copy-Requirements -DocsRoot $docsRoot -TaskId $TaskId -Workspace $Workspace

Write-ConditionManifest -Workspace $Workspace -Condition 'C1' -TaskId $TaskId `
    -PlacedFiles @('REQUIREMENTS.md')
Write-Log "C1.setup done"
