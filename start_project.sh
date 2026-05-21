#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BACKEND_DIR="$SCRIPT_DIR/backend"
BACKEND_BE_DIR="$SCRIPT_DIR/backend_BE"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

resolve_python_cmd() {
  local service_dir="$1"

  local common_candidates=(
    "$SCRIPT_DIR/.venv/Scripts/python.exe"
    "$SCRIPT_DIR/.venv/bin/python"
    "$BACKEND_BE_DIR/myenv/Scripts/python.exe"
    "$BACKEND_BE_DIR/myenv/bin/python"
  )

  local candidates=(
    "$service_dir/.venv/Scripts/python.exe"
    "$service_dir/.venv/bin/python"
    "$service_dir/venv/Scripts/python.exe"
    "$service_dir/venv/bin/python"
    "$service_dir/myenv/Scripts/python.exe"
    "$service_dir/myenv/bin/python"
  )

  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  for candidate in "${common_candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done

  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  if command -v py >/dev/null 2>&1; then
    echo "py -3"
    return 0
  fi

  return 1
}

BACKEND_PYTHON_CMD="$(resolve_python_cmd "$BACKEND_DIR" || true)"
BACKEND_BE_PYTHON_CMD="$(resolve_python_cmd "$BACKEND_BE_DIR" || true)"

if [[ -z "$BACKEND_PYTHON_CMD" ]]; then
  echo "Error: No Python runtime found for backend."
  exit 1
fi
if [[ -z "$BACKEND_BE_PYTHON_CMD" ]]; then
  echo "Error: No Python runtime found for backend_BE."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Error: npm is not installed or not in PATH."
  exit 1
fi

PIDS=()

cleanup() {
  echo
  echo "Stopping services..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait || true
}

trap cleanup EXIT INT TERM

start_service() {
  local name="$1"
  local dir="$2"
  local cmd="$3"

  echo "Starting $name..."
  (
    cd "$dir"
    eval "$cmd"
  ) &
  local pid=$!
  PIDS+=("$pid")
  echo "$name started (PID: $pid)"
}

start_service "Backend API (port 8000)" "$BACKEND_DIR" "$BACKEND_PYTHON_CMD -m uvicorn main:app --host 127.0.0.1 --port 8000"
start_service "Backend BE API (port 8001)" "$BACKEND_BE_DIR" "$BACKEND_BE_PYTHON_CMD -m uvicorn main:app --host 127.0.0.1 --port 8001"
start_service "Frontend (port 3000)" "$FRONTEND_DIR" "npm start"

echo
echo "All services launched:"
echo "- Frontend:      http://127.0.0.1:3000"
echo "- Backend API:   http://127.0.0.1:8000"
echo "- Backend BE:    http://127.0.0.1:8001"
echo
echo "Press Ctrl+C to stop all services."

wait
