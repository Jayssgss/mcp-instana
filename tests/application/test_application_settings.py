"""
Unit tests for the ApplicationSettingsMCPTools class.

Tests focus on the public execute_settings_operation method which routes
to private internal methods. Tests for the private methods themselves
are removed since they are internal implementation details.
"""

import asyncio
import logging
import os
import sys
import unittest
from functools import wraps
from unittest.mock import AsyncMock, MagicMock, patch


# Create a null handler that will discard all log messages
class NullHandler(logging.Handler):
    def emit(self, record):
        pass


# Configure root logger to use ERROR level and disable propagation
logging.basicConfig(level=logging.ERROR)

# Get the application logger and replace its handlers
app_logger = logging.getLogger('src.application.application_settings')
app_logger.handlers = []
app_logger.addHandler(NullHandler())
app_logger.propagate = False

# Add src to path before any imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Create a mock for the with_header_auth decorator
def mock_with_header_auth(api_class, allow_mock=False):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            kwargs['api_client'] = self.settings_api
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator


# Set up mock modules (defined outside patch.dict so they persist after import)
mock_mcp = MagicMock()
mock_mcp_types = MagicMock()
mock_tool_annotations = MagicMock()
mock_mcp_types.ToolAnnotations = mock_tool_annotations

mock_instana_client = MagicMock()
mock_instana_api = MagicMock()
mock_settings_api_mod = MagicMock()
mock_instana_api_client = MagicMock()
mock_instana_configuration = MagicMock()
mock_instana_models = MagicMock()
mock_app_config_mod = MagicMock()
mock_endpoint_config_mod = MagicMock()
mock_manual_service_config_mod = MagicMock()
mock_new_app_config_mod = MagicMock()
mock_new_manual_service_config_mod = MagicMock()
mock_service_config_mod = MagicMock()
mock_fastmcp = MagicMock()
mock_fastmcp_server = MagicMock()
mock_fastmcp_deps = MagicMock()
mock_pydantic = MagicMock()

# Mock the get_http_headers function
mock_get_http_headers = MagicMock(return_value={})
mock_fastmcp_deps.get_http_headers = mock_get_http_headers

# Set up mock classes
mock_configuration = MagicMock()
mock_api_client = MagicMock()
mock_settings_api = MagicMock()
mock_application_config = MagicMock()
mock_endpoint_config = MagicMock()
mock_manual_service_config = MagicMock()
mock_new_application_config = MagicMock()
mock_new_manual_service_config = MagicMock()
mock_service_config = MagicMock()

# Add __name__ attribute to mock classes
mock_settings_api.__name__ = "ApplicationSettingsApi"
mock_application_config.__name__ = "ApplicationConfig"
mock_endpoint_config.__name__ = "EndpointConfig"
mock_manual_service_config.__name__ = "ManualServiceConfig"
mock_new_application_config.__name__ = "NewApplicationConfig"
mock_new_manual_service_config.__name__ = "NewManualServiceConfig"
mock_service_config.__name__ = "ServiceConfig"

mock_instana_configuration.Configuration = mock_configuration
mock_instana_api_client.ApiClient = mock_api_client
mock_instana_api.ApplicationSettingsApi = mock_settings_api
mock_instana_models.ApplicationConfig = mock_application_config
mock_instana_models.EndpointConfig = mock_endpoint_config
mock_instana_models.ManualServiceConfig = mock_manual_service_config
mock_instana_models.NewApplicationConfig = mock_new_application_config
mock_instana_models.NewManualServiceConfig = mock_new_manual_service_config
mock_instana_models.ServiceConfig = mock_service_config
mock_instana_models.TagFilter = MagicMock()
mock_instana_models.TagFilterExpression = MagicMock()

# Mock src.prompts
mock_src_prompts = MagicMock()

# Mock src.core and src.core.utils
mock_src_core = MagicMock()
mock_src_core_utils = MagicMock()


class MockBaseInstanaClient:
    def __init__(self, read_token: str, base_url: str):
        self.read_token = read_token
        self.base_url = base_url


mock_src_core_utils.BaseInstanaClient = MockBaseInstanaClient
mock_src_core_utils.register_as_tool = lambda *args, **kwargs: lambda func: func
mock_src_core_utils.with_header_auth = mock_with_header_auth

# Build the full mocks dict for patch.dict
_mocks = {
    'mcp': mock_mcp,
    'mcp.types': mock_mcp_types,
    'instana_client': mock_instana_client,
    'instana_client.api': mock_instana_api,
    'instana_client.api.application_settings_api': mock_settings_api_mod,
    'instana_client.api_client': mock_instana_api_client,
    'instana_client.configuration': mock_instana_configuration,
    'instana_client.models': mock_instana_models,
    'instana_client.models.application_config': mock_app_config_mod,
    'instana_client.models.endpoint_config': mock_endpoint_config_mod,
    'instana_client.models.manual_service_config': mock_manual_service_config_mod,
    'instana_client.models.new_application_config': mock_new_app_config_mod,
    'instana_client.models.new_manual_service_config': mock_new_manual_service_config_mod,
    'instana_client.models.service_config': mock_service_config_mod,
    'fastmcp': mock_fastmcp,
    'fastmcp.server': mock_fastmcp_server,
    'fastmcp.server.dependencies': mock_fastmcp_deps,
    'pydantic': mock_pydantic,
    'src.prompts': mock_src_prompts,
    'src.core': mock_src_core,
    'src.core.utils': mock_src_core_utils,
}

