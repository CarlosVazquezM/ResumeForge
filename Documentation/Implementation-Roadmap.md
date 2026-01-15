# ResumeForge Implementation Roadmap

**Generated:** January 2025  
**Last Updated:** January 2025  
**Status:** Configuration Complete - Ready for Code Implementation

---

## Quick Status

### ✅ Completed
- ✅ `pyproject.toml` - All dependencies configured
- ✅ `config.yaml` - All 5 agents configured per ADR-004
- ✅ `.cursor/rules` - Project rules and guidelines
- ✅ Configuration verification - Aligned with ADR/SAD/SDD

### ⏭️ Next Steps
- [ ] Create project directory structure (`src/resumeforge/`)
- [ ] Implement core schemas (Pydantic models)
- [ ] Implement provider abstraction layer
- [ ] Implement agents (5 agents)
- [ ] Implement orchestrator
- [ ] Implement CLI and output generation

**Estimated Time to MVP:** 5 weeks (part-time) or 2-3 weeks (full-time)

---

## Executive Summary

You have **excellent, comprehensive documentation** covering architecture, design, and workflow. The project is well-planned with clear technical specifications. **Project configuration is complete** (`pyproject.toml`, `config.yaml`) and verified against architecture decisions. However, **no implementation code exists yet**. This document outlines the critical path to move from configuration to a working MVP.

---

## Current State Analysis

### ✅ What You Have (Strengths)

1. **Complete Architecture Documentation**
   - **ADR.md**: 10 well-reasoned architecture decisions
   - **SAD.md**: Comprehensive solution architecture with C4 diagrams
   - **SDD.md**: Detailed technical specifications with code examples
   - **UserWorkFlow.md**: Clear user journey and CLI usage patterns

2. **Well-Defined Technical Specifications**
   - Data models (Evidence Cards, Blackboard State)
   - Agent specifications with prompt templates
   - Orchestrator state machine design
   - Provider abstraction layer design
   - CLI command specifications

3. **Clear Design Principles**
   - Evidence-first approach (no hallucination)
   - Deterministic orchestration (no LLM routing)
   - Multi-provider strategy (cost optimization)
   - Privacy by default (local storage)

### ✅ What's Already Done

1. **Project Configuration** ✅
   - `pyproject.toml` - Complete with all dependencies
   - `config.yaml` - Complete with all agents configured per ADR-004
   - `.cursor/rules` - Complete project rules and guidelines
   - `.gitignore` - Complete Python gitignore

2. **Architecture Alignment** ✅
   - Configuration verified against ADR/SAD/SDD
   - All 5 agents configured correctly
   - Model assignments match ADR-004
   - Dependencies match requirements

### ❌ What's Missing (Gaps)

1. **No Code Implementation**
   - Zero Python files
   - No project structure (directories not created)
   - Package code not implemented

2. **Development Infrastructure (Partial)**
   - ✅ `pyproject.toml` - Done
   - ✅ `config.yaml` - Done
   - ❌ `.env.example` template - Missing
   - ❌ Project directory structure - Not created
   - ❌ Test framework setup - Not initialized

3. **No Sample Data**
   - No example Fact Resume
   - No sample evidence cards
   - No template resume structure
   - No test job descriptions

---

## Critical Path to MVP

### Phase 1: Foundation Setup (Days 1-2) ✅ Partially Complete

**Goal:** Establish project structure and core infrastructure

**Status:**
- ✅ `pyproject.toml` - Complete with all dependencies
- ✅ `config.yaml` - Complete with all agents configured
- ✅ `.cursor/rules` - Complete project rules
- ❌ Project directory structure - Not created yet
- ❌ `.env.example` - Not created yet

#### 1.1 Project Structure Setup (TODO)

**Note:** Project structure follows `src/` layout as defined in `pyproject.toml` and `.cursor/rules`:

```
resumeforge/
├── src/
│   └── resumeforge/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── orchestrator.py
│       ├── agents/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── jd_analyst.py
│       │   ├── evidence_mapper.py
│       │   ├── resume_writer.py
│       │   └── auditor.py
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── openai_provider.py
│       │   ├── anthropic_provider.py
│       │   ├── google_provider.py
│       │   └── groq_provider.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── evidence_card.py
│       │   ├── blackboard.py
│       │   └── outputs.py
│       ├── parsers/
│       │   ├── __init__.py
│       │   ├── fact_resume_parser.py
│       │   └── jd_parser.py
│       ├── generators/
│       │   ├── __init__.py
│       │   └── docx_generator.py
│       └── utils/
│           ├── __init__.py
│           ├── tokens.py
│           └── diff.py
├── tests/
│   ├── __init__.py
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── data/
│   ├── templates/
│   ├── evidence_cards.json (generated)
│   └── synonyms.json
├── outputs/
│   └── (generated per job)
├── config.yaml ✅ (exists)
├── .env.example (TODO)
├── pyproject.toml ✅ (exists)
└── README.md (TODO)
```

