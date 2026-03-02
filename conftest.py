"""
Top-level pytest configuration
"""

import sys

import pytest

pytest_plugins = ["pytest_asyncio"]

# Keys polluted at module-level by tests/application/test_application_metrics.py
# and tests/application/test_application_settings.py. We save originals here
# (before any test module is imported) and restore them after collection so
# that tests/core/ and tests/prompts/ can import the real modules.
_POLLUTED_KEYS = [
    "mcp",
    "mcp.types",
    "fastmcp",
    "fastmcp.server",
    "fastmcp.server.dependencies",
    "pydantic",
    "instana_client",
    "instana_client.api",
    "instana_client.api.application_metrics_api",
    "instana_client.api.application_settings_api",
    "instana_client.api_client",
    "instana_client.configuration",
    "instana_client.models",
    "instana_client.models.get_application_metrics",
    "instana_client.models.get_applications",
    "instana_client.models.get_endpoints",
    "instana_client.models.get_services",
    "instana_client.models.application_config",
    "instana_client.models.endpoint_config",
    "instana_client.models.manual_service_config",
    "instana_client.models.new_application_config",
    "instana_client.models.new_manual_service_config",
    "instana_client.models.service_config",
    "src.prompts",
    "src.core",
    "src.core.utils",
]

_saved_modules: dict = {}


def pytest_configure(config):
    """Save sys.modules state before any test module is imported."""
    for key in _POLLUTED_KEYS:
        _saved_modules[key] = sys.modules.get(key)


def pytest_collection_finish(session):
    """Restore sys.modules after all test modules have been collected.

    This runs after collection (when application test modules have been
    imported and have polluted sys.modules) but before any test executes.
    Tests/core/ and tests/prompts/ modules are already imported by this
    point, so restoring sys.modules here only affects future imports
    (e.g., lazy imports inside test functions).
    """
    for key, original in _saved_modules.items():
        if original is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = original
