"""Unit tests for .github/actions/observe-deployment/mcp_call.py (no server or tenant needed)."""

import asyncio
import importlib.util
import pathlib

import pytest

_PATH = (pathlib.Path(__file__).resolve().parents[2]
         / ".github" / "actions" / "observe-deployment" / "mcp_call.py")
_spec = importlib.util.spec_from_file_location("mcp_call", _PATH)
mc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mc)


def test_classify_success():
    out = mc.classify({"operation": "x", "results": {"success": True}}, False)
    assert out["ok"] and out["reason"] is None


def test_classify_success_without_results_key():
    assert mc.classify({"skills": []}, False)["ok"]


def test_classify_http200_but_success_false_is_failure():
    out = mc.classify({"results": {"success": False, "error": "Failed to get releases: boom"}}, False)
    assert not out["ok"] and out["reason"] == mc.TOOL_ERROR
    assert "boom" in out["detail"]


def test_classify_is_error_flag():
    out = mc.classify({"detail": "validation error"}, True)
    assert not out["ok"] and out["reason"] == mc.TOOL_ERROR


@pytest.mark.parametrize("text", [
    "HTTP mode detected but missing required headers: instana-base-url",
    "401 Unauthorized", "403 Forbidden"])
def test_classify_auth_hints(text):
    out = mc.classify({"results": {"success": False, "error": text}}, False)
    assert out["reason"] == mc.AUTH_FAILED


@pytest.mark.parametrize("url,token,base", [
    ("", "t", "https://x"), ("http://h/mcp", "", "https://x"),
    ("http://h/mcp", "t", ""), ("http://h/mcp", "  ", "https://x")])
def test_empty_inputs_rejected_without_network(url, token, base):
    out = asyncio.run(mc.call_tool(url, token, base, "any"))
    assert not out["ok"] and out["reason"] == mc.INVALID_INPUT


def test_server_down_maps_to_unreachable():
    # Port 1 is never an MCP server; connection is refused immediately.
    out = asyncio.run(mc.call_tool("http://127.0.0.1:1/mcp", "t", "https://x", "any", timeout=5))
    assert not out["ok"] and out["reason"] == mc.SERVER_UNREACHABLE


def test_timeout_maps_to_timeout():
    assert mc._map_exception(asyncio.TimeoutError())["reason"] == mc.TIMEOUT


def test_unknown_exception_maps_to_invalid_response():
    assert mc._map_exception(ValueError("bad json"))["reason"] == mc.INVALID_RESPONSE

def test_wrapped_timeout_maps_to_timeout():
    # fastmcp 4.x: RuntimeError("Client failed to connect") caused by a read timeout.
    class ReadTimeout(Exception):
        pass

    wrapped = RuntimeError("Client failed to connect: ")
    wrapped.__cause__ = ReadTimeout()
    assert mc._map_exception(wrapped)["reason"] == mc.TIMEOUT


def test_timed_out_message_maps_to_timeout():
    # fastmcp 3.x: McpError("Timed out while waiting for response ... 1.0 seconds").
    exc = Exception("Timed out while waiting for response to ClientRequest. Waited 1.0 seconds.")
    assert mc._map_exception(exc)["reason"] == mc.TIMEOUT


def test_connect_failure_without_timeout_stays_unreachable():
    assert mc._map_exception(RuntimeError("Client failed to connect: refused"))["reason"] == mc.SERVER_UNREACHABLE




def test_cli_invalid_json_args(capsys, monkeypatch):
    monkeypatch.setenv("INSTANA_API_TOKEN", "t")
    monkeypatch.setenv("INSTANA_BASE_URL", "https://x")
    assert mc.main(["--tool", "a", "--args", "{nope"]) == 2


def test_cli_without_action_is_invalid_input(monkeypatch):
    monkeypatch.setenv("INSTANA_API_TOKEN", "t")
    monkeypatch.setenv("INSTANA_BASE_URL", "https://x")
    assert mc.main([]) == 2


def test_cli_missing_credentials_exit_2(monkeypatch):
    monkeypatch.delenv("INSTANA_API_TOKEN", raising=False)
    monkeypatch.delenv("INSTANA_BASE_URL", raising=False)
    assert mc.main(["--list-tools"]) == 2


def test_classify_error_without_success_key_is_failure():
    # Real response from a server with no credentials (plan step 1.3).
    out = mc.classify({"operation": "get_all_releases", "results": {
        "error": "Authentication failed: Missing credentials  - INSTANA_API_TOKEN is missing"}}, False)
    assert not out["ok"] and out["reason"] == mc.AUTH_FAILED


def test_classify_missing_header_message_is_auth_failed():
    out = mc.classify({"results": {
        "error": "HTTP mode detected but missing required headers: instana-base-url"}}, False)
    assert not out["ok"] and out["reason"] == mc.AUTH_FAILED


def test_classify_success_true_with_error_key_is_still_success():
    assert mc.classify({"results": {"success": True, "error": None}}, False)["ok"]


def _silent_server():
    """Accepts TCP connections and never answers, like a hung MCP server."""
    import socket
    import threading

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    conns = []

    def accept():
        while True:
            try:
                conns.append(srv.accept()[0])
            except OSError:
                return

    threading.Thread(target=accept, daemon=True).start()
    return srv, conns


def test_hung_server_maps_to_timeout():
    import time

    srv, conns = _silent_server()
    try:
        url = f"http://127.0.0.1:{srv.getsockname()[1]}/mcp"
        start = time.monotonic()
        out = asyncio.run(mc.call_tool(url, "t", "https://x", "any", timeout=1))
        elapsed = time.monotonic() - start
    finally:
        srv.close()
        for c in conns:
            c.close()
    assert not out["ok"], out
    assert out["reason"] == mc.TIMEOUT, out
    assert elapsed < 15, f"gave up after {elapsed:.1f}s; the timeout is not bounded"
