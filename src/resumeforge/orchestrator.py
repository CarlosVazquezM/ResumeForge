"""Pipeline orchestrator for ResumeForge."""

import json
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Callable, TYPE_CHECKING

import structlog

from resumeforge.exceptions import OrchestrationError
from resumeforge.schemas.blackboard import Blackboard
from resumeforge.schemas.evidence_card import EvidenceCard
from resumeforge.utils.cache import load_evidence_cards_cached
from resumeforge.utils.metrics import PerformanceMetrics, timed_operation

if TYPE_CHECKING:
    from resumeforge.agents.base import BaseAgent
    from resumeforge.config import Config

# Configure structured logging
logger = structlog.get_logger(__name__)


class PipelineState(Enum):
    """Pipeline execution states."""

    INIT = auto()
    PREPROCESSING = auto()
    JD_ANALYSIS = auto()
    EVIDENCE_MAPPING = auto()
    WRITING = auto()
    AUDITING = auto()
    REVISION = auto()
    COMPLETE = auto()
    FAILED = auto()


class StateTransition:
    """Defines a state transition with condition and action."""

    def __init__(
        self,
        from_state: PipelineState,
        to_state: PipelineState,
        condition: Callable[[Blackboard], bool] = lambda _: True,
    ):
        """
        Initialize state transition.
        
        Args:
            from_state: Source state
            to_state: Target state
            condition: Condition function that takes blackboard and returns bool
        """
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition


# Define valid state transitions
TRANSITIONS = [
    StateTransition(PipelineState.INIT, PipelineState.PREPROCESSING),
    StateTransition(PipelineState.PREPROCESSING, PipelineState.JD_ANALYSIS),
    StateTransition(PipelineState.JD_ANALYSIS, PipelineState.EVIDENCE_MAPPING),
    StateTransition(PipelineState.EVIDENCE_MAPPING, PipelineState.WRITING),
    StateTransition(PipelineState.WRITING, PipelineState.AUDITING),
    StateTransition(
        PipelineState.AUDITING,
        PipelineState.COMPLETE,
        condition=lambda b: b.audit_report is not None and b.audit_report.passed,
    ),
    StateTransition(
        PipelineState.AUDITING,
        PipelineState.REVISION,
        condition=lambda b: (
            b.audit_report is not None
            and not b.audit_report.passed
            and b.retry_count < b.max_retries
        ),
    ),
    StateTransition(
        PipelineState.AUDITING,
        PipelineState.FAILED,
        condition=lambda b: (
            b.audit_report is not None
            and not b.audit_report.passed
            and b.retry_count >= b.max_retries
        ),
    ),
    StateTransition(PipelineState.REVISION, PipelineState.WRITING),
]


