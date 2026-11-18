"""Unit tests for the genai-instrumentation MCP skill."""

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# ---------------------------------------------------------------------------
# SDK stubs (needed when server.py / fastmcp loads indirectly)
# ---------------------------------------------------------------------------
_SDK_STUBS = {
    "instana_client": MagicMock(),
    "instana_client.api": MagicMock(),
    "instana_client.api.events_api": MagicMock(),
    "instana_client.api.releases_api": MagicMock(),
    "instana_client.models": MagicMock(),
    "instana_client.models.release": MagicMock(),
    "instana_client.api_client": MagicMock(),
    "instana_client.configuration": MagicMock(),
}
for mod_name, stub in _SDK_STUBS.items():
    sys.modules.setdefault(mod_name, stub)

SKILLS_DIR = Path(__file__).parent.parent.parent / "src" / "skills"
SKILL_NAME = "genai-instrumentation"
SKILL_DIR = SKILLS_DIR / SKILL_NAME
SKILL_MD = SKILL_DIR / "SKILL.md"
REFS_DIR = SKILL_DIR / "references"


def _skill_content() -> str:
    return SKILL_MD.read_text(encoding="utf-8")


def _all_content() -> str:
    parts = [_skill_content()]
    if REFS_DIR.is_dir():
        for ref in sorted(REFS_DIR.glob("*.md")):
            parts.append(ref.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _frontmatter() -> str:
    return _skill_content().split("---", 2)[1]


def _reference_content(name: str) -> str:
    return (REFS_DIR / name).read_text(encoding="utf-8")


class TestSkillFiles(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}")

    def test_skill_md_non_empty(self):
        self.assertGreater(SKILL_MD.stat().st_size, 0)

    def test_directory_name_matches_skill_name(self):
        """Directory name must equal the skill name (the load tool keys off directory)."""
        self.assertEqual(SKILL_DIR.name, SKILL_NAME)

    def test_reference_files_exist(self):
        for ref_name in (
            "detect-and-credentials.md",
            "apply-diff.md",
            "verify-telemetry.md",
            "iterate.md",
        ):
            ref_path = REFS_DIR / ref_name
            self.assertTrue(ref_path.exists(), f"Reference file not found: {ref_path}")
            self.assertGreater(ref_path.stat().st_size, 0)


class TestSkillFrontmatter(unittest.TestCase):
    def test_yaml_frontmatter_present(self):
        self.assertTrue(_skill_content().startswith("---"), "SKILL.md must start with YAML front-matter '---'")

    def test_frontmatter_has_closing_delimiter(self):
        self.assertGreaterEqual(len(_skill_content().split("---", 2)), 3)

    def test_name_field_matches_directory(self):
        self.assertRegex(_frontmatter(), rf'name:\s*"?{SKILL_NAME}"?')

    def test_description_field_present(self):
        self.assertIn("description:", _frontmatter())

    def test_description_covers_core_triggers(self):
        fm = _frontmatter()
        self.assertIn("OpenTelemetry", fm)
        self.assertIn("Instana", fm)
        for stack in ("LangGraph", "LangChain", "OpenAI", "Anthropic", "watsonx.ai", "Traceloop"):
            self.assertIn(stack, fm)

    def test_description_has_not_clause(self):
        fm = _frontmatter()
        self.assertTrue(
            "NOT" in fm or "Does not" in fm or "does not" in fm,
            "Description must contain a NOT/Does not clause",
        )

    def test_references_list_in_frontmatter(self):
        fm = _frontmatter()
        self.assertIn("references:", fm)
        for ref in ("detect-and-credentials.md", "apply-diff.md", "verify-telemetry.md", "iterate.md"):
            self.assertIn(ref, fm)

    def test_content_hash_present(self):
        self.assertIn("content_hash: sha256:", _frontmatter())


class TestConstitution(unittest.TestCase):
    """The non-negotiable rules table must remain intact in SKILL.md."""

    def test_constitution_section_present(self):
        self.assertIn("## Constitution — Non-Negotiable Rules", _skill_content())

    def test_all_eleven_principles_present(self):
        content = _skill_content()
        for principle in (
            "Verification Before Success",
            "Security First",
            "Read Before Write",
            "Stack-Aware",
            "Never Double-Instrument",
            "GenAI Compatibility",
            "Backward Compatibility",
            "Deterministic",
            "Minimal Privileges",
            "Structured Result",
            "Human Review Required",
        ):
            self.assertIn(principle, content, f"Constitution principle missing: {principle}")

    def test_permanently_forbidden_section_present(self):
        content = _skill_content()
        self.assertIn("## Permanently Forbidden", content)
        self.assertIn("Calling `manage_applications`", content)
        self.assertIn("Writing any credential value", content)
        self.assertIn("Adding a second `TracerProvider`", content)

    def test_credentials_never_displayed(self):
        content = _skill_content()
        self.assertIn("NEVER write, echo, log, display", content)
        self.assertIn("Reference env var names only", content)

    def test_human_approval_required_before_changes(self):
        self.assertIn("explicit developer approval", _skill_content())

    def test_read_only_token_permissions(self):
        content = _skill_content()
        self.assertIn("must be read-only", content)
        self.assertIn("Service & Endpoint Map Read", content)
        self.assertIn("Application Read", content)


class TestWorkflowSteps(unittest.TestCase):
    def test_execution_contract_present(self):
        self.assertIn("## Execution Contract", _skill_content())

    def test_skip_verification_gate_documented(self):
        content = _skill_content()
        self.assertIn("Skip-verification gate", content)
        self.assertIn("instrument and verify", content)

    def test_workflow_overview_present(self):
        self.assertIn("DETECT → CREDENTIALS → [CHECK] → SELECT → APPLY → RUN → [VERIFY → ITERATE] → [HAND OFF]", _skill_content())

    def test_all_primary_step_headings_present(self):
        content = _skill_content()
        for heading in (
            "## Step 1 — DETECT",
            "## Step 2 — CREDENTIALS",
            "## Step 3 — CHECK",
            "## Step 4 — SELECT",
            "## Step 5 — APPLY",
            "## Step 6 — RUN",
            "## Step 7 — VERIFY",
            "## Step 8 — HAND OFF",
        ):
            self.assertIn(heading, content, f"Missing heading: {heading}")

    def test_steps_appear_in_order(self):
        content = _skill_content()
        headings = [
            "## Step 1 — DETECT",
            "## Step 2 — CREDENTIALS",
            "## Step 3 — CHECK",
            "## Step 4 — SELECT",
            "## Step 5 — APPLY",
            "## Step 6 — RUN",
            "## Step 7 — VERIFY",
            "## Step 8 — HAND OFF",
        ]
        positions = [content.index(h) for h in headings]
        self.assertEqual(positions, sorted(positions))

    def test_step_gates_load_references(self):
        content = _skill_content()
        self.assertIn('load_instana_skills(operation="get_reference", name="genai-instrumentation", path="detect-and-credentials.md")', content)
        self.assertIn('load_instana_skills(operation="get_reference", name="genai-instrumentation", path="apply-diff.md")', content)
        self.assertIn('load_instana_skills(operation="get_reference", name="genai-instrumentation", path="verify-telemetry.md")', content)


class TestMcpToolsUsed(unittest.TestCase):
    def test_tools_table_lists_required_tools(self):
        content = _skill_content()
        self.assertIn("manage_applications", content)
        self.assertIn("manage_infrastructure", content)
        self.assertIn("get_all_traces", content)
        self.assertIn("get_trace_details", content)
        self.assertIn("get_grouped_calls_metrics", content)
        self.assertIn("get_entity_groups", content)

    def test_no_external_mcp_server_required(self):
        self.assertIn("requires no external MCP server", _skill_content())


class TestDetectAndCredentialsReference(unittest.TestCase):
    def setUp(self):
        self.content = _reference_content("detect-and-credentials.md")

    def test_lock_files_excluded(self):
        self.assertIn("Do **not** include lock files", self.content)

    def test_source_file_cap(self):
        self.assertIn("capped at the first 200", self.content)

    def test_framework_detection_table(self):
        for fw in ("langgraph", "langchain", "crewai", "openai-agents"):
            self.assertIn(f"`{fw}`", self.content)

    def test_provider_detection_table(self):
        for provider in ("groq", "anthropic", "watsonx", "bedrock", "deepseek", "sagemaker", "gemini", "openai"):
            self.assertIn(f"`{provider}`", self.content)

    def test_provider_specific_before_openai(self):
        self.assertLess(self.content.index("| `groq` |"), self.content.index("| `openai` |"))
        self.assertLess(self.content.index("| `anthropic` |"), self.content.index("| `openai` |"))

    def test_detection_flags(self):
        for flag in ("alreadyInstrumented", "usingTraceloop", "serviceName", "parentSpanRequired"):
            self.assertIn(flag, self.content)

    def test_env_var_presence(self):
        for name in (
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_HEADERS",
            "OTEL_RESOURCE_ATTRIBUTES",
            "envVarsPresent",
            "envVarsMissing",
        ):
            self.assertIn(name, self.content)

    def test_provider_credential_vars(self):
        for name in (
            "OPENAI_API_KEY",
            "GROQ_API_KEY",
            "ANTHROPIC_API_KEY",
            "WATSONX_APIKEY",
            "WATSONX_PROJECT_ID",
            "AWS_ACCESS_KEY_ID",
            "DEEPSEEK_API_KEY",
            "GOOGLE_API_KEY",
        ):
            self.assertIn(name, self.content)

    def test_python_only_guard(self):
        self.assertIn("UNSUPPORTED_STACK", self.content)
        self.assertIn("Only Python is currently supported", self.content)

    def test_mode_and_transport_decision(self):
        self.assertIn("`agentless`", self.content)
        self.assertIn("`agent`", self.content)
        self.assertIn("`grpc`", self.content)
        self.assertIn("`http`", self.content)

    def test_endpoint_resolution_rules(self):
        self.assertIn("never ask for a region colour", self.content)
        self.assertIn("What is your Instana OTLP acceptor endpoint?", self.content)
        self.assertIn("Do **not** append `/v1/traces`", self.content)

    def test_security_rules(self):
        self.assertIn("PLACEHOLDER_PATTERN", self.content)
        self.assertIn("Please do not share credential values in chat", self.content)


class TestApplyDiffReference(unittest.TestCase):
    def setUp(self):
        self.content = _reference_content("apply-diff.md")

    def test_both_transport_templates(self):
        self.assertIn("opentelemetry.exporter.otlp.proto.<http|grpc>.trace_exporter", self.content)
        self.assertIn("opentelemetry.exporter.otlp.proto.<http|grpc>.metric_exporter", self.content)

    def test_instana_plugin_genai_in_resource(self):
        self.assertIn('"INSTANA_PLUGIN": "genai"', self.content)

    def test_never_double_instrument(self):
        self.assertIn("do NOT add a second one", self.content)

    def test_traceloop_ordering_rule(self):
        self.assertIn("Critical ordering rule", self.content)
        self.assertIn("MUST be called before importing", self.content)
        self.assertIn("traceloop-sdk==0.62.3", self.content)

    def test_credential_scan_before_diff(self):
        self.assertIn("## §5b. Credential scan", self.content)
        self.assertIn("base64", self.content)
        self.assertIn("Hex strings", self.content)
        self.assertIn("Diff scan failed", self.content)

    def test_approval_options(self):
        self.assertIn("(yes / no / modify)", self.content)


class TestVerifyTelemetryReference(unittest.TestCase):
    def setUp(self):
        self.content = _reference_content("verify-telemetry.md")

    def test_verify_phases_present(self):
        for phase in ("Phase 7-A", "Phase 7-B", "Phase 7-C", "Phase 7-D"):
            self.assertIn(phase, self.content)

    def test_service_filter_structure(self):
        self.assertIn('"name": "service.name"', self.content)
        self.assertIn('"entity": "DESTINATION"', self.content)
        self.assertIn('"entity": "SOURCE"', self.content)

    def test_content_probes_and_disable_prompt(self):
        for key in ("gen_ai.input.messages", "gen_ai.output.messages", "traceloop.entity.input", "traceloop.entity.output"):
            self.assertIn(key, self.content)
        self.assertIn("Keep capturing it? (keep / disable)", self.content)
        self.assertNotIn("not checked", self.content)

    def test_call_probe_uses_not_applicable_entity(self):
        self.assertIn('"operator": "NOT_EMPTY", "entity": "NOT_APPLICABLE"', self.content)
        self.assertNotIn('"groupbyTag": "otel.', self.content)

    def test_alias_resolution_table(self):
        for legacy, canonical in (
            ("gen_ai.usage.prompt_tokens", "gen_ai.usage.input_tokens"),
            ("gen_ai.usage.completion_tokens", "gen_ai.usage.output_tokens"),
            ("gen_ai.system", "gen_ai.provider.name"),
            ("traceloop.association_properties", "gen_ai.conversation.id"),
            ("gen_ai.prompt", "gen_ai.content.prompt"),
            ("gen_ai.completion", "gen_ai.content.completion"),
        ):
            self.assertIn(legacy, self.content)
            self.assertIn(canonical, self.content)

    def test_level_rank_ordering(self):
        for level in ("Basic", "LLM Calls", "Agent", "Conversation"):
            self.assertIn(level, self.content)

    def test_evaluation_block_fields(self):
        for field in (
            "verification_level",
            "achieved_level",
            "target_level",
            "detected_convention",
            "missing_fields",
            "metrics_received",
            "prompt_text_detected",
            "diagnosis",
            "timestamp",
        ):
            self.assertIn(field, self.content)

    def test_step_8_pass_handoff(self):
        self.assertIn("Step 8 — HAND OFF (PASS)", self.content)
        self.assertIn("Instana GenAI Instrumentation — VERIFIED", self.content)

    def test_http_error_guidance(self):
        self.assertIn("## HTTP Error Guidance", self.content)
        self.assertIn("401", self.content)
        self.assertIn("403", self.content)
        self.assertIn("415", self.content)


class TestIterateReference(unittest.TestCase):
    def setUp(self):
        self.content = _reference_content("iterate.md")

    def test_iterate_step_heading(self):
        self.assertIn("## Step 7a — ITERATE", self.content)

    def test_remediation_catalog_covers_canonical_fields(self):
        for field in (
            "gen_ai.operation.name",
            "gen_ai.provider.name",
            "gen_ai.request.model",
            "gen_ai.usage.input_tokens",
            "gen_ai.usage.output_tokens",
            "gen_ai.agent.name",
            "gen_ai.tool.name",
            "gen_ai.conversation.id",
        ):
            self.assertIn(field, self.content, f"Remediation missing for {field}")

    def test_targeted_fix_diff(self):
        self.assertIn("targeted fix diff", self.content)
        self.assertIn("only the specific missing attributes", self.content)

    def test_bounded_failure_template(self):
        self.assertIn("Bounded failure", self.content)
        self.assertIn("Instana GenAI Instrumentation — BOUNDED FAILURE", self.content)


class TestSkillBodyGuards(unittest.TestCase):
    def test_no_plaintext_secret_patterns(self):
        """SKILL.md and references must not embed plaintext secrets."""
        for text in [_skill_content()] + [
            _reference_content(f) for f in ("detect-and-credentials.md", "apply-diff.md", "verify-telemetry.md", "iterate.md")
        ]:
            # Filter out frontmatter content_hash line
            lines = [ln for ln in text.splitlines() if not ln.startswith("content_hash:")]
            clean_text = "\n".join(lines)
            for token in re.findall(r"[A-Za-z0-9+/]{40,}", clean_text):
                # Allow standard URLs or words with hyphens/slashes
                if "http" not in token and "opentelemetry" not in token:
                    self.fail(f"Possible embedded credential-like token: {token[:16]}...")

    def test_no_unresolved_merge_markers(self):
        for text in [_skill_content()] + [
            _reference_content(f) for f in ("detect-and-credentials.md", "apply-diff.md", "verify-telemetry.md", "iterate.md")
        ]:
            for marker in ("<<<<<<<", ">>>>>>>"):
                self.assertNotIn(marker, text)

    def test_code_fences_balanced(self):
        self.assertEqual(_skill_content().count("```") % 2, 0, "Unbalanced code fences in SKILL.md")
        for ref_name in ("detect-and-credentials.md", "apply-diff.md", "verify-telemetry.md", "iterate.md"):
            ref_text = _reference_content(ref_name)
            self.assertEqual(ref_text.count("```") % 2, 0, f"Unbalanced code fences in {ref_name}")


class TestInstructionsAreExecutable(unittest.TestCase):
    """Guards against wrong instructions, not just missing prose."""

    def test_nonexistent_apis_not_recommended(self):
        content = _all_content()
        self.assertNotIn("TRACELOOP_DISABLE_BATCH", content)
        self.assertNotIn("enrich_token_usage", content)
        self.assertNotIn("INSTANA_ALLOW_INSECURE", content)

    def test_python_snippets_compile(self):
        for name in ("apply-diff.md", "iterate.md"):
            for block in re.findall(r"```python\n(.*?)```", _reference_content(name), re.S):
                if ("<" in block and ">" in block) or "..." in block:  # template placeholders / pseudo-code
                    continue
                compile(block, name, "exec")

    def test_json_snippets_parse(self):
        for block in re.findall(r"```json\n(.*?)```", _reference_content("verify-telemetry.md"), re.S):
            if "<" in block and ">" in block:  # template placeholders
                continue
            json.loads(block)

    def _run_credential_scan(self, diff_text):
        section = _reference_content("apply-diff.md")
        section = section[section.index("## §5b"):section.index("## §5c")]
        cmd = re.search(r"```bash\n(.*?)```", section, re.S).group(1)
        cmd = cmd.replace("<insert unified diff here>", diff_text.rstrip("\n"))
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)

    def test_credential_scan_ignores_placeholders_and_context(self):
        diff = (
            "+OTEL_EXPORTER_OTLP_HEADERS=x-instana-key=<set-by-developer>\n"
            "+# TODO wire this up\n"
            '+    api_key=os.environ.get("OPENAI_API_KEY"),\n'
            "+max_tokens = 1000\n"
            " context sk-abcdefghijklmnopqrstuvwxyz123456\n"
        )
        result = self._run_credential_scan(diff)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("CLEAN", result.stdout)

    def test_credential_scan_flags_added_secrets_without_echoing_them(self):
        secret = "sk-abcdefghijklmnopqrstuvwxyz123456"
        diff = f"+ok = 1\n+OPENAI_API_KEY={secret}\n+deadbeefdeadbeefdeadbeefdeadbeef\n"
        result = self._run_credential_scan(diff)
        self.assertEqual(result.returncode, 1)
        self.assertIn("FLAGGED lines: 2, 3", result.stdout)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_env_status_command_never_prints_secret_values(self):
        section = _reference_content("detect-and-credentials.md")
        cmd = re.search(r"```bash\n(\{ cat \.env.*?)```", section, re.S).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".env").write_text(
                "OPENAI_API_KEY=sk-secretvalue123\n"
                "OTEL_EXPORTER_OTLP_HEADERS=x-instana-key=topsecretkey\n"
                "OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-http-blue-saas.instana.io:443\n"
                "GROQ_API_KEY=your-key-here\n"
            )
            result = subprocess.run(cmd, shell=True, cwd=tmp, capture_output=True, text=True, check=False, env={"PATH": os.environ["PATH"]})
        out = result.stdout
        self.assertNotIn("sk-secretvalue123", out)
        self.assertNotIn("topsecretkey", out)
        self.assertIn("OPENAI_API_KEY=real", out)
        self.assertIn("GROQ_API_KEY=placeholder", out)
        self.assertIn("OTEL_EXPORTER_OTLP_HEADERS=real (has x-instana-key)", out)
        self.assertIn("OTEL_EXPORTER_OTLP_ENDPOINT=real https://otlp-http-blue-saas.instana.io:443", out)

    def test_untrusted_content_clause_present(self):
        self.assertIn("never instructions", _skill_content())

    def test_all_providers_collected_not_first_match(self):
        content = _reference_content("detect-and-credentials.md")
        self.assertIn("collect ALL matches", content)
        self.assertNotIn("Record the first matching provider", content)


