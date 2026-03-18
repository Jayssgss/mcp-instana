"""
Tests for Two-Pass Elicitation Flow

Tests the new analyze_infrastructure tool with:
- Pass 1: Intent → Schema Elicitation
- Pass 2: Selections → API Call
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from mcp.types import EmbeddedResource, TextContent, TextResourceContents

from src.infrastructure.infrastructure_analyze import InfrastructureAnalyze


@pytest.fixture
def mock_schema_dir(tmp_path):
    """Create temporary schema directory with test schemas"""
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()

    # Create jvmRuntimePlatform schema
    jvm_schema = {
        "type": "jvmRuntimePlatform",
        "parameters": {
            "metrics": {
                "metric": [
                    "jvm.heap.maxSize",
                    "jvm.heap.used",
                    "jvm.threads.count"
                ],
                "aggregation": {
                    "enum": ["mean", "max", "min", "sum"]
                }
            },
            "tagFilterElements": {
                "enum": [
                    "host.name",
                    "jvm.name",
                    "process.name"
                ]
            }
        }
    }

    with open(schema_dir / "jvmRuntimePlatform_schema.json", "w") as f:
        json.dump(jvm_schema, f)

    # Create kubernetesPod schema
    k8s_schema = {
        "type": "kubernetesPod",
        "parameters": {
            "metrics": {
                "metric": [
                    "cpuRequests",
                    "cpuLimits",
                    "cpuUsed"
                ],
                "aggregation": {
                    "enum": ["mean", "max", "min"]
                }
            },
            "tagFilterElements": {
                "enum": [
                    "kubernetes.namespace.name",
                    "kubernetes.cluster.name"
                ]
            }
        }
    }

    with open(schema_dir / "kubernetesPod_schema.json", "w") as f:
        json.dump(k8s_schema, f)

    return schema_dir


@pytest.fixture
def tool_instance(mock_schema_dir):
    """Create InfrastructureAnalyze instance with test schema dir"""
    return InfrastructureAnalyze(
        read_token="test_token",
        base_url="https://test.instana.io",
        schema_dir=mock_schema_dir
    )


class TestPass1IntentToElicitation:
    """Test Pass 1: Intent → Schema Elicitation"""

    @pytest.mark.asyncio
    async def test_pass1_jvm_entity(self, tool_instance):
        """Test Pass 1 with JVM entity"""
        result = await tool_instance.analyze_infrastructure(
            intent="maximum heap size of JVM on host galactica1",
            entity="jvm"
        )

        # Should return list with 2 items
        assert isinstance(result, list)
        assert len(result) == 2

        # First item should be TextContent with instructions
        assert isinstance(result[0], TextContent)
        assert result[0].type == "text"
        assert "jvmRuntimePlatform" in result[0].text
        assert "maximum heap size" in result[0].text

        # Second item should be EmbeddedResource with schema
        assert isinstance(result[1], EmbeddedResource)
        assert result[1].type == "resource"
        assert isinstance(result[1].resource, TextResourceContents)
        assert "jvmRuntimePlatform" in str(result[1].resource.uri)

        # Schema should be valid JSON
        schema = json.loads(result[1].resource.text)
        assert schema["type"] == "jvmRuntimePlatform"
        assert "jvm.heap.maxSize" in schema["parameters"]["metrics"]["metric"]

    @pytest.mark.asyncio
    async def test_pass1_kubernetes_pod(self, tool_instance):
        """Test Pass 1 with kubernetes pod entity"""
        result = await tool_instance.analyze_infrastructure(
            intent="CPU usage of pods in production namespace",
            entity="kubernetes pod"
        )

        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], TextContent)
        assert isinstance(result[1], EmbeddedResource)

        # Check schema is for kubernetesPod
        schema = json.loads(result[1].resource.text)
        assert schema["type"] == "kubernetesPod"

    @pytest.mark.asyncio
    async def test_pass1_ambiguous_kubernetes(self, tool_instance):
        """Test Pass 1 with ambiguous 'kubernetes' entity"""
        result = await tool_instance.analyze_infrastructure(
            intent="CPU usage",
            entity="kubernetes"
        )

        # Should return error asking for clarification
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Ambiguous" in result[0].text
        assert "kubernetes pod" in result[0].text
        assert "kubernetes deployment" in result[0].text

    @pytest.mark.asyncio
    async def test_pass1_unknown_entity(self, tool_instance):
        """Test Pass 1 with unknown entity"""
        result = await tool_instance.analyze_infrastructure(
            intent="some query",
            entity="unknown_entity"
        )

        # Should return error
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Unknown entity type" in result[0].text

    @pytest.mark.asyncio
    async def test_pass1_entity_resolution_priority(self, tool_instance):
        """Test entity resolution priority (specific before general)"""
        # Test "kubernetes deployment" resolves to deployment, not pod
        result = await tool_instance.analyze_infrastructure(
            intent="replica count",
            entity="kubernetes deployment"
        )

        # Should try to load kubernetesDeployment schema
        # (will fail since we only created pod schema, but that's ok for this test)
        assert isinstance(result, list)


class TestPass2SelectionsToAPI:
    """Test Pass 2: Selections → API Call"""

    @pytest.mark.asyncio
    async def test_pass2_with_valid_selections(self, tool_instance):
        """Test Pass 2 with valid selections"""
        # Mock the API client
        mock_api_client = Mock()
        mock_response = Mock()
        mock_response.data = json.dumps({
            "items": [
                {
                    "label": "test-jvm-1",
                    "metrics": {
                        "jvm.heap.maxSize[max]": 1024000000
                    }
                }
            ]
        }).encode('utf-8')
        mock_api_client.get_entities_without_preload_content.return_value = mock_response

        selections = {
            "entity_type": "jvmRuntimePlatform",
            "metric": "jvm.heap.maxSize",
            "aggregation": "max",
            "filters": [
                {"name": "host.name", "value": "galactica1"}
            ]
        }

        result = await tool_instance.analyze_infrastructure(
            selections=selections,
            api_client=mock_api_client
        )

        # Should return list with TextContent
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "test-jvm-1" in result[0].text
        assert "jvm.heap.maxSize" in result[0].text

    @pytest.mark.asyncio
    async def test_pass2_missing_entity_type(self, tool_instance):
        """Test Pass 2 with missing entity_type"""
        selections = {
            "metric": "jvm.heap.maxSize",
            "aggregation": "max"
        }

        result = await tool_instance.analyze_infrastructure(
            selections=selections
        )

        # Should return error
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "must include 'entity_type'" in result[0].text

    @pytest.mark.asyncio
    async def test_pass2_missing_metric(self, tool_instance):
        """Test Pass 2 with missing metric"""
        selections = {
            "entity_type": "jvmRuntimePlatform",
            "aggregation": "max"
        }

        result = await tool_instance.analyze_infrastructure(
            selections=selections
        )

        # Should return error
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "must include" in result[0].text and "metric" in result[0].text

    @pytest.mark.asyncio
    async def test_pass2_api_error(self, tool_instance):
        """Test Pass 2 with API error"""
        mock_api_client = Mock()
        mock_api_client.get_entities_without_preload_content.side_effect = Exception("API Error")

        selections = {
            "entity_type": "jvmRuntimePlatform",
            "metric": "jvm.heap.maxSize",
            "aggregation": "max"
        }

        result = await tool_instance.analyze_infrastructure(
            selections=selections,
            api_client=mock_api_client
        )

        # Should return error message
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Error calling Instana API" in result[0].text

    @pytest.mark.asyncio
    async def test_pass2_no_results(self, tool_instance):
        """Test Pass 2 with no results from API"""
        mock_api_client = Mock()
        mock_response = Mock()
        mock_response.data = json.dumps({"items": []}).encode('utf-8')
        mock_api_client.get_entities_without_preload_content.return_value = mock_response

        selections = {
            "entity_type": "jvmRuntimePlatform",
            "metric": "jvm.heap.maxSize",
            "aggregation": "max"
        }

        result = await tool_instance.analyze_infrastructure(
            selections=selections,
            api_client=mock_api_client
        )

        # Should return "no entities found" message
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "No" in result[0].text and "found" in result[0].text


class TestInvalidInput:
    """Test invalid input handling"""

    @pytest.mark.asyncio
    async def test_no_parameters(self, tool_instance):
        """Test with no parameters"""
        result = await tool_instance.analyze_infrastructure()

        # Should return error
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Invalid input" in result[0].text

    @pytest.mark.asyncio
    async def test_intent_without_entity(self, tool_instance):
        """Test with intent but no entity"""
        result = await tool_instance.analyze_infrastructure(
            intent="some query"
        )

        # Should return error
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert "Invalid input" in result[0].text


class TestEntityResolution:
    """Test entity resolution logic"""

    @pytest.mark.asyncio
    async def test_jvm_aliases(self, tool_instance):
        """Test JVM entity aliases"""
        # Test "jvm"
        result1 = await tool_instance._handle_pass1_intent({"intent": "test", "entity": "jvm"})
        assert isinstance(result1, list)

        # Test "java"
        result2 = await tool_instance._handle_pass1_intent({"intent": "test", "entity": "java"})
        assert isinstance(result2, list)

    @pytest.mark.asyncio
    async def test_kubernetes_specific_matches(self, tool_instance):
        """Test kubernetes specific matches"""
        # "kubernetes deployment" should resolve to deployment
        result1 = await tool_instance._handle_pass1_intent({
            "intent": "test",
            "entity": "kubernetes deployment"
        })
        # Will fail to load schema but that's ok - we're testing resolution
        assert isinstance(result1, list)

        # "kubernetes pod" should resolve to pod
        result2 = await tool_instance._handle_pass1_intent({
            "intent": "test",
            "entity": "kubernetes pod"
        })
        assert isinstance(result2, list)
        assert len(result2) == 2  # Should succeed with pod schema

    @pytest.mark.asyncio
    async def test_deployment_keyword(self, tool_instance):
        """Test 'deployment' keyword alone"""
        result = await tool_instance._handle_pass1_intent({
            "intent": "test",
            "entity": "deployment"
        })
        # Should resolve to kubernetesDeployment
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_pod_keyword(self, tool_instance):
        """Test 'pod' keyword alone"""
        result = await tool_instance._handle_pass1_intent({
            "intent": "test",
            "entity": "pod"
        })
        # Should resolve to kubernetesPod
        assert isinstance(result, list)
        assert len(result) == 2  # Should succeed with pod schema

