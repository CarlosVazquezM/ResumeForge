"""Parser for Fact Resume to Evidence Cards."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from resumeforge.exceptions import ProviderError, ValidationError
from resumeforge.schemas.evidence_card import EvidenceCard
from resumeforge.utils.cost_estimator import estimate_cost
from resumeforge.utils.tokens import estimate_tokens

if TYPE_CHECKING:
    from resumeforge.providers.base import BaseProvider

logger = structlog.get_logger(__name__)

# Constants
MARKDOWN_JSON_PREFIX_LENGTH = 7  # Length of "```json"
MARKDOWN_PREFIX_LENGTH = 3  # Length of "```"
MARKDOWN_SUFFIX_LENGTH = 3  # Length of "```"


class FactResumeParser:
    """Parses a Fact Resume into structured Evidence Cards."""
    
    def __init__(self, provider: "BaseProvider"):
        """
        Initialize parser.
        
        Args:
            provider: LLM provider for parsing assistance
        """
        self.provider = provider
        self.logger = logger.bind(parser="FactResumeParser", model=provider.model)
    
    def estimate_cost(self, resume_path: Path, max_output_tokens: int = 16384) -> dict:
        """
        Estimate the cost of parsing a resume without actually calling the LLM.
        
        Args:
            resume_path: Path to fact resume file
            max_output_tokens: Expected maximum output tokens
            
        Returns:
            Dictionary with cost estimation details
        """
        if not resume_path.exists():
            raise ValidationError(f"Fact Resume Parser: Fact resume file not found: {resume_path}")
        
        resume_text = resume_path.read_text(encoding="utf-8")
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_user_prompt(resume_text)
        
        # Estimate tokens
        input_tokens = estimate_tokens(system_prompt + user_prompt, self.provider)
        
        # Get provider name from class name
        class_name = self.provider.__class__.__name__.lower()
        provider_map = {
            "anthropicprovider": "anthropic",
            "openaiprovider": "openai",
            "googleprovider": "google",
            "groqprovider": "groq",
        }
        provider_name = provider_map.get(class_name, "anthropic")  # Default to anthropic
        
        return estimate_cost(
            provider_name=provider_name,
            model=self.provider.model,
            input_tokens=input_tokens,
            output_tokens=max_output_tokens,
        )
    
    def parse(self, resume_path: Path, dry_run: bool = False) -> list[EvidenceCard] | dict:
        """
        Parse fact resume into evidence cards using LLM-assisted parsing.
        
        Args:
            resume_path: Path to fact resume file
            dry_run: If True, return cost estimation without calling LLM
            
        Returns:
            List of parsed EvidenceCard objects, or cost estimation dict if dry_run=True
            
        Raises:
            FileNotFoundError: If resume file doesn't exist
            ValidationError: If parsed cards don't validate
            ProviderError: If LLM call fails
        """
        if not resume_path.exists():
            raise ValidationError(f"Fact Resume Parser: Fact resume file not found: {resume_path}")
        
        # Read resume text
        self.logger.info("Reading fact resume", path=str(resume_path))
        resume_text = resume_path.read_text(encoding="utf-8")
        
        # Build prompts
        system_prompt = self._get_system_prompt()
        user_prompt = self._build_user_prompt(resume_text)
        
        # Dry run: return cost estimation only
        if dry_run:
            cost_est = self.estimate_cost(resume_path)
            return {
                "dry_run": True,
                "resume_path": str(resume_path),
                "resume_size_chars": len(resume_text),
                "cost_estimation": cost_est,
            }
        
        # Call LLM
        self.logger.info(
            "Calling LLM to parse resume into evidence cards",
            resume_size_chars=len(resume_text),
            timeout_seconds=self.provider.timeout_seconds,
            max_tokens=16384
        )
        try:
            # Try to use JSON mode for OpenAI, but it's optional for other providers
            kwargs = {}
            if hasattr(self.provider, "model") and "gpt" in self.provider.model.lower():
                kwargs["response_format"] = {"type": "json_object"}
            
            self.logger.info("Sending request to LLM (this may take 1-3 minutes for large resumes)...")
            response = self.provider.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,  # Slightly higher for more creative/comprehensive extraction
                max_tokens=16384,  # Increased for comprehensive extraction (30-40+ cards)
                **kwargs
            )
            self.logger.info("Received response from LLM", response_length=len(response))
        except ProviderError:
            # Re-raise ProviderError without wrapping (preserves original error message)
            raise
        except Exception as e:
            self.logger.error("Failed to call LLM for parsing", error=str(e))
            raise ProviderError(f"Failed to parse resume with LLM: {e}") from e
        
        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_text = self._extract_json(response)
            data = json.loads(json_text)
            
            # Validate structure
            if "evidence_cards" not in data:
                raise ValidationError("LLM response missing 'evidence_cards' key")
            
            cards_data = data["evidence_cards"]
            if not isinstance(cards_data, list):
                raise ValidationError("'evidence_cards' must be a list")
            
        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse JSON response", error=str(e), response_preview=response[:500])
            raise ValidationError(f"Invalid JSON response from LLM: {e}") from e
        
        # Validate and create EvidenceCard objects
        evidence_cards = []
        errors = []
        
        for i, card_data in enumerate(cards_data):
            try:
                card = EvidenceCard(**card_data)
                evidence_cards.append(card)
                self.logger.debug("Parsed evidence card", card_id=card.id, index=i)
            except Exception as e:
                errors.append(f"Card {i}: {e}")
                self.logger.warning("Failed to validate evidence card", index=i, error=str(e), card_data=card_data)
        
        if errors:
            self.logger.warning("Some evidence cards failed validation", error_count=len(errors), total=len(cards_data))
        
        if not evidence_cards:
            raise ValidationError(f"No valid evidence cards found. Errors: {errors}")
        
        self.logger.info("Successfully parsed resume", card_count=len(evidence_cards))
        return evidence_cards
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for evidence card parsing."""
        return """You are an expert at parsing resumes into structured evidence cards. Your task is to extract discrete, verifiable units of information from a comprehensive Fact Resume.

## Evidence Card Structure

Each evidence card represents a single project, initiative, or significant accomplishment. Extract:

1. **Unique ID**: Create a kebab-case identifier (e.g., "nostromo-etl-metrics")
2. **Project**: Name of the project or initiative
3. **Company**: Company name where this work was done
4. **Timeframe**: Format as "YYYY-YYYY" or "YYYY-MM to YYYY-MM"
5. **Role**: Job title during this work
6. **Scope**: Team size, direct reports, geography, budget (if available)
7. **Metrics**: Quantified achievements (values with descriptions and context)
8. **Skills**: Technologies, tools, or methodologies demonstrated
9. **Leadership Signals**: Indicators of leadership or impact (if applicable)
10. **Raw Text**: Original source paragraph from the resume

## Rules

- **BE COMPREHENSIVE**: Extract ALL distinct projects, initiatives, and significant achievements. Do not combine unrelated work. Create separate cards for each distinct accomplishment.
- **Granular Extraction**: Don't hesitate to create many cards (30-40+ is fine for a comprehensive career). Each card should represent ONE specific project/achievement.
- Extract ONE card per distinct project/initiative/achievement
- Include ALL quantifiable metrics (percentages, numbers, sizes)
- Preserve exact metric values - do not round or modify
- Include scope information when available (team size, geography, etc.)
- Each card should be self-contained and verifiable
- Use clear, descriptive IDs that indicate the project and key aspect
- **Prioritize completeness**: It's better to have many specific cards than fewer combined ones

## Output Format

Respond with valid JSON:
{
  "evidence_cards": [
    {
      "id": "string",
      "project": "string",
      "company": "string",
      "timeframe": "YYYY-YYYY or YYYY-MM to YYYY-MM (e.g., '2022-2022' for single year, '2020-2024' for range)",
      "role": "string",
      "scope": {
        "team_size": int or null,
        "direct_reports": int or null,
        "geography": ["string"] or [] (never null - use empty array if not available),
        "budget": "string or null"
      },
      "metrics": [
        {
          "value": "string (e.g., '75%', '340K+')",
          "description": "string",
          "context": "string or null"
        }
      ],
      "skills": ["string"],
      "leadership_signals": ["string"],
      "raw_text": "string"
    }
  ]
}

Respond ONLY with valid JSON. Do not include markdown formatting or explanatory text."""
    
    def _build_user_prompt(self, resume_text: str) -> str:
        """Build the user prompt with resume text."""
        return f"""Parse the following Fact Resume into evidence cards.

## Fact Resume

{resume_text}

## Instructions

1. **Extract ALL distinct projects, initiatives, and achievements** - be comprehensive and granular. Don't combine unrelated work. Create separate cards for:
   - Each major project or initiative
   - Each significant achievement with metrics
   - Each team-building/scaling effort
   - Each process improvement initiative
   - Each technical modernization project
   - Each customer impact story
   - Each leadership accomplishment

2. Create one evidence card per distinct project/achievement

3. **Be thorough**: For a comprehensive 20+ year career, expect to generate 30-40+ evidence cards. Don't hesitate to create many cards - completeness is more important than consolidation.

4. Extract all quantifiable metrics exactly as written

5. Include scope information (team size, geography, etc.) when mentioned

6. List all relevant skills and technologies

7. Note leadership signals (team leadership, cross-functional work, etc.)

8. Preserve the original text as raw_text

## Important Formatting Rules

- **Timeframe**: Must be in format "YYYY-YYYY" (e.g., "2022-2022" for a single year, "2020-2024" for a range)
- **Geography**: Use empty array `[]` if not available, never use `null`
- **Scope fields**: Use `null` for missing numeric fields (team_size, direct_reports), but use `[]` for geography

## Goal: Generate 30-40+ evidence cards for comprehensive career coverage. Extract everything, be granular.

Respond with valid JSON matching the evidence card schema."""
    
    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from LLM response, handling markdown code blocks.
        
        Args:
            text: Raw LLM response
            
        Returns:
            JSON string
        """
        text = text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[MARKDOWN_JSON_PREFIX_LENGTH:]  # Remove ```json
        elif text.startswith("```"):
            text = text[MARKDOWN_PREFIX_LENGTH:]  # Remove ```
        
        if text.endswith("```"):
            text = text[:-MARKDOWN_SUFFIX_LENGTH]  # Remove closing ```
        
        return text.strip()
