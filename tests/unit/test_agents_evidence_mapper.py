"""Unit tests for Evidence Mapper Agent."""

import json
import pytest
from unittest.mock import MagicMock

from resumeforge.agents.evidence_mapper import EvidenceMapperAgent
from resumeforge.exceptions import ValidationError
from resumeforge.schemas.blackboard import (
    Blackboard,
    Confidence,
    GapStrategy,
    Priority,
    Requirement,
    RoleProfile,
)
from tests.fixtures import create_mock_provider, create_sample_blackboard, load_sample_evidence_cards


class TestEvidenceMapperAgent:
    """Tests for EvidenceMapperAgent."""
    
    def _create_blackboard_with_prerequisites(self):
        """Create blackboard with role_profile and requirements."""
        blackboard = create_sample_blackboard()
        
        # Add role_profile
        blackboard.role_profile = RoleProfile(
            inferred_level="Senior Manager",
            must_haves=["Management experience"],
            nice_to_haves=["Cloud experience"],
            seniority_signals=[],
            keyword_clusters={"cloud": ["AWS", "Azure"]},
            recommended_storylines=[],
            priority_sections=[],
            downplay_sections=[]
        )
        
        # Add requirements
        blackboard.requirements = [
            Requirement(
                id="req-001",
                text="5+ years engineering management",
                priority=Priority.HIGH,
                keywords=["management", "engineering"]
            ),
            Requirement(
                id="req-002",
                text="Cloud infrastructure experience",
                priority=Priority.MEDIUM,
                keywords=["cloud", "AWS"]
            )
        ]
        
        return blackboard
    
    def test_get_system_prompt(self):
        """Verify no-fabrication guardrails in prompt."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        
        prompt = agent.get_system_prompt()
        
        assert "NO FABRICATION" in prompt
        assert "CITE BY ID" in prompt
        assert "ACKNOWLEDGE GAPS" in prompt
        assert "evidence_card_id" in prompt.lower()
    
    def test_build_user_prompt(self):
        """Test prompt with requirements, evidence cards, synonyms."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        
        blackboard = self._create_blackboard_with_prerequisites()
        blackboard.synonyms_map = {"AWS": ["Amazon Web Services", "aws"]}
        
        prompt = agent.build_user_prompt(blackboard)
        
        assert "req-001" in prompt
        assert "req-002" in prompt
        assert "test-payscale-leadership" in prompt  # From sample evidence cards
        assert "synonyms" in prompt.lower()
    
    def test_build_user_prompt_missing_prerequisites(self):
        """Test ValidationError on missing prerequisites."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        
        # Missing role_profile
        blackboard = create_sample_blackboard()
        with pytest.raises(ValidationError) as exc_info:
            agent.build_user_prompt(blackboard)
        assert "role_profile" in str(exc_info.value).lower()
        assert "Evidence Mapper" in str(exc_info.value)
        
        # Missing requirements
        blackboard.role_profile = RoleProfile(inferred_level="Manager")
        with pytest.raises(ValidationError) as exc_info:
            agent.build_user_prompt(blackboard)
        assert "requirements" in str(exc_info.value).lower()
        assert "Evidence Mapper" in str(exc_info.value)
        
        # Missing evidence_cards
        blackboard.requirements = [Requirement(id="req-001", text="test", priority=Priority.MEDIUM)]
        blackboard.evidence_cards = []
        with pytest.raises(ValidationError) as exc_info:
            agent.build_user_prompt(blackboard)
        assert "evidence_cards" in str(exc_info.value).lower()
        assert "Evidence Mapper" in str(exc_info.value)
    
    def test_parse_response_valid_mapping(self):
        """Test parsing valid evidence_map."""
        response_data = {
            "evidence_map": [
                {
                    "requirement_id": "req-001",
                    "evidence_card_ids": ["test-payscale-leadership"],
                    "confidence": "high",
                    "notes": "Direct match for management experience"
                }
            ],
            "gaps": [],
            "supported_keywords": ["management"],
            "selected_evidence_ids": ["test-payscale-leadership"]
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert len(result.evidence_map) == 1
        assert result.evidence_map[0].requirement_id == "req-001"
        assert result.evidence_map[0].confidence == Confidence.HIGH
        assert result.evidence_map[0].evidence_card_ids == ["test-payscale-leadership"]
        assert result.selected_evidence_ids == ["test-payscale-leadership"]
        assert result.current_step == "evidence_mapping_complete"
    
    def test_parse_response_invalid_card_ids(self):
        """Test filtering invalid evidence_card_ids with warnings."""
        response_data = {
            "evidence_map": [
                {
                    "requirement_id": "req-001",
                    "evidence_card_ids": ["test-payscale-leadership", "non-existent-card"],
                    "confidence": "high",
                    "notes": "Test"
                }
            ],
            "gaps": [],
            "supported_keywords": [],
            "selected_evidence_ids": ["test-payscale-leadership", "non-existent-card"]
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        # Should filter out non-existent card
        assert len(result.evidence_map) == 1
        assert result.evidence_map[0].evidence_card_ids == ["test-payscale-leadership"]
        assert "non-existent-card" not in result.selected_evidence_ids
    
    def test_parse_response_invalid_requirement_ids(self):
        """Test warning on unknown requirement_ids."""
        response_data = {
            "evidence_map": [
                {
                    "requirement_id": "req-999",  # Doesn't exist
                    "evidence_card_ids": ["test-payscale-leadership"],
                    "confidence": "high",
                    "notes": "Test"
                }
            ],
            "gaps": [],
            "supported_keywords": [],
            "selected_evidence_ids": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        # Should skip unknown requirement
        assert len(result.evidence_map) == 0
    
    def test_parse_response_confidence_enum_conversion(self):
        """Test confidence string to enum."""
        response_data = {
            "evidence_map": [
                {
                    "requirement_id": "req-001",
                    "evidence_card_ids": ["test-payscale-leadership"],
                    "confidence": "high",
                    "notes": "Test"
                },
                {
                    "requirement_id": "req-002",
                    "evidence_card_ids": ["test-payscale-cloud-migration"],
                    "confidence": "low",
                    "notes": "Test"
                },
                {
                    "requirement_id": "req-001",
                    "evidence_card_ids": ["test-payscale-quality-improvement"],
                    "confidence": "medium",
                    "notes": "Test"
                }
            ],
            "gaps": [],
            "supported_keywords": [],
            "selected_evidence_ids": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert result.evidence_map[0].confidence == Confidence.HIGH
        assert result.evidence_map[1].confidence == Confidence.LOW
        assert result.evidence_map[2].confidence == Confidence.MEDIUM
    
    def test_parse_response_gap_resolution(self):
        """Test gap resolution parsing."""
        response_data = {
            "evidence_map": [],
            "gaps": [
                {
                    "gap_id": "gap-001",
                    "requirement_text": "Kubernetes experience",
                    "gap_type": "true_gap",
                    "suggested_strategy": "omit",
                    "adjacent_evidence_ids": []
                },
                {
                    "gap_id": "gap-002",
                    "requirement_text": "Docker experience",
                    "gap_type": "terminology_gap",
                    "suggested_strategy": "adjacent_experience",
                    "adjacent_evidence_ids": ["test-payscale-cloud-migration"]
                }
            ],
            "supported_keywords": [],
            "selected_evidence_ids": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert len(result.gap_resolutions) == 2
        assert result.gap_resolutions[0].gap_id == "gap-001"
        assert result.gap_resolutions[0].strategy == GapStrategy.OMIT
        assert result.gap_resolutions[1].strategy == GapStrategy.ADJACENT
        assert result.gap_resolutions[1].adjacent_evidence_ids == ["test-payscale-cloud-migration"]
    
    def test_parse_response_gap_strategy_enum(self):
        """Test gap strategy string to enum conversion."""
        response_data = {
            "evidence_map": [],
            "gaps": [
                {
                    "gap_id": "gap-001",
                    "requirement_text": "Test",
                    "gap_type": "true_gap",
                    "suggested_strategy": "omit",
                    "adjacent_evidence_ids": []
                },
                {
                    "gap_id": "gap-002",
                    "requirement_text": "Test",
                    "gap_type": "true_gap",
                    "suggested_strategy": "adjacent_experience",
                    "adjacent_evidence_ids": []
                },
                {
                    "gap_id": "gap-003",
                    "requirement_text": "Test",
                    "gap_type": "true_gap",
                    "suggested_strategy": "ask_user",
                    "adjacent_evidence_ids": []
                }
            ],
            "supported_keywords": [],
            "selected_evidence_ids": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert result.gap_resolutions[0].strategy == GapStrategy.OMIT
        assert result.gap_resolutions[1].strategy == GapStrategy.ADJACENT
        assert result.gap_resolutions[2].strategy == GapStrategy.ASK_USER
    
    def test_no_fabrication_guardrail(self):
        """Test that invalid card IDs are filtered, not invented."""
        response_data = {
            "evidence_map": [
                {
                    "requirement_id": "req-001",
                    "evidence_card_ids": ["fabricated-card-id"],  # Doesn't exist
                    "confidence": "high",
                    "notes": "Test"
                }
            ],
            "gaps": [],
            "supported_keywords": [],
            "selected_evidence_ids": ["fabricated-card-id"]
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        result = agent.parse_response(response_json, blackboard)
        
        # Should filter out fabricated card ID
        assert len(result.evidence_map) == 0  # Mapping skipped due to no valid cards
        assert "fabricated-card-id" not in result.selected_evidence_ids
    
    def test_parse_response_missing_keys(self):
        """Test ValidationError on missing required keys."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.1, "max_tokens": 4096}
        agent = EvidenceMapperAgent(mock_provider, config)
        blackboard = self._create_blackboard_with_prerequisites()
        
        # Missing evidence_map
        response_data = {"gaps": [], "selected_evidence_ids": []}
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_response(json.dumps(response_data), blackboard)
        assert "missing 'evidence_map' key" in str(exc_info.value)
        
        # Missing gaps
        response_data = {"evidence_map": [], "selected_evidence_ids": []}
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_response(json.dumps(response_data), blackboard)
        assert "missing 'gaps' key" in str(exc_info.value)
        
        # Missing selected_evidence_ids
        response_data = {"evidence_map": [], "gaps": []}
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_response(json.dumps(response_data), blackboard)
        assert "missing 'selected_evidence_ids' key" in str(exc_info.value)
