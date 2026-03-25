#!/bin/bash
# OnePay — Start Script
# Run from the onepay/ directory: ./start.sh

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${CYAN}"
echo "  ██████╗ ███╗   ██╗███████╗██████╗  █████╗ ██╗   ██╗"
echo "  ██╔═══██╗████╗  ██║██╔════╝██╔══██╗██╔══██╗╚██╗ ██╔╝"
echo "  ██║   ██║██╔██╗ ██║█████╗  ██████╔╝███████║ ╚████╔╝ "
echo "  ██║   ██║██║╚██╗██║██╔══╝  ██╔═══╝ ██╔══██║  ╚██╔╝  "
echo "  ╚██████╔╝██║ ╚████║███████╗██║     ██║  ██║   ██║   "
echo "   ╚═════╝ ╚═╝  ╚═══╝╚══════╝╚═╝     ╚═╝  ╚═╝   ╚═╝   "
echo -e "${NC}"

cd "$ROOT"

# ── Virtual environment ────────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
  echo -e "${CYAN}Creating Python virtual environment…${NC}"
  python3 -m venv venv
fi

echo -e "${CYAN}Activating virtual environment…${NC}"
source venv/bin/activate

# ── Dependencies ────────────────────────────────────────────────────────────────
echo -e "${CYAN}Installing dependencies…${NC}"
pip install -q -r requirements.txt

# ── .env file ──────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo -e "${YELLOW}No .env file found — copying from .env.example${NC}"
  cp .env.example .env
  echo -e "${YELLOW}⚠  Edit .env and add your credentials before using in production${NC}"
fi

# ── Launch ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "  ${GREEN}Starting OnePay…${NC}"
echo -e "  ${CYAN}Dashboard →${NC}  http://localhost:5000"
echo -e "  ${CYAN}Health    →${NC}  http://localhost:5000/health"
echo ""

# Use gunicorn in production, flask dev server only when DEBUG=true
DEBUG_VAL=$(grep -E '^DEBUG=' .env 2>/dev/null | cut -d= -f2 | tr '[:upper:]' '[:lower:]' || echo "false")

if [ "$DEBUG_VAL" = "true" ]; then
  echo -e "  ${YELLOW}Running in DEBUG mode (Flask dev server)${NC}"
  echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop."
  echo ""
  python app.py
else
  echo -e "  ${GREEN}Running with gunicorn (4 workers)${NC}"
  echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop."
  echo ""
  gunicorn app:app \
    --bind 0.0.0.0:5000 \
    --workers 4 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -
fi
