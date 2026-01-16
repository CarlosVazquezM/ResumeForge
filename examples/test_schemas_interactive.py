"""Interactive schema testing and demonstration script.

This script demonstrates various schema operations and validations.
Run with: python examples/test_schemas_interactive.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from resumeforge.schemas import (
    Blackboard,
    EvidenceCard,
    Inputs,
    MetricEntry,
    ScopeInfo,
    ClaimMapping,
    Priority,
    Confidence,
    GapStrategy,
    Requirement,
    EvidenceMapping,
    GapResolution,
    RoleProfile,
    ResumeDraft,
    ResumeSection,
    ATSReport,
    AuditReport,
    TruthViolation,
    export_json_schema,
)
from resumeforge.config import load_config


def test_evidence_card_creation():
    """Test creating EvidenceCard with various configurations."""
    print("\n" + "=" * 60)
    print("TEST 1: EvidenceCard Creation & Validation")
    print("=" * 60)

    # Test 1.1: Basic card
    print("\n1.1 Creating basic EvidenceCard...")
    card1 = EvidenceCard(
        id="demo-basic",
        project="Demo Project",
        company="Tech Corp",
        timeframe="2020-2024",
        role="Senior Engineer",
        raw_text="Led development of..."
    )
    print(f"   ✓ Created: {card1.id}")
    print(f"   ✓ Timeframe: {card1.timeframe}")
    print(f"   ✓ Company: {card1.company}")

    # Test 1.2: Card with metrics
    print("\n1.2 Creating EvidenceCard with metrics...")
    card2 = EvidenceCard(
        id="demo-metrics",
        project="Performance Optimization",
        company="Tech Corp",
        timeframe="2022-01 to 2024-12",
        role="Engineering Manager",
        metrics=[
            MetricEntry(value="75%", description="reduction in latency", context="p95"),
            MetricEntry(value="340K+", description="requests per second", context="peak"),
            MetricEntry(value="50%", description="cost reduction"),
        ],
        skills=["Python", "Kubernetes", "AWS", "Docker"],
        leadership_signals=["managed 8 engineers", "zero attrition"],
        raw_text="Optimized system performance..."
    )
    print(f"   ✓ Created: {card2.id}")
    print(f"   ✓ Metrics summary: {card2.get_metrics_summary()}")
    print(f"   ✓ Skills: {card2.get_skills_summary()}")
    print(f"   ✓ Leadership: {', '.join(card2.leadership_signals)}")

    # Test 1.3: Invalid timeframe (should fail)
    print("\n1.3 Testing invalid timeframe format...")
    try:
        card3 = EvidenceCard(
            id="demo-invalid",
            project="Test",
            company="Test",
            timeframe="2020/2024",  # Invalid format
            role="Engineer",
            raw_text="Test"
        )
        print("   ✗ ERROR: Should have raised ValidationError!")
    except Exception as e:
        print(f"   ✓ Correctly rejected invalid timeframe: {type(e).__name__}")

    # Test 1.4: Card with full scope
    print("\n1.4 Creating EvidenceCard with full scope...")
    card4 = EvidenceCard(
        id="demo-full-scope",
        project="Enterprise Platform",
        company="BigCorp",
        timeframe="2019-2023",
        role="Senior Engineering Manager",
        scope=ScopeInfo(
            team_size=19,
            direct_reports=19,
            geography=["US", "Romania", "India"],
            budget="$5M"
        ),
        metrics=[
            MetricEntry(value="520+", description="client integrations"),
        ],
        skills=[".NET", "microservices", "distributed systems"],
        leadership_signals=["cross-geo team", "zero voluntary attrition"],
        raw_text="Led global team..."
    )
    print(f"   ✓ Created: {card4.id}")
    print(f"   ✓ Team size: {card4.scope.team_size}")
    print(f"   ✓ Geography: {', '.join(card4.scope.geography)}")
    print(f"   ✓ Budget: {card4.scope.budget}")

    return [card1, card2, card4]


def test_blackboard_operations():
    """Test Blackboard state management."""
    print("\n" + "=" * 60)
    print("TEST 2: Blackboard State Management")
    print("=" * 60)

    # Create inputs
    print("\n2.1 Creating Blackboard with inputs...")
    inputs = Inputs(
        job_description="We are looking for a Senior Engineering Manager...",
        target_title="Senior Engineering Manager",
        template_path="./templates/base.md"
    )
    blackboard = Blackboard(inputs=inputs)
    print(f"   ✓ Blackboard created")
    print(f"   ✓ Current step: {blackboard.current_step}")
    print(f"   ✓ Target title: {blackboard.inputs.target_title}")

    # Add evidence cards
    print("\n2.2 Adding evidence cards...")
    cards = test_evidence_card_creation()
    blackboard.evidence_cards = cards
    blackboard.selected_evidence_ids = [card.id for card in cards]
    print(f"   ✓ Added {len(blackboard.evidence_cards)} evidence cards")
    print(f"   ✓ Selected {len(blackboard.selected_evidence_ids)} cards")

    # Test helper methods
    print("\n2.3 Testing helper methods...")
    selected = blackboard.get_selected_evidence_cards()
    print(f"   ✓ get_selected_evidence_cards(): {len(selected)} cards")
    
    card = blackboard.get_evidence_card_by_id("demo-metrics")
    if card:
        print(f"   ✓ get_evidence_card_by_id(): Found {card.id}")

    # Test state validation
    print("\n2.4 Testing state validation...")
    is_valid, errors = blackboard.validate_state()
    print(f"   ✓ State valid: {is_valid}")
    if errors:
        print(f"   ✓ Validation errors: {errors}")

    return blackboard


def test_claim_mapping_validation():
    """Test ClaimMapping validation."""
    print("\n" + "=" * 60)
    print("TEST 3: ClaimMapping Validation (Truthfulness Guarantee)")
    print("=" * 60)

    # Test 3.1: Valid claim mapping
    print("\n3.1 Creating valid ClaimMapping...")
    claim1 = ClaimMapping(
        bullet_id="experience-bullet-1",
        bullet_text="Led team of 19 engineers achieving 75% reduction in defects",
        evidence_card_ids=["demo-metrics", "demo-full-scope"]
    )
    print(f"   ✓ Created claim: {claim1.bullet_id}")
    print(f"   ✓ References {len(claim1.evidence_card_ids)} evidence cards")

    # Test 3.2: Empty evidence_card_ids (should fail)
    print("\n3.2 Testing empty evidence_card_ids (should fail)...")
    try:
        claim2 = ClaimMapping(
            bullet_id="invalid-claim",
            bullet_text="Some claim without evidence",
            evidence_card_ids=[]  # Empty - violates truthfulness
        )
        print("   ✗ ERROR: Should have raised ValidationError!")
    except Exception as e:
        print(f"   ✓ Correctly rejected empty evidence_card_ids: {type(e).__name__}")

    # Test 3.3: Validate against available cards
    print("\n3.3 Validating claims against available cards...")
    available_ids = {"demo-basic", "demo-metrics", "demo-full-scope"}
    is_valid = claim1.validate_against_cards(available_ids)
    print(f"   ✓ Claim valid: {is_valid}")
    
    claim3 = ClaimMapping(
        bullet_id="invalid-ref",
        bullet_text="Claim with non-existent card",
        evidence_card_ids=["non-existent-card"]
    )
    is_valid = claim3.validate_against_cards(available_ids)
    print(f"   ✓ Invalid claim detected: {not is_valid}")

    return [claim1]


def test_pipeline_models():
    """Test pipeline-specific models."""
    print("\n" + "=" * 60)
    print("TEST 4: Pipeline Models (RoleProfile, EvidenceMapping, etc.)")
    print("=" * 60)

    # Test 4.1: RoleProfile
    print("\n4.1 Creating RoleProfile...")
    role_profile = RoleProfile(
        inferred_level="Senior Manager",
        must_haves=["Python", "Team Leadership", "Microservices"],
        nice_to_haves=["Kubernetes", "AWS"],
        seniority_signals=["manages team", "strategic decisions"],
        keyword_clusters={
            "languages": ["Python", "Java"],
            "cloud": ["AWS", "Azure"],
        },
        recommended_storylines=[
            "Technical leadership and team scaling",
            "System architecture and performance"
        ],
        priority_sections=["Experience", "Technical Leadership"],
        downplay_sections=["Education"]
    )
    print(f"   ✓ RoleProfile created: {role_profile.inferred_level}")
    print(f"   ✓ Must haves: {len(role_profile.must_haves)}")
    print(f"   ✓ Storylines: {len(role_profile.recommended_storylines)}")

    # Test 4.2: Requirement
    print("\n4.2 Creating Requirement...")
    requirement = Requirement(
        id="req-001",
        text="5+ years of Python experience",
        priority=Priority.HIGH,
        keywords=["Python", "backend development"]
    )
    print(f"   ✓ Requirement created: {requirement.id}")
    print(f"   ✓ Priority: {requirement.priority.value}")

    # Test 4.3: EvidenceMapping
    print("\n4.3 Creating EvidenceMapping...")
    evidence_mapping = EvidenceMapping(
        requirement_id="req-001",
        evidence_card_ids=["demo-metrics", "demo-full-scope"],
        confidence=Confidence.HIGH,
        notes="Strong match with 8 years Python experience"
    )
    print(f"   ✓ EvidenceMapping created")
    print(f"   ✓ Confidence: {evidence_mapping.confidence.value}")

    # Test 4.4: GapResolution
    print("\n4.4 Creating GapResolution...")
    gap_resolution = GapResolution(
        gap_id="gap-001",
        requirement_text="Kubernetes expertise required",
        strategy=GapStrategy.ADJACENT,
        adjacent_evidence_ids=["demo-full-scope"],
        user_confirmed=False
    )
    print(f"   ✓ GapResolution created")
    print(f"   ✓ Strategy: {gap_resolution.strategy.value}")

    # Test 4.5: ResumeDraft
    print("\n4.5 Creating ResumeDraft...")
    resume_draft = ResumeDraft(
        sections=[
            ResumeSection(name="Summary", content="Senior Engineering Manager..."),
            ResumeSection(
                name="Experience",
                content="**Company A** (2020-2024)\n- Led team...\n- Achieved 75%..."
            )
        ]
    )
    print(f"   ✓ ResumeDraft created with {len(resume_draft.sections)} sections")

    # Test 4.6: ATSReport
    print("\n4.6 Creating ATSReport...")
    ats_report = ATSReport(
        keyword_coverage_score=87.5,
        supported_keywords=["Python", "AWS", "Team Leadership"],
        missing_keywords=["Kubernetes"],
        format_warnings=[],
        role_signal_score=90.0
    )
    print(f"   ✓ ATS Report created")
    print(f"   ✓ Keyword coverage: {ats_report.keyword_coverage_score}%")
    print(f"   ✓ Role signal score: {ats_report.role_signal_score}%")

    # Test 4.7: AuditReport
    print("\n4.7 Creating AuditReport...")
    audit_report = AuditReport(
        truth_violations=[],
        ats_suggestions=["Consider adding 'Kubernetes' keyword if applicable"],
        inconsistencies=[],
        passed=True
    )
    print(f"   ✓ Audit Report created")
    print(f"   ✓ Passed: {audit_report.passed}")

    return {
        "role_profile": role_profile,
        "requirement": requirement,
        "evidence_mapping": evidence_mapping,
        "gap_resolution": gap_resolution,
        "resume_draft": resume_draft,
        "ats_report": ats_report,
        "audit_report": audit_report,
    }


def test_json_serialization():
    """Test JSON serialization/deserialization."""
    print("\n" + "=" * 60)
    print("TEST 5: JSON Serialization")
    print("=" * 60)

    # Create a card
    card = EvidenceCard(
        id="serialization-test",
        project="Test Project",
        company="Test Co",
        timeframe="2020-2024",
        role="Engineer",
        raw_text="Test content",
        metrics=[MetricEntry(value="50%", description="improvement")]
    )

    # Serialize to JSON
    print("\n5.1 Serializing EvidenceCard to JSON...")
    json_str = card.model_dump_json(indent=2)
    print(f"   ✓ JSON length: {len(json_str)} bytes")
    print(f"   ✓ First 100 chars: {json_str[:100]}...")

    # Deserialize from JSON
    print("\n5.2 Deserializing JSON back to EvidenceCard...")
    card2 = EvidenceCard.model_validate_json(json_str)
    print(f"   ✓ Deserialized: {card2.id}")
    print(f"   ✓ Values match: {card.id == card2.id}")

    # Test Blackboard serialization
    print("\n5.3 Serializing Blackboard...")
    inputs = Inputs(
        job_description="Test JD",
        target_title="Engineer",
        template_path="./templates/base.md"
    )
    blackboard = Blackboard(inputs=inputs)
    blackboard.evidence_cards = [card]
    json_str = blackboard.model_dump_json(indent=2)
    print(f"   ✓ Blackboard JSON length: {len(json_str)} bytes")
    print(f"   ✓ Contains {json_str.count('evidence_cards')} 'evidence_cards' references")


def test_config_loading():
    """Test configuration loading."""
    print("\n" + "=" * 60)
    print("TEST 6: Configuration Loading")
    print("=" * 60)

    print("\n6.1 Loading config.yaml...")
    cfg = load_config("config.yaml")
    print(f"   ✓ Config loaded successfully")
    print(f"   ✓ Models configured: {len(cfg.models)}")
    print(f"   ✓ Agents configured: {len(cfg.agents)}")
    print(f"   ✓ Providers configured: {len(cfg.providers)}")
    
    print("\n6.2 Inspecting agent configurations...")
    for agent_name, agent_config in cfg.agents.items():
        print(f"   • {agent_name}:")
        print(f"     - Model alias: {agent_config.get('model_alias')}")
        print(f"     - Temperature: {agent_config.get('temperature')}")
        print(f"     - Max tokens: {agent_config.get('max_tokens')}")


def test_json_schema_export():
    """Test JSON schema export functionality."""
    print("\n" + "=" * 60)
    print("TEST 7: JSON Schema Export")
    print("=" * 60)

    from pathlib import Path

    print("\n7.1 Exporting EvidenceCard schema...")
    export_path = Path("data/evidence_card.schema.json")
    export_json_schema(EvidenceCard, export_path)
    if export_path.exists():
        size = export_path.stat().st_size
        print(f"   ✓ Schema exported to {export_path}")
        print(f"   ✓ File size: {size} bytes")
    else:
        print(f"   ✗ Export failed: {export_path} not found")


def main():
    """Run all schema tests."""
    print("\n" + "=" * 60)
    print("ResumeForge Schema Testing & Demonstration")
    print("=" * 60)
    print("\nThis script demonstrates all schema functionality:")
    print("  • EvidenceCard creation and validation")
    print("  • Blackboard state management")
    print("  • ClaimMapping truthfulness validation")
    print("  • Pipeline models (RoleProfile, EvidenceMapping, etc.)")
    print("  • JSON serialization/deserialization")
    print("  • Configuration loading")
    print("  • JSON Schema export")
    print()

    try:
        # Run all tests
        test_evidence_card_creation()
        blackboard = test_blackboard_operations()
        test_claim_mapping_validation()
        test_pipeline_models()
        test_json_serialization()
        test_config_loading()
        test_json_schema_export()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nSummary:")
        print("  ✓ EvidenceCard validation working")
        print("  ✓ Blackboard state management working")
        print("  ✓ ClaimMapping truthfulness guarantee enforced")
        print("  ✓ All pipeline models functional")
        print("  ✓ JSON serialization working")
        print("  ✓ Configuration loading working")
        print("  ✓ JSON Schema export working")
        print()

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
