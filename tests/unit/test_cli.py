"""Unit tests for CLI commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest
import click.testing

from resumeforge.cli import cli, parse, generate
from resumeforge.exceptions import ConfigError, ProviderError, ValidationError, OrchestrationError
from tests.fixtures import create_sample_blackboard


class TestCLIParseCommand:
    """Tests for the 'parse' CLI command."""
    
    def test_parse_command_exists(self):
        """Test that parse command is registered."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["parse", "--help"])
        assert result.exit_code == 0
        assert "Parse fact resume into evidence cards" in result.output
    
    def test_parse_requires_fact_resume(self):
        """Test that parse command requires --fact-resume option."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["parse"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "Error" in result.output
    
    @patch("resumeforge.cli.load_config")
    @patch("resumeforge.cli.create_provider_from_alias")
    @patch("resumeforge.cli.FactResumeParser")
    def test_parse_success(self, mock_parser_class, mock_create_provider, mock_load_config):
        """Test successful parse command execution."""
        runner = click.testing.CliRunner()
        
        # Setup mocks
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        mock_provider = MagicMock()
        mock_create_provider.return_value = mock_provider
        
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            {"id": "test-card", "project": "Test", "company": "Test Co", "timeframe": "2020-2024", "role": "Engineer", "raw_text": "Test"}
        ]
        mock_parser.estimate_cost.return_value = {"estimated_cost_usd": 0.05}
        mock_parser_class.return_value = mock_parser
        
        # Create temporary fact resume file
        with runner.isolated_filesystem():
            fact_resume = Path("fact_resume.md")
            fact_resume.write_text("Test resume content")
            
            result = runner.invoke(cli, ["parse", "--fact-resume", str(fact_resume), "--yes"])
            
            assert result.exit_code == 0
            assert "Successfully parsed" in result.output
            mock_parser.parse.assert_called_once()
    
    @patch("resumeforge.cli.load_config")
    def test_parse_missing_config_file(self, mock_load_config):
        """Test parse command with missing config file."""
        runner = click.testing.CliRunner()
        
        mock_load_config.side_effect = ConfigError("Config file not found")
        
        with runner.isolated_filesystem():
            fact_resume = Path("fact_resume.md")
            fact_resume.write_text("Test resume content")
            
            result = runner.invoke(cli, ["parse", "--fact-resume", str(fact_resume)])
            
            assert result.exit_code != 0
            assert "Configuration error" in result.output
    
    @patch("resumeforge.cli.load_config")
    @patch("resumeforge.cli.create_provider_from_alias")
    def test_parse_missing_api_key(self, mock_create_provider, mock_load_config):
        """Test parse command with missing API key."""
        runner = click.testing.CliRunner()
        
        mock_load_config.return_value = MagicMock()
        mock_create_provider.side_effect = ProviderError("Missing API key")
        
        with runner.isolated_filesystem():
            fact_resume = Path("fact_resume.md")
            fact_resume.write_text("Test resume content")
            
            result = runner.invoke(cli, ["parse", "--fact-resume", str(fact_resume)])
            
            assert result.exit_code != 0
            assert "Provider error" in result.output
            assert "API keys" in result.output
    
    @patch("resumeforge.cli.load_config")
    @patch("resumeforge.cli.create_provider_from_alias")
    @patch("resumeforge.cli.FactResumeParser")
    def test_parse_dry_run(self, mock_parser_class, mock_create_provider, mock_load_config):
        """Test parse command with --dry-run flag."""
        runner = click.testing.CliRunner()
        
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        mock_provider = MagicMock()
        mock_create_provider.return_value = mock_provider
        
        mock_parser = MagicMock()
        mock_parser.parse.return_value = {
            "cost_estimation": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "provider": "anthropic",
                "model": "claude-sonnet-4",
                "estimated_cost_usd": 0.05,
                "input_cost_usd": 0.03,
                "output_cost_usd": 0.02
            },
            "resume_size_chars": 5000
        }
        mock_parser_class.return_value = mock_parser
        
        with runner.isolated_filesystem():
            fact_resume = Path("fact_resume.md")
            fact_resume.write_text("Test resume content")
            
            result = runner.invoke(cli, ["parse", "--fact-resume", str(fact_resume), "--dry-run"])
            
            assert result.exit_code == 0
            assert "Dry run complete" in result.output
            assert "Cost Estimation" in result.output
            # Verify parse was called with dry_run=True
            mock_parser.parse.assert_called_once()
            call_args = mock_parser.parse.call_args
            assert call_args[1].get("dry_run") is True
    
    @patch("resumeforge.cli.load_config")
    @patch("resumeforge.cli.create_provider_from_alias")
    @patch("resumeforge.cli.FactResumeParser")
    def test_parse_validation_error(self, mock_parser_class, mock_create_provider, mock_load_config):
        """Test parse command with validation error."""
        runner = click.testing.CliRunner()
        
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        mock_provider = MagicMock()
        mock_create_provider.return_value = mock_provider
        
        mock_parser = MagicMock()
        mock_parser.parse.side_effect = ValidationError("Invalid evidence card format")
        mock_parser.estimate_cost.return_value = {"estimated_cost_usd": 0.05}
        mock_parser_class.return_value = mock_parser
        
        with runner.isolated_filesystem():
            fact_resume = Path("fact_resume.md")
            fact_resume.write_text("Test resume content")
            
            result = runner.invoke(cli, ["parse", "--fact-resume", str(fact_resume), "--yes"])
            
            assert result.exit_code != 0
            assert "Validation error" in result.output


class TestCLIGenerateCommand:
    """Tests for the 'generate' CLI command."""
    
    def test_generate_command_exists(self):
        """Test that generate command is registered."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "Generate a targeted resume" in result.output
    
    def test_generate_requires_jd_and_title(self):
        """Test that generate command requires --jd and --title options."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["generate"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "Error" in result.output
    
    @patch("resumeforge.cli.load_config")
    @patch("resumeforge.cli.create_provider_from_alias")
    @patch("resumeforge.cli.PipelineOrchestrator")
    def test_generate_success(self, mock_orchestrator_class, mock_create_provider, mock_load_config):
        """Test successful generate command execution."""
        runner = click.testing.CliRunner()
        
        # Setup mocks
        mock_config = MagicMock()
        mock_config.paths = {"templates": "./data/templates"}
        mock_config.agents = {
            "jd_analyst": {},
            "evidence_mapper": {},
            "resume_writer": {},
            "writer": {},
            "truth_auditor": {}
        }
        mock_load_config.return_value = mock_config
        
        # Mock providers
        mock_provider = MagicMock()
        mock_create_provider.return_value = mock_provider
        
        # Mock orchestrator
        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.current_step = "complete"
        mock_result.ats_report = MagicMock(keyword_coverage_score=85.0, role_signal_score=90.0)
        mock_result.audit_report = MagicMock(truth_violations=[], passed=True)
        mock_result.resume_draft = MagicMock(sections=["Section1", "Section2"])
        mock_result.claim_index = [{"bullet_id": "bullet-1"}]
        mock_result.selected_evidence_ids = ["card-1", "card-2"]
        mock_orchestrator.run.return_value = mock_result
        mock_orchestrator_class.return_value = mock_orchestrator
        
        with runner.isolated_filesystem():
            jd_file = Path("job_description.txt")
            jd_file.write_text("Looking for a senior engineer...")
            
            result = runner.invoke(cli, [
                "generate",
                "--jd", str(jd_file),
                "--title", "Senior Engineer",
                "--yes"
            ])
            
            assert result.exit_code == 0
            assert "Pipeline completed successfully" in result.output
            mock_orchestrator.run.assert_called_once()
    
    @patch("resumeforge.cli.load_config")
    def test_generate_missing_config_file(self, mock_load_config):
        """Test generate command with missing config file."""
        runner = click.testing.CliRunner()
        
        mock_load_config.side_effect = ConfigError("Config file not found")
        
        with runner.isolated_filesystem():
            jd_file = Path("job_description.txt")
            jd_file.write_text("Test job description")
            
            result = runner.invoke(cli, [
                "generate",
                "--jd", str(jd_file),
                "--title", "Engineer"
            ])
            
            assert result.exit_code != 0
            assert "Configuration error" in result.output
    
    @patch("resumeforge.cli.load_config")
    @patch("resumeforge.cli.create_provider_from_alias")
    def test_generate_missing_api_key(self, mock_create_provider, mock_load_config):
        """Test generate command with missing API key."""
        runner = click.testing.CliRunner()
        
        mock_config = MagicMock()
        mock_config.paths = {"templates": "./data/templates"}
        mock_config.agents = {}
        mock_load_config.return_value = mock_config
        mock_create_provider.side_effect = ProviderError("Missing API key")
        
        with runner.isolated_filesystem():
            jd_file = Path("job_description.txt")
            jd_file.write_text("Test job description")
            
            result = runner.invoke(cli, [
                "generate",
                "--jd", str(jd_file),
                "--title", "Engineer"
            ])
            
            assert result.exit_code != 0
            assert "Provider error" in result.output
            assert "API keys" in result.output
    
    @patch("resumeforge.cli.load_config")
    @patch("resumeforge.cli.create_provider_from_alias")
    @patch("resumeforge.cli.PipelineOrchestrator")
    def test_generate_empty_jd_file(self, mock_orchestrator_class, mock_create_provider, mock_load_config):
        """Test generate command with empty job description file."""
        runner = click.testing.CliRunner()
        
        mock_config = MagicMock()
        mock_config.paths = {"templates": "./data/templates"}
        mock_config.agents = {}
        mock_load_config.return_value = mock_config
        
        with runner.isolated_filesystem():
            jd_file = Path("job_description.txt")
            jd_file.write_text("")  # Empty file
            
            result = runner.invoke(cli, [
                "generate",
                "--jd", str(jd_file),
                "--title", "Engineer"
            ])
            
            assert result.exit_code != 0
            assert "empty" in result.output.lower()
    
    @patch("resumeforge.cli.load_config")
    @patch("resumeforge.cli.create_provider_from_alias")
    @patch("resumeforge.cli.PipelineOrchestrator")
    def test_generate_orchestration_error(self, mock_orchestrator_class, mock_create_provider, mock_load_config):
        """Test generate command with orchestration error."""
        runner = click.testing.CliRunner()
        
        mock_config = MagicMock()
        mock_config.paths = {"templates": "./data/templates"}
        mock_config.agents = {
            "jd_analyst": {},
            "evidence_mapper": {},
            "resume_writer": {},
            "writer": {},
            "truth_auditor": {}
        }
        mock_load_config.return_value = mock_config
        
        mock_provider = MagicMock()
        mock_create_provider.return_value = mock_provider
        
        mock_orchestrator = MagicMock()
        mock_orchestrator.run.side_effect = OrchestrationError("Pipeline failed", "auditing")
        mock_orchestrator_class.return_value = mock_orchestrator
        
        with runner.isolated_filesystem():
            jd_file = Path("job_description.txt")
            jd_file.write_text("Test job description")
            
            result = runner.invoke(cli, [
                "generate",
                "--jd", str(jd_file),
                "--title", "Engineer",
                "--yes"
            ])
            
            assert result.exit_code != 0
            assert "Pipeline failed" in result.output
    
    @patch("resumeforge.cli.load_config")
    @patch("resumeforge.cli.create_provider_from_alias")
    @patch("resumeforge.cli.PipelineOrchestrator")
    def test_generate_with_template(self, mock_orchestrator_class, mock_create_provider, mock_load_config):
        """Test generate command with custom template."""
        runner = click.testing.CliRunner()
        
        mock_config = MagicMock()
        mock_config.paths = {"templates": "./data/templates"}
        mock_config.agents = {
            "jd_analyst": {},
            "evidence_mapper": {},
            "resume_writer": {},
            "writer": {},
            "truth_auditor": {}
        }
        mock_load_config.return_value = mock_config
        
        mock_provider = MagicMock()
        mock_create_provider.return_value = mock_provider
        
        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.current_step = "complete"
        mock_result.ats_report = None
        mock_result.audit_report = None
        mock_result.resume_draft = None
        mock_result.claim_index = None
        mock_result.selected_evidence_ids = []
        mock_orchestrator.run.return_value = mock_result
        mock_orchestrator_class.return_value = mock_orchestrator
        
        with runner.isolated_filesystem():
            jd_file = Path("job_description.txt")
            jd_file.write_text("Test job description")
            
            template_file = Path("template.md")
            template_file.write_text("# Resume Template")
            
            result = runner.invoke(cli, [
                "generate",
                "--jd", str(jd_file),
                "--title", "Engineer",
                "--template", str(template_file),
                "--yes"
            ])
            
            assert result.exit_code == 0
            # Verify orchestrator was called
            mock_orchestrator.run.assert_called_once()
    
    @patch("resumeforge.cli.load_config")
    @patch("resumeforge.cli.create_provider_from_alias")
    @patch("resumeforge.cli.PipelineOrchestrator")
    def test_generate_with_custom_output_dir(self, mock_orchestrator_class, mock_create_provider, mock_load_config):
        """Test generate command with custom output directory."""
        runner = click.testing.CliRunner()
        
        mock_config = MagicMock()
        mock_config.paths = {"templates": "./data/templates"}
        mock_config.agents = {
            "jd_analyst": {},
            "evidence_mapper": {},
            "resume_writer": {},
            "writer": {},
            "truth_auditor": {}
        }
        mock_load_config.return_value = mock_config
        
        mock_provider = MagicMock()
        mock_create_provider.return_value = mock_provider
        
        mock_orchestrator = MagicMock()
        mock_result = MagicMock()
        mock_result.current_step = "complete"
        mock_result.ats_report = None
        mock_result.audit_report = None
        mock_result.resume_draft = None
        mock_result.claim_index = None
        mock_result.selected_evidence_ids = []
        mock_orchestrator.run.return_value = mock_result
        mock_orchestrator_class.return_value = mock_orchestrator
        
        with runner.isolated_filesystem():
            jd_file = Path("job_description.txt")
            jd_file.write_text("Test job description")
            
            result = runner.invoke(cli, [
                "generate",
                "--jd", str(jd_file),
                "--title", "Engineer",
                "--output-dir", "./custom-outputs",
                "--yes"
            ])
            
            assert result.exit_code == 0
            # Verify output directory was set in config
            assert mock_config.paths["outputs"] == "./custom-outputs"


class TestCLIVersion:
    """Tests for CLI version command."""
    
    def test_version_command(self):
        """Test that version command works."""
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower()
