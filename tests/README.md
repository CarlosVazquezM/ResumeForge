# Testing Guide for ResumeForge

This directory contains both unit tests and integration tests.

## Test Structure

```
tests/
├── unit/                    # Unit tests (mocked, no API keys needed)
│   ├── test_providers.py
│   ├── test_schemas_evidence_card.py
│   └── test_schemas_blackboard.py
└── integration/             # Integration tests (real API calls, need API keys)
    └── test_providers_integration.py
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

## Best Practices

1. **Unit tests should be fast and isolated** - Use mocks, no network calls
2. **Integration tests should be clearly marked** - Use `@pytest.mark.integration`
3. **Skip gracefully** - Integration tests should skip if API keys are missing
4. **Keep tests deterministic** - Use `temperature=0.0` for LLM calls when possible
5. **Minimize API calls** - Integration tests should be minimal to avoid costs
