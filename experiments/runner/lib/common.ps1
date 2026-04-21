# ============================================================
# common.ps1 — conditions/C*/setup.ps1 에서 공용으로 사용하는 헬퍼
# dot-sourcing 방식으로 import:
#   . "$PSScriptRoot\..\..\runner\lib\common.ps1"
# ============================================================

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Log {
    param(
        [string]$Message,
        [ValidateSet('INFO', 'WARN', 'ERROR', 'DEBUG')]
        [string]$Level = 'INFO'
    )
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "[$ts] [$Level] $Message"
    switch ($Level) {
        'ERROR' { Write-Host $line -ForegroundColor Red }
        'WARN'  { Write-Host $line -ForegroundColor Yellow }
        'DEBUG' { Write-Host $line -ForegroundColor DarkGray }
        default { Write-Host $line }
    }
}

function Initialize-Workspace {
    <#
    .SYNOPSIS
        워크스페이스 디렉터리를 비우고 초기화한다(이미 존재하면 docs/ 하위만 제거).
    .PARAMETER Workspace
        대상 경로 (예: experiments/ws/task-1-C0-sonnet-1)
    #>
    param([Parameter(Mandatory)][string]$Workspace)

    if (-not (Test-Path $Workspace)) {
        New-Item -ItemType Directory -Force -Path $Workspace | Out-Null
    }

    # 이전 실행 잔여 문서 제거 (조건별로 오염되지 않도록)
    foreach ($name in @('docs', 'AGENTS.md', 'REQUIREMENTS.md')) {
        $p = Join-Path $Workspace $name
        if (Test-Path $p) {
            Remove-Item -Recurse -Force $p
            Write-Log "removed stale: $p" -Level DEBUG
        }
    }
}

function Copy-Requirements {
    <#
    .SYNOPSIS
        docs/요구사항/<task>.md 를 workspace 루트의 REQUIREMENTS.md 로 복사한다.
        C1 이상 모든 조건에서 사용.
    #>
    param(
        [Parameter(Mandatory)][string]$DocsRoot,
        [Parameter(Mandatory)][string]$TaskId,
        [Parameter(Mandatory)][string]$Workspace
    )
    $src = Join-Path $DocsRoot "요구사항\$TaskId.md"
    if (-not (Test-Path $src)) {
        throw "requirements not found: $src"
    }
    $dst = Join-Path $Workspace 'REQUIREMENTS.md'
    Copy-Item $src $dst -Force
    Write-Log "placed REQUIREMENTS.md ($src -> $dst)"
}

function Copy-DesignDocs {
    <#
    .SYNOPSIS
        architecture/api/db.md 를 workspace/docs/ 하위에 복사 (C2 이상).
    #>
    param(
        [Parameter(Mandatory)][string]$DocsRoot,
        [Parameter(Mandatory)][string]$Workspace
    )
    $dstDocs = Join-Path $Workspace 'docs'
    New-Item -ItemType Directory -Force -Path $dstDocs | Out-Null
    foreach ($name in @('architecture.md', 'api.md', 'db.md')) {
        $src = Join-Path $DocsRoot $name
        $dst = Join-Path $dstDocs $name
        Copy-Item $src $dst -Force
        Write-Log "placed docs/$name"
    }
}

function Copy-AdrAndAgents {
    <#
    .SYNOPSIS
        adr/ 폴더 전체 + 루트 AGENTS.md 복사 (C3 이상).
    #>
    param(
        [Parameter(Mandatory)][string]$DocsRoot,
        [Parameter(Mandatory)][string]$Workspace
    )
    $dstDocs = Join-Path $Workspace 'docs'
    New-Item -ItemType Directory -Force -Path $dstDocs | Out-Null

    $adrSrc = Join-Path $DocsRoot 'adr'
    $adrDst = Join-Path $dstDocs 'adr'
    if (Test-Path $adrSrc) {
        Copy-Item $adrSrc $adrDst -Recurse -Force
        Write-Log "placed docs/adr/"
    }

    $agentsSrc = Join-Path $DocsRoot 'AGENTS.md'
    $agentsDst = Join-Path $Workspace 'AGENTS.md'
    if (Test-Path $agentsSrc) {
        Copy-Item $agentsSrc $agentsDst -Force
        Write-Log "placed AGENTS.md at workspace root"
    }
}

function Enable-ContinualLearning {
    <#
    .SYNOPSIS
        C4 전용: .cursor/ 하위에 continual-learning 플러그인 활성화 힌트 파일을 남긴다.
        (실제 플러그인 설치는 Cursor CLI 에서 /add-plugin continual-learning 으로 선행 필요.)
        본 함수는 해당 workspace 에서 플러그인이 AGENTS.md 를 업데이트할 수 있도록 hooks 상태 폴더를 미리 만들어 둔다.
    #>
    param([Parameter(Mandatory)][string]$Workspace)

    $cursorDir = Join-Path $Workspace '.cursor'
    $stateDir = Join-Path $cursorDir 'hooks\state'
    New-Item -ItemType Directory -Force -Path $stateDir | Out-Null

    $marker = Join-Path $cursorDir 'continual-learning.enabled'
    Set-Content -Path $marker -Value "enabled at $(Get-Date -Format o)" -Encoding UTF8
    Write-Log "C4 enabled: .cursor/ + continual-learning marker created"
}

function Write-ConditionManifest {
    <#
    .SYNOPSIS
        조건별 적용 내역을 workspace 에 JSON 으로 기록(후속 분석용).
    #>
    param(
        [Parameter(Mandatory)][string]$Workspace,
        [Parameter(Mandatory)][string]$Condition,
        [Parameter(Mandatory)][string]$TaskId,
        [Parameter(Mandatory)][string[]]$PlacedFiles
    )
    $manifest = [pscustomobject]@{
        condition   = $Condition
        task_id     = $TaskId
        placed      = $PlacedFiles
        created_at  = (Get-Date -Format o)
    }
    $p = Join-Path $Workspace '.condition_manifest.json'
    $manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $p -Encoding UTF8
    Write-Log "wrote $p"
}

function Get-DocsRoot {
    <#
    .SYNOPSIS
        레포 루트의 docs/ 경로를 반환 (setup.ps1 위치 기준 상대 해석).
    #>
    param([Parameter(Mandatory)][string]$ScriptDir)
    # ScriptDir: experiments/conditions/C?/
    $repoRoot = Resolve-Path (Join-Path $ScriptDir '..\..\..')
    return (Join-Path $repoRoot 'docs')
}
