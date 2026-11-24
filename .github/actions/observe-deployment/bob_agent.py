"""Run one agent task with Bob Shell (``bob run``) against our MCP server (D-17).

Bob's built-in loop stands in for our own agent loop during the PoC. This module is
the single seam: ``run_agent()`` takes a prompt and returns the usual outcome shape,
so the rest of the action does not care which agent is behind it.

What it adds on top of ``bob run``:
  * refuses to start without a prompt, the MCP URL, both Instana credentials and
    ``BOB_API_KEY``,
  * writes a throw-away ``.bob/mcp.json`` (mode 0600) holding the real headers,
    because Bob does NOT substitute ``${ENV}`` in headers, and deletes it afterwards,
  * runs Bob with the ``execute`` tool group disabled (``bob run`` pre-approves tools),
  * enforces a hard wall-clock timeout (``--max-cost`` is not a hard stop) and kills
    Bob's whole process group,
  * redacts the Instana token and the Bob key from everything it returns,
  * maps every failure to a reason code (same codes as ``mcp_call.py``).

Settings (environment, never argv): BOB_API_KEY, INSTANA_API_TOKEN, INSTANA_BASE_URL,
MCP_SERVER_URL (default http://127.0.0.1:8080/mcp).

CLI:
  python bob_agent.py --prompt "Use the change-timeline skill ..." [--isolate-home]

Prints one JSON object: {"ok": bool, "reason": str|None, "detail": str, "result": any}.
On success ``result`` is {"answer", "duration_ms", "cost", "tool_calls", "task_id",
"over_cost_cap"}. Exit code: 0 when ok, 1 on an operational failure, 2 on invalid input.

Local note: a global Bob config in ``~/.bob`` can add its own MCP servers and hijack
the run. ``--isolate-home`` runs Bob with an empty HOME to avoid that. A clean CI
runner has no global config.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional

INVALID_INPUT = "invalid_input"
SERVER_UNREACHABLE = "server_unreachable"
TIMEOUT = "timeout"
AUTH_FAILED = "auth_failed"
TOOL_ERROR = "tool_error"
INVALID_RESPONSE = "invalid_response"
LIMIT_REACHED = "limit_reached"

DEFAULT_URL = "http://127.0.0.1:8080/mcp"
SERVER_NAME = "instana-ci"
_MAX_DETAIL = 500


def _outcome(ok: bool, reason: Optional[str], detail: str = "", result: Any = None) -> Dict[str, Any]:
    return {"ok": ok, "reason": reason, "detail": detail, "result": result}


def _redact(text: str, secrets: List[str], limit: Optional[int] = _MAX_DETAIL) -> str:
    """Remove every secret from text that may be returned or logged."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text if limit is None else text[:limit]


def _validate(prompt: str, mcp_url: str, token: str, base_url: str, bob_key: str,
              bob_bin: str) -> Optional[Dict[str, Any]]:
    missing = [n for n, v in (("prompt", prompt), ("MCP_SERVER_URL", mcp_url),
                              ("INSTANA_API_TOKEN", token), ("INSTANA_BASE_URL", base_url),
                              ("BOB_API_KEY", bob_key)) if not (v or "").strip()]
    if missing:
        return _outcome(False, INVALID_INPUT, "missing: " + ", ".join(missing))
    if shutil.which(bob_bin) is None:
        return _outcome(False, INVALID_INPUT, f"'{bob_bin}' not found on PATH")
    return None


def _write_mcp_config(workdir: str, mcp_url: str, token: str, base_url: str) -> None:
    config_dir = os.path.join(workdir, ".bob")
    os.makedirs(config_dir, mode=0o700, exist_ok=True)
    config = {"mcpServers": {SERVER_NAME: {
        "type": "streamable-http",
        "url": mcp_url,
        "headers": {"instana-api-token": token, "instana-base-url": base_url},
    }}}
    path = os.path.join(config_dir, "mcp.json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(config, fh)


def _parse_output(text: str) -> List[Dict[str, Any]]:
    """Return the JSON objects in Bob's output (one object, or one per line)."""
    text = (text or "").strip()
    if not text:
        return []
    try:
        whole = json.loads(text)
        return [whole] if isinstance(whole, dict) else []
    except ValueError:
        pass
    objects = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict):
                objects.append(obj)
    return objects


