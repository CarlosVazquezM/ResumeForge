"""
Integration tests for agent implementations.

These tests make real API calls to LLM providers and require valid API keys.
They are excluded from the default test run. To run them:

    # Run only integration tests
    pytest -m integration
    
    # Run all tests including integration (requires API keys)
    pytest -m ""
"""

import os
import pytest

from resumeforge.agents.auditor import AuditorAgent
from resumeforge.agents.evidence_mapper import EvidenceMapperAgent
from resumeforge.agents.jd_analyst import JDAnalystAgent
from resumeforge.agents.resume_writer import ResumeWriterAgent
from resumeforge.providers import create_provider_from_alias
from resumeforge.schemas.blackboard import (
    Blackboard,
    ClaimMapping,
    GapResolution,
    GapStrategy,
    Priority,
    Requirement,
    ResumeDraft,
    ResumeSection,
    RoleProfile,
)
from resumeforge.config import load_config
from tests.fixtures import (
    create_sample_blackboard,
    load_sample_evidence_cards,
    load_sample_jd,
)


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestJDAnalystAgentIntegration:
    """Integration tests for JDAnalystAgent (requires ANTHROPIC_API_KEY)."""
    
    @pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="Requires ANTHROPIC_API_KEY environment variable"
    )
    def test_jd_analyst_real_api(self):
        """Test JD Analyst with real provider (small JD)."""
        config = load_config("config.yaml")
        provider = create_provider_from_alias("jd_analyst_default", config)
        agent_config = config["agents"]["jd_analyst"]
        
        agent = JDAnalystAgent(provider, agent_config)
        
        # Use minimal JD for cost efficiency
        minimal_jd = """Senior Engineering Manager

Required: 5+ years management experience, cloud infrastructure (AWS/Azure).
Preferred: Microservices architecture, CI/CD experience.

Lead team of 15-20 engineers. Report to Director."""
        
        blackboard = create_sample_blackboard(
            job_description=minimal_jd,
            target_title="Senior Engineering Manager"
        )
        
        result = agent.execute(blackboard)
        
        assert result.role_profile is not None
        assert result.role_profile.inferred_level is not None
        assert len(result.requirements) > 0
        assert result.current_step == "jd_analysis_complete"


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestEvidenceMapperAgentIntegration:
    """Integration tests for EvidenceMapperAgent (requires ANTHROPIC_API_KEY)."""
    
    @pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="Requires ANTHROPIC_API_KEY environment variable"
    )
    def test_evidence_mapper_real_api(self):
        """Test Evidence Mapper with real provider (minimal cards)."""
        config = load_config("config.yaml")
        provider = create_provider_from_alias("mapper_precise", config)
        agent_config = config["agents"]["evidence_mapper"]
        
        agent = EvidenceMapperAgent(provider, agent_config)
        
        # Create blackboard with prerequisites
        blackboard = create_sample_blackboard()
        evidence_cards = load_sample_evidence_cards()
        blackboard.evidence_cards = evidence_cards
        
        # Add minimal role_profile and requirements
        blackboard.role_profile = RoleProfile(
            inferred_level="Senior Manager",
            must_haves=["Management experience", "Cloud infrastructure"],
            nice_to_haves=[],
            seniority_signals=[],
            keyword_clusters={"cloud": ["AWS", "Azure"]},
            recommended_storylines=[],
            priority_sections=[],
            downplay_sections=[]
        )
        
        blackboard.requirements = [
            Requirement(
                id="req-001",
                text="5+ years engineering management",
                priority=Priority.HIGH,
                keywords=["management"]
            ),
            Requirement(
                id="req-002",
                text="Cloud infrastructure experience",
                priority=Priority.MEDIUM,
                keywords=["cloud", "AWS"]
            )
        ]
        
        result = agent.execute(blackboard)
        
        assert result.evidence_map is not None
        assert result.current_step == "evidence_mapping_complete"
        # Should have some mappings or gaps
        assert len(result.evidence_map) > 0 or len(result.gap_resolutions) > 0


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestResumeWriterAgentIntegration:
    """Integration tests for ResumeWriterAgent (requires OPENAI_API_KEY)."""
    
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY environment variable"
    )
    def test_resume_writer_real_api(self):
        """Test Resume Writer with real provider (2-3 evidence cards)."""
        config = load_config("config.yaml")
        provider = create_provider_from_alias("writer_default", config)
        agent_config = config["agents"]["writer"]
        
        agent = ResumeWriterAgent(provider, agent_config)
        
        # Create blackboard with prerequisites
        blackboard = create_sample_blackboard()
        evidence_cards = load_sample_evidence_cards()
        # Use only 2 cards to reduce token usage
        blackboard.evidence_cards = evidence_cards[:2]
        blackboard.selected_evidence_ids = [card.id for card in evidence_cards[:2]]
        
        blackboard.role_profile = RoleProfile(
            inferred_level="Senior Manager",
            must_haves=[],
            nice_to_haves=[],
            seniority_signals=[],
            keyword_clusters={},
            recommended_storylines=["Leadership"],
            priority_sections=["Experience"],
            downplay_sections=[]
        )
        
        blackboard.gap_resolutions = []
        
        result = agent.execute(blackboard)
        
        assert result.resume_draft is not None
        assert len(result.resume_draft.sections) > 0
        assert len(result.claim_index) > 0
        assert result.current_step == "writing_complete"
        
        # Verify all claims reference valid evidence cards
        available_ids = {card.id for card in blackboard.evidence_cards}
        for claim in result.claim_index:
            for card_id in claim.evidence_card_ids:
                assert card_id in available_ids


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestAuditorAgentIntegration:
    """Integration tests for AuditorAgent (requires GOOGLE_API_KEY and ANTHROPIC_API_KEY)."""
    
    @pytest.mark.skipif(
        not os.getenv("GOOGLE_API_KEY") or not os.getenv("ANTHROPIC_API_KEY"),
        reason="Requires GOOGLE_API_KEY and ANTHROPIC_API_KEY environment variables"
    )
    def test_auditor_real_api(self):
        """Test Auditor with real providers (minimal resume)."""
        config = load_config("config.yaml")
        ats_provider = create_provider_from_alias("ats_scorer_default", config)
        truth_provider = create_provider_from_alias("truth_auditor_default", config)
        agent_config = config["agents"]["ats_scorer"]  # Use ATS config for both
        
        agent = AuditorAgent(ats_provider, truth_provider, agent_config)
        
        # Create minimal blackboard with resume
        blackboard = create_sample_blackboard()
        evidence_cards = load_sample_evidence_cards()
        blackboard.evidence_cards = evidence_cards[:1]  # Use only 1 card
        
        blackboard.role_profile = RoleProfile(
            inferred_level="Senior Manager",
            must_haves=["Management"],
            nice_to_haves=[],
            seniority_signals=[],
            keyword_clusters={},
            recommended_storylines=[],
            priority_sections=[],
            downplay_sections=[]
        )
        
        # Minimal resume draft
        blackboard.resume_draft = ResumeDraft(
            sections=[
                ResumeSection(
                    name="Experience",
                    content="### Senior Manager | PayScale\n- Led 19 engineers"
                )
            ]
        )
        
        blackboard.claim_index = [
            ClaimMapping(
                bullet_id="exp-bullet-1",
                bullet_text="Led 19 engineers",
                evidence_card_ids=[evidence_cards[0].id]
            )
        ]
        
        result = agent.execute(blackboard)
        
        assert result.ats_report is not None
        assert result.audit_report is not None
        assert 0 <= result.ats_report.keyword_coverage_score <= 100
        assert result.current_step == "auditing_complete"
