# Software Design Document (SDD)

## ResumeForge: Multi-Agent Resume Optimization System

**Version:** 1.0.0  
**Last Updated:** January 14, 2025  
**Author:** Carlos A. Vazquez Morales  
**Status:** Draft

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Architecture](#2-system-architecture)
3. [Data Models](#3-data-models)
4. [Agent Specifications](#4-agent-specifications)
5. [Orchestrator Design](#5-orchestrator-design)
6. [Provider Abstraction Layer](#6-provider-abstraction-layer)
7. [CLI Interface](#7-cli-interface)
8. [Output Generation](#8-output-generation)
9. [Error Handling](#9-error-handling)
10. [Testing Strategy](#10-testing-strategy)
11. [Configuration](#11-configuration)

---

## 1. Introduction

### 1.1 Purpose

This document provides the detailed technical design for ResumeForge, including data models, interfaces, algorithms, and implementation specifications. It serves as the blueprint for development.

### 1.2 Scope

This SDD covers:
- Complete data schemas (JSON Schema format)
- Agent prompt templates with guardrails
- Orchestrator state machine implementation
- Provider abstraction interface
- CLI command specifications
- DOCX generation approach

### 1.3 References

- ADR.md — Architecture Decision Records
- SAD.md — Solution Architecture Document
- OpenAI API Documentation
- Anthropic API Documentation

---

## 2. System Architecture

### 2.1 Module Structure

```
resumeforge/
├── __init__.py
├── cli.py                    # CLI entry point
├── orchestrator.py           # Pipeline orchestrator
├── config.py                 # Configuration loader
│
├── agents/
│   ├── __init__.py
│   ├── base.py               # Base agent class
│   ├── jd_analyst.py         # JD Analyst + Strategy
│   ├── evidence_mapper.py    # Evidence Mapper
│   ├── resume_writer.py      # Resume Writer
│   └── auditor.py            # ATS + Truth Auditor
│
├── providers/
│   ├── __init__.py
│   ├── base.py               # Provider interface
│   ├── openai_provider.py
│   ├── anthropic_provider.py
│   ├── google_provider.py
│   ├── groq_provider.py
│   └── deepseek_provider.py
│
├── schemas/
│   ├── __init__.py
│   ├── evidence_card.py      # Pydantic models
│   ├── blackboard.py
│   └── outputs.py
│
├── parsers/
│   ├── __init__.py
│   ├── fact_resume_parser.py # Parse to evidence cards
│   └── jd_parser.py          # Extract JD text
│
├── generators/
│   ├── __init__.py
│   └── docx_generator.py     # DOCX output
│
└── utils/
    ├── __init__.py
    ├── tokens.py             # Token counting
    └── diff.py               # Variant diffing
```

### 2.2 Dependency Graph

```
cli.py
  └── orchestrator.py
        ├── agents/*
        │     └── providers/*
        ├── schemas/*
        └── generators/*
```

---

## 3. Data Models

### 3.1 Evidence Card (Pydantic Model)

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class MetricEntry(BaseModel):
    value: str = Field(..., description="Quantified value, e.g., '75%', '340K+'")
    description: str = Field(..., description="What the metric represents")
    context: Optional[str] = Field(None, description="Additional context")

class ScopeInfo(BaseModel):
    team_size: Optional[int] = None
    direct_reports: Optional[int] = None
    geography: list[str] = Field(default_factory=list)
    budget: Optional[str] = None

class EvidenceCard(BaseModel):
    id: str = Field(..., description="Unique identifier, e.g., 'nostromo-etl-metrics'")
    project: str = Field(..., description="Project or initiative name")
    company: str
    timeframe: str = Field(..., description="YYYY-YYYY or YYYY-MM to YYYY-MM")
    role: str = Field(..., description="Job title during this work")
    scope: ScopeInfo = Field(default_factory=ScopeInfo)
    metrics: list[MetricEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    leadership_signals: list[str] = Field(default_factory=list)
    raw_text: str = Field(..., description="Original source paragraph")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "nostromo-etl-metrics",
                "project": "Nostromo HRIS Integration Platform",
                "company": "PayScale",
                "timeframe": "2020-2024",
                "role": "Senior Manager, Software Engineering",
                "scope": {
                    "team_size": 19,
                    "direct_reports": 19,
                    "geography": ["US", "Romania", "India"],
                    "budget": None
                },
                "metrics": [
                    {"value": "340K+", "description": "employee records processed", "context": "nightly"},
                    {"value": "520+", "description": "client integrations"},
                    {"value": "75%", "description": "reduction in release defects"}
                ],
                "skills": ["ETL", "distributed systems", ".NET/C#", "microservices"],
                "leadership_signals": ["cross-geo management", "zero voluntary attrition"],
                "raw_text": "Led development of Nostromo platform processing 340K+ employee records..."
            }
        }
```

### 3.2 Blackboard State Model

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum

class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class GapStrategy(str, Enum):
    OMIT = "omit"
    ADJACENT = "adjacent_experience"
    ASK_USER = "ask_user"

# --- Input Models ---

class LengthRules(BaseModel):
    max_pages: int = 2

class Inputs(BaseModel):
    job_description: str
    target_title: str
    length_rules: LengthRules = Field(default_factory=LengthRules)
    template_path: str

# --- Analysis Models ---

class RoleProfile(BaseModel):
    inferred_level: str = Field(..., description="e.g., 'Senior Manager', 'Director'")
    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    seniority_signals: list[str] = Field(default_factory=list)
    keyword_clusters: dict[str, list[str]] = Field(default_factory=dict)
    recommended_storylines: list[str] = Field(default_factory=list)
    priority_sections: list[str] = Field(default_factory=list)
    downplay_sections: list[str] = Field(default_factory=list)

class Requirement(BaseModel):
    id: str
    text: str
    priority: Priority = Priority.MEDIUM
    keywords: list[str] = Field(default_factory=list)

# --- Evidence Mapping Models ---

class EvidenceMapping(BaseModel):
    requirement_id: str
    evidence_card_ids: list[str]
    confidence: Confidence
    notes: Optional[str] = None

class GapResolution(BaseModel):
    gap_id: str
    requirement_text: str
    strategy: GapStrategy
    adjacent_evidence_ids: list[str] = Field(default_factory=list)
    user_confirmed: bool = False

# --- Resume Draft Models ---

class ResumeSection(BaseModel):
    name: str
    content: str

class ResumeDraft(BaseModel):
    sections: list[ResumeSection] = Field(default_factory=list)

class ClaimMapping(BaseModel):
    bullet_id: str = Field(..., description="e.g., 'experience-payscale-bullet-1'")
    bullet_text: str
    evidence_card_ids: list[str]

# --- Audit Models ---

class TruthViolation(BaseModel):
    bullet_id: str
    bullet_text: str
    violation: str = Field(..., description="Description of the violation")

class ATSReport(BaseModel):
    keyword_coverage_score: float = Field(..., ge=0, le=100)
    supported_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    format_warnings: list[str] = Field(default_factory=list)
    role_signal_score: float = Field(..., ge=0, le=100)

class AuditReport(BaseModel):
    truth_violations: list[TruthViolation] = Field(default_factory=list)
    ats_suggestions: list[str] = Field(default_factory=list)
    inconsistencies: list[str] = Field(default_factory=list)
    passed: bool = Field(default=True)

# --- User Interaction Models ---

class UserQuestion(BaseModel):
    gap_id: str
    question: str
    impact: str = Field(..., description="Why answering this matters")

# --- Main Blackboard ---

class Blackboard(BaseModel):
    # Inputs
    inputs: Inputs
    
    # Parsed data
    evidence_cards: list[EvidenceCard] = Field(default_factory=list)
    synonyms_map: dict[str, list[str]] = Field(default_factory=dict)
    
    # JD Analysis outputs
    role_profile: Optional[RoleProfile] = None
    requirements: list[Requirement] = Field(default_factory=list)
    
    # Evidence Mapping outputs
    evidence_map: list[EvidenceMapping] = Field(default_factory=list)
    gap_resolutions: list[GapResolution] = Field(default_factory=list)
    selected_evidence_ids: list[str] = Field(default_factory=list)
    
    # Writer outputs
    resume_draft: Optional[ResumeDraft] = None
    claim_index: list[ClaimMapping] = Field(default_factory=list)
    change_log: list[str] = Field(default_factory=list)
    
    # Audit outputs
    ats_report: Optional[ATSReport] = None
    audit_report: Optional[AuditReport] = None
    
    # User interaction
    questions_for_user: list[UserQuestion] = Field(default_factory=list)
    
    # Pipeline state
    current_step: str = "init"
    retry_count: int = 0
    max_retries: int = 3
```

### 3.3 JSON Schema Export

```python
# Generate JSON Schema for external tools
import json

schema = Blackboard.model_json_schema()
with open("schemas/blackboard.schema.json", "w") as f:
    json.dump(schema, f, indent=2)
```

---

## 4. Agent Specifications

### 4.1 Base Agent Interface

```python
from abc import ABC, abstractmethod
from typing import Any

class BaseAgent(ABC):
    """Base class for all agents in the pipeline."""
    
    def __init__(self, provider: "BaseProvider", config: dict):
        self.provider = provider
        self.config = config
        self.temperature = config.get("temperature", 0.3)
        self.max_tokens = config.get("max_tokens", 4096)
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
    
    @abstractmethod
    def build_user_prompt(self, blackboard: "Blackboard") -> str:
        """Build the user prompt from blackboard state."""
        pass
    
    @abstractmethod
    def parse_response(self, response: str, blackboard: "Blackboard") -> "Blackboard":
        """Parse LLM response and update blackboard."""
        pass
    
    def execute(self, blackboard: "Blackboard") -> "Blackboard":
        """Execute this agent's task."""
        system_prompt = self.get_system_prompt()
        user_prompt = self.build_user_prompt(blackboard)
        
        response = self.provider.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
        
        return self.parse_response(response, blackboard)
```

### 4.2 JD Analyst + Strategy Agent

**System Prompt:**

```
You are an expert technical recruiter and resume strategist. Your task is to analyze a job description and produce a structured analysis that will guide resume optimization.

## Your Outputs (JSON format)

1. **inferred_level**: The seniority level this role represents (e.g., "Senior Manager", "Director", "VP")

2. **must_haves**: Skills/experiences that are non-negotiable requirements
   - Look for: "required", "must have", "X+ years", listed first in requirements

3. **nice_to_haves**: Skills that would strengthen a candidate but aren't required
   - Look for: "preferred", "bonus", "ideally", "nice to have"

4. **seniority_signals**: Phrases indicating the expected level
   - Examples: "lead a team", "strategic decisions", "report to CTO", "hands-on"

5. **keyword_clusters**: Group related terms together
   - Example: {"cloud": ["AWS", "Azure", "GCP"], "languages": ["Python", "Java"]}

6. **recommended_storylines**: 3-5 themes the resume should emphasize
   - Based on what this company clearly values

7. **priority_sections**: Which resume sections should get the most real estate

8. **downplay_sections**: What can be minimized or omitted

## Rules

- Be precise. Don't inflate requirements.
- Distinguish between explicit requirements and inferred preferences.
- Note any unusual requirements or red flags.
- Output valid JSON only.
```

**User Prompt Template:**

```
Analyze this job description and produce the structured analysis.

## Job Description

{job_description}

## Target Title (from user)

{target_title}

## Output Format

Respond with a JSON object matching this structure:
{
  "inferred_level": "string",
  "must_haves": ["string"],
  "nice_to_haves": ["string"],
  "seniority_signals": ["string"],
  "keyword_clusters": {"category": ["term1", "term2"]},
  "recommended_storylines": ["string"],
  "priority_sections": ["string"],
  "downplay_sections": ["string"]
}
```

### 4.3 Evidence Mapper Agent

**System Prompt:**

```
You are a precise evidence-matching system. Your task is to map job requirements to verified evidence from the candidate's history.

## CRITICAL RULES (Non-negotiable)

1. **NO FABRICATION**: You can ONLY cite evidence that exists in the provided evidence cards.
2. **CITE BY ID**: Every match must reference specific evidence_card_id(s).
3. **ACKNOWLEDGE GAPS**: If no evidence exists, mark it as a gap. Do not invent.
4. **TERMINOLOGY AWARENESS**: Use the synonyms map to recognize equivalent terms.

## Gap Classification

- **true_gap**: The candidate genuinely doesn't have this experience
- **terminology_gap**: The candidate has it but named differently (use synonyms_map)
- **hidden_evidence**: The candidate has it but it's not prominent in their evidence

## Confidence Levels

- **high**: Direct match with metrics or explicit statements
- **medium**: Related experience that demonstrates transferable skills
- **low**: Tangential connection; may need explanation

## Output Format

For each requirement, produce:
{
  "requirement_id": "req-001",
  "evidence_card_ids": ["card-id-1", "card-id-2"],
  "confidence": "high|medium|low",
  "notes": "Explanation of the match"
}

For gaps, produce:
{
  "gap_id": "gap-001",
  "requirement_text": "The requirement text",
  "gap_type": "true_gap|terminology_gap|hidden_evidence",
  "suggested_strategy": "omit|adjacent_experience|ask_user",
  "adjacent_evidence_ids": ["card-id-if-applicable"]
}
```

**User Prompt Template:**

```
Map the following requirements to the candidate's evidence cards.

## Requirements (from JD Analysis)

{requirements_json}

## Synonyms Map

{synonyms_map_json}

## Evidence Cards

{evidence_cards_json}

## Output

Respond with JSON:
{
  "evidence_map": [
    {
      "requirement_id": "string",
      "evidence_card_ids": ["string"],
      "confidence": "high|medium|low",
      "notes": "string"
    }
  ],
  "gaps": [
    {
      "gap_id": "string",
      "requirement_text": "string",
      "gap_type": "true_gap|terminology_gap|hidden_evidence",
      "suggested_strategy": "omit|adjacent_experience|ask_user",
      "adjacent_evidence_ids": ["string"]
    }
  ],
  "supported_keywords": ["string"],
  "selected_evidence_ids": ["string"]
}
```

### 4.4 Resume Writer Agent

**System Prompt:**

```
You are an expert resume writer who creates compelling, human-sounding resumes. You write with clarity, confidence, and results-focus.

## CRITICAL RULES (Non-negotiable)

1. **EVIDENCE-ONLY**: You may ONLY use information from the provided evidence cards. Do not add any facts, metrics, or claims not present in the evidence.

2. **CITE EVERYTHING**: For every bullet point, record which evidence_card_id(s) you used.

3. **NO AI VOICE**: Avoid these phrases entirely:
   - "Leveraged", "Utilized", "Spearheaded", "Synergized"
   - "Passionate about", "Proven track record"
   - "Dynamic", "Results-driven", "Self-starter"
   
4. **RESULTS-FORWARD**: Start bullets with impact when possible:
   - ❌ "Responsible for managing a team of 19 engineers"
   - ✅ "Led 19 engineers across 3 countries, achieving zero voluntary attrition"

5. **QUANTIFY**: Use metrics from evidence cards. Do not round or modify numbers.

6. **TEMPLATE COMPLIANCE**: Follow the base template structure exactly.

## Tone Guidelines

- Active voice, past tense for past roles
- Confident but not boastful
- Specific over vague
- Concise: aim for 1-2 lines per bullet

## Output Format

Produce the resume as structured sections, plus a claim_index mapping every bullet to its evidence sources.
```

**User Prompt Template:**

```
Write a targeted resume using ONLY the following inputs.

## Base Template Structure

{template_structure}

## Strategy Guidance

- Recommended storylines: {recommended_storylines}
- Priority sections: {priority_sections}
- Downplay: {downplay_sections}

## Evidence Cards to Use (ONLY use these)

{selected_evidence_cards_json}

## Gap Handling

{gap_resolutions_json}

## Constraints

- Maximum pages: {max_pages}
- Target role: {target_title}

## Output Format

Respond with JSON:
{
  "sections": [
    {
      "name": "Summary",
      "content": "markdown content"
    },
    {
      "name": "Experience",
      "content": "markdown content with bullets"
    }
  ],
  "claim_index": [
    {
      "bullet_id": "experience-payscale-bullet-1",
      "bullet_text": "The actual bullet text",
      "evidence_card_ids": ["card-id-1", "card-id-2"]
    }
  ],
  "change_log": [
    "Added emphasis on distributed systems per strategy",
    "Moved AI initiatives to prominent position"
  ]
}
```

### 4.5 ATS + Truth Auditor Agent

**System Prompt (ATS Heuristic):**

```
You are an ATS (Applicant Tracking System) compatibility analyzer. Score the resume on keyword coverage and formatting safety.

## Scoring Criteria

### Keyword Coverage (0-100)
- Count supported keywords from the JD that appear in the resume
- Score = (matched_keywords / total_jd_keywords) * 100
- Only count keywords the candidate can legitimately claim

### Role Signal Score (0-100)
- Does the resume's tone match the seniority level?
- Leadership language for manager+ roles
- Technical depth for IC roles
- Balance of strategic vs tactical

### Format Warnings
Flag any of these ATS-unfriendly elements:
- Tables or columns
- Images or graphics
- Headers/footers with critical info
- Non-standard section names
- Unusual fonts or formatting

## Output Format

{
  "keyword_coverage_score": 85,
  "supported_keywords": ["Python", "AWS", "team leadership"],
  "missing_keywords": ["Kubernetes"],
  "format_warnings": [],
  "role_signal_score": 90
}
```

**System Prompt (Truth Auditor):**

```
You are a truth verification system. Your job is to ensure every claim in the resume is supported by evidence.

## CRITICAL: This is a blocking check. Be strict.

### What to Check

1. **Unsupported Claims**: Any statement not traceable to an evidence card
2. **Metric Inconsistencies**: Numbers that don't match evidence (e.g., "40%" vs "35%")
3. **Date/Tenure Errors**: Incorrect timeframes
4. **Inflated Scope**: Claims that overstate what's in evidence
5. **Fabricated Skills**: Technologies or skills not in evidence cards

### Violation Severity

- **BLOCKER**: Unsupported claims, fabricated data → Pipeline must halt
- **WARNING**: Minor inconsistencies, phrasing concerns → Log but continue

### Output Format

{
  "truth_violations": [
    {
      "bullet_id": "experience-payscale-bullet-3",
      "bullet_text": "The problematic text",
      "violation": "Claims 80% improvement but evidence shows 75%"
    }
  ],
  "inconsistencies": [
    "Date range for PayScale shows 2020-2024 in one place, 2021-2024 in another"
  ],
  "ats_suggestions": [
    "Consider adding 'microservices' keyword which you can support"
  ],
  "passed": false
}
```

---

## 5. Orchestrator Design

### 5.1 State Machine Definition

```python
from enum import Enum, auto
from typing import Callable

class PipelineState(Enum):
    INIT = auto()
    PREPROCESSING = auto()
    JD_ANALYSIS = auto()
    EVIDENCE_MAPPING = auto()
    WRITING = auto()
    AUDITING = auto()
    REVISION = auto()
    COMPLETE = auto()
    FAILED = auto()

class StateTransition:
    def __init__(
        self,
        from_state: PipelineState,
        to_state: PipelineState,
        condition: Callable[["Blackboard"], bool] = lambda _: True,
        action: Callable[["Blackboard"], "Blackboard"] = lambda b: b
    ):
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition
        self.action = action

# Define valid transitions
TRANSITIONS = [
    StateTransition(PipelineState.INIT, PipelineState.PREPROCESSING),
    StateTransition(PipelineState.PREPROCESSING, PipelineState.JD_ANALYSIS),
    StateTransition(PipelineState.JD_ANALYSIS, PipelineState.EVIDENCE_MAPPING),
    StateTransition(PipelineState.EVIDENCE_MAPPING, PipelineState.WRITING),
    StateTransition(PipelineState.WRITING, PipelineState.AUDITING),
    StateTransition(
        PipelineState.AUDITING,
        PipelineState.COMPLETE,
        condition=lambda b: b.audit_report and b.audit_report.passed
    ),
    StateTransition(
        PipelineState.AUDITING,
        PipelineState.REVISION,
        condition=lambda b: b.audit_report and not b.audit_report.passed and b.retry_count < b.max_retries
    ),
    StateTransition(
        PipelineState.AUDITING,
        PipelineState.FAILED,
        condition=lambda b: b.audit_report and not b.audit_report.passed and b.retry_count >= b.max_retries
    ),
    StateTransition(PipelineState.REVISION, PipelineState.WRITING),
]
```

### 5.2 Orchestrator Implementation

```python
import logging
from datetime import datetime
from pathlib import Path

class PipelineOrchestrator:
    def __init__(self, config: dict, agents: dict):
        self.config = config
        self.agents = agents
        self.logger = logging.getLogger(__name__)
    
    def run(self, blackboard: Blackboard) -> Blackboard:
        """Execute the full pipeline."""
        state = PipelineState.INIT
        
        while state not in (PipelineState.COMPLETE, PipelineState.FAILED):
            self.logger.info(f"Pipeline state: {state.name}")
            blackboard.current_step = state.name
            
            # Execute current state's action
            blackboard = self._execute_state(state, blackboard)
            
            # Find valid transition
            state = self._get_next_state(state, blackboard)
        
        if state == PipelineState.COMPLETE:
            self._save_outputs(blackboard)
        
        return blackboard
    
    def _execute_state(self, state: PipelineState, blackboard: Blackboard) -> Blackboard:
        """Execute the action for the current state."""
        
        if state == PipelineState.PREPROCESSING:
            return self._preprocess(blackboard)
        
        elif state == PipelineState.JD_ANALYSIS:
            agent = self.agents["jd_analyst"]
            return agent.execute(blackboard)
        
        elif state == PipelineState.EVIDENCE_MAPPING:
            agent = self.agents["evidence_mapper"]
            return agent.execute(blackboard)
        
        elif state == PipelineState.WRITING:
            agent = self.agents["writer"]
            return agent.execute(blackboard)
        
        elif state == PipelineState.AUDITING:
            agent = self.agents["auditor"]
            return agent.execute(blackboard)
        
        elif state == PipelineState.REVISION:
            blackboard.retry_count += 1
            # Prepare revision instructions from audit report
            blackboard = self._prepare_revision(blackboard)
            return blackboard
        
        return blackboard
    
    def _get_next_state(self, current: PipelineState, blackboard: Blackboard) -> PipelineState:
        """Find the next valid state based on conditions."""
        for transition in TRANSITIONS:
            if transition.from_state == current and transition.condition(blackboard):
                return transition.to_state
        
        raise ValueError(f"No valid transition from {current}")
    
    def _preprocess(self, blackboard: Blackboard) -> Blackboard:
        """Load evidence cards and build synonyms map."""
        # Load cached evidence cards
        evidence_path = Path(self.config["evidence_cards_path"])
        with open(evidence_path) as f:
            cards_data = json.load(f)
        blackboard.evidence_cards = [EvidenceCard(**c) for c in cards_data]
        
        # Build synonyms map (could be LLM-assisted or rule-based)
        blackboard.synonyms_map = self._build_synonyms(blackboard)
        
        return blackboard
    
    def _build_synonyms(self, blackboard: Blackboard) -> dict:
        """Build terminology normalization map."""
        # Rule-based synonyms (extend as needed)
        base_synonyms = {
            "HCM": ["HRIS", "HR systems", "human capital management"],
            "CI/CD": ["continuous integration", "continuous deployment", "DevOps pipelines"],
            "microservices": ["distributed systems", "service-oriented architecture"],
            "ETL": ["data pipelines", "data integration", "data processing"],
        }
        return base_synonyms
    
    def _prepare_revision(self, blackboard: Blackboard) -> Blackboard:
        """Prepare context for revision based on audit failures."""
        violations = blackboard.audit_report.truth_violations
        
        # Add revision instructions to blackboard
        revision_instructions = []
        for v in violations:
            revision_instructions.append(
                f"FIX REQUIRED: Bullet '{v.bullet_id}' - {v.violation}"
            )
        
        blackboard.change_log.append(f"Revision attempt {blackboard.retry_count}")
        blackboard.change_log.extend(revision_instructions)
        
        return blackboard
    
    def _save_outputs(self, blackboard: Blackboard) -> None:
        """Save all outputs to versioned folder."""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        company = blackboard.inputs.target_title.lower().replace(" ", "-")
        
        output_dir = Path(self.config["output_dir"]) / f"{company}-{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save files
        self._save_json(output_dir / "evidence_used.json", blackboard.selected_evidence_ids)
        self._save_json(output_dir / "claim_index.json", [c.model_dump() for c in blackboard.claim_index])
        self._save_json(output_dir / "ats_report.json", blackboard.ats_report.model_dump())
        self._save_json(output_dir / "audit_report.json", blackboard.audit_report.model_dump())
        
        # Generate DOCX
        self._generate_docx(output_dir / "resume.docx", blackboard)
        
        # Generate diff
        self._generate_diff(output_dir / "diff_from_base.md", blackboard)
```

---

## 6. Provider Abstraction Layer

### 6.1 Base Provider Interface

```python
from abc import ABC, abstractmethod
from typing import Optional
import logging

class BaseProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None
    ) -> str:
        """Generate a completion from the model."""
        pass
    
    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Count tokens in the given text."""
        pass
```

### 6.2 OpenAI Provider

```python
from openai import OpenAI
import tiktoken

class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        super().__init__(api_key, model)
        self.client = OpenAI(api_key=api_key)
        self.encoding = tiktoken.encoding_for_model(model)
    
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None
    ) -> str:
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    
    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))
```

### 6.3 Anthropic Provider

```python
from anthropic import Anthropic

class AnthropicProvider(BaseProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        super().__init__(api_key, model)
        self.client = Anthropic(api_key=api_key)
    
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_format: Optional[dict] = None
    ) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.content[0].text
    
    def count_tokens(self, text: str) -> int:
        # Anthropic doesn't expose tokenizer; estimate at 4 chars/token
        return len(text) // 4
```

### 6.4 Provider Factory

```python
def create_provider(provider_name: str, config: dict) -> BaseProvider:
    """Factory function to create provider instances."""
    
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "google": GoogleProvider,
        "groq": GroqProvider,
        "deepseek": DeepSeekProvider,
    }
    
    if provider_name not in providers:
        raise ValueError(f"Unknown provider: {provider_name}")
    
    api_key = os.environ.get(f"{provider_name.upper()}_API_KEY")
    if not api_key:
        raise ValueError(f"Missing API key for {provider_name}")
    
    return providers[provider_name](
        api_key=api_key,
        model=config.get("model")
    )
```

---

## 7. CLI Interface

### 7.1 Command Definitions

```python
import click
from pathlib import Path

@click.group()
@click.version_option(version="1.0.0")
def cli():
    """ResumeForge: AI-powered resume optimization."""
    pass

@cli.command()
@click.option("--fact-resume", "-f", required=True, type=click.Path(exists=True),
              help="Path to fact resume (Markdown)")
@click.option("--output", "-o", default="./data/evidence_cards.json",
              help="Output path for evidence cards")
def parse(fact_resume: str, output: str):
    """Parse fact resume into evidence cards (one-time setup)."""
    from resumeforge.parsers import FactResumeParser
    
    parser = FactResumeParser()
    cards = parser.parse(Path(fact_resume))
    
    with open(output, "w") as f:
        json.dump([c.model_dump() for c in cards], f, indent=2)
    
    click.echo(f"✓ Parsed {len(cards)} evidence cards to {output}")

@cli.command()
@click.option("--jd", "-j", required=True, type=click.Path(exists=True),
              help="Path to job description (text file)")
@click.option("--title", "-t", required=True,
              help="Target job title")
@click.option("--output-dir", "-o", default="./outputs",
              help="Output directory")
@click.option("--config", "-c", default="./config.yaml",
              help="Configuration file")
@click.option("--interactive/--batch", default=False,
              help="Interactive mode for gap questions")
def generate(jd: str, title: str, output_dir: str, config: str, interactive: bool):
    """Generate a targeted resume for a job description."""
    from resumeforge.orchestrator import PipelineOrchestrator
    from resumeforge.config import load_config
    
    cfg = load_config(config)
    
    # Load JD
    with open(jd) as f:
        jd_text = f.read()
    
    # Initialize blackboard
    blackboard = Blackboard(
        inputs=Inputs(
            job_description=jd_text,
            target_title=title,
            template_path=cfg["template_path"]
        )
    )
    
    # Initialize agents with configured providers
    agents = initialize_agents(cfg)
    
    # Run pipeline
    orchestrator = PipelineOrchestrator(cfg, agents)
    result = orchestrator.run(blackboard)
    
    if result.current_step == "COMPLETE":
        click.echo(f"✓ Resume generated successfully")
        click.echo(f"  Output: {output_dir}/{title}-{date.today()}/")
    else:
        click.echo(f"✗ Pipeline failed at step: {result.current_step}")
        if result.audit_report:
            for v in result.audit_report.truth_violations:
                click.echo(f"  - {v.violation}")

@cli.command()
@click.option("--variant1", required=True, type=click.Path(exists=True))
@click.option("--variant2", required=True, type=click.Path(exists=True))
def diff(variant1: str, variant2: str):
    """Compare two resume variants."""
    from resumeforge.utils import generate_diff
    
    diff_text = generate_diff(variant1, variant2)
    click.echo(diff_text)

if __name__ == "__main__":
    cli()
```

### 7.2 Usage Examples

```bash
# One-time: Parse fact resume into evidence cards
resumeforge parse --fact-resume ./fact_resume.md --output ./data/evidence_cards.json

# Generate resume for a job
resumeforge generate \
  --jd ./jobs/draftkings-senior-em.txt \
  --title "Senior Engineering Manager" \
  --output-dir ./outputs

# Compare two variants
resumeforge diff \
  --variant1 ./outputs/draftkings-2025-01-14 \
  --variant2 ./outputs/whoop-2025-01-15
```

---

## 8. Output Generation

### 8.1 DOCX Generation

```python
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

class DocxGenerator:
    def __init__(self, template_path: str = None):
        if template_path:
            self.doc = Document(template_path)
        else:
            self.doc = Document()
            self._setup_default_styles()
    
    def _setup_default_styles(self):
        """Configure default document styles."""
        style = self.doc.styles["Normal"]
        font = style.font
        font.name = "Arial"
        font.size = Pt(11)
    
    def generate(self, blackboard: Blackboard, output_path: str):
        """Generate DOCX from blackboard state."""
        
        for section in blackboard.resume_draft.sections:
            self._add_section(section)
        
        self.doc.save(output_path)
    
    def _add_section(self, section: ResumeSection):
        """Add a section to the document."""
        # Add heading
        self.doc.add_heading(section.name, level=1)
        
        # Parse markdown content and add paragraphs
        lines = section.content.split("\n")
        for line in lines:
            if line.startswith("- "):
                # Bullet point
                p = self.doc.add_paragraph(line[2:], style="List Bullet")
            elif line.strip():
                # Regular paragraph
                self.doc.add_paragraph(line)
```

---

## 9. Error Handling

### 9.1 Error Types

```python
class ResumeForgeError(Exception):
    """Base exception for ResumeForge."""
    pass

class EvidenceParsingError(ResumeForgeError):
    """Error parsing fact resume into evidence cards."""
    pass

class ProviderError(ResumeForgeError):
    """Error communicating with LLM provider."""
    pass

class TruthViolationError(ResumeForgeError):
    """Resume contains unverified claims."""
    def __init__(self, violations: list[TruthViolation]):
        self.violations = violations
        super().__init__(f"{len(violations)} truth violations found")

class PipelineError(ResumeForgeError):
    """Pipeline execution error."""
    def __init__(self, state: str, message: str):
        self.state = state
        super().__init__(f"Pipeline failed at {state}: {message}")
```

### 9.2 Retry Strategy

```python
import time
from functools import wraps

def with_retry(max_retries: int = 3, backoff_factor: float = 2.0):
    """Decorator for retrying failed operations."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except ProviderError as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        sleep_time = backoff_factor ** attempt
                        logging.warning(f"Retry {attempt + 1}/{max_retries} after {sleep_time}s")
                        time.sleep(sleep_time)
            raise last_exception
        return wrapper
    return decorator
```

---

## 10. Testing Strategy

### 10.1 Test Categories

| Category | What to Test | Approach |
|----------|--------------|----------|
| Unit | Individual functions, parsers | pytest with mocks |
| Integration | Agent + Provider | Real API calls (gated) |
| Contract | Blackboard schema | Pydantic validation |
| E2E | Full pipeline | Golden file comparison |

### 10.2 Example Tests

```python
import pytest
from resumeforge.schemas import EvidenceCard, Blackboard

class TestEvidenceCard:
    def test_valid_card(self):
        card = EvidenceCard(
            id="test-card",
            project="Test Project",
            company="Test Co",
            timeframe="2020-2024",
            role="Engineer",
            raw_text="Sample text"
        )
        assert card.id == "test-card"
    
    def test_card_with_metrics(self):
        card = EvidenceCard(
            id="metrics-card",
            project="Metrics Project",
            company="Test Co",
            timeframe="2020-2024",
            role="Engineer",
            metrics=[
                {"value": "75%", "description": "improvement"}
            ],
            raw_text="Achieved 75% improvement"
        )
        assert len(card.metrics) == 1
        assert card.metrics[0].value == "75%"

class TestTruthAuditor:
    def test_detects_unsupported_claim(self):
        # Setup blackboard with claim not in evidence
        blackboard = create_test_blackboard()
        blackboard.claim_index.append(
            ClaimMapping(
                bullet_id="test-bullet",
                bullet_text="Achieved 90% improvement",
                evidence_card_ids=[]  # No evidence!
            )
        )
        
        auditor = TruthAuditor(mock_provider)
        result = auditor.execute(blackboard)
        
        assert not result.audit_report.passed
        assert len(result.audit_report.truth_violations) > 0
```

---

## 11. Configuration

### 11.1 Configuration Schema

```yaml
# config.yaml

# Paths
evidence_cards_path: ./data/evidence_cards.json
template_path: ./templates/base_resume.md
output_dir: ./outputs

# Pipeline settings
max_retries: 3
interactive_mode: false

# Length constraints
default_max_pages: 2

# Agent configurations
agents:
  jd_analyst:
    provider: anthropic
    model: claude-sonnet-4-20250514
    temperature: 0.3
    max_tokens: 4096
  
  evidence_mapper:
    provider: anthropic
    model: claude-sonnet-4-20250514
    temperature: 0.1
    max_tokens: 4096
  
  writer:
    provider: openai
    model: gpt-4o
    temperature: 0.4
    max_tokens: 8192
  
  ats_scorer:
    provider: google
    model: gemini-1.5-flash
    temperature: 0.2
    max_tokens: 2048
  
  truth_auditor:
    provider: anthropic
    model: claude-sonnet-4-20250514
    temperature: 0.0
    max_tokens: 4096

# Fallback models (if primary fails)
fallbacks:
  openai: anthropic
  anthropic: openai
  google: groq

# Logging
logging:
  level: INFO
  file: ./logs/resumeforge.log
```

### 11.2 Environment Variables

```bash
# Required API keys
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GOOGLE_API_KEY=AI...

# Optional (for fallbacks)
export GROQ_API_KEY=gsk_...
export DEEPSEEK_API_KEY=sk-...
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-14 | Carlos Vazquez | Initial SDD from architecture sessions |
