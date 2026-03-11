#!/bin/bash
# Test script for running groundtruth tests with IBM Bob (watsonx)
# 
# This script sets the required environment variables and runs the tests.
# DO NOT commit this file with real credentials!

set -e  # Exit on error

echo "================================================================================"
echo "Testing with IBM Bob (watsonx)"
echo "================================================================================"
echo ""

# Set watsonx credentials
export WATSONX_URL="https://us-south.ml.cloud.ibm.com"
export WATSONX_PROJECT_ID="7df21499-6277-4938-af57-a409852ae8f1"
export WATSONX_API_KEY="5cSMM-2lAi040vKauIMv3Pp_zf6EP_Gse-D7z0CC03KV"

# Check if ibm-watsonx-ai is installed
if ! python3 -c "import ibm_watsonx_ai" 2>/dev/null; then
    echo "⚠️  ibm-watsonx-ai package not found. Installing..."
    pip install ibm-watsonx-ai
    echo "✅ Package installed"
    echo ""
fi

echo "Running tests with IBM Bob..."
echo ""

# Run tests with Bob
LLM_PROVIDER=bob uv run pytest tests/groundtruth/test_db2_groundtruth.py -v -s

echo ""
echo "================================================================================"
echo "Test complete!"
echo "================================================================================"

# Made with Bob
