"""Unit tests for the change-timeline MCP skill."""

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

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

SKILLS_DIR   = Path(__file__).parent.parent.parent / "src" / "skills"
SKILL_DIR    = SKILLS_DIR / "change-timeline"
SKILL_MD     = SKILL_DIR / "SKILL.md"
OUTPUT_SCHEMA = SKILL_DIR / "references" / "output-schema.md"


class TestSkillFiles(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}")

    def test_output_schema_exists(self):
        self.assertTrue(OUTPUT_SCHEMA.exists(), f"output-schema.md not found at {OUTPUT_SCHEMA}")

    def test_skill_md_non_empty(self):
        self.assertGreater(SKILL_MD.stat().st_size, 0)

    def test_output_schema_non_empty(self):
        self.assertGreater(OUTPUT_SCHEMA.stat().st_size, 0)


class TestSkillFrontmatter(unittest.TestCase):
    def _load(self):
        return SKILL_MD.read_text(encoding="utf-8")

    def test_yaml_frontmatter_present(self):
        content = self._load()
        self.assertTrue(content.startswith("---"), "SKILL.md must start with YAML front-matter '---'")

    def test_name_field_is_change_timeline(self):
        content = self._load()
        # Extract YAML front-matter block
        parts = content.split("---", 2)
        self.assertGreaterEqual(len(parts), 3, "Expected opening and closing '---' delimiters")
        frontmatter = parts[1]
        self.assertIn("name: change-timeline", frontmatter)

    def test_description_field_present(self):
        content = self._load()
        parts = content.split("---", 2)
        frontmatter = parts[1]
        self.assertIn("description:", frontmatter)

    def test_description_does_not_claim_fully_parallel_workflow(self):
        """Phase 1 is partly sequential; parallelism applies to the Phase 2 batch only."""
        frontmatter = self._load().split("---", 2)[1]
        self.assertNotIn("parallel smart router queries", frontmatter)
        self.assertIn("release markers", frontmatter)

    def test_description_length_and_content(self):
        """Frontmatter description is concise and covers core triggers and guardrails."""
        frontmatter = self._load().split("---", 2)[1]
        self.assertIn("what changed", frontmatter)
        self.assertIn("Kubernetes events", frontmatter)
        self.assertIn("Does NOT", frontmatter)

    def test_no_four_source_wording(self):
        """The skill has exactly 3 sources; no '4 sources' wording may remain."""
        content = self._load()
        self.assertNotIn("4 sources", content)
        self.assertNotIn("4 source", content)


class TestSkillDirectory(unittest.TestCase):
    def test_directory_name_matches_skill_name(self):
        """Directory name must equal the skill name (fastmcp keys off directory)."""
        self.assertEqual(SKILL_DIR.name, "change-timeline")


class TestSkillBodyGuards(unittest.TestCase):
    """Guard tests: SKILL.md must NOT mention Phase 2/3 tools (not yet registered)."""

    def _body(self):
        return SKILL_MD.read_text(encoding="utf-8")

    def test_no_compare_release_reference(self):
        self.assertNotIn(
            "compare_release", self._body(),
            "SKILL.md must not reference compare_release (Phase 2 tool not yet registered)"
        )

    def test_no_analyze_change_impact_reference(self):
        self.assertNotIn(
            "analyze_change_impact", self._body(),
            "SKILL.md must not reference analyze_change_impact (Phase 3 tool not yet registered)"
        )


