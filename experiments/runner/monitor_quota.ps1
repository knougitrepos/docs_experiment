<#
.SYNOPSIS
    실행 중 quota/시간 예산 초과를 감시해 stop 파일을 생성한다.

.DESCRIPTION
    별도 터미널에서 상시 실행. 아래 상황 중 하나라도 감지되면
    -StopFile 경로에 중단 시그널 파일을 생성해 runner 가 다음 iter 전에 멈추도록 한다.

    - 누적 wall-clock 이 TimeBudgetMinutes 초과
    - 최근 WindowMinutes 분 사이 adapter 실패(adapter_exit != 0) 수가 FailureThreshold 초과
    - 사용자가 수동으로 .stop 파일을 touch 한 경우(이 스크립트와 상관없이 runner 가 반응)

    단일 (agent, model) 실행 정책에 맞춰, RunRoot 하위의 모든
    <agent>/<model>/runs.csv 를 합산하여 판단한다.

.PARAMETER RunRoot
    실험 run 루트 (experiments\results\<RunId>). 이 하위의 모든 runs.csv 를 합산.

.PARAMETER StopFile
    생성할 stop 시그널 파일 경로. 기본 "$RunRoot\.stop"

.PARAMETER PollSeconds
    폴링 주기. 기본 60.

.PARAMETER FailureThreshold
    최근 WindowMinutes 분 실패 허용 건 수. 기본 5.

.PARAMETER WindowMinutes
    실패 집계 윈도우. 기본 10.

.PARAMETER TimeBudgetMinutes
    총 누적 wall-clock 상한(분). 기본 360 (6 시간).

.EXAMPLE
    .\monitor_quota.ps1 -RunRoot .\experiments\results\20260421_140000 -TimeBudgetMinutes 300

.NOTES
    Cursor Pro 등 대부분의 구독은 공개 API 로 잔여 request 조회가 불가능하므로,
    "에이전트 실패율" + "시간 예산" 프록시로만 감시한다.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$RunRoot,
    [string]$StopFile,
    [int]$PollSeconds = 60,
    [int]$FailureThreshold = 5,
    [int]$WindowMinutes = 10,
    [int]$TimeBudgetMinutes = 360
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\common.ps1"

if (-not $StopFile) { $StopFile = Join-Path $RunRoot '.stop' }

Write-Log "monitor_quota: RunRoot=$RunRoot"
Write-Log "  StopFile        : $StopFile"
Write-Log "  PollSeconds     : $PollSeconds"
Write-Log "  FailureThreshold: $FailureThreshold within $WindowMinutes min"
Write-Log "  TimeBudgetMin   : $TimeBudgetMinutes"

if (-not (Test-Path $RunRoot)) {
    New-Item -ItemType Directory -Force -Path $RunRoot | Out-Null
    Write-Log "RunRoot did not exist; created $RunRoot" -Level WARN
}

function Get-AllRunRows {
    param([string]$Root)
    $csvs = Get-ChildItem -Path $Root -Recurse -Filter 'runs.csv' -ErrorAction SilentlyContinue
    $all = @()
    foreach ($csv in $csvs) {
        try {
            $rows = Import-Csv -Path $csv.FullName
            if ($rows) { $all += $rows }
        } catch {
            Write-Log "failed to read $($csv.FullName): $_" -Level WARN
        }
    }
    return ,$all
}

while ($true) {
    if (Test-Path $StopFile) {
        Write-Log "StopFile already exists at $StopFile. Exiting monitor." -Level WARN
        break
    }

    $rows = Get-AllRunRows -Root $RunRoot
    if (-not $rows -or $rows.Count -eq 0) {
        Write-Log "no runs yet; waiting..." -Level DEBUG
        Start-Sleep -Seconds $PollSeconds
        continue
    }

    # 1) 시간 예산
    $totalMin = 0.0
    foreach ($r in $rows) {
        $ws = $null
        try { $ws = [double]$r.wall_sec } catch { }
        if ($ws) { $totalMin += $ws / 60.0 }
    }
    Write-Log ("cumulative wall: {0:N1} min (budget {1}) across {2} runs" -f $totalMin, $TimeBudgetMinutes, $rows.Count) -Level DEBUG

    if ($totalMin -ge $TimeBudgetMinutes) {
        Set-Content -Path $StopFile -Value "budget exceeded: $([math]::Round($totalMin,1)) min" -Encoding UTF8
        Write-Log "STOP: time budget exceeded ($([math]::Round($totalMin,1)) min)" -Level ERROR
        break
    }

    # 2) 최근 실패율
    $cutoff = (Get-Date).AddMinutes(-$WindowMinutes)
    $recent = @()
    foreach ($r in $rows) {
        try {
            $ft = [datetime]::Parse($r.finished_at)
            if ($ft -ge $cutoff) { $recent += $r }
        } catch { }
    }
    $fails = @()
    foreach ($r in $recent) {
        $exit = 0
        try { $exit = [int]$r.adapter_exit } catch {
            try { $exit = [int]$r.agent_exit } catch { $exit = 0 }
        }
        if ($exit -ne 0) { $fails += $r }
    }
    if ($fails.Count -ge $FailureThreshold) {
        Set-Content -Path $StopFile `
            -Value "recent failures: $($fails.Count) of $($recent.Count) in last $WindowMinutes min" `
            -Encoding UTF8
        Write-Log "STOP: $($fails.Count) adapter failures in last $WindowMinutes min" -Level ERROR
        break
    }

    Start-Sleep -Seconds $PollSeconds
}

Write-Log "monitor_quota exited"
