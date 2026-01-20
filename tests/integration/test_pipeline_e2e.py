"""
End-to-end integration tests for the full ResumeForge pipeline.

These tests exercise the complete pipeline from job description to resume output.
Two test classes:
1. TestPipelineE2EMocked - Uses mocked providers (fast, no API costs)
2. TestPipelineE2EReal - Uses real API calls (requires API keys, slower, costs money)
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from resumeforge.orchestrator import PipelineOrchestrator
from resumeforge.agents import (
    AuditorAgent,
    EvidenceMapperAgent,
    JDAnalystAgent,
    ResumeWriterAgent,
)
from resumeforge.config import load_config
from resumeforge.schemas.blackboard import Blackboard, Inputs, LengthRules
from resumeforge.schemas.blackboard import (
    AuditReport,
    ATSReport,
    ClaimMapping,
    ResumeDraft,
    ResumeSection,
    TruthViolation,
)
from tests.fixtures import (
    create_sample_blackboard,
    load_sample_evidence_cards,
    load_sample_jd,
)
from tests.fixtures.output_verification import OutputVerifier


@pytest.mark.integration
class TestPipelineE2EMocked:
    """End-to-end pipeline tests with mocked providers (no API calls)."""
    
    def test_full_pipeline_success(self, tmp_path):
        """Test complete pipeline execution with mocked agents."""
        # Setup
        config = load_config("config.yaml")
        config.paths["outputs"] = str(tmp_path)
        config.paths["evidence_cards"] = str(tmp_path / "evidence_cards.json")
        
        # Create evidence cards file
        evidence_cards = load_sample_evidence_cards()
        evidence_path = Path(config.paths["evidence_cards"])
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with open(evidence_path, "w") as f:
            json.dump([card.model_dump() for card in evidence_cards], f)
        
        # Create mock agents
        mock_jd_agent = MagicMock(spec=JDAnalystAgent)
        mock_mapper_agent = MagicMock(spec=EvidenceMapperAgent)
        mock_writer_agent = MagicMock(spec=ResumeWriterAgent)
        mock_auditor_agent = MagicMock(spec=AuditorAgent)
        
        # Setup blackboard progression
        blackboard = create_sample_blackboard()
        blackboard.evidence_cards = evidence_cards
        
        # JD Analyst result
        jd_result = blackboard.model_copy(deep=True)
        from resumeforge.schemas.blackboard import RoleProfile, Requirement, Priority
        jd_result.role_profile = RoleProfile(
            inferred_level="Senior Manager"
        )
        jd_result.requirements = [
            Requirement(
                id="requirement-1",
                text="5+ years of engineering management experience",
                priority=Priority.HIGH
            )
        ]
        mock_jd_agent.execute.return_value = jd_result
        
        # Evidence Mapper result
        mapper_result = jd_result.model_copy(deep=True)
        mapper_result.selected_evidence_ids = [evidence_cards[0].id]
        mapper_result.evidence_map = {
            evidence_cards[0].id: ["requirement-1"]
        }
        mock_mapper_agent.execute.return_value = mapper_result
        
        # Resume Writer result
        writer_result = mapper_result.model_copy(deep=True)
        writer_result.resume_draft = ResumeDraft(
            sections=[
                ResumeSection(
                    name="Experience",
                    content="Led engineering team..."
                )
            ]
        )
        writer_result.claim_index = [
            ClaimMapping(
                bullet_id="bullet-1",
                bullet_text="Led engineering team...",
                evidence_card_ids=[evidence_cards[0].id]
            )
        ]
        mock_writer_agent.execute.return_value = writer_result
        
        # Auditor result (passing)
        auditor_result = writer_result.model_copy(deep=True)
        auditor_result.audit_report = AuditReport(
            passed=True,
            truth_violations=[]
        )
        auditor_result.ats_report = ATSReport(
            keyword_coverage_score=85.0,
            role_signal_score=90.0,
            missing_keywords=[],
            format_warnings=[]
        )
        mock_auditor_agent.execute.return_value = auditor_result
        
        agents = {
            "jd_analyst": mock_jd_agent,
            "evidence_mapper": mock_mapper_agent,
            "resume_writer": mock_writer_agent,
            "auditor": mock_auditor_agent,
        }
        
        orchestrator = PipelineOrchestrator(config, agents)
        
        # Run pipeline
        result = orchestrator.run(blackboard)
        
        # Assertions
        assert result.current_step == "complete"
        assert result.role_profile is not None
        assert result.selected_evidence_ids is not None
        assert result.resume_draft is not None
        assert result.audit_report is not None
        assert result.audit_report.passed is True
        assert result.ats_report is not None
        
        # Verify all agents were called
        mock_jd_agent.execute.assert_called_once()
        mock_mapper_agent.execute.assert_called_once()
        mock_writer_agent.execute.assert_called_once()
        mock_auditor_agent.execute.assert_called_once()
    
    @pytest.mark.output_verification
    def test_output_files_generated(self, tmp_path):
        """Test that all expected output files are created."""
        config = load_config("config.yaml")
        config.paths["outputs"] = str(tmp_path)
        config.paths["evidence_cards"] = str(tmp_path / "evidence_cards.json")
        
        # Create evidence cards file
        evidence_cards = load_sample_evidence_cards()
        evidence_path = Path(config.paths["evidence_cards"])
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with open(evidence_path, "w") as f:
            json.dump([card.model_dump() for card in evidence_cards], f)
        
        # Create mock agents (same setup as test_full_pipeline_success)
        mock_jd_agent = MagicMock(spec=JDAnalystAgent)
        mock_mapper_agent = MagicMock(spec=EvidenceMapperAgent)
        mock_writer_agent = MagicMock(spec=ResumeWriterAgent)
        mock_auditor_agent = MagicMock(spec=AuditorAgent)
        
        # Create a template file to test diff generation (before creating blackboard)
        template_file = tmp_path / "base_template.md"
        template_file.write_text("# Base Template\n\nOriginal content")
        
        # Create blackboard with template path
        blackboard = create_sample_blackboard()
        blackboard.evidence_cards = evidence_cards
        blackboard.inputs.template_path = str(template_file)
        
        # Setup mock responses (same as test_full_pipeline_success)
        jd_result = blackboard.model_copy(deep=True)
        from resumeforge.schemas.blackboard import RoleProfile, Requirement, Priority
        jd_result.role_profile = RoleProfile(
            inferred_level="Senior Manager"
        )
        jd_result.requirements = [
            Requirement(
                id="requirement-1",
                text="5+ years of engineering management experience",
                priority=Priority.HIGH
            )
        ]
        # Preserve template_path in copied results
        jd_result.inputs.template_path = str(template_file)
        mock_jd_agent.execute.return_value = jd_result
        
        mapper_result = jd_result.model_copy(deep=True)
        mapper_result.selected_evidence_ids = [evidence_cards[0].id]
        mapper_result.evidence_map = {
            evidence_cards[0].id: ["requirement-1"]
        }
        mapper_result.inputs.template_path = str(template_file)
        mock_mapper_agent.execute.return_value = mapper_result
        
        writer_result = mapper_result.model_copy(deep=True)
        writer_result.resume_draft = ResumeDraft(
            sections=[
                ResumeSection(
                    name="Experience",
                    content="Led engineering team..."
                )
            ]
        )
        writer_result.claim_index = [
            ClaimMapping(
                bullet_id="bullet-1",
                bullet_text="Led engineering team...",
                evidence_card_ids=[evidence_cards[0].id]
            )
        ]
        writer_result.inputs.template_path = str(template_file)
        mock_writer_agent.execute.return_value = writer_result
        
        auditor_result = writer_result.model_copy(deep=True)
        auditor_result.audit_report = AuditReport(
            passed=True,
            truth_violations=[]
        )
        auditor_result.ats_report = ATSReport(
            keyword_coverage_score=85.0,
            role_signal_score=90.0,
            missing_keywords=[],
            format_warnings=[]
        )
        auditor_result.inputs.template_path = str(template_file)
        mock_auditor_agent.execute.return_value = auditor_result
        
        agents = {
            "jd_analyst": mock_jd_agent,
            "evidence_mapper": mock_mapper_agent,
            "resume_writer": mock_writer_agent,
            "auditor": mock_auditor_agent,
        }
        
        orchestrator = PipelineOrchestrator(config, agents)
        result = orchestrator.run(blackboard)
        
        # Verify pipeline completed
        assert result.current_step == "complete"
        
        # Find output directory
        output_dir = OutputVerifier.find_output_dir(Path(tmp_path))
        assert output_dir is not None, "Output directory should be created"
        
        # Verify all expected outputs exist
        all_present, missing = OutputVerifier.verify_outputs(output_dir, result)
        assert all_present, f"Missing output files: {missing}. Output dir: {output_dir}"
        
        # Verify specific files exist
        assert (output_dir / "resume.md").exists()
        assert (output_dir / "evidence_used.json").exists()
        
        # Verify DOCX if resume_draft exists
        if result.resume_draft:
            docx_path = output_dir / "resume.docx"
            assert docx_path.exists(), \
                "DOCX file should be created when resume_draft exists"
            assert OutputVerifier.verify_docx_exists(docx_path), \
                "DOCX file exists but is invalid"
        
        # Verify diff file is generated when template exists
        if result.resume_draft and result.inputs.template_path:
            diff_path = output_dir / "diff_from_base.md"
            assert diff_path.exists(), \
                "Diff file should be created when template exists"
            diff_content = diff_path.read_text()
            assert len(diff_content) > 0, "Diff file should not be empty"
    
    def test_pipeline_with_audit_failure_and_retry(self, tmp_path):
        """Test pipeline that fails audit, retries, and succeeds."""
        config = load_config("config.yaml")
        config.paths["outputs"] = str(tmp_path)
        config.paths["evidence_cards"] = str(tmp_path / "evidence_cards.json")
        config.pipeline["max_retries"] = 2
        
        # Create evidence cards file
        evidence_cards = load_sample_evidence_cards()
        evidence_path = Path(config.paths["evidence_cards"])
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with open(evidence_path, "w") as f:
            json.dump([card.model_dump() for card in evidence_cards], f)
        
        # Create mock agents
        mock_jd_agent = MagicMock(spec=JDAnalystAgent)
        mock_mapper_agent = MagicMock(spec=EvidenceMapperAgent)
        mock_writer_agent = MagicMock(spec=ResumeWriterAgent)
        mock_auditor_agent = MagicMock(spec=AuditorAgent)
        
        blackboard = create_sample_blackboard()
        blackboard.evidence_cards = evidence_cards
        blackboard.max_retries = 2
        
        # Setup progression
        jd_result = blackboard.model_copy(deep=True)
        mock_jd_agent.execute.return_value = jd_result
        
        mapper_result = jd_result.model_copy(deep=True)
        mapper_result.selected_evidence_ids = [evidence_cards[0].id]
        mock_mapper_agent.execute.return_value = mapper_result
        
        writer_result = mapper_result.model_copy(deep=True)
        writer_result.resume_draft = ResumeDraft(sections=[])
        writer_result.claim_index = []
        mock_writer_agent.execute.return_value = writer_result
        
        # First audit fails, second passes
        first_audit_result = writer_result.model_copy(deep=True)
        first_audit_result.audit_report = AuditReport(
            passed=False,
            truth_violations=[
                TruthViolation(bullet_id="bullet-1", violation="Missing evidence")
            ]
        )
        
        second_audit_result = writer_result.model_copy(deep=True)
        second_audit_result.audit_report = AuditReport(
            passed=True,
            truth_violations=[]
        )
        second_audit_result.ats_report = ATSReport(
            keyword_coverage_score=80.0,
            role_signal_score=85.0,
            missing_keywords=[],
            format_warnings=[]
        )
        
        mock_auditor_agent.execute.side_effect = [
            first_audit_result,
            second_audit_result
        ]
        
        agents = {
            "jd_analyst": mock_jd_agent,
            "evidence_mapper": mock_mapper_agent,
            "resume_writer": mock_writer_agent,
            "auditor": mock_auditor_agent,
        }
        
        orchestrator = PipelineOrchestrator(config, agents)
        
        # Run pipeline
        result = orchestrator.run(blackboard)
        
        # Assertions
        assert result.current_step == "complete"
        assert result.audit_report.passed is True
        assert mock_auditor_agent.execute.call_count == 2  # Called twice (retry)
        assert mock_writer_agent.execute.call_count == 2  # Called twice (revision)
    
    def test_pipeline_fails_after_max_retries(self, tmp_path):
        """Test pipeline that fails audit repeatedly and exhausts retries."""
        config = load_config("config.yaml")
        config.paths["outputs"] = str(tmp_path)
        config.paths["evidence_cards"] = str(tmp_path / "evidence_cards.json")
        config.pipeline["max_retries"] = 2
        
        # Create evidence cards file
        evidence_cards = load_sample_evidence_cards()
        evidence_path = Path(config.paths["evidence_cards"])
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with open(evidence_path, "w") as f:
            json.dump([card.model_dump() for card in evidence_cards], f)
        
        # Create mock agents
        mock_jd_agent = MagicMock(spec=JDAnalystAgent)
        mock_mapper_agent = MagicMock(spec=EvidenceMapperAgent)
        mock_writer_agent = MagicMock(spec=ResumeWriterAgent)
        mock_auditor_agent = MagicMock(spec=AuditorAgent)
        
        blackboard = create_sample_blackboard()
        blackboard.evidence_cards = evidence_cards
        blackboard.max_retries = 2
        
        # Setup progression
        jd_result = blackboard.model_copy(deep=True)
        mock_jd_agent.execute.return_value = jd_result
        
        mapper_result = jd_result.model_copy(deep=True)
        mapper_result.selected_evidence_ids = [evidence_cards[0].id]
        mock_mapper_agent.execute.return_value = mapper_result
        
        writer_result = mapper_result.model_copy(deep=True)
        writer_result.resume_draft = ResumeDraft(sections=[])
        writer_result.claim_index = []
        mock_writer_agent.execute.return_value = writer_result
        
        # Audit always fails
        failed_audit_result = writer_result.model_copy(deep=True)
        failed_audit_result.audit_report = AuditReport(
            passed=False,
            truth_violations=[
                TruthViolation(bullet_id="bullet-1", violation="Missing evidence")
            ]
        )
        mock_auditor_agent.execute.return_value = failed_audit_result
        
        agents = {
            "jd_analyst": mock_jd_agent,
            "evidence_mapper": mock_mapper_agent,
            "resume_writer": mock_writer_agent,
            "auditor": mock_auditor_agent,
        }
        
        orchestrator = PipelineOrchestrator(config, agents)
        
        # Run pipeline - should fail
        with pytest.raises(Exception):  # Should raise OrchestrationError
            result = orchestrator.run(blackboard)
            
            # If we get here, check that it failed
            assert result.current_step == "failed"
            assert result.retry_count >= result.max_retries


@pytest.mark.integration
@pytest.mark.requires_api_key
class TestPipelineE2EReal:
    """End-to-end pipeline tests with real API calls (requires API keys)."""
    
    @pytest.mark.skipif(
        not all([
            os.getenv("ANTHROPIC_API_KEY"),
            os.getenv("OPENAI_API_KEY"),
            os.getenv("GOOGLE_API_KEY"),
        ]),
        reason="Requires ANTHROPIC_API_KEY, OPENAI_API_KEY, and GOOGLE_API_KEY"
    )
    def test_full_pipeline_real_api(self, tmp_path):
        """Test complete pipeline with real API calls (minimal to reduce cost)."""
        config = load_config("config.yaml")
        config.paths["outputs"] = str(tmp_path)
        config.paths["evidence_cards"] = str(tmp_path / "evidence_cards.json")
        
        # Create minimal evidence cards file
        evidence_cards = load_sample_evidence_cards()[:2]  # Use only 2 cards
        evidence_path = Path(config.paths["evidence_cards"])
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        with open(evidence_path, "w") as f:
            json.dump([card.model_dump() for card in evidence_cards], f)
        
        # Create agents with real providers
        from resumeforge.providers import create_provider_from_alias
        
        jd_provider = create_provider_from_alias("jd_analyst_default", config)
        mapper_provider = create_provider_from_alias("mapper_precise", config)
        writer_provider = create_provider_from_alias("writer_default", config)
        ats_provider = create_provider_from_alias("ats_scorer_fast", config)
        truth_provider = create_provider_from_alias("auditor_deterministic", config)
        
        agents = {
            "jd_analyst": JDAnalystAgent(jd_provider, config.agents.get("jd_analyst", {})),
            "evidence_mapper": EvidenceMapperAgent(mapper_provider, config.agents.get("evidence_mapper", {})),
            "resume_writer": ResumeWriterAgent(writer_provider, config.agents.get("resume_writer", config.agents.get("writer", {}))),
            "auditor": AuditorAgent(ats_provider, truth_provider, config.agents.get("truth_auditor", {})),
        }
        
        # Create minimal blackboard
        minimal_jd = "Looking for a senior engineer with Python experience."
        blackboard = Blackboard(
            inputs=Inputs(
                job_description=minimal_jd,
                target_title="Senior Engineer",
                length_rules=LengthRules(max_pages=1),  # Keep it short
                template_path=str(tmp_path / "template.md")
            )
        )
        
        orchestrator = PipelineOrchestrator(config, agents)
        
        # Run pipeline
        result = orchestrator.run(blackboard)
        
        # Basic assertions (don't be too strict - LLM outputs vary)
        assert result.current_step == "complete"
        assert result.role_profile is not None
        # Note: Other assertions may vary based on LLM responses
