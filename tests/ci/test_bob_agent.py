"""Unit tests for .github/actions/observe-deployment/bob_agent.py.

A tiny fake ``bob`` shell script stands in for Bob Shell. No real Bob, model or
network is used (D-13: the product path never uses a fake agent).
"""

import importlib.util
import json
import os
import pathlib
import stat
import textwrap
import time

import pytest

_PATH = (pathlib.Path(__file__).resolve().parents[2]
         / ".github" / "actions" / "observe-deployment" / "bob_agent.py")
_spec = importlib.util.spec_from_file_location("bob_agent", _PATH)
ba = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ba)

TOKEN = "instana-token-SECRET-123456"
BOB_KEY = "bob-key-SECRET-abcdef"
BASE_URL = "https://tenant.example.instana.io"
URL = "http://127.0.0.1:9999/mcp"


def _fake_bob(tmp_path, body: str) -> str:
    """Write an executable shell script named bob and return its path."""
    path = tmp_path / "bob"
    path.write_text("#!/bin/bash\n" + textwrap.dedent(body))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def _result_json(**over):
    stats = {"task_id": "t1", "duration_ms": 1234, "session_costs": 0.5, "max_cost": 1.5, "tool_calls": 3}
    stats.update(over.pop("stats", {}))
    obj = {"type": "result", "status": "success", "stats": stats, "last_message": "all good"}
    obj.update(over)
    return json.dumps(obj)


def _run(bob, **kw):
    kw.setdefault("mcp_url", URL)
    kw.setdefault("token", TOKEN)
    kw.setdefault("base_url", BASE_URL)
    kw.setdefault("bob_key", BOB_KEY)
    return ba.run_agent("hello", bob_bin=bob, **kw)


def test_success_returns_answer_and_stats(tmp_path):
    bob = _fake_bob(tmp_path, f"echo '{_result_json()}'\n")
    out = _run(bob)
    assert out["ok"] is True and out["reason"] is None
    r = out["result"]
    assert r["answer"] == "all good"
    assert r["cost"] == 0.5 and r["tool_calls"] == 3 and r["duration_ms"] == 1234
    assert r["over_cost_cap"] is False


def test_over_cost_cap_is_flagged_but_still_ok(tmp_path):
    bob = _fake_bob(tmp_path, f"echo '{_result_json(stats={'session_costs': 1.716})}'\n")
    out = _run(bob, max_cost=1.5)
    assert out["ok"] is True and out["result"]["over_cost_cap"] is True


def test_stream_of_json_lines_uses_the_result_line(tmp_path):
    lines = json.dumps({"type": "message", "content": "x"}) + "\n" + _result_json()
    bob = _fake_bob(tmp_path, f"cat <<'EOF'\n{lines}\nEOF\n")
    assert _run(bob)["result"]["answer"] == "all good"


@pytest.mark.parametrize("missing", ["token", "base_url", "bob_key", "mcp_url"])
def test_empty_settings_refuse_without_starting_bob(tmp_path, missing):
    marker = tmp_path / "ran"
    bob = _fake_bob(tmp_path, f"touch {marker}\n")
    out = _run(bob, **{missing: ""})
    assert out["ok"] is False and out["reason"] == ba.INVALID_INPUT
    assert not marker.exists()


def test_empty_prompt_is_invalid_input(tmp_path):
    bob = _fake_bob(tmp_path, "echo hi\n")
    out = ba.run_agent("  ", bob_bin=bob, mcp_url=URL, token=TOKEN, base_url=BASE_URL, bob_key=BOB_KEY)
    assert out["reason"] == ba.INVALID_INPUT


def test_missing_bob_binary_is_invalid_input():
    out = _run("definitely-not-a-real-bob-binary")
    assert out["reason"] == ba.INVALID_INPUT and "not found" in out["detail"]


def test_mcp_config_has_headers_and_mode_0600_and_is_deleted(tmp_path):
    seen = tmp_path / "seen.json"
    mode = tmp_path / "mode.txt"
    bob = _fake_bob(tmp_path, f"""
        cp .bob/mcp.json {seen}
        stat -f '%Lp' .bob/mcp.json > {mode} 2>/dev/null || stat -c '%a' .bob/mcp.json > {mode}
        pwd > {tmp_path / 'cwd.txt'}
        echo '{_result_json()}'
    """)
    assert _run(bob)["ok"] is True
    cfg = json.loads(seen.read_text())["mcpServers"][ba.SERVER_NAME]
    assert cfg["url"] == URL and cfg["type"] == "streamable-http"
    assert cfg["headers"] == {"instana-api-token": TOKEN, "instana-base-url": BASE_URL}
    assert mode.read_text().strip() == "600"
    assert not os.path.exists((tmp_path / "cwd.txt").read_text().strip())


