[CmdletBinding()]
param([string]$DataRoot, [ValidateRange(0,65535)][int]$Port = 0, [string]$PublicOrigin, [switch]$Apply)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\startup-common.ps1')
$porchPlan = Get-PorchlightStartupPlan -DataRoot $DataRoot -Port $Port -PublicOrigin $PublicOrigin
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'apps\web\dist\index.html'))) { throw 'Build the frontend first.' }
if (-not $Apply) {
    Write-Host ('Preview: ' + $porchPlan.task_name + ' would run this checkout at sign-in for the current Windows user.')
    Write-Host ('Data: ' + $porchPlan.data_root + '; loopback port: ' + $porchPlan.port)
    Write-Host ('HTTPS origin: ' + $(if ($porchPlan.public_origin) { $porchPlan.public_origin } else { 'none' }))
    Write-Host ('Executable: ' + $porchPlan.Execute)
    Write-Host ('Arguments: ' + $porchPlan.Arguments)
    Write-Host 'No task was registered. Review this plan, then run the same command with -Apply to opt in.'
    return
}
$porchExisting = Get-ScheduledTask -TaskName $porchPlan.task_name -TaskPath '\' -ErrorAction SilentlyContinue
if ($porchExisting) {
    Assert-PorchlightStartupOwnership -Task $porchExisting -Plan $porchPlan
    if (@($porchExisting.Actions)[0].Arguments -ne $porchPlan.Arguments) { throw 'Startup configuration changed. Review and explicitly uninstall the old registration first.' }
    Write-Host 'The matching Porchlight startup task is already registered.'
    return
}
$porchAction = New-ScheduledTaskAction -Execute $porchPlan.Execute -Argument $porchPlan.Arguments -WorkingDirectory $porchPlan.repository
$porchPrincipal = New-ScheduledTaskPrincipal -UserId $porchPlan.UserId -LogonType Interactive -RunLevel Limited
$porchTrigger = New-ScheduledTaskTrigger -AtLogOn -User $porchPlan.UserId
$porchSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -DisallowHardTerminate -DontStopOnIdleEnd
Register-ScheduledTask -TaskName $porchPlan.task_name -TaskPath '\' -Action $porchAction -Principal $porchPrincipal -Trigger $porchTrigger -Settings $porchSettings -Description $porchPlan.description -ErrorAction Stop | Out-Null
Write-Host 'Porchlight startup registered for the next Windows sign-in. It was not started now. No password, service, firewall or power setting was changed.'
