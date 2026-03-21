"""Rich console UI — streaming log output with live status footer."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from kresearch.models.mind_map import MindMap
from kresearch.providers.types import ModelInfo

BANNER = r"""
  ██╗  ██╗██████╗ ███████╗███████╗███████╗ █████╗ ██████╗  ██████╗██╗  ██╗
  ██║ ██╔╝██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██║  ██║
  █████╔╝ ██████╔╝█████╗  ███████╗█████╗  ███████║██████╔╝██║     ███████║
  ██╔═██╗ ██╔══██╗██╔══╝  ╚════██║██╔══╝  ██╔══██║██╔══██╗██║     ██╔══██║
  ██║  ██╗██║  ██║███████╗███████║███████╗██║  ██║██║  ██║╚██████╗██║  ██║
  ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝"""

ICONS = {
    "web_search": "🔍", "read_webpage": "📄", "execute_python": "💻",
    "update_findings": "📝", "log_contradiction": "⚠️ ",
    "spawn_subagent": "🤖", "draft_report": "📋", "thinking": "🧠",
    "result": "📊", "status": "📌",
}


class ConsoleUI:
    """Streams research activity as permanent log lines users can scroll back."""

    def __init__(self) -> None:
        self.console = Console()
        self._query = ""
        self._iteration = 0
        self._sources = 0

    def show_banner(self, provider: str, model: str) -> None:
        self.console.print(Text(BANNER, style="bold cyan"))
        self.console.print("  [dim]Autonomous Deep Research Agent[/dim]")
        self.console.print(f"  {'─' * 40}")
        self.console.print(
            f"  Provider: [bold green]{provider}[/bold green]  │  "
            f"Model: [bold green]{model}[/bold green]\n"
        )

    def show_models_table(self, models: list[ModelInfo], default: str) -> None:
        table = Table(title="Available Models", border_style="cyan", show_lines=True)
        table.add_column("Model ID", style="white", min_width=30)
        table.add_column("Display Name", style="dim")
        table.add_column("Context", justify="right", style="green")
        for m in models:
            mid = f"● {m.id} [yellow](default)[/yellow]" if m.id == default else f"  {m.id}"
            table.add_row(mid, m.name, f"{m.context_window:,}" if m.context_window else "—")
        self.console.print(table)

    def show_config_table(self, config_data: dict) -> None:
        table = Table(title="Current Configuration", border_style="cyan", show_lines=True)
        table.add_column("Setting", style="bold white", min_width=25)
        table.add_column("Value", style="green")
        table.add_column("Source", style="dim")
        for key, (val, source) in config_data.items():
            table.add_row(key, "********" if "key" in key.lower() and val else str(val), source)
        self.console.print(table)

    # --- UIProtocol methods (async) ---

    async def start_research(self, query: str) -> None:
        self._query = query
        self.console.print(Panel(
            f'[bold]{query}[/bold]', title="Research Query", border_style="cyan",
        ))
        self.console.print('[dim]Type a message to redirect, or "stop" to finish early[/dim]\n')

    async def log_action(self, tool: str, desc: str, status: str = "done",
                         elapsed: float | None = None) -> None:
        icon = ICONS.get(tool, "⚙️ ")
        mark = "[green]✓[/green]" if status == "done" else "[red]✗[/red]"
        time_str = f"  [dim]{elapsed:.1f}s[/dim]" if elapsed is not None else ""
        self.console.print(f"  {icon} {desc}  {mark}{time_str}")

    async def log_thinking(self, text: str) -> None:
        if not text or len(text.strip()) < 5:
            return
        snippet = text.strip()
        if len(snippet) > 500:
            snippet = snippet[:497] + "..."
        self.console.print(f"\n  🧠 [italic]{snippet}[/italic]\n")

    async def log_result_summary(self, tool: str, result: dict) -> None:
        summary = _summarize_result(tool, result)
        if summary:
            self.console.print(f"     [dim]→ {summary}[/dim]")

    def log_iteration(self, iteration: int, sources: int, tokens: int) -> None:
        self._iteration, self._sources = iteration, sources
        self.console.print(
            f"\n  {'─' * 50}\n  📌 Iteration {iteration}  │  "
            f"Sources: {sources}  │  Tokens: ~{tokens // 1000}K\n  {'─' * 50}\n")

    def update_mind_map_display(self, mind_map: MindMap) -> None:
        pass  # Mind map updates are shown via update_findings log lines

    async def update_stats(self, iteration: int, sources: int, tokens: int) -> None:
        self.log_iteration(iteration, sources, tokens)

    async def show_report(self, text: str) -> None:
        self.console.print("\n")
        self.console.print(Panel("[bold green]Research Complete[/bold green]", border_style="green"))
        self.console.print(text)

    async def show_total_time(self, elapsed: float, state: object) -> None:
        mins, secs = int(elapsed // 60), int(elapsed % 60)
        time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
        t = state.token_usage.input_tokens + state.token_usage.output_tokens  # type: ignore[attr-defined]
        self.console.print(
            f"\n  [bold cyan]Total research time: {time_str}[/bold cyan]  │  "
            f"Sources: {state.mind_map.source_count()}  │  "  # type: ignore[attr-defined]
            f"Iterations: {state.iteration}  │  Tokens: ~{t // 1000}K\n")  # type: ignore[attr-defined]

    async def stop(self) -> None:
        pass  # No Live panel to stop

    async def print(self, msg: str, **kw: object) -> None:
        self.console.print(msg, **kw)


def _summarize_result(tool: str, result: dict) -> str:
    if "error" in result:
        return f"[red]Error: {result['error'][:100]}[/red]"
    if tool == "web_search":
        count = result.get("count", 0)
        titles = [r.get("title", "")[:50] for r in result.get("results", [])[:3]]
        return f"{count} results: {', '.join(titles)}" if titles else f"{count} results"
    if tool == "read_webpage":
        title = result.get("title", "")[:60]
        chars = result.get("char_count", len(result.get("content", "")))
        return f'"{title}" ({chars:,} chars)' if title else f"({chars:,} chars)"
    if tool == "execute_python":
        out = result.get("stdout", "").strip()[:100]
        return f"Output: {out}" if out else "Executed (no output)"
    if tool == "update_findings":
        return result.get("summary", "")[:100] if "summary" in result else "Findings recorded"
    if tool == "log_contradiction":
        return f"{result.get('contradictions_count', '?')} contradictions logged"
    if tool == "draft_report":
        return "Mind map data returned — writing final report..."
    if tool == "spawn_subagent":
        sc = result.get("sources_count", 0)
        return f"Sub-agent finished ({sc} sources)"
    return ""
