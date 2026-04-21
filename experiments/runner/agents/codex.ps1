<#
.SYNOPSIS
    OpenAI Codex CLI 어댑터. 비대화형 `codex exec` 사용.

.DESCRIPTION
    공식 CLI: `@openai/codex` (npm 설치) 또는 `codex` 바이너리.
    참고: https://github.com/openai/codex

    본 어댑터는 다음 호출을 시도:
        codex exec --model <M> --json --output-last-message <STREAM_OUT> "<prompt>"

    - `exec` 은 Codex CLI 의 비대화형 모드.
    - 실제 플래그 이름/형식은 Codex CLI 버전에 따라 달라질 수 있으므로,
      문제가 있으면 -Extra @{ ExtraArgs = '--some-flag val' } 로 주입하거나,
      `custom.ps1` 어댑터를 사용하여 템플릿 커맨드를 직접 지정하세요.

.NOTES
    OPENAI_API_KEY 등 인증은 사용자의 환경변수/CLI 구성에 위임.
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

# codex 바이너리가 없으면 에러 대신 meta 기록 후 non-zero exit
$codex = Get-Command 'codex' -ErrorAction SilentlyContinue
$started = Get-Date
if (-not $codex) {
    Write-AdapterLog "codex CLI not found. Install: npm i -g @openai/codex (or equivalent)" -Level ERROR
    '{"event":"adapter_error","message":"codex CLI not found"}' | Set-Content -Path $StreamOut -Encoding UTF8
    $meta = New-AdapterMeta -Agent 'codex' -Model $Model `
        -Started $started -Finished (Get-Date) -ExitCode 127 `
        -PromptFile $PromptFile -StreamOut $StreamOut -Notes 'codex not in PATH'
    Save-AdapterMeta -Meta $meta -MetaOut $MetaOut
    exit 127
}

$prompt = Get-Content $PromptFile -Raw -Encoding UTF8
Write-AdapterLog "codex exec model=$Model workspace=$Workspace"

# Base args
$argv = @('exec', '--model', $Model, '--json')
# Extra.ExtraArgs 가 공백 구분된 문자열로 주어지면 토큰화해 뒤에 붙임
if ($Extra.ContainsKey('ExtraArgs') -and $Extra.ExtraArgs) {
    $tokens = $Extra.ExtraArgs -split '\s+'
    $argv += $tokens
}
# 마지막에 프롬프트 텍스트(동일 동작을 위해 문자열로 전달)
$argv += $prompt

$result = Invoke-WithTimeout `
    -FilePath 'codex' `
    -ArgumentList $argv `
    -StdoutFile $StreamOut `
    -TimeoutSec $TimeoutSec `
    -WorkingDirectory $Workspace

$finished = Get-Date
if ($result.TimedOut) { Write-AdapterLog "codex TIMED OUT" -Level ERROR }
if ($result.StdErr)   { Write-AdapterLog "stderr:`n$($result.StdErr.Substring(0,[math]::Min(500,$result.StdErr.Length)))" -Level WARN }

$meta = New-AdapterMeta -Agent 'codex' -Model $Model `
    -Started $started -Finished $finished -ExitCode $result.ExitCode `
    -PromptFile $PromptFile -StreamOut $StreamOut `
    -Notes ("timed_out=" + $result.TimedOut)
Save-AdapterMeta -Meta $meta -MetaOut $MetaOut

exit $result.ExitCode
