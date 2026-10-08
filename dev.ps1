[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$porchOldDev = $env:PORCHLIGHT_DEV_FRONTEND
$porchBackend = $null
Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run .\bootstrap.ps1 first.' }
    $env:PORCHLIGHT_DEV_FRONTEND = 'true'
    $porchPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    $porchRuntimeJson = & $porchPython -c 'import json; from porchlight.config import Config; c=Config(); print(json.dumps({"data_root":str(c.data_root),"port":c.port}))'
    if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the validated application configuration.' }
    $porchRuntime = $porchRuntimeJson | ConvertFrom-Json
    $porchStatePath = Join-Path $porchRuntime.data_root 'process.json'
    $porchLaunchId = [guid]::NewGuid().ToString()
    $porchBackend = Start-Process -FilePath $porchPython -ArgumentList '-m', 'porchlight', '--launch-id', $porchLaunchId -WorkingDirectory $PSScriptRoot -PassThru -WindowStyle Hidden
    $porchDeadline = [DateTime]::UtcNow.AddSeconds(30)
    $porchReady = $false
    while ([DateTime]::UtcNow -lt $porchDeadline) {
        if ($porchBackend.HasExited) { throw 'Porchlight could not start. Check whether this profile or backend port is already in use.' }
        try {
            if (Test-Path -LiteralPath $porchStatePath) {
                $porchState = Get-Content -LiteralPath $porchStatePath -Raw | ConvertFrom-Json
                if ($porchState.instance -eq $porchLaunchId) {
                    $porchLive = Invoke-RestMethod -Uri ('http://127.0.0.1:' + $porchRuntime.port + '/health/live') -TimeoutSec 1
                    if ($porchLive.status -eq 'alive') { $porchReady = $true; break }
                }
            }
        } catch {
            # A process-owned startup marker may still be being written.
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $porchReady) { throw 'Porchlight did not become ready within 30 seconds. The frontend was not started.' }
    Write-Host 'Development interface: http://127.0.0.1:5174. Backend changes require restarting dev.ps1.'
    Push-Location -LiteralPath 'apps\web'
    try { & npm.cmd run dev } finally { Pop-Location }
} finally {
    if ($porchBackend -and -not $porchBackend.HasExited) {
        # The Windows venv launcher can own a Python child with a different PID.
        # A fresh per-launch UUID identifies only this requested cooperative shutdown.
        $porchOwnedStopPath = Join-Path $porchRuntime.data_root ($porchLaunchId + '.stop')
        if (Test-Path -LiteralPath $porchRuntime.data_root) {
            Set-Content -LiteralPath $porchOwnedStopPath -Value 'stop' -Encoding utf8
        }
        $porchDataRoot = & $porchPython -c 'from porchlight.config import Config; print(Config().data_root)'
        if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the application data directory.' }
        $porchStatePath = Join-Path $porchDataRoot 'process.json'
        if (Test-Path -LiteralPath $porchStatePath) {
            $porchState = Get-Content -LiteralPath $porchStatePath -Raw | ConvertFrom-Json
            if ($porchState.instance -eq $porchLaunchId) { & (Join-Path $PSScriptRoot 'stop.ps1') }
        }
    }
    $env:PORCHLIGHT_DEV_FRONTEND = $porchOldDev
    Pop-Location
}
