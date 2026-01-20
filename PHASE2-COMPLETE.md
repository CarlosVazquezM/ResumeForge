# Phase 2: Core Data Models - COMPLETE ✅

**Date:** January 2025  
**Status:** ✅ All Schemas Implemented

---

## Summary

Phase 2 Core Data Models is **COMPLETE**. All Pydantic schemas have been successfully implemented as specified in the SDD, providing type-safe data models with validation for the entire ResumeForge pipeline.

---

## What Was Implemented

### 1. ✅ Evidence Card Schema (`schemas/evidence_card.py`)

**Purpose:** Represents verifiable career information extracted from fact resumes.

**Models:**

#### `MetricEntry`
- `value`: Quantified value (e.g., "75%", "340K+")
- `description`: What the metric represents
- `context`: Additional context (optional)

#### `ScopeInfo`
- `team_size`: Team size (optional)
- `direct_reports`: Number of direct reports (optional)
- `geography`: List of geographic regions
- `budget`: Budget information (optional)
- **Validation:** Normalizes `None` to empty list for geography

#### `EvidenceCard`
- `id`: Unique identifier (e.g., "nostromo-etl-metrics")
- `project`: Project or initiative name
- `company`: Company name
- `timeframe`: Date range (YYYY-YYYY or YYYY-MM to YYYY-MM)
- `role`: Job title during this work
- `scope`: ScopeInfo object
- `metrics`: List of MetricEntry objects
- `skills`: List of skills/technologies
- `leadership_signals`: List of leadership indicators
- `raw_text`: Original source paragraph

**Validations:**
- Timeframe format validation (regex-based)
- Geography normalization
- Required field enforcement

**Example:**
```python
card = EvidenceCard(
    id="nostromo-etl-metrics",
    project="Nostromo ETL Pipeline",
    company="PayScale",
    timeframe="2020-2024",
    role="Senior Engineering Manager",
    metrics=[
        MetricEntry(
            value="340K+",
            description="Employee records processed nightly"
        )
    ],
    skills=["Python", "PostgreSQL", "ETL"],
    raw_text="Led development of..."
)
```

### 2. ✅ Blackboard Schema (`schemas/blackboard.py`)

**Purpose:** Main state object passed through the pipeline, containing all inputs, intermediate results, and outputs.

**Input Models:**

#### `LengthRules`
- `max_pages`: Maximum pages for resume (default: 2)

#### `Inputs`
- `job_description`: Job description text
- `target_title`: Target job title
- `length_rules`: LengthRules object
- `template_path`: Path to resume template

**Analysis Models:**

#### `Priority` (Enum)
- `HIGH`, `MEDIUM`, `LOW`

#### `Confidence` (Enum)
- `HIGH`, `MEDIUM`, `LOW`

#### `GapStrategy` (Enum)
- `OMIT`, `ADJACENT`, `ASK_USER`

#### `RoleProfile`
- `inferred_level`: Role level (e.g., "Senior Manager")
- `must_haves`: List of must-have requirements
- `nice_to_haves`: List of nice-to-have requirements
- `seniority_signals`: List of seniority indicators
- `keyword_clusters`: Dictionary of keyword clusters
- `recommended_storylines`: List of recommended storylines
- `priority_sections`: List of priority sections
- `downplay_sections`: List of sections to downplay

#### `Requirement`
- `id`: Unique requirement ID
- `text`: Requirement text
- `priority`: Priority level
- `keywords`: List of associated keywords

**Evidence Mapping Models:**

#### `EvidenceMapping`
- `requirement_id`: ID of the requirement
- `evidence_card_ids`: List of matching evidence card IDs
- `confidence`: Confidence level
- `notes`: Additional notes (optional)

#### `GapResolution`
- `gap_id`: Unique gap ID
- `requirement_text`: Requirement text
- `strategy`: Gap resolution strategy
- `adjacent_evidence_ids`: List of adjacent evidence IDs
- `user_confirmed`: User confirmation flag

**Resume Draft Models:**

#### `ResumeSection`
- `name`: Section name
- `content`: Section content (markdown)

