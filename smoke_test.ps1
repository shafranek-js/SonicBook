param(
    [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Get-RunningPid {
    $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($conn) {
        return $conn.OwningProcess
    }
    return $null
}

function Assert-StatusCode($url, $expectedCode = 200) {
    $response = Invoke-WebRequest -UseBasicParsing $url -TimeoutSec 20
    if ($response.StatusCode -ne $expectedCode) {
        throw "Unexpected status code for ${url}: $($response.StatusCode)"
    }
    return $response
}

if (-not $SkipRestart) {
    $runningPid = Get-RunningPid
    if ($runningPid) {
        Stop-Process -Id $runningPid -Force
        Start-Sleep -Seconds 1
    }
    $env:SONICBOOK_OPEN_BROWSER = "0"
    try {
        & (Join-Path $ProjectRoot "launch_sonicbook.ps1") -Background -NoBrowser | Out-Null
    }
    finally {
        Remove-Item Env:SONICBOOK_OPEN_BROWSER -ErrorAction SilentlyContinue
    }
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        try {
            $null = Invoke-WebRequest -UseBasicParsing "http://localhost:8000/" -TimeoutSec 5
            break
        }
        catch {
            if ($i -eq 19) {
                throw
            }
        }
    }
}

$root = Assert-StatusCode "http://localhost:8000/"
$folder = Assert-StatusCode "http://localhost:8000/api/settings/folder"
$driveStatus = Assert-StatusCode "http://localhost:8000/api/google-drive/status"

$folderJson = $folder.Content | ConvertFrom-Json
$driveJson = $driveStatus.Content | ConvertFrom-Json

if (-not $folderJson.folder) {
    throw "Folder endpoint returned an empty downloads directory."
}

if ($null -eq $driveJson.configured) {
    throw "Google Drive status payload is missing the 'configured' field."
}

Write-Host "Smoke test passed."
Write-Host "Root: 200"
Write-Host "Folder endpoint: 200 -> $($folderJson.folder)"
Write-Host "Google Drive status: 200 -> configured=$($driveJson.configured) connected=$($driveJson.connected)"
