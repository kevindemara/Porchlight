[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$porchOriginalOrigin = $env:PORCHLIGHT_PUBLIC_ORIGIN
Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe') -or -not (Test-Path -LiteralPath 'apps\web\dist\index.html')) { throw 'Run .\bootstrap.ps1 first.' }
    . (Join-Path $PSScriptRoot 'scripts\phone-config.ps1')
    $porchPhonePath = Get-PorchlightPhoneConfigPath
    if (-not $porchOriginalOrigin -and (Test-Path -LiteralPath $porchPhonePath)) {
        $porchPhone = Get-Content -LiteralPath $porchPhonePath -Raw | ConvertFrom-Json
        if ($porchPhone.version -ne 1 -or -not $porchPhone.public_origin) { throw 'Invalid phone configuration. Review scripts/configure-phone.ps1.' }
        $env:PORCHLIGHT_PUBLIC_ORIGIN = ConvertTo-PorchlightPhoneOrigin $porchPhone.public_origin
    }
    & .\.venv\Scripts\python.exe -m porchlight
    exit $LASTEXITCODE
} finally { $env:PORCHLIGHT_PUBLIC_ORIGIN = $porchOriginalOrigin; Pop-Location }

