"""Send one chat request to an OpenAI-compatible model and classify the outcome.

Thin wrapper over ``requests``. It adds only what the library does not:
  * refuses to send anything without a base URL, model and API key,
  * trusts an optional private CA file (``LLM_CA_BUNDLE``) and never turns TLS
    verification off,
  * returns a small, fixed result shape and drops the model's ``reasoning`` fields,
  * parses tool-call arguments into dicts,
  * maps every failure to a reason code (same codes as ``mcp_call.py``).

Settings (environment, never argv): LLM_BASE_URL (including /v1), LLM_MODEL,
LLM_API_KEY, LLM_CA_BUNDLE (optional).

CLI:
  python llm_client.py --prompt "hello"

Prints one JSON object: {"ok": bool, "reason": str|None, "detail": str, "result": any}.
On success ``result`` is {"content", "tool_calls", "finish_reason", "usage"}.
Exit code: 0 when ok, 1 on an operational failure, 2 on invalid input.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

import requests

INVALID_INPUT = "invalid_input"
SERVER_UNREACHABLE = "server_unreachable"
TIMEOUT = "timeout"
AUTH_FAILED = "auth_failed"
INVALID_RESPONSE = "invalid_response"

_MAX_DETAIL = 500


def _outcome(ok: bool, reason: Optional[str], detail: str = "", result: Any = None) -> Dict[str, Any]:
    return {"ok": ok, "reason": reason, "detail": detail, "result": result}


def _redact(text: str, api_key: str) -> str:
    """Remove the API key from any text that may be returned or logged."""
    if api_key:
        text = text.replace(api_key, "***")
    return text[:_MAX_DETAIL]


def _validate(base_url: str, model: str, api_key: str, ca_bundle: str) -> Optional[Dict[str, Any]]:
    missing = [n for n, v in (("LLM_BASE_URL", base_url), ("LLM_MODEL", model),
                              ("LLM_API_KEY", api_key)) if not (v or "").strip()]
    if missing:
        return _outcome(False, INVALID_INPUT, "missing: " + ", ".join(missing))
    if ca_bundle and not os.path.isfile(ca_bundle):
        return _outcome(False, INVALID_INPUT, "LLM_CA_BUNDLE is set but the file does not exist")
    return None


def _map_exception(exc: BaseException, api_key: str) -> Dict[str, Any]:
    # Timeout first: requests.ConnectTimeout is also a ConnectionError.
    if isinstance(exc, requests.exceptions.Timeout):
        return _outcome(False, TIMEOUT, "request timed out")
    text = _redact(f"{type(exc).__name__}: {exc}", api_key)
    if isinstance(exc, requests.exceptions.ConnectionError):  # includes SSLError
        return _outcome(False, SERVER_UNREACHABLE, text)
    return _outcome(False, INVALID_RESPONSE, text)


def _parse_tool_calls(raw: Any, api_key: str) -> Any:
    """Return a list of {id, name, arguments: dict}, or an error outcome."""
    parsed: List[Dict[str, Any]] = []
    for call in raw or []:
        fn = (call or {}).get("function") or {}
        args_text = fn.get("arguments")
        try:
            arguments = json.loads(args_text) if args_text else {}
        except (TypeError, json.JSONDecodeError):
            return _outcome(False, INVALID_RESPONSE,
                            _redact("tool call arguments are not valid JSON: "
                                    f"{str(args_text)[:200]}", api_key))
        if not isinstance(arguments, dict) or not fn.get("name"):
            return _outcome(False, INVALID_RESPONSE, "tool call has no name or non-object arguments")
        parsed.append({"id": call.get("id"), "name": fn["name"], "arguments": arguments})
    return parsed


def _parse_response(data: Any, api_key: str) -> Dict[str, Any]:
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices or not isinstance(choices[0], dict) or "message" not in choices[0]:
        return _outcome(False, INVALID_RESPONSE, "response has no choices[0].message")
    choice = choices[0]
    message = choice["message"] or {}
    tool_calls = _parse_tool_calls(message.get("tool_calls"), api_key)
    if isinstance(tool_calls, dict):
        return tool_calls
    # Only these fields are kept. "reasoning" and "reasoning_content" are dropped on purpose.
    return _outcome(True, None, "", {
        "content": message.get("content"),
        "tool_calls": tool_calls,
        "finish_reason": choice.get("finish_reason"),
        "usage": data.get("usage"),
    })


def chat(messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None,
         timeout: float = 60.0, *, base_url: Optional[str] = None, model: Optional[str] = None,
         api_key: Optional[str] = None, ca_bundle: Optional[str] = None) -> Dict[str, Any]:
    """One chat completion. Settings default to the LLM_* environment variables."""
    base_url = os.environ.get("LLM_BASE_URL", "") if base_url is None else base_url
    model = os.environ.get("LLM_MODEL", "") if model is None else model
    api_key = os.environ.get("LLM_API_KEY", "") if api_key is None else api_key
    ca_bundle = os.environ.get("LLM_CA_BUNDLE", "") if ca_bundle is None else ca_bundle

    bad = _validate(base_url, model, api_key, ca_bundle)
    if bad:
        return bad

    body: Dict[str, Any] = {"model": model, "messages": messages}
    if tools:
        body["tools"] = tools
    try:
        resp = requests.post(
            base_url.rstrip("/") + "/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            verify=ca_bundle or True,
        )
    except Exception as exc:  # - every failure must become a reason code
        return _map_exception(exc, api_key)

    if resp.status_code in (401, 403):
        return _outcome(False, AUTH_FAILED, f"HTTP {resp.status_code}")
    if resp.status_code != 200:
        return _outcome(False, INVALID_RESPONSE,
                        _redact(f"HTTP {resp.status_code}: {resp.text}", api_key))
    try:
        data = resp.json()
    except ValueError:
        return _outcome(False, INVALID_RESPONSE, "response body is not valid JSON")
    return _parse_response(data, api_key)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--prompt", required=True)
    p.add_argument("--timeout", type=float, default=60.0)
    a = p.parse_args(argv)

    out = chat([{"role": "user", "content": a.prompt}], timeout=a.timeout)
    print(json.dumps(out, default=str))
    if out["ok"]:
        return 0
    return 2 if out["reason"] == INVALID_INPUT else 1


if __name__ == "__main__":
    sys.exit(main())