**Tasks:**
- [ ] Create all directory structure
- [ ] Create all `__init__.py` files
- [ ] Create stub files for main modules

#### 1.2 Dependencies & Configuration ✅ COMPLETE

**Status:** Already done!

- ✅ `pyproject.toml` with all dependencies:
  - `pydantic>=2.10.0` (data validation)
  - `click>=8.1.0` (CLI framework)
  - `openai`, `anthropic`, `google-genai`, `groq` (LLM SDKs)
  - `python-docx` (DOCX generation)
  - `pyyaml` (config loading)
  - `pytest`, `pytest-cov`, `pytest-asyncio` (testing)
  - `tiktoken` (token counting)
  - `structlog` (structured logging)
  - `tenacity` (retry logic)
  - `httpx` (HTTP client)
  
- ✅ `config.yaml` with all agents configured:
  - All 5 agents: `jd_analyst`, `evidence_mapper`, `writer`, `ats_scorer`, `truth_auditor`
  - Model aliases matching ADR-004 specifications
  - Provider configurations
  - Fallback chains

**No action needed** - Ready to proceed with code implementation.

#### 1.3 Environment Setup (TODO)

**Tasks:**
- [ ] Create `.env.example` template with API key placeholders
- [ ] Document API key requirements in README
- [ ] Set up logging configuration module

**Deliverable:** Project skeleton that can be imported and basic CLI command works

---

### Phase 2: Core Data Models (Days 2-4)

**Goal:** Implement Pydantic schemas as specified in SDD

#### 2.1 Schema Implementation Priority

1. **Evidence Card Schema** (SDD Section 3.1)
   - `EvidenceCard` model
   - `MetricEntry` model
   - `ScopeInfo` model
   - Validation rules

2. **Blackboard Schema** (SDD Section 3.2)
   - All input/output models
   - State management models
   - JSON schema export capability

3. **Output Schemas**
   - `ATSReport`
   - `AuditReport`
   - `ResumeDraft`

**Deliverable:** All schemas implemented with tests, JSON schema export working

---

### Phase 3: Provider Abstraction Layer (Days 3-5)

**Goal:** Implement multi-provider support as per SDD Section 6

#### 3.1 Implementation Order

1. **Base Provider Interface** (SDD 6.1)
   - Abstract base class
   - Standardized `complete()` method
   - Token counting interface

2. **Provider Implementations**
   - OpenAI Provider (SDD 6.2) - **Start here** (easiest)
   - Anthropic Provider (SDD 6.3) - **Critical** (most agents use this)
   - Google Provider (for ATS scoring)
   - Groq Provider (optional fallback)
   - DeepSeek Provider (optional fallback)

3. **Provider Factory** (SDD 6.4)
   - Dynamic provider creation from config
   - API key validation
   - Error handling

**Deliverable:** Can create providers from config, make API calls, handle errors gracefully

**Testing Strategy:**
- Mock API responses for unit tests
- Integration tests with real APIs (gated behind flag)
- Test rate limiting and retry logic

---

### Phase 4: Parsers (Days 5-7)

**Goal:** Parse Fact Resume into Evidence Cards

#### 4.1 Fact Resume Parser

**Challenge:** This is the most complex part - parsing unstructured resume text into structured Evidence Cards.

**Approach Options:**

1. **LLM-Assisted Parsing** (Recommended for MVP)
   - Use Claude Sonnet 4 to parse resume text
   - Provide structured prompt with Evidence Card schema
   - Validate output against Pydantic models
   - Manual review step for first run

2. **Template-Based Parsing** (Future enhancement)
   - Markdown sections with specific format
   - Regex-based extraction
   - Hybrid approach

**Implementation:**
```python
# parsers/fact_resume_parser.py
class FactResumeParser:
    def __init__(self, provider: BaseProvider):
        self.provider = provider
    
    def parse(self, resume_path: Path) -> list[EvidenceCard]:
        # 1. Read resume text
        # 2. Call LLM with structured prompt
        # 3. Parse JSON response
        # 4. Validate with Pydantic
        # 5. Return list of EvidenceCard
```

**Deliverable:** `resumeforge parse` command works, generates `evidence_cards.json`

---

### Phase 5: Agents Implementation (Weeks 2-3)

**Goal:** Implement all 5 agents with their prompts

#### 5.1 Implementation Order (Priority)

1. **Base Agent Class** (SDD 4.1)
   - Abstract interface
   - Common execution pattern
   - Error handling

2. **JD Analyst Agent** (SDD 4.2) - **Start here**
   - Simpler than others
   - Good for testing provider integration
   - Output feeds everything else

