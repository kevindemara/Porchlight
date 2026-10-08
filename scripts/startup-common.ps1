# Shared plan/ownership checks; dot-sourcing does not register, run or remove tasks.
function Get-PorchlightStartupPlan {
    param([string]$DataRoot, [int]$Port, [string]$PublicOrigin)
    $porchRepository = Split-Path -Parent $PSScriptRoot
    $porchPython = Join-Path $porchRepository '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $porchPython)) { throw 'Run bootstrap.ps1 first.' }
    $porchArguments = @((Join-Path $PSScriptRoot 'startup-plan.py'))
    if ($DataRoot) { $porchArguments += @('--data-root', $DataRoot) }
    if ($Port) { $porchArguments += @('--port', [string]$Port) }
    if ($PublicOrigin) { $porchArguments += @('--public-origin', $PublicOrigin) }
    $porchOutput = & $porchPython @porchArguments
    if ($LASTEXITCODE -ne 0) { throw 'Invalid startup configuration. No task was changed.' }
    $porchPlan = $porchOutput | ConvertFrom-Json
    $porchPlan | Add-Member -NotePropertyName UserId -NotePropertyValue ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value)
    $porchShell = Join-Path $PSHOME 'pwsh.exe'
    if (-not (Test-Path -LiteralPath $porchShell)) { $porchShell = Join-Path $PSHOME 'powershell.exe' }
    if (-not (Test-Path -LiteralPath $porchShell)) { throw 'The current PowerShell executable is unavailable.' }
    $porchPlan | Add-Member -NotePropertyName Execute -NotePropertyValue $porchShell
    $porchCommand = '-NoProfile -NonInteractive -WindowStyle Hidden -File "' + $porchPlan.launcher + '" -DataRoot "' + $porchPlan.data_root + '" -Port ' + $porchPlan.port
    if ($porchPlan.public_origin) { $porchCommand += ' -PublicOrigin "' + $porchPlan.public_origin + '"' }
    if ($porchPlan.ffmpeg) { $porchCommand += ' -Ffmpeg "' + $porchPlan.ffmpeg + '"' }
    if ($porchPlan.ffprobe) { $porchCommand += ' -Ffprobe "' + $porchPlan.ffprobe + '"' }
    $porchPlan | Add-Member -NotePropertyName Arguments -NotePropertyValue $porchCommand
    return $porchPlan
}

function Assert-PorchlightStartupOwnership {
    param($Task, $Plan)
    # A matching task name alone never establishes ownership.
    $porchActions = @($Task.Actions)
    $porchPrefix = '-NoProfile -NonInteractive -WindowStyle Hidden -File "' + $Plan.launcher + '" -DataRoot "' + $Plan.data_root + '" -Port '
    if ($Task.Description -ne $Plan.description -or $porchActions.Count -ne 1 -or
        $Task.Principal.UserId -ne $Plan.UserId -or
        $porchActions[0].Execute -ne $Plan.Execute -or
        $porchActions[0].WorkingDirectory -ne $Plan.repository -or
        -not ([string]$porchActions[0].Arguments).StartsWith($porchPrefix, [StringComparison]::Ordinal)) {
        throw 'Task ownership does not match this checkout, profile and Windows user. No task was changed.'
    }
}
