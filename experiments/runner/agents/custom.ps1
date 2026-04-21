<#
.SYNOPSIS
    임의 CLI 에이전트를 위한 템플릿 어댑터.

.DESCRIPTION
    사용자가 `-Extra @{ Cmd = '<template>' }` 로 커맨드 템플릿을 주입한다.
    템플릿 내 치환자:
      ${WORKSPACE}  → -Workspace 경로
      ${PROMPT_FILE}→ -PromptFile 경로
      ${MODEL}      → -Model 값
      ${STREAM_OUT} → -StreamOut 경로 (어댑터가 stdout 을 여기로 리다이렉트할 수도 있음)
      ${PROMPT}     → 프롬프트 텍스트 (escape 주의: 큰 텍스트는 PROMPT_FILE 권장)

    예:
      -Extra @{ Cmd = 'my-cli --model ${MODEL} --cwd ${WORKSPACE} --prompt-file ${PROMPT_FILE}' }

    Cmd 가 없으면 에러.
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
$template = $null
if ($Extra.ContainsKey('Cmd')) { $template = $Extra.Cmd }

if (-not $template) {
    Write-AdapterLog "custom adapter requires -Extra @{ Cmd = '...' }" -Level ERROR
    '{"event":"adapter_error","message":"no Cmd template"}' | Set-Content -Path $StreamOut -Encoding UTF8
    $meta = New-AdapterMeta -Agent 'custom' -Model $Model `
        -Started $started -Finished (Get-Date) -ExitCode 2 `
        -PromptFile $PromptFile -StreamOut $StreamOut -Notes 'no Cmd template'
    Save-AdapterMeta -Meta $meta -MetaOut $MetaOut
    exit 2
}

$prompt = Get-Content $PromptFile -Raw -Encoding UTF8
$cmd = $template `
    -replace [regex]::Escape('${WORKSPACE}'),   [regex]::Escape($Workspace) `
    -replace [regex]::Escape('${PROMPT_FILE}'), [regex]::Escape($PromptFile) `
    -replace [regex]::Escape('${MODEL}'),       [regex]::Escape($Model) `
    -replace [regex]::Escape('${STREAM_OUT}'),  [regex]::Escape($StreamOut)
# ${PROMPT} 는 escape 위험이 큼 → 단순 치환
$cmd = $cmd.Replace('${PROMPT}', $prompt)

Write-AdapterLog "custom command: $cmd"

# 쉘을 통해 실행 (&/|/환경변수 확장 허용). cmd.exe 경유.
$tmpBat = [System.IO.Path]::GetTempFileName() + '.ps1'
@"
Set-Location -LiteralPath '$Workspace'
$cmd
"@ | Set-Content -Path $tmpBat -Encoding UTF8

try {
    $result = Invoke-WithTimeout `
        -FilePath 'pwsh' `
        -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File', $tmpBat) `
        -StdoutFile $StreamOut `
        -TimeoutSec $TimeoutSec `
        -WorkingDirectory $Workspace
} catch {
    # pwsh 없으면 powershell 로 fallback
    $result = Invoke-WithTimeout `
        -FilePath 'powershell' `
        -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File', $tmpBat) `
        -StdoutFile $StreamOut `
        -TimeoutSec $TimeoutSec `
        -WorkingDirectory $Workspace
} finally {
    try { Remove-Item $tmpBat -Force } catch { }
}

$finished = Get-Date
$meta = New-AdapterMeta -Agent 'custom' -Model $Model `
    -Started $started -Finished $finished -ExitCode $result.ExitCode `
    -PromptFile $PromptFile -StreamOut $StreamOut `
    -Notes "template=$template"
Save-AdapterMeta -Meta $meta -MetaOut $MetaOut

exit $result.ExitCode