3. **Evidence Mapper Agent** (SDD 4.3)
   - Critical for accuracy
   - Must enforce "no fabrication" rule strictly
   - Uses terminology normalization

4. **Resume Writer Agent** (SDD 4.4)
   - Most complex prompt
   - Output quality critical
   - Must generate claim_index

5. **Auditor Agent** (SDD 4.5)
   - Two sub-agents: ATS scorer + Truth verifier
   - Can run in parallel or sequence
   - Blocks pipeline if truth violations found

**Deliverable:** All agents can execute, parse responses, update blackboard

**Testing Strategy:**
- Unit tests with mocked LLM responses
- Test prompt templates with sample inputs
- Validate JSON parsing and error handling
- Test guardrail enforcement (e.g., no evidence card = fail)

---

### Phase 6: Orchestrator (Week 3)

**Goal:** Implement state machine orchestrator (SDD Section 5)

#### 6.1 Core Components

1. **State Machine** (SDD 5.1)
   - State enum
   - Transition definitions
   - Condition checking

2. **Orchestrator Implementation** (SDD 5.2)
   - Main `run()` loop
   - State execution handlers
   - Retry logic
   - Output saving

3. **Preprocessing** (SDD 5.2 `_preprocess`)
   - Load evidence cards
   - Build synonyms map
   - Initialize blackboard

4. **Revision Handling** (SDD 5.2 `_prepare_revision`)
   - Extract violations from audit
   - Format revision instructions
   - Handle max retries

**Deliverable:** Full pipeline executes end-to-end, handles errors, saves outputs

---

### Phase 7: CLI & Output Generation (Week 4)

**Goal:** Complete user interface and output formatting

#### 7.1 CLI Commands (SDD Section 7)

**Priority Order:**

1. `resumeforge parse` - Essential for setup
2. `resumeforge generate` - Core functionality
3. `resumeforge list` - View generated variants
4. `resumeforge show <variant> --evidence` - Debugging
5. `resumeforge diff` - Comparison utility
6. `resumeforge prep <variant>` - Interview prep
7. `resumeforge refresh --all` - Batch update

#### 7.2 DOCX Generation (SDD Section 8)

- Implement `DocxGenerator` class
- Markdown to DOCX conversion
- Template support
- Formatting (fonts, spacing, bullets)

#### 7.3 Output Files

- Resume DOCX
- Resume Markdown (for diffing)
- `evidence_used.json`
- `claim_index.json`
- `ats_report.json`
- `audit_report.json`
- `diff_from_base.md`

**Deliverable:** Complete CLI with all commands, DOCX output generation working

---

### Phase 8: Testing & Refinement (Week 5)

**Goal:** Ensure quality and reliability

#### 8.1 Test Coverage

1. **Unit Tests**
   - All schema validations
   - Provider abstractions (mocked)
   - Agent response parsing
   - Utility functions

2. **Integration Tests**
   - Agent + Provider (real APIs, but small inputs)
   - Full pipeline with minimal data
   - Error path testing

3. **Contract Tests**
   - Blackboard schema validation
   - Evidence Card schema validation
   - Output format validation

4. **E2E Tests**
   - Complete pipeline with sample data
   - Golden file comparison
   - Regression testing

#### 8.2 Sample Data Creation

- Create sample Fact Resume
- Generate test evidence cards
- Create test job descriptions
- Expected output fixtures

**Deliverable:** Test suite with >80% coverage, sample data for demos

---

## Risk Mitigation Recommendations

### High-Risk Areas

1. **Evidence Card Parsing Accuracy**
   - **Risk:** LLM may miss or misinterpret resume content
   - **Mitigation:** 
     - Implement validation checks
     - Add manual review step for first parse
     - Provide editing capability for evidence cards JSON

2. **Truth Auditor False Negatives**
   - **Risk:** Missing fabricated claims
   - **Mitigation:**
     - Strict prompt with examples
     - Multiple validation passes
     - User can review claim_index before submission

3. **API Cost Overruns**
   - **Risk:** Multiple LLM calls per resume = high cost
   - **Mitigation:**
     - Token counting and estimation
     - Cost logging per run
     - Provider selection optimization (as designed)

4. **Provider Rate Limiting**
   - **Risk:** API throttling blocks pipeline
   - **Mitigation:**
     - Implement exponential backoff
     - Provider fallback strategy
     - Graceful degradation

### Medium-Risk Areas

1. **Template Format Compatibility**
   - **Risk:** DOCX generation may not match expected format
   - **Mitigation:** Use `python-docx` best practices, test with real ATS systems

2. **Terminology Normalization**
   - **Risk:** Missing synonyms cause false gaps
   - **Mitigation:** Start with rule-based dictionary, expand based on usage

---

## Immediate Next Steps (This Week)

