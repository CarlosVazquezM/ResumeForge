"""CLI entry point for ResumeForge."""

import click

from resumeforge import __version__


@click.group()
@click.version_option(version=__version__)
def cli():
    """ResumeForge: AI-powered resume optimization."""
    pass


@cli.command()
@click.option("--fact-resume", "-f", required=True, type=click.Path(exists=True),
              help="Path to fact resume (Markdown)")
@click.option("--output", "-o", default="./data/evidence_cards.json",
              help="Output path for evidence cards")
def parse(fact_resume: str, output: str):
    """Parse fact resume into evidence cards (one-time setup)."""
    click.echo(f"Parsing fact resume: {fact_resume}")
    click.echo(f"Output: {output}")
    click.echo("⚠️  Not yet implemented")


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
