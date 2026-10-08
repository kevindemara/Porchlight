[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$porchPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $porchPython)) { throw 'Run bootstrap.ps1 first.' }
# Python installed through the Microsoft Store can resolve LocalAppData into its package cache.
# Read the same validated location as the application, without starting it or touching credentials.
$porchDataRoot = & $porchPython -c 'from porchlight.config import Config; print(Config().data_root)'
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the application data directory.' }
$porchStatePath = Join-Path $porchDataRoot 'process.json'
if (-not (Test-Path -LiteralPath $porchStatePath)) { Write-Host 'No running Porchlight process is recorded.'; exit 0 }
$porchState = Get-Content -LiteralPath $porchStatePath -Raw | ConvertFrom-Json
$porchInstance = [guid]::Parse($porchState.instance).ToString()
# Request cooperative shutdown; never kill a PID that might now belong to another application.
$porchStopPath = Join-Path $porchDataRoot ($porchInstance + '.stop')
Set-Content -LiteralPath $porchStopPath -Value 'stop' -Encoding utf8
for ($porchWait = 0; $porchWait -lt 100; $porchWait++) {
    if (-not (Test-Path -LiteralPath $porchStatePath)) { Write-Host 'Porchlight stopped gracefully.'; exit 0 }
    Start-Sleep -Milliseconds 200
}
throw 'Porchlight did not acknowledge shutdown. Check its terminal; no process was forcibly killed.'
