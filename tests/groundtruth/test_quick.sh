#!/bin/bash
# Quick test script to run a single test case with detailed output

echo "Running Test Case #3 with detailed logs..."
echo "=========================================="
echo ""

cd "$(dirname "$0")/../.."
uv run pytest tests/groundtruth/test_db2_groundtruth.py::TestDB2Groundtruth::test_db2_case[3] -v -s --tb=short

echo ""
echo "=========================================="
echo "Test complete!"

# Made with Bob
