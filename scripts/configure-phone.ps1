<# Explicit optional origin configuration. No connector install, DNS, firewall or restart. #>
[CmdletBinding(DefaultParameterSetName = 'Origin')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Origin')][string]$Origin,
    [Parameter(Mandatory, ParameterSetName = 'Disable')][switch]$Disable,
    [Parameter(ParameterSetName = 'Origin')][guid]$TunnelId,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'phone-config.ps1')
$porchPath = Get-PorchlightPhoneConfigPath
$porchOrigin = if ($Disable) { $null } else { ConvertTo-PorchlightPhoneOrigin $Origin }
Write-Host $(if ($Disable) { 'Preview: remove the saved phone origin for start.ps1.' } else { 'Preview: start.ps1 will accept exactly ' + $porchOrigin + ' through a loopback HTTPS proxy.' })
Write-Host 'This makes no tunnel, DNS, firewall, certificate or service change. Ollama remains private.'
if (-not $Apply) { Write-Host 'No changes made. Review the phone guide, then repeat with -Apply.'; return }
if ($Disable) {
    if (Test-Path -LiteralPath $porchPath) { Remove-Item -LiteralPath $porchPath }
} else {
    if (Test-Path -LiteralPath $porchPath) {
        $porchPrevious = Get-Content -LiteralPath $porchPath -Raw | ConvertFrom-Json
        if ($porchPrevious.public_origin -ne $porchOrigin) {
            throw 'A different phone origin is already saved. Disable it explicitly before replacing it.'
        }
    }
    New-Item -ItemType Directory -Path (Split-Path -Parent $porchPath) -Force | Out-Null
    @{ version = 1; public_origin = $porchOrigin } | ConvertTo-Json | Set-Content -LiteralPath $porchPath -Encoding utf8
    if ($TunnelId -and $TunnelId -ne [guid]::Empty) {
        $porchCredentials = Join-Path $env:USERPROFILE ('.cloudflared\' + $TunnelId + '.json')
        if (-not (Test-Path -LiteralPath $porchCredentials)) {
            throw 'Tunnel credentials are missing. Origin saved; complete cloudflared tunnel login/create, then repeat to generate its routing file.'
        }
        # JSON quoting is valid YAML quoting; paths with spaces/backslashes stay literal.
        $porchQuotedCredentials = ConvertTo-Json -InputObject $porchCredentials -Compress
        $porchHostname = ([uri]$porchOrigin).Host
        @"
tunnel: $TunnelId
credentials-file: $porchQuotedCredentials
ingress:
  - hostname: $porchHostname
    service: http://127.0.0.1:8765
    originRequest:
      httpHostHeader: $porchHostname
  - service: http_status:404
"@ | Set-Content -LiteralPath (Join-Path (Split-Path -Parent $porchPath) 'tunnel.yml') -Encoding utf8
        Write-Host 'Private tunnel routing file generated. Start the connector using the phone guide; no connector was started.'
    }
}
Write-Host 'Saved outside the repository. Stop and restart Porchlight to apply. Explicit PORCHLIGHT_PUBLIC_ORIGIN overrides this file.'
