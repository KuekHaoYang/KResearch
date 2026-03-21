"""Output formatting and console UI."""

from kresearch.output.console import ConsoleUI
from kresearch.output.markdown import ensure_citations, format_source_list, save_report
from kresearch.output.protocol import UIProtocol

__all__ = ["ConsoleUI", "UIProtocol", "ensure_citations", "format_source_list", "save_report"]
