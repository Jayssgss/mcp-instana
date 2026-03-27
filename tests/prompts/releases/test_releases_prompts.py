"""Tests for the ReleasesPrompts class."""
import unittest
from unittest.mock import MagicMock, patch

from src.prompts import PROMPT_REGISTRY
from src.prompts.releases.releases_prompts import ReleasesPrompts


class TestReleasesPrompts(unittest.TestCase):
    """Test cases for the ReleasesPrompts class."""

    # ========== Registration Tests ==========
    def test_get_all_releases_registered(self):
        """Test that get_all_releases is registered in the prompt registry."""
        # Check if any registry item wraps our function
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.get_all_releases
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found, "get_all_releases not found in registry")

    def test_get_release_registered(self):
        """Test that get_release is registered in the prompt registry."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.get_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found, "get_release not found in registry")

    def test_create_release_registered(self):
        """Test that create_release is registered in the prompt registry."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.create_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found, "create_release not found in registry")

    def test_update_release_registered(self):
        """Test that update_release is registered in the prompt registry."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.update_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found, "update_release not found in registry")

    def test_delete_release_registered(self):
        """Test that delete_release is registered in the prompt registry."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.delete_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found, "delete_release not found in registry")

    def test_analyze_application_performance_after_release_registered(self):
        """Test that analyze_application_performance_after_release is registered."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.analyze_application_performance_after_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found, "analyze_application_performance_after_release not found in registry")

    def test_check_incidents_after_release_registered(self):
        """Test that check_incidents_after_release is registered."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.check_incidents_after_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found, "check_incidents_after_release not found in registry")

    def test_analyze_kpi_evolution_after_release_registered(self):
        """Test that analyze_kpi_evolution_after_release is registered."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.analyze_kpi_evolution_after_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found, "analyze_kpi_evolution_after_release not found in registry")

    def test_all_prompts_registered(self):
        """Test that all prompts from get_prompts are in the registry."""
        prompts = ReleasesPrompts.get_prompts()
        for name, prompt_func in prompts:
            # Check if the function is wrapped in a staticmethod in the registry
            found = any(
                isinstance(item, staticmethod) and item.__func__ == prompt_func
                for item in PROMPT_REGISTRY
            )
            self.assertTrue(found, f"Prompt {name} not found in registry")

    # ========== get_prompts Method Tests ==========
    def test_get_prompts_returns_all_prompts(self):
        """Test that get_prompts returns all prompts defined in the class."""
        prompts = ReleasesPrompts.get_prompts()
        self.assertEqual(len(prompts), 8)
        expected_names = [
            'get_all_releases',
            'get_release',
            'create_release',
            'update_release',
            'delete_release',
            'analyze_application_performance_after_release',
            'check_incidents_after_release',
            'analyze_kpi_evolution_after_release'
        ]
        actual_names = [p[0] for p in prompts]
        self.assertEqual(actual_names, expected_names)

    def test_get_prompts_returns_list_of_tuples(self):
        """Test that get_prompts returns a list of tuples."""
        prompts = ReleasesPrompts.get_prompts()
        self.assertIsInstance(prompts, list)
        for item in prompts:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[0], str)
            self.assertIsNotNone(item[1])

    def test_get_prompts_order_is_consistent(self):
        """Test that get_prompts returns prompts in consistent order."""
        prompts1 = ReleasesPrompts.get_prompts()
        prompts2 = ReleasesPrompts.get_prompts()
        self.assertEqual([p[0] for p in prompts1], [p[0] for p in prompts2])

    # ========== Prompt Structure Tests ==========
    def test_get_all_releases_has_correct_name(self):
        """Test that get_all_releases has the correct name in get_prompts."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        self.assertIn('get_all_releases', names)

    def test_get_release_has_correct_name(self):
        """Test that get_release has the correct name in get_prompts."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        self.assertIn('get_release', names)

    def test_create_release_has_correct_name(self):
        """Test that create_release has the correct name in get_prompts."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        self.assertIn('create_release', names)

    def test_update_release_has_correct_name(self):
        """Test that update_release has the correct name in get_prompts."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        self.assertIn('update_release', names)

    def test_delete_release_has_correct_name(self):
        """Test that delete_release has the correct name in get_prompts."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        self.assertIn('delete_release', names)

    def test_analyze_application_performance_after_release_has_correct_name(self):
        """Test that analyze_application_performance_after_release has correct name."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        self.assertIn('analyze_application_performance_after_release', names)

    def test_check_incidents_after_release_has_correct_name(self):
        """Test that check_incidents_after_release has correct name."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        self.assertIn('check_incidents_after_release', names)

    def test_analyze_kpi_evolution_after_release_has_correct_name(self):
        """Test that analyze_kpi_evolution_after_release has correct name."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        self.assertIn('analyze_kpi_evolution_after_release', names)

    def test_prompts_have_function_prompt_wrapper(self):
        """Test that prompts are wrapped by the decorator."""
        prompts = ReleasesPrompts.get_prompts()
        for name, prompt_func in prompts:
            self.assertIsNotNone(prompt_func)
            # Check if wrapped in staticmethod in registry
            found = any(
                isinstance(item, staticmethod) and item.__func__ == prompt_func
                for item in PROMPT_REGISTRY
            )
            self.assertTrue(found, f"Prompt {name} not properly wrapped in registry")

    def test_prompt_registry_contains_all_prompts(self):
        """Test that all prompts are registered in PROMPT_REGISTRY."""
        prompts = ReleasesPrompts.get_prompts()
        self.assertEqual(len(prompts), 8)
        for name, prompt_func in prompts:
            found = any(
                isinstance(item, staticmethod) and item.__func__ == prompt_func
                for item in PROMPT_REGISTRY
            )
            self.assertTrue(found, f"Prompt {name} not in registry")

    def test_no_duplicate_prompts_in_registry(self):
        """Test that there are no duplicate prompts in the registry."""
        prompts = ReleasesPrompts.get_prompts()
        prompt_funcs = [p[1] for p in prompts]
        prompt_ids = [id(p) for p in prompt_funcs]
        self.assertEqual(len(prompt_ids), len(set(prompt_ids)))

    # ========== Prompt Content Tests ==========
    def test_get_all_releases_prompt_content(self):
        """Test that get_all_releases prompt contains expected content."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.get_all_releases
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found)

    def test_get_release_prompt_content(self):
        """Test that get_release prompt is properly registered."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.get_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found)

    def test_create_release_prompt_content(self):
        """Test that create_release prompt is properly registered."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.create_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found)

    def test_update_release_prompt_content(self):
        """Test that update_release prompt is properly registered."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.update_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found)

    def test_delete_release_prompt_content(self):
        """Test that delete_release prompt is properly registered."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.delete_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found)

    def test_analyze_application_performance_after_release_prompt_content(self):
        """Test that analyze_application_performance_after_release is registered."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.analyze_application_performance_after_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found)

    def test_check_incidents_after_release_prompt_content(self):
        """Test that check_incidents_after_release is registered."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.check_incidents_after_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found)

    def test_analyze_kpi_evolution_after_release_prompt_content(self):
        """Test that analyze_kpi_evolution_after_release is registered."""
        found = any(
            isinstance(item, staticmethod) and item.__func__ == ReleasesPrompts.analyze_kpi_evolution_after_release
            for item in PROMPT_REGISTRY
        )
        self.assertTrue(found)

    # ========== Prompt Count Tests ==========
    def test_correct_number_of_prompts(self):
        """Test that the correct number of prompts are defined."""
        prompts = ReleasesPrompts.get_prompts()
        self.assertEqual(len(prompts), 8, "Expected 8 prompts in ReleasesPrompts")

    def test_all_crud_operations_present(self):
        """Test that all CRUD operations have prompts."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        crud_operations = ['get_all_releases', 'get_release', 'create_release', 'update_release', 'delete_release']
        for operation in crud_operations:
            self.assertIn(operation, names, f"CRUD operation {operation} not found in prompts")

    def test_all_analysis_operations_present(self):
        """Test that all analysis operations have prompts."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        analysis_operations = [
            'analyze_application_performance_after_release',
            'check_incidents_after_release',
            'analyze_kpi_evolution_after_release'
        ]
        for operation in analysis_operations:
            self.assertIn(operation, names, f"Analysis operation {operation} not found in prompts")

    # ========== Prompt Uniqueness Tests ==========
    def test_prompt_names_are_unique(self):
        """Test that all prompt names are unique."""
        prompts = ReleasesPrompts.get_prompts()
        names = [p[0] for p in prompts]
        self.assertEqual(len(names), len(set(names)), "Duplicate prompt names found")

    def test_prompt_functions_are_unique(self):
        """Test that all prompt functions are unique."""
        prompts = ReleasesPrompts.get_prompts()
        funcs = [p[1] for p in prompts]
        func_ids = [id(f) for f in funcs]
        self.assertEqual(len(func_ids), len(set(func_ids)), "Duplicate prompt functions found")

    # ========== Integration Tests ==========
    def test_prompts_class_is_static(self):
        """Test that ReleasesPrompts class methods are static."""
        # All methods should be accessible without instantiation
        prompts = ReleasesPrompts.get_prompts()
        self.assertIsNotNone(prompts)
        self.assertGreater(len(prompts), 0)

    def test_prompts_can_be_retrieved_multiple_times(self):
        """Test that prompts can be retrieved multiple times consistently."""
        prompts1 = ReleasesPrompts.get_prompts()
        prompts2 = ReleasesPrompts.get_prompts()
        self.assertEqual(len(prompts1), len(prompts2))
        self.assertEqual([p[0] for p in prompts1], [p[0] for p in prompts2])


if __name__ == '__main__':
    unittest.main()

