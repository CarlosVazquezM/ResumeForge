"""Unit tests for Auditor Agent."""

import json
import pytest
from unittest.mock import MagicMock

from resumeforge.agents.auditor import AuditorAgent
from resumeforge.exceptions import ValidationError
from resumeforge.schemas.blackboard import (
    ATSReport,
    AuditReport,
    Blackboard,
    ClaimMapping,
    ResumeDraft,
    ResumeSection,
    RoleProfile,
    TruthViolation,
)
from tests.fixtures import create_mock_provider, create_sample_blackboard, load_sample_evidence_cards


class TestAuditorAgent:
    """Tests for AuditorAgent."""
    
    def _create_blackboard_with_resume(self):
        """Create blackboard with resume draft and claim index."""
        blackboard = create_sample_blackboard()
        
        # Add role_profile
        blackboard.role_profile = RoleProfile(
            inferred_level="Senior Manager",
            must_haves=["Management experience"],
            nice_to_haves=[],
            seniority_signals=[],
            keyword_clusters={"cloud": ["AWS", "Azure"]},
            recommended_storylines=[],
            priority_sections=[],
            downplay_sections=[]
        )
        
        # Add resume draft
        blackboard.resume_draft = ResumeDraft(
            sections=[
                ResumeSection(
                    name="Experience",
                    content="### Senior Manager | PayScale\n- Led 19 engineers\n- Managed $3M budget"
                )
            ]
        )
        
        # Add claim index
        evidence_cards = load_sample_evidence_cards()
        blackboard.evidence_cards = evidence_cards
        blackboard.claim_index = [
            ClaimMapping(
                bullet_id="exp-bullet-1",
                bullet_text="Led 19 engineers",
                evidence_card_ids=["test-payscale-leadership"]
            )
        ]
        
        return blackboard
    
    def test_get_system_prompt(self):
        """Verify truth verification system prompt."""
        ats_provider = create_mock_provider(model="gemini-1.5-flash")
        truth_provider = create_mock_provider(model="claude-sonnet-4")
        config = {"temperature": 0.0, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        
        prompt = agent.get_system_prompt()
        
        assert "truth verification" in prompt.lower()
        assert "blocking check" in prompt.lower()
        assert "Unsupported Claims" in prompt
        assert "Metric Inconsistencies" in prompt
    
    def test_build_user_prompt(self):
        """Test truth auditing prompt with resume draft and claim_index."""
        ats_provider = create_mock_provider()
        truth_provider = create_mock_provider()
        config = {"temperature": 0.0, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        
        blackboard = self._create_blackboard_with_resume()
        
        prompt = agent.build_user_prompt(blackboard)
        
        assert "Experience" in prompt  # Resume section
        assert "exp-bullet-1" in prompt  # Claim ID
        assert "test-payscale-leadership" in prompt  # Evidence card ID
    
    def test_build_user_prompt_missing_prerequisites(self):
        """Test ValidationError on missing prerequisites."""
        ats_provider = create_mock_provider()
        truth_provider = create_mock_provider()
        config = {"temperature": 0.0, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        
        # Missing resume_draft
        blackboard = create_sample_blackboard()
        with pytest.raises(ValidationError) as exc_info:
            agent.build_user_prompt(blackboard)
        assert "resume_draft" in str(exc_info.value).lower()
        
        # Missing claim_index
        blackboard.resume_draft = ResumeDraft(sections=[])
        with pytest.raises(ValidationError) as exc_info:
            agent.build_user_prompt(blackboard)
        assert "claim_index" in str(exc_info.value).lower()
        
        # Missing evidence_cards (but claim_index is checked first)
        blackboard.claim_index = [ClaimMapping(
            bullet_id="test",
            bullet_text="test",
            evidence_card_ids=["test-card"]
        )]
        blackboard.evidence_cards = []
        with pytest.raises(ValidationError) as exc_info:
            agent.build_user_prompt(blackboard)
        assert "evidence_cards" in str(exc_info.value).lower()
    
    def test_execute_ats_scoring(self):
        """Test ATS scoring execution flow."""
        ats_response = {
            "keyword_coverage_score": 85.0,
            "supported_keywords": ["management", "cloud"],
            "missing_keywords": ["Kubernetes"],
            "format_warnings": [],
            "role_signal_score": 90.0
        }
        ats_provider = create_mock_provider(response=json.dumps(ats_response))
        truth_provider = create_mock_provider()
        config = {"temperature": 0.2, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        
        blackboard = self._create_blackboard_with_resume()
        
        result = agent.execute_ats_scoring(blackboard)
        
        assert result.ats_report is not None
        assert result.ats_report.keyword_coverage_score == 85.0
        assert result.ats_report.role_signal_score == 90.0
        assert "management" in result.ats_report.supported_keywords
        assert "Kubernetes" in result.ats_report.missing_keywords
    
    def test_execute_ats_scoring_missing_draft(self):
        """Test ValidationError on missing resume_draft."""
        ats_provider = create_mock_provider()
        truth_provider = create_mock_provider()
        config = {"temperature": 0.2, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        
        blackboard = create_sample_blackboard()
        
        with pytest.raises(ValidationError) as exc_info:
            agent.execute_ats_scoring(blackboard)
        assert "resume_draft" in str(exc_info.value).lower()
        assert "Auditor" in str(exc_info.value)
    
    def test_parse_response_truth_violations(self):
        """Test parsing truth violations."""
        response_data = {
            "truth_violations": [
                {
                    "bullet_id": "exp-bullet-1",
                    "bullet_text": "Led 20 engineers",
                    "violation": "Claims 20 engineers but evidence shows 19"
                }
            ],
            "inconsistencies": [],
            "ats_suggestions": [],
            "passed": False
        }
        response_json = json.dumps(response_data)
        
        ats_provider = create_mock_provider()
        truth_provider = create_mock_provider()
        config = {"temperature": 0.0, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        blackboard = self._create_blackboard_with_resume()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert result.audit_report is not None
        assert len(result.audit_report.truth_violations) == 1
        assert result.audit_report.truth_violations[0].bullet_id == "exp-bullet-1"
        assert result.audit_report.passed is False
        assert result.current_step == "auditing_complete"
    
    def test_parse_response_passed_false(self):
        """Test passed=false when violations found."""
        response_data = {
            "truth_violations": [
                {
                    "bullet_id": "exp-bullet-1",
                    "bullet_text": "Test",
                    "violation": "Unsupported claim"
                }
            ],
            "inconsistencies": [],
            "ats_suggestions": [],
            "passed": False
        }
        response_json = json.dumps(response_data)
        
        ats_provider = create_mock_provider()
        truth_provider = create_mock_provider()
        config = {"temperature": 0.0, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        blackboard = self._create_blackboard_with_resume()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert result.audit_report.passed is False
    
    def test_parse_response_passed_true(self):
        """Test passed=true when no violations."""
        response_data = {
            "truth_violations": [],
            "inconsistencies": [],
            "ats_suggestions": [],
            "passed": True
        }
        response_json = json.dumps(response_data)
        
        ats_provider = create_mock_provider()
        truth_provider = create_mock_provider()
        config = {"temperature": 0.0, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        blackboard = self._create_blackboard_with_resume()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert result.audit_report.passed is True
        assert len(result.audit_report.truth_violations) == 0
    
    def test_execute_dual_providers(self):
        """Test both ATS and Truth auditing execute."""
        # ATS response
        ats_response = {
            "keyword_coverage_score": 80.0,
            "supported_keywords": ["management"],
            "missing_keywords": [],
            "format_warnings": [],
            "role_signal_score": 85.0
        }
        ats_provider = create_mock_provider(response=json.dumps(ats_response))
        
        # Truth response
        truth_response = {
            "truth_violations": [],
            "inconsistencies": [],
            "ats_suggestions": [],
            "passed": True
        }
        truth_provider = create_mock_provider(response=json.dumps(truth_response))
        
        config = {"temperature": 0.0, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        blackboard = self._create_blackboard_with_resume()
        
        result = agent.execute(blackboard)
        
        # Both should be executed
        assert result.ats_report is not None
        assert result.audit_report is not None
        assert result.ats_report.keyword_coverage_score == 80.0
        assert result.audit_report.passed is True
    
    def test_ats_suggestions_merged(self):
        """Test ATS suggestions merged into audit_report."""
        # ATS response with missing keywords
        ats_response = {
            "keyword_coverage_score": 75.0,
            "supported_keywords": ["management"],
            "missing_keywords": ["Kubernetes", "Docker"],
            "format_warnings": ["Non-standard section name"],
            "role_signal_score": 80.0
        }
        ats_provider = create_mock_provider(response=json.dumps(ats_response))
        
        # Truth response
        truth_response = {
            "truth_violations": [],
            "inconsistencies": [],
            "ats_suggestions": [],
            "passed": True
        }
        truth_provider = create_mock_provider(response=json.dumps(truth_response))
        
        config = {"temperature": 0.0, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        blackboard = self._create_blackboard_with_resume()
        
        result = agent.execute(blackboard)
        
        # ATS suggestions should be merged
        assert len(result.audit_report.ats_suggestions) > 0
        # Should include keyword suggestion
        assert any("Kubernetes" in s for s in result.audit_report.ats_suggestions)
        # Should include format warning
        assert any("section name" in s.lower() for s in result.audit_report.ats_suggestions)
    
    def test_parse_response_missing_passed_key(self):
        """Test ValidationError on missing 'passed' key."""
        response_data = {
            "truth_violations": [],
            "inconsistencies": []
        }
        response_json = json.dumps(response_data)
        
        ats_provider = create_mock_provider()
        truth_provider = create_mock_provider()
        config = {"temperature": 0.0, "max_tokens": 2048}
        agent = AuditorAgent(ats_provider, truth_provider, config)
        blackboard = self._create_blackboard_with_resume()
        
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_response(response_json, blackboard)
        
        assert "missing 'passed' key" in str(exc_info.value)
