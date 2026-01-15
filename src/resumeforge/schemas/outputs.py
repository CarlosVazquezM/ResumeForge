"""Output schema definitions."""

# Re-export commonly used schemas for convenience
from resumeforge.schemas.blackboard import (
    ATSReport,
    AuditReport,
    ResumeDraft,
    TruthViolation,
)

__all__ = [
    "ATSReport",
    "AuditReport",
    "ResumeDraft",
    "TruthViolation",
]
