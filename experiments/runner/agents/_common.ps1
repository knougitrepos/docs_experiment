# ============================================================
# _common.ps1 — 어댑터 공용 헬퍼 (dot-sourcing 으로 import)
# ============================================================
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function New-AdapterMeta {
    param(
        [Parameter(Mandatory)][string]$Agent,
        [Parameter(Mandatory)][string]$Model,
        [Parameter(Mandatory)][datetime]$Started,
        [Parameter(Mandatory)][datetime]$Finished,
        [Parameter(Mandatory)][int]$ExitCode,
        [Parameter(Mandatory)][string]$PromptFile,
        [Parameter(Mandatory)][string]$StreamOut,
        [hashtable]$TokensHint,
        [Nullable[double]]$CostHint = $null,
        [Nullable[int]]$StepsHint = $null,
        [string]$Notes = ""
    )
    $promptBytes = 0
    if (Test-Path $PromptFile) { $promptBytes = (Get-Item $PromptFile).Length }
    $streamBytes = 0
    if (Test-Path $StreamOut) { $streamBytes = (Get-Item $StreamOut).Length }

    $obj = [ordered]@{
        agent            = $Agent
        model            = $Model
        started_at       = $Started.ToString('o')
        finished_at      = $Finished.ToString('o')
        wall_seconds     = [math]::Round(($Finished - $Started).TotalSeconds, 2)
        exit_code        = $ExitCode
        prompt_bytes     = $promptBytes
        stream_bytes     = $streamBytes
        agent_steps_hint = $StepsHint
        tokens_hint      = $TokensHint
        cost_usd_hint    = $CostHint
        notes            = $Notes
    }
    return $obj
}

function Save-AdapterMeta {
    param(
        [Parameter(Mandatory)][object]$Meta,
        [Parameter(Mandatory)][string]$MetaOut
    )
    $dir = Split-Path -Parent $MetaOut
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $Meta | ConvertTo-Json -Depth 5 | Set-Content -Path $MetaOut -Encoding UTF8
}

function Write-AdapterLog {
    param([string]$Message, [ValidateSet('INFO','WARN','ERROR','DEBUG')][string]$Level = 'INFO')
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$ts] [$Level] [adapter] $Message"
    switch ($Level) {
        'ERROR' { Write-Host $line -ForegroundColor Red }
        'WARN'  { Write-Host $line -ForegroundColor Yellow }
        'DEBUG' { Write-Host $line -ForegroundColor DarkGray }
        default { Write-Host $line }
    }
}

function Test-Command {
    <#
    .SYNOPSIS
        특정 실행파일이 PATH 에 있는지 확인. 없으면 throw.
    #>
    param([Parameter(Mandatory)][string]$Name, [string]$InstallHint = "")
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        $msg = "required CLI not found: $Name"
        if ($InstallHint) { $msg += " (install: $InstallHint)" }
        throw $msg
    }
    return $cmd
}

function Invoke-WithTimeout {
    <#
    .SYNOPSIS
        외부 프로세스를 타임아웃과 함께 실행하고, 표준출력을 파일에 기록.
    .OUTPUTS
        [pscustomobject] { ExitCode, TimedOut, StdErr }
    #>
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory)][string]$StdoutFile,
        [int]$TimeoutSec = 1800,
        [string]$WorkingDirectory
    )
    $stderrFile = [System.IO.Path]::GetTempFileName()
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    foreach ($a in $ArgumentList) { [void]$psi.ArgumentList.Add($a) }
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.UseShellExecute = $false
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding  = [System.Text.Encoding]::UTF8
    if ($WorkingDirectory) { $psi.WorkingDirectory = $WorkingDirectory }

    $proc = [System.Diagnostics.Process]::Start($psi)
    $sw = [System.IO.StreamWriter]::new($StdoutFile, $false, [System.Text.Encoding]::UTF8)
    $errSw = [System.IO.StreamWriter]::new($stderrFile, $false, [System.Text.Encoding]::UTF8)
    try {
        $proc.BeginOutputReadLine() | Out-Null
        $proc.BeginErrorReadLine()  | Out-Null
    } catch { }
    # BeginOutputReadLine 은 이벤트 핸들러 필요 → 복잡해지니 동기 read 로 대체
    $proc.StandardOutput.BaseStream.CopyToAsync($sw.BaseStream) | Out-Null
    $proc.StandardError.BaseStream.CopyToAsync($errSw.BaseStream) | Out-Null

    $timedOut = $false
    if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
        try { $proc.Kill($true) } catch { }
        $timedOut = $true
    }
    $sw.Dispose(); $errSw.Dispose()
    $exitCode = if ($timedOut) { 124 } else { $proc.ExitCode }

    $stderrText = ""
    try { $stderrText = Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue } catch { }
    try { Remove-Item $stderrFile -Force } catch { }

    return [pscustomobject]@{
        ExitCode = $exitCode
        TimedOut = $timedOut
        StdErr   = $stderrText
    }
}
