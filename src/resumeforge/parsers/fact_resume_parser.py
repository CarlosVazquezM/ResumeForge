"""Parser for Fact Resume to Evidence Cards."""

from pathlib import Path
from typing import TYPE_CHECKING

from resumeforge.schemas.evidence_card import EvidenceCard

if TYPE_CHECKING:
    from resumeforge.providers.base import BaseProvider


class FactResumeParser:
    """Parses a Fact Resume into structured Evidence Cards."""
    
    def __init__(self, provider: "BaseProvider"):
        """
        Initialize parser.
        
        Args:
            provider: LLM provider for parsing assistance
        """
        self.provider = provider
    
    def parse(self, resume_path: Path) -> list[EvidenceCard]:
        """
        Parse fact resume into evidence cards.
        
        Args:
            resume_path: Path to fact resume file
            
        Returns:
            List of parsed EvidenceCard objects
        """
        # TODO: Implement LLM-assisted parsing
        # See SDD Section 4 and Phase 4 of roadmap
        raise NotImplementedError("Fact resume parser not yet implemented")
