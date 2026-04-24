<#
.SYNOPSIS
    Antigravity GUI adapter for manual/semi-manual experiment runs.

.DESCRIPTION
    Antigravity currently exposes `antigravity chat --mode ...`, but the local
    CLI help does not expose a stable `--model` flag. To keep the experiment
    auditable, this adapter records the selected model as a run label and asks
    the user to select the same model inside the Antigravity UI before running
    the prepared prompt.

    Flow:
      1. The runner prepares a workspace and prompt file.
      2. This adapter optionally opens the workspace in Antigravity.
      3. The user selects MODEL and mode in the Antigravity UI, runs the prompt,
         then returns here and presses Enter.
      4. The runner continues with test/evaluation gates.
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
$parsedExtra = @{}
if ($Extra.ContainsKey('ExtraArgs') -and $Extra.ExtraArgs) {
    foreach ($token in ([string]$Extra.ExtraArgs -split '\s+')) {
        if ($token -match '^([^=]+)=(.*)$') {
            $parsedExtra[$matches[1]] = $matches[2]
        }
    }
}

$mode = if ($Extra.ContainsKey('Mode') -and $Extra.Mode) { [string]$Extra.Mode } else { 'agent' }
$mode = if ($parsedExtra.ContainsKey('Mode') -and $parsedExtra.Mode) { [string]$parsedExtra.Mode } else { $mode }
$launch = -not ($Extra.ContainsKey('Launch') -and -not [bool]$Extra.Launch)
$launch = if ($parsedExtra.ContainsKey('Launch')) { [System.Convert]::ToBoolean($parsedExtra.Launch) } else { $launch }
$nonInteractive = $Extra.ContainsKey('NonInteractive') -and [bool]$Extra.NonInteractive
$nonInteractive = if ($parsedExtra.ContainsKey('NonInteractive')) { [System.Convert]::ToBoolean($parsedExtra.NonInteractive) } else { $nonInteractive }

$cmd = Get-Command 'antigravity' -ErrorAction SilentlyContinue
if (-not $cmd) {
    Write-AdapterLog "antigravity CLI not found. Install or add Antigravity to PATH." -Level ERROR
    '{"event":"adapter_error","message":"antigravity CLI not found"}' | Set-Content -Path $StreamOut -Encoding UTF8
    $meta = New-AdapterMeta -Agent 'antigravity' -Model $Model `
        -Started $started -Finished (Get-Date) -ExitCode 127 `
        -PromptFile $PromptFile -StreamOut $StreamOut -Notes 'antigravity not in PATH'
    $meta['mode'] = $mode
    Save-AdapterMeta -Meta $meta -MetaOut $MetaOut
    exit 127
}

if ($launch) {
    try {
        Start-Process -FilePath 'antigravity' -ArgumentList @('--reuse-window', $Workspace) | Out-Null
        Write-AdapterLog "opened Antigravity workspace=$Workspace"
    } catch {
        Write-AdapterLog "failed to open Antigravity automatically: $_" -Level WARN
    }
}

Write-Host "=================================================="
Write-Host " [antigravity adapter] manual/semi-manual run"
Write-Host "   model label : $Model"
Write-Host "   mode        : $mode"
Write-Host "   workspace   : $Workspace"
Write-Host "   promptFile  : $PromptFile"
Write-Host "   streamOut   : $StreamOut"
Write-Host "   timeoutSec  : $TimeoutSec"
Write-Host "--------------------------------------------------"
Write-Host " 1) Open the workspace above in Antigravity."
Write-Host " 2) In Antigravity, select the model exactly as recorded above."
Write-Host " 3) Select mode '$mode' or the matching UI mode."
Write-Host " 4) Paste the prompt file contents and let Antigravity finish editing."
Write-Host " 5) Return here and press Enter so the runner can evaluate the workspace."
Write-Host "=================================================="

$notes = "manual antigravity run; mode=$mode"
if ($nonInteractive) {
    Write-AdapterLog "NonInteractive: skipping wait"
    $notes += "; non-interactive skip"
} else {
    try {
        $deadline = (Get-Date).AddSeconds($TimeoutSec)
        while ($true) {
            if ([Console]::KeyAvailable) {
                $key = [Console]::ReadKey($true)
                if ($key.Key -eq 'Enter') { break }
            }
            if ((Get-Date) -ge $deadline) {
                Write-AdapterLog "antigravity wait timed out after $TimeoutSec sec" -Level WARN
                $notes += "; timed out waiting for user"
                break
            }
            Start-Sleep -Milliseconds 250
        }
    } catch {
        Read-Host "Press Enter after the Antigravity run is complete"
    }
}

$finished = Get-Date
$placeholder = @{
    event      = "antigravity_manual_run"
    agent      = "antigravity"
    model      = $Model
    mode       = $mode
    workspace  = $Workspace
    promptFile = $PromptFile
    started    = $started.ToString('o')
    finished   = $finished.ToString('o')
    note       = "human-in-the-loop; stream not captured"
} | ConvertTo-Json -Compress
$placeholder | Set-Content -Path $StreamOut -Encoding UTF8

$meta = New-AdapterMeta -Agent 'antigravity' -Model $Model `
    -Started $started -Finished $finished -ExitCode 0 `
    -PromptFile $PromptFile -StreamOut $StreamOut -Notes $notes
$meta['mode'] = $mode
Save-AdapterMeta -Meta $meta -MetaOut $MetaOut
exit 0
