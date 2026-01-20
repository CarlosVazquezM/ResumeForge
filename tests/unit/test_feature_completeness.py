"""Test that critical features are implemented (not NotImplementedError)."""

import pytest
from pathlib import Path
from resumeforge.generators.docx_generator import DocxGenerator
from resumeforge.utils.diff import generate_diff
from resumeforge.schemas.blackboard import Blackboard, Inputs, ResumeDraft, ResumeSection


@pytest.mark.feature_completeness
@pytest.mark.critical
class TestFeatureCompleteness:
    """Verify critical features are implemented."""
    
    def test_docx_generator_implemented(self, tmp_path):
        """Test that DOCX generator is implemented."""
        generator = DocxGenerator()
        blackboard = Blackboard(
            inputs=Inputs(
                job_description="Test",
                target_title="Test",
                template_path="test.md"
            )
        )
        blackboard.resume_draft = ResumeDraft(
            sections=[ResumeSection(name="Test", content="Test content")]
        )
        
        output_path = tmp_path / "test_resume.docx"
        
        # This should NOT raise NotImplementedError
        try:
            generator.generate(blackboard, output_path)
            # If we get here, verify file was created
            assert output_path.exists(), "DOCX file should be created"
        except NotImplementedError as e:
            pytest.fail(
                f"DOCX generator raises NotImplementedError: {e}. "
                "This feature must be implemented."
            )
    
    def test_diff_generator_implemented(self, tmp_path):
        """Test that diff generator is implemented."""
        variant1 = tmp_path / "variant1.md"
        variant2 = tmp_path / "variant2.md"
        
        # Create test files
        variant1.write_text("# Resume 1\n\nContent 1")
        variant2.write_text("# Resume 2\n\nContent 2")
        
        try:
            result = generate_diff(variant1, variant2)
            assert result is not None, "Diff generator should return a result"
            assert isinstance(result, str), "Diff generator should return a string"
            assert len(result) > 0, "Diff generator should return non-empty result"
        except NotImplementedError as e:
            pytest.fail(
                f"Diff generator raises NotImplementedError: {e}. "
                "This feature must be implemented."
            )
