"""Auditor Agent implementation (ATS Scorer + Truth Auditor)."""

import json
from typing import TYPE_CHECKING

from resumeforge.agents.base import BaseAgent
from resumeforge.exceptions import ValidationError
from resumeforge.schemas.blackboard import ATSReport, AuditReport, Blackboard, TruthViolation

if TYPE_CHECKING:
    from resumeforge.providers.base import BaseProvider

# Constants
ATS_SCORING_TEMPERATURE = 0.2  # Low temperature for consistent scoring
ATS_SCORING_MAX_TOKENS = 8192  # Increased to 8K to handle long keyword lists (Gemini 2.5 Flash supports up to 8K output)
MAX_KEYWORDS_IN_SUGGESTION = 5


class AuditorAgent(BaseAgent):
    """Audits resume for ATS compatibility and truthfulness."""
    
    def get_cache_key_inputs(self, blackboard: Blackboard) -> tuple | None:
        """Get cache key inputs for truth auditing: resume content and evidence card IDs."""
        if not blackboard.resume_draft or not blackboard.evidence_cards:
            return None
        
        # Serialize resume content
        resume_content = "\n\n".join([
            f"## {section.name}\n{section.content}"
            for section in blackboard.resume_draft.sections
        ])
        
        # Include evidence card IDs (sorted)
        evidence_card_ids = tuple(sorted(card.id for card in blackboard.evidence_cards))
        
        return (resume_content, evidence_card_ids)
    
    def restore_from_cache(self, blackboard: Blackboard, cached_result: dict) -> Blackboard | None:
        """Restore blackboard from cached truth audit result."""
        try:
            # Restore audit report
            if "audit_report" in cached_result:
                audit_report_data = cached_result["audit_report"]
                # Convert truth violations
                if "truth_violations" in audit_report_data:
                    violations = [
                        TruthViolation(**v) for v in audit_report_data["truth_violations"]
                    ]
                    audit_report_data["truth_violations"] = violations
                blackboard.audit_report = AuditReport(**audit_report_data)
            
            blackboard.current_step = "auditing"
            
            self.logger.info(
                "Truth auditing restored from cache",
                passed=blackboard.audit_report.passed if blackboard.audit_report else None,
                violations_count=len(blackboard.audit_report.truth_violations) if blackboard.audit_report else 0
            )
            
            return blackboard
        except Exception as e:
            self.logger.warning("Failed to restore from cache, falling back to LLM", error=str(e))
            return None
    
    def extract_cache_result(self, blackboard: Blackboard) -> dict | None:
        """Extract truth audit result for caching."""
        if not blackboard.audit_report:
            return None
        
        return {
            "audit_report": blackboard.audit_report.model_dump()
        }
    
    def _get_ats_cache_key_inputs(self, blackboard: Blackboard) -> tuple | None:
        """Get cache key inputs for ATS scoring: resume content, role profile keywords, and target title."""
        if not blackboard.resume_draft or not blackboard.role_profile:
            return None
        
        # Serialize resume content
        resume_content = "\n\n".join([
            f"## {section.name}\n{section.content}"
            for section in blackboard.resume_draft.sections
        ])
        
        # Get JD keywords
        jd_keywords = []
        if blackboard.role_profile.keyword_clusters:
            for cluster in blackboard.role_profile.keyword_clusters.values():
                jd_keywords.extend(cluster)
        jd_keywords.extend(blackboard.role_profile.must_haves)
        jd_keywords.extend(blackboard.role_profile.nice_to_haves)
        jd_keywords_key = tuple(sorted(set(jd_keywords)))
        
        # Include target title
        target_title = blackboard.inputs.target_title or ""
        
        return (resume_content, jd_keywords_key, target_title)
    
    def _get_ats_cache_result(self, blackboard: Blackboard) -> dict | None:
        """Get cached ATS report if available."""
        cache_inputs = self._get_ats_cache_key_inputs(blackboard)
        if cache_inputs is None:
            return None
        
        cache = getattr(blackboard, "_llm_cache", None)
        if cache is None:
            return None
        
        return cache.get("ats_scorer", *cache_inputs)
    
    def _save_ats_cache_result(self, blackboard: Blackboard, result: dict) -> None:
        """Save ATS report to cache."""
        cache_inputs = self._get_ats_cache_key_inputs(blackboard)
        if cache_inputs is None:
            return
        
        cache = getattr(blackboard, "_llm_cache", None)
        if cache is None:
            return
        
        cache.set("ats_scorer", result, *cache_inputs)
    
    def __init__(self, ats_provider: "BaseProvider", truth_provider: "BaseProvider", config: dict):
        """
        Initialize auditor with two providers.
        
        Args:
            ats_provider: Provider for ATS scoring (typically Gemini)
            truth_provider: Provider for truth auditing (typically Claude)
            config: Agent configuration dictionary
        """
        # Use truth_provider as the main provider for BaseAgent
        super().__init__(truth_provider, config)
        self.ats_provider = ats_provider
        self.truth_provider = truth_provider
        self.logger = self.logger.bind(agent="AuditorAgent")
    
    def get_system_prompt(self) -> str:
        """Return the system prompt for truth auditing."""
        return """You are a truth verification system. Your job is to ensure every claim in the resume is supported by evidence.

## CRITICAL: This is a blocking check. Be strict.

### What to Check

1. **Unsupported Claims**: Any statement not traceable to an evidence card
2. **Metric Inconsistencies**: Numbers that don't match evidence (e.g., "40%" vs "35%")
3. **Date/Tenure Errors**: Incorrect timeframes
4. **Inflated Scope**: Claims that overstate what's in evidence
5. **Fabricated Skills**: Technologies or skills not in evidence cards

### Violation Severity

- **BLOCKER**: Unsupported claims, fabricated data → Pipeline must halt
- **WARNING**: Minor inconsistencies, phrasing concerns → Log but continue

### Output Format

{
  "truth_violations": [
    {
      "bullet_id": "experience-payscale-bullet-3",
      "bullet_text": "The problematic text",
      "violation": "Claims 80% improvement but evidence shows 75%"
    }
  ],
  "inconsistencies": [
    "Date range for PayScale shows 2020-2024 in one place, 2021-2024 in another"
  ],
  "ats_suggestions": [
    "Consider adding 'microservices' keyword which you can support"
  ],
  "passed": false
}"""

    def build_user_prompt(self, blackboard: Blackboard) -> str:
        """Build the user prompt from blackboard state."""
        # Validate prerequisites
        if not blackboard.resume_draft:
            raise ValidationError(
                "Auditor: resume_draft is required. "
                "Please run Resume Writer agent first to populate resume_draft."
            )
        if not blackboard.claim_index:
            raise ValidationError(
                "Auditor: claim_index is required. "
                "Please run Resume Writer agent first to populate claim_index."
            )
        if not blackboard.evidence_cards:
            raise ValidationError(
                "Auditor: evidence_cards list is empty. "
                "Please load evidence cards into blackboard.evidence_cards before auditing."
            )
        if not blackboard.role_profile:
            raise ValidationError(
                "Auditor: role_profile is required. "
                "Please run JD Analyst agent first to populate role_profile."
            )
        
        # Serialize resume draft
        resume_sections = []
        for section in blackboard.resume_draft.sections:
            resume_sections.append({
                "name": section.name,
                "content": section.content
            })
        resume_draft_json = json.dumps(resume_sections, indent=2)
        
        # Serialize claim index
        claim_index_json = json.dumps(
            [claim.model_dump() for claim in blackboard.claim_index],
            indent=2
        )
        
        # Serialize evidence cards (for verification)
        evidence_cards_json = json.dumps(
            [card.model_dump() for card in blackboard.evidence_cards],
            indent=2
        )
        
        # Get JD keywords for reference
        jd_keywords = []
        if blackboard.role_profile.keyword_clusters:
            for cluster in blackboard.role_profile.keyword_clusters.values():
                jd_keywords.extend(cluster)
        jd_keywords.extend(blackboard.role_profile.must_haves)
        jd_keywords.extend(blackboard.role_profile.nice_to_haves)
        
        return f"""Verify the truthfulness of this resume against the evidence cards.

## Resume Draft

{resume_draft_json}

## Claim Index (Bullet → Evidence Mapping)

{claim_index_json}

## Evidence Cards (Source of Truth)

{evidence_cards_json}

## Target Role

{blackboard.inputs.target_title}

## JD Keywords (for reference)

{', '.join(set(jd_keywords)) if jd_keywords else 'None specified'}

## Instructions

1. **Verify every bullet point** - Check that each claim in claim_index is supported by the referenced evidence cards
2. **Check metrics** - Ensure numbers match exactly (don't allow rounding or modification)
3. **Check dates/timeframes** - Verify consistency across the resume
4. **Check scope** - Ensure claims don't overstate what's in evidence
5. **Check skills** - Ensure technologies/skills mentioned are in evidence cards
6. **Be strict** - Any unsupported claim is a blocker

## Output Format

Respond with JSON:
{{
  "truth_violations": [
    {{
      "bullet_id": "string",
      "bullet_text": "string",
      "violation": "string (description of the violation)"
    }}
  ],
  "inconsistencies": ["string"],
  "ats_suggestions": ["string"],
  "passed": true/false
}}

**CRITICAL**: If ANY truth_violations are found, set "passed" to false. Only set "passed" to true if ALL claims are verifiable."""

    def parse_response(self, response: str, blackboard: Blackboard) -> Blackboard:
        """Parse LLM response and update blackboard."""
        # Extract JSON from response
        json_text = self._extract_json(response)
        
        try:
            data = self._parse_json_with_repair(json_text, context="Truth Auditor")
        except ValidationError:
            # Re-raise ValidationError as-is (already has good error message)
            raise
        
        # Validate structure
        if "passed" not in data:
            raise ValidationError("LLM response missing 'passed' key")
        
        truth_violations_data = data.get("truth_violations", [])
        inconsistencies = data.get("inconsistencies", [])
        ats_suggestions = data.get("ats_suggestions", [])
        passed = data.get("passed", True)
        
        # Parse truth violations
        truth_violations = []
        for i, violation_data in enumerate(truth_violations_data):
            try:
                violation = TruthViolation(**violation_data)
                truth_violations.append(violation)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse truth violation",
                    index=i,
                    error=str(e),
                    violation_data=violation_data
                )
                continue
        
        # Create audit report
        audit_report = AuditReport(
            truth_violations=truth_violations,
            ats_suggestions=ats_suggestions if isinstance(ats_suggestions, list) else [],
            inconsistencies=inconsistencies if isinstance(inconsistencies, list) else [],
            passed=passed
        )
        
        # Update blackboard
        blackboard.audit_report = audit_report
        blackboard.current_step = "auditing"
        
        self.logger.info(
            "Truth audit complete",
            passed=passed,
            violations_count=len(truth_violations),
            inconsistencies_count=len(inconsistencies)
        )
        
        return blackboard
    
    def execute_ats_scoring(self, blackboard: Blackboard) -> Blackboard:
        """
        Execute ATS scoring using the ATS provider.
        
        Args:
            blackboard: Current blackboard state
            
        Returns:
            Updated blackboard with ATS report
        """
        if not blackboard.resume_draft:
            raise ValidationError(
                "Auditor: resume_draft is required for ATS scoring. "
                "Please run Resume Writer agent first to populate resume_draft."
            )
        if not blackboard.role_profile:
            raise ValidationError(
                "Auditor: role_profile is required for ATS scoring. "
                "Please run JD Analyst agent first to populate role_profile."
            )
        
        # Check cache first
        cached_ats_result = self._get_ats_cache_result(blackboard)
        if cached_ats_result is not None:
            self.logger.info("ATS scoring cache hit - restoring from cache")
            try:
                ats_report = ATSReport(**cached_ats_result["ats_report"])
                blackboard.ats_report = ats_report
                self.logger.info(
                    "ATS scoring restored from cache",
                    keyword_coverage=ats_report.keyword_coverage_score,
                    role_signal=ats_report.role_signal_score
                )
                return blackboard
            except Exception as e:
                self.logger.warning("Failed to restore ATS from cache, falling back to LLM", error=str(e))
                # Fall through to normal execution
        
        # Build ATS scoring prompt
        system_prompt = """You are an ATS (Applicant Tracking System) compatibility analyzer. Score the resume on keyword coverage and formatting safety.

## Scoring Criteria

### Keyword Coverage (0-100)
- Count supported keywords from the JD that appear in the resume
- Score = (matched_keywords / total_jd_keywords) * 100
- Only count keywords the candidate can legitimately claim

### Role Signal Score (0-100)
- Does the resume's tone match the seniority level?
- Leadership language for manager+ roles
- Technical depth for IC roles
- Balance of strategic vs tactical

### Format Warnings
Flag any of these ATS-unfriendly elements:
- Tables or columns
- Images or graphics
- Headers/footers with critical info
- Non-standard section names
- Unusual fonts or formatting

## Output Format

{
  "keyword_coverage_score": 85,
  "supported_keywords": ["Python", "AWS", "team leadership"],
  "missing_keywords": ["Kubernetes"],
  "format_warnings": [],
  "role_signal_score": 90
}"""
        
        # Serialize resume draft
        resume_content = "\n\n".join([
            f"## {section.name}\n{section.content}"
            for section in blackboard.resume_draft.sections
        ])
        
        # Get JD keywords
        jd_keywords = []
        if blackboard.role_profile.keyword_clusters:
            for cluster in blackboard.role_profile.keyword_clusters.values():
                jd_keywords.extend(cluster)
        jd_keywords.extend(blackboard.role_profile.must_haves)
        jd_keywords.extend(blackboard.role_profile.nice_to_haves)
        
        user_prompt = f"""Score this resume for ATS compatibility.

## Resume Content

{resume_content}

## Target Role

{blackboard.inputs.target_title}

## JD Keywords to Check

{', '.join(set(jd_keywords)) if jd_keywords else 'None specified'}

## Instructions

1. Calculate keyword coverage score (0-100)
2. Calculate role signal score (0-100)
3. Check for format warnings
4. List supported and missing keywords (limit to top 20 most important keywords per list to keep response concise)

Respond with JSON matching the ATS report format."""
        
        # Call ATS provider
        self.logger.info("Executing ATS scoring")
        try:
            response = self.ats_provider.generate_text(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=ATS_SCORING_TEMPERATURE,
                max_tokens=ATS_SCORING_MAX_TOKENS
            )
        except Exception as e:
            self.logger.error("ATS scoring failed", error=str(e))
            raise ValidationError(f"Failed to execute ATS scoring: {e}") from e
        
        # Parse ATS response
        json_text = self._extract_json(response)
        try:
            ats_data = self._parse_json_with_repair(json_text, context="ATS Scorer")
        except ValidationError:
            # Re-raise ValidationError as-is (already has good error message)
            raise
        
        # Validate and create ATSReport
        # If JSON was truncated, provide defaults for missing required fields
        if "role_signal_score" not in ats_data:
            self.logger.warning(
                "ATS response truncated - missing role_signal_score, using default",
                available_fields=list(ats_data.keys())
            )
            # Estimate role_signal_score based on keyword_coverage_score if available
            if "keyword_coverage_score" in ats_data:
                # Use keyword coverage as a proxy (usually correlated)
                ats_data["role_signal_score"] = min(ats_data["keyword_coverage_score"] * 1.1, 100.0)
            else:
                ats_data["role_signal_score"] = 50.0  # Neutral default
        
        if "keyword_coverage_score" not in ats_data:
            self.logger.warning(
                "ATS response truncated - missing keyword_coverage_score, using default",
                available_fields=list(ats_data.keys())
            )
            ats_data["keyword_coverage_score"] = 0.0
        
        try:
            ats_report = ATSReport(**ats_data)
        except Exception as e:
            raise ValidationError(f"Invalid ATS report structure: {e}") from e
        
        # Update blackboard
        blackboard.ats_report = ats_report
        
        # Save to cache
        cache_inputs = self._get_ats_cache_key_inputs(blackboard)
        if cache_inputs is not None:
            self._save_ats_cache_result(blackboard, {
                "ats_report": ats_report.model_dump()
            })
        
        self.logger.info(
            "ATS scoring complete",
            keyword_coverage=ats_report.keyword_coverage_score,
            role_signal=ats_report.role_signal_score,
            format_warnings_count=len(ats_report.format_warnings)
        )
        
        return blackboard
    
    def execute(self, blackboard: Blackboard) -> Blackboard:
        """
        Execute both ATS scoring and truth auditing.
        
        Args:
            blackboard: Current blackboard state
            
        Returns:
            Updated blackboard with audit reports
        """
        # First run ATS scoring
        blackboard = self.execute_ats_scoring(blackboard)
        
        # Then run truth auditing (uses parent execute method)
        blackboard = super().execute(blackboard)
        
        # Merge ATS suggestions into audit report if available
        if blackboard.ats_report and blackboard.audit_report:
            # Add ATS suggestions to audit report
            if blackboard.ats_report.missing_keywords:
                suggestion = (
                    f"Consider adding these keywords: "
                    f"{', '.join(blackboard.ats_report.missing_keywords[:MAX_KEYWORDS_IN_SUGGESTION])}"
                )
                if suggestion not in blackboard.audit_report.ats_suggestions:
                    blackboard.audit_report.ats_suggestions.append(suggestion)
            
            if blackboard.ats_report.format_warnings:
                for warning in blackboard.ats_report.format_warnings:
                    if warning not in blackboard.audit_report.ats_suggestions:
                        blackboard.audit_report.ats_suggestions.append(warning)
        
        return blackboard
