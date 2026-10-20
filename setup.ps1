<# Beginner setup. Installs only after explicit local choices. -Check is read-only. #>
[CmdletBinding()]
param([switch]$Check)
$ErrorActionPreference = 'Stop'
Write-Host 'Porchlight setup — cameras first, AI and phone access optional.'
Write-Host 'Need prerequisites? Python: https://www.python.org/downloads/windows/ (3.12–3.14, add to PATH)'
Write-Host 'Node: https://nodejs.org/en/download (22.12+; tested with 24.19.0, include npm)'
Write-Host 'Open a new PowerShell window after installing prerequisites, then retry.'
& (Join-Path $PSScriptRoot 'bootstrap.ps1') -Check
if ($Check) {
    Write-Host 'Read-only check complete. No software, model or phone connection changed.'
    return
}
$porchAnswer = Read-Host 'Install the locked Python/frontend packages in this checkout and build Porchlight? Type YES'
if ($porchAnswer -cne 'YES') {
    Write-Host 'Installation skipped. You can return with .\setup.ps1.'
    return
}
& (Join-Path $PSScriptRoot 'bootstrap.ps1')
$porchAnswer = Read-Host 'Install the pinned FFmpeg tools for recording imports/playback processing (109 MB, private folder, no PATH change)? Type YES'
if ($porchAnswer -ceq 'YES') { & (Join-Path $PSScriptRoot 'scripts\install-ffmpeg.ps1') }
Write-Host 'Start: .\start.ps1. Open http://127.0.0.1:8765 and create your local owner.'
Write-Host 'Then Settings → Open setup guide. AI can stay off; use the phone guide for optional HTTPS.'
Write-Host 'Detailed help: docs\QUICK_START.md. No account, tunnel, AI or startup registration was created.'
