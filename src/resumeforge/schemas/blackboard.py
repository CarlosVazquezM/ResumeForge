"""Blackboard state schema definitions."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator

from resumeforge.schemas.evidence_card import EvidenceCard


class Priority(str, Enum):
    """Priority level for requirements."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Confidence(str, Enum):
    """Confidence level for evidence matching."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GapStrategy(str, Enum):
    """Strategy for handling gaps."""

    OMIT = "omit"
    ADJACENT = "adjacent_experience"
    ASK_USER = "ask_user"


# Input Models
class LengthRules(BaseModel):
    """Length constraints for resume."""

    max_pages: int = 2


class Inputs(BaseModel):
    """Pipeline inputs."""

    job_description: str
    target_title: str
    length_rules: LengthRules = Field(default_factory=LengthRules)
    template_path: str


# Analysis Models
class RoleProfile(BaseModel):
    """Role profile from JD analysis."""

    inferred_level: str = Field(..., description="e.g., 'Senior Manager', 'Director'")
    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    seniority_signals: list[str] = Field(default_factory=list)
    keyword_clusters: dict[str, list[str]] = Field(default_factory=dict)
    recommended_storylines: list[str] = Field(default_factory=list)
    priority_sections: list[str] = Field(default_factory=list)
    downplay_sections: list[str] = Field(default_factory=list)


class Requirement(BaseModel):
    """A requirement from the job description."""

    id: str
    text: str
    priority: Priority = Priority.MEDIUM
    keywords: list[str] = Field(default_factory=list)


# Evidence Mapping Models
class EvidenceMapping(BaseModel):
    """Mapping of requirement to evidence cards."""

    requirement_id: str
    evidence_card_ids: list[str]
    confidence: Confidence
    notes: str | None = None


class GapResolution(BaseModel):
    """Resolution strategy for a gap."""

    gap_id: str
    requirement_text: str
    strategy: GapStrategy
    adjacent_evidence_ids: list[str] = Field(default_factory=list)
    user_confirmed: bool = False


# Resume Draft Models
class ResumeSection(BaseModel):
    """A section of the resume."""

    name: str
    content: str


class ResumeDraft(BaseModel):
    """Draft resume content."""

    sections: list[ResumeSection] = Field(default_factory=list)


class ClaimMapping(BaseModel):
    """Mapping of a claim to evidence cards."""

    bullet_id: str = Field(..., description="e.g., 'experience-payscale-bullet-1'")
    bullet_text: str
    evidence_card_ids: list[str] = Field(..., min_length=1)

    @field_validator("evidence_card_ids")
    @classmethod
    def validate_evidence_card_ids(cls, v: list[str]) -> list[str]:
        """Ensure at least one evidence card ID is provided (truthfulness guarantee)."""
        if not v:
            raise ValueError("ClaimMapping must reference at least one evidence_card_id")
        return v

    def validate_against_cards(self, available_card_ids: set[str]) -> bool:
        """
        Validate that all referenced evidence cards exist.
        
        Args:
            available_card_ids: Set of available evidence card IDs
            
        Returns:
            True if all referenced cards exist
        """
        return set(self.evidence_card_ids).issubset(available_card_ids)


# Audit Models
class TruthViolation(BaseModel):
    """A truth violation found by auditor."""

    bullet_id: str
    bullet_text: str
    violation: str = Field(..., description="Description of the violation")


class ATSReport(BaseModel):
    """ATS compatibility report."""

    keyword_coverage_score: float = Field(..., ge=0, le=100)
    supported_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    format_warnings: list[str] = Field(default_factory=list)
    role_signal_score: float = Field(..., ge=0, le=100)


class AuditReport(BaseModel):
    """Audit report with truth violations and ATS suggestions."""

    truth_violations: list[TruthViolation] = Field(default_factory=list)
    ats_suggestions: list[str] = Field(default_factory=list)
    inconsistencies: list[str] = Field(default_factory=list)
    passed: bool = Field(default=True)


# User Interaction Models
class UserQuestion(BaseModel):
    """A question for the user."""

    gap_id: str
    question: str
    impact: str = Field(..., description="Why answering this matters")


# Main Blackboard
class Blackboard(BaseModel):
    """Main blackboard state object passed through pipeline."""

    # Inputs
    inputs: Inputs
    
    # Parsed data
    evidence_cards: list[EvidenceCard] = Field(default_factory=list)
    synonyms_map: dict[str, list[str]] = Field(default_factory=dict)
    
    # JD Analysis outputs
    role_profile: RoleProfile | None = None
    requirements: list[Requirement] = Field(default_factory=list)
    
    # Evidence Mapping outputs
    evidence_map: list[EvidenceMapping] = Field(default_factory=list)
    gap_resolutions: list[GapResolution] = Field(default_factory=list)
    selected_evidence_ids: list[str] = Field(default_factory=list)
    
    # Writer outputs
    resume_draft: ResumeDraft | None = None
    claim_index: list[ClaimMapping] = Field(default_factory=list)
    change_log: list[str] = Field(default_factory=list)
    
    # Audit outputs
    ats_report: ATSReport | None = None
    audit_report: AuditReport | None = None
    
    # User interaction
    questions_for_user: list[UserQuestion] = Field(default_factory=list)
    
    # Pipeline state
    current_step: str = "init"
    retry_count: int = 0
    max_retries: int = 3

    def get_selected_evidence_cards(self) -> list[EvidenceCard]:
        """
        Get EvidenceCard objects for all selected evidence card IDs.
        
        Returns:
            List of EvidenceCard objects that match selected_evidence_ids
        """
        card_dict = {card.id: card for card in self.evidence_cards}
        return [card_dict[card_id] for card_id in self.selected_evidence_ids if card_id in card_dict]

    def validate_state(self) -> tuple[bool, list[str]]:
        """
        Validate that the blackboard is in a valid state for the current step.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # State validation based on current_step
        if self.current_step in ("evidence_mapping", "writing", "auditing"):
            if not self.role_profile:
                errors.append("role_profile required for evidence_mapping step")
            if not self.requirements:
                errors.append("requirements required for evidence_mapping step")
        
        if self.current_step in ("writing", "auditing"):
            if not self.evidence_map:
                errors.append("evidence_map required for writing step")
            if not self.selected_evidence_ids:
                errors.append("selected_evidence_ids required for writing step")
        
        if self.current_step == "auditing":
            if not self.resume_draft:
                errors.append("resume_draft required for auditing step")
            if not self.claim_index:
                errors.append("claim_index required for auditing step")
        
        # Validate claim_index references
        if self.claim_index:
            available_ids = {card.id for card in self.evidence_cards}
            for claim in self.claim_index:
                if not claim.validate_against_cards(available_ids):
                    errors.append(
                        f"Claim {claim.bullet_id} references non-existent evidence cards: "
                        f"{set(claim.evidence_card_ids) - available_ids}"
                    )
        
        # Validate selected_evidence_ids exist
        if self.selected_evidence_ids:
            available_ids = {card.id for card in self.evidence_cards}
            missing = set(self.selected_evidence_ids) - available_ids
            if missing:
                errors.append(f"selected_evidence_ids references non-existent cards: {missing}")
        
        return len(errors) == 0, errors

    def get_evidence_card_by_id(self, card_id: str) -> EvidenceCard | None:
        """
        Get an evidence card by its ID.
        
        Args:
            card_id: The evidence card ID
            
        Returns:
            EvidenceCard if found, None otherwise
        """
        for card in self.evidence_cards:
            if card.id == card_id:
                return card
        return None
