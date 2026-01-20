"""Evidence Mapper Agent implementation."""

import json
from typing import TYPE_CHECKING

from resumeforge.agents.base import BaseAgent
from resumeforge.exceptions import ValidationError
from resumeforge.schemas.blackboard import (
    Blackboard,
    Confidence,
    EvidenceMapping,
    GapResolution,
    GapStrategy,
)

if TYPE_CHECKING:
    from resumeforge.providers.base import BaseProvider


class EvidenceMapperAgent(BaseAgent):
    """Maps job requirements to evidence cards and identifies gaps."""
    
    def get_system_prompt(self) -> str:
        """Return the system prompt for evidence mapping."""
        return """You are a precise evidence-matching system. Your task is to map job requirements to verified evidence from the candidate's history.

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
}"""

    def build_user_prompt(self, blackboard: Blackboard) -> str:
        """Build the user prompt from blackboard state."""
        # Validate prerequisites
        if not blackboard.role_profile:
            raise ValidationError(
                "Evidence Mapper: role_profile is required. "
                "Please run JD Analyst agent first to populate role_profile."
            )
        if not blackboard.requirements:
            raise ValidationError(
                "Evidence Mapper: requirements list is empty. "
                "Please run JD Analyst agent first to extract requirements from job description."
            )
        if not blackboard.evidence_cards:
            raise ValidationError(
                "Evidence Mapper: evidence_cards list is empty. "
                "Please load evidence cards into blackboard.evidence_cards before mapping."
            )
        
        # Serialize requirements
        requirements_json = json.dumps(
            [req.model_dump() for req in blackboard.requirements],
            indent=2
        )
        
        # Serialize synonyms map
        synonyms_map_json = json.dumps(blackboard.synonyms_map, indent=2)
        
        # Serialize evidence cards (include key fields for matching)
        evidence_cards_summary = []
        for card in blackboard.evidence_cards:
            card_summary = {
                "id": card.id,
                "project": card.project,
                "company": card.company,
                "timeframe": card.timeframe,
                "role": card.role,
                "skills": card.skills,
                "metrics": [m.model_dump() for m in card.metrics],
                "leadership_signals": card.leadership_signals,
                "raw_text": card.raw_text,
            }
            evidence_cards_summary.append(card_summary)
        
        evidence_cards_json = json.dumps(evidence_cards_summary, indent=2)
        
        return f"""Map the following requirements to the candidate's evidence cards.

## Requirements (from JD Analysis)

{requirements_json}

## Synonyms Map

{synonyms_map_json}

## Evidence Cards

{evidence_cards_json}

## Instructions

1. For each requirement, find matching evidence cards by ID
2. Use the synonyms map to recognize equivalent terms (e.g., "AWS" = "Amazon Web Services")
3. If no evidence exists, mark it as a gap with appropriate classification
4. For gaps, suggest a strategy:
   - **omit**: Not critical, can be omitted
   - **adjacent_experience**: Candidate has related experience that could be emphasized
   - **ask_user**: Critical gap that needs user input

## Output

Respond with JSON:
{{
  "evidence_map": [
    {{
      "requirement_id": "string",
      "evidence_card_ids": ["string"],
      "confidence": "high|medium|low",
      "notes": "string"
    }}
  ],
  "gaps": [
    {{
      "gap_id": "string",
      "requirement_text": "string",
      "gap_type": "true_gap|terminology_gap|hidden_evidence",
      "suggested_strategy": "omit|adjacent_experience|ask_user",
      "adjacent_evidence_ids": ["string"]
    }}
  ],
  "supported_keywords": ["string"],
  "selected_evidence_ids": ["string"]
}}

**IMPORTANT**: 
- Only use evidence_card_ids that exist in the provided evidence cards list
- selected_evidence_ids should be the union of all evidence_card_ids from evidence_map
- supported_keywords should be keywords from requirements that have matching evidence"""

    def parse_response(self, response: str, blackboard: Blackboard) -> Blackboard:
        """Parse LLM response and update blackboard."""
        # Extract JSON from response
        json_text = self._extract_json(response)
        
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON response from Evidence Mapper: {e}") from e
        
        # Validate structure
        if "evidence_map" not in data:
            raise ValidationError("LLM response missing 'evidence_map' key")
        
        if "gaps" not in data:
            raise ValidationError("LLM response missing 'gaps' key")
        
        if "selected_evidence_ids" not in data:
            raise ValidationError("LLM response missing 'selected_evidence_ids' key")
        
        evidence_map_data = data.get("evidence_map", [])
        gaps_data = data.get("gaps", [])
        supported_keywords = data.get("supported_keywords", [])
        selected_evidence_ids = data.get("selected_evidence_ids", [])
        
        # Validate evidence card IDs exist
        available_card_ids = {card.id for card in blackboard.evidence_cards}
        
        # Parse evidence mappings
        evidence_mappings = []
        for i, mapping_data in enumerate(evidence_map_data):
            try:
                # Validate requirement_id exists
                requirement_ids = {req.id for req in blackboard.requirements}
                if mapping_data["requirement_id"] not in requirement_ids:
                    self.logger.warning(
                        "Evidence mapping references unknown requirement",
                        requirement_id=mapping_data["requirement_id"]
                    )
                    continue
                
                # Validate evidence_card_ids exist
                card_ids = mapping_data.get("evidence_card_ids", [])
                invalid_ids = set(card_ids) - available_card_ids
                if invalid_ids:
                    self.logger.warning(
                        "Evidence mapping references non-existent cards",
                        invalid_ids=list(invalid_ids),
                        requirement_id=mapping_data["requirement_id"]
                    )
                    # Filter out invalid IDs
                    card_ids = [cid for cid in card_ids if cid in available_card_ids]
                
                if not card_ids:
                    self.logger.warning(
                        "Evidence mapping has no valid card IDs",
                        requirement_id=mapping_data["requirement_id"]
                    )
                    continue
                
                # Convert confidence string to enum
                confidence_str = mapping_data.get("confidence", "medium").lower()
                if confidence_str == "high":
                    confidence = Confidence.HIGH
                elif confidence_str == "low":
                    confidence = Confidence.LOW
                else:
                    confidence = Confidence.MEDIUM
                
                mapping = EvidenceMapping(
                    requirement_id=mapping_data["requirement_id"],
                    evidence_card_ids=card_ids,
                    confidence=confidence,
                    notes=mapping_data.get("notes")
                )
                evidence_mappings.append(mapping)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse evidence mapping",
                    index=i,
                    error=str(e),
                    mapping_data=mapping_data
                )
                continue
        
        # Parse gap resolutions
        gap_resolutions = []
        for i, gap_data in enumerate(gaps_data):
            try:
                # Convert gap_type to strategy (simplified mapping)
                gap_type = gap_data.get("gap_type", "true_gap")
                strategy_str = gap_data.get("suggested_strategy", "omit")
                
                # Map strategy string to enum
                if strategy_str == "adjacent_experience":
                    strategy = GapStrategy.ADJACENT
                elif strategy_str == "ask_user":
                    strategy = GapStrategy.ASK_USER
                else:
                    strategy = GapStrategy.OMIT
                
                # Validate adjacent_evidence_ids if provided
                adjacent_ids = gap_data.get("adjacent_evidence_ids", [])
                if adjacent_ids:
                    invalid_adjacent = set(adjacent_ids) - available_card_ids
                    if invalid_adjacent:
                        self.logger.warning(
                            "Gap resolution references non-existent adjacent cards",
                            invalid_ids=list(invalid_adjacent)
                        )
                        adjacent_ids = [cid for cid in adjacent_ids if cid in available_card_ids]
                
                gap_resolution = GapResolution(
                    gap_id=gap_data["gap_id"],
                    requirement_text=gap_data["requirement_text"],
                    strategy=strategy,
                    adjacent_evidence_ids=adjacent_ids,
                    user_confirmed=False
                )
                gap_resolutions.append(gap_resolution)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse gap resolution",
                    index=i,
                    error=str(e),
                    gap_data=gap_data
                )
                continue
        
        # Validate selected_evidence_ids
        invalid_selected = set(selected_evidence_ids) - available_card_ids
        if invalid_selected:
            self.logger.warning(
                "Selected evidence IDs include non-existent cards",
                invalid_ids=list(invalid_selected)
            )
            selected_evidence_ids = [cid for cid in selected_evidence_ids if cid in available_card_ids]
        
        # Update blackboard
        blackboard.evidence_map = evidence_mappings
        blackboard.gap_resolutions = gap_resolutions
        blackboard.selected_evidence_ids = selected_evidence_ids
        blackboard.current_step = "evidence_mapping_complete"
        
        self.logger.info(
            "Evidence mapping complete",
            evidence_mappings_count=len(evidence_mappings),
            gaps_count=len(gap_resolutions),
            selected_evidence_count=len(selected_evidence_ids),
            supported_keywords_count=len(supported_keywords)
        )
        
        return blackboard
