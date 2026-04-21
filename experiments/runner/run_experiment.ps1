<#
.SYNOPSIS
    문서 참조 구조 비교 실험 — 단일 (agent, model) 기준 오케스트레이터.

.DESCRIPTION
    한 번의 실행은 **하나의 에이전트(CLI) × 하나의 모델** 만 사용합니다.
    여러 모델을 같이 돌리면 토큰 비용/환경 통제가 어렵기 때문에,
    Cursor / Codex / Aider / Copilot / custom / manual 중 하나를 골라 End-to-End 로 수행합니다.

    실행 매트릭스(이번 호출 내):
        Conditions × Repeats × Tasks  (Agent, Model 은 고정)

    산출물:
        experiments/results/<ts>/<agent>/<model>/<cond>/rep<N>/<task>/
          ├─ prompt.txt               runner 가 생성한 프롬프트 사본
          ├─ stream.jsonl             어댑터의 원시 stdout (JSONL 또는 텍스트)
          ├─ agent.meta.json          어댑터 meta
          ├─ run.meta.json            runner meta (wall, gate exit codes)
          ├─ pytest.json / pytest.log pytest-json-report
          ├─ ruff.json
          ├─ mypy.txt
          ├─ build.log
          └─ metrics.json             evaluate.py 결과

.PARAMETER Agent
    어댑터 이름. cursor | codex | aider | copilot | custom | manual

.PARAMETER Model
    에이전트별 모델 이름. (예: sonnet / gpt-5 / openai/gpt-4o / anthropic/claude-3-7-sonnet-...)

.PARAMETER Conditions
    실행할 조건 목록(콤마 구분). 기본 "C0,C1,C2,C3,C4"

.PARAMETER Repeats
    rep 반복 수. 기본 3.

.PARAMETER Tasks
    실행 task 순서(콤마 구분). 기본 전체 3 task.
    C4 의 '연속 task 학습' 효과 검증을 위해 순서대로 같은 workspace 에서 수행됩니다.

.PARAMETER OutputRoot
    결과 디렉터리 루트. 기본 experiments\results

.PARAMETER QuotaStopFile
    이 파일이 존재하면 다음 iteration 전에 중단 (monitor_quota.ps1 과 연동).

.PARAMETER DryRun
    실제 에이전트/게이트 호출 없이 매트릭스 계획만 출력.

.PARAMETER SkipAgent
    에이전트 호출을 생략(이미 workspace 에 있는 코드로 품질 게이트/평가만).

.PARAMETER NoEvaluate
    evaluate.py 호출 생략.

.PARAMETER CustomCmd
    Agent=custom 또는 copilot(mode=custom) 일 때 사용하는 커맨드 템플릿.
    템플릿 치환자: ${WORKSPACE}, ${PROMPT_FILE}, ${MODEL}, ${STREAM_OUT}, ${PROMPT}

.PARAMETER AdapterTimeoutSec
    어댑터 1 회 호출 타임아웃. 기본 1800 (30 분).

.PARAMETER RunId
    출력 디렉터리 timestamp 대신 사용할 ID. 같은 ID 로 여러 agent 실험을 같은 run 밑에 묶을 수 있음.

.EXAMPLE
    # 파일럿: Cursor sonnet, C0/C1, 반복 1, task-1 만
    .\run_experiment.ps1 -Agent cursor -Model sonnet `
        -Conditions "C0,C1" -Repeats 1 -Tasks "task-1-todo-crud"

.EXAMPLE
    # Aider 로 OpenAI 남은 크레딧 소진
    .\run_experiment.ps1 -Agent aider -Model "openai/gpt-4o-mini" `
        -Conditions "C0,C1,C2,C3,C4" -Repeats 3

.EXAMPLE
    # DryRun 으로 계획만 확인
    .\run_experiment.ps1 -Agent cursor -Model sonnet -DryRun

.EXAMPLE
    # 수동 모드 (Copilot GUI 등): 워크스페이스만 준비, 사용자가 수동 작업
    .\run_experiment.ps1 -Agent manual -Model "copilot-gui-claude37" -Conditions C1 -Repeats 1

