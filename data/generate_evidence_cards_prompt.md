# Prompt for Generating Evidence Cards from Resume Data

Use this prompt in Claude UI to generate `evidence_cards.json` from resume or career data.

---

## Instructions

Please analyze the provided resume/career information and generate a JSON object containing an array of evidence cards following the structure below. Each evidence card should represent a distinct project, initiative, or significant achievement from the career history.

### Evidence Card Structure

Each evidence card must include the following fields:

**Required Fields:**
- `id` (string): Unique identifier using kebab-case, format: `company-project-name`
- `project` (string): Name of the project or initiative
- `company` (string): Company name where this work occurred
- `timeframe` (string): Date range in format `YYYY-YYYY` or `YYYY-MM to YYYY-MM`
- `role` (string): Job title held during this work
- `raw_text` (string): A single concise paragraph (1-2 sentences) describing the achievement

**Optional but Recommended Fields:**
- `scope` (object): Contains:
  - `team_size` (integer | null): Number of team members
  - `direct_reports` (integer | null): Number of direct reports (if applicable)
  - `geography` (array of strings): Locations/regions involved (e.g., ["US", "Romania"])
  - `budget` (string | null): Budget information if available (e.g., "$3M annual")
  
- `metrics` (array of objects): Quantifiable achievements, each with:
  - `value` (string): The metric value (e.g., "75%", "340K+", "19", "2 months")
  - `description` (string): What the metric represents
  - `context` (string | null): Additional context for the metric

- `skills` (array of strings): Technical skills, tools, or methodologies demonstrated

- `leadership_signals` (array of strings): Leadership behaviors or outcomes (2-5 bullet points)

### Guidelines

1. **Extract Distinct Achievements**: Create separate evidence cards for each significant project, initiative, or achievement. Don't combine unrelated work.

2. **Quantify Everything**: Include metrics wherever possible (percentages, counts, timeframes, sizes, etc.). Metrics are critical for resume impact.

3. **Focus on Impact**: Emphasize outcomes, improvements, and business value. Show before/after comparisons when possible.

4. **Be Specific**: Include actual numbers, technologies used, team sizes, timeframes, and geographic scope.

5. **Extract Leadership Signals**: Identify and highlight leadership behaviors such as:
   - Team building/scaling
   - Process improvements
   - Cross-functional collaboration
   - Budget/resource management
   - Technical decision-making
   - Organizational transformation

6. **Raw Text Quality**: Write clear, concise paragraphs (1-2 sentences) that capture the essence of the achievement with key metrics.

7. **ID Format**: Use kebab-case for IDs: `company-short-project-name` (e.g., `payscale-engineering-leadership-scale`, `grand-circle-cicd-pipeline`)

### Example Evidence Card

```json
{
  "id": "payscale-engineering-leadership-scale",
  "project": "Engineering Organization Leadership & Scale",
  "company": "PayScale",
  "timeframe": "2023-2025",
  "role": "Senior Manager, Software Engineering",
  "scope": {
    "team_size": 19,
    "direct_reports": null,
    "geography": ["US", "Romania", "India"],
    "budget": "$3M annual"
  },
  "metrics": [
    {
      "value": "19",
      "description": "engineers across 3 Scrum teams",
      "context": "supporting B2B and B2C enterprise SaaS product lines"
    },
    {
      "value": "95%",
      "description": "budget adherence",
      "context": "$3M annual engineering budget"
    }
  ],
  "skills": [
    "Team Leadership",
    "Budget Management",
    "Global Team Management",
    "Enterprise SaaS"
  ],
  "leadership_signals": [
    "Led 19 engineers across 3 geographies",
    "Managed $3M annual budget",
    "Built partnerships with product, architecture, DevOps teams"
  ],
  "raw_text": "Led engineering organization of 19 engineers across 3 Scrum teams supporting B2B and B2C enterprise SaaS product lines, overseeing individual performance and collective team goals aligned with product objectives"
}
```

### Output Format

Output **ONLY** valid JSON object format (no markdown code blocks, no explanation text):

```json
{
  "evidence_cards": [
    {
      "id": "...",
      "project": "...",
      "company": "...",
      "timeframe": "...",
      "role": "...",
      "scope": {...},
      "metrics": [...],
      "skills": [...],
      "leadership_signals": [...],
      "raw_text": "..."
    },
    ...
  ]
}
```

**Important:** The output must be a JSON **object** with an `"evidence_cards"` key containing the array, not a direct array. This matches the ResumeForge parser's expected format.

### Important Notes

- All string fields must use proper JSON escaping
- Arrays and objects should be properly formatted
- Use `null` (not `"null"` string) for null values
- Ensure all dates follow the timeframe format: `YYYY-YYYY` or `YYYY-MM to YYYY-MM`
- Include 30-40+ evidence cards for a comprehensive career history (be thorough and granular)
- Group related achievements but separate distinct projects
- Prioritize recent and impactful work

---

## Your Task

Now, please analyze the following resume/career data and generate the evidence cards JSON object (with `"evidence_cards"` key):

[PASTE YOUR RESUME DATA HERE]
