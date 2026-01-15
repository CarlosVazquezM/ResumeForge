"""Evidence Card schema definitions."""

from pydantic import BaseModel, Field
from typing import Optional


class MetricEntry(BaseModel):
    """A single metric entry."""

    value: str = Field(..., description="Quantified value, e.g., '75%', '340K+'")
    description: str = Field(..., description="What the metric represents")
    context: Optional[str] = Field(None, description="Additional context")


class ScopeInfo(BaseModel):
    """Scope information for an evidence card."""

    team_size: Optional[int] = None
    direct_reports: Optional[int] = None
    geography: list[str] = Field(default_factory=list)
    budget: Optional[str] = None


class EvidenceCard(BaseModel):
    """An evidence card representing verifiable career information."""

    id: str = Field(..., description="Unique identifier, e.g., 'nostromo-etl-metrics'")
    project: str = Field(..., description="Project or initiative name")
    company: str
    timeframe: str = Field(..., description="YYYY-YYYY or YYYY-MM to YYYY-MM")
    role: str = Field(..., description="Job title during this work")
    scope: ScopeInfo = Field(default_factory=ScopeInfo)
    metrics: list[MetricEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    leadership_signals: list[str] = Field(default_factory=list)
    raw_text: str = Field(..., description="Original source paragraph")
