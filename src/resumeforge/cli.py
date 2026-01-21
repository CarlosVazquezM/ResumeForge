"""CLI entry point for ResumeForge."""

import json
from pathlib import Path

import click
import structlog
from dotenv import load_dotenv

from resumeforge import __version__
from resumeforge.agents import (
    AuditorAgent,
    EvidenceMapperAgent,
    JDAnalystAgent,
    ResumeWriterAgent,
)
from resumeforge.config import load_config
from resumeforge.exceptions import ConfigError, OrchestrationError, ProviderError, ValidationError
from resumeforge.orchestrator import PipelineOrchestrator
from resumeforge.parsers.fact_resume_parser import FactResumeParser
from resumeforge.providers import create_provider_from_alias
from resumeforge.schemas.blackboard import Blackboard, Inputs, LengthRules

# Load environment variables from .env file
load_dotenv()

# Configure logging (use console renderer for CLI)
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
)

logger = structlog.get_logger(__name__)


def handle_error_interactive(error: Exception, context: dict | None = None, auto_yes: bool = False) -> bool:
    """
    Handle errors interactively, showing details and prompting for retry/cancel.
    
    Args:
        error: The exception that occurred
        context: Optional context dictionary with additional info (e.g., {'step': 'parsing', 'attempt': 1})
        auto_yes: If True, automatically retry without prompting (for --yes flag)
        
    Returns:
        True if user wants to retry, False if they want to cancel
    """
    context = context or {}
    step = context.get('step', 'operation')
    attempt = context.get('attempt', 1)
    
    # Categorize errors
    error_type = type(error).__name__
    error_msg = str(error)
    
    # Determine if error is retryable
    is_retryable = False
    error_category = "Unknown"
    suggestions = []
    
    if isinstance(error, ProviderError):
        error_category = "Provider/Network Error"
        error_lower = error_msg.lower()
        
        if "timeout" in error_lower:
            is_retryable = True
            suggestions = [
                "• The request may have timed out due to network issues",
                "• Very large resumes may take longer than expected",
                "• Try again - timeouts can be transient",
                "• Check your internet connection",
            ]
        elif "rate limit" in error_lower or "429" in error_msg:
            is_retryable = True
            suggestions = [
                "• API rate limit exceeded - wait a moment and try again",
                "• Consider using a different provider if available",
            ]
        elif "api key" in error_lower or "authentication" in error_lower:
            is_retryable = False
            suggestions = [
                "• Check that your API key is set correctly",
                f"• Verify the {context.get('provider', 'provider')} API key in your environment",
            ]
        elif "connection" in error_lower or "network" in error_lower:
            is_retryable = True
            suggestions = [
                "• Network connection issue detected",
                "• Check your internet connection",
                "• Try again in a moment",
            ]
        else:
            is_retryable = True  # Most provider errors are transient
            suggestions = [
                "• This may be a temporary API issue",
                "• Try again - many provider errors are transient",
            ]
    
    elif isinstance(error, ValidationError):
        error_category = "Validation Error"
        is_retryable = False
        suggestions = [
            "• The LLM response may be invalid or malformed",
            "• Check your input format (fact resume or evidence cards)",
            "• The model may have produced unexpected output",
        ]
    
    elif isinstance(error, ConfigError):
        error_category = "Configuration Error"
        is_retryable = False
        suggestions = [
            "• Check your config.yaml file",
            "• Verify all required settings are present",
            "• Ensure model aliases are correctly defined",
        ]
    
    elif isinstance(error, OrchestrationError):
        error_category = "Pipeline Error"
        is_retryable = True  # Pipeline errors might be retryable depending on context
        suggestions = [
            "• The pipeline failed during execution",
            f"• Failed at step: {context.get('current_step', 'unknown')}",
            "• Check the error details above",
        ]
        if context.get('retry_count', 0) > 0:
            suggestions.append(f"• Already retried {context['retry_count']} times")
    
    elif isinstance(error, FileNotFoundError):
        error_category = "File Not Found"
        is_retryable = False
        suggestions = [
            "• Verify the file path is correct",
            "• Check that the file exists",
            "• Ensure you have read permissions",
        ]
    
    else:
        error_category = "Unexpected Error"
        is_retryable = True  # Give user option to retry unexpected errors
        suggestions = [
            "• This is an unexpected error",
            "• Check the error message above for details",
            "• You may want to report this issue",
        ]
    
    # Display error information
    click.echo(f"\n{'='*60}", err=True)
    click.echo(f"❌ Error: {error_category}", err=True)
    click.echo(f"{'='*60}", err=True)
    click.echo(f"\n📋 Details:", err=True)
    click.echo(f"   Step: {step}", err=True)
    if attempt > 1:
        click.echo(f"   Attempt: {attempt}", err=True)
    click.echo(f"   Error Type: {error_type}", err=True)
    click.echo(f"   Message: {error_msg}", err=True)
    
    if suggestions:
        click.echo(f"\n💡 Suggestions:", err=True)
        for suggestion in suggestions:
            click.echo(f"   {suggestion}", err=True)
    
    click.echo(f"\n{'='*60}", err=True)
    
    # Handle retry logic
    if not is_retryable:
        click.echo("\n⚠️  This error is not retryable. Please fix the issue and try again.", err=True)
        return False
    
    if auto_yes:
        click.echo(f"\n🔄 Auto-retrying (--yes flag enabled)...", err=True)
        return True
    
    # Prompt user
    click.echo(f"\n❓ What would you like to do?", err=True)
    click.echo("   [R]etry - Try the operation again", err=True)
    click.echo("   [C]ancel - Exit and fix the issue manually", err=True)
    
    while True:
        choice = click.prompt("   Your choice", default="C", type=click.Choice(["R", "r", "C", "c"], case_sensitive=False), err=True)
        if choice.upper() == "R":
            click.echo("\n🔄 Retrying operation...")
            return True
        elif choice.upper() == "C":
            click.echo("\n❌ Operation cancelled by user.")
            return False