def test_command_line_has_safety_flags_and_no_secrets(tmp_path):
    args_file = tmp_path / "args.txt"
    bob = _fake_bob(tmp_path, f'printf "%s\\n" "$@" > {args_file}\necho \'{_result_json()}\'\n')
    assert _run(bob, max_turns=7, max_cost=0.9)["ok"] is True
    args = args_file.read_text().splitlines()
    assert args[0] == "run"
    assert args[args.index("--format") + 1] == "json"
    assert args[args.index("--disable-tool-groups") + 1] == "execute"
    assert args[args.index("--max-turns") + 1] == "7"
    assert args[args.index("--max-cost") + 1] == "0.9"
    assert "--accept-license" in args and args[-1] == "hello"
    joined = " ".join(args)
    assert TOKEN not in joined and BOB_KEY not in joined


def test_bob_key_is_passed_by_environment(tmp_path):
    out_file = tmp_path / "key.txt"
    bob = _fake_bob(tmp_path, f'echo "$BOB_API_KEY" > {out_file}\necho \'{_result_json()}\'\n')
    assert _run(bob)["ok"] is True
    assert out_file.read_text().strip() == BOB_KEY


def test_isolate_home_sets_an_empty_home_and_removes_it(tmp_path):
    home_file = tmp_path / "home.txt"
    bob = _fake_bob(tmp_path, f'echo "$HOME" > {home_file}\nls -A "$HOME" | wc -l >> {home_file}\necho \'{_result_json()}\'\n')
    assert _run(bob, isolate_home=True)["ok"] is True
    home, count = home_file.read_text().split()
    assert home != os.environ.get("HOME") and count == "0"
    assert not os.path.exists(home)


def test_hung_bob_times_out_and_is_killed(tmp_path):
    pid_file = tmp_path / "pid.txt"
    bob = _fake_bob(tmp_path, f"sleep 30 &\necho $! > {pid_file}\nwait\n")
    t0 = time.time()
    out = _run(bob, timeout=1.0)
    assert out["ok"] is False and out["reason"] == ba.TIMEOUT
    assert time.time() - t0 < 10
    time.sleep(0.3)
    child = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(child, 0)


def test_turn_limit_message_maps_to_limit_reached(tmp_path):
    err = json.dumps({"type": "error", "message": "The task reached the maximum of 8 turns."})
    bob = _fake_bob(tmp_path, f"echo '{err}'\necho '{_result_json()}'\n")
    out = _run(bob)
    assert out["ok"] is False and out["reason"] == ba.LIMIT_REACHED


def test_no_result_and_auth_text_maps_to_auth_failed(tmp_path):
    bob = _fake_bob(tmp_path, "echo 'Error: BOB_API_KEY is invalid (401 Unauthorized)' >&2\nexit 1\n")
    assert _run(bob)["reason"] == ba.AUTH_FAILED


def test_garbage_output_maps_to_invalid_response(tmp_path):
    bob = _fake_bob(tmp_path, "echo 'something odd'\nexit 0\n")
    assert _run(bob)["reason"] == ba.INVALID_RESPONSE


def test_failed_status_maps_to_tool_error(tmp_path):
    bob = _fake_bob(tmp_path, f"echo '{_result_json(status='error')}'\nexit 1\n")
    assert _run(bob)["reason"] == ba.TOOL_ERROR


def test_secrets_never_appear_in_any_output(tmp_path):
    bob = _fake_bob(tmp_path, f"echo 'oops {TOKEN} and {BOB_KEY}' >&2\nexit 3\n")
    out = _run(bob)
    text = json.dumps(out)
    assert TOKEN not in text and BOB_KEY not in text and "***" in text


def test_secrets_are_redacted_from_the_answer(tmp_path):
    obj = _result_json(last_message=f"the token is {TOKEN}")
    bob = _fake_bob(tmp_path, f"cat <<'EOF'\n{obj}\nEOF\n")
    out = _run(bob)
    assert out["ok"] is True and TOKEN not in out["result"]["answer"]


def test_cli_exit_codes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("INSTANA_API_TOKEN", "")
    monkeypatch.setenv("INSTANA_BASE_URL", "")
    monkeypatch.setenv("BOB_API_KEY", "")
    assert ba.main(["--prompt", "x"]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == ba.INVALID_INPUT
