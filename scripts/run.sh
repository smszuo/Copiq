#!/usr/bin/env bash
# Runs the API server and clipboard daemon together in one terminal, for
# everyday dev use. Ctrl+C stops both cleanly.
#
# This is NOT the deploy/*.service systemd units (section 31.0) -- those
# are for always-on, survive-a-reboot use. This is for "I'm working on the
# project right now and want both processes up".
set -uo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

PYTHON="$ROOT/.venv/bin/python"
UVICORN="$ROOT/.venv/bin/uvicorn"

if [ ! -x "$PYTHON" ]; then
  echo "error: .venv not found. Run: uv sync --extra dev --no-config" >&2
  exit 1
fi

if [ ! -f "$HOME/.config/copiq/config.json" ]; then
  echo "warning: ~/.config/copiq/config.json not found." >&2
  echo "  The daemon (and copiq) need it. Create a key first:" >&2
  echo "    $PYTHON scripts/create_api_key.py --name dev" >&2
  echo ""
fi

if [ -z "${DISPLAY:-}" ]; then
  echo "warning: \$DISPLAY is not set -- the daemon needs an X11 session" >&2
  echo "  (architecture.md section 6.1) and will likely fail to start." >&2
  echo ""
fi

HOST="${COPIQ_HOST:-127.0.0.1}"
PORT="${COPIQ_PORT:-5080}"

PIDS=()

cleanup() {
  trap - EXIT INT TERM
  echo ""
  echo "stopping..."
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null
  done
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "starting server  -- http://$HOST:$PORT"
"$UVICORN" copiq_server.main:app --host "$HOST" --port "$PORT" --reload &
PIDS+=("$!")

# Give the server a moment to bind the port before the daemon's first
# clipboard change tries to upload to it.
sleep 1

echo "starting daemon  -- watching clipboard (needs X11)"
"$PYTHON" -m copiq_daemon &
PIDS+=("$!")

echo ""
echo "both running. Ctrl+C to stop."
wait
