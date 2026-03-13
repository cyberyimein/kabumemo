#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_VENV="$BACKEND_DIR/.venv"
BACKEND_PY="$BACKEND_VENV/bin/python"
BOOTSTRAP_PY="${KABUMEMO_BASE_PY:-}"
SERVER_HOST="${KABUMEMO_HOST:-0.0.0.0}"

if [[ -z "$BOOTSTRAP_PY" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    BOOTSTRAP_PY="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    BOOTSTRAP_PY="$(command -v python)"
  else
    echo "[ERROR] python3 or python is required." >&2
    exit 1
  fi
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[ERROR] npm is required." >&2
  exit 1
fi

echo "============================================="
echo "  Kabumemo macOS/Linux production preview"
echo "============================================="
echo "Project root: $ROOT"
echo "Backend bootstrap Python: $BOOTSTRAP_PY"

cd "$BACKEND_DIR"
if [[ ! -x "$BACKEND_PY" ]]; then
  echo "[Backend] Creating virtual environment..."
  "$BOOTSTRAP_PY" -m venv .venv
fi

if [[ ! -x "$BACKEND_VENV/bin/uvicorn" ]]; then
  echo "[Backend] Installing dependencies..."
  "$BACKEND_PY" -m pip install --upgrade pip setuptools wheel
  "$BACKEND_PY" -m pip install .
fi

cd "$FRONTEND_DIR"
if [[ ! -d node_modules ]]; then
  echo "[Frontend] Installing dependencies..."
  npm install --no-audit --no-fund
fi

echo "[Frontend] Building dist bundle..."
npm run build

export KABUMEMO_DIST_DIR="$FRONTEND_DIR/dist"
echo "[Server] Starting http://127.0.0.1:8000"
cd "$BACKEND_DIR"
exec "$BACKEND_PY" -m uvicorn app.main:app --host "$SERVER_HOST" --port 8000