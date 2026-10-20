<# Explicit local actions only. Default is preview; no installer or shared-server restart. #>
[CmdletBinding()]
param(
    [switch]$LocalOnly,
    [ValidateSet('qwen3-vl:4b', 'qwen3-vl:8b')][string]$Model,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
if (-not $LocalOnly -and -not $Model) { throw 'Choose -LocalOnly or -Model. Run without -Apply to preview.' }
if ($Model) {
    Write-Host ('Preview: ollama pull ' + $Model + '. Review model terms and free space first.')
    if ($Apply -and -not (Get-Command ollama -ErrorAction SilentlyContinue)) { throw 'Install/open Ollama first, then reopen Terminal.' }
}
if ($LocalOnly) {
    Write-Host 'Preview: disable cloud models/search for ALL applications using your Ollama server.'
    Write-Host 'Existing settings/models are preserved. You must quit/reopen Ollama yourself afterward.'
}
if (-not $Apply) { Write-Host 'No changes made. Repeat with -Apply only after reviewing these actions.'; return }
if ($LocalOnly) {
    $porchOllamaFolder = Join-Path $env:USERPROFILE '.ollama'
    $porchServerFile = Join-Path $porchOllamaFolder 'server.json'
    $porchSettings = [pscustomobject]@{}
    if (Test-Path -LiteralPath $porchServerFile) {
        $porchSettings = Get-Content -LiteralPath $porchServerFile -Raw | ConvertFrom-Json
        if ($porchSettings -isnot [pscustomobject]) { throw 'Expected an Ollama JSON object. Review server.json; nothing was replaced.' }
    }
    if ($porchSettings.disable_ollama_cloud -isnot [bool] -or -not $porchSettings.disable_ollama_cloud) {
        New-Item -ItemType Directory -Path $porchOllamaFolder -Force | Out-Null
        if (Test-Path -LiteralPath $porchServerFile) {
            $porchBackup = Join-Path $porchOllamaFolder ('server.before-porchlight-' + [guid]::NewGuid() + '.json')
            Copy-Item -LiteralPath $porchServerFile -Destination $porchBackup
        }
        $porchSettings | Add-Member -NotePropertyName disable_ollama_cloud -NotePropertyValue $true -Force
        $porchTemp = Join-Path $porchOllamaFolder ('server.porchlight-' + [guid]::NewGuid() + '.tmp')
        $porchJson = $porchSettings | ConvertTo-Json -Depth 100
        [System.IO.File]::WriteAllText($porchTemp, $porchJson, [System.Text.UTF8Encoding]::new($false))
        # Fixed files inside this user's .ollama folder; no recursive move/delete.
        Move-Item -LiteralPath $porchTemp -Destination $porchServerFile -Force
    }
    Write-Host 'Local-only setting saved. Quit Ollama from its tray menu and reopen it before testing.'
}
if ($Model) {
    & ollama pull $Model
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Automatic Porchlight AI remains unchanged; retry or skip AI.' }
    Write-Host 'Model downloaded. In Porchlight, check models and pass the synthetic image test before enabling analysis.'
}
