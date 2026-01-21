# ResumeForge Testing Guide

**Current Status:** Phase 2 Complete - Core Schemas Implemented ✅

---

## What Can Be Tested Right Now

### ✅ Fully Functional

1. **EvidenceCard Schema**
   - Create evidence cards with validation
   - Validate timeframe formats (YYYY-YYYY or YYYY-MM to YYYY-MM)
   - Use helper methods (get_metrics_summary, get_skills_summary)
   - JSON serialization/deserialization

2. **Blackboard State Management**
   - Create and manage pipeline state
   - Validate state for current pipeline step
   - Get selected evidence cards
   - Lookup evidence cards by ID

3. **ClaimMapping Validation**
   - Enforce truthfulness guarantee (no empty evidence_card_ids)
   - Validate claim references against available cards

4. **Configuration Loading**
   - Load and inspect config.yaml
   - Access agent configurations
   - Access model aliases and provider settings

5. **JSON Schema Export**
   - Export Pydantic models to JSON Schema format
   - Useful for documentation and external tools

---

## Testing Methods

### 1. Quick Test (Recommended to Start)

**Fast validation of core functionality:**

```bash
python examples/quick_schema_test.py
```

**Tests:**
- ✓ EvidenceCard creation
- ✓ Blackboard state management
- ✓ ClaimMapping validation
- ✓ Configuration loading
- ✓ State validation

**Output:**
```
============================================================
Quick Schema Test
============================================================

1. Creating EvidenceCard...
   ✓ Created: test-card
   ✓ Metrics: 50% improvement (Q1)
   ✓ Skills: Python, Docker

2. Creating Blackboard...
   ✓ Blackboard created
   ✓ Selected 1 evidence cards

3. Creating ClaimMapping...
   ✓ Claim created: bullet-1
   ✓ References 1 evidence card(s)

4. Loading config...
   ✓ Config loaded: 5 agents configured

5. Validating Blackboard state...
   ✓ State valid: True

============================================================
✅ All tests passed!
============================================================
```

### 2. Comprehensive Interactive Test

**Full demonstration of all schema features:**

```bash
python examples/test_schemas_interactive.py
```

**Tests:**
- ✓ EvidenceCard with all field types (metrics, scope, skills)
- ✓ Invalid timeframe format validation (should fail)
- ✓ Blackboard helper methods
- ✓ ClaimMapping truthfulness enforcement
- ✓ All pipeline models (RoleProfile, EvidenceMapping, GapResolution, etc.)
- ✓ JSON serialization round-trip
- ✓ Configuration inspection
- ✓ JSON Schema export

### 3. Unit Tests (Pytest)

**Automated test suite:**

```bash
pytest tests/unit/test_schemas_*.py -v
```

**Test Coverage:**
- ✓ 23 tests total
- ✓ 11 EvidenceCard tests
- ✓ 12 Blackboard tests
- ✓ 100% pass rate

**Run specific test file:**
```bash
pytest tests/unit/test_schemas_evidence_card.py -v
pytest tests/unit/test_schemas_blackboard.py -v
```

---

## Interactive Testing in Python

### Example 1: Create and Validate EvidenceCard

```python
from resumeforge.schemas import EvidenceCard, MetricEntry, ScopeInfo

# Create an evidence card
card = EvidenceCard(
    id="my-project",
    project="Performance Optimization",
    company="Tech Corp",
    timeframe="2020-2024",  # ✅ Validated format
    role="Senior Engineer",
    scope=ScopeInfo(
        team_size=5,
        geography=["US", "UK"]
    ),
    metrics=[
        MetricEntry(value="75%", description="reduction in latency"),
        MetricEntry(value="340K+", description="requests per second", context="peak")
    ],
    skills=["Python", "Docker", "AWS"],
    leadership_signals=["mentored 3 engineers"],
    raw_text="Led team of 5 engineers..."
)

# Use helper methods
print(card.get_metrics_summary())
# Output: "75% reduction in latency, 340K+ requests per second (peak)"

print(card.get_skills_summary())
# Output: "Python, Docker, AWS"

# Try invalid timeframe (should fail)
try:
    invalid_card = EvidenceCard(
        id="invalid",
        project="Test",
        company="Test",
        timeframe="2020/2024",  # ❌ Invalid format
        role="Engineer",
        raw_text="Test"
    )
except Exception as e:
    print(f"Correctly rejected: {e}")
```

### Example 2: Blackboard State Management