class TestSkillsProvider(unittest.TestCase):
    """Verify the skills provider can mount the skills directory and serve the skill."""

    def test_provider_serves_skill_md(self):
        """SkillsDirectoryProvider should list skill://change-timeline/SKILL.md."""
        from fastmcp.server.providers.skills import SkillsDirectoryProvider

        provider = SkillsDirectoryProvider(roots=SKILLS_DIR, reload=False, supporting_files="resources")

        async def _run():
            resources = await provider.list_resources()
            uris = [str(r.uri) for r in resources]
            return uris

        uris = asyncio.run(_run())
        self.assertTrue(
            any("change-timeline" in u and "SKILL.md" in u for u in uris),
            f"skill://change-timeline/SKILL.md not found in {uris}"
        )

    def test_provider_serves_output_schema(self):
        """SkillsDirectoryProvider should list the output-schema.md supporting file."""
        from fastmcp.server.providers.skills import SkillsDirectoryProvider

        provider = SkillsDirectoryProvider(roots=SKILLS_DIR, reload=False, supporting_files="resources")

        async def _run():
            resources = await provider.list_resources()
            uris = [str(r.uri) for r in resources]
            return uris

        uris = asyncio.run(_run())
        self.assertTrue(
            any("output-schema" in u for u in uris),
            f"output-schema.md not found in skill resource list: {uris}"
        )

    def test_provider_reads_skill_md_content(self):
        """resources/read on skill://change-timeline/SKILL.md returns non-empty text."""
        from fastmcp.server.providers.skills import SkillsDirectoryProvider

        provider = SkillsDirectoryProvider(roots=SKILLS_DIR, reload=False)

        async def _run():
            resources = await provider.list_resources()
            skill_res = next(
                (r for r in resources if "change-timeline" in str(r.uri) and "SKILL.md" in str(r.uri)),
                None
            )
            if skill_res is None:
                return None
            # get_resource expects a string URI in fastmcp 3.4.7
            content = await provider.get_resource(str(skill_res.uri))
            return content

        content = asyncio.run(_run())
        self.assertIsNotNone(content, "Could not find or read skill://change-timeline/SKILL.md")


class TestLoadToolByteIdentity(unittest.TestCase):
    """Assert byte-identity: load_instana_skills output == resource content."""

    def test_load_tool_output_equals_resource_content(self):
        """Invariant: Load-tool output ≡ resource content, byte for byte."""
        from fastmcp.server.providers.skills import SkillsDirectoryProvider

        from src.skills.skills_tool import SkillsMCPTool

        tool = SkillsMCPTool("token", "https://example.com")
        result = asyncio.run(tool.load_instana_skills("get", "change-timeline"))

        provider = SkillsDirectoryProvider(roots=SKILLS_DIR, reload=False, supporting_files="resources")

        async def _read_resource():
            resource = await provider.get_resource("skill://change-timeline/SKILL.md")
            return await resource.read()

        resource_text = asyncio.run(_read_resource())

        self.assertIn("content", result)
        self.assertEqual(result["content"], resource_text)


