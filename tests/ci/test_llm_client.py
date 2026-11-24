"""Unit tests for .github/actions/observe-deployment/llm_client.py.

A tiny local HTTP server stands in for the model. It exists in tests only (D-13);
no real model or network is used.
"""

import importlib.util
import json
import pathlib
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

_PATH = (pathlib.Path(__file__).resolve().parents[2]
         / ".github" / "actions" / "observe-deployment" / "llm_client.py")
_spec = importlib.util.spec_from_file_location("llm_client", _PATH)
lc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lc)

KEY = "sk-test-secret-key-123"
MESSAGES = [{"role": "user", "content": "hi"}]


def _reply(content="hello", tool_calls=None, finish="stop", extra_message=None):
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    message.update(extra_message or {})
    return {"choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}


class _Fake:
    """Local fake model server. Set .status / .body / .delay before calling."""

    def __init__(self):
        self.status = 200
        self.body = json.dumps(_reply())
        self.delay = 0.0
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - http.server API
                length = int(self.headers.get("Content-Length", 0))
                fake.requests.append({
                    "path": self.path,
                    "auth": self.headers.get("Authorization"),
                    "json": json.loads(self.rfile.read(length) or b"{}"),
                })
                if fake.delay:
                    time.sleep(fake.delay)
                payload = fake.body.encode()
                try:
                    self.send_response(fake.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except OSError:
                    pass  # client gave up (timeout test)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake():
    f = _Fake()
    yield f
    f.stop()


def _chat(fake, **kw):
    kw.setdefault("base_url", fake.url)
    kw.setdefault("model", "test-model")
    kw.setdefault("api_key", KEY)
    kw.setdefault("ca_bundle", "")
    return lc.chat(MESSAGES, **kw)


def test_plain_text_reply(fake):
    out = _chat(fake)
    assert out["ok"] and out["reason"] is None
    assert out["result"] == {
        "content": "hello", "tool_calls": [], "finish_reason": "stop",
        "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}


def test_request_shape(fake):
    _chat(fake)
    req = fake.requests[0]
    assert req["path"] == "/v1/chat/completions"
    assert req["auth"] == f"Bearer {KEY}"
    assert req["json"] == {"model": "test-model", "messages": MESSAGES}


def test_tools_are_sent_only_when_given(fake):
    tools = [{"type": "function", "function": {"name": "t", "parameters": {"type": "object"}}}]
    _chat(fake, tools=tools)
    assert fake.requests[0]["json"]["tools"] == tools


def test_base_url_trailing_slash_is_ok(fake):
    assert _chat(fake, base_url=fake.url + "/")["ok"]
    assert fake.requests[0]["path"] == "/v1/chat/completions"


def test_tool_calls_arguments_are_parsed(fake):
    fake.body = json.dumps(_reply(content=None, finish="tool_calls", tool_calls=[
        {"id": "c1", "type": "function",
         "function": {"name": "manage_releases", "arguments": '{"page_size": 1}'}}]))
    out = _chat(fake)
    assert out["ok"]
    assert out["result"]["finish_reason"] == "tool_calls"
    assert out["result"]["tool_calls"] == [
        {"id": "c1", "name": "manage_releases", "arguments": {"page_size": 1}}]


def test_empty_arguments_become_empty_dict(fake):
    fake.body = json.dumps(_reply(tool_calls=[
        {"id": "c1", "function": {"name": "t", "arguments": ""}}]))
    assert _chat(fake)["result"]["tool_calls"][0]["arguments"] == {}


def test_invalid_json_arguments_is_invalid_response(fake):
    fake.body = json.dumps(_reply(tool_calls=[
        {"id": "c1", "function": {"name": "t", "arguments": "{not json"}}]))
    out = _chat(fake)
    assert not out["ok"] and out["reason"] == lc.INVALID_RESPONSE
    assert "{not json" in out["detail"]


def test_non_object_arguments_is_invalid_response(fake):
    fake.body = json.dumps(_reply(tool_calls=[
        {"id": "c1", "function": {"name": "t", "arguments": "[1, 2]"}}]))
    assert _chat(fake)["reason"] == lc.INVALID_RESPONSE


def test_reasoning_fields_are_dropped(fake):
    fake.body = json.dumps(_reply(extra_message={
        "reasoning": "secret thoughts", "reasoning_content": "more thoughts"}))
    out = _chat(fake)
    assert out["ok"]
    assert "secret thoughts" not in json.dumps(out)
    assert "more thoughts" not in json.dumps(out)


@pytest.mark.parametrize("status", [401, 403])
def test_auth_status_maps_to_auth_failed(fake, status):
    fake.status = status
    fake.body = json.dumps({"error": "nope"})
    out = _chat(fake)
    assert not out["ok"] and out["reason"] == lc.AUTH_FAILED


def test_other_http_error_is_invalid_response(fake):
    fake.status = 500
    fake.body = "boom"
    out = _chat(fake)
    assert out["reason"] == lc.INVALID_RESPONSE and "500" in out["detail"]


def test_non_json_body_is_invalid_response(fake):
    fake.body = "<html>not json</html>"
    assert _chat(fake)["reason"] == lc.INVALID_RESPONSE


@pytest.mark.parametrize("body", [{}, {"choices": []}, {"choices": [{}]}, []])
def test_missing_choices_is_invalid_response(fake, body):
    fake.body = json.dumps(body)
    assert _chat(fake)["reason"] == lc.INVALID_RESPONSE


def test_slow_server_maps_to_timeout(fake):
    fake.delay = 2.0
    out = _chat(fake, timeout=0.3)
    assert not out["ok"] and out["reason"] == lc.TIMEOUT


def test_closed_port_maps_to_server_unreachable():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    out = lc.chat(MESSAGES, base_url=f"http://127.0.0.1:{port}/v1", model="m",
                  api_key=KEY, ca_bundle="", timeout=2)
    assert not out["ok"] and out["reason"] == lc.SERVER_UNREACHABLE


@pytest.mark.parametrize("field", ["base_url", "model", "api_key"])
def test_empty_setting_sends_no_request(fake, field):
    kw = {"base_url": fake.url, "model": "m", "api_key": KEY, "ca_bundle": ""}
    kw[field] = "  "
    out = lc.chat(MESSAGES, **kw)
    assert not out["ok"] and out["reason"] == lc.INVALID_INPUT
    assert fake.requests == []


def test_missing_ca_file_is_invalid_input_and_sends_nothing(fake, tmp_path):
    out = _chat(fake, ca_bundle=str(tmp_path / "missing.pem"))
    assert out["reason"] == lc.INVALID_INPUT
    assert fake.requests == []


def test_settings_default_to_environment(fake, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", fake.url)
    monkeypatch.setenv("LLM_MODEL", "env-model")
    monkeypatch.setenv("LLM_API_KEY", KEY)
    monkeypatch.setenv("LLM_CA_BUNDLE", "")
    assert lc.chat(MESSAGES)["ok"]
    assert fake.requests[0]["json"]["model"] == "env-model"


def test_unset_environment_is_invalid_input(monkeypatch):
    for name in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_CA_BUNDLE"):
        monkeypatch.delenv(name, raising=False)
    out = lc.chat(MESSAGES)
    assert out["reason"] == lc.INVALID_INPUT
    assert "LLM_API_KEY" in out["detail"]


def test_key_never_appears_in_error_details(fake):
    # The server echoes the key back in its error body; it must be redacted.
    fake.status = 500
    fake.body = f"internal error for key {KEY}"
    out = _chat(fake)
    assert KEY not in json.dumps(out)

    fake.status = 200
    fake.body = json.dumps(_reply(tool_calls=[
        {"id": "c1", "function": {"name": "t", "arguments": f"bad {KEY}"}}]))
    out = _chat(fake)
    assert not out["ok"] and KEY not in json.dumps(out)


def test_key_not_in_connection_error_text():
    out = lc.chat(MESSAGES, base_url="http://127.0.0.1:1/v1", model="m",
                  api_key=KEY, ca_bundle="", timeout=2)
    assert not out["ok"] and KEY not in json.dumps(out)


def test_cli_without_settings_exits_2(monkeypatch, capsys):
    for name in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "LLM_CA_BUNDLE"):
        monkeypatch.delenv(name, raising=False)
    assert lc.main(["--prompt", "hi"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == lc.INVALID_INPUT


def test_cli_success_exits_0(fake, monkeypatch, capsys):
    monkeypatch.setenv("LLM_BASE_URL", fake.url)
    monkeypatch.setenv("LLM_MODEL", "m")
    monkeypatch.setenv("LLM_API_KEY", KEY)
    monkeypatch.setenv("LLM_CA_BUNDLE", "")
    assert lc.main(["--prompt", "hi"]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["content"] == "hello"
