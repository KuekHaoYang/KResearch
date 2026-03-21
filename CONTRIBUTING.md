# Contributing to KResearch

Thank you for considering a contribution to KResearch. This document explains the project's architecture in enough detail that you can orient yourself, add a new provider or tool, or modify the agent loop without guesswork.

---

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Code Conventions](#code-conventions)
- [Understanding the Agent Loop](#understanding-the-agent-loop)
- [Adding a New Provider](#adding-a-new-provider)
- [Adding a New Tool](#adding-a-new-tool)
- [Modifying the System Prompt](#modifying-the-system-prompt)
- [Data Models](#data-models)
- [Testing](#testing)
- [Pull Request Guidelines](#pull-request-guidelines)

---

## Development Setup

### Prerequisites

- Python 3.10+
- A Gemini API key for integration testing (`export GOOGLE_API_KEY=...`)

### Install

```bash
git clone https://github.com/yourname/kresearch.git
cd kresearch
pip install -e ".[dev]"
```

This installs the package in editable mode with dev dependencies: `pytest`, `pytest-asyncio`, `ruff`, `mypy`.

### Verify

```bash
# Run the linter
ruff check src/

# Run type checking
mypy src/

# Run tests
pytest

# Verify CLI works
kresearch --help
```

---

## Project Structure

```
src/kresearch/
├── cli.py                   # Click CLI entry point — parses args, builds config,
│                            #   creates provider, launches orchestrator
├── config.py                # KResearchConfig (Pydantic Settings) — loads from
│                            #   env vars, .env file, and CLI overrides
├── prompts.py               # SYSTEM_TEMPLATE — the ~7K-char system prompt that
│                            #   defines the agent's research methodology, tool
│                            #   usage guide, citation rules, and report format
├── orchestrator.py          # Orchestrator class — the autonomous agent loop
│                            #   with interrupt monitoring, batch function
│                            #   responses, budget enforcement, and finalization
│
├── models/
│   ├── mind_map.py          # MindMap (hierarchical tree), MindMapNode, Source,
│   │                        #   Contradiction — the agent's persistent memory
│   ├── task_graph.py        # TaskGraph, TaskNode, TaskStatus — tracks sub-tasks
│   │                        #   spawned by the agent (pending/running/completed)
│   └── state.py             # ResearchState — the top-level mutable session state
│                            #   containing mind_map, task_graph, iteration count,
│                            #   token usage, action log, and draft_requested flag
│
├── providers/
│   ├── __init__.py          # get_provider(config) factory — dynamically imports
│   │                        #   and instantiates the configured provider class
│   ├── base.py              # ProviderInterface (ABC) and ChatSession (ABC) —
│   │                        #   the contracts every provider must implement
│   ├── types.py             # Provider-agnostic types: Message, GenerateResponse,
│   │                        #   FunctionCall, ModelInfo, ToolDeclaration
│   ├── gemini/
│   │   ├── provider.py      # GeminiProvider — wraps google-genai SDK; handles
│   │   │                    #   tool declaration conversion, response parsing,
│   │   │                    #   thinking config, proxy support, model listing
│   │   └── chat.py          # GeminiChatSession — multi-turn chat with proper
│   │                        #   batch function-response support (sends all tool
│   │                        #   results in a single message)
│   ├── openai/
│   │   ├── provider.py      # OpenaiProvider — wraps openai SDK; handles tool
│   │   │                    #   declaration conversion, response parsing with
│   │   │                    #   tool_call_id tracking, proxy support
│   │   └── chat.py          # OpenaiChatSession — multi-turn chat with proper
│   │                        #   batch tool results (multiple role=tool messages)
│   ├── custom/
│   │   └── provider.py      # CustomProvider — subclass of OpenaiProvider with
│   │                        #   custom base_url for OpenAI-compatible endpoints
│   ├── anthropic/__init__.py
│   ├── xai/__init__.py
│   └── perplexity/__init__.py
│
├── tools/
│   ├── registry.py          # ToolRegistry (register/execute/get_declarations)
│   │                        #   + create_default_registry() that wires all tools
│   ├── web_search.py        # DuckDuckGo search via ddgs library
│   ├── web_reader.py        # trafilatura extraction + httpx/bs4 fallback
│   ├── code_executor.py     # Sandboxed subprocess Python execution
│   ├── research_tools.py    # update_findings, log_contradiction, draft_report
│   │                        #   — tools that modify the MindMap state
│   └── subagent_tool.py     # spawn_subagent — creates a new ChatSession and
│                            #   runs a mini 5-iteration research loop
│
└── output/
    ├── console.py           # ConsoleUI — Rich-based terminal UI (ASCII banner,
    │                        #   live progress panel, model table, report display)
    ├── protocol.py          # UIProtocol — async display contract implemented by
    │                        #   both ConsoleUI and WebUI
    └── markdown.py          # Post-processing: ensure_citations(), format_source_list(),
                             #   save_report()

├── web/                     # Optional Web UI (pip install -e ".[web]")
│   ├── __init__.py          # Exports create_app
│   ├── app.py               # Starlette ASGI app factory + entry point
│   ├── models.py            # Pydantic models for WebSocket events and REST responses
│   ├── webui.py             # WebUI — UIProtocol over WebSocket (JSON events)
│   ├── db.py                # aiosqlite storage for past research reports
│   ├── session.py           # ResearchSession + SessionManager
│   ├── routes.py            # REST endpoints (/api/config, /api/reports, /api/health)
│   ├── ws.py                # WebSocket endpoint (/ws) for real-time streaming
│   └── static/index.html    # Single-page frontend (vanilla JS, dark theme)
```

---

## Code Conventions

### File size limit

Every `.py` file must be **150 lines or fewer**. This is a hard constraint enforced during review. If a file grows beyond this, split it into focused modules. The system prompt is the longest single string in the project (~136 lines in `prompts.py`) and is exempt from the "code logic" line count only because it is a data constant.

### Style

- **Formatter/linter:** `ruff` (configured at 100 chars line length, Python 3.10 target).
- **Type checker:** `mypy` in strict mode.
- **Async everywhere:** All I/O-bound code uses `asyncio`. Blocking calls (ddgs, trafilatura, subprocess) are wrapped in `asyncio.to_thread()`.
- **Pydantic models:** All data structures use Pydantic `BaseModel` with type annotations.
- **No hardcoded model IDs** outside `config.py` defaults and provider `DEFAULT_MODEL`/`FAST_MODEL` constants.

### Naming

- Tool handlers: `handle_<tool_name>(args: dict, **ctx) -> dict`
- Tool declarations: `<TOOL_NAME>_DECLARATION: ToolDeclaration`
- Provider classes: `<Name>Provider(ProviderInterface)`
- Chat session classes: `<Name>ChatSession(ChatSession)`

### Error handling

- Tool handlers must **never raise**. They catch exceptions internally and return `{"error": "..."}`. The `ToolRegistry.execute()` wrapper also catches uncaught exceptions as a safety net.
- Provider errors (invalid API key, network failure) propagate up and are caught by the CLI.

---

## Understanding the Agent Loop

The core logic lives in `Orchestrator` (`orchestrator.py`). Here is the exact control flow:

### `Orchestrator.run(query)`

1. Create `ResearchState` from the query.
2. Build the system prompt from `SYSTEM_TEMPLATE`, injecting the current mind map state.
3. Create a `ChatSession` via `provider.create_chat()`, passing the system prompt and all tool declarations.
4. Start the Rich live panel.
5. Start the stdin monitor task (`_monitor_input`).
6. Call `_agent_loop()`.
7. On exit (success or exception): cancel the input monitor, stop the live panel.

### `Orchestrator._agent_loop(chat, state, input_queue)`

1. Send the initial message: `"Research this thoroughly: {query}"`.
2. Enter an infinite loop:
   - Check `input_queue` for user interrupts.
   - Call `_process_response()` on the LLM's latest response.
   - If `_process_response()` returns a string, that is the final report — return it.
   - If the iteration budget is exceeded, call `_finalize()` to force a report.
   - Otherwise, increment iteration and update the UI.

### `Orchestrator._process_response(response, state, chat)`

1. Track token usage from `response.usage`.
2. **If no function calls:**
   - If `state.draft_requested` is `True` and the response has text → return it (this is the report).
   - If the response text is >500 chars → return it (the agent wrote the report without calling `draft_report()` explicitly).
   - Otherwise → return `None` (continue the loop).
3. **If function calls are present:**
   - Execute ALL calls via `ToolRegistry.execute()`, collecting `(name, result)` pairs.
   - Log each action to the UI and the `state.actions_log`.
   - Send all results back in one batch via `chat.send_function_responses()`.
   - If `state.draft_requested` and the response has text → return it.
   - If the response has more function calls → **recurse** (handle them immediately).
   - Otherwise → return `None`.

### `Orchestrator._finalize(response, state, chat)`

A fallback loop (max 5 rounds) that keeps processing tool calls and prompting until the agent produces final text. Used when:
- The user typed `stop`.
- The iteration budget was hit.

This ensures the user always gets a report, even if the agent is mid-tool-call when interrupted.

---

## Adding a New Provider

This is the most common extension. Here is a concrete walkthrough — see `providers/openai/` and `providers/gemini/` for fully working examples.

### Step 1: Create the provider module

```
src/kresearch/providers/openai/
├── __init__.py       # from .provider import OpenaiProvider
├── provider.py       # OpenaiProvider(ProviderInterface)
└── chat.py           # OpenaiChatSession(ChatSession)
```

### Step 2: Implement `ProviderInterface`

In `provider.py`, implement all abstract methods. The key mapping:

| Our interface | OpenAI SDK equivalent |
|---|---|
| `generate()` | `client.chat.completions.create()` |
| `generate_stream()` | `client.chat.completions.create(stream=True)` |
| `create_chat()` | Return an `OpenaiChatSession` that manages message history |
| `list_models()` | `client.models.list()` |

You must convert:
- `ToolDeclaration` → the provider's function-calling format (e.g., OpenAI's `tools` parameter).
- The provider's response → `GenerateResponse` (extract `text`, `function_calls`, `usage`).

### Step 3: Implement `ChatSession`

In `chat.py`, implement `send()`, `send_function_response()`, and override `send_function_responses()` if the provider supports batch function results in a single message.

**Critical:** When the model returns multiple function calls, the orchestrator executes all of them and calls `send_function_responses()` with all results. If your provider requires them sent individually, the base class default handles that — but batch sending is more correct.

### Step 4: Register the provider

In `src/kresearch/providers/__init__.py`, add to `PROVIDER_REGISTRY`:

```python
PROVIDER_REGISTRY = {
    "gemini": "kresearch.providers.gemini.provider.GeminiProvider",
    "openai": "kresearch.providers.openai.provider.OpenaiProvider",  # ← add this
    ...
}
```

### Step 5: Add the SDK dependency

In `pyproject.toml`:

```toml
[project.optional-dependencies]
openai = ["openai>=1.0"]
```

### Step 6: Add the API key to config

In `config.py`, add:

```python
openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
```

### Verification

```bash
pip install -e ".[openai]"
export OPENAI_API_KEY=sk-...
kresearch --provider openai --model gpt-4o "test query"
kresearch --provider openai --list-models
```

**Zero changes** to the orchestrator, tools, system prompt, or UI.

---

## Adding a New Tool

### Step 1: Create the tool file

Create `src/kresearch/tools/your_tool.py`:

```python
"""Description of what this tool does."""

from __future__ import annotations
import asyncio
from kresearch.providers.types import ToolDeclaration

YOUR_TOOL_DECLARATION = ToolDeclaration(
    name="your_tool_name",
    description="Description the LLM sees when deciding whether to use this tool.",
    parameters={
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "What this param is."},
            "param2": {"type": "integer", "description": "What this param is."},
        },
        "required": ["param1"],
    },
)

async def handle_your_tool(args: dict, **ctx) -> dict:
    """Execute the tool. Must return a dict. Must never raise."""
    # Access shared state if needed:
    # state = ctx.get("state")   # ResearchState
    # provider = ctx.get("provider")  # ProviderInterface
    # config = ctx.get("config")  # KResearchConfig

    param1 = args.get("param1", "")
    param2 = args.get("param2", 10)

    # For blocking operations, use asyncio.to_thread():
    # result = await asyncio.to_thread(blocking_function, param1)

    try:
        # ... your logic ...
        return {"result": "some data", "status": "ok"}
    except Exception as e:
        return {"error": str(e)}
```

### Step 2: Register it

In `src/kresearch/tools/registry.py`, add to `create_default_registry()`:

```python
from kresearch.tools.your_tool import YOUR_TOOL_DECLARATION, handle_your_tool

# In the tools list:
("your_tool_name", handle_your_tool, YOUR_TOOL_DECLARATION),
```

### That's it

The agent will automatically see the new tool in its function declarations and can decide to call it. No changes to the orchestrator, system prompt, or any other file. If you want the agent to know specific strategies for using your tool, add guidance to the `## TOOL REFERENCE` section in `prompts.py`.

### Tool handler contract

- **Signature:** `async def handler(args: dict, **ctx) -> dict`
- **`args`:** The function arguments the LLM provided, as a plain dict.
- **`ctx`:** Keyword arguments injected by the orchestrator: `state` (ResearchState), `provider` (ProviderInterface), `config` (KResearchConfig).
- **Return:** Always a dict. On success, include whatever data is useful for the LLM. On failure, include `{"error": "description"}`.
- **Exceptions:** Catch them. The registry has a safety net, but explicit handling produces better error messages for the LLM.
- **Blocking I/O:** Wrap in `asyncio.to_thread()` to avoid blocking the event loop.

---

## Modifying the System Prompt

The system prompt lives in `src/kresearch/prompts.py` as `SYSTEM_TEMPLATE`. It is a Python format string with these placeholders, filled at runtime by `Orchestrator._build_system_prompt()`:

| Placeholder | Source |
|---|---|
| `{query}` | The user's research question |
| `{mind_map_summary}` | `state.mind_map.get_summary()` — compact text tree of all findings |
| `{gaps}` | `state.mind_map.get_gaps()` — topics with confidence < 0.3 |
| `{contradictions}` | Count of unresolved contradictions |
| `{source_count}` | Total sources across all mind map nodes |
| `{iteration}` | Current iteration number |
| `{max_iterations}` | Configured max, or "unlimited" |

The prompt is injected once at chat creation as the `system_instruction`. It is **not** rebuilt each iteration — the mind map state is the agent's persistent memory that carries forward through tool calls.

### Prompt structure

1. **Identity and mandate** — "You are KResearch, an autonomous deep research agent..."
2. **Five-phase methodology** — Decompose, Broad Search, Deep Reading, Verify, Synthesize
3. **Tool reference** — When and how to use each tool, with best practices
4. **Citation rules** — Non-negotiable; every factual claim must carry `[N]`
5. **Report format** — Required structure: Executive Summary, thematic sections, Contradictions, Limitations, Sources
6. **Quality standards** — Depth, specificity, structure, balance, honesty
7. **Current state** — Dynamic section with the placeholders above

When modifying the prompt, use `{{` and `}}` to include literal braces (since it's a Python format string). Test with a real query to verify the agent follows the updated instructions.

---

## Data Models

### ResearchState (`models/state.py`)

The top-level mutable object for one research session. Contains everything the orchestrator needs:

| Field | Type | Purpose |
|---|---|---|
| `query` | `str` | The original user query |
| `mind_map` | `MindMap` | Hierarchical findings tree |
| `task_graph` | `TaskGraph` | Sub-task tracking |
| `iteration` | `int` | Current loop iteration |
| `max_iterations` | `int` | Budget (0 = unlimited) |
| `actions_log` | `list[ActionLog]` | Timestamped log of every tool call |
| `token_usage` | `TokenUsage` | Cumulative input/output token counts |
| `subagent_results` | `list[str]` | Results from spawned sub-agents |
| `draft_requested` | `bool` | Set to `True` when `draft_report()` is called |

### MindMap (`models/mind_map.py`)

A tree where each node represents a research topic:

| Field | Type | Purpose |
|---|---|---|
| `MindMapNode.topic` | `str` | Topic name (e.g., "Quantum Hardware") |
| `MindMapNode.content` | `str` | Accumulated findings text |
| `MindMapNode.sources` | `list[Source]` | URLs + titles backing this topic |
| `MindMapNode.confidence` | `float` | 0.0-1.0, highest confidence assigned |
| `MindMapNode.children` | `list[MindMapNode]` | Sub-topics |
| `MindMapNode.contradictions` | `list[Contradiction]` | Conflicting claims |

Node lookup is case-insensitive. `find_or_create_node(topic)` searches the tree; if not found, creates a new child of the root.

### TaskGraph (`models/task_graph.py`)

Tracks sub-tasks for sub-agent spawning: `add_task()`, `complete_task()`, `fail_task()`, `get_pending()`.

---

## Testing

```bash
# Run all tests
pytest

# Stop on first failure, short traceback
pytest -x --tb=short

# Run a specific test file
pytest tests/test_mind_map.py

# Run with verbose output
pytest -v
```

### Test fixtures (`tests/conftest.py`)

| Fixture | Returns |
|---|---|
| `config` | `KResearchConfig(gemini_api_key="test-key")` |
| `mind_map` | `MindMap.create("test query")` |
| `state` | `ResearchState.create("test query", max_iterations=5)` |
| `sample_source` | `Source(url="https://example.com", title="Example")` |

### Integration testing

For live API tests, set `GOOGLE_API_KEY` and run:

```bash
kresearch --max-iterations 2 "What is quantum computing?"
```

This runs a real research loop limited to 2 iterations — enough to verify the full pipeline (search, read, update findings, draft report) without excessive API usage.

---

## Web UI Architecture

The Web UI wraps the existing Orchestrator without modifying its core logic. The key pattern is `UIProtocol` — a `typing.Protocol` that defines the async display contract.

### The UIProtocol Pattern

Both `ConsoleUI` (terminal) and `WebUI` (browser) implement the same interface structurally:

```python
class UIProtocol(Protocol):
    async def start_research(self, query: str) -> None: ...
    async def log_action(self, tool: str, desc: str, ...) -> None: ...
    async def log_thinking(self, text: str) -> None: ...
    async def log_result_summary(self, tool: str, result: dict) -> None: ...
    async def update_stats(self, iteration: int, sources: int, tokens: int) -> None: ...
    async def show_report(self, text: str) -> None: ...
    async def show_total_time(self, elapsed: float, state: object) -> None: ...
    async def stop(self) -> None: ...
    async def print(self, msg: str, **kw: object) -> None: ...
```

- `ConsoleUI` calls `rich.Console.print()` synchronously inside each `async def`.
- `WebUI` serializes events as `WSEvent` JSON and sends via `WebSocket.send_json()`.

### WebSocket Flow

1. Browser connects to `/ws`.
2. Browser sends `{"type": "start", "query": "...", "config": {...}}`.
3. Server creates a `ResearchSession` with its own `WebUI`, `Orchestrator`, and `asyncio.Task`.
4. As the Orchestrator runs, `WebUI` streams events: `action`, `thinking`, `stats`, `log`, `report`, `stopped`.
5. Browser can send `{"type": "interrupt", "message": "..."}` at any time — injected into the Orchestrator's input queue.
6. On completion, the report is saved to SQLite and the session cleans up.

### Adding Web UI Features

The REST API (`routes.py`) and WebSocket handler (`ws.py`) are separate. To add a new REST endpoint, add a route to `routes.py`. To add a new real-time event type, add a method to `WebUI` and handle the new event type in `index.html`'s `handleEvent()` switch.

---

## Pull Request Guidelines

1. **Keep changes focused.** One feature or fix per PR. If a PR touches the orchestrator, the system prompt, and two tools, it should probably be three PRs.

2. **Respect the 150-line limit.** If your change pushes a file over 150 lines, refactor it into smaller modules.

3. **Test your changes.** Add unit tests for new tools, providers, or model changes. For orchestrator changes, verify with a live `--max-iterations 2` run.

4. **Lint and type-check before pushing.**
   ```bash
   ruff check src/
   mypy src/
   ```

5. **Follow existing patterns.** Tool handlers return dicts. Providers implement the abstract interface. Models use Pydantic. Blocking I/O uses `asyncio.to_thread()`.

6. **Do not hardcode model IDs** in agent logic. Models are configuration — they go in `config.py` defaults or provider-level `DEFAULT_MODEL` constants.

7. **Do not add provider-specific tool logic.** All tools must work identically regardless of which LLM provider is active. If you need provider-specific behaviour, it belongs in the provider layer.

8. **Update the system prompt** if your new tool needs the agent to know specific usage strategies. The agent only knows what the `ToolDeclaration.description` and the system prompt tell it.

9. **Document architectural decisions** in your PR description. If you chose approach A over approach B, explain why.
