# ============================================================
# C4 — ContinualDocs
# - C3의 모든 파일 + continual-learning 플러그인 활성화.
# - 이 조건은 "연속 3 task" 로 평가되어야 의미가 있다 (task-1 → 2 → 3 순차).
# - runner 는 rep 단위로 .cursor/hooks/state/ 를 초기화한다.
# ============================================================
param(
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$TaskId,
    [switch]$KeepState   # 연속 task 2, 3 에서 runner 가 true 로 넘겨 상태 유지
)

$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\..\runner\lib\common.ps1"

$docsRoot = Get-DocsRoot -ScriptDir $PSScriptRoot
Write-Log "C4.setup Workspace=$Workspace TaskId=$TaskId KeepState=$KeepState"

if (-not $KeepState) {
    # rep 시작: workspace 초기화 + continual-learning state 리셋
    Initialize-Workspace -Workspace $Workspace
    Copy-Requirements -DocsRoot $docsRoot -TaskId $TaskId -Workspace $Workspace
    Copy-DesignDocs   -DocsRoot $docsRoot -Workspace $Workspace
    Copy-AdrAndAgents -DocsRoot $docsRoot -Workspace $Workspace
    Enable-ContinualLearning -Workspace $Workspace
} else {
    # 같은 rep 내 후속 task: AGENTS.md 의 학습된 내용은 보존, REQUIREMENTS.md 만 교체
    Write-Log "KeepState mode: only swap REQUIREMENTS.md"
    $reqPath = Join-Path $Workspace 'REQUIREMENTS.md'
    if (Test-Path $reqPath) { Remove-Item -Force $reqPath }
    Copy-Requirements -DocsRoot $docsRoot -TaskId $TaskId -Workspace $Workspace
}

Write-ConditionManifest -Workspace $Workspace -Condition 'C4' -TaskId $TaskId `
    -PlacedFiles @(
        'REQUIREMENTS.md',
        'AGENTS.md',
        'docs/architecture.md',
        'docs/api.md',
        'docs/db.md',
        'docs/adr/*',
        '.cursor/continual-learning.enabled'
    )
Write-Log "C4.setup done"
