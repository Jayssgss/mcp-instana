#!/usr/bin/env bash
# Local smoke run: start a private MCP server, wait until it answers, run smoke.py, stop the server.
#
# Same shape the GitHub job will use. The server is started with EMPTY Instana
# credentials so it has no fallback: only the headers sent by the client can
# authenticate. Client credentials come from the environment, or (PoC only) from
# the repo's .env. Only the two Instana variables are read from .env, and are
# never printed.
#
#   INSTANA_API_TOKEN, INSTANA_BASE_URL   client credentials (env wins over .env)
#   SMOKE_PORT                            server port (default 8082; must be free)
#   SMOKE_READY_TIMEOUT                   seconds to wait for the server (default 60)
#
# Exit code: smoke.py's (0 pass, 1 fail, 2 invalid input), or 3 if the server never became ready.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PORT="${SMOKE_PORT:-8082}"
READY_TIMEOUT="${SMOKE_READY_TIMEOUT:-60}"
LOG="$(mktemp -t mcp-smoke-server.XXXXXX)"
SERVER_PID=""

env_from_dotenv() {  # name -> value from .env (last assignment, quotes stripped)
  [ -f "$REPO/.env" ] || return 0
  grep -E "^$1=" "$REPO/.env" | tail -1 | cut -d= -f2- | sed -e "s/^[\"']//" -e "s/[\"']\$//"
}

cleanup() {
  if [ -n "$SERVER_PID" ]; then
    pkill -P "$SERVER_PID" 2>/dev/null
    kill "$SERVER_PID" 2>/dev/null
    wait "$SERVER_PID" 2>/dev/null
  fi
  rm -f "$LOG"
}
trap cleanup EXIT INT TERM

TOKEN="${INSTANA_API_TOKEN:-$(env_from_dotenv INSTANA_API_TOKEN)}"
BASE_URL="${INSTANA_BASE_URL:-$(env_from_dotenv INSTANA_BASE_URL)}"
if [ -z "$TOKEN" ] || [ -z "$BASE_URL" ]; then
  echo "invalid_input: set INSTANA_API_TOKEN and INSTANA_BASE_URL (env or .env)" >&2
  exit 2
fi

if lsof -iTCP:"$PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "invalid_input: port $PORT is already in use; set SMOKE_PORT to a free port" >&2
  exit 2
fi

START=$(date +%s)
echo "Starting MCP server on 127.0.0.1:$PORT (no fallback credentials)..."
( cd "$REPO" && INSTANA_API_TOKEN="" INSTANA_BASE_URL="" \
  exec uv run src/core/server.py --transport streamable-http --host 127.0.0.1 --port "$PORT" ) >"$LOG" 2>&1 &
SERVER_PID=$!

ready=0
for _ in $(seq 1 "$READY_TIMEOUT"); do
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "server exited early; last log lines:" >&2; tail -15 "$LOG" >&2; exit 3
  fi
  code=$(curl -s -m 2 -o /dev/null -w "%{http_code}" -X POST "http://127.0.0.1:$PORT/mcp" \
    -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
  [ "$code" = "200" ] && { ready=1; break; }
  sleep 1
done
if [ "$ready" != "1" ]; then
  echo "server not ready after ${READY_TIMEOUT}s; last log lines:" >&2; tail -15 "$LOG" >&2; exit 3
fi
READY_AT=$(date +%s)
echo "Server ready after $((READY_AT - START))s."

( cd "$REPO" && MCP_SERVER_URL="http://127.0.0.1:$PORT/mcp" INSTANA_API_TOKEN="$TOKEN" INSTANA_BASE_URL="$BASE_URL" \
  PYTHONWARNINGS=ignore uv run python .github/actions/observe-deployment/smoke.py )
RC=$?

echo "Timing: startup $((READY_AT - START))s, smoke $(( $(date +%s) - READY_AT ))s, total $(( $(date +%s) - START ))s."
exit "$RC"
