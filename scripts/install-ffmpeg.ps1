<# Explicit opt-in install of Porchlight's private FFmpeg toolset; no global PATH changes. #>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$porchToolsRoot = Join-Path $env:LOCALAPPDATA 'Porchlight\tools\ffmpeg'
$porchBin = Join-Path $porchToolsRoot 'bin'
$porchArchive = Join-Path $porchToolsRoot 'ffmpeg-9.0.2-essentials_build.zip'
$porchExpectedHash = '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'
if ((Test-Path -LiteralPath (Join-Path $porchBin 'ffmpeg.exe')) -and (Test-Path -LiteralPath (Join-Path $porchBin 'ffprobe.exe'))) {
    $porchExistingVersion = & (Join-Path $porchBin 'ffmpeg.exe') -version
    if ($LASTEXITCODE -ne 0) { throw 'Installed FFmpeg could not start.' }
    Write-Host $porchExistingVersion[0]
    $porchExistingProbeVersion = & (Join-Path $porchBin 'ffprobe.exe') -version
    if ($LASTEXITCODE -ne 0) { throw 'Installed ffprobe could not start.' }
    Write-Host $porchExistingProbeVersion[0]
    Write-Host ('Porchlight media tools are configured at ' + $porchBin)
    exit 0
}
New-Item -ItemType Directory -Path $porchToolsRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath $porchArchive)) {
    Write-Host 'Downloading the pinned 109 MB FFmpeg 9.0.2 Windows essentials build.'
    & curl.exe --fail --location --silent --show-error --output $porchArchive 'https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip'
    if ($LASTEXITCODE -ne 0) { throw 'FFmpeg download failed. No executable was installed.' }
}
$porchActualHash = (Get-FileHash -LiteralPath $porchArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($porchActualHash -ne $porchExpectedHash) { throw 'FFmpeg checksum mismatch. No executable was installed.' }
$porchStaging = Join-Path $porchToolsRoot 'verified-package'
if (-not (Test-Path -LiteralPath $porchStaging)) { Expand-Archive -LiteralPath $porchArchive -DestinationPath $porchStaging }
$porchPackage = Join-Path $porchStaging 'ffmpeg-9.0.2-essentials_build'
New-Item -ItemType Directory -Path $porchBin -Force | Out-Null
foreach ($porchExecutable in @('ffmpeg.exe', 'ffprobe.exe')) {
    $porchSource = Join-Path $porchPackage ('bin\' + $porchExecutable)
    if (-not (Test-Path -LiteralPath $porchSource)) { throw 'Verified package layout changed.' }
    Copy-Item -LiteralPath $porchSource -Destination (Join-Path $porchBin $porchExecutable)
}
$porchVersion = & (Join-Path $porchBin 'ffmpeg.exe') -version
if ($LASTEXITCODE -ne 0) { throw 'FFmpeg could not start.' }
Write-Host $porchVersion[0]
& (Join-Path $porchBin 'ffmpeg.exe') -buildconf 2>&1 | Out-File -LiteralPath (Join-Path $porchToolsRoot 'buildconf.txt') -Encoding utf8
@{ version = '9.0.2'; archive_sha256 = $porchExpectedHash; source = 'https://www.gyan.dev/ffmpeg/builds/'; licence = 'GPL-3.0-or-later'; usage = 'Local subprocess; binaries not bundled in repository' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $porchToolsRoot 'installation.json') -Encoding utf8
Write-Host ('Installed for Porchlight at ' + $porchBin)
