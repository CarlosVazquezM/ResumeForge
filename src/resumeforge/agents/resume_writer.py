"""Resume Writer Agent implementation."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from resumeforge.agents.base import BaseAgent
from resumeforge.exceptions import ValidationError
from resumeforge.schemas.blackboard import Blackboard, ClaimMapping, ResumeDraft, ResumeSection

if TYPE_CHECKING:
    from resumeforge.providers.base import BaseProvider


class ResumeWriterAgent(BaseAgent):
    """Generates resume content from evidence cards with human tone."""
    
    def get_cache_key_inputs(self, blackboard: Blackboard) -> tuple | None:
        """Get cache key inputs: role profile, evidence map, selected evidence IDs, and template."""
        if not blackboard.role_profile or not blackboard.selected_evidence_ids:
            return None
        
        # Include role profile key fields
        role_profile_key = (
            blackboard.role_profile.inferred_level,
            tuple(sorted(blackboard.role_profile.must_haves)),
            tuple(sorted(blackboard.role_profile.nice_to_haves)),
        )
        
        # Include selected evidence IDs (sorted)
        selected_ids_key = tuple(sorted(blackboard.selected_evidence_ids))
        
        # Include evidence map (requirement IDs and evidence card IDs)
        evidence_map_key = tuple(
            (m.requirement_id, tuple(sorted(m.evidence_card_ids)))
            for m in sorted(blackboard.evidence_map, key=lambda m: m.requirement_id)
        ) if blackboard.evidence_map else ()
        
        # Include gap resolutions (gap IDs)
        gap_resolutions_key = tuple(
            g.gap_id for g in sorted(blackboard.gap_resolutions, key=lambda g: g.gap_id)
        ) if blackboard.gap_resolutions else ()
        
        # Include template path (or hash of template content)
        template_path = blackboard.inputs.template_path or ""
        template_key = template_path
        
        return (role_profile_key, selected_ids_key, evidence_map_key, gap_resolutions_key, template_key)
    
    def restore_from_cache(self, blackboard: Blackboard, cached_result: dict) -> Blackboard | None:
        """Restore blackboard from cached resume draft."""
        try:
            # Restore resume draft
            if "resume_draft" in cached_result:
                resume_draft_data = cached_result["resume_draft"]
                resume_sections = [
                    ResumeSection(**s) for s in resume_draft_data.get("sections", [])
                ]
                blackboard.resume_draft = ResumeDraft(sections=resume_sections)
            
            # Restore claim index
            if "claim_index" in cached_result:
                claim_mappings = [
                    ClaimMapping(**c) for c in cached_result["claim_index"]
                ]
                blackboard.claim_index = claim_mappings
            
            # Restore change log
            if "change_log" in cached_result:
                blackboard.change_log = cached_result["change_log"]
            
            blackboard.current_step = "writing"
            
            self.logger.info(
                "Resume writing restored from cache",
                sections_count=len(blackboard.resume_draft.sections) if blackboard.resume_draft else 0,
                claim_mappings_count=len(blackboard.claim_index)
            )
            
            return blackboard
        except Exception as e:
            self.logger.warning("Failed to restore from cache, falling back to LLM", error=str(e))
            return None
    
    def extract_cache_result(self, blackboard: Blackboard) -> dict | None:
        """Extract resume writing result for caching."""
        if not blackboard.resume_draft or not blackboard.claim_index:
            return None
        
        return {
            "resume_draft": blackboard.resume_draft.model_dump(),
            "claim_index": [c.model_dump() for c in blackboard.claim_index],
            "change_log": blackboard.change_log
        }
    
    def get_system_prompt(self) -> str:
        """Return the system prompt for resume writing."""
        return """You are an expert resume writer who creates compelling, human-sounding resumes. You write with clarity, confidence, and results-focus.

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

