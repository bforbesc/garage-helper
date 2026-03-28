#!/bin/zsh
set -e

PROJECT_DIR="/Users/bernardo/Desktop/CODE/garage-ai"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

if [ ! -f ".venv/.deps_installed" ]; then
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/.deps_installed
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

open "http://127.0.0.1:5050"
exec .venv/bin/python app.py
