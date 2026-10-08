[CmdletBinding()]
param([switch]$Install)
$ErrorActionPreference = 'Stop'
$porchRoot = Split-Path -Parent $PSScriptRoot
$porchPython = Join-Path $porchRoot '.venv\Scripts\python.exe'
if (-not $Install) {
    Write-Host 'Preview: install the four optional packages pinned in requirements.push.lock into Porchlight .venv.'
    Write-Host 'This does not create keys, expose a server, pair a phone or send a notification.'
    Write-Host 'After approval, rerun with -Install and restart Porchlight.'
    exit 0
}
if (-not (Test-Path -LiteralPath $porchPython)) { throw 'Run bootstrap.ps1 first.' }
& $porchPython -m pip install --constraint (Join-Path $porchRoot 'requirements.lock') --requirement (Join-Path $porchRoot 'requirements.push.lock')
if ($LASTEXITCODE -ne 0) { throw 'Optional Web Push installation failed.' }
