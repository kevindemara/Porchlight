param([string]$Repository, [string]$DataRoot)
$ErrorActionPreference = 'Stop'
$global:porchStartupSynthetic = @{ registered=0; removed=0; queried=0; task=$null; built=$true }
function Test-Path {
    [CmdletBinding()] param([string]$LiteralPath)
    if ($LiteralPath.EndsWith('apps\web\dist\index.html')) {
        return $global:porchStartupSynthetic.built
    }
    return Microsoft.PowerShell.Management\Test-Path -LiteralPath $LiteralPath
}
function Get-ScheduledTask {
    [CmdletBinding()] param($TaskName, $TaskPath)
    $global:porchStartupSynthetic.queried++; return $global:porchStartupSynthetic.task
}
function New-ScheduledTaskAction { param($Execute,$Argument,$WorkingDirectory)
    return [pscustomobject]@{ Execute=$Execute; Arguments=$Argument; WorkingDirectory=$WorkingDirectory }
}
function New-ScheduledTaskPrincipal { param($UserId,$LogonType,$RunLevel)
    return [pscustomobject]@{ UserId=$UserId; LogonType=$LogonType; RunLevel=$RunLevel }
}
function New-ScheduledTaskTrigger { param([switch]$AtLogOn,$User)
    return [pscustomobject]@{ AtLogOn=$AtLogOn; User=$User }
}
function New-ScheduledTaskSettingsSet { param($MultipleInstances,$ExecutionTimeLimit,$RestartCount,$RestartInterval,[switch]$DisallowHardTerminate,[switch]$DontStopOnIdleEnd)
    return [pscustomobject]@{ MultipleInstances=$MultipleInstances; RestartCount=$RestartCount; ExecutionTimeLimit=$ExecutionTimeLimit }
}
function Register-ScheduledTask {
    [CmdletBinding()] param($TaskName,$TaskPath,$Action,$Principal,$Trigger,$Settings,$Description)
    $global:porchStartupSynthetic.registered++
    $global:porchStartupSynthetic.task=[pscustomobject]@{ Description=$Description; Actions=@($Action); Principal=$Principal; Settings=$Settings; Trigger=$Trigger }
    return $global:porchStartupSynthetic.task
}
function Unregister-ScheduledTask {
    [CmdletBinding(SupportsShouldProcess)] param($InputObject)
    if ($InputObject -ne $global:porchStartupSynthetic.task) { throw 'Unexpected task removal' }
    $global:porchStartupSynthetic.removed++; $global:porchStartupSynthetic.task=$null
}
$install=Join-Path $Repository 'install-startup.ps1'
$uninstall=Join-Path $Repository 'uninstall-startup.ps1'
& $install -DataRoot $DataRoot
& $uninstall -DataRoot $DataRoot
if ($global:porchStartupSynthetic.registered -or $global:porchStartupSynthetic.queried -or $global:porchStartupSynthetic.removed) { throw 'Preview accessed task scheduler' }
& $install -DataRoot $DataRoot -Apply
& $install -DataRoot $DataRoot -Apply
if ($global:porchStartupSynthetic.registered -ne 1 -or $global:porchStartupSynthetic.task.Principal.LogonType -ne 'Interactive' -or $global:porchStartupSynthetic.task.Principal.RunLevel -ne 'Limited' -or $global:porchStartupSynthetic.task.Settings.RestartCount -ne 3 -or $global:porchStartupSynthetic.task.Settings.MultipleInstances -ne 'IgnoreNew') { throw 'Unexpected registration plan' }
$savedDescription=$global:porchStartupSynthetic.task.Description
$global:porchStartupSynthetic.task.Description='Unrelated application'
$rejected=$false
try { & $uninstall -DataRoot $DataRoot -Apply } catch { $rejected=$true }
if (-not $rejected -or $global:porchStartupSynthetic.removed) { throw 'Removed unrelated task' }
$global:porchStartupSynthetic.task.Description=$savedDescription
$savedArguments=$global:porchStartupSynthetic.task.Actions[0].Arguments
$global:porchStartupSynthetic.task.Actions[0].Arguments='-File unrelated.ps1'
$rejected=$false
try { & $install -DataRoot $DataRoot -Apply } catch { $rejected=$true }
if (-not $rejected -or $global:porchStartupSynthetic.registered -ne 1) { throw 'Overwrote unrelated task' }
$global:porchStartupSynthetic.task.Actions[0].Arguments=$savedArguments
$savedUser=$global:porchStartupSynthetic.task.Principal.UserId
$global:porchStartupSynthetic.task.Principal.UserId='Unrelated user'
$rejected=$false
try { & $uninstall -DataRoot $DataRoot -Apply } catch { $rejected=$true }
if (-not $rejected -or $global:porchStartupSynthetic.removed) { throw 'Removed another user task' }
$global:porchStartupSynthetic.task.Principal.UserId=$savedUser
$global:porchStartupSynthetic.built=$false
$rejected=$false
try { & $install -DataRoot $DataRoot -Apply } catch { $rejected=$true }
if (-not $rejected -or $global:porchStartupSynthetic.registered -ne 1) { throw 'Registered missing build' }
$global:porchStartupSynthetic.built=$true
$rejected=$false
try { & $install -DataRoot $DataRoot -Port 9999 -Apply } catch { $rejected=$true }
if (-not $rejected -or $global:porchStartupSynthetic.registered -ne 1) { throw 'Changed task configuration silently' }
& $uninstall -DataRoot $DataRoot -Apply
& $uninstall -DataRoot $DataRoot -Apply
if ($global:porchStartupSynthetic.removed -ne 1 -or (Test-Path -LiteralPath $DataRoot)) { throw 'Unexpected removal or profile creation' }
Write-Output ('RESULT '+(@{ registered=$global:porchStartupSynthetic.registered; removed=$global:porchStartupSynthetic.removed; passed=$true }|ConvertTo-Json -Compress))
