"""JD Analyst + Strategy Agent implementation."""

import json
from typing import TYPE_CHECKING

from resumeforge.agents.base import BaseAgent
from resumeforge.exceptions import ValidationError
from resumeforge.schemas.blackboard import Blackboard, Priority, Requirement, RoleProfile

if TYPE_CHECKING:
    from resumeforge.providers.base import BaseProvider


class JDAnalystAgent(BaseAgent):
    """Analyzes job descriptions and produces strategic guidance."""
    
    def get_system_prompt(self) -> str:
        """Return the system prompt for JD analysis."""
        return """You are an expert technical recruiter and resume strategist. Your task is to analyze a job description and produce a structured analysis that will guide resume optimization.

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
- Output valid JSON only."""

    def build_user_prompt(self, blackboard: Blackboard) -> str:
        """Build the user prompt from blackboard state."""
        job_description = blackboard.inputs.job_description
        target_title = blackboard.inputs.target_title
        
        # Validate inputs
        if not job_description or not job_description.strip():
            raise ValidationError(
                "JD Analyst: job_description is empty. "
                "Please provide a valid job description in blackboard.inputs.job_description"
            )
        if not target_title or not target_title.strip():
            raise ValidationError(
                "JD Analyst: target_title is empty. "
                "Please provide a valid target title in blackboard.inputs.target_title"
            )
        
        return f"""Analyze this job description and produce the structured analysis.

## Job Description

{job_description}

## Target Title (from user)

{target_title}

## Output Format

Respond with a JSON object matching this structure:
{{
  "inferred_level": "string",
  "must_haves": ["string"],
  "nice_to_haves": ["string"],
  "seniority_signals": ["string"],
  "keyword_clusters": {{"category": ["term1", "term2"]}},
  "recommended_storylines": ["string"],
  "priority_sections": ["string"],
  "downplay_sections": ["string"]
}}

Additionally, extract individual requirements as a list. For each requirement, provide:
- id: A unique identifier (e.g., "req-001")
- text: The requirement text
- priority: "high", "medium", or "low" based on how critical it is
- keywords: List of key terms in this requirement

Respond with JSON:
{{
  "role_profile": {{
    "inferred_level": "string",
    "must_haves": ["string"],
    "nice_to_haves": ["string"],
    "seniority_signals": ["string"],
    "keyword_clusters": {{"category": ["term1", "term2"]}},
    "recommended_storylines": ["string"],
    "priority_sections": ["string"],
    "downplay_sections": ["string"]
  }},
  "requirements": [
    {{
      "id": "req-001",
      "text": "string",
      "priority": "high|medium|low",
      "keywords": ["string"]
    }}
  ]
}}"""

    def parse_response(self, response: str, blackboard: Blackboard) -> Blackboard:
        """Parse LLM response and update blackboard."""
        # Extract JSON from response
        json_text = self._extract_json(response)
        
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON response from JD Analyst: {e}") from e
        
        # Validate structure
        if "role_profile" not in data:
            raise ValidationError("LLM response missing 'role_profile' key")
        
        if "requirements" not in data:
            raise ValidationError("LLM response missing 'requirements' key")
        
        role_profile_data = data["role_profile"]
        requirements_data = data["requirements"]
        
        # Validate and create RoleProfile
        try:
            role_profile = RoleProfile(**role_profile_data)
        except Exception as e:
            raise ValidationError(f"Invalid role_profile structure: {e}") from e
        
        # Validate and create Requirements
        requirements = []
        for i, req_data in enumerate(requirements_data):
            try:
                # Convert priority string to Priority enum
                if "priority" in req_data:
                    priority_str = req_data["priority"].lower()
                    if priority_str == "high":
                        req_data["priority"] = Priority.HIGH
                    elif priority_str == "low":
                        req_data["priority"] = Priority.LOW
                    else:
                        req_data["priority"] = Priority.MEDIUM
                else:
                    req_data["priority"] = Priority.MEDIUM
                
                requirement = Requirement(**req_data)
                requirements.append(requirement)
            except Exception as e:
                self.logger.warning("Failed to parse requirement", index=i, error=str(e), req_data=req_data)
                # Continue with other requirements rather than failing entirely
                continue
        
        if not requirements:
            raise ValidationError("No valid requirements found in response")
        
        # Update blackboard
        blackboard.role_profile = role_profile
        blackboard.requirements = requirements
        blackboard.current_step = "jd_analysis_complete"
        
        self.logger.info(
            "JD analysis complete",
            inferred_level=role_profile.inferred_level,
            requirement_count=len(requirements),
            must_haves_count=len(role_profile.must_haves)
        )
        
        return blackboard
