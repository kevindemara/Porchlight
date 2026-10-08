[CmdletBinding()]
param([string]$DataRoot, [ValidateRange(0,65535)][int]$Port = 0, [string]$PublicOrigin, [switch]$Apply)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\startup-common.ps1')
$porchPlan = Get-PorchlightStartupPlan -DataRoot $DataRoot -Port $Port -PublicOrigin $PublicOrigin
if (-not $Apply) {
    Write-Host ('Preview: remove only the matching ' + $porchPlan.task_name + ' registration for this checkout/profile/user.')
    Write-Host 'No task was queried or removed. Add -Apply after review. Running processes and all data are left in place.'
    return
}
$porchExisting = Get-ScheduledTask -TaskName $porchPlan.task_name -TaskPath '\' -ErrorAction SilentlyContinue
if (-not $porchExisting) { Write-Host 'No matching Porchlight startup registration exists.'; return }
Assert-PorchlightStartupOwnership -Task $porchExisting -Plan $porchPlan
Unregister-ScheduledTask -InputObject $porchExisting -Confirm:$false -ErrorAction Stop
Write-Host 'Porchlight startup registration removed. Use stop.ps1 to stop a running app; data was preserved.'
