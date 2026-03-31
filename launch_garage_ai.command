#!/bin/zsh
set -e

PROJECT_DIR="/Users/bernardo/Desktop/CODE/garage-ai"
PID_FILE="/tmp/garage_ai.pid"
REQ_HASH_FILE=".venv/.requirements.sha1"
cd "$PROJECT_DIR"

is_project_app_pid() {
  local pid="$1"
  local cmd
  local cwd
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  if [[ -z "$cmd" ]]; then
    return 1
  fi
  if [[ "$cmd" != *"app.py"* ]]; then
    return 1
  fi
  cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -n 1)"
  [[ "$cwd" == "$PROJECT_DIR" ]]
}

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

CURRENT_REQ_HASH="$(shasum requirements.txt | awk '{print $1}')"
INSTALLED_REQ_HASH="$(cat "$REQ_HASH_FILE" 2>/dev/null || true)"
if [ ! -f ".venv/.deps_installed" ] || [ "$CURRENT_REQ_HASH" != "$INSTALLED_REQ_HASH" ]; then
  .venv/bin/python -m pip install -r requirements.txt
  touch .venv/.deps_installed
  echo "$CURRENT_REQ_HASH" > "$REQ_HASH_FILE"
fi

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

# Load local env (optional) for launcher behavior overrides.
set -a
source .env >/dev/null 2>&1 || true
set +a
PORT_VALUE="${PORT:-5050}"

# Open GarageBand automatically by default.
AUTO_OPEN_GARAGEBAND_VALUE="${AUTO_OPEN_GARAGEBAND:-true}"
AUTO_OPEN_GARAGEBAND_VALUE="${AUTO_OPEN_GARAGEBAND_VALUE:l}"
if [[ "$AUTO_OPEN_GARAGEBAND_VALUE" == "true" || "$AUTO_OPEN_GARAGEBAND_VALUE" == "1" || "$AUTO_OPEN_GARAGEBAND_VALUE" == "yes" ]]; then
  open -a "GarageBand" >/dev/null 2>&1 || true
fi

# Always restart server so env changes (like API keys) are picked up.
if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && is_project_app_pid "$OLD_PID"; then
    kill "$OLD_PID" >/dev/null 2>&1 || true
  fi
  rm -f "$PID_FILE"
fi

# Also stop any lingering process already bound to our port from this same project.
for PID in $(lsof -tiTCP:"$PORT_VALUE" -sTCP:LISTEN 2>/dev/null || true); do
  if is_project_app_pid "$PID"; then
    kill "$PID" >/dev/null 2>&1 || true
  fi
done

nohup .venv/bin/python app.py >> /tmp/garage_ai.log 2>&1 &
echo $! > "$PID_FILE"
sleep 1

# Opening browser can fail in some contexts; it should not abort startup.
open "http://127.0.0.1:$PORT_VALUE" >/dev/null 2>&1 || true

echo "Garage AI running at http://127.0.0.1:$PORT_VALUE"
