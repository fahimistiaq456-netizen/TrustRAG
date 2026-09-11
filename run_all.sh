#!/usr/bin/env bash
# =============================================================
#  run_all.sh — start the Hallufix backend AND the Next.js webapp
#               together, logging each to logs/.
#
#  Usage:
#    ./run_all.sh               start both in the background (recommended)
#    ./run_all.sh --foreground  backend in foreground, frontend in background
#    ./run_all.sh --background  start both in background, return to shell
#    ./run_all.sh --status      show what is currently running
#    ./run_all.sh --stop        stop background servers started here
#    ./run_all.sh --help
#
#  Env overrides: HALLUFIX_HOST, HALLUFIX_PORT, HALLUFIX_WEB_PORT
# =============================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
BACK_PID_FILE="$LOG_DIR/.backend.pid"
FRONT_PID_FILE="$LOG_DIR/.frontend.pid"

BACK_HOST="${HALLUFIX_HOST:-127.0.0.1}"
BACK_PORT="${HALLUFIX_PORT:-8000}"
WEB_PORT="${HALLUFIX_WEB_PORT:-3000}"
BACK_URL="http://${BACK_HOST}:${BACK_PORT}/health"
WEB_URL="http://127.0.0.1:${WEB_PORT}"

usage() {
  sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
}

# Kill whatever listens on the given port (handles stale PID files / reloaders).
kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti "tcp:${port}" | xargs kill 2>/dev/null || true
  fi
}

is_backend_up() { curl -sf "$BACK_URL" -o /dev/null 2>/dev/null; }
is_frontend_up() { curl -sf "$WEB_URL" -o /dev/null 2>/dev/null; }

stop_servers() {
  [ -f "$BACK_PID_FILE" ] && kill "$(cat "$BACK_PID_FILE")" 2>/dev/null && rm -f "$BACK_PID_FILE"
  [ -f "$FRONT_PID_FILE" ] && kill "$(cat "$FRONT_PID_FILE")" 2>/dev/null && rm -f "$FRONT_PID_FILE"
  kill_port "$BACK_PORT"
  kill_port "$WEB_PORT"
  sleep 1
  echo "Stopped background servers (backend :$BACK_PORT, frontend :$WEB_PORT)."
}

show_status() {
  echo "backend  :$BACK_PORT -> $(is_backend_up && echo 'UP' || echo 'down')"
  echo "frontend :$WEB_PORT -> $(is_frontend_up && echo 'UP' || echo 'down')"
}

MODE="background"
while [ $# -gt 0 ]; do
  case "$1" in
    --background) MODE="background"; shift ;;
    --foreground) MODE="foreground"; shift ;;
    --stop) stop_servers; exit 0 ;;
    --status) show_status; exit 0 ;;
    --help) usage ;;
    *) printf 'Unknown option: %s (see --help)\n' "$1" >&2; exit 1 ;;
  esac
done

if is_backend_up; then
  echo "Backend already running on :$BACK_PORT (health OK)."
else
  (nohup ./run_backend.sh > "$LOG_DIR/api.log" 2>&1 & echo $! > "$BACK_PID_FILE")
  # Wait (up to ~30s) for the API to become healthy.
  for _ in $(seq 1 30); do
    is_backend_up && break
    sleep 1
  done
  if is_backend_up; then
    echo "Backend  -> http://${BACK_HOST}:${BACK_PORT}  (log: logs/api.log, pid: $(cat "$BACK_PID_FILE"))"
  else
    echo "Backend failed to start; see logs/api.log for details." >&2
    tail -20 "$LOG_DIR/api.log" >&2 || true
    exit 1
  fi
fi

if is_frontend_up; then
  echo "Frontend already running on :$WEB_PORT."
else
  (nohup ./run_frontend.sh --port "$WEB_PORT" > "$LOG_DIR/webapp.log" 2>&1 & echo $! > "$FRONT_PID_FILE")
  for _ in $(seq 1 30); do
    is_frontend_up && break
    sleep 1
  done
  if is_frontend_up; then
    echo "Frontend -> $WEB_URL  (log: logs/webapp.log, pid: $(cat "$FRONT_PID_FILE"))"
  else
    echo "Frontend failed to start; see logs/webapp.log for details." >&2
    tail -20 "$LOG_DIR/webapp.log" >&2 || true
  fi
fi

echo "Open http://localhost:${WEB_PORT}  |  Stop with: ./run_all.sh --stop"