@click.group()
@click.version_option(version=__version__)
def cli():
    """
    ResumeForge: AI-powered resume optimization.
    
    ResumeForge helps you create targeted resumes by analyzing job descriptions
    and matching your experience to requirements using AI-powered evidence mapping.
    
    Commands:
      parse     Parse your fact resume into evidence cards (one-time setup)
      generate  Generate a targeted resume for a specific job description
      diff      Compare two resume variants and show differences
    """
    pass


@cli.command()
@click.option("--fact-resume", "-f", required=True, type=click.Path(exists=True, path_type=Path),
              help="Path to your fact resume file (Markdown or text format). "
                   "This is your master resume containing all your experience and achievements.")
@click.option("--output", "-o", default="./data/evidence_cards.json", type=click.Path(path_type=Path),
              help="Output file path for the generated evidence cards JSON file. "
                   "Defaults to ./data/evidence_cards.json")
@click.option("--config", "-c", default="./config.yaml", type=click.Path(exists=True, path_type=Path),
              help="Path to the configuration file. Defaults to ./config.yaml")
@click.option("--dry-run", is_flag=True, default=False,
              help="Run in dry-run mode: estimate cost without calling the LLM API. "
                   "No API charges will be incurred. Same as --estimate-only.")
@click.option("--estimate-only", is_flag=True, default=False,
              help="Show cost estimation and exit without making API calls. "
                   "Useful for checking costs before running the full parse operation.")
@click.option("--yes", "-y", is_flag=True, default=False,
              help="Skip all confirmation prompts and proceed automatically. "
                   "Useful for automated scripts or when you're confident about the operation.")
