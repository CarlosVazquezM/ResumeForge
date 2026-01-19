"""Evidence Card schema definitions."""

import re

from pydantic import BaseModel, Field, field_validator


class MetricEntry(BaseModel):
    """A single metric entry."""

    value: str = Field(..., description="Quantified value, e.g., '75%', '340K+'")
    description: str = Field(..., description="What the metric represents")
    context: str | None = Field(None, description="Additional context")


class ScopeInfo(BaseModel):
    """Scope information for an evidence card."""

    team_size: int | None = None
    direct_reports: int | None = None
    geography: list[str] = Field(default_factory=list)
    budget: str | None = None
    
    @field_validator("geography", mode="before")
    @classmethod
    def normalize_geography(cls, v):
        """Convert None to empty list for geography."""
        if v is None:
            return []
        return v


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

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """
        Validate timeframe format: YYYY-YYYY or YYYY-MM to YYYY-MM.
        
        Examples:
        - "2020-2024" (valid)
        - "2020-01 to 2024-12" (valid)
        - "2020-01-2024-12" (invalid)
        """
        # Pattern for YYYY-YYYY
        pattern_year_range = r"^\d{4}-\d{4}$"
        # Pattern for YYYY-MM to YYYY-MM
        pattern_month_range = r"^\d{4}-\d{2} to \d{4}-\d{2}$"
        
        if re.match(pattern_year_range, v) or re.match(pattern_month_range, v):
            return v
        
        raise ValueError(
            f"Timeframe must be in format 'YYYY-YYYY' or 'YYYY-MM to YYYY-MM', got: {v}"
        )

    def get_metrics_summary(self) -> str:
        """
        Get a summary string of all metrics in this card.
        
        Returns:
            Formatted string with metrics, e.g., "340K+ employee records, 75% reduction"
        """
        if not self.metrics:
            return ""
        
        summaries = []
        for metric in self.metrics:
            summary = f"{metric.value} {metric.description}"
            if metric.context:
                summary += f" ({metric.context})"
            summaries.append(summary)
        
        return ", ".join(summaries)

    def get_skills_summary(self) -> str:
        """
        Get a comma-separated string of all skills.
        
        Returns:
            Skills joined with commas
        """
        return ", ".join(self.skills)

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "nostromo-etl-metrics",
                "project": "Nostromo HRIS Integration Platform",
                "company": "PayScale",
                "timeframe": "2020-2024",
                "role": "Senior Manager, Software Engineering",
                "scope": {
                    "team_size": 19,
                    "direct_reports": 19,
                    "geography": ["US", "Romania"],
                    "budget": None
                },
                "metrics": [
                    {"value": "340K+", "description": "employee records processed", "context": "nightly"},
                    {"value": "520+", "description": "client integrations"},
                    {"value": "75%", "description": "reduction in release defects"}
                ],
                "skills": ["ETL", "distributed systems", ".NET/C#", "microservices"],
                "leadership_signals": ["cross-geo management", "zero voluntary attrition"],
                "raw_text": "Led development of Nostromo platform processing 340K+ employee records nightly across 520+ client integrations, achieving 75% reduction in release defects."
            }
        }
    }
