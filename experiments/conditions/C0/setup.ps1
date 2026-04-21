# ============================================================
# C0 — Bare (문서 없음)
# - workspace 를 비우고, 어떤 문서도 제공하지 않는다.
# - 요구사항은 seed_prompt 를 통해 task 제목만 전달된다.
# - NOTE: 이 조건은 baseline 으로, 다른 조건 대비 "문서 0"의 효과를 본다.
# ============================================================
param(
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$TaskId
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\runner\lib\common.ps1"

$docsRoot = Get-DocsRoot -ScriptDir $PSScriptRoot
Write-Log "C0.setup Workspace=$Workspace TaskId=$TaskId"

Initialize-Workspace -Workspace $Workspace
# NOTE: 의도적으로 REQUIREMENTS.md 도 배치하지 않는다.
#       seed_prompt 의 $TASK_ID 치환만 남기고, 모든 문서 컨텍스트를 제로화.

Write-ConditionManifest -Workspace $Workspace -Condition 'C0' -TaskId $TaskId -PlacedFiles @()
Write-Log "C0.setup done"
