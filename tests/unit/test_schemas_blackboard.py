"""Unit tests for Blackboard schema."""

import pytest
from pydantic import ValidationError

from resumeforge.schemas.blackboard import (
    Blackboard,
    ClaimMapping,
    Inputs,
    LengthRules,
    Priority,
    Requirement,
)
from resumeforge.schemas.evidence_card import EvidenceCard


class TestClaimMapping:
    """Tests for ClaimMapping model."""

    def test_valid_claim_mapping(self):
        """Test creating a valid ClaimMapping."""
        claim = ClaimMapping(
            bullet_id="test-bullet-1",
            bullet_text="Led team of 10 engineers",
            evidence_card_ids=["card-1", "card-2"]
        )
        assert claim.bullet_id == "test-bullet-1"
        assert len(claim.evidence_card_ids) == 2

    def test_claim_mapping_empty_evidence_ids(self):
        """Test that empty evidence_card_ids raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ClaimMapping(
                bullet_id="test-bullet",
                bullet_text="Some claim",
                evidence_card_ids=[]  # Empty - should fail
            )
        assert "evidence_card_ids" in str(exc_info.value).lower()

    def test_validate_against_cards(self):
        """Test validate_against_cards method."""
        claim = ClaimMapping(
            bullet_id="test-bullet",
            bullet_text="Claim",
            evidence_card_ids=["card-1", "card-2"]
        )
        available = {"card-1", "card-2", "card-3"}
        assert claim.validate_against_cards(available) is True

    def test_validate_against_cards_missing(self):
        """Test validate_against_cards with missing cards."""
        claim = ClaimMapping(
            bullet_id="test-bullet",
            bullet_text="Claim",
            evidence_card_ids=["card-1", "card-4"]  # card-4 doesn't exist
        )
        available = {"card-1", "card-2", "card-3"}
        assert claim.validate_against_cards(available) is False


class TestBlackboard:
    """Tests for Blackboard model."""

    @pytest.fixture
    def sample_inputs(self):
        """Create sample Inputs for testing."""
        return Inputs(
            job_description="We are looking for...",
            target_title="Senior Engineering Manager",
            template_path="./templates/base.md"
        )

    @pytest.fixture
    def sample_evidence_cards(self):
        """Create sample evidence cards for testing."""
        return [
            EvidenceCard(
                id="card-1",
                project="Project 1",
                company="Company A",
                timeframe="2020-2024",
                role="Engineer",
                raw_text="Worked on..."
            ),
            EvidenceCard(
                id="card-2",
                project="Project 2",
                company="Company B",
                timeframe="2018-2020",
                role="Senior Engineer",
                raw_text="Led..."
            )
        ]

    def test_valid_blackboard_init(self, sample_inputs):
        """Test creating a valid Blackboard."""
        blackboard = Blackboard(inputs=sample_inputs)
        assert blackboard.inputs == sample_inputs
        assert blackboard.current_step == "init"
        assert blackboard.retry_count == 0

    def test_get_selected_evidence_cards(self, sample_inputs, sample_evidence_cards):
        """Test get_selected_evidence_cards method."""
        blackboard = Blackboard(
            inputs=sample_inputs,
            evidence_cards=sample_evidence_cards,
            selected_evidence_ids=["card-1", "card-2"]
        )
        selected = blackboard.get_selected_evidence_cards()
        assert len(selected) == 2
        assert {card.id for card in selected} == {"card-1", "card-2"}

    def test_get_selected_evidence_cards_partial(self, sample_inputs, sample_evidence_cards):
        """Test get_selected_evidence_cards with partial selection."""
        blackboard = Blackboard(
            inputs=sample_inputs,
            evidence_cards=sample_evidence_cards,
            selected_evidence_ids=["card-1"]
        )
        selected = blackboard.get_selected_evidence_cards()
        assert len(selected) == 1
        assert selected[0].id == "card-1"

    def test_get_evidence_card_by_id(self, sample_inputs, sample_evidence_cards):
        """Test get_evidence_card_by_id method."""
        blackboard = Blackboard(
            inputs=sample_inputs,
            evidence_cards=sample_evidence_cards
        )
        card = blackboard.get_evidence_card_by_id("card-1")
        assert card is not None
        assert card.id == "card-1"

    def test_get_evidence_card_by_id_not_found(self, sample_inputs, sample_evidence_cards):
        """Test get_evidence_card_by_id with non-existent ID."""
        blackboard = Blackboard(
            inputs=sample_inputs,
            evidence_cards=sample_evidence_cards
        )
        card = blackboard.get_evidence_card_by_id("card-999")
        assert card is None

    def test_validate_state_init(self, sample_inputs):
        """Test validate_state for initial state."""
        blackboard = Blackboard(inputs=sample_inputs, current_step="init")
        is_valid, errors = blackboard.validate_state()
        assert is_valid is True
        assert errors == []

    def test_validate_state_missing_role_profile(self, sample_inputs):
        """Test validate_state detects missing role_profile."""
        blackboard = Blackboard(
            inputs=sample_inputs,
            current_step="evidence_mapping"
        )
        is_valid, errors = blackboard.validate_state()
        assert is_valid is False
        assert any("role_profile" in error.lower() for error in errors)

    def test_validate_state_claim_index_validation(self, sample_inputs, sample_evidence_cards):
        """Test validate_state validates claim_index references."""
        blackboard = Blackboard(
            inputs=sample_inputs,
            evidence_cards=sample_evidence_cards,
            current_step="auditing",
            claim_index=[
                ClaimMapping(
                    bullet_id="bullet-1",
                    bullet_text="Claim",
                    evidence_card_ids=["card-1", "card-999"]  # card-999 doesn't exist
                )
            ]
        )
        is_valid, errors = blackboard.validate_state()
        assert is_valid is False
        assert any("non-existent" in error.lower() for error in errors)
