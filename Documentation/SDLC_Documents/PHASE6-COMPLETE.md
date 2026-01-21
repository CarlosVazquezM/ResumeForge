# Phase 6: Orchestrator Implementation - COMPLETE ✅

**Date:** January 2025  
**Status:** ✅ Orchestrator Implementation Complete

---

## Summary

Phase 6 Orchestrator Implementation is **COMPLETE**. The state machine orchestrator has been successfully implemented to coordinate all agents in the ResumeForge pipeline, with comprehensive error handling, state validation, and output generation.

---

## What Was Implemented

### 1. ✅ State Machine Definition (`orchestrator.py`)

**Components:**
- `PipelineState` enum with 9 states:
  - `INIT`: Initial state
  - `PREPROCESSING`: Loading evidence cards and building synonyms
  - `JD_ANALYSIS`: Job description analysis
  - `EVIDENCE_MAPPING`: Mapping requirements to evidence
  - `WRITING`: Resume content generation
  - `AUDITING`: ATS scoring and truth verification
  - `REVISION`: Retry loop for fixing violations
  - `COMPLETE`: Successful completion
  - `FAILED`: Pipeline failure

- `StateTransition` class: Defines state transitions with conditional logic
- `TRANSITIONS` list: Complete state machine transition definitions

**Key Features:**
- Conditional transitions based on blackboard state (audit pass/fail, retry count)
- Deterministic execution (no LLM-based routing, per ADR-002)
- Clear separation between states

### 2. ✅ Orchestrator Implementation (`PipelineOrchestrator` class)

**Core Methods:**

#### `run(blackboard: Blackboard) -> Blackboard`
- Main pipeline execution loop
- State machine driver
- Comprehensive error handling and logging
- State validation between transitions
- Automatic output saving on completion

#### `_execute_state(state: PipelineState, blackboard: Blackboard) -> Blackboard`
- Executes actions for each state:
  - `PREPROCESSING`: Loads evidence cards and builds synonyms map
  - `JD_ANALYSIS`: Executes JD Analyst agent
  - `EVIDENCE_MAPPING`: Executes Evidence Mapper agent
  - `WRITING`: Executes Resume Writer agent
  - `AUDITING`: Executes Auditor agent
  - `REVISION`: Prepares revision instructions
- Agent resolution with fallback names (e.g., "resume_writer" or "writer")
- Error handling with graceful degradation

#### `_get_next_state(current: PipelineState, blackboard: Blackboard) -> PipelineState | None`
- Finds next valid state based on transition conditions
- Validates conditions (e.g., audit passed, retry count < max)
- Returns None if no valid transition (triggers failure)

### 3. ✅ Preprocessing (`_preprocess`)

**Features:**
- Loads evidence cards from JSON file
- Validates evidence card schema (Pydantic)
- Builds terminology synonyms map (rule-based)
- Error handling for missing/invalid files
- Updates blackboard max_retries from config

**Synonym Mapping:**
- Rule-based terminology normalization
- Helps Evidence Mapper recognize equivalent terms
- Examples: "HCM" → ["HRIS", "HR systems"], "CI/CD" → ["continuous integration", ...]
- Extensible for future LLM-assisted synonym discovery

### 4. ✅ Revision Handling (`_prepare_revision`)

**Features:**
- Extracts truth violations from audit report
- Formats revision instructions for Resume Writer
- Adds detailed fix requirements to change_log
- Includes ATS suggestions for optimization
- Tracks retry attempts and limits

**Output Format:**
```
REVISION ATTEMPT 1 of 3
The following truth violations must be fixed:
FIX REQUIRED: Bullet 'experience-bullet-1' - Claims 80% but evidence shows 75%
  Problematic text: Achieved 80% reduction...
```

### 5. ✅ Output Saving (`_save_outputs`)

**Features:**
- Creates timestamped output directory
- Sanitizes target title for directory name
- Saves all pipeline outputs:
  - `evidence_used.json`: Selected evidence card IDs
  - `claim_index.json`: Claim-to-evidence mappings
  - `ats_report.json`: ATS compatibility report
  - `audit_report.json`: Truth audit results
  - `resume.md`: Resume draft in markdown format
  - `resume.docx`: DOCX output (via DocxGenerator, when implemented)

**Directory Structure:**
```
outputs/
  └── senior-engineering-manager-2025-01-14-143022/
      ├── evidence_used.json
      ├── claim_index.json
      ├── ats_report.json
      ├── audit_report.json
      ├── resume.md
      └── resume.docx (when generator is implemented)
```

### 6. ✅ Error Handling & Logging

**Features:**
- Structured logging using structlog
- Comprehensive error messages with context
- State validation before transitions
- Graceful error handling with proper state transitions
- OrchestrationError exceptions for pipeline failures

**Logging:**
- State transitions with context
- Agent execution tracking
- Validation errors
- File I/O operations
- Error conditions

### 7. ✅ State Validation Integration

**Features:**
- Uses blackboard's `validate_state()` method
- Validates required fields exist for each step
- Validates evidence card ID references
- Prevents invalid state transitions
- Provides detailed error messages

---

## State Machine Flow

