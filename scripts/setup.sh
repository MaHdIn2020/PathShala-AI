#!/usr/bin/env bash
# First-time setup. Usage: bash scripts/setup.sh [--legacy]  (--legacy also copies .agents -> .agent)
cd "$(dirname "$0")/.." || exit 2
python3 -m venv .venv && . .venv/bin/activate
pip install -q -U pip && pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
if command -v docker >/dev/null 2>&1; then docker compose up -d db; else echo "docker not found: set DATABASE_URL to a Postgres with pgvector (e.g. Supabase) and run db/schema.sql"; fi
if [ "${1:-}" = "--legacy" ]; then rm -rf .agent && cp -r .agents .agent && echo "copied .agents -> .agent"; fi
[ -d .git ] || git init -q -b main
git config core.hooksPath .githooks
echo "setup done. Edit .env (GEMINI_API_KEY), then: make verify"
