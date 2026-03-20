"""Sandboxed Python code execution tool."""

from __future__ import annotations

import asyncio
import subprocess

from kresearch.providers.types import ToolDeclaration

EXECUTE_PYTHON_DECLARATION = ToolDeclaration(
    name="execute_python",
    description=(
        "Execute Python code in a sandboxed subprocess. "
        "Use for calculations, data processing, or verification. "
        "The code runs with a 30-second timeout and restricted env."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute.",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default 30).",
            },
        },
        "required": ["code"],
    },
)


async def handle_execute_python(args: dict, **_ctx) -> dict:
    """Run Python code in a subprocess with timeout."""
    code = args.get("code", "")
    timeout = args.get("timeout", 30)

    def _run():
        try:
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={"PATH": "/usr/bin:/usr/local/bin"},
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Execution timed out after {timeout}s",
                "returncode": -1,
            }

    return await asyncio.to_thread(_run)