class PipelineOrchestrator:
    """Orchestrates the multi-agent resume generation pipeline."""

    def __init__(self, config: "Config", agents: dict[str, "BaseAgent"]):
        """
        Initialize orchestrator with configuration and agents.
        
        Args:
            config: Configuration object (from load_config)
            agents: Dictionary mapping agent names to agent instances
        """
        self.config = config
        self.agents = agents
        self.logger = logger.bind(orchestrator="PipelineOrchestrator")
        self.metrics = PerformanceMetrics()

    def run(self, blackboard: Blackboard) -> Blackboard:
        """
        Execute the full pipeline using state machine.
        
        Args:
            blackboard: Initial blackboard state
            
        Returns:
            Updated blackboard with pipeline results
            
        Raises:
            OrchestrationError: If pipeline fails or invalid state transition
        """
        self.metrics.start_pipeline()
        state = PipelineState.INIT
        self.logger.info("Pipeline started", initial_state=state.name)

        while state not in (PipelineState.COMPLETE, PipelineState.FAILED):
            self.logger.info(
                "Pipeline state transition",
                state=state.name,
                step=blackboard.current_step,
                retry_count=blackboard.retry_count,
            )
            blackboard.current_step = state.name.lower()

            try:
                # Execute current state's action
                blackboard = self._execute_state(state, blackboard)

                # Validate state before transitioning
                is_valid, errors = blackboard.validate_state()
                if not is_valid:
                    self.logger.error(
                        "Blackboard validation failed",
                        state=state.name,
                        errors=errors,
                    )
                    state = PipelineState.FAILED
                    blackboard.current_step = "failed"
                    break

                # Find valid transition
                next_state = self._get_next_state(state, blackboard)
                if next_state is None:
                    self.logger.error(
                        "No valid transition found",
                        current_state=state.name,
                    )
                    state = PipelineState.FAILED
                    blackboard.current_step = "failed"
                    break

                state = next_state

            except Exception as e:
                self.logger.exception(
                    "Error executing state",
                    state=state.name,
                    error=str(e),
                )
                state = PipelineState.FAILED
                blackboard.current_step = "failed"
                break

        if state == PipelineState.COMPLETE:
            self.metrics.end_pipeline()
            self.logger.info("Pipeline completed successfully")
            blackboard.current_step = "complete"
            self.metrics.log_summary()
            self._save_outputs(blackboard)
        elif state == PipelineState.FAILED:
            self.metrics.end_pipeline()
            self.logger.error("Pipeline failed", final_step=blackboard.current_step)
            self.metrics.log_summary()
            raise OrchestrationError(
                f"Pipeline failed at step: {blackboard.current_step}"
            )

        return blackboard

    def _execute_state(
        self, state: PipelineState, blackboard: Blackboard
    ) -> Blackboard:
        """
        Execute the action for the current state.
        
        Args:
            state: Current pipeline state
            blackboard: Current blackboard state
            
        Returns:
            Updated blackboard after state execution
        """
        if state == PipelineState.PREPROCESSING:
            return self._preprocess(blackboard)

        elif state == PipelineState.JD_ANALYSIS:
            agent = self.agents.get("jd_analyst")
            if not agent:
                raise OrchestrationError("JD Analyst agent not found")
            self.logger.info("Executing JD Analyst agent")
            # Attach metrics to blackboard for agent to record (using setattr to avoid Pydantic validation)
            blackboard.__dict__["performance_metrics"] = self.metrics
            with timed_operation("JD Analysis"):
                result = agent.execute(blackboard)
            return result

        elif state == PipelineState.EVIDENCE_MAPPING:
            agent = self.agents.get("evidence_mapper")
            if not agent:
                raise OrchestrationError("Evidence Mapper agent not found")
            
            # Pre-filter evidence cards if JD analysis is complete (token optimization)
            if blackboard.role_profile:
                # Extract keywords from role profile
                jd_keywords = []
                if blackboard.role_profile.keyword_clusters:
                    for cluster in blackboard.role_profile.keyword_clusters.values():
                        jd_keywords.extend(cluster)
                jd_keywords.extend(blackboard.role_profile.must_haves)
                jd_keywords.extend(blackboard.role_profile.nice_to_haves)
                
                # Filter evidence cards before sending to Evidence Mapper
                original_count = len(blackboard.evidence_cards)
                blackboard.evidence_cards = self._filter_relevant_evidence_cards(
                    blackboard.evidence_cards, jd_keywords
                )
                if len(blackboard.evidence_cards) < original_count:
                    self.logger.info(
                        "Evidence cards pre-filtered for Evidence Mapper",
                        original=original_count,
                        filtered=len(blackboard.evidence_cards),
                    )
            
            self.logger.info("Executing Evidence Mapper agent")
            # Attach metrics to blackboard for agent to record
            blackboard.__dict__["performance_metrics"] = self.metrics
            with timed_operation("Evidence Mapping"):
                return agent.execute(blackboard)

        elif state == PipelineState.WRITING:
            agent = self.agents.get("resume_writer") or self.agents.get("writer")
            if not agent:
                raise OrchestrationError("Resume Writer agent not found")
            self.logger.info("Executing Resume Writer agent")
            # Attach metrics to blackboard for agent to record
            blackboard.__dict__["performance_metrics"] = self.metrics
            with timed_operation("Resume Writing"):
                return agent.execute(blackboard)

        elif state == PipelineState.AUDITING:
            # Try both "auditor" and "truth_auditor" keys for compatibility
            agent = self.agents.get("auditor") or self.agents.get("truth_auditor")
            if not agent:
                raise OrchestrationError(
                    "Auditor agent not found. Expected key 'auditor' or 'truth_auditor' in agents dict."
                )
            self.logger.info("Executing Auditor agent")
            # Attach metrics to blackboard for agent to record
            blackboard.__dict__["performance_metrics"] = self.metrics
            with timed_operation("Auditing"):
                return agent.execute(blackboard)

        elif state == PipelineState.REVISION:
            blackboard.retry_count += 1
            self.logger.info(
                "Preparing revision",
                retry_count=blackboard.retry_count,
                max_retries=blackboard.max_retries,
            )
            return self._prepare_revision(blackboard)

        elif state == PipelineState.INIT:
            # Initial state, no action needed
            return blackboard

        else:
            # COMPLETE, FAILED - no action
            return blackboard

    def _get_next_state(
        self, current: PipelineState, blackboard: Blackboard
    ) -> PipelineState | None:
        """
        Find the next valid state based on conditions.
        
        Args:
            current: Current pipeline state
            blackboard: Current blackboard state
            
        Returns:
            Next valid state, or None if no valid transition
        """
        for transition in TRANSITIONS:
            if transition.from_state == current:
                if transition.condition(blackboard):
                    return transition.to_state

        return None

    def _preprocess(self, blackboard: Blackboard) -> Blackboard:
        """
        Load evidence cards and build synonyms map.
        
        Args:
            blackboard: Current blackboard state
            
        Returns:
            Updated blackboard with evidence cards and synonyms map
        """
        self.logger.info("Preprocessing: loading evidence cards and building synonyms")

        # Load evidence cards from file
        evidence_path_str = self.config.paths.get("evidence_cards", "./data/evidence_cards.json")
        evidence_path = Path(evidence_path_str)
        
        # Update max_retries from config if available (with type validation)
        if "max_retries" in self.config.pipeline:
            max_retries_value = self.config.pipeline["max_retries"]
            try:
                # Convert to int if it's a string, or validate if it's already an int
                blackboard.max_retries = int(max_retries_value)
                if blackboard.max_retries < 0:
                    raise ValueError("max_retries must be non-negative")
            except (ValueError, TypeError) as e:
                raise OrchestrationError(
                    f"Invalid max_retries value in config.pipeline: {max_retries_value!r}. "
                    f"Expected a non-negative integer, got {type(max_retries_value).__name__}. "
                    f"Error: {e}"
                ) from e

        # Load evidence cards using cache
        try:
            with timed_operation("Evidence Cards Loading"):
                blackboard.evidence_cards = load_evidence_cards_cached(evidence_path)
            self.logger.info(
                "Evidence cards loaded",
                count=len(blackboard.evidence_cards),
            )
        except OrchestrationError:
            # Re-raise OrchestrationError without wrapping (preserves specific error messages)
            raise
        except Exception as e:
            raise OrchestrationError(
                f"Error loading evidence cards: {e}"
            ) from e

        # Build synonyms map
        blackboard.synonyms_map = self._build_synonyms(blackboard)
        self.logger.info(
            "Synonyms map built",
            synonym_count=len(blackboard.synonyms_map),
        )

        return blackboard
    
    def _filter_relevant_evidence_cards(
        self,
        all_cards: list[EvidenceCard],
        jd_keywords: list[str] | None = None,
    ) -> list[EvidenceCard]:
        """
        Filter evidence cards that might be relevant to JD keywords.
        
        This pre-filtering reduces token usage by only sending potentially
        relevant cards to the Evidence Mapper agent.
        
        Args:
            all_cards: All available evidence cards
            jd_keywords: List of keywords extracted from JD (if available)
            
        Returns:
            Filtered list of potentially relevant evidence cards
        """
        if not jd_keywords:
            # If no keywords available yet, return all cards (filtering will happen later)
            return all_cards
        
        # Normalize keywords for matching (lowercase)
        jd_keywords_lower = [kw.lower() for kw in jd_keywords if kw]
        
        if not jd_keywords_lower:
            return all_cards
        
        relevant = []
        for card in all_cards:
            # Build searchable text from card
            card_text_parts = [
                card.project.lower(),
                card.raw_text.lower(),
                " ".join(card.skills).lower(),
                " ".join(card.leadership_signals).lower(),
                card.role.lower(),
            ]
            card_text = " ".join(card_text_parts)
            
            # Check if any JD keyword appears in card text
            # Simple substring matching (could be enhanced with fuzzy matching)
            if any(kw in card_text for kw in jd_keywords_lower):
                relevant.append(card)
        
        # Guard against empty input to prevent division by zero
        if len(all_cards) == 0:
            return relevant
        
        # If filtering too aggressive (less than 20% of cards), return all
        # This prevents over-filtering that might miss relevant cards
        if len(relevant) < len(all_cards) * 0.2:
            self.logger.warning(
                "Evidence filtering too aggressive, returning all cards",
                filtered_count=len(relevant),
                total_count=len(all_cards),
            )
            return all_cards
        
        self.logger.info(
            "Evidence cards filtered",
            original_count=len(all_cards),
            filtered_count=len(relevant),
            reduction_percent=round((1 - len(relevant) / len(all_cards)) * 100, 1),
        )
        
        return relevant

    def _build_synonyms(self, blackboard: Blackboard) -> dict[str, list[str]]:
        """
        Build terminology normalization map.
        
        Currently uses rule-based synonyms. Can be extended with LLM-assisted
        synonym discovery in the future.
        
        Args:
            blackboard: Current blackboard state
            
        Returns:
            Dictionary mapping terms to lists of synonyms
        """
        # Rule-based synonyms (extend as needed)
        # These help the Evidence Mapper recognize equivalent terms
        base_synonyms = {
            "HCM": ["HRIS", "HR systems", "human capital management"],
            "CI/CD": [
                "continuous integration",
                "continuous deployment",
                "DevOps pipelines",
            ],
            "microservices": ["distributed systems", "service-oriented architecture"],
            "ETL": ["data pipelines", "data integration", "data processing"],
            "Kubernetes": ["k8s", "container orchestration"],
            "AWS": ["Amazon Web Services", "Amazon cloud"],
            "GCP": ["Google Cloud Platform", "Google Cloud"],
            "Azure": ["Microsoft Azure"],
        }

        # TODO: Could extend with LLM-assisted synonym discovery based on
        # job description terminology and evidence card skills

        return base_synonyms

    def _prepare_revision(self, blackboard: Blackboard) -> Blackboard:
        """
        Prepare context for revision based on audit failures.
        
        Extracts truth violations from audit report and adds revision
        instructions to the change_log for the Resume Writer to address.
        
        Args:
            blackboard: Current blackboard state with audit report
            
        Returns:
            Updated blackboard with revision instructions
        """
        if not blackboard.audit_report:
            self.logger.warning("No audit report available for revision")
            return blackboard

        violations = blackboard.audit_report.truth_violations

        if not violations:
            self.logger.warning(
                "Revision requested but no truth violations found",
                audit_passed=blackboard.audit_report.passed,
            )
            return blackboard

        # Add revision instructions to blackboard
        revision_instructions = []
        revision_instructions.append(
            f"REVISION ATTEMPT {blackboard.retry_count} of {blackboard.max_retries}"
        )
        revision_instructions.append(
            "The following truth violations must be fixed:"
        )

        for v in violations:
            revision_instructions.append(
                f"FIX REQUIRED: Bullet '{v.bullet_id}' - {v.violation}"
            )
            revision_instructions.append(f"  Problematic text: {v.bullet_text}")

        # Also include ATS suggestions if any
        if blackboard.audit_report.ats_suggestions:
            revision_instructions.append("\nATS Optimization Suggestions:")
            for suggestion in blackboard.audit_report.ats_suggestions:
                revision_instructions.append(f"  - {suggestion}")

        blackboard.change_log.extend(revision_instructions)

        self.logger.info(
            "Revision instructions prepared",
            violation_count=len(violations),
            retry_count=blackboard.retry_count,
        )

        return blackboard

    def _save_outputs(self, blackboard: Blackboard) -> None:
        """
        Save all pipeline outputs to versioned folder.
        
        Creates output directory with timestamp and saves:
        - evidence_used.json
        - claim_index.json
        - ats_report.json
        - audit_report.json
        - resume.docx (via DocxGenerator)
        - diff_from_base.md (if base resume exists)
        
        Args:
            blackboard: Final blackboard state
        """
        # Create output directory
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        # Sanitize target title for directory name
        safe_title = "".join(
            c if c.isalnum() or c in ("-", "_") else "-"
            for c in blackboard.inputs.target_title.lower()
        )
        safe_title = safe_title.replace(" ", "-")[:50]  # Limit length

        output_base_dir = Path(
            self.config.paths.get("outputs", "./outputs")
        )
        output_dir = output_base_dir / f"{safe_title}-{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info("Saving outputs", output_dir=str(output_dir))

        # Save JSON outputs
        self._save_json(
            output_dir / "evidence_used.json",
            blackboard.selected_evidence_ids,
        )

        if blackboard.claim_index:
            self._save_json(
                output_dir / "claim_index.json",
                [claim.model_dump() for claim in blackboard.claim_index],
            )

        if blackboard.ats_report:
            self._save_json(
                output_dir / "ats_report.json",
                blackboard.ats_report.model_dump(),
            )

        if blackboard.audit_report:
            self._save_json(
                output_dir / "audit_report.json",
                blackboard.audit_report.model_dump(),
            )

        # Save resume markdown for diffing
        if blackboard.resume_draft:
            self._save_resume_markdown(output_dir / "resume.md", blackboard)

        # Generate DOCX (if generator is implemented)
        if blackboard.resume_draft:
            try:
                from resumeforge.generators.docx_generator import DocxGenerator

                docx_gen = DocxGenerator()
                docx_path = output_dir / "resume.docx"
                docx_gen.generate(blackboard, docx_path)
                self.logger.info("DOCX generated", path=str(docx_path))
            except NotImplementedError:
                self.logger.warning("DOCX generator not yet implemented")
            except Exception as e:
                self.logger.warning(
                    "Failed to generate DOCX",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Generate diff (if base resume template exists)
        if blackboard.resume_draft and blackboard.inputs.template_path:
            template_path = Path(blackboard.inputs.template_path)
            if template_path.exists():
                try:
                    from resumeforge.utils.diff import generate_diff
                    
                    resume_md_path = output_dir / "resume.md"
                    if resume_md_path.exists():
                        diff_text = generate_diff(resume_md_path, template_path)
                        diff_path = output_dir / "diff_from_base.md"
                        diff_path.write_text(diff_text, encoding="utf-8")
                        self.logger.info("Diff generated", path=str(diff_path))
                except Exception as e:
                    self.logger.warning(
                        "Failed to generate diff",
                        error=str(e),
                        error_type=type(e).__name__,
                    )

        self.logger.info("All outputs saved", output_dir=str(output_dir))

    def _save_json(self, file_path: Path, data: dict | list) -> None:
        """
        Save data as JSON file.
        
        Args:
            file_path: Path to save JSON file
            data: Data to serialize (dict or list)
        """
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            self.logger.warning(
                "Failed to save JSON file",
                file_path=str(file_path),
                error=str(e),
            )

    def _save_resume_markdown(self, file_path: Path, blackboard: Blackboard) -> None:
        """
        Save resume draft as markdown file.
        
        Args:
            file_path: Path to save markdown file
            blackboard: Blackboard with resume draft
        """
        if not blackboard.resume_draft:
            return

        try:
            with open(file_path, "w") as f:
                for section in blackboard.resume_draft.sections:
                    f.write(f"# {section.name}\n\n")
                    f.write(f"{section.content}\n\n")
        except Exception as e:
            self.logger.warning(
                "Failed to save resume markdown",
                file_path=str(file_path),
                error=str(e),
            )
