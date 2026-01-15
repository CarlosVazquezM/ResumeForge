# ResumeForge

**Multi-agent AI system for job-targeted resume generation with truthfulness guarantees.**

ResumeForge transforms your comprehensive "Fact Resume" into job-targeted resumes optimized for specific job descriptions while maintaining strict truthfulness—every claim is traceable to verified source evidence.

## Features

- 🎯 **Job-Targeted Optimization**: Automatically tailors your resume for each job description
- ✅ **Truthfulness Guaranteed**: Zero hallucinated claims—every bullet point traces to evidence
- 🤖 **Multi-Agent Pipeline**: Specialized AI agents for analysis, mapping, writing, and auditing
- 📊 **ATS Optimization**: Keyword coverage scoring and format validation
- 🔒 **Privacy First**: All sensitive data stays local; only selected evidence sent to APIs

## Installation

### Prerequisites

- Python 3.11+
- API keys for at least one LLM provider:
  - OpenAI (GPT-4o) - Required for Writer
  - Anthropic (Claude Sonnet 4) - Required for JD Analyst, Evidence Mapper, Truth Auditor
  - Google (Gemini 1.5 Flash) - Required for ATS Scorer

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/CarlosVazquezM/ResumeForge.git
   cd ResumeForge
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .
   ```

   Or for development with testing tools:
   ```bash
   pip install -e ".[dev]"
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

4. **Copy and customize config (optional):**
   ```bash
   cp config.yaml config.local.yaml
   # Edit config.local.yaml for your preferences
   ```

## Quick Start

### 1. Parse Your Fact Resume (One-time)

```bash
resumeforge parse --fact-resume ./fact_resume.md --output ./data/evidence_cards.json
```

This parses your comprehensive Fact Resume into structured evidence cards.

### 2. Generate a Targeted Resume

```bash
resumeforge generate \
  --jd ./jobs/draftkings-senior-em.txt \
  --title "Senior Engineering Manager" \
  --output-dir ./outputs
```

This generates a job-targeted resume with:
- `resume.docx` - Final DOCX output
- `evidence_used.json` - Which evidence cards were selected
- `claim_index.json` - Traceability map
- `ats_report.json` - ATS scoring details
- `audit_report.json` - Truth audit results

## Project Structure

```
resumeforge/
├── src/resumeforge/       # Main package
│   ├── agents/            # Agent implementations
│   ├── providers/         # LLM provider abstractions
│   ├── schemas/           # Pydantic data models
│   ├── parsers/           # Resume/JD parsers
│   ├── generators/        # Output generators
│   └── utils/             # Utilities
├── tests/                 # Test suite
├── data/                  # Data files (evidence cards, templates)
├── outputs/               # Generated resumes (versioned per job)
└── config.yaml            # Configuration file
```

## Architecture

ResumeForge uses a **multi-agent pipeline** with 5 specialized agents:

1. **JD Analyst + Strategy** - Analyzes job descriptions and determines positioning
2. **Evidence Mapper** - Matches requirements to evidence cards
3. **Resume Writer** - Generates resume content with human tone
4. **ATS Scorer** - Scores keyword coverage and format compatibility
5. **Truth Auditor** - Validates all claims against evidence

See [Documentation/](Documentation/) for detailed architecture documentation:
- [ADR.md](Documentation/ADR.md) - Architecture Decision Records
- [SAD.md](Documentation/SAD.md) - Solution Architecture Document
- [SDD.md](Documentation/SDD.md) - Software Design Document
- [Implementation-Roadmap.md](Documentation/Implementation-Roadmap.md) - Development roadmap

## Development Status

**Current Status:** Configuration complete, ready for implementation

- ✅ Project configuration (`pyproject.toml`, `config.yaml`)
- ✅ Architecture documentation
- ✅ Project structure setup
- ⏭️ Code implementation in progress

See [Implementation-Roadmap.md](Documentation/Implementation-Roadmap.md) for development progress.

## Configuration

Configuration is managed via `config.yaml`. Key settings:

- **Models**: Configure which LLM models to use for each agent
- **Agents**: Adjust temperature, max_tokens per agent
- **Providers**: Configure timeouts, retries per provider
- **Fallback Chain**: Define provider fallback order

See `config.yaml` for all configuration options.

## Contributing

This project is currently in active development. Contributions welcome once MVP is complete.

## License

MIT License - see LICENSE file for details.

## Author

Carlos A. Vazquez Morales

---

**Note:** This is an MVP in development. See [Documentation/Implementation-Roadmap.md](Documentation/Implementation-Roadmap.md) for current status.