```python
from resumeforge.schemas import Blackboard, Inputs

# Create blackboard
inputs = Inputs(
    job_description="Looking for senior engineer...",
    target_title="Senior Engineering Manager",
    template_path="./templates/base.md"
)
blackboard = Blackboard(inputs=inputs)

# Add evidence cards
blackboard.evidence_cards = [card]  # from Example 1
blackboard.selected_evidence_ids = [card.id]

# Use helper methods
selected = blackboard.get_selected_evidence_cards()
print(f"Selected {len(selected)} cards")

found_card = blackboard.get_evidence_card_by_id("my-project")
print(f"Found card: {found_card.id}")

# Validate state
is_valid, errors = blackboard.validate_state()
print(f"State valid: {is_valid}")
if errors:
    print(f"Errors: {errors}")
```

### Example 3: ClaimMapping Truthfulness Validation

```python
from resumeforge.schemas import ClaimMapping

# Valid claim (has evidence)
claim1 = ClaimMapping(
    bullet_id="bullet-1",
    bullet_text="Led team achieving 75% reduction in latency",
    evidence_card_ids=["my-project"]  # ✅ References evidence
)
print(f"Claim valid: {claim1.bullet_id}")

# Invalid claim (no evidence - should fail)
try:
    claim2 = ClaimMapping(
        bullet_id="invalid",
        bullet_text="Some claim",
        evidence_card_ids=[]  # ❌ Empty - violates truthfulness
    )
except Exception as e:
    print(f"Correctly rejected empty evidence: {e}")

# Validate against available cards
available_ids = {"my-project", "other-card"}
is_valid = claim1.validate_against_cards(available_ids)
print(f"Claim references valid cards: {is_valid}")
```

### Example 4: Configuration Inspection

```python
from resumeforge.config import load_config

# Load config
cfg = load_config("config.yaml")

# Inspect agents
print(f"Configured agents: {len(cfg.agents)}")
for agent_name, agent_config in cfg.agents.items():
    print(f"  {agent_name}:")
    print(f"    - Model: {agent_config.get('model_alias')}")
    print(f"    - Temperature: {agent_config.get('temperature')}")
    print(f"    - Max tokens: {agent_config.get('max_tokens')}")

# Inspect models
print(f"\nModel aliases: {len(cfg.models)}")
for alias, model_config in cfg.models.items():
    print(f"  {alias}: {model_config.get('provider')} - {model_config.get('model')}")
```

### Example 5: JSON Serialization

```python
from resumeforge.schemas import EvidenceCard

# Create card
card = EvidenceCard(
    id="json-test",
    project="Test",
    company="Test Co",
    timeframe="2020-2024",
    role="Engineer",
    raw_text="Test"
)

# Serialize to JSON
json_str = card.model_dump_json(indent=2)
print(json_str)

# Deserialize from JSON
card2 = EvidenceCard.model_validate_json(json_str)
assert card2.id == card.id
print("✓ Round-trip successful")
```

---

## Test Results Summary

### Unit Tests

```
✓ 23 tests passing
✓ EvidenceCard: 11 tests
✓ Blackboard: 12 tests
✓ Coverage: 100% for EvidenceCard, 95% for Blackboard
```

### Example Scripts

```
✓ quick_schema_test.py: All tests passing
✓ test_schemas_interactive.py: All tests passing
```

---

## Validation Features Tested

### ✅ EvidenceCard Validation

- **Timeframe format**: Validates YYYY-YYYY or YYYY-MM to YYYY-MM
- **Required fields**: All required fields validated
- **Helper methods**: get_metrics_summary(), get_skills_summary()

### ✅ Blackboard Validation

- **State validation**: Validates state for current pipeline step
- **Reference validation**: Ensures evidence_card_ids exist
- **Claim validation**: Validates claim_index references

### ✅ ClaimMapping Validation

- **Truthfulness guarantee**: Empty evidence_card_ids rejected
- **Reference validation**: Invalid card IDs detected

---

## Next Steps

Once you're satisfied with schema testing:

1. **Phase 3**: Implement Provider Abstraction Layer
   - Enable LLM API calls
   - Test with real providers

2. **Phase 4**: Implement Fact Resume Parser
   - Parse resumes into evidence cards
   - Test with sample resumes

3. **Phase 5**: Implement Agents
   - JD Analyst, Evidence Mapper, Writer, Auditor
   - Test agent logic with mock providers

---

## Troubleshooting

### Import Errors

If you get import errors, make sure you're in the virtual environment:

```bash
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows
```

### Module Not Found

If schemas can't be imported:

```bash
# Make sure package is installed
pip install -e .
```

### Validation Errors

If validation fails, check:
- Timeframe format (must be YYYY-YYYY or YYYY-MM to YYYY-MM)
- Required fields are present
- evidence_card_ids is not empty for ClaimMapping

---

**Happy Testing! 🚀**
