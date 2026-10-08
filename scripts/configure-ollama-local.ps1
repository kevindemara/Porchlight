param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$taskOllamaDirectory = Join-Path $env:USERPROFILE '.ollama'
$taskConfigPath = Join-Path $taskOllamaDirectory 'server.json'
$taskValues = [ordered]@{}
if (Test-Path -LiteralPath $taskConfigPath) {
    $taskDocument = Get-Content -LiteralPath $taskConfigPath -Raw | ConvertFrom-Json
    if ($taskDocument -isnot [System.Management.Automation.PSCustomObject]) {
        throw 'Existing Ollama server.json must contain an object. No changes were made.'
    }
    foreach ($taskProperty in $taskDocument.PSObject.Properties) {
        $taskValues[$taskProperty.Name] = $taskProperty.Value
    }
}
Write-Output "Ollama configuration: $taskConfigPath"
Write-Output 'Proposed change: disable_ollama_cloud = true. Other settings are preserved.'
Write-Output 'This disables Ollama cloud models and web search for all clients of this server.'
if (-not $Apply) {
    Write-Output 'Preview only. Run again with -Apply after approving the shared setting change.'
    return
}
if ($taskValues['disable_ollama_cloud'] -eq $true) {
    Write-Output 'The configuration already disables cloud features. Restart Ollama if needed.'
    return
}
$taskValues['disable_ollama_cloud'] = $true
New-Item -ItemType Directory -Path $taskOllamaDirectory -Force | Out-Null
$taskTemporaryPath = Join-Path $taskOllamaDirectory ('.porchlight-' + [guid]::NewGuid().ToString() + '.tmp')
try {
    [System.IO.File]::WriteAllText($taskTemporaryPath, ($taskValues | ConvertTo-Json -Depth 100), [System.Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $taskConfigPath) {
        $taskBackupPath = Join-Path $taskOllamaDirectory ('server.porchlight-' + [guid]::NewGuid().ToString() + '.bak')
        [System.IO.File]::Replace($taskTemporaryPath, $taskConfigPath, $taskBackupPath)
        Write-Output "Original configuration backed up to: $taskBackupPath"
    } else {
        Move-Item -LiteralPath $taskTemporaryPath -Destination $taskConfigPath
    }
} finally {
    if (Test-Path -LiteralPath $taskTemporaryPath) { Remove-Item -LiteralPath $taskTemporaryPath }
}
Write-Output 'Configuration saved. Restart Ollama, then check Local AI in Porchlight Settings.'
