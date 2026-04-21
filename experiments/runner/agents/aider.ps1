<#
.SYNOPSIS
    Aider 어댑터. `aider --model <M> --yes --no-pretty --message-file <prompt>` 로 1 회 실행.

.DESCRIPTION
    Aider (https://aider.chat) 는 파일을 직접 수정하는 CLI 코딩 에이전트.
    - `--yes` 로 자동 승인
    - `--no-pretty` 로 파싱 친화 출력
    - `--message-file` 로 프롬프트 전달
    - `--no-stream`, `--no-auto-commits` 등 환경에 맞춰 Extra 로 확장

    OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 등 Aider 가 요구하는 환경변수는 사용자 쉘에 설정되어야 함.

.NOTES
    모델명 예시:
      - openai/gpt-4o
      - anthropic/claude-3-7-sonnet-20250219
      - deepseek/deepseek-coder
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

$aider = Get-Command 'aider' -ErrorAction SilentlyContinue
$started = Get-Date
if (-not $aider) {
    Write-AdapterLog "aider CLI not found. Install: pip install aider-chat" -Level ERROR
    '{"event":"adapter_error","message":"aider not in PATH"}' | Set-Content -Path $StreamOut -Encoding UTF8
    $meta = New-AdapterMeta -Agent 'aider' -Model $Model `
        -Started $started -Finished (Get-Date) -ExitCode 127 `
        -PromptFile $PromptFile -StreamOut $StreamOut -Notes 'aider not in PATH'
    Save-AdapterMeta -Meta $meta -MetaOut $MetaOut
    exit 127
}

Write-AdapterLog "aider model=$Model workspace=$Workspace"

$argv = @(
    '--model', $Model,
    '--yes',
    '--no-pretty',
    '--no-stream',
    '--no-auto-commits',
    '--message-file', $PromptFile
)
if ($Extra.ContainsKey('ExtraArgs') -and $Extra.ExtraArgs) {
    $argv += ($Extra.ExtraArgs -split '\s+')
}

$result = Invoke-WithTimeout `
    -FilePath 'aider' `
    -ArgumentList $argv `
    -StdoutFile $StreamOut `
    -TimeoutSec $TimeoutSec `
    -WorkingDirectory $Workspace

$finished = Get-Date
if ($result.TimedOut) { Write-AdapterLog "aider TIMED OUT" -Level ERROR }
if ($result.StdErr)   { Write-AdapterLog "stderr:`n$($result.StdErr.Substring(0,[math]::Min(500,$result.StdErr.Length)))" -Level WARN }

$meta = New-AdapterMeta -Agent 'aider' -Model $Model `
    -Started $started -Finished $finished -ExitCode $result.ExitCode `
    -PromptFile $PromptFile -StreamOut $StreamOut `
    -Notes ("timed_out=" + $result.TimedOut)
Save-AdapterMeta -Meta $meta -MetaOut $MetaOut

exit $result.ExitCode
