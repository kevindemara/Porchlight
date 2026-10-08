[CmdletBinding()]
param([switch]$Install, [string]$ModelDirectory = 'C:\local-models\sface-recognition')
$ErrorActionPreference = 'Stop'
$porchRoot = Split-Path -Parent $PSScriptRoot
$porchPython = Join-Path $porchRoot '.venv\Scripts\python.exe'
if (-not $Install) {
    Write-Host "Preview: download the pinned Apache-2.0 OpenCV Zoo SFace model (38,696,353 bytes) to $ModelDirectory."
    Write-Host 'YuNet/OpenCV from enable-face-detection.ps1 is required. No recognition profile or automatic processing is enabled by installation.'
    Write-Host 'After reviewing this action: rerun with -Install, then restart Porchlight.'
    exit 0
}
if (-not (Test-Path -LiteralPath $porchPython -PathType Leaf)) { throw 'Run bootstrap.ps1 first.' }
& $porchPython -c 'import cv2; assert hasattr(cv2, "FaceRecognizerSF")'
if ($LASTEXITCODE -ne 0) { throw 'Install optional face detection prerequisites first.' }
& $porchPython (Join-Path $PSScriptRoot 'install-sface-model.py') --directory $ModelDirectory
if ($LASTEXITCODE -ne 0) { throw 'SFace model installation failed.' }
