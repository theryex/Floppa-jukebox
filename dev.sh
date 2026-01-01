#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_VENV="$ROOT/api/.venv"
ENGINE_VENV="$ROOT/engine/.venv"
WEB_DIR="$ROOT/web"
VITE_HOST_FLAG=""

for arg in "$@"; do
  if [[ "$arg" == "--host" ]]; then
    VITE_HOST_FLAG="VITE_LAN=1"
  fi
done

if [[ "${1:-}" == "--clean" ]]; then
  echo "Cleaning local storage..."
  running_pids=()
  while IFS= read -r pid; do
    running_pids+=("$pid")
  done < <(pgrep -f "$ROOT/api/worker/worker.py" || true)
  while IFS= read -r pid; do
    running_pids+=("$pid")
  done < <(pgrep -f "uvicorn api.main:app" || true)
  if [[ "${#running_pids[@]}" -gt 0 ]]; then
    echo "Stopping running dev processes..."
    pkill -f "$ROOT/api/worker/worker.py" || true
    pkill -f "uvicorn api.main:app" || true
    for _ in {1..10}; do
      if pgrep -f "$ROOT/api/worker/worker.py" >/dev/null 2>&1; then
        sleep 0.2
        continue
      fi
      if pgrep -f "uvicorn api.main:app" >/dev/null 2>&1; then
        sleep 0.2
        continue
      fi
      break
    done
    if pgrep -f "$ROOT/api/worker/worker.py" >/dev/null 2>&1; then
      pkill -9 -f "$ROOT/api/worker/worker.py" || true
    fi
    if pgrep -f "uvicorn api.main:app" >/dev/null 2>&1; then
      pkill -9 -f "uvicorn api.main:app" || true
    fi
  fi
  rm -rf "$ROOT/api/storage/audio" "$ROOT/api/storage/analysis" "$ROOT/api/storage/logs" "$ROOT/api/storage/jobs.db"
  mkdir -p "$ROOT/api/storage/audio" "$ROOT/api/storage/analysis" "$ROOT/api/storage/logs"
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<PY
from pathlib import Path
import sys

root = Path("${ROOT}")
sys.path.insert(0, str(root / "api"))
from api.db import init_db

init_db(root / "api" / "storage" / "jobs.db")
PY
    echo "Recreated job schema."
  else
    echo "Warning: python3 not found; jobs.db schema not recreated."
  fi
  echo "Done."
  exit 0
fi

ensure_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd"
    exit 1
  fi
}

ensure_venv() {
  local venv_path="$1"
  if [[ ! -d "$venv_path" ]]; then
    python3 -m venv "$venv_path"
    return
  fi
  if [[ ! -x "$venv_path/bin/python" ]] || ! "$venv_path/bin/python" -c "import sys" >/dev/null 2>&1; then
    echo "Recreating venv at $venv_path (stale or moved)."
    rm -rf "$venv_path"
    python3 -m venv "$venv_path"
  fi
}

ensure_api_env() {
  ensure_venv "$API_VENV"
  if ! "$API_VENV/bin/python" -c "import fastapi, yt_dlp, httpx, dotenv" >/dev/null 2>&1; then
    "$API_VENV/bin/python" -m pip install -r "$ROOT/api/requirements.txt"
  fi
  if [[ "${FJ_UPDATE_YTDLP:-}" == "1" ]]; then
    "$API_VENV/bin/python" -m pip install --upgrade yt-dlp
  fi
}

ensure_engine_env() {
  ensure_venv "$ENGINE_VENV"
  if ! "$ENGINE_VENV/bin/python" -c "import pkg_resources" >/dev/null 2>&1; then
    "$ENGINE_VENV/bin/python" -m pip install setuptools
  fi
  if ! "$ENGINE_VENV/bin/python" -c "import madmom, mutagen" >/dev/null 2>&1; then
    "$ENGINE_VENV/bin/python" -m pip install -r "$ROOT/engine/requirements.txt"
  fi
}

ensure_web_deps() {
  if [[ ! -d "$WEB_DIR/node_modules" ]]; then
    (cd "$WEB_DIR" && npm install)
  fi
}

export GENERATOR_REPO="$ROOT/engine"
export GENERATOR_CONFIG="$ROOT/engine/tuned_config.json"

pids=()

run_prefixed() {
  local name="$1"
  shift
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -oL -eL "$@" 2>&1 | sed -e "s/^/[$name] /"
  else
    "$@" 2>&1 | sed -e "s/^/[$name] /"
  fi
}

start_api() {
  (
    cd "$ROOT/api"
    run_prefixed "api" "$API_VENV/bin/python" -m uvicorn api.main:app --host 0.0.0.0 --port 8000
  ) &
  pids+=("$!")
}

start_worker() {
  (
    cd "$ROOT/api"
    export PYTHONPATH="$ROOT/api"
    run_prefixed "worker" "$ENGINE_VENV/bin/python" worker/worker.py
  ) &
  pids+=("$!")
}

start_web() {
  (
    cd "$ROOT/web"
    if [[ -n "$VITE_HOST_FLAG" ]]; then
      VITE_LAN=1 run_prefixed "web" npm run dev -- --host
    else
      run_prefixed "web" npm run dev
    fi
  ) &
  pids+=("$!")
}

cleanup() {
  echo "Shutting down..."
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  pkill -f "$ROOT/api/worker/worker.py" 2>/dev/null || true
  pkill -f "uvicorn api.main:app" 2>/dev/null || true
  wait
}

trap cleanup INT TERM EXIT

ensure_command python3
ensure_command npm
ensure_api_env
ensure_engine_env
ensure_web_deps

start_api
start_worker
start_web

echo "API: http://localhost:8000"
echo "Web: http://localhost:5173"
wait
