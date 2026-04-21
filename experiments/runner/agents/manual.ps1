<#
.SYNOPSIS
    수동(human-in-the-loop) 어댑터.
    워크스페이스와 프롬프트만 준비한 뒤, 사용자가 **IDE/채팅에서 직접 에이전트를 실행**한다.

.DESCRIPTION
    실험 자동화가 불가능한 에이전트(예: VS Code Copilot Chat GUI, Cursor IDE 대화, 웹 챗)를 위한 모드.

    흐름:
    1. 워크스페이스와 프롬프트 파일을 생성하고 안내문 출력.
    2. 사용자가 해당 워크스페이스를 IDE로 열고 에이전트를 호출.
    3. 작업이 끝나면, 사용자가 Enter 를 눌러 본 스크립트가 complete 신호로 meta.json 을 마감.
    4. stream_out 에는 "manual" 사실을 명시한 placeholder 이벤트를 기록.

    -Extra @{ NonInteractive = $true } 옵션을 주면 대기 없이 즉시 meta 만 남기고 끝낸다.
    (CI 테스트용)

.NOTES
    완전 자동화는 아니지만, Copilot GUI / 수동 Codex 세션 등의 **통제된 수집** 을 돕는다.
    사용자는 작업 후 workspace 상태(코드+테스트)를 그대로 두어야 하며, runner 가 이어서 품질 게이트를 실행한다.
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
$nonInteractive = $Extra.ContainsKey('NonInteractive') -and [bool]$Extra.NonInteractive

Write-Host "=================================================="
Write-Host " [manual adapter] ready for human-in-the-loop run"
Write-Host "   model      : $Model"
Write-Host "   workspace  : $Workspace"
Write-Host "   promptFile : $PromptFile"
Write-Host "   streamOut  : $StreamOut"
Write-Host "   timeoutSec : $TimeoutSec"
Write-Host "--------------------------------------------------"
Write-Host " 1) 위 workspace 경로를 IDE 로 열고, 원하는 에이전트(예: Copilot Chat) 로"
Write-Host "    PROMPT_FILE 의 내용을 붙여넣어 작업을 수행하세요."
Write-Host " 2) 테스트 코드까지 생성되었는지 확인한 뒤"
Write-Host "    Enter 키를 눌러 이 창으로 돌아와 완료를 확정하세요."
Write-Host "    (취소하려면 Ctrl+C 로 중단)"
Write-Host "=================================================="

$notes = "manual run"
if ($nonInteractive) {
    Write-AdapterLog "NonInteractive: skipping wait"
    $notes += " (non-interactive skip)"
} else {
    try {
        # 타임아웃 대기
        $deadline = (Get-Date).AddSeconds($TimeoutSec)
        while ($true) {
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true)
                if ($key.Key -eq 'Enter') { break }
            }
            if ((Get-Date) -ge $deadline) {
                Write-AdapterLog "manual wait timed out after $TimeoutSec sec" -Level WARN
                $notes += " (timed out waiting for user)"
                break
            }
            Start-Sleep -Milliseconds 250
        }
    } catch {
        Read-Host "Enter 를 눌러 완료"
    }
}

$finished = Get-Date

# placeholder stream (evaluate 는 파일 기반 품질 게이트로 대체 평가)
$placeholder = @{
    event    = "manual_run"
    model    = $Model
    workspace = $Workspace
    started  = $started.ToString('o')
    finished = $finished.ToString('o')
    note     = "human-in-the-loop; stream not captured"
} | ConvertTo-Json -Compress
$placeholder | Set-Content -Path $StreamOut -Encoding UTF8

$meta = New-AdapterMeta -Agent 'manual' -Model $Model `
    -Started $started -Finished $finished -ExitCode 0 `
    -PromptFile $PromptFile -StreamOut $StreamOut `
    -Notes $notes
Save-AdapterMeta -Meta $meta -MetaOut $MetaOut
exit 0