def parse(fact_resume: Path, output: Path, config: Path, dry_run: bool, estimate_only: bool, yes: bool):
    """
    Parse fact resume into evidence cards (one-time setup).
    
    This command extracts structured evidence cards from your master fact resume.
    Evidence cards are reusable components that can be matched to different job requirements.
    
    This is a one-time setup step that should be run before generating targeted resumes.
    
    Example:
        resumeforge parse --fact-resume my_resume.md --output evidence_cards.json
    """
    # Initialize attempt counter before try block to avoid UnboundLocalError
    # if exceptions occur before parsing logic
    attempt = 1
    max_attempts = 5  # Reasonable limit to prevent infinite loops
    
    try:
        dry_run_mode = dry_run or estimate_only
        
        click.echo(f"📄 Fact resume: {fact_resume}")
        if not dry_run_mode:
            click.echo(f"💾 Output: {output}")
        
        # Load configuration
        click.echo("⚙️  Loading configuration...")
        cfg = load_config(config)
        
        # Create provider (use mapper_precise for precision parsing)
        click.echo("🤖 Initializing LLM provider...")
        try:
            provider = create_provider_from_alias("mapper_precise", cfg)
        except ConfigError as e:
            click.echo(f"❌ Configuration error: {e}", err=True)
            raise click.Abort()
        
        # Create parser
        parser = FactResumeParser(provider)
        
        # Dry run: estimate cost only
        if dry_run_mode:
            click.echo("💰 Estimating cost (dry run - no API calls)...")
            result = parser.parse(fact_resume, dry_run=True)
            
            cost_est = result["cost_estimation"]
            click.echo(f"\n📊 Cost Estimation:")
            click.echo(f"   Resume size: {result['resume_size_chars']:,} characters")
            click.echo(f"   Input tokens: ~{cost_est['input_tokens']:,}")
            click.echo(f"   Output tokens (est): ~{cost_est['output_tokens']:,}")
            click.echo(f"   Provider: {cost_est['provider']} ({cost_est['model']})")
            click.echo(f"\n💵 Estimated Cost:")
            click.echo(f"   Input:  ${cost_est.get('input_cost_usd', 0):.4f}")
            click.echo(f"   Output: ${cost_est.get('output_cost_usd', 0):.4f}")
            click.echo(f"   Total:  ${cost_est.get('estimated_cost_usd', 0):.4f}")
            
            if cost_est.get('note'):
                click.echo(f"\n⚠️  Note: {cost_est['note']}")
            
            click.echo("\n✅ Dry run complete - no API charges incurred")
            return
        
        # Show cost estimation before proceeding
        click.echo("💰 Estimating cost...")
        cost_est = parser.estimate_cost(fact_resume)
        estimated_cost = cost_est.get('estimated_cost_usd', 0)
        
        click.echo(f"   Estimated cost: ${estimated_cost:.4f}")
        if estimated_cost > 0.10 and not yes:  # Warn if over 10 cents (unless --yes flag)
            click.echo(f"   ⚠️  This will cost approximately ${estimated_cost:.4f}")
            if not click.confirm("   Continue with parsing?", default=True):
                click.echo("❌ Cancelled by user")
                return
        
        # Parse resume with retry logic
        click.echo("🔍 Parsing resume into evidence cards...")
        click.echo("   ⏳ This may take 1-3 minutes for large resumes. Please wait...")
        
        # Reset attempt counter for parsing retry loop
        attempt = 1
        
        while attempt <= max_attempts:
            try:
                evidence_cards = parser.parse(fact_resume, dry_run=False)
                
                # Success - save and exit
                output.parent.mkdir(parents=True, exist_ok=True)
                click.echo(f"💾 Saving {len(evidence_cards)} evidence cards to {output}...")
                with open(output, "w", encoding="utf-8") as f:
                    json.dump(
                        [card.model_dump() for card in evidence_cards],
                        f,
                        indent=2,
                        ensure_ascii=False
                    )
                
                click.echo(f"✅ Successfully parsed {len(evidence_cards)} evidence cards!")
                click.echo(f"📋 Evidence cards saved to: {output}")
                return
                
            except (ProviderError, ValidationError) as e:
                # Use interactive error handler
                should_retry = handle_error_interactive(
                    e,
                    context={
                        'step': 'parsing resume',
                        'attempt': attempt,
                        'provider': 'mapper_precise'
                    },
                    auto_yes=yes
                )
                
                if should_retry and attempt < max_attempts:
                    # User wants to retry and we haven't reached max attempts
                    attempt += 1
                    click.echo(f"\n🔄 Retrying (attempt {attempt}/{max_attempts})...\n")
                    continue
                elif not should_retry:
                    # User chose to cancel (regardless of attempt number)
                    raise click.Abort()
                else:
                    # User wants to retry but we've reached max attempts
                    click.echo(f"\n❌ Maximum retry attempts ({max_attempts}) reached.", err=True)
                    raise click.Abort()
        
    except FileNotFoundError as e:
        handle_error_interactive(e, context={'step': 'file access'}, auto_yes=yes)
        raise click.Abort()
    except ConfigError as e:
        handle_error_interactive(e, context={'step': 'configuration'}, auto_yes=yes)
        raise click.Abort()
    except Exception as e:
        # Catch-all for unexpected errors
        should_retry = handle_error_interactive(
            e,
            context={'step': 'parsing', 'attempt': attempt},
            auto_yes=yes
        )
        if should_retry and attempt < max_attempts:
            # This won't actually retry here since we're in the outer catch,
            # but we've shown the error to the user
            pass
        logger.exception("Unexpected error in parse command")
        raise click.Abort()


@cli.command()
@click.option("--jd", "-j", required=False, type=click.Path(exists=True, path_type=Path),
              help="Path to the job description text file. Required for new runs, "
                   "optional when resuming from checkpoint. If provided when resuming, "
                   "will override the checkpoint's job description and restart from JD analysis.")
@click.option("--title", "-t", required=False,
              help="Target job title for the resume. Required for new runs, "
                   "optional when resuming from checkpoint (will use checkpoint's title if not provided).")
@click.option("--template", default=None, type=click.Path(exists=True, path_type=Path),
              help="Path to a custom resume template file (Markdown format). "
                   "If not provided, uses the default template from config.yaml or a minimal template.")
@click.option("--max-pages", default=2, type=int,
              help="Maximum number of pages for the generated resume. Defaults to 2 pages. "
                   "The pipeline will optimize content to fit within this limit.")
@click.option("--output-dir", "-o", default="./outputs",
              help="Base output directory where resume files will be saved. "
                   "The orchestrator creates a timestamped subdirectory within this path. "
                   "Defaults to ./outputs")
@click.option("--config", "-c", default="./config.yaml", type=click.Path(exists=True, path_type=Path),
              help="Path to the configuration file. Defaults to ./config.yaml")
@click.option("--yes", "-y", is_flag=True, default=False,
              help="Skip all confirmation prompts and proceed automatically. "
                   "Useful for automated scripts or when you're confident about the operation.")
