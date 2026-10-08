[CmdletBinding()]
param([switch]$Check)
$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Install Python 3.12 through 3.14, then rerun bootstrap.' }
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw 'Install a supported Node runtime, then rerun bootstrap.' }
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Install a supported Node LTS with npm, then rerun bootstrap.' }
    $porchPythonText = & python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
    if ($LASTEXITCODE -ne 0) { throw 'Python version detection failed.' }
    $porchPythonVersion = [version]$porchPythonText
    if ($porchPythonVersion -lt [version]'3.12.0' -or $porchPythonVersion -ge [version]'3.15.0') {
        throw 'This project requires Python 3.12 through 3.14; this environment was tested with 3.12.10.'
    }
    $porchNodeText = & node -p 'process.versions.node'
    if ($LASTEXITCODE -ne 0) { throw 'Node version detection failed.' }
    $porchNodeVersion = [version]$porchNodeText
    # Match the locked Vite runtime's ^20.19.0 || >=22.12.0 engine requirement.
    if (-not (($porchNodeVersion.Major -eq 20 -and $porchNodeVersion.Minor -ge 19) -or $porchNodeVersion -ge [version]'22.12.0')) {
        throw 'The locked frontend build requires Node 20.19+ in the 20 series, or Node 22.12+; this environment was tested with 24.19.0.'
    }
    if (Test-Path -LiteralPath '.venv\Scripts\python.exe') {
        $porchVenvText = & .\.venv\Scripts\python.exe -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
        if ($LASTEXITCODE -ne 0) { throw 'Existing virtual environment version detection failed.' }
        $porchVenvVersion = [version]$porchVenvText
        if ($porchVenvVersion -lt [version]'3.12.0' -or $porchVenvVersion -ge [version]'3.15.0') {
            throw 'The existing virtual environment uses an unsupported Python version. Review it before replacing it.'
        }
    }
    if ($Check) {
        Write-Host ('Bootstrap preflight passed: Python ' + $porchPythonText + ', Node ' + $porchNodeText + '. No dependencies installed.')
        Write-Host 'Run bootstrap.ps1 without -Check when ready to install the locked packages. Native hardware, FFmpeg, AI and phone checks are separate.'
        return
    }
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        & python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the project virtual environment.' }
    }
    & .\.venv\Scripts\python.exe -m pip install -r requirements.lock
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    & .\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
    if ($LASTEXITCODE -ne 0) { throw 'Application installation failed.' }
    & .\.venv\Scripts\python.exe scripts\export-openapi.py
    if ($LASTEXITCODE -ne 0) { throw 'API contract generation failed.' }
    Push-Location -LiteralPath 'apps\web'
    try {
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        & npm.cmd run generate:api
        if ($LASTEXITCODE -ne 0) { throw 'API type generation failed.' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
    Write-Host 'Ready. Run .\start.ps1, then open http://127.0.0.1:8765.'
    Write-Host 'If FFmpeg is missing, explicitly run .\scripts\install-ffmpeg.ps1 to enable MP4 imports.'
} finally { Pop-Location }
