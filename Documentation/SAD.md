# Solution Architecture Document (SAD)

## ResumeForge: Multi-Agent Resume Optimization System

**Version:** 1.0.0  
**Last Updated:** January 14, 2025  
**Author:** Carlos A. Vazquez Morales  
**Status:** Draft

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Context](#2-business-context)
3. [Architecture Overview](#3-architecture-overview)
4. [C4 Model Diagrams](#4-c4-model-diagrams)
5. [Component Descriptions](#5-component-descriptions)
6. [Data Architecture](#6-data-architecture)
7. [Integration Architecture](#7-integration-architecture)
8. [Security & Privacy](#8-security--privacy)
9. [Deployment Architecture](#9-deployment-architecture)
10. [Quality Attributes](#10-quality-attributes)
11. [Constraints & Assumptions](#11-constraints--assumptions)
12. [Risks & Mitigations](#12-risks--mitigations)

---

## 1. Executive Summary

### 1.1 Purpose

ResumeForge is a multi-agent AI system that transforms a comprehensive "Fact Resume" into job-targeted resumes optimized for specific job descriptions. The system maintains strict truthfulness guarantees—no claim appears in the output unless it traces back to verified source evidence.

### 1.2 Key Objectives

- **Accuracy:** Zero hallucinated claims; every bullet point traceable to evidence
- **Optimization:** Maximize relevance to target job description keywords and requirements
- **Efficiency:** Reduce manual resume customization from hours to minutes
- **Consistency:** Maintain professional tone and formatting across all variants

### 1.3 Scope

**In Scope:**
- Job description analysis and requirement extraction
- Evidence matching from source resume
- Resume content generation with human tone
- ATS compatibility scoring and optimization
- Truth auditing and claim verification
- DOCX output generation

**Out of Scope (v1):**
- Cover letter generation
- LinkedIn profile optimization
- Application tracking/submission
- Interview preparation content

---

## 2. Business Context

### 2.1 Problem Statement

Job seekers targeting multiple positions must customize their resume for each application to maximize ATS scores and recruiter relevance. This process is:
- **Time-consuming:** 1-3 hours per tailored resume
- **Error-prone:** Risk of inconsistent claims or accidental fabrication
- **Repetitive:** Same evidence rephrased for different contexts

### 2.2 Solution Value Proposition

ResumeForge automates the customization process while enforcing truthfulness:

| Manual Process | ResumeForge |
|----------------|-------------|
| 1-3 hours per resume | 2-5 minutes per resume |
| Risk of inconsistency | Traceable claims with audit trail |
| Subjective ATS guessing | Heuristic-based keyword optimization |
| Single variant | Multiple variants possible |

### 2.3 Target Users

- **Primary:** Senior technical professionals (engineering managers, directors) actively job searching
- **Secondary:** Career coaches assisting clients with resume optimization

---

## 3. Architecture Overview

### 3.1 Architecture Style

**Multi-Agent Pipeline with Deterministic Orchestration**

The system uses specialized AI agents for discrete tasks, coordinated by a deterministic Python orchestrator. This pattern provides:
- Clear separation of concerns
- Optimal model selection per task
- Predictable execution flow
- Easy debugging and iteration

### 3.2 High-Level Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Fact Resume │     │   Base      │     │    Job      │
│   (source)  │     │  Template   │     │ Description │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
                 ┌─────────────────┐
                 │   Orchestrator  │
                 │   (Python)      │
                 └────────┬────────┘
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
       ▼                  ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ JD Analyst  │───▶│  Evidence   │───▶│   Resume    │
│ + Strategy  │    │   Mapper    │    │   Writer    │
└─────────────┘    └─────────────┘    └──────┬──────┘
                                             │
                                             ▼
                                    ┌─────────────┐
                                    │ ATS + Truth │
                                    │   Auditor   │
                                    └──────┬──────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │   Output    │
                                    │   (DOCX)    │
                                    └─────────────┘
```

### 3.3 Design Principles

1. **Evidence-First:** No claim without traceable source
2. **Separation of Concerns:** Matching ≠ Writing ≠ Validation
3. **Deterministic Orchestration:** LLMs for content, code for control flow
4. **Model Optimization:** Best model for each task
5. **Privacy by Default:** Sensitive data stays local

---

## 4. C4 Model Diagrams

### 4.1 Context Diagram (Level 1)

```
┌─────────────────────────────────────────────────────────────────────┐
│                          SYSTEM CONTEXT                             │
│                                                                     │
│    ┌──────────┐                                    ┌─────────────┐  │
│    │   User   │                                    │  LLM APIs   │  │
│    │ (Carlos) │                                    │ (External)  │  │
│    └────┬─────┘                                    └──────┬──────┘  │
│         │                                                 │         │
│         │  Provides: JD, commands                         │         │
│         │  Receives: Resume, reports                      │         │
│         │                                                 │         │
│         ▼                                                 ▼         │
│    ┌────────────────────────────────────────────────────────┐      │
│    │                                                        │      │
│    │                    ResumeForge                         │      │
│    │                                                        │      │
│    │    Multi-agent system for job-targeted resume          │      │
│    │    generation with truthfulness guarantees             │      │
│    │                                                        │      │
│    └────────────────────────────────────────────────────────┘      │
│                              │                                      │
│                              │                                      │
│                              ▼                                      │
│                      ┌──────────────┐                               │
│                      │ Local Files  │                               │
│                      │ evidence.json│                               │
│                      │ outputs/     │                               │
│                      └──────────────┘                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

External Systems:
┌─────────────────┬────────────────────────────────────────┐
│ OpenAI API      │ GPT-4o for Resume Writer               │
│ Anthropic API   │ Claude Sonnet 4 for analysis/audit     │
│ Google AI API   │ Gemini Flash for ATS scoring           │
│ Groq API        │ Fast inference for preprocessing       │
└─────────────────┴────────────────────────────────────────┘
```

### 4.2 Container Diagram (Level 2)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ResumeForge System                              │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                         CLI Application                           │  │
│  │                         (Python)                                  │  │
│  │                                                                   │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │   Command   │  │    Config   │  │   Output    │               │  │
│  │  │   Parser    │  │   Loader    │  │  Generator  │               │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      Pipeline Orchestrator                        │  │
│  │                      (Python State Machine)                       │  │
│  │                                                                   │  │
│  │  • Step sequencing           • Blackboard state management       │  │
│  │  • Validation gates          • Retry logic                       │  │
│  │  • Error handling            • Output collection                 │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                    │                                    │
│          ┌─────────────────────────┼─────────────────────────┐          │
│          │                         │                         │          │
│          ▼                         ▼                         ▼          │
│  ┌───────────────┐        ┌───────────────┐        ┌───────────────┐   │
│  │  JD Analyst   │        │   Evidence    │        │    Resume     │   │
│  │  + Strategy   │        │    Mapper     │        │    Writer     │   │
│  │               │        │               │        │               │   │
│  │ Claude Sonnet │        │ Claude Sonnet │        │    GPT-4o     │   │
│  └───────────────┘        └───────────────┘        └───────────────┘   │
│                                    │                                    │
│                                    ▼                                    │
│                           ┌───────────────┐                             │
│                           │  ATS + Truth  │                             │
│                           │    Auditor    │                             │
│                           │               │                             │
│                           │ Gemini + Claude│                            │
│                           └───────────────┘                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                       Provider Abstraction                        │  │
│  │                                                                   │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │  │
│  │  │ OpenAI  │ │Anthropic│ │ Google  │ │  Groq   │ │DeepSeek │    │  │
│  │  │ Client  │ │ Client  │ │ Client  │ │ Client  │ │ Client  │    │  │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                        Local Data Store                           │  │
│  │                                                                   │  │
│  │  evidence_cards.json    config.yaml    outputs/                   │  │
│  │  synonyms.json          templates/     logs/                      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Component Diagram (Level 3)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Pipeline Orchestrator                              │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        Blackboard                               │    │
│  │                  (Shared State Object)                          │    │
│  │                                                                 │    │
│  │  inputs{}  evidence_cards[]  role_profile{}  evidence_map[]     │    │
│  │  resume_draft{}  claim_index[]  ats_report{}  audit_report{}    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                    │
│                                    ▼                                    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     Pipeline Steps                              │    │
│  │                                                                 │    │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │    │
│  │  │  Step 0  │───▶│  Step 1  │───▶│  Step 2  │───▶│  Step 3  │   │    │
│  │  │ Preproc  │    │ Analyze  │    │   Map    │    │  Write   │   │    │
│  │  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │    │
│  │                                                        │        │    │
│  │                                                        ▼        │    │
│  │                                                 ┌──────────┐    │    │
│  │                         ┌───────────────────────│  Step 4  │    │    │
│  │                         │    Retry Loop         │  Audit   │    │    │
│  │                         │    (if failed)        └──────────┘    │    │
│  │                         ▼                              │        │    │
│  │                  ┌──────────┐                          │        │    │
│  │                  │  Step 3  │◀─────────────────────────┘        │    │ 
│  │                  │  Write   │   (with fixes)                    │    │
│  │                  └──────────┘                                   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Validation Gates                             │    │
│  │                                                                 │    │
│  │  • Post-Mapping: evidence_map not empty                         │    │
│  │  • Post-Writing: claim_index complete                           │    │
│  │  • Post-Audit: truth_violations == []                           │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Component Descriptions

### 5.1 CLI Application

| Attribute | Description |
|-----------|-------------|
| **Purpose** | User interface for invoking pipeline |
| **Technology** | Python (Click or Typer) |
| **Responsibilities** | Parse commands, load config, invoke orchestrator, display results |

**Commands:**
```bash
resumeforge parse --fact-resume ./fact_resume.md    # One-time: generate evidence cards
resumeforge generate --jd ./job.txt --output ./out/ # Generate targeted resume
resumeforge diff --variant1 ./a/ --variant2 ./b/    # Compare variants
```
**Additional commands to create**
#List all variants you've generated
```bash
resumeforge list
```
# Output:
#  draftkings-senior-em-2025-01-14  (ATS: 87%)
# whoop-director-2025-01-16        (ATS: 82%)
# athena-em-2025-01-18             (ATS: 91%)

#Show what evidence was used for a specific variant
```bash
   resumeforge show draftkings-senior-em-2025-01-14 --evidence
```
#Output: Lists the evidence cards that were selected

#Re-run with updated Fact Resume (after you add new accomplishments)
```bash
resumeforge refresh --all
```
#Re-generates all variants with updated evidence cards

#Interview prep mode: show claims you need to defend
```bash
resumeforge prep draftkings-senior-em-2025-01-14
``` 
#Output: 
# "Be ready to discuss:"
# 1. "340K+ employee records processed nightly" — Source: Nostromo project
# 2. "75% reduction in release defects" — Source: Shift-left initiative
# 3. ...

### 5.2 Pipeline Orchestrator

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Coordinate agent execution and state management |
| **Technology** | Python (pure code, no LLM) |
| **Pattern** | State machine with validation gates |

**State Transitions:**
```
INIT → PREPROCESSING → JD_ANALYSIS → EVIDENCE_MAPPING → WRITING → AUDITING → COMPLETE
                                                           ↑          │
                                                           └──────────┘
                                                          (retry on fail)
```

### 5.3 JD Analyst + Strategy Agent

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Analyze job description; determine positioning strategy |
| **Model** | Claude Sonnet 4 (claude-sonnet-4-20250514) |
| **Temperature** | 0.3 |

**Inputs:** Job description text, target role level  
**Outputs:** `role_profile`, `keyword_clusters`, `recommended_storylines`, `priority_sections`

### 5.4 Evidence Mapper Agent

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Match JD requirements to evidence cards; identify gaps |
| **Model** | Claude Sonnet 4 |
| **Temperature** | 0.1 (low for precision) |

**Inputs:** `role_profile`, `evidence_cards[]`, `synonyms_map`  
**Outputs:** `evidence_map[]`, `supported_keywords[]`, `gaps[]`

**Hard Guardrail:** Cannot recommend adding content without citing an evidence card ID.

### 5.5 Resume Writer Agent

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Generate resume content with human tone |
| **Model** | GPT-4o |
| **Temperature** | 0.4 |

**Inputs:** Base template, `selected_evidence_ids[]`, `strategy_priorities`  
**Outputs:** `resume_draft`, `change_log`, `claim_index[]`

**Constraints:**
- Only use evidence from approved card IDs
- Follow template structure exactly
- Avoid AI-sounding phrases

### 5.6 ATS Heuristic + Truth Auditor

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Score ATS compatibility; verify all claims are truthful |
| **Models** | Gemini 1.5 Flash (ATS), Claude Sonnet 4 (Truth) |
| **Temperature** | 0.2 (ATS), 0.0 (Truth) |

**ATS Outputs:** `keyword_coverage_score`, `format_warnings`, `role_signal_score`  
**Truth Outputs:** `truth_violations[]` (blockers), `inconsistencies[]`

### 5.7 Provider Abstraction Layer

| Attribute | Description |
|-----------|-------------|
| **Purpose** | Unified interface to multiple LLM providers |
| **Technology** | Python with provider-specific SDKs |

**Supported Providers:**
- OpenAI (openai SDK)
- Anthropic (anthropic SDK)
- Google (google-generativeai SDK)
- Groq (groq SDK)
- DeepSeek (OpenAI-compatible API)

---

## 6. Data Architecture

### 6.1 Evidence Card Schema

```json
{
  "id": "string (unique identifier)",
  "project": "string (initiative/project name)",
  "company": "string",
  "timeframe": "string (YYYY-YYYY or YYYY-MM to YYYY-MM)",
  "role": "string (job title during this work)",
  "scope": {
    "team_size": "number | null",
    "direct_reports": "number | null",
    "geography": ["string"],
    "budget": "string | null"
  },
  "metrics": [
    {
      "value": "string (e.g., '75%', '340K+')",
      "description": "string",
      "context": "string | null"
    }
  ],
  "skills": ["string"],
  "leadership_signals": ["string"],
  "raw_text": "string (original source paragraph)"
}
```

### 6.2 Blackboard State Schema

```json
{
  "inputs": {
    "job_description": "string",
    "target_title": "string",
    "length_rules": { "max_pages": 2 },
    "template_path": "string"
  },
  "evidence_cards": ["EvidenceCard[]"],
  "synonyms_map": { "jd_term": ["equivalent_terms"] },
  "role_profile": {
    "inferred_level": "string",
    "must_haves": ["string"],
    "nice_to_haves": ["string"],
    "seniority_signals": ["string"]
  },
  "requirements": [
    { "id": "string", "text": "string", "priority": "high|medium|low" }
  ],
  "evidence_map": [
    {
      "requirement_id": "string",
      "evidence_card_ids": ["string"],
      "confidence": "high|medium|low",
      "notes": "string | null"
    }
  ],
  "gap_resolutions": [
    {
      "gap_id": "string",
      "strategy": "omit|adjacent_experience|ask_user",
      "adjacent_evidence": ["string"] ,
      "user_confirmed": "boolean"
    }
  ],
  "selected_evidence_ids": ["string"],
  "resume_draft": {
    "sections": [
      { "name": "string", "content": "string" }
    ]
  },
  "claim_index": [
    { "bullet_id": "string", "evidence_card_ids": ["string"] }
  ],
  "ats_report": {
    "keyword_coverage_score": "number (0-100)",
    "supported_keywords": ["string"],
    "missing_keywords": ["string"],
    "format_warnings": ["string"],
    "role_signal_score": "number (0-100)"
  },
  "audit_report": {
    "truth_violations": [
      { "bullet_id": "string", "violation": "string" }
    ],
    "ats_suggestions": ["string"],
    "inconsistencies": ["string"]
  },
  "questions_for_user": [
    { "gap_id": "string", "question": "string", "impact": "string" }
  ]
}
```

### 6.3 Output Folder Structure

```
outputs/
└── {company}-{role}-{date}/
    ├── resume.docx              # Final output
    ├── resume.md                # Markdown source (for diffing)
    ├── evidence_used.json       # Which cards were selected
    ├── claim_index.json         # Traceability map
    ├── ats_report.json          # ATS scoring details
    ├── audit_report.json        # Truth audit results
    └── diff_from_base.md        # Changes from base template
```

---

## 7. Integration Architecture

### 7.1 External API Integrations

| Provider | Endpoint | Auth Method | Rate Limits |
|----------|----------|-------------|-------------|
| OpenAI | api.openai.com/v1/chat/completions | API Key (Bearer) | Tier-dependent |
| Anthropic | api.anthropic.com/v1/messages | API Key (x-api-key) | Tier-dependent |
| Google AI | generativelanguage.googleapis.com | API Key | 60 RPM (free) |
| Groq | api.groq.com/openai/v1/chat/completions | API Key (Bearer) | 30 RPM |
| DeepSeek | api.deepseek.com/v1/chat/completions | API Key (Bearer) | Tier-dependent |

### 7.2 Error Handling Strategy

| Error Type | Handling |
|------------|----------|
| Rate limit (429) | Exponential backoff with jitter; max 3 retries |
| Timeout | Retry once; fail if second attempt times out |
| Invalid response | Log and retry with simplified prompt |
| Truth violation | Return to Writer with explicit fix instructions |
| Provider outage | Fall back to secondary model if configured |

---

## 8. Security & Privacy

### 8.1 Data Classification

| Data Type | Classification | Storage | Transmission |
|-----------|----------------|---------|--------------|
| Fact Resume | Confidential | Local only | Never sent whole |
| Evidence Cards | Confidential | Local JSON | Partial (selected cards only) |
| Job Descriptions | Internal | Local | Sent to LLM APIs |
| Generated Resumes | Confidential | Local | Not transmitted |
| API Keys | Secret | Environment variables | HTTPS only |

### 8.2 Privacy Controls

1. **Fact Resume never sent whole** — Only parsed evidence cards transmitted
2. **Selected cards only** — Downstream agents receive 15-25 cards, not full set
3. **Local storage** — All outputs stored locally; no cloud sync
4. **No logging of PII** — API requests logged without sensitive content

### 8.3 API Key Management

```bash
# Environment variables (not in config files)
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GOOGLE_API_KEY=AI...
export GROQ_API_KEY=gsk_...
export DEEPSEEK_API_KEY=sk-...
```

---

## 9. Deployment Architecture

### 9.1 Local Development (MVP)

```
┌─────────────────────────────────────────┐
│           Developer Machine             │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │     Python Virtual Environment  │   │
│  │                                 │   │
│  │  resumeforge/                   │   │
│  │  ├── cli.py                     │   │
│  │  ├── orchestrator.py            │   │
│  │  ├── agents/                    │   │
│  │  ├── providers/                 │   │
│  │  └── schemas/                   │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │          Local Data             │   │
│  │                                 │   │
│  │  data/                          │   │
│  │  ├── evidence_cards.json        │   │
│  │  ├── synonyms.json              │   │
│  │  └── templates/                 │   │
│  │                                 │   │
│  │  outputs/                       │   │
│  │  └── {variant folders}          │   │
│  └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
            │
            │ HTTPS
            ▼
┌─────────────────────────────────────────┐
│         External LLM APIs               │
│  OpenAI │ Anthropic │ Google │ Groq    │
└─────────────────────────────────────────┘
```

### 9.2 Future: Streamlit UI (v2)

```
┌─────────────────────────────────────────┐
│           Developer Machine             │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │        Streamlit App            │   │
│  │        localhost:8501           │   │
│  └──────────────┬──────────────────┘   │
│                 │                       │
│                 ▼                       │
│  ┌─────────────────────────────────┐   │
│  │      ResumeForge Core           │   │
│  │      (same as CLI)              │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

---

## 10. Quality Attributes

### 10.1 Quality Attribute Requirements

| Attribute | Requirement | Measurement |
|-----------|-------------|-------------|
| **Accuracy** | Zero hallucinated claims | 100% of bullets trace to evidence cards |
| **Performance** | < 3 minutes per resume | End-to-end pipeline time |
| **Reliability** | 95% success rate | Completed runs / attempted runs |
| **Usability** | Single command execution | `resumeforge generate --jd ./job.txt` |
| **Maintainability** | Modular agent design | Each agent independently testable |
| **Cost Efficiency** | < $0.10 per resume | API costs per successful run |

### 10.2 Traceability Guarantee

Every bullet point in the output resume MUST:
1. Have an entry in `claim_index`
2. Reference at least one `evidence_card_id`
3. Pass Truth Auditor verification

If any bullet fails these checks, the pipeline halts and returns to the Writer with explicit fixes required.

---

## 11. Constraints & Assumptions

### 11.1 Constraints

| Constraint | Impact |
|------------|--------|
| CLI-first (no web UI in v1) | Limits non-technical user adoption |
| External API dependency | Requires internet; subject to rate limits |
| English language only | No i18n in v1 |
| DOCX output only | No native PDF generation |

### 11.2 Assumptions

| Assumption | Risk if Invalid |
|------------|-----------------|
| Fact Resume is comprehensive and accurate | Garbage in, garbage out |
| User has API keys for at least 2 providers | Single provider failures block pipeline |
| Job descriptions are text-extractable | May need OCR for image-based JDs |
| 2-page max is acceptable for target roles | Some industries expect different lengths |

---

## 12. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM hallucination despite guardrails | Medium | High | Truth Auditor as hard gate; claim index requirement |
| API cost overruns | Low | Medium | Token counting; model selection optimization |
| Provider rate limiting | Medium | Medium | Multi-provider fallback; backoff strategy |
| Evidence card parsing errors | Medium | Medium | Manual review of parsed cards before use |
| Template format drift | Low | Low | Template versioning; validation on load |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-14 | Carlos Vazquez | Initial SAD from architecture sessions |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Evidence Card** | Structured unit of verifiable information parsed from Fact Resume |
| **Fact Resume** | Comprehensive source document containing all career evidence |
| **Blackboard** | Shared state object passed through pipeline |
| **Claim Index** | Mapping of output bullets to source evidence card IDs |
| **Gap** | JD requirement without matching evidence |
| **ATS** | Applicant Tracking System |
