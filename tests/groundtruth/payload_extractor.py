"""
Payload Extractor for Groundtruth Testing.

Extracts and formats payloads from server responses for comparison
with groundtruth expected outputs.
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class PayloadExtractor:
    """Extracts payloads from server responses."""
    
    def __init__(self):
        """Initialize payload extractor."""
        pass
    
    def extract_payload_from_pass2_response(
        self,
        response: Any,
        entity_type: str
    ) -> Dict[str, Any]:
        """
        Extract payload from Pass 2 server response.
        
        The server's Pass 2 response contains the API call details.
        We need to extract and format it to match groundtruth structure.
        
        Args:
            response: Server response from Pass 2
            entity_type: Entity type (e.g., "db2Database")
            
        Returns:
            Payload dict in groundtruth format
        """
        
        # The response format depends on how the server returns data
        # This is a template - adjust based on actual response format
        
        payload = {
            "type": entity_type,
            "api_endpoint": self._extract_endpoint(response, entity_type),
            "arguments": self._extract_arguments(response)
        }
        
        logger.info(f"Extracted payload: {json.dumps(payload, indent=2)}")
        return payload
    
    def _extract_endpoint(self, response: Any, entity_type: str) -> str:
        """Extract API endpoint from response."""
        
        # Check if response has endpoint info
        if hasattr(response, 'endpoint'):
            return response.endpoint
        
        # Determine endpoint based on entity type and groupBy
        # This matches the groundtruth format
        if isinstance(response, dict):
            arguments = response.get('arguments', {})
            group_by = arguments.get('groupBy', [])
            
            if group_by and len(group_by) > 0:
                return "/api/infrastructure-monitoring/analyze/entity-groups"
            else:
                return "/api/infrastructure-monitoring/analyze/entities"
        
        # Default
        return "/api/infrastructure-monitoring/analyze/entities"
    
    def _extract_arguments(self, response: Any) -> Dict[str, Any]:
        """Extract arguments from response."""
        
        # If response is already a dict with arguments
        if isinstance(response, dict) and 'arguments' in response:
            return self._normalize_arguments(response['arguments'])
        
        # If response is an object, try to extract attributes
        if hasattr(response, 'arguments'):
            return self._normalize_arguments(response.arguments)
        
        # Try to extract from response structure
        # This depends on your server's response format
        logger.warning("Could not extract arguments from response")
        return {}
    
    def _normalize_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize arguments to match groundtruth format.
        
        The server might return arguments in a slightly different format
        than groundtruth expects. This normalizes them.
        """
        
        normalized = {}
        
        # Pagination
        if 'pagination' in arguments:
            normalized['pagination'] = arguments['pagination']
        else:
            normalized['pagination'] = {"retrievalSize": 20}
        
        # Metrics
        if 'metrics' in arguments:
            normalized['metrics'] = self._normalize_metrics(arguments['metrics'])
        else:
            normalized['metrics'] = []
        
        # Tag filters - convert from simple 'filters' to complex 'tagFilterElements'
        if 'tagFilterElements' in arguments:
            normalized['tagFilterElements'] = self._normalize_tag_filters(
                arguments['tagFilterElements']
            )
        elif 'filters' in arguments:
            # Convert from simplified format to tagFilterElements
            normalized['tagFilterElements'] = self._convert_filters_to_tag_elements(
                arguments['filters']
            )
        else:
            normalized['tagFilterElements'] = []
        
        # Order
        if 'order' in arguments and arguments['order']:
            normalized['order'] = arguments['order']
        else:
            normalized['order'] = "NONE"
        
        # GroupBy
        if 'groupBy' in arguments:
            normalized['groupBy'] = arguments['groupBy']
        else:
            normalized['groupBy'] = []
        
        # Time range
        if 'start_time' in arguments:
            normalized['start_time'] = arguments['start_time']
        else:
            normalized['start_time'] = "NONE"
        
        if 'end_time' in arguments:
            normalized['end_time'] = arguments['end_time']
        else:
            normalized['end_time'] = "NONE"
        
        return normalized
    
    def _normalize_metrics(self, metrics: List[Any]) -> List[Dict[str, str]]:
        """Normalize metrics to groundtruth format."""
        
        normalized = []
        
        for metric in metrics:
            if isinstance(metric, dict):
                # Already in correct format
                normalized.append({
                    "metric": metric.get("metric", ""),
                    "aggregation": metric.get("aggregation", "sum").lower()
                })
            elif isinstance(metric, str):
                # Just metric name, need to add aggregation
                normalized.append({
                    "metric": metric,
                    "aggregation": "sum"
                })
        
        return normalized
    
    def _normalize_tag_filters(
        self,
        tag_filters: List[Any]
    ) -> List[Dict[str, Any]]:
        """Normalize tag filters to groundtruth format."""
        
        normalized = []
        
        for filter_item in tag_filters:
            if isinstance(filter_item, dict):
                normalized.append({
                    "type": filter_item.get("type", "TAG_FILTER"),
                    "name": filter_item.get("name", ""),
                    "operator": filter_item.get("operator", "equals").lower(),
                    "value": filter_item.get("value", "")
                })
        
        return normalized
    
    def _convert_filters_to_tag_elements(
        self,
        filters: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        Convert simplified filters to tag filter elements.
        
        This is the key conversion:
        LLM output: filters: [{name, value}]
        Groundtruth: tagFilterElements: [{type, name, operator, value}]
        """
        
        tag_elements = []
        
        for filter_item in filters:
            # Get operator if specified, default to "equals"
            operator = filter_item.get("operator", "equals")
            
            tag_elements.append({
                "type": "TAG_FILTER",
                "name": filter_item.get("name", ""),
                "operator": operator,
                "value": filter_item.get("value", "")
            })
        
        return tag_elements

# Made with Bob
