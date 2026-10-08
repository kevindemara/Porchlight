[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe') -or -not (Test-Path -LiteralPath 'apps\web\dist\index.html')) { throw 'Run .\bootstrap.ps1 first.' }
    & .\.venv\Scripts\python.exe -m porchlight
    exit $LASTEXITCODE
} finally { Pop-Location }

