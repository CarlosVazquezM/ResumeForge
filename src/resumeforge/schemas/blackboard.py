"""Blackboard state schema definitions."""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum

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
    notes: Optional[str] = None


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
    evidence_card_ids: list[str]


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
    role_profile: Optional[RoleProfile] = None
    requirements: list[Requirement] = Field(default_factory=list)
    
    # Evidence Mapping outputs
    evidence_map: list[EvidenceMapping] = Field(default_factory=list)
    gap_resolutions: list[GapResolution] = Field(default_factory=list)
    selected_evidence_ids: list[str] = Field(default_factory=list)
    
    # Writer outputs
    resume_draft: Optional[ResumeDraft] = None
    claim_index: list[ClaimMapping] = Field(default_factory=list)
    change_log: list[str] = Field(default_factory=list)
    
    # Audit outputs
    ats_report: Optional[ATSReport] = None
    audit_report: Optional[AuditReport] = None
    
    # User interaction
    questions_for_user: list[UserQuestion] = Field(default_factory=list)
    
    # Pipeline state
    current_step: str = "init"
    retry_count: int = 0
    max_retries: int = 3