### Step 1: Project Initialization (Days 1-2)
- [ ] Create project directory structure (`src/resumeforge/`, `tests/`, `data/`, `outputs/`)
- [ ] Create all `__init__.py` files
- [ ] Create stub Python files for main modules
- [ ] Create `.env.example` template
- [ ] Create `README.md` with setup instructions
- [x] ~~Set up `pyproject.toml`~~ ✅ Already done
- [x] ~~Configure `config.yaml`~~ ✅ Already done

### Step 2: Core Schemas (Days 2-3)
- [ ] Implement `schemas/evidence_card.py`
- [ ] Implement `schemas/blackboard.py`
- [ ] Write unit tests for schemas
- [ ] Test JSON schema export

### Step 3: Provider Foundation (Days 3-4)
- [ ] Implement `providers/base.py` (abstract interface)
- [ ] Implement `providers/openai_provider.py` (with tiktoken token counting)
- [ ] Implement `providers/anthropic_provider.py` (critical - most agents use this)
- [ ] Implement `providers/google_provider.py` (for ATS scoring)
- [ ] Implement provider factory (from `config.yaml`)
- [ ] Test basic API calls with real keys

### Step 4: Basic CLI (Day 4)
- [ ] Implement `cli.py` using Click (already in dependencies)
- [ ] Implement `resumeforge --version` command
- [ ] Create stub for `resumeforge parse` command
- [ ] Create stub for `resumeforge generate` command
- [ ] Test CLI installation (`pip install -e .`)

---

## Success Criteria for MVP

✅ **Functional Requirements:**
- Can parse a Fact Resume into evidence cards
- Can analyze a job description
- Can map evidence to requirements
- Can generate a resume draft
- Can audit for truth violations
- Can output DOCX file

✅ **Quality Requirements:**
- Zero truth violations in output (by design)
- Pipeline completes in <5 minutes
- All claims traceable to evidence cards
- CLI is intuitive and well-documented

✅ **Technical Requirements:**
- Code follows SDD specifications
- Test coverage >70%
- Error handling for all failure modes
- Logging sufficient for debugging

---

## Post-MVP Enhancements (Future)

1. **Streamlit UI** (SAD mentions v2)
2. **Enhanced Terminology Normalization** (LLM-assisted synonym mapping)
3. **Batch Processing** (Generate multiple resumes at once)
4. **Template Library** (Multiple resume formats)
5. **Cover Letter Generation** (Out of scope for v1)
6. **Git Integration** (Version control for variants)
7. **Cost Analytics Dashboard**
8. **Interview Prep Question Generation**

---

## Recommended Development Approach

### Option A: Incremental (Recommended)
Build and test each component before moving to the next. This ensures each layer works before building on top.

**Pros:** Lower risk, easier debugging, incremental value  
**Cons:** Slower to see end-to-end results

### Option B: Vertical Slice (Faster Feedback)
Build a minimal end-to-end flow first (parse → one agent → output), then add remaining agents.

**Pros:** See results faster, validate architecture early  
**Cons:** More refactoring as you add features

**Recommendation:** Hybrid approach
- Build foundation (schemas, providers) incrementally
- Then build one vertical slice (parse → JD Analyst → simple output)
- Then add remaining agents incrementally

---

## Documentation Gaps to Address

While your documentation is excellent, consider adding:

1. **API Reference** - Generated from docstrings
2. **Troubleshooting Guide** - Common errors and solutions
3. **Cost Estimation Guide** - Help users budget for API usage
4. **Contributing Guide** - If open-sourcing
5. **Example Fact Resume** - Template format for users

---

## Conclusion

You have **exceptional planning documentation**. The architecture is well-thought-out, the design is detailed, and the specifications are clear. The main gap is **implementation code**.

**Recommended Timeline (Updated):**
- **Days 1-2:** Project structure + Environment setup ✅ (Partial: configs done)
- **Days 2-4:** Core Schemas + Providers (foundation)
- **Days 4-7:** Basic CLI + Fact Resume Parser
- **Weeks 2-3:** Agents Implementation (all 5 agents)
- **Week 3:** Orchestrator Implementation
- **Week 4:** CLI Completion + DOCX Generation
- **Week 5:** Testing + Refinement

**Total Estimated Time to MVP: 5 weeks** (assuming part-time work, or 2-3 weeks full-time)

**Current Status:**
- ✅ Configuration complete (`pyproject.toml`, `config.yaml`)
- ✅ Architecture verified and aligned
- ⏭️ Ready to start code implementation

The path forward is clear. Start with Phase 1.1 (Project Structure Setup) and proceed incrementally. Each phase builds on the previous, and your excellent documentation will serve as the blueprint throughout.

---

**Next Action:** Ready to start implementing Phase 1.1 (Project Structure) and then move to Phase 2 (Core Schemas)?
