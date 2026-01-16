"""Pydantic schemas for ResumeForge data models."""

import json
from pathlib import Path
from typing import Type

from pydantic import BaseModel

from resumeforge.schemas.evidence_card import EvidenceCard, MetricEntry, ScopeInfo
from resumeforge.schemas.blackboard import (
    Blackboard,
    ATSReport,
    AuditReport,
    ClaimMapping,
    Confidence,
    GapResolution,
    GapStrategy,
    Inputs,
    LengthRules,
    Priority,
    Requirement,
    ResumeDraft,
    ResumeSection,
    RoleProfile,
    TruthViolation,
    UserQuestion,
    EvidenceMapping,
)

__all__ = [
    # Evidence Card models
    "EvidenceCard",
    "MetricEntry",
    "ScopeInfo",
    # Blackboard and state models
    "Blackboard",
    "Inputs",
    "LengthRules",
    "RoleProfile",
    "Requirement",
    "EvidenceMapping",
    "GapResolution",
    "ResumeDraft",
    "ResumeSection",
    "ClaimMapping",
    "ATSReport",
    "AuditReport",
    "TruthViolation",
    "UserQuestion",
    # Enums
    "Priority",
    "Confidence",
    "GapStrategy",
    # Utility functions
    "export_json_schema",
]


def export_json_schema(model_class: Type[BaseModel], output_path: Path | str) -> None:
    """
    Export a Pydantic model's JSON schema to a file.
    
    Args:
        model_class: Pydantic model class to export
        output_path: Path where to save the JSON schema
        
    Example:
        >>> export_json_schema(Blackboard, Path("schemas/blackboard.schema.json"))
    """
    schema = model_class.model_json_schema()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(schema, f, indent=2)
