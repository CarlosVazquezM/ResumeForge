# ResumeForge Examples

Example scripts demonstrating schema functionality.

## Quick Start

### 1. Quick Schema Test

Simple test of core functionality:

```bash
python examples/quick_schema_test.py
```

Tests:
- EvidenceCard creation and validation
- Blackboard state management
- ClaimMapping truthfulness validation
- Configuration loading

### 2. Comprehensive Interactive Test

Full demonstration of all schema features:

```bash
python examples/test_schemas_interactive.py
```

Tests:
- All EvidenceCard features (metrics, scope, validation)
- Blackboard state management and validation
- ClaimMapping truthfulness guarantee
- All pipeline models (RoleProfile, EvidenceMapping, etc.)
- JSON serialization/deserialization
- Configuration loading and inspection
- JSON Schema export

## Unit Tests

Run all unit tests:

```bash
pytest tests/unit/test_schemas_*.py -v
```

## Interactive Exploration

You can also explore schemas interactively in Python:

```python
from resumeforge.schemas import EvidenceCard, MetricEntry, Blackboard, Inputs
from resumeforge.config import load_config

# Create an evidence card
card = EvidenceCard(
    id="my-card",
    project="My Project",
    company="My Company",
    timeframe="2020-2024",
    role="Engineer",
    metrics=[MetricEntry(value="50%", description="improvement")],
    raw_text="Led development..."
)

# Create a blackboard
inputs = Inputs(
    job_description="Looking for engineer...",
    target_title="Senior Engineer",
    template_path="./templates/base.md"
)
blackboard = Blackboard(inputs=inputs)
blackboard.evidence_cards = [card]

# Validate state
is_valid, errors = blackboard.validate_state()
print(f"Valid: {is_valid}, Errors: {errors}")

# Load config
cfg = load_config("config.yaml")
print(f"Agents: {len(cfg.agents)}")
```
