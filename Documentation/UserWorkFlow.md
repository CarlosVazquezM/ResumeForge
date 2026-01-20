# ResumeForge User Workflow

This document outlines a typical 4-week workflow for using ResumeForge to manage your job applications.

---

## Week 1: Setup

### 1. Create your comprehensive Fact Resume (once)

Create a single, comprehensive fact-based resume that contains all your accomplishments, skills, and experiences.

### 2. Parse it into evidence cards (once)

```bash
$ resumeforge parse --fact-resume ./fact_resume.md
```

**Output:**
```
✓ Parsed 67 evidence cards to ./data/evidence_cards.json
```

---

## Week 1-4: Active Applications

### Monday: Found DraftKings Senior EM role

```bash
$ resumeforge generate \
    --jd ./jobs/draftkings-senior-em.txt \
    --title "Senior Engineering Manager"
```

**Output:**
```
outputs/draftkings-senior-em-2025-01-14/
├── resume.docx
├── evidence_used.json
└── ats_report.json
```

---

### Wednesday: Found WHOOP Director role

```bash
$ resumeforge generate \
    --jd ./jobs/whoop-director.txt \
    --title "Director of Engineering"
```

**Output:**
```
outputs/whoop-director-2025-01-16/
```

---

### Friday: Found athenahealth EM role

```bash
$ resumeforge generate \
    --jd ./jobs/athena-em.txt \
    --title "Engineering Manager"
```

**Output:**
```
outputs/athena-em-2025-01-18/
```

---

## Week 3: Interview Prep

DraftKings called back! Time to prepare.

**"What did I emphasize in my DraftKings resume vs my base?"**

```bash
$ resumeforge diff \
    --variant1 ./outputs/draftkings-senior-em-2025-01-14 \
    --variant2 ./templates/base
```

**Output:**

```
DIFFERENCES: DraftKings vs Base
──────────────────────────────────────────────────────────────────────

ADDED EMPHASIS:
+ "real-time data processing" (mentioned 3x)
+ "high-throughput systems" (mentioned 2x)
+ "340K+ records nightly" (promoted to summary)

KEYWORDS INSERTED:
+ distributed systems, event-driven, scalability

SECTIONS REORDERED:
~ Technical Leadership moved above Team Management

EVIDENCE CARDS USED:
• nostromo-etl-metrics (primary)
• romania-scaling (secondary)
• ai-tooling-initiative (tertiary)
```

**Takeaway:** Be ready to discuss real-time processing, Nostromo architecture, and the 340K records metric in depth.

---

## Week 4: Cross-Compare

**"WHOOP also called. How did I position differently?"**

```bash
$ resumeforge diff \
    --variant1 ./outputs/draftkings-senior-em-2025-01-14 \
    --variant2 ./outputs/whoop-director-2025-01-16
```

**Output:**

```
DIFFERENCES: DraftKings vs WHOOP
──────────────────────────────────────────────────────────────────────

DRAFTKINGS emphasized:
• Real-time data, high-throughput, sports/betting domain adjacency
• Technical depth (architecture, systems design)

WHOOP emphasized:
• Health-tech domain, consumer product experience
• Team scaling, cross-geo leadership, culture building
• Director-level scope (strategy, roadmap, stakeholders)

SHARED (consistent across both):
• 19-person team management
• Zero voluntary attrition
• 75% defect reduction
```

**Takeaway:** Now you can context-switch between interviews without mixing up what you told each company.

---

## Summary

This workflow demonstrates:

1. **One-time setup**: Parse your comprehensive fact resume into reusable evidence cards
2. **Rapid application generation**: Create tailored resumes for multiple roles quickly
3. **Interview preparation**: Use diff to understand what you emphasized for each role
4. **Cross-comparison**: Compare different resume variants to maintain consistency and avoid confusion

Each generated resume is:
- Tailored to the specific job description
- Backed by evidence cards (traceable claims)
- ATS-optimized with keyword coverage
- Ready for interviews with clear talking points
