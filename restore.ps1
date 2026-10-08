[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Backup,
    [Parameter(Mandatory=$true)][string]$Destination,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$porchPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $porchPython)) { throw 'Run bootstrap.ps1 first.' }
$porchArguments = @('-m', 'porchlight.operations', 'restore', '--backup', $Backup, '--destination', $Destination)
if ($Apply) { $porchArguments += '--apply' }
& $porchPython @porchArguments
if ($LASTEXITCODE -ne 0) { throw 'Restore validation failed. Existing data was not replaced.' }
