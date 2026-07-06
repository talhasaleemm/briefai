# setup.ps1 — Full first-time environment setup for BriefAI (Windows / PowerShell)
#
# Usage (from repo root):
#   .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
Write-Host "=== BriefAI Setup ===" -ForegroundColor Cyan

# ── 1. Python virtual environment ────────────────────────────────────────────
Write-Host "`n[1/5] Creating Python 3.12 virtual environment..." -ForegroundColor Yellow
py -V:Astral/CPython3.12.12 -m venv venv
.\venv\Scripts\Activate.ps1

# ── 2. Upgrade pip ───────────────────────────────────────────────────────────
Write-Host "`n[2/5] Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# ── 3. Install backend dependencies ──────────────────────────────────────────
Write-Host "`n[3/5] Installing backend dependencies..." -ForegroundColor Yellow
pip install -r backend\requirements.txt

# ── 4. Copy .env ─────────────────────────────────────────────────────────────
Write-Host "`n[4/5] Setting up environment config..." -ForegroundColor Yellow
if (-not (Test-Path "backend\.env")) {
    Copy-Item "backend\.env.example" "backend\.env"
    Write-Host "  backend\.env created from .env.example — edit it to customize." -ForegroundColor Green
} else {
    Write-Host "  backend\.env already exists, skipping." -ForegroundColor Gray
}

# ── 5. Pull Ollama models ─────────────────────────────────────────────────────
Write-Host "`n[5/5] Pulling Ollama models..." -ForegroundColor Yellow
$ollamaRunning = $false
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:11434" -TimeoutSec 3 -ErrorAction Stop
    $ollamaRunning = $true
} catch {}

if ($ollamaRunning) {
    .\scripts\pull_models.ps1
} else {
    Write-Host "  Ollama not running. Start it with 'ollama serve', then run:" -ForegroundColor DarkYellow
    Write-Host "  .\scripts\pull_models.ps1" -ForegroundColor DarkYellow
}

Write-Host "`n=== Setup complete! ===" -ForegroundColor Cyan
Write-Host "Start the backend: cd backend && uvicorn app.main:app --reload"
