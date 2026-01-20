"""Unit tests for JD Analyst Agent."""

import json
import pytest
from unittest.mock import MagicMock

from resumeforge.agents.jd_analyst import JDAnalystAgent
from resumeforge.exceptions import ValidationError
from resumeforge.schemas.blackboard import Blackboard, Inputs, LengthRules, Priority
from tests.fixtures import create_mock_provider, create_sample_blackboard


class TestJDAnalystAgent:
    """Tests for JDAnalystAgent."""
    
    def test_get_system_prompt(self):
        """Verify system prompt matches SDD."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        
        prompt = agent.get_system_prompt()
        
        assert "expert technical recruiter" in prompt.lower()
        assert "inferred_level" in prompt
        assert "must_haves" in prompt
        assert "nice_to_haves" in prompt
        assert "keyword_clusters" in prompt
    
    def test_build_user_prompt(self):
        """Test prompt building with blackboard inputs."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        
        blackboard = create_sample_blackboard(
            job_description="Test JD: Need 5+ years experience",
            target_title="Senior Manager"
        )
        
        prompt = agent.build_user_prompt(blackboard)
        
        assert "Test JD: Need 5+ years experience" in prompt
        assert "Senior Manager" in prompt
        assert "role_profile" in prompt
        assert "requirements" in prompt
    
    def test_build_user_prompt_missing_inputs(self):
        """Test that prompt building works with valid blackboard."""
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        
        # Blackboard should always have inputs from create_sample_blackboard
        blackboard = create_sample_blackboard()
        prompt = agent.build_user_prompt(blackboard)
        assert len(prompt) > 0
    
    def test_parse_response_valid(self):
        """Test parsing valid JSON response."""
        response_data = {
            "role_profile": {
                "inferred_level": "Senior Manager",
                "must_haves": ["5+ years management", "Cloud experience"],
                "nice_to_haves": ["AWS certification"],
                "seniority_signals": ["lead teams", "strategic decisions"],
                "keyword_clusters": {"cloud": ["AWS", "Azure"]},
                "recommended_storylines": ["Leadership", "Cloud expertise"],
                "priority_sections": ["Experience"],
                "downplay_sections": []
            },
            "requirements": [
                {
                    "id": "req-001",
                    "text": "5+ years engineering management",
                    "priority": "high",
                    "keywords": ["management", "engineering"]
                },
                {
                    "id": "req-002",
                    "text": "Cloud infrastructure experience",
                    "priority": "medium",
                    "keywords": ["cloud", "AWS"]
                }
            ]
        }
        
        response_json = json.dumps(response_data)
        mock_provider = create_mock_provider(response=response_json)
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert result.role_profile is not None
        assert result.role_profile.inferred_level == "Senior Manager"
        assert len(result.requirements) == 2
        assert result.requirements[0].id == "req-001"
        assert result.requirements[0].priority == Priority.HIGH
        assert result.current_step == "jd_analysis_complete"
    
    def test_parse_response_missing_role_profile(self):
        """Test ValidationError on missing role_profile."""
        response_data = {
            "requirements": [{"id": "req-001", "text": "test", "priority": "high"}]
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_response(response_json, blackboard)
        
        assert "missing 'role_profile' key" in str(exc_info.value)
    
    def test_parse_response_missing_requirements(self):
        """Test ValidationError on missing requirements."""
        response_data = {
            "role_profile": {
                "inferred_level": "Senior Manager",
                "must_haves": [],
                "nice_to_haves": [],
                "seniority_signals": [],
                "keyword_clusters": {},
                "recommended_storylines": [],
                "priority_sections": [],
                "downplay_sections": []
            }
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_response(response_json, blackboard)
        
        assert "missing 'requirements' key" in str(exc_info.value)
    
    def test_parse_response_invalid_role_profile(self):
        """Test ValidationError on invalid structure."""
        response_data = {
            "role_profile": {
                "invalid_field": "value"
            },
            "requirements": []
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_response(response_json, blackboard)
        
        assert "Invalid role_profile structure" in str(exc_info.value)
    
    def test_parse_response_priority_enum_conversion(self):
        """Test priority string to enum conversion."""
        response_data = {
            "role_profile": {
                "inferred_level": "Senior Manager",
                "must_haves": [],
                "nice_to_haves": [],
                "seniority_signals": [],
                "keyword_clusters": {},
                "recommended_storylines": [],
                "priority_sections": [],
                "downplay_sections": []
            },
            "requirements": [
                {"id": "req-001", "text": "High priority", "priority": "high", "keywords": []},
                {"id": "req-002", "text": "Low priority", "priority": "low", "keywords": []},
                {"id": "req-003", "text": "Medium priority", "priority": "medium", "keywords": []},
                {"id": "req-004", "text": "Default priority", "keywords": []}
            ]
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        result = agent.parse_response(response_json, blackboard)
        
        assert result.requirements[0].priority == Priority.HIGH
        assert result.requirements[1].priority == Priority.LOW
        assert result.requirements[2].priority == Priority.MEDIUM
        assert result.requirements[3].priority == Priority.MEDIUM  # Default
    
    def test_parse_response_graceful_degradation(self):
        """Test continues if one requirement fails."""
        response_data = {
            "role_profile": {
                "inferred_level": "Senior Manager",
                "must_haves": [],
                "nice_to_haves": [],
                "seniority_signals": [],
                "keyword_clusters": {},
                "recommended_storylines": [],
                "priority_sections": [],
                "downplay_sections": []
            },
            "requirements": [
                {"id": "req-001", "text": "Valid requirement", "priority": "high", "keywords": []},
                {"id": "req-002"},  # Missing required fields
                {"id": "req-003", "text": "Another valid", "priority": "medium", "keywords": []}
            ]
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        result = agent.parse_response(response_json, blackboard)
        
        # Should have 2 valid requirements (req-001 and req-003)
        assert len(result.requirements) == 2
        assert result.requirements[0].id == "req-001"
        assert result.requirements[1].id == "req-003"
    
    def test_parse_response_no_valid_requirements(self):
        """Test ValidationError if all requirements fail."""
        response_data = {
            "role_profile": {
                "inferred_level": "Senior Manager",
                "must_haves": [],
                "nice_to_haves": [],
                "seniority_signals": [],
                "keyword_clusters": {},
                "recommended_storylines": [],
                "priority_sections": [],
                "downplay_sections": []
            },
            "requirements": [
                {"id": "req-001"},  # Missing required fields
                {"id": "req-002"}   # Missing required fields
            ]
        }
        response_json = json.dumps(response_data)
        
        mock_provider = create_mock_provider()
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        with pytest.raises(ValidationError) as exc_info:
            agent.parse_response(response_json, blackboard)
        
        assert "No valid requirements found" in str(exc_info.value)
    
    def test_execute_full_flow(self):
        """Test complete execute flow."""
        response_data = {
            "role_profile": {
                "inferred_level": "Senior Manager",
                "must_haves": ["Management experience"],
                "nice_to_haves": [],
                "seniority_signals": [],
                "keyword_clusters": {},
                "recommended_storylines": [],
                "priority_sections": [],
                "downplay_sections": []
            },
            "requirements": [
                {"id": "req-001", "text": "Test requirement", "priority": "high", "keywords": []}
            ]
        }
        response_json = json.dumps(response_data)
        mock_provider = create_mock_provider(response=response_json)
        config = {"temperature": 0.3, "max_tokens": 4096}
        agent = JDAnalystAgent(mock_provider, config)
        blackboard = create_sample_blackboard()
        
        result = agent.execute(blackboard)
        
        assert result.role_profile is not None
        assert len(result.requirements) == 1
        assert result.current_step == "jd_analysis_complete"
