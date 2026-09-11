#!/usr/bin/env bash
# =============================================================
#  run_backend.sh — start the Hallufix backend (FastAPI + Ollama + index)
#
#  Usage:
#    ./run_backend.sh                 start the API on :8000
#    ./run_backend.sh --port 9000     custom bind port
#    ./run_backend.sh --install       (re)install Python dependencies
#    ./run_backend.sh --rebuild-index rebuild the FAISS index from data/
#    ./run_backend.sh --no-ollama     skip the Ollama check/start
#    ./run_backend.sh --host 0.0.0.0  bind to all interfaces
#    ./run_backend.sh --help          show this help
#
#  Env overrides: HALLUFIX_HOST, HALLUFIX_PORT
# =============================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV_DIR="$ROOT/.venv"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
REQ="$ROOT/requirements.txt"
ENV_EXAMPLE="$ROOT/.env.example"
ENV_FILE="$ROOT/.env"
INDEX_DIR="$ROOT/data/index"
OLLAMA_URL="http://127.0.0.1:11434/api/tags"

HOST="${HALLUFIX_HOST:-127.0.0.1}"
PORT="${HALLUFIX_PORT:-8000}"

DO_INSTALL=0
DO_REBUILD=0
SKIP_OLLAMA=0

step() { printf "\033[1;34m▶\033[0m %s\n" "$1"; }
warn() { printf "\033[1;33m!\033[0m %s\n" "$1"; }
ok()   { printf "\033[1;32m✓\033[0m %s\n" "$1"; }
die()  { printf "\033[1;31m✗\033[0m %s\n" "$1" >&2; exit 1; }

usage() {
  sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --install)      DO_INSTALL=1; shift ;;
    --rebuild-index) DO_REBUILD=1; shift ;;
    --no-ollama)    SKIP_OLLAMA=1; shift ;;
    --port)         PORT="${2:?--port needs a value}"; shift 2 ;;
    --host)         HOST="$2"; shift 2 ;;
    --help)         usage ;;
    *) die "Unknown option: $1 (see --help)" ;;
  esac
done

# -------------------------------------------------------------
# 1. Python + venv
# -------------------------------------------------------------
if [ ! -x "$PY" ]; then
  warn "Virtualenv not found; creating it with python3.11..."
  (command -v python3.11 || command -v python3) >/dev/null 2>&1 \
    && python3.11 -m venv "$VENV_DIR" 2>/dev/null \
    || python3 -m venv "$VENV_DIR"
fi
[ -x "$PY" ] || die "Python venv is missing! Please create it manually: python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt"
ok "Python: $("$PY" --version 2>&1)"

# -------------------------------------------------------------
# 2. Configure (.env) + dependencies
# -------------------------------------------------------------
if [ ! -f "$ENV_FILE" ] && [ -f "$ENV_EXAMPLE" ]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  ok "Created $ENV_FILE from $ENV_EXAMPLE"
fi

if [ "$DO_INSTALL" = "1" ]; then
  step "Installing Python dependencies..."
  "$PIP" install -r "$REQ" || die "pip install failed"
else
  # Cheap availability probe: import fastapi via the venv.
  if ! "$PY" -c "import fastapi, faiss" >/dev/null 2>&1; then
    step "Installing Python dependencies (first run)..."
    "$PIP" install -r "$REQ" || die "pip install failed"
  fi
fi
ok "Dependencies available"

# -------------------------------------------------------------
# 3. Ollama (backend LLM) — optional, non-fatal
# -------------------------------------------------------------
start_ollama() {
  command -v ollama >/dev/null 2>&1 || { warn "Ollama CLI not found — install it (brew install ollama) and run 'ollama serve'."; return 1; }
  (nohup ollama serve >/dev/null 2>&1 &)
  sleep 2
}

if [ "$SKIP_OLLAMA" = "1" ]; then
  warn "Skipping Ollama check (--no-ollama). The API will report Ollama offline."
else
  if curl -sf "$OLLAMA_URL" -o /dev/null 2>/dev/null; then
    ok "Ollama already running"
  else
    step "Ollama not running — attempting to start it..."
    start_ollama
    sleep 1
    if curl -sf "$OLLAMA_URL" -o /dev/null 2>/dev/null; then
      ok "Ollama started"
    else
      warn "Ollama not reachable yet. Start it manually if needed ('ollama serve')."
    fi
  fi
fi

# -------------------------------------------------------------
# 4. Build the index if it's missing / explicitly requested
# -------------------------------------------------------------
needs_index() {
  [ -f "$INDEX_DIR/handbook.faiss" ] && [ -f "$INDEX_DIR/metadata.json" ] || return 1
}
if [ "$DO_REBUILD" = "1" ] || ! needs_index; then
  step "Building the FAISS index from data/ ..."
  "$PY" -m backend.build_index data || die "Index build failed"
  ok "Index ready in $INDEX_DIR"
else
  ok "Index already present in $INDEX_DIR"
fi

# -------------------------------------------------------------
# 5. Start the FastAPI server
# -------------------------------------------------------------
step "Starting HalluFix backend on $HOST:$PORT"
exec "$PY" -m uvicorn backend.api:app --host "$HOST" --port "$PORT" --reload