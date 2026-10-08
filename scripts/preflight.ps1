<#
.SYNOPSIS
Read-only Porchlight prerequisite inventory for Windows PowerShell 5.1 or newer.
.DESCRIPTION
No installs, downloads, model inference, Blink login, configuration edits,
firewall changes or file writes. Ollama requests are restricted to loopback.
Review the script before running. Output may contain local model names;
keep the output private. It is not a hardware compatibility test.
#>
[CmdletBinding()]
param(
    [uri]$OllamaBaseUrl = 'http://127.0.0.1:11434',
    [ValidateRange(0, 20)]
    [int]$ModelDetailsLimit = 8
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

if (-not $OllamaBaseUrl.IsAbsoluteUri -or
    $OllamaBaseUrl.Scheme -notin @('http', 'https') -or
    -not $OllamaBaseUrl.IsLoopback -or
    $OllamaBaseUrl.UserInfo -or $OllamaBaseUrl.Query -or
    $OllamaBaseUrl.Fragment -or $OllamaBaseUrl.AbsolutePath -ne '/') {
    throw 'Use a root loopback HTTP(S) Ollama URL with no credentials, query or fragment.'
}
$Base = $OllamaBaseUrl.AbsoluteUri.TrimEnd('/')

function Write-Section {
    param([string]$Title)
    Write-Host ''
    Write-Host ('=== ' + $Title + ' ===')
}

function Read-Version {
    param([string]$Name, [string[]]$VersionArgs)
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $command) {
        Write-Host ($Name + ': not found on PATH')
        return
    }
    # Avoid launching a Microsoft Store Python app-execution alias.
    if ($Name -in @('python', 'python3') -and $command.Source -match '\\WindowsApps\\') {
        Write-Host ($Name + ': WindowsApps alias found; real interpreter not established')
        return
    }
    try {
        $lines = @(& $command.Source @VersionArgs 2>&1)
        if ($lines.Count -gt 0) {
            Write-Host ($Name + ': ' + [string]$lines[0])
        } else {
            Write-Host ($Name + ': found; no version output')
        }
    } catch {
        Write-Host ($Name + ': found; version probe did not complete successfully')
    }
}

function Read-OllamaMetadata {
    param([string]$Route, [object]$Body = $null)
    if ($Route -notin @('/api/version', '/api/tags', '/api/show')) {
        throw 'Only the three read-only metadata routes are allowed.'
    }
    try {
        $request = @{
            Uri = ($Base + $Route)
            TimeoutSec = 5
            MaximumRedirection = 0
            ErrorAction = 'Stop'
        }
        if ($null -eq $Body) {
            return Invoke-RestMethod @request -Method Get
        }
        return Invoke-RestMethod @request -Method Post -ContentType 'application/json' -Body ($Body | ConvertTo-Json -Depth 5 -Compress)
    } catch {
        # Avoid dumping request/response bodies or any unrelated configuration.
        Write-Host ('Ollama metadata unavailable at ' + $Route + '; no changes made.')
        return $null
    }
}

Write-Section 'Scope'
Write-Host 'Read-only environment inventory. No Blink connection and no vision inference.'
Write-Host ('PowerShell: ' + $PSVersionTable.PSVersion.ToString())

Write-Section 'Tools already installed'
Read-Version -Name 'git' -VersionArgs @('--version')
Read-Version -Name 'python' -VersionArgs @('--version')
Read-Version -Name 'node' -VersionArgs @('--version')
Read-Version -Name 'ffmpeg' -VersionArgs @('-version')
Read-Version -Name 'ffprobe' -VersionArgs @('-version')
Read-Version -Name 'ollama' -VersionArgs @('--version')
# Presence only; do not invoke a downloaded script or package installation.
foreach ($name in @('npm', 'pnpm', 'uv')) {
    $found = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $found) { Write-Host ($name + ': not found on PATH') }
    else { Write-Host ($name + ': available; not invoked') }
}

Write-Section 'Hardware, without serial numbers'
try {
    $os = Get-CimInstance -ClassName Win32_OperatingSystem
    Write-Host ('Windows: ' + $os.Caption + ' / ' + $os.Version)
    Write-Host ('Physical RAM GiB: ' + [math]::Round($os.TotalVisibleMemorySize / 1MB, 1))
    $cpu = Get-CimInstance -ClassName Win32_Processor | Select-Object -First 1
    Write-Host ('CPU: ' + $cpu.Name)
    Get-CimInstance -ClassName Win32_VideoController | ForEach-Object {
        Write-Host ('Display adapter: ' + $_.Name)
    }
} catch {
    Write-Host 'Windows hardware metadata unavailable in this environment.'
}
$nvidia = Get-Command 'nvidia-smi' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $nvidia) {
    try {
        Write-Host 'NVIDIA name, total VRAM MiB, free VRAM MiB:'
        & $nvidia.Source '--query-gpu=name,memory.total,memory.free' '--format=csv,noheader,nounits'
    } catch { Write-Host 'NVIDIA memory probe unavailable; do not infer VRAM from a model name.' }
} else {
    Write-Host 'nvidia-smi not found; exact VRAM was not measured.'
}

Write-Section 'Drive free space (not automatic storage selection)'
Get-PSDrive -PSProvider FileSystem | ForEach-Object {
    if ($null -ne $_.Free) {
        Write-Host ($_.Name + ': ' + [math]::Round($_.Free / 1GB, 1) + ' GiB free')
    }
}

Write-Section 'Existing loopback Ollama metadata'
$version = Read-OllamaMetadata -Route '/api/version'
if ($null -ne $version -and $version.PSObject.Properties.Name -contains 'version') {
    Write-Host ('Ollama API version: ' + $version.version)
}
$tags = Read-OllamaMetadata -Route '/api/tags'
if ($null -ne $tags -and $tags.PSObject.Properties.Name -contains 'models') {
    $models = @($tags.models)
    Write-Host ('Installed entries reported: ' + $models.Count)
    foreach ($model in $models) {
        if ($model.PSObject.Properties.Name -contains 'name') {
            $sizeText = 'size unknown'
            if ($model.PSObject.Properties.Name -contains 'size') {
                $sizeText = ([math]::Round($model.size / 1GB, 2).ToString() + ' GiB artifact; not VRAM requirement')
            }
            Write-Host ('  ' + $model.name + ' | ' + $sizeText)
        }
    }
    foreach ($model in ($models | Select-Object -First $ModelDetailsLimit)) {
        if ($model.PSObject.Properties.Name -notcontains 'name') { continue }
        $detail = Read-OllamaMetadata -Route '/api/show' -Body @{model = $model.name}
        if ($null -ne $detail -and $detail.PSObject.Properties.Name -contains 'capabilities') {
            Write-Host ('Capabilities for ' + $model.name + ': ' + (@($detail.capabilities) -join ', '))
        } else {
            Write-Host ('Capabilities for ' + $model.name + ': not established from metadata')
        }
    }
}

Write-Section 'What this did NOT verify'
Write-Host 'No vision accuracy, private-image processing, cloud-disable state, camera compatibility, entitlement, or phone delivery was tested.'
Write-Host 'Local model execution must be established before private footage is analysed. No models were pulled, run, unloaded or deleted.'
