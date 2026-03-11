# IBM Bob (Watsonx) Setup Guide

This guide explains how to use IBM Bob (watsonx) with the groundtruth testing framework.

## Prerequisites

1. **IBM watsonx Account**: You need access to IBM watsonx
2. **API Credentials**: API key and Project ID
3. **Python Package**: `ibm-watsonx-ai`

## Installation

```bash
# Install the IBM watsonx AI package
pip install ibm-watsonx-ai

# Or with uv
uv pip install ibm-watsonx-ai
```

## Configuration

### Step 1: Set Environment Variables

You need to set two environment variables with your credentials:

```bash
# Set your watsonx API key
export WATSONX_API_KEY="your-api-key-here"

# Set your watsonx project ID
export WATSONX_PROJECT_ID="your-project-id-here"

# Optional: Set custom watsonx URL (default: https://us-south.ml.cloud.ibm.com)
export WATSONX_URL="https://us-south.ml.cloud.ibm.com"

# Optional: Set custom model ID (default: ibm/granite-13b-chat-v2)
export WATSONX_MODEL_ID="ibm/granite-13b-chat-v2"
```

### Step 2: Verify Setup

Test that your credentials work:

```bash
# Run a single test with Bob
LLM_PROVIDER=bob uv run pytest tests/groundtruth/test_db2_groundtruth.py::TestDB2Groundtruth::test_db2_case[1] -v -s
```

## Usage

### Running Tests with Bob

```bash
# Run all tests with IBM Bob
LLM_PROVIDER=bob uv run pytest tests/groundtruth/test_db2_groundtruth.py -v

# Run with detailed output
LLM_PROVIDER=bob uv run pytest tests/groundtruth/test_db2_groundtruth.py -v -s

# Run specific test
LLM_PROVIDER=bob uv run pytest tests/groundtruth/test_db2_groundtruth.py::TestDB2Groundtruth::test_db2_case[3] -v
```

### Using Command Line Option

```bash
# Alternative: Use pytest option
uv run pytest tests/groundtruth/test_db2_groundtruth.py --llm-provider=bob -v
```

## Available Models

The default model is `ibm/granite-13b-chat-v2` (IBM's Bob model). You can use other watsonx models by setting `WATSONX_MODEL_ID`:

```bash
# Use a different model
export WATSONX_MODEL_ID="ibm/granite-20b-multilingual"
LLM_PROVIDER=bob uv run pytest tests/groundtruth/test_db2_groundtruth.py -v
```

## Troubleshooting

### Error: "WATSONX_API_KEY environment variable required"

**Solution**: Make sure you've exported the environment variables:
```bash
export WATSONX_API_KEY="your-key"
export WATSONX_PROJECT_ID="your-project-id"
```

### Error: "ibm-watsonx-ai package not installed"

**Solution**: Install the package:
```bash
pip install ibm-watsonx-ai
```

### Error: "Failed to initialize IBM Bob client"

**Possible causes**:
1. Invalid API key
2. Invalid project ID
3. Network connectivity issues
4. Insufficient permissions

**Solution**: Verify your credentials and network connection.

## Comparison with Other Providers

| Provider | Cost | Speed | Accuracy | Use Case |
|----------|------|-------|----------|----------|
| **mock** | Free | Fastest | Good | Quick testing, CI/CD |
| **ollama** | Free | Fast | Variable | Local development |
| **bob** | Paid | Medium | High | Production validation |
| **mistral** | Paid | Medium | High | Alternative validation |

## Best Practices

1. **Use Mock for Development**: Start with mock provider for fast iteration
2. **Use Bob for Validation**: Run Bob tests before committing changes
3. **Track Accuracy**: Compare Bob results against groundtruth
4. **Control Variables**: When comparing implementations, use the SAME model

## Example Workflow

```bash
# 1. Quick test with mock (fast)
uv run pytest tests/groundtruth/test_db2_groundtruth.py -v

# 2. Validate with Bob (accurate)
LLM_PROVIDER=bob uv run pytest tests/groundtruth/test_db2_groundtruth.py -v

# 3. Compare results
# Check accuracy scores in test output
```

## Security Notes

- **Never commit credentials** to version control
- Use environment variables for sensitive data
- Consider using a `.env` file (add to `.gitignore`)
- Rotate API keys regularly

## Support

For issues with:
- **IBM watsonx**: Contact IBM support
- **Testing framework**: Open an issue in the repository
- **Credentials**: Contact your IBM account administrator

---

*Last updated: 2026-02-27*