def _classify(objects: List[Dict[str, Any]], raw: str, returncode: int,
              secrets: List[str], max_cost: Optional[float]) -> Dict[str, Any]:
    result = next((o for o in reversed(objects) if o.get("type") == "result" or "last_message" in o), None)
    errors = " ".join(str(o.get("message", "")) for o in objects if o.get("type") == "error")

    if "maximum of" in errors.lower():
        return _outcome(False, LIMIT_REACHED, _redact(errors, secrets))
    if result is None:
        lowered = raw.lower()
        if any(w in lowered for w in ("api key", "api_key", "unauthorized", "authentication", "401")):
            return _outcome(False, AUTH_FAILED, "Bob rejected the credentials (check BOB_API_KEY)")
        return _outcome(False, INVALID_RESPONSE,
                        _redact(f"no result from bob (exit {returncode}): {raw}", secrets))
    if result.get("status") != "success" or returncode != 0:
        return _outcome(False, TOOL_ERROR, _redact(
            f"bob status={result.get('status')} exit={returncode} {errors}", secrets))

    stats = result.get("stats") or {}
    cost = stats.get("session_costs")
    answer = _redact(str(result.get("last_message") or ""), secrets, limit=None)
    return _outcome(True, None, "", {
        "answer": answer,
        "duration_ms": stats.get("duration_ms"),
        "cost": cost,
        "tool_calls": stats.get("tool_calls"),
        "task_id": stats.get("task_id"),
        "over_cost_cap": bool(max_cost and cost and cost > max_cost),
    })


def _kill_group(proc: "subprocess.Popen[str]") -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()


def run_agent(prompt: str, *, timeout: float = 300.0, max_turns: int = 25,
              max_cost: Optional[float] = 1.5, isolate_home: bool = False,
              bob_bin: str = "bob", mcp_url: Optional[str] = None, token: Optional[str] = None,
              base_url: Optional[str] = None, bob_key: Optional[str] = None) -> Dict[str, Any]:
    """One Bob task. Settings default to the environment variables listed above."""
    mcp_url = os.environ.get("MCP_SERVER_URL", DEFAULT_URL) if mcp_url is None else mcp_url
    token = os.environ.get("INSTANA_API_TOKEN", "") if token is None else token
    base_url = os.environ.get("INSTANA_BASE_URL", "") if base_url is None else base_url
    bob_key = os.environ.get("BOB_API_KEY", "") if bob_key is None else bob_key

    bad = _validate(prompt, mcp_url, token, base_url, bob_key, bob_bin)
    if bad:
        return bad

    secrets = [token, bob_key]
    workdir = tempfile.mkdtemp(prefix="bob-agent-")
    home = tempfile.mkdtemp(prefix="bob-home-") if isolate_home else None
    try:
        _write_mcp_config(workdir, mcp_url, token, base_url)
        env = dict(os.environ, BOB_API_KEY=bob_key)
        if home:
            env["HOME"] = home
        cmd = [bob_bin, "run", "--format", "json", "--disable-tool-groups", "execute",
               "--max-turns", str(max_turns)]
        if max_cost:
            cmd += ["--max-cost", str(max_cost)]
        cmd += ["--accept-license", prompt]

        try:
            proc = subprocess.Popen(cmd, cwd=workdir, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True)
        except OSError as exc:
            return _outcome(False, SERVER_UNREACHABLE, _redact(f"cannot start bob: {exc}", secrets))
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            proc.communicate()
            return _outcome(False, TIMEOUT, f"bob did not finish within {timeout:g} s")

        return _classify(_parse_output(stdout), (stdout or "") + (stderr or ""),
                         proc.returncode, secrets, max_cost)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        if home:
            shutil.rmtree(home, ignore_errors=True)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--prompt", required=True)
    p.add_argument("--timeout", type=float, default=300.0)
    p.add_argument("--max-turns", type=int, default=25)
    p.add_argument("--max-cost", type=float, default=1.5)
    p.add_argument("--isolate-home", action="store_true",
                   help="run Bob with an empty HOME so ~/.bob MCP servers are not used")
    a = p.parse_args(argv)

    out = run_agent(a.prompt, timeout=a.timeout, max_turns=a.max_turns,
                    max_cost=a.max_cost, isolate_home=a.isolate_home)
    print(json.dumps(out, default=str))
    if out["ok"]:
        return 0
    return 2 if out["reason"] == INVALID_INPUT else 1


if __name__ == "__main__":
    sys.exit(main())