class TestSkillsProvider(unittest.TestCase):
    """Verify the skills provider can mount the skills directory and serve the skill."""

    def _provider(self, **kwargs):
        from fastmcp.server.providers.skills import SkillsDirectoryProvider

        return SkillsDirectoryProvider(roots=SKILLS_DIR, reload=False, **kwargs)

    def test_provider_serves_skill_md(self):
        provider = self._provider(supporting_files="resources")
        uris = [str(r.uri) for r in asyncio.run(provider.list_resources())]
        self.assertTrue(
            any(SKILL_NAME in u and "SKILL.md" in u for u in uris),
            f"skill://{SKILL_NAME}/SKILL.md not found in {uris}",
        )

    def test_provider_serves_references(self):
        provider = self._provider(supporting_files="resources")
        uris = [str(r.uri) for r in asyncio.run(provider.list_resources())]
        for ref in ("detect-and-credentials.md", "apply-diff.md", "verify-telemetry.md", "iterate.md"):
            self.assertTrue(any(ref in u for u in uris), f"{ref} not found in {uris}")


class TestLoadToolByteIdentity(unittest.TestCase):
    """load_instana_skills output must equal the SKILL.md content, byte for byte."""

    def test_load_tool_returns_skill(self):
        from src.skills.skills_tool import SkillsMCPTool

        tool = SkillsMCPTool("token", "https://example.com")
        result = asyncio.run(tool.load_instana_skills("get", SKILL_NAME))
        self.assertEqual(result["skill"], SKILL_NAME)
        self.assertEqual(result["content"], _skill_content())
        self.assertEqual(
            sorted(result["references"]),
            ["apply-diff.md", "detect-and-credentials.md", "iterate.md", "verify-telemetry.md"],
        )

    def test_skill_is_listed(self):
        from src.skills.skills_tool import SkillsMCPTool

        tool = SkillsMCPTool("token", "https://example.com")
        result = asyncio.run(tool.load_instana_skills("list"))
        entry = next((s for s in result["skills"] if s["id"] == SKILL_NAME), None)
        self.assertIsNotNone(entry, f"{SKILL_NAME} not listed by load_instana_skills")
        self.assertEqual(entry["name"], SKILL_NAME)
        self.assertTrue(entry["description"])

    def test_load_reference(self):
        from src.skills.skills_tool import SkillsMCPTool

        tool = SkillsMCPTool("token", "https://example.com")
        result = asyncio.run(
            tool.load_instana_skills("get_reference", SKILL_NAME, "detect-and-credentials.md")
        )
        self.assertEqual(result["skill"], SKILL_NAME)
        self.assertEqual(result["reference"], "detect-and-credentials.md")
        self.assertEqual(result["content"], _reference_content("detect-and-credentials.md"))


if __name__ == "__main__":
    unittest.main()