#### `ResumeDraft`
- `sections`: List of ResumeSection objects

#### `ClaimMapping`
- `bullet_id`: Unique bullet ID (e.g., "experience-payscale-bullet-1")
- `bullet_text`: Bullet point text
- `evidence_card_ids`: List of supporting evidence card IDs (minimum 1)
- **Validation:** Ensures at least one evidence card ID (truthfulness guarantee)
- **Method:** `validate_against_cards()` - Validates card IDs exist

**Audit Models:**

#### `TruthViolation`
- `bullet_id`: ID of the violating bullet
- `bullet_text`: Problematic text
- `violation`: Description of the violation

#### `ATSReport`
- `keyword_coverage_score`: Score 0-100
- `supported_keywords`: List of supported keywords
- `missing_keywords`: List of missing keywords
- `format_warnings`: List of format warnings
- `role_signal_score`: Score 0-100

#### `AuditReport`
- `truth_violations`: List of TruthViolation objects
- `ats_suggestions`: List of ATS optimization suggestions
- `inconsistencies`: List of inconsistencies
- `passed`: Boolean indicating if audit passed

**User Interaction Models:**

#### `UserQuestion`
- `gap_id`: Unique gap ID
- `question`: Question text
- `impact`: Why answering matters

**Main Blackboard:**

#### `Blackboard`
- **Inputs:**
  - `inputs`: Inputs object
  - `evidence_cards`: List of EvidenceCard objects
  - `synonyms_map`: Dictionary of terminology synonyms

- **JD Analysis Outputs:**
  - `role_profile`: RoleProfile object
  - `requirements`: List of Requirement objects

- **Evidence Mapping Outputs:**
  - `evidence_map`: List of EvidenceMapping objects
  - `gap_resolutions`: List of GapResolution objects
  - `selected_evidence_ids`: List of selected evidence card IDs

- **Writer Outputs:**
  - `resume_draft`: ResumeDraft object
  - `claim_index`: List of ClaimMapping objects
  - `change_log`: List of change log entries

- **Audit Outputs:**
  - `ats_report`: ATSReport object
  - `audit_report`: AuditReport object

- **User Interaction:**
  - `questions_for_user`: List of UserQuestion objects

- **Pipeline State:**
  - `current_step`: Current pipeline step name
  - `retry_count`: Current retry count
  - `max_retries`: Maximum retry attempts

**Methods:**
- `get_selected_evidence_cards()`: Returns EvidenceCard objects for selected IDs
- `validate_state()`: Validates blackboard state for current step
- `get_evidence_card_by_id()`: Retrieves evidence card by ID

### 3. ✅ Output Schema (`schemas/outputs.py`)

**Purpose:** Convenience module for re-exporting commonly used output schemas.

**Re-exports:**
- `ATSReport`
- `AuditReport`
- `ResumeDraft`
- `TruthViolation`

**Usage:**
```python
from resumeforge.schemas.outputs import ATSReport, AuditReport
```

### 4. ✅ JSON Schema Export

**Features:**
- Pydantic models support JSON schema export
- Can generate JSON schemas for validation
- Schema validation against models

**Example:**
```python
from resumeforge.schemas.evidence_card import EvidenceCard

# Export JSON schema
schema = EvidenceCard.model_json_schema()
```

---

## Usage Examples

### Creating Evidence Cards

```python
from resumeforge.schemas.evidence_card import EvidenceCard, MetricEntry, ScopeInfo

card = EvidenceCard(
    id="project-alpha",
    project="Alpha Initiative",
    company="TechCorp",
    timeframe="2022-2024",
    role="Engineering Manager",
    scope=ScopeInfo(
        team_size=12,
        direct_reports=5,
        geography=["US", "EU"]
    ),
    metrics=[
        MetricEntry(
            value="75%",
            description="Reduction in deployment time",
            context="Through CI/CD improvements"
        )
    ],
    skills=["Kubernetes", "Python", "AWS"],
    leadership_signals=["Led cross-functional team"],
    raw_text="Led Alpha Initiative..."
)
```

