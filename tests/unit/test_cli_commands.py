"""Test that all documented CLI commands exist and work."""

import pytest
from click.testing import CliRunner
from resumeforge.cli import cli


@pytest.mark.cli_coverage
class TestCLICommandsExist:
    """Verify all documented CLI commands are implemented."""
    
    DOCUMENTED_COMMANDS = [
        "parse",      # Parse fact resume
        "generate",  # Generate targeted resume
        "diff",       # Compare resume variants (from SDD)
    ]
    
    def test_all_documented_commands_exist(self):
        """Verify all commands from documentation exist."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0, f"CLI help failed: {result.output}"
        
        for command in self.DOCUMENTED_COMMANDS:
            assert command in result.output, \
                f"Command '{command}' is documented but not implemented. " \
                f"Available commands: {result.output}"
    
    def test_parse_command_exists(self):
        """Test parse command is registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ["parse", "--help"])
        assert result.exit_code == 0, f"Parse command help failed: {result.output}"
        assert "--fact-resume" in result.output or "fact-resume" in result.output
    
    def test_generate_command_exists(self):
        """Test generate command is registered."""
        runner = CliRunner()
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0, f"Generate command help failed: {result.output}"
        assert "--jd" in result.output or "--job-description" in result.output.lower()
    
    def test_diff_command_exists(self):
        """Test diff command is registered (from SDD)."""
        runner = CliRunner()
        result = runner.invoke(cli, ["diff", "--help"])
        # This will fail until diff command is implemented
        assert result.exit_code == 0, \
            "diff command is documented in SDD but not implemented. " \
            f"CLI error: {result.output}"


@pytest.mark.cli_coverage
class TestCLIDiffCommand:
    """Test diff command functionality."""
    
    def test_diff_command_help(self, tmp_path):
        """Test diff command shows help."""
        runner = CliRunner()
        result = runner.invoke(cli, ["diff", "--help"])
        
        # This will fail until diff command is implemented
        assert result.exit_code == 0, \
            "diff command should exist and show help. " \
            f"Error: {result.output}"
        
        # Once implemented, verify it has expected options
        if result.exit_code == 0:
            assert "--variant1" in result.output or "variant1" in result.output.lower()
            assert "--variant2" in result.output or "variant2" in result.output.lower()
    
    def test_diff_command_execution(self, tmp_path):
        """Test diff command executes successfully."""
        # Create two sample resume files
        variant1 = tmp_path / "resume1.md"
        variant2 = tmp_path / "resume2.md"
        
        variant1.write_text("# Resume 1\n\nContent 1")
        variant2.write_text("# Resume 2\n\nContent 2")
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            "diff",
            "--variant1", str(variant1),
            "--variant2", str(variant2),
        ])
        
        # This will fail until diff is implemented
        assert result.exit_code == 0, \
            "diff command should execute successfully. " \
            f"Error: {result.output}"
        
        # Once implemented, verify output
        if result.exit_code == 0:
            assert len(result.output) > 0, "Diff command should produce output"
