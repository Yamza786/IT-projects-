#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
APP_SESSION="fastapi-app"
MONITOR_SESSION="fastapi-monitor"

pkg update -y
pkg install -y git python tmux openssl clang libffi

python -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$REPO_DIR/requirements-termux.txt"

tmux has-session -t "$APP_SESSION" 2>/dev/null && tmux kill-session -t "$APP_SESSION" || true
tmux new-session -d -s "$APP_SESSION" \
  "cd '$REPO_DIR' && source '$VENV_DIR/bin/activate' && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 2>&1 | tee '$REPO_DIR/uvicorn.log'"

tmux has-session -t "$MONITOR_SESSION" 2>/dev/null && tmux kill-session -t "$MONITOR_SESSION" || true
tmux new-session -d -s "$MONITOR_SESSION" \
  "cd '$REPO_DIR' && source '$VENV_DIR/bin/activate' && exec python monitor.py"

echo "App logs:     tmux attach -t $APP_SESSION"
echo "Monitor logs: tmux attach -t $MONITOR_SESSION"
