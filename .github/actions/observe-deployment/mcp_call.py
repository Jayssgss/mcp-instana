"""Call one tool on the Instana MCP server (streamable-http) and classify the outcome.

Thin wrapper over ``fastmcp.Client``. It adds only what the library does not:
  * refuses to run without explicit credentials (the server may otherwise fall
    back to its own ``.env`` and hide a missing-header bug),
  * treats "HTTP 200 + isError false + results.success false" as a failure,
  * maps every failure to a reason code.

CLI (credentials from the environment, never from argv):
  INSTANA_API_TOKEN, INSTANA_BASE_URL, MCP_SERVER_URL (default http://127.0.0.1:8080/mcp)
  python mcp_call.py --list-tools
  python mcp_call.py --tool load_instana_skills --args '{"operation": "list"}'

Prints one JSON object: {"ok": bool, "reason": str|None, "detail": str, "result": any}.
Exit code: 0 when ok, 1 on a tool/operational failure, 2 on invalid input.
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, Optional

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

DEFAULT_URL = "http://127.0.0.1:8080/mcp"

INVALID_INPUT = "invalid_input"
SERVER_UNREACHABLE = "server_unreachable"
TIMEOUT = "timeout"
AUTH_FAILED = "auth_failed"
TOOL_ERROR = "tool_error"
INVALID_RESPONSE = "invalid_response"

# Heuristic only. Real error texts are still to be recorded (plan step 1.4).
_AUTH_HINTS = ("401", "403", "unauthorized", "forbidden", "missing required headers",
               "invalid token", "api token", "credentials")


def _outcome(ok: bool, reason: Optional[str], detail: str = "", result: Any = None) -> Dict[str, Any]:
    return {"ok": ok, "reason": reason, "detail": detail, "result": result}


def classify(structured: Any, is_error: bool) -> Dict[str, Any]:
    """Classify a completed tool call. HTTP and JSON-RPC errors are handled by the caller."""
    results = structured.get("results") if isinstance(structured, dict) else None
    # Observed failure shapes (HTTP 200, isError false):
    #   {"success": false, "error": "..."}  and  {"error": "..."} with no success key.
    failed = is_error or (isinstance(results, dict) and (
        results.get("success") is False
        or ("error" in results and results.get("success") is not True)))
    if not failed:
        return _outcome(True, None, "", structured)
    text = ""
    if isinstance(results, dict):
        text = str(results.get("error", ""))
    text = text or json.dumps(structured, default=str)[:500]
    reason = AUTH_FAILED if any(h in text.lower() for h in _AUTH_HINTS) else TOOL_ERROR
    return _outcome(False, reason, text[:500], structured)


def _is_timeout(exc: BaseException) -> bool:
    """True if exc or anything in its cause/context chain is a timeout.

    fastmcp wraps a handshake timeout (4.x: RuntimeError "Client failed to connect"
    caused by httpx.ReadTimeout; 3.x: McpError "Timed out ..."), so the top-level
    type and message alone are not enough.
    """
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if (isinstance(exc, (TimeoutError, asyncio.TimeoutError))
                or "Timeout" in type(exc).__name__
                or "timed out" in str(exc).lower()):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def _map_exception(exc: BaseException) -> Dict[str, Any]:
    if _is_timeout(exc):
        return _outcome(False, TIMEOUT, "request timed out")
    text = f"{type(exc).__name__}: {exc}"
    if isinstance(exc, (RuntimeError, OSError, ConnectionError)) and (
        "connect" in text.lower() or isinstance(exc, (OSError, ConnectionError))
    ):
        return _outcome(False, SERVER_UNREACHABLE, text[:500])
    return _outcome(False, INVALID_RESPONSE, text[:500])


def _validate(url: str, token: str, base_url: str) -> Optional[Dict[str, Any]]:
    missing = [n for n, v in (("MCP server url", url), ("Instana API token", token),
                              ("Instana base url", base_url)) if not (v or "").strip()]
    if missing:
        return _outcome(False, INVALID_INPUT, "missing: " + ", ".join(missing))
    return None


async def _run(url, token, base_url, timeout, action):
    transport = StreamableHttpTransport(
        url, headers={"instana-api-token": token, "instana-base-url": base_url})
    async with Client(transport, timeout=timeout) as client:
        return await action(client)


async def call_tool(url: str, token: str, base_url: str, name: str,
                    arguments: Optional[Dict[str, Any]] = None, timeout: float = 60.0) -> Dict[str, Any]:
    bad = _validate(url, token, base_url)
    if bad:
        return bad

    async def action(client):
        r = await client.call_tool(name, arguments or {}, raise_on_error=False)
        return classify(r.structured_content, r.is_error)

    try:
        return await asyncio.wait_for(_run(url, token, base_url, timeout, action), timeout + 5)
    except Exception as exc:  # - every failure must become a reason code
        return _map_exception(exc)


async def list_tools(url: str, token: str, base_url: str, timeout: float = 60.0) -> Dict[str, Any]:
    bad = _validate(url, token, base_url)
    if bad:
        return bad

    async def action(client):
        return _outcome(True, None, "", [t.name for t in await client.list_tools()])

    try:
        return await asyncio.wait_for(_run(url, token, base_url, timeout, action), timeout + 5)
    except Exception as exc:
        return _map_exception(exc)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--tool")
    p.add_argument("--args", default="{}", help="JSON object of tool arguments")
    p.add_argument("--list-tools", action="store_true")
    p.add_argument("--timeout", type=float, default=60.0)
    a = p.parse_args(argv)

    url = os.environ.get("MCP_SERVER_URL", DEFAULT_URL)
    token = os.environ.get("INSTANA_API_TOKEN", "")
    base_url = os.environ.get("INSTANA_BASE_URL", "")

    if a.list_tools:
        out = asyncio.run(list_tools(url, token, base_url, a.timeout))
    elif a.tool:
        try:
            arguments = json.loads(a.args)
        except json.JSONDecodeError as exc:
            out = _outcome(False, INVALID_INPUT, f"--args is not valid JSON: {exc}")
        else:
            out = asyncio.run(call_tool(url, token, base_url, a.tool, arguments, a.timeout))
    else:
        out = _outcome(False, INVALID_INPUT, "give --tool or --list-tools")

    print(json.dumps(out, default=str))
    if out["ok"]:
        return 0
    return 2 if out["reason"] == INVALID_INPUT else 1


if __name__ == "__main__":
    sys.exit(main())
