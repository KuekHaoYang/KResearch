"""Rich console UI — banner, live research panel, model table."""

from __future__ import annotations

from rich.console import Console
from rich.live import Live
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


class ConsoleUI:
    """Rich-based terminal UI for KResearch."""

    def __init__(self) -> None:
        self.console = Console()
        self._live: Live | None = None
        self._actions: list[tuple[str, str, str]] = []
        self._mind_map_text = ""
        self._stats = ""
        self._query = ""

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
        table.add_column("Context Window", justify="right", style="green")
        for m in models:
            mid = f"● {m.id} [yellow](default)[/yellow]" if m.id == default else f"  {m.id}"
            ctx = f"{m.context_window:,} tokens" if m.context_window else "—"
            table.add_row(mid, m.name, ctx)
        self.console.print(table)

    def start_research(self, query: str) -> None:
        self._query = query
        self._actions = []
        self._mind_map_text = ""
        self._stats = ""
        self._live = Live(
            self._build_panel(), console=self.console, refresh_per_second=4,
        )
        self._live.start()

    def log_action(self, tool: str, desc: str, status: str = "done") -> None:
        icons = {
            "web_search": "🔍", "read_webpage": "📄",
            "execute_python": "💻", "update_findings": "📝",
            "log_contradiction": "⚠️ ", "spawn_subagent": "🤖",
            "draft_report": "📋",
        }
        icon = icons.get(tool, "⚙️ ")
        mark = "✓" if status == "done" else ("✗" if status == "error" else "⠋")
        self._actions.append((icon, desc, mark))
        self._refresh()

    def update_mind_map_display(self, mind_map: MindMap) -> None:
        self._mind_map_text = mind_map.get_summary()
        self._refresh()

    def update_stats(self, iteration: int, sources: int, tokens: int) -> None:
        self._stats = (
            f"Iteration: {iteration}  │  Sources: {sources}  │  "
            f"Tokens: ~{tokens // 1000}K"
        )
        self._refresh()

    def _refresh(self) -> None:
        if self._live:
            self._live.update(self._build_panel())

    def _build_panel(self) -> Panel:
        parts: list[str] = []
        for icon, desc, mark in self._actions[-10:]:
            parts.append(f"  {icon} {desc}  {mark}")
        if self._mind_map_text:
            parts.append(f"\n  {'─' * 20} Mind Map {'─' * 20}")
            for line in self._mind_map_text.split("\n"):
                parts.append(f"  {line}")
        if self._stats:
            parts.append(f"\n  {self._stats}")
        parts.append('\n  [dim]Type a message to redirect, or "stop" to finish early[/dim]')
        body = "\n".join(parts)
        return Panel(body, title=f'Researching: "{self._query}"', border_style="cyan")

    def show_report(self, text: str) -> None:
        self.console.print("\n")
        self.console.print(text)

    def stop(self) -> None:
        if self._live:
            self._live.stop()
            self._live = None

    def print(self, msg: str, **kw) -> None:
        self.console.print(msg, **kw)
