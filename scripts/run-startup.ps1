[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$DataRoot, [ValidateRange(1024,65535)][int]$Port = 8765, [string]$PublicOrigin, [string]$Ffmpeg, [string]$Ffprobe)
$ErrorActionPreference = 'Stop'
$env:PORCHLIGHT_DATA_ROOT = $DataRoot
$env:PORCHLIGHT_PORT = [string]$Port
$env:PORCHLIGHT_DEV_FRONTEND = 'false'
$env:PORCHLIGHT_PUBLIC_ORIGIN = $PublicOrigin
if ($Ffmpeg) { $env:PORCHLIGHT_FFMPEG = $Ffmpeg }
if ($Ffprobe) { $env:PORCHLIGHT_FFPROBE = $Ffprobe }
# The native application validates configuration, holds its profile lock and
# monitors Ollama readiness without starting/reconfiguring/unloading Ollama.
& (Join-Path (Split-Path -Parent $PSScriptRoot) 'start.ps1')
exit $LASTEXITCODE
