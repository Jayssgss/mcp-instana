#!/usr/bin/env bash
# Start a private MCP server (no fallback credentials), run ONE Bob Shell task through
# bob_agent.run_agent(), stop the server. Same shape the GitHub job will use.
#
#   BOB_API_KEY, INSTANA_API_TOKEN, INSTANA_BASE_URL   from the environment (never printed)
#   BOB_TEST_PROMPT      prompt for Bob (default: the constant change-timeline demo query below)
#   BOB_TEST_PORT        server port (default 8083; must be free)
#   BOB_READY_TIMEOUT    seconds to wait for the server (default 60)
#   BOB_RUN_TIMEOUT      hard limit for the Bob run in seconds (default 280)
#   BOB_ISOLATE_HOME     set to 1 on a laptop so Bob ignores ~/.bob MCP servers (default 0)
#
# Exit code: bob_agent.py's (0 ok, 1 failure, 2 invalid input), or 3 if the server never became ready.
set -u

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PORT="${BOB_TEST_PORT:-8083}"
READY_TIMEOUT="${BOB_READY_TIMEOUT:-60}"
RUN_TIMEOUT="${BOB_RUN_TIMEOUT:-280}"
# Constant demo query (demous tenant): fixed absolute window around the two k8s-demo releases
# (2026-11-09 10:09 and 12:09 UTC), so the expected answer does not drift with time.
# Expected: 2 releases, 0 change events, 0 incidents. Single quotes keep the JSON braces literal.
DEFAULT_PROMPT='Use the change-timeline skill. Application: "Instana sample k8s demo". Use exactly this absolute window: from 2026-11-09 06:00 UTC to 2026-11-10 12:00 UTC (epoch ms 1794204000000 to 1794312000000). Do not use a relative window and do not shift it. After the timeline, end your reply with exactly one line of JSON and nothing after it: {"releases": N, "change_events": N, "incidents": N, "k8s_events": N}, where N are the counts kept in the timeline.'
PROMPT="${BOB_TEST_PROMPT:-$DEFAULT_PROMPT}"
LOG="$(mktemp -t bob-test-server.XXXXXX)"
SERVER_PID=""

cleanup() {
  if [ -n "$SERVER_PID" ]; then
    pkill -P "$SERVER_PID" 2>/dev/null
    kill "$SERVER_PID" 2>/dev/null
    wait "$SERVER_PID" 2>/dev/null
  fi
  rm -f "$LOG"
}
trap cleanup EXIT INT TERM

for v in BOB_API_KEY INSTANA_API_TOKEN INSTANA_BASE_URL; do
  if [ -z "${!v:-}" ]; then
    echo "invalid_input: $v is not set" >&2
    exit 2
  fi
done
command -v bob >/dev/null 2>&1 || { echo "invalid_input: bob is not installed or not on PATH" >&2; exit 2; }
echo "bob version: $(bob --version 2>&1 | head -1)"

if lsof -iTCP:"$PORT" -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "invalid_input: port $PORT is already in use; set BOB_TEST_PORT to a free port" >&2
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

# Default: no --isolate-home (clean-runner case, no ~/.bob). On a laptop with a global Bob MCP
# server set BOB_ISOLATE_HOME=1 so only our server is used.
ISO=""
[ "${BOB_ISOLATE_HOME:-0}" = "1" ] && ISO="--isolate-home"
( cd "$REPO" && MCP_SERVER_URL="http://127.0.0.1:$PORT/mcp" PYTHONWARNINGS=ignore \
  uv run python .github/actions/observe-deployment/bob_agent.py $ISO --timeout "$RUN_TIMEOUT" --max-turns 25 --max-cost 1.5 --prompt "$PROMPT" )
RC=$?

echo "Server calls seen by the MCP server log:"
grep -iE "manage_|tools/call" "$LOG" | sed -E 's/[A-Za-z0-9_-]{40,}/***/g' | tail -5
echo "Timing: server startup $((READY_AT - START))s, bob run $(( $(date +%s) - READY_AT ))s."
exit "$RC"
