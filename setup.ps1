# Loqi Plugin Setup (Windows PowerShell)
# Creates a virtualenv and installs Loqi + dependencies.
# Run once after cloning the plugin.

$ErrorActionPreference = "Stop"
$VenvDir = "$env:USERPROFILE\.loqi-env"

Write-Host "=== Loqi Plugin Setup ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create virtualenv
if (Test-Path $VenvDir) {
    Write-Host "Virtualenv already exists at $VenvDir"
} else {
    Write-Host "Creating virtualenv at $VenvDir..."
    python -m venv $VenvDir
}

$Pip = "$VenvDir\Scripts\pip.exe"
$Python = "$VenvDir\Scripts\python.exe"

if (-not (Test-Path $Pip)) {
    Write-Host "ERROR: Could not find pip at $Pip" -ForegroundColor Red
    exit 1
}

# Step 2: Install Loqi
Write-Host "Installing loqi-memory from PyPI..."
& $Pip install loqi-memory --quiet

# Step 3: Pre-download embedding model
Write-Host "Downloading embedding model (one-time, ~90MB)..."
& $Python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('all-MiniLM-L6-v2'); print(f'Model ready: {m.get_sentence_embedding_dimension()}d')"

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "To use the plugin, start Claude Code with:"
Write-Host "  claude --plugin-dir `"$PSScriptRoot`"" -ForegroundColor Yellow
Write-Host ""