@click.option("--resume-latest", is_flag=True,
              help="Resume from the latest checkpoint for the given job title. "
                   "Requires --title to be specified. If no checkpoint is found, starts from beginning.")
@click.option("--resume-from", type=click.Path(exists=True, path_type=Path),
              help="Resume from a specific checkpoint file. Provide the full path to the checkpoint JSON file. "
                   "Useful when you want to resume from a specific point in time.")
@click.option("--restart", "--no-resume", is_flag=True,
              help="Explicitly ignore any existing checkpoints and restart from the beginning. "
                   "Useful when you want to force a fresh run even if checkpoints exist.")
@click.option("--no-cache", is_flag=True, default=False,
              help="Bypass LLM result cache and force fresh LLM calls. "
                   "Useful when you want to regenerate results even if cached versions exist.")
def generate(jd: Path | None, title: str | None, template: Path | None, max_pages: int, output_dir: str, config: Path, yes: bool, resume_latest: bool, resume_from: Path | None, restart: bool, no_cache: bool):
    """
    Generate a targeted resume for a job description.
    
    This command runs the full ResumeForge pipeline:
    1. Analyzes the job description to extract requirements
    2. Maps your evidence cards to job requirements
    3. Generates a targeted resume draft
    4. Audits the resume for truthfulness and ATS compatibility
    
    The pipeline supports checkpointing - if interrupted, you can resume from where it left off.
    
    Examples:
        # Generate a new resume
        resumeforge generate --jd job.txt --title "Senior Software Engineer"
        
        # Resume from latest checkpoint
        resumeforge generate --resume-latest --title "Senior Software Engineer"
        
        # Resume from specific checkpoint with new job description
        resumeforge generate --resume-from checkpoint.json --jd new_job.txt
    """
    try:
        click.echo("🚀 ResumeForge: Generating targeted resume")
        
        # Load configuration first (needed for checkpoint detection)
        click.echo("⚙️  Loading configuration...")
        try:
            cfg = load_config(config)
        except ConfigError as e:
            handle_error_interactive(e, context={'step': 'configuration'}, auto_yes=yes)
            raise click.Abort()
        
        # Determine checkpoint behavior
        checkpoint_path = None
        # Track if user explicitly provided --jd (for override when resuming)
        jd_explicitly_provided = jd is not None
        
        if resume_from:
            # Resume from specific checkpoint
            checkpoint_path = resume_from
            click.echo(f"📂 Resuming from checkpoint: {checkpoint_path}")
            # Load checkpoint to get job details if not provided
            try:
                with open(checkpoint_path, "r") as f:
                    checkpoint_data = json.load(f)
                # If user provided --jd, use it (will override checkpoint JD in orchestrator)
                # Otherwise, use checkpoint JD if available
                if jd:
                    job_description_text = jd.read_text(encoding="utf-8")
                elif checkpoint_data.get("inputs", {}).get("job_description"):
                    job_description_text = checkpoint_data["inputs"]["job_description"]
                else:
                    click.echo("❌ --jd required when resuming without checkpoint job description", err=True)
                    raise click.Abort()
                if not title:
                    title = checkpoint_data.get("inputs", {}).get("target_title", "")
                    if not title:
                        click.echo("❌ --title required when resuming without checkpoint target_title", err=True)
                        raise click.Abort()
            except Exception as e:
                click.echo(f"❌ Failed to load checkpoint: {e}", err=True)
                raise click.Abort()
        elif resume_latest:
            # Try to find latest checkpoint
            if not title:
                click.echo("❌ --title required when using --resume-latest", err=True)
                raise click.Abort()
            # Create temporary orchestrator to find checkpoint
            from resumeforge.orchestrator import PipelineOrchestrator
            temp_orch = PipelineOrchestrator(cfg, {})
            checkpoint_path = temp_orch._find_latest_checkpoint(title)
            if checkpoint_path:
                click.echo(f"📂 Resuming from latest checkpoint: {checkpoint_path}")
                # Load checkpoint for job details
                try:
                    with open(checkpoint_path, "r") as f:
                        checkpoint_data = json.load(f)
                    # If user provided --jd, use it (will override checkpoint JD in orchestrator)
                    # Otherwise, use checkpoint JD if available
                    if jd:
                        job_description_text = jd.read_text(encoding="utf-8")
                    else:
                        job_description_text = checkpoint_data.get("inputs", {}).get("job_description", "")
                        if not job_description_text:
                            click.echo("❌ --jd required when checkpoint has no job description", err=True)
                            raise click.Abort()
                    # Note: title is already validated as non-empty at line 471-473 when using --resume-latest
                except Exception as e:
                    click.echo(f"⚠️  Could not load checkpoint details: {e}", err=True)
                    if not jd:
                        click.echo("❌ --jd required when checkpoint cannot be loaded", err=True)
                        raise click.Abort()
                    job_description_text = jd.read_text(encoding="utf-8")
            else:
                click.echo("⚠️  No checkpoint found, starting from beginning")
                checkpoint_path = None
                if not jd or not title:
                    click.echo("❌ --jd and --title required when no checkpoint found", err=True)
                    raise click.Abort()
                job_description_text = jd.read_text(encoding="utf-8")
        elif restart:
            # Explicit restart - ignore any checkpoints
            click.echo("🔄 Restarting from beginning (checkpoints ignored)")
            checkpoint_path = None
            if not jd or not title:
                click.echo("❌ --jd and --title required when restarting", err=True)
                raise click.Abort()
            job_description_text = jd.read_text(encoding="utf-8")
        else:
            # Default: Check if checkpoint exists and prompt user
            if not jd or not title:
                click.echo("❌ --jd and --title required", err=True)
                raise click.Abort()
            job_description_text = jd.read_text(encoding="utf-8")
            
            # Check for checkpoint
            from resumeforge.orchestrator import PipelineOrchestrator
            temp_orch = PipelineOrchestrator(cfg, {})
            checkpoint_path = temp_orch._find_latest_checkpoint(title)
            if checkpoint_path:
                try:
                    with open(checkpoint_path, "r") as f:
                        checkpoint_data = json.load(f)
                    metadata = checkpoint_data.get("_checkpoint_metadata", {})
                    checkpoint_time = metadata.get("timestamp", "unknown")
                    checkpoint_state = metadata.get("state", "unknown")
                    
                    click.echo(f"\n💾 Found checkpoint:")
                    click.echo(f"   Step: {checkpoint_state}")
                    click.echo(f"   Time: {checkpoint_time}")
                    if click.confirm("   Resume from checkpoint?", default=True):
                        click.echo("📂 Resuming from checkpoint...")
                    else:
                        click.echo("🔄 Starting from beginning...")
                        checkpoint_path = None
                except Exception as e:
                    click.echo(f"⚠️  Could not read checkpoint: {e}", err=True)
                    checkpoint_path = None
        
        # Display job info (if not resuming, we already have it)
        if not checkpoint_path:
            click.echo(f"📄 Job description: {jd}")
            click.echo(f"🎯 Target title: {title}")
        
        # Determine template path
        if template:
            template_path = str(template)
            if not Path(template_path).exists():
                click.echo(f"⚠️  Template file not found: {template_path}", err=True)
                click.echo("   Writer will use default structure", err=True)
        else:
            # Try default template path from config
            templates_dir = Path(cfg.paths.get("templates", "./data/templates"))
            default_template = templates_dir / "base.md"
            template_path = str(default_template)
            if not default_template.exists():
                click.echo(f"⚠️  Template not found at {template_path}, writer will use default structure")
        
        # Validate job description if not from checkpoint
        if not checkpoint_path:
            if not job_description_text.strip():
                click.echo("❌ Job description file is empty", err=True)
                raise click.Abort()
        
        # Create providers for each agent
        click.echo("🤖 Initializing LLM providers and agents...")
        agents = {}
        
        try:
            # JD Analyst
            click.echo("   • JD Analyst agent...")
            jd_provider = create_provider_from_alias("jd_analyst_default", cfg)
            agents["jd_analyst"] = JDAnalystAgent(
                jd_provider,
                cfg.agents.get("jd_analyst", {})
            )
            
            # Evidence Mapper
            click.echo("   • Evidence Mapper agent...")
            mapper_provider = create_provider_from_alias("mapper_precise", cfg)
            agents["evidence_mapper"] = EvidenceMapperAgent(
                mapper_provider,
                cfg.agents.get("evidence_mapper", {})
            )
            
            # Resume Writer
            click.echo("   • Resume Writer agent...")
            writer_provider = create_provider_from_alias("writer_default", cfg)
            # Use "writer" key to match config.yaml, but store as "resume_writer" for orchestrator compatibility
            agents["resume_writer"] = ResumeWriterAgent(
                writer_provider,
                cfg.agents.get("resume_writer", cfg.agents.get("writer", {}))
            )
            
            # Auditor (combines ATS scorer and Truth auditor)
            click.echo("   • Auditor agent (ATS + Truth)...")
            ats_provider = create_provider_from_alias("ats_scorer_fast", cfg)
            truth_provider = create_provider_from_alias("auditor_deterministic", cfg)
            # Use truth_auditor config as the main config (BaseAgent uses truth_provider)
            agents["auditor"] = AuditorAgent(
                ats_provider,
                truth_provider,
                cfg.agents.get("truth_auditor", {})
            )
            
        except ConfigError as e:
            handle_error_interactive(e, context={'step': 'agent initialization'}, auto_yes=yes)
            raise click.Abort()
        except ProviderError as e:
            handle_error_interactive(e, context={'step': 'agent initialization'}, auto_yes=yes)
            raise click.Abort()
        
        click.echo("✅ All agents initialized")
        
        # Initialize blackboard
        # Note: If resuming, orchestrator will load blackboard from checkpoint,
        # but we still need one here for error handling
        click.echo("📋 Initializing pipeline state...")
        blackboard = Blackboard(
            inputs=Inputs(
                job_description=job_description_text,
                target_title=title,
                length_rules=LengthRules(max_pages=max_pages),
                template_path=template_path
            )
        )
        
        # Update output directory in config (orchestrator will use this)
        cfg.paths["outputs"] = output_dir
        
        # Create orchestrator (pass disable_cache flag to disable caching when --no-cache is set)
        if no_cache:
            click.echo("🔄 Caching disabled (--no-cache flag set)")
        orchestrator = PipelineOrchestrator(cfg, agents, disable_cache=no_cache)
        
        # Run pipeline
        if checkpoint_path:
            click.echo("\n🔄 Resuming pipeline execution...")
            click.echo("   Continuing from checkpoint.\n")
            # If user explicitly provided --jd when resuming, use it to override checkpoint's job description
            # Note: job_description_text already contains the correct value (from jd if provided, else from checkpoint)
            if jd_explicitly_provided:
                click.echo("⚠️  Note: New job description provided - will override checkpoint's job description")
                click.echo("   Pipeline will restart from JD analysis step.\n")
                job_description_override = job_description_text
            else:
                job_description_override = None
        else:
            click.echo("\n🔄 Starting pipeline execution...")
            click.echo("   This may take several minutes depending on job description complexity.\n")
            job_description_override = None
        
        # Define interactive audit failure handler
        def handle_audit_failure_interactive(blackboard: Blackboard) -> str | dict:
            """
            Handle audit failures by prompting the user.
            
            Returns:
                "proceed": User wants to proceed despite violations
                {"action": "add_evidence", "evidence_text": "..."}: User wants to add evidence
                "cancel": User wants to cancel
            """
            if not blackboard.audit_report:
                return "cancel"
            
            click.echo("\n" + "="*70)
            click.echo("⚠️  TRUTH AUDIT FAILED - Violations Found")
            click.echo("="*70)
            
            # Display violations
            if blackboard.audit_report.truth_violations:
                click.echo("\n❌ Truth Violations:")
                for i, violation in enumerate(blackboard.audit_report.truth_violations, 1):
                    click.echo(f"\n   {i}. Bullet: {violation.bullet_id}")
                    click.echo(f"      Text: {violation.bullet_text[:100]}..." if len(violation.bullet_text) > 100 else f"      Text: {violation.bullet_text}")
                    click.echo(f"      Issue: {violation.violation}")
            
            # Display inconsistencies
            if blackboard.audit_report.inconsistencies:
                click.echo("\n⚠️  Inconsistencies:")
                for i, inconsistency in enumerate(blackboard.audit_report.inconsistencies, 1):
                    click.echo(f"   {i}. {inconsistency}")
            
            # Prompt user
            click.echo("\n" + "-"*70)
            click.echo("What would you like to do?")
            click.echo("   [P] Proceed anyway (accept violations and continue)")
            click.echo("   [A] Add evidence and re-run (add fact, then re-run pipeline from evidence mapping)")
            click.echo("   [N] Add evidence and proceed (add fact, but continue without re-running)")
            click.echo("   [C] Cancel (stop the pipeline)")
            click.echo("-"*70)
            
            choice = click.prompt(
                "   Your choice",
                default="C",
                type=click.Choice(["P", "p", "A", "a", "N", "n", "C", "c"], case_sensitive=False),
                err=True
            ).upper()
            
            if choice == "P":
                click.echo("\n✅ Proceeding despite violations...")
                return "proceed"
            elif choice == "A":
                click.echo("\n📝 Please provide the evidence/fact that supports the claim:")
                click.echo("   (This will be added as a new evidence card and pipeline will re-run)")
                evidence_text = click.prompt("   Evidence text", type=str)
                if evidence_text.strip():
                    click.echo(f"\n✅ Adding evidence and re-running pipeline...")
                    click.echo(f"   Evidence: {evidence_text[:100]}..." if len(evidence_text) > 100 else f"   Evidence: {evidence_text}")
                    return {"action": "add_evidence", "evidence_text": evidence_text.strip()}
                else:
                    click.echo("\n❌ Empty evidence text provided, cancelling...")
                    return "cancel"
            elif choice == "N":
                click.echo("\n📝 Please provide the evidence/fact that supports the claim:")
                click.echo("   (This will be added as a new evidence card but pipeline will continue)")
                evidence_text = click.prompt("   Evidence text", type=str)
                if evidence_text.strip():
                    click.echo(f"\n✅ Adding evidence and proceeding...")
                    click.echo(f"   Evidence: {evidence_text[:100]}..." if len(evidence_text) > 100 else f"   Evidence: {evidence_text}")
                    return {"action": "add_evidence_and_proceed", "evidence_text": evidence_text.strip()}
                else:
                    click.echo("\n❌ Empty evidence text provided, cancelling...")
                    return "cancel"
            else:  # C or default
                click.echo("\n❌ Cancelling pipeline...")
                return "cancel"
        
        try:
            result = orchestrator.run(
                blackboard, 
                resume_from=checkpoint_path, 
                job_description_override=job_description_override,
                audit_failure_handler=handle_audit_failure_interactive
            )
            
            # Success!
            click.echo("\n✅ Pipeline completed successfully!")
            click.echo(f"📊 Final state: {result.current_step}")
            
            # Show summary
            # Display ATS report independently (if available)
            if result.ats_report:
                click.echo(f"\n📊 ATS Report:")
                click.echo(f"   Keyword coverage: {result.ats_report.keyword_coverage_score:.1f}%")
                click.echo(f"   Role signal score: {result.ats_report.role_signal_score:.1f}%")
            
            # Display audit report independently (if available)
            if result.audit_report:
                click.echo(f"\n📈 Audit Results:")
                click.echo(f"   Truth violations: {len(result.audit_report.truth_violations)}")
                click.echo(f"   Audit passed: {'✅ Yes' if result.audit_report.passed else '❌ No'}")
            
            if result.resume_draft:
                click.echo(f"\n📄 Resume generated:")
                click.echo(f"   Sections: {len(result.resume_draft.sections)}")
                if result.claim_index:
                    click.echo(f"   Claims mapped: {len(result.claim_index)}")
            
            if result.selected_evidence_ids:
                click.echo(f"\n🎯 Evidence used:")
                click.echo(f"   Evidence cards selected: {len(result.selected_evidence_ids)}")
            
            # Output directory is created by orchestrator with timestamp
            # We can't easily get the exact path here, but we can show where outputs go
            click.echo(f"\n💾 Outputs saved to: {output_dir}/<timestamped-directory>/")
            click.echo("   Files generated:")
            click.echo("   • resume.md - Resume in markdown format")
            click.echo("   • resume.docx - Resume in DOCX format (if generator implemented)")
            click.echo("   • evidence_used.json - Selected evidence card IDs")
            click.echo("   • claim_index.json - Claim-to-evidence mappings")
            click.echo("   • ats_report.json - ATS compatibility report")
            click.echo("   • audit_report.json - Truth audit results")
            
        except OrchestrationError as e:
            # Use the orchestrator's stored blackboard (which reflects the actual pipeline state)
            # This is especially important when resuming from checkpoint, as the original
            # blackboard created before resuming doesn't reflect the checkpoint state
            error_blackboard = orchestrator._current_blackboard if orchestrator._current_blackboard else blackboard
            
            # Build context with pipeline details from the actual blackboard used
            context = {
                'step': 'pipeline execution',
                'current_step': error_blackboard.current_step,
                'retry_count': error_blackboard.retry_count,
            }
            
            # Add truth violations to context if available
            if error_blackboard.audit_report and error_blackboard.audit_report.truth_violations:
                context['truth_violations'] = len(error_blackboard.audit_report.truth_violations)
                # Show truth violations before error handler
                click.echo(f"\n⚠️  Truth violations found:", err=True)
                for violation in error_blackboard.audit_report.truth_violations[:5]:
                    click.echo(f"   • {violation.bullet_id}: {violation.violation}", err=True)
                if len(error_blackboard.audit_report.truth_violations) > 5:
                    click.echo(f"   ... and {len(error_blackboard.audit_report.truth_violations) - 5} more", err=True)
            
            # Show error details (pipeline errors are usually not retryable at CLI level
            # since orchestrator handles internal retries)
            handle_error_interactive(e, context=context, auto_yes=yes)
            raise click.Abort()
        
    except FileNotFoundError as e:
        handle_error_interactive(e, context={'step': 'file access'}, auto_yes=yes)
        raise click.Abort()
    except ConfigError as e:
        handle_error_interactive(e, context={'step': 'configuration'}, auto_yes=yes)
        raise click.Abort()
    except ProviderError as e:
        handle_error_interactive(e, context={'step': 'pipeline execution'}, auto_yes=yes)
        raise click.Abort()
    except ValidationError as e:
        handle_error_interactive(e, context={'step': 'validation'}, auto_yes=yes)
        raise click.Abort()
    except KeyboardInterrupt:
        click.echo("\n⚠️  Pipeline interrupted by user", err=True)
        raise click.Abort()
    except Exception as e:
        handle_error_interactive(e, context={'step': 'pipeline execution'}, auto_yes=yes)
        logger.exception("Unexpected error in generate command")
        raise click.Abort()