# Import the class under test with sys.modules mocked.
# patch.dict restores sys.modules after the with-block exits, so other
# test modules (tests/core/, tests/prompts/) can import the real modules.
with patch.dict(sys.modules, _mocks):
    with patch('src.core.utils.with_header_auth', mock_with_header_auth):
        from src.application.application_settings import ApplicationSettingsMCPTools


class TestApplicationSettingsMCPTools(unittest.TestCase):
    """Test the ApplicationSettingsMCPTools class.

    Tests focus on execute_settings_operation routing. Private methods
    (_get_all_applications_configs, _add_application_config, etc.) are
    internal implementation details and not tested directly.
    """

    def setUp(self):
        """Set up test fixtures"""
        mock_configuration.reset_mock()
        mock_api_client.reset_mock()
        mock_settings_api.reset_mock()

        self.mock_configuration = mock_configuration
        self.mock_api_client = mock_api_client
        self.settings_api = mock_settings_api

        self.read_token = "test_token"
        self.base_url = "https://test.instana.io"

        self.patcher = patch('src.core.utils.with_header_auth', mock_with_header_auth)
        self.patcher.start()

        self.client = ApplicationSettingsMCPTools(read_token=self.read_token, base_url=self.base_url)
        self.client.settings_api = mock_settings_api

        patcher = patch('src.application.application_settings.debug_print')
        self.mock_debug_print = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.patcher.stop()

    def test_init(self):
        """Test that the client is initialized with the correct values"""
        self.assertEqual(self.client.read_token, self.read_token)
        self.assertEqual(self.client.base_url, self.base_url)

    def test_execute_settings_operation_application_get_all(self):
        """Test execute_settings_operation routes application/get_all correctly"""
        expected = [{"id": "app1", "label": "My App"}]
        self.client._get_all_applications_configs = AsyncMock(return_value=expected)

        result = asyncio.run(self.client.execute_settings_operation(
            operation="get_all",
            resource_subtype="application"
        ))

        self.client._get_all_applications_configs.assert_called_once()
        self.assertEqual(result, expected)

    def test_execute_settings_operation_application_get(self):
        """Test execute_settings_operation routes application/get correctly"""
        expected = {"id": "app1", "label": "My App"}
        self.client._get_application_config = AsyncMock(return_value=expected)

        result = asyncio.run(self.client.execute_settings_operation(
            operation="get",
            resource_subtype="application",
            id="app1"
        ))

        self.client._get_application_config.assert_called_once_with("app1", None)
        self.assertEqual(result, expected)

    def test_execute_settings_operation_application_create(self):
        """Test execute_settings_operation routes application/create correctly"""
        expected = {"id": "new-app", "label": "New App"}
        self.client._add_application_config = AsyncMock(return_value=expected)
        payload = {"label": "New App"}

        result = asyncio.run(self.client.execute_settings_operation(
            operation="create",
            resource_subtype="application",
            payload=payload
        ))

        self.client._add_application_config.assert_called_once_with(payload, None)
        self.assertEqual(result, expected)

    def test_execute_settings_operation_application_delete(self):
        """Test execute_settings_operation routes application/delete correctly"""
        expected = {"message": "Deleted"}
        self.client._delete_application_config = AsyncMock(return_value=expected)

        result = asyncio.run(self.client.execute_settings_operation(
            operation="delete",
            resource_subtype="application",
            id="app1"
        ))

        self.client._delete_application_config.assert_called_once_with("app1", None)
        self.assertEqual(result, expected)

    def test_execute_settings_operation_service_order(self):
        """Test execute_settings_operation routes service/order correctly"""
        expected = {"message": "Ordered"}
        self.client._order_service_config = AsyncMock(return_value=expected)
        request_body = ["svc1", "svc2"]

        result = asyncio.run(self.client.execute_settings_operation(
            operation="order",
            resource_subtype="service",
            request_body=request_body
        ))

        self.client._order_service_config.assert_called_once_with(request_body, None)
        self.assertEqual(result, expected)

    def test_execute_settings_operation_manual_service_get_all(self):
        """Test execute_settings_operation routes manual_service/get_all correctly"""
        expected = [{"id": "ms1"}]
        self.client._get_all_manual_service_configs = AsyncMock(return_value=expected)

        result = asyncio.run(self.client.execute_settings_operation(
            operation="get_all",
            resource_subtype="manual_service"
        ))

        self.client._get_all_manual_service_configs.assert_called_once()
        self.assertEqual(result, expected)

    def test_execute_settings_operation_unsupported_returns_error(self):
        """Test execute_settings_operation returns error for unsupported operation/subtype"""
        result = asyncio.run(self.client.execute_settings_operation(
            operation="unknown_op",
            resource_subtype="unknown_type"
        ))

        self.assertIn("error", result)
        self.assertIn("unknown_op", result["error"])
        self.assertIn("unknown_type", result["error"])

    def test_execute_settings_operation_exception_handling(self):
        """Test execute_settings_operation handles exceptions gracefully"""
        self.client._get_all_applications_configs = AsyncMock(
            side_effect=Exception("API failure")
        )

        result = asyncio.run(self.client.execute_settings_operation(
            operation="get_all",
            resource_subtype="application"
        ))

        self.assertIn("error", result)
        self.assertIn("API failure", result["error"])


if __name__ == '__main__':
    unittest.main()