Produce the resume as structured sections, plus a claim_index mapping every bullet to its evidence sources."""

    def build_user_prompt(self, blackboard: Blackboard) -> str:
        """Build the user prompt from blackboard state."""
        # Validate prerequisites
        if not blackboard.role_profile:
            raise ValidationError(
                "Resume Writer: role_profile is required. "
                "Please run JD Analyst agent first to populate role_profile."
            )
        if not blackboard.selected_evidence_ids:
            raise ValidationError(
                "Resume Writer: selected_evidence_ids is empty. "
                "Please run Evidence Mapper agent first to select evidence cards."
            )
        if not blackboard.evidence_cards:
            raise ValidationError(
                "Resume Writer: evidence_cards list is empty. "
                "Please load evidence cards into blackboard.evidence_cards before writing."
            )
        
        # Get selected evidence cards
        selected_cards = blackboard.get_selected_evidence_cards()
        if not selected_cards:
            raise ValidationError(
                f"Resume Writer: No evidence cards found for selected_evidence_ids: {blackboard.selected_evidence_ids}. "
                f"Available card IDs: {[card.id for card in blackboard.evidence_cards]}"
            )
        
        # Load template structure
        template_path = Path(blackboard.inputs.template_path)
        if template_path.exists():
            template_structure = template_path.read_text(encoding="utf-8")
        else:
            # Fallback to basic structure if template doesn't exist
            template_structure = """# [Name]
[Contact Information]

## Summary
[Professional summary]

## Experience
[Work experience with bullets]

## Education
[Education details]

## Skills
[Skills list]"""
            self.logger.warning("Template file not found, using default structure", template_path=str(template_path))
        
        # Serialize selected evidence cards (full details for writing)
        evidence_cards_json = json.dumps(
            [card.model_dump() for card in selected_cards],
            indent=2
        )
        
        # Serialize gap resolutions
        gap_resolutions_json = json.dumps(
            [gap.model_dump() for gap in blackboard.gap_resolutions],
            indent=2
        )
        
        # Get strategy guidance
        role_profile = blackboard.role_profile
        recommended_storylines = ", ".join(role_profile.recommended_storylines) if role_profile.recommended_storylines else "None specified"
        priority_sections = ", ".join(role_profile.priority_sections) if role_profile.priority_sections else "All sections"
        downplay_sections = ", ".join(role_profile.downplay_sections) if role_profile.downplay_sections else "None"
        
        max_pages = blackboard.inputs.length_rules.max_pages
        target_title = blackboard.inputs.target_title
        
        return f"""Write a targeted resume using ONLY the following inputs.

## Base Template Structure

{template_structure}

## Strategy Guidance

- Recommended storylines: {recommended_storylines}
- Priority sections: {priority_sections}
- Downplay: {downplay_sections}

## Evidence Cards to Use (ONLY use these)

{evidence_cards_json}

## Gap Handling

{gap_resolutions_json}

## Constraints

- Maximum pages: {max_pages}
- Target role: {target_title}

## Instructions

1. **Follow the template structure exactly** - Use the same section names and order
2. **Use ONLY information from the provided evidence cards** - Do not add facts not in the cards
3. **Create compelling bullets** - Start with impact, use metrics, avoid AI-sounding phrases
4. **For each bullet point**, assign a unique bullet_id (format: "section-company-bullet-N")
5. **Record evidence sources** - Every bullet must reference at least one evidence_card_id
6. **Handle gaps appropriately** - Use gap_resolutions to decide what to omit or emphasize
7. **Write in markdown format** - Use proper markdown syntax for formatting

## Output Format

Respond with JSON:
{{
  "sections": [
    {{
      "name": "Summary",
      "content": "markdown content"
    }},
    {{
      "name": "Experience",
      "content": "markdown content with bullets"
    }}
  ],
  "claim_index": [
    {{
      "bullet_id": "experience-payscale-bullet-1",
      "bullet_text": "The actual bullet text",
      "evidence_card_ids": ["card-id-1", "card-id-2"]
    }}
  ],
  "change_log": [
    "Added emphasis on distributed systems per strategy",
    "Moved AI initiatives to prominent position"
  ]
}}

