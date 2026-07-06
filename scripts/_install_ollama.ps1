$url = "https://ollama.com/download/OllamaSetup.exe"
$dest = "C:\Users\talha\AppData\Local\Temp\OllamaSetup.exe"

Write-Host "=== Downloading Ollama installer (using curl.exe) ==="
if (Test-Path $dest) {
    Remove-Item $dest -Force
}

# Run curl.exe to download
curl.exe -L -o $dest $url

if (-not (Test-Path $dest)) {
    Write-Host "ERROR: Download failed. File does not exist: $dest"
    exit 1
}

$fileSize = (Get-Item $dest).Length
Write-Host "Downloaded file size: $fileSize bytes"
if ($fileSize -lt 10MB) {
    Write-Host "ERROR: Downloaded file is too small. Probably a download error."
    exit 1
}

Write-Host "=== Installing Ollama silently ==="
$proc = Start-Process -FilePath $dest -ArgumentList "/silent", "/VERYSILENT", "/SUPPRESSMSGBBOXES", "/NORESTART" -PassThru -Wait
Write-Host "Ollama installation completed. Exit code: $($proc.ExitCode)"

# Cleanup installer
Remove-Item $dest -Force

# Locate ollama executable
$paths = @(
    "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
    "$env:LOCALAPPDATA\Ollama\ollama.exe",
    "C:\Program Files\Ollama\ollama.exe",
    "C:\Program Files (x86)\Ollama\ollama.exe"
)

$ollamaPath = $null
foreach ($p in $paths) {
    if (Test-Path $p) {
        $ollamaPath = $p
        break
    }
}

if ($null -eq $ollamaPath) {
    Write-Host "ERROR: ollama.exe not found in standard paths."
    Get-ChildItem -Path "$env:LOCALAPPDATA" -Directory -Filter "*Ollama*"
    exit 1
}

Write-Host "Found Ollama executable at: $ollamaPath"

Write-Host "=== Starting Ollama server in background ==="
# Start-Process with serve argument and hide window
$serverProc = Start-Process -FilePath $ollamaPath -ArgumentList "serve" -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 5

# Check if responding
$retries = 15
$started = $false
for ($i = 1; $i -le $retries; $i++) {
    try {
        $res = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -Method Get -ErrorAction Stop
        Write-Host "Ollama server is active!"
        $started = $true
        break
    } catch {
        Write-Host "Waiting for Ollama server... ($i/$retries)"
        Start-Sleep -Seconds 3
    }
}

if (-not $started) {
    Write-Host "ERROR: Ollama server failed to start or respond."
    exit 1
}

Write-Host "=== Pulling qwen3:1.7b ==="
& $ollamaPath pull qwen3:1.7b

Write-Host "=== Pulling llama3.2:1b ==="
& $ollamaPath pull llama3.2:1b

Write-Host "=== Listing pulled models ==="
& $ollamaPath list
