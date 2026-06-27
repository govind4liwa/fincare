# ============================================================
# FinCare — Windows Bootstrap
# Run from repo root: .\scripts\bootstrap.ps1
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==> FinCare bootstrap (Windows)" -ForegroundColor Cyan
Write-Host ""

# --- 1. Check prerequisites ---
function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

$missing = @()
foreach ($cmd in @("git", "python", "docker")) {
    if (-not (Test-Command $cmd)) { $missing += $cmd }
}
if ($missing.Count -gt 0) {
    Write-Host "ERROR: Missing prerequisites: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Install them and re-run." -ForegroundColor Red
    exit 1
}

$pyVersion = (python --version) -replace "Python ", ""
Write-Host "Python: $pyVersion" -ForegroundColor Green
Write-Host "Git:    $(git --version)" -ForegroundColor Green
Write-Host "Docker: $(docker --version)" -ForegroundColor Green
Write-Host ""

# --- 2. Rename pre-commit config if needed (session limitation workaround) ---
if ((Test-Path "pre-commit-config.yaml") -and (-not (Test-Path ".pre-commit-config.yaml"))) {
    Write-Host "==> Renaming pre-commit-config.yaml -> .pre-commit-config.yaml" -ForegroundColor Cyan
    Rename-Item -Path "pre-commit-config.yaml" -NewName ".pre-commit-config.yaml"
}

# --- 3. Create .env from .env.example ---
if (-not (Test-Path ".env")) {
    Write-Host "==> Creating .env from .env.example" -ForegroundColor Cyan
    Copy-Item ".env.example" ".env"
    Write-Host "    Edit .env with your local values (especially DJANGO_SECRET_KEY)" -ForegroundColor Yellow
} else {
    Write-Host "==> .env already exists — skipping" -ForegroundColor Yellow
}

# --- 4. Create Python venv ---
if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating Python virtual environment (.venv)" -ForegroundColor Cyan
    python -m venv .venv
}

# --- 5. Activate venv & install dev deps ---
Write-Host "==> Installing dev dependencies into .venv" -ForegroundColor Cyan
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements\dev.txt

# --- 6. Install pre-commit hooks ---
Write-Host "==> Installing pre-commit hooks" -ForegroundColor Cyan
pre-commit install
pre-commit install --hook-type commit-msg

# --- 7. Done ---
Write-Host ""
Write-Host "==> Bootstrap complete." -ForegroundColor Green
Write-Host ""
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  1. Edit .env with your local values (especially DJANGO_SECRET_KEY)"
Write-Host "  2. docker compose up -d"
Write-Host "  3. docker compose logs -f web"
Write-Host ""