class TestSkillHardeningInvariants(unittest.TestCase):
    """Regression tests that assert the hardened SKILL.md contract invariants are present.

    _content() returns SKILL.md combined with all references/*.md files so that
    invariants still hold after content is moved to on-demand reference files.
    """

    def _content(self):
        parts = [SKILL_MD.read_text(encoding="utf-8")]
        ref_dir = SKILL_DIR / "references"
        if ref_dir.is_dir():
            for ref in sorted(ref_dir.glob("*.md")):
                parts.append(ref.read_text(encoding="utf-8"))
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # ST1: Execution Contract header
    # ------------------------------------------------------------------
    def test_execution_contract_present(self):
        """SKILL.md MUST contain an Execution Contract section."""
        self.assertIn(
            "## Execution Contract",
            self._content(),
            "SKILL.md must contain '## Execution Contract' section (ST1)",
        )

    def test_phase1_is_required_not_optional(self):
        """Phase 1 heading MUST say REQUIRED, not Optional."""
        content = self._content()
        self.assertNotIn(
            "Phase 1 — Scope & Service Discovery (Optional)",
            content,
            "Phase 1 MUST NOT be labelled Optional — it must be REQUIRED (ST1)",
        )
        self.assertIn(
            "(REQUIRED)",
            content,
            "Phase 1 heading MUST contain '(REQUIRED)' (ST1)",
        )

    # ------------------------------------------------------------------
    # ST3: Guard Clauses section
    # ------------------------------------------------------------------
    def test_guard_clauses_section_present(self):
        """SKILL.md MUST contain a Guard Clauses section."""
        self.assertIn(
            "## Guard Clauses",
            self._content(),
            "SKILL.md must contain '## Guard Clauses' section (ST3)",
        )

    def test_guard_clause_must_not_language(self):
        """All 7 guard clauses MUST use RFC 2119 MUST NOT language."""
        content = self._content()
        # Each prohibition uses MUST NOT at least once per clause
        must_not_count = content.count("MUST NOT")
        self.assertGreaterEqual(
            must_not_count,
            7,
            f"Expected at least 7 'MUST NOT' occurrences in SKILL.md (one per guard clause), found {must_not_count} (ST3)",
        )

    def test_guard_clause_no_premature_negative(self):
        """Guard clause 1 MUST prohibit premature negative conclusions."""
        self.assertIn(
            "no changes found",
            self._content(),
            "SKILL.md must contain a guard clause referencing 'no changes found' (ST3 clause 1)",
        )

    def test_guard_clause_no_source_substitution(self):
        """Guard clause 4 MUST prohibit substituting get_events for k8s calls."""
        content = self._content()
        self.assertIn(
            "get_kubernetes_info_events",
            content,
            "Guard clause MUST mention get_kubernetes_info_events as a non-substitutable source (ST3 clause 4)",
        )

    # ------------------------------------------------------------------
    # ST2: Phase 2 [REQUIRED] labels and SCOPE RESTRICTION
    # ------------------------------------------------------------------
    def test_phase2_required_labels(self):
        """Phase 2 MUST label all 3 sources as [REQUIRED]."""
        content = self._content()
        required_count = content.count("[REQUIRED]")
        self.assertGreaterEqual(
            required_count,
            3,
            f"Expected at least 3 '[REQUIRED]' labels in SKILL.md (one per Phase 2 source), found {required_count} (ST2)",
        )

    def test_phase2_scope_restriction_present(self):
        """Phase 2 MUST contain a SCOPE RESTRICTION block."""
        self.assertIn(
            "SCOPE RESTRICTION",
            self._content(),
            "SKILL.md must contain 'SCOPE RESTRICTION' block in Phase 2 (ST2)",
        )

    def test_phase2_scope_restriction_forbids_manage_applications(self):
        """SCOPE RESTRICTION MUST explicitly forbid manage_applications."""
        self.assertIn(
            "manage_applications",
            self._content(),
            "SKILL.md SCOPE RESTRICTION must mention manage_applications as forbidden (ST2)",
        )

    def test_completion_gate_present(self):
        """Phase 2 MUST contain a COMPLETION GATE clause."""
        self.assertIn(
            "COMPLETION GATE",
            self._content(),
            "SKILL.md must contain 'COMPLETION GATE' in Phase 2 (ST2)",
        )

    # ------------------------------------------------------------------
    # ST4: Structured synthesis template
    # ------------------------------------------------------------------
    def test_synthesis_template_slots_present(self):
        """Phase 3 MUST contain the 2 mandatory synthesis template slots and no removed slots."""
        content = self._content()
        for slot in ("Change Records Found", "Timeline"):
            self.assertIn(
                slot,
                content,
                f"SKILL.md Phase 3 synthesis template MUST contain slot '{slot}' (ST4)",
            )
        for removed in ("Sources Queried", "Caveats"):
            self.assertNotIn(
                removed,
                content,
                f"Phase 3 synthesis template MUST NOT contain removed slot '{removed}'",
            )

    def test_empty_timeline_guard_present(self):
        """Phase 3 MUST contain the empty-timeline guard clause."""
        self.assertIn(
            "none — all 3 sources queried and returned empty results",
            self._content(),
            "SKILL.md must contain the empty-timeline guard text (ST4)",
        )

    # ------------------------------------------------------------------
    # Guard clause 7: No heuristic entity association
    # ------------------------------------------------------------------
    def test_guard_clause_no_heuristic_entity_association(self):
        """Guard clause 7 MUST prohibit shared application perspective or unverified infrastructure events."""
        content = self._content()
        self.assertIn(
            "No heuristic entity association",
            content,
            "SKILL.md must contain a 'No heuristic entity association' guard clause (clause 7)",
        )
        self.assertIn(
            "All Services",
            content,
            "Guard clause 7 MUST reference 'All Services' as an example of shared perspective",
        )

    # ------------------------------------------------------------------
    # Phase 2 time parameter format
    # ------------------------------------------------------------------
    def test_phase2_epoch_ms_requirement(self):
        """Phase 2 MUST specify that from_time/to_time use epoch milliseconds."""
        content = self._content()
        self.assertIn(
            "epoch milliseconds",
            content,
            "SKILL.md Phase 2 MUST specify that time parameters use Unix epoch milliseconds (not natural-language strings)",
        )
        self.assertIn(
            "Natural-language strings",
            content,
            "SKILL.md Phase 2 MUST explicitly forbid natural-language time strings as from_time/to_time values",
        )

    # ------------------------------------------------------------------
    # ST3 clause 5: No hallucinated tools
    # ------------------------------------------------------------------
    def test_no_hallucinated_call_graph_api(self):
        """SKILL.md MUST NOT contain the hallucinated 'Call-graph API' text."""
        self.assertNotIn(
            "Call-graph API",
            self._content(),
            "SKILL.md must not reference 'Call-graph API' — this is a known hallucinated tool (ST3 clause 5)",
        )

    # ------------------------------------------------------------------
    # Guard clause 6: No unscoped attribution
    # ------------------------------------------------------------------
    def test_guard_clause_no_unscoped_attribution(self):
        """Guard clause 6 MUST prohibit presenting tenant-wide events as service-scoped findings."""
        content = self._content()
        self.assertIn(
            "No unscoped attribution",
            content,
            "SKILL.md must contain a 'No unscoped attribution' guard clause (clause 6)",
        )
        self.assertIn(
            "service_id",
            content,
            "Guard clause 6 MUST reference service_id as the required scope filter (clause 6)",
        )
        self.assertIn(
            "Out-of-scope events MUST be omitted from the output",
            content,
            "Guard clause 6 MUST direct out-of-scope events to be omitted from the output (clause 6)",
        )

    # ------------------------------------------------------------------
    # Application resolution support (new Phase 1 dual-resolution path)
    # ------------------------------------------------------------------
    def test_phase1_get_applications_documented(self):
        """Phase 1 MUST document get_applications as the application-resolution call."""
        self.assertIn(
            "get_applications",
            self._content(),
            "SKILL.md Phase 1 MUST mention get_applications for application perspective resolution",
        )

    def test_phase1_application_id_scope_noted(self):
        """Phase 1 MUST acknowledge application_id as a valid scope output."""
        self.assertIn(
            "application_id",
            self._content(),
            "SKILL.md Phase 1 MUST mention application_id as a valid resolved scope identifier",
        )

    def test_guard_clause3_phase_scoped_restriction(self):
        """Guard clause 3 MUST scope the manage_applications prohibition to Phase 2 and Phase 3."""
        content = self._content()
        self.assertIn(
            "Phase 2 or Phase 3",
            content,
            "Guard clause 3 MUST restrict manage_applications to Phase 2 and Phase 3 (not a blanket ban)",
        )
        self.assertIn(
            "Phase 1",
            content,
            "Guard clause 3 MUST name Phase 1 as where get_services/get_applications are permitted",
        )

    # ------------------------------------------------------------------
    # Phase 1: Cluster & Namespace Topology Discovery
    # ------------------------------------------------------------------
    def test_phase1_cluster_and_namespace_topology_discovery(self):
        """Phase 1 MUST discover both kubernetes.cluster.name and kubernetes.namespace.name."""
        content = self._content()
        self.assertIn(
            "kubernetes.cluster.name",
            content,
            "SKILL.md Phase 1 MUST discover kubernetes.cluster.name",
        )
        self.assertIn(
            "kubernetes.namespace.name",
            content,
            "SKILL.md Phase 1 MUST discover kubernetes.namespace.name",
        )
        self.assertIn(
            "kubernetes_cluster_name",
            content,
            "SKILL.md Phase 1 output MUST include kubernetes_cluster_name",
        )
        self.assertIn(
            "kubernetes_namespace_name",
            content,
            "SKILL.md Phase 1 output MUST include kubernetes_namespace_name",
        )

    def test_phase1_no_service_fanout_or_tag_catalog(self):
        """Phase 1 MUST forbid get_application_services and get_tag_catalog."""
        content = self._content()
        self.assertIn(
            "get_application_services",
            content,
            "SKILL.md MUST explicitly forbid get_application_services",
        )
        self.assertIn(
            "NO SERVICE FAN-OUT",
            content,
            "SKILL.md Phase 1 MUST contain NO SERVICE FAN-OUT guidance",
        )

    # ------------------------------------------------------------------
    # Phase 2: Exactly 4 Parallel Calls & Scoped Sources
    # ------------------------------------------------------------------
    def test_phase2_three_parallel_calls_contract(self):
        """Phase 2 MUST mandate up to 3 parallel tool calls with no per-service fan-out."""
        content = self._content()
        self.assertIn(
            "3 active sources",
            content,
            "SKILL.md Phase 2 MUST specify up to 3 active sources",
        )
        self.assertIn(
            "exactly 1 call",
            content,
            "SKILL.md Phase 2 MUST specify each source is queried with exactly 1 call",
        )
        self.assertIn(
            "NO per-service fan-out",
            content,
            "SKILL.md Phase 2 MUST explicitly state there is NO per-service fan-out",
        )

    def test_phase2_k8s_events_entity_label_scoping(self):
        """Phase 2 Source 3 MUST be scoped using entity_label with trailing slash when namespace-scoped."""
        content = self._content()
        self.assertIn(
            'get_kubernetes_info_events',
            content,
        )
        self.assertIn(
            'trailing slash',
            content,
            "SKILL.md Phase 2 MUST specify trailing slash scoping for namespace-scoped k8s calls",
        )

    def test_k8s_scope_mode_documented(self):
        """Phase 1 output MUST include explicit k8s_scope_mode."""
        content = self._content()
        self.assertIn("k8s_scope_mode", content)
        self.assertIn("namespace-scoped", content)
        self.assertIn("cluster-scoped", content)
        self.assertIn("unscoped", content)
        self.assertIn("non-kubernetes", content)

    def test_truncation_rules_distinguish_tool_and_api_caps(self):
        """Phase 2 MUST define separate tool cap and API cap truncation rules."""
        content = self._content()
        self.assertIn("Tool cap:", content)
        self.assertIn("API cap:", content)
        self.assertIn("10,000", content)

    # ------------------------------------------------------------------
    # Phase 3: Synthesis Template Structure
    # ------------------------------------------------------------------
    def test_phase3_synthesis_template_fields(self):
        """Phase 3 template MUST include the 3 change record categories and total, and no Scope slot."""
        content = self._content()
        self.assertIn("releases: N", content)
        self.assertIn("change_events: N", content)
        self.assertIn("kubernetes_info_events: N", content)
        self.assertIn("Total:", content)
        for removed in ("Target Entity:", "Underlying Kubernetes Cluster:", "Underlying Kubernetes Namespace:"):
            self.assertNotIn(removed, content, f"Removed Scope field {removed!r} must not appear")


