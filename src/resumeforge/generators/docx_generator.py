"""DOCX generator for resume output."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from resumeforge.schemas.blackboard import Blackboard


class DocxGenerator:
    """Generates DOCX output from blackboard state."""
    
    def __init__(self, template_path: str | None = None):
        """
        Initialize generator.
        
        Args:
            template_path: Optional path to DOCX template
        """
        self.template_path = template_path
    
    def generate(self, blackboard: "Blackboard", output_path: Path) -> None:
        """
        Generate DOCX file from blackboard.
        
        Args:
            blackboard: Blackboard with resume draft
            output_path: Path to output DOCX file
        """
        # TODO: Implement DOCX generation using python-docx
        # See SDD Section 8.1 for implementation details
        raise NotImplementedError("DOCX generator not yet implemented")
