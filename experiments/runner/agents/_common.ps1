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

function Resolve-AdapterExecutable {
    param([Parameter(Mandatory)][string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) { return $Name }
    $path = $cmd.Path
    if (-not $path) { $path = $cmd.Source }
    if ($path -and $path.EndsWith('.ps1', [System.StringComparison]::OrdinalIgnoreCase)) {
        $cmdPath = [System.IO.Path]::ChangeExtension($path, '.cmd')
        if (Test-Path $cmdPath) { return $cmdPath }
    }
    if ($path) { return $path }
    return $Name
}

function Join-WindowsProcessArguments {
    param([string[]]$ArgumentValues)
    $parts = foreach ($arg in $ArgumentValues) {
        if ($null -eq $arg) {
            '""'
        } else {
            $s = [string]$arg
            if ($s.Length -eq 0) {
                '""'
            } elseif ($s -notmatch '[\s"]') {
                $s
            } else {
                $sb = [System.Text.StringBuilder]::new()
                [void]$sb.Append('"')
                $backslashes = 0
                foreach ($ch in $s.ToCharArray()) {
                    if ($ch -eq [char]'\') {
                        $backslashes++
                    } elseif ($ch -eq [char]'"') {
                        if ($backslashes -gt 0) { [void]$sb.Append(('\' * ($backslashes * 2))) }
                        [void]$sb.Append('\"')
                        $backslashes = 0
                    } else {
                        if ($backslashes -gt 0) {
                            [void]$sb.Append(('\' * $backslashes))
                            $backslashes = 0
                        }
                        [void]$sb.Append($ch)
                    }
                }
                if ($backslashes -gt 0) { [void]$sb.Append(('\' * ($backslashes * 2))) }
                [void]$sb.Append('"')
                $sb.ToString()
            }
        }
    }
    return ($parts -join ' ')
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
    $psi.FileName = Resolve-AdapterExecutable -Name $FilePath
    $psi.Arguments = Join-WindowsProcessArguments -ArgumentValues $ArgumentList
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.RedirectStandardInput  = $true
    $psi.UseShellExecute = $false
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding  = [System.Text.Encoding]::UTF8
    if ($WorkingDirectory) { $psi.WorkingDirectory = $WorkingDirectory }

    $proc = [System.Diagnostics.Process]::Start($psi)
    # 일부 CLI(codex 등)는 stdin EOF를 받아야 즉시 실행된다.
    try { $proc.StandardInput.Close() } catch { }
    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()

    $timedOut = $false
    if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
        try { $proc.Kill() } catch { }
        $timedOut = $true
    }
    $exitCode = if ($timedOut) { 124 } else { $proc.ExitCode }

    $stdoutText = ""
    $stderrText = ""
    try { $stdoutText = $stdoutTask.Result } catch { }
    try { $stderrText = $stderrTask.Result } catch { }
    [System.IO.File]::WriteAllText($StdoutFile, $stdoutText, [System.Text.Encoding]::UTF8)
    [System.IO.File]::WriteAllText($stderrFile, $stderrText, [System.Text.Encoding]::UTF8)
    try { $stderrText = Get-Content $stderrFile -Raw -ErrorAction SilentlyContinue } catch { }
    try { Remove-Item $stderrFile -Force } catch { }

    return [pscustomobject]@{
        ExitCode = $exitCode
        TimedOut = $timedOut
        StdErr   = $stderrText
    }
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
