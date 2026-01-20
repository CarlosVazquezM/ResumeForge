"""Unit tests for Resume Writer Agent."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from resumeforge.agents.resume_writer import ResumeWriterAgent
from resumeforge.exceptions import ValidationError
from resumeforge.schemas.blackboard import (
    Blackboard,
    GapResolution,
    GapStrategy,
    Priority,
    Requirement,
    RoleProfile,
)
from tests.fixtures import (
    create_mock_provider,
    create_sample_blackboard,
    load_sample_evidence_cards,
    load_sample_template,
)


class TestResumeWriterAgent:
    """Tests for ResumeWriterAgent."""
    
    def _create_blackboard_with_prerequisites(self):
        """Create blackboard with prerequisites for resume writing."""
        blackboard = create_sample_blackboard()
        
        # Add role_profile
        blackboard.role_profile = RoleProfile(
            inferred_level="Senior Manager",
            must_haves=["Management experience"],
            nice_to_haves=[],
            seniority_signals=[],
            keyword_clusters={},
            recommended_storylines=["Leadership", "Cloud expertise"],
            priority_sections=["Experience"],
            downplay_sections=[]
        )
        
        # Add selected evidence IDs
        evidence_cards = load_sample_evidence_cards()
        blackboard.evidence_cards = evidence_cards
        blackboard.selected_evidence_ids = [card.id for card in evidence_cards]
        
        # Add gap resolutions
        blackboard.gap_resolutions = [
            GapResolution(
                gap_id="gap-001",
                requirement_text="Kubernetes experience",
                strategy=GapStrategy.OMIT,
                adjacent_evidence_ids=[]
            )
        ]
        
        return blackboard
    
    def test_get_system_prompt(self):
        """Verify evidence-only and no-AI-voice rules."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        
        prompt = agent.get_system_prompt()
        
        assert "EVIDENCE-ONLY" in prompt
        assert "CITE EVERYTHING" in prompt
        assert "NO AI VOICE" in prompt
        assert "Leveraged" in prompt  # Should mention avoiding this
        assert "evidence_card_id" in prompt.lower()
    
    def test_build_user_prompt(self):
        """Test prompt with template, evidence cards, gap resolutions."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        
        blackboard = self._create_blackboard_with_prerequisites()
        
        prompt = agent.build_user_prompt(blackboard)
        
        assert "test-payscale-leadership" in prompt  # Evidence card ID
        assert "Leadership" in prompt  # Storyline
        assert "Experience" in prompt  # Priority section
        assert "Kubernetes" in prompt  # Gap resolution
    
    def test_build_user_prompt_missing_prerequisites(self):
        """Test ValidationError on missing prerequisites."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        
        # Missing role_profile
        blackboard = create_sample_blackboard()
        with pytest.raises(ValidationError) as exc_info:
            agent.build_user_prompt(blackboard)
        assert "role_profile" in str(exc_info.value).lower()
        assert "Resume Writer" in str(exc_info.value)
        
        # Missing selected_evidence_ids
        blackboard.role_profile = RoleProfile(inferred_level="Manager")
        with pytest.raises(ValidationError) as exc_info:
            agent.build_user_prompt(blackboard)
        assert "selected_evidence_ids" in str(exc_info.value).lower()
        assert "Resume Writer" in str(exc_info.value)
        
        # Missing evidence_cards
        blackboard.selected_evidence_ids = ["test-card"]
        blackboard.evidence_cards = []
        with pytest.raises(ValidationError) as exc_info:
            agent.build_user_prompt(blackboard)
        assert "evidence_cards" in str(exc_info.value).lower()
        assert "Resume Writer" in str(exc_info.value)
    
    def test_build_user_prompt_template_not_found(self):
        """Test fallback to default template structure."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        
        blackboard = self._create_blackboard_with_prerequisites()
        # Set template path to non-existent file
        blackboard.inputs.template_path = "/nonexistent/template.md"
        
        prompt = agent.build_user_prompt(blackboard)
        
        # Should include default template structure
        assert "Summary" in prompt
        assert "Experience" in prompt
        assert "Education" in prompt
    
    def test_parse_response_valid_draft(self):
        """Test parsing valid resume draft with sections."""
        response_data = {
            "sections": [
                {
                    "name": "Summary",
                    "content": "Experienced engineering manager with 5+ years leading teams."
                },
                {
                    "name": "Experience",
                    "content": "### Senior Manager | PayScale\n- Led 19 engineers\n- Managed $3M budget"
                }
            ],
            "claim_index": [
                {
                    "bullet_id": "experience-payscale-bullet-1",
                    "bullet_text": "Led 19 engineers",
                    "evidence_card_ids": ["test-payscale-leadership"]
                }
            ],
            "change_log": ["Added emphasis on leadership"]
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert result.resume_draft is not None
        assert len(result.resume_draft.sections) == 2
        assert result.resume_draft.sections[0].name == "Summary"
        assert len(result.claim_index) == 1
        assert result.claim_index[0].bullet_id == "experience-payscale-bullet-1"
        assert result.change_log == ["Added emphasis on leadership"]
        assert result.current_step == "writing_complete"
    
    def test_parse_response_claim_index(self):
        """Test claim_index parsing and validation."""
        response_data = {
            "sections": [
                {"name": "Experience", "content": "Test content"}
            ],
            "claim_index": [
                {
                    "bullet_id": "exp-bullet-1",
                    "bullet_text": "Led team of 19",
                    "evidence_card_ids": ["test-payscale-leadership"]
                },
                {
                    "bullet_id": "exp-bullet-2",
                    "bullet_text": "Migrated 30+ servers",
                    "evidence_card_ids": ["test-payscale-cloud-migration"]
                }
            ],
            "change_log": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert len(result.claim_index) == 2
        assert result.claim_index[0].evidence_card_ids == ["test-payscale-leadership"]
        assert result.claim_index[1].evidence_card_ids == ["test-payscale-cloud-migration"]
    
    def test_parse_response_invalid_card_ids_in_claims(self):
        """Test filtering invalid evidence_card_ids."""
        response_data = {
            "sections": [
                {"name": "Experience", "content": "Test"}
            ],
            "claim_index": [
                {
                    "bullet_id": "exp-bullet-1",
                    "bullet_text": "Test bullet",
                    "evidence_card_ids": ["test-payscale-leadership", "non-existent-card"]
                }
            ],
            "change_log": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        # Should filter out invalid card ID
        assert len(result.claim_index) == 1
        assert result.claim_index[0].evidence_card_ids == ["test-payscale-leadership"]
        assert "non-existent-card" not in result.claim_index[0].evidence_card_ids
    
    def test_parse_response_empty_claim_index(self):
        """Test ValidationError if no valid claims."""
        response_data = {
            "sections": [
                {"name": "Experience", "content": "Test"}
            ],
            "claim_index": [
                {
                    "bullet_id": "exp-bullet-1",
                    "bullet_text": "Test",
                    "evidence_card_ids": ["non-existent-card"]  # Invalid
                }
            ],
            "change_log": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_response(response_json, blackboard)
        
        assert "No valid claim mappings found" in str(exc_info.value)
    
    def test_parse_response_missing_sections(self):
        """Test ValidationError on missing sections."""
        response_data = {
            "claim_index": [],
            "change_log": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_response(response_json, blackboard)
        
        assert "missing 'sections' key" in str(exc_info.value)
    
    def test_claim_index_validation(self):
        """Test that every claim references valid evidence cards."""
        response_data = {
            "sections": [
                {"name": "Experience", "content": "Test"}
            ],
            "claim_index": [
                {
                    "bullet_id": "exp-bullet-1",
                    "bullet_text": "Valid claim",
                    "evidence_card_ids": ["test-payscale-leadership"]
                },
                {
                    "bullet_id": "exp-bullet-2",
                    "bullet_text": "Another valid claim",
                    "evidence_card_ids": ["test-payscale-cloud-migration", "test-payscale-quality-improvement"]
                }
            ],
            "change_log": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        # All claims should reference valid cards
        for claim in result.claim_index:
            for card_id in claim.evidence_card_ids:
                assert card_id in [card.id for card in blackboard.evidence_cards]
    
    def test_parse_response_empty_evidence_card_ids(self):
        """Test that claims with empty evidence_card_ids are skipped."""
        response_data = {
            "sections": [
                {"name": "Experience", "content": "Test"}
            ],
            "claim_index": [
                {
                    "bullet_id": "exp-bullet-1",
                    "bullet_text": "Valid claim",
                    "evidence_card_ids": ["test-payscale-leadership"]
                },
                {
                    "bullet_id": "exp-bullet-2",
                    "bullet_text": "Invalid claim",
                    "evidence_card_ids": []  # Empty
                }
            ],
            "change_log": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.4, "max_tokens": 4096}
        agent = ResumeWriterAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        # Should only have one valid claim
        assert len(result.claim_index) == 1
        assert result.claim_index[0].bullet_id == "exp-bullet-1"