class TestSkillMdAloneCarriesCriticalRules(unittest.TestCase):
    """Critical rules and load gates must be in SKILL.md itself.

    TestSkillHardeningInvariants reads SKILL.md plus every reference, so it cannot
    notice a rule that was moved out of SKILL.md into a file the model might never
    load.  These tests read SKILL.md only.
    """

    def setUp(self):
        self.md = SKILL_MD.read_text(encoding="utf-8")

    def _phase1_section(self):
        start = self.md.index("## Phase 1 ")
        end = self.md.index("## Phase 2 ")
        return self.md[start:end]

    # --- load gates -------------------------------------------------------
    def test_phase1_gate_names_reference_and_blocks_calls(self):
        section = self._phase1_section()
        self.assertIn("PHASE 1 GATE", section)
        self.assertIn(
            'load_instana_skills(operation="get_reference", name="change-timeline", '
            'path="phase1-call-params.md")',
            section,
        )
        self.assertIn("Do NOT issue `get_applications`, `get_services`", section)
        self.assertIn("Do NOT reconstruct the templates from memory", section)

    def test_phase1_gate_comes_before_phase1_output(self):
        section = self._phase1_section()
        self.assertLess(section.index("PHASE 1 GATE"), section.index("Phase 1 Output"))

    def test_phase2_gate_still_present(self):
        self.assertIn("Do NOT proceed to Step 3b until this reference is loaded", self.md)
        self.assertIn('path="phase2-k8s-events.md"', self.md)

    def test_phase3_gate_still_present(self):
        self.assertIn('path="output-schema.md"', self.md)
        self.assertIn("Do NOT fill any slot before this reference is loaded", self.md)

    def test_every_listed_reference_is_loaded_by_name_from_skill_md(self):
        for ref in ("phase1-call-params.md", "phase2-k8s-events.md", "output-schema.md"):
            self.assertIn(f'path="{ref}"', self.md, ref)

    # --- Phase 1 invariants -----------------------------------------------
    def test_phase1_invariants_block_present(self):
        self.assertIn("Phase 1 invariants", self._phase1_section())

    def test_exact_match_and_ambiguity_rules_in_skill_md(self):
        section = self._phase1_section()
        self.assertIn("Exact match wins", section)
        self.assertIn("without asking the user", section)
        self.assertIn("Ambiguity stops the run", section)
        self.assertIn("stop and ask the user to pick one", section)
        self.assertIn("do not proceed to Phase 2", section)

    def test_cluster_discovery_is_conditional_in_skill_md(self):
        section = self._phase1_section()
        self.assertIn("Cluster discovery is conditional", section)
        self.assertIn("zero Kubernetes groups", section)

    def test_non_kubernetes_requires_positive_evidence_in_skill_md(self):
        section = self._phase1_section()
        self.assertIn("needs positive evidence", section)
        self.assertIn("stays `unknown`/`unscoped`", section)

    def test_no_fanout_rule_in_phase1_of_skill_md(self):
        section = self._phase1_section()
        self.assertIn("No fan-out", section)
        for forbidden in ("get_application_services", "get_tag_catalog"):
            self.assertIn(forbidden, section, forbidden)
        self.assertIn("callers, or callees", section)

    # --- no dangling references -------------------------------------------
    def test_no_undefined_step_labels_in_skill_md(self):
        for label in ("Step B\u2032", "Step C\u2032", "Steps B\u2032", "B\u2032/C\u2032"):
            self.assertNotIn(label, self.md, f"{label!r} is defined only in a reference")

    def test_skill_md_stays_materially_smaller_than_before_the_split(self):
        # Before the reference split SKILL.md was 29,373 bytes.
        self.assertLess(len(self.md.encode("utf-8")), 22000)


if __name__ == "__main__":
    unittest.main()
