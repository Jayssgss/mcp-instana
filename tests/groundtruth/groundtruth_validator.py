"""
Groundtruth validation framework for prompt testing.

This module provides utilities for validating prompt outputs against
groundtruth test data, calculating accuracy metrics, and generating reports.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class TestCase:
    """Represents a single groundtruth test case."""
    num: str
    input: str
    expected_output: Dict[str, Any]
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestCase":
        """Create TestCase from dictionary."""
        return cls(
            num=data.get("num", ""),
            input=data["input"],
            expected_output=data["output"]
        )


@dataclass
class ValidationResult:
    """Results from validating a single test case."""
    test_case: TestCase
    actual_output: Optional[Dict[str, Any]]
    type_correct: bool
    api_endpoint_correct: bool
    field_accuracy: Dict[str, bool]
    overall_accuracy: float
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "num": self.test_case.num,
            "input": self.test_case.input,
            "type_correct": self.type_correct,
            "api_endpoint_correct": self.api_endpoint_correct,
            "field_accuracy": self.field_accuracy,
            "overall_accuracy": self.overall_accuracy,
            "error": self.error
        }


@dataclass
class EvaluationMetrics:
    """Aggregated evaluation metrics."""
    total_tests: int = 0
    type_accuracy: float = 0.0
    api_endpoint_accuracy: float = 0.0
    overall_accuracy: float = 0.0
    field_level_accuracy: Dict[str, float] = field(default_factory=dict)
    per_entity_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_tests": self.total_tests,
            "type_accuracy": f"{self.type_accuracy:.2%}",
            "api_endpoint_accuracy": f"{self.api_endpoint_accuracy:.2%}",
            "overall_accuracy": f"{self.overall_accuracy:.2%}",
            "field_level_accuracy": {k: f"{v:.2%}" for k, v in self.field_level_accuracy.items()},
            "per_entity_metrics": self.per_entity_metrics
        }


class GroundtruthValidator:
    """Validator for comparing actual outputs against groundtruth."""
    
    def __init__(self):
        """Initialize the validator."""
        self.results: List[ValidationResult] = []
    
    def load_groundtruth(self, file_path: Path) -> List[TestCase]:
        """Load groundtruth test cases from JSONL file."""
        test_cases = []
        with open(file_path, 'r') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    test_cases.append(TestCase.from_dict(data))
        return test_cases
    
    def validate_test_case(
        self,
        test_case: TestCase,
        actual_output: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate a single test case against actual output."""
        if actual_output is None:
            return ValidationResult(
                test_case=test_case,
                actual_output=None,
                type_correct=False,
                api_endpoint_correct=False,
                field_accuracy={},
                overall_accuracy=0.0,
                error="No output generated"
            )
        
        expected = test_case.expected_output
        
        # Check type
        type_correct = actual_output.get("type") == expected.get("type")
        
        # Check API endpoint
        api_endpoint_correct = actual_output.get("api_endpoint") == expected.get("api_endpoint")
        
        # Check arguments field by field
        field_accuracy = self._compare_arguments(
            expected.get("arguments", {}),
            actual_output.get("arguments", {})
        )
        
        # Calculate overall accuracy
        correct_fields = sum(field_accuracy.values())
        total_fields = len(field_accuracy)
        field_score = correct_fields / total_fields if total_fields > 0 else 0.0
        
        # Overall = (type + endpoint + avg_field_score) / 3
        overall_accuracy = (
            (1.0 if type_correct else 0.0) +
            (1.0 if api_endpoint_correct else 0.0) +
            field_score
        ) / 3.0
        
        result = ValidationResult(
            test_case=test_case,
            actual_output=actual_output,
            type_correct=type_correct,
            api_endpoint_correct=api_endpoint_correct,
            field_accuracy=field_accuracy,
            overall_accuracy=overall_accuracy
        )
        
        self.results.append(result)
        return result
    
    def _compare_arguments(
        self,
        expected: Dict[str, Any],
        actual: Dict[str, Any]
    ) -> Dict[str, bool]:
        """Compare arguments field by field."""
        field_accuracy = {}
        
        # Check pagination
        field_accuracy["pagination"] = self._compare_pagination(
            expected.get("pagination"),
            actual.get("pagination")
        )
        
        # Check metrics (most important)
        field_accuracy["metrics"] = self._compare_metrics(
            expected.get("metrics", []),
            actual.get("metrics", [])
        )
        
        # Check tagFilterElements (CRITICAL - this is the hard field mentioned)
        field_accuracy["tagFilterElements"] = self._compare_tag_filters(
            expected.get("tagFilterElements", []),
            actual.get("tagFilterElements", [])
        )
        
        # Check order
        field_accuracy["order"] = self._compare_order(
            expected.get("order"),
            actual.get("order")
        )
        
        # Check groupBy
        field_accuracy["groupBy"] = self._compare_lists(
            expected.get("groupBy", []),
            actual.get("groupBy", [])
        )
        
        # Check time fields
        field_accuracy["start_time"] = self._compare_time_values(
            expected.get("start_time"),
            actual.get("start_time")
        )
        
        field_accuracy["end_time"] = self._compare_time_values(
            expected.get("end_time"),
            actual.get("end_time")
        )
        
        return field_accuracy
    
    def _compare_pagination(self, expected: Any, actual: Any) -> bool:
        """Compare pagination objects."""
        if expected == actual:
            return True
        if expected is None and actual is None:
            return True
        if isinstance(expected, dict) and isinstance(actual, dict):
            return expected.get("retrievalSize") == actual.get("retrievalSize")
        return False
    
    def _compare_metrics(self, expected: List[Dict], actual: List[Dict]) -> bool:
        """Compare metrics lists."""
        if len(expected) != len(actual):
            return False
        
        # Sort both lists for comparison
        expected_sorted = sorted(expected, key=lambda x: x.get("metric", ""))
        actual_sorted = sorted(actual, key=lambda x: x.get("metric", ""))
        
        for exp, act in zip(expected_sorted, actual_sorted):
            if exp.get("metric") != act.get("metric"):
                return False
            # Normalize aggregation to lowercase for comparison
            exp_agg = exp.get("aggregation", "").lower()
            act_agg = act.get("aggregation", "").lower()
            if exp_agg != act_agg:
                return False
        
        return True
    
    def _compare_tag_filters(self, expected: List[Dict], actual: List[Dict]) -> bool:
        """
        Compare tag filter elements.
        This is the CRITICAL field that was mentioned as having 0% → 94.1% improvement.
        """
        if len(expected) != len(actual):
            return False
        
        # If both are empty, they match
        if len(expected) == 0:
            return True
        
        # Sort both lists for comparison by name
        expected_sorted = sorted(expected, key=lambda x: x.get("name", ""))
        actual_sorted = sorted(actual, key=lambda x: x.get("name", ""))
        
        for exp, act in zip(expected_sorted, actual_sorted):
            # Check type
            if exp.get("type") != act.get("type"):
                return False
            # Check name
            if exp.get("name") != act.get("name"):
                return False
            # Check operator (normalize to lowercase)
            exp_op = exp.get("operator", "").lower()
            act_op = act.get("operator", "").lower()
            if exp_op != act_op:
                return False
            # Check value
            if exp.get("value") != act.get("value"):
                return False
        
        return True
    
    def _compare_order(self, expected: Any, actual: Any) -> bool:
        """Compare order specifications."""
        # Handle "NONE" string
        if expected == "NONE" and actual in [None, "NONE"]:
            return True
        if actual == "NONE" and expected in [None, "NONE"]:
            return True
        
        # Both None or both "NONE"
        if expected in [None, "NONE"] and actual in [None, "NONE"]:
            return True
        
        # Compare dict objects
        if isinstance(expected, dict) and isinstance(actual, dict):
            exp_by = expected.get("by", "")
            act_by = actual.get("by", "")
            exp_dir = expected.get("direction", "").upper()
            act_dir = actual.get("direction", "").upper()
            return exp_by == act_by and exp_dir == act_dir
        
        return expected == actual
    
    def _compare_lists(self, expected: List, actual: List) -> bool:
        """Compare two lists (order-independent)."""
        if len(expected) != len(actual):
            return False
        return sorted(expected) == sorted(actual)
    
    def _compare_time_values(self, expected: Any, actual: Any) -> bool:
        """Compare time values with normalization."""
        # Handle "NONE" string
        if expected == "NONE" and actual in [None, "NONE"]:
            return True
        if actual == "NONE" and expected in [None, "NONE"]:
            return True
        
        # Normalize time expressions
        if isinstance(expected, str) and isinstance(actual, str):
            expected_norm = self._normalize_time_expression(expected)
            actual_norm = self._normalize_time_expression(actual)
            return expected_norm == actual_norm
        
        return expected == actual
    
    def _normalize_time_expression(self, time_expr: str) -> str:
        """Normalize time expressions for comparison."""
        if time_expr == "NONE":
            return "NONE"
        
        # Remove spaces and normalize
        normalized = time_expr.replace(" ", "").lower()
        
        # Normalize common patterns
        normalized = normalized.replace("current_timestamp", "CURRENT_TIMESTAMP")
        normalized = normalized.replace("currenttimestamp", "CURRENT_TIMESTAMP")
        
        # Normalize time units
        normalized = normalized.replace("1hour", "1h")
        normalized = normalized.replace("1day", "1d")
        normalized = normalized.replace("24hours", "24h")
        normalized = normalized.replace("60minutes", "1h")
        
        return normalized
    
    def calculate_metrics(self) -> EvaluationMetrics:
        """Calculate aggregated evaluation metrics."""
        if not self.results:
            return EvaluationMetrics()
        
        total = len(self.results)
        type_correct = sum(1 for r in self.results if r.type_correct)
        api_correct = sum(1 for r in self.results if r.api_endpoint_correct)
        
        # Calculate field-level accuracy
        field_counts = defaultdict(lambda: {"correct": 0, "total": 0})
        for result in self.results:
            for field, correct in result.field_accuracy.items():
                field_counts[field]["total"] += 1
                if correct:
                    field_counts[field]["correct"] += 1
        
        field_level_accuracy = {
            field: counts["correct"] / counts["total"]
            for field, counts in field_counts.items()
        }
        
        # Calculate per-entity metrics
        entity_results = defaultdict(list)
        for result in self.results:
            entity_type = result.test_case.expected_output.get("type", "unknown")
            entity_results[entity_type].append(result)
        
        per_entity_metrics = {}
        for entity_type, results in entity_results.items():
            entity_total = len(results)
            entity_correct = sum(1 for r in results if r.overall_accuracy == 1.0)
            per_entity_metrics[entity_type] = {
                "total": entity_total,
                "accuracy": f"{entity_correct / entity_total:.2%}" if entity_total > 0 else "0%",
                "correct": entity_correct
            }
        
        overall_accuracy = sum(r.overall_accuracy for r in self.results) / total
        
        return EvaluationMetrics(
            total_tests=total,
            type_accuracy=type_correct / total,
            api_endpoint_accuracy=api_correct / total,
            overall_accuracy=overall_accuracy,
            field_level_accuracy=field_level_accuracy,
            per_entity_metrics=per_entity_metrics
        )
    
    def generate_report(self, output_path: Optional[Path] = None) -> str:
        """Generate a detailed evaluation report."""
        metrics = self.calculate_metrics()
        
        report_lines = [
            "=" * 80,
            "GROUNDTRUTH EVALUATION REPORT",
            "=" * 80,
            "",
            f"Total Test Cases: {metrics.total_tests}",
            f"Overall Accuracy: {metrics.overall_accuracy:.2%}",
            "",
            "Component Accuracy:",
            f"  - Type Selection: {metrics.type_accuracy:.2%}",
            f"  - API Endpoint: {metrics.api_endpoint_accuracy:.2%}",
            "",
            "Field-Level Accuracy:",
        ]
        
        for field, accuracy in sorted(metrics.field_level_accuracy.items()):
            marker = "  ← CRITICAL" if field == "tagFilterElements" else ""
            report_lines.append(f"  - {field}: {accuracy:.2%}{marker}")
        
        report_lines.extend([
            "",
            "Per-Entity Metrics:",
        ])
        
        for entity_type, entity_metrics in sorted(metrics.per_entity_metrics.items()):
            report_lines.append(
                f"  - {entity_type}: {entity_metrics['accuracy']} "
                f"({entity_metrics['correct']}/{entity_metrics['total']} tests)"
            )
        
        report_lines.extend([
            "",
            "Failed Test Cases:",
        ])
        
        failed_results = [r for r in self.results if r.overall_accuracy < 1.0]
        if failed_results:
            for result in failed_results:
                report_lines.append(f"  - Test #{result.test_case.num}: {result.test_case.input[:60]}...")
                report_lines.append(f"    Accuracy: {result.overall_accuracy:.2%}")
                if not result.type_correct:
                    report_lines.append("    ✗ Type mismatch")
                if not result.api_endpoint_correct:
                    report_lines.append("    ✗ API endpoint mismatch")
                for field, correct in result.field_accuracy.items():
                    if not correct:
                        report_lines.append(f"    ✗ {field} mismatch")
                report_lines.append("")
        else:
            report_lines.append("  None - All tests passed! 🎉")
        
        report_lines.append("=" * 80)
        
        report = "\n".join(report_lines)
        
        if output_path:
            output_path.write_text(report)
        
        return report
    
    def reset(self):
        """Reset the validator state."""
        self.results = []