.NOTES
    - Windows num_workers>0 이슈 회피(user rule 11): pytest 는 -p no:xdist.
    - 한 번에 한 (agent, model) 만 실행하여 토큰/환경 통제.
    - 같은 RunId 로 여러 번 호출하면 같은 run-root 아래 (agent,model) 별로 누적.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('cursor','codex','aider','copilot','custom','manual')]
    [string]$Agent,

    [Parameter(Mandatory)][string]$Model,

    [string]$Conditions = 'C0,C1,C2,C3,C4',
    [int]$Repeats       = 3,
    [string]$Tasks      = 'task-1-todo-crud,task-2-jwt,task-3-pagination',
    [string]$OutputRoot = 'experiments\results',
    [string]$QuotaStopFile,
    [switch]$DryRun,
    [switch]$SkipAgent,
    [switch]$NoEvaluate,
    [string]$CustomCmd,
    [int]$AdapterTimeoutSec = 1800,
    [string]$RunId,
    [switch]$Help
)

if ($Help) { Get-Help $PSCommandPath -Full; exit 0 }

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\lib\common.ps1"

# ------------------------------------------------------------
# 1) 파싱/검증
# ------------------------------------------------------------
$condList  = @(($Conditions -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$taskList  = @(($Tasks      -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })

if ($condList.Count -eq 0) { throw 'No conditions' }
if ($taskList.Count -eq 0)  { throw 'No tasks' }
if ($Repeats -lt 1) { throw 'Repeats must be >=1' }

foreach ($c in $condList) {
    if ($c -notmatch '^C[0-4]$') { throw "Invalid condition: $c (must be C0..C4)" }
    $sp = Join-Path $PSScriptRoot "..\conditions\$c\setup.ps1"
    if (-not (Test-Path $sp)) { throw "setup.ps1 not found for $c : $sp" }
}

$adapter = Join-Path $PSScriptRoot "agents\$Agent.ps1"
if (-not (Test-Path $adapter)) { throw "adapter not found: $adapter" }

if ($Agent -eq 'custom' -and -not $CustomCmd) {
    throw "-Agent custom requires -CustomCmd '<template>' (e.g. 'my-cli --model `${MODEL} --prompt-file `${PROMPT_FILE}')"
}

if (-not $RunId) { $RunId = Get-Date -Format 'yyyyMMdd_HHmmss' }
$runRoot   = Join-Path $OutputRoot $RunId
$agentRoot = Join-Path $runRoot ("{0}\{1}" -f $Agent, ($Model -replace '[\\\/:*?"<>|]', '_'))
New-Item -ItemType Directory -Force -Path $agentRoot | Out-Null

if (-not $QuotaStopFile) { $QuotaStopFile = Join-Path $runRoot '.stop' }
$runsCsv = Join-Path $agentRoot 'runs.csv'
'run_index,agent,model,task,cond,rep,started_at,finished_at,adapter_exit,pytest_exit,ruff_exit,mypy_exit,wall_sec,ws_path' `
    | Set-Content -Path $runsCsv -Encoding UTF8

$matrixCount = $condList.Count * $Repeats * $taskList.Count
Write-Log "===== run_experiment.ps1 ====="
Write-Log "runId          : $RunId"
Write-Log "agent          : $Agent"
Write-Log "model          : $Model"
Write-Log "conditions     : $($condList -join ', ')"
Write-Log "repeats        : $Repeats"
Write-Log "tasks          : $($taskList -join ', ')"
Write-Log "matrix size    : $matrixCount run"
Write-Log "runRoot        : $runRoot"
Write-Log "agentRoot      : $agentRoot"
Write-Log "quotaStopFile  : $QuotaStopFile"
Write-Log "dryRun=$DryRun  skipAgent=$SkipAgent  noEvaluate=$NoEvaluate"
Write-Log "================================"

# ------------------------------------------------------------
# 2) workspace 루트
# ------------------------------------------------------------
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$wsRoot   = Join-Path $repoRoot 'experiments\ws'
New-Item -ItemType Directory -Force -Path $wsRoot | Out-Null

# ------------------------------------------------------------
# 3) 헬퍼
# ------------------------------------------------------------
function Invoke-QualityGates {
    param(
        [Parameter(Mandatory)][string]$Ws,
        [Parameter(Mandatory)][string]$RunDir
    )
    Write-Log "pytest"
    Push-Location $Ws
    try {
        & pytest --cov=app --cov-report=term `
            --json-report --json-report-file=(Join-Path $RunDir 'pytest.json') `
            -p no:xdist 2>&1 | Tee-Object (Join-Path $RunDir 'pytest.log') | Out-Null
        $ptExit = $LASTEXITCODE
    } catch {
        Write-Log "pytest failed: $_" -Level WARN
        $ptExit = -1
    } finally { Pop-Location }

    Write-Log "ruff"
    Push-Location $Ws
    try {
        & ruff check . --output-format=json 2>&1 `
            | Set-Content -Path (Join-Path $RunDir 'ruff.json') -Encoding UTF8
        $ruExit = $LASTEXITCODE
    } catch {
        Write-Log "ruff failed: $_" -Level WARN
        $ruExit = -1
    } finally { Pop-Location }

    Write-Log "mypy"
    Push-Location $Ws
    try {
        & mypy app 2>&1 | Tee-Object (Join-Path $RunDir 'mypy.txt') | Out-Null
        $myExit = $LASTEXITCODE
    } catch {
        Write-Log "mypy failed: $_" -Level WARN
        $myExit = -1
    } finally { Pop-Location }

    return [pscustomobject]@{
        pytest_exit = $ptExit
        ruff_exit   = $ruExit
        mypy_exit   = $myExit
    }
}

