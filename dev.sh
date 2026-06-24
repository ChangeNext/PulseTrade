#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
PYTHON_BIN="${PYTHON:-python3}"

backend_pid=""
frontend_pid=""

cleanup() {
  trap - EXIT INT TERM
  printf '\n[stop] Stopping PulseTrade servers...\n'
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid" 2>/dev/null || true
  fi
  if [[ -n "$frontend_pid" ]] && kill -0 "$frontend_pid" 2>/dev/null; then
    kill "$frontend_pid" 2>/dev/null || true
  fi
  wait "$backend_pid" "$frontend_pid" 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 0' INT TERM

printf '\n  PulseTrade development launcher\n'
printf '  --------------------------------\n'

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  printf '[setup] Creating backend virtual environment...\n'
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

if ! "$VENV_DIR/bin/python" -c 'import fastapi, sqlalchemy, uvicorn, alembic' 2>/dev/null; then
  printf '[setup] Installing backend dependencies...\n'
  "$VENV_DIR/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"
fi

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  printf '[setup] Created backend/.env from .env.example (SIM mode).\n'
fi

if [[ ! -x "$FRONTEND_DIR/node_modules/.bin/vite" ]]; then
  printf '[setup] Installing frontend dependencies...\n'
  npm --prefix "$FRONTEND_DIR" install
fi

printf '[setup] Applying database migrations...\n'
(
  cd "$BACKEND_DIR"
  "$VENV_DIR/bin/python" -m alembic upgrade head
)

printf '[start] Backend  http://127.0.0.1:8000\n'
(
  cd "$BACKEND_DIR"
  exec "$VENV_DIR/bin/python" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
backend_pid=$!

printf '[start] Frontend http://127.0.0.1:5173\n'
(
  cd "$FRONTEND_DIR"
  exec npm run dev -- --host 127.0.0.1 --port 5173
) &
frontend_pid=$!

printf '\nPress Ctrl+C to stop both servers.\n\n'

set +e
wait -n "$backend_pid" "$frontend_pid"
status=$?
set -e
printf '[error] A development server stopped unexpectedly (exit code %s).\n' "$status" >&2
exit "$status"
