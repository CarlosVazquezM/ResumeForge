"""CLI entry point for ResumeForge."""

import json
from pathlib import Path

import click
import structlog
from dotenv import load_dotenv

from resumeforge import __version__
from resumeforge.config import load_config
from resumeforge.exceptions import ConfigError, ProviderError, ValidationError
from resumeforge.parsers.fact_resume_parser import FactResumeParser
from resumeforge.providers import create_provider_from_alias

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
        
        # Parse resume
        click.echo("🔍 Parsing resume into evidence cards...")
        evidence_cards = parser.parse(fact_resume, dry_run=False)
        
        # Ensure output directory exists
        output.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to JSON
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
        
    except FileNotFoundError as e:
        click.echo(f"❌ File not found: {e}", err=True)
        raise click.Abort()
    except ConfigError as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        raise click.Abort()
    except ProviderError as e:
        click.echo(f"❌ Provider error: {e}", err=True)
        click.echo("💡 Make sure your API keys are set in the environment.", err=True)
        raise click.Abort()
    except ValidationError as e:
        click.echo(f"❌ Validation error: {e}", err=True)
        click.echo("💡 The LLM response may be invalid. Check your fact resume format.", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        logger.exception("Unexpected error in parse command")
        raise click.Abort()


@cli.command()
@click.option("--jd", "-j", required=True, type=click.Path(exists=True),
              help="Path to job description (text file)")
@click.option("--title", "-t", required=True,
              help="Target job title")
@click.option("--output-dir", "-o", default="./outputs",
              help="Output directory")
@click.option("--config", "-c", default="./config.yaml",
              help="Configuration file")
def generate(jd: str, title: str, output_dir: str, config: str):
    """Generate a targeted resume for a job description."""
    click.echo(f"Generating resume for: {title}")
    click.echo(f"Job description: {jd}")
    click.echo(f"Output directory: {output_dir}")
    click.echo("⚠️  Not yet implemented")


if __name__ == "__main__":
    cli()