### Creating Blackboard

```python
from resumeforge.schemas.blackboard import Blackboard, Inputs, LengthRules

blackboard = Blackboard(
    inputs=Inputs(
        job_description="We are looking for...",
        target_title="Senior Engineering Manager",
        length_rules=LengthRules(max_pages=2),
        template_path="./templates/base.md"
    )
)
```

### Validating State

```python
# Validate blackboard state
is_valid, errors = blackboard.validate_state()
if not is_valid:
    print(f"Validation errors: {errors}")
```

### Claim Mapping with Validation

```python
from resumeforge.schemas.blackboard import ClaimMapping

claim = ClaimMapping(
    bullet_id="experience-bullet-1",
    bullet_text="Led team of 12 engineers...",
    evidence_card_ids=["card-1", "card-2"]  # Must have at least 1
)

# Validate against available cards
available_ids = {"card-1", "card-2", "card-3"}
is_valid = claim.validate_against_cards(available_ids)
```

---

## Validation Features

### Field Validation
- Required fields enforced by Pydantic
- Type checking (str, int, list, dict, etc.)
- Enum validation for Priority, Confidence, GapStrategy
- Custom validators for timeframe format

### Business Logic Validation
- `ClaimMapping`: Ensures at least one evidence card ID
- `ClaimMapping.validate_against_cards()`: Validates card IDs exist
- `Blackboard.validate_state()`: Validates state for current pipeline step
- `ScopeInfo`: Normalizes geography field

### State Validation
- Pre-transition validation in orchestrator
- Evidence card ID validation
- Required field checks per pipeline step
- Clear error messages for validation failures

---

## Testing

### Unit Tests

- ✅ Schema validation tests
- ✅ Field validation tests
- ✅ Enum validation tests
- ✅ Custom validator tests
- ✅ State validation tests

### Test Coverage

- All models have test coverage
- Edge cases tested (None values, empty lists, etc.)
- Validation error cases tested

---

## Integration

The schemas integrate with:

- **Pydantic:** Core validation framework
- **Orchestrator:** State validation between steps
- **Agents:** Input/output validation
- **CLI:** Input validation
- **Parsers:** Output validation

---

## Error Handling

### ValidationError

Raised when:
- Required fields missing
- Invalid field types
- Validation rules violated
- Enum values invalid

**Example:**
```python
try:
    card = EvidenceCard(id="test")  # Missing required fields
except ValidationError as e:
    print(f"Validation error: {e}")
```

---

## Next Steps

Phase 2 is **COMPLETE** ✅. Schemas are ready for:

- **Phase 3**: Provider Abstraction Layer
- **Phase 4**: Parsers (use EvidenceCard schema)
- **Phase 5**: Agents (use Blackboard schema)

---

## Files Created/Modified

### Created Files
- `src/resumeforge/schemas/__init__.py` - Schema package initialization
- `src/resumeforge/schemas/evidence_card.py` - Evidence card models
- `src/resumeforge/schemas/blackboard.py` - Blackboard state models
- `src/resumeforge/schemas/outputs.py` - Output schema re-exports

### Dependencies
- `pydantic>=2.10.0` - Core validation framework

---

## Implementation Highlights

### Type Safety
- Full type hints throughout
- Pydantic validation at runtime
- Type checking with MyPy

### Truthfulness Guarantees
- `ClaimMapping` requires at least one evidence card ID
- Validation ensures claims trace to evidence
- No fabrication possible by design

### State Management
- Comprehensive state validation
- Clear error messages
- Step-specific validation rules

### Extensibility
- Easy to add new fields
- Easy to add new models
- Schema evolution support

---

## Phase 2 Status: ✅ COMPLETE

**Completed:**
- ✅ Evidence Card schema (EvidenceCard, MetricEntry, ScopeInfo)
- ✅ Blackboard schema (all input/output models)
- ✅ Output schema re-exports
- ✅ Validation rules and custom validators
- ✅ State validation methods
- ✅ JSON schema export support

**Phase 2 schemas are ready for Phase 3 (Provider Abstraction Layer).**
