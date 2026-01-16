"""Unit tests for EvidenceCard schema."""

import pytest
from pydantic import ValidationError

from resumeforge.schemas.evidence_card import EvidenceCard, MetricEntry, ScopeInfo


class TestMetricEntry:
    """Tests for MetricEntry model."""

    def test_valid_metric_entry(self):
        """Test creating a valid MetricEntry."""
        metric = MetricEntry(
            value="75%",
            description="reduction in defects",
            context="over 6 months"
        )
        assert metric.value == "75%"
        assert metric.description == "reduction in defects"
        assert metric.context == "over 6 months"

    def test_metric_entry_without_context(self):
        """Test MetricEntry without optional context."""
        metric = MetricEntry(value="340K+", description="records processed")
        assert metric.context is None


class TestScopeInfo:
    """Tests for ScopeInfo model."""

    def test_valid_scope_info(self):
        """Test creating a valid ScopeInfo."""
        scope = ScopeInfo(
            team_size=19,
            direct_reports=19,
            geography=["US", "Romania"],
            budget="$2M"
        )
        assert scope.team_size == 19
        assert scope.direct_reports == 19
        assert scope.geography == ["US", "Romania"]
        assert scope.budget == "$2M"

    def test_empty_scope_info(self):
        """Test ScopeInfo with all optional fields None."""
        scope = ScopeInfo()
        assert scope.team_size is None
        assert scope.direct_reports is None
        assert scope.geography == []
        assert scope.budget is None


class TestEvidenceCard:
    """Tests for EvidenceCard model."""

    def test_valid_evidence_card_year_range(self):
        """Test EvidenceCard with year range timeframe."""
        card = EvidenceCard(
            id="test-card-1",
            project="Test Project",
            company="Test Co",
            timeframe="2020-2024",
            role="Engineer",
            raw_text="Worked on project"
        )
        assert card.timeframe == "2020-2024"

    def test_valid_evidence_card_month_range(self):
        """Test EvidenceCard with month range timeframe."""
        card = EvidenceCard(
            id="test-card-2",
            project="Test Project",
            company="Test Co",
            timeframe="2020-01 to 2024-12",
            role="Engineer",
            raw_text="Worked on project"
        )
        assert card.timeframe == "2020-01 to 2024-12"

    def test_invalid_timeframe_format(self):
        """Test that invalid timeframe format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EvidenceCard(
                id="test-card",
                project="Test",
                company="Test Co",
                timeframe="2020-01-2024-12",  # Invalid format
                role="Engineer",
                raw_text="Work"
            )
        assert "timeframe" in str(exc_info.value).lower()

    def test_get_metrics_summary(self):
        """Test get_metrics_summary helper method."""
        card = EvidenceCard(
            id="test-card",
            project="Test",
            company="Test Co",
            timeframe="2020-2024",
            role="Engineer",
            raw_text="Work",
            metrics=[
                MetricEntry(value="75%", description="improvement", context="Q1"),
                MetricEntry(value="340K+", description="records processed"),
            ]
        )
        summary = card.get_metrics_summary()
        assert "75% improvement (Q1)" in summary
        assert "340K+ records processed" in summary

    def test_get_metrics_summary_empty(self):
        """Test get_metrics_summary with no metrics."""
        card = EvidenceCard(
            id="test-card",
            project="Test",
            company="Test Co",
            timeframe="2020-2024",
            role="Engineer",
            raw_text="Work"
        )
        assert card.get_metrics_summary() == ""

    def test_get_skills_summary(self):
        """Test get_skills_summary helper method."""
        card = EvidenceCard(
            id="test-card",
            project="Test",
            company="Test Co",
            timeframe="2020-2024",
            role="Engineer",
            raw_text="Work",
            skills=["Python", "Docker", "Kubernetes"]
        )
        assert card.get_skills_summary() == "Python, Docker, Kubernetes"

    def test_evidence_card_with_all_fields(self):
        """Test EvidenceCard with all fields populated."""
        card = EvidenceCard(
            id="nostromo-etl-metrics",
            project="Nostromo HRIS Integration Platform",
            company="PayScale",
            timeframe="2020-2024",
            role="Senior Manager, Software Engineering",
            scope=ScopeInfo(
                team_size=19,
                direct_reports=19,
                geography=["US", "Romania"]
            ),
            metrics=[
                MetricEntry(
                    value="340K+",
                    description="employee records processed",
                    context="nightly"
                )
            ],
            skills=["ETL", "distributed systems"],
            leadership_signals=["cross-geo management"],
            raw_text="Led development..."
        )
        assert card.id == "nostromo-etl-metrics"
        assert len(card.metrics) == 1
        assert len(card.skills) == 2
        assert card.scope.team_size == 19
