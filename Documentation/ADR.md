# Architecture Decision Records (ADRs)

## Resume Optimization Multi-Agent System

**Project:** ResumeForge  
**Version:** 1.0.0  
**Last Updated:** January 14, 2025  
**Author:** Carlos A. Vazquez Morales

---

## ADR-001: Multi-Agent Architecture Pattern

### Status
Accepted

### Context
We need a system that transforms a comprehensive "Fact Resume" into job-targeted resumes while maintaining strict truthfulness guarantees. The system must analyze job descriptions, match evidence, write compelling content, and validate output—each requiring different capabilities.

### Decision
Implement a **multi-agent architecture** with 5 specialized functional units, each responsible for a discrete task in the pipeline.

### Alternatives Considered
1. **Single monolithic prompt** — Rejected. Too much cognitive load for one model call; high hallucination risk; no separation of concerns.
2. **Simple RAG pipeline** — Rejected. Retrieval-only doesn't provide the reasoning needed for strategic resume positioning.
3. **7+ agent system** — Rejected for MVP. Orchestration complexity increases fragility; consolidate to 5 units first.

### Consequences
- **Positive:** Clear separation of concerns; each agent can use the optimal model; easier debugging and iteration.
- **Negative:** Increased latency (5 sequential LLM calls minimum); requires robust orchestration.
- **Mitigation:** Deterministic Python orchestrator; parallel calls where possible in future versions.

### References
- ChatGPT architecture proposal (January 2025)
- Claude audit and refinement (January 2025)

---

## ADR-002: Deterministic Orchestrator (No LLM Routing)

### Status
Accepted

### Context
Multi-agent systems often use an LLM as the "conductor" to decide which agent to invoke next. This introduces non-determinism, latency, and debugging difficulty.

### Decision
Implement the orchestrator as **pure Python code** using a state machine pattern. The orchestrator handles:
- Pipeline step sequencing
- State validation between steps
- Retry logic on failures
- Stop conditions (e.g., Truth Auditor hard failures)

LLMs are invoked **only within agent steps**, never for routing decisions.

### Alternatives Considered
1. **LLM-based orchestrator** — Rejected. Adds ~1-2 seconds latency per routing decision; non-deterministic; harder to debug.
2. **LangChain Agent with tools** — Rejected. Tool-calling pattern doesn't fit our linear-with-validation pipeline.
3. **LangGraph state machine** — Considered viable. May adopt in v2 for more complex branching.

### Consequences
- **Positive:** Predictable execution; easier logging and debugging; faster overall pipeline.
- **Negative:** Less flexibility for dynamic task decomposition; requires explicit handling of edge cases.

---

## ADR-003: Evidence Card Data Model

### Status
Accepted

### Context
To prevent hallucination, every claim in the output resume must trace back to source evidence. We need a structured representation of the Fact Resume that enables precise matching and auditing.

### Decision
Parse the Fact Resume into **Evidence Cards**—discrete, ID-referenced units of verifiable information. Each card contains:
- Unique identifier
- Project/initiative name
- Company and timeframe
- Role held during this work
- Scope metadata (team size, geography, budget)
- Quantified metrics (with units and context)
- Skills/tools demonstrated
- Leadership signals
- Raw source text

### Alternatives Considered
1. **Raw text chunks** — Rejected. No structure for precise matching; metrics could be duplicated or contradictory.
2. **Vector embeddings only** — Rejected. Semantic search doesn't guarantee factual accuracy; can't audit claims.
3. **Full document in context each time** — Rejected. Token-inefficient; ~3,500 tokens vs ~800-1,200 for selected cards.

### Consequences
- **Positive:** Every claim is traceable; token-efficient (send only relevant cards); reusable across job applications.
- **Negative:** Requires upfront parsing effort; schema must be maintained as resume evolves.

---

## ADR-004: Multi-Provider LLM Strategy

### Status
Accepted

### Context
Different agents have different requirements: the Evidence Mapper needs precision and low hallucination; the Writer needs natural prose; the ATS Scorer needs speed and low cost.

### Decision
Use **different LLM providers per agent**, configured via YAML:

| Agent | Primary Model | Rationale |
|-------|---------------|-----------|
| JD Analyst + Strategy | Claude Sonnet 4 | Strong reasoning for role inference |
| Evidence Mapper | Claude Sonnet 4 | Lowest hallucination rate; precise instruction-following |
| Resume Writer | GPT-4o | Best natural prose; avoids AI voice |
| ATS Heuristic | Gemini 1.5 Flash | Fast, cheap; pattern matching task |
| Truth Auditor | Claude Sonnet 4 | Conservative; won't rationalize errors |

### Alternatives Considered
1. **Single provider (OpenAI only)** — Rejected. Suboptimal for precision tasks; higher cost.
2. **Single provider (Claude only)** — Rejected. GPT-4o produces more natural prose for writing tasks.
3. **Local models only** — Rejected for MVP. Quality gap too large for critical steps.

### Consequences
- **Positive:** Optimal model for each task; cost optimization; avoids single-provider dependency.
- **Negative:** Multiple API keys to manage; slightly more complex error handling.

---

## ADR-005: Cached Evidence Cards (Privacy & Efficiency)

### Status
Accepted

### Context
The Fact Resume is stable (changes infrequently). Sending the full document (~3,500 tokens) with every job application is token-inefficient and increases API costs.

