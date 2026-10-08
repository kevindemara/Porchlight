[CmdletBinding()]
param([switch]$Browser)
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    & .\.venv\Scripts\python.exe -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
    & .\.venv\Scripts\ruff.exe check services tests scripts\export-openapi.py
    if ($LASTEXITCODE -ne 0) { throw 'Python lint failed.' }
    & .\.venv\Scripts\mypy.exe services\porchlight
    if ($LASTEXITCODE -ne 0) { throw 'Python type checks failed.' }
    Push-Location -LiteralPath 'apps\web'
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend checks/build failed.' }
        if ($Browser) {
            & npm.cmd test
            if ($LASTEXITCODE -ne 0) { throw 'Browser tests failed.' }
        }
    } finally { Pop-Location }
} finally { Pop-Location }

