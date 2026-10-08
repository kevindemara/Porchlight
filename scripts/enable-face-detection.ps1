[CmdletBinding()]
param([switch]$Install, [string]$ModelDirectory = 'C:\local-models\yunet-face-detection')
$ErrorActionPreference = 'Stop'
$porchRoot = Split-Path -Parent $PSScriptRoot
$porchPython = Join-Path $porchRoot '.venv\Scripts\python.exe'
if (-not $Install) {
    Write-Host 'Preview: install opencv-python-headless 4.14.0.94 and numpy 2.5.3 into Porchlight .venv.'
    Write-Host "Download the pinned MIT YuNet detector (232,589 bytes) into $ModelDirectory."
    Write-Host 'No recognition model, profiles, global Ollama change or automatic analysis enablement.'
    Write-Host 'After specific approval: rerun with -Install, then restart Porchlight.'
    exit 0
}
if (-not (Test-Path -LiteralPath $porchPython -PathType Leaf)) { throw 'Run bootstrap.ps1 first.' }
& $porchPython -m pip install --only-binary=:all: --constraint (Join-Path $porchRoot 'requirements.lock') --requirement (Join-Path $porchRoot 'requirements.faces.lock')
if ($LASTEXITCODE -ne 0) { throw 'Optional detector dependency installation failed.' }
& $porchPython (Join-Path $PSScriptRoot 'install-face-model.py') --directory $ModelDirectory
if ($LASTEXITCODE -ne 0) { throw 'Detector model installation failed.' }
