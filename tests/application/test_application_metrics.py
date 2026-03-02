"""
Unit tests for the ApplicationMetricsMCPTools class.

Only tests for active (non-commented-out) methods are included.
Methods get_application_metrics, get_endpoints_metrics, and get_services_metrics
have been removed from source and their tests are removed accordingly.
"""

import asyncio
import logging
import os
import sys
import unittest
from functools import wraps
from unittest.mock import MagicMock, patch


# Create a null handler that will discard all log messages
class NullHandler(logging.Handler):
    def emit(self, record):
        pass


# Configure root logger to use ERROR level and disable propagation
logging.basicConfig(level=logging.ERROR)

# Get the application logger and replace its handlers
app_logger = logging.getLogger('src.application.application_metrics')
app_logger.handlers = []
app_logger.addHandler(NullHandler())
app_logger.propagate = False  # Prevent logs from propagating to parent loggers

# Add src to path before any imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Create a mock for the with_header_auth decorator
def mock_with_header_auth(api_class, allow_mock=False):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Just pass the API client directly
            kwargs['api_client'] = self.metrics_api
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator


# Set up mock classes (defined outside patch.dict so they persist after import)
mock_mcp = MagicMock()
mock_mcp_types = MagicMock()
mock_tool_annotations = MagicMock()
mock_mcp_types.ToolAnnotations = mock_tool_annotations

mock_instana_client = MagicMock()
mock_instana_api = MagicMock()
mock_app_metrics_api_mod = MagicMock()
mock_instana_configuration = MagicMock()
mock_instana_api_client = MagicMock()
mock_instana_models = MagicMock()
mock_get_app_metrics_mod = MagicMock()
mock_get_applications_mod = MagicMock()
mock_get_endpoints_mod = MagicMock()
mock_get_services_mod = MagicMock()
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
mock_app_metrics_api = MagicMock()
mock_get_app_metrics = MagicMock()
mock_get_applications = MagicMock()
mock_get_endpoints = MagicMock()
mock_get_services = MagicMock()

# Add __name__ attribute to mock classes
mock_app_metrics_api.__name__ = "ApplicationMetricsApi"
mock_get_app_metrics.__name__ = "GetApplicationMetrics"
mock_get_applications.__name__ = "GetApplications"
mock_get_endpoints.__name__ = "GetEndpoints"
mock_get_services.__name__ = "GetServices"

mock_instana_configuration.Configuration = mock_configuration
mock_instana_api_client.ApiClient = mock_api_client
mock_app_metrics_api_mod.ApplicationMetricsApi = mock_app_metrics_api
mock_get_app_metrics_mod.GetApplicationMetrics = mock_get_app_metrics
mock_get_applications_mod.GetApplications = mock_get_applications
mock_get_endpoints_mod.GetEndpoints = mock_get_endpoints
mock_get_services_mod.GetServices = mock_get_services

# Mock src.prompts (needed by application_metrics.py: from src.prompts import mcp)
mock_src_prompts = MagicMock()

# Mock src.core and src.core.utils modules
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
    'instana_client.api.application_metrics_api': mock_app_metrics_api_mod,
    'instana_client.configuration': mock_instana_configuration,
    'instana_client.api_client': mock_instana_api_client,
    'instana_client.models': mock_instana_models,
    'instana_client.models.get_application_metrics': mock_get_app_metrics_mod,
    'instana_client.models.get_applications': mock_get_applications_mod,
    'instana_client.models.get_endpoints': mock_get_endpoints_mod,
    'instana_client.models.get_services': mock_get_services_mod,
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
        from src.application.application_metrics import ApplicationMetricsMCPTools


class TestApplicationMetricsMCPTools(unittest.TestCase):
    """Test the ApplicationMetricsMCPTools class.

    Only tests for active methods are included. The following methods were
    removed from source and their tests are omitted:
      - get_application_metrics
      - get_endpoints_metrics
      - get_services_metrics
    """

    def setUp(self):
        """Set up test fixtures"""
        mock_configuration.reset_mock()
        mock_api_client.reset_mock()
        mock_app_metrics_api.reset_mock()

        self.mock_configuration = mock_configuration
        self.mock_api_client = mock_api_client
        self.app_metrics_api = MagicMock()

        self.read_token = "test_token"
        self.base_url = "https://test.instana.io"

        self.client = ApplicationMetricsMCPTools(read_token=self.read_token, base_url=self.base_url)
        self.client.metrics_api = self.app_metrics_api

        patcher = patch('src.application.application_metrics.logger')
        self.mock_logger = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        pass

    def test_init(self):
        """Test that the client is initialized with the correct values"""
        self.assertEqual(self.client.read_token, self.read_token)
        self.assertEqual(self.client.base_url, self.base_url)

    def test_get_application_data_metrics_v2_elicitation_when_no_params(self):
        """Test get_application_data_metrics_v2 returns elicitation_needed when called without required params.

        The method requires 'metrics' and recommends 'time_frame'. When called without
        these, it returns an elicitation_needed response instead of calling the API.
        """
        result = asyncio.run(self.client.get_application_data_metrics_v2())

        self.assertIn("elicitation_needed", result)
        self.assertTrue(result["elicitation_needed"])
        self.assertIn("missing_parameters", result)
        self.assertIn("metrics", result["missing_parameters"])

    def test_get_application_data_metrics_v2_with_params(self):
        """Test get_application_data_metrics_v2 with required parameters calls the API"""
        mock_result = MagicMock()
        mock_result.to_dict = MagicMock(return_value={"metrics": "test_data"})
        self.client.metrics_api.get_application_data_metrics_v2 = MagicMock(return_value=mock_result)

        metrics = [{"metric": "calls", "aggregation": "SUM"}]
        time_frame = {"from": 1000, "to": 2000}
        application_id = "app123"
        service_id = "svc456"
        endpoint_id = "ep789"

        result = asyncio.run(self.client.get_application_data_metrics_v2(
            metrics=metrics,
            time_frame=time_frame,
            application_id=application_id,
            service_id=service_id,
            endpoint_id=endpoint_id
        ))

        self.client.metrics_api.get_application_data_metrics_v2.assert_called_once()
        self.assertEqual(result, {"metrics": "test_data"})

    def test_get_application_data_metrics_v2_error_handling(self):
        """Test get_application_data_metrics_v2 error handling when API raises exception"""
        self.client.metrics_api.get_application_data_metrics_v2 = MagicMock(
            side_effect=Exception("Test error")
        )

        # Must provide required params to bypass elicitation and reach the API call
        result = asyncio.run(self.client.get_application_data_metrics_v2(
            metrics=[{"metric": "calls", "aggregation": "SUM"}],
            time_frame={"from": 1000, "to": 2000}
        ))

        self.assertIn("error", result)
        self.assertIn("Failed to get application data metrics", result["error"])
        self.assertIn("Test error", result["error"])

    def test_get_application_data_metrics_v2_dict_result(self):
        """Test get_application_data_metrics_v2 with a result that's already a dict"""
        mock_result = {"metrics": "test_data"}
        self.client.metrics_api.get_application_data_metrics_v2 = MagicMock(return_value=mock_result)

        # Must provide required params to bypass elicitation and reach the API call
        result = asyncio.run(self.client.get_application_data_metrics_v2(
            metrics=[{"metric": "calls", "aggregation": "SUM"}],
            time_frame={"from": 1000, "to": 2000}
        ))

        self.assertEqual(result, {"metrics": "test_data"})


if __name__ == '__main__':
    unittest.main()
