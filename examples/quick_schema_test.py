"""Quick schema testing script for interactive exploration.

Run this to quickly test schema functionality.
Usage: python examples/quick_schema_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from resumeforge.schemas import EvidenceCard, MetricEntry, Blackboard, Inputs, ClaimMapping
from resumeforge.config import load_config


def quick_test():
    """Quick test of core schema functionality."""
    print("=" * 60)
    print("Quick Schema Test")
    print("=" * 60)
    
    # 1. Create an EvidenceCard
    print("\n1. Creating EvidenceCard...")
    card = EvidenceCard(
        id="test-card",
        project="My Project",
        company="My Company",
        timeframe="2020-2024",
        role="Engineer",
        metrics=[
            MetricEntry(value="50%", description="improvement", context="Q1")
        ],
        skills=["Python", "Docker"],
        raw_text="Led development..."
    )
    print(f"   ✓ Created: {card.id}")
    print(f"   ✓ Metrics: {card.get_metrics_summary()}")
    print(f"   ✓ Skills: {card.get_skills_summary()}")
    
    # 2. Create a Blackboard
    print("\n2. Creating Blackboard...")
    inputs = Inputs(
        job_description="Looking for engineer...",
        target_title="Senior Engineer",
        template_path="./templates/base.md"
    )
    blackboard = Blackboard(inputs=inputs)
    blackboard.evidence_cards = [card]
    blackboard.selected_evidence_ids = [card.id]
    
    selected = blackboard.get_selected_evidence_cards()
    print(f"   ✓ Blackboard created")
    print(f"   ✓ Selected {len(selected)} evidence cards")
    
    # 3. Create a ClaimMapping
    print("\n3. Creating ClaimMapping...")
    claim = ClaimMapping(
        bullet_id="bullet-1",
        bullet_text="Led team achieving 50% improvement",
        evidence_card_ids=[card.id]
    )
    print(f"   ✓ Claim created: {claim.bullet_id}")
    print(f"   ✓ References {len(claim.evidence_card_ids)} evidence card(s)")
    
    # 4. Load config
    print("\n4. Loading config...")
    cfg = load_config("config.yaml")
    print(f"   ✓ Config loaded: {len(cfg.agents)} agents configured")
    
    # 5. Validate state
    print("\n5. Validating Blackboard state...")
    blackboard.claim_index = [claim]
    is_valid, errors = blackboard.validate_state()
    print(f"   ✓ State valid: {is_valid}")
    if errors:
        print(f"   ✓ Errors: {errors}")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        quick_test()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
