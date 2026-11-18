"""Smoke test: prove a CI-style client can reach the Instana MCP server and get data.

Checks, in order (each reported as PASS/FAIL with timing):
  1. tools/list returns tools, including load_instana_skills
  2. load_instana_skills list returns at least one skill
  3. load_instana_skills get returns the SKILL.md of the first skill
  4. one read-only tenant call (manage_releases get_all_releases, page_size 1)

Environment: INSTANA_API_TOKEN, INSTANA_BASE_URL, MCP_SERVER_URL (default
http://127.0.0.1:8080/mcp). Credentials are never printed.
Writes a markdown report to stdout, and appends it to $GITHUB_STEP_SUMMARY if set.
Exit code: 0 if all checks pass, 1 if any fails, 2 on invalid input.
"""

import asyncio
import os
import sys
import time
from typing import Any, Callable, Dict, List, Tuple

import mcp_call as mc

Check = Tuple[str, bool, float, str]


async def _timed(name: str, fn: Callable[[], Any]) -> Tuple[Check, Dict[str, Any]]:
    start = time.monotonic()
    out = await fn()
    secs = time.monotonic() - start
    detail = "" if out["ok"] else f'{out["reason"]}: {out["detail"]}'
    return (name, bool(out["ok"]), secs, detail[:200]), out


async def run_checks(url: str, token: str, base_url: str, timeout: float = 60.0) -> Tuple[List[Check], Dict[str, Any]]:
    checks: List[Check] = []
    facts: Dict[str, Any] = {}

    check, out = await _timed("tools/list", lambda: mc.list_tools(url, token, base_url, timeout))
    if out["ok"] and "load_instana_skills" not in out["result"]:
        check = (check[0], False, check[2], "load_instana_skills not in tool list")
    checks.append(check)
    facts["tools"] = len(out["result"]) if out["ok"] else 0
    if not check[1]:
        return checks, facts

    check, out = await _timed("skills list", lambda: mc.call_tool(
        url, token, base_url, "load_instana_skills", {"operation": "list"}, timeout))
    skills = (out["result"] or {}).get("skills", []) if out["ok"] else []
    if out["ok"] and not skills:
        check = (check[0], False, check[2], "no skills returned")
    checks.append(check)
    facts["skills"] = [s.get("id") for s in skills]
    if not skills:
        return checks, facts

    first = skills[0]["id"]
    check, out = await _timed(f"skill get ({first})", lambda: mc.call_tool(
        url, token, base_url, "load_instana_skills", {"operation": "get", "name": first}, timeout))
    if out["ok"] and not (out["result"] or {}).get("content"):
        check = (check[0], False, check[2], "empty skill content")
    checks.append(check)
    facts["skill_chars"] = len((out["result"] or {}).get("content", "")) if out["ok"] else 0

    check, out = await _timed("tenant call (manage_releases)", lambda: mc.call_tool(
        url, token, base_url, "manage_releases",
        {"operation": "get_all_releases", "params": {"page_size": 1}}, timeout))
    checks.append(check)
    return checks, facts


def render(checks: List[Check], facts: Dict[str, Any], url: str) -> str:
    lines = ["## Instana MCP smoke test", "", f"Server: `{url}`", "",
             "| Check | Result | Seconds | Detail |", "|---|---|---|---|"]
    for name, ok, secs, detail in checks:
        lines.append(f'| {name} | {"PASS" if ok else "FAIL"} | {secs:.2f} | {detail.replace("|", "/")} |')
    lines += ["", f'Tools: {facts.get("tools", 0)}. Skills: {", ".join(facts.get("skills", [])) or "none"}.']
    ok = all(c[1] for c in checks)
    lines += ["", "**Overall: PASS**" if ok else "**Overall: FAIL**"]
    return "\n".join(lines) + "\n"


def main() -> int:
    url = os.environ.get("MCP_SERVER_URL", mc.DEFAULT_URL)
    token = os.environ.get("INSTANA_API_TOKEN", "")
    base_url = os.environ.get("INSTANA_BASE_URL", "")
    bad = mc._validate(url, token, base_url)
    if bad:
        print(f'invalid_input: {bad["detail"]}', file=sys.stderr)
        return 2
    if token and os.environ.get("GITHUB_ACTIONS") == "true":
        # Only on a runner: there the command is consumed and masks the value.
        # Anywhere else it would print the token.
        print(f"::add-mask::{token}")

    checks, facts = asyncio.run(run_checks(url, token, base_url))
    report = render(checks, facts, url)
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    return 0 if all(c[1] for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
