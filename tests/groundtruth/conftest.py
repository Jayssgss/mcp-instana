"""
Pytest configuration and fixtures for groundtruth testing.
"""

import pytest
import os
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@pytest.fixture(scope="session")
def groundtruth_data_dir():
    """Path to groundtruth data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def schema_dir():
    """Path to schema directory."""
    return Path(__file__).parent.parent.parent / "schema"


@pytest.fixture(scope="session")
def llm_provider():
    """
    LLM provider to use for testing.
    
    Allowed providers:
    - mock: Rule-based intelligent mock (no API calls, free)
    - ollama: Local LLM (free, requires ollama installed)
    - bob: IBM Bob via watsonx (Instana-approved, requires credentials)
    - mistral: Mistral API (Instana-approved, requires API key)
    """
    provider = os.getenv("LLM_PROVIDER", "mock")
    
    # Allowed providers for testing
    allowed = ["mock", "ollama", "bob", "mistral"]
    if provider not in allowed:
        raise ValueError(
            f"LLM_PROVIDER '{provider}' not allowed. "
            f"Use one of: {', '.join(allowed)}"
        )
    
    return provider


@pytest.fixture(scope="session")
def instana_credentials():
    """Instana API credentials."""
    return {
        "api_token": os.getenv("INSTANA_API_TOKEN", "test_token"),
        "base_url": os.getenv("INSTANA_BASE_URL", "https://test.instana.io")
    }


@pytest.fixture
def llm_client(llm_provider):
    """
    LLM client based on provider.
    
    Defaults to mock (rule-based), can use ollama (local LLM).
    """
    from tests.groundtruth.llm_client_wrapper import create_llm_client
    return create_llm_client(provider=llm_provider)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--llm-provider",
        action="store",
        default="mock",
        choices=["mock", "ollama", "bob", "mistral"],
        help="LLM provider to use: mock (free), ollama (free), bob (Instana-approved), mistral (Instana-approved)"
    )
    parser.addoption(
        "--report",
        action="store_true",
        default=False,
        help="Generate detailed evaluation report"
    )


@pytest.fixture
def use_ollama(request):
    """Whether to use Ollama instead of mock."""
    return request.config.getoption("--llm-provider") == "ollama"
