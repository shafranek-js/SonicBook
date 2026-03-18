param(
    [switch]$Background,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Get-PythonExe {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    $fallback = "C:\Python314\python.exe"
    if (Test-Path $fallback) {
        return $fallback
    }

    throw "Python was not found. Install Python or add it to PATH."
}

function Get-DefaultFfmpegPath($binaryName) {
    $command = Get-Command "$binaryName.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $binaryName
    }

    foreach ($candidate in @(
        (Join-Path $ProjectRoot "bin\$binaryName.exe"),
        (Join-Path $ProjectRoot "ffmpeg\$binaryName.exe")
    )) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    $package = Get-ChildItem -Path $wingetRoot -Directory -Filter "Gyan.FFmpeg_*" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($package) {
        $candidate = Get-ChildItem -Path (Join-Path $package.FullName "ffmpeg-*\bin\$binaryName.exe") -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }

    return $null
}

function Get-RunningPid {
    $conn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($conn) {
        return $conn.OwningProcess
    }
    return $null
}

$runningPid = Get-RunningPid
if ($runningPid) {
    Write-Host "SonicBook is already running on port 8000 with PID $runningPid."
    exit 0
}

$pythonExe = Get-PythonExe
$ffmpegPath = Get-DefaultFfmpegPath "ffmpeg"
$ffprobePath = Get-DefaultFfmpegPath "ffprobe"

if (-not $ffmpegPath) {
    throw 'ffmpeg.exe was not found. Put FFmpeg in PATH, or place ffmpeg.exe under "bin" or "ffmpeg" next to the launcher.'
}
if (-not $ffprobePath) {
    throw 'ffprobe.exe was not found. Put FFprobe in PATH, or place ffprobe.exe under "bin" or "ffmpeg" next to the launcher.'
}

$stdoutLog = Join-Path $ProjectRoot "app_stdout.log"
$stderrLog = Join-Path $ProjectRoot "app_stderr.log"
$previousFfmpeg = $env:FFMPEG_PATH
$previousFfprobe = $env:FFPROBE_PATH

Write-Host "Starting SonicBook..."
Write-Host "Python: $pythonExe"
Write-Host "FFmpeg: $ffmpegPath"
Write-Host "FFprobe: $ffprobePath"

if ($Background) {
    $env:FFMPEG_PATH = $ffmpegPath
    $env:FFPROBE_PATH = $ffprobePath
    $psi = @{
        FilePath = $pythonExe
        ArgumentList = "main.py"
        WorkingDirectory = $ProjectRoot
        RedirectStandardOutput = $stdoutLog
        RedirectStandardError = $stderrLog
        WindowStyle = "Hidden"
    }
    try {
        Start-Process @psi | Out-Null
    }
    finally {
        $env:FFMPEG_PATH = $previousFfmpeg
        $env:FFPROBE_PATH = $previousFfprobe
    }

    if (-not $NoBrowser) {
        Start-Process powershell -WindowStyle Hidden -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command", "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8000/'"
        ) | Out-Null
    }

    Write-Host "SonicBook launched in background."
    exit 0
}

try {
    if (-not $NoBrowser) {
        Start-Process powershell -WindowStyle Hidden -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command", "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8000/'"
        ) | Out-Null
    }

    $env:FFMPEG_PATH = $ffmpegPath
    $env:FFPROBE_PATH = $ffprobePath
    & $pythonExe "main.py"
    exit $LASTEXITCODE
}
finally {
    $env:FFMPEG_PATH = $previousFfmpeg
    $env:FFPROBE_PATH = $previousFfprobe
}
