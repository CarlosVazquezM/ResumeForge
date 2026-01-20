"""Test fixtures and sample data."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from resumeforge.schemas.blackboard import Blackboard, Inputs, LengthRules
from resumeforge.schemas.evidence_card import EvidenceCard

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent

# Import output verification helper
from tests.fixtures.output_verification import OutputVerifier

__all__ = [
    "load_sample_evidence_cards",
    "load_sample_jd",
    "load_sample_template",
    "create_mock_provider",
    "create_sample_blackboard",
    "OutputVerifier",
]


def load_sample_evidence_cards() -> list[EvidenceCard]:
    """Load sample evidence cards from fixture file."""
    fixture_path = FIXTURES_DIR / "sample_evidence_cards.json"
    with open(fixture_path, encoding="utf-8") as f:
        data = json.load(f)
    return [EvidenceCard(**card) for card in data]


def load_sample_jd() -> str:
    """Load sample job description from fixture file."""
    fixture_path = FIXTURES_DIR / "sample_job_description.txt"
    return fixture_path.read_text(encoding="utf-8")


def load_sample_template() -> str:
    """Load sample resume template from fixture file."""
    fixture_path = FIXTURES_DIR / "sample_resume_template.md"
    return fixture_path.read_text(encoding="utf-8")


def create_mock_provider(
    model: str = "test-model",
    response: str = '{"test": "response"}',
    token_count: int = 100
) -> MagicMock:
    """
    Create a mocked provider for unit tests.
    
    Args:
        model: Model name to use
        response: Response text to return from generate_text()
        token_count: Token count to return from count_tokens()
        
    Returns:
        Mocked provider instance
    """
    mock_provider = MagicMock()
    mock_provider.model = model
    mock_provider.generate_text = MagicMock(return_value=response)
    mock_provider.count_tokens = MagicMock(return_value=token_count)
    return mock_provider


def create_sample_blackboard(
    job_description: str | None = None,
    target_title: str = "Senior Engineering Manager",
    evidence_cards: list[EvidenceCard] | None = None,
    **kwargs
) -> Blackboard:
    """
    Create a sample blackboard for testing.
    
    Args:
        job_description: Job description text (defaults to sample JD)
        target_title: Target job title
        evidence_cards: List of evidence cards (defaults to sample cards)
        **kwargs: Additional blackboard fields to set
        
    Returns:
        Blackboard instance with test data
    """
    if job_description is None:
        job_description = load_sample_jd()
    
    if evidence_cards is None:
        evidence_cards = load_sample_evidence_cards()
    
    template_path = str(FIXTURES_DIR / "sample_resume_template.md")
    
    blackboard = Blackboard(
        inputs=Inputs(
            job_description=job_description,
            target_title=target_title,
            length_rules=LengthRules(max_pages=2),
            template_path=template_path
        ),
        evidence_cards=evidence_cards,
        **kwargs
    )
    
    return blackboard
