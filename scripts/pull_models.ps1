# pull_models.ps1 — Downloads required Ollama models for BriefAI
# Run this after installing Ollama: https://ollama.com/download
#
# Usage:
#   .\scripts\pull_models.ps1

Write-Host "=== BriefAI: Pulling Ollama Models ===" -ForegroundColor Cyan

$models = @("qwen3:1.7b", "llama3.2:1b", "nomic-embed-text")

foreach ($model in $models) {
    Write-Host "`nPulling $model ..." -ForegroundColor Yellow
    ollama pull $model
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to pull $model. Make sure Ollama is running: ollama serve"
        exit 1
    }
    Write-Host "$model pulled successfully." -ForegroundColor Green
}

Write-Host "`n=== All models ready. ===" -ForegroundColor Cyan
Write-Host "Verify with: ollama list"
