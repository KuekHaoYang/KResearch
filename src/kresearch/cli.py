"""CLI entry point for KResearch."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from kresearch.config import KResearchConfig
from kresearch.output.console import ConsoleUI
from kresearch.output.markdown import save_report


@click.command()
@click.argument("query", required=False)
@click.option("--model", default=None, help="Override the default model.")
@click.option("--fast-model", default=None, help="Override the fast model.")
@click.option("--provider", default=None, help="LLM provider (gemini, openai, ...).")
@click.option("--proxy", default=None, help="HTTP proxy URL.")
@click.option("--list-models", is_flag=True, help="List available models and exit.")
@click.option("--verbose", is_flag=True, help="Enable verbose logging.")
@click.option("--output", "-o", type=click.Path(), help="Save report to file.")
@click.option("--max-iterations", type=int, help="Max agent loop iterations (0=unlimited).")
def main(
    query: str | None,
    model: str | None,
    fast_model: str | None,
    provider: str | None,
    proxy: str | None,
    list_models: bool,
    verbose: bool,
    output: str | None,
    max_iterations: int | None,
) -> None:
    """KResearch - Autonomous Deep Research Agent."""
    overrides: dict = {}
    if model:
        overrides["model"] = model
    if fast_model:
        overrides["fast_model"] = fast_model
    if provider:
        overrides["provider"] = provider
    if proxy:
        overrides["proxy"] = proxy
    if verbose:
        overrides["verbose"] = True
    if max_iterations is not None:
        overrides["max_iterations"] = max_iterations

    config = KResearchConfig(**overrides)
    console = ConsoleUI()

    from kresearch.providers import get_provider

    try:
        prov = get_provider(config)
    except Exception as e:
        console.print(f"[red]Error initialising provider: {e}[/red]")
        raise SystemExit(1)

    if list_models:
        console.show_banner(config.provider, config.model)
        try:
            models = prov.list_models()
        except Exception as e:
            console.print(f"[red]Failed to list models: {e}[/red]")
            raise SystemExit(1)
        console.show_models_table(models, config.model)
        return

    if not query:
        console.show_banner(config.provider, config.model)
        console.print("[yellow]Usage: kresearch \"your research query\"[/yellow]")
        console.print("       kresearch --list-models")
        return

    console.show_banner(config.provider, config.model)

    from kresearch.orchestrator import Orchestrator
    from kresearch.tools.registry import create_default_registry

    registry = create_default_registry()
    orchestrator = Orchestrator(config, prov, registry, console)

    try:
        report = asyncio.run(orchestrator.run(query))
    except KeyboardInterrupt:
        console.stop()
        console.print("\n[yellow]Research interrupted by user.[/yellow]")
        return

    console.show_report(report)

    if output:
        path = save_report(report, Path(output))
        console.print(f"\n[green]Report saved to {path}[/green]")


if __name__ == "__main__":
    main()
