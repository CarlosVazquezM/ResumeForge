# Testing Guide for ResumeForge

This directory contains both unit tests and integration tests.

## Test Structure

```
tests/
├── fixtures/                 # Test fixtures and helpers
│   ├── sample_evidence_cards.json
│   ├── sample_job_description.txt
│   ├── sample_resume_template.md
│   └── __init__.py           # Helper functions
├── unit/                      # Unit tests (mocked, no API keys needed)
│   ├── test_providers.py
│   ├── test_schemas_evidence_card.py
│   ├── test_schemas_blackboard.py
│   ├── test_agents_base.py
│   ├── test_agents_jd_analyst.py
│   ├── test_agents_evidence_mapper.py
│   ├── test_agents_resume_writer.py
│   └── test_agents_auditor.py
└── integration/              # Integration tests (real API calls, need API keys)
    ├── test_providers_integration.py
    └── test_agents_integration.py
```

## Running Tests

### Default: Unit Tests Only (No API Keys Required)

```bash
# Run all unit tests (default - excludes integration tests)
pytest

# Run specific test file
pytest tests/unit/test_providers.py

# Run specific test
pytest tests/unit/test_providers.py::TestOpenAIProvider::test_count_tokens
```

### Integration Tests (Requires API Keys)

```bash
# Run all integration tests (requires API keys in environment)
pytest -m integration

# Run integration tests for a specific provider
pytest -m integration tests/integration/test_providers_integration.py::TestOpenAIProviderIntegration

# Run ALL tests including integration
pytest -m ""

# Run with specific API key set
OPENAI_API_KEY=sk-... pytest -m integration tests/integration/test_providers_integration.py::TestOpenAIProviderIntegration
```

## Setting Up API Keys for Integration Tests

Integration tests are automatically skipped if the required API keys are not set. Set them as environment variables:

```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GOOGLE_API_KEY=AIza...
export GROQ_API_KEY=gsk_...
```

Or use a `.env` file (not committed to git):

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Then load with:
```bash
source .env  # or use python-dotenv
pytest -m integration
```

## Test Markers

Tests are organized using pytest markers:

- **No marker**: Regular unit tests (run by default)
- `@pytest.mark.integration`: Integration tests (excluded by default, require API keys)
- `@pytest.mark.requires_api_key`: Tests that check for API keys

## CI/CD Considerations

In CI/CD pipelines:

1. **Always run unit tests** (fast, no external dependencies):
   ```bash
   pytest  # Excludes integration by default
   ```

2. **Optionally run integration tests** (slower, requires API keys):
   ```bash
   pytest -m integration  # Only if API keys are available in CI secrets
   ```

3. **Coverage**: Integration tests are included in coverage if run, but typically only unit tests are run in CI for speed and cost reasons.

## Writing New Tests

### Unit Test Example

```python
# tests/unit/test_my_module.py
import pytest
from unittest.mock import Mock, patch

def test_my_function():
    # Mock external dependencies
    with patch("my_module.external_api") as mock_api:
        mock_api.return_value = "test"
        result = my_function()
        assert result == "expected"
```

### Integration Test Example

```python
# tests/integration/test_my_module_integration.py
import os
import pytest

@pytest.mark.integration
@pytest.mark.requires_api_key
@pytest.mark.skipif(
    not os.getenv("MY_API_KEY"),
    reason="Requires MY_API_KEY environment variable"
)
def test_my_function_real_api():
    # Real API call
    result = my_function_with_real_api()
    assert result is not None
```

## Agent Testing

### Unit Tests

All agent unit tests use mocked providers and test:
- Prompt building and validation
- Response parsing and error handling
- Edge cases and guardrails
- Enum conversions (Priority, Confidence, GapStrategy)

**Example:**
```python
from tests.fixtures import create_mock_provider, create_sample_blackboard
from resumeforge.agents.jd_analyst import JDAnalystAgent

def test_jd_analyst_parsing():
    mock_provider = create_mock_provider(response='{"role_profile": {...}}')
    agent = JDAnalystAgent(mock_provider, config)
    blackboard = create_sample_blackboard()
    result = agent.execute(blackboard)
    assert result.role_profile is not None
```

### Integration Tests

Agent integration tests make real API calls with minimal inputs:
- JD Analyst: Small JD (~200 words)
- Evidence Mapper: 3 evidence cards
- Resume Writer: 2-3 evidence cards
- Auditor: Minimal resume draft

**Coverage:** 88.4% average for agents module (exceeds 80% target)

## Best Practices

1. **Unit tests should be fast and isolated** - Use mocks, no network calls
2. **Integration tests should be clearly marked** - Use `@pytest.mark.integration`
3. **Skip gracefully** - Integration tests should skip if API keys are missing
4. **Keep tests deterministic** - Use `temperature=0.0` for LLM calls when possible
5. **Minimize API calls** - Integration tests should be minimal to avoid costs
6. **Use test fixtures** - Leverage `tests/fixtures/` for reusable test data
7. **Test guardrails** - Verify no-fabrication rules and evidence-only constraints