@cli.command()
@click.option("--variant1", "-v1", required=True, type=click.Path(exists=True, path_type=Path),
              help="Path to the first resume variant. Can be a directory (containing resume files) "
                   "or a single file (Markdown or DOCX format).")
@click.option("--variant2", "-v2", required=True, type=click.Path(exists=True, path_type=Path),
              help="Path to the second resume variant. Can be a directory (containing resume files) "
                   "or a single file (Markdown or DOCX format). Must match the format of variant1.")
def diff(variant1: Path, variant2: Path):
    """
    Compare two resume variants and show differences.
    
    This command analyzes two resume versions and highlights the differences between them.
    Useful for reviewing changes between iterations or comparing different targeting strategies.
    
    Example:
        resumeforge diff --variant1 outputs/resume1.md --variant2 outputs/resume2.md
    """
    try:
        from resumeforge.utils.diff import generate_diff
        
        click.echo("🔍 Comparing resume variants...")
        click.echo(f"   Variant 1: {variant1}")
        click.echo(f"   Variant 2: {variant2}")
        click.echo()
        
        diff_text = generate_diff(variant1, variant2)
        click.echo(diff_text)
        
    except FileNotFoundError as e:
        click.echo(f"❌ File not found: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Error generating diff: {e}", err=True)
        logger.exception("Error in diff command")
        raise click.Abort()


