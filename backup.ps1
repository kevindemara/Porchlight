[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$porchPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $porchPython)) { throw 'Run bootstrap.ps1 first.' }
& $porchPython -m porchlight.operations backup --backup $Destination
if ($LASTEXITCODE -ne 0) { throw 'Backup failed. Stop Porchlight first and use a new local destination.' }
