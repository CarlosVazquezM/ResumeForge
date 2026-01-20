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
    """ResumeForge: AI-powered resume optimization."""
    pass


@cli.command()
@click.option("--fact-resume", "-f", required=True, type=click.Path(exists=True, path_type=Path),
              help="Path to fact resume (Markdown or text)")
@click.option("--output", "-o", default="./data/evidence_cards.json", type=click.Path(path_type=Path),
              help="Output path for evidence cards")
@click.option("--config", "-c", default="./config.yaml", type=click.Path(exists=True, path_type=Path),
              help="Configuration file path")
@click.option("--dry-run", is_flag=True, default=False,
              help="Estimate cost without calling LLM (no API charges)")
@click.option("--estimate-only", is_flag=True, default=False,
              help="Show cost estimation and exit (same as --dry-run)")
@click.option("--yes", "-y", is_flag=True, default=False,
              help="Skip confirmation prompt and proceed automatically")
def parse(fact_resume: Path, output: Path, config: Path, dry_run: bool, estimate_only: bool, yes: bool):
    """Parse fact resume into evidence cards (one-time setup)."""
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
@click.option("--jd", "-j", required=True, type=click.Path(exists=True, path_type=Path),
              help="Path to job description (text file)")
@click.option("--title", "-t", required=True,
              help="Target job title")
@click.option("--template", default=None, type=click.Path(exists=True, path_type=Path),
              help="Path to resume template (Markdown). Defaults to config path or minimal template")
@click.option("--max-pages", default=2, type=int,
              help="Maximum pages for resume (default: 2)")
@click.option("--output-dir", "-o", default="./outputs",
              help="Output directory (orchestrator creates timestamped subdirectory)")
@click.option("--config", "-c", default="./config.yaml", type=click.Path(exists=True, path_type=Path),
              help="Configuration file")
@click.option("--yes", "-y", is_flag=True, default=False,
              help="Skip confirmation prompts and proceed automatically")
def generate(jd: Path, title: str, template: Path | None, max_pages: int, output_dir: str, config: Path, yes: bool):
    """Generate a targeted resume for a job description."""
    try:
        click.echo("🚀 ResumeForge: Generating targeted resume")
        click.echo(f"📄 Job description: {jd}")
        click.echo(f"🎯 Target title: {title}")
        
        # Load configuration
        click.echo("⚙️  Loading configuration...")
        try:
            cfg = load_config(config)
        except ConfigError as e:
            click.echo(f"❌ Configuration error: {e}", err=True)
            raise click.Abort()
        
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
        
        # Read job description
        click.echo("📖 Reading job description...")
        try:
            with open(jd, "r", encoding="utf-8") as f:
                job_description_text = f.read()
        except Exception as e:
            click.echo(f"❌ Failed to read job description: {e}", err=True)
            raise click.Abort()
        
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
        
        # Create orchestrator
        orchestrator = PipelineOrchestrator(cfg, agents)
        
        # Run pipeline
        click.echo("\n🔄 Starting pipeline execution...")
        click.echo("   This may take several minutes depending on job description complexity.\n")
        
        try:
            result = orchestrator.run(blackboard)
            
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
            # Build context with pipeline details
            context = {
                'step': 'pipeline execution',
                'current_step': blackboard.current_step,
                'retry_count': blackboard.retry_count,
            }
            
            # Add truth violations to context if available
            if blackboard.audit_report and blackboard.audit_report.truth_violations:
                context['truth_violations'] = len(blackboard.audit_report.truth_violations)
                # Show truth violations before error handler
                click.echo(f"\n⚠️  Truth violations found:", err=True)
                for violation in blackboard.audit_report.truth_violations[:5]:
                    click.echo(f"   • {violation.bullet_id}: {violation.violation}", err=True)
                if len(blackboard.audit_report.truth_violations) > 5:
                    click.echo(f"   ... and {len(blackboard.audit_report.truth_violations) - 5} more", err=True)
            
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
              help="Path to first resume variant (directory or file)")
@click.option("--variant2", "-v2", required=True, type=click.Path(exists=True, path_type=Path),
              help="Path to second resume variant (directory or file)")
def diff(variant1: Path, variant2: Path):
    """Compare two resume variants and show differences."""
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


if __name__ == "__main__":
    cli()