@cli.group()
def cache():
    """Cache management commands for LLM result caching."""
    pass


@cache.command("clear")
@click.option("--agent", help="Clear cache for specific agent only (e.g., 'jd_analyst', 'evidence_mapper')")
@click.option("--config", "-c", default="./config.yaml", type=click.Path(exists=True, path_type=Path),
              help="Path to the configuration file. Defaults to ./config.yaml")
@click.option("--yes", "-y", is_flag=True, default=False,
              help="Skip confirmation prompt")
def cache_clear(agent: str | None, config: Path, yes: bool):
    """
    Clear LLM result cache.
    
    This command clears cached LLM results to force fresh API calls on the next run.
    Useful when you want to regenerate results even if cached versions exist.
    
    Examples:
        # Clear all caches
        resumeforge cache clear
        
        # Clear cache for specific agent
        resumeforge cache clear --agent jd_analyst
    """
    try:
        from resumeforge.utils.cache import get_llm_cache
        from resumeforge.config import load_config
        
        cfg = load_config(config)
        cache = get_llm_cache(cfg.model_dump() if hasattr(cfg, "model_dump") else {})
        
        if agent:
            if not yes:
                if not click.confirm(f"Clear cache for agent '{agent}'?", default=True):
                    click.echo("Cancelled")
                    return
            cache.clear(agent)
            click.echo(f"✅ Cache cleared for agent: {agent}")
        else:
            if not yes:
                if not click.confirm("Clear all LLM result caches?", default=True):
                    click.echo("Cancelled")
                    return
            cache.clear()
            click.echo("✅ All LLM result caches cleared")
            
    except Exception as e:
        click.echo(f"❌ Error clearing cache: {e}", err=True)
        logger.exception("Error in cache clear command")
        raise click.Abort()


