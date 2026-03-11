"""
LLM Client Wrapper for Groundtruth Testing.

Supports:
- Ollama (local, free)
- Intelligent Mock (rule-based, free)
- IBM Bob (Instana-approved, requires API key)
- Mistral (when available via API)

External paid APIs (Claude, OpenAI) are disabled for testing.
"""

import os
import json
import logging
import re
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class LLMClientWrapper:
    """Wrapper for LLM communication in groundtruth testing."""
    
    # Allowed providers for testing
    # - mock: Rule-based intelligent mock (no API calls)
    # - ollama: Local LLM (free, requires ollama installed)
    # - bob: IBM Bob (Instana-approved, requires WATSONX_API_KEY)
    # - mistral: Mistral API (Instana-approved, requires MISTRAL_API_KEY)
    ALLOWED_PROVIDERS = ["ollama", "mock", "bob", "mistral"]
    
    def __init__(self, provider: str = "mock"):
        """
        Initialize LLM client.
        
        Args:
            provider: LLM provider ("ollama" or "mock" only)
        
        Raises:
            ValueError: If provider is not allowed
        """
        self.provider = provider.lower()
        
        # Enforce free providers only
        if self.provider not in self.ALLOWED_PROVIDERS:
            raise ValueError(
                f"Provider '{self.provider}' not allowed for testing. "
                f"Use one of: {', '.join(self.ALLOWED_PROVIDERS)}"
            )
        
        self._client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the appropriate LLM client."""
        if self.provider == "ollama":
            self._initialize_ollama()
        elif self.provider == "bob":
            self._initialize_bob()
        elif self.provider == "mistral":
            self._initialize_mistral()
        elif self.provider == "mock":
            # Use intelligent mock (no initialization needed)
            logger.info("Using Intelligent Mock LLM (rule-based)")
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _initialize_ollama(self):
        """Initialize Ollama client (local, free)."""
        try:
            import ollama
            self._client = ollama
            
            # Verify Ollama is running
            try:
                models = self._client.list()
                logger.info(f"Initialized Ollama client. Available models: {len(models.get('models', []))}")
            except Exception as e:
                logger.warning(f"Ollama may not be running: {e}")
                logger.warning("Make sure Ollama is installed and running: ollama serve")
                
        except ImportError:
            raise ImportError(
                "ollama package not installed. Install with:\n"
                "  pip install ollama\n"
                "Then install a model:\n"
                "  ollama pull llama2"
            )
    
    def _initialize_bob(self):
        """Initialize IBM Bob (watsonx) client."""
        api_key = os.getenv("WATSONX_API_KEY")
        project_id = os.getenv("WATSONX_PROJECT_ID")
        
        if not api_key or not project_id:
            raise ValueError(
                "WATSONX_API_KEY and WATSONX_PROJECT_ID environment variables required for Bob.\n"
                "Set them with:\n"
                "  export WATSONX_API_KEY='your-api-key'\n"
                "  export WATSONX_PROJECT_ID='your-project-id'"
            )
        
        try:
            from ibm_watsonx_ai import Credentials
            from ibm_watsonx_ai.foundation_models import ModelInference
            
            # Initialize credentials
            credentials = Credentials(
                api_key=api_key,
                url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
            )
            
            # Initialize model (default to granite-13b-chat-v2, IBM's Bob model)
            model_id = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-chat-v2")
            
            self._client = ModelInference(
                model_id=model_id,
                credentials=credentials,
                project_id=project_id
            )
            
            logger.info(f"✅ Initialized IBM Bob (watsonx) client with model: {model_id}")
            
        except ImportError:
            raise ImportError(
                "ibm-watsonx-ai package not installed. Install with:\n"
                "  pip install ibm-watsonx-ai"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize IBM Bob client: {e}")
    
    def _initialize_mistral(self):
        """Initialize Mistral API client."""
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError(
                "MISTRAL_API_KEY environment variable required for Mistral.\n"
                "Set it with: export MISTRAL_API_KEY='your-api-key'"
            )
        
        try:
            from mistralai.client import MistralClient
            
            self._client = MistralClient(api_key=api_key)
            logger.info("✅ Initialized Mistral API client")
            
        except ImportError:
            raise ImportError(
                "mistralai package not installed. Install with:\n"
                "  pip install mistralai"
            )
    
    def get_selections_from_schema(
        self,
        query: str,
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send query and schema to LLM, get selections dict.
        
        Args:
            query: Natural language query
            schema: Schema from Pass 1
            
        Returns:
            Selections dict with simplified 'filters' (not tagFilterElements)
        """
        if self.provider == "ollama":
            return self._get_selections_ollama(query, schema)
        elif self.provider == "bob":
            return self._get_selections_bob(query, schema)
        elif self.provider == "mistral":
            return self._get_selections_mistral(query, schema)
        elif self.provider == "mock":
            return self._get_selections_mock(query, schema)
        else:
            # Fallback to mock if provider is unknown
            logger.warning(f"Unknown provider '{self.provider}', falling back to mock")
            return self._get_selections_mock(query, schema)
    
    def _get_selections_ollama(
        self,
        query: str,
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get selections from Ollama (local, free)."""
        
        # Build prompt
        prompt = self._build_selection_prompt(query, schema)
        
        # Try models in order of preference: mistral > llama2
        models_to_try = ['mistral', 'llama2', 'llama3']
        
        for model in models_to_try:
            try:
                logger.info(f"Trying Ollama model: {model}")
                # Call Ollama
                response = self._client.chat(
                    model=model,
                    messages=[{
                        'role': 'user',
                        'content': prompt
                    }]
                )
                
                # Extract selections from response
                selections = self._parse_ollama_response(response)
                
                logger.info(f"✅ {model} selections: {json.dumps(selections, indent=2)}")
                return selections
                
            except Exception as e:
                logger.warning(f"❌ {model} failed: {e}")
                continue
        
        # All models failed, fall back to mock
        logger.warning("All Ollama models failed, falling back to intelligent mock")
        return self._get_selections_mock(query, schema)
    
    def _get_selections_ollama_single_model(
        self,
        query: str,
        schema: Dict[str, Any],
        model: str = 'mistral'
    ) -> Dict[str, Any]:
        """Get selections from Ollama using a specific model."""
        
        # Build prompt
        prompt = self._build_selection_prompt(query, schema)
        
        try:
            # Call Ollama
            response = self._client.chat(
                model=model,
                messages=[{
                    'role': 'user',
                    'content': prompt
                }]
            )
            
            # Extract selections from response
            selections = self._parse_ollama_response(response)
            
            logger.info(f"Ollama selections: {json.dumps(selections, indent=2)}")
            return selections
            
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            logger.warning("Falling back to intelligent mock")
            return self._get_selections_mock(query, schema)
    def _get_selections_bob(self, query: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Get selections from IBM Bob (watsonx)."""
        
        # Build prompt
        prompt = self._build_selection_prompt(query, schema)
        
        try:
            logger.info("Calling IBM Bob (watsonx)...")
            
            # Call watsonx
            response = self._client.generate_text(
                prompt=prompt,
                params={
                    "max_new_tokens": 1000,
                    "temperature": 0.1,  # Low temperature for consistent results
                    "top_p": 0.95,
                    "top_k": 50
                }
            )
            
            # Extract selections from response
            selections = self._parse_watsonx_response(response)
            
            logger.info(f"✅ IBM Bob selections: {json.dumps(selections, indent=2)}")
            return selections
            
        except Exception as e:
            logger.error(f"❌ IBM Bob error: {e}")
            logger.warning("Falling back to intelligent mock")
            return self._get_selections_mock(query, schema)
    
    def _get_selections_mistral(self, query: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Get selections from Mistral API."""
        
        # Build prompt
        prompt = self._build_selection_prompt(query, schema)
        
        try:
            logger.info("Calling Mistral API...")
            
            # Call Mistral
            response = self._client.chat(
                model="mistral-medium",
                messages=[{
                    "role": "user",
                    "content": prompt
                }],
                temperature=0.1,  # Low temperature for consistent results
                max_tokens=1000
            )
            
            # Extract selections from response
            selections = self._parse_mistral_response(response)
            
            logger.info(f"✅ Mistral selections: {json.dumps(selections, indent=2)}")
            return selections
            
        except Exception as e:
            logger.error(f"❌ Mistral error: {e}")
            logger.warning("Falling back to intelligent mock")
            return self._get_selections_mock(query, schema)
    
    
    def _get_selections_mock(self, query: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Get selections from intelligent mock (rule-based)."""
        return IntelligentMockLLM().get_selections_from_schema(query, schema)
    
    def _build_selection_prompt(self, query: str, schema: Dict[str, Any]) -> str:
        """Build prompt for LLM to create selections."""
        
        entity_type = schema.get("entity_type", "unknown")
        metrics = schema.get("metrics", [])
        tags = schema.get("tags", [])
        aggregations = schema.get("aggregations", ["sum", "mean", "max", "min"])
        
        # Limit metrics/tags shown to avoid token overflow
        metrics_sample = metrics[:20] if len(metrics) > 20 else metrics
        tags_sample = tags[:20] if len(tags) > 20 else tags
        
        prompt = f"""You are analyzing infrastructure monitoring data. Based on the user's query and the available schema, create a selections object.

User Query: "{query}"

Available Schema for {entity_type}:

Metrics (choose from these exact names):
{json.dumps(metrics_sample, indent=2)}

Tags/Filters (choose from these exact names):
{json.dumps(tags_sample, indent=2)}

Aggregations: {', '.join(aggregations)}

Create a JSON object with these fields:
{{
  "entity_type": "{entity_type}",
  "metrics": ["exact.metric.name"],
  "aggregation": "sum|mean|max|min",
  "filters": [{{"name": "exact.tag.name", "value": "filter_value"}}],
  "groupBy": ["optional.tag.name"],
  "timeRange": "1h|24h|etc or omit for no time range",
  "order": {{"by": "metric.name", "direction": "ASC|DESC"}} or omit
}}

IMPORTANT RULES:
1. Use EXACT metric and tag names from the schema above
2. Extract filter values from the user query
3. Use "filters" (NOT "tagFilterElements") - server will convert
4. Choose appropriate aggregation based on query intent
5. Include groupBy only if query mentions grouping
6. Include timeRange only if query mentions time period
7. Include order only if query mentions sorting

Return ONLY the JSON object, no explanation."""

        return prompt
    
    def _parse_ollama_response(self, response) -> Dict[str, Any]:
        """Parse Ollama's response to extract selections."""
        
        # Get message content
        content = response['message']['content']
        
        # Extract JSON from response
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()
        
        # Parse JSON
        try:
            selections = json.loads(json_str)
            
            # Validate required fields
            if "entity_type" not in selections:
                raise ValueError("Missing entity_type in selections")
            if "metrics" not in selections:
                raise ValueError("Missing metrics in selections")
            
            return selections
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse Ollama response: {e}")
            logger.error(f"Content: {content}")
            raise

    
    def _parse_watsonx_response(self, response: str) -> Dict[str, Any]:
        """Parse watsonx (IBM Bob) response to extract selections."""
        
        # watsonx returns plain text, extract JSON
        content = response.strip()
        
        # Extract JSON from response
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()
        
        # Parse JSON
        try:
            selections = json.loads(json_str)
            
            # Validate required fields
            if "entity_type" not in selections:
                raise ValueError("Missing entity_type in selections")
            if "metrics" not in selections:
                raise ValueError("Missing metrics in selections")
            
            return selections
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse watsonx response: {e}")
            logger.error(f"Content: {content}")
            raise
    
    def _parse_mistral_response(self, response) -> Dict[str, Any]:
        """Parse Mistral API response to extract selections."""
        
        # Get message content
        content = response.choices[0].message.content
        
        # Extract JSON from response
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()
        
        # Parse JSON
        try:
            selections = json.loads(json_str)
            
            # Validate required fields
            if "entity_type" not in selections:
                raise ValueError("Missing entity_type in selections")
            if "metrics" not in selections:
                raise ValueError("Missing metrics in selections")
            
            return selections
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse Mistral response: {e}")
            logger.error(f"Content: {content}")
            raise


class IntelligentMockLLM:
    """
    Intelligent rule-based mock LLM for testing without external APIs.
    
    This uses pattern matching and NLP techniques to simulate LLM behavior
    for common query patterns. It's free, fast, and deterministic.
    
    NOTE: Returns 'filters' (simple format), NOT 'tagFilterElements'.
    The server will convert filters → tagFilterElements.
    """
    
    def __init__(self):
        """Initialize intelligent mock."""
        self.provider = "intelligent_mock"
    
    def get_selections_from_schema(
        self,
        query: str,
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate selections using intelligent pattern matching.
        
        Returns selections with 'filters' (simple format).
        Server will convert to 'tagFilterElements' (complex format).
        """
        
        query_lower = query.lower()
        entity_type = schema.get("entity_type", "db2Database")
        available_metrics = schema.get("metrics", [])
        available_tags = schema.get("tags", [])
        
        selections = {
            "entity_type": entity_type,
            "metrics": [],
            "aggregation": "sum",
            "filters": [],  # Simple format: {name, value}
            "groupBy": [],
        }
        
        # Extract metrics using pattern matching
        selections["metrics"] = self._extract_metrics(
            query_lower,
            available_metrics
        )
        
        # Extract aggregation
        selections["aggregation"] = self._extract_aggregation(query_lower)
        
        # Extract filters (simple format)
        selections["filters"] = self._extract_filters(
            query,
            query_lower,
            available_tags
        )
        
        # Extract groupBy
        selections["groupBy"] = self._extract_group_by(
            query_lower,
            available_tags
        )
        
        # Extract pagination (top N, limit N, or implicit from singular/plural)
        pagination = self._extract_pagination(query_lower, query)
        if pagination:
            selections["pagination"] = pagination
        
        # Extract time range
        time_range = self._extract_time_range(query_lower)
        if time_range:
            selections["timeRange"] = time_range
        
        # Extract order
        order = self._extract_order(query_lower, selections["metrics"])
        if order:
            selections["order"] = order
        
        logger.info(f"Intelligent mock selections: {json.dumps(selections, indent=2)}")
        return selections
    
    def _extract_metrics(
        self,
        query_lower: str,
        available_metrics: List[str]
    ) -> List[str]:
        """Extract metrics from query using pattern matching."""
        
        metrics = []
        
        # Common metric patterns for DB2
        metric_patterns = {
            r'\bqueries\b(?!\s+failed)': ['databases.queries'],
            r'\bfailed\s+queries\b': ['databases.failedQueries'],
            r'\block\s+wait\s+time\b': ['vmonlockstats.lockWaitTime'],
            r'\bconnections?\b': ['vmonlockstats.numberOfConnections'],
            r'\brequest\s+time\b': ['workloadstats.totalRequestTime'],
            r'\bwait\s+time\b': ['workloadstats.totalWaitTime'],
            r'\brollbacks?\b': ['databases.rollbacks'],
            r'\brows?\s+returned\b': ['databases.rowsReturned'],
        }
        
        for pattern, metric_names in metric_patterns.items():
            if re.search(pattern, query_lower):
                metrics.extend(metric_names)
        
        # If no metrics found, try fuzzy matching with available metrics
        if not metrics and available_metrics:
            # Extract key words from query
            words = re.findall(r'\b\w+\b', query_lower)
            for metric in available_metrics:
                metric_lower = metric.lower()
                for word in words:
                    if word in metric_lower and len(word) > 3:
                        metrics.append(metric)
                        break
        
        return metrics if metrics else ["databases.queries"]  # Default
    
    def _extract_aggregation(self, query_lower: str) -> str:
        """Extract aggregation type from query."""
        
        if any(word in query_lower for word in ['average', 'mean', 'avg']):
            return "mean"
        elif any(word in query_lower for word in ['maximum', 'max']):
            return "max"
        elif any(word in query_lower for word in ['minimum', 'min']):
            return "min"
        elif any(word in query_lower for word in ['total', 'sum', 'how many', 'number of', 'high number']):
            return "sum"
        
        # Note: "top N" and "highest" are about ordering, not aggregation
        # They should use sum aggregation with DESC order
        
        return "sum"  # Default
    
    def _extract_filters(
        self,
        query: str,
        query_lower: str,
        available_tags: List[str]
    ) -> List[Dict[str, str]]:
        """Extract filters from query."""
        
        filters = []
        
        # Pattern: "name=value" (most explicit)
        name_equals_pattern = r'\bname\s*=\s*(\w+)'
        match = re.search(name_equals_pattern, query_lower)
        if match:
            db_name = match.group(1)
            # Skip if it's a common word that's not a database name
            if db_name not in ['in', 'the', 'last', 'on', 'by', 'for', 'each', 'with']:
                # Get original case
                orig_match = re.search(name_equals_pattern, query, re.IGNORECASE)
                if orig_match:
                    db_name = orig_match.group(1)
                
                filters.append({
                    "name": "db2.name",
                    "value": db_name
                })
        else:
            # Pattern: "database named X", "db2 named X"
            # But NOT "for each database" or "in the database"
            db_name_patterns = [
                r'database\s+(?:named|called)\s+(\w+)',
                r'db2\s+(?:named|called)\s+(\w+)',
                r'(?:on|to)\s+(?:db2\s+)?database\s+(\w+)',  # "on database X"
            ]
            
            for pattern in db_name_patterns:
                match = re.search(pattern, query_lower)
                if match:
                    db_name = match.group(1)
                    # Skip common words
                    if db_name not in ['in', 'the', 'last', 'on', 'by', 'for', 'each', 'with']:
                        # Find in original query for correct case
                        orig_match = re.search(pattern, query, re.IGNORECASE)
                        if orig_match:
                            db_name = orig_match.group(1)
                        
                        filters.append({
                            "name": "db2.name",
                            "value": db_name
                        })
                        break
        
        # Pattern: "host=X" or "host name X" (but NOT "by host name" or "on host")
        host_equals_pattern = r'\bhost\s*=\s*(\w+)'
        match = re.search(host_equals_pattern, query_lower)
        if match:
            host_name = match.group(1)
            orig_match = re.search(host_equals_pattern, query, re.IGNORECASE)
            if orig_match:
                host_name = orig_match.group(1)
            
            filters.append({
                "name": "host.name",
                "value": host_name
            })
        
        # Pattern: "namespace X" or "in namespace X"
        namespace_patterns = [
            r'\bnamespace\s+(\w+)',
            r'\bin\s+namespace\s+(\w+)',
        ]
        
        for pattern in namespace_patterns:
            match = re.search(pattern, query_lower)
            if match:
                namespace = match.group(1)
                orig_match = re.search(pattern, query, re.IGNORECASE)
                if orig_match:
                    namespace = orig_match.group(1)
                
                filters.append({
                    "name": "kubernetes.namespace.name",
                    "value": namespace
                })
                break
        
        # Pattern: "name contains X"
        contains_pattern = r'name\s+contains\s+(\w+)'
        match = re.search(contains_pattern, query_lower)
        if match:
            value = match.group(1).upper()
            orig_match = re.search(contains_pattern, query, re.IGNORECASE)
            if orig_match:
                value = orig_match.group(1)
            
            # Note: This would need operator support in filters
            filters.append({
                "name": "db2.name",
                "value": value,
                "operator": "contains"
            })
        
        return filters
    
    def _extract_group_by(
        self,
        query_lower: str,
        available_tags: List[str]
    ) -> List[str]:
        """Extract groupBy from query."""
        
        group_by = []
        
        # Check for explicit "group by" or "grouped by"
        if 'group by' in query_lower or 'grouped by' in query_lower:
            # Extract what comes after "group by"
            match = re.search(r'group(?:ed)?\s+by\s+([\w\s,]+)', query_lower)
            if match:
                group_text = match.group(1)
                
                # Common grouping patterns
                if 'database' in group_text or 'db' in group_text:
                    group_by.append("db2.name")
                if 'host' in group_text:
                    group_by.append("host.name")
                if 'namespace' in group_text:
                    group_by.append("kubernetes.namespace.name")
        
        # Check for implicit grouping: "for each X", "per X", "by X"
        elif any(phrase in query_lower for phrase in ['for each', 'per ', 'by each']):
            # "for each database" or "per database"
            if re.search(r'(?:for each|per|by each)\s+database', query_lower):
                group_by.append("db2.name")
            # "for each host" or "per host"
            if re.search(r'(?:for each|per|by each)\s+host', query_lower):
                group_by.append("host.name")
        
        # Check for plural forms with superlatives (implies grouping)
        # "Show databases with highest..." → group by db2.name
        elif any(word in query_lower for word in ['highest', 'lowest', 'best', 'worst']):
            # Plural "databases" (not singular "database")
            if re.search(r'\b(?:show|get|find)\s+(?:the\s+)?databases\s+with', query_lower):
                group_by.append("db2.name")
        
        return group_by
    
    def _extract_pagination(self, query_lower: str, query: str) -> Optional[Dict[str, int]]:
        """Extract pagination from query (top N, limit N, first N, or implicit from context)."""
        
        # Pattern: "top N", "first N", "limit N"
        pagination_patterns = [
            r'\btop\s+(\d+)\b',
            r'\bfirst\s+(\d+)\b',
            r'\blimit\s+(\d+)\b',
            r'\bshow\s+(\d+)\b',
        ]
        
        for pattern in pagination_patterns:
            match = re.search(pattern, query_lower)
            if match:
                size = int(match.group(1))
                return {"retrievalSize": size}
        
        # Implicit pagination from singular forms with superlatives
        # "Show database with highest..." → retrievalSize: 1
        # "Show databases with highest..." → no pagination (show all)
        if any(word in query_lower for word in ['highest', 'lowest', 'best', 'worst', 'maximum', 'minimum']):
            # Check for singular "database" (not "databases")
            if re.search(r'\b(?:show|get|find)\s+(?:the\s+)?database\s+with', query_lower):
                return {"retrievalSize": 1}
        
        return None
    
    def _extract_time_range(self, query_lower: str) -> Optional[str]:
        """Extract time range from query."""
        
        # Pattern: "last X hours/minutes/days"
        time_patterns = {
            r'last\s+(\d+)\s+hours?': lambda m: f"{m.group(1)}h",
            r'last\s+(\d+)\s+minutes?': lambda m: f"{m.group(1)}m",
            r'last\s+(\d+)\s+days?': lambda m: f"{m.group(1)}d",
            r'last\s+hour': lambda m: "1h",
            r'last\s+day': lambda m: "1d",
        }
        
        for pattern, formatter in time_patterns.items():
            match = re.search(pattern, query_lower)
            if match:
                return formatter(match)
        
        return None
    
    def _extract_order(
        self,
        query_lower: str,
        metrics: List[str]
    ) -> Optional[Dict[str, str]]:
        """Extract order from query."""
        
        # Check for ordering keywords
        has_order_keyword = any(word in query_lower for word in [
            'order', 'sort', 'top', 'highest', 'lowest', 'best', 'worst'
        ])
        
        if not has_order_keyword:
            return None
        
        # Determine direction
        if any(word in query_lower for word in ['descending', 'desc', 'highest', 'top', 'best', 'high']):
            direction = "DESC"
        elif any(word in query_lower for word in ['ascending', 'asc', 'lowest', 'worst', 'low']):
            direction = "ASC"
        else:
            direction = "DESC"  # Default
        
        # Determine what to order by
        if metrics:
            order_by = metrics[0]  # Order by first metric
        else:
            order_by = "databases.queries"  # Default
        
        return {
            "by": order_by,
            "direction": direction
        }


# Convenience function
def create_llm_client(provider: str = "mock") -> LLMClientWrapper:
    """
    Create LLM client with specified provider.
    
    Args:
        provider: "mock" (default, rule-based) or "ollama" (local LLM)
    
    Returns:
        LLM client wrapper
    
    Raises:
        ValueError: If provider is not allowed (e.g., "claude", "openai")
    """
    return LLMClientWrapper(provider=provider)

# Made with Bob
