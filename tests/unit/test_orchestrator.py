"""Unit tests for Pipeline Orchestrator."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from resumeforge.orchestrator import (
    PipelineOrchestrator,
    PipelineState,
    StateTransition,
    TRANSITIONS,
)
from resumeforge.exceptions import OrchestrationError
from resumeforge.schemas.blackboard import Blackboard, Inputs, LengthRules
from resumeforge.schemas.evidence_card import EvidenceCard
from tests.fixtures import create_sample_blackboard, load_sample_evidence_cards


class TestPipelineState:
    """Tests for PipelineState enum."""
    
    def test_pipeline_state_values(self):
        """Test that all expected states exist."""
        assert PipelineState.INIT
        assert PipelineState.PREPROCESSING
        assert PipelineState.JD_ANALYSIS
        assert PipelineState.EVIDENCE_MAPPING
        assert PipelineState.WRITING
        assert PipelineState.AUDITING
        assert PipelineState.REVISION
        assert PipelineState.COMPLETE
        assert PipelineState.FAILED


class TestStateTransitions:
    """Tests for state transition logic."""
    
    def test_transitions_defined(self):
        """Test that all expected transitions are defined."""
        assert len(TRANSITIONS) > 0
        
        # Check key transitions exist
        init_to_preprocessing = any(
            t.from_state == PipelineState.INIT and t.to_state == PipelineState.PREPROCESSING
            for t in TRANSITIONS
        )
        assert init_to_preprocessing
    
    def test_auditing_to_complete_condition(self):
        """Test that auditing->complete transition requires passed audit."""
        blackboard = create_sample_blackboard()
        
        # Find auditing->complete transition
        transition = next(
            (t for t in TRANSITIONS 
             if t.from_state == PipelineState.AUDITING and t.to_state == PipelineState.COMPLETE),
            None
        )
        assert transition is not None
        
        # Test condition: should require audit_report.passed == True
        from resumeforge.schemas.outputs import AuditReport, TruthViolation
        
        # Case 1: No audit report (should not transition)
        blackboard.audit_report = None
        assert not transition.condition(blackboard)
        
        # Case 2: Audit passed (should transition)
        blackboard.audit_report = AuditReport(passed=True, truth_violations=[])
        assert transition.condition(blackboard)
        
        # Case 3: Audit failed (should not transition)
        blackboard.audit_report = AuditReport(
            passed=False,
            truth_violations=[TruthViolation(bullet_id="test", violation="test")]
        )
        assert not transition.condition(blackboard)
    
    def test_auditing_to_revision_condition(self):
        """Test that auditing->revision transition requires failed audit and retries available."""
        blackboard = create_sample_blackboard()
        
        # Find auditing->revision transition
        transition = next(
            (t for t in TRANSITIONS 
             if t.from_state == PipelineState.AUDITING and t.to_state == PipelineState.REVISION),
            None
        )
        assert transition is not None
        
        from resumeforge.schemas.outputs import AuditReport, TruthViolation
        
        # Case 1: Audit passed (should not transition)
        blackboard.audit_report = AuditReport(passed=True, truth_violations=[])
        assert not transition.condition(blackboard)
        
        # Case 2: Audit failed, retries available (should transition)
        blackboard.audit_report = AuditReport(
            passed=False,
            truth_violations=[TruthViolation(bullet_id="test", violation="test")]
        )
        blackboard.retry_count = 0
        blackboard.max_retries = 3
        assert transition.condition(blackboard)
        
        # Case 3: Audit failed, no retries left (should not transition)
        blackboard.retry_count = 3
        blackboard.max_retries = 3
        assert not transition.condition(blackboard)
    
    def test_auditing_to_failed_condition(self):
        """Test that auditing->failed transition requires failed audit and no retries."""
        blackboard = create_sample_blackboard()
        
        # Find auditing->failed transition
        transition = next(
            (t for t in TRANSITIONS 
             if t.from_state == PipelineState.AUDITING and t.to_state == PipelineState.FAILED),
            None
        )
        assert transition is not None
        
        from resumeforge.schemas.outputs import AuditReport, TruthViolation
        
        # Case 1: Audit passed (should not transition)
        blackboard.audit_report = AuditReport(passed=True, truth_violations=[])
        assert not transition.condition(blackboard)
        
        # Case 2: Audit failed, retries available (should not transition)
        blackboard.audit_report = AuditReport(
            passed=False,
            truth_violations=[TruthViolation(bullet_id="test", violation="test")]
        )
        blackboard.retry_count = 0
        blackboard.max_retries = 3
        assert not transition.condition(blackboard)
        
        # Case 3: Audit failed, no retries left (should transition)
        blackboard.retry_count = 3
        blackboard.max_retries = 3
        assert transition.condition(blackboard)


class TestPipelineOrchestrator:
    """Tests for PipelineOrchestrator class."""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator can be initialized."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        agents = {}
        
        orchestrator = PipelineOrchestrator(mock_config, agents)
        assert orchestrator.config == mock_config
        assert orchestrator.agents == agents
    
    def test_get_next_state_init_to_preprocessing(self):
        """Test state transition from INIT to PREPROCESSING."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        orchestrator = PipelineOrchestrator(mock_config, {})
        
        blackboard = create_sample_blackboard()
        next_state = orchestrator._get_next_state(PipelineState.INIT, blackboard)
        
        assert next_state == PipelineState.PREPROCESSING
    
    def test_get_next_state_no_valid_transition(self):
        """Test that None is returned when no valid transition exists."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        orchestrator = PipelineOrchestrator(mock_config, {})
        
        blackboard = create_sample_blackboard()
        # COMPLETE state has no outgoing transitions
        next_state = orchestrator._get_next_state(PipelineState.COMPLETE, blackboard)
        
        assert next_state is None
    
    @patch("resumeforge.orchestrator.Path")
    def test_preprocess_loads_evidence_cards(self, mock_path_class):
        """Test that preprocessing loads evidence cards from file."""
        mock_config = MagicMock()
        mock_config.paths = {"evidence_cards": "./data/evidence_cards.json"}
        mock_config.pipeline = {}
        
        # Mock Path and file reading
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_class.return_value = mock_path
        
        evidence_cards = load_sample_evidence_cards()
        with patch("builtins.open", mock_open(read_data=json.dumps([card.model_dump() for card in evidence_cards]))):
            orchestrator = PipelineOrchestrator(mock_config, {})
            blackboard = create_sample_blackboard()
            blackboard.evidence_cards = []  # Start empty
            
            result = orchestrator._preprocess(blackboard)
            
            assert len(result.evidence_cards) > 0
    
    @patch("resumeforge.orchestrator.Path")
    def test_preprocess_missing_evidence_file(self, mock_path_class):
        """Test that preprocessing raises error if evidence cards file is missing."""
        mock_config = MagicMock()
        mock_config.paths = {"evidence_cards": "./data/evidence_cards.json"}
        mock_config.pipeline = {}
        
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path
        
        orchestrator = PipelineOrchestrator(mock_config, {})
        blackboard = create_sample_blackboard()
        
        with pytest.raises(OrchestrationError) as exc_info:
            orchestrator._preprocess(blackboard)
        
        assert "evidence cards" in str(exc_info.value).lower()
    
    def test_preprocess_sets_max_retries_from_config(self):
        """Test that preprocessing sets max_retries from config."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {"max_retries": 5}
        
        orchestrator = PipelineOrchestrator(mock_config, {})
        blackboard = create_sample_blackboard()
        blackboard.max_retries = 0  # Start with default
        
        result = orchestrator._preprocess(blackboard)
        
        assert result.max_retries == 5
    
    def test_preprocess_invalid_max_retries(self):
        """Test that preprocessing raises error for invalid max_retries."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {"max_retries": -1}  # Invalid
        
        orchestrator = PipelineOrchestrator(mock_config, {})
        blackboard = create_sample_blackboard()
        
        with pytest.raises(OrchestrationError) as exc_info:
            orchestrator._preprocess(blackboard)
        
        assert "max_retries" in str(exc_info.value).lower()
    
    def test_execute_state_jd_analysis(self):
        """Test executing JD_ANALYSIS state."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        mock_agent = MagicMock()
        mock_agent.execute.return_value = create_sample_blackboard()
        
        agents = {"jd_analyst": mock_agent}
        orchestrator = PipelineOrchestrator(mock_config, agents)
        blackboard = create_sample_blackboard()
        
        result = orchestrator._execute_state(PipelineState.JD_ANALYSIS, blackboard)
        
        mock_agent.execute.assert_called_once_with(blackboard)
        assert result is not None
    
    def test_execute_state_missing_agent(self):
        """Test that executing state with missing agent raises error."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        orchestrator = PipelineOrchestrator(mock_config, {})  # No agents
        blackboard = create_sample_blackboard()
        
        with pytest.raises(OrchestrationError) as exc_info:
            orchestrator._execute_state(PipelineState.JD_ANALYSIS, blackboard)
        
        assert "agent not found" in str(exc_info.value).lower()
    
    def test_execute_state_evidence_mapping(self):
        """Test executing EVIDENCE_MAPPING state."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        mock_agent = MagicMock()
        mock_agent.execute.return_value = create_sample_blackboard()
        
        agents = {"evidence_mapper": mock_agent}
        orchestrator = PipelineOrchestrator(mock_config, agents)
        blackboard = create_sample_blackboard()
        
        result = orchestrator._execute_state(PipelineState.EVIDENCE_MAPPING, blackboard)
        
        mock_agent.execute.assert_called_once_with(blackboard)
        assert result is not None
    
    def test_execute_state_writing(self):
        """Test executing WRITING state."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        mock_agent = MagicMock()
        mock_agent.execute.return_value = create_sample_blackboard()
        
        agents = {"resume_writer": mock_agent}
        orchestrator = PipelineOrchestrator(mock_config, agents)
        blackboard = create_sample_blackboard()
        
        result = orchestrator._execute_state(PipelineState.WRITING, blackboard)
        
        mock_agent.execute.assert_called_once_with(blackboard)
        assert result is not None
    
    def test_execute_state_writing_fallback_to_writer_key(self):
        """Test that WRITING state can use 'writer' key as fallback."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        mock_agent = MagicMock()
        mock_agent.execute.return_value = create_sample_blackboard()
        
        agents = {"writer": mock_agent}  # Use 'writer' instead of 'resume_writer'
        orchestrator = PipelineOrchestrator(mock_config, agents)
        blackboard = create_sample_blackboard()
        
        result = orchestrator._execute_state(PipelineState.WRITING, blackboard)
        
        mock_agent.execute.assert_called_once_with(blackboard)
        assert result is not None
    
    def test_execute_state_auditing(self):
        """Test executing AUDITING state."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        mock_agent = MagicMock()
        mock_agent.execute.return_value = create_sample_blackboard()
        
        agents = {"auditor": mock_agent}
        orchestrator = PipelineOrchestrator(mock_config, agents)
        blackboard = create_sample_blackboard()
        
        result = orchestrator._execute_state(PipelineState.AUDITING, blackboard)
        
        mock_agent.execute.assert_called_once_with(blackboard)
        assert result is not None
    
    def test_execute_state_revision_increments_retry_count(self):
        """Test that REVISION state increments retry_count."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        orchestrator = PipelineOrchestrator(mock_config, {})
        blackboard = create_sample_blackboard()
        blackboard.retry_count = 0
        
        result = orchestrator._execute_state(PipelineState.REVISION, blackboard)
        
        assert result.retry_count == 1
    
    def test_execute_state_init_no_action(self):
        """Test that INIT state returns blackboard unchanged."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        orchestrator = PipelineOrchestrator(mock_config, {})
        blackboard = create_sample_blackboard()
        
        result = orchestrator._execute_state(PipelineState.INIT, blackboard)
        
        assert result == blackboard
    
    def test_run_pipeline_completes_successfully(self):
        """Test that run() completes pipeline successfully."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        # Create mock agents
        mock_jd_agent = MagicMock()
        mock_jd_agent.execute.return_value = create_sample_blackboard()
        
        mock_mapper_agent = MagicMock()
        mock_mapper_agent.execute.return_value = create_sample_blackboard()
        
        mock_writer_agent = MagicMock()
        mock_writer_agent.execute.return_value = create_sample_blackboard()
        
        from resumeforge.schemas.outputs import AuditReport
        mock_auditor_agent = MagicMock()
        audit_blackboard = create_sample_blackboard()
        audit_blackboard.audit_report = AuditReport(passed=True, truth_violations=[])
        mock_auditor_agent.execute.return_value = audit_blackboard
        
        agents = {
            "jd_analyst": mock_jd_agent,
            "evidence_mapper": mock_mapper_agent,
            "resume_writer": mock_writer_agent,
            "auditor": mock_auditor_agent,
        }
        
        orchestrator = PipelineOrchestrator(mock_config, agents)
        blackboard = create_sample_blackboard()
        blackboard.evidence_cards = load_sample_evidence_cards()  # Pre-load evidence
        
        # Mock _preprocess to skip file loading
        with patch.object(orchestrator, "_preprocess", return_value=blackboard):
            with patch.object(orchestrator, "_save_outputs"):
                result = orchestrator.run(blackboard)
                
                assert result.current_step == "complete"
                assert mock_jd_agent.execute.called
                assert mock_mapper_agent.execute.called
                assert mock_writer_agent.execute.called
                assert mock_auditor_agent.execute.called
    
    def test_run_pipeline_fails_on_validation_error(self):
        """Test that run() fails when blackboard validation fails."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        orchestrator = PipelineOrchestrator(mock_config, {})
        blackboard = create_sample_blackboard()
        blackboard.evidence_cards = load_sample_evidence_cards()
        
        # Mock _preprocess to return invalid blackboard
        invalid_blackboard = create_sample_blackboard()
        invalid_blackboard.current_step = "jd_analysis"
        # Make validation fail by removing required fields
        invalid_blackboard.inputs = None
        
        with patch.object(orchestrator, "_preprocess", return_value=invalid_blackboard):
            with pytest.raises(OrchestrationError):
                orchestrator.run(blackboard)
    
    def test_run_pipeline_fails_on_agent_error(self):
        """Test that run() fails when agent raises exception."""
        mock_config = MagicMock()
        mock_config.paths = {}
        mock_config.pipeline = {}
        
        mock_agent = MagicMock()
        mock_agent.execute.side_effect = Exception("Agent error")
        
        agents = {"jd_analyst": mock_agent}
        orchestrator = PipelineOrchestrator(mock_config, agents)
        blackboard = create_sample_blackboard()
        blackboard.evidence_cards = load_sample_evidence_cards()
        
        with patch.object(orchestrator, "_preprocess", return_value=blackboard):
            with pytest.raises(OrchestrationError):
                orchestrator.run(blackboard)