@cache.command("stats")
@click.option("--config", "-c", default="./config.yaml", type=click.Path(exists=True, path_type=Path),
              help="Path to the configuration file. Defaults to ./config.yaml")
def cache_stats(config: Path):
    """
    Show cache statistics.
    
    Displays information about cached entries, cache size, and hit rates.
    """
    try:
        from resumeforge.utils.cache import get_llm_cache
        from resumeforge.config import load_config
        from pathlib import Path
        
        cfg = load_config(config)
        cache = get_llm_cache(cfg.model_dump() if hasattr(cfg, "model_dump") else {})
        
        # Get cache backend to inspect
        backend = cache.backend
        
        click.echo("📊 Cache Statistics")
        click.echo("=" * 50)
        
        # Check if backend is FileCacheBackend
        from resumeforge.utils.cache import FileCacheBackend
        if isinstance(backend, FileCacheBackend):
            # File cache backend
            if hasattr(backend, 'cache_dir'):
                cache_dir = Path(backend.cache_dir)
                if cache_dir.exists():
                    cache_files = list(cache_dir.glob("*.json"))
                    click.echo(f"Cache directory: {cache_dir}")
                    click.echo(f"Total cache entries: {len(cache_files)}")
                    
                    # Group by agent
                    agents = {}
                    for cache_file in cache_files:
                        # Extract agent name from filename (format: {agent}-{hash}.json)
                        parts = cache_file.stem.split("-", 1)
                        if len(parts) >= 2:
                            agent_name = parts[0]
                            agents[agent_name] = agents.get(agent_name, 0) + 1
                    
                    if agents:
                        click.echo("\nCache entries by agent:")
                        for agent, count in sorted(agents.items()):
                            click.echo(f"   {agent}: {count} entries")
                else:
                    click.echo(f"Cache directory does not exist: {cache_dir}")
            else:
                click.echo("Cache backend: Unknown type")
        else:
            click.echo(f"Cache backend: {type(backend).__name__}")
            click.echo("Statistics not available for this backend type")
        
    except Exception as e:
        click.echo(f"❌ Error getting cache stats: {e}", err=True)
        logger.exception("Error in cache stats command")
        raise click.Abort()


if __name__ == "__main__":
    cli()