function Invoke-OneRun {
    param(
        [int]$Index,
        [string]$TaskId,
        [string]$Condition,
        [int]$Rep,
        [string]$WsPath,
        [bool]$KeepState
    )

    $runDir = Join-Path $agentRoot ("{0}\rep{1}\{2}" -f $Condition, $Rep, $TaskId)
    New-Item -ItemType Directory -Force -Path $runDir | Out-Null

    $wall = [System.Diagnostics.Stopwatch]::StartNew()
    $started = Get-Date

    # 3.1 조건별 workspace 세팅
    $setupScript = Join-Path $PSScriptRoot "..\conditions\$Condition\setup.ps1"
    if ($DryRun) {
        Write-Log "[DRY] setup: $Condition task=$TaskId keepState=$KeepState" -Level DEBUG
    } else {
        if ($Condition -eq 'C4' -and $KeepState) {
            & $setupScript -Workspace $WsPath -TaskId $TaskId -KeepState
        } else {
            & $setupScript -Workspace $WsPath -TaskId $TaskId
        }
    }

    # 3.2 prompt 파일 작성 (seed_prompt.md 의 <TASK_ID> 를 치환)
    $promptTemplate = Get-Content (Join-Path $repoRoot 'experiments\prompts\seed_prompt.md') -Raw
    $prompt = $promptTemplate -replace '<TASK_ID>', $TaskId
    $promptFile = Join-Path $runDir 'prompt.txt'
    $prompt | Set-Content -Path $promptFile -Encoding UTF8

    # 3.3 어댑터 호출
    $streamFile   = Join-Path $runDir 'stream.jsonl'
    $agentMetaOut = Join-Path $runDir 'agent.meta.json'
    $adapterExit  = 0

    if ($DryRun) {
        Write-Log "[DRY] adapter: $Agent model=$Model -> $streamFile" -Level DEBUG
        '{"event":"dry_run"}' | Set-Content -Path $streamFile -Encoding UTF8
        '{"dry_run":true}'    | Set-Content -Path $agentMetaOut -Encoding UTF8
    } elseif ($SkipAgent) {
        Write-Log "[SKIP] agent (SkipAgent). Using existing workspace code."
        '{"event":"skipped"}' | Set-Content -Path $streamFile -Encoding UTF8
        '{"skipped":true}'    | Set-Content -Path $agentMetaOut -Encoding UTF8
    } else {
        Write-Log "[run $Index] adapter=$Agent model=$Model cond=$Condition rep=$Rep task=$TaskId"
        $extra = @{}
        if ($Agent -eq 'custom') { $extra.Cmd = $CustomCmd }
        if ($Agent -eq 'copilot' -and $CustomCmd) { $extra.Mode = 'custom'; $extra.Cmd = $CustomCmd }

        try {
            & $adapter `
                -Workspace $WsPath `
                -PromptFile $promptFile `
                -Model $Model `
                -StreamOut $streamFile `
                -MetaOut $agentMetaOut `
                -TimeoutSec $AdapterTimeoutSec `
                -Extra $extra
            $adapterExit = $LASTEXITCODE
        } catch {
            Write-Log "adapter crashed: $_" -Level ERROR
            $adapterExit = -1
            "{`"event`":`"adapter_crash`",`"message`":`"$($_ -replace '"','\\"')`"}" `
                | Set-Content -Path $streamFile -Encoding UTF8
        }
    }

    # 3.4 quality gates
    $gate = [pscustomobject]@{ pytest_exit=0; ruff_exit=0; mypy_exit=0 }
    if (-not $DryRun) {
        $gate = Invoke-QualityGates -Ws $WsPath -RunDir $runDir
    }

    $wall.Stop()
    $finished = Get-Date

    # 3.5 runner meta
    $runMeta = [pscustomobject]@{
        index         = $Index
        run_id        = $RunId
        agent         = $Agent
        model         = $Model
        task_id       = $TaskId
        condition     = $Condition
        rep           = $Rep
        ws_path       = $WsPath
        started_at    = $started.ToString('o')
        finished_at   = $finished.ToString('o')
        wall_seconds  = [math]::Round($wall.Elapsed.TotalSeconds, 2)
        adapter_exit  = $adapterExit
        pytest_exit   = $gate.pytest_exit
        ruff_exit     = $gate.ruff_exit
        mypy_exit     = $gate.mypy_exit
        dry_run       = [bool]$DryRun
        skip_agent    = [bool]$SkipAgent
    }
    $runMeta | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $runDir 'run.meta.json') -Encoding UTF8

    # 3.6 runs.csv
    $line = "$Index,$Agent,$Model,$TaskId,$Condition,$Rep,$($started.ToString('o')),$($finished.ToString('o')),$adapterExit,$($gate.pytest_exit),$($gate.ruff_exit),$($gate.mypy_exit),$($runMeta.wall_seconds),$WsPath"
    Add-Content -Path $runsCsv -Value $line -Encoding UTF8

    # 3.7 evaluate
    if (-not $NoEvaluate -and -not $DryRun) {
        Write-Log "[run $Index] evaluate.py"
        & python (Join-Path $PSScriptRoot 'evaluate.py') `
            --run-dir $runDir `
            --ws $WsPath `
            --task $TaskId `
            --cond $Condition `
            --model $Model `
            --agent $Agent `
            --rep $Rep `
            --repo-root $repoRoot 2>&1 | Tee-Object (Join-Path $runDir 'evaluate.log') | Out-Null
    }
}

