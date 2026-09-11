#!/usr/bin/env bash
# =============================================================
#  run_frontend.sh — start the Hallufix Next.js webapp (dev server)
#
#  Usage:
#    ./run_frontend.sh          start the Next.js dev server (usually :3000)
#    ./run_frontend.sh --port 4000
#    ./run_frontend.sh --build  production build, then serve
#    ./run_frontend.sh --help
#
#  Requires Node.js (>=18) and npm. Installs deps on first run.
# =============================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBAPP="$ROOT/webapp"

PORT="${HALLUFIX_WEB_PORT:-3000}"
MODE="dev"

usage() {
  sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="${2:?--port needs a value}"; shift 2 ;;
    --build) MODE="build"; shift ;;
    --help) usage ;;
    *) printf 'Unknown option: %s (see --help)\n' "$1" >&2; exit 1 ;;
  esac
done

command -v node >/dev/null 2>&1 || { echo "✗ Node.js not found. Install it via https://nodejs.org or 'brew install node'." >&2; exit 1; }
command -v npm  >/dev/null 2>&1 || { echo "✗ npm not found." >&2; exit 1; }

if [ ! -d "$WEBAPP/node_modules" ]; then
  printf '\033[1;34m▶\033[0m Installing frontend dependencies...\n'
  (cd "$WEBAPP" && npm install) || { echo "✗ npm install failed" >&2; exit 1; }
fi

cd "$WEBAPP" || exit 1

case "$MODE" in
  dev)
    printf '\033[1;34m▶\033[0m Starting Next.js dev server on :%s\n' "$PORT"
    exec npm run dev -- --port "$PORT"
    ;;
  *build)
    printf '\033[1;34m▶\033[0m Building for production...\n'
    npm run build || exit 1
    printf '\033[1;34m▶\033[0m Starting production server on :%s\n' "$PORT"
    exec npm run start -- -p "$PORT"
    ;;
esac