### Decision
- Parse Fact Resume **once** into `evidence_cards.json`
- Store locally (not sent to any API)
- Each pipeline run:
  1. Evidence Mapper selects relevant card IDs
  2. Only selected cards (~15-25) sent to downstream agents
  
This provides ~65-70% token reduction for Writer and Auditor steps.

### Alternatives Considered
1. **Send full resume every time** — Rejected. Wasteful; ~$0.02-0.05 additional cost per run.
2. **Cloud-hosted evidence store** — Rejected. Privacy concern; adds infrastructure dependency.

### Consequences
- **Positive:** Lower cost; faster inference; resume data stays local.
- **Negative:** Must re-parse when Fact Resume changes; local JSON file must be kept secure.

---

## ADR-006: Separate Truth vs ATS Failure Modes

### Status
Accepted

### Context
The post-Writer validation step checks two categories: (1) factual accuracy/truthfulness, and (2) ATS optimization suggestions. These have different severity levels.

### Decision
Implement **separate failure handling**:

| Category | Severity | Behavior |
|----------|----------|----------|
| Truth Violations | **Blocker** | Pipeline halts; Writer must revise with explicit fixes |
| ATS Suggestions | **Advisory** | Logged in report; surfaced to user; does not block output |

### Alternatives Considered
1. **Single pass/fail** — Rejected. Conflates critical errors with optimization suggestions.
2. **All advisory** — Rejected. Truth violations must be hard stops to maintain integrity.

### Consequences
- **Positive:** Clear priority; user knows which issues are critical vs nice-to-have.
- **Negative:** Requires separate report sections; slightly more complex UI in future.

---

## ADR-007: Output Format (DOCX Primary)

### Status
Accepted

### Context
The system needs to produce resumes that are: (1) ATS-parseable, (2) professionally formatted, (3) editable by the user.

### Decision
- **Primary output:** `.docx` (Microsoft Word format)
- **Internal working format:** Markdown (for diffing and version control)
- **PDF:** Generated from DOCX on-demand, not as primary output

### Alternatives Considered
1. **PDF primary** — Rejected. Not editable; some ATS systems struggle with PDF parsing.
2. **Markdown only** — Rejected. Requires user to convert; loses formatting control.
3. **HTML** — Rejected. Not a standard resume format; ATS compatibility varies.

### Consequences
- **Positive:** Universal compatibility; editable; ATS-safe.
- **Negative:** DOCX generation requires additional tooling (python-docx or docx-js).

---

## ADR-008: Versioning Strategy (Folder Per Job)

### Status
Accepted

### Context
User is applying to multiple companies (DraftKings, WHOOP, athenahealth, etc.) and needs to track what was emphasized for each application.

### Decision
Each pipeline run creates a **versioned output folder**:
```
outputs/
  draftkings-senior-em-2025-01-14/
    resume.docx
    evidence_used.json
    ats_report.json
    diff_from_base.md
  whoop-director-2025-01-15/
    ...
```

### Alternatives Considered
1. **Overwrite single file** — Rejected. Loses history; can't compare variants.
2. **Git-based versioning** — Considered for v2. Adds complexity for MVP.

### Consequences
- **Positive:** Full history; easy comparison; supports interview prep ("what did I claim for this company?").
- **Negative:** Disk space grows with applications (minimal; ~50KB per run).

---

## ADR-009: Gap Handling Strategy

### Status
Accepted

### Context
When a job description requires something not present in the Fact Resume, the system must decide how to handle the gap without inventing information.

### Decision
Implement **three gap strategies**, selectable per gap:

| Strategy | Behavior |
|----------|----------|
| `omit` | Do not mention this requirement in resume |
| `adjacent_experience` | Reference related experience with honest framing (e.g., "containerization experience with Docker" when K8s is requested) |
| `ask_user` | Surface question to user; only add if confirmed |

Default behavior: `adjacent_experience` for skills with clear adjacency; `ask_user` for uncertain gaps; `omit` for hard gaps with no adjacency.

### Alternatives Considered
1. **Always omit** — Rejected. Misses opportunity to show transferable skills.
2. **Always ask user** — Rejected. Too many questions; slows pipeline.
3. **Infer and add** — Rejected. Risk of fabrication.

### Consequences
- **Positive:** Honest handling; preserves user control; surfaces important gaps.
- **Negative:** Requires adjacency mapping; some subjectivity in strategy selection.

---

## ADR-010: Terminology Normalization Pre-Step

### Status
Accepted

### Context
Job descriptions and resumes often use different terms for the same concept (e.g., "HCM" vs "HRIS", "orchestration" vs "workflow automation"). Without normalization, the Evidence Mapper will report false gaps.

### Decision
Implement a **terminology normalization step** before Evidence Mapping:
1. Extract key terms from JD
2. Extract key terms from Evidence Cards
3. Build synonym map (can be LLM-assisted or rule-based)
4. Tag gaps as "true gap" vs "terminology gap"

### Alternatives Considered
1. **Rely on embeddings** — Rejected. Semantic similarity doesn't guarantee term equivalence.
2. **Manual synonym dictionary** — Considered as supplement. Too brittle alone.
3. **Skip normalization** — Rejected. High false-negative rate in matching.

### Consequences
- **Positive:** More accurate matching; fewer false gaps; better keyword optimization.
- **Negative:** Adds one pipeline step; requires maintenance if domains change.

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-01-14 | Carlos Vazquez | Initial ADRs from architecture sessions |
