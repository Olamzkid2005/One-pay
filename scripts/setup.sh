#!/usr/bin/env bash
# scripts/setup.sh — OnePay local development setup
#
# Usage:
#   chmod +x scripts/setup.sh   # run once to make executable
#   ./scripts/setup.sh
#
# This script is idempotent — safe to run multiple times.

set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✔${RESET}  $*"; }
info() { echo -e "${BLUE}▶${RESET}  $*"; }
warn() { echo -e "${YELLOW}⚠${RESET}  $*"; }
fail() { echo -e "${RED}✘${RESET}  $*" >&2; exit 1; }
header() { echo -e "\n${BOLD}${BLUE}── $* ──${RESET}"; }

# ── Resolve project root (directory containing this script's parent) ──────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo -e "${BOLD}${GREEN}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   OnePay — Development Setup          ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${RESET}"

# ── 1. Python version check ───────────────────────────────────────────────────
header "Python"

if ! command -v python3 &>/dev/null; then
    fail "python3 not found. Install Python 3.9+ and try again."
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [[ "${PYTHON_MAJOR}" -lt 3 ]] || { [[ "${PYTHON_MAJOR}" -eq 3 ]] && [[ "${PYTHON_MINOR}" -lt 9 ]]; }; then
    fail "Python 3.9+ required (found ${PYTHON_VERSION}). Please upgrade."
fi

ok "Python ${PYTHON_VERSION}"

# ── 2. Virtual environment ────────────────────────────────────────────────────
header "Virtual Environment"

if [[ ! -d ".venv" ]]; then
    info "Creating .venv..."
    python3 -m venv .venv
    ok "Created .venv"
else
    ok ".venv already exists — skipping creation"
fi

# Activate
# shellcheck source=/dev/null
source .venv/bin/activate
ok "Activated .venv"

# ── 3. Dependencies ───────────────────────────────────────────────────────────
header "Python Dependencies"

if [[ ! -f "requirements.txt" ]]; then
    fail "requirements.txt not found in ${PROJECT_ROOT}"
fi

info "Installing from requirements.txt..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Dependencies installed"

# ── 4. Environment file ───────────────────────────────────────────────────────
header "Environment Configuration"

if [[ ! -f ".env" ]]; then
    if [[ ! -f ".env.example" ]]; then
        fail ".env.example not found — cannot create .env"
    fi
    info "Copying .env.example → .env..."
    cp .env.example .env
    ok "Created .env — edit it with your local values before running the app"
else
    ok ".env already exists — skipping copy"
fi

# ── 5. PostgreSQL via Docker ──────────────────────────────────────────────────
header "PostgreSQL"

if ! command -v docker &>/dev/null; then
    warn "docker not found — skipping PostgreSQL startup"
    warn "Start PostgreSQL manually and ensure DATABASE_URL in .env is correct"
else
    COMPOSE_CMD=""
    if docker compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        warn "docker compose not available — skipping PostgreSQL startup"
    fi

    if [[ -n "${COMPOSE_CMD}" ]]; then
        info "Starting PostgreSQL (docker compose up db -d)..."
        ${COMPOSE_CMD} up db -d

        info "Waiting for PostgreSQL to be healthy..."
        MAX_WAIT=30
        WAITED=0
        until ${COMPOSE_CMD} exec -T db pg_isready -U onepay_user -q 2>/dev/null; do
            if [[ "${WAITED}" -ge "${MAX_WAIT}" ]]; then
                fail "PostgreSQL did not become healthy within ${MAX_WAIT}s"
            fi
            sleep 2
            WAITED=$((WAITED + 2))
        done
        ok "PostgreSQL is healthy"
    fi
fi

# ── 6. Database migrations ────────────────────────────────────────────────────
header "Database Migrations"

if ! command -v alembic &>/dev/null; then
    warn "alembic not found in PATH — trying via python -m alembic"
    ALEMBIC="python -m alembic"
else
    ALEMBIC="alembic"
fi

info "Running alembic upgrade head..."
if ${ALEMBIC} upgrade head; then
    ok "Migrations applied"
else
    warn "Migrations failed — check DATABASE_URL in .env and ensure PostgreSQL is running"
fi

# ── 7. npm dependencies ───────────────────────────────────────────────────────
header "Node / Tailwind Build Pipeline"

if ! command -v npm &>/dev/null; then
    warn "npm not found — skipping Tailwind build pipeline setup"
    warn "Install Node.js 18+ to enable the CSS build pipeline"
else
    if [[ -f "package.json" ]]; then
        info "Installing npm dependencies..."
        npm install --silent
        ok "npm dependencies installed"

        info "Building CSS (npm run build:css)..."
        if npm run build:css --silent 2>/dev/null; then
            ok "CSS built successfully"
        else
            warn "CSS build failed — run 'npm run build:css' manually after checking package.json"
        fi
    else
        warn "package.json not found — skipping npm setup"
    fi
fi

# ── 8. Pre-commit hooks (optional) ───────────────────────────────────────────
header "Pre-Commit Hooks"

INSTALL_PRECOMMIT=false
if [[ -t 0 ]]; then
    # Interactive terminal — ask the user
    read -r -p "$(echo -e "${BLUE}?${RESET}  Install pre-commit hooks? [y/N] ")" REPLY
    if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
        INSTALL_PRECOMMIT=true
    fi
else
    info "Non-interactive mode — skipping pre-commit hook installation"
    info "Run 'pre-commit install' manually to enable hooks"
fi

if [[ "${INSTALL_PRECOMMIT}" == "true" ]]; then
    if ! command -v pre-commit &>/dev/null; then
        info "Installing pre-commit..."
        pip install --quiet pre-commit
    fi
    if [[ -f ".pre-commit-config.yaml" ]]; then
        pre-commit install
        ok "Pre-commit hooks installed"
    else
        warn ".pre-commit-config.yaml not found — run task 22.1 first to create it"
    fi
fi

# ── 9. Next steps ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}✔  Setup complete!${RESET}"
echo ""
echo -e "${BOLD}Next steps:${RESET}"
echo ""
echo -e "  1. ${YELLOW}Edit .env${RESET} with your local configuration:"
echo "       • Set SECRET_KEY and HMAC_SECRET to different 32+ char random strings"
echo "       • Set INBOUND_WEBHOOK_SECRET to a 32+ char random string"
echo "       • Configure KORAPAY_SECRET_KEY if testing payments"
echo ""
echo -e "  2. ${YELLOW}Activate the virtual environment${RESET} in your shell:"
echo "       source .venv/bin/activate"
echo ""
echo -e "  3. ${YELLOW}Run the development server:${RESET}"
echo "       flask run --debug"
echo "     or:"
echo "       python app.py"
echo ""
echo -e "  4. ${YELLOW}(Optional) Start the Huey task worker:${RESET}"
echo "       huey_consumer app.huey --workers 2"
echo ""
echo -e "  5. ${YELLOW}(Optional) Watch CSS changes during development:${RESET}"
echo "       npm run watch:css"
echo ""
echo -e "  Tip: Generate secrets with:"
echo "       python -c \"import secrets; print(secrets.token_hex(32))\""
echo ""
