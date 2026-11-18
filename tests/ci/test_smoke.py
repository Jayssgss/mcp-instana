"""Unit tests for .github/actions/observe-deployment/smoke.py (mcp_call is faked; no server needed)."""

import asyncio
import importlib.util
import pathlib
import sys

_DIR = (pathlib.Path(__file__).resolve().parents[2] / ".github" / "actions" / "observe-deployment")
sys.path.insert(0, str(_DIR))
_spec = importlib.util.spec_from_file_location("smoke", _DIR / "smoke.py")
smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(smoke)
mc = smoke.mc


def _ok(result):
    return {"ok": True, "reason": None, "detail": "", "result": result}


def _fail(reason="tool_error", detail="boom"):
    return {"ok": False, "reason": reason, "detail": detail, "result": None}


def _fake(monkeypatch, tools=None, skills=None, skill_get=None, tenant=None):
    async def list_tools(*a, **k):
        return tools if tools is not None else _ok(["load_instana_skills", "manage_releases"])

    async def call_tool(url, token, base, name, arguments=None, timeout=60.0):
        if name == "load_instana_skills" and arguments["operation"] == "list":
            return skills if skills is not None else _ok({"skills": [{"id": "change-timeline"}]})
        if name == "load_instana_skills":
            return skill_get if skill_get is not None else _ok({"content": "# skill"})
        return tenant if tenant is not None else _ok({"results": {"success": True}})

    monkeypatch.setattr(mc, "list_tools", list_tools)
    monkeypatch.setattr(mc, "call_tool", call_tool)


def _run():
    return asyncio.run(smoke.run_checks("http://h/mcp", "t", "https://x"))


def test_all_pass(monkeypatch):
    _fake(monkeypatch)
    checks, facts = _run()
    assert [c[1] for c in checks] == [True, True, True, True]
    assert facts["skills"] == ["change-timeline"] and facts["tools"] == 2


def test_stops_after_tool_list_failure(monkeypatch):
    _fake(monkeypatch, tools=_fail("server_unreachable", "down"))
    checks, _ = _run()
    assert len(checks) == 1 and not checks[0][1] and "server_unreachable" in checks[0][3]


def test_missing_skills_tool_fails(monkeypatch):
    _fake(monkeypatch, tools=_ok(["manage_releases"]))
    checks, _ = _run()
    assert len(checks) == 1 and not checks[0][1]


def test_empty_skill_list_fails_and_stops(monkeypatch):
    _fake(monkeypatch, skills=_ok({"skills": []}))
    checks, _ = _run()
    assert len(checks) == 2 and not checks[1][1]


def test_empty_skill_content_fails(monkeypatch):
    _fake(monkeypatch, skill_get=_ok({"content": ""}))
    checks, _ = _run()
    assert not checks[2][1]


def test_tenant_failure_is_reported(monkeypatch):
    _fake(monkeypatch, tenant=_fail("auth_failed", "401"))
    checks, _ = _run()
    assert not checks[3][1] and "auth_failed" in checks[3][3]


def test_render_marks_overall_and_escapes_pipes():
    text = smoke.render([("a", True, 0.1, ""), ("b", False, 0.2, "x|y")], {"tools": 1, "skills": []}, "http://h/mcp")
    assert "Overall: FAIL" in text and "x/y" in text and "Skills: none" in text


def test_main_invalid_input_exit_2(monkeypatch):
    monkeypatch.delenv("INSTANA_API_TOKEN", raising=False)
    monkeypatch.delenv("INSTANA_BASE_URL", raising=False)
    assert smoke.main() == 2


def test_main_writes_job_summary_and_exit_codes(monkeypatch, tmp_path):
    _fake(monkeypatch)
    out = tmp_path / "summary.md"
    monkeypatch.setenv("INSTANA_API_TOKEN", "t")
    monkeypatch.setenv("INSTANA_BASE_URL", "https://x")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(out))
    assert smoke.main() == 0
    assert "Overall: PASS" in out.read_text()
    _fake(monkeypatch, tenant=_fail())
    assert smoke.main() == 1


def test_token_never_printed_outside_github_actions(monkeypatch, capsys):
    _fake(monkeypatch)
    monkeypatch.setenv("INSTANA_API_TOKEN", "SECRET-TOKEN-VALUE")
    monkeypatch.setenv("INSTANA_BASE_URL", "https://x")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    smoke.main()
    assert "SECRET-TOKEN-VALUE" not in capsys.readouterr().out


def test_token_masked_on_github_actions(monkeypatch, capsys):
    _fake(monkeypatch)
    monkeypatch.setenv("INSTANA_API_TOKEN", "SECRET-TOKEN-VALUE")
    monkeypatch.setenv("INSTANA_BASE_URL", "https://x")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    smoke.main()
    assert "::add-mask::SECRET-TOKEN-VALUE" in capsys.readouterr().out
