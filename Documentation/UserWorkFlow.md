┌─────────────────────────────────────────────────────────────────────────────┐
│                           WEEK 1: SETUP                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Create your comprehensive Fact Resume (once)                            │
│                                                                             │
│  2. Parse it into evidence cards (once)                                     │
│     $ resumeforge parse --fact-resume ./fact_resume.md                      │
│                                                                             │
│     Output: "✓ Parsed 67 evidence cards to ./data/evidence_cards.json"      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      WEEK 1-4: ACTIVE APPLICATIONS                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Monday: Found DraftKings Senior EM role                                    │
│  $ resumeforge generate \                                                   │
│      --jd ./jobs/draftkings-senior-em.txt \                                 │
│      --title "Senior Engineering Manager"                                   │
│                                                                             │
│  Output: outputs/draftkings-senior-em-2025-01-14/                           │
│          ├── resume.docx                                                    │
│          ├── evidence_used.json                                             │
│          └── ats_report.json                                                │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  Wednesday: Found WHOOP Director role                                       │
│  $ resumeforge generate \                                                   │
│      --jd ./jobs/whoop-director.txt \                                       │
│      --title "Director of Engineering"                                      │
│                                                                             │
│  Output: outputs/whoop-director-2025-01-16/                                 │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  Friday: Found athenahealth EM role                                         │
│  $ resumeforge generate \                                                   │
│      --jd ./jobs/athena-em.txt \                                            │
│      --title "Engineering Manager"                                          │
│                                                                             │
│  Output: outputs/athena-em-2025-01-18/                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       WEEK 3: INTERVIEW PREP                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  DraftKings called back! Time to prepare.                                   │
│                                                                             │
│  "What did I emphasize in my DraftKings resume vs my base?"                 │
│  $ resumeforge diff \                                                       │
│      --variant1 ./outputs/draftkings-senior-em-2025-01-14 \                 │
│      --variant2 ./templates/base                                            │
│                                                                             │
│  Output:                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ DIFFERENCES: DraftKings vs Base                                     │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                     │    │
│  │ ADDED EMPHASIS:                                                     │    │
│  │ + "real-time data processing" (mentioned 3x)                        │    │
│  │ + "high-throughput systems" (mentioned 2x)                          │    │
│  │ + "340K+ records nightly" (promoted to summary)                     │    │
│  │                                                                     │    │
│  │ KEYWORDS INSERTED:                                                  │    │
│  │ + distributed systems, event-driven, scalability                    │    │
│  │                                                                     │    │
│  │ SECTIONS REORDERED:                                                 │    │
│  │ ~ Technical Leadership moved above Team Management                  │    │
│  │                                                                     │    │
│  │ EVIDENCE CARDS USED:                                                │    │
│  │ • nostromo-etl-metrics (primary)                                    │    │
│  │ • romania-scaling (secondary)                                       │    │
│  │ • ai-tooling-initiative (tertiary)                                  │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Now you know: Be ready to discuss real-time processing, Nostromo           │
│  architecture, and the 340K records metric in depth.                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      WEEK 4: CROSS-COMPARE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  "WHOOP also called. How did I position differently?"                       │
│  $ resumeforge diff \                                                       │
│      --variant1 ./outputs/draftkings-senior-em-2025-01-14 \                 │
│      --variant2 ./outputs/whoop-director-2025-01-16                         │
│                                                                             │
│  Output:                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ DIFFERENCES: DraftKings vs WHOOP                                    │    │
│  ├─────────────────────────────────────────────────────────────────────┤    │
│  │                                                                     │    │
│  │ DRAFTKINGS emphasized:                                              │    │
│  │ • Real-time data, high-throughput, sports/betting domain adjacency  │    │
│  │ • Technical depth (architecture, systems design)                    │    │
│  │                                                                     │    │
│  │ WHOOP emphasized:                                                   │    │
│  │ • Health-tech domain, consumer product experience                   │    │
│  │ • Team scaling, cross-geo leadership, culture building              │    │
│  │ • Director-level scope (strategy, roadmap, stakeholders)            │    │
│  │                                                                     │    │
│  │ SHARED (consistent across both):                                    │    │
│  │ • 19-person team management                                         │    │
│  │ • Zero voluntary attrition                                          │    │
│  │ • 75% defect reduction                                              │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  Now you can context-switch between interviews without mixing up            │
│  what you told each company.                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