**CRITICAL**: Every bullet point in the content must have a corresponding entry in claim_index with evidence_card_ids."""

    def parse_response(self, response: str, blackboard: Blackboard) -> Blackboard:
        """Parse LLM response and update blackboard."""
        # Extract JSON from response
        json_text = self._extract_json(response)
        
        try:
            data = self._parse_json_with_repair(json_text, context="Resume Writer")
        except ValidationError:
            # Re-raise ValidationError as-is (already has good error message)
            raise
        
        # Validate structure
        if "sections" not in data:
            raise ValidationError("LLM response missing 'sections' key")
        
        if "claim_index" not in data:
            raise ValidationError("LLM response missing 'claim_index' key")
        
        sections_data = data.get("sections", [])
        claim_index_data = data.get("claim_index", [])
        change_log = data.get("change_log", [])
        
        # Validate and create ResumeSections
        resume_sections = []
        for i, section_data in enumerate(sections_data):
            try:
                if "name" not in section_data or "content" not in section_data:
                    raise ValidationError("Resume Writer: Section must have 'name' and 'content' fields")
                
                section = ResumeSection(
                    name=section_data["name"],
                    content=section_data["content"]
                )
                resume_sections.append(section)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse resume section",
                    index=i,
                    error=str(e),
                    section_data=section_data
                )
                continue
        
        if not resume_sections:
            raise ValidationError("No valid resume sections found in response")
        
        # Validate and create ClaimMappings
        available_card_ids = {card.id for card in blackboard.evidence_cards}
        claim_mappings = []
        
        for i, claim_data in enumerate(claim_index_data):
            try:
                # Validate required fields
                if "bullet_id" not in claim_data:
                    raise ValidationError("Resume Writer: ClaimMapping must have 'bullet_id'")
                if "bullet_text" not in claim_data:
                    raise ValidationError("Resume Writer: ClaimMapping must have 'bullet_text'")
                if "evidence_card_ids" not in claim_data:
                    raise ValidationError("Resume Writer: ClaimMapping must have 'evidence_card_ids'")
                
                evidence_card_ids = claim_data["evidence_card_ids"]
                if not isinstance(evidence_card_ids, list):
                    raise ValidationError("Resume Writer: evidence_card_ids must be a list")
                
                if not evidence_card_ids:
                    self.logger.warning(
                        "ClaimMapping has no evidence_card_ids",
                        bullet_id=claim_data.get("bullet_id")
                    )
                    continue
                
                # Validate evidence card IDs exist
                invalid_ids = set(evidence_card_ids) - available_card_ids
                if invalid_ids:
                    self.logger.warning(
                        "ClaimMapping references non-existent evidence cards",
                        bullet_id=claim_data.get("bullet_id"),
                        invalid_ids=list(invalid_ids)
                    )
                    # Filter out invalid IDs
                    evidence_card_ids = [cid for cid in evidence_card_ids if cid in available_card_ids]
                
                if not evidence_card_ids:
                    self.logger.warning(
                        "ClaimMapping has no valid evidence_card_ids after filtering",
                        bullet_id=claim_data.get("bullet_id")
                    )
                    continue
                
                claim_mapping = ClaimMapping(
                    bullet_id=claim_data["bullet_id"],
                    bullet_text=claim_data["bullet_text"],
                    evidence_card_ids=evidence_card_ids
                )
                claim_mappings.append(claim_mapping)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse claim mapping",
                    index=i,
                    error=str(e),
                    claim_data=claim_data
                )
                continue
        
        if not claim_mappings:
            raise ValidationError("No valid claim mappings found in response")
        
        # Create ResumeDraft
        resume_draft = ResumeDraft(sections=resume_sections)
        
        # Update blackboard
        blackboard.resume_draft = resume_draft
        blackboard.claim_index = claim_mappings
        blackboard.change_log = change_log if isinstance(change_log, list) else []
        blackboard.current_step = "writing"
        
        self.logger.info(
            "Resume writing complete",
            sections_count=len(resume_sections),
            claim_mappings_count=len(claim_mappings),
            change_log_entries=len(blackboard.change_log)
        )
        
        return blackboard
