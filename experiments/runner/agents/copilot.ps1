<#
.SYNOPSIS
    GitHub Copilot CLI 어댑터 (실험적).

.DESCRIPTION
    GitHub Copilot CLI (`gh copilot`) 는 현재 대화형 보조 위주이고,
    **코드베이스를 직접 수정하는 비대화형 모드** 는 공식적으로 제한적입니다.
    따라서 본 어댑터는 두 가지 모드를 지원합니다:

    1) -Extra @{ Mode = 'suggest' }  (기본)
       - `gh copilot suggest -t shell "<prompt>"` 호출.
       - **1 turn 답변만** 받아 stream 파일로 저장.
       - 코드 수정까지는 하지 않으므로 본 실험에서는 "정보성" 조건으로만 유용.

    2) -Extra @{ Mode = 'custom' ; Cmd = '<template>' }
       - 사용자 정의 템플릿 실행 (`custom.ps1` 과 동일 동작).
       - 예: `copilot-cli --model ${MODEL} --prompt-file ${PROMPT_FILE}`

    일반적으로 Copilot 환경에서 실험을 할 때는 VS Code Copilot Chat 에서 수동으로 진행하고,
    본 레포는 `agents/manual.ps1` 로 워크스페이스만 준비하는 방식이 현실적입니다.
#>
param(
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$PromptFile,
    [Parameter(Mandatory)][string]$Model,
    [Parameter(Mandatory)][string]$StreamOut,
    [Parameter(Mandatory)][string]$MetaOut,
    [int]$TimeoutSec = 1800,
    [hashtable]$Extra = @{}
)

. "$PSScriptRoot\_common.ps1"

$started = Get-Date
$mode = if ($Extra.ContainsKey('Mode')) { $Extra.Mode } else { 'suggest' }

if ($mode -eq 'custom') {
    # custom 모드로 위임
    $customAdapter = Join-Path $PSScriptRoot 'custom.ps1'
    & $customAdapter -Workspace $Workspace -PromptFile $PromptFile -Model $Model `
        -StreamOut $StreamOut -MetaOut $MetaOut -TimeoutSec $TimeoutSec -Extra $Extra
    exit $LASTEXITCODE
}

$gh = Get-Command 'gh' -ErrorAction SilentlyContinue
if (-not $gh) {
    Write-AdapterLog "gh CLI not found. Install: https://cli.github.com/" -Level ERROR
    '{"event":"adapter_error","message":"gh not in PATH"}' | Set-Content -Path $StreamOut -Encoding UTF8
    $meta = New-AdapterMeta -Agent 'copilot' -Model $Model `
        -Started $started -Finished (Get-Date) -ExitCode 127 `
        -PromptFile $PromptFile -StreamOut $StreamOut -Notes 'gh not in PATH'
    Save-AdapterMeta -Meta $meta -MetaOut $MetaOut
    exit 127
}

Write-AdapterLog "gh copilot suggest (mode=$mode) workspace=$Workspace"
$prompt = Get-Content $PromptFile -Raw -Encoding UTF8
$argv = @('copilot', 'suggest', '-t', 'shell', $prompt)

$result = Invoke-WithTimeout `
    -FilePath 'gh' `
    -ArgumentList $argv `
    -StdoutFile $StreamOut `
    -TimeoutSec $TimeoutSec `
    -WorkingDirectory $Workspace

$finished = Get-Date
if ($result.TimedOut) { Write-AdapterLog "copilot TIMED OUT" -Level ERROR }

$meta = New-AdapterMeta -Agent 'copilot' -Model $Model `
    -Started $started -Finished $finished -ExitCode $result.ExitCode `
    -PromptFile $PromptFile -StreamOut $StreamOut `
    -Notes "mode=$mode (Copilot CLI is limited to suggestion; for full coding prefer manual adapter)"
Save-AdapterMeta -Meta $meta -MetaOut $MetaOut

exit $result.ExitCode
