<# Shared validation only; dot-sourcing this file makes no changes. #>
function ConvertTo-PorchlightPhoneOrigin {
    param([Parameter(Mandatory)][string]$Origin)
    # Match Config.public_origin: one ASCII domain, HTTPS, port 443, no credentials/path.
    if ($Origin -cnotmatch '^https://(?<domain>[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?)(?::443)?/?$') {
        throw 'Use one HTTPS domain on port 443, without credentials, query, fragment or path.'
    }
    $porchDomain = $Matches.domain.ToLowerInvariant()
    if ($porchDomain.Length -gt 253 -or $porchDomain -notmatch '\.' -or $porchDomain.Contains('..') -or $porchDomain -match '^[0-9.]+$' -or $porchDomain -eq 'localhost') {
        throw 'Use a domain hostname, not an IP address, wildcard or localhost.'
    }
    $porchUri = [uri]$Origin
    return ('https://' + $porchUri.Authority.ToLowerInvariant())
}
function Get-PorchlightPhoneConfigPath {
    if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable; use the documented explicit environment setting.' }
    return (Join-Path $env:LOCALAPPDATA 'PorchlightSetup\phone-access.json')
}
