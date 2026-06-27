#!/usr/bin/env bash
# ============================================================
# FinCare — macOS / Linux Bootstrap
# Run from repo root: ./scripts/bootstrap.sh
# ============================================================
set -euo pipefail

GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${CYAN}==> FinCare bootstrap (Unix)${NC}"
echo ""

# --- 1. Prerequisites ---
missing=()
for cmd in git python3 docker; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        missing+=("$cmd")
    fi
done
if [ "${#missing[@]}" -gt 0 ]; then
    echo -e "${RED}ERROR: Missing prerequisites: ${missing[*]}${NC}"
    exit 1
fi

echo -e "${GREEN}Python: $(python3 --version)${NC}"
echo -e "${GREEN}Git:    $(git --version)${NC}"
echo -e "${GREEN}Docker: $(docker --version)${NC}"
echo ""

# --- 2. Rename pre-commit config if needed ---
if [ -f "pre-commit-config.yaml" ] && [ ! -f ".pre-commit-config.yaml" ]; then
    echo -e "${CYAN}==> Renaming pre-commit-config.yaml -> .pre-commit-config.yaml${NC}"
    mv pre-commit-config.yaml .pre-commit-config.yaml
fi

# --- 3. .env ---
if [ ! -f ".env" ]; then
    echo -e "${CYAN}==> Creating .env from .env.example${NC}"
    cp .env.example .env
    echo -e "${YELLOW}    Edit .env with your local values (especially DJANGO_SECRET_KEY)${NC}"
else
    echo -e "${YELLOW}==> .env already exists — skipping${NC}"
fi

# --- 4. venv ---
if [ ! -d ".venv" ]; then
    echo -e "${CYAN}==> Creating Python virtual environment (.venv)${NC}"
    python3 -m venv .venv
fi

# --- 5. Install dev deps ---
echo -e "${CYAN}==> Installing dev dependencies into .venv${NC}"
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements/dev.txt

# --- 6. Pre-commit ---
echo -e "${CYAN}==> Installing pre-commit hooks${NC}"
pre-commit install
pre-commit install --hook-type commit-msg

# --- 7. Done ---
echo ""
echo -e "${GREEN}==> Bootstrap complete.${NC}"
echo ""
echo -e "${CYAN}Next:${NC}"
echo "  1. Edit .env with your local values (especially DJANGO_SECRET_KEY)"
echo "  2. docker compose up -d"
echo "  3. docker compose logs -f web"
echo ""
