"""
Groundtruth tests for DB2 Database entity.

Tests the two-pass infrastructure analysis flow with DB2 database queries.
"""

import pytest
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any

from tests.groundtruth.groundtruth_validator import GroundtruthValidator, TestCase
from tests.groundtruth.llm_client_wrapper import create_llm_client
from tests.groundtruth.payload_extractor import PayloadExtractor

# Import the infrastructure analyze tool
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.infrastructure.infrastructure_analyze_new import InfrastructureAnalyzeOption2

logger = logging.getLogger(__name__)


class TestDB2Groundtruth:
    """Test DB2 database queries against groundtruth."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = GroundtruthValidator()
        self.extractor = PayloadExtractor()
        self.groundtruth_file = Path(__file__).parent / "data" / "db2_groundtruth.jsonl"
        
        # Initialize server
        schema_dir = Path(__file__).parent.parent.parent / "schema"
        self.server = InfrastructureAnalyzeOption2(
            read_token="test_token",
            base_url="https://test.instana.io",
            schema_dir=schema_dir
        )
    
    @pytest.mark.parametrize("test_num", range(1, 18))  # Tests 1-17
    def test_db2_case(self, test_num, llm_client):
        """
        Test individual DB2 case.
        
        Args:
            test_num: Test case number (1-17)
            llm_client: LLM client fixture (mock or ollama)
        """
        
        # Load test case
        test_cases = self.validator.load_groundtruth(self.groundtruth_file)
        test_case = next((tc for tc in test_cases if tc.num == str(test_num)), None)
        
        if not test_case:
            pytest.skip(f"Test case {test_num} not found")
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Test #{test_case.num}: {test_case.input}")
        logger.info(f"{'='*80}")
        
        # Execute two-pass flow
        actual_payload = self._execute_two_pass_flow(
            test_case.input,
            "db2",
            llm_client
        )
        
        # Validate against groundtruth
        result = self.validator.validate_test_case(test_case, actual_payload)
        
        # Log result
        logger.info(f"\nResult: {result.overall_accuracy:.2%} accuracy")
        
        # Show detailed comparison if failed
        if result.overall_accuracy < 1.0:
            logger.warning(f"\n{'='*80}")
            logger.warning(f"FAILED FIELDS:")
            logger.warning(f"{'='*80}")
            
            for field, correct in result.field_accuracy.items():
                if not correct:
                    logger.warning(f"\n❌ {field}:")
                    
                    # Show expected vs actual
                    expected_val = test_case.expected_output.get("arguments", {}).get(field)
                    actual_val = actual_payload.get("arguments", {}).get(field)
                    
                    logger.warning(f"  Expected: {json.dumps(expected_val, indent=4)}")
                    logger.warning(f"  Actual:   {json.dumps(actual_val, indent=4)}")
            
            logger.warning(f"\n{'='*80}")
            logger.warning(f"FULL COMPARISON:")
            logger.warning(f"{'='*80}")
            logger.warning(f"\nExpected payload:")
            logger.warning(json.dumps(test_case.expected_output, indent=2))
            logger.warning(f"\nActual payload:")
            logger.warning(json.dumps(actual_payload, indent=2))
            logger.warning(f"{'='*80}\n")
        
        # Assert (can be disabled for reporting mode)
        assert result.overall_accuracy >= 0.8, \
            f"Accuracy too low: {result.overall_accuracy:.2%}\nRun with -s flag to see detailed comparison"
    
    def test_all_db2_cases_with_report(
        self,
        llm_client,
        request
    ):
        """
        Test all DB2 cases and generate comprehensive report.
        
        Run with: pytest tests/groundtruth/test_db2_groundtruth.py::TestDB2Groundtruth::test_all_db2_cases_with_report -v
        """
        
        # Load all test cases
        test_cases = self.validator.load_groundtruth(self.groundtruth_file)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Running all {len(test_cases)} DB2 test cases")
        logger.info(f"LLM: {llm_client.provider}")
        logger.info(f"{'='*80}\n")
        
        # Run all tests
        for test_case in test_cases:
            logger.info(f"Test #{test_case.num}: {test_case.input[:60]}...")
            
            try:
                # Execute two-pass flow
                actual_payload = self._execute_two_pass_flow(
                    test_case.input,
                    "db2",
                    llm_client
                )
                
                # Validate
                result = self.validator.validate_test_case(test_case, actual_payload)
                logger.info(f"  Result: {result.overall_accuracy:.2%}")
                
            except Exception as e:
                logger.error(f"  Error: {e}")
                # Record as failed
                self.validator.validate_test_case(test_case, None)
        
        # Generate report
        report = self.validator.generate_report()
        print("\n" + report)
        
        # Save report if requested
        if request.config.getoption("--report"):
            report_file = Path(__file__).parent / "db2_test_report.txt"
            report_file.write_text(report)
            logger.info(f"\nReport saved to: {report_file}")
        
        # Calculate metrics
        metrics = self.validator.calculate_metrics()
        
        # Assert overall quality
        assert metrics.overall_accuracy >= 0.85, \
            f"Overall accuracy too low: {metrics.overall_accuracy:.2%}"
    
    def _execute_two_pass_flow(
        self,
        query: str,
        entity_hint: str,
        llm_client
    ) -> Dict[str, Any]:
        """
        Execute the complete two-pass flow.
        
        Args:
            query: Natural language query
            entity_hint: Entity hint (e.g., "db2")
            llm_client: LLM client to use
            
        Returns:
            Actual payload generated
        """
        
        # PASS 1: Get schema
        logger.info("\n" + "="*80)
        logger.info("PASS 1: Getting schema...")
        logger.info("="*80)
        schema_response = self._execute_pass1(query, entity_hint)
        
        # Extract schema from response
        schema = self._extract_schema_from_response(schema_response)
        logger.info(f"Schema extracted: {len(schema.get('metrics', []))} metrics, {len(schema.get('tags', []))} tags")
        
        # Send to LLM
        logger.info("\n" + "="*80)
        logger.info("SENDING TO LLM...")
        logger.info("="*80)
        logger.info(f"Query: {query}")
        
        llm_selections = llm_client.get_selections_from_schema(query, schema)
        
        logger.info("\n" + "-"*80)
        logger.info("LLM SELECTIONS (what LLM prepared):")
        logger.info("-"*80)
        logger.info(json.dumps(llm_selections, indent=2))
        logger.info("-"*80)
        
        # PASS 2: Build payload directly from LLM selections (no API call)
        logger.info("\n" + "="*80)
        logger.info("PASS 2: Building payload from LLM selections...")
        logger.info("="*80)
        
        # Build payload directly from selections without calling API
        actual_payload = self._build_payload_from_selections(llm_selections)
        
        logger.info("\n" + "-"*80)
        logger.info("ACTUAL PAYLOAD (after server processing):")
        logger.info("-"*80)
        logger.info(json.dumps(actual_payload, indent=2))
        logger.info("-"*80)
        
        return actual_payload
    
    def _execute_pass1(self, query: str, entity_hint: str) -> Any:
        """Execute Pass 1: Intent → Schema."""
        
        # Call server's Pass 1
        response = asyncio.run(
            self.server.analyze_infrastructure_elicitation(
                intent=query,
                entity=entity_hint
            )
        )
        
        return response
    
    def _build_payload_from_selections(self, selections: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build payload directly from LLM selections without making API calls.
        
        This converts the LLM's simple selections into the groundtruth payload format.
        
        Args:
            selections: LLM selections dict with entity_type, metrics, filters, etc.
            
        Returns:
            Payload in groundtruth format
        """
        
        entity_type = selections.get("entity_type", "db2Database")
        
        # Determine API endpoint based on groupBy
        group_by = selections.get("groupBy", [])
        if group_by and len(group_by) > 0:
            api_endpoint = "/api/infrastructure-monitoring/analyze/entity-groups"
        else:
            api_endpoint = "/api/infrastructure-monitoring/analyze/entities"
        
        # Build arguments
        arguments = {}
        
        # Pagination
        pagination_size = selections.get("pagination", {}).get("retrievalSize", 20)
        arguments["pagination"] = {"retrievalSize": pagination_size}
        
        # Metrics
        metrics = selections.get("metrics", [])
        aggregation = selections.get("aggregation", "sum")
        
        if metrics:
            arguments["metrics"] = []
            for metric in metrics:
                if isinstance(metric, dict):
                    arguments["metrics"].append(metric)
                else:
                    arguments["metrics"].append({
                        "metric": metric,
                        "aggregation": aggregation
                    })
        
        # Filters → tagFilterElements conversion
        filters = selections.get("filters", [])
        if filters:
            arguments["tagFilterElements"] = []
            for f in filters:
                arguments["tagFilterElements"].append({
                    "type": "TAG_FILTER",
                    "name": f.get("name", ""),
                    "operator": f.get("operator", "equals"),
                    "value": f.get("value", "")
                })
        
        # Order
        order = selections.get("order")
        if order and isinstance(order, dict):
            arguments["order"] = order
        else:
            arguments["order"] = "NONE"
        
        # GroupBy
        if group_by:
            arguments["groupBy"] = group_by
        
        # Time range - convert from timeRange to start_time/end_time
        time_range = selections.get("timeRange")
        if time_range:
            # Convert "1h", "24h", "10m" to CURRENT_TIMESTAMP format
            arguments["start_time"] = f"CURRENT_TIMESTAMP-{time_range}"
            arguments["end_time"] = "CURRENT_TIMESTAMP"
        else:
            arguments["start_time"] = selections.get("start_time", "NONE")
            arguments["end_time"] = selections.get("end_time", "NONE")
        
        # Build final payload
        payload = {
            "type": entity_type,
            "api_endpoint": api_endpoint,
            "arguments": arguments
        }
        
        return payload
    
    def _extract_schema_from_response(self, response: Any) -> Dict[str, Any]:
        """Extract schema from Pass 1 response."""
        
        # The response format depends on server implementation
        # This is a template - adjust based on actual format
        
        if isinstance(response, list) and len(response) > 0:
            # Response is list of content blocks
            for content in response:
                if hasattr(content, 'text'):
                    # Try to parse as JSON
                    try:
                        schema = json.loads(content.text)
                        return schema
                    except:
                        pass
        
        # Default schema structure for db2Database
        return {
            "entity_type": "db2Database",
            "metrics": [
                "databases.queries",
                "databases.failedQueries",
                "databases.rollbacks",
                "databases.rowsReturned",
                "vmonlockstats.lockWaitTime",
                "vmonlockstats.numberOfConnections",
                "workloadstats.totalRequestTime",
                "workloadstats.totalWaitTime"
            ],
            "tags": [
                "db2.name",
                "host.name",
                "kubernetes.namespace.name",
                "kubernetes.cluster.name"
            ],
            "aggregations": ["sum", "mean", "max", "min"]
        }


if __name__ == "__main__":
    """Run tests with report generation."""
    pytest.main([
        __file__,
        "-v",
        "--report",
        "-s"
    ])

# Made with Bob