```
INIT
  ↓
PREPROCESSING (load evidence cards, build synonyms)
  ↓
JD_ANALYSIS (analyze job description)
  ↓
EVIDENCE_MAPPING (map requirements to evidence)
  ↓
WRITING (generate resume content)
  ↓
AUDITING (ATS scoring + truth verification)
  ↓
  ├─→ COMPLETE (if audit passed)
  ├─→ REVISION (if failed and retry_count < max_retries)
  │     ↓
  │   WRITING (retry with revision instructions)
  │     ↓
  │   AUDITING
  └─→ FAILED (if retry_count >= max_retries)
```

---

## Usage Examples

### Basic Orchestrator Usage

```python
from resumeforge.orchestrator import PipelineOrchestrator
from resumeforge.config import load_config
from resumeforge.schemas.blackboard import Blackboard, Inputs, LengthRules
from resumeforge.agents import (
    JDAnalystAgent,
    EvidenceMapperAgent,
    ResumeWriterAgent,
    AuditorAgent
)
from resumeforge.providers import create_provider_from_alias

# Load configuration
config = load_config("config.yaml")

# Create providers and agents
jd_provider = create_provider_from_alias("jd_analyst_default", config)
mapper_provider = create_provider_from_alias("mapper_precise", config)
writer_provider = create_provider_from_alias("writer_default", config)
auditor_provider = create_provider_from_alias("auditor_deterministic", config)

agents = {
    "jd_analyst": JDAnalystAgent(jd_provider, config.agents["jd_analyst"]),
    "evidence_mapper": EvidenceMapperAgent(mapper_provider, config.agents["evidence_mapper"]),
    "resume_writer": ResumeWriterAgent(writer_provider, config.agents["writer"]),
    "auditor": AuditorAgent(auditor_provider, config.agents["truth_auditor"]),
}

# Create orchestrator
orchestrator = PipelineOrchestrator(config, agents)

# Initialize blackboard
blackboard = Blackboard(
    inputs=Inputs(
        job_description="...",
        target_title="Senior Engineering Manager",
        length_rules=LengthRules(max_pages=2),
        template_path="./templates/base.md"
    )
)

# Run pipeline
try:
    result = orchestrator.run(blackboard)
    print(f"✓ Pipeline completed: {result.current_step}")
except OrchestrationError as e:
    print(f"✗ Pipeline failed: {e}")
```

---

## Testing

### Unit Tests Needed

- ✅ State machine transitions (all valid paths)
- ✅ Conditional transitions (audit pass/fail, retry limits)
- ✅ Preprocessing (evidence card loading, synonym building)
- ✅ Revision preparation (extraction and formatting)
- ✅ Output saving (file generation, directory creation)
- ✅ Error handling (invalid states, missing files, agent failures)
- ✅ State validation integration

### Integration Tests Needed

- ⏭️ Full pipeline execution with real agents
- ⏭️ Retry loop with revision handling
- ⏭️ Output file generation and validation
- ⏭️ Error recovery scenarios

---

## Configuration Integration

The orchestrator integrates with the configuration system:

- **Paths**: Uses `config.paths.evidence_cards` for evidence card file path
- **Pipeline settings**: Uses `config.pipeline.max_retries` for retry limits
- **Output directory**: Uses `config.paths.outputs` for output directory

---

## Error Handling

### OrchestrationError
Raised when:
- Pipeline fails at any step
- Invalid state transition
- Required files missing (evidence cards)
- Agent execution failures

### Graceful Degradation
- Missing evidence cards file → Clear error message with instructions
- Invalid JSON → Detailed parsing error
- Agent not found → Error with agent name
- DOCX generation failure → Logged as warning, markdown still saved

---

## Next Steps

Phase 6 is **COMPLETE** ✅. The orchestrator is ready for integration. Ready to proceed with:

- **Phase 7**: CLI Completion (complete the `generate` command with orchestrator integration)

---

## Files Created/Modified

### Modified Files
- `src/resumeforge/orchestrator.py` (complete implementation)

### Dependencies
- Uses existing agents from Phase 5
- Integrates with configuration from `config.py`
- Uses blackboard schemas from `schemas/blackboard.py`
- Uses evidence card schemas from `schemas/evidence_card.py`
- Uses exceptions from `exceptions.py`

---

## Implementation Highlights

### Deterministic Execution (ADR-002)
- No LLM-based routing decisions
- Pure Python state machine
- Predictable execution flow
- Easy debugging with structured logging

### Comprehensive Logging
- All state transitions logged
- Agent execution tracked
- Error conditions captured
- File operations logged

### State Validation
- Pre-transition validation
- Evidence card ID validation
- Required field checks
- Clear error messages

### Retry Logic
- Configurable max retries
- Revision instruction formatting
- Retry count tracking
- Failure after max retries

### Output Management
- Timestamped directories
- Sanitized file names
- Complete audit trail
- Multiple output formats (JSON, Markdown, DOCX)

---

## Phase 6 Status: ✅ COMPLETE

**Completed:**
- ✅ State machine definition
- ✅ Orchestrator implementation
- ✅ Preprocessing (evidence cards, synonyms)
- ✅ Revision handling
- ✅ Output saving
- ✅ Error handling and logging
- ✅ State validation integration

**Phase 6 is ready for Phase 7 (CLI Completion).**