# ------------------------------------------------------------
# 4) 매트릭스 실행 (agent/model 고정, conditions × repeats × tasks)
# ------------------------------------------------------------
$runIdx = 0
foreach ($cond in $condList) {
    for ($rep = 1; $rep -le $Repeats; $rep++) {
        if (Test-Path $QuotaStopFile) {
            Write-Log "Quota stop file detected ($QuotaStopFile). Aborting." -Level WARN
            break
        }

        $wsName = ("{0}-{1}-{2}-rep{3}" -f $Agent, ($Model -replace '[\\\/:*?"<>|]', '_'), $cond, $rep)
        $wsPath = Join-Path $wsRoot $wsName
        Write-Log "===== sequence start: $wsName ====="

        for ($ti = 0; $ti -lt $taskList.Count; $ti++) {
            $t = $taskList[$ti]
            $runIdx++
            $keepState = ($cond -eq 'C4' -and $ti -gt 0)
            Write-Log "--- run $runIdx : $t (keepState=$keepState) ---"
            Invoke-OneRun -Index $runIdx -TaskId $t -Condition $cond `
                          -Rep $rep -WsPath $wsPath -KeepState:$keepState
            if (Test-Path $QuotaStopFile) { break }
        }
        Write-Log "===== sequence end: $wsName ====="
    }
    if (Test-Path $QuotaStopFile) { break }
}

# ------------------------------------------------------------
# 5) aggregate (현재 agent/model 범위)
# ------------------------------------------------------------
if (-not $NoEvaluate -and -not $DryRun) {
    Write-Log "===== aggregate (scope=agent/model) ====="
    & python (Join-Path $PSScriptRoot 'aggregate.py') `
        --run-root $runRoot `
        --scope "$Agent/$(($Model -replace '[\\\/:*?"<>|]', '_'))" 2>&1 `
        | Tee-Object (Join-Path $agentRoot 'aggregate.log')
}

Write-Log "done. results at: $agentRoot"
Write-Host ""
Write-Host "Summary:"
Write-Host "  run count      : $runIdx"
Write-Host "  runs.csv       : $runsCsv"
if (-not $DryRun -and -not $NoEvaluate) {
    Write-Host "  summary.csv    : $(Join-Path $agentRoot 'summary.csv')"
    Write-Host "  report.md      : $(Join-Path $agentRoot 'report.md')"
}
Write-Host ""
Write-Host "다른 (agent,model) 을 같은 run 으로 묶으려면 -RunId $RunId 로 다시 호출하세요."
