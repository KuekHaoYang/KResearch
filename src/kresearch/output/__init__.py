"""Output formatting and console UI."""

from kresearch.output.console import ConsoleUI
from kresearch.output.markdown import ensure_citations, format_source_list, save_report

__all__ = ["ConsoleUI", "ensure_citations", "format_source_list", "save_report"]
