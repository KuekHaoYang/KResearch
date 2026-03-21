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
@click.option("--config", "show_config", is_flag=True, help="Show all configuration.")
@click.option("--verbose", is_flag=True, help="Enable verbose logging.")
@click.option("--output", "-o", type=click.Path(), help="Save report to file.")
@click.option("--max-iterations", type=int, help="Max agent iterations (0=unlimited).")
def main(query, model, fast_model, provider, proxy, list_models, show_config,
         verbose, output, max_iterations):
    """KResearch - Autonomous Deep Research Agent."""
    overrides = _build_overrides(model, fast_model, provider, proxy, verbose, max_iterations)
    cfg = KResearchConfig(**overrides)
    console = ConsoleUI()

    if show_config:
        console.show_banner(cfg.provider, cfg.model)
        _show_config(cfg, overrides, console)
        return

    from kresearch.providers import get_provider
    try:
        prov = get_provider(cfg)
    except Exception as e:
        console.print(f"[red]Error initialising provider: {e}[/red]")
        raise SystemExit(1)

    if list_models:
        console.show_banner(cfg.provider, cfg.model)
        try:
            models = prov.list_models()
        except Exception as e:
            console.print(f"[red]Failed to list models: {e}[/red]")
            raise SystemExit(1)
        console.show_models_table(models, cfg.model)
        return

    if not query:
        console.show_banner(cfg.provider, cfg.model)
        console.print("[yellow]Usage: kresearch \"your research query\"[/yellow]")
        console.print("       kresearch --list-models")
        console.print("       kresearch --config")
        return

    console.show_banner(cfg.provider, cfg.model)
    from kresearch.orchestrator import Orchestrator
    from kresearch.tools.registry import create_default_registry
    registry = create_default_registry()
    orchestrator = Orchestrator(cfg, prov, registry, console)
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


def _show_config(cfg: KResearchConfig, overrides: dict, console: ConsoleUI) -> None:
    data = {}
    for name in cfg.model_fields:
        if name == "model_config":
            continue
        val = getattr(cfg, name, None)
        default = cfg.model_fields[name].default
        source = "CLI" if name in overrides else ("env / .env" if val != default else "default")
        data[name] = (val, source)
    console.show_config_table(data)


def _build_overrides(model, fast_model, provider, proxy, verbose, max_iterations):
    o: dict = {}
    if model:
        o["model"] = model
    if fast_model:
        o["fast_model"] = fast_model
    if provider:
        o["provider"] = provider
    if proxy:
        o["proxy"] = proxy
    if verbose:
        o["verbose"] = True
    if max_iterations is not None:
        o["max_iterations"] = max_iterations
    return o


if __name__ == "__main__":
    main()
