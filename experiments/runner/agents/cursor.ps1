<#
.SYNOPSIS
    Cursor CLI 어댑터. `cursor-agent -p --force --output-format stream-json` 호출.

.NOTES
    Cursor Pro 구독 내에서 지원되는 모델명을 -Model 로 전달.
    예: sonnet, gpt-5, composer
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
Test-Command -Name 'cursor-agent' -InstallHint 'irm https://cursor.com/install?win32=true | iex' | Out-Null

$started = Get-Date
$prompt = Get-Content $PromptFile -Raw -Encoding UTF8

Write-AdapterLog "cursor-agent model=$Model workspace=$Workspace"

$argv = @(
    '-p', '--force',
    '--model', $Model,
    '--output-format', 'stream-json',
    $prompt
)

$result = Invoke-WithTimeout `
    -FilePath 'cursor-agent' `
    -ArgumentList $argv `
    -StdoutFile $StreamOut `
    -TimeoutSec $TimeoutSec `
    -WorkingDirectory $Workspace

$finished = Get-Date
if ($result.TimedOut) { Write-AdapterLog "cursor-agent TIMED OUT" -Level ERROR }
if ($result.StdErr)   { Write-AdapterLog "stderr:`n$($result.StdErr.Substring(0,[math]::Min(500,$result.StdErr.Length)))" -Level WARN }

# 토큰/step 힌트는 stream 파싱으로 evaluate.py 쪽에서 정확히 계산.
$meta = New-AdapterMeta -Agent 'cursor' -Model $Model `
    -Started $started -Finished $finished -ExitCode $result.ExitCode `
    -PromptFile $PromptFile -StreamOut $StreamOut `
    -Notes ("timed_out=" + $result.TimedOut)
Save-AdapterMeta -Meta $meta -MetaOut $MetaOut

exit $result.ExitCode
